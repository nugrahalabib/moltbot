---
name: shila-wake
description: |
  Smart alarm system with wake modes (gentle/normal/nuclear), smart home device control, 
  and notification actions (voice, WhatsApp, Telegram). Use when user asks to: set alarm, 
  bangunin, reminder, buatkan alarm, hapus alarm, edit alarm, list alarm.
  Keywords: alarm, bangun, bangunin, wake, reminder, ingatkan, jadwal.
metadata: {"moltbot":{"emoji":"⏰"}}
---

# Shila Wake - Alarm Management

Use `wake_system.py` to manage alarms with smart home integration.

## Script Location
```
C:\Users\nugra\OneDrive\Documents\Project\Shila-PartnerInCrime\moltbot\skills\shila-wake\scripts\wake_system.py
```

Run with: `python wake_system.py <command> [args]`

---

## 🚀 Startup - How to Run Wake System

> [!IMPORTANT]
> **WAJIB JALANKAN WEB SERVER** agar alarm bisa berfungsi!
> Web server harus running agar scheduler bisa monitor dan trigger alarm.

### Start Web Server (REQUIRED)
```powershell
cd C:\Users\nugra\OneDrive\Documents\Project\Shila-PartnerInCrime\moltbot\skills\shila-wake\scripts
python web_server.py
```

**Expected output:**
```
========================================================
       SHILA WAKE SYSTEM v2.0 - Web Dashboard
       Open http://localhost:8765 in browser
========================================================
[SCHEDULER] Background scheduler started
INFO:     Uvicorn running on http://0.0.0.0:8765
```

### Check if Already Running
Jika sudah running, akses http://localhost:8765 di browser atau gunakan:
```powershell
Invoke-RestMethod -Uri "http://localhost:8765/api/alarms" -Method GET
```

### Dashboard URL
- **Main Dashboard**: http://localhost:8765
- **Alarms Page**: http://localhost:8765/alarms
- **Active Alarm**: http://localhost:8765/alarm-active (saat alarm trigger)

---

## Add Alarm

```python
from wake_system import add_alarm

add_alarm(
    time_str="07:00",                    # REQUIRED: HH:MM format
    mode="normal",                       # REQUIRED: gentle | normal | nuclear
    label="Morning Routine",             # Optional: descriptive label
    repeat="once",                       # Optional: once | daily | weekdays | weekends
    date="2026-02-01",                   # Optional: YYYY-MM-DD (default: today)
    sound="Birds.mp3",                   # Optional: sound file (see list below)
    devices=[...],                       # Optional: smart home devices
    actions=[...]                        # Optional: notification actions
)
```

---

## Edit Alarm

```python
from wake_system import update_alarm

update_alarm(
    alarm_id="alarm_1769902777",         # REQUIRED: existing alarm ID
    time_str="08:00",                    # Optional: new time
    mode="nuclear",                      # Optional: new mode
    label="Updated Label",               # Optional: new label
    sound="Piano.mp3",                   # Optional: new sound
    devices=[...],                       # Optional: replace all devices
    actions=[...]                        # Optional: replace all actions
)
```

---

## Delete Alarm

```python
from wake_system import delete_alarm

delete_alarm("alarm_1769902777")         # Delete specific alarm
delete_alarm(delete_all=True)            # Delete ALL alarms
```

---

## List Alarms

```python
from wake_system import load_alarms

alarms = load_alarms()
for a in alarms:
    print(f"{a['id']}: {a['time']} - {a['label']} ({a['mode']})")
```

---

## Wake Modes

| Mode | Description | Recommended Sounds |
|------|-------------|-------------------|
| `gentle` | Gradual lights 30→100%, soft sound, gentle TTS | Gentle category sounds |
| `normal` | Lights ON 100%, alarm sound, normal TTS | Normal category sounds |
| `nuclear` | ALL lights MAX, loud alarm 5x, urgent TTS, no snooze | Nuclear category sounds |

---

## Available Sounds (32 files)

> [!CAUTION]
> **STRICT RULES untuk pemilihan sound:**
> 1. Sound filename harus **EXACT** (case-sensitive) - contoh: `Birds.mp3` BUKAN `birds.mp3`
> 2. Sound **WAJIB** dipilih dari kategori yang sesuai dengan mode alarm
> 3. **JANGAN** pilih sound di luar kategori mode yang dipilih
> 4. Jika user tidak spesifik, pilih sound DEFAULT dari kategori yang sesuai

### Sound Selection by Mode

| Mode | Kategori Sound | Default Sound | Keywords User |
|------|---------------|---------------|---------------|
| `gentle` | GENTLE | `Birds.mp3` | lembut, pelan, santai, soft, calm, nature |
| `normal` | NORMAL | `Bells.mp3` | biasa, standar, normal, regular |
| `nuclear` | NUCLEAR | `School.mp3` | keras, brutal, kencang, loud, urgent, extreme |

