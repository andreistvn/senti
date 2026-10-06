"""
The name of the network this machine is connected to, for display.

Each platform needs a different command and none is guaranteed to be present, so
every probe is best-effort and the interface name is the fallback — a label the
dashboard can always show, even on a wired VM with no SSID at all.
"""

from __future__ import annotations

import plistlib
import subprocess
import sys
from datetime import datetime
from typing import List, Optional

_TIMEOUT_SECONDS = 2.0


def _output(command: List[str]) -> str:
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=_TIMEOUT_SECONDS)
    except Exception:
        return ""
    return result.stdout if result.returncode == 0 else ""


def _linux(iface: Optional[str]) -> Optional[str]:
    # NetworkManager's connection name: the SSID for Wi-Fi, and something like
    # "Wired connection 1" for Ethernet (which is what a bridged VM has).
    for line in _output(["nmcli", "-t", "-f", "NAME,DEVICE", "connection", "show", "--active"]).splitlines():
        name, _, device = line.rpartition(":")
        if name and device and device != "lo" and (iface is None or device == iface):
            return name.replace("\\:", ":")
    ssid = _output(["iwgetid", "-r"]).strip()
    return ssid or None


MACOS_KNOWN_NETWORKS = "/Library/Preferences/com.apple.wifi.known-networks.plist"
_MACOS_KNOWN_PREFIX = "wifi.network.ssid."


def _macos_last_joined(path: str = MACOS_KNOWN_NETWORKS) -> Optional[str]:
    """
    The saved Wi-Fi network this Mac joined most recently.

    Recent macOS releases hide the current SSID from every command-line tool
    (they print "<redacted>") unless the asking app holds Location permission,
    which a background daemon cannot be granted. The system's own list of saved
    networks is still readable by root, and each entry records when it was last
    joined — on a Mac that is connected to Wi-Fi, the latest of those is the
    network it is on now.
    """
    try:
        with open(path, "rb") as f:
            known = plistlib.load(f)
    except Exception:
        return None
    best_name, best_time = None, None
    for key, entry in known.items() if isinstance(known, dict) else []:
        if not key.startswith(_MACOS_KNOWN_PREFIX) or not isinstance(entry, dict):
            continue
        joined = [entry.get(k) for k in ("JoinedBySystemAt", "JoinedByUserAt")]
        joined = [t for t in joined if isinstance(t, datetime)]
        if joined and (best_time is None or max(joined) > best_time):
            best_name, best_time = key[len(_MACOS_KNOWN_PREFIX):], max(joined)
    return best_name


def _macos(iface: Optional[str]) -> Optional[str]:
    if not iface:
        return None
    on_wifi = False
    for line in _output(["ipconfig", "getsummary", iface]).splitlines():
        key, _, value = line.partition(" : ")
        if key.strip() == "SSID" and value.strip():
            on_wifi = True
            if "redacted" not in value:
                return value.strip()
    out = _output(["networksetup", "-getairportnetwork", iface]).strip()
    prefix = "Current Wi-Fi Network: "
    if out.startswith(prefix):
        return out[len(prefix):]
    return _macos_last_joined() if on_wifi else None


def _windows(_iface: Optional[str]) -> Optional[str]:
    for line in _output(["netsh", "wlan", "show", "interfaces"]).splitlines():
        key, _, value = line.partition(":")
        if key.strip() == "SSID" and value.strip():
            return value.strip()
    return None


def network_name(iface: Optional[str]) -> str:
    """The Wi-Fi or connection name if it can be found, else the interface name."""
    if sys.platform.startswith("linux"):
        name = _linux(iface)
    elif sys.platform == "darwin":
        name = _macos(iface)
    elif sys.platform == "win32":
        name = _windows(iface)
    else:
        name = None
    return name or iface or "Unknown network"
