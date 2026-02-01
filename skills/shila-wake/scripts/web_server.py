#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["fastapi>=0.110.0", "uvicorn>=0.27.0", "jinja2>=3.1.0", "schedule>=1.2.0"]
# ///
"""
Shila Wake System - Web Dashboard Server v2.0
FastAPI-based web interface with proper date handling.
"""
import os
import sys
import json
import asyncio
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List
from contextlib import asynccontextmanager

# Fix Windows console encoding
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# Setup paths
SCRIPT_DIR = Path(__file__).parent
SKILL_DIR = SCRIPT_DIR.parent
TEMPLATES_DIR = SKILL_DIR / "templates"
STATIC_DIR = SKILL_DIR / "static"

sys.path.insert(0, str(SCRIPT_DIR))

# Import wake system
from wake_system import (
    load_config, save_config, load_alarms, save_alarms, add_alarm, delete_alarm, toggle_alarm,
    load_reminders, save_reminders, add_reminder, delete_reminder,
    load_routines, save_routines, add_routine, update_routine, delete_routine, toggle_routine, run_routine, get_routine_by_id,
    load_activity, log_activity, get_recent_activity,
    load_analytics, log_wake_event, calculate_weekly_score, get_snooze_heatmap, get_calendar_data,
    execute_wake, routine_morning, routine_work, routine_sleep, routine_movie,
    check_alarms, check_reminders, turn_on_lights, turn_off_ac, speak_tts,
    test_sound, test_lights, test_tts, get_next_alarm, safe_print,
    ALARMS_FILE, REMINDERS_FILE, CONFIG_FILE,
    # Active Alarm functions
    snooze_active_alarm, dismiss_active_alarm, get_active_alarm_status
)

# Install dependencies if needed
try:
    from fastapi import FastAPI, HTTPException, Request, Form
    from fastapi.responses import HTMLResponse, JSONResponse
    from fastapi.staticfiles import StaticFiles
    from fastapi.templating import Jinja2Templates
    import uvicorn
except ImportError:
    print("Installing web dependencies...")
    os.system(f"{sys.executable} -m pip install fastapi uvicorn jinja2")
    from fastapi import FastAPI, HTTPException, Request, Form
    from fastapi.responses import HTMLResponse, JSONResponse
    from fastapi.staticfiles import StaticFiles
    from fastapi.templating import Jinja2Templates
    import uvicorn

try:
    import schedule
except ImportError:
    os.system(f"{sys.executable} -m pip install schedule")
    import schedule


# ===========================================================================
# Scheduler Background Task (Improved)
# ===========================================================================

scheduler_running = False
scheduler_thread = None

def scheduler_loop():
    """Background scheduler loop with error handling."""
    global scheduler_running
    scheduler_running = True
    
    # Clear any existing jobs
    schedule.clear()
    
    # Schedule checks every 30 seconds for responsive alarms
    schedule.every(30).seconds.do(safe_check_alarms)
    schedule.every().minute.at(":30").do(safe_check_reminders)
    
    safe_print("[SCHEDULER] Background scheduler started")
    
    while scheduler_running:
        try:
            schedule.run_pending()
        except Exception as e:
            safe_print(f"[SCHEDULER] Error in scheduler: {e}")
        time.sleep(1)
    
    safe_print("[SCHEDULER] Background scheduler stopped")


def safe_check_alarms():
    """Wrapper for check_alarms with error handling."""
    try:
        check_alarms()
    except Exception as e:
        safe_print(f"[SCHEDULER] check_alarms error: {e}")


def safe_check_reminders():
    """Wrapper for check_reminders with error handling."""
    try:
        check_reminders()
    except Exception as e:
        safe_print(f"[SCHEDULER] check_reminders error: {e}")


def start_scheduler():
    """Start the scheduler thread."""
    global scheduler_thread, scheduler_running
    
    if scheduler_thread and scheduler_thread.is_alive():
        safe_print("[SCHEDULER] Already running")
        return
    
    scheduler_running = True
    scheduler_thread = threading.Thread(target=scheduler_loop, daemon=True)
    scheduler_thread.start()
    safe_print("[WEB] Scheduler started")


def stop_scheduler():
    """Stop the scheduler thread."""
    global scheduler_running
    scheduler_running = False
    safe_print("[WEB] Scheduler stop requested")


