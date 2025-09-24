import tkinter as tk
from tkinter import ttk
import serial
import serial.tools.list_ports
import threading
import time
from datetime import datetime
import struct  # Import struct for handling binary data
import os
import random

application_path = os.path.dirname(os.path.abspath(__file__))

class SimuladorTiltSensor:
    def __init__(self, root):
        self.root = root
        self.root.title("Simulador Tilt Sensor")
        self.root.geometry("1500x230")
        #self.root.state('zoomed')
        self.root.iconbitmap(os.path.join(application_path, 'favicon.ico'))

        self.current_values = {"Pitch": -3, "Roll": 2, "Temperatura(⁰C)": 21}

        self.is_generating_random = False
        self.random_thread = None

        self.endian_format = '<h'  # Little endian by default

        self.setup_upper_container()
        separator = ttk.Separator(root, orient='horizontal')
        separator.pack(fill='x', padx=5)
        self.setup_lower_container()

        self.debug_text = tk.Text(root, bg='black', fg='white')
        self.debug_text.pack(fill='both', expand=True)

        self.serial_port = None
        self.sending_thread = None
        self.is_sending = False

    def setup_upper_container(self):
        upper_frame = tk.Frame(self.root)
        upper_frame.pack(fill='x', pady=5)

        tk.Label(upper_frame, text="COM Port:").pack(side='left', padx=(5, 0))
        
        self.com_port_combo = ttk.Combobox(upper_frame, values=self.get_com_ports(), state='readonly', width=7)
        self.com_port_combo.set('COM42')
        self.com_port_combo.pack(side='left', padx=(0, 5))
        
        tk.Label(upper_frame, text="Baudrate:").pack(side='left', padx=(5, 0))
        self.baudrate_combo = ttk.Combobox(upper_frame, values=[9600, 115200], state='readonly', width=7)
        self.baudrate_combo.set(115200)
        self.baudrate_combo.pack(side='left', padx=(0, 5))

        # Toggle button for connecting and disconnecting
        self.connect_button = tk.Button(upper_frame, text="CONECTAR", bg='green', fg='black', font=("Arial", 10, "bold"), command=self.toggle_connection)
        self.connect_button.pack(side='left', padx=10)

        tk.Button(upper_frame, text="LIMPAR LOG", bg='white', fg='black', font=("Arial", 10, "bold"), command=self.clear_log).pack(side='left', padx=10)

        # Toggle button for switching little or big endian packing
        self.endian_button = tk.Button(upper_frame, text="LITTLE ENDIAN", bg='white', fg='black', font=("Arial", 10, "bold"), command=self.toggle_endian)
        self.endian_button.pack(side='left', padx=10)

    def setup_lower_container(self):
        lower_frame = tk.Frame(self.root)
        lower_frame.pack(fill='x', pady=5)

        labels = ["Roll", "Pitch", "Temperatura(⁰C)"]
        self.entries = {}

        for label in labels:
            tk.Label(lower_frame, text=label).pack(side='left', padx=5)
            entry = tk.Entry(lower_frame, width=5)
            entry.insert(0, self.current_values[label])
            entry.pack(side='left', padx=5)
            self.entries[label] = entry

        tk.Button(lower_frame, text="SET", bg='grey', fg='black', font=("Arial", 10, "bold"), command=self.update_values).pack(side='left', padx=10)

        tk.Button(lower_frame, text="RESET", bg='grey', fg='black', font=("Arial", 10, "bold"), command=self.reset_to_default_values).pack(side='left', padx=10)

        # RANDOM toggle Button - Updated to include command
        self.random_button = tk.Button(lower_frame, text="START RANDOM", bg='grey', fg='black', font=("Arial", 10, "bold"), command=self.toggle_random_generation)
        self.random_button.pack(side='left', padx=10)

    def toggle_connection(self):
        if self.connect_button['text'] == "CONECTAR":
            self.start_sending_data()
            self.connect_button.config(text="DESCONECTAR", bg='yellow')
        else:
            self.stop_sending_data()
            self.connect_button.config(text="CONECTAR", bg='green')

    def toggle_random_generation(self):
        if self.is_generating_random:
            # Resetting is already handled here
            self.reset_to_default_values()
            self.is_generating_random = False
            self.random_button.config(text="START RANDOM")
        else:
            # Starting random generation, no changes needed here
            self.is_generating_random = True
            self.random_button.config(text="STOP RANDOM")
            self.random_thread = threading.Thread(target=self.generate_random_values, daemon=True)
            self.random_thread.start()

    def generate_random_values(self):
        import random
        while self.is_generating_random:
            self.entries["Pitch"].delete(0, tk.END)
            self.entries["Pitch"].insert(0, str(random.randint(-39, 39)))
            self.entries["Roll"].delete(0, tk.END)
            self.entries["Roll"].insert(0, str(random.randint(-39, 39)))
            self.entries["Temperatura(⁰C)"].delete(0, tk.END)
            self.entries["Temperatura(⁰C)"].insert(0, str(random.randint(-10, 60)))
            self.update_values()
            time.sleep(0.5)  # 200ms

    def get_com_ports(self):
        ports = serial.tools.list_ports.comports()
        return [port.device for port in ports]

    def start_sending_data(self):
        try:
            self.serial_port = serial.Serial(self.com_port_combo.get(), self.baudrate_combo.get(), timeout=1)
            self.debug_text.insert(tk.END, f"Conectado a porta serial {self.com_port_combo.get()}.\n")
            self.is_sending = True
            self.sending_thread = threading.Thread(target=self.send_data, daemon=True)
            self.sending_thread.start()
        except serial.SerialException as e:
            tk.messagebox.showerror("Erro de conexão", "Erro ao abrir a porta serial.")

    def stop_sending_data(self):
        if self.is_generating_random:
            self.toggle_random_generation()  # Stop random generation if active
        if self.serial_port and self.serial_port.is_open:
            self.is_sending = False
            self.serial_port.close()
            self.debug_text.insert(tk.END, "Desconectado da porta serial.\n")
        # Reset the fields to default values
        self.reset_to_default_values()

    def clear_log(self):
        self.debug_text.delete('1.0', tk.END)

    def update_values(self):
        # Update current_values with values from the entries, converting them to their correct types
        self.current_values["Pitch"] = float(self.entries["Pitch"].get())
        self.current_values["Roll"] = float(self.entries["Roll"].get())
        self.current_values["Temperatura(⁰C)"] = float(self.entries["Temperatura(⁰C)"].get())

    def reset_to_default_values(self):
        # Explicitly set to default values
        self.entries["Pitch"].delete(0, tk.END)
        self.entries["Pitch"].insert(0, "-3")
        self.entries["Roll"].delete(0, tk.END)
        self.entries["Roll"].insert(0, "2")
        self.entries["Temperatura(⁰C)"].delete(0, tk.END)
        self.entries["Temperatura(⁰C)"].insert(0, "21")

    def send_data(self):
        while self.is_sending:
            # Convert angles and temperature to the protocol format
            roll_bytes = self.angle_to_bytes(self.current_values["Roll"])
            pitch_bytes = self.angle_to_bytes(self.current_values["Pitch"])
            temperature_bytes = self.temperature_to_bytes(self.current_values["Temperatura(⁰C)"])

            # Assemble the message
            message = bytes([0x55, 0x53]) + roll_bytes + pitch_bytes + bytes([0x00, 0x00]) + temperature_bytes
            checksum = sum(message) & 0xFF
            message += bytes([checksum])

            timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            if self.serial_port and self.serial_port.is_open:
                try:
                    self.serial_port.write(message)
                    hex_string = ' '.join(f'{byte:02X}' for byte in message)
                    self.debug_text.insert(tk.END, f"{timestamp} Tx: {hex_string}\r\n")
                    self.debug_text.see(tk.END)
                except serial.SerialException:
                    self.is_sending = False
                    tk.messagebox.showerror("Erro de conexão", "Erro na comunicação serial.")
            time.sleep(1)

    def toggle_endian(self):
        if self.endian_format == '<h':
            self.endian_format = '>h'  # Switch to big endian
            self.endian_button.config(text="BIG ENDIAN")
        else:
            self.endian_format = '<h'  # Switch back to little endian
            self.endian_button.config(text="LITTLE ENDIAN")

    def angle_to_bytes(self, angle):
        angle_int = int(angle / 180.0 * 32768)
        angle_bytes = struct.pack(self.endian_format, angle_int)
        return angle_bytes

    def temperature_to_bytes(self, temperature):
        temperature_int = int((temperature - 36.53) * 340)
        temperature_bytes = struct.pack(self.endian_format, temperature_int)
        return temperature_bytes

if __name__ == "__main__":
    root = tk.Tk()
    app = SimuladorTiltSensor(root)
    root.mainloop()