#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SETERA - Atualização e Configuração - Leitor CANBUS
Versão: 1.0
Data: 14Out2025
Descrição: Software para atualização de firmware de dispositivos leitores CANBUS
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

class CANBusUpdater:
    def __init__(self, root):
        self.root = root
        self.root.title("Atualização e Configuração - Leitor CANBUS - v1.0 - 14Out2025")
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
        self.update_in_progress = False
        self.current_frame_index = 0

        # Device state variables
        self.device_fw_version = None
        self.device_serial_number = None
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

    def create_widgets(self):
        """Create all UI widgets"""
        # Top frame for COM port and firmware selection
        top_frame = ttk.Frame(self.root, padding="10")
        top_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N), padx=5, pady=5)

        # COM Port selection
        ttk.Label(top_frame, text="Porta COM:").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.com_port_var = tk.StringVar()
        self.com_port_combo = ttk.Combobox(top_frame, textvariable=self.com_port_var,
                                           width=15, state='readonly')
        self.com_port_combo.grid(row=0, column=1, padx=5)

        # Connect/Disconnect button
        self.connect_button = ttk.Button(top_frame, text="CONECTAR",
                                         command=self.toggle_connection, width=15)
        self.connect_button.grid(row=0, column=2, padx=10)

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
        self.update_button.grid(row=0, column=3, padx=10)

        # Configure button
        self.configure_button = ttk.Button(top_frame, text="CONFIGURAR",
                                           command=self.open_configure_dialog, width=15,
                                           state='disabled', style='Red.TButton')
        self.configure_button.grid(row=0, column=4, padx=10)

        # Clear Log button
        self.clear_log_button = ttk.Button(top_frame, text="LIMPAR LOG",
                                           command=self.clear_log, width=15)
        self.clear_log_button.grid(row=0, column=5, padx=10)

        # Save Log button
        self.save_log_button = ttk.Button(top_frame, text="SALVAR LOG",
                                          command=self.save_log, width=15)
        self.save_log_button.grid(row=0, column=6, padx=10)

        # Device info label (firmware version and serial number)
        self.device_label = ttk.Label(top_frame, text="Dispositivo: Desconectado",
                                      foreground="gray")
        self.device_label.grid(row=1, column=0, columnspan=7, sticky=tk.W, padx=5, pady=(5,0))

        # Firmware info label
        self.firmware_label = ttk.Label(top_frame, text="Nenhum firmware selecionado",
                                        foreground="gray")
        self.firmware_label.grid(row=2, column=0, columnspan=7, sticky=tk.W, padx=5, pady=(0,0))

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
        self.log_text.tag_config('error', foreground='red')
        self.log_text.tag_config('success', foreground='green')
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

        self.connect_button.config(text="CONECTAR")
        self.update_button.config(state='disabled', style='Red.TButton')
        self.configure_button.config(state='disabled', style='Red.TButton')
        self.device_label.config(text="Dispositivo: Desconectado", foreground="gray")
        self.log_message("Desconectado da porta COM", 'info')

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
                response = self.send_serial("VERSIONS", wait_for_response=True, timeout=2.0, expected_prefix="VERSIONS")

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
                            response = self.send_serial("VERSIONS", wait_for_response=True, timeout=2.0, expected_prefix="VERSIONS")

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
                self.root.after(0, lambda: self.update_button.config(state='normal', style='Green.TButton'))
                self.root.after(0, lambda: self.configure_button.config(state='normal', style='Green.TButton'))

                # Start FR1 activity monitoring on main thread
                self.last_fr1_time = time.time()
                self.monitoring_active = True
                self.root.after(0, self.start_fr1_monitoring)

        except Exception as e:
            self.log_message(f"Erro na ativação do dispositivo: {str(e)}", 'error')

    def parse_versions_response(self, response):
        """Parse VERSIONS command response and extract firmware version and serial number"""
        try:
            # Expected format: VERSIONS FW3.0.18b HW3.0.5 BL3.0.12 SN3035331
            parts = response.split()

            for part in parts:
                if part.startswith('FW'):
                    self.device_fw_version = part[2:]  # Remove 'FW' prefix
                elif part.startswith('SN'):
                    self.device_serial_number = part[2:]  # Remove 'SN' prefix

            if self.device_fw_version and self.device_serial_number:
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

                # If more than 2 seconds since last FR1 and buttons are enabled
                if elapsed > 2.0:
                    # Check if buttons are currently enabled and we're not in the middle of an update
                    if (self.update_button['state'] == 'normal' and
                        self.configure_button['state'] == 'normal' and
                        not self.update_in_progress):
                        # Disable buttons
                        self.update_button.config(state='disabled', style='Red.TButton')
                        self.configure_button.config(state='disabled', style='Red.TButton')
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

                                # Log the received data
                                self.log_message(f"RX: {decoded_data}", 'received')

                                # Track FR1 frames (device is active)
                                if decoded_data.startswith('FR1,'):
                                    self.fr1_received = True
                                    self.last_fr1_time = time.time()

                                    # If device is ready but buttons are disabled, re-enable them
                                    if self.device_ready and self.update_button['state'] == 'disabled' and not self.update_in_progress:
                                        self.root.after(0, lambda: self.update_button.config(state='normal', style='Green.TButton'))
                                        self.root.after(0, lambda: self.configure_button.config(state='normal', style='Green.TButton'))
                                        self.log_message("Dispositivo reativado, botões habilitados", 'info')

                                # Process received data for responses
                                if self.waiting_for_response:
                                    # If we have a prefix filter, only accept matching responses
                                    if self.expected_response_prefix:
                                        if decoded_data.startswith(self.expected_response_prefix):
                                            self.last_response = decoded_data
                                            self.response_event.set()
                                        # else: ignore this message (e.g., FR1 frames during firmware update)
                                    else:
                                        # No filter, accept any response
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
        """Open configuration dialog for device limits"""
        if not self.is_connected:
            messagebox.showwarning("Aviso", "Conecte-se à porta COM primeiro!")
            return

        # Create configuration dialog
        config_dialog = tk.Toplevel(self.root)
        config_dialog.title("Configurar Limites do Dispositivo")
        config_dialog.geometry("400x200")
        config_dialog.resizable(False, False)
        config_dialog.transient(self.root)
        config_dialog.grab_set()

        # Main frame
        main_frame = ttk.Frame(config_dialog, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Speed limit
        ttk.Label(main_frame, text="Vel Máx:").grid(row=0, column=0, sticky=tk.W, pady=10)
        speed_var = tk.StringVar()
        speed_entry = ttk.Entry(main_frame, textvariable=speed_var, width=15)
        speed_entry.grid(row=0, column=1, padx=10, pady=10)
        ttk.Label(main_frame, text="(10-200 km/h)").grid(row=0, column=2, sticky=tk.W)

        # RPM limit
        ttk.Label(main_frame, text="Limite RPM:").grid(row=1, column=0, sticky=tk.W, pady=10)
        rpm_var = tk.StringVar()
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

                # Close dialog and send configuration
                config_dialog.destroy()
                self.send_limits_configuration(speed, rpm_multiple)

            except ValueError:
                messagebox.showerror("Erro", "Por favor, preencha todos os campos com valores válidos")

        def on_cancel():
            config_dialog.destroy()

        ttk.Button(button_frame, text="OK", command=on_ok, width=10).grid(row=0, column=0, padx=5)
        ttk.Button(button_frame, text="CANCELAR", command=on_cancel, width=10).grid(row=0, column=1, padx=5)

        # Focus on speed entry
        speed_entry.focus()

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

    def select_firmware(self):
        """Open file dialog to select firmware file"""
        filename = filedialog.askopenfilename(
            title="Selecionar Arquivo de Firmware",
            filetypes=[("Arquivos de Firmware", "*.frm"), ("Todos os arquivos", "*.*")],
            initialdir=os.path.dirname(__file__)
        )

        if filename:
            if self.parse_firmware_file(filename):
                self.firmware_file = filename
                filename_only = os.path.basename(filename)
                info_text = f"Firmware: {filename_only} | Versão: {self.firmware_info.get('version', 'N/A')} | Frames: {self.firmware_info.get('num_frames', 0)}"
                self.firmware_label.config(text=info_text, foreground="blue")
                self.log_message(f"Firmware selecionado: {filename_only}", 'success')

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
                    elif line.startswith('D '):
                        self.firmware_info['serial_number'] = line[2:].strip()
                    elif line.startswith('V '):
                        self.firmware_info['version'] = line[2:].strip()
                    elif line.startswith('N '):
                        self.firmware_info['num_frames'] = int(line[2:].strip())
                    elif line.startswith('C '):
                        self.firmware_info['checksum'] = line[2:].strip()
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

    def start_firmware_update(self):
        """Start firmware update process"""
        if not self.is_connected:
            messagebox.showwarning("Aviso", "Conecte-se à porta COM primeiro!")
            return

        if self.update_in_progress:
            messagebox.showwarning("Aviso", "Uma atualização já está em andamento!")
            return

        # Open file picker to select firmware
        self.select_firmware()

        # If firmware was successfully loaded, show confirmation
        if self.firmware_frames:
            result = messagebox.askyesno("Confirmar Atualização",
                                         f"Iniciar atualização de firmware?\n\nVersão: {self.firmware_info.get('version', 'N/A')}\nFrames: {len(self.firmware_frames)}\n\nO dispositivo será reiniciado após a atualização.")

            if result:
                self.update_in_progress = True
                self.update_button.config(state='disabled', style='Red.TButton')
                self.configure_button.config(state='disabled', style='Red.TButton')
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

            # Step 2: Send firmware frames
            total_frames = len(self.firmware_frames)
            self.current_frame_index = 0

            for i, frame in enumerate(self.firmware_frames):
                if not self.update_in_progress:
                    raise Exception("Atualização cancelada pelo usuário")

                self.current_frame_index = i
                progress = (i + 1) / total_frames * 100

                # Update progress bar
                self.root.after(0, self.update_progress, progress)

                # Send frame and wait for acknowledgment
                response = self.send_serial(frame, wait_for_response=True, timeout=2.0, expected_prefix="@FRM")

                if not response or "OK" not in response:
                    raise Exception(f"Falha no frame {i+1}: {response}")

                # Log progress every 50 frames
                if (i + 1) % 50 == 0:
                    self.log_message(f"Progresso: {i+1}/{total_frames} frames enviados ({progress:.1f}%)", 'info')

            # Step 3: Send UPGRADE command
            self.log_message("Enviando comando de upgrade final...", 'info')
            response = self.send_serial("@FRM,UPGRADE", wait_for_response=True, timeout=5.0, expected_prefix="@FRM")

            if not response or "OK" not in response:
                raise Exception(f"Falha no comando UPGRADE: {response}")

            self.log_message("Comando UPGRADE aceito", 'success')
            time.sleep(0.5)

            # Update complete
            self.root.after(0, self.update_complete)

        except Exception as e:
            self.log_message(f"Erro durante atualização: {str(e)}", 'error')
            self.root.after(0, self.update_failed, str(e))

    def update_progress(self, progress):
        """Update progress bar"""
        self.progress_var.set(progress)
        self.progress_label.config(text=f"{progress:.1f}%")

    def update_complete(self):
        """Called when firmware update completes successfully"""
        self.update_in_progress = False
        self.update_button.config(state='normal', style='Green.TButton')
        self.configure_button.config(state='normal', style='Green.TButton')
        self.connect_button.config(state='normal')
        self.progress_var.set(100)
        self.progress_label.config(text="100%")
        self.log_message("=== ATUALIZAÇÃO CONCLUÍDA COM SUCESSO ===", 'success')

        messagebox.showinfo("Sucesso",
                           "Atualização de firmware concluída com sucesso!\n\nO dispositivo será reiniciado automaticamente.")

    def update_failed(self, error_msg):
        """Called when firmware update fails"""
        self.update_in_progress = False
        self.update_button.config(state='normal', style='Green.TButton')
        self.configure_button.config(state='normal', style='Green.TButton')
        self.connect_button.config(state='normal')
        self.log_message("=== ATUALIZAÇÃO FALHOU ===", 'error')

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
