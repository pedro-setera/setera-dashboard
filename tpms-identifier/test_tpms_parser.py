"""
Test script for TPMS parser
Tests all sample frames from the documentation
"""

# Test frames from documentation
test_frames = [
    ("Normal 105 PSI / 49°C", "54 50 56 2C A7 00 2C 00 0F 2C 00 65 2C 00 FA 2C 00 8E 2C 00 63 2C 00 FF 2C 00 D6 0D 0A"),
    ("Low pressure 30 PSI / 28°C", "54 50 56 2C A7 00 2C 00 0F 2C 00 65 2C 00 FA 2C 00 29 2C 00 4E 2C 00 FF 2C 00 5C 0D 0A"),
    ("High Temp 105 PSI / 80°C", "54 50 56 2C A7 00 2C 00 0F 2C 00 65 2C 00 FA 2C 00 8E 2C 00 82 2C 00 FF 2C 00 F5 0D 0A"),
    ("Low pressure and High Temp 30 PSI / 80°C", "54 50 56 2C A7 00 2C 00 0F 2C 00 65 2C 00 FA 2C 00 29 2C 00 82 2C 00 FF 2C 00 90 0D 0A"),
    ("Leaking frame 20 PSI / 37°C", "54 50 56 2C 02 00 2C 00 0F 2C 00 65 2C 00 FA 2C 00 1B 2C 00 57 2C 00 FF 2C 00 D7 0D 0A"),
    ("Low battery 110 PSI / 49°C", "54 50 56 2C 01 00 2C 00 0F 2C 00 65 2C 00 FA 2C 00 95 2C 00 63 2C 00 00 2C 00 1D 0D 0A"),
]

print("="*80)
print("TESTE DO PARSER TPMS - SETERA TELEMETRIA")
print("="*80)
print()

def parse_tpms(hex_string, description):
    """Parse TPMS data and display results"""
    print(f"\nTeste: {description}")
    print(f"Frame: {hex_string}")
    print("-"*80)

    try:
        # Remove spaces and convert to uppercase
        hex_clean = hex_string.replace(' ', '').upper()

        # Check if it starts with TPV (545056)
        if not hex_clean.startswith('545056'):
            print("[ERRO] Formato invalido (nao comeca com TPV)")
            return

        # Split by comma separator (2C)
        parts = hex_clean.split('2C')

        if len(parts) < 9:
            print(f"[ERRO] Formato invalido (poucos campos: {len(parts)})")
            return

        # Extract fields
        header = parts[0]  # 545056 (TPV)
        flag_and_sensor = parts[1]
        id1 = parts[2]
        id2 = parts[3]
        id3 = parts[4]
        temp_hex = parts[5]
        pressure_hex = parts[6]
        battery_hex = parts[7]
        checksum_hex = parts[8]

        # Parse flag and sensor number
        flag = flag_and_sensor[:2]
        sensor_num = flag_and_sensor[2:] if len(flag_and_sensor) > 2 else '00'

        # Determine status
        status_desc = {
            'A7': 'Normal (sem alarmes)',
            '02': 'VAZAMENTO DE AR',
            '01': 'BATERIA FRACA'
        }
        status = status_desc.get(flag, f'Desconhecido (0x{flag})')

        # Parse sensor ID
        id1_val = int(id1, 16)
        id2_val = int(id2, 16)
        id3_val = int(id3, 16)
        sensor_id = f"0x{id1}{id2}{id3}"

        # Parse temperature
        if flag == '02':
            temperature = "N/A (frame de vazamento)"
            temp_val = 0
        elif temp_hex == '0057':
            temperature = "N/A (código de aprendizado)"
            temp_val = 0x57
        else:
            temp_val = int(temp_hex, 16)
            temp_celsius = temp_val - 50
            temperature = f"{temp_celsius}°C"

        # Parse pressure
        if flag == '02':
            pressure = "N/A (frame de vazamento)"
            pressure_val = 0
        else:
            pressure_val = int(pressure_hex, 16)
            pressure_psi = pressure_val * 0.74
            pressure_kpa = pressure_val * 1.37
            pressure = f"{pressure_psi:.1f} PSI ({pressure_kpa:.1f} kPa)"

        # Parse battery
        battery_val = int(battery_hex, 16)
        battery = "OK" if battery_val == 0xFF else "FRACA" if battery_val == 0x00 else f"0x{battery_hex}"

        # Calculate checksum - the format is "00 XX 0D 0A", we want the XX part
        # In hex string "00D60D0A", we want bytes 2-3 (D6)
        if len(checksum_hex) >= 4:
            checksum_received = int(checksum_hex[2:4], 16)
        else:
            checksum_received = 0

        if flag == '02':  # Leak
            checksum_calc = (0x80 | id1_val) + id2_val + id3_val + int(pressure_hex, 16) + int(temp_hex, 16) + 0x77
        elif flag == 'A7':  # Normal
            checksum_calc = id1_val + id2_val + id3_val + int(pressure_hex, 16) + int(temp_hex, 16) + 0x77
        elif flag == '01':  # Low battery
            checksum_calc = (0x40 | id1_val) + id2_val + id3_val + int(pressure_hex, 16) + int(temp_hex, 16) + 0x77
        else:
            checksum_calc = 0

        checksum_calc = checksum_calc & 0xFF

        # Display results
        print(f"[OK] Header: {header} (TPV)")
        print(f"[OK] Flag: 0x{flag} ({status})")
        print(f"[OK] Sensor Number: {int(sensor_num, 16) if sensor_num else 0}")
        print(f"[OK] Sensor ID: {sensor_id} ({id1_val:02X}-{id2_val:02X}-{id3_val:02X})")
        print(f"[OK] Temperatura: {temperature}")
        print(f"[OK] Pressao: {pressure}")
        print(f"[OK] Bateria: {battery}")

        if checksum_received == checksum_calc:
            print(f"[OK] Checksum: VALIDO (RX: 0x{checksum_received:02X}, Calc: 0x{checksum_calc:02X})")
        else:
            print(f"[ERRO] Checksum: INVALIDO (RX: 0x{checksum_received:02X}, Calc: 0x{checksum_calc:02X})")

    except Exception as e:
        print(f"[ERRO] ERRO ao parsear: {str(e)}")
        import traceback
        traceback.print_exc()

# Run tests
for description, frame in test_frames:
    parse_tpms(frame, description)

print("\n" + "="*80)
print("TESTE CONCLUÍDO")
print("="*80)
