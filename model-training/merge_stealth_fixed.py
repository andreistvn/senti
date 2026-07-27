"""
merge_stealth_fixed.py

Simplified merge for the case where every new session has exactly the same
row count (here: 120 rows/session, 10 sessions = 1200 rows total).

Assumes rows in the new CSV are in session order (session 1's 120 rows,
then session 2's 120 rows, etc.) -- true as long as the file wasn't
reordered/shuffled after collection.

Splits: first 8 sessions (rows 1-960) -> train
        last 2 sessions  (rows 961-1200) -> test
Matches your existing 8-train/2-test-per-scenario pattern.

Usage:
    python merge_stealth_fixed.py \\
        --new-data training_data_stealth.csv \\
        --existing-train train.csv \\
        --existing-test test.csv \\
        --output-train train_updated.csv \\
        --output-test test_updated.csv
"""

import argparse
import csv

ROWS_PER_SESSION = 120
TRAIN_SESSIONS = 8
TEST_SESSIONS = 2


def read_csv_rows(path):
    with open(path, newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
        rows = list(reader)
    return header, rows


def write_csv_rows(path, header, rows):
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--new-data", required=True)
    parser.add_argument("--existing-train", required=True)
    parser.add_argument("--existing-test", required=True)
    parser.add_argument("--output-train", required=True)
    parser.add_argument("--output-test", required=True)
    args = parser.parse_args()

    new_header, new_rows = read_csv_rows(args.new_data)

    expected_total = (TRAIN_SESSIONS + TEST_SESSIONS) * ROWS_PER_SESSION
    if len(new_rows) != expected_total:
        print(f"WARNING: expected {expected_total} rows, found {len(new_rows)}. "
              f"Check the file wasn't altered before proceeding.")

    train_cutoff = TRAIN_SESSIONS * ROWS_PER_SESSION  # 960
    new_train_rows = new_rows[:train_cutoff]
    new_test_rows = new_rows[train_cutoff:]

    print(f"New rows -> train: {len(new_train_rows)}, test: {len(new_test_rows)}")

    existing_train_header, existing_train_rows = read_csv_rows(args.existing_train)
    existing_test_header, existing_test_rows = read_csv_rows(args.existing_test)

    updated_train = existing_train_rows + new_train_rows
    updated_test = existing_test_rows + new_test_rows

    write_csv_rows(args.output_train, existing_train_header, updated_train)
    write_csv_rows(args.output_test, existing_test_header, updated_test)

    print(f"Wrote {len(updated_train)} rows to {args.output_train}")
    print(f"Wrote {len(updated_test)} rows to {args.output_test}")

    label_idx = existing_train_header.index("label")
    for name, rows in [("train", updated_train), ("test", updated_test)]:
        counts = {}
        for r in rows:
            counts[r[label_idx]] = counts.get(r[label_idx], 0) + 1
        print(f"{name} label distribution: {counts}")


if __name__ == "__main__":
    main()
