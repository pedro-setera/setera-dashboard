/*
 * SMS Serial Bridge - Production Version
 * Arduino Uno R4 WiFi
 * Shield: Keyestudio SIM800C (Ks0254)
 *
 * HARDWARE SETUP:
 * - Jumper caps MUST be on D0 and D1 (NOT D6/D7)
 * - Uses Hardware Serial1 (reliable on R4 WiFi)
 * - External power connected, DIP switch = EXTERN
 * - Press "To Start" button before use (STA LED = solid on)
 *
 * COMMUNICATION:
 * - USB Serial (9600 baud): PC ↔ Arduino
 * - Hardware Serial1 (9600 baud): Arduino ↔ SIM800C
 *
 * IMPORTANT: If your SIM800C uses a different baudrate:
 * Change the value below and re-upload:
 */
const int SIM800C_BAUDRATE = 9600;  // Change this if your module uses 19200, 38400, etc.

/*
 * This sketch acts as a transparent bridge between PC and SIM800C module.
 * All AT commands from PC are forwarded to SIM800C.
 * All responses from SIM800C are forwarded to PC.
 */

const int POWER_PIN = 9;

void setup() {
  // USB Serial for PC communication
  Serial.begin(9600);
  while (!Serial) delay(10);

  // Ensure power pin is high
  pinMode(POWER_PIN, OUTPUT);
  digitalWrite(POWER_PIN, HIGH);

  // Initialize SIM800C communication
  Serial1.begin(SIM800C_BAUDRATE);

  // Short initialization message
  Serial.println("\n==============================================");
  Serial.println("SMS Serial Bridge Ready");
  Serial.print("SIM800C Baudrate: ");
  Serial.println(SIM800C_BAUDRATE);
  Serial.println("==============================================\n");
}

void loop() {
  // Transparent bridge: Forward data in both directions

  // PC → SIM800C
  if (Serial.available()) {
    char c = Serial.read();
    Serial1.write(c);
  }

  // SIM800C → PC
  if (Serial1.available()) {
    char c = Serial1.read();
    Serial.write(c);
  }
}
