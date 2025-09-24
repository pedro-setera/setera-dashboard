import tkinter as tk
from tkinter import ttk
import traceback
import tkinter.messagebox
import configparser
from tkinter import font
import serial
import serial.tools.list_ports
import os

# Simplified path determination for portable Python environment
application_path = os.path.dirname(os.path.abspath(__file__))

# Construct the path to the config file dynamically
config_file_path = os.path.join(application_path, 'config_parser_str1010.ini')

# Initialization of global variable 'ser'
ser = None
serial_reading_active = False

root = tk.Tk()
root.title("SETERA - STR1010 Plus Parser")
root.state('zoomed')

# Use the dynamically constructed path for the icon
root.iconbitmap(os.path.join(application_path, 'favicon.ico'))

# Load the alarm codes from the dynamically specified config file
config = configparser.ConfigParser()
config.read(config_file_path, encoding='utf-8')
alarms = dict(config.items('alarms'))
gps = dict(config.items('gps'))
entradas = dict(config.items('entradas'))
saidas = dict(config.items('saidas'))
status_caminhao = dict(config.items('status_caminhao'))
tpms = dict(config.items('tpms'))
atividade = dict(config.items('atividade'))

# Define the fields
labels = ["1-Header/Cód Mensagem: ", "2-IMEI: ", "3-N/A: ", "4-Alarmes: ", "5-Conteúdo Alarme: ", "6-Data-Hora: ", "7-GPS: ", "8-Latitude: ", "9-Longitude: ",
    "10-Quantidade Sat: ", "11-HDOP: ", "12-Velocidade (Km/h): ", "13-Direção (graus): ", "14-Altitude (m): ",
    "15-Odômetro GPS (Km): ", "16-Torre GSM: ", "17-Nível Sinal GSM(0 a 31): ", "18-Status: ", "19-Entradas: ", "20-Saídas: ",
    "21-Alimentação Externa (V): ", "22-Bateria Interna (V): ", "23-N/A: ", "24-N/A: ", "25-CAN Header: ", "26-Status do caminhão: ",
    "27-Odômetro CAN (Km): ", "28-Consumo total (L): ", "29-Combustível no tanque (L): ", "30-Nível do tanque (%): ",
    "31-Velocidade (Km/h): ", "32-RPM do motor: ", "33-Posição do acelerador (%): ", "34-Temperatura do motor (°C): ",
    "35-Horímetro geral (seg): ", "36-Horímetro em movimento (seg): ", "37-Horímetro parado (seg): ", "38-Consumo em ponto morto (L): ",
    "39-Equipamentos ligados: ", "40-Estado das portas: ", "41-Tempo sobrevelocidade (seg): ", "42-Tempo excesso de RPM (seg): ",
    "43-Consumo instantâneo (Km/L): ", "44-Total frenagens: ", "45-Total acelerações fundo: ", "46-Torque do motor: ",
    "47-Pressão do Turbo: ", "48-RPM faixa verde (seg): ", "49-RPM faixa amarela (seg): ", "50-RPM faixa vermelha (seg): ",
    "51-Tempo banguela (seg): ", "52-Velocidade por pulsos (Hz): ", "53-RPM por pulsos (Hz): ", "54-Odômetro por pulsos (pulsos): ",
    "55-Roll (°): ", "56-Pitch (°): ", "57-Temp. placa eletrônica (°C): ", "58-Alarme de tombamento: ", "59-Entrada Digital 3: ",
    "60-Entrada Digital 4: ", "61-Tempo excesso pressão do turbo: ", "62-Entrada Digital 5: ", "63-Entrada Digital 6: ",
    "64-Entrada Digital 7: ", "65-Entrada Digital 8: ", "66-Entrada Digital 9: ", "67-Entrada Digital 10: ", "68-Saída Digital 2: ",
    "69-Saída Digital 3: ", "70-Saída Digital 4: ", "71-Saída Digital 5: ", "72-Motorista: ", "73-Atividade: ", "74-Sensor TPMS: ",
    "Alarmes TPMS: ", "Pressão TPMS (PSI): ", "Temperatura TPMS (°C): "]

def clear_textbox():
    entry.delete("1.0", tk.END)

def calculate_checksum(data):
    # Include the comma in the checksum calculation
    checksum_data = data + ','
    checksum = sum(checksum_data.encode()) % 256
    return checksum

