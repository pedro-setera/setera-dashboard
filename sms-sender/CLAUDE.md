# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

The `sms-sender` tool is a Python-based GUI application for automating SMS configuration commands to GPS camera devices. It's part of the larger SETERA tools suite for STR1010/STR1010Plus/STR2020 tracker development.

### Purpose
Send configuration SMS commands (e.g., APN settings) to multiple GPS cameras sequentially via Arduino Uno R4 + SIM800C GSM module.

**✨ v2.0 Feature: SETERA API Integration**
- Authenticates with SETERA tracking platform API on startup
- Fetches STR-CAM devices from production database
- Provides searchable dropdown for secure device selection
- Auto-fills SIM card numbers to prevent configuration errors

### System Architecture

```
┌─────────────────────┐       USB Serial        ┌──────────────────┐
│   Python GUI App    │◄────────(9600)──────────►│  Arduino Uno R4  │
│  (sms_automation_   │                          │  (serial_bridge  │
│     gui.pyw)        │                          │      .ino)       │
└─────────────────────┘                          └──────────────────┘
                                                          │
                                                  Hardware Serial1
                                                    (Pins 0 & 1)
                                                   (auto-detect baud)
                                                          │
                                                          ▼
                                                  ┌──────────────┐
                                                  │   SIM800C    │
                                                  │  GSM Shield  │
                                                  └──────────────┘
```

**Component Roles:**
- **Python GUI**: User interface, automation logic, state management, logging
- **Arduino Uno R4**: Transparent serial bridge (passthrough only, no processing)
- **SIM800C Shield**: GSM modem for SMS transmission/reception

## Architecture

### Technology Stack
- **GUI Framework**: ttkbootstrap (modern themed tkinter)
- **Serial Communication**: pyserial
- **Threading Model**: Worker thread pattern with queue-based communication
- **State Management**: Enum-based status tracking (pending → sending → waiting → success/failed)

### Core Components

#### 1. SMSAutomationApp (Main GUI)
- Main application window managing the entire workflow
- Handles camera list management (add/edit/remove/import)
- Controls automation flow (start/pause/stop)
- Progress tracking and logging

#### 2. SerialWorker (Background Thread)
- Daemon thread for non-blocking serial communication
- Command queue-based architecture using `message_queue`
- Sends AT commands to SIM800C module
- Handles SMS transmission and response checking
- Communicates results back via `log_queue`

#### 3. CameraDialog
- Modal dialog for adding/editing camera entries
- Validates camera name and phone number input
- **v2.0**: Integrates with SeteraAPIManager for secure device selection

#### 4. SeteraAPIManager (API Integration Module)
- Handles OAuth2 authentication with SETERA API
- Fetches and filters STR-CAM terminals from production database
- Provides caching mechanism for terminal data
- Thread-safe operations for background authentication

### Communication Flow

```
┌─────────────────────────────────────────────────────────────┐
│                     Python Application                       │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Main Thread                    Worker Thread                │
│      |                               |                       │
│      |-- Command Queue Put --------->|                       │
│      |   (SEND_SMS/CHECK_SMS)        |                       │
│      |                               |                       │
│      |                               |-- AT Command ─────────┼──► USB Serial (COM port)
│      |                               |   (e.g., "AT+CMGS...") │         │
│      |                               |                       │         ▼
│      |                               |                       │   ┌──────────┐
│      |                               |                       │   │ Arduino  │
│      |                               |◄── Response ──────────┼───┤  Bridge  │
│      |◄─────── Log Queue ◄───────────|   (e.g., "+CMGS:")   │   │ (R4 + HW │
│      |◄───── Message Queue ◄─────────|                       │   │ Serial1) │
│      |   (SMS_RESULT/SMS_RECEIVED)   |                       │   └──────────┘
│      |                               |                       │         │
│      |-- Process Result ------------>|                       │         ▼
│                                                              │   ┌──────────┐
└──────────────────────────────────────────────────────────────┘   │ SIM800C  │
                                                                   │  Modem   │
                                                                   └──────────┘
```

**Data Flow:**
1. Python sends AT command as string (e.g., `AT+CMGS="+5511999999999"\r\n`)
2. Arduino forwards byte-by-byte to SIM800C via Hardware Serial1
3. SIM800C processes AT command and responds
4. Arduino forwards response back to Python via USB Serial
5. Python worker thread parses response and updates GUI

