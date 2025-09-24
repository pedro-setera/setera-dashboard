import tkinter as tk
from tkinter import messagebox
import configparser
from tkinter import font
import os
import pandas as pd

# Simplified path determination for portable Python environment
application_path = os.path.dirname(os.path.abspath(__file__))

root = tk.Tk()
root.state('zoomed')  # Set the window maximized
root.title("SETERA - STR2020 Parser")  # Change the program title

# Modify icon path
icon_path = os.path.join(application_path, 'favicon.ico')
root.iconbitmap(default=icon_path)  # Add custom icon

# Load the alarm codes from a config_parser_str2020.ini file
config = configparser.ConfigParser()
config_path = os.path.join(application_path, 'config_parser_str2020.ini')

with open(config_path, 'r', encoding='utf-8') as f:  # Open the file with utf-8 encoding
    config.read_file(f)

main_frame = tk.Frame(root) # Replace PanedWindow with Frame
main_frame.pack(fill=tk.BOTH, expand=1)

entry = tk.Text(main_frame, height=5, borderwidth=2)
entry.pack(fill=tk.X, padx=10, pady=(10, 5)) # Use pack instead of add

button_frame = tk.Frame(main_frame)
button_frame.pack(fill=tk.X, pady=10) # Use pack instead of add

# Create a bold font style
bold_font = font.Font(weight='bold', size=10)

# Configure the first button and place it on the left side of the grid (column 0)
parse_button = tk.Button(button_frame, text="PROCESSAR", borderwidth=2, background="#AAEAF8", foreground='black', font=bold_font)
parse_button.grid(row=0, column=0)  # Use grid layout with padding

# Configure the second button and place it next to the first button (column 1)
clear_button = tk.Button(button_frame, text="LIMPAR", borderwidth=2, background="#AAF8B5", foreground='black', font=bold_font, command=lambda: clear_fields())
clear_button.grid(row=0, column=1)  # Use grid layout with padding

# Adjust the button_frame to center its content
button_frame.grid_columnconfigure(0, weight=1)
button_frame.grid_columnconfigure(1, weight=1)

output_frame = tk.Frame(main_frame)  # Replace PanedWindow with Frame
output_frame.pack(fill=tk.BOTH, expand=1, padx=10, pady=(0, 10))  # Use pack instead of add

output1_frame = tk.Frame(output_frame)
output1_frame.grid(row=0, column=0, sticky='nsew')  # Use grid instead of add

output2_frame = tk.Frame(output_frame)
output2_frame.grid(row=0, column=1, sticky='nsew')  # Use grid instead of add

output3_frame = tk.Frame(output_frame)
output3_frame.grid(row=0, column=2, sticky='nsew')  # Use grid instead of add

output_frame.columnconfigure(0, weight=1)  # Set the weight for each column to 1
output_frame.columnconfigure(1, weight=1)  # This tells tkinter to distribute space equally among the columns
output_frame.columnconfigure(2, weight=1)

output_frame.rowconfigure(0, weight=1)  # This tells tkinter to distribute space equally among the rows

output1_label = tk.Label(output1_frame, text="DADOS GERAIS", font=bold_font)
output1_label.pack(pady=(0, 5))
output1 = tk.Text(output1_frame, borderwidth=2)
output1.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True)

output2_label = tk.Label(output2_frame, text="DADOS CANBUS", font=bold_font)
output2_label.pack(pady=(0, 5))
output2 = tk.Text(output2_frame, borderwidth=2)
output2.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True)

output3_label = tk.Label(output3_frame, text="DADOS TPMS", font=bold_font)
output3_label.pack(pady=(0, 5))
output3 = tk.Text(output3_frame, borderwidth=2)
output3.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True)

def clear_fields():
    entry.delete("1.0", tk.END)
    output1.delete("1.0", tk.END)
    output2.delete("1.0", tk.END)
    output3.delete("1.0", tk.END)

