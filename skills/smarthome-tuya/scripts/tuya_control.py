#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["tinytuya>=1.15.0"]
# ///
"""
Tuya Smart Home Control CLI
Standalone script for controlling Tuya devices via Moltbot.

Usage:
    uv run tuya_control.py <command> [args]
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import tinytuya
except ImportError:
    print("ERROR: tinytuya not installed. Run: pip install tinytuya")
    sys.exit(1)

# ===========================================================================
# Configuration
# ===========================================================================

# Credentials path (relative to Shila-PartnerInCrime project)
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent.parent.parent  # skills/smarthome-tuya/scripts -> moltbot -> Shila-PartnerInCrime
CREDENTIALS_FILE = PROJECT_ROOT / "backend" / "config" / "tuya_credentials.json"
DEVICES_CACHE_FILE = SCRIPT_DIR.parent / "devices_cache.json"
SCENES_FILE = SCRIPT_DIR.parent / "scenes.json"

# Common switch codes (ordered by popularity)
SWITCH_CODES = [
    'switch_led', 'switch_1', 'switch', 'power', 'Power',
    'power_go', 'start', 'basic_power', 'switch_2', 'switch_3', 'switch_4',
]

BRIGHTNESS_CODES = ['bright_value_v2', 'bright_value', 'brightness']
COLOR_CODES = ['colour_data_v2', 'colour_data']
MODE_CODES = ['work_mode', 'mode']

# Color name to Hue mapping
COLOR_MAP = {
    'red': 0, 'merah': 0,
    'orange': 30, 'oranye': 30,
    'yellow': 60, 'kuning': 60,
    'green': 120, 'hijau': 120,
    'cyan': 180, 'biru_muda': 180,
    'blue': 240, 'biru': 240,
    'purple': 270, 'ungu': 270,
    'pink': 330, 'magenta': 300,
    'white': -1, 'putih': -1,
    'warm': -2, 'hangat': -2,
}

# Category mappings
CATEGORY_MAP = {
    'light': ['dj', 'dd', 'fwd', 'xdd'],
    'lights': ['dj', 'dd', 'fwd', 'xdd'],
    'lampu': ['dj', 'dd', 'fwd', 'xdd'],
    'ac': ['infrared_ac', 'kt', 'qt', 'wnykq'],
    'socket': ['cz', 'pc'],
    'plug': ['cz', 'pc'],
    'switch': ['kg'],
}


# ===========================================================================
# TuyaController Class
# ===========================================================================

class TuyaController:
    def __init__(self):
        self.cloud = None
        self.devices: Dict[str, Dict] = {}
        self.credentials = self._load_credentials()
        self._init_cloud()
        self._load_devices_cache()
    
    def _load_credentials(self) -> Dict:
        """Load Tuya API credentials."""
        if CREDENTIALS_FILE.exists():
            try:
                with open(CREDENTIALS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading credentials: {e}")
        return {"access_id": "", "access_secret": "", "region": "us"}
    
    def _init_cloud(self):
        """Initialize Tuya Cloud connection."""
        if not self.credentials.get('access_id') or not self.credentials.get('access_secret'):
            print("WARNING: No Tuya credentials configured")
            return
        
        try:
            self.cloud = tinytuya.Cloud(
                apiRegion=self.credentials.get('region', 'us'),
                apiKey=self.credentials['access_id'],
                apiSecret=self.credentials['access_secret']
            )
            print(f"Cloud connected (region: {self.credentials.get('region', 'us')})")
        except Exception as e:
            print(f"Cloud connection error: {e}")
    
    def _load_devices_cache(self):
        """Load devices from cache."""
        if DEVICES_CACHE_FILE.exists():
            try:
                with open(DEVICES_CACHE_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.devices = {d['id']: d for d in data.get('devices', [])}
                    print(f"Loaded {len(self.devices)} devices from cache")
            except Exception as e:
                print(f"Cache load error: {e}")
    
    def _save_devices_cache(self):
        """Save devices to cache."""
        try:
            DEVICES_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(DEVICES_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump({
                    'devices': list(self.devices.values()),
                    'updated': time.strftime('%Y-%m-%d %H:%M:%S')
                }, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Cache save error: {e}")
    
    # -------------------------------------------------------------------------
    # Device Discovery
    # -------------------------------------------------------------------------
    
    def discover_devices(self) -> List[Dict]:
        """Fetch all devices from Tuya Cloud."""
        if not self.cloud:
            print("ERROR: Cloud not connected")
            return []
        
        try:
            cloud_devices = self.cloud.getdevices(True)
            
            if not cloud_devices:
                print("No devices found")
                return []
            
            if isinstance(cloud_devices, dict):
                if 'result' in cloud_devices:
                    cloud_devices = cloud_devices['result']
                else:
                    cloud_devices = list(cloud_devices.values())
            
            # Scan network for local IPs (with timeout)
            id_to_ip = {}
            try:
                print("Scanning network for local IPs...")
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(tinytuya.deviceScan, False)
                    try:
                        scanned = future.result(timeout=8)
                        for ip, info in scanned.items():
                            dev_id = info.get('gwId', '')
                            if dev_id:
                                id_to_ip[dev_id] = ip
                        print(f"Found {len(id_to_ip)} local device IPs")
                    except concurrent.futures.TimeoutError:
                        print("Network scan timed out")
            except Exception:
                pass
            
            # Process each device
            processed = []
            for device in cloud_devices:
                device_id = device.get('id')
                if not device_id:
                    continue
                
                # Get capabilities
                capabilities = self._fetch_capabilities(device_id)
                
                device_info = {
                    'id': device_id,
                    'name': device.get('name', 'Unknown'),
                    'category': device.get('category', 'other'),
                    'product_name': device.get('product_name', ''),
                    'local_key': device.get('key', ''),
                    'online': device.get('online', True),
                    'ip': id_to_ip.get(device_id, device.get('ip', '')),
                    'capabilities': capabilities,
                    'switch_code': self._detect_switch_code(capabilities),
                    'supports_brightness': self._has_capability(capabilities, BRIGHTNESS_CODES),
                    'supports_color': self._has_capability(capabilities, COLOR_CODES),
                }
                
                self.devices[device_id] = device_info
                processed.append(device_info)
            
            self._save_devices_cache()
            print(f"Discovered {len(processed)} devices")
            return processed
            
        except Exception as e:
            print(f"Discovery error: {e}")
            return []
    
    def _fetch_capabilities(self, device_id: str) -> List[Dict]:
        """Fetch device capabilities from Tuya Cloud."""
        if not self.cloud:
            return []
        
        try:
            result = self.cloud.getproperties(device_id)
            
            if result and 'result' in result:
                props = result['result']
                capabilities = []
                
                if 'status' in props and isinstance(props['status'], list):
                    for item in props['status']:
                        capabilities.append({
                            'code': item.get('code'),
                            'type': item.get('type'),
                            'values': item.get('values', '{}'),
                            'mode': 'ro'
                        })
                
                if 'functions' in props and isinstance(props['functions'], list):
                    for item in props['functions']:
                        code = item.get('code')
                        existing = next((c for c in capabilities if c['code'] == code), None)
                        if existing:
                            existing['mode'] = 'rw'
                        else:
                            capabilities.append({
                                'code': code,
                                'type': item.get('type'),
                                'values': item.get('values', '{}'),
                                'mode': 'rw'
                            })
                
                return capabilities
            return []
        except Exception as e:
            return []
    
    def _detect_switch_code(self, capabilities: List[Dict]) -> Optional[str]:
        """Detect switch code for a device."""
        cap_codes = [c.get('code') for c in capabilities]
        for code in SWITCH_CODES:
            if code in cap_codes:
                return code
        return None
    
    def _has_capability(self, capabilities: List[Dict], codes: List[str]) -> bool:
        """Check if device has any of the specified capabilities."""
        cap_codes = [c.get('code') for c in capabilities]
        return any(code in cap_codes for code in codes)
    
    def _get_capability_code(self, capabilities: List[Dict], codes: List[str]) -> Optional[str]:
        """Get first matching capability code."""
        cap_codes = [c.get('code') for c in capabilities]
        for code in codes:
            if code in cap_codes:
                return code
        return None
    
    # -------------------------------------------------------------------------
    # Device Lookup
    # -------------------------------------------------------------------------
    
    def get_device(self, target: str) -> Optional[Dict]:
        """Find device by ID, name, or partial name."""
        if not target:
            return None
        
        target_lower = target.lower()
        
        # Exact ID match
        if target in self.devices:
            return self.devices[target]
        
        # Name match (case-insensitive)
        for device in self.devices.values():
            if device.get('name', '').lower() == target_lower:
                return device
        
        # Partial name match
        for device in self.devices.values():
            if target_lower in device.get('name', '').lower():
                return device
        
        return None
    
    def list_devices(self) -> List[Dict]:
        """List all devices."""
        return list(self.devices.values())
    
    # -------------------------------------------------------------------------
    # Command Sending
    # -------------------------------------------------------------------------
    
    def _send_command(self, device_id: str, code: str, value: Any) -> Dict:
        """Send command to device via Cloud API."""
        if not self.cloud:
            return {'success': False, 'error': 'Cloud not connected'}
        
        try:
            commands = {"commands": [{"code": code, "value": value}]}
            result = self.cloud.sendcommand(device_id, commands)
            
            if result and (result.get('success') or result.get('result')):
                return {'success': True, 'result': result}
            return {'success': False, 'error': result.get('msg', 'Unknown error')}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _try_command_variations(self, device_id: str, device_name: str,
                                 primary_code: str, target_val: Any,
                                 variations: List[tuple]) -> Dict:
        """Try multiple command variations until one works."""
        # Try primary
        result = self._send_command(device_id, primary_code, target_val)
        if result.get('success'):
            return result
        
        # Try variations
        for code, val in variations:
            if code == primary_code and val == target_val:
                continue
            
            time.sleep(0.3)
            res = self._send_command(device_id, code, val)
            if res.get('success'):
                # Update switch code
                if device_id in self.devices:
                    self.devices[device_id]['switch_code'] = code
                return res
        
        return {'success': False, 'error': f'All command variations failed for {device_name}'}
    
    # -------------------------------------------------------------------------
    # Basic Control
    # -------------------------------------------------------------------------
    
    def turn_on(self, target: str) -> Dict:
        """Turn on a device."""
        device = self.get_device(target)
        if not device:
            return {'success': False, 'error': f'Device not found: {target}'}
        
        device_id = device['id']
        device_name = device['name']
        category = device.get('category', '')
        
        # IR AC handling
        if category in ['infrared_ac', 'wnykq']:
            result = self._send_ac_ir_command(device_id, power=1)
            if result.get('success'):
                print(f"âœ“ ON: {device_name} (IR API)")
                return {'success': True, 'device': device_name, 'action': 'turn_on'}
        
        # Standard devices
        switch_code = device.get('switch_code', 'switch_led')
        variations = [
            (switch_code, True),
            (switch_code, 'true'),
            (switch_code, 1),
            ('switch_1', True),
            ('switch', True),
        ]
        
        result = self._try_command_variations(device_id, device_name, switch_code, True, variations)
        if result.get('success'):
            print(f"âœ“ ON: {device_name}")
        return result
    
    def turn_off(self, target: str) -> Dict:
        """Turn off a device."""
        device = self.get_device(target)
        if not device:
            return {'success': False, 'error': f'Device not found: {target}'}
        
        device_id = device['id']
        device_name = device['name']
        category = device.get('category', '')
        
        # IR AC handling
        if category in ['infrared_ac', 'wnykq']:
            result = self._send_ac_ir_command(device_id, power=0)
            if result.get('success'):
                print(f"âœ“ OFF: {device_name} (IR API)")
                return {'success': True, 'device': device_name, 'action': 'turn_off'}
        
        # Standard devices
        switch_code = device.get('switch_code', 'switch_led')
        variations = [
            (switch_code, False),
            (switch_code, 'false'),
            (switch_code, 0),
            ('switch_1', False),
            ('switch', False),
        ]
        
        result = self._try_command_variations(device_id, device_name, switch_code, False, variations)
        if result.get('success'):
            print(f"âœ“ OFF: {device_name}")
        return result
    
    # -------------------------------------------------------------------------
    # Light Control
    # -------------------------------------------------------------------------
    
    def set_brightness(self, target: str, brightness: int) -> Dict:
        """Set device brightness (0-100)."""
        device = self.get_device(target)
        if not device:
            return {'success': False, 'error': f'Device not found: {target}'}
        
        if not device.get('supports_brightness'):
            return {'success': False, 'error': f'{device["name"]} does not support brightness'}
        
        capabilities = device.get('capabilities', [])
        bright_code = self._get_capability_code(capabilities, BRIGHTNESS_CODES)
        
        if not bright_code:
            return {'success': False, 'error': 'Brightness capability not found'}
        
        # Scale to device range (usually 10-1000 or 25-255)
        is_v2 = 'v2' in bright_code
        max_val = 1000 if is_v2 else 255
        min_val = 10 if is_v2 else 25
        scaled = int(min_val + (brightness / 100) * (max_val - min_val))
        
        result = self._send_command(device['id'], bright_code, scaled)
        if result.get('success'):
            print(f"âœ“ BRIGHTNESS: {device['name']} -> {brightness}%")
        return result
    
    def set_color(self, target: str, color: str) -> Dict:
        """Set device color."""
        device = self.get_device(target)
        if not device:
            return {'success': False, 'error': f'Device not found: {target}'}
        
        if not device.get('supports_color'):
            return {'success': False, 'error': f'{device["name"]} does not support color'}
        
        capabilities = device.get('capabilities', [])
        
        # Check for v2 or v1 color code
        is_v2 = self._has_capability(capabilities, ['colour_data_v2'])
        color_code = 'colour_data_v2' if is_v2 else 'colour_data'
        mode_code = self._get_capability_code(capabilities, MODE_CODES)
        
        hue = COLOR_MAP.get(color.lower(), -1)
        
        # White mode
        if hue == -1:
            if mode_code:
                self._send_command(device['id'], mode_code, 'white')
            print(f"âœ“ COLOR: {device['name']} -> white")
            return {'success': True, 'device': device['name'], 'color': 'white'}
        
        # Warm white
        if hue == -2:
            if mode_code:
                self._send_command(device['id'], mode_code, 'white')
            # Set warm temperature
            temp_code = self._get_capability_code(capabilities, ['temp_value_v2', 'temp_value'])
            if temp_code:
                self._send_command(device['id'], temp_code, 500)  # Warm
            print(f"âœ“ COLOR: {device['name']} -> warm white")
            return {'success': True, 'device': device['name'], 'color': 'warm'}
        
        # Set colour mode first
        if mode_code:
            self._send_command(device['id'], mode_code, 'colour')
            time.sleep(0.2)
        
        # Use correct scale
        s_max = 1000 if is_v2 else 255
        v_max = 1000 if is_v2 else 255
        hsv_data = {'h': hue, 's': s_max, 'v': v_max}
        
        result = self._send_command(device['id'], color_code, hsv_data)
        
        # Retry with JSON string if dict fails
        if not result.get('success'):
            result = self._send_command(device['id'], color_code, json.dumps(hsv_data))
        
        if result.get('success'):
            print(f"âœ“ COLOR: {device['name']} -> {color}")
        return result
    
    # -------------------------------------------------------------------------
    # AC Control (IR-based)
    # -------------------------------------------------------------------------
    
    _ac_state: Dict[str, Dict] = {}
    
    def _get_ir_blaster_id(self) -> Optional[str]:
        """Get IR blaster device ID."""
        for device in self.devices.values():
            if device.get('category') == 'wnykq':
                return device.get('id')
        return None
    
    def _send_ac_ir_command(self, ac_device_id: str, power: int, temp: int = 24,
                            mode: int = 0, wind: int = 0) -> Dict:
        """Send AC command via IR API."""
        ir_blaster_id = self._get_ir_blaster_id()
        if not ir_blaster_id:
            return {'success': False, 'error': 'IR blaster not found'}
        
        url = f"/v2.0/infrareds/{ir_blaster_id}/air-conditioners/{ac_device_id}/scenes/command"
        body = {
            "power": str(power),
            "temp": str(temp),
            "mode": str(mode),
            "wind": str(wind)
        }
        
        try:
            result = self.cloud.cloudrequest(url, action="POST", post=body)
            if result.get('success') and result.get('result'):
                return {'success': True}
            return {'success': False, 'error': result.get('msg', 'IR command failed')}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _get_ac_state(self, device_id: str) -> Dict:
        """Get current AC state."""
        if device_id not in self._ac_state:
            self._ac_state[device_id] = {'power': 0, 'temp': 24, 'mode': 0, 'wind': 0}
        return self._ac_state[device_id]
    
    def control_ac(self, target: str, power: bool = None, temperature: int = None,
                   mode: str = None, fan: str = None) -> Dict:
        """Full AC control."""
        device = self.get_device(target)
        if not device:
            return {'success': False, 'error': f'Device not found: {target}'}
        
        if device.get('category') not in ['infrared_ac', 'kt', 'qt', 'wnykq']:
            return {'success': False, 'error': f'{device["name"]} is not an AC'}
        
        state = self._get_ac_state(device['id'])
        
        if power is not None:
            state['power'] = 1 if power else 0
        if temperature is not None:
            state['temp'] = max(16, min(30, temperature))
        if mode is not None:
            mode_map = {'cool': 0, 'dingin': 0, 'heat': 1, 'panas': 1, 
                        'auto': 2, 'fan': 3, 'kipas': 3, 'dry': 4, 'kering': 4}
            state['mode'] = mode_map.get(mode.lower(), 0)
        if fan is not None:
            fan_map = {'auto': 0, 'low': 1, 'rendah': 1, 'medium': 2, 'sedang': 2, 
                       'high': 3, 'tinggi': 3}
            state['wind'] = fan_map.get(fan.lower(), 0)
        
        result = self._send_ac_ir_command(
            device['id'],
            power=state['power'],
            temp=state['temp'],
            mode=state['mode'],
            wind=state['wind']
        )
        
        if result.get('success'):
            status = "ON" if state['power'] else "OFF"
            print(f"âœ“ AC: {device['name']} -> {status}, {state['temp']}Â°C")
        return result
    
    # -------------------------------------------------------------------------
    # Group Control
    # -------------------------------------------------------------------------
    
    def control_all(self, action: str) -> Dict:
        """Control all devices."""
        results = []
        failed = []
        
        for device in self.devices.values():
            if not device.get('switch_code'):
                continue
            
            try:
                time.sleep(0.1)
                if action == 'on':
                    result = self.turn_on(device['name'])
                else:
                    result = self.turn_off(device['name'])
                
                if result.get('success'):
                    results.append(device['name'])
                else:
                    failed.append(device['name'])
            except Exception:
                failed.append(device['name'])
        
        print(f"Group control: {len(results)} success, {len(failed)} failed")
        return {'success': len(results) > 0, 'affected': results, 'failed': failed}
    
    def control_by_category(self, category: str, action: str) -> Dict:
        """Control devices by category."""
        target_categories = CATEGORY_MAP.get(category.lower(), [category.lower()])
        
        results = []
        failed = []
        
        for device in self.devices.values():
            if device.get('category', '').lower() not in target_categories:
                continue
            if not device.get('switch_code'):
                continue
            
            try:
                time.sleep(0.1)
                if action == 'on':
                    result = self.turn_on(device['name'])
                else:
                    result = self.turn_off(device['name'])
                
                if result.get('success'):
                    results.append(device['name'])
                else:
                    failed.append(device['name'])
            except Exception:
                failed.append(device['name'])
        
        print(f"Category '{category}' control: {len(results)} success")
        return {'success': len(results) > 0, 'affected': results, 'failed': failed}
    
    def set_all_brightness(self, brightness: int) -> Dict:
        """Set brightness on all capable devices."""
        results = []
        for device in self.devices.values():
            if device.get('supports_brightness'):
                r = self.set_brightness(device['name'], brightness)
                if r.get('success'):
                    results.append(device['name'])
        return {'success': len(results) > 0, 'affected': results}
    
    def set_all_color(self, color: str) -> Dict:
        """Set color on all capable devices."""
        results = []
        for device in self.devices.values():
            if device.get('supports_color'):
                r = self.set_color(device['name'], color)
                if r.get('success'):
                    results.append(device['name'])
        return {'success': len(results) > 0, 'affected': results}
    
    # -------------------------------------------------------------------------
    # Scenes
    # -------------------------------------------------------------------------
    
    def _load_scenes(self) -> Dict:
        """Load scenes from file."""
        if SCENES_FILE.exists():
            try:
                with open(SCENES_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return {}
    
    def _save_scenes(self, scenes: Dict):
        """Save scenes to file."""
        try:
            with open(SCENES_FILE, 'w', encoding='utf-8') as f:
                json.dump(scenes, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving scenes: {e}")
    
    def capture_scene(self, scene_name: str) -> Dict:
        """Capture current state of all devices as a scene."""
        if not self.cloud:
            return {'success': False, 'error': 'Cloud not connected'}
        
        captured = []
        
        for device_id, device in self.devices.items():
            try:
                # Get current status
                result = self.cloud.getstatus(device_id)
                if not result or 'result' not in result:
                    continue
                
                state = {}
                for item in result['result']:
                    state[item.get('code', '')] = item.get('value')
                
                switch_code = device.get('switch_code', 'switch_led')
                is_on = state.get(switch_code, state.get('switch', False))
                
                action_data = {
                    'device': device['name'],
                    'device_id': device_id,
                    'action': 'on' if is_on else 'off',
                    'params': {}
                }
                
                # Capture brightness (convert raw value to 0-100 percentage)
                for code in BRIGHTNESS_CODES:
                    if code in state:
                        raw_val = state[code]
                        # Convert raw to percentage based on code version
                        if 'v2' in code:
                            # v2: 10-1000 range
                            pct = int((raw_val - 10) / (1000 - 10) * 100)
                        else:
                            # v1: 25-255 range
                            pct = int((raw_val - 25) / (255 - 25) * 100)
                        action_data['params']['brightness'] = max(0, min(100, pct))
                        break
                
                # Capture color
                for code in COLOR_CODES:
                    if code in state:
                        action_data['params']['color_data'] = state[code]
                        break
                
                captured.append(action_data)
                
            except Exception as e:
                continue
        
        if not captured:
            return {'success': False, 'error': 'No devices captured'}
        
        # Save scene
        scenes = self._load_scenes()
        scenes[scene_name] = {
            'name': scene_name,
            'actions': captured,
            'created': time.strftime('%Y-%m-%d %H:%M:%S')
        }
        self._save_scenes(scenes)
        
        print(f"âœ“ Scene '{scene_name}' captured with {len(captured)} devices")
        return {'success': True, 'scene': scene_name, 'devices': len(captured)}
    
    def activate_scene(self, scene_name: str) -> Dict:
        """Activate a saved scene."""
        scenes = self._load_scenes()
        
        # Find scene (case-insensitive)
        scene = None
        for name, data in scenes.items():
            if name.lower() == scene_name.lower():
                scene = data
                break
        
        if not scene:
            return {'success': False, 'error': f'Scene not found: {scene_name}'}
        
        results = []
        failed = []
        
        for action_item in scene.get('actions', []):
            device = action_item.get('device')
            action = action_item.get('action')
            params = action_item.get('params', {})
            
            try:
                if action == 'on':
                    result = self.turn_on(device)
                else:
                    result = self.turn_off(device)
                
                if result.get('success'):
                    results.append(device)
                    
                    # Apply additional params
                    if 'brightness' in params:
                        self.set_brightness(device, params['brightness'])
                else:
                    failed.append(device)
            except Exception:
                failed.append(device)
        
        print(f"âœ“ Scene '{scene_name}' activated: {len(results)} devices")
        return {'success': len(results) > 0, 'affected': results, 'failed': failed}
    
    def list_scenes(self) -> List[Dict]:
        """List all scenes."""
        scenes = self._load_scenes()
        return [
            {
                'name': data.get('name', name),
                'devices': len(data.get('actions', [])),
                'created': data.get('created', 'unknown')
            }
            for name, data in scenes.items()
        ]
    
    def delete_scene(self, scene_name: str) -> Dict:
        """Delete a scene."""
        scenes = self._load_scenes()
        
        to_delete = None
        for name in scenes:
            if name.lower() == scene_name.lower():
                to_delete = name
                break
        
        if to_delete:
            del scenes[to_delete]
            self._save_scenes(scenes)
            print(f"âœ“ Scene '{scene_name}' deleted")
            return {'success': True}
        
        return {'success': False, 'error': f'Scene not found: {scene_name}'}
    
    # -------------------------------------------------------------------------
    # Status
    # -------------------------------------------------------------------------
    
    def get_device_status(self, target: str) -> Dict:
        """Get device status."""
        device = self.get_device(target)
        if not device:
            return {'success': False, 'error': f'Device not found: {target}'}
        
        if not self.cloud:
            return {'success': False, 'error': 'Cloud not connected'}
        
        try:
            result = self.cloud.getstatus(device['id'])
            if result and 'result' in result:
                status = {}
                for item in result['result']:
                    status[item.get('code', '')] = item.get('value')
                
                return {
                    'success': True,
                    'device': device['name'],
                    'online': device.get('online', True),
                    'status': status
                }
            return {'success': False, 'error': 'Could not get status'}
        except Exception as e:
            return {'success': False, 'error': str(e)}


# ===========================================================================
# CLI Entry Point
# ===========================================================================

def main():
    parser = argparse.ArgumentParser(description='Tuya Smart Home Control')
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # list
    subparsers.add_parser('list', help='List all devices')
    
    # discover
    subparsers.add_parser('discover', help='Discover devices from cloud')
    
    # on
    on_parser = subparsers.add_parser('on', help='Turn on device')
    on_parser.add_argument('device', nargs='?', help='Device name')
    on_parser.add_argument('--all', action='store_true', help='All devices')
    
    # off
    off_parser = subparsers.add_parser('off', help='Turn off device')
    off_parser.add_argument('device', nargs='?', help='Device name')
    off_parser.add_argument('--all', action='store_true', help='All devices')
    
    # brightness
    bright_parser = subparsers.add_parser('brightness', help='Set brightness')
    bright_parser.add_argument('device', nargs='?', help='Device name')
    bright_parser.add_argument('level', type=int, nargs='?', help='Brightness 0-100')
    bright_parser.add_argument('--all', action='store_true', help='All devices')
    
    # color
    color_parser = subparsers.add_parser('color', help='Set color')
    color_parser.add_argument('device', nargs='?', help='Device name')
    color_parser.add_argument('color', nargs='?', help='Color name')
    color_parser.add_argument('--all', action='store_true', help='All devices')
    
    # ac
    ac_parser = subparsers.add_parser('ac', help='Control AC')
    ac_parser.add_argument('device', help='AC device name')
    ac_parser.add_argument('--power', choices=['on', 'off'], help='Power on/off')
    ac_parser.add_argument('--temp', type=int, help='Temperature 16-30')
    ac_parser.add_argument('--mode', help='Mode: cool/heat/auto/fan/dry')
    ac_parser.add_argument('--fan', help='Fan: auto/low/medium/high')
    
    # category
    cat_parser = subparsers.add_parser('category', help='Control by category')
    cat_parser.add_argument('category', help='Category: lights/ac/socket')
    cat_parser.add_argument('action', choices=['on', 'off'], help='Action')
    
    # scene
    scene_parser = subparsers.add_parser('scene', help='Scene management')
    scene_parser.add_argument('action', choices=['capture', 'activate', 'list', 'delete'])
    scene_parser.add_argument('name', nargs='?', help='Scene name')
    
    # timer
    timer_parser = subparsers.add_parser('timer', help='Set timer')
    timer_parser.add_argument('device', help='Device name')
    timer_parser.add_argument('minutes', type=int, help='Minutes')
    timer_parser.add_argument('action', choices=['on', 'off'], help='Action when timer ends')
    
    # status
    status_parser = subparsers.add_parser('status', help='Get device status')
    status_parser.add_argument('device', nargs='?', help='Device name')
    status_parser.add_argument('--all', action='store_true', help='All devices')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Initialize controller
    controller = TuyaController()
    
    # Execute command
    if args.command == 'list':
        devices = controller.list_devices()
        if not devices:
            print("No devices found. Run 'discover' first.")
            return
        
        print(f"\n{'Name':<30} {'Category':<15} {'Online':<8} {'Color':<6} {'Bright':<6}")
        print("-" * 75)
        for d in devices:
            print(f"{d['name']:<30} {d['category']:<15} {'Yes' if d.get('online') else 'No':<8} "
                  f"{'Yes' if d.get('supports_color') else '':<6} "
                  f"{'Yes' if d.get('supports_brightness') else '':<6}")
    
    elif args.command == 'discover':
        controller.discover_devices()
    
    elif args.command == 'on':
        if args.all:
            controller.control_all('on')
        elif args.device:
            controller.turn_on(args.device)
        else:
            print("Specify device name or use --all")
    
    elif args.command == 'off':
        if args.all:
            controller.control_all('off')
        elif args.device:
            controller.turn_off(args.device)
        else:
            print("Specify device name or use --all")
    
    elif args.command == 'brightness':
        if args.all and args.device:
            # device is actually the brightness level in this case
            try:
                level = int(args.device)
                controller.set_all_brightness(level)
            except ValueError:
                print("Usage: brightness --all <level>")
        elif args.device and args.level:
            controller.set_brightness(args.device, args.level)
        else:
            print("Usage: brightness <device> <level> or brightness --all <level>")
    
    elif args.command == 'color':
        if args.all and args.device:
            # device is actually the color in this case
            controller.set_all_color(args.device)
        elif args.device and args.color:
            controller.set_color(args.device, args.color)
        else:
            print("Usage: color <device> <color> or color --all <color>")
    
    elif args.command == 'ac':
        controller.control_ac(
            args.device,
            power=(args.power == 'on') if args.power else None,
            temperature=args.temp,
            mode=args.mode,
            fan=args.fan
        )
    
    elif args.command == 'category':
        controller.control_by_category(args.category, args.action)
    
    elif args.command == 'scene':
        if args.action == 'list':
            scenes = controller.list_scenes()
            if not scenes:
                print("No scenes found.")
                return
            
            print(f"\n{'Name':<20} {'Devices':<10} {'Created':<20}")
            print("-" * 50)
            for s in scenes:
                print(f"{s['name']:<20} {s['devices']:<10} {s['created']:<20}")
        
        elif args.action == 'capture':
            if not args.name:
                print("Specify scene name")
                return
            controller.capture_scene(args.name)
        
        elif args.action == 'activate':
            if not args.name:
                print("Specify scene name")
                return
            controller.activate_scene(args.name)
        
        elif args.action == 'delete':
            if not args.name:
                print("Specify scene name")
                return
            controller.delete_scene(args.name)
    
    elif args.command == 'timer':
        print(f"Timer set: {args.device} will turn {args.action} in {args.minutes} minutes")
        print("Note: Timer runs in background. Keep script running or use system scheduler.")
        
        import threading
        def delayed_action():
            time.sleep(args.minutes * 60)
            if args.action == 'on':
                controller.turn_on(args.device)
            else:
                controller.turn_off(args.device)
        
        t = threading.Thread(target=delayed_action, daemon=False)
        t.start()
        t.join()
    
    elif args.command == 'status':
        if args.all:
            for device in controller.list_devices():
                result = controller.get_device_status(device['name'])
                if result.get('success'):
                    print(f"\n{result['device']}:")
                    for k, v in result.get('status', {}).items():
                        print(f"  {k}: {v}")
        elif args.device:
            result = controller.get_device_status(args.device)
            if result.get('success'):
                print(f"\n{result['device']} ({'online' if result['online'] else 'offline'}):")
                for k, v in result.get('status', {}).items():
                    print(f"  {k}: {v}")
            else:
                print(result.get('error'))
        else:
            print("Specify device name or use --all")


if __name__ == '__main__':
    main()
