---
name: smarthome-tuya
description: |
  Control Tuya-based smart home devices (lights, AC, sockets, switches).
  Use when user asks to: turn on/off lights, control AC temperature/mode, 
  set light color/brightness, control all devices, manage scenes, set timers.
  Keywords: lampu, AC, nyalakan, matikan, terang, redup, warna, suhu, dingin, panas.
---

# Smart Home Tuya Control

Control all Tuya-based smart home devices using the `tuya_control.py` script.

## Prerequisites

- **Credentials**: Tuya API credentials stored at `C:\Users\nugra\OneDrive\Documents\Project\Shila-PartnerInCrime\backend\config\tuya_credentials.json`
- **Dependency**: `tinytuya` (install with `pip install tinytuya`)

## Quick Reference

### Script Location
```
C:\Users\nugra\OneDrive\Documents\Project\Shila-PartnerInCrime\moltbot\skills\smarthome-tuya\scripts\tuya_control.py
```

### Run with uv (recommended)
```powershell
uv run tuya_control.py <command> [args]
```

## Commands

### Device Discovery
```powershell
# List all devices
uv run tuya_control.py list

# Refresh devices from cloud
uv run tuya_control.py discover
```

### Basic Control
```powershell
# Turn on device
uv run tuya_control.py on "Lampu Meja"

# Turn off device  
uv run tuya_control.py off "Lampu Meja"

# Turn off ALL devices
uv run tuya_control.py off --all
```

### Light Control
```powershell
# Set brightness (0-100)
uv run tuya_control.py brightness "Lampu Meja" 80

# Set color (red, green, blue, yellow, purple, white, etc.)
uv run tuya_control.py color "Lampu Meja" blue

# Set all lights to same color
uv run tuya_control.py color --all warm
```

### AC Control (IR-based)
```powershell
# Turn on AC with temperature
uv run tuya_control.py ac "AC Kamar" --power on --temp 24

# Set AC mode (cool/heat/auto/fan/dry)
uv run tuya_control.py ac "AC Kamar" --mode cool --temp 22

# Set fan speed (auto/low/medium/high)
uv run tuya_control.py ac "AC Kamar" --fan high

# Full AC control
uv run tuya_control.py ac "AC Kamar" --power on --temp 24 --mode cool --fan auto
```

### Group Control
```powershell
# Control by category
uv run tuya_control.py category lights on
uv run tuya_control.py category lights off

# Set all lights brightness
uv run tuya_control.py brightness --all 50
```

### Scenes
```powershell
# Capture current state as scene
uv run tuya_control.py scene capture "kerja"

# Activate a scene
uv run tuya_control.py scene activate "tidur"

# List all scenes
uv run tuya_control.py scene list

# Delete a scene
uv run tuya_control.py scene delete "old_scene"
```

### Timers
```powershell
# Set timer to turn off in X minutes
uv run tuya_control.py timer "Lampu Meja" 30 off

# Set timer to turn on
uv run tuya_control.py timer "AC Kamar" 60 on
```

### Status
```powershell
# Get device status
uv run tuya_control.py status "Lampu Meja"

# Get all devices status
uv run tuya_control.py status --all
```

## Common Use Cases

### "Matikan semua lampu"
```powershell
uv run tuya_control.py category lights off
```

### "Nyalakan AC 24 derajat mode dingin"
```powershell
uv run tuya_control.py ac "AC Kamar" --power on --temp 24 --mode cool
```

### "Lampu meja warna biru terang 80%"
```powershell
uv run tuya_control.py on "Lampu Meja"
uv run tuya_control.py color "Lampu Meja" blue
uv run tuya_control.py brightness "Lampu Meja" 80
```

### "Simpan kondisi saat ini sebagai scene kerja"
```powershell
uv run tuya_control.py scene capture "kerja"
```

### "Aktifkan scene tidur"
```powershell
uv run tuya_control.py scene activate "tidur"
```

## Device Categories

- `lights` / `lampu` - Light bulbs (dj, dd categories)
- `ac` - Air conditioners (infrared_ac, kt categories)
- `socket` / `plug` - Smart plugs (cz, pc categories)
- `switch` - Wall switches (kg category)

## Color Names (Indonesian & English)

| English | Indonesian | Hue |
|---------|------------|-----|
| red | merah | 0 |
| orange | oranye | 30 |
| yellow | kuning | 60 |
| green | hijau | 120 |
| cyan | biru_muda | 180 |
| blue | biru | 240 |
| purple | ungu | 270 |
| pink | pink | 330 |
| white | putih | (white mode) |
| warm | hangat | (warm white) |

## Troubleshooting

### "Cloud not connected"
Check credentials at `backend/config/tuya_credentials.json`:
```json
{
  "access_id": "your_access_id",
  "access_secret": "your_access_secret", 
  "region": "us"
}
```

### "Device not found"
Run `uv run tuya_control.py discover` to refresh device list.

### AC not responding
AC uses IR blaster - ensure IR blaster device is online and paired.
