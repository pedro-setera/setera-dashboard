import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

import tkinter as tk
from tkinter import ttk, messagebox
import time
import threading
import telnetlib
from datetime import datetime, timedelta
import configparser
import tkintermapview
import os
import socket
import errno

# Global variables
telnet_connection = None
send_task = None
sending_active = False  # Tracks whether sending is active
time_offset = 0
send_interval = 5
listener_thread = None
connection_monitor_task = None
connection_monitor_active = False

# Simplified path determination for portable Python environment
application_path = os.path.dirname(os.path.abspath(__file__))

class CaseSensitiveConfigParser(configparser.ConfigParser):
    def optionxform(self, optionstr):
        return optionstr

def load_alarm_values():
    config = CaseSensitiveConfigParser()
    config_path = os.path.join(application_path, 'config_simulador.ini')
    with open(config_path, 'r', encoding='utf-8') as configfile:
        config.read_file(configfile)
    alarms = config['alarms']
    return {key: value for key, value in alarms.items()}

def check_socket_state_passive():
    """Passively check socket state without any network activity - only for logging"""
    global telnet_connection
    if telnet_connection is None:
        return "DISCONNECTED"
    
    try:
        # Get the underlying socket
        sock = telnet_connection.get_socket()
        if sock is None:
            return "NO_SOCKET"
            
        # Try to get socket addresses - this doesn't generate network traffic
        try:
            local_addr = sock.getsockname()
            remote_addr = sock.getpeername()
            
            # Check if socket has any errors using SO_ERROR - passive check
            error_code = sock.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
            if error_code != 0:
                timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                append_to_log(f"{timestamp} [SOCKET-PASSIVE] Socket error detected: error code {error_code}")
                return f"ERROR_{error_code}"
                
            return "APPEARS_CONNECTED"  # We can't know for sure without active probing
            
        except socket.error as e:
            # If getpeername fails, socket is likely disconnected
            timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            
            # Windows-specific error codes
            WSAENOTCONN = 10057
            WSAECONNRESET = 10054
            
            if hasattr(e, 'winerror'):
                if e.winerror == WSAENOTCONN:
                    append_to_log(f"{timestamp} [SOCKET-PASSIVE] Socket not connected (getpeername failed)")
                    return "NOT_CONNECTED"
                elif e.winerror == WSAECONNRESET:
                    append_to_log(f"{timestamp} [SOCKET-PASSIVE] Connection was reset")
                    return "RESET"
            
            append_to_log(f"{timestamp} [SOCKET-PASSIVE] Socket error: {e}")
            return "ERROR_CHECK"
            
    except Exception as e:
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        append_to_log(f"{timestamp} [SOCKET-PASSIVE] Exception checking state: {e}")
        return "EXCEPTION"

# Removed active monitoring function - we don't want any periodic socket checks

def send_data_to_server():
    global telnet_connection
    if not sending_active:  # Check if sending should be active
        return
        
    # Fetch values from the UI components
    imei = imei_entry.get()
    alarme = alarm_var.get()
    sat = sat_entry.get()
    hdop = hdop_entry.get()
    vel = vel_entry.get()
    odo = odo_entry.get()
    entradas = entradas_mapping[entradas_var.get()]
    saidas = bloqueio_mapping[bloqueio_var.get()]
    motor = motor_mapping[motor_var.get()]
    in5 = gpio_mapping[in5_var.get()]
    in6 = gpio_mapping[in6_var.get()]
    in7 = gpio_mapping[in7_var.get()]
    in8 = gpio_mapping[in8_var.get()]
    in9 = gpio_mapping[in9_var.get()]
    in10 = gpio_mapping[in10_var.get()]
    out2 = gpio_mapping[out2_var.get()]
    out3 = gpio_mapping[out3_var.get()]
    out4 = gpio_mapping[out4_var.get()]
    out5 = gpio_mapping[out5_var.get()]
    driver = driver_entry.get()
    activity = activity_entry.get()
    tpms_sensor = tpms_sensor_entry.get()
    tpms_alarme = tpms_alarm_mapping[tpms_alarm_var.get()]
    tpms_pressure = tpms_pressure_entry.get()
    tpms_temperature = tpms_temperature_entry.get()
    tanque = tanque_entry.get()
    can_vel = can_vel_entry.get()
    rpm = rpm_entry.get()
    temp = temp_entry.get()
    turbo = turbo_entry.get()
    lat = lat_entry.get()
    long = long_entry.get()

    # Apply the corrected time offset
    time_offset_seconds = time_offset * 3600
    current_utc_datetime = datetime.utcnow() + timedelta(seconds=time_offset_seconds)
    current_date_time = current_utc_datetime.strftime("%y%m%d%H%M%S")

    # Generate the GPS string with current settings
    send_data = calculate_gps_string(imei, alarme, sat, hdop, vel, odo, entradas, saidas, motor, tanque,
                                     can_vel, rpm, temp, turbo, lat, long, in5, in6, in7, in8, in9, in10,
                                     out2, out3, out4, out5, current_date_time, driver, activity, tpms_sensor,
                                     tpms_alarme, tpms_pressure, tpms_temperature)

    if telnet_connection is not None:
        try:
            bytes_to_send = len(send_data.encode('ascii'))
            timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            
            # Send data
            telnet_connection.write(send_data.encode('ascii'))
            
            append_to_log(f"{timestamp} [TX-TIMER] Sent {bytes_to_send} bytes: {send_data}")
                
        except socket.error as e:
            timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            
            # Windows-specific error codes
            WSAECONNRESET = 10054
            WSAECONNABORTED = 10053
            WSAENOTCONN = 10057
            WSAESHUTDOWN = 10058
            
            if hasattr(e, 'winerror'):
                if e.winerror == WSAECONNRESET:
                    append_to_log(f"{timestamp} [TX-ERROR] Connection reset by gateway - socket was closed by remote!")
                elif e.winerror == WSAECONNABORTED:
                    append_to_log(f"{timestamp} [TX-ERROR] Connection aborted - socket was terminated!")
                elif e.winerror == WSAENOTCONN:
                    append_to_log(f"{timestamp} [TX-ERROR] Socket not connected - gateway closed the connection!")
                elif e.winerror == WSAESHUTDOWN:
                    append_to_log(f"{timestamp} [TX-ERROR] Socket shutdown - cannot send after socket shutdown!")
                else:
                    append_to_log(f"{timestamp} [TX-ERROR] Socket error during send: {e} (winerror: {e.winerror})")
            else:
                append_to_log(f"{timestamp} [TX-ERROR] Socket error during send: {e}")
                
            # Mark connection as dead
            telnet_connection = None
            connect_button.config(text="CONECTAR", bg='SystemButtonFace', fg='black')
            
        except Exception as e:
            timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            append_to_log(f"{timestamp} [TX-ERROR] General error sending data: {e}")