### 🌿 GENTLE Mode Sounds ONLY
**Gunakan untuk mode `gentle` saja!**

| Filename (EXACT) | Description | Keywords |
|------------------|-------------|----------|
| `Birds.mp3` | Bird chirping - nature ambience | burung, nature, alam |
| `Windchimes.mp3` | Wind chimes - peaceful | angin, chimes |
| `Glow.mp3` | Soft ambient glow | ambient, glow |
| `Twinkle.mp3` | Gentle twinkling | twinkle, bintang |
| `Pizzicato.mp3` | Soft pizzicato strings | strings, pizzicato |
| `Piano.mp3` | Calm piano melody | piano |
| `Harp.mp3` | Gentle harp melody | harp, harpa |
| `Guitar.mp3` | Soft guitar melody | guitar, gitar |
| `Flute.mp3` | Peaceful flute melody | flute, seruling |
| `MusicBox.mp3` | Delicate music box | music box, kotak musik |
| `ParadiseIsland.mp3` | Tropical ambience | tropis, island, pantai |
| `Savannah.mp3` | Savannah nature sounds | savannah, safari |

### ⏰ NORMAL Mode Sounds ONLY  
**Gunakan untuk mode `normal` saja!**

| Filename (EXACT) | Description | Keywords |
|------------------|-------------|----------|

| `Bells.mp3` | Bell chime | bell, lonceng |
| `Bells2.mp3` | Bell chime variant 2 | bell |
| `Bells3.mp3` | Bell chime variant 3 | bell |
| `Bells4.mp3` | Bell chime variant 4 | bell |
| `Bells5.mp3` | Bell chime variant 5 | bell |
| `Bells6.mp3` | Bell chime variant 6 | bell |
| `Bells7.mp3` | Bell chime variant 7 | bell |
| `Classic.mp3` | Classic alarm tone | classic, klasik |
| `Classic2.mp3` | Classic alarm variant 2 | classic |
| `Classic3.mp3` | Classic alarm variant 3 | classic |
| `Xylophone.mp3` | Xylophone melody | xylophone |
| `Happy.mp3` | Upbeat happy melody | happy, senang, ceria |
| `Childhood.mp3` | Cheerful childhood melody | childhood, ceria |
| `Christmas.mp3` | Festive Christmas melody | christmas, natal |

### ☢️ NUCLEAR Mode Sounds ONLY
**Gunakan untuk mode `nuclear` saja! Untuk sound brutal/keras/kencang!**

| Filename (EXACT) | Description | Keywords |
|------------------|-------------|----------|
| `Alarm.mp3` | Standard alarm beep | alarm, beep |
| `School.mp3` | Loud school bell | sekolah, school, keras, brutal |
| `Rooster.mp3` | Loud rooster crow | ayam, rooster, brutal |
| `Cuckoo.mp3` | Loud cuckoo clock | cuckoo, kukuk |
| `Electricity.mp3` | Electronic urgent beep | elektrik, urgent, darurat |
| `Pipe.mp3` | Loud pipe organ | pipe, organ, keras |

---

## Smart Home Devices

### Check Available Devices
Shila dapat cek device yang tersedia dengan command:
```bash
python tuya_control.py list
```
Script location: `C:\Users\nugra\OneDrive\Documents\Project\Shila-PartnerInCrime\moltbot\skills\smarthome-tuya\scripts\tuya_control.py`

### All Available Devices (10 devices)

Device names are **CASE-SENSITIVE**. Use exact names as shown:

#### 💡 Lights (7 devices)
| Device Name | Type | Product | Supports |
|-------------|------|---------|----------|
| `lampu meja` | light | Wi-Fi Bulb | on/off, brightness (0-100), color |
| `lampu strip dinding` | light | BARDI LED Flowing Strip 5M | on/off, brightness, color |
| `lampu strip meja` | light | BARDI RGBWW strip | on/off, brightness, color |
| `soft box 1` | light | BARDI 12w rgbww bulb | on/off, brightness, color |
| `soft box 2` | light | BARDI 12w rgbww bulb | on/off, brightness, color |
| `lampu tidur` | plug | Smart plug (controls lamp) | on/off only |
| `monitor` | plug | Smart plug (controls monitor) | on/off only |

#### ❄️ AC (1 device)
| Device Name | Type | Product | Supports |
|-------------|------|---------|----------|
| `AC Studio` | ac | IR AC Controller | on/off, temp (16-30), mode (cool/heat/auto/fan/dry) |

#### 🔌 IR Remote (1 device)
| Device Name | Type | Product | Notes |
|-------------|------|---------|-------|
| `Remote` | remote | Dual-mode IR Blaster | Used to control AC Studio |