# ===========================================================================
# Lifespan (Modern FastAPI approach)
# ===========================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup
    start_scheduler()
    yield
    # Shutdown
    stop_scheduler()


# ===========================================================================
# FastAPI App
# ===========================================================================

app = FastAPI(
    title="Shila Wake System",
    description="Smart Alarm & Reminder Dashboard v2.0",
    version="2.0.0",
    lifespan=lifespan
)

# Create directories
TEMPLATES_DIR.mkdir(exist_ok=True)
STATIC_DIR.mkdir(exist_ok=True)

# Templates
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Mount static files
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Mount sounds folder for audio files
SOUNDS_DIR = SKILL_DIR / "sounds"
if SOUNDS_DIR.exists():
    app.mount("/sounds", StaticFiles(directory=str(SOUNDS_DIR)), name="sounds")


# ===========================================================================
# API Routes
# ===========================================================================

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard page with enriched data."""
    alarms = load_alarms()
    reminders = load_reminders()
    config = load_config()
    
    # Get next alarm info
    next_alarm_info = get_next_alarm()
    
    now = datetime.now()
    
    # Format next alarm for hero card
    next_alarm = None
    if next_alarm_info:
        alarm = next_alarm_info['alarm']
        delta = next_alarm_info['delta']
        hours = int(delta.total_seconds() // 3600)
        mins = int((delta.total_seconds() % 3600) // 60)
        
        # Mode icons
        mode_icons = {"gentle": "🌿", "normal": "⏰", "nuclear": "🔥"}
        
        # Parse target datetime
        target_dt = None
        if alarm.get('target_datetime'):
            try:
                target_dt = datetime.fromisoformat(alarm['target_datetime'])
            except:
                pass
        
        next_alarm = {
            "time": alarm['time'],
            "date_formatted": target_dt.strftime("%A, %d %B") if target_dt else alarm.get('date', 'Today'),
            "datetime_iso": alarm.get('target_datetime', now.isoformat()),
            "mode": alarm.get('mode', 'normal').title(),
            "mode_icon": mode_icons.get(alarm.get('mode', 'normal'), "⏰"),
            "label": alarm.get('label', ''),
            "countdown": f"{hours}h {mins}m"
        }
    
    # Format alarm list
    formatted_alarms = []
    mode_icons = {"gentle": "🌿", "normal": "⏰", "nuclear": "🔥"}
    for a in alarms:
        mode = a.get('mode', 'normal')
        repeat = a.get('repeat', 'once')
        repeat_texts = {
            "once": "Once",
            "daily": "Every day",
            "weekdays": "Mon-Fri",
            "weekends": "Sat-Sun",
            "weekly": "Every week",
            "monthly": "Monthly"
        }
        formatted_alarms.append({
            **a,
            "date_short": a.get('date', 'Today'),
            "mode": mode.title(),
            "mode_icon": mode_icons.get(mode, "⏰"),
            "repeat_text": repeat_texts.get(repeat, repeat)
        })
    
    # Stats - using real analytics data
    active_alarms = [a for a in alarms if a.get('enabled', True)]
    active_reminders = [r for r in reminders if r.get('enabled', True)]
    routines = load_routines()
    
    # Get real analytics
    analytics = load_analytics()
    score_data = calculate_weekly_score()
    
    stats = {
        "alarm_count": len(active_alarms),
        "alarm_sub": f"{len(alarms)} total configured",
        "reminder_count": len(active_reminders),
        "reminder_sub": f"for today and upcoming",
        "avg_sleep": "7.5h",
        "sleep_sub": "based on last 7 days",
        "routine_count": len(routines),
        "weekly_score": score_data.get("score", 0),
        "on_time": score_data.get("on_time", 0),
        "late": score_data.get("late", 0),
        "current_streak": analytics.get("streaks", {}).get("current", 0),
        "longest_streak": analytics.get("streaks", {}).get("longest", 0),
        "wake_status": "Pending"
    }
    
    # TODO: Integrate with smarthome-tuya skill to get real device states
    # Use: uv run tuya_control.py status --all
    devices = {
        "lights": False,
        "ac": False,
        "music": False,
        "coffee": False
    }
    
    # TODO: Integrate with weather skill to get real weather
    # Use: curl -s "wttr.in/Bandung?format=j1"
    weather = {
        "icon": "⛅",
        "temp": 28,
        "condition": "Partly Cloudy",
        "humidity": 72,
        "wind": 12,
        "recommendation": "Good morning! Consider opening windows for fresh air."
    }
    
    # TODO: Integrate with Google Calendar API
    # These are placeholder events - can be populated via API
    schedule = [
        {"time": "09:00", "title": "Morning standup"},
        {"time": "11:00", "title": "Code review session"},
        {"time": "14:00", "title": "Project planning"},
        {"time": "16:30", "title": "Team sync"}
    ]
    
    # Current date formatted
    current_date = now.strftime("%A, %d %B %Y")
    
    # Get real activity feed
    activity_feed = get_recent_activity(5)
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "active_page": "dashboard",
        "next_alarm": next_alarm,
        "alarms": formatted_alarms,
        "stats": stats,
        "devices": devices,
        "weather": weather,
        "schedule": schedule,
        "current_date": current_date,
        "activity_feed": activity_feed,
        "scheduler_running": scheduler_running
    })


@app.get("/alarms", response_class=HTMLResponse)
async def alarms_page(request: Request):
    """Alarms management page."""
    alarms = load_alarms()
    
    # Format alarms
    formatted_alarms = []
    repeat_texts = {
        "once": "Once",
        "daily": "Every day", 
        "weekdays": "Mon-Fri",
        "weekends": "Sat-Sun",
        "weekly": "Every week",
        "monthly": "Monthly"
    }
    
    for a in alarms:
        formatted_alarms.append({
            **a,
            "date_display": a.get('date', 'Today'),
            "mode": a.get('mode', 'normal').title(),
            "repeat_text": repeat_texts.get(a.get('repeat', 'once'), 'Once')
        })
    
    # Sound library - scan actual sounds folder
    sounds = {"gentle": [], "normal": [], "nuclear": []}
    if SOUNDS_DIR.exists():
        # Categorize sounds by type
        gentle_sounds = ["Birds", "Windchimes", "Piano", "Harp", "MusicBox", "Flute", "Glow", "ParadiseIsland"]
        nuclear_sounds = ["Alarm", "Electricity", "Classic", "Classic2", "Classic3", "School", "Rooster"]
        
        for f in sorted(SOUNDS_DIR.glob("*.mp3")):
            name = f.stem
            sound_entry = {"name": name, "path": f"/sounds/{f.name}"}
            
            if name in gentle_sounds:
                sounds["gentle"].append(sound_entry)
            elif name in nuclear_sounds:
                sounds["nuclear"].append(sound_entry)
            else:
                sounds["normal"].append(sound_entry)
    
    return templates.TemplateResponse("alarms.html", {
        "request": request,
        "active_page": "alarms",
        "alarms": formatted_alarms,
        "sounds": sounds
    })


@app.get("/routines", response_class=HTMLResponse)
async def routines_page(request: Request):
    """Routines automation page."""
    
    # Sound library (same as alarms page)
    sounds = {
        "gentle": [
            {"name": "Morning Birds", "path": "gentle/birds.mp3"},
            {"name": "Ocean Waves", "path": "gentle/waves.mp3"},
            {"name": "Soft Piano", "path": "gentle/piano.mp3"}
        ],
        "normal": [
            {"name": "Digital Alarm", "path": "normal/digital.mp3"},
            {"name": "Classic Bell", "path": "normal/bell.mp3"},
            {"name": "Rooster", "path": "normal/rooster.mp3"}
        ],
        "nuclear": [
            {"name": "Air Raid Siren", "path": "nuclear/siren.mp3"},
            {"name": "Truck Horn", "path": "nuclear/horn.mp3"},
            {"name": "Thunder Strike", "path": "nuclear/thunder.mp3"}
        ]
    }
    
    # Load real routines from routines.json
    routines = load_routines()
    
    return templates.TemplateResponse("routines.html", {
        "request": request,
        "active_page": "routines",
        "routines": routines,
        "sounds": sounds
    })

@app.get("/analytics", response_class=HTMLResponse)
async def analytics_page(request: Request):
    """Analytics and insights page with real data."""
    # Get real analytics data
    analytics = load_analytics()
    score_data = calculate_weekly_score()
    heatmap_data = get_snooze_heatmap()
    calendar_data = get_calendar_data()
    
    return templates.TemplateResponse("analytics.html", {
        "request": request,
        "active_page": "analytics",
        "score": score_data,
        "streaks": analytics.get("streaks", {}),
        "totals": analytics.get("totals", {}),
        "heatmap": heatmap_data,
        "calendar": calendar_data
    })


@app.get("/smart-home", response_class=HTMLResponse)

async def smart_home_page(request: Request):
    """Smart home control page."""
    config = load_config()
    
    # Device data (mock - would come from Tuya API)
    devices = {
        "lights": [
            {"id": "studio_light", "name": "Studio Light", "on": True},
            {"id": "desk_lamp", "name": "Desk Lamp", "on": False},
            {"id": "ceiling_light", "name": "Ceiling Light", "on": False}
        ],
        "ac": [
            {"id": "studio_ac", "name": "Studio AC", "on": True, "temp": 24}
        ],
        "plugs": [
            {"id": "coffee_plug", "name": "Coffee Machine", "on": False},
            {"id": "pc_plug", "name": "PC Setup", "on": True}
        ]
    }
    
    # Activity log
    activity_log = [
        {"time": "22:15", "device": "Studio Light", "action": "ON"},
        {"time": "21:30", "device": "AC", "action": "24°C"},
        {"time": "19:00", "device": "Coffee Machine", "action": "OFF"}
    ]
    
    return templates.TemplateResponse("smart-home.html", {
        "request": request,
        "active_page": "smart-home",
        "devices": devices,
        "activity_log": activity_log
    })


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """Settings page."""
    config = load_config()
    
    # Sounds list
    sounds = [
        {"name": "Morning Birds", "path": "gentle/birds.mp3"},
        {"name": "Ocean Waves", "path": "gentle/waves.mp3"},
        {"name": "Digital Alarm", "path": "normal/digital.mp3"},
        {"name": "Classic Bell", "path": "normal/bell.mp3"},
        {"name": "Air Raid Siren", "path": "nuclear/siren.mp3"}
    ]
    
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "active_page": "settings",
        "config": config,
        "sounds": sounds,
        "scheduler_running": scheduler_running
    })


@app.get("/api/status")

async def get_status():
    """Get system status."""
    alarms = load_alarms()
    reminders = load_reminders()
    
    active_alarms = [a for a in alarms if a.get('enabled', True)]
    active_reminders = [r for r in reminders if r.get('enabled', True)]
    
    next_alarm_info = get_next_alarm()
    
    return {
        "status": "running",
        "scheduler": scheduler_running,
        "alarms": {
            "total": len(alarms),
            "active": len(active_alarms)
        },
        "reminders": {
            "total": len(reminders),
            "active": len(active_reminders)
        },
        "next_alarm": {
            "time": next_alarm_info['alarm']['time'] if next_alarm_info else None,
            "date": next_alarm_info['alarm'].get('date') if next_alarm_info else None,
            "label": next_alarm_info['alarm'].get('label') if next_alarm_info else None,
            "seconds_until": int(next_alarm_info['delta_seconds']) if next_alarm_info else None
        } if next_alarm_info else None,
        "time": datetime.now().isoformat()
    }


@app.get("/api/next-alarm")
async def get_next_alarm_api():
    """Get next alarm info for countdown."""
    next_alarm_info = get_next_alarm()
    
    if not next_alarm_info:
        return {"next_alarm": None}
    
    alarm = next_alarm_info['alarm']
    delta = next_alarm_info['delta']
    
    return {
        "next_alarm": {
            "id": alarm['id'],
            "time": alarm['time'],
            "date": alarm.get('date'),
            "mode": alarm['mode'],
            "label": alarm.get('label', ''),
            "target_datetime": alarm.get('target_datetime'),
            "seconds_until": int(next_alarm_info['delta_seconds']),
            "formatted": f"{int(delta.total_seconds() // 3600)}h {int((delta.total_seconds() % 3600) // 60)}m {int(delta.total_seconds() % 60)}s"
        }
    }


# Alarm API
@app.get("/api/alarms")
async def get_alarms():
    """Get all alarms."""
    return load_alarms()


@app.get("/api/sounds")
async def list_sounds():
    """Get all available alarm sounds."""
    sounds = []
    if SOUNDS_DIR.exists():
        for f in sorted(SOUNDS_DIR.glob("*.mp3")):
            name = f.stem  # filename without extension
            sounds.append({
                "id": f.name,
                "name": name,
                "url": f"/sounds/{f.name}"
            })
    return sounds


# Tuya devices cache path
TUYA_SKILL_DIR = SKILL_DIR.parent / "smarthome-tuya"
TUYA_DEVICES_CACHE = TUYA_SKILL_DIR / "devices_cache.json"

@app.get("/api/devices")
async def list_devices():
    """Get all available Tuya devices from cache."""
    devices = {"lights": [], "ac": [], "plugs": [], "other": []}
    
    if not TUYA_DEVICES_CACHE.exists():
        return devices
    
    try:
        with open(TUYA_DEVICES_CACHE, 'r', encoding='utf-8') as f:
            cache = json.load(f)
        
        for device in cache.get("devices", []):
            device_info = {
                "id": device.get("id", ""),
                "name": device.get("name", "Unknown"),
                "online": device.get("online", False),
                "category": device.get("category", ""),
                "supports_brightness": device.get("supports_brightness", False),
                "supports_color": device.get("supports_color", False),
            }
            
            category = device.get("category", "")
            
            # Categorize devices
            if category in ["dj", "dd"]:  # Lights and LED strips
                device_info["icon"] = "💡"
                device_info["type"] = "light"
                devices["lights"].append(device_info)
            elif category in ["infrared_ac", "kt"]:  # AC
                device_info["icon"] = "❄️"
                device_info["type"] = "ac"
                devices["ac"].append(device_info)
            elif category in ["cz", "pc"]:  # Smart plugs
                device_info["icon"] = "🔌"
                device_info["type"] = "plug"
                devices["plugs"].append(device_info)
            else:
                device_info["icon"] = "📱"
                device_info["type"] = "other"
                devices["other"].append(device_info)
        
        return devices
    except Exception as e:
        safe_print(f"[ERROR] Loading Tuya devices: {e}")
        return devices


@app.post("/api/alarms")
async def create_alarm(request: Request):
    """
    Create new alarm with devices and actions support.
    
    Request Body:
    {
        "time": "07:00",
        "date": "2026-02-01",
        "mode": "normal",
        "label": "Morning wake",
        "sound": "gentle_alarm.wav",
        "repeat": "weekdays",
        "days": ["mon", "tue", "wed", "thu", "fri"],
        "devices": [...],
        "actions": [...]
    }
    """
    data = await request.json()
    
    # Validate required fields
    time_str = data.get("time")
    if not time_str:
        raise HTTPException(status_code=400, detail="Time is required")
    
    try:
        datetime.strptime(time_str, "%H:%M")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid time format. Use HH:MM")
    
    # Optional date validation
    date_str = data.get("date")
    if date_str:
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    
    # Create alarm with all fields
    alarm = add_alarm(
        time_str=time_str,
        mode=data.get("mode", "normal"),
        label=data.get("label", ""),
        repeat=data.get("repeat", "once"),
        date_str=date_str,
        sound=data.get("sound"),
        days=data.get("days", []),
        devices=data.get("devices", []),
        actions=data.get("actions", [])
    )
    
    if not alarm:
        raise HTTPException(status_code=400, detail="Failed to create alarm")
    
    return {"success": True, "alarm": alarm}


@app.post("/api/alarms/skip")
async def skip_next_alarm():
    """Skip the next upcoming alarm."""
    next_alarm_info = get_next_alarm()
    
    if not next_alarm_info:
        return {"success": False, "error": "No upcoming alarm to skip"}
    
    alarm_id = next_alarm_info["alarm"]["id"]
    alarms = load_alarms()
    
    for alarm in alarms:
        if alarm["id"] == alarm_id:
            alarm["enabled"] = False
            break
    
    save_alarms(alarms)
    
    return {
        "success": True, 
        "skipped_id": alarm_id,
        "message": f"Skipped alarm at {next_alarm_info['alarm']['time']}"
    }


@app.get("/api/alarms/{alarm_id}")
async def get_single_alarm(alarm_id: str):
    """Get single alarm by ID."""
    alarms = load_alarms()
    for alarm in alarms:
        if alarm["id"] == alarm_id:
            return alarm
    raise HTTPException(status_code=404, detail="Alarm not found")


@app.delete("/api/alarms/{alarm_id}")
async def remove_alarm(alarm_id: str):
    """Delete alarm."""
    success = delete_alarm(alarm_id)
    return {"success": success}


@app.post("/api/alarms/{alarm_id}/toggle")
async def toggle_alarm_status(alarm_id: str):
    """Toggle alarm enabled/disabled."""
    success = toggle_alarm(alarm_id)
    return {"success": success}


# ===========================================================================
# Active Alarm API (Snooze/Dismiss)
# ===========================================================================

@app.get("/alarm-active", response_class=HTMLResponse)
async def active_alarm_page(request: Request):
    """Active alarm page with snooze/dismiss controls."""
    status = get_active_alarm_status()
    
    return templates.TemplateResponse("alarm_active.html", {
        "request": request,
        "alarm_status": status,
        "current_time": datetime.now().strftime("%H:%M:%S"),
        "current_date": datetime.now().strftime("%A, %d %B %Y")
    })


@app.get("/api/alarm/active/status")
async def get_alarm_active_status():
    """Get current active alarm status."""
    return get_active_alarm_status()


@app.post("/api/alarm/active/snooze")
async def snooze_alarm_api(request: Request):
    """Snooze the active alarm for X minutes."""
    try:
        data = await request.json()
        minutes = int(data.get("minutes", 5))
        
        if minutes not in [5, 10, 15]:
            raise HTTPException(status_code=400, detail="Invalid snooze duration")
        
        result = snooze_active_alarm(minutes)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/alarm/active/dismiss")
async def dismiss_alarm_api(request: Request):
    """Dismiss the active alarm by answering math problem."""
    try:
        data = await request.json()
        answer = int(data.get("answer", 0))
        
        result = dismiss_active_alarm(answer)
        return result
    except ValueError:
        return {"success": False, "error": "Invalid answer format"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Reminder API
@app.get("/api/reminders")
async def get_reminders():
    """Get all reminders."""
    return load_reminders()


@app.post("/api/reminders")
async def create_reminder(
    message: str = Form(...),
    time: str = Form(...),
    date: str = Form(None),
    priority: str = Form("normal")
):
    """Create new reminder."""
    try:
        datetime.strptime(time, "%H:%M")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid time format. Use HH:MM")
    
    reminder = add_reminder(message, time, date, priority=priority)
    return {"success": True, "reminder": reminder}


@app.delete("/api/reminders/{reminder_id}")
async def remove_reminder(reminder_id: str):
    """Delete reminder."""
    success = delete_reminder(reminder_id)
    return {"success": success}


# Routine API (Full CRUD)
@app.get("/api/routines")
async def list_routines_api():
    """Get all routines."""
    return load_routines()


@app.get("/api/routines/{routine_id}")
async def get_routine_api(routine_id: str):
    """Get single routine by ID."""
    routine = get_routine_by_id(routine_id)
    if not routine:
        raise HTTPException(status_code=404, detail="Routine not found")
    return routine


@app.post("/api/routines")
async def create_routine_api(request: Request):
    """Create new routine."""
    data = await request.json()
    
    if not data.get("name"):
        raise HTTPException(status_code=400, detail="Name is required")
    
    routine = add_routine(data)
    return {"success": True, "routine": routine}


@app.put("/api/routines/{routine_id}")
async def update_routine_api(routine_id: str, request: Request):
    """Update routine."""
    data = await request.json()
    routine = update_routine(routine_id, data)
    
    if not routine:
        raise HTTPException(status_code=404, detail="Routine not found")
    
    return {"success": True, "routine": routine}


@app.delete("/api/routines/{routine_id}")
async def delete_routine_api(routine_id: str):
    """Delete routine."""
    success = delete_routine(routine_id)
    return {"success": success}


@app.post("/api/routines/{routine_id}/toggle")
async def toggle_routine_api(routine_id: str):
    """Toggle routine enabled/disabled."""
    routine = toggle_routine(routine_id)
    if not routine:
        raise HTTPException(status_code=404, detail="Routine not found")
    return {"success": True, "enabled": routine["enabled"]}


@app.post("/api/routines/{routine_id}/run")
async def run_routine_api(routine_id: str):
    """Execute routine immediately."""
    def execute():
        run_routine(routine_id)
    
    thread = threading.Thread(target=execute, daemon=True)
    thread.start()
    
    return {"success": True, "message": "Routine started"}


# Legacy routine activation (for backward compatibility)
@app.post("/api/routines/activate/{routine_name}")
async def activate_routine_legacy(routine_name: str):
    """Activate a routine by name (legacy endpoint)."""
    routines = {
        "morning": routine_morning,
        "work": routine_work,
        "sleep": routine_sleep,
        "movie": routine_movie
    }
    
    if routine_name not in routines:
        raise HTTPException(status_code=404, detail="Routine not found")
    
    def run_legacy():
        try:
            routines[routine_name]()
        except Exception as e:
            safe_print(f"[ROUTINE] Error: {e}")
    
    thread = threading.Thread(target=run_legacy, daemon=True)
    thread.start()
    
    return {"success": True, "routine": routine_name}


# Activity API
@app.get("/api/activity")
async def get_activity(limit: int = 10):
    """Get recent activity with formatted timestamps."""
    return get_recent_activity(limit)


@app.get("/api/activity/raw")
async def get_raw_activity(limit: int = 50):
    """Get raw activity log entries."""
    activities = load_activity()
    return activities[:limit]


# Analytics API
@app.get("/api/analytics")
async def get_analytics():
    """Get all analytics data."""
    return load_analytics()


@app.get("/api/analytics/score")
async def get_weekly_score():
    """Get weekly performance score."""
    return calculate_weekly_score()


@app.get("/api/analytics/heatmap")
async def get_heatmap():
    """Get snooze heatmap data by day and hour."""
    return get_snooze_heatmap()


@app.get("/api/analytics/calendar")
async def get_calendar():
    """Get historical calendar data for year view."""
    return get_calendar_data()


# Test API
@app.post("/api/test/{test_type}")
async def run_test(test_type: str, mode: str = "normal", text: str = "Test dari Shila Wake"):
    """Run test functions."""
    def run_in_thread():
        try:
            if test_type == "sound":
                test_sound()
            elif test_type == "lights":
                test_lights()
            elif test_type == "tts":
                test_tts(text)
            elif test_type == "wake":
                execute_wake(mode)
        except Exception as e:
            safe_print(f"[TEST] Error: {e}")
    
    thread = threading.Thread(target=run_in_thread, daemon=True)
    thread.start()
    
    return {"success": True, "test": test_type}


# Config API
@app.get("/api/config")
async def get_config():
    """Get configuration."""
    return load_config()


@app.post("/api/config")
async def update_config(request: Request):
    """Update configuration."""
    data = await request.json()
    config = load_config()
    config.update(data)
    save_config(config)
    return {"success": True, "config": config}


# Smart Home Quick Actions
@app.post("/api/lights/{action}")
async def control_lights(action: str, brightness: int = 100, color: str = "white"):
    """Quick light control."""
    def run():
        try:
            if action == "on":
                turn_on_lights(brightness, color)
            elif action == "off":
                from wake_system import execute_tuya_command
                execute_tuya_command("category", "lights", "off")
        except Exception as e:
            safe_print(f"[LIGHTS] Error: {e}")
    
    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    
    return {"success": True, "action": action}


@app.post("/api/ac/{action}")
async def control_ac(action: str, temp: int = 24):
    """Quick AC control."""
    def run():
        try:
            from wake_system import execute_tuya_command
            if action == "on":
                execute_tuya_command("ac", '"AC Studio"', "--power", "on", "--temp", str(temp))
            elif action == "off":
                turn_off_ac()
        except Exception as e:
            safe_print(f"[AC] Error: {e}")
    
    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    
    return {"success": True, "action": action}


# Manual check endpoint
@app.post("/api/check")
async def manual_check():
    """Manually trigger alarm/reminder check."""
    def run():
        safe_check_alarms()
        safe_check_reminders()
    
    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    
    return {"success": True, "message": "Check triggered"}


# ===========================================================================
# Main
# ===========================================================================

def main():
    safe_print("""
========================================================
       SHILA WAKE SYSTEM v2.0 - Web Dashboard
       
       Open http://localhost:8765 in browser
       
       Features:
       - Proper date handling
       - Auto date calculation
       - Stable scheduler
========================================================
    """)
    
    uvicorn.run(app, host="0.0.0.0", port=8765, log_level="info")


if __name__ == "__main__":
    main()
