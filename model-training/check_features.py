import joblib

# Load your newly trained model
model = joblib.load("sentinet_rf_model.joblib")

# The exact 8 features from your methodology
features = [
    "arp_request_rate", "arp_reply_rate", "req_to_reply_ratio",
    "unique_ip_per_mac", "iat_mean", "iat_variance",
    "packet_burstiness", "gratuitous_arp_count"
]

# Extract and sort the weights
importances = model.feature_importances_
print("\n--- SENTINET FEATURE IMPORTANCES ---")
for feature, weight in sorted(zip(features, importances), key=lambda x: x[1], reverse=True):
    print(f"{feature:<22}: {weight * 100:.2f}%")