import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
import serial
import serial.tools.list_ports
import threading
import time
from datetime import datetime  # Import datetime to generate timestamps
import os
import random

application_path = os.path.dirname(os.path.abspath(__file__))

class SimuladorCANBUS:
    def __init__(self, root):
        self.root = root
        self.root.title("Simulador CANBUS Visual")
        self.root.state('zoomed')
        self.root.iconbitmap(os.path.join(application_path, 'favicon.ico'))

        self.initial_canbus_string = "FR1,2,81329.10,69891.76,123,60,60,1215,53,92,270102,236529,33573,52.750,15872,0,255,12,6.9,3109,275,75,120"
        self.canbus_string = self.initial_canbus_string

        self.random_thread = None
        self.random_running = False
        self.running = False  # Initialize running state to False
        self.serial_port = None  # Initialize serial port to None
        self.serial_thread = None  # Initialize serial thread to None

        # Create the main frames
        self.upper_frame = tk.Frame(root)
        self.upper_frame.pack(fill='x', pady=5)

        self.middle_frame = tk.Frame(root)
        self.middle_frame.pack(fill='x', pady=5)

        self.log_frame = tk.Frame(root)
        self.log_frame.pack(fill='x', pady=5)

        self.lower_frame = tk.Frame(root)
        self.lower_frame.pack(fill='x', pady=5, expand=True)

        # Setup upper container
        self.setup_upper_container()

        # Setup middle container for text entries
        self.setup_middle_container()

        # Setup log area
        self.setup_log_area()

        # Setup lower container for sliders and switches
        self.setup_lower_container()
        
        # Setup proper cleanup on window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def setup_upper_container(self):
        tk.Label(self.upper_frame, text="COM Port:").pack(side='left', padx=(5, 0))
        self.com_port_combo = ttk.Combobox(self.upper_frame, values=self.get_com_ports(), state='readonly', width=7)
        self.com_port_combo.set('COM43')
        self.com_port_combo.pack(side='left', padx=(0, 5))
        
        tk.Label(self.upper_frame, text="Baudrate:").pack(side='left', padx=(5, 0))
        self.baudrate_combo = ttk.Combobox(self.upper_frame, values=[9600, 115200, 230400], state='readonly', width=7)
        self.baudrate_combo.set(115200)
        self.baudrate_combo.pack(side='left', padx=(0, 5))

        self.connect_button = tk.Button(self.upper_frame, text="CONECTAR", bg='green', fg='black', font=("Arial", 10, "bold"), command=self.toggle_connection)
        self.connect_button.pack(side='left', padx=20, pady=5)

        tk.Button(self.upper_frame, text="LIMPAR LOG", bg='white', fg='black', font=("Arial", 10, "bold"), command=self.clear_log).pack(side='left', padx=20)
        tk.Button(self.upper_frame, text="RESET", bg='grey', fg='black', font=("Arial", 10, "bold"), command=self.reset_to_initial_string).pack(side='left', padx=20)

        self.random_button = tk.Button(self.upper_frame, text="START RANDOM", bg='grey', fg='black', font=("Arial", 10, "bold"), command=self.toggle_random_generation)
        self.random_button.pack(side='left', padx=20)

        self.visual_controls_var = tk.BooleanVar(value=True)
        self.visual_controls_checkbox = tk.Checkbutton(self.upper_frame, text="Visual Controls", variable=self.visual_controls_var)
        self.visual_controls_checkbox.pack(side='left', padx=10)

    def setup_middle_container(self):
        labels = ["Status", "Odo", "Cons", "Tanque(L)", "Tanque", "Vel", "RPM", "Acel", "Temp", "Hor", "Fren", "Torque", "Turbo"]
        default_values = ["2", "81329.10", "69891.76", "123", "90", "60", "1215", "53", "92", "270102", "3109", "75", "120"]
        widths = [3, 13, 13, 4, 4, 4, 5, 4, 4, 10, 10, 4, 5]
        self.entries = {}

        for label, value, width in zip(labels, default_values, widths):
            tk.Label(self.middle_frame, text=label).pack(side='left', padx=(5, 0))
            entry = tk.Entry(self.middle_frame, width=width)
            entry.insert(0, value)
            entry.pack(side='left', padx=(0, 5), pady=(0, 5))
            self.entries[label] = entry

    def setup_log_area(self):
        self.debug_text = tk.Text(self.log_frame, bg='black', fg='white', height=18, wrap='none')
        self.debug_text.pack(side='left', fill='both', expand=True, padx=5)

        self.scrollbar = tk.Scrollbar(self.log_frame, command=self.debug_text.yview)
        self.scrollbar.pack(side='right', fill='y')
        self.debug_text['yscrollcommand'] = self.scrollbar.set

        separator = ttk.Separator(self.root, orient='horizontal')
        separator.pack(fill='x', padx=5)

    def setup_lower_container(self):
        font_style = ("Arial", 10, "bold")

        # Status Combo Box (removed label)
        self.status_combo = ttk.Combobox(self.lower_frame, values=["DESL", "IGN", "MOTOR"], state='readonly', width=10, font=font_style)
        self.status_combo.set("MOTOR")
        self.status_combo.pack(side='left', padx=20)  # Increased padding

        # Odo Slider
        odo_frame = tk.Frame(self.lower_frame)
        odo_frame.pack(side='left', padx=20, pady=5)  # Increased padding
        tk.Label(odo_frame, text="Odo", font=font_style).pack(side='top', anchor='center')
        self.odo_value_label = tk.Label(odo_frame, text="81329.10", font=font_style)
        self.odo_value_label.pack(side='top', anchor='center')
        self.odo_slider = tk.Scale(odo_frame, from_=300000, to=0, orient='vertical', length=250, width=25, showvalue=False,
                                command=lambda value: self.odo_value_label.config(text=value))
        self.odo_slider.set(81329.10)
        self.odo_slider.pack(side='top', anchor='center')
        self.odo_slider.bind("<MouseWheel>", lambda event: self.scroll_slider(event, self.odo_slider))

        # Cons Slider
        cons_frame = tk.Frame(self.lower_frame)
        cons_frame.pack(side='left', padx=20, pady=5)  # Increased padding
        tk.Label(cons_frame, text="Cons", font=font_style).pack(side='top', anchor='center')
        self.cons_value_label = tk.Label(cons_frame, text="69891.76", font=font_style)
        self.cons_value_label.pack(side='top', anchor='center')
        self.cons_slider = tk.Scale(cons_frame, from_=100000, to=0, orient='vertical', length=250, width=25, showvalue=False,
                                    command=lambda value: self.cons_value_label.config(text=value))
        self.cons_slider.set(69891.76)
        self.cons_slider.pack(side='top', anchor='center')
        self.cons_slider.bind("<MouseWheel>", lambda event: self.scroll_slider(event, self.cons_slider))

        # Tanque(L) Slider
        tanquel_frame = tk.Frame(self.lower_frame)
        tanquel_frame.pack(side='left', padx=20, pady=5)  # Increased padding
        tk.Label(tanquel_frame, text="Tanque(L)", font=font_style).pack(side='top', anchor='center')
        self.tanquel_limit = tk.IntVar(value=20)
        self.tanquel_limit_entry = tk.Entry(tanquel_frame, textvariable=self.tanquel_limit, width=5, fg="red", justify='center', font=font_style)
        self.tanquel_limit_entry.pack(side='top', anchor='center')
        self.tanquel_value_label = tk.Label(tanquel_frame, text="200", font=font_style)
        self.tanquel_value_label.pack(side='top', anchor='center')
        self.tanquel_slider = tk.Scale(tanquel_frame, from_=500, to=0, orient='vertical', length=250, width=25, showvalue=False,
                                    command=self.check_tanquel_value)
        self.tanquel_slider.set(123)
        self.tanquel_slider.pack(side='top', anchor='center')
        self.tanquel_slider.bind("<MouseWheel>", lambda event: self.scroll_slider(event, self.tanquel_slider))

        # Tanque Slider
        tanque_frame = tk.Frame(self.lower_frame)
        tanque_frame.pack(side='left', padx=20, pady=5)  # Increased padding
        tk.Label(tanque_frame, text="Tanque", font=font_style).pack(side='top', anchor='center')
        self.tanque_limit = tk.IntVar(value=20)
        self.tanque_limit_entry = tk.Entry(tanque_frame, textvariable=self.tanque_limit, width=5, fg="red", justify='center', font=font_style)
        self.tanque_limit_entry.pack(side='top', anchor='center')
        self.tanque_value_label = tk.Label(tanque_frame, text="90", font=font_style)
        self.tanque_value_label.pack(side='top', anchor='center')
        self.tanque_slider = tk.Scale(tanque_frame, from_=100, to=0, orient='vertical', length=250, width=25, showvalue=False,
                                    command=self.check_tanque_value)
        self.tanque_slider.set(90)
        self.tanque_slider.pack(side='top', anchor='center')
        self.tanque_slider.bind("<MouseWheel>", lambda event: self.scroll_slider(event, self.tanque_slider))

        # Vel Slider
        vel_frame = tk.Frame(self.lower_frame)
        vel_frame.pack(side='left', padx=20, pady=5)  # Increased padding
        tk.Label(vel_frame, text="Vel", font=font_style).pack(side='top', anchor='center')
        self.vel_limit = tk.IntVar(value=90)
        self.vel_limit_entry = tk.Entry(vel_frame, textvariable=self.vel_limit, width=5, fg="red", justify='center', font=font_style)
        self.vel_limit_entry.pack(side='top', anchor='center')
        self.vel_value_label = tk.Label(vel_frame, text="60", font=font_style)
        self.vel_value_label.pack(side='top', anchor='center')
        self.vel_slider = tk.Scale(vel_frame, from_=150, to=0, orient='vertical', length=250, width=25, showvalue=False,
                                command=self.check_vel_value)
        self.vel_slider.set(60)
        self.vel_slider.pack(side='top', anchor='center')
        self.vel_slider.bind("<MouseWheel>", lambda event: self.scroll_slider(event, self.vel_slider))

        # RPM Slider
        rpm_frame = tk.Frame(self.lower_frame)
        rpm_frame.pack(side='left', padx=20, pady=5)  # Increased padding
        tk.Label(rpm_frame, text="RPM", font=font_style).pack(side='top', anchor='center')
        self.rpm_limit = tk.IntVar(value=2400)
        self.rpm_limit_entry = tk.Entry(rpm_frame, textvariable=self.rpm_limit, width=5, fg="red", justify='center', font=font_style)
        self.rpm_limit_entry.pack(side='top', anchor='center')
        self.rpm_value_label = tk.Label(rpm_frame, text="1215", font=font_style)
        self.rpm_value_label.pack(side='top', anchor='center')
        self.rpm_slider = tk.Scale(rpm_frame, from_=4000, to=0, orient='vertical', length=250, width=25, showvalue=False,
                                command=self.check_rpm_value)
        self.rpm_slider.set(1215)
        self.rpm_slider.pack(side='top', anchor='center')
        self.rpm_slider.bind("<MouseWheel>", lambda event: self.scroll_slider(event, self.rpm_slider))

        # Acel Slider
        acel_frame = tk.Frame(self.lower_frame)
        acel_frame.pack(side='left', padx=20, pady=5)  # Increased padding
        tk.Label(acel_frame, text="Acel", font=font_style).pack(side='top', anchor='center')
        self.acel_limit = tk.IntVar(value=90)
        self.acel_limit_entry = tk.Entry(acel_frame, textvariable=self.acel_limit, width=5, fg="red", justify='center', font=font_style)
        self.acel_limit_entry.pack(side='top', anchor='center')
        self.acel_value_label = tk.Label(acel_frame, text="53", font=font_style)
        self.acel_value_label.pack(side='top', anchor='center')
        self.acel_slider = tk.Scale(acel_frame, from_=120, to=0, orient='vertical', length=250, width=25, showvalue=False,
                                    command=self.check_acel_value)
        self.acel_slider.set(53)
        self.acel_slider.pack(side='top', anchor='center')
        self.acel_slider.bind("<MouseWheel>", lambda event: self.scroll_slider(event, self.acel_slider))

        # Temp Slider
        temp_frame = tk.Frame(self.lower_frame)
        temp_frame.pack(side='left', padx=20, pady=5)  # Increased padding
        tk.Label(temp_frame, text="Temp", font=font_style).pack(side='top', anchor='center')
        self.temp_limit = tk.IntVar(value=100)
        self.temp_limit_entry = tk.Entry(temp_frame, textvariable=self.temp_limit, width=5, fg="red", justify='center', font=font_style)
        self.temp_limit_entry.pack(side='top', anchor='center')
        self.temp_value_label = tk.Label(temp_frame, text="92", font=font_style)
        self.temp_value_label.pack(side='top', anchor='center')
        self.temp_slider = tk.Scale(temp_frame, from_=130, to=-20, orient='vertical', length=250, width=25, showvalue=False,
                                    command=self.check_temp_value)
        self.temp_slider.set(92)
        self.temp_slider.pack(side='top', anchor='center')
        self.temp_slider.bind("<MouseWheel>", lambda event: self.scroll_slider(event, self.temp_slider))

        # Hor Slider
        hor_frame = tk.Frame(self.lower_frame)
        hor_frame.pack(side='left', padx=20, pady=5)  # Increased padding
        tk.Label(hor_frame, text="Hor", font=font_style).pack(side='top', anchor='center')
        self.hor_value_label = tk.Label(hor_frame, text="270102", font=font_style)
        self.hor_value_label.pack(side='top', anchor='center')
        self.hor_slider = tk.Scale(hor_frame, from_=400000, to=0, orient='vertical', length=250, width=25, showvalue=False,
                                command=lambda value: self.hor_value_label.config(text=value))
        self.hor_slider.set(270102)
        self.hor_slider.pack(side='top', anchor='center')
        self.hor_slider.bind("<MouseWheel>", lambda event: self.scroll_slider(event, self.hor_slider))

        # Torque Slider
        torque_frame = tk.Frame(self.lower_frame)
        torque_frame.pack(side='left', padx=20, pady=5)  # Increased padding
        tk.Label(torque_frame, text="Torque", font=font_style).pack(side='top', anchor='center')
        self.torque_limit = tk.IntVar(value=90)
        self.torque_limit_entry = tk.Entry(torque_frame, textvariable=self.torque_limit, width=5, fg="red", justify='center', font=font_style)
        self.torque_limit_entry.pack(side='top', anchor='center')
        self.torque_value_label = tk.Label(torque_frame, text="75", font=font_style)
        self.torque_value_label.pack(side='top', anchor='center')
        self.torque_slider = tk.Scale(torque_frame, from_=120, to=0, orient='vertical', length=250, width=25, showvalue=False,
                                    command=self.check_torque_value)
        self.torque_slider.set(75)
        self.torque_slider.pack(side='top', anchor='center')
        self.torque_slider.bind("<MouseWheel>", lambda event: self.scroll_slider(event, self.torque_slider))

        # Turbo Slider
        turbo_frame = tk.Frame(self.lower_frame)
        turbo_frame.pack(side='left', padx=20, pady=5)  # Increased padding
        tk.Label(turbo_frame, text="Turbo", font=font_style).pack(side='top', anchor='center')
        self.turbo_limit = tk.IntVar(value=150)
        self.turbo_limit_entry = tk.Entry(turbo_frame, textvariable=self.turbo_limit, width=5, fg="red", justify='center', font=font_style)
        self.turbo_limit_entry.pack(side='top', anchor='center')
        self.turbo_value_label = tk.Label(turbo_frame, text="120", font=font_style)
        self.turbo_value_label.pack(side='top', anchor='center')
        self.turbo_slider = tk.Scale(turbo_frame, from_=250, to=0, orient='vertical', length=250, width=25, showvalue=False,
                                    command=self.check_turbo_value)
        self.turbo_slider.set(120)
        self.turbo_slider.pack(side='top', anchor='center')
        self.turbo_slider.bind("<MouseWheel>", lambda event: self.scroll_slider(event, self.turbo_slider))

        # Fren Button with Counter
        fren_frame = tk.Frame(self.lower_frame)
        fren_frame.pack(side='left', padx=20, pady=5)  # Increased padding
        tk.Label(fren_frame, text="Fren", font=font_style).pack(side='top')
        self.fren_counter = tk.IntVar(value=3109)
        self.fren_button = tk.Button(fren_frame, textvariable=self.fren_counter, command=self.increment_fren, font=font_style)
        self.fren_button.pack(side='top')

    def scroll_slider(self, event, slider):
        step = 1  # Define the step for each scroll
        if event.delta > 0:  # Scroll up
            slider.set(slider.get() + step)
        elif event.delta < 0:  # Scroll down
            slider.set(slider.get() - step)

    def check_tanquel_value(self, value):
        limit = self.tanquel_limit.get()
        self.tanquel_value_label.config(text=value)
        if int(value) < limit:
            self.tanquel_value_label.config(fg="red", font=("Arial", 10, "bold"))
        else:
            self.tanquel_value_label.config(fg="black", font=("Arial", 10, "bold"))

    def check_tanque_value(self, value):
        limit = self.tanque_limit.get()
        self.tanque_value_label.config(text=value)
        if int(value) < limit:
            self.tanque_value_label.config(fg="red", font=("Arial", 10, "bold"))
        else:
            self.tanque_value_label.config(fg="black", font=("Arial", 10, "bold"))

    def check_vel_value(self, value):
        limit = self.vel_limit.get()
        self.vel_value_label.config(text=value)
        if int(value) > limit:
            self.vel_value_label.config(fg="red", font=("Arial", 10, "bold"))
        else:
            self.vel_value_label.config(fg="black", font=("Arial", 10, "bold"))

    def check_acel_value(self, value):
        limit = self.acel_limit.get()
        self.acel_value_label.config(text=value)
        if int(value) > limit:
            self.acel_value_label.config(fg="red", font=("Arial", 10, "bold"))
        else:
            self.acel_value_label.config(fg="black", font=("Arial", 10, "bold"))

    def check_temp_value(self, value):
        limit = self.temp_limit.get()
        self.temp_value_label.config(text=value)
        if int(value) > limit:
            self.temp_value_label.config(fg="red", font=("Arial", 10, "bold"))
        else:
            self.temp_value_label.config(fg="black", font=("Arial", 10, "bold"))

    def check_torque_value(self, value):
        limit = self.torque_limit.get()
        self.torque_value_label.config(text=value)
        if int(value) > limit:
            self.torque_value_label.config(fg="red", font=("Arial", 10, "bold"))
        else:
            self.torque_value_label.config(fg="black", font=("Arial", 10, "bold"))

    def check_turbo_value(self, value):
        limit = self.turbo_limit.get()
        self.turbo_value_label.config(text=value)
        if int(value) > limit:
            self.turbo_value_label.config(fg="red", font=("Arial", 10, "bold"))
        else:
            self.turbo_value_label.config(fg="black", font=("Arial", 10, "bold"))

    def check_rpm_value(self, value):
        limit = self.rpm_limit.get()
        self.rpm_value_label.config(text=value)
        if int(value) > limit:
            self.rpm_value_label.config(fg="red", font=("Arial", 10, "bold"))
        else:
            self.rpm_value_label.config(fg="black", font=("Arial", 10, "bold"))

    def increment_fren(self):
        self.fren_counter.set(self.fren_counter.get() + 1)

    def toggle_connection(self):
        if not self.running:
            self.connect()
        else:
            self.disconnect()

    def toggle_random_generation(self):
        if not self.random_running:
            self.random_running = True
            self.random_button.config(text="STOP RANDOM")
            self.generate_random_values()
        else:
            self.random_running = False
            # Cancel any pending timer
            if self.random_thread is not None:
                self.random_thread.cancel()
                self.random_thread = None
            self.random_button.config(text="START RANDOM")
            self.reset_to_initial_string()

    def generate_random_values(self):
        if self.random_running:
            if self.visual_controls_var.get():
                # Update visual controls with random values
                self.status_combo.set(random.choice(["DESL", "IGN", "MOTOR"]))
                self.odo_slider.set(random.uniform(0, 300000))
                self.cons_slider.set(random.uniform(0, 100000))
                self.tanquel_slider.set(random.randint(0, 500))
                self.tanque_slider.set(random.randint(0, 100))
                self.vel_slider.set(random.randint(0, 150))
                self.rpm_slider.set(random.randint(0, 4000))
                self.acel_slider.set(random.uniform(0, 120))
                self.temp_slider.set(random.randint(-20, 130))
                self.hor_slider.set(random.randint(0, 400000))
                self.torque_slider.set(random.randint(0, 120))
                self.turbo_slider.set(random.randint(0, 250))
                self.fren_counter.set(random.randint(0, 9999))

            else:
                # Exclude "Status" from the random value generation
                excluded_field = "Status"
                for field in self.entries.keys():
                    if field != excluded_field:  # Check to exclude "Status"
                        if field == "Odo":
                            value = f"{random.uniform(0, 300000):.1f}"
                        elif field == "Cons":
                            value = f"{random.uniform(0, 100000):.1f}"
                        elif field == "RPM":
                            value = str(random.randint(0, 4000))
                        elif field == "Hor":
                            value = str(random.randint(0, 400000))
                        elif field == "Fren":
                            value = str(random.randint(0, 9999))
                        else:
                            if field == "Tanque(L)":
                                value = str(random.randint(0, 500))
                            elif field == "Tanque":
                                value = str(random.randint(0, 100))
                            elif field == "Vel":
                                value = str(random.randint(0, 150))
                            elif field == "Acel":
                                value = str(random.randint(0, 120))
                            elif field == "Temp":
                                value = str(random.randint(-20, 130))
                            elif field == "Torque":
                                value = str(random.randint(0, 120))
                            elif field == "Turbo":
                                value = str(random.randint(0, 250))

                        self.entries[field].delete(0, tk.END)
                        self.entries[field].insert(0, value)

            self.update_string()  # Call update_string to apply the new random values to the canbus_string

            # Schedule the next call
            self.random_thread = threading.Timer(1, self.generate_random_values)
            self.random_thread.start()

    def get_com_ports(self):
        ports = serial.tools.list_ports.comports()
        return [port.device for port in ports]

    def connect(self):
        try:
            self.serial_port = serial.Serial(self.com_port_combo.get(), self.baudrate_combo.get(), timeout=1)
            connected_message = f"Conectado a porta serial {self.com_port_combo.get()}.\n"
            self.debug_text.insert(tk.END, connected_message)
            self.debug_text.see(tk.END)
            self.running = True
            self.serial_thread = threading.Thread(target=self.send_data, daemon=True)  # Make daemon thread
            self.serial_thread.start()
            # Update button to show "DESCONECTAR"
            self.connect_button.config(text="DESCONECTAR", bg='yellow')
        except serial.SerialException as e:
            self.serial_port = None
            tk.messagebox.showerror("Erro de conexão", f"Erro ao abrir a porta serial: {str(e)}")

    def disconnect(self):
        # Check and stop random generation if it's running
        if self.random_running:
            self.random_running = False
            if self.random_thread is not None:
                self.random_thread.cancel()
            self.random_button.config(text="START RANDOM")
            self.reset_to_initial_string()  # Reset values as if "STOP RANDOM" was clicked
        
        # Proceed with the existing disconnection logic
        if self.running:
            self.running = False
            # Add timeout to prevent hanging
            if self.serial_thread is not None:
                self.serial_thread.join(timeout=2.0)  # 2 second timeout
                if self.serial_thread.is_alive():
                    print("Warning: Serial thread did not terminate within timeout")
            
            # Always ensure port closure, even if thread is still alive
            if hasattr(self, 'serial_port') and self.serial_port is not None:
                try:
                    self.serial_port.close()
                except Exception as e:
                    print(f"Error closing serial port: {e}")
                finally:
                    self.serial_port = None
            
            disconnected_message = "Desconectado da porta serial.\n"
            self.debug_text.insert(tk.END, disconnected_message)
            self.debug_text.see(tk.END)
            # Update button to show "CONECTAR"
            self.connect_button.config(text="CONECTAR", bg='green')
        # Ensure the UI reflects the stopped state of random generation
        self.reset_to_initial_string()

    def clear_log(self):
        self.debug_text.delete('1.0', tk.END)
        self.reset_to_initial_string()

    def update_string(self):
        if self.visual_controls_var.get():
            # Map the visual controls to their respective fields
            status_map = {"DESL": "0", "IGN": "1", "MOTOR": "2"}
            values_map = {
                "Status": status_map[self.status_combo.get()],
                "Odo": f"{self.odo_slider.get():.1f}",
                "Cons": f"{self.cons_slider.get():.1f}",
                "Tanque(L)": str(self.tanquel_slider.get()),
                "Tanque": str(self.tanque_slider.get()),
                "Vel": str(self.vel_slider.get()),
                "RPM": str(self.rpm_slider.get()),
                "Acel": str(self.acel_slider.get()),
                "Temp": str(self.temp_slider.get()),
                "Hor": str(self.hor_slider.get()),
                "Fren": str(self.fren_counter.get()),
                "Torque": str(self.torque_slider.get()),
                "Turbo": str(self.turbo_slider.get())
            }
        else:
            # Use values from text entries
            values_map = {label: entry.get() for label, entry in self.entries.items()}

        # Update the CANBUS string
        fields_map = {
            "Status": 1, "Odo": 2, "Cons": 3, "Tanque(L)": 4, "Tanque": 5, "Vel": 6,
            "RPM": 7, "Acel": 8, "Temp": 9, "Hor": 10, "Fren": 19,
            "Torque": 21, "Turbo": 22
        }
        parts = self.canbus_string.rstrip().split(',')

        for field, position in fields_map.items():
            parts[position] = values_map[field]

        self.canbus_string = ','.join(parts) + "\r\n"

    def reset_to_initial_string(self):
        self.canbus_string = self.initial_canbus_string
        for label, entry in self.entries.items():
            if label == "Status":
                entry.delete(0, tk.END)
                entry.insert(0, "2")
            elif label == "Odo":
                entry.delete(0, tk.END)
                entry.insert(0, "81329.10")
            elif label == "Cons":
                entry.delete(0, tk.END)
                entry.insert(0, "69891.76")
            elif label == "Tanque(L)":
                entry.delete(0, tk.END)
                entry.insert(0, "123")
            elif label == "Tanque":
                entry.delete(0, tk.END)
                entry.insert(0, "90")
            elif label == "Vel":
                entry.delete(0, tk.END)
                entry.insert(0, "60")
            elif label == "RPM":
                entry.delete(0, tk.END)
                entry.insert(0, "1215")
            elif label == "Acel":
                entry.delete(0, tk.END)
                entry.insert(0, "53")
            elif label == "Temp":
                entry.delete(0, tk.END)
                entry.insert(0, "92")
            elif label == "Hor":
                entry.delete(0, tk.END)
                entry.insert(0, "270102")
            elif label == "Fren":
                entry.delete(0, tk.END)
                entry.insert(0, "3109")
            elif label == "Torque":
                entry.delete(0, tk.END)
                entry.insert(0, "75")
            elif label == "Turbo":
                entry.delete(0, tk.END)
                entry.insert(0, "120")

        # Reset visual controls
        self.status_combo.set("DESL")
        self.odo_slider.set(81329.10)
        self.cons_slider.set(69891.76)
        self.tanquel_slider.set(123)
        self.tanque_slider.set(90)
        self.vel_slider.set(60)
        self.rpm_slider.set(1215)
        self.acel_slider.set(53)
        self.temp_slider.set(92)
        self.hor_slider.set(270102)
        self.torque_slider.set(75)
        self.turbo_slider.set(120)
        self.fren_counter.set(3109)

    def update_gui_log(self, timestamp, message):
        """Thread-safe method to update GUI log"""
        try:
            self.debug_text.insert(tk.END, f"{timestamp} Tx: {message}")
            self.debug_text.see(tk.END)  # Auto-scroll to the bottom
        except tk.TclError:
            # GUI might be destroyed, ignore the error
            pass

    def send_data(self):
        while self.running:
            try:
                # Validate port state before each operation
                if not hasattr(self, 'serial_port') or self.serial_port is None:
                    break
                if not self.serial_port.is_open:
                    break
                
                self.update_string()
                timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                self.serial_port.write(self.canbus_string.encode())
                
                # Use thread-safe GUI update
                self.root.after(0, self.update_gui_log, timestamp, self.canbus_string)
                
                time.sleep(1)
            except serial.SerialException as e:
                self.running = False
                # Ensure port is closed on exception
                try:
                    if hasattr(self, 'serial_port') and self.serial_port is not None:
                        self.serial_port.close()
                        self.serial_port = None
                except Exception:
                    pass  # Ignore errors during forced closure
                
                # Use thread-safe error message
                self.root.after(0, lambda: tk.messagebox.showerror("Erro de conexão", f"Erro na comunicação serial: {str(e)}"))
                break
            except Exception as e:
                # Catch any other unexpected errors
                self.running = False
                try:
                    if hasattr(self, 'serial_port') and self.serial_port is not None:
                        self.serial_port.close()
                        self.serial_port = None
                except Exception:
                    pass
                
                self.root.after(0, lambda: tk.messagebox.showerror("Erro inesperado", f"Erro inesperado: {str(e)}"))
                break

    def on_closing(self):
        """Cleanup method called when window is being closed"""
        try:
            # Stop random generation if running
            if self.random_running:
                self.random_running = False
                if self.random_thread is not None:
                    self.random_thread.cancel()
            
            # Disconnect and cleanup serial connection
            if self.running:
                self.running = False
                
                # Force close serial port immediately
                if hasattr(self, 'serial_port') and self.serial_port is not None:
                    try:
                        self.serial_port.close()
                    except Exception:
                        pass
                    self.serial_port = None
                
                # Wait briefly for thread to finish, but don't hang
                if hasattr(self, 'serial_thread') and self.serial_thread is not None:
                    self.serial_thread.join(timeout=1.0)
        
        except Exception as e:
            print(f"Error during cleanup: {e}")
        finally:
            # Always destroy the window
            self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = SimuladorCANBUS(root)
    root.mainloop()
