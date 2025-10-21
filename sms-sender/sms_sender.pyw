"""
Sistema de Envio de SMS - v2.1.2 - 20Out2025
Ferramenta de Automação para Configuração de Equipamentos GPS
Interface Gráfica Moderna usando ttkbootstrap
Arduino + Shield SIM800C
✨ v2.0: Integração com API SETERA para seleção segura de dispositivos STR-CAM
✨ v2.1: Multi-seleção de placas no modo "Adicionar Comando"
✨ v2.1.2: UX improvements - auto-fill SIMs, fix focus loss, simplified UI
"""

# ============================================================================
# UAC ELEVATION - Request Administrator Privileges
# ============================================================================
import sys
import ctypes
import os

def is_admin():
    """Check if the script is running with administrator privileges"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def request_admin():
    """Request UAC elevation and restart the script as administrator"""
    if not is_admin():
        # Re-run the program with admin rights
        try:
            # Get the path to the Python executable
            if getattr(sys, 'frozen', False):
                # Running as compiled exe (PyInstaller)
                script = sys.executable
                params = ' '.join([f'"{arg}"' for arg in sys.argv[1:]])
            else:
                # Running as .pyw script
                script = sys.executable
                params = f'"{os.path.abspath(__file__)}"'

            # Request elevation using ShellExecute
            ctypes.windll.shell32.ShellExecuteW(
                None,           # hwnd
                "runas",        # operation (triggers UAC prompt)
                script,         # file to execute
                params,         # parameters
                None,           # directory
                1               # SW_SHOWNORMAL
            )
            sys.exit(0)  # Exit the non-elevated instance
        except Exception as e:
            # User cancelled UAC or error occurred
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()  # Hide the root window
            messagebox.showerror(
                "Permissões Necessárias",
                f"Este programa requer privilégios de administrador.\n\nErro: {e}"
            )
            sys.exit(1)
    # If already admin, continue normally

# Request admin privileges on startup
request_admin()

# ============================================================================
# MAIN IMPORTS
# ============================================================================

import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.scrolled import ScrolledText
from ttkbootstrap.dialogs import Messagebox
import serial
import serial.tools.list_ports
import threading
import queue
import time
import json
import os
from datetime import datetime
from enum import Enum
import tkinter  # For Listbox widget

# SETERA API Integration
from setera_api import SeteraAPIManager, format_terminal_for_display, search_terminals

# ============================================================================
# CONFIGURATION
# ============================================================================

CONFIG_FILE = 'sms_config.json'
LOG_FILE = 'sms_automation.log'

class CameraStatus(Enum):
    PENDING = "pending"
    SENDING = "sending"
    WAITING = "waiting"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    UNKNOWN_RESPONSE = "unknown_response"

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def format_elapsed_time(seconds):
    """
    Format elapsed time in smart, simplified units
    - Less than 1 minute: Xs (e.g., 45s)
    - 1 minute to 1 hour: XmYs (e.g., 2m30s)
    - 1 hour to 1 day: XhYm (no seconds) (e.g., 1h15m)
    - More than 1 day: XdYh (no minutes/seconds) (e.g., 2d5h)
    """
    if seconds < 0:
        return "0s"

    days = int(seconds // 86400)
    hours = int((seconds % 86400) // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    if days > 0:
        # More than 1 day: XdYh (no minutes/seconds)
        return f"{days}d{hours}h"
    elif hours > 0:
        # 1 hour to 1 day: XhYm (no seconds)
        return f"{hours}h{minutes}m"
    elif minutes > 0:
        # 1 minute to 1 hour: XmYs
        return f"{minutes}m{secs}s"
    else:
        # Less than 1 minute: Xs
        return f"{secs}s"

# ============================================================================
# SERIAL COMMUNICATION THREAD
# ============================================================================

class SerialWorker(threading.Thread):
    def __init__(self, port, baudrate, command_queue, response_queue, log_queue):
        super().__init__(daemon=True)
        self.port = port
        self.baudrate = baudrate
        self.command_queue = command_queue    # Receive commands from GUI
        self.response_queue = response_queue  # Send responses to GUI
        self.log_queue = log_queue
        self.serial = None
        self.running = True
        self.connected = False
        self.validated = False
        
    def log(self, message, level="INFO"):
        """Send log message to GUI"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.log_queue.put((level, f"[{timestamp}] {message}"))
    
    def run(self):
        """Main worker thread"""
        try:
            # Open serial port
            self.log(f"Abrindo porta {self.port} a {self.baudrate} baud...")
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=1,
                write_timeout=1,
                rtscts=False,      # Disable RTS/CTS flow control
                dsrdtr=False,      # Disable DTR/DSR flow control
                xonxoff=False      # Disable software flow control
            )
            self.connected = True
            self.log("✓ Conectado ao Arduino + SIM800C", "SUCCESS")

            # Wait for Arduino to reset and initialize (DTR triggers reset on connection)
            self.log("Aguardando inicialização do Arduino...", "INFO")
            time.sleep(3)  # Increased from 2 to 3 seconds

            # Clear any startup messages
            self.serial.reset_input_buffer()
            self.serial.reset_output_buffer()
            
            # Process commands from queue
            while self.running:
                try:
                    # Get command from queue (non-blocking with timeout)
                    cmd = self.command_queue.get(timeout=0.1)
                    
                    if cmd['type'] == 'STOP':
                        break
                    elif cmd['type'] == 'AT_COMMAND':
                        self.send_at_command(cmd['command'], cmd.get('wait_time', 1))
                    elif cmd['type'] == 'VALIDATE_CONNECTION':
                        self.validate_connection()
                    elif cmd['type'] == 'GET_MODULE_INFO':
                        self.get_module_info()
                    elif cmd['type'] == 'SEND_SMS':
                        self.send_sms(cmd['number'], cmd['message'], cmd['camera_name'], cmd['command_index'])
                    elif cmd['type'] == 'CHECK_ALL_SMS':
                        self.check_all_sms()
                    elif cmd['type'] == 'DELETE_ALL_SMS':
                        self.delete_all_sms()
                    elif cmd['type'] == 'GET_CSQ_ONLY':
                        self.get_csq_only()
                        
                except queue.Empty:
                    continue
                    
        except serial.SerialException as e:
            self.log(f"✗ Erro na porta serial: {e}", "ERROR")
            self.connected = False
        except Exception as e:
            self.log(f"✗ Erro inesperado: {e}", "ERROR")
        finally:
            if self.serial and self.serial.is_open:
                self.serial.close()
                self.log("Porta serial fechada", "INFO")
    
    def send_at_command(self, command, wait_time=1, log_command=True):
        """Send AT command and return response"""
        if not self.serial or not self.serial.is_open:
            return ""

        # Clear buffers
        self.serial.reset_input_buffer()
        self.serial.reset_output_buffer()

        # Log command being sent
        if log_command:
            self.log(f"→ TX: {command}", "INFO")

        # Send command
        cmd_bytes = (command + '\r\n').encode()
        self.serial.write(cmd_bytes)
        self.serial.flush()  # Ensure data is sent

        # Wait for response with multiple read attempts
        response = ''
        start_time = time.time()

        while time.time() - start_time < wait_time + 1:
            waiting = self.serial.in_waiting
            if waiting > 0:
                chunk = self.serial.read(waiting).decode('utf-8', errors='ignore')
                response += chunk

                # If we got OK or ERROR, we have the complete response
                if 'OK' in response or 'ERROR' in response:
                    break

            time.sleep(0.1)

        # Log response received
        if log_command and response:
            # Clean up response for display
            clean_response = response.replace('\r', '').replace('\n', ' ').strip()
            self.log(f"← RX: {clean_response}", "INFO")
        elif log_command:
            self.log(f"← RX: (sem resposta após {wait_time}s)", "WARNING")

        return response
    
    def send_sms(self, number, message, camera_name, command_index):
        """Send SMS to specified number"""
        self.log(f"📤 Iniciando envio de SMS para {number} ({camera_name})...", "INFO")

        # Set SMS mode to text mode first
        self.log(f"→ TX: AT+CMGF=1", "INFO")
        self.serial.reset_input_buffer()
        self.serial.reset_output_buffer()
        self.serial.write(b'AT+CMGF=1\r\n')
        time.sleep(0.5)

        # Read response
        mode_response = ''
        if self.serial.in_waiting:
            mode_response = self.serial.read(self.serial.in_waiting).decode('utf-8', errors='ignore')
            clean = mode_response.replace('\r', '').replace('\n', ' ').strip()
            self.log(f"← RX: {clean}", "INFO")

        # Start SMS
        self.serial.reset_input_buffer()
        self.serial.reset_output_buffer()

        command = f'AT+CMGS="{number}"'
        self.log(f"→ TX: {command}", "INFO")
        self.serial.write((command + '\r\n').encode())
        self.serial.flush()

        # Wait for '>' prompt
        response = ''
        self.log(f"Aguardando prompt '>'...", "INFO")

        for i in range(20):  # Increased from 10 to 20 attempts
            if self.serial.in_waiting:
                chunk = self.serial.read(self.serial.in_waiting).decode('utf-8', errors='ignore')
                response += chunk
                self.log(f"← RX: {repr(chunk)}", "INFO")

                if '>' in response:
                    self.log(f"✓ Prompt '>' recebido", "SUCCESS")
                    break
            time.sleep(0.5)

        if '>' not in response:
            clean_resp = response.replace('\r', '').replace('\n', ' ').strip()
            self.log(f"✗ Sem prompt '>'. Resposta: '{clean_resp}'", "ERROR")
            self.response_queue.put({'type': 'SMS_RESULT', 'camera_name': camera_name, 'command_index': command_index, 'success': False})
            return
        
        # Send message content
        self.log(f"→ TX: {message}", "INFO")
        self.serial.write(message.encode('utf-8'))
        self.serial.flush()
        time.sleep(0.5)

        # Send Ctrl+Z to finalize
        self.log(f"→ TX: <Ctrl+Z> (0x1A)", "INFO")
        self.serial.write(bytes([26]))
        self.serial.flush()

        # Wait for result
        response = ''
        start_time = time.time()
        self.log(f"Aguardando confirmação de envio...", "INFO")

        while time.time() - start_time < 60:
            if self.serial.in_waiting:
                chunk = self.serial.read(self.serial.in_waiting).decode('utf-8', errors='ignore')
                response += chunk

                # Log each chunk received
                clean_chunk = chunk.replace('\r', '').replace('\n', ' ').strip()
                if clean_chunk:
                    self.log(f"← RX: {clean_chunk}", "INFO")

                if '+CMGS:' in response:
                    self.log(f"✓ SMS enviado com sucesso para {camera_name}", "SUCCESS")
                    self.response_queue.put({'type': 'SMS_RESULT', 'camera_name': camera_name, 'command_index': command_index, 'success': True})
                    return

                if 'ERROR' in response or 'CMS ERROR' in response:
                    clean_error = response.replace('\r', '').replace('\n', ' ').strip()
                    self.log(f"✗ Erro ao enviar SMS para {camera_name}: {clean_error}", "ERROR")
                    self.response_queue.put({'type': 'SMS_RESULT', 'camera_name': camera_name, 'command_index': command_index, 'success': False})
                    return

            time.sleep(0.5)

        self.log(f"✗ Timeout (60s) ao aguardar confirmação de envio para {camera_name}", "ERROR")
        self.response_queue.put({'type': 'SMS_RESULT', 'camera_name': camera_name, 'command_index': command_index, 'success': False})
    
    def validate_connection(self):
        """Validate connection by sending AT command"""
        response = self.send_at_command('AT', wait_time=3)

        if response and 'OK' in response:
            self.validated = True
            self.log("✓ Módulo validado com sucesso", "SUCCESS")
        else:
            self.validated = False
            self.log("✗ Módulo não responde aos comandos AT", "ERROR")
            # Show response for troubleshooting
            self.log(f"Resposta recebida: {repr(response)}", "ERROR")

    def get_module_info(self):
        """Get module information (CSQ)"""
        csq = None

        # Get signal quality (CSQ)
        self.log("Consultando qualidade do sinal...", "INFO")
        response = self.send_at_command('AT+CSQ', wait_time=1)
        if response and '+CSQ:' in response:
            # Parse CSQ response: +CSQ: 15,0
            try:
                import re
                match = re.search(r'\+CSQ:\s*(\d+),', response)
                if match:
                    csq = int(match.group(1))
                    # Use same mapping as GUI for consistency
                    if csq == 99:
                        signal_text = "Sem sinal"
                        self.log(f"⚠ Sinal GSM: {csq} ({signal_text})", "WARNING")
                    elif csq >= 20:
                        signal_text = "Excelente"
                        self.log(f"✓ Sinal GSM: {csq} ({signal_text})", "SUCCESS")
                    elif csq >= 15:
                        signal_text = "Bom"
                        self.log(f"✓ Sinal GSM: {csq} ({signal_text})", "SUCCESS")
                    elif csq >= 10:
                        signal_text = "OK"
                        self.log(f"✓ Sinal GSM: {csq} ({signal_text})", "SUCCESS")
                    elif csq >= 5:
                        signal_text = "Fraco"
                        self.log(f"⚠ Sinal GSM: {csq} ({signal_text})", "WARNING")
                    else:
                        signal_text = "Muito fraco"
                        self.log(f"⚠ Sinal GSM: {csq} ({signal_text})", "WARNING")
            except:
                self.log("⚠ Erro ao processar sinal", "WARNING")

        # Send info back to GUI
        self.response_queue.put({
            'type': 'MODULE_INFO',
            'csq': csq
        })

    def get_csq_only(self):
        """Get signal quality only (for periodic polling) - silent mode"""
        response = self.send_at_command('AT+CSQ', wait_time=1, log_command=False)
        if response and '+CSQ:' in response:
            try:
                import re
                match = re.search(r'\+CSQ:\s*(\d+),', response)
                if match:
                    csq = int(match.group(1))
                    # Send CSQ-only update to GUI silently (no logging)
                    self.response_queue.put({
                        'type': 'CSQ_UPDATE',
                        'csq': csq
                    })
            except:
                pass  # Silently ignore errors during background polling

    def delete_all_sms(self):
        """Delete all SMS messages from SIM card"""
        self.log("Limpando mensagens antigas do SIM...", "INFO")
        # Delete all read and unread messages
        response = self.send_at_command('AT+CMGD=1,4', wait_time=3)
        if 'OK' in response:
            self.log("✓ Mensagens antigas removidas", "SUCCESS")
        else:
            self.log("⚠ Não foi possível limpar mensagens antigas", "WARNING")

    def check_all_sms(self):
        """Check for ALL incoming SMS and return with sender phone numbers"""
        response = self.send_at_command('AT+CMGL="REC UNREAD"', wait_time=2, log_command=False)

        messages = []
        if '+CMGL:' in response:
            # Parse SMS content
            # Format: +CMGL: <index>,"REC UNREAD","<sender>","","<timestamp>"
            #         <message text>
            import re
            try:
                lines = response.split('\n')
                i = 0
                while i < len(lines):
                    line = lines[i]
                    if '+CMGL:' in line:
                        # Parse sender from +CMGL line
                        # Format: +CMGL: 1,"REC UNREAD","+5511999999999","","25/01/19,10:30:45-12"
                        sender_match = re.search(r'\+CMGL:\s*\d+,"[^"]*","([^"]+)"', line)
                        if sender_match and i + 1 < len(lines):
                            sender = sender_match.group(1)
                            message_text = lines[i + 1].strip()
                            if message_text:
                                messages.append({
                                    'sender': sender,
                                    'message': message_text
                                })
                                self.log(f"📩 SMS de {sender}: '{message_text}'", "INFO")
                    i += 1
            except Exception as e:
                self.log(f"⚠ Erro ao processar SMS: {e}", "WARNING")

        # Send all messages to GUI for matching
        self.response_queue.put({
            'type': 'SMS_BATCH',
            'messages': messages
        })

