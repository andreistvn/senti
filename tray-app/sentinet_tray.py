"""
SentiNet Agent — System Tray Controller (unprivileged).

Run this on your machine (NOT as root)::

    cd tray-app
    python -m venv .venv
    source .venv/bin/activate         # Windows: .venv\\\\Scripts\\\\activate
    pip install -r requirements.txt
    python sentinet_tray.py

A shield icon appears in your OS tray/menu bar. Right-click it to toggle
protection, open the dashboard, or quit. While the tray runs it serves a local
API on http://127.0.0.1:8770 that the web dashboard reads for live state.

This process is **unprivileged**. It does not touch raw sockets or perform any
packet capture. All security-critical state comes from the root-privileged
daemon (``sentinet_daemon.py``) via IPC.
"""
import webbrowser

import pystray
from PIL import Image, ImageDraw

from api_server import ApiServer
from config import API_HOST, API_PORT, DASHBOARD_URL
from state import AgentState

# SentiNet palette
GREEN = (0, 204, 102, 255)
GREY = (58, 80, 112, 255)
NAVY = (13, 27, 62, 255)
WHITE = (255, 255, 255, 255)


def make_icon_image(protected: bool):
    """Draw a simple shield glyph, green when protected, grey when off."""
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    accent = GREEN if protected else GREY

    # shield body (rounded top, pointed bottom)
    d.polygon(
        [(32, 4), (58, 14), (58, 34), (32, 60), (6, 34), (6, 14)],
        fill=NAVY,
        outline=accent,
    )
    # inner check / dot
    if protected:
        d.line([(22, 32), (29, 40), (44, 22)], fill=accent, width=5, joint="curve")
    else:
        d.ellipse([(27, 27), (37, 37)], outline=accent, width=4)
    return img


def build(state: AgentState):
    def status_text(_item):
        if not state.daemon_connected():
            return "Status: DAEMON DISCONNECTED"
        return "Status: PROTECTED" if state.is_protected() else "Status: UNPROTECTED"

    def on_toggle(icon, _item):
        state.toggle()
        # The actual state change will arrive via IPC TOGGLE_ACK.
        # The on_change listener below will refresh the icon.

    def on_open_dashboard(_icon, _item):
        webbrowser.open(DASHBOARD_URL)

    def on_quit(icon, _item):
        icon.stop()

    menu = pystray.Menu(
        pystray.MenuItem(status_text, None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(
            "Protection Active",
            on_toggle,
            checked=lambda _i: state.is_protected(),
        ),
        pystray.MenuItem("Open Dashboard", on_open_dashboard),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit SentiNet", on_quit),
    )

    icon = pystray.Icon(
        "sentinet",
        icon=make_icon_image(state.is_protected()),
        title="SentiNet Agent",
        menu=menu,
    )

    # keep the tray icon in sync when state changes via IPC
    def refresh():
        icon.icon = make_icon_image(state.is_protected())
        icon.update_menu()

    state.on_change(refresh)
    return icon


def main():
    state = AgentState()

    # Connect to the root-privileged daemon over IPC.
    ipc_client = state.connect_daemon()

    # Start the HTTP API server (serves the IPC-mirrored state to the dashboard).
    api = ApiServer(state).start()

    daemon_label = "CONNECTED" if state.daemon_connected() else "WAITING (will auto-connect)"
    print(f"[SentiNet Tray] Daemon IPC: {daemon_label}")
    print(f"[SentiNet Tray] API listening on http://{API_HOST}:{API_PORT}")
    print(f"[SentiNet Tray] Dashboard target: {DASHBOARD_URL}")
    print("[SentiNet Tray] Tray icon is running. Right-click it for the menu.")

    icon = build(state)
    try:
        icon.run()  # blocks on the main thread until Quit
    finally:
        ipc_client.stop()
        api.stop()
        print("[SentiNet Tray] Shut down cleanly.")


if __name__ == "__main__":
    main()
