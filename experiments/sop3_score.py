#!/usr/bin/env python3
"""Score SOP 3 logs into experiment paper Tables 17, 19, 20, 21 (and the
Table 22 t-tests). Standard library only.

    python3 sop3_score.py --attacker <MAC> --s2 <dir> [--s3 <dir>]

Each scenario directory holds the logs gathered from the three machines after
that scenario's trials (append mode keeps one row per trial, joined by event id):
    nodeA_detections.csv     Kali A  /tmp/sentinet_detections.csv
    nodeB_enforcements.csv   Kali B  /tmp/sentinet_enforcements.csv
    relay_broadcast.csv      relay   relay_broadcast.csv
    relay_ledger.csv         relay   relay_ledger.csv        (MultiChain only)
    tradA_blocks.csv         Kali A  /var/log/tidps/blocks.csv   (traditional, optional)
    tradB_blocks.csv         Kali B  /var/log/tidps/blocks.csv   (traditional, optional)

Cross-machine columns (Report Upload, Total Propagation, cross-node TTB) assume
the clocks are synced (sop3_setup_chrony.sh). Broadcast Latency and the local
response times use one machine's clock only and do not.
"""
import argparse
import csv
import math
import os
import statistics as st


def load(path):
    return list(csv.DictReader(open(path))) if os.path.exists(path) else []


def by_event(rows):
    out = {}
    for r in rows:
        eid = r.get("event_id")
        if eid and eid not in out:
            out[eid] = r
    return out


def f(x, n=2):
    return "" if x is None else f"{x:.{n}f}"


def summarise(writer, label, values, n=2):
    vals = [v for v in values if v is not None]
    if not vals:
        writer.writerow([label] + ["N/A"])
        return
    writer.writerow([f"{label} Mean (x̄)", f(st.mean(vals), n)])
    if len(vals) >= 2:
        writer.writerow([f"{label} SD", f(st.stdev(vals), n)])
        s = sorted(vals)
        p95 = s[min(len(s) - 1, int(math.ceil(0.95 * len(s)) - 1))]
        writer.writerow([f"{label} 95th percentile", f(p95, n)])


def welch(a, b):
    a = [x for x in a if x is not None]
    b = [x for x in b if x is not None]
    if len(a) < 2 or len(b) < 2:
        return None
    m1, m2, v1, v2, n1, n2 = st.mean(a), st.mean(b), st.variance(a), st.variance(b), len(a), len(b)
    se2 = v1 / n1 + v2 / n2
    if se2 == 0:
        return (m1, m2, v1, v2, None, None, None)
    t = (m1 - m2) / math.sqrt(se2)
    df = se2 ** 2 / ((v1 / n1) ** 2 / (n1 - 1) + (v2 / n2) ** 2 / (n2 - 1))
    try:
        from scipy import stats
        p = 2 * stats.t.sf(abs(t), df)
    except ImportError:
        p = None
    return (m1, m2, v1, v2, t, df, p)


