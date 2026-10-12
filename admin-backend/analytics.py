"""
Network traffic analytics for the admin dashboard's Analytics tab.

Every agent sends, with each telemetry report (about once a second), two running
counts since it started: ARP packets inspected and ARP packets blocked by Tier 1.
The relay turns consecutive counts into per-second rates for each agent, which
the live chart shows for the last few minutes, and adds the same counts into
per-minute totals in the database for the daily, weekly and monthly views.

Blocked means a Tier-1 hit: the agent recognised the sender as blacklisted. On a
Linux agent the kernel has also dropped the packet; on Windows and macOS it is
counted only (see tray-app/enforcer.py), which the dashboard labels.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from datetime import datetime, timedelta
from typing import Any, Deque, Dict, List, Optional, Tuple

from sqlalchemy import Column, Float, Integer, String

import state

# How much of the live chart to keep, in seconds.
LIVE_WINDOW_SECONDS = 300
# An agent with no report for this long is shown as idle rather than at its last rate.
STALE_SECONDS = 5.0


class DBTrafficMinute(state.Base):
    """ARP packets one agent inspected and blocked in one minute of local time."""
    __tablename__ = "traffic_minutes"
    id = Column(Integer, primary_key=True)
    minute_ts = Column(Float, index=True)   # epoch seconds at the start of the minute
    mac = Column(String, index=True)
    name = Column(String)
    packets = Column(Integer)
    blocked = Column(Integer)


state.Base.metadata.create_all(bind=state.engine, tables=[DBTrafficMinute.__table__])

_lock = threading.Lock()
# Per agent MAC: name, enforcement mode, the previous report's counts, and recent
# per-second samples (time, packets/s, blocked/s).
_agents: Dict[str, Dict[str, Any]] = {}
# Per (minute start, MAC): packets and blocked so far in the minute being filled.
_minutes: Dict[Tuple[float, str], Dict[str, Any]] = {}
# The busiest second and the overall totals since the relay started, network-wide.
_session = {"peak_pps": 0.0, "packets": 0, "blocked": 0, "started": time.time()}


def _flush_minutes_locked(before: float) -> None:
    """Write every completed minute (start < `before`) to the database."""
    done = [key for key in _minutes if key[0] < before]
    if not done:
        return
    db = state.SessionLocal()
    try:
        for key in done:
            row = _minutes.pop(key)
            db.add(DBTrafficMinute(minute_ts=key[0], mac=key[1], name=row["name"],
                                   packets=row["packets"], blocked=row["blocked"]))
        db.commit()
    finally:
        db.close()


def record(mac: str, name: str, inspected: Any, blocked: Any, enforcement: Optional[str]) -> None:
    """Take one agent's running counts from its telemetry report."""
    if not mac or not isinstance(inspected, (int, float)) or not isinstance(blocked, (int, float)):
        return
    now = time.time()
    with _lock:
        agent = _agents.setdefault(mac, {"samples": deque(), "last": None})
        agent["name"] = name or mac
        agent["enforcement"] = enforcement
        agent["seen"] = now
        last = agent["last"]
        agent["last"] = (now, inspected, blocked)
        if last is None:
            return

        then, last_inspected, last_blocked = last
        # Counts going backwards mean the agent restarted from zero.
        new_packets = inspected - last_inspected if inspected >= last_inspected else inspected
        new_blocked = blocked - last_blocked if blocked >= last_blocked else blocked
        elapsed = now - then
        if elapsed <= 0:
            return

        samples: Deque = agent["samples"]
        samples.append((now, new_packets / elapsed, new_blocked / elapsed))
        while samples and now - samples[0][0] > LIVE_WINDOW_SECONDS:
            samples.popleft()

        # Network-wide rate right now: every agent's latest current reading.
        total = sum(a["samples"][-1][1] for a in _agents.values()
                    if a["samples"] and now - a["samples"][-1][0] <= STALE_SECONDS)
        _session["peak_pps"] = max(_session["peak_pps"], total)

        _session["packets"] += new_packets
        _session["blocked"] += new_blocked

        minute = now - (now % 60)
        bucket = _minutes.setdefault((minute, mac), {"name": agent["name"], "packets": 0, "blocked": 0})
        bucket["packets"] += new_packets
        bucket["blocked"] += new_blocked
        _flush_minutes_locked(minute)


def forget(mac: str) -> None:
    """An agent disconnected: stop charting it. Its stored minutes are kept."""
    with _lock:
        _agents.pop(mac, None)