### Device JSON Formats

#### Light Device
```json
{
  "id": "lampu meja",
  "name": "lampu meja",
  "type": "light",
  "action": "on",
  "brightness": 100,
  "color": "white"
}
```

#### Smart Plug Device
```json
{
  "id": "lampu tidur",
  "name": "lampu tidur",
  "type": "plug",
  "action": "on"
}
```

#### AC Device
```json
{
  "id": "AC Studio",
  "name": "AC Studio",
  "type": "ac",
  "action": "on",
  "temperature": 24,
  "ac_mode": "cool"
}
```

### Available Colors
`white`, `warm`, `red`, `orange`, `yellow`, `green`, `cyan`, `blue`, `purple`, `pink`

---

## Additional Actions

| Action ID | Required Fields | Optional Fields | Description |
|-----------|-----------------|-----------------|-------------|
| `voice` | `message` | - | TTS announcement via Gemini |
| `whatsapp` | `recipient`, `message` | - | Send WhatsApp (via Shila) |
| `telegram` | `message` | - | Send Telegram (via Shila) |
| `weather` | - | `location` | Fetch & announce real weather from wttr.in |
| `music` | - | `playlist` | Play music (via Shila) |
| `quote` | - | - | Random motivational quote TTS |
| `spam` | `message` | `channels` | **INFINITE LOOP** repeated notifications until dismissed |

### Action JSON Formats

#### Voice (TTS Announcement)
```json
{
  "id": "voice",
  "message": "Selamat pagi! Ayo bangun!"
}
```

#### WhatsApp Notification
```json
{
  "id": "whatsapp",
  "recipient": "+6287877974096",
  "message": "Alarm berbunyi! Waktunya bangun!"
}
```

#### Telegram Notification
```json
{
  "id": "telegram",
  "message": "Waktunya bangun!"
}
```

#### Weather Report
```json
{
  "id": "weather",
  "location": "Jakarta"
}
```
> Fetches real weather from wttr.in API and announces via TTS.
> Location is optional, defaults to "Jakarta".

#### Play Music
```json
{
  "id": "music",
  "playlist": "morning vibes"
}
```

#### Motivational Quote
```json
{
  "id": "quote"
}
```
> Randomly selects from 5 motivational quotes and speaks via TTS.

#### Spam Mode (INFINITE LOOP until dismissed!)
```json
{
  "id": "spam",
  "message": "BANGUN SEKARANG!",
  "channels": ["tts", "telegram", "whatsapp"]
}
```
> [!CAUTION]
> **SPAM MODE = INFINITE LOOP!**
> - Spam terus berulang setiap 15 detik sampai alarm di-dismiss via math problem
> - `message`: Custom spam message (default: "BANGUN SAYANG!")
> - `channels`: Array of `"tts"`, `"telegram"`, `"whatsapp"` (default: `["tts"]`)
> - Tidak ada limit! Akan spam terus sampai user bangun dan dismiss alarm

---

## Active Alarm System ⏰🔔

Saat alarm trigger, Active Alarm System akan aktif dengan fitur:

### Fitur Active Alarm

| Fitur | Deskripsi |
|-------|-----------|
| **Auto Open Browser** | Browser otomatis terbuka ke `/alarm-active` |
| **Max Volume** | Volume PC di-set ke 100% |
| **Sound Loop** | Alarm sound loop terus sampai dismiss |
| **Snooze Options** | 5, 10, atau 15 menit - semua actions diulang setelah snooze |
| **Math Dismiss** | Wajib jawab soal matematika kelas 6 untuk matikan alarm |
| **Browser Watchdog** | Jika browser ditutup, otomatis dibuka lagi (setiap 30 detik) |
| **Spam Forever** | Jika ada action spam, loop terus sampai dismiss |

### Active Alarm Page
URL: `http://localhost:8765/alarm-active`

Fitur halaman:
- Jam digital besar (fullscreen)
- Tombol snooze (5/10/15 menit)
- Soal matematika untuk dismiss
- Warning jika coba tutup browser

### API Endpoints

```
GET  /api/alarm/active/status   - Cek status alarm aktif
POST /api/alarm/active/snooze   - Snooze alarm (body: {"minutes": 5|10|15})
POST /api/alarm/active/dismiss  - Dismiss dengan jawaban (body: {"answer": 42})
```

### Math Problem Types
- Penjumlahan dengan perkalian: `7 × 8 + 15`
- Pengurangan dengan perkalian: `9 × 6 - 12`
- Perkalian dengan tanda kurung: `(4 + 5) × 7`
- Kuadrat: `8² + 13`

---

## Complete Examples

