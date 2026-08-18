import os
import sys
import subprocess

def check_pyinstaller():
    try:
        import PyInstaller
    except ImportError:
        print("PyInstaller is not installed. Installing it now...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

def build():
    check_pyinstaller()
    import PyInstaller.__main__
    
    # We must run PyInstaller from within the tray-app directory so it finds local modules
    base_dir = os.path.dirname(os.path.abspath(__file__))
    tray_dir = os.path.join(base_dir, "tray-app")
    os.chdir(tray_dir)
    
    print("\n" + "="*50)
    print("📦 BUILDING SENTINET DAEMON")
    print("="*50)
    
    # Bundle the daemon into a single executable, including the ML models
    # Note: On Windows, use ';' instead of ':' for add-data separator. We'll use os.pathsep.
    separator = os.pathsep
    
    PyInstaller.__main__.run([
        'sentinet_daemon.py',
        '--onefile',
        '--name=sentinet_daemon',
        f'--add-data=ml_models/*{separator}ml_models/',
        '--clean'
    ])
    
    print("\n" + "="*50)
    print("📦 BUILDING SENTINET TRAY APP")
    print("="*50)
    
    # Bundle the tray app into a single windowless executable
    PyInstaller.__main__.run([
        'sentinet_tray.py',
        '--onefile',
        '--name=sentinet_tray',
        '--windowed', # Suppress the console window (acts as a true background app)
        '--clean'
    ])
    
    print("\n✅ Build Complete!")
    print(f"Executables are located in: {os.path.join(tray_dir, 'dist')}")

if __name__ == "__main__":
    build()