def send_single_position():
    global telnet_connection
    if telnet_connection is None:
        append_to_log("Não conectado ao servidor. Por favor, conecte-se primeiro.")
        messagebox.showerror("Erro de conexão", "Não conectado ao servidor. Por favor, conecte-se primeiro.")
        return
    # Fetch values from the UI components just like in send_data_to_server
    imei = imei_entry.get()
    alarme = alarm_var.get()
    sat = sat_entry.get()
    hdop = hdop_entry.get()
    vel = vel_entry.get()
    odo = odo_entry.get()
    entradas = entradas_mapping[entradas_var.get()]
    saidas = bloqueio_mapping[bloqueio_var.get()]
    motor = motor_mapping[motor_var.get()]
    in5 = gpio_mapping[in5_var.get()]
    in6 = gpio_mapping[in6_var.get()]
    in7 = gpio_mapping[in7_var.get()]
    in8 = gpio_mapping[in8_var.get()]
    in9 = gpio_mapping[in9_var.get()]
    in10 = gpio_mapping[in10_var.get()]
    out2 = gpio_mapping[out2_var.get()]
    out3 = gpio_mapping[out3_var.get()]
    out4 = gpio_mapping[out4_var.get()]
    out5 = gpio_mapping[out5_var.get()]
    driver = driver_entry.get()
    activity = activity_entry.get()
    tpms_sensor = tpms_sensor_entry.get()
    tpms_alarme = tpms_alarm_mapping[tpms_alarm_var.get()]
    tpms_pressure = tpms_pressure_entry.get()
    tpms_temperature = tpms_temperature_entry.get()
    tanque = tanque_entry.get()
    can_vel = can_vel_entry.get()
    rpm = rpm_entry.get()
    temp = temp_entry.get()
    turbo = turbo_entry.get()
    lat = lat_entry.get()
    long = long_entry.get()

    # Apply the corrected time offset
    time_offset_seconds = time_offset * 3600
    current_utc_datetime = datetime.utcnow() + timedelta(seconds=time_offset_seconds)
    current_date_time = current_utc_datetime.strftime("%y%m%d%H%M%S")

    # Generate the GPS string with current settings
    send_data = calculate_gps_string(imei, alarme, sat, hdop, vel, odo, entradas, saidas, motor, tanque,
                                     can_vel, rpm, temp, turbo, lat, long, in5, in6, in7, in8, in9, in10,
                                     out2, out3, out4, out5, current_date_time, driver, activity, tpms_sensor,
                                     tpms_alarme, tpms_pressure, tpms_temperature)

    try:
        bytes_to_send = len(send_data.encode('ascii'))
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        
        # Send data
        telnet_connection.write(send_data.encode('ascii'))
        
        append_to_log(f"{timestamp} [TX-SINGLE] Sent {bytes_to_send} bytes: {send_data}")
            
    except socket.error as e:
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        
        # Windows-specific error codes
        WSAECONNRESET = 10054
        WSAECONNABORTED = 10053
        WSAENOTCONN = 10057
        WSAESHUTDOWN = 10058
        
        if hasattr(e, 'winerror'):
            if e.winerror == WSAECONNRESET:
                append_to_log(f"{timestamp} [TX-ERROR] Connection reset by gateway - socket was closed by remote!")
            elif e.winerror == WSAECONNABORTED:
                append_to_log(f"{timestamp} [TX-ERROR] Connection aborted - socket was terminated!")
            elif e.winerror == WSAENOTCONN:
                append_to_log(f"{timestamp} [TX-ERROR] Socket not connected - gateway closed the connection!")
            elif e.winerror == WSAESHUTDOWN:
                append_to_log(f"{timestamp} [TX-ERROR] Socket shutdown - cannot send after socket shutdown!")
            else:
                append_to_log(f"{timestamp} [TX-ERROR] Socket error during send: {e} (winerror: {e.winerror})")
        else:
            append_to_log(f"{timestamp} [TX-ERROR] Socket error during send: {e}")
            
        # Mark connection as dead
        telnet_connection = None
        connect_button.config(text="CONECTAR", bg='SystemButtonFace', fg='black')
        
    except Exception as e:
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        append_to_log(f"{timestamp} [TX-ERROR] General error sending single position: {e}")

def schedule_sending():
    global send_task
    if sending_active:  # Only proceed if sending is active
        send_data_to_server()
        # Update to read interval directly from the UI component
        current_interval = float(intervalo_var.get())
        send_task = threading.Timer(current_interval, schedule_sending)
        send_task.start()

def stop_sending():
    global send_task
    if send_task is not None:
        send_task.cancel()
        send_task = None

def append_to_log(message):
    log_text.config(state='normal')  # Enable editing to append text
    log_text.insert(tk.END, message + '\n')  # Append the message and a newline
    log_text.config(state='disabled')  # Disable editing again
    log_text.see(tk.END)  # Scroll to the end of the log

