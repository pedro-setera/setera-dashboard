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
import logging
from concurrent.futures import ThreadPoolExecutor
from collections import deque
import weakref


# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class CircularBuffer:
    """Thread-safe circular buffer for managing display data"""
    def __init__(self, maxsize=10000):
        self.maxsize = maxsize
        self.buffer = deque(maxlen=maxsize)
        self.lock = threading.Lock()
    
    def append(self, item):
        with self.lock:
            self.buffer.append(item)
    
    def get_recent(self, count=None):
        with self.lock:
            if count is None:
                return list(self.buffer)
            return list(self.buffer)[-count:] if count <= len(self.buffer) else list(self.buffer)
    
    def clear(self):
        with self.lock:
            self.buffer.clear()
    
    def size(self):
        with self.lock:
            return len(self.buffer)


class SerialConnectionManager:
    """Enhanced serial connection management with auto-reconnection"""
    def __init__(self, port=None, baudrate=115200, timeout=1):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.connection = None
        self.is_connected = False
        self.lock = threading.Lock()
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 3
        
    def connect(self):
        """Establish serial connection"""
        try:
            with self.lock:
                if self.connection and self.connection.is_open:
                    return True
                    
                self.connection = serial.Serial(
                    port=self.port,
                    baudrate=self.baudrate,
                    timeout=self.timeout,
                    write_timeout=1
                )
                self.is_connected = True
                self.reconnect_attempts = 0
                logger.info(f"Connected to {self.port} at {self.baudrate} baud")
                return True
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            self.is_connected = False
            return False
    
    def disconnect(self):
        """Safely disconnect"""
        try:
            with self.lock:
                if self.connection and self.connection.is_open:
                    self.connection.close()
                self.is_connected = False
                logger.info(f"Disconnected from {self.port}")
        except Exception as e:
            logger.error(f"Disconnect error: {e}")
    
    def read(self, size=1):
        """Thread-safe read operation"""
        try:
            with self.lock:
                if self.connection and self.connection.is_open:
                    return self.connection.read(size)
        except Exception as e:
            logger.error(f"Read error: {e}")
            self.is_connected = False
        return b''
    
    def write(self, data):
        """Thread-safe write operation"""
        try:
            with self.lock:
                if self.connection and self.connection.is_open:
                    bytes_written = self.connection.write(data)
                    self.connection.flush()
                    return bytes_written
        except Exception as e:
            logger.error(f"Write error: {e}")
            self.is_connected = False
        return 0
    
    def in_waiting(self):
        """Check bytes waiting to be read"""
        try:
            with self.lock:
                if self.connection and self.connection.is_open:
                    return self.connection.in_waiting
        except Exception:
            self.is_connected = False
        return 0
    
    def auto_reconnect(self):
        """Attempt to reconnect if disconnected"""
        if not self.is_connected and self.reconnect_attempts < self.max_reconnect_attempts:
            self.reconnect_attempts += 1
            logger.info(f"Auto-reconnect attempt {self.reconnect_attempts}")
            return self.connect()
        return False


