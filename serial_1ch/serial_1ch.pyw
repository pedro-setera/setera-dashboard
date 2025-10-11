import os
import threading
import tkinter as tk
from tkinter import ttk
from tkinter import filedialog
from datetime import datetime
import time
import serial
from serial.tools import list_ports

# Dynamic path finding for support files
application_path = os.path.dirname(os.path.abspath(__file__))

# Function to list available COM ports
def get_com_ports():
    return [port.device for port in list_ports.comports()]

# Function to load commands from INI file
def load_commands():
    commands = []
    commands_file = os.path.join(application_path, 'commands.ini')
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
            print(f"Error loading commands: {e}")
    return commands

# Function for autocomplete and capitalization
def on_combobox_key_release(event, send_text_var, send_text_combobox, commands):
    current_text = send_text_var.get()
    cursor_position = send_text_combobox.index(tk.INSERT)
    capitalized_text = current_text.upper()

    if capitalized_text != current_text:
        send_text_var.set(capitalized_text)
        send_text_combobox.icursor(cursor_position)

    if current_text:
        filtered = [cmd for cmd in commands if current_text.upper() in cmd.upper() and not cmd.startswith('---')]
        if filtered:
            send_text_combobox['values'] = filtered
        else:
            send_text_combobox['values'] = commands
    else:
        send_text_combobox['values'] = commands

# Function to send data
def send_data(ser, send_text_var, crlf_var, hex_mode, debug_log):
    if not ser or not ser.is_open:
        add_timestamp(debug_log, "Erro: Primeiro conecte à porta serial.")
        return

    data = send_text_var.get()
    if not data:
        add_timestamp(debug_log, "Erro: Não há texto para envio.")
        return

    try:
        if hex_mode[0]:
            try:
                data_bytes = bytes.fromhex(data.replace(' ', ''))
            except ValueError:
                add_timestamp(debug_log, "Erro: Formato HEX inválido.")
                return
        else:
            data_bytes = data.encode('utf-8')

        if crlf_var.get():
            data_bytes += b'\r\n'

        ser.write(data_bytes)
        timestamp = datetime.now().strftime('%d/%m/%Y - %H:%M:%S.%f')[:-3]
        debug_log.configure(state='normal')
        debug_log.insert('end', f"{timestamp} TX: ", 'sent')
        if hex_mode[0]:
            debug_log.insert('end', ' '.join([f"{b:02X}" for b in data_bytes]) + '\n')
        else:
            debug_log.insert('end', data_bytes.decode("utf-8", "ignore") + '\n')
        debug_log.see('end')
        debug_log.configure(state='disabled')
        debug_log.tag_configure('sent', foreground='red', font=('Arial', 10, 'bold'))
    except Exception as e:
        add_timestamp(debug_log, f"Erro ao enviar dados: {str(e)}")

# Function to send data every 1 second
def send_data_every_1s(ser, send_text_var, crlf_var, hex_mode, debug_log, send_every_1s_var, run_flag):
    while send_every_1s_var.get() and run_flag[0]:
        send_data(ser, send_text_var, crlf_var, hex_mode, debug_log)
        time.sleep(1)

# Function to toggle send every 1s
def toggle_send_every_1s(ser, send_text_var, crlf_var, hex_mode, debug_log, send_every_1s_var, run_flag):
    if send_every_1s_var.get():
        if not ser or not ser.is_open:
            add_timestamp(debug_log, "Erro: Primeiro conecte à porta serial.")
            send_every_1s_var.set(False)
            return
        if not send_text_var.get():
            add_timestamp(debug_log, "Erro: Não há texto para envio.")
            send_every_1s_var.set(False)
            return
        threading.Thread(target=send_data_every_1s, args=(ser, send_text_var, crlf_var, hex_mode, debug_log, send_every_1s_var, run_flag), daemon=True).start()

