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
import os
import sys
import webbrowser


def _select_linux_backend():
    """
    Choose pystray's Linux backend before it is imported.

    Left to itself pystray tries AppIndicator, then GTK, then raw Xorg. The
    first two need PyGObject (`gi`), a system package that an ordinary venv
    cannot see — so inside one, pystray silently lands on the Xorg backend,
    which has no menu at all and draws the icon without transparency. That is
    the tray icon that looks wrong and does nothing when clicked.

    Probing here also sidesteps a pystray bug: with `gi` present but no
    AppIndicator library, its AppIndicator backend raises ValueError instead of
    ImportError, which crashes the import rather than falling through to GTK.

    Returns the backend chosen, or None to leave the choice to pystray.
    """
    if not sys.platform.startswith("linux") or os.environ.get("PYSTRAY_BACKEND"):
        return os.environ.get("PYSTRAY_BACKEND")
    try:
        import gi
        gi.require_version("Gtk", "3.0")
    except (ImportError, ValueError):
        os.environ["PYSTRAY_BACKEND"] = "xorg"
        return "xorg"
    for namespace in ("AyatanaAppIndicator3", "AppIndicator3"):
        try:
            gi.require_version(namespace, "0.1")
            os.environ["PYSTRAY_BACKEND"] = "appindicator"
            return "appindicator"
        except ValueError:
            continue
    os.environ["PYSTRAY_BACKEND"] = "gtk"
    return "gtk"


TRAY_BACKEND = _select_linux_backend()

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
            # A backend with no menu (Xorg) only ever fires the default item,
            # on a click of the icon — so make that the toggle, or the icon
            # would do nothing at all. Where there is a menu, clicking the icon
            # should open it rather than flip protection by surprise.
            default=not pystray.Icon.HAS_MENU,
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
    last_protected = [None]

    # keep the tray icon in sync when state changes via IPC
    def refresh():
        current_state = state.is_protected()
        if last_protected[0] != current_state:
            icon.icon = make_icon_image(current_state)
            icon.update_menu()
            last_protected[0] = current_state

    state.on_change(refresh)
    return icon


def _install_windows_close_handler(icon):
    """Make ``stop_all.bat`` / a closed console window remove the notify icon.

    A force-killed process (``taskkill /F``, or any other TerminateProcess)
    never runs Python cleanup code, so pystray never sends the Shell_NotifyIcon
    NIM_DELETE that removes the icon - it lingers as a "ghost" until Explorer
    happens to redraw the tray. Handling CTRL_CLOSE/LOGOFF/SHUTDOWN lets a
    *graceful* close call icon.stop() first, so the icon disappears immediately.
    Windows-only; keeps a reference to the ctypes callback alive to prevent GC.
    """
    import ctypes

    CTRL_CLOSE_EVENT = 2
    CTRL_LOGOFF_EVENT = 5
    CTRL_SHUTDOWN_EVENT = 6
    HANDLER_ROUTINE = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_uint)

    def handler(ctrl_type):
        if ctrl_type in (CTRL_CLOSE_EVENT, CTRL_LOGOFF_EVENT, CTRL_SHUTDOWN_EVENT):
            icon.stop()
            return 1
        return 0

    callback = HANDLER_ROUTINE(handler)
    ctypes.windll.kernel32.SetConsoleCtrlHandler(callback, True)
    return callback


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
    if pystray.Icon.HAS_MENU:
        print("[SentiNet Tray] Tray icon is running. Right-click it for the menu.")
    else:
        print("[SentiNet Tray] Tray icon is running WITHOUT a menu: PyGObject is not visible to")
        print("                this Python, so only the basic Xorg tray is available. Clicking")
        print("                the icon toggles protection. For the full menu:")
        print("                  sudo apt-get install -y python3-gi gir1.2-gtk-3.0 gir1.2-ayatanaappindicator3-0.1")
        print("                  sed -i 's/^include-system-site-packages.*/include-system-site-packages = true/' venv/pyvenv.cfg")

    icon = build(state)
    _keepalive = _install_windows_close_handler(icon) if sys.platform == "win32" else None
    try:
        icon.run()  # blocks on the main thread until Quit
    finally:
        ipc_client.stop()
        api.stop()
        print("[SentiNet Tray] Shut down cleanly.")


if __name__ == "__main__":
    main()
