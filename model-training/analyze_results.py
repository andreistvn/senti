"""
analyze_results.py

Generates the concrete evidence artifacts for defending your accuracy numbers:

  1. Decision tree depth comparison (depth=1 vs depth=3 vs depth=5) -- shows
     whether a single feature can still trivially separate the classes, or
     whether it now takes a deeper, multi-feature tree.
  2. Prints the actual tree structure at depth=3, so you can see/screenshot
     which features and thresholds it's using.
  3. Finds the actual false positive(s) from your saved model's predictions
     on test.csv, and prints their feature values side-by-side with typical
     normal and attack windows, so you can discuss the specific case.

Usage:
    python3 analyze_results.py

Expects in the same folder:
    train.csv, test.csv
    sentinet_rf_model.joblib, sentinet_label_encoder.joblib
"""

import pandas as pd
import joblib
from sklearn.tree import DecisionTreeClassifier, export_text
from sklearn.model_selection import train_test_split

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


def decision_tree_comparison(train_df, test_df, label_map):
    print("=" * 60)
    print("PART 1: Decision Tree Depth Comparison")
    print("=" * 60)
    print(
        "This shows whether a single feature (or a shallow rule) can still\n"
        "trivially separate the classes, or whether real multi-feature\n"
        "reasoning is now required.\n"
    )

    X_train = train_df[FEATURE_COLUMNS]
    y_train = train_df[LABEL_COLUMN].map(label_map)
    X_test = test_df[FEATURE_COLUMNS]
    y_test = test_df[LABEL_COLUMN].map(label_map)

    for depth in [1, 2, 3, 4, 5]:
        dt = DecisionTreeClassifier(max_depth=depth, random_state=42)
        dt.fit(X_train, y_train)
        acc = dt.score(X_test, y_test)
        print(f"  max_depth={depth}: test accuracy = {acc*100:.2f}%")

    print("\n--- Tree structure at depth=3 (for your thesis figure/screenshot) ---")
    dt3 = DecisionTreeClassifier(max_depth=3, random_state=42).fit(X_train, y_train)
    print(export_text(dt3, feature_names=FEATURE_COLUMNS))


def find_false_positives(test_df, label_map, model_path, label_map_path):
    print("=" * 60)
    print("PART 2: False Positive Inspection")
    print("=" * 60)

    clf = joblib.load(model_path)
    saved_label_map = joblib.load(label_map_path)

    X_test = test_df[FEATURE_COLUMNS]
    y_test = test_df[LABEL_COLUMN].map(saved_label_map)

    probs = clf.predict_proba(X_test)[:, 1]
    preds = (probs >= DECISION_THRESHOLD).astype(int)

    test_df = test_df.copy()
    test_df["predicted"] = preds
    test_df["predicted_prob_attack"] = probs
    test_df["true_label_code"] = y_test.values

    false_positives = test_df[(test_df["true_label_code"] == 0) & (test_df["predicted"] == 1)]

    if len(false_positives) == 0:
        print("No false positives found in this run (model may have changed slightly, or threshold differs).")
        return

    print(f"Found {len(false_positives)} false positive(s):\n")
    for idx, row in false_positives.iterrows():
        print(f"--- False Positive (row index {idx}) ---")
        for col in FEATURE_COLUMNS:
            print(f"  {col:<22}: {row[col]}")
        print(f"  predicted_prob_attack: {row['predicted_prob_attack']:.4f}  (threshold=0.50)")
        print()

    print("--- For comparison: typical NORMAL window (median values) ---")
    normal_rows = test_df[test_df["true_label_code"] == 0]
    for col in FEATURE_COLUMNS:
        print(f"  {col:<22}: {normal_rows[col].median()}")

    print("\n--- For comparison: typical ARP_SPOOFING window (median values) ---")
    attack_rows = test_df[test_df["true_label_code"] == 1]
    for col in FEATURE_COLUMNS:
        print(f"  {col:<22}: {attack_rows[col].median()}")


def main():
    train_df = pd.read_csv("train.csv")
    test_df = pd.read_csv("test.csv")

    label_map = {"arp_spoofing": 1, "normal": 0}

    decision_tree_comparison(train_df, test_df, label_map)
    print()
    find_false_positives(test_df, label_map, "sentinet_rf_model.joblib", "sentinet_label_encoder.joblib")


if __name__ == "__main__":
    main()