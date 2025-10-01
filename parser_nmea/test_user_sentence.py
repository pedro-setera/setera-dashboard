"""
Test with user's sentence
"""
import pynmea2

sentence = "$GNRMC,152829.501,A,1953.5786,S,04404.3335,W,22,23,011025,,,A,V*02"

print("Testando sentença do usuário:")
print(f"Sentença: {sentence}")
print("-" * 80)

try:
    msg = pynmea2.parse(sentence, check=False)  # Don't check checksum
    print(f"[OK] Parse bem-sucedido!")
    print(f"  Tipo: {msg.sentence_type}")
    print(f"  Talker ID: {msg.talker}")
    print(f"  Latitude RAW: {msg.latitude}")
    print(f"  Latitude ARREDONDADA: {msg.latitude:.6f}")
    print(f"  Longitude RAW: {msg.longitude}")
    print(f"  Longitude ARREDONDADA: {msg.longitude:.6f}")
    print(f"  Velocidade: {msg.spd_over_grnd} nos")
    print(f"  Data: {msg.datestamp}")
    print(f"  Horário: {msg.timestamp}")
except Exception as e:
    print(f"[ERRO] {e}")