def listen_for_server_messages():
    global telnet_connection
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    append_to_log(f"{timestamp} [LISTENER] Receiver thread started - passively listening for server messages")
    
    consecutive_errors = 0
    max_consecutive_errors = 5
    
    try:
        while telnet_connection is not None:
            try:
                    
                message = telnet_connection.read_very_eager()  # Non-blocking read
                if message:
                    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                    
                    # Log raw bytes received
                    bytes_received = len(message)
                    append_to_log(f"{timestamp} [RX-BYTES] Received {bytes_received} bytes from server")
                    
                    # Try to decode and log message
                    try:
                        decoded_msg = message.decode('ascii')
                        append_to_log(f"{timestamp} [RX-DATA] {decoded_msg}")
                    except UnicodeDecodeError:
                        # If not ASCII, show hex representation
                        hex_msg = message.hex()
                        append_to_log(f"{timestamp} [RX-HEX] Non-ASCII data: {hex_msg}")
                    
                    consecutive_errors = 0  # Reset error counter on successful read
                    
                time.sleep(0.1)  # Prevent CPU overuse
                
            except socket.error as e:
                consecutive_errors += 1
                timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                
                # Windows-specific error codes
                WSAECONNRESET = 10054
                WSAECONNABORTED = 10053
                WSAETIMEDOUT = 10060
                
                if hasattr(e, 'winerror'):
                    # Windows socket errors
                    if e.winerror == WSAECONNRESET:
                        append_to_log(f"{timestamp} [LISTENER] Connection reset by server (TCP RST received)")
                        break
                    elif e.winerror == WSAECONNABORTED:
                        append_to_log(f"{timestamp} [LISTENER] Connection aborted")
                        break
                    elif e.winerror == WSAETIMEDOUT:
                        append_to_log(f"{timestamp} [LISTENER] Socket timeout during read")
                    else:
                        append_to_log(f"{timestamp} [LISTENER] Socket error: {e} (winerror: {e.winerror})")
                elif hasattr(errno, 'ECONNRESET') and e.errno == errno.ECONNRESET:
                    append_to_log(f"{timestamp} [LISTENER] Connection reset by server (TCP RST received)")
                    break
                elif hasattr(errno, 'ECONNABORTED') and e.errno == errno.ECONNABORTED:
                    append_to_log(f"{timestamp} [LISTENER] Connection aborted")
                    break
                elif hasattr(errno, 'ETIMEDOUT') and e.errno == errno.ETIMEDOUT:
                    append_to_log(f"{timestamp} [LISTENER] Socket timeout during read")
                else:
                    if hasattr(e, 'errno'):
                        append_to_log(f"{timestamp} [LISTENER] Socket error: {e} (errno: {e.errno})")
                    else:
                        append_to_log(f"{timestamp} [LISTENER] Socket error: {e}")
                
                if consecutive_errors >= max_consecutive_errors:
                    append_to_log(f"{timestamp} [LISTENER] Too many consecutive errors ({consecutive_errors}), stopping listener")
                    break
                    
            except EOFError:
                timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                append_to_log(f"{timestamp} [LISTENER] EOF received - server closed connection")
                break
                
            except Exception as e:
                consecutive_errors += 1
                timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                append_to_log(f"{timestamp} [LISTENER-ERROR] Error reading from server: {e}")
                
                if consecutive_errors >= max_consecutive_errors:
                    append_to_log(f"{timestamp} [LISTENER] Too many consecutive errors, stopping listener")
                    break
                    
    except Exception as e:
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        append_to_log(f"{timestamp} [LISTENER-FATAL] Fatal error in listener thread: {e}")
    
    finally:
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        append_to_log(f"{timestamp} [LISTENER] Receiver thread stopped")

def calculate_length(data_string):
    """Calculate the length of the data string from the first comma to the last comma (excluding the comma before checksum)."""
    # Find the position of the last comma before the checksum
    last_comma_pos = data_string.rfind(',')
    # Calculate length from first comma to the last comma before checksum
    return last_comma_pos - data_string.find(',')

def calculate_checksum(data_string):
    """Calculate the checksum (CheckSum8 Modulo 256) for the given string."""
    checksum = sum(ord(c) for c in data_string) % 256
    return format(checksum, '02X')

def calculate_gps_string(imei_value, alarme_value, sat_value, hdop_value, vel_value, odo_value,
                         entradas, saidas, motor, tanque, can_vel, rpm, temp, turbo, lat, long,
                         in5, in6, in7, in8, in9, in10, out2, out3, out4, out5, current_date_time,
                         driver, activity, tpms_sensor, tpms_alarme, tpms_pressure, tpms_temperature):
    # Fetch alarm code from alarm_values using the selected alarm name
    alarm_code = alarm_values[alarme_value]

    # Construct the dynamic part of the GPS tracker string with user-provided values
    dynamic_part = f",{imei_value},000,{alarm_code},,{current_date_time},A,{lat},{long},{sat_value},{hdop_value},{vel_value},167,900,{odo_value},724|2|8182|031DC00A,30,003D,{entradas},{saidas},099E|019C|0000|0000,128,,FR1,{motor},234212.58,84093.896,,{tanque},{can_vel},{rpm},28,{temp},22263300,3615461,347962,193.943,1235,128,28654,28,3.80,44252,33729,62,{turbo},15110510,116654,1,2,0,0,0,-1,9,44,0,0,0,512,{in5},{in6},{in7},{in8},{in9},{in10},{out2},{out3},{out4},{out5},{driver},{activity},{tpms_sensor}|{tpms_alarme}|{tpms_pressure}|{tpms_temperature},"

    # First, calculate the length as it would appear in the final string
    length = len(dynamic_part) - 1  # -1 to remove the last comma before checksum

    # Now insert the length into the string
    string_with_length = f"&&]{length}{dynamic_part}"

    # Finally, calculate the checksum for this string, including the last comma
    checksum_value = calculate_checksum(string_with_length)

    # Append the checksum to complete the string
    finalized_string = f"{string_with_length}{checksum_value}\r\n"

    return finalized_string

entradas_mapping = {
    "Nenhuma": "00",
    "Ignição": "02",
    "Pânico": "01",
    "Ignição+Pânico": "03"
}

