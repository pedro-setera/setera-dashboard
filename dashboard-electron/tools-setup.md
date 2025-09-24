# Tools Directory Setup

## Development Mode
When running `npm run dev`, the app looks for tools in:
```
dashboard-electron/
├── src/
└── ../../../  (goes to setera-tools directory)
    ├── busca_placa/
    ├── config_str1010/
    ├── simulador_STR1010/
    └── ... (all other tools)
```

## Production Mode
When running the built portable executable, the app expects this structure:
```
distribution-folder/
├── SETERA-Dashboard-1.2.0-portable.exe
└── tools/  (copy all tools here)
    ├── busca_placa/
    ├── config_str1010/
    ├── simulador_STR1010/
    └── ... (all other tools)
```

## Setup Instructions for Distribution

1. Build the app: `npm run dist`
2. Create distribution folder with this structure:
   ```
   SETERA-Dashboard-v1.2/
   ├── SETERA-Dashboard-1.2.0-portable.exe (from dist folder)
   └── tools/
       ├── busca_placa/
       ├── check_cpf/
       ├── config_str1010/
       ├── ConfigSTR1010/
       ├── ConfigSTR1010+/
       ├── field_counter/
       ├── gprs-server/
       ├── odo_fuel/
       ├── parser_STR1010Plus/
       ├── parser_STR2020/
       ├── rpm_analysis/
       ├── serial_1ch/
       ├── serial_2ch/
       ├── serial_4ch/
       ├── simulador_can_visual/
       ├── simulador_nmea/
       ├── simulador_STR1010/
       ├── simulador_STR1010CAN/
       ├── simulador_STR1010Plus/
       ├── simulador_tilt/
       ├── simulador_tpms/
       ├── tpms/
       └── update-fw-str1010/
   ```

3. Distribute the entire `SETERA-Dashboard-v1.2` folder
4. Users create desktop shortcuts to the `.exe` file
5. The app will work portably on any Windows machine with Python installed