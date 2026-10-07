#!/bin/bash

# SentiNet Installer for Kali Linux VMs

if [ "$EUID" -ne 0 ]; then
  echo "Please run this script as root (sudo ./install.sh <role>)"
  exit 1
fi

ROLE=$1
INSTALL_DIR=$(pwd)

if [ -z "$ROLE" ]; then
    echo "Usage: sudo ./install.sh [agent|admin]"
    echo "  agent : Installs the Daemon, Tray App, and Agent Dashboard"
    echo "  admin : Installs the Relay Node and Admin Dashboard"
    exit 1
fi

echo "==========================================="
echo "🛠️ Installing SentiNet ($ROLE node)..."
echo "==========================================="

echo "[1/4] Installing system dependencies..."
apt-get update
apt-get install -y python3-venv npm nftables python3-gi gir1.2-gtk-3.0
# The tray menu's library. Its package was renamed, and asking apt for a name it
# does not have fails the whole install line, so try each on its own.
apt-get install -y gir1.2-ayatanaappindicator3-0.1 \
    || apt-get install -y gir1.2-appindicator3-0.1 \
    || echo "  -> No AppIndicator package found; the tray will use its plain GTK icon."

setup_python_venv() {
    local dir=$1
    echo "Setting up Python venv in $dir..."
    cd "$INSTALL_DIR/$dir" || exit
    # --system-site-packages lets the venv see PyGObject (python3-gi), which the
    # tray icon's menu needs and which pip cannot install without a compiler.
    # Packages installed into the venv still take precedence.
    python3 -m venv --system-site-packages venv
    source venv/bin/activate
    pip install -r requirements.txt
    cd - > /dev/null
}

setup_npm() {
    local dir=$1
    echo "Installing Node modules in $dir..."
    cd "$INSTALL_DIR/$dir" || exit
    npm install
    cd - > /dev/null
}

if [ "$ROLE" = "agent" ]; then
    echo "[2/4] Setting up Agent Python environment..."
    setup_python_venv "tray-app"
    
    echo "[3/4] Setting up Agent Dashboard..."
    setup_npm "agent-dashboard"
    
    echo "[4/4] Configuring Systemd and Desktop Shortcuts..."
    # 1. Daemon Systemd Service
    sed "s|{{INSTALL_DIR}}|$INSTALL_DIR|g" scripts/sentinet-daemon.service > /etc/systemd/system/sentinet-daemon.service
    systemctl daemon-reload
    systemctl enable sentinet-daemon
    systemctl start sentinet-daemon
    echo "  -> Daemon registered and started in background."
    
    # 2. Desktop Shortcuts
    # We need to install the desktop shortcuts for the SUDO_USER, not root
    if [ -n "$SUDO_USER" ]; then
        USER_HOME=$(getent passwd "$SUDO_USER" | cut -d: -f6)
        APPS_DIR="$USER_HOME/.local/share/applications"
        mkdir -p "$APPS_DIR"
        
        sed "s|{{INSTALL_DIR}}|$INSTALL_DIR|g" scripts/sentinet-tray.desktop > "$APPS_DIR/sentinet-tray.desktop"
        sed "s|{{INSTALL_DIR}}|$INSTALL_DIR|g" scripts/sentinet-dashboard.desktop > "$APPS_DIR/sentinet-dashboard.desktop"
        
        chown -R "$SUDO_USER:$SUDO_USER" "$APPS_DIR"
        echo "  -> Desktop shortcuts created in application menu."
    else
        echo "  -> Warning: Could not detect standard user. Skipping desktop shortcuts."
    fi

elif [ "$ROLE" = "admin" ]; then
    echo "[2/4] Setting up Admin Python environment..."
    setup_python_venv "admin-backend"
    
    echo "[3/4] Setting up Admin Dashboard..."
    setup_npm "admin-dashboard"
    
    echo "[4/4] Setup complete. (Systemd for admin not implemented yet)"
else
    echo "Unknown role: $ROLE"
    exit 1
fi

echo "==========================================="
echo "✅ Installation Complete!"
echo "If you installed the agent, you can now launch the SentiNet Tray App"
echo "and Dashboard directly from your Kali Linux applications menu!"
echo "==========================================="