bloqueio_mapping = {
    "Desbloqueado": "00",
    "Bloqueado": "01"
}

motor_mapping = {
    "Desligado": "0",
    "Ligado": "2"
}

gpio_mapping = {
    "OFF": "0",
    "ON": "1"
}

tpms_alarm_mapping = {
    "Nenhum": "0",
    "Pressão": "1",
    "Temperatura": "2",
    "Bateria": "4",
    "Pressão + Temperatura": "3",
    "Pressão + Bateria": "5",
    "Temperatura + Bateria": "6",
    "Temperatura + Pressão + Bateria": "7"
}

def apply_settings():
    global send_interval, send_data
    # Fetch values from the UI components and set send_interval
    imei = imei_entry.get()
    alarme = alarm_var.get()
    sat = sat_entry.get()
    hdop = hdop_entry.get()
    vel = vel_entry.get()
    odo = odo_entry.get()
    entradas = entradas_mapping[entradas_var.get()]
    saidas = bloqueio_mapping[bloqueio_var.get()]
    motor = motor_mapping[motor_var.get()]
    in5 = gpio_mapping[in5_var.get()]
    in6 = gpio_mapping[in6_var.get()]
    in7 = gpio_mapping[in7_var.get()]
    in8 = gpio_mapping[in8_var.get()]
    in9 = gpio_mapping[in9_var.get()]
    in10 = gpio_mapping[in10_var.get()]
    out2 = gpio_mapping[out2_var.get()]
    out3 = gpio_mapping[out3_var.get()]
    out4 = gpio_mapping[out4_var.get()]
    out5 = gpio_mapping[out5_var.get()]
    driver = driver_entry.get()
    activity = activity_entry.get()
    tpms_sensor = tpms_sensor_entry.get()
    tpms_alarme = tpms_alarm_mapping[tpms_alarm_var.get()]
    tpms_pressure = tpms_pressure_entry.get()
    tpms_temperature = tpms_temperature_entry.get()
    tanque = tanque_entry.get()
    can_vel = can_vel_entry.get()
    rpm = rpm_entry.get()
    temp = temp_entry.get()
    turbo = turbo_entry.get()
    lat = lat_entry.get()
    long = long_entry.get()
    send_interval = int(intervalo_var.get())

    # Now generate the GPS string with the current settings without immediately scheduling
    send_data = calculate_gps_string(imei, alarme, sat, hdop, vel, odo, entradas, saidas, motor, tanque,
                                     can_vel, rpm, temp, turbo, lat, long, in5, in6, in7, in8, in9, in10,
                                     out2, out3, out4, out5, time_offset, driver, activity, tpms_sensor,
                                     tpms_alarme, tpms_pressure, tpms_temperature)

def load_server_values():
    config = CaseSensitiveConfigParser()
    # Open the ini file with UTF-8 encoding
    config_path = os.path.join(application_path, 'config_simulador.ini')
    with open(config_path, 'r', encoding='utf-8') as configfile:
        config.read_file(configfile)
    servers = config['servers']
    return {key: value for key, value in servers.items()}

# In your main program, load the server values and use them to populate the combobox
server_values = load_server_values()
# The keys are the user-friendly names, and the values are "address:port"
server_names = list(server_values.keys())

def toggle_connection():
    global telnet_connection, listener_thread, connection_monitor_active, connection_monitor_task
    
    if telnet_connection is None:  # Attempt to connect
        selected_server = server_var.get()
        server_address, server_port = server_values[selected_server].split(':')
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        
        append_to_log(f"{timestamp} [CONNECT] Initiating connection to '{selected_server}' ({server_address}:{server_port})")
        
        try:
            # Create telnet connection
            telnet_connection = telnetlib.Telnet()
            # Note: debuglevel removed as it can clutter the log
            
            # Log connection attempt details
            append_to_log(f"{timestamp} [CONNECT] Opening TCP socket to {server_address}:{server_port}")
            
            # Connect with timeout
            telnet_connection.open(server_address, int(server_port), timeout=3)
            
            # Get socket details after connection
            sock = telnet_connection.get_socket()
            local_addr = sock.getsockname()
            remote_addr = sock.getpeername()
            
            # IMPORTANT: Do NOT enable keepalive - we want to test if gateway closes idle connections
            # sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 0)  # Explicitly disabled
            
            timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            append_to_log(f"{timestamp} [CONNECT-SUCCESS] TCP connection established")
            append_to_log(f"{timestamp} [SOCKET-INFO] Local endpoint: {local_addr}")
            append_to_log(f"{timestamp} [SOCKET-INFO] Remote endpoint: {remote_addr}")
            append_to_log(f"{timestamp} [SOCKET-INFO] Socket timeout: {sock.gettimeout()}")
            append_to_log(f"{timestamp} [SOCKET-INFO] TCP Keep-alive: DISABLED (testing idle connection behavior)")
            
            # Start the listener thread
            listener_thread = threading.Thread(target=listen_for_server_messages, daemon=True)
            listener_thread.start()
            append_to_log(f"{timestamp} [CONNECT] Message listener thread started")
            
            # No connection monitoring - we want passive observation only
            append_to_log(f"{timestamp} [CONNECT] Socket is idle - no active monitoring (passive mode)")
            
            connect_button.config(text="DESCONECTAR", bg='green', fg='white')
            
        except socket.timeout:
            timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            append_to_log(f"{timestamp} [CONNECT-FAIL] Connection timeout after 3 seconds")
        except socket.gaierror as e:
            timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            append_to_log(f"{timestamp} [CONNECT-FAIL] DNS resolution failed: {e}")
        except ConnectionRefusedError:
            timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            append_to_log(f"{timestamp} [CONNECT-FAIL] Connection refused by server (port might be closed)")
        except OSError as e:
            timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            # Windows-specific error codes
            WSAEHOSTUNREACH = 10065
            WSAENETUNREACH = 10051
            
            if hasattr(e, 'winerror'):
                if e.winerror == WSAEHOSTUNREACH:
                    append_to_log(f"{timestamp} [CONNECT-FAIL] Host unreachable")
                elif e.winerror == WSAENETUNREACH:
                    append_to_log(f"{timestamp} [CONNECT-FAIL] Network unreachable")
                else:
                    append_to_log(f"{timestamp} [CONNECT-FAIL] OS error: {e}")
            elif hasattr(errno, 'EHOSTUNREACH') and e.errno == errno.EHOSTUNREACH:
                append_to_log(f"{timestamp} [CONNECT-FAIL] Host unreachable")
            elif hasattr(errno, 'ENETUNREACH') and e.errno == errno.ENETUNREACH:
                append_to_log(f"{timestamp} [CONNECT-FAIL] Network unreachable")
            else:
                append_to_log(f"{timestamp} [CONNECT-FAIL] OS error: {e}")
        except Exception as e:
            timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            append_to_log(f"{timestamp} [CONNECT-FAIL] Unexpected error: {e}")
            
    else:  # Disconnect if already connected
        selected_server = server_var.get()
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        
        # No monitoring to stop in passive mode
        
        try:
            # Get final socket state before closing
            sock = telnet_connection.get_socket()
            local_addr = sock.getsockname()
            remote_addr = sock.getpeername()
            
            append_to_log(f"{timestamp} [DISCONNECT] Closing connection from {local_addr} to {remote_addr}")
            
            # Close the connection
            telnet_connection.close()
            
            append_to_log(f"{timestamp} [DISCONNECT] TCP connection closed successfully")
            
        except Exception as e:
            append_to_log(f"{timestamp} [DISCONNECT-ERROR] Error during disconnect: {e}")
        
        telnet_connection = None
        listener_thread = None
        
        append_to_log(f"{timestamp} [DISCONNECT] Cleanup completed - disconnected from '{selected_server}'")
        connect_button.config(text="CONECTAR", bg='SystemButtonFace', fg='black')