class SerialCollectorQuadrant(tk.Frame):
    def __init__(self, parent, quadrant_number, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        
        self.quadrant_number = quadrant_number
        
        # Core variables
        self.serial_manager = SerialConnectionManager()
        self.data_queue = queue.Queue(maxsize=1000)  # Limit queue size
        self.display_buffer = CircularBuffer(maxsize=5000)  # Circular buffer for display
        
        # GUI variables
        self.connect_var = tk.StringVar(value="CONECTAR")
        self.filter_var = tk.StringVar()
        self.send_text_var = tk.StringVar()
        self.display_mode = tk.StringVar(value="ASCII")
        self.crlf_var = tk.BooleanVar()
        self.send_every_1s_var = tk.BooleanVar()
        
        # Threading variables
        self.shutdown_event = threading.Event()
        self.reading_thread = None
        self.send_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix=f"SendWorker-Q{quadrant_number}")
        self.periodic_send_thread = None
        self.running = False
        
        # Performance variables
        self.last_gui_update = time.time()
        self.gui_update_interval = 0.050  # Start with 50ms, will adapt
        self.pending_updates = []
        
        # Load commands and create GUI
        self.commands = self.load_commands()
        self.create_widgets()
        
        # Start background tasks
        self.auto_update_com_ports()
        self.start_gui_processor()
        
        # Register cleanup
        self.bind('<Destroy>', self.on_destroy)
    
    def create_widgets(self):
        """Create all GUI widgets"""
        # Row 0: Connection controls
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
        self.send_text_combobox = ttk.Combobox(self, textvariable=self.send_text_var, values=self.commands, height=20)
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
    
    def load_commands(self):
        """Load commands from INI file"""
        commands = []
        script_dir = os.path.dirname(os.path.realpath(__file__))
        commands_file = os.path.join(script_dir, 'commands.ini')

        if os.path.exists(commands_file):
            try:
                with open(commands_file, 'r', encoding='utf-8') as file:
                    section = None
                    for line in file:
                        line = line.strip()
                        if line.startswith('[') and line.endswith(']'):
                            section = line[1:-1]
                            if section:
                                commands.append('')
                            commands.append(f'--- {section} ---')
                        elif line:
                            commands.append(line)
            except Exception as e:
                logger.error(f"Error loading commands: {e}")
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
        """Toggle serial connection with enhanced error handling"""
        if self.connect_var.get() == "CONECTAR":
            try:
                port = self.com_dropbox.get()
                baudrate = int(self.baudrate_dropbox.get())
                
                if not port:
                    messagebox.showerror("Erro", "Selecione uma porta COM.")
                    return
                
                self.serial_manager.port = port
                self.serial_manager.baudrate = baudrate
                
                if self.serial_manager.connect():
                    self.connect_var.set("DESCONECTAR")
                    self.connect_button.config(bg='green')
                    self.running = True
                    self.shutdown_event.clear()
                    
                    # Start reading thread
                    self.reading_thread = threading.Thread(target=self.read_from_port,
                                                          name=f"Reader-Q{self.quadrant_number}")
                    self.reading_thread.start()
                    
                    self.add_status_message(f"Conectado a {port} ({baudrate} baud)", 'timestamp')
                else:
                    messagebox.showerror("Erro de conexão", "Não foi possível conectar à porta COM.")
                    
            except ValueError:
                messagebox.showerror("Erro", "Baudrate inválido.")
            except Exception as e:
                logger.error(f"Connection error: {e}")
                messagebox.showerror("Erro de conexão", f"Erro inesperado: {str(e)}")
        else:
            self.disconnect()
    
    def disconnect(self):
        """Safely disconnect from serial port"""
        self.connect_var.set("CONECTAR")
        self.connect_button.config(bg=self.cget('bg'))
        self.running = False
        self.shutdown_event.set()
        
        # Stop periodic sending
        if self.send_every_1s_var.get():
            self.send_every_1s_var.set(False)
        
        # Wait for reading thread to finish
        if self.reading_thread and self.reading_thread.is_alive():
            self.reading_thread.join(timeout=2.0)
            if self.reading_thread.is_alive():
                logger.warning("Reading thread did not terminate gracefully")
        
        self.serial_manager.disconnect()
        self.add_status_message("Desconectado", 'error')
    
    def auto_update_com_ports(self):
        """Auto-update COM ports list"""
        try:
            if not self.running:
                com_list = [port.device for port in serial.tools.list_ports.comports()]
                current_com = self.com_dropbox.get()
                self.com_dropbox['values'] = com_list
                
                if current_com not in com_list and com_list:
                    self.com_dropbox.set("")
                elif current_com in com_list:
                    self.com_dropbox.set(current_com)
        except Exception as e:
            logger.error(f"Error updating COM ports: {e}")
        
        # Schedule next update
        self.after(2000, self.auto_update_com_ports)
    
    def read_from_port(self):
        """Enhanced reading thread with better frame detection"""
        buffer = bytearray()
        last_byte_time = time.time()
        consecutive_errors = 0
        max_consecutive_errors = 5
        
        while self.running and not self.shutdown_event.is_set():
            try:
                if self.serial_manager.in_waiting() > 0:
                    byte = self.serial_manager.read(1)
                    if byte:
                        buffer.extend(byte)
                        last_byte_time = time.time()
                        consecutive_errors = 0
                    else:
                        consecutive_errors += 1
                else:
                    current_time = time.time()
                    # Process buffer if timeout occurred and buffer has data
                    if current_time - last_byte_time > 0.020 and buffer:
                        self.process_received_data(buffer)
                        buffer = bytearray()
                    
                    # Small sleep to prevent excessive CPU usage
                    time.sleep(0.001)
                
                # Handle connection errors
                if consecutive_errors >= max_consecutive_errors:
                    logger.warning("Multiple read errors, attempting reconnection")
                    if not self.serial_manager.auto_reconnect():
                        self.add_status_message("Conexão perdida", 'error')
                        self.after_idle(self.disconnect)
                        break
                    consecutive_errors = 0
                    
            except Exception as e:
                logger.error(f"Read thread error: {e}")
                consecutive_errors += 1
                if consecutive_errors >= max_consecutive_errors:
                    self.after_idle(self.disconnect)
                    break
                time.sleep(0.1)
    
    def process_received_data(self, buffer):
        """Process received data and queue for display"""
        try:
            if self.display_mode.get() == "ASCII":
                reading = buffer.decode("utf-8", "ignore").strip()
                reading_with_labels = self.format_control_chars(reading)
            else:  # HEX mode
                reading_with_labels = " ".join(f"{byte:02X}" for byte in buffer)
            
            if reading_with_labels:
                timestamp = datetime.now().strftime("[%H:%M:%S.%f]")[:-4] + "]"
                
                # Use queue with timeout to prevent blocking
                try:
                    self.data_queue.put((timestamp, reading_with_labels), timeout=0.1)
                except queue.Full:
                    # If queue is full, remove oldest item and add new one
                    try:
                        self.data_queue.get_nowait()
                        self.data_queue.put((timestamp, reading_with_labels), timeout=0.1)
                    except (queue.Empty, queue.Full):
                        pass  # Skip this data if still can't add
                        
        except Exception as e:
            logger.error(f"Error processing received data: {e}")
    
    def format_control_chars(self, text):
        """Format control characters for display"""
        result = ""
        i = 0
        while i < len(text):
            if text[i] == '\r':
                if i + 1 < len(text) and text[i + 1] == '\n':
                    result += '<CRLF>\r\n'
                    i += 2
                else:
                    result += '<CR>\r'
                    i += 1
            elif text[i] == '\n':
                result += '<LF>\n'
                i += 1
            else:
                result += text[i]
                i += 1
        return result
    
    def start_gui_processor(self):
        """Start the GUI update processor with adaptive timing"""
        self.process_display_queue()
    
    def process_display_queue(self):
        """Process display queue with adaptive timing and batching"""
        batch_size = 0
        max_batch_size = 20
        
        # Process multiple items in one GUI update for better performance
        while not self.data_queue.empty() and batch_size < max_batch_size:
            try:
                timestamp, text = self.data_queue.get_nowait()
                self.add_to_display(timestamp, text)
                batch_size += 1
            except queue.Empty:
                break
        
        # Manage text widget size to prevent memory issues
        if batch_size > 0:
            self.manage_text_widget_size()
        
        # Adaptive timing based on queue size
        queue_size = self.data_queue.qsize()
        if queue_size > 50:
            interval = 20  # Fast updates when busy
        elif queue_size > 10:
            interval = 30
        else:
            interval = 50  # Slower updates when idle
        
        self.after(interval, self.process_display_queue)
    
    def add_to_display(self, timestamp, text):
        """Add data to display with filtering"""
        filter_text = self.filter_var.get().lower()
        
        if filter_text and filter_text in text.lower():
            # Filtered text with highlighting
            self.serial_text.insert(tk.END, '\n' + timestamp, 'timestamp')
            start_index = text.lower().find(filter_text)
            end_index = start_index + len(filter_text)
            self.serial_text.insert(tk.END, text[:start_index])
            self.serial_text.insert(tk.END, text[start_index:end_index], 'filtered')
            self.serial_text.insert(tk.END, text[end_index:])
            self.serial_text.see(tk.END)
        elif not filter_text:
            # Normal display
            self.serial_text.insert(tk.END, '\n' + timestamp, 'timestamp')
            self.serial_text.insert(tk.END, text)
            self.serial_text.see(tk.END)
        
        # Store in circular buffer
        self.display_buffer.append((timestamp, text))
    
    def add_status_message(self, message, tag='timestamp'):
        """Add a status message to the display"""
        timestamp = datetime.now().strftime("[%H:%M:%S.%f]")[:-4] + "]"
        self.serial_text.insert(tk.END, f'\n{timestamp} {message}', tag)
        self.serial_text.see(tk.END)
    
    def manage_text_widget_size(self):
        """Manage text widget size to prevent excessive memory usage"""
        try:
            line_count = int(self.serial_text.index('end').split('.')[0])
            max_lines = 5000
            
            if line_count > max_lines:
                # Remove first 1000 lines to keep widget responsive
                self.serial_text.delete('1.0', f'{1000}.0')
        except Exception as e:
            logger.error(f"Error managing text widget size: {e}")
    
    def clear_text(self):
        """Clear all text displays and buffers"""
        self.serial_text.delete(1.0, tk.END)
        self.display_buffer.clear()
        
        # Clear any pending queue items
        while not self.data_queue.empty():
            try:
                self.data_queue.get_nowait()
            except queue.Empty:
                break
    
    def save_text(self):
        """Save text with enhanced error handling"""
        try:
            now = datetime.now()
            downloads_folder = os.path.join(os.path.expanduser("~"), "Downloads")
            default_filename = f"CH{self.quadrant_number}_{now.strftime('%y%m%d_%H%M%S')}.txt"
            
            file_path = filedialog.asksaveasfilename(
                initialdir=downloads_folder,
                defaultextension=".txt",
                filetypes=[("Text file", "*.txt"), ("All files", "*.*")],
                initialfile=default_filename
            )
            
            if file_path:
                with open(file_path, 'w', encoding='utf-8') as file:
                    text_to_save = self.serial_text.get(1.0, tk.END)
                    file.write(text_to_save)
                
                self.add_status_message(f"Log salvo: {os.path.basename(file_path)}", 'timestamp')
                
        except Exception as e:
            logger.error(f"Error saving file: {e}")
            messagebox.showerror("Erro", f"Erro ao salvar arquivo: {str(e)}")
    
    def toggle_display_mode(self):
        """Toggle between ASCII and HEX display modes"""
        if self.display_mode.get() == "ASCII":
            self.display_mode.set("HEX")
            self.toggle_display_button.config(bg='yellow')
        else:
            self.display_mode.set("ASCII")
            self.toggle_display_button.config(bg=self.cget('bg'))
    
    def start_send_data_thread(self):
        """Start send operation using thread pool"""
        if not self.serial_manager.is_connected:
            messagebox.showerror("Erro de envio", "Primeiro conecte à porta serial.")
            return
        
        if not self.send_text_var.get():
            messagebox.showerror("Erro de envio", "Não há texto para envio.")
            return
        
        # Use thread pool to avoid creating new threads constantly
        future = self.send_executor.submit(self.send_data)
        
        # Optional: Add error handling for the future
        def handle_send_result(future):
            try:
                future.result()  # This will raise any exception that occurred
            except Exception as e:
                logger.error(f"Send operation failed: {e}")
                self.after_idle(lambda: messagebox.showerror("Erro de envio", f"Erro ao enviar: {str(e)}"))
        
        future.add_done_callback(handle_send_result)
    
    def send_data(self):
        """Enhanced send data function"""
        try:
            if not self.serial_manager.is_connected:
                return False
            
            data = self.send_text_var.get()
            if not data:
                return False
            
            # Prepare data based on display mode
            if self.display_mode.get() == "HEX":
                try:
                    data_bytes = bytes.fromhex(data.replace(' ', ''))
                except ValueError:
                    self.after_idle(lambda: messagebox.showerror("Erro de envio", 
                                   "Formato HEX inválido. Use pares de caracteres separados por espaço."))
                    return False
            else:
                data_bytes = data.encode('utf-8')
            
            # Add CRLF if requested
            if self.crlf_var.get():
                data_bytes += b'\r\n'
            
            # Send data
            bytes_sent = self.serial_manager.write(data_bytes)
            
            if bytes_sent > 0:
                # Display sent data
                timestamp = datetime.now().strftime("[%H:%M:%S.%f]")[:-4] + "]"
                if self.display_mode.get() == "HEX":
                    display_text = ' '.join([f"{b:02X}" for b in data_bytes])
                else:
                    display_text = data_bytes.decode("utf-8", "ignore")
                
                self.after_idle(lambda: self.add_sent_message(timestamp, display_text))
                return True
            else:
                self.after_idle(lambda: messagebox.showerror("Erro de envio", "Nenhum byte foi enviado."))
                return False
                
        except Exception as e:
            logger.error(f"Send error: {e}")
            self.after_idle(lambda: messagebox.showerror("Erro de envio", f"Erro ao enviar dados: {str(e)}"))
            return False
    
    def add_sent_message(self, timestamp, text):
        """Add sent message to display"""
        self.serial_text.insert(tk.END, f'\n{timestamp} TX: {text}', 'sent')
        self.serial_text.see(tk.END)
    
    def toggle_send_every_1s(self):
        """Toggle periodic sending with proper thread management"""
        if self.send_every_1s_var.get():
            if not self.serial_manager.is_connected:
                messagebox.showerror("Erro de envio", "Primeiro conecte à porta serial.")
                self.send_every_1s_var.set(False)
                return
            
            if not self.send_text_var.get():
                messagebox.showerror("Erro de envio", "Não há texto para envio.")
                self.send_every_1s_var.set(False)
                return
            
            # Start periodic sending thread
            self.periodic_send_thread = threading.Thread(target=self.send_data_every_1s,
                                                        name=f"PeriodicSend-Q{self.quadrant_number}")
            self.periodic_send_thread.start()
        else:
            # Stop periodic sending (thread will check the variable and exit)
            pass
    
    def send_data_every_1s(self):
        """Periodic send function with proper shutdown handling"""
        while self.send_every_1s_var.get() and self.running and not self.shutdown_event.is_set():
            if self.serial_manager.is_connected:
                self.send_data()
            
            # Sleep in small increments to allow for responsive shutdown
            for _ in range(10):
                if not self.send_every_1s_var.get() or self.shutdown_event.is_set():
                    break
                time.sleep(0.1)
    
    def on_destroy(self, event=None):
        """Cleanup when widget is destroyed"""
        if event and event.widget != self:
            return
        
        self.cleanup()
    
    def cleanup(self):
        """Comprehensive cleanup of resources"""
        logger.info(f"Cleaning up quadrant {self.quadrant_number}")
        
        try:
            # Stop all operations immediately
            self.running = False
            self.shutdown_event.set()
            self.send_every_1s_var.set(False)
            
            # Cancel any pending after() calls
            try:
                self.after_cancel('all')
            except:
                pass
            
            # Force disconnect serial first
            try:
                self.serial_manager.disconnect()
            except:
                pass
            
            # Cleanup threads with shorter timeout
            if self.reading_thread and self.reading_thread.is_alive():
                self.reading_thread.join(timeout=0.5)
            
            if self.periodic_send_thread and self.periodic_send_thread.is_alive():
                self.periodic_send_thread.join(timeout=0.5)
            
            # Force shutdown thread pool
            if hasattr(self, 'send_executor'):
                try:
                    self.send_executor.shutdown(wait=False)
                except:
                    pass
            
            # Clear queues and buffers
            try:
                while not self.data_queue.empty():
                    try:
                        self.data_queue.get_nowait()
                    except queue.Empty:
                        break
                self.display_buffer.clear()
            except:
                pass
                
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