### Data Structures

**Camera Object:**
```python
{
    'name': str,          # Camera identifier
    'phone': str,         # Phone number (format: +5512345678)
    'status': str,        # CameraStatus enum value
    'result': str         # Human-readable result message
}
```

**Message Queue Commands:**
- `{'type': 'AT_COMMAND', 'command': str, 'wait_time': int}`
- `{'type': 'VALIDATE_CONNECTION'}` - Validate connection after opening port
- `{'type': 'GET_MODULE_INFO'}` - Get MSISDN and CSQ from module
- `{'type': 'TEST_MODULE'}` - Run diagnostic tests
- `{'type': 'SEND_SMS', 'number': str, 'message': str, 'camera_id': int}`
- `{'type': 'CHECK_SMS', 'camera_id': int}`
- `{'type': 'STOP'}` - Terminate worker thread

**Message Queue Responses:**
- `{'type': 'SMS_RESULT', 'camera_id': int, 'success': bool}`
- `{'type': 'SMS_RECEIVED', 'camera_id': int, 'message': str}`
- `{'type': 'MODULE_INFO', 'msisdn': str, 'csq': int}` - Module information

### SETERA API Integration (v2.0)

**API Endpoints:**
- OAuth: `https://api-manager.hgdigital.io/oauth2/token`
- Terminals: `https://api.hgdigital.io/setera-core/v1/v2/terminals/find-terminal`

**Authentication Flow:**
1. Application startup triggers background authentication thread
2. OAuth2 client credentials flow with hardcoded credentials
3. Bearer token obtained and cached for session
4. Terminal list fetched and filtered for STR-CAM devices

**Terminal Data Structure:**
```python
{
    'id': 17635,                    # Terminal ID in database
    'plate': 'CARGA-1823',          # Vehicle plate (user-visible)
    'sim': '16999281300',           # SIM card number (auto-filled)
    'imei': '865413057420555',      # Device IMEI
    'model': 'STR-CAM',             # Device model (filtered)
    'company': 'TAMBASA CARGA'      # Company/division name
}
```

**Security Benefits:**
- ✅ Prevents typos in plate names (dropdown selection only)
- ✅ Prevents wrong SIM numbers (API-sourced, read-only)
- ✅ Ensures only STR-CAM devices are configured
- ✅ Validates against production database in real-time
- ✅ Reduces human error to zero for device identification

**Fallback Mode:**
If API is unavailable (network error, timeout), the dialog automatically switches to manual entry mode with a warning indicator.

## Running the Application

### Hardware Setup

**IMPORTANTE - Shield Keyestudio SIM800C (Ks0254):**

1. **Arduino Uno R4 WiFi** with **SIM800C Shield** installed
2. **JUMPER CAPS Configuration (CRÍTICO!):**
   - Localize os jumper caps no shield
   - **Conecte os jumpers em D0/D1** (NOT D6/D7!)
   - D0/D1 são necessários para usar Hardware Serial1 do R4
   - IMPORTANTE: O R4 WiFi não suporta SoftwareSerial de forma confiável em D6/D7
3. **DIP Switch Configuration:**
   - Set to **EXTERN** if using external power supply (recommended)
   - Set to **ARDUINO** to power through Arduino (requires adequate power)
4. **Pin Connections (via jumpers):**
   - SIM800C TX → Arduino Pin 0 (RX - Hardware Serial1)
   - SIM800C RX → Arduino Pin 1 (TX - Hardware Serial1)
   - Pin 9 → Power control (handled by firmware)
5. Active SIM card inserted in SIM800C module
6. Power supply: 7-12V, 2A+ (SIM800C requires ~2A peak during transmission)
7. USB connection from Arduino to PC
8. **"To Start" button**: Press and hold for 2-3 seconds after power-up
   - STA LED should be solid on (not blinking)
   - NET LED should be blinking (searching/registered on GSM network)

### Arduino Setup

```bash
# Upload the serial bridge firmware
# Open serial_bridge/serial_bridge.ino in Arduino IDE
# Select: Board → Arduino Uno R4 WiFi
# Select: Port → (your COM port)
# Click Upload

# Verify bridge is working:
# Open Serial Monitor (9600 baud)
# Should see initialization messages
# Should see: "✓ SIM800C Module Ready"
# Should see detected baudrate (typically 9600 or 19200)
```