def toggle_sending():
    global sending_active, send_task, telnet_connection
    # Check if the telnet connection is open before proceeding
    if telnet_connection is None:
        append_to_log("Não conectado ao servidor. Por favor, conecte-se primeiro.")
        messagebox.showerror("Erro de conexão", "Não conectado ao servidor. Por favor, conecte-se primeiro.")
        return  # Exit the function to prevent toggling the button and starting the sending process
    if not sending_active:
        sending_active = True
        send_toggle_button["text"] = "PARAR ENVIO TEMPORIZADO"
        send_toggle_button.config(bg='green', fg='white')
        # Start sending with the currently selected interval
        schedule_sending()
    else:
        sending_active = False
        send_toggle_button["text"] = "INICIAR ENVIO TEMPORIZADO"
        send_toggle_button.config(bg='SystemButtonFace', fg='black')
        stop_sending()  # This will cancel the current send task

# Create the main window
root = tk.Tk()
root.title("SETERA - Simulador STR1010 Plus V1.0")
root.state('zoomed')
root.iconbitmap(os.path.join(application_path, 'favicon.ico'))

# Create the top frame for server connection
top_upper_frame = tk.Frame(root)
top_upper_frame.pack(fill=tk.X)

# Server Combobox setup with new server_values
server_label = tk.Label(top_upper_frame, text="Servidor:")
server_label.pack(side=tk.LEFT, padx=5, pady=5)

server_var = tk.StringVar()
server_combobox = ttk.Combobox(top_upper_frame, textvariable=server_var, state="readonly", width=15, values=server_names)
server_combobox.current(0)  # Default to the first server in the list
server_combobox.pack(side=tk.LEFT, padx=1, pady=5)

connect_button = tk.Button(top_upper_frame, text="CONECTAR", command=toggle_connection)
connect_button.pack(side=tk.LEFT, padx=20, pady=5)

send_toggle_button = tk.Button(top_upper_frame, text="INICIAR ENVIO TEMPORIZADO", command=toggle_sending)
send_toggle_button.pack(side=tk.LEFT, padx=20, pady=5)

send_one_button = tk.Button(top_upper_frame, text="ENVIAR UMA POSIÇÃO", command=send_single_position)
send_one_button.pack(side=tk.LEFT, padx=20, pady=5)

# Function to clear the log text widget
def clear_log():
    log_text.config(state='normal')  # Enable editing to clear the widget
    log_text.delete('1.0', tk.END)  # Clear all content
    log_text.config(state='disabled')  # Disable editing again

clear_log_button = tk.Button(top_upper_frame, text="LIMPAR LOG", command=clear_log)
clear_log_button.pack(side=tk.LEFT, padx=20, pady=5)

separator = ttk.Separator(root, orient='horizontal')
separator.pack(fill='x', padx=5, pady=1)

# Create the second top frame for tracker settings
top_lower_frame = tk.Frame(root)
top_lower_frame.pack(fill=tk.X)

# IMEI
imei_label = tk.Label(top_lower_frame, text="IMEI:")
imei_label.pack(side=tk.LEFT, padx=1, pady=5)
imei_entry = tk.Entry(top_lower_frame, width=16)
imei_entry.insert(0, "869731052487220")  # Default value
imei_entry.pack(side=tk.LEFT, padx=5, pady=5)

# Alarme
# Load alarms and sort keys alphabetically, ensuring "Nenhum" is at the start
alarm_values = load_alarm_values()
# Sort alarm keys alphabetically, but place "Nenhum" first
alarm_keys_sorted = sorted(alarm_values.keys(), key=lambda x: (x != "Nenhum", x))
alarm_label = tk.Label(top_lower_frame, text="Alarme:")
alarm_label.pack(side=tk.LEFT, padx=5, pady=5)
alarm_var = tk.StringVar()
alarm_combobox = ttk.Combobox(top_lower_frame, textvariable=alarm_var, state="readonly", width=22, values=alarm_keys_sorted)
alarm_combobox.set("Nenhum")  # Set to default value "Nenhum"
alarm_combobox.pack(side=tk.LEFT, padx=5, pady=5)

