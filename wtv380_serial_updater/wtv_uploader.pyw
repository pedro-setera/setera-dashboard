#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WTV380 / Waytronic UART Firmware Updater (FIXED VERSION)

CRITICAL FIXES APPLIED:
- Skips 16-byte header when flashing (header only for handshake)
- Flooding technique with manual power cycle
- High-resolution timing (perf_counter) for precise 2ms handshake intervals
- Bootloader @ 1000000 baud

Requirements (Windows):
    Python 3.9+
    pip install pyserial
"""

import os, time, queue, struct, threading, ctypes
from datetime import datetime
from typing import List, Optional
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

try:
    import serial
    import serial.tools.list_ports as list_ports
except Exception:
    serial = None
    list_ports = None

APP_NAME = "Atualiza Firmware WTV380 UART - v1.7 - 16Out2025"

# Windows high-resolution timer setup
if os.name == 'nt':
    try:
        # Set Windows timer resolution to 1ms for better sleep accuracy
        winmm = ctypes.WinDLL('winmm')
        winmm.timeBeginPeriod(1)
    except:
        pass

# ------------------ Protocol constants ------------------
PROTOCOL = {
    "boot_baudrate": 1_000_000,      # Bootloader mode baud (FIXED per vendor spec)
    "hs_period_ms": 2.0,             # Handshake period: 2ms (per flowchart)
    "handshake_header_len": 16,      # Header size to skip when flashing
    "packet_data_bytes": 4096,
    "write_header": {
        "Head1": 0x7E, "Head2": 0xFE, "Check": 0x00, "Mode": 0xC3
    },
    "frames": {
        "TARGET_INIT_CMD":        "7E FE 00 C0 00 00 00 00 00 00 00 00",  # 12 bytes
        "FINISH_CMD":             "7E FE 00 D3 00 00 00 00 00 00 00 00"   # 12 bytes
    }
}

# ----------------------------- High-Resolution Timing -----------------------------
def precise_sleep(duration_seconds: float):
    """
    High-precision sleep using busy-wait for sub-millisecond accuracy.
    Uses perf_counter which has microsecond resolution on Windows.
    """
    if duration_seconds <= 0:
        return

    target = time.perf_counter() + duration_seconds

    # For durations > 5ms, sleep most of it, then busy-wait the remainder
    if duration_seconds > 0.005:
        time.sleep(duration_seconds - 0.002)  # Sleep most of it

    # Busy-wait for the remainder
    while time.perf_counter() < target:
        pass

# ----------------------------- Logging Utility -----------------------------
class GuiLogger:
    def __init__(self, text_widget: tk.Text, progress_var: tk.DoubleVar):
        self.text = text_widget
        self.progress_var = progress_var
        self.queue = queue.Queue()
        self.text.after(50, self._drain)

    def log(self, msg: str):
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self.queue.put(('log', f"[{timestamp}] {msg}\n"))

    def update_progress(self, percent: float):
        """Update progress bar (0-100)"""
        self.queue.put(('progress', percent))

    def _drain(self):
        try:
            while True:
                item_type, data = self.queue.get_nowait()
                if item_type == 'log':
                    self.text.configure(state="normal")
                    self.text.insert("end", data)
                    self.text.see("end")
                    self.text.configure(state="disabled")
                elif item_type == 'progress':
                    self.progress_var.set(data)
        except queue.Empty:
            pass
        finally:
            self.text.after(50, self._drain)

# ----------------------------- CRC (vendor 'chip_crc16') -------------------
def compute_crc(data: bytes) -> int:
    table = [
        0x0000, 0x1021, 0x2042, 0x3063, 0x4084, 0x50A5, 0x60C6, 0x70E7,
        0x8108, 0x9129, 0xA14A, 0xB16B, 0xC18C, 0xD1AD, 0xE1CE, 0xF1EF,
    ]
    crc = 0
    for b in data:
        da = (crc >> 12) & 0xF
        crc = ((crc << 4) & 0xFFFF) ^ table[da ^ (b >> 4)]
        da = (crc >> 12) & 0xF
        crc = ((crc << 4) & 0xFFFF) ^ table[da ^ (b & 0x0F)]
    return crc & 0xFFFF

# ----------------------------- Serial Worker -------------------------------
class SerialWorker:
    def __init__(self, logger: GuiLogger):
        self.ser = None
        self.log = logger.log

    def open(self, port: str, baud: int, timeout: float = 0.01, write_timeout: float = None) -> bool:
        if serial is None:
            self.log("ERRO: pyserial não instalado. Execute: pip install pyserial")
            return False
        try:
            if write_timeout is None:
                write_timeout = timeout
            self.ser = serial.Serial(
                port=port, baudrate=baud,
                bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=timeout, write_timeout=write_timeout
            )
            self.log(f"✓ Porta {port} aberta @ {baud} baud")
            return True
        except Exception as e:
            self.log(f"ERRO ao abrir porta serial: {e}")
            self.ser = None
            return False

    def set_baudrate(self, baud: int):
        """Change baud rate without closing port"""
        if self.ser:
            self.ser.baudrate = baud
            self.log(f"Alterado para {baud} baud")

    def close(self):
        try:
            if self.ser and self.ser.is_open:
                self.ser.close()
                self.log("✓ Porta fechada")
        except Exception as e:
            self.log(f"⚠ Erro ao fechar porta: {e}")
        finally:
            self.ser = None

    def is_open(self) -> bool:
        return bool(self.ser and self.ser.is_open)

    def write(self, data: bytes):
        if not self.is_open():
            raise RuntimeError("Porta serial não aberta")
        self.ser.write(data)
        self.ser.flush()

    def read(self, size: int = 1) -> bytes:
        if not self.is_open():
            raise RuntimeError("Porta serial não aberta")
        return self.ser.read(size)

    def in_waiting(self) -> int:
        if not self.is_open():
            return 0
        return self.ser.in_waiting

    def purge(self):
        if self.is_open():
            try:
                self.ser.reset_input_buffer()
                self.ser.reset_output_buffer()
            except Exception:
                pass

# ----------------------------- Protocol Layer ------------------------------
def parse_hex_string(hx: str) -> bytes:
    hx = hx.strip().replace(",", " ").replace(";", " ").replace("\n", " ")
    parts = [p for p in hx.split(" ") if p]
    return bytes(int(p, 16) for p in parts)

class WTV380Protocol:
    def __init__(self, ser: SerialWorker, logger: GuiLogger, firmware_data: bytes):
        self.ser = ser
        self.logger = logger  # Keep full logger for progress updates
        self.log = logger.log  # Shortcut for logging
        self.cfg = PROTOCOL
        self.firmware_data = firmware_data  # Pre-loaded firmware
        self.header_16 = firmware_data[:16]  # Cached header for handshake

    def handshake_flooding(self, timeout_sec: int = 10) -> bool:
        """
        FLOODING HANDSHAKE with precise 2ms timing and manual power cycle.
        User must manually power cycle the device during flooding.

        NO LOGGING during flood to prevent GUI freeze!
        Only logs when VALID handshake response is found.
        """
        # PURGE #3: Final purge right before flooding starts
        # This is the last chance to clear any garbage
        self.ser.purge()
        time.sleep(0.020)  # 20ms settling time

        period_s = self.cfg["hs_period_ms"] / 1000.0  # 2ms

        buf64 = bytearray(64)
        buf64[:16] = self.header_16  # Use pre-cached header
        send = bytes(buf64)

        self.log("Aguardando ciclo de energia...")

        start_time = time.perf_counter()
        next_send_time = start_time
        send_count = 0

        # Accumulate responses in buffer to find valid handshake
        response_buffer = bytearray()

        # Minimum delay before accepting response (prevents false positives from garbage)
        MIN_RESPONSE_DELAY = 0.100  # 100ms - real bootloader takes time to respond

        while True:
            current_time = time.perf_counter()
            elapsed = current_time - start_time

            # Check timeout
            if elapsed > timeout_sec:
                self.log(f"✗ Timeout do handshake após {timeout_sec}s")
                return False

            # Send handshake at precise intervals
            if current_time >= next_send_time:
                self.ser.write(send)
                send_count += 1
                next_send_time += period_s

            # Check for response (non-blocking) - NO LOGGING!
            # IMPORTANT: Ignore responses in first 100ms (prevents false positives from garbage)
            waiting_bytes = self.ser.in_waiting()
            if waiting_bytes > 0 and elapsed > MIN_RESPONSE_DELAY:
                try:
                    chunk = self.ser.read(waiting_bytes)
                    response_buffer += chunk

                    # Aggressively discard garbage: if buffer doesn't start with 0x7E, trim it
                    # Valid response MUST start with 7E EF 00 D0
                    while len(response_buffer) > 0 and response_buffer[0] != 0x7E:
                        response_buffer.pop(0)

                    # Keep buffer manageable (last 128 bytes)
                    if len(response_buffer) > 128:
                        response_buffer = response_buffer[-128:]

                    # Search for valid handshake: 7E EF 00 D0
                    for i in range(len(response_buffer) - 3):
                        if (response_buffer[i] == 0x7E and
                            response_buffer[i+1] == 0xEF and
                            response_buffer[i+2] == 0x00 and
                            response_buffer[i+3] == 0xD0):

                            # Found valid handshake! Extract full 64-byte response
                            if i + 64 <= len(response_buffer):
                                valid_response = response_buffer[i:i+64]
                            else:
                                # Need to read more to get full 64 bytes
                                remaining_needed = 64 - (len(response_buffer) - i)
                                time.sleep(0.01)  # Wait for rest of packet
                                extra = self.ser.read(remaining_needed)
                                valid_response = response_buffer[i:] + extra

                            # Log success ONCE
                            self.log("✓ Handshake bem-sucedido")
                            return True

                except Exception as e:
                    # Only log errors, not every response
                    pass

            # Maintain precise timing - NO LOGGING IN LOOP!
            remaining = next_send_time - time.perf_counter()
            if remaining > 0.0001:
                precise_sleep(remaining - 0.0001)

    def _pack_u16(self, val: int, little: bool = True) -> bytes:
        return struct.pack("<H" if little else ">H", val & 0xFFFF)

    def _pack_u32(self, val: int, little: bool = True) -> bytes:
        return struct.pack("<I" if little else ">I", val & 0xFFFFFFFF)

    def build_write_packet(self, address: int, payload: bytes, flag: int) -> bytes:
        wh = self.cfg["write_header"]
        head1, head2, check, mode = wh["Head1"] & 0xFF, wh["Head2"] & 0xFF, wh["Check"] & 0xFF, wh["Mode"] & 0xFF

        addr_bytes = self._pack_u32(address, True)
        leng_bytes = self._pack_u16(len(payload), True)
        crc_val = compute_crc(payload)
        crc_bytes = self._pack_u16(crc_val, True)

        # Per STM32 Write_ST struct: Address + Length + CRC
        pkt = bytes([head1, head2, check, mode]) + addr_bytes + leng_bytes + crc_bytes + bytes([flag]) + payload
        return pkt

    def send_init(self, timeout_ms: int = 10000) -> bool:
        # Send INIT command without logging
        hx = (self.cfg["frames"].get("TARGET_INIT_CMD") or "").strip()
        if not hx:
            raise ValueError(f"Frame 'TARGET_INIT_CMD' not set.")
        data = parse_hex_string(hx)
        self.ser.write(data)

        deadline = time.perf_counter() + timeout_ms/1000.0
        bad_ack_count = 0
        MAX_BAD_ACKS = 500

        buf = bytearray()

        while time.perf_counter() < deadline:
            if self.ser.in_waiting() > 0:
                chunk = self.ser.read(self.ser.in_waiting())
                buf += chunk

                # Search for valid INIT ACK pattern: 7E FE 00 C0
                # Don't assume it starts at byte 0 - there may be garbage before it
                for i in range(len(buf) - 3):
                    if (buf[i] == 0x7E and buf[i+1] == 0xFE and buf[i+3] == 0xC0):
                        if buf[i+2] == 0x00:
                            # INIT ACK OK
                            return True
                        else:
                            # Bad ACK
                            bad_ack_count += 1
                            if bad_ack_count > MAX_BAD_ACKS:
                                return False
                            # Remove processed data up to and including this bad ACK
                            buf = buf[i+4:]
                            break

                # Keep buffer manageable
                if len(buf) > 128:
                    buf = buf[-128:]

            precise_sleep(0.001)

        return False

    def write_loop(self) -> bool:
        """Write loop using pre-loaded firmware data with progress reporting"""
        file_size = len(self.firmware_data)
        HEAD_SIZE = self.cfg["handshake_header_len"]

        # Extract firmware size from header (bytes 4-7)
        firmware_size = struct.unpack('<I', self.firmware_data[4:8])[0]
        expected_file_size = HEAD_SIZE + firmware_size

        if file_size < expected_file_size:
            self.log(f"✗ Arquivo de firmware muito pequeno")
            return False

        # CRITICAL: Skip the 16-byte header when flashing!
        # Header (bytes 0-15) is only for handshake
        # Firmware code starts at byte 16
        firmware_to_flash = self.firmware_data[HEAD_SIZE:HEAD_SIZE + firmware_size]

        # PURGE #2: Clear buffers again right before handshake
        # (Extra insurance against any accumulated garbage)
        self.ser.purge()
        time.sleep(0.050)  # 50ms settling time

        # Handshake with flooding (30s timeout for user to power cycle)
        self.logger.update_progress(5)
        if not self.handshake_flooding(timeout_sec=30):
            self.log("✗ Falha no handshake")
            return False

        self.logger.update_progress(10)

        # Init
        if not self.send_init():
            self.log("✗ Falha no INIT")
            return False
        self.log("✓ INIT bem-sucedido")

        self.logger.update_progress(15)

        # Write firmware data
        self.log("Gravando dados do firmware...")

        total_bytes = len(firmware_to_flash)
        psize = 4096
        addr = 0
        sent = 0
        packet_num = 0

        while sent < total_bytes:
            chunk = firmware_to_flash[sent:sent + psize]
            actual_chunk_size = len(chunk)

            # Pad if needed (shouldn't happen if size is validated)
            if len(chunk) < psize:
                chunk = chunk + b"\xFF" * (psize - len(chunk))

            # Calculate flag (always 0 for 4096-byte aligned firmware)
            flag = 0

            pkt = self.build_write_packet(address=addr, payload=chunk, flag=flag)
            self.ser.write(pkt)

            # Wait for ACK - device needs time to respond
            time.sleep(0.100)  # 100ms wait for ACK

            # Now check for ACK response
            if self.ser.in_waiting() > 0:
                rx = self.ser.read(self.ser.in_waiting())

                # Search for valid ACK pattern: 7E FE 00 C3
                # Don't assume it starts at byte 0 - there may be garbage before it
                ack_found = False
                for i in range(len(rx) - 3):
                    if (rx[i] == 0x7E and rx[i+1] == 0xFE and
                        rx[i+2] == 0x00 and rx[i+3] == 0xC3):
                        ack_found = True
                        break

                if ack_found:
                    # ACK OK - continue
                    pass
                else:
                    self.log(f"ERRO: ACK inválido para pacote #{packet_num + 1} @ 0x{addr:08X}")
                    self.log(f"  Resposta: {rx.hex(' ').upper()}")
                    return False
            else:
                self.log(f"ERRO: Sem ACK para pacote #{packet_num + 1} @ 0x{addr:08X}")
                return False

            sent += actual_chunk_size
            addr += psize
            packet_num += 1

            # Update progress (15% to 95%)
            progress_percent = 15 + (sent / total_bytes) * 80
            self.logger.update_progress(progress_percent)

            # Log every 10 packets or at end
            if packet_num % 10 == 0 or sent >= total_bytes:
                self.log(f"Pacote #{packet_num}: {sent}/{total_bytes} bytes ({100.0*sent/total_bytes:.1f}%)")

        self.log(f"✓ Todos os {packet_num} pacotes gravados com sucesso")

        # Finish
        hx = (self.cfg["frames"].get("FINISH_CMD") or "").strip()
        data = parse_hex_string(hx)
        self.ser.write(data)

        deadline = time.perf_counter() + 2.0
        buf = bytearray()
        while time.perf_counter() < deadline:
            if self.ser.in_waiting() > 0:
                rx = self.ser.read(self.ser.in_waiting())
                buf += rx

                # Search for valid FINISH ACK pattern: 7E FE 00 D3
                # Don't assume it starts at byte 0 - there may be garbage before it
                for i in range(len(buf) - 3):
                    if (buf[i] == 0x7E and buf[i+1] == 0xFE and
                        buf[i+2] == 0x00 and buf[i+3] == 0xD3):
                        self.log("✓ FINISH bem-sucedido")
                        self.logger.update_progress(100)
                        return True

            precise_sleep(0.001)

        self.log("✓ Comando FINISH enviado (sem ACK, pode ser normal)")
        self.logger.update_progress(100)
        return True  # Consider success even without FINISH ACK

# --------------------------- Tkinter Application ---------------------------
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)

        # Load icon if available
        try:
            icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "favicon.ico")
            if os.path.exists(icon_path):
                self.iconbitmap(icon_path)
        except Exception:
            pass  # Ignore if icon not found

        try:
            self.state('zoomed')
        except Exception:
            self.attributes('-zoomed', True)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # Connection state
        self.is_connected = False

        # === ROW 1: Main Controls ===
        top = ttk.Frame(self); top.pack(fill="x", padx=10, pady=10)

        # COM Port selector (no label, just dropdown)
        self.comb = ttk.Combobox(top, values=self.list_serial_ports(), width=15, state="readonly")
        self.comb.pack(side="left", padx=(0, 15))

        # Toggle Connect/Disconnect button (green/red) - fixed width to prevent shifting
        self.toggle_btn = tk.Button(top, text="CONECTAR", command=self.on_toggle_connection,
                                      bg="green", fg="black", font=("Arial", 10, "bold"),
                                      width=13, pady=5, relief=tk.RAISED)
        self.toggle_btn.pack(side="left", padx=15)

        # Start Update button (blue - primary action)
        self.start_btn = tk.Button(top, text="INICIAR ATUALIZAÇÃO", command=self.on_start, state="disabled",
                                     bg="#1E90FF", fg="black", font=("Arial", 10, "bold"),
                                     padx=20, pady=5, relief=tk.RAISED, disabledforeground="darkgray")
        self.start_btn.pack(side="left", padx=15)

        # Clear Log button (orange - caution action)
        clear_log_btn = tk.Button(top, text="LIMPAR LOG", command=self.on_clear_log,
                                    bg="#FF8C00", fg="black", font=("Arial", 10, "bold"),
                                    padx=20, pady=5, relief=tk.RAISED)
        clear_log_btn.pack(side="left", padx=15)

        # Save Log button (sea green - save action)
        save_log_btn = tk.Button(top, text="SALVAR LOG", command=self.on_save_log,
                                   bg="#2E8B57", fg="black", font=("Arial", 10, "bold"),
                                   padx=20, pady=5, relief=tk.RAISED)
        save_log_btn.pack(side="left", padx=15)

        # === ROW 2: Firmware Info ===
        filef = ttk.Frame(self); filef.pack(fill="x", padx=10, pady=(0,10))
        ttk.Label(filef, text="Firmware:").pack(side="left")
        self.firmware_label = ttk.Label(filef, text="", foreground="blue", font=("Arial", 9))
        self.firmware_label.pack(side="left", padx=5, fill="x", expand=True)

        # === ROW 3: Progress Bar ===
        progf = ttk.Frame(self); progf.pack(fill="x", padx=10, pady=(0,10))
        ttk.Label(progf, text="Progresso:").pack(side="left")
        self.progress_var = tk.DoubleVar(value=0.0)
        self.progress_bar = ttk.Progressbar(progf, variable=self.progress_var, maximum=100, length=400)
        self.progress_bar.pack(side="left", fill="x", expand=True, padx=5)
        self.progress_label = ttk.Label(progf, text="0%", width=6)
        self.progress_label.pack(side="left")

        # === ROW 4+: Log Pane (Expanded Vertically) ===
        logf = ttk.Frame(self); logf.pack(fill="both", expand=True, padx=10, pady=10)
        self.text = tk.Text(logf, wrap="none", background="black", foreground="white")
        self.text.pack(fill="both", expand=True, side="left")
        self.text.configure(state="disabled")
        vsb = ttk.Scrollbar(logf, command=self.text.yview); vsb.pack(side="right", fill="y")
        self.text.configure(yscrollcommand=vsb.set)

        self.logger = GuiLogger(self.text, self.progress_var)
        self.ser_worker = SerialWorker(self.logger)
        self.worker_thread = None
        self.stop_event = threading.Event()

        # Firmware data (loaded on startup)
        self.firmware_data = None
        self.firmware_filename = None

        # Update progress label when progress changes
        self.progress_var.trace_add('write', lambda *args: self.progress_label.config(text=f"{self.progress_var.get():.0f}%"))

        # Auto-load firmware on startup
        self.load_firmware_on_startup()

        # Start auto-refresh for COM ports (every 1 second)
        self.start_comport_auto_refresh()

    def list_serial_ports(self) -> List[str]:
        if list_ports is None:
            return []
        return [p.device for p in list_ports.comports()]

    def load_firmware_on_startup(self):
        """Auto-load the .bin file in the same folder as the script"""
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            # Find all .bin files
            bin_files = [f for f in os.listdir(script_dir) if f.lower().endswith('.bin')]

            if len(bin_files) == 0:
                self.logger.log("✗ Nenhum arquivo .bin encontrado no diretório")
                self.firmware_label.config(text="Firmware não encontrado!", foreground="red")
                return

            if len(bin_files) > 1:
                self.logger.log(f"⚠ Múltiplos arquivos .bin encontrados, usando: {bin_files[0]}")

            # Load the first .bin file found
            firmware_path = os.path.join(script_dir, bin_files[0])
            with open(firmware_path, 'rb') as f:
                self.firmware_data = f.read()

            self.firmware_filename = bin_files[0]
            self.firmware_label.config(text=f"{bin_files[0]} ({len(self.firmware_data)} bytes)", foreground="green")
            self.logger.log(f"✓ Firmware carregado: {bin_files[0]} ({len(self.firmware_data)} bytes)")

        except Exception as e:
            self.logger.log(f"✗ Erro ao carregar firmware: {e}")
            self.firmware_label.config(text="Erro ao carregar firmware!", foreground="red")

    def start_comport_auto_refresh(self):
        """Auto-refresh COM port list every 1 second"""
        self.auto_refresh_comports()

    def auto_refresh_comports(self):
        """Periodic callback to update COM port list"""
        current_ports = self.list_serial_ports()
        current_values = list(self.comb["values"])

        # Only update if list changed (avoid flickering)
        if current_ports != current_values:
            current_selection = self.comb.get()
            self.comb["values"] = current_ports

            # Restore selection if still valid
            if current_selection in current_ports:
                self.comb.set(current_selection)

        # Schedule next refresh in 1 second
        self.after(1000, self.auto_refresh_comports)

    def on_toggle_connection(self):
        """Toggle between Connect and Disconnect"""
        if not self.is_connected:
            # Currently disconnected -> Connect
            port = self.comb.get()
            if not port:
                messagebox.showwarning(APP_NAME, "Selecione uma porta COM primeiro.")
                return

            # Open at bootloader baud (1000000)
            ok = self.ser_worker.open(port, PROTOCOL["boot_baudrate"], timeout=0.2, write_timeout=1.0)
            if not ok:
                return

            # Update state
            self.is_connected = True
            self.toggle_btn.config(text="DESCONECTAR", bg="red")
            self.start_btn.configure(state="normal" if self.firmware_data else "disabled")
        else:
            # Currently connected -> Disconnect
            self.on_stop()
            self.ser_worker.close()

            # Update state
            self.is_connected = False
            self.toggle_btn.config(text="CONECTAR", bg="green")
            self.start_btn.configure(state="disabled")

    def on_start(self):
        if not self.firmware_data:
            messagebox.showerror(APP_NAME, "Nenhum firmware carregado. Verifique o arquivo de firmware.")
            return

        self.stop_event.clear()
        self.worker_thread = threading.Thread(target=self._worker_main, daemon=True)
        self.worker_thread.start()
        self.start_btn.configure(state="disabled")

    def on_stop(self):
        """Stop worker thread (called during disconnect or close)"""
        self.stop_event.set()
        if self.worker_thread and self.worker_thread.is_alive():
            self.logger.log("Parando processo...")
            self.worker_thread.join(timeout=2.0)
        self.worker_thread = None
        if self.is_connected:
            self.start_btn.configure(state="normal")

    def on_clear_log(self):
        """Clear the log pane"""
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")
        self.logger.log("Log limpo")

    def on_save_log(self):
        """Save log content to file"""
        try:
            # Get log content
            log_content = self.text.get("1.0", "end-1c")

            if not log_content.strip():
                messagebox.showinfo(APP_NAME, "Log está vazio. Nada para salvar.")
                return

            # Open file picker
            from datetime import datetime
            default_filename = f"wtv380_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

            filepath = filedialog.asksaveasfilename(
                title="Salvar Arquivo de Log",
                defaultextension=".txt",
                filetypes=[("Arquivos de texto", "*.txt"), ("Todos os arquivos", "*.*")],
                initialfile=default_filename
            )

            if filepath:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(log_content)
                self.logger.log(f"✓ Log salvo em: {os.path.basename(filepath)}")
                messagebox.showinfo(APP_NAME, f"Log salvo com sucesso em:\n{filepath}")

        except Exception as e:
            error_msg = f"Erro ao salvar log: {e}"
            self.logger.log(f"✗ {error_msg}")
            messagebox.showerror(APP_NAME, error_msg)

    def _worker_main(self):
        try:
            # Reset progress (through logger queue for thread safety)
            self.logger.update_progress(0)

            # CRITICAL: Purge buffers FIRST - clear any accumulated garbage
            # (Device might have been sending data if it was powered ON)
            self.ser_worker.purge()
            time.sleep(0.050)  # 50ms settling time for hardware buffers

            # Use pre-loaded firmware data
            self.logger.log(f"Usando firmware: {self.firmware_filename} ({len(self.firmware_data)} bytes)")

            # Create protocol instance with pre-loaded firmware
            prot = WTV380Protocol(
                ser=self.ser_worker,
                logger=self.logger,
                firmware_data=self.firmware_data
            )

            # Execute update (handshake + init + write + finish)
            ok = prot.write_loop()

            if ok:
                self.logger.log("✓ Atualização de firmware concluída com sucesso!")

                # Show success popup with power cycle instruction (must use after() for thread safety)
                self.after(0, lambda: messagebox.showinfo(
                    APP_NAME,
                    "✓ Atualização de firmware concluída com sucesso!\n\n"
                    "Desligue e religue o dispositivo agora para ativar o novo firmware.\n"
                    "Você deve ouvir uma mensagem de áudio em chinês confirmando a atualização.",
                    icon='info'
                ))
            else:
                self.logger.log("✗ Atualização de firmware falhou")
                # Show error popup (must use after() for thread safety)
                self.after(0, lambda: messagebox.showerror(APP_NAME, "Atualização falhou. Verifique o log para detalhes."))

        except Exception as e:
            self.logger.log(f"✗ Erro: {e}")
            # Show error popup (must use after() for thread safety)
            error_msg = f"Erro: {e}"
            self.after(0, lambda: messagebox.showerror(APP_NAME, error_msg))
        finally:
            # Re-enable Start Update button (must use after() for thread safety)
            self.after(0, lambda: self.start_btn.configure(state="normal"))

    def on_close(self):
        try:
            self.on_stop()
            self.ser_worker.close()
        finally:
            self.destroy()

def main():
    app = App()
    app.mainloop()

if __name__ == "__main__":
    import threading
    main()
