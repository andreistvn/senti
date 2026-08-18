import time
import random
import requests
import socket

# A list of top websites to simulate normal browsing
SITES = [
    "http://www.google.com",
    "http://www.youtube.com",
    "http://www.facebook.com",
    "http://www.wikipedia.org",
    "http://www.yahoo.com",
    "http://www.reddit.com",
    "http://www.amazon.com",
]

def generate_benign_traffic():
    """
    Constantly ping various top websites, perform DNS lookups, 
    and download small files to simulate baseline noise.
    """
    print("[BenignTraffic] Starting benign traffic generator...")
    while True:
        target = random.choice(SITES)
        try:
            print(f"[BenignTraffic] Browsing {target}")
            # Simulate a quick DNS lookup
            hostname = target.replace("http://", "").replace("https://", "").split("/")[0]
            socket.gethostbyname(hostname)
            
            # Simulate an HTTP request
            requests.get(target, timeout=2.0)
            
            # Simulate user reading the page (1 to 5 seconds)
            time.sleep(random.uniform(1.0, 5.0))
        except Exception as e:
            print(f"[BenignTraffic] Error accessing {target}: {e}")
            time.sleep(1)

if __name__ == "__main__":
    try:
        generate_benign_traffic()
    except KeyboardInterrupt:
        print("\n[BenignTraffic] Stopped.")