def parse_string():
    try:
        # Get input
        input_string = entry.get("1.0", 'end-1c')
        sections = input_string.split(';')

        # Clear output grid
        output1.delete("1.0", tk.END)
        output2.delete("1.0", tk.END)
        output3.delete("1.0", tk.END)

        # Parse sections
        for i, section in enumerate(sections):
            if i > 6:  # Ignore sections after the 7th one
                break

            fields = section.split(',')

            # Section 1
            if i == 0:
                output1.insert(tk.END, "IMEI: " + fields[0] + '\n')

            # Section 2
            elif i == 1:
                output1.insert(tk.END, "Tipo de Mensagem: " + config.get('tipo', fields[0], fallback=fields[0]) + '\n')
                output1.insert(tk.END, "Data Hora: " + fields[1][4:6] + '/' + fields[1][2:4] + '/' + fields[1][:2] + ' - ' + fields[1][6:8] + ':' + fields[1][8:10] + ':' + fields[1][10:] + ' UTC\n')
                output1.insert(tk.END, "Status GPS: " + config.get('gps', fields[2].upper(), fallback=fields[2]) + '\n')
                output1.insert(tk.END, "Latitude: " + fields[3] + '\n')
                output1.insert(tk.END, "Longitude: " + fields[4] + '\n')
                output1.insert(tk.END, "Vel GPS (Km/h): " + str(round(float(fields[5]) * 1.854, 0)) + '\n')
                output1.insert(tk.END, "Direção (°): " + fields[6] + '\n')
                output1.insert(tk.END, "Diluição da precisão: " + fields[7] + '\n')
                output1.insert(tk.END, "Status: " + fields[8] + '\n')

            # Section 3
            elif i == 2:
                output1.insert(tk.END, "Quantidade de Satélites: " + fields[2] + '\n')
                output1.insert(tk.END, "Altitude (m): " + fields[3] + '\n')
                output1.insert(tk.END, "Voltagem veículo (V): " + fields[4] + '\n')
                output1.insert(tk.END, "Voltagem bateria interna (V): " + fields[5] + '\n')
                output1.insert(tk.END, "Odômetro GPS (km): " + fields[6] + '\n')
                output1.insert(tk.END, "Sinal GSM(0 a 31): " + fields[7] + '\n')
                output1.insert(tk.END, "Rede GSM: " + config.get('gsm', fields[8], fallback=fields[8]) + '\n')
                output1.insert(tk.END, "Contador reboot GSM: " + fields[9] + '\n')
                output1.insert(tk.END, "Reservado: " + fields[10] + '\n')

            # Section 4
            elif i == 3:
                if len(fields) < 36:  # If the section has less than 36 fields
                    output2.insert(tk.END, "SEM DADOS CANBUS\n")
                elif len(fields) == 36:
                    output2.insert(tk.END, "Status do caminhão: " + config.get('status_carro', fields[2], fallback=fields[2]) + '\n')
                    output2.insert(tk.END, "Odômetro (Km): " + fields[3] + '\n')
                    output2.insert(tk.END, "Consumo total (L): " + fields[4] + '\n')
                    output2.insert(tk.END, "Combustível no tanque (L): " + fields[5] + '\n')
                    output2.insert(tk.END, "Nível do tanque (%): " + fields[6] + '\n')
                    output2.insert(tk.END, "Vel CAN (Km/h): " + fields[7] + '\n')
                    output2.insert(tk.END, "RPM do motor: " + fields[8] + '\n')
                    output2.insert(tk.END, "Posição do acelerador (%): " + fields[9] + '\n')
                    output2.insert(tk.END, "Temperatura do motor (°C): " + fields[10] + '\n')
                    output2.insert(tk.END, "Horímetro geral (seg): " + fields[11] + '\n')
                    output2.insert(tk.END, "Horímetro em movimento (seg): " + fields[12] + '\n')
                    output2.insert(tk.END, "Horímetro parado (seg): " + fields[13] + '\n')
                    output2.insert(tk.END, "Consumo em ponto morto (L): " + fields[14] + '\n')
                    output2.insert(tk.END, "Equipamentos: " + fields[15] + '\n')
                    output2.insert(tk.END, "Portas: " + fields[16] + '\n')
                    output2.insert(tk.END, "Tempo sobrevelocidade (seg): " + fields[17] + '\n')
                    output2.insert(tk.END, "Tempo excesso de RPM (seg): " + fields[18] + '\n')
                    output2.insert(tk.END, "Consumo instantâneo (Km/L): " + fields[19] + '\n')
                    output2.insert(tk.END, "Total frenagens: " + fields[20] + '\n')
                    output2.insert(tk.END, "Total acelerações fundo: " + fields[21] + '\n')
                    output2.insert(tk.END, "Torque do motor (%): " + fields[22] + '\n')
                    output2.insert(tk.END, "RPM faixa verde (seg): " + fields[23] + '\n')
                    output2.insert(tk.END, "RPM faixa amarela (seg): " + fields[24] + '\n')
                    output2.insert(tk.END, "RPM faixa vermelha (seg): " + fields[25] + '\n')
                    output2.insert(tk.END, "Tempo banguela (seg): " + fields[26] + '\n')
                    output2.insert(tk.END, "Velocidade por pulsos (Hz): " + fields[27] + '\n')
                    output2.insert(tk.END, "RPM por pulsos (Hz): " + fields[28] + '\n')
                    output2.insert(tk.END, "Odômetro por pulsos (pulsos): " + fields[29] + '\n')
                    output2.insert(tk.END, "Pitch (°): " + fields[30] + '\n')
                    output2.insert(tk.END, "Roll (°): " + fields[31] + '\n')
                    output2.insert(tk.END, "Temperatura da placa eletrônica (°C): " + fields[32] + '\n')
                    output2.insert(tk.END, "Alarme de tombamento: " + config.get('tombamento', fields[33], fallback=fields[33]) + '\n')
                    output2.insert(tk.END, "Entrada Digital 6: " + config.get('entrada_6', fields[34], fallback=fields[34]) + '\n')
                    output2.insert(tk.END, "Entrada Digital 7: " + config.get('entrada_7', fields[35], fallback=fields[35]) + '\n')

                elif len(fields) == 38:  # If the section has 38 fields
                    output2.insert(tk.END, "Status do caminhão: " + config.get('status_carro', fields[2], fallback=fields[2]) + '\n')
                    output2.insert(tk.END, "Odômetro (Km): " + fields[3] + '\n')
                    output2.insert(tk.END, "Consumo total (L): " + fields[4] + '\n')
                    output2.insert(tk.END, "Combustível no tanque (L): " + fields[5] + '\n')
                    output2.insert(tk.END, "Nível do tanque (%): " + fields[6] + '\n')
                    output2.insert(tk.END, "Vel CAN (Km/h): " + fields[7] + '\n')
                    output2.insert(tk.END, "RPM do motor: " + fields[8] + '\n')
                    output2.insert(tk.END, "Posição do acelerador (%): " + fields[9] + '\n')
                    output2.insert(tk.END, "Temperatura do motor (°C): " + fields[10] + '\n')
                    output2.insert(tk.END, "Horímetro geral (seg): " + fields[11] + '\n')
                    output2.insert(tk.END, "Horímetro em movimento (seg): " + fields[12] + '\n')
                    output2.insert(tk.END, "Horímetro parado (seg): " + fields[13] + '\n')
                    output2.insert(tk.END, "Consumo em ponto morto (L): " + fields[14] + '\n')
                    output2.insert(tk.END, "Equipamentos: " + fields[15] + '\n')
                    output2.insert(tk.END, "Portas: " + fields[16] + '\n')
                    output2.insert(tk.END, "Tempo sobrevelocidade (seg): " + fields[17] + '\n')
                    output2.insert(tk.END, "Tempo excesso de RPM (seg): " + fields[18] + '\n')
                    output2.insert(tk.END, "Consumo instantâneo (Km/L): " + fields[19] + '\n')
                    output2.insert(tk.END, "Total frenagens: " + fields[20] + '\n')
                    output2.insert(tk.END, "Total acelerações fundo: " + fields[21] + '\n')
                    output2.insert(tk.END, "Torque do motor (%): " + fields[22] + '\n')
                    output2.insert(tk.END, "Pressão do Turbo: " + fields[23] + '\n')
                    output2.insert(tk.END, "RPM faixa verde (seg): " + fields[24] + '\n')
                    output2.insert(tk.END, "RPM faixa amarela (seg): " + fields[25] + '\n')
                    output2.insert(tk.END, "RPM faixa vermelha (seg): " + fields[26] + '\n')
                    output2.insert(tk.END, "Tempo banguela (seg): " + fields[27] + '\n')
                    output2.insert(tk.END, "Velocidade por pulsos (Hz): " + fields[28] + '\n')
                    output2.insert(tk.END, "RPM por pulsos (Hz): " + fields[29] + '\n')
                    output2.insert(tk.END, "Odômetro por pulsos (pulsos): " + fields[30] + '\n')
                    output2.insert(tk.END, "Pitch (°): " + fields[31] + '\n')
                    output2.insert(tk.END, "Roll (°): " + fields[32] + '\n')
                    output2.insert(tk.END, "Temperatura da placa eletrônica (°C): " + fields[33] + '\n')
                    output2.insert(tk.END, "Alarme de tombamento: " + config.get('tombamento', fields[34], fallback=fields[34]) + '\n')
                    output2.insert(tk.END, "Entrada Digital 6: " + config.get('entrada_6', fields[35], fallback=fields[35]) + '\n')
                    output2.insert(tk.END, "Entrada Digital 7: " + config.get('entrada_7', fields[36], fallback=fields[36]) + '\n')
                    output2.insert(tk.END, "Tempo excesso pressão do turbo: " + fields[37] + '\n')

            # Section 5
            elif i == 4:
                output1.insert(tk.END, "Versão HW: " + fields[1] + '\n')
                output1.insert(tk.END, "Versão FW: " + fields[2] + '\n')
                output1.insert(tk.END, "Versão HW GSM: " + fields[5] + '\n')
                output1.insert(tk.END, "Versão FW GSM: " + fields[6] + '\n')
                output1.insert(tk.END, "ICCID: " + fields[10] + '\n')

            # Section 6
            elif i == 5:
                if fields[1]:
                    output1.insert(tk.END, "ID Motorista: " + fields[1][:5] + '\n')
                    output1.insert(tk.END, "Senha Motorista: " + fields[1][5:9] + '\n')
                    atividade = config.get('atividade', fields[1][9:], fallback="Atividade não declarada")
                    output1.insert(tk.END, "Atividade: " + atividade + '\n')
                else:
                    output1.insert(tk.END, "ID Motorista: Motorista não identificado" + '\n')
                    output1.insert(tk.END, "Senha Motorista: Motorista não identificado" + '\n')
                    output1.insert(tk.END, "Atividade: Motorista não identificado" + '\n')

            # Section 7
            elif i == 6:
                # Ignore the first two fields
                fields = fields[2:]

                # Check if there is any TPMS data
                if len(fields) % 5 != 0:
                    output3.insert(tk.END, "SEM DADOS TPMS\n")
                    continue

                # Create a DataFrame object
                data = []
                for j in range(0, len(fields), 5):
                    id_sensor = fields[j]
                    alarmes = config.get('alarme_tpms', fields[j + 1], fallback=fields[j + 1])
                    
                    # Check if the field is empty or equals to '-1' and replace it with a dash
                    pressao = fields[j + 2] if fields[j + 2] not in ('', '-1') else '-'
                    temp = fields[j + 3] if fields[j + 3] not in ('', '-1') else '-'
                    bat = config.get('bateria_tpms', fields[j + 4], fallback=fields[j + 4]) if fields[j + 4] not in ('', '-1') else '-'
                    
                    data.append([id_sensor, alarmes, pressao, temp, bat])

                df = pd.DataFrame(data, columns=["Sensor", "Alarme", "Pressão", "Temp.(°C)", "Bateria"])

                # Insert the string representation of the DataFrame into the output Text widget
                output3.insert(tk.END, df.to_string(index=False, col_space=10) + '\n')

    except Exception as e:
        messagebox.showerror("Erro", f"String em formato incorreto: {e}")


# Replace the old parse_string function with the new one
parse_button.configure(command=parse_string)

root.mainloop()
