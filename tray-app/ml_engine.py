import os
import time
import threading
import pandas as pd
import joblib
from collections import defaultdict

# Absolute paths to the bundled model files
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, 'ml_models', 'sentinet_rf_model.joblib')
ENCODER_PATH = os.path.join(BASE_DIR, 'ml_models', 'sentinet_label_encoder.joblib')
# Held-out test set (a copy of model-training/test.csv), for evaluate() below.
TEST_DATA_PATH = os.path.join(BASE_DIR, 'ml_models', 'test.csv')
# Score at or above which Tier 2 classifies a MAC as malicious.
DECISION_THRESHOLD = 0.50

# Must match FEATURE_COLUMNS in model-training/train_sentinet.py, in order -
# the model was fit on a DataFrame with these column names, and predict_proba
# warns if X lacks them.
FEATURE_COLUMNS = [
    "arp_request_rate",
    "arp_reply_rate",
    "req_to_reply_ratio",
    "unique_ip_per_mac",
    "iat_mean",
    "iat_variance",
    "packet_burstiness",
    "gratuitous_arp_count",
]

class MLEngine:
    """
    Tier-2 Detective Engine.
    Maintains a 5-second sliding window per MAC address and extracts
    behavioral features to feed into the Random Forest classifier.
    """
    def __init__(self):
        self.window_size = 5.0  # seconds
        self.lock = threading.Lock()
        
        # State: MAC -> list of packet dicts
        self.history = defaultdict(list)
        
        print(f"[MLEngine] Loading model from {MODEL_PATH}")
        try:
            self.model = joblib.load(MODEL_PATH)
            print("[MLEngine] Model loaded successfully.")
        except Exception as e:
            print(f"[MLEngine] WARNING: Failed to load model: {e}")
            self.model = None

    def evaluate(self):
        """
        Score the loaded model against the held-out test set (SOP 2).

        Same procedure as model-training/evaluate_sentinet.py. Run once at
        start-up and sent to the relay with this agent's registration, so the
        admin dashboard shows the figures for the model this agent is actually
        running. Returns None if the model or the test set is unavailable.
        """
        if self.model is None:
            return None
        try:
            label_map = joblib.load(ENCODER_PATH)
            test_df = pd.read_csv(TEST_DATA_PATH)
            y_true = test_df['label'].map(label_map).to_numpy()
            probs = self.model.predict_proba(test_df[FEATURE_COLUMNS])[:, 1]
            preds = (probs >= DECISION_THRESHOLD).astype(int)
        except Exception as e:
            print(f"[MLEngine] WARNING: Could not evaluate the model: {e}")
            return None

        tp = int(((preds == 1) & (y_true == 1)).sum())
        fp = int(((preds == 1) & (y_true == 0)).sum())
        tn = int(((preds == 0) & (y_true == 0)).sum())
        fn = int(((preds == 0) & (y_true == 1)).sum())
        n = tp + fp + tn + fn
        return {
            "threshold": DECISION_THRESHOLD,
            "n": n,
            "truePositives": tp,
            "falsePositives": fp,
            "trueNegatives": tn,
            "falseNegatives": fn,
            "accuracy": (tp + tn) / n * 100 if n else None,
            "detectionRate": tp / (tp + fn) * 100 if (tp + fn) else None,
            "falsePositiveRate": fp / (fp + tn) * 100 if (fp + tn) else None,
        }

    def window_count(self, src_mac: str) -> int:
        """Packets from this MAC currently in its sliding window."""
        with self.lock:
            return len(self.history.get(src_mac, ()))

    def window_span(self, src_mac: str) -> float:
        """Seconds from the oldest to the newest packet in this MAC's window."""
        with self.lock:
            window = self.history.get(src_mac)
            return (window[-1]['timestamp'] - window[0]['timestamp']) if window else 0.0

    def process_packet(self, src_mac: str, op: int, src_ip: str, dst_ip: str) -> float:
        """
        Ingests a packet, updates the sliding window, extracts features, 
        and returns the malicious probability score [0.0, 1.0].
        """
        self.observe(src_mac, op, src_ip, dst_ip)
        return self.score(src_mac)

    def observe(self, src_mac: str, op: int, src_ip: str, dst_ip: str) -> None:
        """
        Add a packet to this MAC's sliding window without scoring it. Used for
        a MAC just blocked, whose detection confidence is finalized over its
        full window (see the daemon's finalize_confidence).
        """
        now = time.time()
        with self.lock:
            self.history[src_mac].append({
                'timestamp': now,
                'op': op,
                'src_ip': src_ip,
                'dst_ip': dst_ip
            })
            self._slide_locked(src_mac, now)

    def _slide_locked(self, src_mac: str, now: float) -> list:
        """Drop packets older than the window from this MAC's history."""
        window = self.history[src_mac]
        while window and (now - window[0]['timestamp']) > self.window_size:
            window.pop(0)
        return window

    def score(self, src_mac: str) -> float:
        """The malicious probability [0.0, 1.0] of this MAC's current window."""
        with self.lock:
            window = self._slide_locked(src_mac, time.time())

            # Wait for sufficient density before scoring
            if len(window) < 3 or self.model is None:
                return 0.0

            # Extract 8-dimensional feature vector
            features = self._extract_features(window)

        try:
            # A DataFrame with the training-time column names avoids sklearn's
            # "X does not have valid feature names" warning on every prediction.
            X = pd.DataFrame([features], columns=FEATURE_COLUMNS)

            # predict_proba returns an array of shape (n_samples, n_classes)
            # Typically class 0 is benign, class 1 is malicious
            probs = self.model.predict_proba(X)[0]

            # If the model has two classes, return the probability of the positive class
            return float(probs[1]) if len(probs) > 1 else 0.0
        except Exception as e:
            print(f"[MLEngine] Inference Exception: {e}")
            return 0.0

    def _extract_features(self, window: list) -> list:
        """
        Calculates the 8 behavioral features:
        1. ARP Request Rate
        2. ARP Reply Rate
        3. Request-to-Reply Ratio
        4. Inter-arrival Mean
        5. Inter-arrival Variance
        6. Packet Burstiness
        7. Unique IP-per-MAC Count
        8. Gratuitous ARP Count
        """
        requests = 0
        replies = 0
        gratuitous = 0
        unique_ips = set()
        timestamps = []
        
        for pkt in window:
            timestamps.append(pkt['timestamp'])
            unique_ips.add(pkt['src_ip'])
            
            if pkt['op'] == 1:
                requests += 1
            elif pkt['op'] == 2:
                replies += 1
                # A reply where src_ip == dst_ip is a common gratuitous signature
                if pkt['src_ip'] == pkt['dst_ip']:
                    gratuitous += 1
                    
        req_rate = requests / self.window_size
        rep_rate = replies / self.window_size
        req_rep_ratio = requests / max(replies, 1.0)
        
        # Calculate inter-arrival timings
        diffs = [timestamps[i] - timestamps[i-1] for i in range(1, len(timestamps))]
        if diffs:
            ia_mean = sum(diffs) / len(diffs)
            # Sample variance (n-1), as the training data computed it.
            ia_var = sum((x - ia_mean)**2 for x in diffs) / (len(diffs) - 1) if len(diffs) > 1 else 0.0
        else:
            ia_mean = 0.0
            ia_var = 0.0
            
        # Burstiness: sample variance of the packet counts in the window's five
        # 1-second sub-intervals, matching how the training data defined it
        # (model-training/README.md). Evenly paced traffic scores near zero; the
        # same number of packets arriving in one spike scores high. Sub-intervals
        # are counted back from the newest packet, and empty ones count as zero.
        sub_intervals = int(self.window_size)
        counts = [0] * sub_intervals
        newest = timestamps[-1]
        for t in timestamps:
            counts[min(int(newest - t), sub_intervals - 1)] += 1
        mean_count = len(timestamps) / sub_intervals
        burstiness = sum((c - mean_count) ** 2 for c in counts) / (sub_intervals - 1)
        
        unique_ip_count = len(unique_ips)
        
        return [
            req_rate,
            rep_rate,
            req_rep_ratio,
            unique_ip_count,
            ia_mean,
            ia_var,
            burstiness,
            gratuitous
        ]
