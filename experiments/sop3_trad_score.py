#!/usr/bin/env python3
"""Add the traditional-IDPS (Snort) batch to the merged SOP 3 Tables 20-22.

    python3 sop3_trad_score.py --tables <dir with Table20/21 CSVs> \
        --trad <dir with S2/ and S3/ of T##_blocks.csv> \
        --nodeb <Kali B blocks.csv> --attacker <MAC> [--out <dir>]

Inputs
  <trad>/S2/T01_blocks.csv ...   one file per Kali A trial (sop3_trad_trial.sh)
  <trad>/S3/T01_blocks.csv ...
  --nodeb                        Kali B's /var/log/tidps/blocks.csv from the run
                                 that stayed up through the whole batch

What it writes (into --out, default = --tables; originals are left untouched
unless --out equals --tables):
  Table20  Trad. IDPS t_detected / t_enforced / Response Time filled per row.
           The k-th Snort trial of a scenario sits beside the k-th SentiNet
           trial of that scenario; the two systems ran separately, so rows are
           side by side, not paired. Summary rows for Trad. are added.
  Table21  Trad. IDPS Cross-Node TTB = "Not blocked" for every row when Kali B
           never blocked the attacker, with a summary count.
  Table22  Welch t-tests (unequal variances), SentiNet vs Trad., for Local
           Response Time and, as a supplementary row, First-Packet-to-Block.
           Cross-node TTB is reported as not testable.

Snort's response time is t_enforced - t_detected, where t_detected is the
capture time of the alerting packet (Snort's own timestamp) and t_enforced is
when the nft drop was in place, both on Kali A's clock.
"""
import argparse
import csv
import glob
import math
import os
import statistics as st


# ---------- Student t two-sided p-value without scipy ----------
def _betacf(a, b, x):
    MAXIT, EPS, FPMIN = 300, 3e-14, 1e-300
    qab, qap, qam = a + b, a + 1, a - 1
    c, d = 1.0, 1 - qab * x / qap
    d = 1 / (d if abs(d) > FPMIN else FPMIN)
    h = d
    for m in range(1, MAXIT + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1 + aa * d; d = 1 / (d if abs(d) > FPMIN else FPMIN)
        c = 1 + aa / c; c = c if abs(c) > FPMIN else FPMIN
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1 + aa * d; d = 1 / (d if abs(d) > FPMIN else FPMIN)
        c = 1 + aa / c; c = c if abs(c) > FPMIN else FPMIN
        de = d * c
        h *= de
        if abs(de - 1) < EPS:
            break
    return h


def _betainc(a, b, x):
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    lbt = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log(1 - x)
    if x < (a + 1) / (a + b + 2):
        return math.exp(lbt) * _betacf(a, b, x) / a
    return 1 - math.exp(lbt) * _betacf(b, a, 1 - x) / b


def t_two_sided_p(t, df):
    return _betainc(df / 2, 0.5, df / (df + t * t))


def welch(a, b):
    if len(a) < 2 or len(b) < 2:
        return None
    m1, m2, v1, v2, n1, n2 = st.mean(a), st.mean(b), st.variance(a), st.variance(b), len(a), len(b)
    se2 = v1 / n1 + v2 / n2
    if se2 == 0:
        return None
    t = (m1 - m2) / math.sqrt(se2)
    df = se2 ** 2 / ((v1 / n1) ** 2 / (n1 - 1) + (v2 / n2) ** 2 / (n2 - 1))
    return m1, m2, v1, v2, t, df, t_two_sided_p(t, df)


def p95(v):
    s = sorted(v)
    k = (len(s) - 1) * 0.95
    lo = math.floor(k); hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def fmt(x, n=2):
    return "" if x is None else f"{x:.{n}f}"


def summary_row(name, group, v):
    if not v:
        return [name, group, 0, "N/A"]
    sd = st.stdev(v) if len(v) > 1 else 0.0
    return [name, group, len(v), fmt(st.mean(v)), fmt(sd), fmt(p95(v)), fmt(st.median(v))]


def read_table(path):
    """Split a merged table into header, trial rows, and the rest (summary)."""
    with open(path, encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))
    header = rows[0]
    body, tail = [], []
    for r in rows[1:]:
        if not tail and r and r[0].isdigit():
            body.append(r)
        else:
            tail.append(r)
    return header, body, tail