class SerialCollectorApp(tk.Tk):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.title("SETERA - Coletor Serial 2 Canais")
        self.state("zoomed")
        
        # Create quadrants
        self.quadrant1 = SerialCollectorQuadrant(self, 1)
        self.quadrant1.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)
        
        self.quadrant2 = SerialCollectorQuadrant(self, 2)
        self.quadrant2.grid(row=0, column=1, sticky="nsew", padx=2, pady=2)
        
        # Grid configuration
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        
        # Handle window closing
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def on_closing(self):
        """Handle application closing with improved shutdown"""
        logger.info("Application closing...")
        
        try:
            # Set a shorter timeout for cleanup
            if hasattr(self, 'quadrant1'):
                self.quadrant1.cleanup()
            if hasattr(self, 'quadrant2'):
                self.quadrant2.cleanup()
            
            # Force quit after a short delay if normal shutdown fails
            self.after(3000, self.force_quit)
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            self.force_quit()
        
        self.destroy()
    
    def force_quit(self):
        """Force application termination"""
        logger.info("Force quitting application")
        try:
            self.quit()
        except:
            pass
        import sys
        sys.exit(0)


if __name__ == "__main__":
    try:
        app = SerialCollectorApp()
        
        # Set icon if available
        script_dir = os.path.dirname(os.path.realpath(__file__))
        icon_path = os.path.join(script_dir, 'favicon.ico')
        if os.path.exists(icon_path):
            app.iconbitmap(icon_path)
        
        logger.info("Starting Serial Collector Application")
        app.mainloop()
        
    except Exception as e:
        logger.error(f"Application error: {e}")
        messagebox.showerror("Erro Fatal", f"Erro na aplicação: {str(e)}")
    
    finally:
        logger.info("Application terminated")