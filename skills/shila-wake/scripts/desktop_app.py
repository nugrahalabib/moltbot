#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pystray>=0.19.0", "Pillow>=10.0.0", "schedule>=1.2.0"]
# ///
"""
Shila Wake System - Desktop App
System tray application for Windows.
"""
import os
import sys
import json
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

# Setup paths
SCRIPT_DIR = Path(__file__).parent
SKILL_DIR = SCRIPT_DIR.parent

sys.path.insert(0, str(SCRIPT_DIR))

# Import wake system modules
from wake_system import (
    load_config, save_config, load_alarms, save_alarms, add_alarm, delete_alarm,
    load_reminders, add_reminder, execute_wake, routine_morning, routine_work,
    routine_sleep, routine_movie, check_alarms, check_reminders,
    turn_on_lights, turn_off_ac, speak_tts, CONFIG_FILE, ALARMS_FILE
)

try:
    import pystray
    from pystray import MenuItem as item
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("Installing required packages...")
    os.system(f"{sys.executable} -m pip install pystray Pillow")
    import pystray
    from pystray import MenuItem as item
    from PIL import Image, ImageDraw, ImageFont

try:
    import schedule
except ImportError:
    os.system(f"{sys.executable} -m pip install schedule")
    import schedule


# ===========================================================================
# Configuration
# ===========================================================================

APP_NAME = "Shila Wake System"
ICON_SIZE = 64

# State
class AppState:
    def __init__(self):
        self.running = True
        self.scheduler_thread = None
        self.icon = None
        self.next_alarm = None
        self.snooze_until = None
        
state = AppState()


# ===========================================================================
# Icon Creation
# ===========================================================================