def show_checksum():
    input_string = entry.get("1.0", 'end-1c')
    data_to_checksum = input_string.rsplit(',', 1)[0]  # Extract the data part for checksum calculation
    calculated_checksum = calculate_checksum(data_to_checksum)
    tk.messagebox.showinfo("Calculador de Checksum", f"Checksum da string atual = {calculated_checksum:02X}")

def update_com_ports():
    # Dynamically update the combobox values with available COM ports
    com_port_combobox['values'] = list_ports()
    if com_port_combobox['values']:
        com_port_combobox.current(0)  # Default to the first COM port if list is not empty
    else:
        com_port_combobox.set('No Ports Available')

def list_ports():
    ports = serial.tools.list_ports.comports()
    return [port.device for port in ports]

def toggle_connection():
    global ser, connect_button, com_port_var, serial_reading_active
    if ser is not None and ser.is_open:
        ser.close()
        ser = None  # Reset the serial object
        connect_button.config(text="CONECTAR", bg="SystemButtonFace")
        serial_reading_active = False
    else:
        selected_port = com_port_combobox.get()
        if selected_port and selected_port != 'No Ports Available':
            try:
                ser = serial.Serial(selected_port, 115200, timeout=1)
                connect_button.config(text="DESCONECTAR", bg="green")
                serial_reading_active = True
                read_from_serial()  # Ensure this is called after setting the flag
            except serial.SerialException as e:
                tkinter.messagebox.showerror("Erro Serial", f"Falha ao abrir a porta {selected_port}: {e}")
        else:
            tkinter.messagebox.showinfo("Erro Serial", "Favor selecionar uma porta COM.")

# Create the top frame for server connection
top_frame = tk.Frame(root)
top_frame.pack(fill=tk.X)

# Server Combobox setup with new server_values
com_port_label = tk.Label(top_frame, text="COM:")
com_port_label.pack(side=tk.LEFT, padx=5, pady=5)

com_port_var = tk.StringVar()
com_port_combobox = ttk.Combobox(top_frame, state="readonly", width=15, textvariable=com_port_var)
update_com_ports()  # Populate the combobox with available COM ports at startup
com_port_combobox.set("COM47")
#com_port_combobox.current(0)  # Default to the first server in the list
com_port_combobox.pack(side=tk.LEFT, padx=1, pady=5)

connect_button = tk.Button(top_frame, text="CONECTAR", command=toggle_connection)
connect_button.pack(side=tk.LEFT, padx=20, pady=5)

main_frame = tk.PanedWindow(root, orient=tk.VERTICAL)
main_frame.pack(fill=tk.BOTH, expand=1)

entry = tk.Text(main_frame, height=5, borderwidth=3)
main_frame.add(entry, padx=10, pady=3)

button_frame = tk.Frame(main_frame)
main_frame.add(button_frame, padx=10, pady=3)

bold_font = font.Font(weight='bold', size=10)

parse_button = tk.Button(button_frame, text="PROCESSAR", borderwidth=3, background='green', foreground='black', font=bold_font)
parse_button.pack(side=tk.LEFT, padx=20)

clear_button = tk.Button(button_frame, text="LIMPAR", borderwidth=3, background='yellow', foreground='black', font=bold_font, command=clear_textbox)
clear_button.pack(side=tk.LEFT, padx=20)

checksum_button = tk.Button(button_frame, text="CHECKSUM", borderwidth=3, background='orange', foreground='black', font=bold_font, command=show_checksum)
checksum_button.pack(side=tk.LEFT, padx=20)

# Add placeholders for the new labels in the button_frame section
checksum_label = tk.Label(button_frame, font=bold_font)
checksum_label.pack(side=tk.LEFT, padx=20)  # Added padding for aesthetics

fields_count_label = tk.Label(button_frame, font=bold_font)
fields_count_label.pack(side=tk.LEFT, padx=20)

output_frame = tk.PanedWindow(main_frame, orient=tk.HORIZONTAL)
main_frame.add(output_frame, padx=10, pady=3)

output1_frame = tk.Frame(output_frame)
output2_frame = tk.Frame(output_frame)
output3_frame = tk.Frame(output_frame)

# Add frames to the PanedWindow (without specifying width here)
output_frame.add(output1_frame)
output_frame.add(output2_frame)
output_frame.add(output3_frame)

# Set up labels for each column
output1_label = tk.Label(output1_frame, text="DADOS RASTREADOR", font=bold_font)
output1_label.pack(anchor='w', padx=10)
output2_label = tk.Label(output2_frame, text="DADOS LEITOR CAN", font=bold_font)
output2_label.pack(anchor='w', padx=10)
output3_label = tk.Label(output3_frame, text="DADOS MÓDULO AUXILIAR e TPMS", font=bold_font)
output3_label.pack(anchor='w', padx=10)

