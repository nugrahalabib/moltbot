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

# ===========================================================================
# Active Alarm State (for snooze/dismiss functionality)
# ===========================================================================

ACTIVE_ALARM = {
    "id": None,
    "alarm_data": None,
    "started_at": None,
    "snooze_count": 0,
    "sound_thread": None,
    "spam_thread": None,
    "browser_thread": None,
    "is_active": False,
    "math_question": None,
    "math_answer": None,
    "sound_file": None
}

# Lock for thread safety
ACTIVE_ALARM_LOCK = threading.Lock()


def set_max_volume():
    """Set Windows system volume to 100%."""
    try:
        import subprocess
        # Method 1: PowerShell with audio library
        ps_script = '''
        $obj = New-Object -ComObject WScript.Shell
        1..50 | ForEach-Object { $obj.SendKeys([char]175) }
        '''
        subprocess.run(
            ["powershell", "-Command", ps_script],
            capture_output=True,
            timeout=10
        )
        safe_print("[VOLUME] Set to maximum")
        return True
    except Exception as e:
        safe_print(f"[VOLUME] Warning: Could not set max volume: {e}")
        return False


def open_alarm_browser():
    """Open browser to active alarm page."""
    try:
        import webbrowser
        url = "http://localhost:8765/alarm-active"
        webbrowser.open(url)
        safe_print(f"[BROWSER] Opened: {url}")
        return True
    except Exception as e:
        safe_print(f"[BROWSER] Error: {e}")
        return False


def browser_watchdog():
    """
    Keep browser open while alarm is active.
    Only reopens browser every 30 seconds as a safety check.
    The main browser open happens once at alarm start.
    """
    import webbrowser
    safe_print("[BROWSER WATCHDOG] Started - will check every 30s if browser needs reopening")
    
    # Wait 30 seconds before first check (give user time to interact)
    time.sleep(30)
    
    while ACTIVE_ALARM["is_active"]:
        # Only reopen as a safety fallback every 30 seconds
        if ACTIVE_ALARM["is_active"]:
            try:
                webbrowser.open("http://localhost:8765/alarm-active")
                safe_print("[BROWSER WATCHDOG] Safety check - reopening browser")
            except:
                pass
        time.sleep(30)  # Check every 30 seconds, not every 10
    
    safe_print("[BROWSER WATCHDOG] Stopped")


def generate_math_problem():
    """Generate a grade 6 math problem."""
    import random
    
    problem_type = random.choice(["multiply_add", "multiply_sub", "parentheses", "square"])
    
    if problem_type == "multiply_add":
        a, b, c = random.randint(3, 12), random.randint(3, 9), random.randint(5, 20)
        question = f"{a} × {b} + {c}"
        answer = a * b + c
    elif problem_type == "multiply_sub":
        a, b, c = random.randint(5, 12), random.randint(3, 9), random.randint(5, 15)
        answer = a * b - c
        if answer < 0:  # Ensure positive
            c = random.randint(1, a * b - 1)
            answer = a * b - c
        question = f"{a} × {b} - {c}"
    elif problem_type == "parentheses":
        a, b, c = random.randint(2, 8), random.randint(2, 8), random.randint(2, 6)
        question = f"({a} + {b}) × {c}"
        answer = (a + b) * c
    else:  # square
        a, b = random.randint(3, 9), random.randint(5, 20)
        question = f"{a}² + {b}"
        answer = a ** 2 + b
    
    return question, answer


def sound_loop_worker(sound_file: str):
    """Loop sound continuously until alarm is dismissed/snoozed."""
    safe_print(f"[SOUND LOOP] Starting continuous playback: {sound_file}")
    
    while ACTIVE_ALARM["is_active"]:
        try:
            play_sound(sound_file)
            time.sleep(1)  # Small gap between loops
        except Exception as e:
            safe_print(f"[SOUND LOOP] Error: {e}")
            time.sleep(2)
    
    safe_print("[SOUND LOOP] Stopped")


def spam_loop_worker(message: str, channels: list):
    """
    Spam TTS/Telegram/WhatsApp continuously until alarm is dismissed.
    This loops FOREVER until user dismisses the alarm - no limit!
    """
    safe_print(f"[SPAM LOOP] Starting INFINITE spam on channels: {channels}")
    
    count = 0
    while ACTIVE_ALARM["is_active"]:
        count += 1
        try:
            # TTS spam
            if "tts" in channels:
                speak_tts(message)
            
            # Telegram spam
            if "telegram" in channels:
                try:
                    from gateway_client import send_telegram_message
                    send_telegram_message(message)
                    safe_print(f"[SPAM] Telegram sent #{count}")
                except Exception as e:
                    safe_print(f"[SPAM] Telegram failed: {e}")
            
            # WhatsApp spam
            if "whatsapp" in channels:
                try:
                    from gateway_client import send_whatsapp_message
                    send_whatsapp_message(message)
                    safe_print(f"[SPAM] WhatsApp sent #{count}")
                except Exception as e:
                    safe_print(f"[SPAM] WhatsApp failed: {e}")
            
            safe_print(f"[SPAM] Repeat #{count} - continues until alarm dismissed!")
            time.sleep(15)  # Spam every 15 seconds
        except Exception as e:
            safe_print(f"[SPAM LOOP] Error: {e}")
            time.sleep(5)
    
    safe_print(f"[SPAM LOOP] Stopped after {count} repeats")


def start_active_alarm(alarm: Dict, sound_file: str):
    """Start the active alarm state with all features."""
    global ACTIVE_ALARM
    
    with ACTIVE_ALARM_LOCK:
        # Generate math problem
        question, answer = generate_math_problem()
        
        ACTIVE_ALARM["id"] = alarm.get("id")
        ACTIVE_ALARM["alarm_data"] = alarm
        ACTIVE_ALARM["started_at"] = datetime.now().isoformat()
        ACTIVE_ALARM["snooze_count"] = 0
        ACTIVE_ALARM["is_active"] = True
        ACTIVE_ALARM["math_question"] = question
        ACTIVE_ALARM["math_answer"] = answer
        ACTIVE_ALARM["sound_file"] = sound_file
        
        # Set max volume
        set_max_volume()
        
        # Open browser
        open_alarm_browser()
        
        # Start browser watchdog
        browser_thread = threading.Thread(target=browser_watchdog, daemon=True)
        browser_thread.start()
        ACTIVE_ALARM["browser_thread"] = browser_thread
        
        # Start sound loop
        sound_thread = threading.Thread(target=sound_loop_worker, args=(sound_file,), daemon=True)
        sound_thread.start()
        ACTIVE_ALARM["sound_thread"] = sound_thread
        
        # Check for spam action and start spam loop
        actions = alarm.get("actions", [])
        for action in actions:
            if action.get("id") == "spam":
                spam_message = action.get("message", "BANGUN SEKARANG!")
                spam_channels = action.get("channels", ["tts"])
                spam_thread = threading.Thread(
                    target=spam_loop_worker, 
                    args=(spam_message, spam_channels), 
                    daemon=True
                )
                spam_thread.start()
                ACTIVE_ALARM["spam_thread"] = spam_thread
                break
        
        safe_print(f"[ACTIVE ALARM] Started: {alarm.get('label', 'Alarm')}")
        safe_print(f"[ACTIVE ALARM] Math problem: {question} = ?")


