#!/usr/bin/env python3
"""
Shila Wake - Feature Test Script
Tests each Smart Home Device and Additional Action feature individually
"""

import sys
import os
from pathlib import Path

# Setup paths
SCRIPT_DIR = Path(__file__).parent
SKILL_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

from wake_system import (
    execute_tuya_command,
    speak_tts,
    send_chat_notification,
    turn_on_lights,
    turn_off_ac,
    play_sound,
    TUYA_SCRIPT,
    SOUNDS_DIR
)

def test_result(name, success, message=""):
    status = "✅ PASS" if success else "❌ FAIL"
    print(f"{status} | {name}: {message}")
    return success

def main():
    print("\n" + "="*60)
    print("SHILA WAKE - FEATURE TESTING")
    print("="*60 + "\n")
    
    results = []
    
    # ========== TEST 1: Tuya Script Exists ==========
    print("\n--- Testing Smart Home (Tuya) ---")
    exists = TUYA_SCRIPT.exists()
    results.append(test_result(
        "Tuya Script Exists", 
        exists,
        str(TUYA_SCRIPT) if exists else "NOT FOUND"
    ))
    
    # Test if Tuya script can be imported/called
    if exists:
        try:
            import subprocess
            result = subprocess.run(
                ["python", str(TUYA_SCRIPT), "--help"],
                capture_output=True,
                text=True,
                timeout=10
            )
            results.append(test_result(
                "Tuya Script Runnable",
                result.returncode == 0,
                "Script runs" if result.returncode == 0 else result.stderr[:50]
            ))
        except Exception as e:
            results.append(test_result("Tuya Script Runnable", False, str(e)[:50]))
    
    # ========== TEST 2: Sound Files ==========
    print("\n--- Testing Sound System ---")
    sound_files = list(SOUNDS_DIR.glob("*.mp3")) if SOUNDS_DIR.exists() else []
    results.append(test_result(
        "Sound Directory Exists",
        SOUNDS_DIR.exists(),
        str(SOUNDS_DIR)
    ))
    results.append(test_result(
        "Sound Files Available",
        len(sound_files) > 0,
        f"{len(sound_files)} MP3 files found"
    ))
    
    # ========== TEST 3: TTS ==========
    print("\n--- Testing TTS (Text-to-Speech) ---")
    try:
        # Check if pyttsx3 is available
        import pyttsx3
        results.append(test_result(
            "pyttsx3 Module",
            True,
            "Installed"
        ))
        # Try to initialize
        try:
            engine = pyttsx3.init()
            results.append(test_result(
                "TTS Engine Init",
                True,
                "Engine initialized successfully"
            ))
        except Exception as e:
            results.append(test_result("TTS Engine Init", False, str(e)[:50]))
    except ImportError:
        results.append(test_result("pyttsx3 Module", False, "NOT INSTALLED - pip install pyttsx3"))
    
    # ========== TEST 4: WhatsApp CLI ==========
    print("\n--- Testing WhatsApp (wacli) ---")
    try:
        import subprocess
        result = subprocess.run(["wacli", "--version"], capture_output=True, text=True, timeout=5)
        results.append(test_result(
            "wacli Installed",
            result.returncode == 0,
            result.stdout.strip() if result.returncode == 0 else "Not found in PATH"
        ))
    except FileNotFoundError:
        results.append(test_result("wacli Installed", False, "NOT INSTALLED - wacli tidak ada di PATH"))
    except Exception as e:
        results.append(test_result("wacli Installed", False, str(e)[:50]))
    
    # ========== TEST 5: Chat Notification (Moltbot) ==========
    print("\n--- Testing Chat Notification ---")
    # Check if moltbot gateway is accessible
    try:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex(('localhost', 5555))  # Common Moltbot port
        sock.close()
        if result == 0:
            results.append(test_result("Moltbot Gateway", True, "Port 5555 accessible"))
        else:
            # Try gateway on 8080
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex(('localhost', 8080))
            sock.close()
            results.append(test_result(
                "Moltbot Gateway", 
                result == 0, 
                "Port 8080 accessible" if result == 0 else "No gateway port found"
            ))
    except Exception as e:
        results.append(test_result("Moltbot Gateway", False, str(e)[:50]))
    
    # ========== SUMMARY ==========
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    passed = sum(1 for r in results if r)
    total = len(results)
    print(f"\nPassed: {passed}/{total}")
    print(f"Failed: {total - passed}/{total}")
    
    print("\n" + "="*60)
    print("FEATURE STATUS")
    print("="*60)
    print("""
🏠 SMART HOME DEVICES:
- 💡 Lights (Tuya) : Requires tuya_control.py + Tuya credentials
- ❄️ AC (Tuya)     : Requires tuya_control.py + Tuya credentials  
- 🔌 Plugs (Tuya)  : Requires tuya_control.py + Tuya credentials

🎯 ADDITIONAL ACTIONS:
- 🎤 Voice TTS    : Requires pyttsx3 module
- 📱 WhatsApp     : Requires wacli installed and authenticated
- ✈️ Telegram     : Placeholder - needs implementation
- 🌤️ Weather      : Uses TTS for announcement
- 🎵 Music        : Placeholder - needs implementation
- 💪 Quote        : Uses TTS for announcement
- 📢 Spam Mode    : Uses chat notification

🔊 SOUND SYSTEM:
- Alarm sounds play via system audio
""")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
