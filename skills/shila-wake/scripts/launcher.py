#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
Shila Wake System - Launcher
Starts all components: Web Server, Desktop App, and Scheduler.
"""
import os
import sys
import subprocess
import threading
import time
import signal
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent

processes = []
running = True


def start_web_server():
    """Start the web dashboard server."""
    print("[LAUNCHER] Starting Web Server...")
    proc = subprocess.Popen(
        [sys.executable, str(SCRIPT_DIR / "web_server.py")],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    processes.append(("Web Server", proc))
    return proc


def start_desktop_app():
    """Start the desktop tray app."""
    print("[LAUNCHER] Starting Desktop App...")
    proc = subprocess.Popen(
        [sys.executable, str(SCRIPT_DIR / "desktop_app.py")],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    processes.append(("Desktop App", proc))
    return proc


def monitor_process(name, proc):
    """Monitor a process and print its output."""
    try:
        for line in proc.stdout:
            if line.strip():
                print(f"[{name}] {line.strip()}")
    except:
        pass


def cleanup(sig=None, frame=None):
    """Cleanup all processes."""
    global running
    running = False
    
    print("\n[LAUNCHER] Shutting down...")
    
    for name, proc in processes:
        try:
            print(f"[LAUNCHER] Stopping {name}...")
            proc.terminate()
            proc.wait(timeout=5)
        except:
            proc.kill()
    
    print("[LAUNCHER] All processes stopped.")
    sys.exit(0)


def main():
    print("""
================================================================
            SHILA WAKE SYSTEM - LAUNCHER
            
   Starting all components...
   
   Components:
   - Web Dashboard  -> http://localhost:8765
   - Desktop App    -> System Tray
   - Scheduler      -> Background
   
   Press Ctrl+C to stop all components
================================================================
    """)
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)
    
    # Start components
    web_proc = start_web_server()
    time.sleep(2)  # Wait for web server to start
    
    desktop_proc = start_desktop_app()
    
    # Start monitoring threads
    threading.Thread(target=monitor_process, args=("WEB", web_proc), daemon=True).start()
    threading.Thread(target=monitor_process, args=("APP", desktop_proc), daemon=True).start()
    
    print("\n[LAUNCHER] All components started!")
    print("[LAUNCHER] Open http://localhost:8765 in your browser")
    print("[LAUNCHER] Look for the alarm icon in your system tray")
    print("[LAUNCHER] Press Ctrl+C to stop\n")
    
    # Open browser automatically
    time.sleep(2)
    try:
        import webbrowser
        webbrowser.open("http://localhost:8765")
    except:
        pass
    
    # Keep running
    try:
        while running:
            # Check if processes are still running
            for name, proc in processes:
                if proc.poll() is not None:
                    print(f"[LAUNCHER] {name} has stopped (exit code: {proc.returncode})")
            time.sleep(1)
    except KeyboardInterrupt:
        cleanup()


if __name__ == "__main__":
    main()