# Define the width of the Text widgets (in characters)
column_width = 48  # Example width, adjust as needed

# Create Text widgets with defined width
output1 = tk.Text(output1_frame, borderwidth=3, width=column_width)
output1.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True)
output2 = tk.Text(output2_frame, borderwidth=3, width=column_width)
output2.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True)
output3 = tk.Text(output3_frame, borderwidth=3, width=column_width)
output3.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True)

def binary_to_on_off(value):
    return "ON" if value == "1" else "OFF"

def read_from_serial():
    global serial_reading_active
    if ser and ser.is_open and serial_reading_active:
        try:
            while ser.in_waiting:  # While there is data waiting in the input buffer
                line = ser.readline().decode('utf-8').strip()
                if line.startswith("&&"):  # Process only lines that start with "&&"
                    clear_textbox()  # Clear the existing text in the entry widget
                    entry.insert(tk.END, line)  # Display the new string in the entry widget
                    parse_string(line)  # Then parse the string
                    break  # Process one line at a time to prevent blocking
        except Exception as e:
            print(f"Erro ao ler porta serial: {e}")
        finally:
            # Schedule this function to be called again soon, maintaining responsiveness
            if serial_reading_active:
                root.after(50, read_from_serial)  # Reduced delay to improve responsiveness
    else:
        # Optionally log or handle the case when reading is not active or serial is disconnected
        pass

def update_labels(checksum, fields_count):
    """
    Update the checksum and fields count labels with the given values.
    """
    checksum_label.config(text=f"Checksum: {checksum:02X}")
    fields_count_label.config(text=f"Número de campos: {fields_count}")

