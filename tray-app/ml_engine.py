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

    def process_packet(self, src_mac: str, op: int, src_ip: str, dst_ip: str) -> float:
        """
        Ingests a packet, updates the sliding window, extracts features, 
        and returns the malicious probability score [0.0, 1.0].
        """
        now = time.time()
        
        with self.lock:
            # 1. Record the new packet
            self.history[src_mac].append({
                'timestamp': now,
                'op': op,
                'src_ip': src_ip,
                'dst_ip': dst_ip
            })
            
            # 2. Slide the window: remove packets older than 5 seconds
            window = self.history[src_mac]
            while window and (now - window[0]['timestamp']) > self.window_size:
                window.pop(0)
                
            # 3. Wait for sufficient density before scoring
            if len(window) < 3 or self.model is None:
                return 0.0
                
            # 4. Extract 8-dimensional feature vector
            features = self._extract_features(window)
            
        # 5. Execute Inference (outside the history lock if possible, but fine here since model.predict is fast)
        try:
            # A DataFrame with the training-time column names avoids sklearn's
            # "X does not have valid feature names" warning on every prediction.
            X = pd.DataFrame([features], columns=FEATURE_COLUMNS)

            # predict_proba returns an array of shape (n_samples, n_classes)
            # Typically class 0 is benign, class 1 is malicious
            probs = self.model.predict_proba(X)[0]
            
            # If the model has two classes, return the probability of the positive class
            score = float(probs[1]) if len(probs) > 1 else 0.0
            return score
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
