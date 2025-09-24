import tkinter as tk
from tkinter import ttk
import serial
import serial.tools.list_ports
import tkinter.messagebox
import threading
from datetime import datetime  # Import datetime to generate timestamps
import os
import time
import random

application_path = os.path.dirname(os.path.abspath(__file__))

class SimuladorTPMS:
    def __init__(self, root):
        self.root = root
        self.root.title("Simulador TPMS")
        self.root.geometry("1500x230")
        #self.root.state('zoomed')  # Open window maximized
        self.root.iconbitmap(os.path.join(application_path, 'favicon.ico'))
        self.running = False

        # Upper Container
        self.setup_upper_container()

        # Horizontal Separator
        separator = ttk.Separator(root, orient='horizontal')
        separator.pack(fill='x', padx=5)

        # Lower Container
        self.setup_lower_container()

        # Debug Text Widget
        self.debug_text = tk.Text(root, bg='black', fg='white')
        self.debug_text.pack(fill='both', expand=True)

        # Serial Communication
        self.serial_port = None

    def setup_upper_container(self):
        upper_frame = tk.Frame(self.root)
        upper_frame.pack(fill='x', pady=5)

        # Labels and Dropdowns for COM Port and Baudrate
        tk.Label(upper_frame, text="COM Port:").pack(side='left', padx=(5, 0))
        
        self.com_port_combo = ttk.Combobox(upper_frame, values=self.get_com_ports(), state='readonly', width=7)
        self.com_port_combo.set('COM44')
        self.com_port_combo.pack(side='left', padx=(0, 5))
        
        tk.Label(upper_frame, text="Baudrate:").pack(side='left', padx=(5, 0))
        self.baudrate_combo = ttk.Combobox(upper_frame, values=[9600, 115200], state='readonly', width=7)
        self.baudrate_combo.set(9600)
        self.baudrate_combo.pack(side='left', padx=(0, 5))

        # Toggle Connect Button
        self.isConnected = False  # Track connection state
        self.toggle_connect_button = tk.Button(upper_frame, text="CONECTAR", bg='green', fg='black', font=("Arial", 10, "bold"), command=self.toggle_connection)
        self.toggle_connect_button.pack(side='left', padx=10)

        # Clear Log Button
        tk.Button(upper_frame, text="LIMPAR LOG", bg='white', fg='black', font=("Arial", 10, "bold"), command=self.clear_log).pack(side='left', padx=10)

        # SET timer send Button
        tk.Button(upper_frame, text="ENVIO LOOP", bg='grey', fg='black', font=("Arial", 10, "bold"), command=self.start_send_timer_data_thread).pack(side='left', padx=10)

        # RANDOM toggle Button - Updated to include command
        self.random_button = tk.Button(upper_frame, text="START RANDOM", bg='grey', fg='black', font=("Arial", 10, "bold"), command=self.toggle_random_generation)
        self.random_button.pack(side='left', padx=10)

    def setup_lower_container(self):
        lower_frame = tk.Frame(self.root)
        lower_frame.pack(fill='x', pady=5)

        # Labels and Text Entry Boxes
        labels = ["ID Sensor:", "Pressão(PSI):", "Temp(⁰C):", "Bateria:"]
        default_values = ["000F007F00CA", "112", "29", "FF"]
        widths = [15, 5, 5, 5]
        self.entries = {}

        for label, value, width in zip(labels, default_values, widths):
            label_widget = tk.Label(lower_frame, text=label)
            label_widget.pack(side='left', padx=(5, 0))  # Apply padx of (5, 0) to the label
            entry = tk.Entry(lower_frame, width=width)
            entry.insert(0, value)
            entry.pack(side='left', padx=(0, 5))  # Apply padx of (0, 5) to the combobox
            self.entries[label] = entry

        # SET single send Button
        tk.Button(lower_frame, text="ENVIO ÚNICO", bg='grey', fg='black', font=("Arial", 10, "bold"), command=self.start_send_data_thread).pack(side='left', padx=10)

        # New Interval Entry
        tk.Label(lower_frame, text="Timer(ms):").pack(side='left')
        self.interval_entry = tk.Entry(lower_frame, width=7)
        self.interval_entry.pack(side='left', padx=(0, 5))
        self.interval_entry.insert(0, "10000")  # Default value

    def toggle_random_generation(self):
        if self.random_button["text"] == "START RANDOM":
            self.random_button.config(text="STOP RANDOM")
            self.running = True
            self.random_thread = threading.Thread(target=self.generate_random_data)
            self.random_thread.daemon = True
            self.random_thread.start()
        else:
            self.stop_random_generation()

    def generate_random_data(self):
        while self.running:
            # Generate random values
            pressao_psi = random.randint(0, 188)  # Random value between 0 and 200
            temperatura_c = random.randint(0, 150)  # Random value between -30 and 150

            # Update the entries with new random values
            self.entries["Pressão(PSI):"].delete(0, tk.END)
            self.entries["Pressão(PSI):"].insert(0, str(pressao_psi))
            self.entries["Temp(⁰C):"].delete(0, tk.END)
            self.entries["Temp(⁰C):"].insert(0, str(temperatura_c))

            time.sleep(0.5)  # Wait for 200ms before generating next values

    def stop_random_generation(self):
        self.random_button.config(text="START RANDOM")
        self.running = False
        self.entries["Pressão(PSI):"].delete(0, tk.END)
        self.entries["Pressão(PSI):"].insert(0, "112")  # Default value
        self.entries["Temp(⁰C):"].delete(0, tk.END)
        self.entries["Temp(⁰C):"].insert(0, "29")  # Default value

    def toggle_connection(self):
        if not self.isConnected:
            self.connect()
            if self.serial_port and self.serial_port.is_open:
                self.isConnected = True
                self.toggle_connect_button.config(text="DESCONECTAR", bg='yellow')
        else:
            self.disconnect()
            self.isConnected = False
            self.toggle_connect_button.config(text="CONECTAR", bg='green')

    def start_send_data_thread(self):
        if self.serial_port and self.serial_port.is_open:
            self.running = True
            send_thread = threading.Thread(target=self.send_data)
            send_thread.daemon = True
            send_thread.start()
        else:
            tk.messagebox.showerror("Erro de conexão", "Sem conexão serial. Favor abrir a conexão antes de enviar dados.")

    def start_send_timer_data_thread(self):
        if self.serial_port and self.serial_port.is_open:
            self.running = True
            send_thread = threading.Thread(target=self.send_timer_data)
            send_thread.daemon = True
            send_thread.start()
        else:
            tk.messagebox.showerror("Erro de conexão", "Sem conexão serial. Favor abrir a conexão antes de enviar dados.")

    def get_com_ports(self):
        ports = serial.tools.list_ports.comports()
        return [port.device for port in ports]

    def connect(self):
        # Check if the serial port is already open
        if not self.serial_port or not self.serial_port.is_open:
            try:
                self.serial_port = serial.Serial(self.com_port_combo.get(), self.baudrate_combo.get(), timeout=1)
                connected_message = f"Conectado a porta serial {self.com_port_combo.get()}.\n"
                self.debug_text.insert(tk.END, connected_message)
                self.debug_text.see(tk.END)
            except serial.SerialException as e:
                tk.messagebox.showerror("Erro de conexão", "Erro ao abrir a porta serial.")
                # In case of connection error, reset the button to initial state
                self.isConnected = False
                self.toggle_connect_button.config(text="CONECTAR", bg='green')

    def disconnect(self):
        # Check if the serial port is open before trying to close it
        if self.serial_port and self.serial_port.is_open:
            self.stop_random_generation()  # Ensure random generation is stopped on disconnect
            self.serial_port.close()
            disconnected_message = "Desconectado da porta serial.\n"
            self.debug_text.insert(tk.END, disconnected_message)
            self.debug_text.see(tk.END)

    def clear_log(self):
        self.debug_text.delete('1.0', tk.END)
        # Reset the values in the text boxes to their default values
        self.entries["ID Sensor:"].delete(0, tk.END)
        self.entries["ID Sensor:"].insert(0, "000F007F00CA")
        self.entries["Pressão(PSI):"].delete(0, tk.END)
        self.entries["Pressão(PSI):"].insert(0, "112")
        self.entries["Temp(⁰C):"].delete(0, tk.END)
        self.entries["Temp(⁰C):"].insert(0, "29")
        self.entries["Bateria:"].delete(0, tk.END)
        self.entries["Bateria:"].insert(0, "FF")

    def send_data(self):
        if self.serial_port and self.serial_port.is_open:
            # Extract values from 'ID Sensor' entry
            id_sensor = self.entries["ID Sensor:"].get()
            if len(id_sensor) != 12:
                tk.messagebox.showerror("Erro de Entrada", "O ID do Sensor deve ter 12 caracteres.")
                return

            try:
                # Convert 'ID Sensor' values to bytes
                id_bytes = [int(id_sensor[i:i+2], 16) for i in range(0, len(id_sensor), 2)]

                # Process 'Pressão(PSI)' value, consider it as zero if empty
                pressao_psi = self.entries["Pressão(PSI):"].get() or "0"
                pressao_psi = int(pressao_psi)
                pressao_hex = int(round(pressao_psi / 0.74))
                pressao_bytes = [pressao_hex >> 8, pressao_hex & 0xFF]

                # Process 'Temperatura(⁰C)' value, consider it as zero if empty
                temperatura_c = self.entries["Temp(⁰C):"].get() or "0"
                temperatura_c = int(temperatura_c)
                temperatura_hex = temperatura_c + 50
                temperatura_bytes = [temperatura_hex >> 8, temperatura_hex & 0xFF]

                # Process 'Bateria' value, consider it as zero if empty
                bateria = self.entries["Bateria:"].get() or "0"
                bateria_hex = int(bateria, 16)

                # Calculate checksum
                checksum = sum(id_bytes + pressao_bytes + temperatura_bytes + [0x77]) & 0xFF

                # Prepare the HEX string
                hex_string = [
                    0x54, 0x50, 0x56, 0x2C, 0xA7, 0x02, 0x2C,
                    id_bytes[0], id_bytes[1], 0x2C, id_bytes[2],
                    id_bytes[3], 0x2C, id_bytes[4], id_bytes[5],
                    0x2C, pressao_bytes[0], pressao_bytes[1], 0x2C,
                    temperatura_bytes[0], temperatura_bytes[1], 0x2C,
                    0x00, bateria_hex, 0x2C, 0x00, checksum, 0x0D, 0x0A
                ]

                # Convert HEX string to bytes
                hex_data = bytes(hex_string)

                # Convert bytes to readable HEX string (e.g., "00 FF 1E")
                readable_hex_string = ' '.join(f'{byte:02X}' for byte in hex_data)

                # Send data over serial
                timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                self.serial_port.write(hex_data)  # Send the hex data
                self.debug_text.insert(tk.END, f"{timestamp} Tx: {readable_hex_string}\r\n")
                self.debug_text.see(tk.END)  # Auto-scroll to the bottom
            except ValueError:
                tk.messagebox.showerror("Erro de Formato", "Formato inválido para o ID do Sensor, Pressão(PSI), Temperatura(⁰C) ou Bateria.")
            except serial.SerialException as e:
                tk.messagebox.showerror("Erro de conexão", "Erro na comunicação serial.")

    def send_timer_data(self):
        while self.running:  # Run indefinitely until self.running is False
            self.send_data()  # call send_data as a method of the class
                        
            # Retrieve the interval from the interval_entry, convert it to float and divide by 1000 to get seconds
            try:
                interval_sec = float(self.interval_entry.get()) / 1000
            except ValueError:
                tk.messagebox.showerror("Intervalo inválido", "Por favor insira um intervalo de envio válido.")
                break  # Exit the loop if the interval is invalid
            
            time.sleep(interval_sec)  # Sleep for the specified interval

if __name__ == "__main__":
    root = tk.Tk()
    app = SimuladorTPMS(root)
    root.mainloop()
