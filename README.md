# SETERA Dashboard - Electron Desktop Application

A modern desktop dashboard for managing and launching SETERA's suite of development tools for STR1010, STR1010Plus, and STR2020 trackers.

![SETERA Ferramentas v1.3](dashboard-electron/assets/logo.png)

## 🚀 Overview

The SETERA Dashboard is an Electron-based desktop application that provides a unified interface to launch 22+ specialized tools for SETERA tracker development and analysis. Originally built as a Flask/Python web application, it has been migrated to Electron for instant startup times and a native desktop experience.

## 📋 Features

- **Instant Startup**: Desktop application launches in under 1 second
- **22+ Integrated Tools**: Easy access to all SETERA development utilities
- **Modern Interface**: Clean, responsive design with search functionality
- **Portable Distribution**: Single executable with no installation required
- **Administrative Privileges**: Automatic UAC elevation for tools requiring admin rights
- **Cross-Platform**: Built with Electron for Windows, macOS, and Linux

## 🛠️ Tools Included

### Communication & Protocol Tools
- **busca_placa** - Board discovery and identification
- **serial_1ch, serial_2ch, serial_4ch** - Multi-channel serial communication
- **gprs-server** - GPRS server management
- **simulador_nmea** - NMEA protocol simulator

### STR1010/STR1010Plus Tools
- **parser_STR1010Plus** - STR1010Plus data parser
- **parser_STR2020** - STR2020 data parser
- **simulador_STR1010** - STR1010 device simulator
- **simulador_STR1010CAN** - STR1010 CAN bus simulator
- **simulador_STR1010Plus** - STR1010Plus simulator
- **update-fw-str1010** - Firmware update utility (requires admin rights)

### Analysis & Monitoring Tools
- **field_counter** - Field data counter and analyzer
- **odo_fuel** - Odometer and fuel consumption analysis
- **odo_gps_can_stats** - GPS and CAN statistics analyzer
- **rpm_analysis** - RPM data analysis with web interface
- **gauge** - Real-time gauge display
- **tpms** - Tire Pressure Monitoring System tools
- **simulador_tpms** - TPMS simulator

### Specialized Tools
- **simulador_can_visual** - Visual CAN bus simulator
- **simulador_tilt** - Tilt sensor simulator
- **check_cpf** - CPF validation utility
- **config_str1010** - STR1010 configuration utility

### Configuration Tools (Separate Repositories)
- **ConfigSTR1010** - Available at [config-fota-str1010](https://github.com/pedro-setera/config-fota-str1010)
- **ConfigSTR1010+** - Available at [str1010plus-config-tool](https://github.com/pedro-setera/str1010plus-config-tool)

## 📦 Installation & Distribution

### For End Users
1. Download the complete `setera-tools` folder
2. Navigate to `dashboard-electron/dist/`
3. Run `SETERA-Ferramentas.exe`
4. Create desktop shortcuts as needed

### For Developers

#### Prerequisites
- **Node.js** (v16 or higher)
- **npm** (comes with Node.js)
- **Python 3.8+** (for Python-based tools)

#### Python Dependencies
Install required Python packages for all tools:
```bash
pip install psycopg2-binary pandas matplotlib seaborn flask
```

#### Build Setup
```bash
# Navigate to the Electron app directory
cd dashboard-electron

# Install dependencies
npm install

# Development mode
npm run dev

# Build for production
npm run dist
```

## 🔧 Development

### Project Structure
```
setera-tools/
├── dashboard-electron/          # Main Electron application
│   ├── src/
│   │   ├── main.js             # Main Electron process
│   │   └── renderer/           # Frontend HTML/CSS/JS
│   ├── assets/                 # Icons and resources
│   ├── package.json            # Node.js configuration
│   └── dist/                   # Build output
├── busca_placa/                # Tool: Board discovery
├── serial_1ch/                 # Tool: Single channel serial
├── rpm_analysis/               # Tool: RPM analysis
├── update-fw-str1010/          # Tool: Firmware updater
└── [... other tools ...]
```

### Key Technologies
- **Frontend**: Electron, HTML5, CSS3, JavaScript
- **Backend**: Node.js, Express.js
- **Python Tools**: Flask, PostgreSQL, Matplotlib, Pandas
- **Build System**: electron-builder
- **Process Management**: Node.js child_process

### Build Scripts
- `npm run dev` - Development mode with hot reload
- `npm run dist` - Build portable executable
- `npm run build` - Production build only

## 🗃️ Database Requirements

Some tools require PostgreSQL database connectivity:
- **odo_gps_can_stats** - Statistics storage and analysis
- **rpm_analysis** - RPM data persistence

Ensure PostgreSQL is installed and properly configured for these tools.

## 🔐 Administrative Privileges

The following tools require administrator privileges and will automatically trigger UAC prompts:
- **update-fw-str1010** - Firmware flashing requires elevated permissions

## 🐛 Troubleshooting

### Common Issues

**Application won't start:**
- Ensure all tool folders are present in the same directory as the dashboard
- Check that `busca_placa`, `config_str1010`, and `update-fw-str1010` folders exist

**Tools not launching:**
- Verify Python installation and dependencies
- Check that executable files have proper permissions
- Ensure PostgreSQL is running for database-dependent tools

**UAC/Admin issues:**
- Run as administrator if UAC prompts fail
- Check Windows security settings

### Debug Information
The application logs debug information to the console. In case of issues:
1. Launch from command line to see console output
2. Check for path resolution messages
3. Verify tool marker directories are found

## 📜 License

Copyright © 2024 SETERA. All rights reserved.

## 🤝 Contributing

This is a private repository for SETERA internal development. For access or contribution guidelines, contact the development team.

## 📞 Support

For technical support or questions:
- Internal SETERA development team
- GitHub Issues (for repository contributors)

---

**SETERA Ferramentas v1.3 - 24Set2025**
Built with ❤️ using Electron and Node.js