import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
from tkinter import filedialog
import serial
import serial.tools.list_ports
import queue
import threading
from datetime import datetime
import time
import os


class SerialCollectorQuadrant(tk.Frame):
    def __init__(self, parent, quadrant_number, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.quadrant_number = quadrant_number
        
        # Variables
        self.serial_connection = None
        self.queue = queue.Queue()
        self.connect_var = tk.StringVar()
        self.connect_var.set("CONECTAR")
        self.filter_var = tk.StringVar()
        self.send_text_var = tk.StringVar()
        self.initial_run = True
        self.display_mode = tk.StringVar()
        self.display_mode.set("ASCII")
        self.crlf_var = tk.BooleanVar()
        self.send_every_1s_var = tk.BooleanVar()
        self.send_every_1s_thread = None
        self.reading_thread = None
        self.running = False
        self.lock = threading.Lock()
        self.commands = self.load_commands()

        # Elements
        ttk.Label(self, text="COM:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.com_dropbox = ttk.Combobox(self, width=15)
        self.com_dropbox.grid(row=0, column=1, pady=5)

        ttk.Label(self, text="Baudrate:").grid(row=0, column=2, padx=5, pady=5, sticky="w")
        self.baudrate_dropbox = ttk.Combobox(self, values=[9600, 14400, 19200, 38400, 57600, 115200], width=15)
        self.baudrate_dropbox.grid(row=0, column=3, pady=5)
        self.baudrate_dropbox.set(115200)

        self.connect_button = tk.Button(self, textvariable=self.connect_var, command=self.toggle_connection)
        self.connect_button.grid(row=0, column=4, padx=5, pady=5)

        self.clear_button = ttk.Button(self, text="LIMPAR", command=self.clear_text)
        self.clear_button.grid(row=0, column=5, pady=5)

        self.save_button = ttk.Button(self, text="SALVAR LOG", command=self.save_text)
        self.save_button.grid(row=0, column=6, padx=5, pady=5, sticky="w")

        self.toggle_display_button = tk.Button(self, textvariable=self.display_mode, command=self.toggle_display_mode)
        self.toggle_display_button.grid(row=0, column=7, padx=5, pady=5, sticky="w")

        ttk.Label(self, text="Filtro:").grid(row=1, column=0, columnspan=2, padx=5, sticky="w")
        self.filter_entry = ttk.Entry(self, textvariable=self.filter_var)
        self.filter_entry.grid(row=1, column=1, columnspan=6, padx=5, sticky="ew")

        ttk.Label(self, text="Envio:").grid(row=2, column=0, columnspan=2, padx=5, pady=5, sticky="w")

        # Change send_text_entry to a Combobox with autocomplete
        self.send_text_combobox = ttk.Combobox(self, textvariable=self.send_text_var, values=self.commands)
        self.send_text_combobox.grid(row=2, column=1, columnspan=3, padx=5, pady=5, sticky="ew")

        # Bind events for autocomplete and capitalization
        self.send_text_combobox.bind('<KeyRelease>', self.on_combobox_key_release)

        self.send_button = ttk.Button(self, text="ENVIAR", command=self.start_send_data_thread)
        self.send_button.grid(row=2, column=4, padx=5, pady=5)

        self.crlf_checkbutton = ttk.Checkbutton(self, text="CRLF", variable=self.crlf_var)
        self.crlf_checkbutton.grid(row=2, column=5, padx=5, pady=5)

        self.send_every_1s_checkbutton = ttk.Checkbutton(self, text="1s", variable=self.send_every_1s_var, command=self.toggle_send_every_1s)
        self.send_every_1s_checkbutton.grid(row=2, column=6, padx=5, pady=5)

        # Serial text and scrollbar
        self.text_frame = tk.Frame(self)
        self.text_frame.grid(row=3, column=0, columnspan=8, padx=5, pady=5, sticky="nsew")
        self.serial_text = tk.Text(self.text_frame, wrap=tk.WORD)
        self.serial_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.serial_text.tag_configure('timestamp', foreground='blue')
        self.serial_text.tag_configure('filtered', foreground='red')
        self.serial_text.tag_configure('sent', foreground='red')
        self.scrollbar = ttk.Scrollbar(self.text_frame, command=self.serial_text.yview)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.serial_text.config(yscrollcommand=self.scrollbar.set)
        
        self.grid_rowconfigure(3, weight=1)
        self.grid_columnconfigure(7, weight=1)

        # Auto-update COM ports
        self.auto_update_com_ports()

        # Start the queue processing
        self.after(10, self.process_queue)

    def load_commands(self):
        commands = []
        script_dir = os.path.dirname(os.path.realpath(__file__))
        commands_file = os.path.join(script_dir, 'commands.ini')
        if os.path.exists(commands_file):
            with open(commands_file, 'r', encoding='utf-8') as file:
                section = None
                for line in file:
                    line = line.strip()
                    if line.startswith('[') and line.endswith(']'):
                        section = line[1:-1]
                        if section:  # Add an empty line before the new section
                            commands.append('')
                        commands.append(f'--- {section} ---')  # Section header with special format
                    elif line:
                        commands.append(line)
        return commands

    def on_combobox_key_release(self, event):
        """Handle autocomplete filtering and automatic capitalization"""
        # Get current text
        current_text = self.send_text_var.get()

        # Automatic capitalization - convert to uppercase
        cursor_position = self.send_text_combobox.index(tk.INSERT)
        capitalized_text = current_text.upper()

        if capitalized_text != current_text:
            self.send_text_var.set(capitalized_text)
            self.send_text_combobox.icursor(cursor_position)

        # Filter dropdown based on typed text (only if text is not empty)
        if current_text:
            # Filter commands that contain the typed text (case-insensitive search)
            filtered = [cmd for cmd in self.commands if current_text.upper() in cmd.upper() and not cmd.startswith('---')]

            if filtered:
                self.send_text_combobox['values'] = filtered
            else:
                # If no matches, show all commands (user is typing a custom command)
                self.send_text_combobox['values'] = self.commands
        else:
            # If text is empty, show all commands
            self.send_text_combobox['values'] = self.commands

    def toggle_connection(self):
        if self.connect_var.get() == "CONECTAR":
            try:
                self.serial_connection = serial.Serial(
                    port=self.com_dropbox.get(),
                    baudrate=int(self.baudrate_dropbox.get()),
                    timeout=1)
                self.connect_var.set("DESCONECTAR")
                self.connect_button.config(bg='green')
                self.running = True
                self.reading_thread = threading.Thread(target=self.read_from_port, daemon=True)
                self.reading_thread.start()
            except Exception as e:
                messagebox.showerror("Erro de conexão", "Porta COM em uso.")
        else:
            self.connect_var.set("CONECTAR")
            self.connect_button.config(bg=self.cget('bg'))
            self.running = False
            if self.serial_connection:
                with self.lock:
                    self.serial_connection.close()
                    self.serial_connection = None

    def auto_update_com_ports(self):
        if self.initial_run or self.connect_var.get() == "CONECTAR":
            com_list = [port.device for port in serial.tools.list_ports.comports()]
            current_com = self.com_dropbox.get()
            self.com_dropbox['values'] = com_list
            if current_com in com_list:
                self.com_dropbox.set(current_com)
            else:
                self.com_dropbox.set("")

    def read_from_port(self):
        buffer = bytearray()
        last_byte_time = time.time()
        line_timeout = max(0.05, 1.0 / (int(self.baudrate_dropbox.get()) / 10))  # Dynamic timeout

        while self.running:
            with self.lock:
                if self.serial_connection and self.serial_connection.in_waiting:
                    new_data = self.serial_connection.read(self.serial_connection.in_waiting)
                    buffer.extend(new_data)
                    last_byte_time = time.time()
                else:
                    current_time = time.time()
                    if current_time - last_byte_time > line_timeout and buffer:
                        self.process_buffer(buffer)
                        buffer = bytearray()

    def process_buffer(self, buffer):
        if self.display_mode.get() == "ASCII":
            reading = buffer.decode("utf-8", "ignore").strip()
            reading_with_labels = ""
            i = 0
            while i < len(reading):
                if reading[i] == '\r':
                    if i + 1 < len(reading) and reading[i + 1] == '\n':
                        reading_with_labels += '<CRLF>\r\n'
                        i += 2
                    else:
                        reading_with_labels += '<CR>\r'
                        i += 1
                elif reading[i] == '\n':
                    reading_with_labels += '<LF>\n'
                    i += 1
                else:
                    reading_with_labels += reading[i]
                    i += 1
            reading = reading_with_labels
        else:  # HEX mode
            reading = " ".join(f"{byte:02X}" for byte in buffer)

        if reading:  # Only process if reading is not empty
            timestamp = datetime.now().strftime("[%H:%M:%S.%f]")[:-4] + "]"
            self.queue.put((timestamp, reading))

    def process_queue(self):
        while not self.queue.empty():
            try:
                timestamp, text = self.queue.get_nowait()
                filter_text = self.filter_var.get().lower()
                if filter_text and filter_text in text.lower():
                    self.serial_text.insert(tk.END, '\n' + timestamp, 'timestamp')
                    start_index = text.lower().find(filter_text)
                    end_index = start_index + len(filter_text)
                    self.serial_text.insert(tk.END, text[:start_index])
                    self.serial_text.insert(tk.END, text[start_index:end_index], 'filtered')
                    self.serial_text.insert(tk.END, text[end_index:])
                    self.serial_text.see(tk.END)
                elif not filter_text:
                    self.serial_text.insert(tk.END, '\n' + timestamp, 'timestamp')
                    self.serial_text.insert(tk.END, text)
                    self.serial_text.see(tk.END)
            except queue.Empty:
                pass
        self.after(10, self.process_queue)

    def clear_text(self):
        self.serial_text.delete(1.0, tk.END)

    def save_text(self):
        now = datetime.now()
        downloads_folder = os.path.join(os.path.expanduser("~"), "Downloads")
        default_filename = f"CH{self.quadrant_number}_{now.strftime('%y%m%d_%H%M%S')}.txt"
        file_path = filedialog.asksaveasfilename(initialdir=downloads_folder, defaultextension=".txt",
                                                 filetypes=[("Text file", "*.txt")],
                                                 initialfile=default_filename)
        if file_path:
            with open(file_path, 'w') as file:
                text_to_save = self.serial_text.get(1.0, tk.END)
                file.write(text_to_save)

    def toggle_display_mode(self):
        if self.display_mode.get() == "ASCII":
            self.display_mode.set("HEX")
            self.toggle_display_button.config(bg='yellow')
        else:
            self.display_mode.set("ASCII")
            self.toggle_display_button.config(bg=self.cget('bg'))

    def start_send_data_thread(self):
        threading.Thread(target=self.send_data, daemon=True).start()

    def send_data(self):
        if not self.serial_connection or not self.serial_connection.is_open:
            messagebox.showerror("Erro de envio", "Primeiro abra a porta serial.")
            return
        if not self.send_text_var.get():
            messagebox.showerror("Erro de envio", "Não há texto para envio.")
            return

        data = self.send_text_var.get()
        if self.display_mode.get() == "HEX":
            try:
                data_bytes = bytes.fromhex(data.replace(' ', ''))
            except ValueError:
                messagebox.showerror("Erro de envio", "Formato HEX inválido. Insira pares de caracteres separados por espaço.")
                return
        else:
            data_bytes = data.encode()

        if self.crlf_var.get():
            if self.display_mode.get() == "HEX":
                data_bytes += b'\x0D\x0A'
            else:
                data_bytes += b'\r\n'

        try:
            with self.lock:
                self.serial_connection.write(data_bytes)
            timestamp = datetime.now().strftime("[%H:%M:%S.%f]")[:-4] + "]"
            if self.display_mode.get() == "HEX":
                self.serial_text.insert(tk.END, '\n' + timestamp + ' '.join([f"{b:02X}" for b in data_bytes]), 'sent')
            else:
                self.serial_text.insert(tk.END, '\n' + timestamp + data_bytes.decode("ascii", "ignore"), 'sent')
            self.serial_text.see(tk.END)
        except Exception as e:
            messagebox.showerror("Erro de envio", "Erro ao enviar dados.")

    def toggle_send_every_1s(self):
        if self.send_every_1s_var.get():
            if not self.serial_connection or not self.serial_connection.is_open:
                messagebox.showerror("Erro de envio", "Primeiro abra a porta serial.")
                self.send_every_1s_var.set(False)
                return
            if not self.send_text_var.get():
                messagebox.showerror("Erro de envio", "Não há texto para envio.")
                self.send_every_1s_var.set(False)
                return
            self.send_every_1s_thread = threading.Thread(target=self.send_data_every_1s, daemon=True)
            self.send_every_1s_thread.start()
        else:
            if self.send_every_1s_thread:
                self.send_every_1s_thread = None

    def send_data_every_1s(self):
        while self.send_every_1s_var.get():
            self.send_data()
            time.sleep(1)


class SerialCollectorApp(tk.Tk):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.title("SETERA - Coletor Serial 4 Canais")
        self.state("zoomed")

        # Create 4 quadrants
        quadrant1 = SerialCollectorQuadrant(self, 1)
        quadrant1.grid(row=0, column=0, sticky="nsew")
        quadrant2 = SerialCollectorQuadrant(self, 2)
        quadrant2.grid(row=0, column=1, sticky="nsew")
        quadrant3 = SerialCollectorQuadrant(self, 3)
        quadrant3.grid(row=1, column=0, sticky="nsew")
        quadrant4 = SerialCollectorQuadrant(self, 4)
        quadrant4.grid(row=1, column=1, sticky="nsew")

        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)


if __name__ == "__main__":
    app = SerialCollectorApp()
    script_dir = os.path.dirname(os.path.realpath(__file__))  # Get the directory of the script
    icon_path = os.path.join(script_dir, 'favicon.ico')  # Construct the path to the icon file
    app.iconbitmap(icon_path)
    app.mainloop()