# Function to add timestamp in blue color and avoid double newlines
def add_timestamp(text_widget, text):
    # Strip any newline characters from the end of the text
    text = text.rstrip('\n\r')
    
    timestamp = datetime.now().strftime('%d/%m/%Y - %H:%M:%S.%f')[:-3]
    text_widget.configure(state='normal')
    text_widget.insert('end', f"{timestamp} = ", 'timestamp')
    text_widget.insert('end', f"{text}\n")  # Add a single newline after processing
    text_widget.see('end')  # Auto-scroll to the bottom
    text_widget.configure(state='disabled')
    text_widget.tag_configure('timestamp', foreground='blue', font=('Arial', 10, 'bold'))

# Function to clear the debug log area
def clear_fields(debug_log):
    debug_log.configure(state='normal')
    debug_log.delete('1.0', tk.END)
    debug_log.configure(state='disabled')

# Function to save log
def save_log(debug_log):
    filename = f'serial_log_{datetime.now().strftime("%d-%m-%Y_%H%M%S")}.txt'
    with open(os.path.join(application_path, filename), 'w') as file:
        log_content = debug_log.get('1.0', tk.END)
        file.write(log_content)
    print(f"Log saved as {filename}")

# Thread function for reading serial data
def read_serial_data(ser, debug_log, filter_entry, run_flag, hex_mode):
    buffer = ''  # Initialize a buffer to accumulate incoming data
    last_received_time = datetime.now()
    
    while run_flag[0]:
        if ser.in_waiting:
            data = ser.read(ser.in_waiting)
            if hex_mode[0]:
                data = ' '.join(f'{byte:02X}' for byte in data)
            else:
                data = data.decode('utf-8')
            buffer += data  # Add data to the buffer
            last_received_time = datetime.now()
        else:
            # Check if the buffer has been stagnant for more than 50ms
            if (datetime.now() - last_received_time).total_seconds() > 0.002 and buffer:
                # Process buffer here as a complete line
                if filter_entry.get().lower() in buffer.lower():
                    add_timestamp(debug_log, buffer)
                buffer = ''  # Reset the buffer for new data
            threading.Event().wait(0.001)  # Short wait to reduce CPU load

# Toggle connect/disconnect
def toggle_connection(port_combobox, baudrate_combobox, connect_button, debug_log, filter_entry, run_flag, hex_mode, ser_ref, send_every_1s_var):
    if connect_button['text'] == "CONECTAR":
        try:
            ser_ref[0] = serial.Serial(port_combobox.get(), baudrate_combobox.get(), timeout=0)
            add_timestamp(debug_log, "Conectado na porta serial")
            connect_button.config(text="DESCONECTAR", bg='SystemButtonFace')
            run_flag[0] = True
            threading.Thread(target=read_serial_data, args=(ser_ref[0], debug_log, filter_entry, run_flag, hex_mode), daemon=True).start()
        except:
            add_timestamp(debug_log, "Erro ao conectar porta serial.")
    else:
        run_flag[0] = False
        send_every_1s_var.set(False)
        if ser_ref[0]:
            try:
                ser_ref[0].close()
            except:
                pass
            ser_ref[0] = None
        add_timestamp(debug_log, "Desconectado da porta serial")
        connect_button.config(text="CONECTAR", bg='green')

# Toggle HEX/ASCII mode
def toggle_hex_mode(hex_button, hex_mode):
    if hex_mode[0]:
        hex_mode[0] = False
        hex_button.config(text="HEX", bg='SystemButtonFace')
    else:
        hex_mode[0] = True
        hex_button.config(text="ASCII", bg='yellow')