### Full Python Example (All Parameters)
```python
import sys
sys.path.insert(0, r'C:\Users\nugra\OneDrive\Documents\Project\Shila-PartnerInCrime\moltbot\skills\shila-wake\scripts')
from wake_system import add_alarm

add_alarm(
    time_str="07:00",               # REQUIRED: HH:MM format
    mode="normal",                   # gentle | normal | nuclear
    label="Morning Wake Up",         # Descriptive label
    repeat="daily",                  # once | daily | weekdays | weekends
    date_str="2026-02-01",          # YYYY-MM-DD (optional, auto-calculated)
    sound="Birds.mp3",               # Sound file from /sounds/
    devices=[
        {"id": "lampu meja", "name": "lampu meja", "type": "light", "action": "on", "brightness": 100, "color": "warm"},
        {"id": "lampu strip meja", "name": "lampu strip meja", "type": "light", "action": "on", "brightness": 80},
        {"id": "AC Studio", "name": "AC Studio", "type": "ac", "action": "off"}
    ],
    actions=[
        {"id": "weather", "location": "Jakarta"},
        {"id": "voice", "message": "Selamat pagi sayang! Waktunya bangun dan mulai hari dengan semangat!"},
        {"id": "quote"}
    ]
)
```

### Nuclear Wake with INFINITE SPAM
```python
add_alarm(
    time_str="06:00",
    mode="nuclear",
    label="BANGUN - NO EXCUSES!",
    sound="School.mp3",
    devices=[
        {"id": "lampu meja", "name": "lampu meja", "type": "light", "action": "on", "brightness": 100},
        {"id": "soft box 1", "name": "soft box 1", "type": "light", "action": "on", "brightness": 100},
        {"id": "soft box 2", "name": "soft box 2", "type": "light", "action": "on", "brightness": 100}
    ],
    actions=[
        {"id": "voice", "message": "BANGUN SEKARANG!"},
        # SPAM = INFINITE LOOP setiap 15 detik sampai dismiss!
        {
            "id": "spam",
            "message": "BANGUN SEKARANG! Tidak ada waktu untuk tidur!",
            "channels": ["tts", "telegram", "whatsapp"]  # Will spam all 3 channels
        }
    ]
)
```

> [!IMPORTANT]
> **Active Alarm System akan aktif saat alarm trigger:**
> - Browser auto-open ke `/alarm-active`
> - Volume PC di-set 100%
> - Sound loop terus
> - Spam loop FOREVER (jika ada action spam)
> - Wajib jawab math problem untuk dismiss

### Simple Gentle Alarm
```python
add_alarm(
    time_str="08:00",
    mode="gentle",
    label="Weekend Wake",
    sound="Piano.mp3"
)
```

---

## CLI Commands

All commands run from: `C:\Users\nugra\OneDrive\Documents\Project\Shila-PartnerInCrime\moltbot\skills\shila-wake\scripts`

### Alarm Management
```bash
python wake_system.py alarm add 07:00 --mode normal --label "Wake Up"
python wake_system.py alarm add 06:30 --mode nuclear --repeat daily
python wake_system.py alarm add 08:00 --mode gentle --date 2026-02-02
python wake_system.py alarm list
python wake_system.py alarm delete <alarm_id>
python wake_system.py alarm delete --all
```

### Reminder Management
```bash
python wake_system.py remind "Meeting with client" --at 14:00 --date 2026-02-01
python wake_system.py remind --list
python wake_system.py remind --delete <reminder_id>
```

### Testing Functions
```bash
python wake_system.py test sound        # Test alarm sound playback
python wake_system.py test lights       # Test smart lights
python wake_system.py test tts --text "Hello World"  # Test TTS
python wake_system.py test wake --mode normal        # Test wake sequence
```

### Routine Management
```bash
python wake_system.py routine list          # List all routines
python wake_system.py routine run <id>      # Run routine by ID/name
python wake_system.py routine morning       # Run morning preset
python wake_system.py routine sleep         # Run sleep preset
```

### Analytics
```bash
python wake_system.py analytics score       # Weekly wake score
python wake_system.py analytics streaks     # Current streaks
python wake_system.py analytics summary     # Full summary
```

### Daemon Control
```bash
python wake_system.py start     # Start alarm daemon
python wake_system.py stop      # Stop alarm daemon
python wake_system.py status    # Check daemon status
python wake_system.py check     # Manual alarm check
```

### Activity Log
```bash
python wake_system.py activity --limit 10   # View recent activity
```

---

## Web Dashboard

URL: http://localhost:8765

| Page | Path | Description |
|------|------|-------------|
| Dashboard | `/` | Overview, quick actions, next alarm |
| Alarms | `/alarms` | Manage alarms with device/action picker |
| Routines | `/routines` | Custom routines management |
| Analytics | `/analytics` | Wake stats, streaks, scores |
| Settings | `/settings` | System configuration |