# ============================================================================
# MAIN APPLICATION GUI
# ============================================================================

class SMSAutomationApp(ttk.Window):
    def __init__(self):
        super().__init__(themename="darkly")  # Modern dark theme

        self.title("Sistema Automatizado de Envio de Comandos SMS - v2.3 - 20Out2025")
        self.geometry("1200x800")

        # Set application icon
        try:
            self.iconbitmap("favicon.ico")
            # Set default icon for all Toplevel windows (including Messagebox)
            self.tk.call('wm', 'iconbitmap', self._w, "favicon.ico")
        except:
            pass  # Ignore if icon file not found

        # Maximize window on startup
        self.state('zoomed')  # Windows
        # For cross-platform compatibility
        try:
            self.attributes('-zoomed', True)  # Linux
        except:
            pass
        
        # Queues for thread communication
        self.command_queue = queue.Queue()   # GUI -> Worker (commands)
        self.response_queue = queue.Queue()  # Worker -> GUI (responses)
        self.log_queue = queue.Queue()       # Worker -> GUI (logs)

        # Worker thread
        self.worker = None

        # Module info
        self.module_msisdn = None
        self.module_csq = None

        # Track SMS send time for timeout
        self.sms_send_time = {}
        self.last_warning_time = {}  # Track last 6-hour warning shown per command
        self.retry_count = {}        # Track retry attempts per command

        # Timeout/Warning configuration (in HOURS)
        # CRITICAL: Maintain 4:1 ratio (RETRY = 4 × WARNING) for correct 24h display intervals!
        #
        # PRODUCTION (warnings every 6h real, retries every 24h real):
        #   self.WARNING_INTERVAL_HOURS = 6
        #   self.RETRY_INTERVAL_HOURS = 24
        #   Ratio: 24/6 = 4 → Retries display as 24h, 48h, 72h... ✓
        #
        # TESTING (warnings every 30s real, retries every 2min real):
        #   self.WARNING_INTERVAL_HOURS = 0.00833   # 30 seconds
        #   self.RETRY_INTERVAL_HOURS = 0.0333      # 2 minutes (120 seconds)
        #   Ratio: 0.0333/0.00833 = 4 → Retries display as 24h, 48h, 72h... ✓
        #
        self.WARNING_INTERVAL_HOURS = 6      # PRODUCTION mode (6 hours)
        self.RETRY_INTERVAL_HOURS = 24       # PRODUCTION mode (24 hours)

        # CSQ polling
        self.csq_polling_active = False

        # Application state
        self.cameras = []
        self.is_running = False
        self.is_paused = False

        # Clear log file at start of each session (non-accumulative logging)
        try:
            with open(LOG_FILE, 'w', encoding='utf-8') as f:
                f.write('')  # Clear the file
        except:
            pass  # Ignore if file doesn't exist or can't be written

        # Load command patterns FIRST (before loading config/creating widgets)
        self.command_patterns = []
        self.load_command_patterns(silent=True)  # Silent - log_text doesn't exist yet

        # Load configuration
        self.load_config()

        # Initialize API Manager for STR-CAM terminal fetching
        self.api_manager = SeteraAPIManager(log_callback=None)  # Will set callback after GUI created
        self.str_cam_terminals = []  # Cache for STR-CAM terminals
        self.api_authenticated = False

        # Build GUI
        self.create_widgets()

        # Now that log_text exists, log the command patterns status
        if len(self.command_patterns) > 0:
            self.add_log(f"✓ Carregados {len(self.command_patterns)} tipos de comando", "SUCCESS")
        else:
            self.add_log("⚠ Nenhum padrão de comando encontrado", "WARNING")

        # Set API log callback now that log_text exists
        self.api_manager.log_callback = self.api_log_callback

        # Start API authentication in background thread
        self.add_log("🔐 Iniciando autenticação com API SETERA...", "INFO")
        auth_thread = threading.Thread(target=self.authenticate_api_startup, daemon=True)
        auth_thread.start()

        # Start checking for log messages
        self.check_log_queue()

        # Start auto-refresh COM ports
        self.auto_refresh_ports()

    # ==================== COMMAND PATTERN MATCHING ====================

    def load_command_patterns(self, silent=False):
        """Load command patterns from JSON configuration file
        Args:
            silent: If True, don't log messages (for initialization before widgets exist)
        """
        patterns_file = 'command_patterns.json'
        try:
            if os.path.exists(patterns_file):
                with open(patterns_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.command_patterns = data.get('command_types', [])
                    if not silent:
                        self.add_log(f"✓ Carregados {len(self.command_patterns)} tipos de comando", "SUCCESS")
            else:
                self.command_patterns = []
                if not silent:
                    self.add_log("⚠ Arquivo command_patterns.json não encontrado", "WARNING")
        except Exception as e:
            self.command_patterns = []
            if not silent:
                self.add_log(f"⚠ Erro ao carregar padrões de comando: {e}", "WARNING")

    def identify_command_type(self, command):
        """
        Identify command type based on pattern matching
        Args:
            command: Full command string
        Returns:
            Command type ID (str) or None if no match
        """
        if not command:
            return None

        for cmd_type in self.command_patterns:
            pattern = cmd_type.get('pattern', '')
            case_sensitive = cmd_type.get('case_sensitive', True)

            if case_sensitive:
                if pattern in command:
                    return cmd_type['id']
            else:
                if pattern.lower() in command.lower():
                    return cmd_type['id']

        return None

    def validate_response(self, command_type, response_text):
        """
        Validate SMS response against expected patterns
        Args:
            command_type: Command type ID
            response_text: Received SMS text
        Returns:
            Tuple (status, matched_pattern)
            - ("success", pattern) if success pattern matched
            - ("failure", pattern) if failure pattern matched
            - ("unknown", None) if no pattern matched

        Pattern Handling Logic:
        1. If response matches failure_pattern → FAILURE
        2. If response matches success_pattern → SUCCESS
        3. If both arrays are empty → SUCCESS (any response accepted)
        4. If only failure_patterns exist → SUCCESS (anything not explicitly an error is good)
        5. If only success_patterns exist → UNKNOWN (must match defined success pattern)
        6. If both exist and neither matched → UNKNOWN (keep waiting for expected response)
        """
        if not command_type or not response_text:
            return ("unknown", None)

        # Find command type config
        cmd_config = next((c for c in self.command_patterns if c['id'] == command_type), None)
        if not cmd_config:
            return ("unknown", None)

        case_sensitive = cmd_config.get('case_sensitive', True)

        # Check failure patterns first (priority)
        failure_patterns = cmd_config.get('failure_patterns', [])
        for pattern in failure_patterns:
            if case_sensitive:
                if pattern in response_text:
                    return ("failure", pattern)
            else:
                if pattern.lower() in response_text.lower():
                    return ("failure", pattern)

        # Check success patterns
        success_patterns = cmd_config.get('success_patterns', [])
        for pattern in success_patterns:
            if case_sensitive:
                if pattern in response_text:
                    return ("success", pattern)
            else:
                if pattern.lower() in response_text.lower():
                    return ("success", pattern)

        # Handle cases where patterns are missing or empty
        has_success_patterns = success_patterns and len(success_patterns) > 0
        has_failure_patterns = failure_patterns and len(failure_patterns) > 0

        # Case 1: Both arrays empty → Any response is success
        if not has_success_patterns and not has_failure_patterns:
            return ("success", None)

        # Case 2: Only failure patterns exist (no success patterns) → Anything not matching failure is success
        if not has_success_patterns and has_failure_patterns:
            return ("success", None)  # We already checked failures above, none matched

        # Case 3: Only success patterns exist (no failure patterns) → Must match success pattern
        if has_success_patterns and not has_failure_patterns:
            return ("unknown", None)  # Response didn't match any success pattern, keep waiting

        # Case 4: Both exist and neither matched → Unknown response, keep waiting
        return ("unknown", None)

    def create_widgets(self):
        """Create all GUI widgets"""
        
        # ==================== SETTINGS SECTION ====================
        settings_frame = ttk.Labelframe(self, text="⚙️ Configurações", padding=15)
        settings_frame.pack(fill=X, padx=10, pady=(15, 5))

        # COM Port
        port_frame = ttk.Frame(settings_frame)
        port_frame.pack(fill=X, pady=5)

        self.port_var = ttk.StringVar(value=self.config.get('port', 'COM3'))
        self.port_combo = ttk.Combobox(
            port_frame,
            textvariable=self.port_var,
            values=self.get_available_ports(),
            width=12,
            bootstyle="primary"
        )
        self.port_combo.pack(side=LEFT, padx=(0, 5))

        self.connect_btn = ttk.Button(
            port_frame,
            text="🔌 Conectar",
            command=self.toggle_connection,
            bootstyle="success-outline",
            width=14
        )
        self.connect_btn.pack(side=LEFT, padx=8)

        ttk.Button(
            port_frame,
            text="🧹 Limpar Log",
            command=self.clear_log,
            bootstyle="warning-outline",
            width=17
        ).pack(side=LEFT, padx=8)

        ttk.Button(
            port_frame,
            text="💾 Exportar Log",
            command=self.export_log,
            bootstyle="info-outline",
            width=17
        ).pack(side=LEFT, padx=8)

        # API Status indicator
        self.api_status_label = ttk.Label(
            port_frame,
            text="🔐 API: Autenticando...",
            font=("Segoe UI", 9),
            foreground="#ffd43b"  # Yellow/warning color
        )
        self.api_status_label.pack(side=LEFT, padx=15)

        # ==================== EQUIPMENT SECTION ====================
        cameras_frame = ttk.Labelframe(self, text="📱 Controle de envios e respostas", padding=15)
        cameras_frame.pack(fill=BOTH, expand=True, padx=10, pady=5)
        
        # Buttons
        btn_frame = ttk.Frame(cameras_frame)
        btn_frame.pack(fill=X, pady=(0, 10))
        
        ttk.Button(
            btn_frame,
            text="➕ Adicionar",
            command=self.add_camera,
            bootstyle="success-outline",
            width=13
        ).pack(side=LEFT, padx=8)

        ttk.Button(
            btn_frame,
            text="✏️ Editar",
            command=self.edit_camera,
            bootstyle="info-outline",
            width=11
        ).pack(side=LEFT, padx=8)

        ttk.Button(
            btn_frame,
            text="❌ Remover",
            command=self.remove_camera,
            bootstyle="danger-outline",
            width=11
        ).pack(side=LEFT, padx=8)

        ttk.Button(
            btn_frame,
            text="❌ Remover Todos",
            command=self.remove_all_cameras,
            bootstyle="danger-outline",
            width=17
        ).pack(side=LEFT, padx=8)

        ttk.Button(
            btn_frame,
            text="📋 Importar Arquivo",
            command=self.import_cameras,
            bootstyle="warning-outline",
            width=19
        ).pack(side=LEFT, padx=8)

        # Signal strength (CSQ) - aligned to the right
        self.signal_label = ttk.Label(
            btn_frame,
            text="Sinal GSM: --",
            font=("Helvetica", 10)
        )
        self.signal_label.pack(side=RIGHT, padx=10)

        # Camera list (Treeview)
        columns = ('id', 'name', 'phone', 'status', 'command_type', 'result')
        self.camera_tree = ttk.Treeview(
            cameras_frame,
            columns=columns,
            show='headings',
            height=6,  # Reduced from 10 to give more space to log
            bootstyle="primary",
            selectmode='extended'  # Enable multi-select (Ctrl+Click, Shift+Click)
        )

        # Configure column header style to show dividers
        # For ttkbootstrap, we need to target the specific bootstyle
        style = ttk.Style()
        style.configure("primary.Treeview.Heading",
                       borderwidth=1,
                       relief="solid",
                       padding=(0, 2))

        # Also configure the row borders to show divisions
        style.configure("primary.Treeview",
                       rowheight=25)

        # Column headings
        self.camera_tree.heading('id', text='#', anchor=CENTER)
        self.camera_tree.heading('name', text='Placa', anchor=CENTER)
        self.camera_tree.heading('phone', text='Número SIM Card', anchor=CENTER)
        self.camera_tree.heading('status', text='Status', anchor=CENTER)
        self.camera_tree.heading('command_type', text='Comando', anchor=CENTER)
        self.camera_tree.heading('result', text='Resposta', anchor=CENTER)

        # Column widths - 30% for Comando, 70% for Resposta (both stretchable)
        # Fixed columns: id(40) + name(130) + phone(160) + status(180) = 510px
        # Remaining space (~690px on 1200px window): 30% comando (207px) + 70% resposta (483px)
        self.camera_tree.column('id', width=40, minwidth=40, stretch=False, anchor=CENTER)
        self.camera_tree.column('name', width=130, minwidth=130, stretch=False, anchor=CENTER)  # Placa
        self.camera_tree.column('phone', width=160, minwidth=160, stretch=False, anchor=CENTER)  # Número SIM Card
        self.camera_tree.column('status', width=180, minwidth=180, stretch=False, anchor=CENTER)  # Status (+ time)
        self.camera_tree.column('command_type', width=220, minwidth=150, stretch=True, anchor=W)  # Comando (30% flexible)
        self.camera_tree.column('result', width=510, minwidth=300, stretch=True, anchor=W)  # Resposta (70% flexible)

        # Configure row colors (tags)
        self.camera_tree.tag_configure('processing', foreground='white')
        self.camera_tree.tag_configure('success', foreground='#00ff00')  # Bright green
        self.camera_tree.tag_configure('failed', foreground='#ff6666')  # Light red
        self.camera_tree.tag_configure('warning', foreground='#ffaa00')  # Orange for unknown response

        # Scrollbar
        scrollbar = ttk.Scrollbar(cameras_frame, orient=VERTICAL, command=self.camera_tree.yview)
        self.camera_tree.configure(yscrollcommand=scrollbar.set)
        
        self.camera_tree.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)
        
        # Populate camera list
        self.refresh_camera_list()
        
        # ==================== CONTROL SECTION ====================
        control_frame = ttk.Frame(self, padding=10)
        control_frame.pack(fill=X, padx=10, pady=5)
        
        self.start_btn = ttk.Button(
            control_frame,
            text="▶️ INICIAR ENVIO",
            command=self.start_automation,
            bootstyle="success-outline",
            width=25
        )
        self.start_btn.pack(side=LEFT, padx=8)

        self.pause_btn = ttk.Button(
            control_frame,
            text="⏸️ PAUSAR",
            command=self.pause_automation,
            bootstyle="warning-outline",
            width=15,
            state=DISABLED
        )
        self.pause_btn.pack(side=LEFT, padx=8)

        self.stop_btn = ttk.Button(
            control_frame,
            text="⏹️ PARAR",
            command=self.stop_automation,
            bootstyle="danger-outline",
            width=15,
            state=DISABLED
        )
        self.stop_btn.pack(side=LEFT, padx=8)
        
        # Progress bar container
        progress_container = ttk.Frame(control_frame)
        progress_container.pack(side=LEFT, padx=20, fill=X, expand=True)

        # Configure progress bar style
        import tkinter as tk
        style = ttk.Style()
        self.theme_bg_color = style.lookup('TFrame', 'background')

        # Configure the progress bar to have:
        # 1. A thin border
        # 2. Trough (unfilled area) same color as theme background
        style.configure("success.Horizontal.TProgressbar",
                       troughcolor=self.theme_bg_color,  # Match theme background
                       borderwidth=1,
                       bordercolor='#555555',  # Subtle gray border
                       lightcolor=self.theme_bg_color,
                       darkcolor=self.theme_bg_color,
                       background='#00bc8c')  # Green fill color

        # Progress bar with green fill
        self.progress = ttk.Progressbar(
            progress_container,
            mode='determinate',
            bootstyle="success",  # Green fill
            length=300
        )
        self.progress.place(relx=0, rely=0, relwidth=1, relheight=1)

        # Percentage label overlaid on progress bar
        self.progress_percent_label = tk.Label(
            progress_container,
            text="0%",
            font=("Helvetica", 10, "bold"),
            foreground="white",
            bg=self.theme_bg_color  # Match theme background for transparency effect
        )
        self.progress_percent_label.place(relx=0.5, rely=0.5, anchor="center")

        # Set container height
        progress_container.config(height=30)  # Slightly taller for better centering

        # Counter label (X / Y)
        self.progress_label = ttk.Label(control_frame, text="0 / 0", font=("Helvetica", 10))
        self.progress_label.pack(side=LEFT, padx=5)
        
        # ==================== LOG SECTION ====================
        log_frame = ttk.Labelframe(self, text="📋 Log de Atividades", padding=10)
        log_frame.pack(fill=BOTH, expand=True, padx=10, pady=5)
        
        self.log_text = ScrolledText(
            log_frame,
            height=15,  # Adjusted for better screen fit
            autohide=True,
            bootstyle="secondary"
        )
        self.log_text.pack(fill=BOTH, expand=True, pady=(0, 5))

        # Initial log message
        self.add_log("Aplicação iniciada. Por favor, conecte ao módulo Arduino + SIM800C.", "INFO")
    
    # ==================== HELPER METHODS ====================
    
    def get_available_ports(self):
        """Get list of available COM ports"""
        ports = serial.tools.list_ports.comports()
        return [port.device for port in ports] if ports else ['COM3']
    
    def auto_refresh_ports(self):
        """Auto-refresh COM port list every second"""
        current_ports = self.get_available_ports()

        # Only update if ports changed
        if current_ports != list(self.port_combo['values']):
            self.port_combo['values'] = current_ports
            # If current selection is not in the new list, select first available
            if self.port_var.get() not in current_ports and current_ports:
                self.port_var.set(current_ports[0])

        # Schedule next refresh in 1000ms (1 second)
        self.after(1000, self.auto_refresh_ports)
    
    def load_config(self):
        """Load configuration from file with migration support"""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    self.config = json.load(f)
                    self.cameras = self.config.get('cameras', [])

                    # MIGRATION STEP 1: Add command field to cameras if missing (old global command format)
                    old_global_command = self.config.get('command', '')
                    migrated_global = False
                    for camera in self.cameras:
                        if 'command' not in camera and 'commands' not in camera:
                            # Migrate: use old global command as default
                            camera['command'] = old_global_command
                            camera['command_type'] = self.identify_command_type(old_global_command)
                            migrated_global = True

                    if migrated_global:
                        self.add_log("✓ Configuração migrada: comandos individuais criados", "SUCCESS")
                        # Remove old global command from config
                        if 'command' in self.config:
                            del self.config['command']

                    # MIGRATION STEP 2: Convert single command to command array (new multi-command format)
                    migrated_array = False
                    for camera in self.cameras:
                        if 'command' in camera and 'commands' not in camera:
                            # Migrate: convert single command to array format
                            single_command = camera['command']
                            single_command_type = camera.get('command_type', '')
                            single_status = camera.get('status', CameraStatus.PENDING.value)
                            single_result = camera.get('result', '')

                            # Create command array with single command
                            camera['commands'] = [{
                                'command': single_command,
                                'command_type': single_command_type,
                                'status': single_status,
                                'result': single_result
                            }]

                            # Remove old single command fields
                            del camera['command']
                            if 'command_type' in camera:
                                del camera['command_type']
                            if 'status' in camera:
                                del camera['status']
                            if 'result' in camera:
                                del camera['result']

                            migrated_array = True

                    if migrated_array:
                        self.add_log("✓ Configuração migrada: sistema de filas de comandos ativado", "SUCCESS")

                    # MIGRATION STEP 3: Merge duplicate equipment names (combine commands into one equipment)
                    equipment_map = {}  # {name: {phone, commands[]}}
                    migrated_duplicates = False

                    for camera in self.cameras:
                        name = camera.get('name', '')
                        phone = camera.get('phone', '')
                        commands = camera.get('commands', [])

                        if name in equipment_map:
                            # Duplicate found! Merge commands
                            equipment_map[name]['commands'].extend(commands)
                            migrated_duplicates = True
                        else:
                            # First occurrence
                            equipment_map[name] = {
                                'name': name,
                                'phone': phone,
                                'commands': commands[:]  # Create a copy to avoid reference issues
                            }

                    if migrated_duplicates:
                        # Replace cameras list with merged list
                        self.cameras = list(equipment_map.values())
                        self.add_log("✓ Equipamentos duplicados mesclados (comandos combinados)", "SUCCESS")

                    # Save if any migration happened
                    if migrated_global or migrated_array or migrated_duplicates:
                        self.save_config()

            except Exception as e:
                self.config = {}
                self.cameras = []
        else:
            self.config = {}
            self.cameras = []

    def save_config(self):
        """Save configuration to file"""
        # Only update port if GUI is initialized (port_var exists)
        if hasattr(self, 'port_var') and self.port_var:
            self.config['port'] = self.port_var.get()

        self.config['cameras'] = self.cameras

        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            error_msg = f"Falha ao salvar configuração: {e}"
            self.add_log(error_msg, "ERROR")
            # Only show messagebox if GUI exists
            if hasattr(self, 'winfo_exists') and self.winfo_exists():
                Messagebox.show_error(error_msg, "Erro")
    
    def add_log(self, message, level="INFO"):
        """Add message to log"""
        timestamp = datetime.now().strftime('%H:%M:%S')

        # Color coding
        if level == "ERROR":
            tag = "error"
            prefix = "✗"
        elif level == "SUCCESS":
            tag = "success"
            prefix = "✓"
        elif level == "WARNING":
            tag = "warning"
            prefix = "⚠"
        else:
            tag = "info"
            prefix = "ℹ"

        log_message = f"[{timestamp}] {prefix} {message}\n"

        # Only update GUI if log_text widget exists (it won't exist during __init__)
        if hasattr(self, 'log_text') and self.log_text:
            self.log_text.insert(END, log_message, tag)
            self.log_text.see(END)

            # Configure tags
            self.log_text.tag_config("error", foreground="#ff6b6b")
            self.log_text.tag_config("success", foreground="#51cf66")
            self.log_text.tag_config("warning", foreground="#ffd43b")
            self.log_text.tag_config("info", foreground="#74c0fc")

        # Always write to log file
        try:
            with open(LOG_FILE, 'a', encoding='utf-8') as f:
                f.write(log_message)
        except:
            pass
    
    def clear_log(self):
        """Clear log text"""
        self.log_text.delete(1.0, END)
        self.add_log("Log limpo", "INFO")
    
    def export_log(self):
        """Export log to file"""
        filename = f"sms_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        try:
            log_content = self.log_text.get(1.0, END)
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(log_content)
            self.add_log(f"Log exportado para {filename}", "SUCCESS")
            Messagebox.ok(f"Log exportado com sucesso para:\n{filename}", "Exportação Concluída")
        except Exception as e:
            self.add_log(f"Falha ao exportar log: {e}", "ERROR")

    # ==================== API MANAGEMENT ====================

    def api_log_callback(self, message, level="INFO"):
        """Callback for API manager to log messages"""
        self.add_log(message, level)

    def authenticate_api_startup(self):
        """Authenticate with SETERA API on startup (runs in background thread)"""
        try:
            # Authenticate
            success, message = self.api_manager.authenticate()

            if success:
                # Fetch STR-CAM terminals
                success, terminals, message = self.api_manager.get_str_cam_terminals()

                if success:
                    self.str_cam_terminals = terminals
                    self.api_authenticated = True
                    # Update status label on main thread
                    self.after(0, lambda: self.update_api_status(
                        "success",
                        f"✅ API: {len(terminals)} STR-CAM"
                    ))
                else:
                    self.api_authenticated = False
                    self.after(0, lambda: self.update_api_status(
                        "warning",
                        "⚠️ API: Sem terminais"
                    ))
            else:
                self.api_authenticated = False
                self.after(0, lambda: self.update_api_status(
                    "error",
                    "❌ API: Offline"
                ))
        except Exception as e:
            self.api_authenticated = False
            self.add_log(f"❌ Erro na autenticação API: {e}", "ERROR")
            self.after(0, lambda: self.update_api_status(
                "error",
                "❌ API: Erro"
            ))

    def update_api_status(self, status_type, text):
        """Update API status label (must be called from main thread)"""
        if hasattr(self, 'api_status_label'):
            self.api_status_label.config(text=text)

            # Update color based on status
            if status_type == "success":
                self.api_status_label.config(foreground="#51cf66")  # Green
            elif status_type == "warning":
                self.api_status_label.config(foreground="#ffd43b")  # Yellow
            elif status_type == "error":
                self.api_status_label.config(foreground="#ff6b6b")  # Red
            else:
                self.api_status_label.config(foreground="#74c0fc")  # Blue (info)

    def refresh_api_terminals(self):
        """Refresh STR-CAM terminals from API (can be called from GUI)"""
        self.add_log("🔄 Atualizando lista de terminais...", "INFO")
        self.update_api_status("info", "🔐 API: Atualizando...")

        # Run in background thread
        refresh_thread = threading.Thread(target=self._refresh_terminals_thread, daemon=True)
        refresh_thread.start()

    def _refresh_terminals_thread(self):
        """Background thread for refreshing terminals"""
        try:
            success, terminals, message = self.api_manager.get_str_cam_terminals(force_refresh=True)

            if success:
                self.str_cam_terminals = terminals
                self.after(0, lambda: self.update_api_status(
                    "success",
                    f"✅ API: {len(terminals)} STR-CAM"
                ))
                self.add_log(f"✅ Lista atualizada: {len(terminals)} terminais STR-CAM", "SUCCESS")
            else:
                self.after(0, lambda: self.update_api_status(
                    "warning",
                    "⚠️ API: Falha"
                ))
                self.add_log(f"⚠️ Falha ao atualizar: {message}", "WARNING")
        except Exception as e:
            self.add_log(f"❌ Erro ao atualizar terminais: {e}", "ERROR")
            self.after(0, lambda: self.update_api_status(
                "error",
                "❌ API: Erro"
            ))

    def check_log_queue(self):
        """Check for messages from worker thread"""
        try:
            while True:
                level, message = self.log_queue.get_nowait()
                self.add_log(message, level)
        except queue.Empty:
            pass
        
        # Check response queue for responses from worker
        try:
            while True:
                msg = self.response_queue.get_nowait()
                self.handle_worker_message(msg)
        except queue.Empty:
            pass
        
        # Schedule next check
        self.after(100, self.check_log_queue)
    
    def handle_worker_message(self, msg):
        """Handle messages from worker thread"""
        if msg['type'] == 'SMS_RESULT':
            camera_name = msg['camera_name']
            command_index = msg['command_index']
            success = msg['success']

            if success:
                # Record send time for timeout tracking (only if not already tracking - don't reset on retry!)
                tracking_key = f"{camera_name}_{command_index}"
                if tracking_key not in self.sms_send_time:
                    # First send - start tracking elapsed time
                    self.sms_send_time[tracking_key] = time.time()
                # If tracking_key already exists, it's a retry - keep original timestamp for continuous elapsed time

                self.update_command_status(camera_name, command_index, CameraStatus.WAITING, "Aguardando resposta...")
                # Start centralized SMS checking if not already running
                if not hasattr(self, 'sms_checking_active') or not self.sms_checking_active:
                    self.sms_checking_active = True
                    self.after(5000, self.check_all_responses)
            else:
                # Command failed - mark as failed and skip remaining commands for this equipment
                self.update_command_status(camera_name, command_index, CameraStatus.FAILED, "Falha ao enviar SMS")
                self.skip_remaining_commands(camera_name, command_index)
                self.check_automation_complete()

        elif msg['type'] == 'SMS_RECEIVED':
            camera_name = msg['camera_name']
            command_index = msg['command_index']
            message = msg['message']

            if message:
                # Find camera by name
                camera = None
                for cam in self.cameras:
                    if cam['name'] == camera_name:
                        camera = cam
                        break

                if not camera:
                    self.add_log(f"⚠ Equipamento não encontrado: {camera_name}", "WARNING")
                    return

                # Get the command
                commands = camera.get('commands', [])
                if command_index >= len(commands):
                    self.add_log(f"⚠ Índice de comando inválido: {command_index} para {camera_name}", "WARNING")
                    return

                command = commands[command_index]
                command_type = command.get('command_type', None)

                # Calculate response time
                tracking_key = f"{camera_name}_{command_index}"
                if tracking_key in self.sms_send_time:
                    elapsed = time.time() - self.sms_send_time[tracking_key]
                else:
                    elapsed = None

                if not command_type:
                    # Fallback: No command type, mark as success (backward compatibility)
                    result_text = message  # Just the message, no prefix
                    if tracking_key in self.sms_send_time:
                        del self.sms_send_time[tracking_key]
                    # Cleanup retry/warning tracking dictionaries
                    if tracking_key in self.last_warning_time:
                        del self.last_warning_time[tracking_key]
                    if tracking_key in self.retry_count:
                        del self.retry_count[tracking_key]
                    self.update_command_status(camera_name, command_index, CameraStatus.SUCCESS, result_text, elapsed)
                    # Send next command for this equipment
                    self.send_next_command_for_equipment(camera_name)
                else:
                    # Validate response against expected patterns
                    validation_status, matched_pattern = self.validate_response(command_type, message)

                    if validation_status == "success":
                        # Expected success response received
                        result_text = message  # Just the message, no prefix
                        if tracking_key in self.sms_send_time:
                            del self.sms_send_time[tracking_key]
                        # Cleanup retry/warning tracking dictionaries
                        if tracking_key in self.last_warning_time:
                            del self.last_warning_time[tracking_key]
                        if tracking_key in self.retry_count:
                            del self.retry_count[tracking_key]
                        self.update_command_status(camera_name, command_index, CameraStatus.SUCCESS, result_text)
                        self.add_log(f"✓ {camera_name}: Resposta válida detectada - '{matched_pattern}'", "SUCCESS")
                        # Send next command for this equipment
                        self.send_next_command_for_equipment(camera_name)

                    elif validation_status == "failure":
                        # Expected failure response received - skip remaining commands
                        result_text = message
                        if tracking_key in self.sms_send_time:
                            del self.sms_send_time[tracking_key]
                        # Cleanup retry/warning tracking dictionaries
                        if tracking_key in self.last_warning_time:
                            del self.last_warning_time[tracking_key]
                        if tracking_key in self.retry_count:
                            del self.retry_count[tracking_key]
                        self.update_command_status(camera_name, command_index, CameraStatus.FAILED, result_text, elapsed)
                        self.add_log(f"✗ {camera_name}: Falha detectada - '{matched_pattern}'", "ERROR")
                        # Skip remaining commands for this equipment
                        self.skip_remaining_commands(camera_name, command_index)
                        self.check_automation_complete()

                    elif validation_status == "unknown":
                        # Unexpected response - mark as unknown but keep listening
                        result_text = message
                        self.update_command_status(camera_name, command_index, CameraStatus.UNKNOWN_RESPONSE, result_text, elapsed)
                        self.add_log(f"⚠ {camera_name}: Resposta desconhecida recebida, aguardando resposta esperada...", "WARNING")
                        # DON'T send next command - keep waiting for expected response
            # If no message, keep waiting (called again by timer)

        elif msg['type'] == 'MODULE_INFO':
            csq = msg.get('csq', None)

            # Update signal strength with visual representation
            if csq is not None:
                signal_bars = self.get_signal_bars(csq)
                signal_text = self.get_signal_text(csq)
                self.signal_label.config(text=f"{signal_bars} Sinal GSM: {csq} ({signal_text})")
            else:
                self.signal_label.config(text="Sinal GSM: --")

        elif msg['type'] == 'CSQ_UPDATE':
            # Update only signal strength (from periodic polling)
            csq = msg.get('csq', None)
            if csq is not None:
                signal_bars = self.get_signal_bars(csq)
                signal_text = self.get_signal_text(csq)
                self.signal_label.config(text=f"{signal_bars} Sinal GSM: {csq} ({signal_text})")

        elif msg['type'] == 'SMS_BATCH':
            # Process all incoming SMS messages and match to waiting commands
            messages = msg.get('messages', [])

            for sms in messages:
                sender = sms['sender']
                message_text = sms['message']

                # Find equipment by phone number (match sender)
                matched_camera = None
                for camera in self.cameras:
                    # Normalize phone numbers for comparison (remove spaces, dashes)
                    camera_phone = camera['phone'].replace(' ', '').replace('-', '')
                    sender_normalized = sender.replace(' ', '').replace('-', '')
                    if camera_phone == sender_normalized:
                        matched_camera = camera
                        break

                if not matched_camera:
                    self.add_log(f"⚠ SMS de número desconhecido: {sender}", "WARNING")
                    continue

                # Find which command is currently WAITING or has received UNKNOWN response for this equipment
                commands = matched_camera.get('commands', [])
                waiting_command_index = None
                for idx, cmd in enumerate(commands):
                    # Check for both WAITING and UNKNOWN_RESPONSE statuses
                    if cmd['status'] in [CameraStatus.WAITING.value, CameraStatus.UNKNOWN_RESPONSE.value]:
                        waiting_command_index = idx
                        break

                if waiting_command_index is None:
                    self.add_log(f"⚠ {matched_camera['name']}: SMS recebido mas nenhum comando aguardando resposta", "WARNING")
                    continue

                # Process the response for this command
                self.process_command_response(matched_camera['name'], waiting_command_index, message_text)

    def process_command_response(self, camera_name, command_index, message):
        """Process SMS response for a specific command"""
        # Find camera by name
        camera = None
        for cam in self.cameras:
            if cam['name'] == camera_name:
                camera = cam
                break

        if not camera:
            return

        commands = camera.get('commands', [])
        if command_index >= len(commands):
            return

        command = commands[command_index]
        command_type = command.get('command_type', None)

        # Calculate response time
        tracking_key = f"{camera_name}_{command_index}"
        if tracking_key in self.sms_send_time:
            elapsed = time.time() - self.sms_send_time[tracking_key]
        else:
            elapsed = None

        if not command_type:
            # No command type, mark as success
            result_text = message
            if tracking_key in self.sms_send_time:
                del self.sms_send_time[tracking_key]
            # Cleanup retry/warning tracking dictionaries
            if tracking_key in self.last_warning_time:
                del self.last_warning_time[tracking_key]
            if tracking_key in self.retry_count:
                del self.retry_count[tracking_key]
            self.update_command_status(camera_name, command_index, CameraStatus.SUCCESS, result_text, elapsed)
            self.send_next_command_for_equipment(camera_name)
        else:
            # Validate response against expected patterns
            validation_status, matched_pattern = self.validate_response(command_type, message)

            if validation_status == "success":
                # Expected success response
                result_text = message
                if tracking_key in self.sms_send_time:
                    del self.sms_send_time[tracking_key]
                # Cleanup retry/warning tracking dictionaries
                if tracking_key in self.last_warning_time:
                    del self.last_warning_time[tracking_key]
                if tracking_key in self.retry_count:
                    del self.retry_count[tracking_key]
                self.update_command_status(camera_name, command_index, CameraStatus.SUCCESS, result_text, elapsed)
                self.add_log(f"✓ {camera_name}: Resposta válida - '{matched_pattern}'", "SUCCESS")
                # Send next command for this equipment
                self.send_next_command_for_equipment(camera_name)

            elif validation_status == "failure":
                # Expected failure response - stop queue
                result_text = message
                if tracking_key in self.sms_send_time:
                    del self.sms_send_time[tracking_key]
                # Cleanup retry/warning tracking dictionaries
                if tracking_key in self.last_warning_time:
                    del self.last_warning_time[tracking_key]
                if tracking_key in self.retry_count:
                    del self.retry_count[tracking_key]
                self.update_command_status(camera_name, command_index, CameraStatus.FAILED, result_text, elapsed)
                self.add_log(f"✗ {camera_name}: Falha detectada - '{matched_pattern}'", "ERROR")
                # Skip remaining commands
                self.skip_remaining_commands(camera_name, command_index)
                self.check_automation_complete()

            elif validation_status == "unknown":
                # Unknown response - keep waiting
                result_text = message
                self.update_command_status(camera_name, command_index, CameraStatus.UNKNOWN_RESPONSE, result_text, elapsed)
                self.add_log(f"⚠ {camera_name}: Resposta desconhecida, aguardando resposta esperada...", "WARNING")
                # DON'T send next command - keep waiting

    def start_csq_polling(self):
        """Start periodic CSQ polling"""
        self.csq_polling_active = True
        self.poll_csq()

    def stop_csq_polling(self):
        """Stop periodic CSQ polling"""
        self.csq_polling_active = False

    def poll_csq(self):
        """Poll CSQ (signal strength) periodically"""
        if not self.csq_polling_active or not self.worker or not self.worker.connected:
            return

        # Request signal quality update
        self.command_queue.put({'type': 'GET_CSQ_ONLY'})

        # Schedule next poll in 5 seconds
        self.after(5000, self.poll_csq)

    def handle_24hour_retry(self, camera_name, command_index, elapsed_hours):
        """Terminate timed-out command and resend after 24 hours (and every 24h thereafter)"""
        tracking_key = f"{camera_name}_{command_index}"

        # Increment retry counter
        if tracking_key not in self.retry_count:
            self.retry_count[tracking_key] = 0
        self.retry_count[tracking_key] += 1
        retry_num = self.retry_count[tracking_key]

        # Calculate actual display hours based on elapsed time
        # This ensures the message shows the correct hours regardless of test/production settings
        current_interval = int(elapsed_hours / self.WARNING_INTERVAL_HOURS)
        display_hours = current_interval * 6

        # Log termination and retry
        self.add_log(f"⏱️ {camera_name} cmd {command_index + 1}: Terminado por timeout após {display_hours}h sem resposta", "WARNING")
        self.add_log(f"🔄 {camera_name} cmd {command_index + 1}: Reenviando (tentativa #{retry_num + 1})", "INFO")

        # Update last_warning_time to mark this interval as already announced
        # This prevents duplicate warnings (e.g., showing "24h" again after retry at 24h)
        self.last_warning_time[tracking_key] = elapsed_hours

        # CRITICAL: Do NOT reset sms_send_time - keep original timestamp for continuous elapsed time tracking

        # Reset status to SENDING for retry
        self.update_command_status(camera_name, command_index, CameraStatus.SENDING, f"Reenviando (#{retry_num + 1})...")

        # Find camera and resend command
        camera = next((c for c in self.cameras if c['name'] == camera_name), None)
        if camera:
            commands = camera.get('commands', [])
            if command_index < len(commands):
                command = commands[command_index]
                cmd = {
                    'type': 'SEND_SMS',
                    'number': camera['phone'],
                    'message': command.get('command', ''),
                    'camera_name': camera_name,
                    'command_index': command_index
                }
                self.command_queue.put(cmd)

    def check_6hour_warnings(self, camera_name, command_index, elapsed_hours):
        """Show warnings at configured intervals for waiting commands"""
        tracking_key = f"{camera_name}_{command_index}"

        # Calculate interval number based on WARNING_INTERVAL_HOURS
        current_interval = int(elapsed_hours / self.WARNING_INTERVAL_HOURS)

        if current_interval == 0:
            return  # Less than one interval, no warning

        # Check if we already warned for this interval
        if tracking_key in self.last_warning_time:
            last_interval = int(self.last_warning_time[tracking_key] / self.WARNING_INTERVAL_HOURS)
            if current_interval <= last_interval:
                return  # Already warned for this interval

        # Calculate display hours - always show 6h increments (6, 12, 18, 24...)
        # This shows consistent hours regardless of WARNING_INTERVAL_HOURS setting
        display_hours = current_interval * 6
        self.add_log(f"⚠️ {camera_name}: Aguardando há {display_hours}h", "WARNING")

        # Update status column to show elapsed time
        result_text = f"Aguardando há {display_hours}h..."
        self.update_command_status(camera_name, command_index, CameraStatus.WAITING, result_text)

        # Record this warning time
        self.last_warning_time[tracking_key] = elapsed_hours

    def check_all_responses(self):
        """Centralized SMS checker + timeout/retry monitoring - checks for ALL device responses"""
        if not self.is_running or self.is_paused:
            self.sms_checking_active = False
            return

        current_time = time.time()
        any_waiting = False

        # Check each device/command for responses, warnings, and retry
        for camera in self.cameras:
            commands = camera.get('commands', [])
            for idx, command in enumerate(commands):
                # Only monitor WAITING or UNKNOWN_RESPONSE commands
                if command['status'] in [CameraStatus.WAITING.value, CameraStatus.UNKNOWN_RESPONSE.value]:
                    any_waiting = True

                    tracking_key = f"{camera['name']}_{idx}"

                    if tracking_key in self.sms_send_time:
                        # Calculate elapsed time in hours
                        elapsed_hours = (current_time - self.sms_send_time[tracking_key]) / 3600

                        # PRIORITY 1: Check for retry at configured interval (24h, 48h, 72h, etc.)
                        # Retry count tracks how many retries have been sent
                        # If elapsed >= (retry_count + 1) * RETRY_INTERVAL_HOURS, time to retry again
                        current_retry_count = self.retry_count.get(tracking_key, 0)
                        next_retry_threshold = (current_retry_count + 1) * self.RETRY_INTERVAL_HOURS

                        if elapsed_hours >= next_retry_threshold:
                            self.handle_24hour_retry(camera['name'], idx, elapsed_hours)
                            continue  # Skip warnings this cycle, command was just retried

                        # PRIORITY 2: Check for 6-hour warnings (independently for each command)
                        self.check_6hour_warnings(camera['name'], idx, elapsed_hours)

        if not any_waiting:
            # No one waiting, stop checking
            self.sms_checking_active = False
            return

        # Ask worker to check for ALL incoming SMS
        self.command_queue.put({'type': 'CHECK_ALL_SMS'})

        # Schedule next check in 5 seconds
        self.after(5000, self.check_all_responses)
    
    def toggle_connection(self):
        """Toggle connection/disconnection"""
        if self.worker and self.worker.is_alive():
            self.disconnect_serial()
        else:
            self.connect_serial()

    def connect_serial(self):
        """Connect to Arduino"""
        port = self.port_var.get()
        baudrate = 9600  # Hardcoded to 9600

        if not port:
            Messagebox.show_error("Por favor, selecione uma porta COM!", "Porta Não Selecionada")
            return

        self.add_log(f"Conectando a {port}...", "INFO")

        # Disable connect button during connection
        self.connect_btn.config(state=DISABLED)

        self.worker = SerialWorker(port, baudrate, self.command_queue, self.response_queue, self.log_queue)
        self.worker.start()

        # Wait a bit and check connection
        self.after(3000, self.check_connection)

    def disconnect_serial(self):
        """Disconnect from Arduino"""
        if self.worker and self.worker.is_alive():
            self.add_log("Desconectando...", "INFO")
            # Stop CSQ polling
            self.stop_csq_polling()
            # Send stop command
            self.command_queue.put({'type': 'STOP'})
            # Wait for thread to finish
            self.worker.join(timeout=2)
            self.worker = None

            self.signal_label.config(text="Sinal GSM: --")
            self.connect_btn.config(text="🔌 Conectar", bootstyle="success-outline", state=NORMAL)
            self.add_log("Desconectado com sucesso", "INFO")

    def check_connection(self):
        """Check if connection was successful and validate communication"""
        if self.worker and self.worker.connected:
            # Send AT command to validate connection
            self.add_log("Validando comunicação com módulo...", "INFO")
            self.command_queue.put({
                'type': 'VALIDATE_CONNECTION'
            })
            # Wait for validation result
            self.after(2000, self.check_validation)
        else:
            self.connect_btn.config(text="🔌 Conectar", bootstyle="success-outline", state=NORMAL)
            self.add_log("✗ Erro ao abrir porta serial", "ERROR")

    def check_validation(self):
        """Check if validation was successful"""
        if self.worker and hasattr(self.worker, 'validated') and self.worker.validated:
            self.connect_btn.config(text="🔌 Desconectar", bootstyle="danger-outline", state=NORMAL)

            # Get module info (MSISDN and CSQ)
            self.add_log("Obtendo informações do módulo...", "INFO")
            self.command_queue.put({'type': 'GET_MODULE_INFO'})

            # Start periodic CSQ polling
            self.start_csq_polling()

            self.add_log("✓ Pronto para enviar SMS!", "SUCCESS")
        else:
            # Validation failed - disconnect
            self.add_log("✗ Módulo não responde. Verifique se Arduino está conectado corretamente.", "ERROR")
            self.disconnect_serial()
    
    def get_signal_bars(self, csq):
        """Convert CSQ value to visual bar representation"""
        if csq == 99:
            return "▯▯▯▯"  # No signal
        elif csq >= 25:
            return "▮▮▮▮"  # Excellent (4/4 bars)
        elif csq >= 20:
            return "▮▮▮▮"  # Very good (4/4 bars)
        elif csq >= 15:
            return "▮▮▮▯"  # Good (3/4 bars)
        elif csq >= 10:
            return "▮▮▯▯"  # OK (2/4 bars)
        elif csq >= 5:
            return "▮▯▯▯"  # Weak (1/4 bar)
        else:
            return "▯▯▯▯"  # Very weak (0/4 bars)

    def get_signal_text(self, csq):
        """Convert CSQ value to text description"""
        if csq == 99:
            return "Sem sinal"
        elif csq >= 20:
            return "Excelente"
        elif csq >= 15:
            return "Bom"
        elif csq >= 10:
            return "OK"
        elif csq >= 5:
            return "Fraco"
        else:
            return "Muito fraco"

    # ==================== CAMERA MANAGEMENT ====================
    
    def refresh_camera_list(self):
        """Refresh camera list in treeview - one row per command"""
        # Clear existing items
        for item in self.camera_tree.get_children():
            self.camera_tree.delete(item)

        # Map to track which command each tree item represents
        self.tree_item_map = {}  # {item_id: (camera_name, command_index)}

        # Flatten structure: create one row per command
        row_number = 1
        for camera in self.cameras:
            # Get command queue for this camera
            commands = camera.get('commands', [])

            # If no commands, show placeholder row
            if not commands:
                item_id = self.camera_tree.insert('', END, values=(
                    row_number,
                    camera['name'],
                    camera['phone'],
                    "⚠️ Sem comandos",
                    "(Nenhum)",
                    ""
                ), tags=('warning',))
                self.tree_item_map[item_id] = (camera['name'], None)  # No command
                row_number += 1
                continue

            # Create one row for each command in the queue
            for cmd_index, command in enumerate(commands):
                status = command.get('status', CameraStatus.PENDING.value)
                result = command.get('result', '')
                elapsed_time = command.get('elapsed_time', None)

                # Status emoji + time (if available)
                status_display_base = {
                    CameraStatus.PENDING.value: "⏳ Pendente",
                    CameraStatus.SENDING.value: "📤 Enviando",
                    CameraStatus.WAITING.value: "⏰ Aguardando",
                    CameraStatus.SUCCESS.value: "✅ Sucesso",
                    CameraStatus.FAILED.value: "❌ Falhou",
                    CameraStatus.SKIPPED.value: "⏭️ Ignorado",
                    CameraStatus.UNKNOWN_RESPONSE.value: "⚠️ Resposta Desconhecida"
                }.get(status, status)

                # Add formatted time to status if available
                if elapsed_time is not None and elapsed_time > 0:
                    formatted_time = format_elapsed_time(elapsed_time)
                    status_display = f"{status_display_base} ({formatted_time})"
                else:
                    status_display = status_display_base

                # Get actual command text for display (not the type name)
                command_display = command.get('command', '(Sem comando)')

                # Determine tag based on status
                if status == CameraStatus.SUCCESS.value:
                    tag = 'success'
                elif status == CameraStatus.FAILED.value:
                    tag = 'failed'
                elif status == CameraStatus.UNKNOWN_RESPONSE.value:
                    tag = 'warning'
                else:
                    tag = 'processing'

                # Insert row and save mapping
                item_id = self.camera_tree.insert('', END, values=(
                    row_number,
                    camera['name'],
                    camera['phone'],
                    status_display,
                    command_display,
                    f"  {result}" if result else ""
                ), tags=(tag,))
                self.tree_item_map[item_id] = (camera['name'], cmd_index)

                row_number += 1
    
    def add_camera(self):
        """Add new camera (supports multi-select)"""
        dialog = CameraDialog(self, "Adicionar Comando", terminals=self.str_cam_terminals)
        self.wait_window(dialog)

        if dialog.result:
            # Check if result is a list (multi-select) or single dict
            results = dialog.result if isinstance(dialog.result, list) else [dialog.result]

            new_equipment_count = 0
            new_commands_count = 0

            for result in results:
                equipment_name = result['name']

                # Find existing equipment
                existing_camera = None
                for cam in self.cameras:
                    if cam['name'] == equipment_name:
                        existing_camera = cam
                        break

                if existing_camera:
                    # Equipment exists: APPEND command to existing equipment
                    if not existing_camera.get('commands'):
                        existing_camera['commands'] = []

                    existing_camera['commands'].append({
                        'command': result['command'],
                        'command_type': result['command_type'],
                        'status': CameraStatus.PENDING.value,
                        'result': ''
                    })
                    new_commands_count += 1
                else:
                    # Equipment doesn't exist: CREATE new equipment with first command
                    self.cameras.append({
                        'name': result['name'],
                        'phone': result['phone'],
                        'commands': [{
                            'command': result['command'],
                            'command_type': result['command_type'],
                            'status': CameraStatus.PENDING.value,
                            'result': ''
                        }]
                    })
                    new_equipment_count += 1
                    new_commands_count += 1

            self.refresh_camera_list()
            self.save_config()

            # Log results
            if new_equipment_count > 0 and new_commands_count > new_equipment_count:
                # Mixed: new equipment + commands added to existing
                self.add_log(f"✓ {new_equipment_count} equipamento(s) novo(s), {new_commands_count} comando(s) total adicionado(s)", "SUCCESS")
            elif new_equipment_count > 0:
                # Only new equipment
                if new_equipment_count == 1:
                    self.add_log(f"✓ Equipamento adicionado: {results[0]['name']} ({new_commands_count} comando(s) na fila)", "SUCCESS")
                else:
                    self.add_log(f"✓ {new_equipment_count} equipamento(s) adicionado(s), {new_commands_count} comando(s) total", "SUCCESS")
            elif new_commands_count > 0:
                # Only commands added to existing equipment
                self.add_log(f"✓ {new_commands_count} comando(s) adicionado(s) a equipamento(s) existente(s)", "SUCCESS")

    def edit_camera(self):
        """Edit selected command (replace it)"""
        selected = self.camera_tree.selection()
        if not selected:
            Messagebox.show_warning("Por favor, selecione um comando para editar", "Nenhuma Seleção")
            return

        item_id = selected[0]

        # Get camera_name and command_index from mapping
        if item_id not in self.tree_item_map:
            Messagebox.show_warning("Erro ao identificar comando selecionado", "Erro")
            return

        camera_name, cmd_index = self.tree_item_map[item_id]

        # Find camera by name
        camera = None
        for cam in self.cameras:
            if cam['name'] == camera_name:
                camera = cam
                break

        if not camera:
            Messagebox.show_warning("Equipamento não encontrado", "Erro")
            return

        # Determine if editing existing command or adding first
        if cmd_index is None:
            # No commands yet, add first command
            dialog_title = "Adicionar Primeiro Comando"
            command_data = None
        else:
            # Editing existing command
            commands = camera.get('commands', [])
            if cmd_index < len(commands):
                dialog_title = "Editar Comando"
                command_data = commands[cmd_index]
            else:
                Messagebox.show_warning("Comando não encontrado", "Erro")
                return

        dialog = CameraDialog(self, dialog_title, camera, command_data, terminals=self.str_cam_terminals)
        self.wait_window(dialog)

        if dialog.result:
            # Update name and phone if changed
            camera['name'] = dialog.result['name']
            camera['phone'] = dialog.result['phone']

            if cmd_index is None or not camera.get('commands'):
                # Add first command
                camera['commands'] = [{
                    'command': dialog.result['command'],
                    'command_type': dialog.result['command_type'],
                    'status': CameraStatus.PENDING.value,
                    'result': ''
                }]
                self.add_log(f"✓ Primeiro comando adicionado ao equipamento {camera['name']}", "SUCCESS")
            else:
                # REPLACE existing command
                camera['commands'][cmd_index] = {
                    'command': dialog.result['command'],
                    'command_type': dialog.result['command_type'],
                    'status': CameraStatus.PENDING.value,  # Reset status
                    'result': ''
                }
                self.add_log(f"✓ Comando {cmd_index + 1} editado para {camera['name']}", "SUCCESS")

            self.refresh_camera_list()
            self.save_config()
    
    def remove_camera(self):
        """Remove selected command(s) - NO CONFIRMATION"""
        selected = self.camera_tree.selection()
        if not selected:
            Messagebox.show_warning("Por favor, selecione um ou mais comandos para remover", "Nenhuma Seleção")
            return

        # Build list of commands to remove: [(camera_name, cmd_index), ...]
        commands_to_remove = []
        for item_id in selected:
            if item_id in self.tree_item_map:
                camera_name, cmd_index = self.tree_item_map[item_id]
                commands_to_remove.append((camera_name, cmd_index))

        if not commands_to_remove:
            Messagebox.show_warning("Erro ao identificar comandos selecionados", "Erro")
            return

        # Group by camera and collect command indices to remove
        cameras_to_process = {}
        for camera_name, cmd_index in commands_to_remove:
            if camera_name not in cameras_to_process:
                cameras_to_process[camera_name] = []
            if cmd_index is not None:  # Only add if it's an actual command
                cameras_to_process[camera_name].append(cmd_index)

        # Remove commands from cameras (in reverse order to maintain indices)
        removed_count = 0
        cameras_to_delete = []

        for camera_name, cmd_indices in cameras_to_process.items():
            # Find camera
            camera = None
            for cam in self.cameras:
                if cam['name'] == camera_name:
                    camera = cam
                    break

            if camera and camera.get('commands'):
                # Sort indices in descending order to remove from end first
                for idx in sorted(cmd_indices, reverse=True):
                    if idx < len(camera['commands']):
                        del camera['commands'][idx]
                        removed_count += 1

                # If no commands left, mark camera for deletion
                if len(camera['commands']) == 0:
                    cameras_to_delete.append(camera_name)

        # Remove cameras with no commands
        self.cameras = [cam for cam in self.cameras if cam['name'] not in cameras_to_delete]

        self.refresh_camera_list()
        self.save_config()

        # Log result
        if removed_count > 0:
            msg = f"{removed_count} comando(s) removido(s)"
            if len(cameras_to_delete) > 0:
                msg += f", {len(cameras_to_delete)} equipamento(s) deletado(s)"
            self.add_log(f"✓ {msg}", "INFO")
        else:
            self.add_log("⚠ Nenhum comando removido", "WARNING")

    def remove_all_cameras(self):
        """Remove ALL commands from ALL equipment - WITH CONFIRMATION"""
        if not self.cameras or len(self.cameras) == 0:
            Messagebox.show_warning("Não há equipamentos para remover", "Lista Vazia")
            return

        # Count total commands
        total_commands = sum(len(cam.get('commands', [])) for cam in self.cameras)
        total_equipment = len(self.cameras)

        # Create custom confirmation dialog with SIM/NÃO buttons
        msg = f"Tem certeza que deseja remover TODOS os comandos?\n\n"
        msg += f"• {total_equipment} equipamento(s)\n"
        msg += f"• {total_commands} comando(s) total\n\n"
        msg += "Esta ação NÃO pode ser desfeita!"

        # Use yesno which shows "Yes"/"No" buttons (will be styled as SIM/NÃO in Portuguese locale)
        response = Messagebox.yesno(msg, "⚠️ CONFIRMAR REMOÇÃO TOTAL")

        if response == "Yes":
            # Clear all cameras
            self.cameras.clear()
            self.refresh_camera_list()
            self.save_config()
            self.add_log(f"✓ Removidos {total_equipment} equipamento(s) com {total_commands} comando(s)", "INFO")
        else:
            self.add_log("⚠ Remoção cancelada pelo usuário", "INFO")

    def import_cameras(self):
        """Import cameras from text file"""
        # Show example format
        example = "Formato (uma por linha):\nNome do Equipamento, +5512345678\nEquipamento 2, +5512345679"
        if Messagebox.show_question(f"Formato de importação:\n\n{example}\n\nContinuar?", "Importar Equipamentos") != "Yes":
            return

        filename = ttk.dialogs.dialogs.Querybox.get_string("Digite o nome do arquivo:", "Importar")
        if not filename:
            return

        try:
            with open(filename, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            count = 0
            for line in lines:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue

                parts = [p.strip() for p in line.split(',')]
                if len(parts) >= 2:
                    # Import with empty command array - user must add commands manually
                    self.cameras.append({
                        'name': parts[0],
                        'phone': parts[1],
                        'commands': []  # Empty array - user will add commands via Edit
                    })
                    count += 1

            self.refresh_camera_list()
            self.save_config()
            self.add_log(f"Importados {count} equipamentos (sem comandos)", "SUCCESS")
            Messagebox.ok(f"Importados {count} equipamentos.\nUse 'Editar' para adicionar comandos a cada equipamento.", "Importação Concluída")
        except Exception as e:
            Messagebox.show_error(f"Falha ao importar: {e}", "Erro na Importação")
    
    def update_command_status(self, camera_name, command_index, status, result="", elapsed_time=None):
        """Update status for a specific command in a camera's queue"""
        # Find camera by name
        camera = None
        for cam in self.cameras:
            if cam['name'] == camera_name:
                camera = cam
                break

        if not camera:
            self.add_log(f"⚠ Equipamento não encontrado: {camera_name}", "WARNING")
            return

        # Update command status
        if command_index < len(camera['commands']):
            camera['commands'][command_index]['status'] = status.value
            camera['commands'][command_index]['result'] = result
            if elapsed_time is not None:
                camera['commands'][command_index]['elapsed_time'] = elapsed_time
            self.refresh_camera_list()
            self.update_progress()
        else:
            self.add_log(f"⚠ Índice de comando inválido: {command_index} para {camera_name}", "WARNING")
    
    # ==================== AUTOMATION CONTROL ====================
    
    def start_automation(self):
        """Start SMS automation - parallel processing for all equipment"""
        if not self.worker or not self.worker.connected:
            Messagebox.show_error("Por favor, conecte ao Arduino primeiro!", "Não Conectado")
            return

        if not self.worker.validated:
            Messagebox.show_error("Conexão não validada. O módulo não está respondendo corretamente.", "Validação Falhou")
            return

        if not self.cameras:
            Messagebox.show_error("Por favor, adicione equipamentos primeiro!", "Sem Equipamentos")
            return

        # Reset all commands in all equipment queues to pending
        total_commands = 0
        for camera in self.cameras:
            for command in camera.get('commands', []):
                command['status'] = CameraStatus.PENDING.value
                command['result'] = ''
                total_commands += 1
        self.refresh_camera_list()

        # Update UI
        self.is_running = True
        self.is_paused = False

        self.start_btn.config(state=DISABLED)
        self.pause_btn.config(state=NORMAL)
        self.stop_btn.config(state=NORMAL)

        # Progress bar now counts total commands, not equipment
        self.progress['maximum'] = total_commands
        self.progress['value'] = 0
        self.update_progress()

        self.add_log("=" * 50, "INFO")
        self.add_log("AUTOMAÇÃO INICIADA - PROCESSAMENTO PARALELO", "SUCCESS")
        self.add_log(f"Total de equipamentos: {len(self.cameras)}", "INFO")
        self.add_log(f"Total de comandos: {total_commands}", "INFO")
        self.add_log("=" * 50, "INFO")

        # Delete all old SMS messages before starting
        self.command_queue.put({'type': 'DELETE_ALL_SMS'})

        # Wait a bit for SMS deletion to complete, then start ALL equipment in parallel
        self.after(2000, self.start_all_equipment_queues)
    
    def start_all_equipment_queues(self):
        """Start processing first command for ALL equipment in parallel"""
        if not self.is_running:
            return

        for camera in self.cameras:
            # Send first command for each equipment
            self.send_next_command_for_equipment(camera['name'])

    def send_next_command_for_equipment(self, camera_name):
        """Send next pending command for a specific equipment"""
        if not self.is_running or self.is_paused:
            return

        # Find camera by name
        camera = None
        for cam in self.cameras:
            if cam['name'] == camera_name:
                camera = cam
                break

        if not camera:
            self.add_log(f"⚠ Equipamento não encontrado: {camera_name}", "WARNING")
            return

        # Find next pending command in this equipment's queue
        commands = camera.get('commands', [])
        next_command_index = None

        for idx, command in enumerate(commands):
            if command['status'] == CameraStatus.PENDING.value:
                next_command_index = idx
                break

        # No more pending commands for this equipment
        if next_command_index is None:
            self.add_log(f"✓ Equipamento {camera_name}: Fila de comandos concluída", "SUCCESS")
            self.check_automation_complete()
            return

        # Get the command to send
        command = commands[next_command_index]
        command_text = command.get('command', '')
        command_type = command.get('command_type', '')

        self.add_log(f"📤 {camera_name}: Enviando comando {next_command_index + 1}/{len(commands)}", "INFO")
        self.update_command_status(camera_name, next_command_index, CameraStatus.SENDING, "Enviando SMS...")

        # Send SMS
        cmd = {
            'type': 'SEND_SMS',
            'number': camera['phone'],
            'message': command_text,
            'camera_name': camera_name,  # NEW: identify by name
            'command_index': next_command_index  # NEW: track which command
        }
        self.command_queue.put(cmd)

    def skip_remaining_commands(self, camera_name, failed_command_index):
        """Skip all remaining pending commands for an equipment after a failure"""
        # Find camera by name
        camera = None
        for cam in self.cameras:
            if cam['name'] == camera_name:
                camera = cam
                break

        if not camera:
            return

        # Mark all commands after the failed one as SKIPPED
        commands = camera.get('commands', [])
        skipped_count = 0
        for idx in range(failed_command_index + 1, len(commands)):
            if commands[idx]['status'] == CameraStatus.PENDING.value:
                commands[idx]['status'] = CameraStatus.SKIPPED.value
                commands[idx]['result'] = "Ignorado (comando anterior falhou)"
                skipped_count += 1

        if skipped_count > 0:
            self.add_log(f"⚠ {camera_name}: {skipped_count} comando(s) restante(s) ignorado(s)", "WARNING")
            self.refresh_camera_list()
            self.update_progress()

    def pause_automation(self):
        """Pause automation"""
        if self.is_paused:
            self.is_paused = False
            self.pause_btn.config(text="⏸️ PAUSAR")
            self.add_log("Automação retomada", "INFO")
            # Resume all equipment queues
            self.start_all_equipment_queues()
        else:
            self.is_paused = True
            self.pause_btn.config(text="▶️ RETOMAR")
            self.add_log("Automação pausada", "WARNING")
    
    def stop_automation(self):
        """Stop automation"""
        self.is_running = False
        self.is_paused = False

        self.start_btn.config(state=NORMAL)
        self.pause_btn.config(state=DISABLED)
        self.stop_btn.config(state=DISABLED)

        self.add_log("=" * 50, "INFO")
        self.add_log("AUTOMAÇÃO INTERROMPIDA", "WARNING")
        self.add_log("=" * 50, "INFO")
    
    def update_progress(self):
        """Update progress bar and percentage"""
        # Count total commands and completed commands across all equipment
        total_commands = 0
        completed_commands = 0

        for camera in self.cameras:
            commands = camera.get('commands', [])
            for command in commands:
                total_commands += 1
                status = command.get('status', '')
                if status in [CameraStatus.SUCCESS.value, CameraStatus.FAILED.value, CameraStatus.SKIPPED.value]:
                    completed_commands += 1

        self.progress['value'] = completed_commands
        self.progress_label.config(text=f"{completed_commands} / {total_commands}")

        # Update percentage label text and background color
        if total_commands > 0:
            percent = int((completed_commands / total_commands) * 100)
            self.progress_percent_label.config(text=f"{percent}%")

            # Update background color based on progress
            # If progress >= 50%, label center is over green fill
            if percent >= 50:
                self.progress_percent_label.configure(bg='#00bc8c')  # Success/green color
            else:
                self.progress_percent_label.configure(bg=self.theme_bg_color)  # Match theme background
        else:
            self.progress_percent_label.config(text="0%")
            self.progress_percent_label.configure(bg=self.theme_bg_color)  # Match theme background

    def check_automation_complete(self):
        """Check if all equipment queues are complete"""
        if not self.is_running:
            return

        # Check if all commands in all equipment are in a terminal state
        all_complete = True
        for camera in self.cameras:
            commands = camera.get('commands', [])
            for command in commands:
                status = command.get('status', '')
                if status not in [CameraStatus.SUCCESS.value, CameraStatus.FAILED.value, CameraStatus.SKIPPED.value]:
                    all_complete = False
                    break
            if not all_complete:
                break

        if all_complete:
            self.automation_complete()

    def automation_complete(self):
        """Called when automation is complete"""
        self.is_running = False

        self.start_btn.config(state=NORMAL)
        self.pause_btn.config(state=DISABLED)
        self.stop_btn.config(state=DISABLED)

        # Count command results across all equipment
        total_commands = 0
        success_commands = 0
        failed_commands = 0
        skipped_commands = 0

        for camera in self.cameras:
            commands = camera.get('commands', [])
            for command in commands:
                total_commands += 1
                status = command.get('status', '')
                if status == CameraStatus.SUCCESS.value:
                    success_commands += 1
                elif status == CameraStatus.FAILED.value:
                    failed_commands += 1
                elif status == CameraStatus.SKIPPED.value:
                    skipped_commands += 1

        self.add_log("=" * 50, "INFO")
        self.add_log("AUTOMAÇÃO CONCLUÍDA!", "SUCCESS")
        self.add_log(f"Total de comandos: {total_commands}", "INFO")
        self.add_log(f"✓ Sucesso: {success_commands}", "SUCCESS")
        self.add_log(f"✗ Falhas: {failed_commands}", "ERROR" if failed_commands > 0 else "INFO")
        if skipped_commands > 0:
            self.add_log(f"⚠ Ignorados: {skipped_commands}", "WARNING")
        self.add_log("=" * 50, "INFO")

        # No popup - user can see results in log and table

# ============================================================================
# CAMERA DIALOG
# ============================================================================

class CameraDialog(ttk.Toplevel):
    def __init__(self, parent, title, camera=None, command_data=None, terminals=None):
        super().__init__(parent)

        self.parent = parent  # Store parent reference for pattern matching
        self.terminals = terminals if terminals else []  # STR-CAM terminals from API
        self.title(title)

        # Determine if this is ADD NEW (needs explanation) or EDIT (no explanation)
        self.is_edit_mode = (command_data is not None)

        # Determine if this is ADD NEW mode (allows multi-select)
        self.is_add_new_mode = (camera is None and command_data is None)

        self.resizable(False, False)

        # Set icon
        try:
            self.iconbitmap("favicon.ico")
        except:
            pass  # Ignore if icon file not found

        self.result = None

        # Create form
        frame = ttk.Frame(self, padding=20)
        frame.pack(fill=BOTH, expand=True)

        # Configure grid column 1 to expand for command field
        frame.columnconfigure(1, weight=1)

        # ==== Placa Selection ====
        plate_label_text = "Placas:" if (self.is_add_new_mode and self.terminals) else "Placa:"
        ttk.Label(frame, text=plate_label_text).grid(row=0, column=0, sticky=NW, pady=10, padx=5)

        # Container for plate field and controls
        plate_container = ttk.Frame(frame)
        plate_container.grid(row=0, column=1, sticky=NSEW, pady=10, padx=5)

        self.name_var = ttk.StringVar(value=camera['name'] if camera else '')

        # If we have terminals from API, use different widgets based on mode
        if self.terminals and len(self.terminals) > 0:
            # ADD NEW mode: Multi-select listbox
            if self.is_add_new_mode:
                # Create scrollable listbox for multi-select
                listbox_frame = ttk.Frame(plate_container)
                listbox_frame.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 5))

                # Scrollbar
                scrollbar = ttk.Scrollbar(listbox_frame, orient=VERTICAL)
                scrollbar.pack(side=RIGHT, fill=Y)

                # Listbox with multi-select (tkinter widget, not ttk)
                self.plate_listbox = tkinter.Listbox(
                    listbox_frame,
                    selectmode='multiple',
                    height=8,
                    yscrollcommand=scrollbar.set,
                    font=("Segoe UI", 9),
                    exportselection=False  # CRITICAL: Prevent selection loss on focus change
                )
                self.plate_listbox.pack(side=LEFT, fill=BOTH, expand=True)
                scrollbar.config(command=self.plate_listbox.yview)

                # Add SELECT ALL as first item
                self.plate_listbox.insert(END, "☑️ SELECIONAR TODOS")

                # Add all plates
                for terminal in self.terminals:
                    self.plate_listbox.insert(END, f"  {terminal['plate']}")

                # Bind selection event
                self.plate_listbox.bind('<<ListboxSelect>>', self.on_listbox_selection)

                # Controls frame (selection counter + manual entry button)
                controls_frame = ttk.Frame(plate_container)
                controls_frame.pack(side=LEFT, fill=Y, padx=(10, 0))

                # Selection counter (blue text, centered)
                self.selection_label = ttk.Label(
                    controls_frame,
                    text=f"0 de {len(self.terminals)}",
                    font=("Segoe UI", 10, "bold"),
                    foreground="#74c0fc"
                )
                self.selection_label.pack(anchor=CENTER, pady=(0, 10))

                # Manual entry button
                ttk.Button(
                    controls_frame,
                    text="✍️ Entrada\nManual",
                    command=self.open_manual_entry,
                    bootstyle="warning-outline",
                    width=12
                ).pack(anchor=CENTER)

            # EDIT/ADD COMMAND mode: Single-select combobox
            else:
                # Build plate list for dropdown
                plate_values = [terminal['plate'] for terminal in self.terminals]

                self.name_combo = ttk.Combobox(
                    plate_container,
                    textvariable=self.name_var,
                    values=plate_values,
                    width=25
                )
                self.name_combo.pack(side=LEFT, padx=(0, 5))
                self.name_combo.bind('<<ComboboxSelected>>', self.on_plate_selected)
                self.name_combo.bind('<KeyRelease>', self.on_plate_search)

                # Refresh button
                ttk.Button(
                    plate_container,
                    text="🔄",
                    command=self.refresh_terminals,
                    bootstyle="info-outline",
                    width=3
                ).pack(side=LEFT)

                # API indicator
                api_label = ttk.Label(
                    plate_container,
                    text=f"({len(self.terminals)} STR-CAM disponíveis)",
                    font=("Segoe UI", 8),
                    foreground="#51cf66"
                )
                api_label.pack(side=LEFT, padx=5)
        else:
            # Fallback: Manual entry if API unavailable
            ttk.Entry(
                plate_container,
                textvariable=self.name_var,
                width=25
            ).pack(side=LEFT)

            # Warning label
            warning_label = ttk.Label(
                plate_container,
                text="(API indisponível - entrada manual)",
                font=("Segoe UI", 8),
                foreground="#ffd43b"
            )
            warning_label.pack(side=LEFT, padx=5)

        # ==== SIM Card Number ====
        # In multi-select mode, show selected SIM numbers
        if self.is_add_new_mode and self.terminals and len(self.terminals) > 0:
            ttk.Label(frame, text="Nr SIM Card:").grid(row=1, column=0, sticky=NW, pady=10, padx=5)

            # Create scrollable container for SIM display with max height
            sim_container = ttk.Frame(frame)
            sim_container.grid(row=1, column=1, sticky=NSEW, pady=10, padx=5)

            # Create canvas with scrollbar for SIM display
            sim_canvas = ttk.Canvas(sim_container, height=80)  # Max height: 80px
            sim_scrollbar = ttk.Scrollbar(sim_container, orient=VERTICAL, command=sim_canvas.yview)
            sim_scrollable_frame = ttk.Frame(sim_canvas)

            sim_scrollable_frame.bind(
                "<Configure>",
                lambda e: sim_canvas.configure(scrollregion=sim_canvas.bbox("all"))
            )

            sim_canvas.create_window((0, 0), window=sim_scrollable_frame, anchor=NW)
            sim_canvas.configure(yscrollcommand=sim_scrollbar.set)

            sim_canvas.pack(side=LEFT, fill=BOTH, expand=True)
            sim_scrollbar.pack(side=RIGHT, fill=Y)

            # Create StringVar for dynamic SIM display
            self.sim_display_var = ttk.StringVar(value="(Nenhuma placa selecionada)")

            self.sim_display_label = ttk.Label(
                sim_scrollable_frame,
                textvariable=self.sim_display_var,
                font=("Segoe UI", 9),
                foreground="#51cf66",
                wraplength=600  # Allow text to wrap if many SIMs
            )
            self.sim_display_label.pack(fill=BOTH, expand=True)
        else:
            # Single-select mode: show SIM field
            ttk.Label(frame, text="Nr SIM Card:").grid(row=1, column=0, sticky=W, pady=10, padx=5)
            self.phone_var = ttk.StringVar(value=camera['phone'] if camera else '')

            # Make SIM field read-only if using API (auto-filled)
            sim_state = 'readonly' if (self.terminals and len(self.terminals) > 0) else 'normal'
            self.phone_entry = ttk.Entry(frame, textvariable=self.phone_var, width=25, state=sim_state)
            self.phone_entry.grid(row=1, column=1, sticky=W, pady=10, padx=5)

        # Command Selection Dropdown
        ttk.Label(frame, text="Selecionar Comando:").grid(row=2, column=0, sticky=W, pady=10, padx=5)

        # Build command list: descriptions
        self.command_list = ["(Nenhum - digitar manualmente)"]  # First option for manual entry
        self.command_map = {}  # Map description to command data

        for cmd in self.parent.command_patterns:
            desc = cmd['description']
            self.command_list.append(desc)
            self.command_map[desc] = cmd

        # Pre-select command if editing
        initial_dropdown_value = self.command_list[0]
        if command_data and command_data.get('command_type'):
            # Find the command in patterns by command_type
            for desc, cmd in self.command_map.items():
                if cmd['id'] == command_data['command_type']:
                    initial_dropdown_value = desc
                    break

        self.command_select_var = ttk.StringVar(value=initial_dropdown_value)
        command_dropdown = ttk.Combobox(
            frame,
            textvariable=self.command_select_var,
            values=self.command_list,
            state='readonly',
            width=80
        )
        command_dropdown.grid(row=2, column=1, sticky=EW, pady=10, padx=5)
        command_dropdown.bind('<<ComboboxSelected>>', self.on_command_selected)

        # Command input with Add button (only in add_new_mode)
        ttk.Label(frame, text="Comando SMS:").grid(row=3, column=0, sticky=W, pady=10, padx=5)

        # Container for command field + add button
        command_input_frame = ttk.Frame(frame)
        command_input_frame.grid(row=3, column=1, sticky=EW, pady=10, padx=5)

        initial_command_value = command_data.get('command', '') if command_data else ''
        self.command_var = ttk.StringVar(value=initial_command_value)

        command_entry = ttk.Entry(command_input_frame, textvariable=self.command_var)
        command_entry.pack(side=LEFT, fill=X, expand=True, padx=(0, 5))

        # Only show "Add to queue" button in add_new_mode
        if self.is_add_new_mode and self.terminals and len(self.terminals) > 0:
            ttk.Button(
                command_input_frame,
                text="➕ Adicionar",
                command=self.add_command_to_queue,
                bootstyle="success",
                width=12
            ).pack(side=LEFT)

            # Command Queue Section (only in add_new_mode)
            ttk.Label(frame, text="Comandos a enviar:").grid(row=4, column=0, sticky=NW, pady=10, padx=5)

            # Command queue container
            queue_container = ttk.Frame(frame)
            queue_container.grid(row=4, column=1, sticky=NSEW, pady=10, padx=5)

            # Configure frame row to expand
            frame.rowconfigure(4, weight=1)

            # Listbox frame with scrollbar
            listbox_frame = ttk.Frame(queue_container)
            listbox_frame.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 5))

            # Scrollbar
            queue_scrollbar = ttk.Scrollbar(listbox_frame, orient=VERTICAL)
            queue_scrollbar.pack(side=RIGHT, fill=Y)

            # Command queue listbox with minimum height to show all 3 buttons
            self.command_queue_listbox = tkinter.Listbox(
                listbox_frame,
                height=8,  # Increased from 6 to 8 for better visibility
                yscrollcommand=queue_scrollbar.set,
                font=("Segoe UI", 9),
                selectmode='single'
            )
            self.command_queue_listbox.pack(side=LEFT, fill=BOTH, expand=True)
            queue_scrollbar.config(command=self.command_queue_listbox.yview)

            # Set minimum height for listbox frame to ensure buttons are visible
            listbox_frame.configure(height=150)  # Min 150px to show all 3 buttons

            # Control buttons frame (up/down/delete)
            controls_frame = ttk.Frame(queue_container)
            controls_frame.pack(side=LEFT, fill=Y)

            ttk.Button(
                controls_frame,
                text="▲",
                command=self.move_command_up,
                bootstyle="info-outline",
                width=3
            ).pack(pady=(0, 5))

            ttk.Button(
                controls_frame,
                text="▼",
                command=self.move_command_down,
                bootstyle="info-outline",
                width=3
            ).pack(pady=(0, 5))

            ttk.Button(
                controls_frame,
                text="❌",
                command=self.remove_command_from_queue,
                bootstyle="danger-outline",
                width=3
            ).pack()

            # Command queue storage
            self.command_queue = []  # List of {command, command_type}

        # EXPLANATION AREA - Only show for non-multi-select ADD NEW mode
        # (In multi-select mode, row 4 is used for command queue)
        if not self.is_edit_mode and not (self.is_add_new_mode and self.terminals and len(self.terminals) > 0):
            ttk.Label(frame, text="Explicação:").grid(row=4, column=0, sticky=NW, pady=5, padx=5)

            # Text widget for multi-line explanation with scrollbar
            explanation_container = ttk.Frame(frame)
            explanation_container.grid(row=4, column=1, sticky=NSEW, pady=5, padx=5)

            # Configure container to expand
            frame.rowconfigure(4, weight=1)

            # Scrollbar
            explanation_scroll = ttk.Scrollbar(explanation_container)
            explanation_scroll.pack(side=RIGHT, fill=Y)

            # Text widget
            self.explanation_text = ttk.Text(
                explanation_container,
                height=10,
                width=80,
                wrap='word',
                state='disabled',
                font=('Segoe UI', 9),
                yscrollcommand=explanation_scroll.set
            )
            self.explanation_text.pack(side=LEFT, fill=BOTH, expand=True)
            explanation_scroll.config(command=self.explanation_text.yview)

            # If editing with pre-selected command, populate explanation
            if initial_dropdown_value != self.command_list[0]:
                self.populate_explanation(initial_dropdown_value)

        # Buttons - adjust row based on mode
        if self.is_add_new_mode and self.terminals and len(self.terminals) > 0:
            button_row = 5  # After command queue
        elif not self.is_edit_mode:
            button_row = 5  # After explanation (fallback mode)
        else:
            button_row = 4  # Edit mode (no queue, no explanation)
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=button_row, column=0, columnspan=2, pady=(20, 0))

        ttk.Button(
            btn_frame,
            text="✓ Salvar",
            command=self.on_save,
            bootstyle="success",
            width=12
        ).pack(side=LEFT, padx=5)

        ttk.Button(
            btn_frame,
            text="✗ Cancelar",
            command=self.destroy,
            bootstyle="secondary",
            width=12
        ).pack(side=LEFT, padx=5)

        # Make modal
        self.transient(parent)
        self.grab_set()

        # Set size and center window AFTER all widgets are created
        self.update_idletasks()

        # Set appropriate size based on mode
        if self.is_edit_mode:
            # EDIT mode: compact, no explanation
            # Calculate natural height needed for content
            self.update_idletasks()
            natural_height = self.winfo_reqheight()
            # Add some padding to ensure buttons are visible
            height = max(natural_height + 40, 300)
            width = 935
        else:
            # ADD NEW mode: larger with command queue
            width = 935
            height = 750  # Increased from 580 to accommodate SIM display + command queue

        # Center on screen
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'{width}x{height}+{x}+{y}')

    def add_command_to_queue(self):
        """Add command to the queue"""
        command = self.command_var.get().strip()

        if not command:
            Messagebox.show_warning("Digite um comando antes de adicionar", "Comando Vazio")
            return

        # Identify command type
        command_type = self.parent.identify_command_type(command)

        # Add to queue
        self.command_queue.append({
            'command': command,
            'command_type': command_type
        })

        # Update listbox display
        self.update_command_queue_display()

        # Clear command field
        self.command_var.set("")

    def update_command_queue_display(self):
        """Update command queue listbox display"""
        if not hasattr(self, 'command_queue_listbox'):
            return

        # Clear listbox
        self.command_queue_listbox.delete(0, END)

        # Add all commands
        for idx, cmd in enumerate(self.command_queue):
            display_text = f"{idx + 1}. {cmd['command']}"
            self.command_queue_listbox.insert(END, display_text)

    def move_command_up(self):
        """Move selected command up in queue"""
        if not hasattr(self, 'command_queue_listbox'):
            return

        selected = self.command_queue_listbox.curselection()
        if not selected:
            Messagebox.show_info("Selecione um comando para mover", "Nenhuma Seleção")
            return

        idx = selected[0]
        if idx == 0:
            return  # Already at top

        # Swap with previous
        self.command_queue[idx], self.command_queue[idx - 1] = \
            self.command_queue[idx - 1], self.command_queue[idx]

        # Update display
        self.update_command_queue_display()

        # Reselect at new position
        self.command_queue_listbox.selection_set(idx - 1)

    def move_command_down(self):
        """Move selected command down in queue"""
        if not hasattr(self, 'command_queue_listbox'):
            return

        selected = self.command_queue_listbox.curselection()
        if not selected:
            Messagebox.show_info("Selecione um comando para mover", "Nenhuma Seleção")
            return

        idx = selected[0]
        if idx >= len(self.command_queue) - 1:
            return  # Already at bottom

        # Swap with next
        self.command_queue[idx], self.command_queue[idx + 1] = \
            self.command_queue[idx + 1], self.command_queue[idx]

        # Update display
        self.update_command_queue_display()

        # Reselect at new position
        self.command_queue_listbox.selection_set(idx + 1)

    def remove_command_from_queue(self):
        """Remove selected command from queue"""
        if not hasattr(self, 'command_queue_listbox'):
            return

        selected = self.command_queue_listbox.curselection()
        if not selected:
            Messagebox.show_info("Selecione um comando para remover", "Nenhuma Seleção")
            return

        idx = selected[0]

        # Remove from queue
        del self.command_queue[idx]

        # Update display
        self.update_command_queue_display()

    def on_listbox_selection(self, event=None):
        """Handle listbox selection changes - implement SELECT ALL logic and update SIM display"""
        if not hasattr(self, 'plate_listbox'):
            return

        selected_indices = self.plate_listbox.curselection()

        # Check if SELECT ALL (index 0) is selected
        if 0 in selected_indices:
            # Get current state
            all_selected = len(selected_indices) == self.plate_listbox.size()

            # Clear all selections
            self.plate_listbox.selection_clear(0, END)

            # If not all were selected, select all (except SELECT ALL itself)
            if not all_selected:
                for i in range(1, self.plate_listbox.size()):
                    self.plate_listbox.selection_set(i)

                # Update SELECT ALL text
                self.plate_listbox.delete(0)
                self.plate_listbox.insert(0, "☑️ SELECIONAR TODOS")
            else:
                # Update SELECT ALL text
                self.plate_listbox.delete(0)
                self.plate_listbox.insert(0, "☑️ SELECIONAR TODOS")

        # Update selection counter
        selected_count = len(self.plate_listbox.curselection())
        if hasattr(self, 'selection_label'):
            self.selection_label.config(text=f"{selected_count} de {len(self.terminals)}")

        # Update SIM card display (multi-select mode only)
        if hasattr(self, 'sim_display_var'):
            selected_indices = self.plate_listbox.curselection()

            if not selected_indices:
                self.sim_display_var.set("(Nenhuma placa selecionada)")
            else:
                # Get SIM numbers for selected plates
                sim_numbers = []
                for idx in selected_indices:
                    plate_text = self.plate_listbox.get(idx).strip()

                    # Find terminal by plate
                    for terminal in self.terminals:
                        if terminal['plate'] == plate_text:
                            sim_numbers.append(terminal['sim'])
                            break

                # Display comma-separated SIM numbers
                if sim_numbers:
                    self.sim_display_var.set(", ".join(sim_numbers))
                else:
                    self.sim_display_var.set("(Nenhuma placa selecionada)")

    def open_manual_entry(self):
        """Open manual entry dialog for plate and SIM number"""
        # Create modal dialog
        dialog = ttk.Toplevel(self)
        dialog.title("Entrada Manual")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()

        # Set icon
        try:
            dialog.iconbitmap("favicon.ico")
        except:
            pass  # Ignore if icon file not found

        # Center dialog
        dialog.update_idletasks()
        width = 400
        height = 250  # Increased from 200 to 250 to fit all content
        x = (dialog.winfo_screenwidth() // 2) - (width // 2)
        y = (dialog.winfo_screenheight() // 2) - (height // 2)
        dialog.geometry(f'{width}x{height}+{x}+{y}')

        # Frame
        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=BOTH, expand=True)

        # Plate name field
        ttk.Label(frame, text="Placa:").grid(row=0, column=0, sticky=W, pady=10, padx=5)
        plate_var = ttk.StringVar()
        plate_entry = ttk.Entry(frame, textvariable=plate_var, width=30)
        plate_entry.grid(row=0, column=1, sticky=EW, pady=10, padx=5)
        plate_entry.focus()

        # SIM number field
        ttk.Label(frame, text="Nr SIM Card:").grid(row=1, column=0, sticky=W, pady=10, padx=5)
        sim_var = ttk.StringVar()
        sim_entry = ttk.Entry(frame, textvariable=sim_var, width=30)
        sim_entry.grid(row=1, column=1, sticky=EW, pady=10, padx=5)

        # Info label
        info_label = ttk.Label(
            frame,
            text="Inclua + para números internacionais\n(ex: +5511999999999 ou 11999999999)",
            font=("Segoe UI", 8),
            foreground="#74c0fc"
        )
        info_label.grid(row=2, column=0, columnspan=2, pady=5)

        # Result variable
        result = {'plate': None, 'sim': None}

        def on_ok():
            plate = plate_var.get().strip()
            sim = sim_var.get().strip()

            if not plate:
                Messagebox.show_warning("Por favor, preencha a Placa", "Campo Obrigatório", parent=dialog)
                return

            if not sim:
                Messagebox.show_warning("Por favor, preencha o Nr SIM Card", "Campo Obrigatório", parent=dialog)
                return

            result['plate'] = plate
            result['sim'] = sim
            dialog.destroy()

        def on_cancel():
            dialog.destroy()

        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=3, column=0, columnspan=2, pady=20)

        ttk.Button(
            btn_frame,
            text="✓ OK",
            command=on_ok,
            bootstyle="success",
            width=12
        ).pack(side=LEFT, padx=5)

        ttk.Button(
            btn_frame,
            text="✗ Cancelar",
            command=on_cancel,
            bootstyle="secondary",
            width=12
        ).pack(side=LEFT, padx=5)

        # Wait for dialog to close
        self.wait_window(dialog)

        # If user entered data, add to terminals list and select it
        if result['plate'] and result['sim']:
            # Create manual terminal entry
            manual_terminal = {
                'plate': result['plate'],
                'sim': result['sim'],
                'id': -1,  # Special ID for manual entries
                'imei': 'MANUAL',
                'model': 'MANUAL',
                'company': 'MANUAL'
            }

            # Add to terminals list if not already there
            plate_exists = any(t['plate'] == result['plate'] for t in self.terminals)
            if not plate_exists:
                self.terminals.append(manual_terminal)
                # Add to listbox
                self.plate_listbox.insert(END, f"  {result['plate']}")

            # Select the manual entry in listbox
            for i in range(1, self.plate_listbox.size()):  # Skip index 0 (SELECT ALL)
                if self.plate_listbox.get(i).strip() == result['plate']:
                    self.plate_listbox.selection_set(i)
                    break

            # Update selection counter and SIM display
            self.on_listbox_selection()

    def on_plate_selected(self, event=None):
        """Handle plate selection from dropdown - auto-fill SIM card"""
        selected_plate = self.name_var.get()

        # Find terminal by plate
        for terminal in self.terminals:
            if terminal['plate'] == selected_plate:
                # Auto-fill SIM card number
                sim = terminal['sim']
                self.phone_var.set(sim)
                break

    def on_plate_search(self, event=None):
        """Handle plate search/filter as user types"""
        if not hasattr(self, 'name_combo'):
            return

        search_text = self.name_var.get().upper()

        # Filter terminals by search text
        filtered_terminals = search_terminals(self.terminals, search_text)

        # Update combobox values
        plate_values = [terminal['plate'] for terminal in filtered_terminals]
        self.name_combo.config(values=plate_values)

    def refresh_terminals(self):
        """Refresh terminal list from API"""
        # Call parent's refresh method
        self.parent.refresh_api_terminals()

        # Wait a bit for refresh to complete, then update dialog
        self.after(2000, self._update_terminal_list)

    def _update_terminal_list(self):
        """Update terminal list after refresh"""
        # Get fresh terminal list from parent
        self.terminals = self.parent.str_cam_terminals

        # Update combobox if it exists
        if hasattr(self, 'name_combo'):
            plate_values = [terminal['plate'] for terminal in self.terminals]
            self.name_combo.config(values=plate_values)

    def on_command_selected(self, event=None):
        """Handle command selection from dropdown"""
        selected_desc = self.command_select_var.get()

        # If manual entry selected, clear command field and explanation
        if selected_desc == "(Nenhum - digitar manualmente)":
            self.command_var.set("")
            if not self.is_edit_mode:
                self.update_explanation("")
            return

        # Get command data from map
        if selected_desc in self.command_map:
            cmd_data = self.command_map[selected_desc]
            example = cmd_data.get('example', '')

            # Auto-fill command field with example
            self.command_var.set(example)

            # Update explanation (only in ADD NEW mode)
            if not self.is_edit_mode:
                explanation = cmd_data.get('explanation_pt', '')
                self.update_explanation(explanation)

    def update_explanation(self, text):
        """Update explanation text widget (only used in ADD NEW mode)"""
        if not hasattr(self, 'explanation_text'):
            return

        self.explanation_text.config(state='normal')
        self.explanation_text.delete('1.0', 'end')

        if text:
            self.explanation_text.insert('1.0', text)
        else:
            self.explanation_text.insert('1.0', "(Nenhuma explicação disponível)")

        self.explanation_text.config(state='disabled')

    def populate_explanation(self, selected_desc):
        """Populate explanation for a given command (only used in ADD NEW mode)"""
        if selected_desc in self.command_map:
            cmd_data = self.command_map[selected_desc]
            explanation = cmd_data.get('explanation_pt', '')
            self.update_explanation(explanation)

    def on_save(self):
        # Multi-select mode with command queue: Handle multiple terminals × multiple commands
        if hasattr(self, 'command_queue_listbox') and hasattr(self, 'plate_listbox'):
            selected_indices = self.plate_listbox.curselection()

            if not selected_indices:
                Messagebox.show_warning("Por favor, selecione pelo menos uma placa", "Erro de Validação")
                return

            if not self.command_queue:
                Messagebox.show_warning("Por favor, adicione pelo menos um comando à fila", "Erro de Validação")
                return

            # Build list of results (terminal × command combinations)
            results = []

            for idx in selected_indices:
                # Get plate text (format: "  PLATE_NAME")
                plate_text = self.plate_listbox.get(idx).strip()

                # Find terminal by plate
                terminal = None
                for t in self.terminals:
                    if t['plate'] == plate_text:
                        terminal = t
                        break

                if terminal:
                    # Create one entry for each command
                    # Add +55 country code if phone doesn't start with +
                    phone = terminal['sim']
                    if not phone.startswith('+'):
                        phone = '+55' + phone

                    for cmd in self.command_queue:
                        results.append({
                            'name': terminal['plate'],
                            'phone': phone,
                            'command': cmd['command'],
                            'command_type': cmd['command_type']
                        })

            if not results:
                Messagebox.show_warning("Nenhuma combinação válida de placa/comando", "Erro de Validação")
                return

            # Set result as list
            self.result = results
            self.destroy()

        # Single-select mode (Edit/Add Command to existing): Handle single selection
        else:
            command = self.command_var.get().strip()

            if not command:
                Messagebox.show_warning("Por favor, preencha o Comando SMS", "Erro de Validação")
                return

            # Identify command type
            command_type = self.parent.identify_command_type(command)

            name = self.name_var.get().strip()
            phone = self.phone_var.get().strip() if hasattr(self, 'phone_var') else ''

            if not name or not phone:
                Messagebox.show_warning("Por favor, preencha Nome e Telefone", "Erro de Validação")
                return

            # Set result as single dict
            self.result = {
                'name': name,
                'phone': phone,
                'command': command,
                'command_type': command_type
            }
            self.destroy()

# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    app = SMSAutomationApp()
    app.mainloop()