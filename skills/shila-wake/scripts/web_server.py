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
    execute_wake, routine_morning, routine_work, routine_sleep, routine_movie,
    check_alarms, check_reminders, turn_on_lights, turn_off_ac, speak_tts,
    test_sound, test_lights, test_tts, get_next_alarm, safe_print,
    ALARMS_FILE, REMINDERS_FILE, CONFIG_FILE
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


# ===========================================================================
# API Routes
# ===========================================================================

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard page."""
    alarms = load_alarms()
    reminders = load_reminders()
    config = load_config()
    
    # Get next alarm info
    next_alarm_info = get_next_alarm()
    
    now = datetime.now()
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "alarms": alarms,
        "reminders": reminders,
        "config": config,
        "next_alarm": next_alarm_info,
        "current_time": now.strftime("%H:%M:%S"),
        "current_date": now.strftime("%A, %d %B %Y"),
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


@app.post("/api/alarms")
async def create_alarm(
    time: str = Form(...),
    mode: str = Form("normal"),
    label: str = Form(""),
    repeat: str = Form("once"),
    date: str = Form(None)
):
    """Create new alarm with auto date calculation."""
    try:
        datetime.strptime(time, "%H:%M")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid time format. Use HH:MM")
    
    if date:
        try:
            datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    
    alarm = add_alarm(time, mode, label, repeat, date)
    return {"success": True, "alarm": alarm}


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


# Routine API
@app.post("/api/routines/{routine_name}")
async def activate_routine(routine_name: str):
    """Activate a routine."""
    routines = {
        "morning": routine_morning,
        "work": routine_work,
        "sleep": routine_sleep,
        "movie": routine_movie
    }
    
    if routine_name not in routines:
        raise HTTPException(status_code=404, detail="Routine not found")
    
    def run_routine():
        try:
            routines[routine_name]()
        except Exception as e:
            safe_print(f"[ROUTINE] Error: {e}")
    
    thread = threading.Thread(target=run_routine, daemon=True)
    thread.start()
    
    return {"success": True, "routine": routine_name}


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