# Main GUI setup
def setup_gui():
    root = tk.Tk()
    root.title("SETERA - Coletor Serial 1 Canal")
    root.state('zoomed')
    root.iconbitmap(os.path.join(application_path, 'favicon.ico'))

    # Top Frame Design
    top_frame = tk.Frame(root, pady=7)
    top_frame.pack(fill='x')

    tk.Label(top_frame, text="COM:").pack(side='left', padx=(10, 0))
    port_combobox = ttk.Combobox(top_frame, width=10, values=get_com_ports())
    port_combobox.pack(side='left', padx=(0, 20))
    port_combobox.set(port_combobox['values'][0] if port_combobox['values'] else "")

    tk.Label(top_frame, text="Baudrate:").pack(side='left', padx=(5, 0))
    baudrate_combobox = ttk.Combobox(top_frame, width=10, values=["115200", "9600"])
    baudrate_combobox.pack(side='left', padx=(0, 20))
    baudrate_combobox.set("115200")

    run_flag = [False]  # Flag to control the execution of the thread
    hex_mode = [False]  # Flag to control HEX/ASCII mode
    ser_ref = [None]  # Reference to serial connection
    send_text_var = tk.StringVar()
    crlf_var = tk.BooleanVar()
    send_every_1s_var = tk.BooleanVar()
    commands = load_commands()

    connect_button = tk.Button(top_frame, text="CONECTAR", bg='green', command=lambda: toggle_connection(port_combobox, baudrate_combobox, connect_button, debug_log, filter_entry, run_flag, hex_mode, ser_ref, send_every_1s_var))
    connect_button.pack(side='left', padx=20)

    clear_button = tk.Button(top_frame, text="LIMPAR", bg='yellow', command=lambda: clear_fields(debug_log))
    clear_button.pack(side='left', padx=20)

    save_button = tk.Button(top_frame, text="SALVAR LOG", command=lambda: save_log(debug_log))
    save_button.pack(side='left', padx=20)

    hex_button = tk.Button(top_frame, text="HEX", command=lambda: toggle_hex_mode(hex_button, hex_mode))
    hex_button.pack(side='left', padx=20)

    # Middle Frame Design
    middle_frame = tk.Frame(root)
    middle_frame.pack(fill='x', pady=(0, 7))
    tk.Label(middle_frame, text="Filtro:").pack(side='left', padx=(10, 5))
    filter_entry = tk.Entry(middle_frame, width=50)
    filter_entry.pack(side='left', padx=(0, 10))

    # Send Frame Design
    send_frame = tk.Frame(root)
    send_frame.pack(fill='x', pady=(0, 7))
    tk.Label(send_frame, text="Envio:").pack(side='left', padx=(10, 5))
    send_text_combobox = ttk.Combobox(send_frame, textvariable=send_text_var, values=commands, height=20, width=50)
    send_text_combobox.pack(side='left', padx=(0, 10))
    send_text_combobox.bind('<KeyRelease>', lambda e: on_combobox_key_release(e, send_text_var, send_text_combobox, commands))

    send_button = tk.Button(send_frame, text="ENVIAR", command=lambda: threading.Thread(target=send_data, args=(ser_ref[0], send_text_var, crlf_var, hex_mode, debug_log), daemon=True).start())
    send_button.pack(side='left', padx=(0, 10))

    crlf_checkbutton = ttk.Checkbutton(send_frame, text="CRLF", variable=crlf_var)
    crlf_checkbutton.pack(side='left', padx=(0, 10))

    send_every_1s_checkbutton = ttk.Checkbutton(send_frame, text="1s", variable=send_every_1s_var, command=lambda: toggle_send_every_1s(ser_ref[0], send_text_var, crlf_var, hex_mode, debug_log, send_every_1s_var, run_flag))
    send_every_1s_checkbutton.pack(side='left', padx=(0, 10))

    # Bottom Frame Design (Modified for Scrollbar)
    bottom_frame = tk.Frame(root)
    bottom_frame.pack(fill='both', expand=True, pady=(0, 7))
    debug_log_scrollbar = tk.Scrollbar(bottom_frame)
    debug_log_scrollbar.pack(side='right', fill='y')
    debug_log = tk.Text(bottom_frame, height=1, state='disabled', yscrollcommand=debug_log_scrollbar.set)
    debug_log.pack(fill='both', expand=True)
    debug_log_scrollbar.config(command=debug_log.yview)

    root.mainloop()

if __name__ == "__main__":
    setup_gui()
