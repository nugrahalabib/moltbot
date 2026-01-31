#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["schedule>=1.2.0"]
# ///
"""
Shila Wake System - Smart Alarm & Reminder System
Main entry point for the wake system daemon.

Version 2.0 - With proper date handling
"""
import argparse
import json
import os
import sys
import signal
import time
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any

# Fix Windows console encoding for emoji support
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# Add parent paths
SCRIPT_DIR = Path(__file__).parent
SKILL_DIR = SCRIPT_DIR.parent
SKILLS_DIR = SKILL_DIR.parent
MOLTBOT_DIR = SKILLS_DIR.parent

sys.path.insert(0, str(SCRIPT_DIR))

try:
    import schedule
except ImportError:
    print("Installing schedule...")
    os.system(f"{sys.executable} -m pip install schedule")
    import schedule

# ===========================================================================
# Configuration
# ===========================================================================

CONFIG_FILE = SKILL_DIR / "config.json"
ALARMS_FILE = SKILL_DIR / "alarms.json"
REMINDERS_FILE = SKILL_DIR / "reminders.json"
PID_FILE = SKILL_DIR / "wake_system.pid"
SOUNDS_DIR = SKILL_DIR / "sounds"

TUYA_SCRIPT = SKILLS_DIR / "smarthome-tuya" / "scripts" / "tuya_control.py"

DEFAULT_CONFIG = {
    "default_mode": "normal",
    "snooze_minutes": 10,
    "max_snooze": 3,
    "volume": 100,
    "sounds": {
        "gentle": "gentle_alarm.wav",
        "normal": "alarm.wav",
        "nuclear": "nuclear_alarm.wav"
    },
    "tts": {
        "enabled": True,
        "messages": {
            "gentle": "Selamat pagi, Sayang. Sudah waktunya bangun.",
            "normal": "Bangun Sayang! Sudah pagi!",
            "nuclear": "BANGUN! SUDAH TELAT! CEPAT BANGUN SEKARANG!"
        }
    },
    "tuya": {
        "enabled": True,
        "wake_lights": ["lampu meja", "soft box 1", "soft box 2", "lampu strip meja", "lampu strip dinding"],
        "ac_device": "AC Studio"
    },
    "chat": {
        "enabled": True,
        "target": "+6287877974096"
    }
}


def safe_print(message: str):
    """Print with encoding safety for Windows."""
    try:
        print(message)
    except UnicodeEncodeError:
        # Remove emojis and try again
        clean_msg = message.encode('ascii', 'ignore').decode('ascii')
        print(clean_msg)


def load_config() -> Dict:
    """Load configuration."""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                for key, value in DEFAULT_CONFIG.items():
                    if key not in config:
                        config[key] = value
                return config
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()


def save_config(config: Dict):
    """Save configuration."""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


# ===========================================================================
# Alarm Management (v2 - with proper date handling)
# ===========================================================================