# Sat
sat_label = tk.Label(top_lower_frame, text="Sat:")
sat_label.pack(side=tk.LEFT, padx=5, pady=5)
sat_entry = tk.Entry(top_lower_frame, width=3)
sat_entry.insert(0, "15")  # Default value
sat_entry.pack(side=tk.LEFT, padx=5, pady=5)

# HDOP
hdop_label = tk.Label(top_lower_frame, text="HDOP:")
hdop_label.pack(side=tk.LEFT, padx=5, pady=5)
hdop_entry = tk.Entry(top_lower_frame, width=3)
hdop_entry.insert(0, "0.8")  # Default value
hdop_entry.pack(side=tk.LEFT, padx=5, pady=5)

# Vel(Km/h)
vel_label = tk.Label(top_lower_frame, text="Vel GPS:")
vel_label.pack(side=tk.LEFT, padx=5, pady=5)
vel_entry = tk.Entry(top_lower_frame, width=3)
vel_entry.insert(0, "55")  # Default value
vel_entry.pack(side=tk.LEFT, padx=5, pady=5)

# Odo(Km)
odo_label = tk.Label(top_lower_frame, text="Odo(m):")
odo_label.pack(side=tk.LEFT, padx=5, pady=5)
odo_entry = tk.Entry(top_lower_frame, width=7)
odo_entry.insert(0, "58952")  # Default value
odo_entry.pack(side=tk.LEFT, padx=5, pady=5)

# Entradas Combobox
entradas_label = tk.Label(top_lower_frame, text="Entradas:")
entradas_label.pack(side=tk.LEFT, padx=5, pady=5)
entradas_var = tk.StringVar()
entradas_combobox = ttk.Combobox(top_lower_frame, textvariable=entradas_var, state="readonly", width=15)
entradas_combobox['values'] = ("Nenhuma", "Ignição", "Pânico", "Ignição+Pânico")
entradas_combobox.current(0)  # Default option "Nenhuma"
entradas_combobox.pack(side=tk.LEFT, padx=5, pady=5)

# Bloqueio Combobox
bloqueio_label = tk.Label(top_lower_frame, text="Bloqueio:")
bloqueio_label.pack(side=tk.LEFT, padx=5, pady=5)
bloqueio_var = tk.StringVar()
bloqueio_combobox = ttk.Combobox(top_lower_frame, textvariable=bloqueio_var, state="readonly", width=13)
bloqueio_combobox['values'] = ("Desbloqueado", "Bloqueado")
bloqueio_combobox.current(0)  # Default option "Desbloqueado"
bloqueio_combobox.pack(side=tk.LEFT, padx=5, pady=5)

# Intervalo(seg) Combobox
intervalo_label = tk.Label(top_lower_frame, text="Intervalo de envio(seg):")
intervalo_label.pack(side=tk.LEFT, padx=5, pady=5)
intervalo_var = tk.StringVar()
intervalo_combobox = ttk.Combobox(top_lower_frame, textvariable=intervalo_var, state="readonly", width=3)
intervalo_combobox['values'] = (1, 5, 10, 30, 45, 60)
intervalo_combobox.current(2)  # Default option "10sec"
intervalo_combobox.pack(side=tk.LEFT, padx=5, pady=5)

separator1 = ttk.Separator(root, orient='horizontal')
separator1.pack(fill='x', padx=5, pady=1)

# Create the second top frame for tracker settings
lower_frame = tk.Frame(root)
lower_frame.pack(fill=tk.X)

# Motor Combobox
motor_label = tk.Label(lower_frame, text="Motor:")
motor_label.pack(side=tk.LEFT, padx=1, pady=5)
motor_var = tk.StringVar()
motor_combobox = ttk.Combobox(lower_frame, textvariable=motor_var, state="readonly", width=10)
motor_combobox['values'] = ("Desligado", "Ligado")
motor_combobox.current(0)  # Default option "Desligado"
motor_combobox.pack(side=tk.LEFT, padx=5, pady=5)

# Tank level
tanque_label = tk.Label(lower_frame, text="Tanque:")
tanque_label.pack(side=tk.LEFT, padx=1, pady=5)
tanque_entry = tk.Entry(lower_frame, width=4)
tanque_entry.insert(0, "95")  # Default value
tanque_entry.pack(side=tk.LEFT, padx=5, pady=5)

# Vel CAN
can_vel_label = tk.Label(lower_frame, text="Vel CAN:")
can_vel_label.pack(side=tk.LEFT, padx=1, pady=5)
can_vel_entry = tk.Entry(lower_frame, width=3)
can_vel_entry.insert(0, "55")  # Default value
can_vel_entry.pack(side=tk.LEFT, padx=5, pady=5)

# RPM
rpm_label = tk.Label(lower_frame, text="RPM:")
rpm_label.pack(side=tk.LEFT, padx=1, pady=5)
rpm_entry = tk.Entry(lower_frame, width=5)
rpm_entry.insert(0, "1115")  # Default value
rpm_entry.pack(side=tk.LEFT, padx=5, pady=5)

# Temp
temp_label = tk.Label(lower_frame, text="Temp Motor:")
temp_label.pack(side=tk.LEFT, padx=1, pady=5)
temp_entry = tk.Entry(lower_frame, width=3)
temp_entry.insert(0, "85")  # Default value
temp_entry.pack(side=tk.LEFT, padx=5, pady=5)

# Turbo
turbo_label = tk.Label(lower_frame, text="Pressão Turbo:")
turbo_label.pack(side=tk.LEFT, padx=1, pady=5)
turbo_entry = tk.Entry(lower_frame, width=3)
turbo_entry.insert(0, "65")  # Default value
turbo_entry.pack(side=tk.LEFT, padx=5, pady=5)

# Latitude
lat_label = tk.Label(lower_frame, text="Latitude:")
lat_label.pack(side=tk.LEFT, padx=1, pady=5)
lat_entry = tk.Entry(lower_frame, width=12)
lat_entry.insert(0, "-19.892976")  # Default value
lat_entry.pack(side=tk.LEFT, padx=5, pady=5)