def snooze_active_alarm(minutes: int) -> Dict:
    """Snooze the active alarm for X minutes."""
    global ACTIVE_ALARM
    
    with ACTIVE_ALARM_LOCK:
        if not ACTIVE_ALARM["is_active"]:
            return {"success": False, "error": "No active alarm"}
        
        ACTIVE_ALARM["is_active"] = False  # Stop sound and spam loops
        ACTIVE_ALARM["snooze_count"] += 1
        
        alarm_data = ACTIVE_ALARM["alarm_data"]
        sound_file = ACTIVE_ALARM["sound_file"]
        
        resume_time = datetime.now() + timedelta(minutes=minutes)
        
        safe_print(f"[SNOOZE] Alarm snoozed for {minutes} minutes. Resume at {resume_time.strftime('%H:%M:%S')}")
        
        # Schedule re-trigger
        def re_trigger():
            safe_print(f"[SNOOZE] Snooze ended, re-triggering alarm...")
            # Re-execute actions
            if alarm_data:
                execute_alarm_actions(alarm_data)
            # Restart active alarm
            start_active_alarm(alarm_data, sound_file)
        
        timer = threading.Timer(minutes * 60, re_trigger)
        timer.start()
        
        return {
            "success": True,
            "snooze_minutes": minutes,
            "snooze_count": ACTIVE_ALARM["snooze_count"],
            "resume_at": resume_time.isoformat()
        }


def dismiss_active_alarm(answer: int) -> Dict:
    """Dismiss the active alarm by answering math problem correctly."""
    global ACTIVE_ALARM
    
    with ACTIVE_ALARM_LOCK:
        if not ACTIVE_ALARM["is_active"]:
            return {"success": False, "error": "No active alarm"}
        
        correct_answer = ACTIVE_ALARM["math_answer"]
        
        if answer == correct_answer:
            ACTIVE_ALARM["is_active"] = False
            alarm_label = ACTIVE_ALARM["alarm_data"].get("label", "Alarm") if ACTIVE_ALARM["alarm_data"] else "Alarm"
            
            # Clear state
            ACTIVE_ALARM["id"] = None
            ACTIVE_ALARM["alarm_data"] = None
            ACTIVE_ALARM["math_question"] = None
            ACTIVE_ALARM["math_answer"] = None
            
            safe_print(f"[DISMISS] Alarm dismissed successfully! Answer was correct: {correct_answer}")
            
            return {
                "success": True,
                "message": "Alarm dismissed! Selamat pagi!"
            }
        else:
            # Generate new math problem
            new_question, new_answer = generate_math_problem()
            ACTIVE_ALARM["math_question"] = new_question
            ACTIVE_ALARM["math_answer"] = new_answer
            
            safe_print(f"[DISMISS] Wrong answer! {answer} != {correct_answer}. New problem: {new_question}")
            
            return {
                "success": False,
                "error": "wrong_answer",
                "message": "Jawaban salah! Coba lagi.",
                "new_question": new_question
            }


