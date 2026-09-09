import pandas as pd
import joblib
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    accuracy_score,
    recall_score
)

# 1. Configuration
MODEL_PATH = "sentinet_rf_model.joblib"
ENCODER_PATH = "sentinet_label_encoder.joblib"
TEST_DATA_PATH = "test.csv"
DECISION_THRESHOLD = 0.50

FEATURE_COLUMNS = [
    "arp_request_rate", "arp_reply_rate", "req_to_reply_ratio",
    "unique_ip_per_mac", "iat_mean", "iat_variance",
    "packet_burstiness", "gratuitous_arp_count"
]

def main():
    print(f"Loading saved model from {MODEL_PATH}...")
    try:
        model = joblib.load(MODEL_PATH)
        label_map = joblib.load(ENCODER_PATH)
    except FileNotFoundError:
        print("Error: Could not find the .joblib files. Have you trained the model yet?")
        return

    print(f"Loading test dataset from {TEST_DATA_PATH}...")
    try:
        test_df = pd.read_csv(TEST_DATA_PATH)
    except FileNotFoundError:
        print(f"Error: Could not find {TEST_DATA_PATH}.")
        return

    # 2. Prepare the data
    X_test = test_df[FEATURE_COLUMNS]
    y_test = test_df['label'].map(label_map).to_numpy()

    # 3. Execute Inference (No training happens here!)
    print(f"\nExecuting inference on {len(test_df)} windows (threshold = {DECISION_THRESHOLD})...")
    probs = model.predict_proba(X_test)[:, 1]  # Get probability of class 1 (malicious)
    preds = (probs >= DECISION_THRESHOLD).astype(int)

    # 4. Calculate Metrics
    acc = accuracy_score(y_test, preds)
    detection_rate = recall_score(y_test, preds)
    cm = confusion_matrix(y_test, preds)
    tn, fp, fn, tp = cm.ravel()
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0

    ordered_names = [name for name, code in sorted(label_map.items(), key=lambda kv: kv[1])]

    # 5. Print the Report
    print("\n--- STANDALONE EVALUATION REPORT ---")
    print(classification_report(y_test, preds, target_names=ordered_names))
    
    print("--- CONFUSION MATRIX ---")
    print(f"TP={tp}  TN={tn}  FP={fp}  FN={fn}")
    
    print("\n--- SUMMARY METRICS ---")
    print(f"Accuracy:            {acc * 100:.2f}%")
    print(f"Detection Rate:      {detection_rate * 100:.2f}%")
    print(f"False Positive Rate: {fpr * 100:.2f}%")

if __name__ == "__main__":
    main()