def load_alarms() -> List[Dict]:
    """Load alarms from file."""
    if ALARMS_FILE.exists():
        try:
            with open(ALARMS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return []


def save_alarms(alarms: List[Dict]):
    """Save alarms to file."""
    with open(ALARMS_FILE, 'w', encoding='utf-8') as f:
        json.dump(alarms, f, indent=2, ensure_ascii=False)


def calculate_alarm_datetime(time_str: str, date_str: str = None) -> datetime:
    """
    Calculate the actual datetime for an alarm.
    
    If no date provided:
    - If time is in the future today -> use today
    - If time has passed today -> use tomorrow
    
    Returns datetime object.
    """
    now = datetime.now()
    hour, minute = map(int, time_str.split(':'))
    
    if date_str:
        # Explicit date provided
        year, month, day = map(int, date_str.split('-'))
        return datetime(year, month, day, hour, minute, 0)
    else:
        # Auto-calculate date
        alarm_today = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        if alarm_today > now:
            # Time is still in the future today
            return alarm_today
        else:
            # Time has passed, schedule for tomorrow
            return alarm_today + timedelta(days=1)


def add_alarm(time_str: str, mode: str = "normal", label: str = "", 
              repeat: str = "once", date_str: str = None) -> Dict:
    """
    Add a new alarm with proper date handling.
    
    Args:
        time_str: Time in HH:MM format
        mode: gentle, normal, or nuclear
        label: Optional label
        repeat: once, daily, or comma-separated days (mon,tue,wed,thu,fri,sat,sun)
        date_str: Optional specific date in YYYY-MM-DD format
    """
    alarms = load_alarms()
    
    # Validate time format
    try:
        hour, minute = map(int, time_str.split(':'))
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError("Invalid time")
    except:
        safe_print(f"[ERROR] Invalid time format: {time_str}. Use HH:MM")
        return None
    
    # Calculate the target datetime
    target_dt = calculate_alarm_datetime(time_str, date_str)
    
    alarm_id = f"alarm_{int(datetime.now().timestamp())}"
    
    alarm = {
        "id": alarm_id,
        "time": time_str,
        "date": target_dt.strftime("%Y-%m-%d"),  # Always store the date
        "target_datetime": target_dt.isoformat(),  # Full datetime for clarity
        "mode": mode,
        "label": label or f"Alarm {time_str}",
        "repeat": repeat,
        "enabled": True,
        "snooze_count": 0,
        "last_triggered": None,
        "created_at": datetime.now().isoformat()
    }
    
    alarms.append(alarm)
    save_alarms(alarms)
    
    safe_print(f"[OK] Alarm added: {time_str} ({mode} mode)")
    safe_print(f"     Date: {target_dt.strftime('%A, %d %B %Y')}")
    safe_print(f"     Target: {target_dt.strftime('%Y-%m-%d %H:%M')}")
    if repeat != "once":
        safe_print(f"     Repeat: {repeat}")
    if label:
        safe_print(f"     Label: {label}")
    
    return alarm


def list_alarms() -> List[Dict]:
    """List all alarms."""
    alarms = load_alarms()
    
    if not alarms:
        safe_print("No alarms set.")
        return []
    
    safe_print(f"\n{'ID':<20} {'DateTime':<20} {'Mode':<10} {'Repeat':<10} {'Label':<20} {'Enabled'}")
    safe_print("-" * 95)
    
    for alarm in alarms:
        enabled = "Yes" if alarm.get('enabled', True) else "No"
        dt_str = f"{alarm.get('date', 'N/A')} {alarm['time']}"
        safe_print(f"{alarm['id']:<20} {dt_str:<20} {alarm['mode']:<10} "
              f"{alarm.get('repeat', 'once'):<10} {alarm.get('label', '')[:20]:<20} {enabled}")
    
    return alarms


def delete_alarm(alarm_id: str = None, delete_all: bool = False) -> bool:
    """Delete an alarm."""
    if delete_all:
        save_alarms([])
        safe_print("[OK] All alarms deleted.")
        return True
    
    alarms = load_alarms()
    original_count = len(alarms)
    alarms = [a for a in alarms if a['id'] != alarm_id]
    
    if len(alarms) < original_count:
        save_alarms(alarms)
        safe_print(f"[OK] Alarm {alarm_id} deleted.")
        return True
    else:
        safe_print(f"[ERROR] Alarm {alarm_id} not found.")
        return False


def toggle_alarm(alarm_id: str, enabled: bool = None) -> bool:
    """Enable/disable an alarm."""
    alarms = load_alarms()
    
    for alarm in alarms:
        if alarm['id'] == alarm_id:
            if enabled is None:
                alarm['enabled'] = not alarm.get('enabled', True)
            else:
                alarm['enabled'] = enabled
            save_alarms(alarms)
            status = "enabled" if alarm['enabled'] else "disabled"
            safe_print(f"[OK] Alarm {alarm_id} {status}.")
            return True
    
    safe_print(f"[ERROR] Alarm {alarm_id} not found.")
    return False


def get_next_alarm() -> Optional[Dict]:
    """Get the next upcoming alarm with time remaining."""
    alarms = load_alarms()
    now = datetime.now()
    
    next_alarm = None
    min_delta = None
    
    for alarm in alarms:
        if not alarm.get('enabled', True):
            continue
        
        # Parse alarm datetime
        try:
            if alarm.get('target_datetime'):
                alarm_dt = datetime.fromisoformat(alarm['target_datetime'])
            else:
                # Fallback for old format
                hour, minute = map(int, alarm['time'].split(':'))
                date_str = alarm.get('date')
                if date_str:
                    year, month, day = map(int, date_str.split('-'))
                    alarm_dt = datetime(year, month, day, hour, minute)
                else:
                    alarm_dt = calculate_alarm_datetime(alarm['time'])
        except:
            continue
        
        # Skip if already triggered today (for one-time alarms)
        if alarm.get('repeat') == 'once' and alarm.get('last_triggered'):
            continue
        
        # For repeating alarms, recalculate next occurrence
        if alarm.get('repeat') == 'daily' and alarm_dt < now:
            alarm_dt = calculate_alarm_datetime(alarm['time'])
        
        if alarm_dt > now:
            delta = alarm_dt - now
            if min_delta is None or delta < min_delta:
                min_delta = delta
                next_alarm = {
                    'alarm': alarm,
                    'datetime': alarm_dt,
                    'delta': delta,
                    'delta_seconds': delta.total_seconds()
                }
    
    return next_alarm


# ===========================================================================
# Reminder Management
# ===========================================================================

def load_reminders() -> List[Dict]:
    """Load reminders from file."""
    if REMINDERS_FILE.exists():
        try:
            with open(REMINDERS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return []


def save_reminders(reminders: List[Dict]):
    """Save reminders to file."""
    with open(REMINDERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(reminders, f, indent=2, ensure_ascii=False)


def add_reminder(message: str, time_str: str, date_str: str = None, 
                 repeat: str = "once", priority: str = "normal") -> Dict:
    """Add a new reminder with proper date handling."""
    reminders = load_reminders()
    
    target_dt = calculate_alarm_datetime(time_str, date_str)
    
    reminder_id = f"remind_{int(datetime.now().timestamp())}"
    
    reminder = {
        "id": reminder_id,
        "message": message,
        "time": time_str,
        "date": target_dt.strftime("%Y-%m-%d"),
        "target_datetime": target_dt.isoformat(),
        "repeat": repeat,
        "priority": priority,
        "enabled": True,
        "last_triggered": None,
        "created_at": datetime.now().isoformat()
    }
    
    reminders.append(reminder)
    save_reminders(reminders)
    
    safe_print(f"[OK] Reminder added: '{message}' at {time_str}")
    safe_print(f"     Date: {target_dt.strftime('%A, %d %B %Y')}")
    if repeat != "once":
        safe_print(f"     Repeat: {repeat}")
    
    return reminder


def list_reminders() -> List[Dict]:
    """List all reminders."""
    reminders = load_reminders()
    
    if not reminders:
        safe_print("No reminders set.")
        return []
    
    safe_print(f"\n{'ID':<20} {'DateTime':<20} {'Priority':<10} {'Message':<30}")
    safe_print("-" * 85)
    
    for r in reminders:
        dt_str = f"{r.get('date', 'N/A')} {r['time']}"
        safe_print(f"{r['id']:<20} {dt_str:<20} "
              f"{r.get('priority', 'normal'):<10} {r['message'][:30]:<30}")
    
    return reminders


def delete_reminder(reminder_id: str) -> bool:
    """Delete a reminder."""
    reminders = load_reminders()
    original_count = len(reminders)
    reminders = [r for r in reminders if r['id'] != reminder_id]
    
    if len(reminders) < original_count:
        save_reminders(reminders)
        safe_print(f"[OK] Reminder {reminder_id} deleted.")
        return True
    else:
        safe_print(f"[ERROR] Reminder {reminder_id} not found.")
        return False


# ===========================================================================
# Action Executor
# ===========================================================================

def play_sound(sound_name: str):
    """Play alarm sound."""
    sound_file = SOUNDS_DIR / sound_name
    
    # Fallback to Windows beep
    try:
        import winsound
        winsound.Beep(1000, 500)
        winsound.Beep(1500, 500)
        winsound.Beep(2000, 500)
        return True
    except Exception:
        pass
    
    # Fallback to PowerShell beep
    try:
        os.system('powershell -c "[console]::beep(1000,500)"')
        return True
    except Exception:
        pass
    
    safe_print("[WARN] Could not play sound")
    return False


def execute_tuya_command(command: str, *args):
    """Execute Tuya command."""
    if not TUYA_SCRIPT.exists():
        safe_print(f"[WARN] Tuya script not found: {TUYA_SCRIPT}")
        return False
    
    cmd = f'python "{TUYA_SCRIPT}" {command} {" ".join(str(a) for a in args)}'
    result = os.system(cmd)
    return result == 0


def turn_on_lights(brightness: int = 100, color: str = "white"):
    """Turn on wake lights."""
    config = load_config()
    
    if not config['tuya']['enabled']:
        return
    
    execute_tuya_command("category", "lights", "on")
    time.sleep(0.5)
    execute_tuya_command("brightness", "--all", str(brightness))
    time.sleep(0.3)
    execute_tuya_command("color", "--all", color)


def turn_off_ac():
    """Turn off AC."""
    config = load_config()
    
    if not config['tuya']['enabled']:
        return
    
    ac_device = config['tuya'].get('ac_device', 'AC Studio')
    execute_tuya_command("ac", f'"{ac_device}"', "--power", "off")


def send_chat_notification(message: str):
    """Send chat notification via Moltbot."""
    config = load_config()
    
    if not config['chat']['enabled']:
        return
    
    # Remove emojis for safe printing
    safe_print(f"[CHAT] {message}")


def speak_tts(text: str):
    """Speak text using TTS."""
    try:
        import subprocess
        # Use simpler PowerShell TTS
        ps_script = f'Add-Type -AssemblyName System.Speech; (New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak("{text}")'
        subprocess.run(["powershell", "-Command", ps_script], capture_output=True, timeout=30)
        return True
    except Exception as e:
        safe_print(f"[TTS] {text}")
        return False


# ===========================================================================
# Wake Sequences
# ===========================================================================

def execute_gentle_wake():
    """Execute gentle wake sequence."""
    safe_print("[WAKE] Starting GENTLE wake sequence...")
    
    turn_on_lights(brightness=30, color="warm")
    time.sleep(2)
    turn_on_lights(brightness=50, color="warm")
    time.sleep(2)
    turn_on_lights(brightness=80, color="white")
    time.sleep(2)
    turn_on_lights(brightness=100, color="white")
    
    turn_off_ac()
    
    config = load_config()
    speak_tts(config['tts']['messages']['gentle'])
    send_chat_notification("Selamat pagi, Sayang! Sudah waktunya bangun~")


def execute_normal_wake():
    """Execute normal wake sequence."""
    safe_print("[WAKE] Starting NORMAL wake sequence...")
    
    turn_on_lights(brightness=100, color="white")
    turn_off_ac()
    
    config = load_config()
    play_sound(config['sounds']['normal'])
    speak_tts(config['tts']['messages']['normal'])
    send_chat_notification("Bangun Sayang! Sudah pagi!")


def execute_nuclear_wake():
    """Execute nuclear wake sequence - NO MERCY!"""
    safe_print("[WAKE] Starting NUCLEAR wake sequence!")
    
    # ALL LIGHTS MAX IMMEDIATELY
    turn_on_lights(brightness=100, color="white")
    turn_off_ac()
    
    # LOUD ALARM
    config = load_config()
    
    def alarm_loop():
        for _ in range(5):
            play_sound(config['sounds']['nuclear'])
            time.sleep(1)
    
    alarm_thread = threading.Thread(target=alarm_loop, daemon=True)
    alarm_thread.start()
    
    # TTS
    speak_tts(config['tts']['messages']['nuclear'])
    
    # Chat notification (just once, no spam)
    send_chat_notification("BANGUN!!! ALARM NUCLEAR - JANGAN DIABAIKAN!")
    
    safe_print("[WAKE] Nuclear sequence completed!")


def execute_wake(mode: str = "normal"):
    """Execute wake sequence based on mode."""
    safe_print(f"\n{'='*50}")
    safe_print(f"  SHILA WAKE SYSTEM - {mode.upper()} MODE")
    safe_print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    safe_print(f"{'='*50}\n")
    
    if mode == "gentle":
        execute_gentle_wake()
    elif mode == "nuclear":
        execute_nuclear_wake()
    else:
        execute_normal_wake()


# ===========================================================================
# Scheduler (v2 - with proper date checking)
# ===========================================================================

def check_alarms():
    """Check and trigger due alarms with proper date+time checking."""
    now = datetime.now()
    
    alarms = load_alarms()
    triggered = []
    modified = False
    
    for alarm in alarms:
        if not alarm.get('enabled', True):
            continue
        
        # Get alarm target datetime
        try:
            if alarm.get('target_datetime'):
                alarm_dt = datetime.fromisoformat(alarm['target_datetime'])
            else:
                # Fallback for old format
                hour, minute = map(int, alarm['time'].split(':'))
                date_str = alarm.get('date')
                if date_str:
                    year, month, day = map(int, date_str.split('-'))
                    alarm_dt = datetime(year, month, day, hour, minute)
                else:
                    # Old alarm without date - treat as today
                    alarm_dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        except Exception as e:
            safe_print(f"[ERROR] Could not parse alarm: {e}")
            continue
        
        # Check if it's time to trigger (within 60 second window)
        time_diff = (now - alarm_dt).total_seconds()
        
        # Trigger if:
        # - Current time is 0-60 seconds AFTER alarm time
        # - AND alarm hasn't been triggered yet for this occurrence
        if not (0 <= time_diff <= 60):
            continue
        
        # Check if already triggered
        if alarm.get('last_triggered'):
            last_trig = datetime.fromisoformat(alarm['last_triggered'])
            # Don't re-trigger if triggered within last 2 minutes
            if (now - last_trig).total_seconds() < 120:
                continue
        
        # TRIGGER!
        safe_print(f"\n[ALARM] TRIGGERING: {alarm.get('label', 'Alarm')} ({alarm['mode']} mode)")
        safe_print(f"[ALARM] Scheduled: {alarm_dt.strftime('%Y-%m-%d %H:%M')}")
        safe_print(f"[ALARM] Current:   {now.strftime('%Y-%m-%d %H:%M:%S')}")
        
        try:
            execute_wake(alarm['mode'])
        except Exception as e:
            safe_print(f"[ERROR] Wake execution failed: {e}")
        
        triggered.append(alarm)
        
        # Mark as triggered
        alarm['last_triggered'] = now.isoformat()
        modified = True
        
        # Handle one-time alarms
        if alarm.get('repeat') == 'once':
            alarm['enabled'] = False
        elif alarm.get('repeat') == 'daily':
            # Reschedule for tomorrow
            new_dt = alarm_dt + timedelta(days=1)
            alarm['date'] = new_dt.strftime('%Y-%m-%d')
            alarm['target_datetime'] = new_dt.isoformat()
    
    if modified:
        save_alarms(alarms)
    
    if triggered:
        safe_print(f"[ALARM] Triggered {len(triggered)} alarm(s)")
    
    return triggered


def check_reminders():
    """Check and trigger due reminders."""
    now = datetime.now()
    
    reminders = load_reminders()
    triggered = []
    modified = False
    
    for reminder in reminders:
        if not reminder.get('enabled', True):
            continue
        
        try:
            if reminder.get('target_datetime'):
                reminder_dt = datetime.fromisoformat(reminder['target_datetime'])
            else:
                hour, minute = map(int, reminder['time'].split(':'))
                date_str = reminder.get('date')
                if date_str:
                    year, month, day = map(int, date_str.split('-'))
                    reminder_dt = datetime(year, month, day, hour, minute)
                else:
                    reminder_dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        except:
            continue
        
        time_diff = (now - reminder_dt).total_seconds()
        
        if not (0 <= time_diff <= 60):
            continue
        
        if reminder.get('last_triggered'):
            last_trig = datetime.fromisoformat(reminder['last_triggered'])
            if (now - last_trig).total_seconds() < 120:
                continue
        
        safe_print(f"\n[REMINDER] {reminder['message']}")
        
        priority = reminder.get('priority', 'normal')
        if priority == 'high':
            play_sound("alert.wav")
            speak_tts(f"Pengingat penting: {reminder['message']}")
        
        send_chat_notification(f"Reminder: {reminder['message']}")
        triggered.append(reminder)
        
        reminder['last_triggered'] = now.isoformat()
        modified = True
        
        if reminder.get('repeat') == 'once':
            reminder['enabled'] = False
        elif reminder.get('repeat') == 'daily':
            new_dt = reminder_dt + timedelta(days=1)
            reminder['date'] = new_dt.strftime('%Y-%m-%d')
            reminder['target_datetime'] = new_dt.isoformat()
    
    if modified:
        save_reminders(reminders)
    
    return triggered


def scheduler_loop():
    """Main scheduler loop."""
    safe_print("[SCHEDULER] Starting Shila Wake System scheduler...")
    safe_print(f"[SCHEDULER] Config: {CONFIG_FILE}")
    safe_print(f"[SCHEDULER] Alarms: {ALARMS_FILE}")
    
    # Schedule checks every 30 seconds
    schedule.every(30).seconds.do(check_alarms)
    schedule.every().minute.at(":00").do(check_reminders)
    
    safe_print("[SCHEDULER] Running... (Press Ctrl+C to stop)")
    
    while True:
        try:
            schedule.run_pending()
            time.sleep(1)
        except Exception as e:
            safe_print(f"[SCHEDULER] Error: {e}")
            time.sleep(5)


# ===========================================================================
# Daemon Management
# ===========================================================================

def start_daemon():
    """Start the wake system daemon."""
    if PID_FILE.exists():
        with open(PID_FILE, 'r') as f:
            old_pid = f.read().strip()
        safe_print(f"[WARN] PID file exists (pid: {old_pid}). Daemon may already be running.")
        return False
    
    with open(PID_FILE, 'w') as f:
        f.write(str(os.getpid()))
    
    def cleanup(sig, frame):
        safe_print("\n[SCHEDULER] Shutting down...")
        if PID_FILE.exists():
            PID_FILE.unlink()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)
    
    if not CONFIG_FILE.exists():
        save_config(DEFAULT_CONFIG)
        safe_print(f"[INFO] Created default config: {CONFIG_FILE}")
    
    try:
        scheduler_loop()
    finally:
        if PID_FILE.exists():
            PID_FILE.unlink()


def stop_daemon():
    """Stop the wake system daemon."""
    if not PID_FILE.exists():
        safe_print("[INFO] Daemon is not running.")
        return True
    
    with open(PID_FILE, 'r') as f:
        pid = int(f.read().strip())
    
    try:
        os.kill(pid, signal.SIGTERM)
        safe_print(f"[OK] Sent stop signal to daemon (pid: {pid})")
        PID_FILE.unlink()
        return True
    except ProcessLookupError:
        safe_print(f"[WARN] Process {pid} not found. Removing stale PID file.")
        PID_FILE.unlink()
        return True
    except Exception as e:
        safe_print(f"[ERROR] Could not stop daemon: {e}")
        return False


def daemon_status():
    """Check daemon status."""
    if not PID_FILE.exists():
        safe_print("[STATUS] Daemon is NOT running.")
        return False
    
    with open(PID_FILE, 'r') as f:
        pid = int(f.read().strip())
    
    try:
        os.kill(pid, 0)
        safe_print(f"[STATUS] Daemon is RUNNING (pid: {pid})")
        
        next_alarm = get_next_alarm()
        if next_alarm:
            alarm = next_alarm['alarm']
            delta = next_alarm['delta']
            hours, remainder = divmod(int(delta.total_seconds()), 3600)
            minutes, seconds = divmod(remainder, 60)
            safe_print(f"\n  Next alarm: {alarm['time']} on {alarm.get('date', 'N/A')}")
            safe_print(f"  Label: {alarm.get('label', 'N/A')}")
            safe_print(f"  Mode: {alarm['mode']}")
            safe_print(f"  In: {hours}h {minutes}m {seconds}s")
        
        return True
    except ProcessLookupError:
        safe_print(f"[STATUS] Daemon NOT running (stale PID file: {pid})")
        PID_FILE.unlink()
        return False


# ===========================================================================
# Test Functions
# ===========================================================================

def test_sound():
    """Test alarm sound."""
    safe_print("[TEST] Playing test sound...")
    play_sound("alarm.wav")


def test_lights():
    """Test wake lights."""
    safe_print("[TEST] Testing lights...")
    turn_on_lights(brightness=100, color="white")
    time.sleep(2)
    turn_on_lights(brightness=50, color="blue")
    time.sleep(2)
    turn_on_lights(brightness=100, color="white")


def test_tts(text: str = "Ini adalah tes suara dari Shila Wake System"):
    """Test TTS."""
    safe_print(f"[TEST] Testing TTS: {text}")
    speak_tts(text)


def test_wake(mode: str = "normal"):
    """Test full wake sequence."""
    safe_print(f"[TEST] Testing {mode} wake sequence...")
    execute_wake(mode)


# ===========================================================================
# Routines
# ===========================================================================

def routine_morning():
    """Morning routine."""
    safe_print("[ROUTINE] Activating morning routine...")
    turn_on_lights(brightness=100, color="white")
    execute_tuya_command("ac", '"AC Studio"', "--power", "on", "--temp", "26", "--mode", "cool")
    speak_tts("Selamat pagi! Semoga hari ini menyenangkan.")


def routine_work():
    """Work mode routine."""
    safe_print("[ROUTINE] Activating work mode...")
    turn_on_lights(brightness=80, color="white")
    execute_tuya_command("ac", '"AC Studio"', "--power", "on", "--temp", "24", "--mode", "cool")


def routine_sleep():
    """Sleep routine."""
    safe_print("[ROUTINE] Activating sleep mode...")
    turn_on_lights(brightness=10, color="warm")
    execute_tuya_command("ac", '"AC Studio"', "--power", "on", "--temp", "26", "--mode", "cool")
    time.sleep(5)
    execute_tuya_command("category", "lights", "off")


def routine_movie():
    """Movie routine."""
    safe_print("[ROUTINE] Activating movie mode...")
    execute_tuya_command("category", "lights", "off")
    execute_tuya_command("ac", '"AC Studio"', "--power", "on", "--temp", "24", "--mode", "cool")


# ===========================================================================
# CLI
# ===========================================================================

def main():
    parser = argparse.ArgumentParser(description='Shila Wake System v2.0')
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # start
    subparsers.add_parser('start', help='Start the wake system daemon')
    
    # stop
    subparsers.add_parser('stop', help='Stop the wake system daemon')
    
    # status
    subparsers.add_parser('status', help='Check daemon status')
    
    # alarm
    alarm_parser = subparsers.add_parser('alarm', help='Alarm management')
    alarm_sub = alarm_parser.add_subparsers(dest='alarm_action')
    
    alarm_add = alarm_sub.add_parser('add', help='Add alarm')
    alarm_add.add_argument('time', help='Time (HH:MM)')
    alarm_add.add_argument('--mode', choices=['gentle', 'normal', 'nuclear'], default='normal')
    alarm_add.add_argument('--label', default='')
    alarm_add.add_argument('--repeat', default='once', help='once, daily, or days (mon,tue,wed...)')
    alarm_add.add_argument('--date', help='Specific date (YYYY-MM-DD), default: auto')
    
    alarm_sub.add_parser('list', help='List alarms')
    
    alarm_del = alarm_sub.add_parser('delete', help='Delete alarm')
    alarm_del.add_argument('alarm_id', nargs='?', help='Alarm ID')
    alarm_del.add_argument('--all', action='store_true', help='Delete all alarms')
    
    # remind
    remind_parser = subparsers.add_parser('remind', help='Reminder management')
    remind_parser.add_argument('message', nargs='?', help='Reminder message')
    remind_parser.add_argument('--at', help='Time (HH:MM)')
    remind_parser.add_argument('--date', help='Date (YYYY-MM-DD)')
    remind_parser.add_argument('--repeat', default='once')
    remind_parser.add_argument('--priority', choices=['low', 'normal', 'high'], default='normal')
    remind_parser.add_argument('--list', action='store_true', help='List reminders')
    remind_parser.add_argument('--delete', help='Delete reminder by ID')
    
    # test
    test_parser = subparsers.add_parser('test', help='Test functions')
    test_parser.add_argument('what', choices=['sound', 'lights', 'tts', 'wake'])
    test_parser.add_argument('--mode', default='normal')
    test_parser.add_argument('--text', default='Ini adalah tes suara')
    
    # routine
    routine_parser = subparsers.add_parser('routine', help='Activate routine')
    routine_parser.add_argument('name', choices=['morning', 'work', 'sleep', 'movie'])
    
    # check (manual check)
    subparsers.add_parser('check', help='Manually check alarms now')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    if args.command == 'start':
        start_daemon()
    elif args.command == 'stop':
        stop_daemon()
    elif args.command == 'status':
        daemon_status()
    elif args.command == 'check':
        safe_print("[CHECK] Running manual alarm check...")
        check_alarms()
        check_reminders()
    elif args.command == 'alarm':
        if args.alarm_action == 'add':
            add_alarm(args.time, args.mode, args.label, args.repeat, args.date)
        elif args.alarm_action == 'list':
            list_alarms()
        elif args.alarm_action == 'delete':
            delete_alarm(args.alarm_id, args.all)
        else:
            alarm_parser.print_help()
    elif args.command == 'remind':
        if args.list:
            list_reminders()
        elif args.delete:
            delete_reminder(args.delete)
        elif args.message and args.at:
            add_reminder(args.message, args.at, args.date, args.repeat, args.priority)
        else:
            remind_parser.print_help()
    elif args.command == 'test':
        if args.what == 'sound':
            test_sound()
        elif args.what == 'lights':
            test_lights()
        elif args.what == 'tts':
            test_tts(args.text)
        elif args.what == 'wake':
            test_wake(args.mode)
    elif args.command == 'routine':
        routines = {'morning': routine_morning, 'work': routine_work, 
                   'sleep': routine_sleep, 'movie': routine_movie}
        routines[args.name]()


if __name__ == '__main__':
    main()
