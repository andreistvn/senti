#!/usr/bin/env python3
"""Score SOP 2 trials into experiment paper Tables 13-16 (standard library only).

    python3 sop2_score.py <sop2_results folder> --attacker d6:25:89:a3:42:63

Reads every <system>_T<n>_<S2|S3> trial folder made by sop2_trial.sh and writes
into the same folder:
  Table13_Traditional_Raw.csv   Table14_SentiNet_Raw.csv
  Table15_Metrics_per_Trial.csv Table16_t-Test_Detection.csv

Counting units (Table 13 note):
  * Packets: inbound ARP frames at the victim NIC (source MAC != victim's own),
    from the trial's capture. Malicious = from the attacker MAC; Benign = the rest.
  * Traditional IDPS, per inspected frame: a frame is flagged if Snort raised an
    ARP-spoof alert (112:2/3/4) on it. TP/FN on attacker frames, FP/TN on benign.
  * SentiNet, per 5-second behavioural window per source MAC: a (window, MAC)
    with at least one frame is flagged if SentiNet had that MAC on its blacklist
    by the end of the window (Tier 2 scores >= 0.50 block at once, Tier 1 then
    drops every later frame, so "on the blacklist" is SentiNet's verdict).
  * Attacks Detected / Blocked: per distinct attacker MAC. Blocked = actually
    dropped by the kernel (nft), not only alerted.
"""
import argparse
import csv
import glob
import math
import os
import re
import statistics as st
import struct
import sys

WINDOW_S = 5.0


def read_pcap(path):
    """Yield (ts_seconds, src_mac) for every frame in a classic pcap file."""
    with open(path, "rb") as f:
        head = f.read(24)
        if len(head) < 24:
            return
        magic = struct.unpack("<I", head[:4])[0]
        if magic in (0xA1B2C3D4, 0xA1B23C4D):
            endian = "<"
        else:
            endian = ">"
            magic = struct.unpack(">I", head[:4])[0]
        if magic not in (0xA1B2C3D4, 0xA1B23C4D):
            sys.exit(f"{path}: not a classic pcap file")
        frac = 1e-9 if magic == 0xA1B23C4D else 1e-6
        while True:
            rec = f.read(16)
            if len(rec) < 16:
                return
            sec, sub, incl, _orig = struct.unpack(endian + "IIII", rec)
            data = f.read(incl)
            if len(data) < 12:
                continue
            yield sec + sub * frac, data[6:12].hex(":")


def snort_flagged(alert_path):
    """Set of (timestamp, mac) frames Snort flagged with an ARP-spoof alert.

    tidps.sh start begins a fresh alert file, so the file holds this trial only.
    Timestamps stay as Snort wrote them (Kali local time) and only dedupe
    several alerts raised on the same frame."""
    flagged = set()
    if not os.path.exists(alert_path):
        return flagged
    for line in open(alert_path, errors="replace"):
        parts = [p.strip() for p in line.split(",", 5)]
        if len(parts) < 6 or parts[1] != "112" or parts[2] not in ("2", "3", "4"):
            continue
        flagged.add((parts[0], parts[3].lower()))
    return flagged


def first_block_times(path, key_added, key_enforced):
    """{mac: (t_added_s, t_enforced_s or None)}: first block per MAC.

    From sentinet_blocks.csv (t_added_ms / t_enforced_ms) or tidps blocks.csv
    (t_enforced_ms). t_enforced_s is None when enforcement did not report a time
    (e.g. simulated mode); callers fall back to t_added_s."""
    out = {}
    if not os.path.exists(path):
        return out
    for r in csv.DictReader(open(path)):
        mac = r["mac"].lower()
        ta = r.get(key_added) or ""
        if not ta or ta == "nan" or mac in out:
            continue
        te = r.get(key_enforced) or ""
        te_s = float(te) / 1000 if te and te != "nan" else None
        out[mac] = (float(ta) / 1000, te_s)
    return out


def pr_counts(blocks, attacker, mal_frames):
    """Per-frame (Attacks Detected, Attacks Blocked) for Prevention Rate.

    Detected = every attacker frame in the trial (the attack being responded to).
    Blocked  = attacker frames at/after enforcement, i.e. dropped by the kernel;
               frames before enforcement leaked through (larger during cold start)
               and lower the Prevention Rate. tcpdump captures frames before the
               nft drop, so the capture holds the dropped frames too."""
    n = len(mal_frames)
    if attacker not in blocks:
        return n, 0
    t_added, t_enf = blocks[attacker]
    split = t_enf if t_enf is not None else t_added
    leaked = sum(1 for ts, _ in mal_frames if ts < split)
    return n, n - leaked


