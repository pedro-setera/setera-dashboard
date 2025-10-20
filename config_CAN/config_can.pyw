#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SETERA - Atualização e Configuração - Leitor CANBUS
Versão: 1.7
Data: 17Out2025
Descrição: Software para atualização de firmware e configuração de dispositivos leitores CANBUS
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import serial
import serial.tools.list_ports
import threading
import time
from datetime import datetime
import os
import re
import json

class CANBusUpdater:
    def parse_version(self, version_str):
        """Parse version string into comparable components (major, minor, patch, letter)

        Args:
            version_str: Version string like "3.0.18b" or "1.2.58"

        Returns:
            Tuple of (major, minor, patch, letter) where letter is '' if not present
        """
        try:
            # Remove any 'v' prefix if present
            version_str = version_str.lstrip('vV')

            # Check if there's a letter suffix
            letter = ''
            if version_str and version_str[-1].isalpha():
                letter = version_str[-1].lower()
                version_str = version_str[:-1]

            # Split by dots
            parts = version_str.split('.')
            major = int(parts[0]) if len(parts) > 0 else 0
            minor = int(parts[1]) if len(parts) > 1 else 0
            patch = int(parts[2]) if len(parts) > 2 else 0

            return (major, minor, patch, letter)
        except Exception as e:
            self.log_message(f"Erro ao parsear versão '{version_str}': {str(e)}", 'error')
            return (0, 0, 0, '')

    def compare_versions(self, version1, version2):
        """Compare two version strings

        Args:
            version1: First version string (e.g., "3.0.18b")
            version2: Second version string (e.g., "3.0.12d")

        Returns:
            -1 if version1 < version2
             0 if version1 == version2
             1 if version1 > version2
        """
        v1 = self.parse_version(version1)
        v2 = self.parse_version(version2)

        # Compare major, minor, patch
        for i in range(3):
            if v1[i] < v2[i]:
                return -1
            elif v1[i] > v2[i]:
                return 1

        # If numbers are equal, compare letter suffix
        # No letter < any letter, and letters are compared alphabetically
        if v1[3] == v2[3]:
            return 0
        elif v1[3] == '':
            return -1  # No letter is less than any letter
        elif v2[3] == '':
            return 1   # Any letter is greater than no letter
        else:
            # Both have letters, compare alphabetically
            if v1[3] < v2[3]:
                return -1
            else:
                return 1

    def find_firmware_files_by_serial(self, folder_path, serial_number):
        """Search folder for firmware files matching the device serial number

        Args:
            folder_path: Path to folder to search
            serial_number: Device serial number to match

        Returns:
            Tuple of (matched_files, error_message)
            - matched_files: List of tuples [(file_path, version), ...]
            - error_message: String with error description if any, None otherwise
        """
        try:
            matched_files = []

            # List all .frm files in the folder
            if not os.path.isdir(folder_path):
                return ([], "Pasta selecionada não existe")

            files = [f for f in os.listdir(folder_path) if f.endswith('.frm')]

            if not files:
                return ([], "Nenhum arquivo .frm encontrado na pasta selecionada")

            # Pattern: CL_v{version}_sn{serial}_asc.frm
            # Example: CL_v3.0.18b_sn3035331_asc.frm
            pattern = r'^CL_v(.+?)_sn(\d+)_asc\.frm$'

            for filename in files:
                match = re.match(pattern, filename)
                if match:
                    file_version = match.group(1)  # e.g., "3.0.18b"
                    file_serial = match.group(2)   # e.g., "3035331"

                    # Check if serial number matches
                    if file_serial == serial_number:
                        full_path = os.path.join(folder_path, filename)
                        matched_files.append((full_path, file_version))
                        self.log_message(f"Arquivo encontrado: {filename} (versão {file_version})", 'info')

            # Check results
            if len(matched_files) == 0:
                return ([], f"Nenhum arquivo de firmware encontrado para o número de série {serial_number}")
            elif len(matched_files) > 1:
                # Multiple files found - select the one with the highest version
                self.log_message(f"Múltiplos arquivos encontrados para SN {serial_number}:", 'info')

                # Log all files found
                for file_path, version in matched_files:
                    self.log_message(f"  - {os.path.basename(file_path)} (versão {version})", 'info')

                # Create list of tuples with (file_path, version, parsed_version_tuple)
                files_with_parsed_versions = []
                for file_path, version in matched_files:
                    parsed = self.parse_version(version)
                    files_with_parsed_versions.append((file_path, version, parsed))

                # Sort by parsed version tuple (descending order)
                # Tuple comparison works perfectly: (3, 1, 12, '') > (3, 0, 22, 'b')
                files_with_parsed_versions.sort(key=lambda x: x[2], reverse=True)

                # Get the highest version file
                highest_file_path, highest_version, _ = files_with_parsed_versions[0]

                self.log_message(f"Selecionado automaticamente: {os.path.basename(highest_file_path)} (versão {highest_version})", 'success')

                # Return only the highest version file
                return ([(highest_file_path, highest_version)], None)
            else:
                return (matched_files, None)

        except Exception as e:
            error_msg = f"Erro ao buscar arquivos de firmware: {str(e)}"
            self.log_message(error_msg, 'error')
            return ([], error_msg)

    def load_config(self):
        """Load configuration from JSON file"""
        config_file = os.path.join(os.path.dirname(__file__), 'config.json')
        try:
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    return config
        except Exception as e:
            self.log_message(f"Erro ao carregar configuração: {str(e)}", 'error')
        return {}

    def save_config(self, config_data):
        """Save configuration to JSON file"""
        config_file = os.path.join(os.path.dirname(__file__), 'config.json')
        try:
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            self.log_message(f"Erro ao salvar configuração: {str(e)}", 'error')

    def extract_fw_and_sn_from_versions(self, response):
        """Extract firmware version and serial number from VERSIONS command response

        Supports two formats:
        - Old format (v2 devices): "VERSION 2.3.8 SN1063641"
        - New format (v3+ devices): "VERSIONS FW3.0.18b HW3.0.5 BL3.0.12 SN3035331"

        Returns: tuple (firmware_version, serial_number, is_v2) or (None, None, False) if parsing fails
        """
        try:
            parts = response.split()
            fw_version = None
            serial_number = None
            is_v2 = False  # Default to V3+

            # Detect if it's V2 or V3 based on first word
            if parts and parts[0] == 'VERSION':
                # V2 format (singular)
                is_v2 = True
            elif parts and parts[0] == 'VERSIONS':
                # V3+ format (plural)
                is_v2 = False

            # FIRST: Check for new format with FW prefix (VERSIONS FW3.0.18b ...)
            # This must be checked BEFORE the old format to avoid picking up BL or HW versions
            for part in parts:
                if part.startswith('FW'):
                    fw_version = part[2:]  # Remove 'FW' prefix
                    break

            # Find serial number (same in both formats)
            for part in parts:
                if part.startswith('SN'):
                    serial_number = part[2:]  # Remove 'SN' prefix
                    break

            # SECOND: If FW not found, check for old format (VERSION 2.3.8 SN1063641)
            # In old format, the version is the part BEFORE 'SN'
            if fw_version is None:
                for i, part in enumerate(parts):
                    if part.startswith('SN') and i > 0:
                        # Make sure the previous part is not a keyword like "VERSION" or "VERSIONS"
                        if not parts[i-1].upper().startswith('VERSION'):
                            fw_version = parts[i-1]
                        break

            return (fw_version, serial_number, is_v2)

        except Exception as e:
            return (None, None, False)

    def __init__(self, root):
        self.root = root
        self.root.title("Atualização e Configuração - Leitor CANBUS - v1.7 - 17Out2025")
        self.root.geometry("900x700")
        self.root.state('zoomed')  # Start maximized
        self.root.resizable(True, True)

        # Set icon
        icon_path = os.path.join(os.path.dirname(__file__), "favicon.ico")
        if os.path.exists(icon_path):
            try:
                self.root.iconbitmap(icon_path)
            except:
                pass

        # Serial port variables
        self.serial_port = None
        self.is_connected = False
        self.baud_rate = 115200

        # Firmware variables
        self.firmware_file = None
        self.firmware_frames = []
        self.firmware_info = {}
        self.firmware_file_version = None  # Version extracted from firmware filename
        self.update_in_progress = False
        self.current_frame_index = 0
        self.suppress_frame_logging = False  # Flag to suppress firmware frame logs during update

        # Configuration parameters for LIMITS command
        self.speed_limit = 90  # Default 90 km/h
        self.rpm_limit = 2400  # Default 2400 RPM

        # Folder path persistence
        self.last_folder_path = None  # Last selected folder for firmware files

        # Auto-update mode for multiple devices
        self.auto_update_mode = False  # Flag to indicate if auto-update is active
        self.polling_active = False  # Flag to control VERSIONS polling loop

        # Device state variables
        self.device_fw_version = None
        self.device_serial_number = None
        self.device_is_v2 = False  # Flag to indicate if device is V2 (vs V3+)
        self.fr1_received = False
        self.device_ready = False
        self.last_fr1_time = None  # Timestamp of last FR1 frame
        self.monitoring_active = False  # Flag to control activity monitoring

        # Protocol headers and footers
        self.req_header = ""
        self.req_footer = "\r\n"
        self.rpl_header = ""
        self.rpl_footer = "\r\n"

        # Response handling
        self.waiting_for_response = False
        self.expected_response_prefix = None  # Filter responses by prefix during firmware update
        self.last_response = None
        self.response_event = threading.Event()

        # Create UI
        self.create_widgets()

        # Start COM port refresh timer
        self.refresh_com_ports()

        # Load saved configuration (last folder path)
        saved_config = self.load_config()
        if 'last_folder_path' in saved_config:
            self.last_folder_path = saved_config['last_folder_path']
            self.log_message(f"Pasta salva carregada: {self.last_folder_path}", 'info')

    def create_widgets(self):
        """Create all UI widgets"""
        # Top frame for COM port and firmware selection
        top_frame = ttk.Frame(self.root, padding="10")
        top_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N), padx=5, pady=5)

        # COM Port selection (no label, just dropdown)
        self.com_port_var = tk.StringVar()
        self.com_port_combo = ttk.Combobox(top_frame, textvariable=self.com_port_var,
                                           width=15, state='readonly')
        self.com_port_combo.grid(row=0, column=0, padx=5)

        # Connect/Disconnect button
        self.connect_button = ttk.Button(top_frame, text="CONECTAR",
                                         command=self.toggle_connection, width=15)
        self.connect_button.grid(row=0, column=1, padx=10)

        # Configure button styles with proper color mapping
        self.button_style = ttk.Style()

        # Red button style (disabled state)
        self.button_style.configure("Red.TButton", background='red', foreground='black')
        self.button_style.map("Red.TButton",
                              background=[('disabled', 'red'), ('active', 'red')],
                              foreground=[('disabled', 'black'), ('active', 'black')])

        # Green button style (enabled state)
        self.button_style.configure("Green.TButton", background='green', foreground='black')
        self.button_style.map("Green.TButton",
                              background=[('!disabled', 'green'), ('active', 'darkgreen')],
                              foreground=[('!disabled', 'black'), ('active', 'black')])

        # Start Update button
        self.update_button = ttk.Button(top_frame, text="INICIAR UPDATE",
                                        command=self.start_firmware_update, width=20,
                                        state='disabled', style='Red.TButton')
        self.update_button.grid(row=0, column=2, padx=10)

        # Configure button (standalone configuration without firmware update)
        self.configure_button = ttk.Button(top_frame, text="CONFIGURAR",
                                          command=self.on_configure_button_clicked, width=15,
                                          state='disabled', style='Red.TButton')
        self.configure_button.grid(row=0, column=3, padx=10)

        # Clear Log button
        self.clear_log_button = ttk.Button(top_frame, text="LIMPAR LOG",
                                           command=self.clear_log, width=15)
        self.clear_log_button.grid(row=0, column=4, padx=10)

        # Save Log button
        self.save_log_button = ttk.Button(top_frame, text="SALVAR LOG",
                                          command=self.save_log, width=15)
        self.save_log_button.grid(row=0, column=5, padx=10)

        # Device info label (firmware version and serial number)
        self.device_label = ttk.Label(top_frame, text="Dispositivo: Desconectado",
                                      foreground="gray")
        self.device_label.grid(row=1, column=0, columnspan=6, sticky=tk.W, padx=5, pady=(5,0))

        # Firmware info label
        self.firmware_label = ttk.Label(top_frame, text="Nenhum firmware selecionado",
                                        foreground="gray")
        self.firmware_label.grid(row=2, column=0, columnspan=6, sticky=tk.W, padx=5, pady=(0,0))

        # Progress frame
        progress_frame = ttk.Frame(self.root, padding="5")
        progress_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), padx=5, pady=(0,5))

        # Progress bar
        self.progress_var = tk.DoubleVar()
        style = ttk.Style()
        style.configure("green.Horizontal.TProgressbar", foreground='green', background='green')
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var,
                                            maximum=100, mode='determinate',
                                            style="green.Horizontal.TProgressbar")
        self.progress_bar.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=5)
        progress_frame.columnconfigure(0, weight=1)

        # Progress percentage label
        self.progress_label = ttk.Label(progress_frame, text="0%")
        self.progress_label.grid(row=0, column=1, padx=5)

        # Log frame
        log_frame = ttk.LabelFrame(self.root, text="Log de Comunicação", padding="10")
        log_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)
        self.root.rowconfigure(2, weight=1)
        self.root.columnconfigure(0, weight=1)

        # Log text widget
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD,
                                                   bg='black', fg='white',
                                                   font=('Consolas', 9))
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)

        # Configure text tags for colors
        self.log_text.tag_config('sent', foreground='white')
        self.log_text.tag_config('received', foreground='yellow')
        self.log_text.tag_config('error', foreground='orange')
        self.log_text.tag_config('success', foreground='lime')
        self.log_text.tag_config('info', foreground='cyan')

    def refresh_com_ports(self):
        """Refresh the list of available COM ports"""
        ports = serial.tools.list_ports.comports()
        port_list = [port.device for port in ports]

        current_selection = self.com_port_var.get()
        self.com_port_combo['values'] = port_list

        # Keep current selection if still available
        if current_selection in port_list:
            self.com_port_var.set(current_selection)
        elif port_list:
            self.com_port_var.set(port_list[0])
        else:
            self.com_port_var.set('')

        # Schedule next refresh after 1 second
        self.root.after(1000, self.refresh_com_ports)

    def toggle_connection(self):
        """Toggle serial port connection"""
        if self.is_connected:
            self.disconnect()
        else:
            self.connect()

    def connect(self):
        """Connect to selected COM port"""
        port = self.com_port_var.get()
        if not port:
            messagebox.showerror("Erro", "Selecione uma porta COM!")
            return

        try:
            # Timeout of 0.1s for more responsive reading in polling loop
            self.serial_port = serial.Serial(port, self.baud_rate, timeout=0.1)
            self.is_connected = True
            self.connect_button.config(text="DESCONECTAR")
            self.log_message(f"Conectado à porta {port} (115200 bps)", 'success')

            # Start reading thread
            self.read_thread = threading.Thread(target=self.read_serial, daemon=True)
            self.read_thread.start()

            # Start device wake-up procedure in separate thread
            wake_up_thread = threading.Thread(target=self.wake_up_device, daemon=True)
            wake_up_thread.start()

        except Exception as e:
            messagebox.showerror("Erro de Conexão", f"Erro ao conectar à porta {port}:\n{str(e)}")
            self.log_message(f"Erro ao conectar: {str(e)}", 'error')

    def disconnect(self):
        """Disconnect from COM port"""
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
        self.is_connected = False
        self.device_ready = False
        self.fr1_received = False
        self.device_fw_version = None
        self.device_serial_number = None

        # Stop FR1 activity monitoring
        self.monitoring_active = False
        self.last_fr1_time = None

        # Stop auto-update polling if active
        self.polling_active = False
        self.auto_update_mode = False

        self.connect_button.config(text="CONECTAR")
        self.configure_button.config(state='disabled', style='Red.TButton')
        self.update_button.config(state='disabled', style='Red.TButton')
        self.device_label.config(text="Dispositivo: Desconectado", foreground="gray")
        self.log_message("Desconectado da porta COM", 'info')

    def start_auto_update_polling(self):
        """Start polling for device changes to enable automatic multi-device updates"""
        self.auto_update_mode = True
        self.polling_active = True
        self.log_message("Modo de atualização automática ativado - aguardando troca de dispositivo...", 'info')
        self.log_message("Troque o dispositivo quando pronto. Para finalizar, clique em DESCONECTAR.", 'info')
        # Start polling in background thread
        polling_thread = threading.Thread(target=self.poll_for_new_device, daemon=True)
        polling_thread.start()

    def poll_for_new_device(self):
        """Poll VERSIONS command every 2 seconds to detect device change"""
        initial_serial = self.device_serial_number  # Remember the current device serial number

        while self.polling_active and self.is_connected:
            try:
                # Send VERSIONS command and wait for response
                response = self.send_serial("VERSIONS", wait_for_response=True, timeout=2.0, expected_prefix="VERSION")

                if response:
                    # Parse response to get serial number (supports both old and new formats)
                    _, new_serial, _ = self.extract_fw_and_sn_from_versions(response)

                    if new_serial and new_serial != initial_serial:
                        # New device detected!
                        self.log_message(f"Novo dispositivo detectado! SN: {new_serial}", 'success')
                        # Update device info and trigger automatic update
                        self.root.after(0, self.handle_new_device_detected, response)
                        return  # Exit polling loop - will be restarted after update

                # Wait 2 seconds before next poll
                time.sleep(2.0)

            except Exception as e:
                # Error in polling - likely device disconnected, continue trying
                time.sleep(2.0)

    def handle_new_device_detected(self, versions_response):
        """Handle when a new device is detected during auto-update mode"""
        try:
            # Parse VERSIONS response to update device info (supports both old and new formats)
            self.device_fw_version, self.device_serial_number, self.device_is_v2 = self.extract_fw_and_sn_from_versions(versions_response)

            if self.device_fw_version and self.device_serial_number:
                # Log device version type
                version_type = "V2" if self.device_is_v2 else "V3+"
                self.log_message(f"Dispositivo detectado como protocolo {version_type}", 'info')

                # Update UI
                device_info = f"Dispositivo: FW {self.device_fw_version} | SN {self.device_serial_number}"
                self.device_label.config(text=device_info, foreground="green")
                self.log_message(f"Novo dispositivo: FW={self.device_fw_version}, SN={self.device_serial_number}", 'success')

                # Automatically trigger update with stored settings
                self.automatic_firmware_update()

        except Exception as e:
            self.log_message(f"Erro ao processar novo dispositivo: {str(e)}", 'error')
            # Restart polling
            self.start_auto_update_polling()

    def wake_up_device(self):
        """Wake up device and get firmware version and serial number"""
        try:
            self.log_message("Iniciando sequência de ativação do dispositivo...", 'info')

            # Reset flags
            self.fr1_received = False
            self.device_ready = False

            # Send VERSIONS command with smart retry mechanism (3 attempts)
            max_retries = 3
            retry_count = 0
            version_success = False

            while retry_count < max_retries and not version_success:
                if retry_count > 0:
                    self.log_message(f"Tentativa {retry_count + 1} de {max_retries}...", 'info')

                # Reset FR1 flag before sending VERSIONS
                self.fr1_received = False

                # Send VERSIONS command
                response = self.send_serial("VERSIONS", wait_for_response=True, timeout=2.0, expected_prefix="VERSION")

                if response:
                    # Got VERSIONS response! Parse it
                    self.parse_versions_response(response)
                    version_success = True
                else:
                    # No VERSIONS response - wait up to 2 seconds checking for FR1 frames
                    retry_count += 1
                    if retry_count < max_retries:
                        self.log_message("Sem resposta, aguardando por ativação do dispositivo...", 'info')

                        # Wait up to 2 seconds, checking every 100ms for FR1 frames
                        wait_count = 0
                        max_wait = 20  # 20 * 0.1s = 2 seconds

                        while wait_count < max_wait and not self.fr1_received:
                            time.sleep(0.1)
                            wait_count += 1

                        # Check if FR1 was received during wait
                        if self.fr1_received:
                            # Device woke up! Send VERSIONS immediately
                            self.log_message("Dispositivo ativado (FR1 detectado), enviando VERSIONS...", 'info')
                            response = self.send_serial("VERSIONS", wait_for_response=True, timeout=2.0, expected_prefix="VERSION")

                            if response:
                                self.parse_versions_response(response)
                                version_success = True
                            # If no response, loop will retry
                        # If no FR1 detected, loop will retry

            if not version_success:
                # All retries failed
                error_msg = "Sem resposta do dispositivo após 3 tentativas.\n\nVerifique:\n- Reinicie o dispositivo\n- Verifique as conexões\n- Tente novamente"
                self.log_message("Erro: Falha ao obter informações do dispositivo após 3 tentativas", 'error')
                self.root.after(0, self.show_versions_failure_popup, error_msg)
                return

            # Device is ready, enable update and configure buttons
            if self.device_ready:
                self.log_message("Dispositivo pronto para atualização e configuração", 'success')
                self.root.after(0, lambda: self.configure_button.config(state='normal', style='Green.TButton'))
                self.root.after(0, lambda: self.update_button.config(state='normal', style='Green.TButton'))

                # Start FR1 activity monitoring on main thread
                self.last_fr1_time = time.time()
                self.monitoring_active = True
                self.root.after(0, self.start_fr1_monitoring)

        except Exception as e:
            self.log_message(f"Erro na ativação do dispositivo: {str(e)}", 'error')

    def parse_versions_response(self, response):
        """Parse VERSIONS command response and extract firmware version and serial number

        Supports both old format (v2 devices) and new format (v3+ devices)
        """
        try:
            # Use helper function to extract version and serial (supports both formats)
            self.device_fw_version, self.device_serial_number, self.device_is_v2 = self.extract_fw_and_sn_from_versions(response)

            if self.device_fw_version and self.device_serial_number:
                # Log device version type
                version_type = "V2" if self.device_is_v2 else "V3+"
                self.log_message(f"Dispositivo detectado como protocolo {version_type}", 'info')

                self.device_ready = True
                device_info = f"Dispositivo: FW {self.device_fw_version} | SN {self.device_serial_number}"
                self.root.after(0, lambda: self.device_label.config(text=device_info, foreground="green"))
                self.log_message(f"Informações do dispositivo: FW={self.device_fw_version}, SN={self.device_serial_number}", 'success')
            else:
                self.log_message("Erro ao parsear resposta VERSIONS", 'error')

        except Exception as e:
            self.log_message(f"Erro ao processar resposta VERSIONS: {str(e)}", 'error')

    def start_fr1_monitoring(self):
        """Start FR1 activity monitoring - must be called from main GUI thread"""
        self.log_message("Iniciando monitoramento de atividade FR1", 'info')
        # Schedule first check in 1 second
        self.root.after(1000, self.check_fr1_activity)

    def check_fr1_activity(self):
        """Periodic checker to monitor FR1 activity and auto-disable buttons if device sleeps"""
        try:
            # Only run if monitoring is active and device is connected
            if not self.monitoring_active or not self.is_connected:
                return

            # Check if we have a last FR1 timestamp
            if self.last_fr1_time is not None and self.device_ready:
                elapsed = time.time() - self.last_fr1_time

                # If more than 2 seconds since last FR1 and button is enabled
                if elapsed > 2.0:
                    # Check if button is currently enabled and we're not in the middle of an update
                    if (self.update_button['state'] == 'normal' and
                        not self.update_in_progress):
                        # Disable buttons
                        self.configure_button.config(state='disabled', style='Red.TButton')
                        self.update_button.config(state='disabled', style='Red.TButton')
                        self.log_message("Dispositivo entrou em modo dormante, botões desabilitados", 'info')

            # Schedule next check in 1 second
            if self.monitoring_active:
                self.root.after(1000, self.check_fr1_activity)

        except Exception as e:
            self.log_message(f"Erro no monitoramento FR1: {str(e)}", 'error')

    def read_serial(self):
        """Read data from serial port in a separate thread"""
        buffer = b''
        while self.is_connected and self.serial_port and self.serial_port.is_open:
            try:
                # Read all available bytes
                if self.serial_port.in_waiting > 0:
                    chunk = self.serial_port.read(self.serial_port.in_waiting)
                    buffer += chunk

                    # Process complete lines (ending with \r\n)
                    while b'\r\n' in buffer:
                        line, buffer = buffer.split(b'\r\n', 1)

                        # Log raw bytes for debugging
                        if len(line) == 0:
                            # Empty line - log it for debugging
                            self.log_message(f"RX (empty line)", 'received')
                        else:
                            try:
                                decoded_data = line.decode('utf-8')

                                # Remove header if present
                                if self.rpl_header and decoded_data.startswith(self.rpl_header):
                                    decoded_data = decoded_data[len(self.rpl_header):]

                                # Log the received data (suppress @FRM:OK responses during firmware update and FR1 frames)
                                # But allow logging for V2 debug mode when suppress_frame_logging is temporarily False
                                suppress_rx = ((self.suppress_frame_logging and
                                              decoded_data.startswith('@FRM') and
                                              decoded_data not in ['@FRM,START:OK', '@FRM,UPGRADE:OK']) or
                                              decoded_data.startswith('FR1,'))

                                if not suppress_rx:
                                    self.log_message(f"RX: {decoded_data}", 'received')

                                # Track FR1 frames (device is active)
                                if decoded_data.startswith('FR1,'):
                                    self.fr1_received = True
                                    self.last_fr1_time = time.time()

                                    # If device is ready but buttons are disabled, re-enable them
                                    if self.device_ready and self.update_button['state'] == 'disabled' and not self.update_in_progress:
                                        self.root.after(0, lambda: self.configure_button.config(state='normal', style='Green.TButton'))
                                        self.root.after(0, lambda: self.update_button.config(state='normal', style='Green.TButton'))
                                        self.log_message("Dispositivo reativado, botões habilitados", 'info')

                                # Process received data for responses
                                if self.waiting_for_response:
                                    # Always ignore FR1 frames when waiting for responses
                                    if decoded_data.startswith("FR1"):
                                        # FR1 frames are device heartbeats, ignore and keep waiting
                                        pass
                                    # If we have a prefix filter, only accept matching responses
                                    elif self.expected_response_prefix:
                                        if decoded_data.startswith(self.expected_response_prefix):
                                            self.last_response = decoded_data
                                            self.response_event.set()
                                        # else: ignore this message (e.g., other unwanted responses)
                                    else:
                                        # No filter, accept any non-FR1 response
                                        self.last_response = decoded_data
                                        self.response_event.set()

                            except UnicodeDecodeError:
                                # If decode fails, show hex
                                self.log_message(f"RX (hex): {line.hex()}", 'received')

                time.sleep(0.01)

            except Exception as e:
                if self.is_connected:
                    self.log_message(f"Erro na leitura: {str(e)}", 'error')
                break

    def send_serial(self, data, wait_for_response=False, timeout=5.0, expected_prefix=None):
        """Send data to serial port and optionally wait for response

        Args:
            data: Data to send
            wait_for_response: Whether to wait for a response
            timeout: Response timeout in seconds
            expected_prefix: Optional prefix to filter responses (e.g., '@FRM' to ignore FR1 frames)
        """
        if not self.is_connected or not self.serial_port:
            self.log_message("Erro: Não conectado", 'error')
            return None

        try:
            if wait_for_response:
                self.waiting_for_response = True
                self.expected_response_prefix = expected_prefix
                self.last_response = None
                self.response_event.clear()

            message = self.req_header + data + self.req_footer
            self.serial_port.write(message.encode('utf-8'))
            self.serial_port.flush()

            # Suppress logging for firmware data frames during update
            if not (self.suppress_frame_logging and data.startswith('@FRM,') and data != '@FRM,START' and data != '@FRM,UPGRADE'):
                self.log_message(f"TX: {data}", 'sent')

            if wait_for_response:
                if self.response_event.wait(timeout):
                    self.waiting_for_response = False
                    self.expected_response_prefix = None
                    return self.last_response
                else:
                    self.waiting_for_response = False
                    self.expected_response_prefix = None
                    self.log_message("Timeout aguardando resposta", 'error')
                    return None
            return True

        except Exception as e:
            self.log_message(f"Erro no envio: {str(e)}", 'error')
            self.waiting_for_response = False
            self.expected_response_prefix = None
            return None

    def log_message(self, message, tag='info'):
        """Add message to log with timestamp"""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        full_message = f"[{timestamp}] {message}\n"

        self.log_text.insert(tk.END, full_message, tag)
        self.log_text.see(tk.END)

    def clear_log(self):
        """Clear all log messages"""
        self.log_text.delete('1.0', tk.END)
        self.log_message("Log limpo", 'info')

    def save_log(self):
        """Save current log to a text file"""
        if not self.device_serial_number:
            # If no device SN available, use a generic name
            sn_part = "unknown"
        else:
            sn_part = self.device_serial_number

        # Generate timestamp for filename: DDMMYYYYHHmmSS
        timestamp = datetime.now().strftime("%d%m%Y%H%M%S")
        default_filename = f"{sn_part}_{timestamp}.txt"

        # Open save dialog
        filename = filedialog.asksaveasfilename(
            title="Salvar Log",
            defaultextension=".txt",
            initialfile=default_filename,
            filetypes=[("Arquivos de Texto", "*.txt"), ("Todos os arquivos", "*.*")]
        )

        if filename:
            try:
                # Get all log content
                log_content = self.log_text.get('1.0', tk.END)

                # Save to file
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(log_content)

                self.log_message(f"Log salvo em: {filename}", 'success')
                messagebox.showinfo("Sucesso", f"Log salvo com sucesso!\n\n{filename}")

            except Exception as e:
                self.log_message(f"Erro ao salvar log: {str(e)}", 'error')
                messagebox.showerror("Erro", f"Erro ao salvar log:\n{str(e)}")

    def open_configure_dialog(self):
        """Open configuration dialog for device limits - returns True if user confirmed, False if canceled"""
        # Create configuration dialog
        config_dialog = tk.Toplevel(self.root)
        config_dialog.title("Configurar Limites do Dispositivo")
        config_dialog.geometry("400x200")
        config_dialog.resizable(False, False)
        config_dialog.transient(self.root)
        config_dialog.grab_set()

        # Variable to store dialog result
        dialog_result = {'confirmed': False}

        # Main frame
        main_frame = ttk.Frame(config_dialog, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Speed limit
        ttk.Label(main_frame, text="Vel Máx:").grid(row=0, column=0, sticky=tk.W, pady=10)
        speed_var = tk.StringVar(value=str(self.speed_limit))  # Pre-fill with default
        speed_entry = ttk.Entry(main_frame, textvariable=speed_var, width=15)
        speed_entry.grid(row=0, column=1, padx=10, pady=10)
        ttk.Label(main_frame, text="(10-200 km/h)").grid(row=0, column=2, sticky=tk.W)

        # RPM limit
        ttk.Label(main_frame, text="Limite RPM:").grid(row=1, column=0, sticky=tk.W, pady=10)
        rpm_var = tk.StringVar(value=str(self.rpm_limit))  # Pre-fill with default
        rpm_entry = ttk.Entry(main_frame, textvariable=rpm_var, width=15)
        rpm_entry.grid(row=1, column=1, padx=10, pady=10)
        ttk.Label(main_frame, text="(100-10000 RPM)").grid(row=1, column=2, sticky=tk.W)

        # Validation command to allow only numbers
        def validate_number(P):
            if P == "":
                return True
            try:
                int(P)
                return True
            except ValueError:
                return False

        vcmd = (config_dialog.register(validate_number), '%P')
        speed_entry.config(validate='key', validatecommand=vcmd)
        rpm_entry.config(validate='key', validatecommand=vcmd)

        # Buttons frame
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=2, column=0, columnspan=3, pady=20)

        def on_ok():
            # Validate inputs
            try:
                speed = int(speed_var.get())
                rpm = int(rpm_var.get())

                if not (10 <= speed <= 200):
                    messagebox.showerror("Erro", "Velocidade máxima deve estar entre 10 e 200 km/h")
                    return

                if not (100 <= rpm <= 10000):
                    messagebox.showerror("Erro", "Limite de RPM deve estar entre 100 e 10000")
                    return

                # Calculate RPM as multiple of 64 (round up)
                rpm_multiple = ((rpm + 63) // 64) * 64

                # Store configuration values
                self.speed_limit = speed
                self.rpm_limit = rpm_multiple
                dialog_result['confirmed'] = True

                # Close dialog
                config_dialog.destroy()

            except ValueError:
                messagebox.showerror("Erro", "Por favor, preencha todos os campos com valores válidos")

        def on_cancel():
            dialog_result['confirmed'] = False
            config_dialog.destroy()

        ttk.Button(button_frame, text="OK", command=on_ok, width=10).grid(row=0, column=0, padx=5)
        ttk.Button(button_frame, text="CANCELAR", command=on_cancel, width=10).grid(row=0, column=1, padx=5)

        # Focus on speed entry
        speed_entry.focus()

        # Wait for dialog to close
        self.root.wait_window(config_dialog)

        # Return whether user confirmed
        return dialog_result['confirmed']

    def send_limits_configuration(self, speed, rpm):
        """Send LIMITS configuration command to device with retry mechanism"""
        # Start configuration in separate thread
        config_thread = threading.Thread(target=self.perform_limits_configuration, args=(speed, rpm), daemon=True)
        config_thread.start()

    def perform_limits_configuration(self, speed, rpm):
        """Perform LIMITS configuration with retry mechanism"""
        try:
            self.log_message("=== INICIANDO CONFIGURAÇÃO DE LIMITES ===", 'info')
            self.log_message(f"Velocidade Máxima: {speed} km/h", 'info')
            self.log_message(f"Limite RPM: {rpm} (múltiplo de 64)", 'info')

            # Disable configure button during configuration
            self.root.after(0, lambda: self.configure_button.config(state='disabled', style='Red.TButton'))

            # Send LIMITS command with retry mechanism (3 attempts, 2 seconds apart)
            max_retries = 3
            retry_count = 0
            config_success = False

            while retry_count < max_retries and not config_success:
                if retry_count > 0:
                    self.log_message(f"Tentativa {retry_count + 1} de {max_retries}...", 'info')

                # Send LIMITS command: LIMITS,{speed},0,{rpm}
                command = f"LIMITS,{speed},0,{rpm}"
                response = self.send_serial(command, wait_for_response=True, timeout=2.0, expected_prefix="LIMITS")

                if response and "OK" in response:
                    config_success = True
                    self.log_message("Configuração aplicada com sucesso!", 'success')
                else:
                    retry_count += 1
                    if retry_count < max_retries:
                        self.log_message("Sem resposta, aguardando 2 segundos para nova tentativa...", 'info')
                        time.sleep(2.0)

            if not config_success:
                # All retries failed
                error_msg = "Falha ao aplicar configuração após 3 tentativas.\n\nVerifique:\n- Reinicie o dispositivo\n- Verifique as conexões\n- Tente novamente"
                self.log_message("Erro: Falha na configuração após 3 tentativas", 'error')
                self.root.after(0, self.show_config_failure_popup, error_msg)
            else:
                # Configuration successful
                self.root.after(0, self.show_config_success_popup)

            # Re-enable configure button
            self.root.after(0, lambda: self.configure_button.config(state='normal', style='Green.TButton'))

        except Exception as e:
            self.log_message(f"Erro durante configuração: {str(e)}", 'error')
            self.root.after(0, lambda: self.configure_button.config(state='normal', style='Green.TButton'))

    def perform_standalone_configuration(self, speed, rpm):
        """Perform standalone LIMITS configuration and start auto-polling after success"""
        try:
            self.log_message("=== CONFIGURAÇÃO STANDALONE - INICIANDO ===", 'info')
            self.log_message(f"Velocidade Máxima: {speed} km/h", 'info')
            self.log_message(f"Limite RPM: {rpm} (múltiplo de 64)", 'info')

            # Disable configure button during configuration
            self.root.after(0, lambda: self.configure_button.config(state='disabled', style='Red.TButton'))

            # Send LIMITS command with retry mechanism (3 attempts, 2 seconds apart)
            max_retries = 3
            retry_count = 0
            config_success = False

            while retry_count < max_retries and not config_success:
                if retry_count > 0:
                    self.log_message(f"Tentativa {retry_count + 1} de {max_retries}...", 'info')

                # Send LIMITS command: LIMITS,{speed},0,{rpm}
                command = f"LIMITS,{speed},0,{rpm}"
                response = self.send_serial(command, wait_for_response=True, timeout=2.0, expected_prefix="LIMITS")

                if response and "OK" in response:
                    config_success = True
                    self.log_message("Configuração aplicada com sucesso!", 'success')
                else:
                    retry_count += 1
                    if retry_count < max_retries:
                        self.log_message("Sem resposta, aguardando 2 segundos para nova tentativa...", 'info')
                        time.sleep(2.0)

            if not config_success:
                # All retries failed
                error_msg = "Falha ao aplicar configuração após 3 tentativas.\n\nVerifique:\n- Reinicie o dispositivo\n- Verifique as conexões\n- Tente novamente"
                self.log_message("Erro: Falha na configuração após 3 tentativas", 'error')
                self.root.after(0, self.show_config_failure_popup, error_msg)
            else:
                # Configuration successful - show success popup
                self.log_message("=== CONFIGURAÇÃO CONCLUÍDA COM SUCESSO ===", 'success')
                self.root.after(0, self.show_standalone_config_success_popup)
                # Note: Auto-polling will be started after user clicks OK on success popup

            # Re-enable configure button
            self.root.after(0, lambda: self.configure_button.config(state='normal', style='Green.TButton'))

        except Exception as e:
            self.log_message(f"Erro durante configuração standalone: {str(e)}", 'error')
            self.root.after(0, lambda: self.configure_button.config(state='normal', style='Green.TButton'))

    def select_firmware(self):
        """Open folder dialog to search for firmware file matching device serial number"""
        # Check if device serial number is available
        if not self.device_serial_number:
            messagebox.showerror("Erro", "Número de série do dispositivo não disponível.\nConecte-se ao dispositivo primeiro.")
            return False

        # Use last selected folder if available, otherwise Downloads
        if self.last_folder_path and os.path.exists(self.last_folder_path):
            initial_folder = self.last_folder_path
        else:
            initial_folder = os.path.join(os.path.expanduser('~'), 'Downloads')

        # Open folder picker
        folder_path = filedialog.askdirectory(
            title="Selecionar Pasta com Arquivo de Firmware",
            initialdir=initial_folder
        )

        if not folder_path:
            # User canceled
            return False

        # Save the selected folder path for next time
        self.last_folder_path = folder_path
        self.save_config({'last_folder_path': folder_path})
        self.log_message(f"Pasta salva: {folder_path}", 'info')

        self.log_message(f"Buscando firmware para SN {self.device_serial_number} na pasta selecionada...", 'info')

        # Search for firmware files matching the device serial number
        matched_files, error_msg = self.find_firmware_files_by_serial(folder_path, self.device_serial_number)

        if error_msg:
            # Error occurred or no/multiple files found
            messagebox.showerror("Erro", error_msg)
            return False

        # We have exactly one file
        filename, file_version = matched_files[0]

        # Parse the firmware file
        if self.parse_firmware_file(filename):
            self.firmware_file = filename
            self.firmware_file_version = file_version  # Store version from filename for comparison
            filename_only = os.path.basename(filename)
            info_text = f"Firmware: {filename_only} | Versão: {file_version} | Frames: {self.firmware_info.get('num_frames', 0)}"
            self.firmware_label.config(text=info_text, foreground="blue")
            self.log_message(f"Firmware selecionado: {filename_only} (versão {file_version})", 'success')
            return True
        else:
            return False

    def parse_firmware_file(self, filename):
        """Parse firmware file and extract frames"""
        try:
            self.firmware_frames = []
            self.firmware_info = {}

            with open(filename, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('#'):
                        continue
                    # Support both V2 format (with space) and V3 format (without space)
                    elif line.startswith('D '):
                        # V2 format: "D 1063641"
                        self.firmware_info['serial_number'] = line[2:].strip()
                    elif line.startswith('D') and not line.startswith('D '):
                        # V3 format: "D3035331"
                        self.firmware_info['serial_number'] = line[1:].strip()
                    elif line.startswith('V '):
                        # V2 format: "V 2.3.12b"
                        self.firmware_info['version'] = line[2:].strip()
                    elif line.startswith('V') and not line.startswith('V '):
                        # V3 format: "V3.0.18b"
                        self.firmware_info['version'] = line[1:].strip()
                    elif line.startswith('N '):
                        # V2 format: "N 2269"
                        self.firmware_info['num_frames'] = int(line[2:].strip())
                    elif line.startswith('N') and not line.startswith('N '):
                        # V3 format: "N3826"
                        self.firmware_info['num_frames'] = int(line[1:].strip())
                    elif line.startswith('C '):
                        # V2 format: "C 0x35DAB2A7"
                        self.firmware_info['checksum'] = line[2:].strip()
                    elif line.startswith('C') and not line.startswith('C '):
                        # V3 format: "C0x4A2F"
                        self.firmware_info['checksum'] = line[1:].strip()
                    elif line.startswith('@FRM,'):
                        self.firmware_frames.append(line)

            if not self.firmware_frames:
                messagebox.showerror("Erro", "Arquivo de firmware inválido: nenhum frame encontrado!")
                return False

            self.log_message(f"Arquivo parseado: {len(self.firmware_frames)} frames encontrados", 'info')
            return True

        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao ler arquivo de firmware:\n{str(e)}")
            self.log_message(f"Erro ao parsear firmware: {str(e)}", 'error')
            return False

    def automatic_firmware_update(self):
        """Automatically update firmware for a new device without user interaction"""
        try:
            # Check if we have a saved folder path
            if not self.last_folder_path or not os.path.exists(self.last_folder_path):
                self.log_message("Erro: Pasta de firmware não configurada. Execute atualização manual primeiro.", 'error')
                messagebox.showerror("Erro", "Pasta de firmware não configurada.\nExecute uma atualização manual primeiro.")
                return

            self.log_message(f"Buscando firmware para SN {self.device_serial_number} automaticamente...", 'info')

            # Search for firmware files matching the device serial number
            matched_files, error_msg = self.find_firmware_files_by_serial(self.last_folder_path, self.device_serial_number)

            if error_msg:
                # Error occurred
                self.log_message(f"Erro na busca automática: {error_msg}", 'error')
                messagebox.showerror("Erro na Atualização Automática", error_msg)
                # Restart polling
                self.start_auto_update_polling()
                return

            # We have exactly one file
            filename, file_version = matched_files[0]

            # Parse the firmware file
            if not self.parse_firmware_file(filename):
                self.log_message("Erro ao analisar arquivo de firmware", 'error')
                messagebox.showerror("Erro", "Erro ao analisar arquivo de firmware")
                # Restart polling
                self.start_auto_update_polling()
                return

            self.firmware_file = filename
            self.firmware_file_version = file_version
            filename_only = os.path.basename(filename)
            self.log_message(f"Firmware selecionado automaticamente: {filename_only} (versão {file_version})", 'success')

            # Update firmware label on UI
            info_text = f"Firmware: {filename_only} | Versão: {file_version} | Frames: {self.firmware_info.get('num_frames', 0)}"
            self.root.after(0, lambda: self.firmware_label.config(text=info_text, foreground="blue"))

            # Compare versions and decide if confirmation is needed
            version_comparison = self.compare_versions(self.firmware_file_version, self.device_fw_version)

            # Only show confirmation for downgrade or same version
            # For newer versions, proceed automatically
            show_confirmation = (version_comparison <= 0)

            if show_confirmation:
                # Build confirmation message for downgrade or same version
                base_msg = f"Firmware:\n  Versão do Arquivo: {self.firmware_file_version}\n  Versão Atual do Dispositivo: {self.device_fw_version}\n  Frames: {len(self.firmware_frames)}\n\nConfiguração:\n  Vel Máx: {self.speed_limit} km/h\n  Limite RPM: {self.rpm_limit} RPM\n\n"

                # Add version-specific warning
                if version_comparison < 0:
                    confirmation_msg = "⚠️ ATENÇÃO: DOWNGRADE DE FIRMWARE ⚠️\n\n" + base_msg
                    confirmation_msg += "A versão do arquivo é MAIS ANTIGA que a versão atual do dispositivo.\n\n"
                    confirmation_msg += "Deseja continuar com o downgrade?"
                    title = "Confirmar Downgrade"
                else:  # version_comparison == 0
                    confirmation_msg = "⚠️ ATENÇÃO: MESMA VERSÃO ⚠️\n\n" + base_msg
                    confirmation_msg += "A versão do arquivo é IGUAL à versão atual do dispositivo.\n\n"
                    confirmation_msg += "Deseja continuar com a reinstalação?"
                    title = "Confirmar Reinstalação"

                # Show confirmation dialog
                result = messagebox.askyesno(title, confirmation_msg)
            else:
                # Newer firmware version - proceed automatically without confirmation
                self.log_message(f"Firmware mais recente detectado ({self.firmware_file_version} > {self.device_fw_version})", 'info')
                self.log_message("Prosseguindo automaticamente com atualização e configuração...", 'success')
                result = True  # Auto-confirm for newer versions

            if result:
                self.update_in_progress = True
                self.configure_button.config(state='disabled', style='Red.TButton')
                self.update_button.config(state='disabled', style='Red.TButton')
                self.connect_button.config(state='disabled')

                # Start update in separate thread
                update_thread = threading.Thread(target=self.perform_firmware_update, daemon=True)
                update_thread.start()
            else:
                # User canceled - restart polling
                self.log_message("Atualização cancelada pelo usuário", 'info')
                self.start_auto_update_polling()

        except Exception as e:
            self.log_message(f"Erro na atualização automática: {str(e)}", 'error')
            messagebox.showerror("Erro", f"Erro na atualização automática:\n{str(e)}")
            # Restart polling
            self.start_auto_update_polling()

    def on_configure_button_clicked(self):
        """Handle CONFIGURAR button click - standalone configuration without firmware update"""
        if not self.is_connected:
            messagebox.showwarning("Aviso", "Conecte-se à porta COM primeiro!")
            return

        if self.update_in_progress:
            messagebox.showwarning("Aviso", "Uma atualização já está em andamento!")
            return

        # Show configuration dialog
        config_confirmed = self.open_configure_dialog()

        # If user canceled configuration, abort
        if not config_confirmed:
            return

        # User confirmed - start standalone configuration with auto-polling after success
        self.log_message("=== INICIANDO CONFIGURAÇÃO STANDALONE ===", 'info')

        # Start configuration in separate thread
        config_thread = threading.Thread(target=self.perform_standalone_configuration,
                                         args=(self.speed_limit, self.rpm_limit), daemon=True)
        config_thread.start()

    def start_firmware_update(self):
        """Start firmware update process with configuration"""
        if not self.is_connected:
            messagebox.showwarning("Aviso", "Conecte-se à porta COM primeiro!")
            return

        if self.update_in_progress:
            messagebox.showwarning("Aviso", "Uma atualização já está em andamento!")
            return

        # Step 1: Open folder picker to select firmware
        firmware_selected = self.select_firmware()

        # If firmware was not loaded, abort
        if not firmware_selected or not self.firmware_frames:
            return

        # Step 2: Show configuration dialog
        config_confirmed = self.open_configure_dialog()

        # If user canceled configuration, abort
        if not config_confirmed:
            return

        # Step 3: Compare versions and show appropriate confirmation message
        version_comparison = self.compare_versions(self.firmware_file_version, self.device_fw_version)

        # Build base confirmation message
        base_msg = f"Firmware:\n  Versão do Arquivo: {self.firmware_file_version}\n  Versão Atual do Dispositivo: {self.device_fw_version}\n  Frames: {len(self.firmware_frames)}\n\nConfiguração:\n  Vel Máx: {self.speed_limit} km/h\n  Limite RPM: {self.rpm_limit} RPM\n\n"

        # Add version-specific warning
        if version_comparison < 0:
            # File version is OLDER than current device version (downgrade)
            confirmation_msg = "⚠️ ATENÇÃO: DOWNGRADE DE FIRMWARE ⚠️\n\n" + base_msg
            confirmation_msg += "A versão do arquivo é MAIS ANTIGA que a versão atual do dispositivo.\n\n"
            confirmation_msg += "Tem certeza que deseja fazer o downgrade?"
            title = "Confirmar Downgrade"
        elif version_comparison == 0:
            # File version is SAME as current device version
            confirmation_msg = "⚠️ ATENÇÃO: MESMA VERSÃO ⚠️\n\n" + base_msg
            confirmation_msg += "A versão do arquivo é IGUAL à versão atual do dispositivo.\n\n"
            confirmation_msg += "Tem certeza que deseja reinstalar a mesma versão?"
            title = "Confirmar Reinstalação"
        else:
            # File version is NEWER than current device version (upgrade)
            confirmation_msg = "Iniciar atualização de firmware e configuração?\n\n" + base_msg
            confirmation_msg += "O dispositivo será atualizado e configurado."
            title = "Confirmar Atualização"

        # Show confirmation dialog
        result = messagebox.askyesno(title, confirmation_msg)

        if result:
            self.update_in_progress = True
            self.configure_button.config(state='disabled', style='Red.TButton')
            self.update_button.config(state='disabled', style='Red.TButton')
            self.connect_button.config(state='disabled')

            # Start update in separate thread
            update_thread = threading.Thread(target=self.perform_firmware_update, daemon=True)
            update_thread.start()

    def perform_firmware_update(self):
        """Perform the firmware update process"""
        try:
            self.log_message("=== INICIANDO ATUALIZAÇÃO DE FIRMWARE ===", 'info')
            self.root.after(0, self.update_progress, 0)

            # Step 1: Send START command with retry mechanism
            self.log_message("Enviando comando de início...", 'info')
            max_retries = 5
            retry_count = 0
            start_command_success = False

            while retry_count < max_retries and not start_command_success:
                if retry_count > 0:
                    self.log_message(f"Tentativa {retry_count + 1} de {max_retries}...", 'info')

                response = self.send_serial("@FRM,START", wait_for_response=True, timeout=2.0, expected_prefix="@FRM")

                if response and "OK" in response:
                    start_command_success = True
                    self.log_message("Comando START aceito", 'success')
                else:
                    retry_count += 1
                    if retry_count < max_retries:
                        self.log_message(f"Sem resposta, aguardando 2 segundos para nova tentativa...", 'info')
                        time.sleep(2.0)

            if not start_command_success:
                # All retries failed, show failure popup and disconnect
                error_msg = "Falha ao iniciar atualização após 5 tentativas.\n\nVerifique:\n- Conexões do dispositivo\n- Reinicie o dispositivo\n- Tente novamente"
                self.log_message("Erro: Falha no comando START após 5 tentativas", 'error')
                self.root.after(0, self.show_retry_failure_popup, error_msg)
                raise Exception("Falha no comando START após 5 tentativas")

            # Add delay after START for V2 devices (they need time to prepare memory)
            if self.device_is_v2:
                self.log_message("Aguardando 500ms para V2 preparar memória...", 'info')
                time.sleep(0.5)

            # Step 2: Send firmware frames
            total_frames = len(self.firmware_frames)
            self.current_frame_index = 0

            # Enable frame logging suppression for firmware data frames
            self.suppress_frame_logging = True

            for i, frame in enumerate(self.firmware_frames):
                if not self.update_in_progress:
                    raise Exception("Atualização cancelada pelo usuário")

                self.current_frame_index = i
                progress = (i + 1) / total_frames * 100

                # Update progress bar
                self.root.after(0, self.update_progress, progress)

                # Send frame and wait for acknowledgment
                # V2 protocol: Each frame gets "@FRM:OK" response (with colon)
                # V3 protocol: May be different
                response = self.send_serial(frame, wait_for_response=True, timeout=2.0, expected_prefix=None)

                # Accept both "@FRM:OK" (V2, with colon) and other OK responses (V3)
                if not response or "OK" not in response:
                    # Log detailed error for debugging
                    self.log_message(f"ERRO Frame {i+1}: Resposta inválida ou vazia: '{response}'", 'error')
                    raise Exception(f"Falha no frame {i+1}: {response}")

                # Log progress every 1000 frames
                if (i + 1) % 1000 == 0:
                    self.log_message(f"Progresso: {i+1}/{total_frames} frames enviados ({progress:.1f}%)", 'info')

            # Disable frame logging suppression before sending final commands
            self.suppress_frame_logging = False

            # Step 3: Send UPGRADE command
            self.log_message("Enviando comando de upgrade final...", 'info')
            response = self.send_serial("@FRM,UPGRADE", wait_for_response=True, timeout=5.0, expected_prefix="@FRM")

            if not response or "OK" not in response:
                raise Exception(f"Falha no comando UPGRADE: {response}")

            self.log_message("Comando UPGRADE aceito", 'success')

            # Step 4: Wait for device to update and reboot (15 seconds with countdown)
            self.log_message("Aguardando atualização e reinício do leitor...", 'info')
            for i in range(1, 16):
                self.log_message(f"Leitor atualizando e reiniciando {i}/15", 'info')
                time.sleep(1.0)

            # Step 5: Send LIMITS configuration after device has rebooted
            self.log_message("Enviando configuração de limites...", 'info')

            # Send LIMITS command with retry mechanism (3 attempts - device should be ready now)
            max_retries = 3
            retry_count = 0
            config_success = False

            while retry_count < max_retries and not config_success:
                if retry_count > 0:
                    self.log_message(f"Tentativa {retry_count + 1} de {max_retries} para configuração...", 'info')

                # Send LIMITS command: LIMITS,{speed},0,{rpm}
                command = f"LIMITS,{self.speed_limit},0,{self.rpm_limit}"
                response = self.send_serial(command, wait_for_response=True, timeout=2.0, expected_prefix="LIMITS")

                if response and "OK" in response:
                    config_success = True
                    self.log_message("Configuração aplicada com sucesso!", 'success')
                else:
                    retry_count += 1
                    if retry_count < max_retries:
                        self.log_message("Sem resposta na configuração, aguardando 1 segundo...", 'info')
                        time.sleep(1.0)

            if not config_success:
                # Configuration failed after all retries, but firmware update succeeded
                self.log_message("Aviso: Configuração falhou após 3 tentativas, mas firmware foi atualizado com sucesso", 'info')

            # Update complete
            self.root.after(0, self.update_complete)

        except Exception as e:
            # Ensure logging suppression is disabled on error
            self.suppress_frame_logging = False
            self.log_message(f"Erro durante atualização: {str(e)}", 'error')
            self.root.after(0, self.update_failed, str(e))

    def update_progress(self, progress):
        """Update progress bar"""
        self.progress_var.set(progress)
        self.progress_label.config(text=f"{progress:.1f}%")

    def update_complete(self):
        """Called when firmware update and configuration complete successfully"""
        self.update_in_progress = False
        self.configure_button.config(state='normal', style='Green.TButton')
        self.update_button.config(state='normal', style='Green.TButton')
        self.connect_button.config(state='normal')
        self.progress_var.set(100)
        self.progress_label.config(text="100%")
        self.log_message("=== ATUALIZAÇÃO E CONFIGURAÇÃO CONCLUÍDAS COM SUCESSO ===", 'success')

        messagebox.showinfo("Sucesso",
                           "Atualização de firmware e configuração concluídas com sucesso!\n\nO dispositivo será reiniciado automaticamente.")

        # Start auto-update polling for multi-device updates
        self.start_auto_update_polling()

    def update_failed(self, error_msg):
        """Called when firmware update fails"""
        self.update_in_progress = False
        self.configure_button.config(state='normal', style='Green.TButton')
        self.update_button.config(state='normal', style='Green.TButton')
        self.connect_button.config(state='normal')
        self.log_message("=== ATUALIZAÇÃO FALHOU ===", 'error')

        # Check if error is ERR#82 (firmware mismatch with device serial number)
        if "ERR#82" in error_msg:
            custom_msg = "A atualização de firmware falhou:\n\nFirmware não corresponde ao número de série do leitor.\nFavor utilizar o firmware correto e tentar novamente."
            messagebox.showerror("Erro na Atualização", custom_msg)
        else:
            messagebox.showerror("Erro na Atualização",
                                f"A atualização de firmware falhou:\n\n{error_msg}\n\nVerifique o log para mais detalhes.")

    def show_retry_failure_popup(self, error_msg):
        """Show failure popup after retry exhaustion and disconnect"""
        messagebox.showerror("Falha na Atualização", error_msg)
        # Auto-disconnect after user clicks OK
        if self.is_connected:
            self.disconnect()

    def show_versions_failure_popup(self, error_msg):
        """Show failure popup after VERSIONS command fails and disconnect"""
        messagebox.showerror("Falha na Comunicação", error_msg)
        # Auto-disconnect after user clicks OK
        if self.is_connected:
            self.disconnect()

    def show_config_success_popup(self):
        """Show success popup after configuration is applied successfully"""
        messagebox.showinfo("Sucesso", "Configuração aplicada com sucesso!")
        # Keep COM port open

    def show_standalone_config_success_popup(self):
        """Show success popup after standalone configuration and start auto-polling"""
        messagebox.showinfo("Sucesso", "Configuração aplicada com sucesso!\n\nAguardando próximo dispositivo...")
        # After user clicks OK, start auto-polling for next device
        self.start_auto_update_polling()

    def show_config_failure_popup(self, error_msg):
        """Show failure popup after configuration fails and disconnect"""
        messagebox.showerror("Falha na Configuração", error_msg)
        # Auto-disconnect after user clicks OK
        if self.is_connected:
            self.disconnect()

    def on_closing(self):
        """Handle window closing"""
        if self.update_in_progress:
            if not messagebox.askokcancel("Atualização em Andamento",
                                         "Uma atualização está em andamento. Fechar agora pode danificar o dispositivo!\n\nDeseja realmente sair?"):
                return

        self.update_in_progress = False
        self.disconnect()
        self.root.destroy()


def main():
    root = tk.Tk()
    app = CANBusUpdater(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()
