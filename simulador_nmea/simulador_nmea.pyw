import tkinter as tk
from tkinter import ttk
import serial
import serial.tools.list_ports
import threading
import time
from datetime import datetime, timezone
from tkintermapview import TkinterMapView
import math
import queue

class NMEAGenerator:
    def __init__(self, root):
        self.root = root
        self.root.title("SETERA - Simulador NMEA")
        self.root.state('zoomed')  # Open window zoomed to fit screen

        self.running = False  # Serial connection status
        self.default_latitude = -19.892976
        self.default_longitude = -44.072225
        self.default_zoom = 15
        self.latitude = self.default_latitude
        self.longitude = self.default_longitude
        self.marker = None

        # Thread-safe communication
        self.gui_queue = queue.Queue()
        self.thread_lock = threading.Lock()

        # Cached values for thread-safe access
        self.cached_hdop = 0.7
        self.cached_vel = 40
        self.cached_invalid_gps = False
        self.cached_invalid_crc = False

        # Create main frames
        self.setup_upper_frame()
        self.setup_middle_frame()
        self.setup_lower_frame()

        # Place marker at default position on startup
        self.place_marker(self.default_latitude, self.default_longitude)

        # Draw static circle and rectangle
        self.draw_static_circle()
        self.draw_static_rectangle()

        # Start GUI queue processing
        self.process_gui_queue()

    def setup_upper_frame(self):
        self.upper_frame = tk.Frame(self.root)
        self.upper_frame.pack(fill='x', pady=5)

        tk.Label(self.upper_frame, text="COM Port:").pack(side='left', padx=(5, 0))
        self.com_port_combo = ttk.Combobox(self.upper_frame, values=self.get_com_ports(), state='readonly', width=7)
        self.com_port_combo.set('COM41')  # Default COM port
        self.com_port_combo.pack(side='left', padx=(0, 5))

        tk.Label(self.upper_frame, text="Baudrate:").pack(side='left', padx=(5, 0))
        self.baudrate_combo = ttk.Combobox(self.upper_frame, values=[9600, 115200], state='readonly', width=7)
        self.baudrate_combo.set(115200)  # Default baudrate
        self.baudrate_combo.pack(side='left', padx=(0, 5))

        self.connect_button = tk.Button(self.upper_frame, text="CONECTAR", bg='green', fg='black', font=("Arial", 10, "bold"), command=self.toggle_connection)
        self.connect_button.pack(side='left', padx=20, pady=5)

        tk.Button(self.upper_frame, text="LIMPAR LOG", bg='white', fg='black', font=("Arial", 10, "bold"), command=self.clear_log).pack(side='left', padx=20)
        tk.Button(self.upper_frame, text="RESET", bg='grey', fg='black', font=("Arial", 10, "bold"), command=self.reset_values).pack(side='left', padx=20)

        self.invalid_gps_var = tk.BooleanVar(value=False)
        self.invalid_gps_checkbox = tk.Checkbutton(self.upper_frame, text="GPS Inválido", variable=self.invalid_gps_var, command=self.update_invalid_gps)
        self.invalid_gps_checkbox.pack(side='left', padx=(5, 0))

        self.invalid_crc_var = tk.BooleanVar(value=False)
        self.invalid_crc_checkbox = tk.Checkbutton(self.upper_frame, text="CRC Errado", variable=self.invalid_crc_var, command=self.update_invalid_crc)
        self.invalid_crc_checkbox.pack(side='left', padx=(5, 0))

    def setup_middle_frame(self):
        self.middle_frame = tk.Frame(self.root)
        self.middle_frame.pack(fill='x', pady=5)

        self.debug_text = tk.Text(self.middle_frame, bg='black', fg='white', height=18, wrap='none')
        self.debug_text.pack(side='left', fill='both', expand=True, padx=5)

        self.scrollbar = tk.Scrollbar(self.middle_frame, command=self.debug_text.yview)
        self.scrollbar.pack(side='right', fill='y')
        self.debug_text['yscrollcommand'] = self.scrollbar.set

    def setup_lower_frame(self):
        self.lower_frame = tk.Frame(self.root)
        self.lower_frame.pack(fill='x', pady=5, expand=True)

        font_style = ("Arial", 10, "bold")

        sliders_frame = tk.Frame(self.lower_frame)
        sliders_frame.pack(side='left', padx=20, pady=5, fill='y')  # Sliders on the left

        vel_frame = tk.Frame(sliders_frame)
        vel_frame.pack(side='left', padx=10, pady=5)
        tk.Label(vel_frame, text="Vel", font=font_style).pack(side='top', anchor='center')
        self.vel_value_label = tk.Label(vel_frame, text="40", font=font_style)  # Default to 40 km/h
        self.vel_value_label.pack(side='top', anchor='center')
        self.vel_slider = tk.Scale(vel_frame, from_=250, to=0, orient='vertical', length=250, width=25, showvalue=False, command=self.update_vel)
        self.vel_slider.set(40)  # Default value 40
        self.vel_slider.pack(side='top', anchor='center')
        self.vel_slider.bind("<MouseWheel>", lambda event: self.scroll_slider_vel(event, self.vel_slider))

        hdop_frame = tk.Frame(sliders_frame)
        hdop_frame.pack(side='left', padx=10, pady=5)
        tk.Label(hdop_frame, text="HDOP", font=font_style).pack(side='top', anchor='center')
        self.hdop_value_label = tk.Label(hdop_frame, text="0.7", font=font_style)  # Default to 0.7
        self.hdop_value_label.pack(side='top', anchor='center')
        self.hdop_slider = tk.Scale(hdop_frame, from_=2.0, to=0.0, resolution=0.1, orient='vertical', length=250, width=25, showvalue=False, command=self.update_hdop)
        self.hdop_slider.set(0.7)  # Default value 0.7
        self.hdop_slider.pack(side='top', anchor='center')
        self.hdop_slider.bind("<MouseWheel>", lambda event: self.scroll_slider_hdop(event, self.hdop_slider))

        map_frame = tk.Frame(self.lower_frame)
        map_frame.pack(side='left', expand=True, fill='both', padx=20)

        self.map_widget = TkinterMapView(map_frame, width=700, height=400, corner_radius=0)
        self.map_widget.set_position(self.default_latitude, self.default_longitude)  # Initial position
        self.map_widget.set_zoom(self.default_zoom)  # Initial zoom level
        self.map_widget.pack(expand=True, fill='both')
        self.map_widget.add_left_click_map_command(self.on_map_click)  # Correct method for adding click callback

    def scroll_slider_vel(self, event, slider):
        step = 1  # Define the step for each scroll
        if event.delta > 0:  # Scroll up
            slider.set(slider.get() + step)
        elif event.delta < 0:  # Scroll down
            slider.set(slider.get() - step)

    def scroll_slider_hdop(self, event, slider):
        step = 0.1  # Define the step for each scroll
        if event.delta > 0:  # Scroll up
            slider.set(slider.get() + step)
        elif event.delta < 0:  # Scroll down
            slider.set(slider.get() - step)

    def get_com_ports(self):
        ports = serial.tools.list_ports.comports()
        return [port.device for port in ports]

    def toggle_connection(self):
        if not self.running:
            self.connect()
        else:
            self.disconnect()

    def connect(self):
        try:
            self.serial_port = serial.Serial(self.com_port_combo.get(), self.baudrate_combo.get(), timeout=1)
            connected_message = f"Connected to {self.com_port_combo.get()}.\n"
            self.gui_queue.put(("debug", connected_message))
            self.running = True
            self.serial_thread = threading.Thread(target=self.send_nmea_sentences, daemon=True)
            self.serial_thread.start()
            self.connect_button.config(text="DESCONECTAR", bg='yellow')
        except serial.SerialException as e:
            self.gui_queue.put(("error", f"Failed to open serial port: {e}"))

    def disconnect(self):
        if self.running:
            self.running = False
            if hasattr(self, 'serial_thread') and self.serial_thread.is_alive():
                self.serial_thread.join(timeout=2)  # Ensure the thread is stopped with a timeout
            if hasattr(self, 'serial_port') and self.serial_port.is_open:
                self.serial_port.close()
            disconnected_message = "Disconnected.\n"
            self.gui_queue.put(("debug", disconnected_message))
            self.connect_button.config(text="CONECTAR", bg='green')

    def send_nmea_sentences(self):
        sentence_count = 0
        while self.running:
            try:
                current_time = datetime.now(timezone.utc)
                timestamp = current_time.strftime("%H%M%S.%f")[:-3]
                date_stamp = current_time.strftime("%d%m%y")

                # Create and send GNGGA sentence
                nmea_gngga = self.create_gngga_sentence(timestamp)
                self.serial_port.write(f"{nmea_gngga}\r\n".encode())
                self.gui_queue.put(("debug", f"{nmea_gngga}\n"))

                # Introduce a 200ms delay
                time.sleep(0.2)

                # Create and send GNRMC sentence
                nmea_gnrmc = self.create_gnrmc_sentence(timestamp, date_stamp)
                self.serial_port.write(f"{nmea_gnrmc}\r\n".encode())
                self.gui_queue.put(("debug", f"{nmea_gnrmc}\n"))

                # Manage text widget memory - prevent unbounded growth
                sentence_count += 1
                if sentence_count % 50 == 0:  # Every 50 sentence pairs (100 lines)
                    self.gui_queue.put(("manage_text_size", None))

                # Sleep for remaining time to maintain 1-second interval
                time.sleep(0.8)
            except serial.SerialException as e:
                self.running = False
                self.gui_queue.put(("error", f"Error communicating with serial port: {e}"))
                break

    def manage_debug_text_size(self):
        """Keep debug text widget size under control to prevent memory issues"""
        try:
            lines = int(self.debug_text.index('end-1c').split('.')[0])
            if lines > 1000:  # If more than 1000 lines
                # Remove the first 200 lines to keep it manageable
                self.debug_text.delete('1.0', '200.0')
        except Exception:
            pass  # Ignore errors in text management

    def process_gui_queue(self):
        """Process GUI updates from the queue (called from main thread)"""
        try:
            while True:
                try:
                    msg_type, content = self.gui_queue.get_nowait()

                    if msg_type == "debug":
                        self.debug_text.insert(tk.END, content)
                        self.debug_text.see(tk.END)
                    elif msg_type == "manage_text_size":
                        self.manage_debug_text_size()
                    elif msg_type == "error":
                        tk.messagebox.showerror("Communication Error", content)

                except queue.Empty:
                    break
                except Exception:
                    break

        except Exception:
            pass

        # Schedule next queue processing
        self.root.after(50, self.process_gui_queue)

    def create_gngga_sentence(self, timestamp):
        with self.thread_lock:
            hdop = self.cached_hdop
            lat, ns = self.convert_latitude(self.latitude)
            lon, ew = self.convert_longitude(self.longitude)
        sentence = f"GNGGA,{timestamp},{lat},{ns},{lon},{ew},1,12,{hdop:.1f},193.0,M,56.0,M,,"
        checksum = self.calculate_checksum(sentence)
        return f"{sentence}*{checksum}"

    def create_gnrmc_sentence(self, timestamp, date_stamp):
        with self.thread_lock:
            speed_kmh = self.cached_vel
            lat, ns = self.convert_latitude(self.latitude)
            lon, ew = self.convert_longitude(self.longitude)
            status = 'V' if self.cached_invalid_gps else 'A'  # A or V
        speed_knots = round(speed_kmh / 1.852)  # Convert km/h to knots
        sentence = f"GNRMC,{timestamp},{status},{lat},{ns},{lon},{ew},{speed_knots},23,{date_stamp},,,A,V"
        checksum = self.calculate_checksum(sentence)
        return f"{sentence}*{checksum}"

    def calculate_checksum(self, sentence):
        checksum = 0
        for char in sentence:
            checksum ^= ord(char)
        with self.thread_lock:
            if self.cached_invalid_crc:
                checksum += 1  # Intentionally make the checksum incorrect
        return f"{checksum:02X}"

    def update_vel(self, value):
        self.vel_value_label.config(text=value)
        with self.thread_lock:
            self.cached_vel = int(value)

    def update_hdop(self, value):
        self.hdop_value_label.config(text=f"{float(value):.1f}")
        with self.thread_lock:
            self.cached_hdop = float(value)

    def update_invalid_gps(self):
        with self.thread_lock:
            self.cached_invalid_gps = self.invalid_gps_var.get()

    def update_invalid_crc(self):
        with self.thread_lock:
            self.cached_invalid_crc = self.invalid_crc_var.get()

    def clear_log(self):
        self.debug_text.delete('1.0', tk.END)

    def reset_values(self):
        self.vel_slider.set(40)  # Reset to default 40 km/h
        self.hdop_slider.set(0.7)  # Reset to default 0.7
        self.vel_value_label.config(text="40")
        self.hdop_value_label.config(text="0.7")
        self.invalid_gps_var.set(False)  # Reset to default unchecked state
        self.invalid_crc_var.set(False)  # Reset to default unchecked state
        with self.thread_lock:
            self.cached_vel = 40
            self.cached_hdop = 0.7
            self.cached_invalid_gps = False
            self.cached_invalid_crc = False
        self.reset_map()  # Reset the map
        self.reset_nmea_position()  # Reset the NMEA position

    def reset_map(self):
        self.map_widget.set_position(self.default_latitude, self.default_longitude)
        self.map_widget.set_zoom(self.default_zoom)
        self.place_marker(self.default_latitude, self.default_longitude)

    def reset_nmea_position(self):
        with self.thread_lock:
            self.latitude = self.default_latitude
            self.longitude = self.default_longitude

    def on_map_click(self, coordinates):
        lat, lon = coordinates
        with self.thread_lock:
            self.latitude, self.longitude = lat, lon
        self.place_marker(lat, lon)

    def place_marker(self, lat, lon):
        if self.marker:
            self.map_widget.delete(self.marker)
        self.marker = self.map_widget.set_marker(lat, lon, text="Posição Simulada")

    def draw_static_circle(self):
        # Draw a static circle centered at the default coordinates with a 500m radius
        circle_points = self.create_circle_points(self.default_latitude, self.default_longitude, 500)
        self.static_circle_polygon = self.map_widget.set_polygon(
            circle_points,
            outline_color='red',
            fill_color=None
        )

    def draw_static_rectangle(self):
        # Define the corners of the rectangle
        top_left = (-19.887458, -44.081717)
        bottom_right = (-19.897387, -44.050690)

        # Create the points for the rectangle
        rectangle_points = [
            top_left,
            (top_left[0], bottom_right[1]),  # Top right
            bottom_right,
            (bottom_right[0], top_left[1]),  # Bottom left
            top_left  # Close the rectangle
        ]

        # Draw the rectangle with a blue outline
        self.rectangle_polygon = self.map_widget.set_polygon(
            rectangle_points,
            outline_color='blue',
            fill_color=None
        )

    def create_circle_points(self, center_lat, center_lon, radius_meters, num_points=100):
        earth_radius = 6371000  # Radius of Earth in meters
        circle_points = []

        for i in range(num_points):
            angle = 2 * math.pi * i / num_points
            dx = radius_meters * math.cos(angle)
            dy = radius_meters * math.sin(angle)
            lat_offset = dx / earth_radius * (180 / math.pi)
            lon_offset = dy / (earth_radius * math.cos(math.radians(center_lat))) * (180 / math.pi)
            point_lat = center_lat + lat_offset
            point_lon = center_lon + lon_offset
            circle_points.append((point_lat, point_lon))

        return circle_points

    def convert_latitude(self, lat):
        degrees = int(abs(lat))
        minutes = (abs(lat) - degrees) * 60
        ns = 'N' if lat >= 0 else 'S'
        return f"{degrees:02d}{minutes:07.4f}", ns

    def convert_longitude(self, lon):
        degrees = int(abs(lon))
        minutes = (abs(lon) - degrees) * 60
        ew = 'E' if lon >= 0 else 'W'
        return f"{degrees:03d}{minutes:07.4f}", ew

if __name__ == "__main__":
    root = tk.Tk()
    app = NMEAGenerator(root)

    # Proper cleanup on window close
    def on_closing():
        if hasattr(app, 'running') and app.running:
            app.disconnect()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()