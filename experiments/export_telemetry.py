"""
Export recorded resource-consumption readings to CSV for statistical analysis.

Chapter 3 evaluates system efficiency from "CPU usage (%) and RAM consumption
(MB) tracked at one-minute intervals", then applies the arithmetic mean, sample
variance and an independent-samples t-test. This script produces the flat table
those computations run on.

It does not perform the t-test — it only prepares the data. Per-group descriptive
statistics are printed so you can sanity-check a run finished cleanly (n, mean,
variance) before doing the inferential work in SPSS, Excel or scipy.

Usage:
    python experiments/export_telemetry.py
    python experiments/export_telemetry.py --scenario arp_flood_1000pps
    python experiments/export_telemetry.py --out ~/Desktop/run1.csv
"""

import argparse
import csv
import os
import sqlite3
import statistics
import sys

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "admin-backend", "sentinet.db")

COLUMNS = [
    "ts", "timestamp", "source", "node", "mac",
    "cpu_percent", "ram_mb", "ram_percent",
    "protected", "scenario", "system",
]


def fetch(scenario=None):
    if not os.path.exists(DB_PATH):
        sys.exit(f"Database not found at {DB_PATH}. Start the relay at least once first.")

    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        if "telemetry_readings" not in tables:
            sys.exit(
                "No telemetry_readings table yet.\n"
                "The relay creates it on startup — run it, let it sample, then retry."
            )

        sql = f"SELECT {', '.join(COLUMNS)} FROM telemetry_readings"
        params = ()
        if scenario:
            sql += " WHERE scenario = ?"
            params = (scenario,)
        sql += " ORDER BY ts ASC"
        return [dict(r) for r in conn.execute(sql, params)]
    finally:
        conn.close()


def describe(rows):
    """Per-group n, mean and sample variance — the inputs to the t-test."""
    groups = {}
    for r in rows:
        key = (r["scenario"] or "unlabelled", r["system"] or "sentinet", r["source"])
        groups.setdefault(key, []).append(r)

    print(f"\n{'scenario':<24}{'system':<12}{'source':<8}{'n':>5}"
          f"{'cpu mean':>10}{'cpu var':>10}{'ram mean':>10}{'ram var':>10}")
    print("-" * 89)

    for key in sorted(groups):
        g = groups[key]
        cpu = [x["cpu_percent"] for x in g if x["cpu_percent"] is not None]
        ram = [x["ram_mb"] for x in g if x["ram_mb"] is not None]

        def stats(vals):
            if not vals:
                return 0.0, 0.0
            mean = statistics.fmean(vals)
            # Sample variance (n-1), matching the paper's formula. Undefined for n=1.
            var = statistics.variance(vals) if len(vals) > 1 else 0.0
            return mean, var

        cm, cv = stats(cpu)
        rm, rv = stats(ram)
        print(f"{key[0]:<24}{key[1]:<12}{key[2]:<8}{len(g):>5}"
              f"{cm:>10.2f}{cv:>10.2f}{rm:>10.2f}{rv:>10.2f}")

    print("\n  cpu = percent, ram = MB. Variance is the sample variance (n-1).")
    if any(len(g) < 2 for g in groups.values()):
        print("  NOTE: a group has fewer than 2 readings — variance is meaningless there.")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scenario", help="only this scenario label")
    ap.add_argument("--out", help="output CSV path")
    args = ap.parse_args()

    rows = fetch(args.scenario)
    if not rows:
        where = f" for scenario '{args.scenario}'" if args.scenario else ""
        sys.exit(
            f"No readings found{where}.\n"
            "Readings are written every TELEMETRY_SAMPLE_INTERVAL seconds (default 60)\n"
            "while the relay runs, so a short run may not have produced any yet."
        )

    out = args.out or os.path.join(
        os.path.dirname(__file__),
        f"telemetry_{args.scenario or 'all'}.csv",
    )
    out = os.path.expanduser(out)

    with open(out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)

    print(f"Wrote {len(rows)} readings to {out}")
    describe(rows)


if __name__ == "__main__":
    main()
