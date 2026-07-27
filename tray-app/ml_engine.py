import os
import time
import threading
import numpy as np
import joblib
from collections import defaultdict

# Absolute paths to the bundled model files
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, 'ml_models', 'sentinet_rf_model.joblib')
ENCODER_PATH = os.path.join(BASE_DIR, 'ml_models', 'sentinet_label_encoder.joblib')

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
            # Reshape into (1, 8) 2D array
            X = np.array(features).reshape(1, -1)
            
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
            ia_var = sum((x - ia_mean)**2 for x in diffs) / len(diffs)
        else:
            ia_mean = 0.0
            ia_var = 0.0
            
        # Calculate burstiness (max packets in any given 1-second interval)
        buckets = defaultdict(int)
        for t in timestamps:
            buckets[int(t)] += 1
        burstiness = max(buckets.values()) if buckets else 0
        
        unique_ip_count = len(unique_ips)
        
        return [
            req_rate,
            rep_rate,
            req_rep_ratio,
            ia_mean,
            ia_var,
            burstiness,
            unique_ip_count,
            gratuitous
        ]