**Key Firmware Features:**
1. **Hardware Serial1:** Uses R4's built-in hardware UART (pins 0/1) instead of SoftwareSerial
2. **Fixed Baudrate:** Uses 9600 baud for SIM800C (configurable via constant in code)
3. **Power Control:** Ensures power pin (D9) is high for module power
4. **USB Serial:** Fixed at 9600 baud for Python communication
5. **Transparent Bridge:** All data forwarded bidirectionally without processing
6. **Fast Startup:** Minimal initialization (~1 second) for immediate Python communication

### Python Application
```bash
# From sms-sender directory
python sms_automation_gui.pyw
```

### Dependencies
```bash
pip install ttkbootstrap pyserial requests
```

**Required packages:**
- `ttkbootstrap`: Modern GUI theme framework
- `pyserial`: Serial port communication with Arduino
- `requests`: HTTP client for SETERA API integration (v2.0)

## Configuration

### Persistent Settings (sms_config.json)
- `port`: COM port for Arduino (auto-detected, updates every second)
- `baudrate`: Always "9600" (hardcoded, not user-configurable)
- `command`: SMS command to send (default: "CONFIG APN=internet.vivo")
- `timeout`: Response wait timeout in seconds (default: 120)
- `cameras`: Array of camera objects

### Auto-Detection Features

**COM Port Auto-Refresh:**
- Scans available COM ports every 1 second
- Automatically updates dropdown list
- No manual refresh button needed
- If current port disappears, auto-selects first available port

### Serial Communication Settings

**Fixed Parameters:**
- USB Serial baudrate: **9600** (Python ↔ Arduino) - hardcoded in both Python and Arduino
- Hardware Serial1 baudrate: **9600** (Arduino ↔ SIM800C) - configurable via constant in firmware
- Python serial settings:
  - Flow control disabled (`rtscts=False`, `dsrdtr=False`, `xonxoff=False`)
  - Write timeout: 1 second
  - Read timeout: 1 second
- Initialization delay: 3 seconds (allows Arduino reset on connection)

**Rationale:**
- **9600 for both:** Standard, reliable, compatible with all systems and SIM800C modules
- **Hardware Serial1:** More reliable than SoftwareSerial on Arduino Uno R4 WiFi (ARM architecture)
- **Flow control disabled:** Prevents interference with Arduino reset and communication
- Baudrate is NOT the bottleneck (GSM network latency is the limiting factor)

**Architecture Difference from Classic Arduino Uno:**
- **Arduino Uno R3** (ATmega328P): SoftwareSerial works well on most pins
- **Arduino Uno R4 WiFi** (Renesas RA4M1 ARM): SoftwareSerial unreliable on D6/D7
- **Solution:** Use Hardware Serial1 (pins 0/1) which uses R4's dedicated UART peripheral

**If you need to change SIM800C baudrate:**
1. Modify `const int SIM800C_BAUDRATE = 9600;` in Arduino sketch (line 19)
2. Change to 19200, 38400, etc. as needed for your module
3. Re-upload firmware to Arduino
4. No Python changes needed (USB Serial stays at 9600)

### Logging
- Activity log: `sms_automation.log` (append mode)
- Export format: `sms_log_YYYYMMDD_HHMMSS.txt`

## Key Implementation Details

### Arduino Bridge Implementation

The Arduino firmware (`serial_bridge/serial_bridge.ino`) is a **stateless transparent bridge**:
- No AT command parsing or processing
- No buffering or protocol logic
- Simply forwards bytes bidirectionally
- Uses **Hardware Serial1** (pins 0 RX, 1 TX) for SIM800C communication
- Auto-detects SIM800C baudrate on startup (9600-115200)

**Key characteristics:**
```cpp
// Forward PC → SIM800C
if (Serial.available()) {
    char c = Serial.read();
    Serial1.write(c);
}

// Forward SIM800C → PC
if (Serial1.available()) {
    char c = Serial1.read();
    Serial.write(c);
}
```

**Why Hardware Serial1 instead of SoftwareSerial:**
- Arduino Uno R4 WiFi uses ARM Cortex-M4 processor (Renesas RA4M1), not AVR (ATmega328P)
- SoftwareSerial library has severe compatibility issues on R4's ARM architecture
- Testing showed SoftwareSerial completely non-functional on pins D6/D7 and D7/D8
- Hardware Serial1 uses dedicated UART peripheral → 100% reliable
- Trade-off: Shares physical pins (0/1) with USB programming, but bridge mode works perfectly
- Requires jumpers on D0/D1 (NOT D6/D7 as classic Uno shields expect)

