import os
import threading
import tkinter as tk
from tkinter import ttk
from tkinter import filedialog
from datetime import datetime
import serial
from serial.tools import list_ports

# Dynamic path finding for support files
application_path = os.path.dirname(os.path.abspath(__file__))

# Function to list available COM ports
def get_com_ports():
    return [port.device for port in list_ports.comports()]

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
def toggle_connection(port_combobox, baudrate_combobox, connect_button, debug_log, filter_entry, run_flag, hex_mode):
    if connect_button['text'] == "CONECTAR":
        try:
            ser = serial.Serial(port_combobox.get(), baudrate_combobox.get(), timeout=0)
            add_timestamp(debug_log, "Conectado na porta serial")
            connect_button.config(text="DESCONECTAR", bg='SystemButtonFace')
            run_flag[0] = True
            threading.Thread(target=read_serial_data, args=(ser, debug_log, filter_entry, run_flag, hex_mode), daemon=True).start()
        except:
            add_timestamp(debug_log, "Erro ao conectar porta serial.")
    else:
        run_flag[0] = False
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
    connect_button = tk.Button(top_frame, text="CONECTAR", bg='green', command=lambda: toggle_connection(port_combobox, baudrate_combobox, connect_button, debug_log, filter_entry, run_flag, hex_mode))
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
    tk.Label(middle_frame, text="Filtro:").pack(side='left')
    filter_entry = tk.Entry(middle_frame)
    filter_entry.pack(fill='x', expand=True)

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
