import tkinter as tk
from tkinter import ttk, font, messagebox
import serial
import serial.tools.list_ports
import threading
import os

# Determine application path for portable Python environment
application_path = os.path.dirname(os.path.abspath(__file__))


class TPMSIdentifier:
    def __init__(self, root):
        self.root = root
        self.root.title("IDENTIFICADOR DE SENSORES TPMS - SETERA TELEMETRIA")
        self.root.state('zoomed')

        # Set icon
        icon_path = os.path.join(application_path, 'favicon.ico')
        if os.path.exists(icon_path):
            self.root.iconbitmap(icon_path)

        # Serial connection variables
        self.serial_port = None
        self.running = False
        self.read_thread = None

        # Define fonts
        self.bold_font = font.Font(weight='bold', size=10)
        self.title_font = font.Font(weight='bold', size=11)
        self.mono_font = font.Font(family='Courier New', size=9)

        self.setup_ui()

    def setup_ui(self):
        """Setup the user interface"""
        # Main container
        main_frame = tk.Frame(self.root, padx=10, pady=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Top frame - Connection controls
        top_frame = tk.LabelFrame(main_frame, text="CONEXÃO SERIAL", font=self.title_font, padx=10, pady=10)
        top_frame.pack(fill=tk.X, pady=(0, 10))

        tk.Label(top_frame, text="Porta COM:", font=self.bold_font).pack(side=tk.LEFT, padx=(0, 5))

        self.com_port_var = tk.StringVar()
        self.com_port_combo = ttk.Combobox(
            top_frame,
            textvariable=self.com_port_var,
            state='readonly',
            width=15,
            font=self.bold_font
        )
        self.update_com_ports()
        self.com_port_combo.pack(side=tk.LEFT, padx=(0, 20))

        self.connect_button = tk.Button(
            top_frame,
            text="CONECTAR",
            command=self.toggle_connection,
            bg='green',
            fg='white',
            font=self.bold_font,
            padx=20,
            pady=5,
            cursor='hand2'
        )
        self.connect_button.pack(side=tk.LEFT, padx=(0, 20))

        tk.Button(
            top_frame,
            text="LIMPAR LOG",
            command=self.clear_log,
            bg='orange',
            fg='white',
            font=self.bold_font,
            padx=20,
            pady=5,
            cursor='hand2'
        ).pack(side=tk.LEFT)

        # Middle frame - Raw data log
        log_frame = tk.LabelFrame(main_frame, text="LOG DE DADOS RECEBIDOS", font=self.title_font, padx=10, pady=10)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Scrollbar for log
        log_scrollbar = tk.Scrollbar(log_frame)
        log_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.log_text = tk.Text(
            log_frame,
            height=10,
            wrap=tk.WORD,
            font=self.mono_font,
            bg='black',
            fg='#00FF00',
            yscrollcommand=log_scrollbar.set
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)
        log_scrollbar.config(command=self.log_text.yview)

        # Bottom frame - Parsed data
        parsed_frame = tk.LabelFrame(main_frame, text="DADOS INTERPRETADOS", font=self.title_font, padx=10, pady=10)
        parsed_frame.pack(fill=tk.BOTH, pady=(0, 10))

        # Create a grid for parsed data
        self.parsed_labels = {}
        self.sensor_id_value = ''  # Store sensor ID for copying

        fields = [
            ('sensor_id', 'ID do Sensor:'),
            ('status', 'Status:'),
            ('pressure', 'Pressão:'),
            ('temperature', 'Temperatura:'),
            ('battery', 'Bateria:'),
            ('checksum', 'Checksum:')
        ]

        for row, (key, label_text) in enumerate(fields):
            tk.Label(
                parsed_frame,
                text=label_text,
                font=self.bold_font,
                anchor='e',
                width=15
            ).grid(row=row, column=0, sticky='e', padx=(0, 10), pady=5)

            value_label = tk.Label(
                parsed_frame,
                text='-',
                font=self.bold_font,
                anchor='w',
                fg='blue'
            )
            value_label.grid(row=row, column=1, sticky='w', pady=5)
            self.parsed_labels[key] = value_label

            # Add COPIAR ID button next to sensor ID field
            if key == 'sensor_id':
                self.copy_id_button = tk.Button(
                    parsed_frame,
                    text="COPIAR ID",
                    command=self.copy_sensor_id,
                    bg='#4CAF50',
                    fg='white',
                    font=self.bold_font,
                    padx=10,
                    pady=2,
                    cursor='hand2',
                    state='disabled'  # Disabled until we have an ID
                )
                self.copy_id_button.grid(row=row, column=2, sticky='w', padx=(10, 0), pady=5)

    def update_com_ports(self):
        """Update the list of available COM ports"""
        ports = [port.device for port in serial.tools.list_ports.comports()]
        self.com_port_combo['values'] = ports
        if ports:
            self.com_port_combo.current(0)
        else:
            self.com_port_combo.set('Nenhuma porta disponível')

    def toggle_connection(self):
        """Toggle serial connection"""
        if not self.running:
            self.connect()
        else:
            self.disconnect()

    def connect(self):
        """Connect to serial port"""
        port = self.com_port_var.get()

        if not port or port == 'Nenhuma porta disponível':
            messagebox.showwarning("Aviso", "Selecione uma porta COM válida.")
            return

        try:
            self.serial_port = serial.Serial(port, 9600, timeout=1)
            self.running = True

            self.log_message(f"✓ Conectado a {port} (9600 baud)\n")
            self.log_message("="*60 + "\n")

            # Update UI
            self.connect_button.config(text="DESCONECTAR", bg='red')
            self.com_port_combo.config(state='disabled')

            # Start read thread
            self.read_thread = threading.Thread(target=self.read_serial, daemon=True)
            self.read_thread.start()

        except serial.SerialException as e:
            messagebox.showerror("Erro", f"Falha ao conectar à porta {port}:\n{str(e)}")

    def disconnect(self):
        """Disconnect from serial port"""
        if self.running:
            self.running = False

            if self.read_thread and self.read_thread.is_alive():
                self.read_thread.join(timeout=2)

            if self.serial_port and self.serial_port.is_open:
                self.serial_port.close()

            self.log_message("\n" + "="*60 + "\n")
            self.log_message("✗ Desconectado\n")

            # Update UI
            self.connect_button.config(text="CONECTAR", bg='green')
            self.com_port_combo.config(state='readonly')

    def read_serial(self):
        """Read data from serial port"""
        while self.running and self.serial_port and self.serial_port.is_open:
            try:
                if self.serial_port.in_waiting:
                    # Read line from serial
                    line = self.serial_port.readline()

                    if line:
                        # Try to decode as ASCII
                        try:
                            hex_string = line.decode('ascii').strip()
                        except:
                            hex_string = ' '.join([f'{b:02X}' for b in line])

                        # Parse and display (logging happens inside parse_tpms_data)
                        self.root.after(0, self.parse_tpms_data, hex_string)

            except Exception as e:
                self.root.after(0, self.log_message, f"ERRO: {str(e)}\n")
                break

    def parse_tpms_data(self, hex_string):
        """Parse TPMS data from hex string"""
        try:
            # Auto-clear log and parsed data when new string arrives
            self.log_text.delete('1.0', tk.END)
            for label in self.parsed_labels.values():
                label.config(text='-', fg='blue')
            self.copy_id_button.config(state='disabled')

            # Remove spaces and convert to uppercase
            hex_clean = hex_string.replace(' ', '').upper()

            # Check if it starts with TPV (545056)
            if not hex_clean.startswith('545056'):
                self.update_parsed_field('checksum', 'Formato inválido (não começa com TPV)', 'red')
                return

            # Split by comma separator (2C)
            parts = hex_clean.split('2C')

            # Validate minimum number of parts
            if len(parts) < 9:
                self.update_parsed_field('checksum', f'Formato inválido (poucos campos: {len(parts)})', 'red')
                return

            # Extract fields
            header = parts[0]  # 545056 (TPV)
            flag_and_sensor = parts[1] if len(parts) > 1 else ''
            id1 = parts[2] if len(parts) > 2 else ''
            id2 = parts[3] if len(parts) > 3 else ''
            id3 = parts[4] if len(parts) > 4 else ''
            temp_hex = parts[5] if len(parts) > 5 else ''
            pressure_hex = parts[6] if len(parts) > 6 else ''
            battery_hex = parts[7] if len(parts) > 7 else ''
            checksum_hex = parts[8] if len(parts) > 8 else ''

            # Parse flag and sensor number
            if len(flag_and_sensor) >= 2:
                flag = flag_and_sensor[:2]
                sensor_num = flag_and_sensor[2:] if len(flag_and_sensor) > 2 else '00'
            else:
                flag = '00'
                sensor_num = '00'

            # Determine status based on flag
            status_desc = {
                'A7': 'Normal (sem alarmes)',
                '02': 'VAZAMENTO DE AR',
                '01': 'BATERIA FRACA'
            }
            status = status_desc.get(flag, f'Desconhecido (0x{flag})')

            # Parse sensor ID
            id1_val = int(id1, 16) if id1 else 0
            id2_val = int(id2, 16) if id2 else 0
            id3_val = int(id3, 16) if id3 else 0

            # Format sensor ID as uppercase without spaces (e.g., 000F009200BC)
            sensor_id = f"{id1}{id2}{id3}".upper()
            self.sensor_id_value = sensor_id  # Store for copying

            # Parse temperature
            if flag == '02':  # Leak frame - ignore temperature
                temperature = "N/A (frame de vazamento)"
            elif temp_hex == '0057':  # Learning code - ignore
                temperature = "N/A (código de aprendizado)"
            else:
                temp_val = int(temp_hex, 16) if temp_hex else 0
                temp_celsius = temp_val - 50
                temperature = f"{temp_celsius}°C"

            # Parse pressure
            if flag == '02':  # Leak frame - pressure is 0000
                pressure = "N/A (frame de vazamento)"
            else:
                pressure_val = int(pressure_hex, 16) if pressure_hex else 0
                pressure_psi = pressure_val * 0.74
                pressure_kpa = pressure_val * 1.37
                pressure = f"{pressure_psi:.1f} PSI ({pressure_kpa:.1f} kPa)"

            # Parse battery status
            battery_val = int(battery_hex, 16) if battery_hex else 0
            if battery_val == 0xFF:
                battery = "OK"
            elif battery_val == 0x00:
                battery = "FRACA"
            else:
                battery = f"0x{battery_hex}"

            # Calculate and verify checksum - format is "00 XX 0D 0A", we want XX
            if len(checksum_hex) >= 4:
                checksum_received = int(checksum_hex[2:4], 16)
            else:
                checksum_received = 0

            # Calculate expected checksum based on flag
            if flag == '02':  # Leak
                checksum_calc = (0x80 | id1_val) + id2_val + id3_val + int(pressure_hex, 16) + int(temp_hex, 16) + 0x77
            elif flag == 'A7':  # Normal
                checksum_calc = id1_val + id2_val + id3_val + int(pressure_hex, 16) + int(temp_hex, 16) + 0x77
            elif flag == '01':  # Low battery
                checksum_calc = (0x40 | id1_val) + id2_val + id3_val + int(pressure_hex, 16) + int(temp_hex, 16) + 0x77
            else:
                checksum_calc = 0

            # Keep only last byte of checksum
            checksum_calc = checksum_calc & 0xFF

            # Verify checksum
            if checksum_received == checksum_calc:
                checksum_status = f"✓ Válido (0x{checksum_received:02X})"
                checksum_color = 'green'
            else:
                checksum_status = f"✗ Inválido (RX: 0x{checksum_received:02X}, Calc: 0x{checksum_calc:02X})"
                checksum_color = 'red'

            # Update parsed fields
            self.update_parsed_field('sensor_id', sensor_id, 'blue')

            # Enable copy button now that we have a valid sensor ID
            self.copy_id_button.config(state='normal')

            status_color = 'green' if flag == 'A7' else 'red'
            self.update_parsed_field('status', status, status_color)

            self.update_parsed_field('pressure', pressure, 'blue')
            self.update_parsed_field('temperature', temperature, 'blue')
            self.update_parsed_field('battery', battery, 'green' if battery == 'OK' else 'red')
            self.update_parsed_field('checksum', checksum_status, checksum_color)

            # Log parsed summary with original data
            self.log_message(f"RX: {hex_string}\n")
            self.log_message(f"  └─> ID: {sensor_id}, Status: {status}, P: {pressure}, T: {temperature}\n")

        except Exception as e:
            self.update_parsed_field('checksum', f'Erro ao parsear: {str(e)}', 'red')
            self.log_message(f"  └─> ERRO: {str(e)}\n")

    def update_parsed_field(self, field_key, value, color='blue'):
        """Update a parsed field label"""
        if field_key in self.parsed_labels:
            self.parsed_labels[field_key].config(text=value, fg=color)

    def log_message(self, message):
        """Add message to log"""
        self.log_text.insert(tk.END, message)
        self.log_text.see(tk.END)

        # Keep log size under control
        lines = int(self.log_text.index('end-1c').split('.')[0])
        if lines > 1000:
            self.log_text.delete('1.0', '200.0')

    def clear_log(self):
        """Clear the log"""
        self.log_text.delete('1.0', tk.END)

        # Reset parsed fields
        for label in self.parsed_labels.values():
            label.config(text='-', fg='blue')

        # Disable copy button and clear sensor ID
        self.sensor_id_value = ''
        self.copy_id_button.config(state='disabled')

    def copy_sensor_id(self):
        """Copy sensor ID to clipboard"""
        if self.sensor_id_value:
            self.root.clipboard_clear()
            self.root.clipboard_append(self.sensor_id_value)
            self.root.update()  # Required for clipboard to work

            # Visual feedback - briefly change button color
            original_bg = self.copy_id_button.cget('bg')
            self.copy_id_button.config(bg='#2196F3', text='COPIADO!')
            self.root.after(1000, lambda: self.copy_id_button.config(bg=original_bg, text='COPIAR ID'))


def main():
    root = tk.Tk()
    app = TPMSIdentifier(root)

    # Handle window close
    def on_closing():
        if app.running:
            app.disconnect()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()