# Longitude
long_label = tk.Label(lower_frame, text="Longitude:")
long_label.pack(side=tk.LEFT, padx=1, pady=5)
long_entry = tk.Entry(lower_frame, width=12)
long_entry.insert(0, "-44.072225")  # Default value
long_entry.pack(side=tk.LEFT, padx=5, pady=5)

# Function to perform search and center map on result
search_label = tk.Label(lower_frame, text="Busca mapa:")
search_label.pack(side=tk.LEFT, padx=5, pady=5)

search_entry = tk.Entry(lower_frame, width=25)
search_entry.pack(side=tk.LEFT, padx=5, pady=5)

def reset_map():
    map_widget.set_position(-19.892976, -44.072225)  # Set initial center
    map_widget.set_zoom(15)  # Set initial zoom level

reset_map_button = tk.Button(lower_frame, text="RESET MAPA", command=reset_map)
reset_map_button.pack(side=tk.LEFT, padx=10, pady=5)

separator2 = ttk.Separator(root, orient='horizontal')
separator2.pack(fill='x', padx=5, pady=1)

# Create the second top frame for tracker settings
bottom_lower_frame = tk.Frame(root)
bottom_lower_frame.pack(fill=tk.X)

# Tempo Banguela
banguela_label = tk.Label(bottom_lower_frame, text="Tempo total em banguela(seg):")
banguela_label.pack(side=tk.LEFT, padx=(1, 0), pady=5)
banguela_entry = tk.Entry(bottom_lower_frame, width=4)
banguela_entry.insert(0, "0")  # Default value
banguela_entry.pack(side=tk.LEFT, padx=(0, 5), pady=5)

# IN5 Combobox
in5_label = tk.Label(bottom_lower_frame, text="IN5:")
in5_label.pack(side=tk.LEFT, pady=5)
in5_var = tk.StringVar(value="OFF")
in5_combobox = ttk.Combobox(bottom_lower_frame, textvariable=in5_var, state="readonly", width=4)
in5_combobox['values'] = ("OFF", "ON")
in5_combobox.pack(side=tk.LEFT, padx=(0, 5), pady=5)

# IN6 Combobox
in6_label = tk.Label(bottom_lower_frame, text="IN6:")
in6_label.pack(side=tk.LEFT, pady=5)
in6_var = tk.StringVar(value="OFF")
in6_combobox = ttk.Combobox(bottom_lower_frame, textvariable=in6_var, state="readonly", width=4)
in6_combobox['values'] = ("OFF", "ON")
in6_combobox.pack(side=tk.LEFT, padx=(0, 5), pady=5)

# IN7 Combobox
in7_label = tk.Label(bottom_lower_frame, text="IN7:")
in7_label.pack(side=tk.LEFT, pady=5)
in7_var = tk.StringVar(value="OFF")
in7_combobox = ttk.Combobox(bottom_lower_frame, textvariable=in7_var, state="readonly", width=4)
in7_combobox['values'] = ("OFF", "ON")
in7_combobox.pack(side=tk.LEFT, padx=(0, 5), pady=5)

# IN8 Combobox
in8_label = tk.Label(bottom_lower_frame, text="IN8:")
in8_label.pack(side=tk.LEFT, pady=5)
in8_var = tk.StringVar(value="OFF")
in8_combobox = ttk.Combobox(bottom_lower_frame, textvariable=in8_var, state="readonly", width=4)
in8_combobox['values'] = ("OFF", "ON")
in8_combobox.pack(side=tk.LEFT, padx=(0, 5), pady=5)

# IN9 Combobox
in9_label = tk.Label(bottom_lower_frame, text="IN9:")
in9_label.pack(side=tk.LEFT, pady=5)
in9_var = tk.StringVar(value="OFF")
in9_combobox = ttk.Combobox(bottom_lower_frame, textvariable=in9_var, state="readonly", width=4)
in9_combobox['values'] = ("OFF", "ON")
in9_combobox.pack(side=tk.LEFT, padx=(0, 5), pady=5)

# IN10 Combobox
in10_label = tk.Label(bottom_lower_frame, text="IN10:")
in10_label.pack(side=tk.LEFT, pady=5)
in10_var = tk.StringVar(value="OFF")
in10_combobox = ttk.Combobox(bottom_lower_frame, textvariable=in10_var, state="readonly", width=4)
in10_combobox['values'] = ("OFF", "ON")
in10_combobox.pack(side=tk.LEFT, padx=(0, 5), pady=5)

# OUT2 Combobox
out2_label = tk.Label(bottom_lower_frame, text="OUT2:")
out2_label.pack(side=tk.LEFT, pady=5)
out2_var = tk.StringVar(value="OFF")
out2_combobox = ttk.Combobox(bottom_lower_frame, textvariable=out2_var, state="readonly", width=4)
out2_combobox['values'] = ("OFF", "ON")
out2_combobox.pack(side=tk.LEFT, padx=(0, 5), pady=5)

# OUT3 Combobox
out3_label = tk.Label(bottom_lower_frame, text="OUT3:")
out3_label.pack(side=tk.LEFT, pady=5)
out3_var = tk.StringVar(value="OFF")
out3_combobox = ttk.Combobox(bottom_lower_frame, textvariable=out3_var, state="readonly", width=4)
out3_combobox['values'] = ("OFF", "ON")
out3_combobox.pack(side=tk.LEFT, padx=(0, 5), pady=5)

# OUT4 Combobox
out4_label = tk.Label(bottom_lower_frame, text="OUT4:")
out4_label.pack(side=tk.LEFT, pady=5)
out4_var = tk.StringVar(value="OFF")
out4_combobox = ttk.Combobox(bottom_lower_frame, textvariable=out4_var, state="readonly", width=4)
out4_combobox['values'] = ("OFF", "ON")
out4_combobox.pack(side=tk.LEFT, padx=(0, 5), pady=5)