This means **all AT command logic lives in Python**, not Arduino.

### AT Command Protocol (Python side)

The Python `SerialWorker` thread handles the AT command protocol:

1. **Initialize SMS**: `AT+CMGS="<phone>"`
2. **Wait for prompt**: Look for `>` character
3. **Send message**: Write message text
4. **Send Ctrl+Z**: Byte `[26]` to confirm
5. **Check response**: Wait for `+CMGS:` (success) or `ERROR`

**Important:** AT commands pass through Arduino unchanged to SIM800C module.

### Camera Processing Workflow
1. Status: PENDING → SENDING
2. Send SMS via AT+CMGS command
3. On SMS sent (+CMGS):
   - Status: SENDING → WAITING
   - Start checking for responses every 10s
4. On response received or timeout:
   - Status: WAITING → SUCCESS/FAILED
   - Process next camera

### Connection Validation Workflow
1. User clicks "Conectar" button
2. Open serial port connection
3. Send AT command to validate communication
4. If response contains "OK":
   - Mark as validated
   - Change button to "Desconectar" (red)
   - Status: "● Conectado" (green)
   - **Get module information:**
     - AT+CNUM → Get phone number (MSISDN)
     - AT+CSQ → Get signal quality
     - Update status area with MSISDN and signal bars
5. If no valid response:
   - Auto-disconnect
   - Show error message
   - Status: "● Validação Falhou" (red)
   - User must check hardware/port selection

### Module Information Display

**MSISDN (Phone Number):**
- Command: `AT+CNUM`
- Response: `+CNUM: "","<number>",129`
- Displayed as: `📱 Número: +5511999999999`
- If not available: `📱 Número: Não disponível`

**Signal Strength (CSQ):**
- Command: `AT+CSQ`
- Response: `+CSQ: <rssi>,<ber>`
- RSSI values: 0-31 (signal strength), 99 (unknown/no signal)
- Displayed with visual bars:
  - `📶 ▮▮▮▮ Sinal: 25 (Excelente)` - CSQ 20-31
  - `📶 ▮▮▮▯ Sinal: 17 (Bom)` - CSQ 15-19
  - `📶 ▮▮▯▯ Sinal: 12 (OK)` - CSQ 10-14
  - `📶 ▮▯▯▯ Sinal: 7 (Fraco)` - CSQ 5-9
  - `📵 ▯▯▯▯ Sinal: 99 (Sem sinal)` - CSQ 0-4 or 99

### Thread Safety
- Queue-based communication prevents race conditions
- GUI updates via `after()` scheduler from main thread
- Worker thread is daemon (auto-terminates with main thread)
- Module testing runs in worker thread to prevent GUI freezing
- COM port polling runs on GUI thread via `after()` timer

## Troubleshooting

### Issue: Python doesn't communicate, but Arduino Serial Monitor works

**Symptoms:**
- Arduino Serial Monitor: AT commands work perfectly
- Python application: Empty responses, validation fails

**Root Cause:**
Serial port flow control settings (DTR/RTS) interfering with communication

**Solution:**
Python serial port configuration in `sms_automation_gui.pyw` line 63-71:
```python
self.serial = serial.Serial(
    port=self.port,
    baudrate=self.baudrate,
    timeout=1,
    write_timeout=1,
    rtscts=False,      # CRITICAL: Disable flow control
    dsrdtr=False,      # CRITICAL: Disable DTR/DSR
    xonxoff=False      # Disable software flow control
)
```

Also requires 3-second initialization delay and buffer clearing after port open.

### Issue: SoftwareSerial not working on Arduino Uno R4 WiFi

**Symptoms:**
- SIM800C module powered and registered on GSM (LEDs confirm)
- No response to AT commands on pins D6/D7 or D7/D8
- Tested all baudrates 9600-115200
- Module works fine with Arduino Uno R3

**Root Cause:**
Arduino Uno R4 WiFi uses ARM Cortex-M4 (Renesas RA4M1) processor. SoftwareSerial library was designed for AVR (ATmega) architecture and is incompatible/unreliable on ARM.