def get_active_alarm_status() -> Dict:
    """Get current active alarm status."""
    with ACTIVE_ALARM_LOCK:
        if not ACTIVE_ALARM["is_active"]:
            return {"is_active": False}
        
        alarm_data = ACTIVE_ALARM["alarm_data"] or {}
        
        return {
            "is_active": True,
            "alarm_id": ACTIVE_ALARM["id"],
            "label": alarm_data.get("label", "Alarm"),
            "mode": alarm_data.get("mode", "normal"),
            "started_at": ACTIVE_ALARM["started_at"],
            "snooze_count": ACTIVE_ALARM["snooze_count"],
            "math_question": ACTIVE_ALARM["math_question"]
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


def add_alarm(
    time_str: str, 
    mode: str = "normal", 
    label: str = "", 
    repeat: str = "once", 
    date_str: str = None,
    sound: str = None,
    days: List[str] = None,
    devices: List[Dict] = None,
    actions: List[Dict] = None
) -> Dict:
    """
    Add a new alarm with devices and actions support.
    
    Args:
        time_str: Time in HH:MM format
        mode: gentle, normal, or nuclear
        label: Optional label
        repeat: once, daily, weekdays, weekends, weekly, monthly, custom
        date_str: Optional specific date in YYYY-MM-DD format
        sound: Sound file path (defaults to mode-specific sound)
        days: List of days for custom repeat (mon, tue, wed, thu, fri, sat, sun)
        devices: List of device configurations for smart home control
        actions: List of additional actions (voice, whatsapp, weather, etc.)
    
    Returns:
        The created alarm dict, or None if validation fails
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
    
    # Get default sound if not specified
    if not sound:
        config = load_config()
        sound = config.get("sounds", {}).get(mode, "alarm.wav")
    
    alarm_id = f"alarm_{int(datetime.now().timestamp())}"
    
    alarm = {
        "id": alarm_id,
        "time": time_str,
        "date": target_dt.strftime("%Y-%m-%d"),
        "target_datetime": target_dt.isoformat(),
        "mode": mode,
        "label": label or f"Alarm {time_str}",
        "sound": sound,
        "repeat": repeat,
        "days": days or [],
        "enabled": True,
        "snooze_count": 0,
        "devices": devices or [],
        "actions": actions or [],
        "last_triggered": None,
        "created_at": datetime.now().isoformat()
    }
    
    alarms.append(alarm)
    save_alarms(alarms)
    
    # Log activity
    log_activity(
        event_type="alarm_created",
        text=f"Alarm created: {time_str} ({mode} mode) - {label or 'No label'}"
    )
    
    safe_print(f"[OK] Alarm added: {time_str} ({mode} mode)")
    safe_print(f"     Date: {target_dt.strftime('%A, %d %B %Y')}")
    safe_print(f"     Target: {target_dt.strftime('%Y-%m-%d %H:%M')}")
    if repeat != "once":
        safe_print(f"     Repeat: {repeat}")
    if label:
        safe_print(f"     Label: {label}")
    if devices:
        safe_print(f"     Devices: {len(devices)} configured")
    if actions:
        safe_print(f"     Actions: {len(actions)} configured")
    
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
# Routine Management
# ===========================================================================

ROUTINES_FILE = SKILL_DIR / "routines.json"


def load_routines() -> List[Dict]:
    """Load routines from file."""
    if ROUTINES_FILE.exists():
        try:
            with open(ROUTINES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return []


def save_routines(routines: List[Dict]):
    """Save routines to file."""
    with open(ROUTINES_FILE, 'w', encoding='utf-8') as f:
        json.dump(routines, f, indent=2, ensure_ascii=False)


def add_routine(data: Dict) -> Dict:
    """Create a new routine."""
    routines = load_routines()
    
    routine = {
        "id": f"routine_{int(datetime.now().timestamp())}",
        "name": data.get("name", "New Routine"),
        "icon": data.get("icon", "🎛️"),
        "color": data.get("color", "gray"),
        "description": data.get("description", ""),
        "trigger_time": data.get("trigger_time"),
        "trigger_date": data.get("trigger_date"),
        "mode": data.get("mode", "normal"),
        "sound": data.get("sound"),
        "repeat": data.get("repeat", "once"),
        "days": data.get("days", []),
        "devices": data.get("devices", []),
        "actions": data.get("actions", []),
        "enabled": True,
        "run_count": 0,
        "success_count": 0,
        "last_triggered": None,
        "created_at": datetime.now().isoformat()
    }
    
    routines.append(routine)
    save_routines(routines)
    
    safe_print(f"[OK] Routine created: {routine['name']}")
    return routine


def update_routine(routine_id: str, data: Dict) -> Optional[Dict]:
    """Update an existing routine."""
    routines = load_routines()
    
    for i, routine in enumerate(routines):
        if routine["id"] == routine_id:
            # Update fields
            for key in ["name", "icon", "color", "description", "trigger_time", 
                       "trigger_date", "mode", "sound", "repeat", "days", 
                       "devices", "actions", "enabled"]:
                if key in data:
                    routine[key] = data[key]
            
            routines[i] = routine
            save_routines(routines)
            safe_print(f"[OK] Routine updated: {routine['name']}")
            return routine
    
    safe_print(f"[ERROR] Routine {routine_id} not found.")
    return None


def delete_routine(routine_id: str) -> bool:
    """Delete a routine."""
    routines = load_routines()
    original_len = len(routines)
    
    routines = [r for r in routines if r["id"] != routine_id]
    
    if len(routines) < original_len:
        save_routines(routines)
        safe_print(f"[OK] Routine {routine_id} deleted.")
        return True
    
    safe_print(f"[ERROR] Routine {routine_id} not found.")
    return False


def toggle_routine(routine_id: str) -> Optional[Dict]:
    """Toggle routine enabled status."""
    routines = load_routines()
    
    for routine in routines:
        if routine["id"] == routine_id:
            routine["enabled"] = not routine.get("enabled", True)
            save_routines(routines)
            status = "enabled" if routine["enabled"] else "disabled"
            safe_print(f"[OK] Routine {routine['name']} {status}.")
            return routine
    
    safe_print(f"[ERROR] Routine {routine_id} not found.")
    return None


def run_routine(routine_id: str) -> bool:
    """Execute a routine immediately."""
    routines = load_routines()
    
    for routine in routines:
        if routine["id"] == routine_id:
            safe_print(f"\n[ROUTINE] Running: {routine['name']}")
            
            # Log activity
            log_activity(
                event_type="routine_run",
                text=f"Routine '{routine['name']}' executed with {len(routine.get('devices', []))} devices"
            )
            
            # Execute devices
            execute_alarm_devices(routine)
            
            # Execute actions
            execute_alarm_actions(routine)
            
            # Update stats
            routine["run_count"] = routine.get("run_count", 0) + 1
            routine["success_count"] = routine.get("success_count", 0) + 1
            routine["last_triggered"] = datetime.now().isoformat()
            
            save_routines(routines)
            safe_print(f"[ROUTINE] {routine['name']} completed!")
            return True
    
    safe_print(f"[ERROR] Routine {routine_id} not found.")
    return False


def list_routines() -> List[Dict]:
    """List all routines."""
    routines = load_routines()
    
    if not routines:
        safe_print("No routines configured.")
        return []
    
    safe_print(f"\n{'ID':<20} {'Name':<20} {'Trigger':<10} {'Enabled':<10}")
    safe_print("-" * 65)
    
    for r in routines:
        trigger = r.get("trigger_time") or "Manual"
        enabled = "Yes" if r.get("enabled", True) else "No"
        safe_print(f"{r['id']:<20} {r['name']:<20} {trigger:<10} {enabled:<10}")
    
    return routines


def get_routine_by_id(routine_id: str) -> Optional[Dict]:
    """Get a single routine by ID."""
    routines = load_routines()
    for routine in routines:
        if routine["id"] == routine_id:
            return routine
    return None


def get_routine_by_name(name: str) -> Optional[Dict]:
    """Get a routine by name (case-insensitive partial match)."""
    routines = load_routines()
    name_lower = name.lower()
    
    for routine in routines:
        if name_lower in routine.get("name", "").lower():
            return routine
    return None


# ===========================================================================
# Activity Logging
# ===========================================================================

ACTIVITY_FILE = SKILL_DIR / "activity_log.json"


def load_activity() -> List[Dict]:
    """Load activity log from file."""
    if ACTIVITY_FILE.exists():
        try:
            with open(ACTIVITY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return []


def save_activity(activities: List[Dict]):
    """Save activity log to file."""
    with open(ACTIVITY_FILE, 'w', encoding='utf-8') as f:
        json.dump(activities, f, indent=2, ensure_ascii=False)


def log_activity(event_type: str, text: str, ref_id: str = None, ref_type: str = None) -> Dict:
    """
    Log an activity event.
    
    Event types and their icons:
    - alarm_created: ⏰
    - alarm_triggered: 🔔
    - alarm_dismissed: ✅
    - alarm_skipped: ⏭️
    - alarm_snoozed: 😴
    - routine_run: 🎛️
    - device_triggered: 💡
    - system_start: 🚀
    """
    activities = load_activity()
    
    # Icon mapping
    icons = {
        "alarm_created": "⏰",
        "alarm_triggered": "🔔",
        "alarm_dismissed": "✅",
        "alarm_skipped": "⏭️",
        "alarm_snoozed": "😴",
        "alarm_deleted": "🗑️",
        "routine_run": "🎛️",
        "routine_created": "➕",
        "device_triggered": "💡",
        "system_start": "🚀",
        "config_updated": "⚙️"
    }
    
    activity = {
        "id": f"act_{int(time.time() * 1000)}",
        "timestamp": datetime.now().isoformat(),
        "type": event_type,
        "icon": icons.get(event_type, "📝"),
        "text": text,
        "ref_id": ref_id,
        "ref_type": ref_type
    }
    
    # Insert at beginning and keep last 100
    activities.insert(0, activity)
    activities = activities[:100]
    
    save_activity(activities)
    return activity


def get_recent_activity(limit: int = 10) -> List[Dict]:
    """Get recent activity with formatted timestamps."""
    activities = load_activity()
    now = datetime.now()
    
    formatted = []
    for act in activities[:limit]:
        try:
            timestamp = datetime.fromisoformat(act["timestamp"])
            
            # Format relative time
            if timestamp.date() == now.date():
                time_str = f"Today {timestamp.strftime('%H:%M')}"
            elif timestamp.date() == (now - timedelta(days=1)).date():
                time_str = f"Yesterday {timestamp.strftime('%H:%M')}"
            else:
                time_str = timestamp.strftime("%d %b %H:%M")
            
            formatted.append({
                "icon": act.get("icon", "📝"),
                "text": act.get("text", ""),
                "time": time_str,
                "type": act.get("type", "unknown")
            })
        except Exception:
            continue
    
    return formatted


# ===========================================================================
# Analytics
# ===========================================================================

ANALYTICS_FILE = SKILL_DIR / "analytics.json"


def load_analytics() -> Dict:
    """Load analytics data from file."""
    if ANALYTICS_FILE.exists():
        try:
            with open(ANALYTICS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "wake_logs": [],
        "streaks": {"current": 0, "longest": 0, "last_success_date": None, "target": 7},
        "totals": {"total_alarms": 0, "on_time": 0, "late": 0, "missed": 0}
    }


def save_analytics(data: Dict):
    """Save analytics data to file."""
    with open(ANALYTICS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def log_wake_event(alarm: Dict, wake_time: datetime = None, snoozed: int = 0) -> Dict:
    """
    Log a wake event for analytics tracking.
    
    Args:
        alarm: The alarm that triggered
        wake_time: When user actually woke up (defaults to now)
        snoozed: Number of times user snoozed
    
    Returns:
        The created log entry
    """
    analytics = load_analytics()
    
    now = datetime.now()
    wake_time = wake_time or now
    
    # Calculate delay from alarm time
    try:
        alarm_hour, alarm_minute = map(int, alarm["time"].split(":"))
        alarm_dt = now.replace(hour=alarm_hour, minute=alarm_minute, second=0, microsecond=0)
        delay = (wake_time - alarm_dt).total_seconds() / 60
    except:
        delay = 0
    
    log = {
        "date": now.strftime("%Y-%m-%d"),
        "alarm_id": alarm.get("id"),
        "alarm_time": alarm.get("time"),
        "wake_time": wake_time.strftime("%H:%M"),
        "delay_minutes": round(delay, 1),
        "mode": alarm.get("mode", "normal"),
        "snooze_count": snoozed,
        "dismissed": True,
        "devices_triggered": [d.get("id") for d in alarm.get("devices", [])],
        "routine_id": alarm.get("routine_id")
    }
    
    analytics["wake_logs"].append(log)
    
    # Update totals
    analytics["totals"]["total_alarms"] += 1
    if delay <= 5:
        analytics["totals"]["on_time"] += 1
    else:
        analytics["totals"]["late"] += 1
    
    # Update streak
    if snoozed == 0:
        analytics["streaks"]["current"] += 1
        if analytics["streaks"]["current"] > analytics["streaks"]["longest"]:
            analytics["streaks"]["longest"] = analytics["streaks"]["current"]
        analytics["streaks"]["last_success_date"] = now.strftime("%Y-%m-%d")
    else:
        analytics["streaks"]["current"] = 0
    
    save_analytics(analytics)
    return log


def calculate_weekly_score() -> Dict:
    """Calculate weekly performance score based on recent wake logs."""
    analytics = load_analytics()
    
    # Get logs from last 7 days
    week_ago = datetime.now() - timedelta(days=7)
    recent_logs = []
    
    for log in analytics.get("wake_logs", []):
        try:
            log_date = datetime.strptime(log["date"], "%Y-%m-%d")
            if log_date >= week_ago:
                recent_logs.append(log)
        except:
            continue
    
    if not recent_logs:
        return {"score": 0, "on_time": 0, "late": 0, "total": 0}
    
    on_time = sum(1 for l in recent_logs if l.get("delay_minutes", 0) <= 5)
    total = len(recent_logs)
    
    return {
        "score": round((on_time / total) * 100) if total > 0 else 0,
        "on_time": on_time,
        "late": total - on_time,
        "total": total
    }


def get_snooze_heatmap() -> Dict:
    """Get snooze frequency heatmap data by day and hour."""
    analytics = load_analytics()
    
    # Initialize heatmap: day -> hour -> count
    days = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    heatmap = {day: {h: 0 for h in range(5, 13)} for day in days}
    
    for log in analytics.get("wake_logs", []):
        if log.get("snooze_count", 0) > 0:
            try:
                log_date = datetime.strptime(log["date"], "%Y-%m-%d")
                day = log_date.strftime("%a").lower()
                hour = int(log["alarm_time"].split(":")[0])
                if 5 <= hour <= 12 and day in heatmap:
                    heatmap[day][hour] += log["snooze_count"]
            except:
                continue
    
    return heatmap


def get_calendar_data() -> Dict:
    """Get historical calendar data for the year view."""
    analytics = load_analytics()
    
    # Build: date -> level (0-4)
    calendar = {}
    
    for log in analytics.get("wake_logs", []):
        date = log.get("date")
        if not date:
            continue
        
        if date not in calendar:
            calendar[date] = {"count": 0, "on_time": 0}
        
        calendar[date]["count"] += 1
        if log.get("delay_minutes", 0) <= 5:
            calendar[date]["on_time"] += 1
    
    # Convert to levels
    result = {}
    for date, data in calendar.items():
        ratio = data["on_time"] / data["count"] if data["count"] > 0 else 0
        if ratio >= 0.8:
            result[date] = 4
        elif ratio >= 0.6:
            result[date] = 3
        elif ratio >= 0.4:
            result[date] = 2
        elif ratio > 0:
            result[date] = 1
        else:
            result[date] = 0
    
    return result


# ===========================================================================
# Action Executor
# ===========================================================================

def play_sound(sound_name: str):
    """Play alarm sound from WAV or MP3 file."""
    sound_file = SOUNDS_DIR / sound_name
    
    # Check if file exists
    if not sound_file.exists():
        safe_print(f"[SOUND] File not found: {sound_file}")
        # Try to find similar file with different extension
        for ext in ['.mp3', '.wav', '.ogg']:
            alt_file = SOUNDS_DIR / (sound_file.stem + ext)
            if alt_file.exists():
                sound_file = alt_file
                safe_print(f"[SOUND] Found alternative: {alt_file}")
                break
    
    if sound_file.exists():
        safe_print(f"[SOUND] Playing: {sound_file.name}")
        
        # Check file extension
        ext = sound_file.suffix.lower()
        
        if ext == '.mp3':
            # Use Windows Media Player for MP3
            try:
                import subprocess
                # Start wmplayer in background, play once and close
                ps_cmd = f'''
                    Add-Type -AssemblyName presentationCore
                    $mediaPlayer = New-Object System.Windows.Media.MediaPlayer
                    $mediaPlayer.Open([System.Uri]::new("{str(sound_file).replace(chr(92), '/')}"))
                    Start-Sleep -Milliseconds 500
                    $mediaPlayer.Play()
                    while ($mediaPlayer.Position -lt $mediaPlayer.NaturalDuration.TimeSpan -and $mediaPlayer.HasAudio) {{
                        Start-Sleep -Milliseconds 100
                    }}
                    $mediaPlayer.Close()
                '''
                subprocess.run(
                    ['powershell', '-ExecutionPolicy', 'Bypass', '-Command', ps_cmd],
                    capture_output=True,
                    timeout=60
                )
                safe_print(f"[SOUND] Played: {sound_name} - OK")
                return True
            except Exception as e:
                safe_print(f"[SOUND] MediaPlayer failed: {e}")
                # Fallback: Use start command to open with default player
                try:
                    import subprocess
                    subprocess.Popen(['start', '', str(sound_file)], shell=True)
                    time.sleep(3)  # Give it time to play
                    safe_print(f"[SOUND] Played via default player: {sound_name} - OK")
                    return True
                except Exception as e2:
                    safe_print(f"[SOUND] Default player failed: {e2}")
        else:
            # Use Media.SoundPlayer for WAV
            try:
                import subprocess
                subprocess.run(
                    ['powershell', '-Command', f'(New-Object Media.SoundPlayer "{sound_file}").PlaySync()'],
                    capture_output=True,
                    timeout=30
                )
                safe_print(f"[SOUND] Played: {sound_name} - OK")
                return True
            except Exception as e:
                safe_print(f"[SOUND] Media.SoundPlayer failed: {e}")
                
                # Fallback to winsound for WAV
                try:
                    import winsound
                    winsound.PlaySound(str(sound_file), winsound.SND_FILENAME)
                    safe_print(f"[SOUND] Played via winsound: {sound_name} - OK")
                    return True
                except Exception as e2:
                    safe_print(f"[SOUND] winsound failed: {e2}")
    
    # Fallback to Windows beep if no sound file
    safe_print("[SOUND] Using fallback beeps...")
    try:
        import winsound
        winsound.Beep(800, 300)
        winsound.Beep(1000, 300)
        winsound.Beep(1200, 300)
        winsound.Beep(1000, 300)
        winsound.Beep(800, 300)
        return True
    except Exception:
        pass
    
    # Last fallback to PowerShell beep
    try:
        os.system('powershell -c "[console]::beep(1000,500)"')
        return True
    except Exception:
        pass
    
    safe_print("[WARN] Could not play any sound")
    return False


# NOTE: execute_tuya_command is defined later in the file (around line 1268+)
# with proper sys.executable support



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


def send_to_shila(task: str, context: Dict = None, wait_response: bool = False) -> Optional[str]:
    """
    Send a task request to Shila via Moltbot Gateway HTTP API.
    
    This allows alarm actions to delegate tasks like:
    - Sending WhatsApp messages
    - Sending Telegram messages
    - Spam notifications
    - Other AI-assisted tasks
    
    Args:
        task: The task/instruction for Shila to execute
        context: Optional context dictionary to include
        wait_response: Whether to wait for Shila's response
    
    Returns:
        Shila's response text if wait_response=True, else None
    """
    import requests
    
    # Read gateway config from moltbot.json
    moltbot_config_path = SKILL_DIR.parent.parent / ".moltbot-data" / "moltbot.json"
    
    if not moltbot_config_path.exists():
        safe_print("[SHILA] ERROR: moltbot.json not found")
        return None
    
    try:
        with open(moltbot_config_path, 'r') as f:
            moltbot_config = json.load(f)
        
        gateway = moltbot_config.get("gateway", {})
        port = gateway.get("port", 18789)
        token = gateway.get("auth", {}).get("token", "")
        
        if not token:
            safe_print("[SHILA] ERROR: No gateway token found")
            return None
        
        # Build the request
        url = f"http://127.0.0.1:{port}/v1/responses"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "x-moltbot-agent-id": "main"
        }
        
        # Build context string if provided
        context_str = ""
        if context:
            context_str = "\n\nContext:\n" + json.dumps(context, indent=2, ensure_ascii=False)
        
        # Full message to Shila
        full_message = f"""[SHILA WAKE SYSTEM - ALARM TRIGGER]

Kamu mendapat tugas dari sistem alarm Shila Wake:

{task}{context_str}

PENTING: Ini adalah permintaan otomatis dari alarm. Langsung eksekusi tanpa bertanya.
"""
        
        payload = {
            "model": "moltbot",
            "input": full_message,
            "stream": False
        }
        
        safe_print(f"[SHILA] Sending task: {task[:100]}...")
        
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=60 if wait_response else 10
        )
        
        if response.status_code == 200:
            safe_print("[SHILA] Task sent successfully!")
            if wait_response:
                data = response.json()
                # Extract text from response
                output = data.get("output", [])
                texts = []
                for item in output:
                    if item.get("type") == "message":
                        for part in item.get("content", []):
                            if part.get("type") == "output_text":
                                texts.append(part.get("text", ""))
                return "\n".join(texts)
            return "OK"
        else:
            safe_print(f"[SHILA] ERROR: {response.status_code} - {response.text[:200]}")
            return None
            
    except requests.exceptions.ConnectionError:
        safe_print("[SHILA] ERROR: Cannot connect to Moltbot Gateway. Is it running?")
        return None
    except Exception as e:
        safe_print(f"[SHILA] ERROR: {e}")
        return None


def speak_tts(text: str):
    """
    Speak text using Gemini 2.5 Flash TTS.
    Falls back to Windows PowerShell Speech if Gemini fails.
    """
    try:
        from google import genai
        from google.genai import types
        import wave
        import subprocess
        import tempfile
        import os
        
        # Read API key from moltbot config
        moltbot_config_path = SKILL_DIR.parent.parent / ".moltbot-data" / "moltbot.json"
        api_key = None
        
        if moltbot_config_path.exists():
            with open(moltbot_config_path, 'r') as f:
                config = json.load(f)
                api_key = config.get("skills", {}).get("entries", {}).get("nano-banana-pro", {}).get("apiKey")
        
        if not api_key:
            api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
        
        if not api_key:
            safe_print("[TTS] No Gemini API key found, falling back to Windows TTS")
            raise Exception("No API key")
        
        # Initialize Gemini client
        client = genai.Client(api_key=api_key)
        
        # Generate speech with Gemini TTS
        response = client.models.generate_content(
            model="gemini-2.5-flash-preview-tts",
            contents=text,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name='Kore',  # Natural female voice
                        )
                    ),
                ),
            )
        )
        
        # Get audio data
        audio_data = response.candidates[0].content.parts[0].inline_data.data
        
        # Save to temp WAV file
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
            tmp_path = tmp.name
            with wave.open(tmp.name, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(24000)
                wf.writeframes(audio_data)
        
        # Play using Windows Media Player
        subprocess.run(
            ['powershell', '-Command', f'(New-Object Media.SoundPlayer "{tmp_path}").PlaySync()'],
            capture_output=True,
            timeout=60
        )
        
        # Cleanup temp file
        try:
            os.unlink(tmp_path)
        except:
            pass
        
        safe_print(f"[TTS] Gemini: '{text[:50]}...' - OK")
        return True
        
    except Exception as e:
        safe_print(f"[TTS] Gemini failed ({e}), using Windows TTS fallback")
        # Fallback to Windows PowerShell TTS
        try:
            import subprocess
            text_safe = text.replace('"', "'").replace('\n', ' ')
            ps_script = f'Add-Type -AssemblyName System.Speech; (New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak("{text_safe}")'
            subprocess.run(["powershell", "-Command", ps_script], capture_output=True, timeout=30)
            return True
        except Exception as e2:
            safe_print(f"[TTS] {text}")
            return False

# ===========================================================================
# Alarm Device & Action Execution
# ===========================================================================

def execute_tuya_command(*args):
    """
    Execute a Tuya control command using the tuya_control.py script.
    
    Args:
        *args: Variable arguments to pass to the script
               e.g., ("on", '"Lampu Meja"')
               e.g., ("brightness", '"Lampu Meja"', "80")
               e.g., ("color", '"Lampu Meja"', "blue")
               e.g., ("ac", '"AC Studio"', "--power", "on", "--temp", "24")
    
    Returns:
        bool: True if command succeeded, False otherwise
    """
    import subprocess
    import sys
    
    if not TUYA_SCRIPT.exists():
        safe_print(f"[TUYA] ERROR: Script not found at {TUYA_SCRIPT}")
        return False
    
    try:
        # Use sys.executable to ensure same Python environment as wake_system.py
        python_exe = sys.executable
        cmd = [python_exe, str(TUYA_SCRIPT)] + list(args)
        
        safe_print(f"[TUYA] Running: {' '.join(cmd)}")
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(TUYA_SCRIPT.parent)
        )
        
        # Log all output regardless of return code
        output = result.stdout.strip() or result.stderr.strip()
        if output:
            safe_print(f"[TUYA] Output: {output[:150]}")
        
        # Consider success if no stderr and output looks good
        if result.returncode == 0 or "OK" in result.stdout or "Success" in result.stdout:
            return True
        else:
            if result.stderr:
                safe_print(f"[TUYA] Warning: {result.stderr.strip()[:100]}")
            return True  # Still return True to continue execution
            
    except subprocess.TimeoutExpired:
        safe_print("[TUYA] Command timed out")
        return False
    except Exception as e:
        safe_print(f"[TUYA] Exception: {e}")
        return False


def execute_alarm_devices(alarm: Dict):
    """Execute all device actions configured for an alarm."""
    devices = alarm.get("devices", [])
    
    if not devices:
        return
    
    safe_print(f"[DEVICES] Executing {len(devices)} device(s)...")
    
    for device in devices:
        device_id = device.get("id", "")
        device_name = device.get("name", device_id)
        device_type = device.get("type", "light")
        action = device.get("action", "on")
        
        try:
            if device_type == "light":
                # Turn on/off light
                if action == "on":
                    execute_tuya_command("on", device_name)
                    
                    # Set brightness if specified
                    brightness = device.get("brightness")
                    if brightness:
                        time.sleep(0.3)
                        execute_tuya_command("brightness", device_name, str(brightness))
                    
                    # Set color if specified
                    color = device.get("color")
                    if color:
                        time.sleep(0.3)
                        execute_tuya_command("color", device_name, color)
                else:
                    execute_tuya_command("off", device_name)
                    
            elif device_type == "ac":
                if action == "on":
                    temp = device.get("temperature", 24)
                    mode = device.get("ac_mode", "cool")
                    execute_tuya_command("ac", device_name, "--power", "on", "--temp", str(temp), "--mode", mode)
                else:
                    execute_tuya_command("ac", device_name, "--power", "off")
                    
            elif device_type == "plug":
                execute_tuya_command(action, device_name)
                
            safe_print(f"[DEVICE] {device_name}: {action} - OK")
            
        except Exception as e:
            safe_print(f"[DEVICE] {device_name}: ERROR - {e}")


def execute_alarm_actions(alarm: Dict):
    """Execute all additional actions configured for an alarm."""
    actions = alarm.get("actions", [])
    
    if not actions:
        return
    
    safe_print(f"[ACTIONS] Executing {len(actions)} action(s)...")
    
    # Get alarm info for context
    alarm_context = {
        "alarm_id": alarm.get("id"),
        "alarm_time": alarm.get("time"),
        "alarm_label": alarm.get("label"),
        "alarm_mode": alarm.get("mode"),
        "triggered_at": datetime.now().isoformat()
    }
    
    for action in actions:
        action_id = action.get("id", "")
        
        try:
            if action_id == "voice":
                message = action.get("message", "Waktunya bangun!")
                speak_tts(message)
                safe_print(f"[ACTION] Voice: '{message}' - OK")
                
            elif action_id == "whatsapp":
                # Delegate to Shila for WhatsApp
                recipient = action.get("recipient", "+6287877974096")
                message = action.get("message", "Alarm berbunyi! Waktunya bangun!")
                
                task = f"""Kirim pesan WhatsApp ke {recipient} dengan isi:
                
"{message}"

Gunakan plugin WhatsApp yang sudah tersedia. Ini adalah notifikasi alarm otomatis."""
                
                send_to_shila(task, context=alarm_context)
                safe_print(f"[ACTION] WhatsApp to {recipient}: DELEGATED TO SHILA")
                        
            elif action_id == "telegram":
                # Delegate to Shila for Telegram
                message = action.get("message", "Alarm berbunyi! Waktunya bangun!")
                
                task = f"""Kirim pesan Telegram dengan isi:

"{message}"

Gunakan plugin Telegram yang sudah tersedia. Ini adalah notifikasi alarm otomatis."""
                
                send_to_shila(task, context=alarm_context)
                safe_print(f"[ACTION] Telegram: DELEGATED TO SHILA")
                
            elif action_id == "weather":
                # Fetch and announce current weather
                try:
                    import requests
                    # Get weather from wttr.in
                    location = action.get("location", "Jakarta")
                    url = f"https://wttr.in/{location}?format=%c+%t+%h+%w&lang=id"
                    response = requests.get(url, timeout=10)
                    
                    if response.status_code == 200:
                        weather_data = response.text.strip()
                        # Parse the response (format: emoji temp humidity wind)
                        # e.g., "☀️ +28°C 70% ↙10km/h"
                        weather_message = f"Cuaca di {location} saat ini: {weather_data}"
                        speak_tts(weather_message)
                        safe_print(f"[ACTION] Weather: {weather_data} - OK")
                    else:
                        speak_tts(f"Cuaca di {location}: Cerah, suhu sekitar 28 derajat.")
                        safe_print("[ACTION] Weather: Using fallback (API error)")
                except Exception as e:
                    safe_print(f"[ACTION] Weather fetch error: {e}")
                    speak_tts("Selamat pagi! Cuaca hari ini cerah, semoga harimu menyenangkan!")
                    safe_print("[ACTION] Weather: Using fallback TTS")
                
            elif action_id == "music":
                playlist = action.get("playlist", "")
                # Delegate to Shila for music
                task = f"""Putar musik untuk membangunkan user.
                
Playlist yang diminta: {playlist or 'musik semangat untuk pagi hari'}

Gunakan kemampuan yang ada untuk memutar musik atau buka aplikasi musik."""
                
                send_to_shila(task, context=alarm_context)
                safe_print(f"[ACTION] Music: DELEGATED TO SHILA")
                
            elif action_id == "quote":
                # Speak motivational quote
                quotes = [
                    "Hari baru, semangat baru! Kamu pasti bisa menaklukkan hari ini!",
                    "Selamat pagi champion! Dunia menunggumu untuk melakukan hal luar biasa!",
                    "Bangun dan bersinar! Hari ini adalah hadiah untukmu!",
                    "Setiap pagi adalah kesempatan baru. Manfaatkan dengan baik!",
                    "Kamu amazing! Ayo mulai hari ini dengan senyuman!"
                ]
                import random
                quote = random.choice(quotes)
                speak_tts(quote)
                safe_print(f"[ACTION] Quote: '{quote[:50]}...' - OK")
                
            elif action_id == "spam":
                # Spam mode - repeated TTS announcements locally
                message = action.get("message", "BANGUN SAYANG!")
                count = action.get("count", 5)
                delay = action.get("delay", 30)
                channels = action.get("channels", ["tts"])  # Default to TTS only
                
                safe_print(f"[ACTION] SPAM MODE: {count}x with {delay}s delay via {channels}")
                
                # Execute spam locally with TTS
                import threading
                
                def spam_loop():
                    for i in range(count):
                        safe_print(f"[SPAM] Round {i+1}/{count}")
                        
                        # Always do TTS locally
                        if "tts" in channels or len(channels) == 0:
                            speak_tts(f"{message} Ini pengingat ke {i+1} dari {count}!")
                        
                        # Send to Shila for WhatsApp/Telegram (async, don't wait)
                        if "whatsapp" in channels or "telegram" in channels:
                            try:
                                wa_msg = f"{message} (Spam {i+1}/{count})"
                                if "whatsapp" in channels:
                                    task = f'Kirim WhatsApp ke +6287877974096: "{wa_msg}"'
                                    threading.Thread(target=send_to_shila, args=(task,), daemon=True).start()
                                if "telegram" in channels:
                                    task = f'Kirim Telegram: "{wa_msg}"'
                                    threading.Thread(target=send_to_shila, args=(task,), daemon=True).start()
                            except Exception as e:
                                safe_print(f"[SPAM] Message send error: {e}")
                        
                        # Wait before next round (except last)
                        if i < count - 1:
                            time.sleep(delay)
                    
                    safe_print(f"[SPAM] Completed {count} rounds!")
                
                # Run spam in background thread so it doesn't block
                spam_thread = threading.Thread(target=spam_loop, daemon=True)
                spam_thread.start()
                safe_print(f"[ACTION] Spam mode started in background")
                
        except Exception as e:
            safe_print(f"[ACTION] {action_id}: ERROR - {e}")


# ===========================================================================
# Wake Sequences
# ===========================================================================

def execute_gentle_wake(alarm: Dict = None):
    """Execute gentle wake sequence."""
    safe_print("[WAKE] Starting GENTLE wake sequence...")
    
    # Check if alarm has custom devices - if not, use default lights
    has_custom_devices = alarm and len(alarm.get('devices', [])) > 0
    if not has_custom_devices:
        turn_on_lights(brightness=30, color="warm")
        time.sleep(2)
        turn_on_lights(brightness=50, color="warm")
        time.sleep(2)
        turn_on_lights(brightness=80, color="white")
        time.sleep(2)
        turn_on_lights(brightness=100, color="white")
        turn_off_ac()
    
    # Play alarm sound
    config = load_config()
    sound_file = alarm.get('sound') if alarm else config['sounds'].get('gentle', 'gentle_alarm.wav')
    if sound_file:
        play_sound(sound_file)
    
    # Check if alarm has custom voice action - if not, use default TTS
    has_voice_action = alarm and any(a.get('id') == 'voice' for a in alarm.get('actions', []))
    if not has_voice_action:
        speak_tts(config['tts']['messages']['gentle'])
        send_chat_notification("Selamat pagi, Sayang! Sudah waktunya bangun~")


def execute_normal_wake(alarm: Dict = None):
    """Execute normal wake sequence."""
    safe_print("[WAKE] Starting NORMAL wake sequence...")
    
    # Check if alarm has custom devices - if not, use default lights
    has_custom_devices = alarm and len(alarm.get('devices', [])) > 0
    if not has_custom_devices:
        turn_on_lights(brightness=100, color="white")
        turn_off_ac()
    
    # Play alarm sound
    config = load_config()
    sound_file = alarm.get('sound') if alarm else config['sounds'].get('normal', 'alarm.wav')
    if sound_file:
        play_sound(sound_file)
    
    # Check if alarm has custom voice action - if not, use default TTS
    has_voice_action = alarm and any(a.get('id') == 'voice' for a in alarm.get('actions', []))
    if not has_voice_action:
        speak_tts(config['tts']['messages']['normal'])
        send_chat_notification("Bangun Sayang! Sudah pagi!")


def execute_nuclear_wake(alarm: Dict = None):
    """Execute nuclear wake sequence - NO MERCY!"""
    safe_print("[WAKE] Starting NUCLEAR wake sequence!")
    
    # Check if alarm has custom devices - if not, use default lights
    has_custom_devices = alarm and len(alarm.get('devices', [])) > 0
    if not has_custom_devices:
        turn_on_lights(brightness=100, color="white")
        turn_off_ac()
    
    # LOUD ALARM - always play for nuclear
    config = load_config()
    sound_file = alarm.get('sound') if alarm else config['sounds'].get('nuclear', 'nuclear_alarm.wav')
    
    def alarm_loop():
        for _ in range(5):
            play_sound(sound_file)
            time.sleep(1)
    
    alarm_thread = threading.Thread(target=alarm_loop, daemon=True)
    alarm_thread.start()
    
    # Check if alarm has custom voice action - if not, use default TTS
    has_voice_action = alarm and any(a.get('id') == 'voice' for a in alarm.get('actions', []))
    if not has_voice_action:
        speak_tts(config['tts']['messages']['nuclear'])
        send_chat_notification("BANGUN!!! ALARM NUCLEAR - JANGAN DIABAIKAN!")
    
    safe_print("[WAKE] Nuclear sequence completed!")


def execute_wake(mode: str = "normal", alarm: Dict = None):
    """Execute wake sequence based on mode. Passes alarm to check for custom actions."""
    safe_print(f"\n{'='*50}")
    safe_print(f"  SHILA WAKE SYSTEM - {mode.upper()} MODE")
    safe_print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if alarm:
        safe_print(f"  Alarm: {alarm.get('label', alarm.get('id', 'N/A'))}")
        safe_print(f"  Custom Actions: {len(alarm.get('actions', []))}")
        safe_print(f"  Custom Devices: {len(alarm.get('devices', []))}")
    safe_print(f"{'='*50}\n")
    
    if mode == "gentle":
        execute_gentle_wake(alarm)
    elif mode == "nuclear":
        execute_nuclear_wake(alarm)
    else:
        execute_normal_wake(alarm)


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
            # Get sound file for this alarm
            config = load_config()
            sound_file = alarm.get('sound')
            if not sound_file:
                mode = alarm.get('mode', 'normal')
                sound_file = config['sounds'].get(mode, 'alarm.wav')
            
            # FIRST: START ACTIVE ALARM - opens browser, sets volume, starts sound loop
            # Browser must open BEFORE other actions so user sees the alarm page immediately
            start_active_alarm(alarm, sound_file)
            
            # THEN: Execute base wake sequence (lights, basic TTS)
            execute_wake(alarm['mode'], alarm)
            
            # Execute custom devices configured in alarm
            execute_alarm_devices(alarm)
            
            # Execute custom actions configured in alarm (except spam, handled by active alarm)
            execute_alarm_actions(alarm)
            
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
    
    # routine - now supports custom routines
    routine_parser = subparsers.add_parser('routine', help='Routine management')
    routine_sub = routine_parser.add_subparsers(dest='routine_action')
    
    routine_list = routine_sub.add_parser('list', help='List all custom routines')
    routine_run = routine_sub.add_parser('run', help='Run routine by ID or name')
    routine_run.add_argument('id', help='Routine ID or name')
    
    # Legacy preset routines
    routine_sub.add_parser('morning', help='[Legacy] Morning preset')
    routine_sub.add_parser('work', help='[Legacy] Work mode preset')
    routine_sub.add_parser('sleep', help='[Legacy] Sleep preset')
    routine_sub.add_parser('movie', help='[Legacy] Movie preset')
    
    # analytics
    analytics_parser = subparsers.add_parser('analytics', help='Wake analytics')
    analytics_sub = analytics_parser.add_subparsers(dest='analytics_action')
    analytics_sub.add_parser('score', help='Get weekly score')
    analytics_sub.add_parser('streaks', help='Get streak info')
    analytics_sub.add_parser('summary', help='Full analytics summary')
    
    # activity
    activity_parser = subparsers.add_parser('activity', help='Activity log')
    activity_parser.add_argument('--limit', type=int, default=10, help='Number of entries')
    
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
        if args.routine_action == 'list':
            # List all custom routines
            routines = load_routines()
            if not routines:
                safe_print("[ROUTINES] No custom routines found")
            else:
                safe_print(f"[ROUTINES] {len(routines)} custom routines:")
                for r in routines:
                    status = "✓" if r.get("enabled", True) else "✗"
                    safe_print(f"  {status} {r['id']}: {r['name']} at {r.get('trigger_time', 'manual')}")
        elif args.routine_action == 'run':
            # Run by ID or name
            routine_id = args.id
            # First try by ID
            if run_routine(routine_id):
                pass  # Success
            else:
                # Try by name
                routine = get_routine_by_name(routine_id)
                if routine:
                    run_routine(routine["id"])
                else:
                    safe_print(f"[ERROR] Routine '{routine_id}' not found")
        elif args.routine_action in ['morning', 'work', 'sleep', 'movie']:
            # Legacy preset routines
            presets = {'morning': routine_morning, 'work': routine_work, 
                       'sleep': routine_sleep, 'movie': routine_movie}
            presets[args.routine_action]()
        else:
            routine_parser.print_help()
    elif args.command == 'analytics':
        analytics = load_analytics()
        score = calculate_weekly_score()
        if args.analytics_action == 'score':
            safe_print(f"[ANALYTICS] Weekly Score: {score['score']}%")
            safe_print(f"            On-time: {score['on_time']}/{score['total']}")
        elif args.analytics_action == 'streaks':
            streaks = analytics.get('streaks', {})
            safe_print(f"[STREAKS] Current: {streaks.get('current', 0)} days")
            safe_print(f"          Longest: {streaks.get('longest', 0)} days")
            safe_print(f"          Target:  {streaks.get('target', 7)} days")
        elif args.analytics_action == 'summary':
            safe_print(f"[ANALYTICS] === Wake Performance ===")
            safe_print(f"  Weekly Score: {score['score']}%")
            safe_print(f"  On-time: {score['on_time']} / Late: {score['late']}")
            streaks = analytics.get('streaks', {})
            safe_print(f"  Current Streak: {streaks.get('current', 0)} days")
            safe_print(f"  Longest Streak: {streaks.get('longest', 0)} days")
            totals = analytics.get('totals', {})
            safe_print(f"  Total Alarms: {totals.get('total_alarms', 0)}")
        else:
            analytics_parser.print_help()
    elif args.command == 'activity':
        activities = get_recent_activity(args.limit)
        if not activities:
            safe_print("[ACTIVITY] No recent activity")
        else:
            safe_print(f"[ACTIVITY] Last {len(activities)} entries:")
            for a in activities:
                safe_print(f"  {a['relative_time']}: {a['title']}")


if __name__ == '__main__':
    main()