# OUT5 Combobox
out5_label = tk.Label(bottom_lower_frame, text="OUT5:")
out5_label.pack(side=tk.LEFT, pady=5)
out5_var = tk.StringVar(value="OFF")
out5_combobox = ttk.Combobox(bottom_lower_frame, textvariable=out5_var, state="readonly", width=4)
out5_combobox['values'] = ("OFF", "ON")
out5_combobox.pack(side=tk.LEFT, padx=(0, 5), pady=5)

# Motorista
driver_label = tk.Label(bottom_lower_frame, text="Motorista:")
driver_label.pack(side=tk.LEFT, padx=(1, 0), pady=5)
driver_entry = tk.Entry(bottom_lower_frame, width=12)
driver_entry.insert(0, "05158015775")  # Default value
driver_entry.pack(side=tk.LEFT, padx=(0, 5), pady=5)

# Atividade
activity_label = tk.Label(bottom_lower_frame, text="Atividade:")
activity_label.pack(side=tk.LEFT, padx=(1, 0), pady=5)
activity_entry = tk.Entry(bottom_lower_frame, width=3)
activity_entry.insert(0, "12")  # Default value
activity_entry.pack(side=tk.LEFT, padx=(0, 5), pady=5)

separator3 = ttk.Separator(root, orient='horizontal')
separator3.pack(fill='x', padx=5, pady=1)

# Create the second top frame for tracker settings
bottom_frame = tk.Frame(root)
bottom_frame.pack(fill=tk.X)

# Sensor TPMS
tpms_sensor_label = tk.Label(bottom_frame, text="Códido do Sensor:")
tpms_sensor_label.pack(side=tk.LEFT, padx=(1, 0), pady=5)
tpms_sensor_entry = tk.Entry(bottom_frame, width=15)
tpms_sensor_entry.insert(0, "000F007F00CA")  # Default value
tpms_sensor_entry.pack(side=tk.LEFT, padx=(0, 10), pady=5)

# Alarme TPMS
tpms_alarm_label = tk.Label(bottom_frame, text="Alarmes TPMS:")
tpms_alarm_label.pack(side=tk.LEFT, pady=5)
tpms_alarm_var = tk.StringVar(value="Nenhum")
tpms_alarm_combobox = ttk.Combobox(bottom_frame, textvariable=tpms_alarm_var, state="readonly", width=22)
tpms_alarm_combobox['values'] = ("Nenhum", "Pressão", "Temperatura", "Bateria", "Pressão + Temperatura", "Pressão + Bateria", "Temperatura + Bateria", "Temperatura + Pressão + Bateria")
tpms_alarm_combobox.pack(side=tk.LEFT, padx=(0, 10), pady=5)

# Pressão TPMS
tpms_pressure_label = tk.Label(bottom_frame, text="Pressão(PSI):")
tpms_pressure_label.pack(side=tk.LEFT, padx=(1, 0), pady=5)
tpms_pressure_entry = tk.Entry(bottom_frame, width=5)
tpms_pressure_entry.insert(0, "122")  # Default value
tpms_pressure_entry.pack(side=tk.LEFT, padx=(0, 10), pady=5)

# Temperatura TPMS
tpms_temperature_label = tk.Label(bottom_frame, text="Temperatura(°C):")
tpms_temperature_label.pack(side=tk.LEFT, padx=(1, 0), pady=5)
tpms_temperature_entry = tk.Entry(bottom_frame, width=5)
tpms_temperature_entry.insert(0, "39")  # Default value
tpms_temperature_entry.pack(side=tk.LEFT, padx=(0, 10), pady=5)

separator4 = ttk.Separator(root, orient='horizontal')
separator4.pack(fill='x', padx=5, pady=1)

def search_location(event=None):
    search_query = search_entry.get().strip()
    if not search_query:
        return  # Exit if query is empty

    map_widget.set_address(search_query)
    map_widget.set_zoom(15)

search_entry.bind("<Return>", search_location)

# Global variable to keep track of the marker count
marker_count = 0

def add_marker_event(coords):
    global marker_count
    # Increment the marker count
    marker_count += 1
    marker_name = f"Marcador {marker_count}"
    # Append the marker name and coordinates to the log
    append_to_log(f"{marker_name} adicionado: {coords}")
    # Set the marker with the incremented name
    map_widget.set_marker(coords[0], coords[1], text=marker_name)

# Create the map widget with initial position and zoom
map_widget = tkintermapview.TkinterMapView(root, width=1920, height=400, corner_radius=0)
map_widget.set_tile_server("https://mt0.google.com/vt/lyrs=m&hl=en&x={x}&y={y}&z={z}&s=Ga", max_zoom=22)
map_widget.pack(expand=True, fill=tk.BOTH)
map_widget.set_position(-19.892976, -44.072225)  # Set initial center
map_widget.set_zoom(15)  # Set initial zoom level
map_widget.add_right_click_menu_command(label="Aicionar marcador", command=add_marker_event, pass_coords=True)

# Updated map click event handling to use the provided add_left_click_map_command
def on_map_click(coordinates_tuple):
    lat, lon = coordinates_tuple
    # Round the coordinates to 6 decimal places
    lat = round(lat, 6)
    lon = round(lon, 6)
    # Update the latitude and longitude entry fields
    lat_entry.delete(0, tk.END)
    lat_entry.insert(0, str(lat))
    long_entry.delete(0, tk.END)
    long_entry.insert(0, str(lon))

# Assign the callback function for a left click event on the map
map_widget.add_left_click_map_command(on_map_click)

# Add a separator before the text log area
separator3 = ttk.Separator(root, orient='horizontal')
separator3.pack(fill='x', padx=5, pady=1)

# Create the text log area
log_text = tk.Text(root, height=10, bg='black', fg='white')
log_text.pack(fill=tk.X, padx=5, pady=5)  # Only expand horizontally
log_text.config(state='disabled')  # Disable editing of the log text

root.mainloop()