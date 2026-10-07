"""
Tier-1 enforcement: making the blacklist actually drop packets.

The capture engine reads traffic through a passive sniffer, which only ever sees
a copy of each frame — the operating system receives and processes the original
regardless of what the agent decides. On its own, then, "blocking" a MAC only
means the agent stops analysing it; a forged ARP reply from that MAC still
reaches the host and can still poison its ARP cache.

On Linux this module closes that gap with nftables. It keeps one small table of
its own:

    table netdev sentinet {
        set blocked { type ether_addr }
        chain ingress {
            type filter hook ingress device "<iface>" priority 0; policy accept;
            ether type arp ether saddr @blocked counter drop
        }
    }

The ingress hook runs before the kernel's ARP handling, so a blacklisted MAC's
ARP frames are discarded before they can touch the ARP cache. Packet sniffers
are fed ahead of that hook, so the capture engine still sees and counts every
frame the kernel then drops, and the rule's own counter gives an independent
figure to check the agent's count against:

    sudo nft list table netdev sentinet

Only ARP is dropped, matching what the agent inspects (it is an ARP-spoofing
IDPS): the two counts stay comparable, and a wrongly flagged device loses its
ARP frames rather than all contact with this host.

Windows and macOS have no comparable facility, so there the enforcer reports
mode "simulated" and does nothing — the behaviour the agent always had.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import threading
from typing import Iterable, Optional, Set

NFT_TABLE = "sentinet"
NFT_SET = "blocked"
NFT_CHAIN = "ingress"
NFT_TIMEOUT_SECONDS = 5.0

MODE_KERNEL = "kernel"
MODE_SIMULATED = "simulated"

_MAC_RE = re.compile(r"^[0-9a-f]{2}(:[0-9a-f]{2}){5}$")

# Never worth blocking whatever the model says: not a single device.
_NON_DEVICE_MACS = {"ff:ff:ff:ff:ff:ff", "00:00:00:00:00:00"}


def normalise_mac(mac: Optional[str]) -> Optional[str]:
    """Lower-case colon form, or None if this is not a MAC address."""
    if not mac:
        return None
    candidate = mac.strip().lower().replace("-", ":")
    return candidate if _MAC_RE.match(candidate) else None


def _find_nft() -> Optional[str]:
    found = shutil.which("nft")
    if found:
        return found
    # sudo and systemd both start the daemon with a minimal PATH.
    for path in ("/usr/sbin/nft", "/sbin/nft"):
        if os.path.exists(path):
            return path
    return None


class Enforcer:
    """
    Owns the kernel rules that back the Tier-1 blacklist.

    The set of MACs that should be blocked is tracked here at all times; it is
    only loaded into the kernel between start() and stop(), i.e. while
    protection is on. That keeps "protection OFF" meaning what it says, and
    makes it the escape hatch if a block ever turns out to be a mistake.
    """

    def __init__(
        self,
        iface: Optional[str] = None,
        platform: str = sys.platform,
        nft_path: Optional[str] = None,
    ) -> None:
        self._lock = threading.Lock()
        self._wanted: Set[str] = set()
        self._active = False
        # Frames dropped during earlier protection sessions: the kernel's own
        # counter starts again from zero each time the table is reloaded.
        self._dropped_before = 0
        self.iface = iface
        self._nft = nft_path or _find_nft()

        if not platform.startswith("linux"):
            self.mode = MODE_SIMULATED
            self.reason = f"no kernel packet filter for ARP on {platform}"
        elif not self._nft:
            self.mode = MODE_SIMULATED
            self.reason = "nftables ('nft') is not installed"
        elif not iface:
            self.mode = MODE_SIMULATED
            self.reason = "could not determine the capture interface"
        else:
            self.mode = MODE_KERNEL
            self.reason = f"nftables ingress hook on {iface}"

    # ── nft plumbing ──────────────────────────────────────────────────────────

    def _run(self, args: list, stdin: Optional[str] = None) -> subprocess.CompletedProcess:
        return subprocess.run(
            [self._nft, *args],
            input=stdin,
            capture_output=True,
            text=True,
            timeout=NFT_TIMEOUT_SECONDS,
        )

    def _ruleset(self) -> str:
        elements = ""
        if self._wanted:
            elements = f"\n\t\telements = {{ {', '.join(sorted(self._wanted))} }}"
        return (
            f"table netdev {NFT_TABLE} {{\n"
            f"\tset {NFT_SET} {{\n"
            f"\t\ttype ether_addr{elements}\n"
            f"\t}}\n"
            f"\tchain {NFT_CHAIN} {{\n"
            f'\t\ttype filter hook ingress device "{self.iface}" priority 0; policy accept;\n'
            f"\t\tether type arp ether saddr @{NFT_SET} counter drop\n"
            f"\t}}\n"
            f"}}\n"
        )

    def _delete_table_locked(self) -> None:
        # Fails harmlessly when the table does not exist.
        try:
            self._run(["delete", "table", "netdev", NFT_TABLE])
        except Exception:
            pass

    def _fall_back_locked(self, why: str) -> None:
        """Enforcement could not be applied — say so loudly and stop pretending."""
        self._delete_table_locked()
        self._active = False
        self.mode = MODE_SIMULATED
        self.reason = why
        print(f"[Enforcer] WARNING: kernel blocking unavailable — {why}. "
              f"Blacklisted MACs will be counted but NOT dropped.", flush=True)

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Protection ON: install the table with everything blacklisted so far."""
        with self._lock:
            if self.mode != MODE_KERNEL or self._active:
                return
            # A table left behind by a daemon that was killed outright.
            self._delete_table_locked()
            try:
                result = self._run(["-f", "-"], stdin=self._ruleset())
            except Exception as exc:
                self._fall_back_locked(f"nft could not be run: {exc}")
                return
            if result.returncode != 0:
                self._fall_back_locked(f"nft rejected the ruleset: {result.stderr.strip()}")
                return
            self._active = True
            print(f"[Enforcer] Kernel blocking active on {self.iface} "
                  f"({len(self._wanted)} MAC(s) loaded).", flush=True)

    def stop(self) -> Optional[int]:
        """
        Protection OFF or shutdown: remove every rule this agent installed.

        Returns how many ARP frames the kernel dropped while it was active.
        """
        with self._lock:
            if not self._active:
                return None
            dropped = self._dropped_packets_locked()
            self._dropped_before += dropped or 0
            self._delete_table_locked()
            self._active = False
            print(f"[Enforcer] Kernel blocking removed"
                  f"{'' if dropped is None else f' — {dropped} ARP frame(s) dropped by the kernel'}.",
                  flush=True)
            return dropped

    # ── blacklist changes ─────────────────────────────────────────────────────

    def _element(self, verb: str, mac: str) -> bool:
        try:
            result = self._run([verb, "element", "netdev", NFT_TABLE, NFT_SET, f"{{ {mac} }}"])
        except Exception as exc:
            print(f"[Enforcer] nft {verb} element failed for {mac}: {exc}", flush=True)
            return False
        if result.returncode != 0:
            print(f"[Enforcer] nft {verb} element failed for {mac}: {result.stderr.strip()}", flush=True)
            return False
        return True

    def block(self, mac: str) -> bool:
        """
        Start dropping this MAC's ARP frames. Returns True once the kernel is
        actually dropping them (False in simulated mode or while protection is off).
        """
        mac = normalise_mac(mac)
        if mac is None or mac in _NON_DEVICE_MACS:
            return False
        with self._lock:
            already = mac in self._wanted
            self._wanted.add(mac)
            if not self._active:
                return False
            return True if already else self._element("add", mac)

    def unblock(self, mac: str) -> None:
        mac = normalise_mac(mac)
        if mac is None:
            return
        with self._lock:
            if mac not in self._wanted:
                return
            self._wanted.discard(mac)
            if self._active:
                self._element("delete", mac)

    def load(self, macs: Iterable[str]) -> None:
        for mac in macs:
            self.block(mac)

    # ── verification ──────────────────────────────────────────────────────────

    def _dropped_packets_locked(self) -> Optional[int]:
        try:
            result = self._run(["-j", "list", "chain", "netdev", NFT_TABLE, NFT_CHAIN])
            if result.returncode != 0:
                return None
            for item in json.loads(result.stdout).get("nftables", []):
                for expr in item.get("rule", {}).get("expr", []):
                    if "counter" in expr:
                        return int(expr["counter"].get("packets", 0))
        except Exception:
            return None
        return None

    def dropped_packets(self) -> Optional[int]:
        """ARP frames the kernel has dropped since start(); None if not enforcing."""
        with self._lock:
            if not self._active:
                return None
            return self._dropped_packets_locked()

    def total_dropped(self) -> int:
        """
        ARP frames the kernel has dropped for this agent since it started,
        across every protection session. This is the figure for "blocked": it
        is counted by the kernel at the moment of the drop, so it cannot include
        a frame that slipped through while a rule was still being installed.
        """
        with self._lock:
            current = self._dropped_packets_locked() if self._active else None
            return self._dropped_before + (current or 0)

    def restore_neighbour(self, ip: Optional[str], mac: Optional[str]) -> bool:
        """
        Put a known-good IP-to-MAC mapping back into the kernel's ARP cache.

        Blocking an attacker stops any further forged replies, but the handful
        that arrived before Tier 2 flagged it may already have overwritten the
        gateway's entry — and nothing would correct that until the gateway next
        happened to answer. Only done while enforcing, i.e. on Linux.
        """
        mac = normalise_mac(mac)
        ip_tool = shutil.which("ip") or next(
            (p for p in ("/usr/sbin/ip", "/sbin/ip", "/usr/bin/ip") if os.path.exists(p)), None)
        with self._lock:
            if not self._active or not ip or not mac or not ip_tool:
                return False
            try:
                result = subprocess.run(
                    [ip_tool, "neigh", "replace", ip, "lladdr", mac, "dev", self.iface, "nud", "reachable"],
                    capture_output=True, text=True, timeout=NFT_TIMEOUT_SECONDS,
                )
            except Exception as exc:
                print(f"[Enforcer] Could not restore the ARP entry for {ip}: {exc}", flush=True)
                return False
            if result.returncode != 0:
                print(f"[Enforcer] Could not restore the ARP entry for {ip}: {result.stderr.strip()}", flush=True)
                return False
            return True

    def is_enforcing(self) -> bool:
        with self._lock:
            return self._active