def parse_string(input_string=None):
    try:
        # If no string is provided, use the text box content
        if input_string is None:
            input_string = entry.get("1.0", 'end-1c')

        data_to_checksum, received_checksum = input_string.rsplit(',', 1)
        calculated_checksum = calculate_checksum(data_to_checksum)
        if calculated_checksum != int(received_checksum, 16):
            tk.messagebox.showerror("Erro de Checksum", f"Checksum inválido. Valor correto: {calculated_checksum:02X}")
            return
        
        # Calculate the number of fields by counting commas and adding one
        fields_count = input_string.count(',') + 1

        fields = data_to_checksum.split(',')
        atividade = dict(config.items('atividade'))
        status_caminhao = dict(config.items('status_caminhao'))

        tpms_alarms = dict(config.items('tpms'))

        # Specifically handle the TPMS data field
        tpms_field_index = 72  # Index of the TPMS field based on the provided information
        if len(fields) > tpms_field_index:
            tpms_data = fields[tpms_field_index].split('|')
            # Replace the TPMS field with its sub-fields
            fields[tpms_field_index:tpms_field_index + 1] = tpms_data

        output1.delete("1.0", tk.END)
        output2.delete("1.0", tk.END)
        output3.delete("1.0", tk.END)

        original_labels = ["1-Header/Cód Mensagem: ", "2-IMEI: ", "3-N/A: ", "4-Alarmes: ", "5-Conteúdo Alarme: ", "6-Data-Hora: ", "7-GPS: ", "8-Latitude: ", "9-Longitude: ",
            "10-Quantidade Sat: ", "11-HDOP: ", "12-Velocidade (Km/h): ", "13-Direção (graus): ", "14-Altitude (m): ",
            "15-Odômetro GPS (Km): ", "16-Torre GSM: ", "17-Nível Sinal GSM(0 a 31): ", "18-Status: ", "19-Entradas: ", "20-Saídas: ",
            "21-Alimentação Externa (V): ", "22-Bateria Interna (V): ", "23-N/A: ", "24-N/A: ", "25-CAN Header: ", "26-Status do caminhão: ",
            "27-Odômetro CAN (Km): ", "28-Consumo total (L): ", "29-Combustível no tanque (L): ", "30-Nível do tanque (%): ",
            "31-Velocidade (Km/h): ", "32-RPM do motor: ", "33-Posição do acelerador (%): ", "34-Temperatura do motor (°C): ",
            "35-Horímetro geral (seg): ", "36-Horímetro em movimento (seg): ", "37-Horímetro parado (seg): ", "38-Consumo em ponto morto (L): ",
            "39-Equipamentos ligados: ", "40-Estado das portas: ", "41-Tempo sobrevelocidade (seg): ", "42-Tempo excesso de RPM (seg): ",
            "43-Consumo instantâneo (Km/L): ", "44-Total frenagens: ", "45-Total acelerações fundo: ", "46-Torque do motor: ",
            "47-Pressão do Turbo: ", "48-RPM faixa verde (seg): ", "49-RPM faixa amarela (seg): ", "50-RPM faixa vermelha (seg): ",
            "51-Tempo banguela (seg): ", "52-Velocidade por pulsos (Hz): ", "53-RPM por pulsos (Hz): ", "54-Odômetro por pulsos (pulsos): ",
            "55-Roll (°): ", "56-Pitch (°): ", "57-Temp. placa eletrônica (°C): ", "58-Alarme de tombamento: ", "59-Entrada Digital 3: ",
            "60-Entrada Digital 4: ", "61-Tempo excesso pressão do turbo: ", "62-Entrada Digital 5: ", "63-Entrada Digital 6: ",
            "64-Entrada Digital 7: ", "65-Entrada Digital 8: ", "66-Entrada Digital 9: ", "67-Entrada Digital 10: ", "68-Saída Digital 2: ",
            "69-Saída Digital 3: ", "70-Saída Digital 4: ", "71-Saída Digital 5: ", "72-Motorista: ", "73-Atividade: ", "74-Sensor TPMS: ",
            "Alarmes TPMS: ", "Pressão TPMS (PSI): ", "Temperatura TPMS (°C): "]

        split_index_1 = original_labels.index("25-CAN Header: ")
        split_index_2 = original_labels.index("48-RPM faixa verde (seg): ")

        binary_labels = ["58-Alarme de tombamento: ", "59-Entrada Digital 3: ", "60-Entrada Digital 4: ", "62-Entrada Digital 5: ",
                        "63-Entrada Digital 6: ", "64-Entrada Digital 7: ", "65-Entrada Digital 8: ", "66-Entrada Digital 9: ", 
                        "67-Entrada Digital 10: ", "68-Saída Digital 2: ", "69-Saída Digital 3: ", "70-Saída Digital 4: ", 
                        "71-Saída Digital 5: "]
        
        update_labels(calculated_checksum, fields_count)

        for i, field in enumerate(fields):
            if i >= len(labels):
                break

            label = labels[i]
            if label == "Ignore":
                continue

            value = field.strip()

            try:
                if label in binary_labels:
                    value = binary_to_on_off(value)
                elif label == "4-Alarmes: ":
                    value = alarms.get(value, "Descnhecido")
                elif label == "7-GPS: ":
                    value = gps.get(value.lower(), "Descnhecido")
                elif label == "19-Entradas: ":
                    value = entradas.get(value, "Descnhecido")  # Look up Entradas status in the dictionary
                elif label == "20-Saídas: ":
                    value = saidas.get(value, "Descnhecido")  # Look up Saídas status in the dictionary
                elif label == "21-Alimentação Externa (V): ":
                    if '|' in field:  # If the field contains sub-fields
                        sub_fields = field.split('|')
                        value = str(int(sub_fields[0], 16) / 100)  # Convert the first sub-field
                        fields.insert(i+1, sub_fields[1])  # Insert the second sub-field back into fields at the next index
                    else:
                        value = str(int(field, 16) / 100)
                elif label == "22-Bateria Interna (V): ":
                    if len(value) == 6:
                        value = value[:-2]  # Remove last two characters if length is 6
                    value = str(int(value, 16) / 100)  # Convert the value to decimal and divide by 100
                elif label == "15-Odômetro GPS (Km): ":
                    value = str(round(int(value) / 1000, 3))  # Convert meters to kilometers
                elif label == "26-Status do caminhão: ":
                    value = status_caminhao.get(value, "Descnhecido")  # Look up truck status in the dictionary
                elif label == "73-Atividade: ":
                    value = atividade.get(value, "Descnhecido")  # Look up activity in the dictionary
                elif label == "Alarmes TPMS: ":
                    value = tpms_alarms.get(value, "Descnhecido")  # Look up tpms alarm status in the dictionary
            except Exception as e:
                value = f"Failed to parse field: {e}"
                traceback.print_exc()

            if i < split_index_1:
                output1.insert(tk.END, label + value + '\n')
            elif i < split_index_2:
                output2.insert(tk.END, label + value + '\n')
            else:
                output3.insert(tk.END, label + value + '\n')
    except Exception as e:
        tk.messagebox.showerror("Erro", f"Erro ao executar o parse: {e}")
        traceback.print_exc()

parse_button.configure(command=parse_string)

root.mainloop()