def collect(scen_dirs, attacker):
    """Per-event joined rows across the scenario dirs. Returns list of dicts."""
    rows = []
    for scen, d in scen_dirs.items():
        det = by_event(load(os.path.join(d, "nodeA_detections.csv")))
        enf = by_event(load(os.path.join(d, "nodeB_enforcements.csv")))
        bro = by_event(load(os.path.join(d, "relay_broadcast.csv")))
        led = by_event(load(os.path.join(d, "relay_ledger.csv")))
        for eid, dr in det.items():
            e, b, l = enf.get(eid), bro.get(eid), led.get(eid)
            g = lambda r, k: float(r[k]) if r and r.get(k) not in (None, "", "nan") else None
            rows.append({
                "scenario": scen, "event": eid,
                "mac": dr.get("mac", ""),
                "correct": (dr.get("mac", "").lower() == attacker),
                "detected_at": g(dr, "detected_at_ms"),
                "t_added": g(dr, "t_added_ms"),
                "t_enforced_local": g(dr, "t_enforced_ms"),
                "confidence": dr.get("confidence", ""),
                "model_load_ms": g(dr, "model_load_ms"),
                "inference_ms": g(dr, "inference_ms"),
                "pre_block": dr.get("pre_block_packets", ""),
                "t_sent": g(b, "t_sent_ms"),
                "relay_received": g(b, "relay_received_ms"),
                "t_ws_push": g(b, "t_ws_push_ms"),
                "t_blockchain_write": g(l, "t_blockchain_write_ms"),
                "nodeB_received": g(e, "received_at_ms"),
                "nodeB_enforced": g(e, "enforced_at_ms"),
            })
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--attacker", required=True)
    ap.add_argument("--s2")
    ap.add_argument("--s3")
    ap.add_argument("--out", default=".")
    a = ap.parse_args()
    attacker = a.attacker.lower()
    dirs = {s: d for s, d in (("S2", a.s2), ("S3", a.s3)) if d}
    if not dirs:
        ap.error("give at least one of --s2 / --s3")
    rows = collect(dirs, attacker)
    if not rows:
        raise SystemExit("No nodeA_detections.csv rows found in the given folder(s).")
    os.makedirs(a.out, exist_ok=True)
    W = lambda name: csv.writer(open(os.path.join(a.out, name), "w", newline="", encoding="utf-8-sig"))

    # ── Table 17: Cold-Start Condition (SentiNet) ──
    w = W("Table17_ColdStart.csv")
    w.writerow(["Trial", "Scenario", "Correctly classified?", "Model confidence",
                "Model load time (s)", "Tier-2 inference latency (ms)",
                "Blacklist population time (s)", "Pre-block packets"])
    pop = []
    for i, r in enumerate(rows, 1):
        p = (r["t_added"] - r["detected_at"]) / 1000 if r["t_added"] and r["detected_at"] else None
        pop.append(p)
        w.writerow([i, r["scenario"], "Yes" if r["correct"] else "No", r["confidence"],
                    f(r["model_load_ms"] / 1000, 3) if r["model_load_ms"] else "",
                    f(r["inference_ms"], 3), f(p, 3), r["pre_block"]])
    summarise(w, "Inference (ms)", [r["inference_ms"] for r in rows], 3)
    summarise(w, "Population (s)", pop, 3)

    # ── Table 19: Report Upload, Blockchain Write, Broadcast Latency ──
    w = W("Table19_Latency.csv")
    w.writerow(["Trial", "Scenario", "t_sent (ms)", "Relay t_received (ms)",
                "Report Upload Time (ms)", "t_blockchain_write (ms)", "t_ws_push (ms)",
                "Node B t_received (ms)", "Broadcast Latency (ms)", "Total Propagation Time (ms)"])
    upload, bcast, prop = [], [], []
    for i, r in enumerate(rows, 1):
        up = r["relay_received"] - r["t_sent"] if r["relay_received"] and r["t_sent"] else None
        bl = abs(r["t_ws_push"] - r["t_blockchain_write"]) if r["t_ws_push"] and r["t_blockchain_write"] else None
        tp = r["nodeB_received"] - r["t_sent"] if r["nodeB_received"] and r["t_sent"] else None
        upload.append(up); bcast.append(bl); prop.append(tp)
        w.writerow([i, r["scenario"], f(r["t_sent"], 0), f(r["relay_received"], 0), f(up),
                    f(r["t_blockchain_write"], 0), f(r["t_ws_push"], 0), f(r["nodeB_received"], 0),
                    f(bl), f(tp)])
    summarise(w, "Report Upload", upload)
    summarise(w, "Broadcast Latency", bcast)
    summarise(w, "Total Propagation", prop)

    # ── Table 20: Local Threat Response Time (same-node) ──
    w = W("Table20_LocalResponse.csv")
    w.writerow(["Trial", "Scenario", "SentiNet t_detected (ms)", "SentiNet t_enforced (ms)",
                "SentiNet Response Time (ms)", "Trad. IDPS Response Time (ms)"])
    trad = {}
    for scen, d in dirs.items():
        for r in load(os.path.join(d, "tradA_blocks.csv")):
            if r.get("response_ms"):
                trad.setdefault(scen, []).append(float(r["response_ms"]))
    sent_resp, trad_resp = [], []
    ti = {s: 0 for s in dirs}
    for i, r in enumerate(rows, 1):
        resp = r["t_enforced_local"] - r["detected_at"] if r["t_enforced_local"] and r["detected_at"] else None
        sent_resp.append(resp)
        tr = None
        lst = trad.get(r["scenario"], [])
        if ti[r["scenario"]] < len(lst):
            tr = lst[ti[r["scenario"]]]; ti[r["scenario"]] += 1
        trad_resp.append(tr)
        w.writerow([i, r["scenario"], f(r["detected_at"], 0), f(r["t_enforced_local"], 0), f(resp), f(tr)])
    summarise(w, "SentiNet Response", sent_resp)
    summarise(w, "Trad. Response", trad_resp)

    # ── Table 21: Cross-Node Time-to-Block ──
    w = W("Table21_CrossNodeTTB.csv")
    w.writerow(["Trial", "Scenario", "t_detected at Node A (ms)", "t_enforced at Node B (ms)",
                "SentiNet TTB (ms)", "Trad. IDPS Cross-Node TTB (ms)", "Remarks"])
    ttb = []
    tradB = {}
    for scen, d in dirs.items():
        for r in load(os.path.join(d, "tradB_blocks.csv")):
            if r.get("t_enforced_ms"):
                tradB.setdefault(scen, []).append(float(r["t_enforced_ms"]))
    for i, r in enumerate(rows, 1):
        t = r["nodeB_enforced"] - r["detected_at"] if r["nodeB_enforced"] and r["detected_at"] else None
        ttb.append(t)
        remark = "" if t is not None else "Node B did not enforce (no second agent / not propagated)"
        w.writerow([i, r["scenario"], f(r["detected_at"], 0), f(r["nodeB_enforced"], 0), f(t), "", remark])
    summarise(w, "SentiNet TTB", ttb)

    # ── Table 22: t-tests (local response and cross-node TTB, SentiNet vs Trad.) ──
    w = W("Table22_tTest_ThreatResponse.csv")
    w.writerow(["Metric", "Scenario", "n1", "n2", "x̄1", "x̄2", "s1²", "s2²", "t-value", "df", "p-value", "Decision at α=0.05"])
    def rows_for(metric_pairs, scen):
        s_vals = [v for r, v in metric_pairs[0] if scen == "Aggregate" or r["scenario"] == scen]
        t_vals = [v for r, v in metric_pairs[1] if scen == "Aggregate" or r["scenario"] == scen]
        return s_vals, t_vals
    local_pairs = ([(r, (r["t_enforced_local"] - r["detected_at"]) if r["t_enforced_local"] and r["detected_at"] else None) for r in rows],
                   [(None, None)])  # traditional local filled below if present
    for metric, s_list in (("Local Response Time (ms)", sent_resp),):
        for scen in ("S2", "S3", "Aggregate"):
            s = [v for r, v in zip(rows, sent_resp) if (scen == "Aggregate" or r["scenario"] == scen) and v is not None]
            t = [v for r, v in zip(rows, trad_resp) if (scen == "Aggregate" or r["scenario"] == scen) and v is not None]
            res = welch(s, t)
            if not res or res[4] is None:
                w.writerow([metric, scen, len(s), len(t)] + ["N/A"] * 8)
                continue
            m1, m2, v1, v2, tv, df, p = res
            ps = "N/A" if p is None else ("< 0.001" if p < 0.001 else f"{p:.4f}")
            dec = "N/A" if p is None else ("Accept Ha (significant)" if p < 0.05 else "Reject Ha (not significant)")
            w.writerow([metric, scen, len(s), len(t), f(m1), f(m2), f(v1, 4), f(v2, 4), f(tv, 3), f(df), ps, dec])

    print(f"{len(rows)} detection events scored across {', '.join(dirs)}.")
    nodeB = sum(1 for r in rows if r["nodeB_enforced"])
    ledger = sum(1 for r in rows if r["t_blockchain_write"])
    print(f"  Node B enforced (cross-node TTB available): {nodeB}/{len(rows)}")
    print(f"  Ledger write logged (Table 19 blockchain column): {ledger}/{len(rows)}")
    print(f"Tables written to {a.out}")


if __name__ == "__main__":
    main()
