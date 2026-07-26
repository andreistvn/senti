"""
SentiNet Tier-2 (Detective) — Random Forest Behavioral Classifier
Training pipeline, following Chapter 3 Methodology
("Model Training and Joblib Serialization Pipeline")

Expects two files in the same directory as this script:
    train.csv
    test.csv

Both must contain the 8 feature columns + label:
    arp_request_rate, arp_reply_rate, req_to_reply_ratio,
    unique_ip_per_mac, iat_mean, iat_variance,
    packet_burstiness, gratuitous_arp_count, label
"""

import pandas as pd
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    accuracy_score,
    recall_score,
)

# Explicit mapping so "malicious" is always the positive class (1),
# regardless of alphabetical ordering of the string labels.
# Adjust the key names here if your label column uses different strings.
LABEL_MAP = {
    "arp_spoofing": 1,  # malicious / positive class
    "normal": 0,        # benign / negative class
}

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
LABEL_COLUMN = "label"
DECISION_THRESHOLD = 0.50
MODEL_OUTPUT_PATH = "sentinet_rf_model.joblib"
ENCODER_OUTPUT_PATH = "sentinet_label_encoder.joblib"


def load_data(train_path="train.csv", test_path="test.csv"):
    train_df = pd.read_csv(train_path)
    test_df = pd.read_csv(test_path)
    return train_df, test_df


def encode_labels(train_df, test_df):
    """Convert string labels (normal / arp_spoofing) into 0/1 for the classifier,
    using the explicit LABEL_MAP so malicious traffic is always class 1."""
    unexpected = set(train_df[LABEL_COLUMN].unique()) - set(LABEL_MAP.keys())
    if unexpected:
        raise ValueError(
            f"Found label(s) not in LABEL_MAP: {unexpected}. "
            f"Update LABEL_MAP at the top of this script to include them."
        )

    y_train = train_df[LABEL_COLUMN].map(LABEL_MAP).to_numpy()
    y_test = test_df[LABEL_COLUMN].map(LABEL_MAP).to_numpy()

    print(f"Label encoding (explicit): {LABEL_MAP}")
    return y_train, y_test, LABEL_MAP


def main():
    print("Loading train.csv and test.csv ...")
    train_df, test_df = load_data()

    X_train = train_df[FEATURE_COLUMNS]
    X_test = test_df[FEATURE_COLUMNS]

    y_train, y_test, label_map = encode_labels(train_df, test_df)

    # --- Step 2: Classifier Initialization (locked hyperparameters) ---
    clf = RandomForestClassifier(
        n_estimators=100,
        max_depth=12,
        class_weight="balanced",
        random_state=42,
    )

    # --- Step 3: Supervised Model Fitting with 5-fold stratified CV ---
    print("\nRunning 5-fold stratified cross-validation on training data...")
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cv_scores = cross_val_score(clf, X_train, y_train, cv=cv, scoring="accuracy")
    print(f"CV accuracy per fold: {cv_scores}")
    print(f"CV accuracy mean: {cv_scores.mean():.4f}  std: {cv_scores.std():.4f}")

    print("\nFitting final model on full training set...")
    clf.fit(X_train, y_train)

    # --- Step 4: Validation and Threshold Calibration ---
    print(f"\nEvaluating on held-out test set (threshold = {DECISION_THRESHOLD})...")
    probs = clf.predict_proba(X_test)[:, 1]  # P(malicious)
    preds = (probs >= DECISION_THRESHOLD).astype(int)

    # --- Step 5: Performance Metric Auditing ---
    acc = accuracy_score(y_test, preds)
    detection_rate = recall_score(y_test, preds)  # TP / (TP + FN)
    cm = confusion_matrix(y_test, preds)
    tn, fp, fn, tp = cm.ravel()
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0

    # Order target names by their numeric code (0, 1, ...) for the report
    ordered_names = [name for name, code in sorted(label_map.items(), key=lambda kv: kv[1])]

    print("\n--- Classification Report ---")
    print(classification_report(y_test, preds, target_names=ordered_names))

    print("--- Confusion Matrix ---")
    print(f"TP={tp}  TN={tn}  FP={fp}  FN={fn}")

    print("\n--- Summary Metrics ---")
    print(f"Accuracy:        {acc * 100:.2f}%")
    print(f"Detection Rate:  {detection_rate * 100:.2f}%")
    print(f"False Positive Rate: {fpr * 100:.2f}%")

    # --- Step 5 (cont): Serialize final model to disk ---
    joblib.dump(clf, MODEL_OUTPUT_PATH)
    joblib.dump(label_map, ENCODER_OUTPUT_PATH)
    print(f"\nSaved trained model to: {MODEL_OUTPUT_PATH}")
    print(f"Saved label map to: {ENCODER_OUTPUT_PATH}")
    print("\nDone. Bundle both .joblib files with the SentiNet agent installer.")


if __name__ == "__main__":
    main()