"""
Test script for NMEA parser
Tests various NMEA sentence types with different talker IDs
"""

import pynmea2

# Test sentences with different talker IDs and sentence types
test_sentences = [
    # GPS GGA
    "$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47",

    # GLONASS GGA
    "$GLGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*5E",

    # GNSS (combined) GGA
    "$GNGGA,184353.07,1929.045,S,02410.506,E,1,04,2.6,100.00,M,-33.9,M,,0000*6D",

    # GPS RMC
    "$GPRMC,123519,A,4807.038,N,01131.000,E,022.4,084.4,230394,003.1,W*6A",

    # GNSS RMC
    "$GNRMC,083559.00,A,4717.11437,N,00833.91522,E,0.004,77.52,091202,,,A*57",

    # GPS GSA
    "$GPGSA,A,3,04,05,,09,12,,,24,,,,,2.5,1.3,2.1*39",

    # GPS GSV
    "$GPGSV,2,1,08,01,40,083,46,02,17,308,41,12,07,344,39,14,22,228,45*75",

    # GPS VTG
    "$GPVTG,054.7,T,034.4,M,005.5,N,010.2,K*48",

    # GPS GLL
    "$GPGLL,4916.45,N,12311.12,W,225444,A,*1D",

    # Invalid sentence (for error testing)
    "$INVALID,123,456,789*00",

    # Sentence without checksum
    "$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,",
]

print("="*80)
print("TESTE DO PARSER NMEA - SETERA TELEMETRIA")
print("="*80)
print()

for i, sentence in enumerate(test_sentences, 1):
    print(f"\nTeste {i}:")
    print(f"Sentença: {sentence}")
    print("-"*80)

    try:
        msg = pynmea2.parse(sentence)
        print(f"[OK] Parse bem-sucedido!")
        print(f"  Tipo: {msg.sentence_type}")
        print(f"  Talker ID: {msg.talker}")

        # Show some specific fields based on type
        if msg.sentence_type == 'GGA':
            print(f"  Latitude: {msg.latitude}")
            print(f"  Longitude: {msg.longitude}")
            print(f"  Altitude: {msg.altitude}")
        elif msg.sentence_type == 'RMC':
            print(f"  Latitude: {msg.latitude}")
            print(f"  Longitude: {msg.longitude}")
            print(f"  Velocidade: {msg.spd_over_grnd} nos")
        elif msg.sentence_type == 'GSA':
            print(f"  Tipo de Fix: {msg.mode_fix_type}")
            print(f"  PDOP: {msg.pdop}")
        elif msg.sentence_type == 'GSV':
            print(f"  Total de Satelites: {msg.num_sv_in_view}")
        elif msg.sentence_type == 'VTG':
            print(f"  Velocidade: {msg.spd_over_grnd_kmph} km/h")
        elif msg.sentence_type == 'GLL':
            print(f"  Latitude: {msg.latitude}")
            print(f"  Longitude: {msg.longitude}")

    except pynmea2.ParseError as e:
        print(f"[ERRO] Erro de parse: {e}")
    except Exception as e:
        print(f"[ERRO] Erro inesperado: {e}")

print("\n" + "="*80)
print("TESTE CONCLUÍDO")
print("="*80)