def _live_locked(now: float) -> Dict[str, Any]:
    """One row per second for the live chart: each agent's rate and the totals."""
    start = int(now) - LIVE_WINDOW_SECONDS
    rows: Dict[int, Dict[str, Any]] = {}
    for mac, agent in _agents.items():
        for t, pps, bps in agent["samples"]:
            second = int(t)
            if second < start:
                continue
            row = rows.setdefault(second, {"t": second * 1000, "pps": 0.0, "blocked": 0.0, "agents": {}})
            row["agents"][mac] = round(pps, 1)
            row["pps"] += pps
            row["blocked"] += bps
    series = [rows[s] for s in sorted(rows)]
    for row in series:
        row["pps"] = round(row["pps"], 1)
        row["blocked"] = round(row["blocked"], 1)
    return {"series": series}


def _agent_rows_locked(now: float) -> List[Dict[str, Any]]:
    rows = []
    for mac, agent in _agents.items():
        recent = [s for s in agent["samples"] if now - s[0] <= STALE_SECONDS]
        last = agent["last"]
        rows.append({
            "mac": mac,
            "name": agent["name"],
            "enforcement": agent.get("enforcement") or "simulated",
            # Averaged over the last few seconds so the figure does not flicker.
            "pps": round(sum(s[1] for s in recent) / len(recent), 1) if recent else 0.0,
            "blockedPps": round(sum(s[2] for s in recent) / len(recent), 1) if recent else 0.0,
            "packets": int(last[1]) if last else 0,
            "blocked": int(last[2]) if last else 0,
        })
    return sorted(rows, key=lambda r: r["name"])


def _period(buckets: List[Tuple[datetime, str]], width: timedelta,
            minutes: List[DBTrafficMinute], current: List[Tuple[float, Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """Total packets and blocked per bucket, from stored minutes plus the one being filled."""
    out = [{"label": label, "packets": 0, "blocked": 0} for _, label in buckets]
    starts = [b[0].timestamp() for b in buckets]
    span = width.total_seconds()

    def add(ts: float, packets: int, blocked: int) -> None:
        for i, s in enumerate(starts):
            if s <= ts < s + span:
                out[i]["packets"] += packets
                out[i]["blocked"] += blocked
                return

    for m in minutes:
        add(m.minute_ts, m.packets or 0, m.blocked or 0)
    for ts, row in current:
        add(ts, row["packets"], row["blocked"])
    return out


def get_analytics() -> Dict[str, Any]:
    now = time.time()
    local_now = datetime.fromtimestamp(now)
    this_hour = local_now.replace(minute=0, second=0, microsecond=0)
    today = local_now.replace(hour=0, minute=0, second=0, microsecond=0)

    hours = [(this_hour - timedelta(hours=23 - i), (this_hour - timedelta(hours=23 - i)).strftime("%H:00"))
             for i in range(24)]
    week = [(today - timedelta(days=6 - i), (today - timedelta(days=6 - i)).strftime("%a %d"))
            for i in range(7)]
    month = [(today - timedelta(days=29 - i), (today - timedelta(days=29 - i)).strftime("%b %d"))
             for i in range(30)]

    db = state.SessionLocal()
    try:
        stored = db.query(DBTrafficMinute).filter(
            DBTrafficMinute.minute_ts >= month[0][0].timestamp()).all()
        threats = db.query(state.DBThreat).filter(
            state.DBThreat.created_ts >= hours[0][0].timestamp()).all()
    finally:
        db.close()

    with _lock:
        current = [(key[0], dict(row)) for key, row in _minutes.items()]
        live = _live_locked(now)
        agents = _agent_rows_locked(now)
        session = dict(_session)

    # Incidents: a Tier-2 report is a new detection; Tier-1 and Tier-3 reports
    # are an agent confirming it is still blocking a known attacker.
    incidents = [{"label": label, "detections": 0, "blocks": 0} for _, label in hours]
    hour_starts = [h[0].timestamp() for h in hours]
    for t in threats:
        for i, s in enumerate(hour_starts):
            if s <= t.created_ts < s + 3600:
                incidents[i]["detections" if t.tier == "Tier 2" else "blocks"] += 1
                break

    elapsed = max(1.0, now - session["started"])
    return {
        "live": live["series"],
        "agents": agents,
        "session": {
            "currentPps": round(sum(a["pps"] for a in agents), 1),
            "currentBlockedPps": round(sum(a["blockedPps"] for a in agents), 1),
            "peakPps": round(session["peak_pps"], 1),
            "avgPps": round(session["packets"] / elapsed, 1),
            "packets": int(session["packets"]),
            "blocked": int(session["blocked"]),
            "since": session["started"] * 1000,
        },
        "daily": _period(hours, timedelta(hours=1), stored, current),
        "weekly": _period(week, timedelta(days=1), stored, current),
        "monthly": _period(month, timedelta(days=1), stored, current),
        "incidents": incidents,
    }
