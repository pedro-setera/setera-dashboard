# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SETERA Tools is a suite of 30+ specialized development and analysis tools for SETERA GPS trackers (STR1010, STR1010Plus, STR2020) and fleet management hardware. The main entry point is an Electron desktop application (SETERA Ferramentas Dashboard) that launches individual Python and compiled tools.

## Build Commands

### Electron Dashboard (from dashboard-electron/)
```bash
npm install          # Install dependencies
npm run dev          # Development mode with hot reload
npm run build        # Build portable executable
npm run dist         # Build and package for distribution
```

### Python Dependencies
```bash
pip install psycopg2-binary pandas matplotlib seaborn flask PyQt6 python-can asammdf pyqtgraph pyperclip requests pyserial tkcalendar tkintermapview xlsxwriter canalystii pywin32 numpy scipy standard-telnetlib pynmea2 ttkbootstrap
```

## Architecture

```
setera-tools/
├── dashboard-electron/          # Electron desktop app (main entry)
│   ├── src/main.js             # Electron main process, Express server, tool launcher
│   ├── src/preload.js          # IPC bridge for renderer
│   └── src/renderer/           # Frontend (dashboard.html, static/)
├── [Config Tools]              # .exe and .pyw configuration tools
├── [Serial Monitors]           # Python tkinter serial port monitors (1ch, 2ch, 4ch)
├── [Simulators]                # Python simulators (STR1010, CAN, NMEA, TPMS, tilt)
├── [Parsers]                   # Data parsers and Flask web apps for analysis
└── [Utilities]                 # License plate lookup, RFID reader, SMS sender
```

## Key Patterns

### Tool Launching (main.js)
```javascript
spawn(`"${exePath}"`, [], {
    cwd: path.dirname(exePath),
    detached: true,
    stdio: 'ignore',
    shell: true  // Required for Windows paths with spaces
});
child.unref();
```

### Python GUI Tools (tkinter + ttkbootstrap)
- Entry point: `toolname/toolname.pyw`
- Single file with all logic
- Serial communication with `pyserial` (timeout=1, rtscts=False, dsrdtr=False)
- Threading with daemon threads for background tasks

### Flask Analysis Tools
- Entry point: `toolname/app.py`
- Configuration in `config.ini`
- PostgreSQL connections for data persistence

## Conventions

- **Serial ports**: Always disable flow control (rtscts=False, dsrdtr=False), use timeout=1
- **File paths**: Use `os.path.join()`, never assume drive letters
- **GUI threading**: Never update GUI from non-main threads
- **Configuration**: JSON or INI format, auto-save on changes

## Adding New Tools

1. Create tool directory with matching `.pyw` or `.exe` entry point
2. Add tool card to `dashboard-electron/src/renderer/dashboard.html`
3. Test launching from Electron app
4. Update README.md and bump dashboard version

## Commit Message Format

```
feat: Add [Tool Name] tool and update dashboard to v[version]
fix: [description]
perf: [description]
```
