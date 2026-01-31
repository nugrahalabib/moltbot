---
name: shila-wake
description: |
  Smart alarm & reminder system with multi-action wake capabilities.
  Use when user asks to: set alarm, wake up, reminder, bangunin, ingatkan.
  Supports: gentle/normal/nuclear wake modes, smart home integration (lights, AC),
  TTS announcements, chat notifications, and PC audio alerts.
  Keywords: alarm, bangun, bangunin, wake, reminder, ingatkan, pengingat, jadwal.
---

# Shila Wake System

AI-powered smart alarm & reminder system with multi-action wake capabilities.

## Features

- ⏰ **Smart Alarms** - Gentle, Normal, Nuclear modes
- 📝 **Reminders** - One-time and recurring
- 💡 **Smart Home Integration** - Lights, AC control via Tuya
- 🔊 **Audio Alerts** - PC speaker alarm sounds
- 🗣️ **TTS Announcements** - Voice wake-up calls
- 💬 **Chat Notifications** - Telegram/WhatsApp alerts

## Quick Start

### Script Location
```
C:\Users\nugra\OneDrive\Documents\Project\Shila-PartnerInCrime\moltbot\skills\shila-wake\scripts\
```

### Run Commands
```powershell
# Start the wake system daemon (background service)
python wake_system.py start

# Stop the daemon
python wake_system.py stop

# Check status
python wake_system.py status
```

## Alarm Commands

### Add Alarm
```powershell
# Simple alarm
python wake_system.py alarm add 07:00

# With mode (gentle/normal/nuclear)
python wake_system.py alarm add 07:00 --mode nuclear

# With label
python wake_system.py alarm add 07:00 --label "Meeting pagi"

# Recurring (daily)
python wake_system.py alarm add 07:00 --repeat daily

# Specific days (mon,tue,wed,thu,fri,sat,sun)
python wake_system.py alarm add 07:00 --repeat mon,tue,wed,thu,fri

# One-time specific date
python wake_system.py alarm add 07:00 --date 2026-02-01
```

### List Alarms
```powershell
python wake_system.py alarm list
```

### Delete Alarm
```powershell
python wake_system.py alarm delete <alarm_id>

# Delete all
python wake_system.py alarm delete --all
```

### Snooze
```powershell
# Snooze active alarm for 10 minutes (default)
python wake_system.py snooze

# Snooze for specific minutes
python wake_system.py snooze 15
```

## Reminder Commands

### Add Reminder
```powershell
# Simple reminder
python wake_system.py remind "Meeting dengan client" --at 14:00

# With date
python wake_system.py remind "Bayar tagihan" --at 09:00 --date 2026-02-05

# Recurring
python wake_system.py remind "Minum obat" --at 08:00 --repeat daily

# High priority
python wake_system.py remind "DEADLINE!" --at 17:00 --priority high
```

### List Reminders
```powershell
python wake_system.py remind list
```

### Delete Reminder
```powershell
python wake_system.py remind delete <reminder_id>
```

## Wake Modes

### Gentle Mode ☀️
Best for: Weekends, holidays, no rush

Timeline:
- -30 min: AC starts turning off gradually
- -15 min: Lights 10% (warm color)
- -10 min: Lights 30% + soft music
- -5 min: Lights 50%
- 0 min: Lights 100% + TTS "Selamat pagi, Sayang~"

### Normal Mode ⏰
Best for: Regular work days

Timeline:
- -5 min: Lights 50%
- 0 min: Lights 100% + alarm sound + AC off
- +2 min: Chat notification
- +5 min: Louder alarm + repeated TTS

### Nuclear Mode ☢️
Best for: Critical meetings, deadlines, MUST NOT OVERSLEEP

Timeline:
- 0 min: ALL lights 100% WHITE + AC OFF + LOUD ALARM
- +1 min: Chat spam every 30 seconds
- +3 min: Repeated TTS "BANGUN! SUDAH TELAT!"
- +5 min: Annoying sound loop
- NO SNOOZE ALLOWED

## Quick Actions

```powershell
# Test alarm sound
python wake_system.py test sound

# Test lights (via Tuya)
python wake_system.py test lights

# Test TTS
python wake_system.py test tts "Selamat pagi Sayang"

# Test full wake sequence
python wake_system.py test wake --mode normal
```

## Routine Commands

```powershell
# Activate predefined routine
python wake_system.py routine morning
python wake_system.py routine work
python wake_system.py routine sleep
python wake_system.py routine movie
```

## Chat Commands (Natural Language)

When chatting with Shila, you can say:

```
"Bangunin aku jam 7 pagi"
"Set alarm 06:30 mode nuclear"
"Alarm besok jam 8"
"Ingatkan aku meeting jam 2 siang"
"Cancel alarm"
"List alarm"
"Snooze 10 menit"
"Aktifkan mode tidur"
```

## Configuration

Config file: `shila-wake/config.json`

```json
{
  "default_mode": "normal",
  "snooze_minutes": 10,
  "max_snooze": 3,
  "sounds": {
    "gentle": "gentle_alarm.mp3",
    "normal": "alarm.mp3",
    "nuclear": "nuclear_alarm.mp3"
  },
  "tts": {
    "enabled": true,
    "voice": "default"
  },
  "tuya": {
    "enabled": true,
    "wake_lights": ["lampu meja", "soft box 1", "soft box 2"],
    "ac_device": "AC Studio"
  },
  "chat": {
    "enabled": true,
    "channel": "whatsapp"
  }
}
```

## Integration with Moltbot

The wake system integrates with Moltbot via:
1. **Cron jobs** - For scheduling alarms/reminders
2. **Tuya skill** - For smart home control
3. **TTS** - For voice announcements
4. **Message tool** - For chat notifications

## Running the Full System

### Option 1: Launcher (Recommended)
Starts everything at once:
```powershell
python scripts/launcher.py
```
This will start:
- Web Dashboard (http://localhost:8765)
- Desktop App (System Tray)
- Scheduler (Background)

### Option 2: Individual Components

**Web Dashboard only:**
```powershell
python scripts/web_server.py
```
Open http://localhost:8765 in browser.

**Desktop App only:**
```powershell
python scripts/desktop_app.py
```
Look for alarm icon in system tray.

**CLI Daemon only:**
```powershell
python scripts/wake_system.py start
```

## Web Dashboard Features

- **Real-time clock** with countdown to next alarm
- **Add/Edit/Delete alarms** with visual interface
- **Quick Routines** - One-click Morning/Work/Sleep/Movie modes
- **Smart Home Controls** - Direct lights and AC control
- **Test buttons** - Test sound, lights, TTS, wake sequence

## Desktop App Features

- **System Tray icon** - Always accessible
- **Quick menu** - Right-click for all options
- **Add alarm dialog** - Simple popup form
- **Routine shortcuts** - Quick access to all routines
- **Notifications** - Windows toast notifications

## Troubleshooting

### Alarm not triggering
- Check if wake_system daemon is running: `python wake_system.py status`
- Check system time/timezone

### Lights not responding
- Verify Tuya credentials
- Run `python tuya_control.py list` to check device status

### No sound
- Check PC volume
- Test with: `python wake_system.py test sound`

### TTS not working
- Ensure Moltbot TTS is configured
- Test with: `python wake_system.py test tts "test"`