def score_trial(d, attacker):
    m = re.match(r"(sentinet|traditional)_T(\d+)_(S[23])$", os.path.basename(d))
    system, trial, scen = m.group(1), int(m.group(2)), m.group(3)
    victim = open(os.path.join(d, "victim_mac.txt")).read().strip().lower()
    start = int(open(os.path.join(d, "start_ms.txt")).read()) / 1000
    end = int(open(os.path.join(d, "end_ms.txt")).read()) / 1000
    frames = [(ts, mac) for ts, mac in read_pcap(os.path.join(d, "arp.pcap")) if mac != victim]

    mal = [f for f in frames if f[1] == attacker]
    total, n_mal = len(frames), len(mal)
    observed_pps = 0.0
    if n_mal > 1:
        span = mal[-1][0] - mal[0][0]
        observed_pps = (n_mal - 1) / span if span > 0 else 0.0

    if system == "traditional":
        flagged = snort_flagged(os.path.join(d, "alert_csv.txt"))
        # Flagged frames per source MAC, capped at the frames captured from it
        # (Snort and the capture start and stop a moment apart).
        per_mac = {}
        for ts, mac in frames:
            per_mac[mac] = per_mac.get(mac, 0) + 1
        hits = {}
        for _, mac in flagged:
            hits[mac] = hits.get(mac, 0) + 1
        tp = min(hits.get(attacker, 0), n_mal)
        fp = sum(min(hits.get(mac, 0), n) for mac, n in per_mac.items() if mac != attacker)
        fn, tn = n_mal - tp, (total - n_mal) - fp
        blocks = first_block_times(os.path.join(d, "blocks.csv"), "t_enforced_ms", "t_enforced_ms")
    else:
        blocks = first_block_times(os.path.join(d, "sentinet_blocks.csv"), "t_added_ms", "t_enforced_ms")
        t0 = frames[0][0] if frames else start
        seen = set()
        for ts, mac in frames:
            seen.add((int((ts - t0) // WINDOW_S), mac))
        tp = tn = fp = fn = 0
        for w, mac in seen:
            w_end = t0 + (w + 1) * WINDOW_S
            flagged = mac in blocks and blocks[mac][0] <= w_end
            if mac == attacker:
                tp += flagged; fn += not flagged
            else:
                fp += flagged; tn += not flagged
    detected, blocked = pr_counts(blocks, attacker, mal)
    return dict(system=system, trial=trial, scenario=scen, TP=tp, TN=tn, FP=fp, FN=fn,
                total=total, malicious=n_mal, benign=total - n_mal,
                detected=detected, blocked=blocked, observed_pps=observed_pps)


def pct(a, b):
    return a / b * 100 if b else float("nan")


def metrics(r):
    tp, tn, fp, fn = r["TP"], r["TN"], r["FP"], r["FN"]
    return dict(acc=pct(tp + tn, tp + tn + fp + fn), dr=pct(tp, tp + fn),
                fpr=pct(fp, fp + tn), pr=pct(r["blocked"], r["detected"]))


def fmt(x):
    return "N/A" if isinstance(x, float) and math.isnan(x) else f"{x:.2f}"


def welch(a, b):
    """Equation 11 (unequal variances) with Welch-Satterthwaite df; two-tailed p."""
    n1, n2 = len(a), len(b)
    m1, m2 = st.mean(a), st.mean(b)
    v1, v2 = st.variance(a), st.variance(b)
    se2 = v1 / n1 + v2 / n2
    if se2 == 0:
        return m1, m2, v1, v2, None, None, None
    t = (m1 - m2) / math.sqrt(se2)
    df = se2 ** 2 / ((v1 / n1) ** 2 / (n1 - 1) + (v2 / n2) ** 2 / (n2 - 1))
    try:
        from scipy import stats
        p = 2 * stats.t.sf(abs(t), df)
    except ImportError:
        p = None
    return m1, m2, v1, v2, t, df, p


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder")
    ap.add_argument("--attacker", required=True, help="attacker MAC (ground truth)")
    a = ap.parse_args()
    attacker = a.attacker.lower()

    rows = []
    for d in sorted(glob.glob(os.path.join(a.folder, "*_T*_S[23]"))):
        r = score_trial(d, attacker)
        rows.append(r)
        print(f"{r['system']:11} T{r['trial']:<2} {r['scenario']}  TP {r['TP']:6} TN {r['TN']:6} FP {r['FP']:5} "
              f"FN {r['FN']:5}  frames {r['total']:6} (mal {r['malicious']}, {r['observed_pps']:.1f} pkt/s)  "
              f"detected {r['detected']} blocked {r['blocked']}")
    if not rows:
        sys.exit("No trial folders found.")

    head = ["Trial", "Scenario", "True Positives", "True Negatives", "False Positives", "False Negatives",
            "Total Packets", "Malicious Injected", "Benign Packets", "Attacks Detected", "Attacks Blocked"]
    keys = ["TP", "TN", "FP", "FN", "total", "malicious", "benign", "detected", "blocked"]
    for num, system, name in (("13", "traditional", "Traditional_Raw"), ("14", "sentinet", "SentiNet_Raw")):
        sel = sorted((r for r in rows if r["system"] == system), key=lambda r: r["trial"])
        if not sel:
            continue
        with open(os.path.join(a.folder, f"Table{num}_{name}.csv"), "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(head)
            for r in sel:
                w.writerow([r["trial"], r["scenario"]] + [r[k] for k in keys])
            w.writerow(["Total", ""] + [sum(r[k] for r in sel) for k in keys])
        with open(os.path.join(a.folder, f"Table12_observed_rates_{system}.csv"), "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["Trial", "Scenario", "Observed Rate at Victim NIC (pkt/s)"])
            for r in sel:
                w.writerow([r["trial"], r["scenario"], f"{r['observed_pps']:.1f}"])

    by = {(r["system"], r["trial"]): (r, metrics(r)) for r in rows}
    trials = sorted({r["trial"] for r in rows})
    with open(os.path.join(a.folder, "Table15_Metrics_per_Trial.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["Trial", "Scenario", "SentiNet Accuracy (%)", "SentiNet Detection Rate (%)", "SentiNet FPR (%)",
                    "SentiNet Prevention Rate (%)", "Trad. IDPS Accuracy (%)", "Trad. IDPS Detection Rate (%)",
                    "Trad. IDPS FPR (%)", "Trad. IDPS Prevention Rate (%)", "Detection Rate Difference (%)"])
        cols = {k: [] for k in ("s_acc", "s_dr", "s_fpr", "s_pr", "t_acc", "t_dr", "t_fpr", "t_pr", "diff")}
        for t in trials:
            s = by.get(("sentinet", t)); tr = by.get(("traditional", t))
            if not (s and tr):
                continue
            sm, tm = s[1], tr[1]
            vals = [sm["acc"], sm["dr"], sm["fpr"], sm["pr"], tm["acc"], tm["dr"], tm["fpr"], tm["pr"], sm["dr"] - tm["dr"]]
            for k, v in zip(cols, vals):
                cols[k].append(v)
            w.writerow([t, s[0]["scenario"]] + [fmt(v) for v in vals])
        for lab, fn in (("Mean (x̄)", st.mean), ("SD", st.stdev)):
            out = []
            for v in cols.values():
                v = [x for x in v if not math.isnan(x)]
                out.append(fmt(fn(v)) if len(v) >= (2 if fn is st.stdev else 1) else "N/A")
            w.writerow([lab, ""] + out)

    with open(os.path.join(a.folder, "Table16_t-Test_Detection.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["Metric", "Scenario", "n1 (SentiNet)", "n2 (Trad.)", "x̄1", "x̄2", "s1²", "s2²",
                    "t-value", "df", "p-value", "Decision at α = 0.05"])
        for key, metric in (("acc", "Accuracy (%)"), ("dr", "Detection Rate (%)"),
                            ("fpr", "False Positive Rate (%)"), ("pr", "Prevention Rate (%)")):
            for scen in ("S2", "S3", "Aggregate"):
                def vals(system):
                    return [m[key] for (sy, _), (r, m) in by.items()
                            if sy == system and (scen == "Aggregate" or r["scenario"] == scen) and not math.isnan(m[key])]
                s_v, t_v = vals("sentinet"), vals("traditional")
                if len(s_v) < 2 or len(t_v) < 2:
                    w.writerow([metric, scen, len(s_v), len(t_v)] + ["N/A"] * 8)
                    continue
                m1, m2, v1, v2, t, df, p = welch(s_v, t_v)
                if t is None:
                    note = "Not computable: both groups have zero variance"
                    w.writerow([metric, scen, len(s_v), len(t_v), fmt(m1), fmt(m2), f"{v1:.4f}", f"{v2:.4f}",
                                "N/A", "N/A", "N/A", note])
                    continue
                ps = "N/A" if p is None else ("< 0.001" if p < 0.001 else f"{p:.4f}")
                dec = "N/A" if p is None else ("Accept Ha (significant)" if p < 0.05 else "Reject Ha (not significant)")
                w.writerow([metric, scen, len(s_v), len(t_v), fmt(m1), fmt(m2), f"{v1:.4f}", f"{v2:.4f}",
                            f"{t:.3f}", f"{df:.2f}", ps, dec])
    print("Tables written to", a.folder)


if __name__ == "__main__":
    main()