**Solution:**
Use Hardware Serial1 instead:
1. Move jumper caps from D6/D7 to **D0/D1**
2. Update firmware to use `Serial1.begin(9600)` instead of SoftwareSerial
3. This uses R4's dedicated UART peripheral (100% reliable)

## Testing the System

### 1. Test Arduino Bridge
```bash
# Open Arduino IDE Serial Monitor (9600 baud)
# Should see: "SMS Serial Bridge Ready"
# Should see: "SIM800C Baudrate: 9600"
# Type: AT
# Should receive: OK
```

### 2. Test SIM800C Module (via Python GUI)

Use the "Test Module" button to verify:
- Basic AT communication (`AT` → `OK`)
- SIM card status (`AT+CPIN?` → `+CPIN: READY`)
- Signal quality (`AT+CSQ` → `+CSQ: 15,0` or higher)
- Network registration (`AT+CREG?` → `+CREG: 0,1` or `0,5`)
- Operator information (`AT+COPS?` → operator name)

**Troubleshooting:**
- No response: Check Arduino USB connection, verify COM port
- "ERROR" responses: Check SIM card insertion, check antenna connection
- Weak signal: Move to location with better GSM coverage
- Power issues: Ensure adequate power supply (2A+ for GSM transmission)

## Import Format

Cameras can be bulk imported from text files:
```
Camera Name, +5512345678
Camera 2, +5512345679
# Comments start with #
```

## Parent Repository Context

This tool is part of the SETERA tools suite (`setera-tools/`). The suite includes 27+ tools for:
- STR1010/STR1010Plus/STR2020 tracker configuration
- Protocol parsing (NMEA, CAN, proprietary)
- Serial communication and simulation
- Firmware updates

Related tools:
- `config_str1010/`: STR1010 configuration utility
- `serial_1ch/`, `serial_2ch/`, `serial_4ch/`: Serial monitors
- `parser_STR1010Plus/`: Protocol data parser

## Project Files

```
sms-sender/
├── sms_automation_gui.pyw         # Main Python application (GUI + logic)
├── setera_api.py                  # SETERA API integration module (v2.0)
├── test_api.py                    # API integration test script (v2.0)
├── serial_bridge/
│   └── serial_bridge.ino          # Arduino firmware (transparent bridge, Hardware Serial1)
├── sms_config.json                # Persistent configuration (auto-generated)
├── sms_automation.log             # Activity log (auto-generated)
├── command_patterns.json          # Command type definitions (optional)
└── CLAUDE.md                      # This file
```

## Common Development Patterns

### Modifying Arduino Bridge

**Current implementation is intentionally simple.** If you need to add Arduino-side logic:

⚠️ **Warning:** Adding processing logic to Arduino breaks the transparent bridge model. Consider these alternatives first:
- Can the logic be implemented in Python instead?
- Does it require real-time hardware access?

**If you must modify Arduino:**
1. Keep forwarding logic intact in `loop()`
2. Add processing only if required for hardware-level features
3. Document protocol changes in this file
4. Update Python side to match any protocol changes

### Adding New AT Commands (Python side)

1. Define command type in message queue
2. Add handler in `SerialWorker.run()` switch statement
3. Implement command method (e.g., `send_at_command()`)
4. Return results via `message_queue.put()`

**Example:**
```python
# In message queue:
{'type': 'CHECK_BALANCE', 'ussd_code': '*222#'}

# In SerialWorker.run():
elif cmd['type'] == 'CHECK_BALANCE':
    self.check_balance(cmd['ussd_code'])
```

### Adding Camera Status States
1. Add enum value to `CameraStatus`
2. Update status display mapping in `refresh_camera_list()`
3. Handle state transitions in automation logic

### UI Customization
- Theme: Modify `themename` parameter in `SMSAutomationApp.__init__()`
- Available themes: darkly, cyborg, solar, superhero, flatly, etc.
- Icons: Currently using emoji; can be replaced with image assets

## Architecture Rationale

**Why separate Arduino and Python?**
- **Simplicity**: Arduino does one thing (serial forwarding) extremely well
- **Maintainability**: Business logic in Python is easier to debug and modify
- **Flexibility**: Can swap Arduino for any USB-serial adapter without code changes
- **Testability**: Can test Python code independently using mock serial ports

**Why not use Arduino for AT command handling?**
- Limited RAM for complex state machines
- Harder to debug and update logic
- Python provides better string processing and threading
- GUI must be in Python anyway (tkinter)