def load_trad(trad_dir, attacker):
    out = {}
    for scen in ("S2", "S3"):
        trials = []
        for p in sorted(glob.glob(os.path.join(trad_dir, scen, "T*_blocks.csv"))):
            with open(p, encoding="utf-8-sig") as f:
                hit = next((r for r in csv.DictReader(f) if (r.get("mac") or "").lower() == attacker), None)
            if not hit:
                print(f"WARNING: {p} has no block of {attacker}; skipped.")
                continue
            try:
                td, te = float(hit["t_detected_ms"]), float(hit["t_enforced_ms"])
            except (TypeError, ValueError):
                print(f"WARNING: {p} has an unreadable timestamp; skipped.")
                continue
            if math.isnan(td) or math.isnan(te):
                print(f"WARNING: {p} has a NaN timestamp (Snort time not parsed); skipped.")
                continue
            trials.append({"file": os.path.basename(p), "t_det": td, "t_enf": te, "resp": te - td})
        out[scen] = trials
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tables", required=True)
    ap.add_argument("--trad", required=True)
    ap.add_argument("--nodeb", required=True)
    ap.add_argument("--attacker", required=True)
    ap.add_argument("--out")
    a = ap.parse_args()
    att = a.attacker.lower()
    out = a.out or a.tables
    os.makedirs(out, exist_ok=True)

    trad = load_trad(a.trad, att)
    for s in ("S2", "S3"):
        print(f"Trad. {s}: {len(trad[s])} usable trials")

    with open(a.nodeb, encoding="utf-8-sig") as f:
        nodeb_rows = list(csv.DictReader(f))
    nodeb_blocked = any((r.get("mac") or "").lower() == att for r in nodeb_rows)

    # ---------------- Table 20 ----------------
    h, body, tail = read_table(os.path.join(a.tables, "Table20_LocalResponse.csv"))
    i_scen = h.index("Scenario")
    i_tr = h.index("Trad. IDPS Response Time (ms)")
    i_sresp = h.index("SentiNet Response Time (ms)")
    i_fpb = h.index("SentiNet First-Packet-to-Block (ms)")
    h2 = h + ["Trad. IDPS t_detected (ms)", "Trad. IDPS t_enforced (ms)"]
    k = {"S2": 0, "S3": 0}
    sent = {"S2": [], "S3": []}
    fpb = {"S2": [], "S3": []}
    new_body = []
    for r in body:
        s = r[i_scen]
        sent[s].append(float(r[i_sresp]))
        if r[i_fpb]:
            fpb[s].append(float(r[i_fpb]))
        t = trad[s][k[s]] if k[s] < len(trad[s]) else None
        k[s] += 1
        r = list(r)
        r[i_tr] = fmt(t["resp"]) if t else ""
        new_body.append(r + ([fmt(t["t_det"], 0), fmt(t["t_enf"], 0)] if t else ["", ""]))
    tr = {s: [t["resp"] for t in trad[s]] for s in trad}
    with open(os.path.join(out, "Table20_LocalResponse.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(h2)
        w.writerows(new_body)
        for r in tail:
            if r and r[0].startswith("Trad. IDPS Response"):
                continue
            w.writerow(r)
        for s in ("S2", "S3"):
            w.writerow(summary_row("Trad. IDPS Response (ms)", s, tr[s]))
        w.writerow(summary_row("Trad. IDPS Response (ms)", f"All {len(tr['S2']) + len(tr['S3'])} trials",
                               tr["S2"] + tr["S3"]))
        w.writerow([])
        w.writerow(["Note: SentiNet and Snort ran as separate batches; the k-th Snort trial of a scenario is "
                    "listed beside the k-th SentiNet trial, not paired with it. Snort's response time starts at "
                    "the capture time of the alerting (first spoofed) frame; SentiNet's starts at its Tier-2 "
                    "decision, and its First-Packet-to-Block adds the detection window span."])

    # ---------------- Table 21 ----------------
    h, body, tail = read_table(os.path.join(a.tables, "Table21_CrossNodeTTB.csv"))
    i_t = h.index("Trad. IDPS Cross-Node TTB (ms)")
    i_rem = h.index("Remarks")
    label = "Not blocked" if not nodeb_blocked else "Blocked (see Kali B log)"
    with open(os.path.join(out, "Table21_CrossNodeTTB.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(h)
        for r in body:
            r = list(r)
            r[i_t] = label
            w.writerow(r)
        for r in tail:
            if r and r[0].startswith("Trad. IDPS Cross-Node TTB"):
                continue
            w.writerow(r)
        n = len(trad["S2"]) + len(trad["S3"])
        if not nodeb_blocked:
            w.writerow(["Trad. IDPS Cross-Node TTB", "All", n,
                        f"Not blocked in {n}/{n} trials: Snort on Kali B ran through the whole batch and never "
                        "blocked the attacker (Kali B was not attacked and Snort nodes share no blacklist). "
                        "Excluded from the mean; no TTB exists."])
        else:
            w.writerow(["Trad. IDPS Cross-Node TTB", "All", n,
                        "Kali B's log contains a block of the attacker; check it before reporting."])

    # ---------------- Table 22 ----------------
    with open(os.path.join(out, "Table22_tTest_ThreatResponse.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["Metric", "Scenario", "n1 (SentiNet)", "n2 (Trad.)", "x̄1", "x̄2", "s1²", "s2²",
                    "t-value", "df", "p-value", "Decision at α=0.05", "Faster system"])

        def test(metric, s_vals, t_vals, scen):
            res = welch(s_vals, t_vals)
            if not res:
                w.writerow([metric, scen, len(s_vals), len(t_vals)] + ["N/A"] * 9)
                return
            m1, m2, v1, v2, tv, df, p = res
            ps = "< 0.001" if p < 0.001 else f"{p:.4f}"
            dec = "Significant (reject H0)" if p < 0.05 else "Not significant (fail to reject H0)"
            faster = ("SentiNet" if m1 < m2 else "Trad. IDPS") if p < 0.05 else "No significant difference"
            w.writerow([metric, scen, len(s_vals), len(t_vals), fmt(m1), fmt(m2), fmt(v1, 4), fmt(v2, 4),
                        fmt(tv, 3), fmt(df), ps, dec, faster])

        for scen in ("S2", "S3", "Aggregate"):
            ss = sent["S2"] + sent["S3"] if scen == "Aggregate" else sent[scen]
            tt = tr["S2"] + tr["S3"] if scen == "Aggregate" else tr[scen]
            test("Local Response Time (ms)", ss, tt, scen)
        for scen in ("S2", "S3", "Aggregate"):
            ss = fpb["S2"] + fpb["S3"] if scen == "Aggregate" else fpb[scen]
            tt = tr["S2"] + tr["S3"] if scen == "Aggregate" else tr[scen]
            test("First-Packet-to-Block (ms), supplementary", ss, tt, scen)
        w.writerow(["Cross-Node TTB (ms)", "Aggregate", 60, 0] + ["N/A"] * 6 +
                   ["Not testable", "SentiNet only (Trad. not blocked)" if not nodeb_blocked else "Check Kali B"])
        w.writerow([])
        w.writerow(["Welch's two-sample t-test (unequal variances), two-sided. p-values computed from the "
                    "Student t distribution with Welch-Satterthwaite df."])

    print(f"Kali B blocked the attacker: {'YES - check' if nodeb_blocked else 'no'}")
    print(f"Tables 20, 21, 22 written to {out}")


if __name__ == "__main__":
    main()