def create_icon_image(color='#FF6B6B'):
    """Create a simple icon image."""
    image = Image.new('RGBA', (ICON_SIZE, ICON_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    
    # Draw alarm clock shape
    # Circle (clock face)
    margin = 4
    draw.ellipse(
        [margin, margin + 8, ICON_SIZE - margin, ICON_SIZE - margin],
        fill=color,
        outline='white',
        width=2
    )
    
    # Clock hands
    center_x = ICON_SIZE // 2
    center_y = ICON_SIZE // 2 + 4
    
    # Hour hand
    draw.line([(center_x, center_y), (center_x - 8, center_y - 8)], fill='white', width=3)
    # Minute hand
    draw.line([(center_x, center_y), (center_x + 10, center_y - 4)], fill='white', width=2)
    
    # Bell on top
    draw.polygon([(ICON_SIZE//2 - 12, 12), (ICON_SIZE//2, 2), (ICON_SIZE//2 + 12, 12)], fill=color, outline='white')
    
    return image


def create_sleeping_icon():
    """Create icon for when no alarms are active."""
    return create_icon_image('#888888')


def create_active_icon():
    """Create icon for when alarms are active."""
    return create_icon_image('#FF6B6B')


def create_alert_icon():
    """Create icon for when alarm is ringing."""
    return create_icon_image('#FF0000')


# ===========================================================================
# Quick Add Alarm Dialog
# ===========================================================================

def show_quick_alarm_dialog():
    """Show a simple dialog to add alarm using tkinter."""
    try:
        import tkinter as tk
        from tkinter import ttk, messagebox
        
        def submit():
            time_str = time_entry.get()
            mode = mode_var.get()
            label = label_entry.get() or f"Alarm {time_str}"
            
            # Validate time format
            try:
                datetime.strptime(time_str, "%H:%M")
            except ValueError:
                messagebox.showerror("Error", "Format waktu salah! Gunakan HH:MM")
                return
            
            add_alarm(time_str, mode, label)
            update_next_alarm()
            messagebox.showinfo("Sukses", f"Alarm {time_str} ({mode}) ditambahkan!")
            root.destroy()
        
        root = tk.Tk()
        root.title("Tambah Alarm - Shila Wake")
        root.geometry("350x250")
        root.resizable(False, False)
        
        # Center window
        root.eval('tk::PlaceWindow . center')
        
        # Style
        style = ttk.Style()
        style.configure('TLabel', font=('Segoe UI', 10))
        style.configure('TButton', font=('Segoe UI', 10))
        
        # Main frame
        main_frame = ttk.Frame(root, padding=20)
        main_frame.pack(fill='both', expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text="⏰ Tambah Alarm Baru", font=('Segoe UI', 14, 'bold'))
        title_label.pack(pady=(0, 15))
        
        # Time input
        time_frame = ttk.Frame(main_frame)
        time_frame.pack(fill='x', pady=5)
        ttk.Label(time_frame, text="Waktu (HH:MM):").pack(side='left')
        time_entry = ttk.Entry(time_frame, width=10)
        time_entry.pack(side='right')
        time_entry.insert(0, "07:00")
        
        # Mode selection
        mode_frame = ttk.Frame(main_frame)
        mode_frame.pack(fill='x', pady=5)
        ttk.Label(mode_frame, text="Mode:").pack(side='left')
        mode_var = tk.StringVar(value='normal')
        mode_combo = ttk.Combobox(mode_frame, textvariable=mode_var, values=['gentle', 'normal', 'nuclear'], width=10, state='readonly')
        mode_combo.pack(side='right')
        
        # Label input
        label_frame = ttk.Frame(main_frame)
        label_frame.pack(fill='x', pady=5)
        ttk.Label(label_frame, text="Label:").pack(side='left')
        label_entry = ttk.Entry(label_frame, width=20)
        label_entry.pack(side='right')
        
        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill='x', pady=20)
        ttk.Button(btn_frame, text="Tambah", command=submit).pack(side='right', padx=5)
        ttk.Button(btn_frame, text="Batal", command=root.destroy).pack(side='right')
        
        root.mainloop()
        
    except Exception as e:
        print(f"Dialog error: {e}")


def show_alarm_list_dialog():
    """Show list of alarms."""
    try:
        import tkinter as tk
        from tkinter import ttk, messagebox
        
        def delete_selected():
            selection = tree.selection()
            if not selection:
                return
            
            alarm_id = tree.item(selection[0])['values'][0]
            if messagebox.askyesno("Konfirmasi", f"Hapus alarm {alarm_id}?"):
                delete_alarm(alarm_id)
                refresh_list()
                update_next_alarm()
        
        def refresh_list():
            for item in tree.get_children():
                tree.delete(item)
            
            alarms = load_alarms()
            for alarm in alarms:
                status = "✓" if alarm.get('enabled', True) else "✗"
                tree.insert('', 'end', values=(
                    alarm['id'],
                    alarm['time'],
                    alarm['mode'],
                    alarm.get('label', '')[:20],
                    status
                ))
        
        root = tk.Tk()
        root.title("Daftar Alarm - Shila Wake")
        root.geometry("500x350")
        
        # Center window
        root.eval('tk::PlaceWindow . center')
        
        # Main frame
        main_frame = ttk.Frame(root, padding=10)
        main_frame.pack(fill='both', expand=True)
        
        # Title
        ttk.Label(main_frame, text="📋 Daftar Alarm", font=('Segoe UI', 14, 'bold')).pack(pady=(0, 10))
        
        # Treeview
        columns = ('ID', 'Waktu', 'Mode', 'Label', 'Aktif')
        tree = ttk.Treeview(main_frame, columns=columns, show='headings', height=10)
        
        tree.heading('ID', text='ID')
        tree.heading('Waktu', text='Waktu')
        tree.heading('Mode', text='Mode')
        tree.heading('Label', text='Label')
        tree.heading('Aktif', text='Aktif')
        
        tree.column('ID', width=120)
        tree.column('Waktu', width=60)
        tree.column('Mode', width=70)
        tree.column('Label', width=150)
        tree.column('Aktif', width=50)
        
        tree.pack(fill='both', expand=True)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(main_frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill='x', pady=10)
        ttk.Button(btn_frame, text="Hapus", command=delete_selected).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Refresh", command=refresh_list).pack(side='left')
        ttk.Button(btn_frame, text="Tutup", command=root.destroy).pack(side='right')
        
        refresh_list()
        root.mainloop()
        
    except Exception as e:
        print(f"Dialog error: {e}")


def show_quick_reminder_dialog():
    """Show dialog to add quick reminder."""
    try:
        import tkinter as tk
        from tkinter import ttk, messagebox
        
        def submit():
            message = message_entry.get()
            time_str = time_entry.get()
            priority = priority_var.get()
            
            if not message:
                messagebox.showerror("Error", "Pesan tidak boleh kosong!")
                return
            
            try:
                datetime.strptime(time_str, "%H:%M")
            except ValueError:
                messagebox.showerror("Error", "Format waktu salah! Gunakan HH:MM")
                return
            
            add_reminder(message, time_str, priority=priority)
            messagebox.showinfo("Sukses", f"Reminder ditambahkan untuk {time_str}!")
            root.destroy()
        
        root = tk.Tk()
        root.title("Tambah Reminder - Shila Wake")
        root.geometry("400x280")
        root.resizable(False, False)
        root.eval('tk::PlaceWindow . center')
        
        main_frame = ttk.Frame(root, padding=20)
        main_frame.pack(fill='both', expand=True)
        
        ttk.Label(main_frame, text="📝 Tambah Reminder", font=('Segoe UI', 14, 'bold')).pack(pady=(0, 15))
        
        # Message
        msg_frame = ttk.Frame(main_frame)
        msg_frame.pack(fill='x', pady=5)
        ttk.Label(msg_frame, text="Pesan:").pack(side='left')
        message_entry = ttk.Entry(msg_frame, width=30)
        message_entry.pack(side='right')
        
        # Time
        time_frame = ttk.Frame(main_frame)
        time_frame.pack(fill='x', pady=5)
        ttk.Label(time_frame, text="Waktu (HH:MM):").pack(side='left')
        time_entry = ttk.Entry(time_frame, width=10)
        time_entry.pack(side='right')
        time_entry.insert(0, "14:00")
        
        # Priority
        pri_frame = ttk.Frame(main_frame)
        pri_frame.pack(fill='x', pady=5)
        ttk.Label(pri_frame, text="Prioritas:").pack(side='left')
        priority_var = tk.StringVar(value='normal')
        priority_combo = ttk.Combobox(pri_frame, textvariable=priority_var, values=['low', 'normal', 'high'], width=10, state='readonly')
        priority_combo.pack(side='right')
        
        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill='x', pady=20)
        ttk.Button(btn_frame, text="Tambah", command=submit).pack(side='right', padx=5)
        ttk.Button(btn_frame, text="Batal", command=root.destroy).pack(side='right')
        
        root.mainloop()
        
    except Exception as e:
        print(f"Dialog error: {e}")


# ===========================================================================
# Menu Actions
# ===========================================================================

def action_add_alarm(icon, item):
    """Add alarm action."""
    threading.Thread(target=show_quick_alarm_dialog, daemon=True).start()


def action_list_alarms(icon, item):
    """Show alarm list."""
    threading.Thread(target=show_alarm_list_dialog, daemon=True).start()


def action_add_reminder(icon, item):
    """Add reminder action."""
    threading.Thread(target=show_quick_reminder_dialog, daemon=True).start()


def action_routine_morning(icon, item):
    """Activate morning routine."""
    threading.Thread(target=routine_morning, daemon=True).start()


def action_routine_work(icon, item):
    """Activate work routine."""
    threading.Thread(target=routine_work, daemon=True).start()


def action_routine_sleep(icon, item):
    """Activate sleep routine."""
    threading.Thread(target=routine_sleep, daemon=True).start()


def action_routine_movie(icon, item):
    """Activate movie routine."""
    threading.Thread(target=routine_movie, daemon=True).start()


def action_test_wake(icon, item):
    """Test wake sequence."""
    def test():
        speak_tts("Ini adalah tes dari Shila Wake System")
        turn_on_lights(brightness=100, color="white")
    threading.Thread(target=test, daemon=True).start()


def action_snooze(icon, item):
    """Snooze current alarm."""
    config = load_config()
    minutes = config.get('snooze_minutes', 10)
    state.snooze_until = datetime.now() + timedelta(minutes=minutes)
    show_notification("Snooze", f"Alarm di-snooze {minutes} menit")


def action_stop_alarm(icon, item):
    """Stop current alarm."""
    state.snooze_until = None
    show_notification("Alarm Stopped", "Alarm dihentikan")


def action_open_dashboard(icon, item):
    """Open web dashboard."""
    import webbrowser
    webbrowser.open("http://localhost:8765")


def action_quit(icon, item):
    """Quit the application."""
    state.running = False
    icon.stop()


# ===========================================================================
# Notification
# ===========================================================================

def show_notification(title: str, message: str):
    """Show Windows notification."""
    try:
        from win10toast import ToastNotifier
        toaster = ToastNotifier()
        toaster.show_toast(title, message, duration=5, threaded=True)
    except ImportError:
        # Fallback to simple notification via icon
        if state.icon:
            state.icon.notify(message, title)
    except Exception:
        pass


# ===========================================================================
# Scheduler Thread
# ===========================================================================

def update_next_alarm():
    """Update next alarm info."""
    alarms = load_alarms()
    active_alarms = [a for a in alarms if a.get('enabled', True)]
    
    if active_alarms:
        # Sort by time
        now = datetime.now()
        next_alarm = None
        min_delta = None
        
        for alarm in active_alarms:
            alarm_time = datetime.strptime(alarm['time'], "%H:%M").replace(
                year=now.year, month=now.month, day=now.day
            )
            if alarm_time <= now:
                alarm_time += timedelta(days=1)
            
            delta = alarm_time - now
            if min_delta is None or delta < min_delta:
                min_delta = delta
                next_alarm = alarm
        
        state.next_alarm = next_alarm
    else:
        state.next_alarm = None


def scheduler_thread_func():
    """Background scheduler thread."""
    print("[SCHEDULER] Starting background scheduler...")
    
    # Schedule checks
    schedule.every().minute.at(":00").do(check_alarms)
    schedule.every().minute.at(":00").do(check_reminders)
    schedule.every(5).minutes.do(update_next_alarm)
    
    update_next_alarm()
    
    while state.running:
        # Check snooze
        if state.snooze_until and datetime.now() >= state.snooze_until:
            state.snooze_until = None
            # Trigger alarm again
            if state.next_alarm:
                execute_wake(state.next_alarm.get('mode', 'normal'))
        
        schedule.run_pending()
        time.sleep(1)
    
    print("[SCHEDULER] Scheduler stopped.")


# ===========================================================================
# System Tray Menu
# ===========================================================================

def get_menu_title():
    """Get dynamic menu title."""
    if state.next_alarm:
        return f"Next: {state.next_alarm['time']} ({state.next_alarm['mode']})"
    return "No alarms set"


def create_menu():
    """Create system tray menu."""
    return pystray.Menu(
        item(lambda text: get_menu_title(), None, enabled=False),
        pystray.Menu.SEPARATOR,
        item('⏰ Tambah Alarm', action_add_alarm),
        item('📋 Lihat Alarm', action_list_alarms),
        item('📝 Tambah Reminder', action_add_reminder),
        pystray.Menu.SEPARATOR,
        item('🎛️ Routines', pystray.Menu(
            item('☀️ Morning', action_routine_morning),
            item('💼 Work', action_routine_work),
            item('🌙 Sleep', action_routine_sleep),
            item('🎬 Movie', action_routine_movie),
        )),
        pystray.Menu.SEPARATOR,
        item('⏸️ Snooze (10 min)', action_snooze),
        item('⏹️ Stop Alarm', action_stop_alarm),
        pystray.Menu.SEPARATOR,
        item('🌐 Open Dashboard', action_open_dashboard),
        item('🔊 Test', action_test_wake),
        pystray.Menu.SEPARATOR,
        item('❌ Quit', action_quit),
    )


# ===========================================================================
# Main
# ===========================================================================

def main():
    print("""
========================================================
         SHILA WAKE SYSTEM - Desktop App
         
  System tray application for alarm management
========================================================
    """)
    
    # Start scheduler thread
    state.scheduler_thread = threading.Thread(target=scheduler_thread_func, daemon=True)
    state.scheduler_thread.start()
    
    # Create icon
    icon_image = create_active_icon()
    
    state.icon = pystray.Icon(
        APP_NAME,
        icon_image,
        APP_NAME,
        menu=create_menu()
    )
    
    print(f"[APP] Starting system tray icon...")
    print(f"[APP] Right-click the tray icon to access menu.")
    print(f"[APP] Press Ctrl+C in this window to quit.")
    
    # Run icon (blocking)
    try:
        state.icon.run()
    except KeyboardInterrupt:
        state.running = False
        state.icon.stop()
    
    print("[APP] Application stopped.")


if __name__ == '__main__':
    main()
