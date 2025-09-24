import tkinter as tk
from tkinter import messagebox
import os
import requests
import threading
import pyperclip

# Function to capitalize entry box content and limit to 7 characters
def validate_plate_entry(*args):
    plate = ''.join([char for char in plate_var.get() if char.isalnum()]).upper()
    if len(plate) > 7:
        plate = plate[:7]
    plate_var.set(plate)

# Function to perform API search
def search_vehicle():
    plate = plate_var.get()
    if not plate:
        messagebox.showwarning("Aviso", "Por favor, insira a placa do veículo.")
        return
    
    def fetch_data():
        try:
            print(f"Sending request to API for plate: {plate}")
            response = requests.get(f'https://placas.fipeapi.com.br/placas/{plate}?key=d72b569603a805c199beb37a9928f35d')
            response.raise_for_status()
            data = response.json()
            print(f"Received response: {data}")
            update_labels(data)
        except requests.RequestException as e:
            print(f"API request error: {e}")
            messagebox.showerror("ERRO DE CONSULTA", "Erro ao consultar dados, Confira a placa e tente novamente")

    threading.Thread(target=fetch_data).start()

# Function to clear all fields
def clear_fields():
    plate_var.set("")
    for label in data_labels.values():
        label.config(text="")

# Function to update labels with fetched data
def update_labels(data):
    veiculo = data.get("data", {}).get("veiculo", {})
    fipes = data.get("data", {}).get("fipes", [])

    def get_value(value, default="SEM DADOS"):
        return value if value is not None else default

    def format_currency(value):
        value_str = str(value)
        value_str = value_str[::-1]
        formatted_value = ".".join([value_str[i:i+3] for i in range(0, len(value_str), 3)])[::-1]
        return f"R${formatted_value},00"

    def strip_zeros(value):
        stripped_value = value.lstrip('0')
        return stripped_value if stripped_value else '0'

    values = {
        "Placa": get_value(veiculo.get("placa")),
        "Tipo": get_value(veiculo.get("tipo_de_veiculo")),
        "Chassi": get_value(veiculo.get("chassi")),
        "Marca": get_value(veiculo.get("marca_modelo", "SEM DADOS").split("/")[0]),
        "Modelo": get_value(veiculo.get("marca_modelo", "SEM DADOS").split("/")[1] if "/" in veiculo.get("marca_modelo", "") else "SEM DADOS"),
        "Cor": get_value(veiculo.get("cor")),
        "Ano Fab": get_value(veiculo.get("ano", "SEM DADOS").split("/")[0]),
        "Ano Mod": get_value(veiculo.get("ano", "SEM DADOS").split("/")[1] if "/" in veiculo.get("ano", "") else "SEM DADOS"),
        "País": "BRASIL" if veiculo.get("procedencia", "").lower() == "nacional" else get_value(veiculo.get("procedencia")).upper(),
        "Cidade": get_value(veiculo.get("municipio")),
        "UF": get_value(veiculo.get("uf")),
        "PBT": strip_zeros(get_value(veiculo.get("pbt"))),
        "CMT": strip_zeros(get_value(veiculo.get("cmt"))),
        "Potência": strip_zeros(get_value(veiculo.get("potencia"))),
        "Cilindrada": strip_zeros(get_value(veiculo.get("cilindradas"))),
        "Passageiros": strip_zeros(get_value(veiculo.get("quantidade_passageiro"))),
        "Eixos": strip_zeros(get_value(veiculo.get("quantidade_de_eixos"))),
        "Nr Motor": get_value(veiculo.get("n_motor")),
        "Combustível": get_value(veiculo.get("combustivel")),
        "Carga Útil": strip_zeros(get_value(veiculo.get("capacidade_de_carga"))),
        "Valor FIPE": format_currency(get_value(str(fipes[0].get("valor")) if fipes else None))
    }

    for key, value in values.items():
        data_labels[key].config(text=value.upper(), anchor="w")

# Function to copy data to clipboard
def copy_to_clipboard(value):
    pyperclip.copy(value)

# Initialize main window
root = tk.Tk()
root.geometry("750x450")
root.title("SETERA - Busca de Veículos")
root.iconbitmap(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'favicon.ico'))
# root.state('zoomed')

# Variables and StringVar for plate entry
plate_var = tk.StringVar()
plate_var.trace_add("write", validate_plate_entry)

# Top frame for input
top_frame = tk.Frame(root)
top_frame.pack(pady=7)

# Plate entry
tk.Label(top_frame, text="Placa:", font=("Helvetica", 10, "bold")).pack(side=tk.LEFT, padx=10)
plate_entry = tk.Entry(top_frame, textvariable=plate_var, width=20, font=("Helvetica", 10, "bold"))
plate_entry.pack(side=tk.LEFT, padx=10)

# Search button
search_button = tk.Button(top_frame, text="BUSCAR", command=search_vehicle, font=("Helvetica", 10, "bold"), bg="green")
search_button.pack(side=tk.LEFT, padx=10)

# Clear button
clear_button = tk.Button(top_frame, text="LIMPAR", command=clear_fields, font=("Helvetica", 10, "bold"), bg="yellow")
clear_button.pack(side=tk.LEFT, padx=10)

# Separator
separator = tk.Frame(root, height=2, bd=1, relief=tk.SUNKEN)
separator.pack(fill=tk.X, padx=5, pady=5)

# Lower frame for displaying data
lower_frame = tk.Frame(root)
lower_frame.pack(pady=5, fill=tk.BOTH, expand=True)

# Left and right frames for data
left_frame = tk.Frame(lower_frame)
left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

right_frame = tk.Frame(lower_frame)
right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 0))

# Labels for data display
data_labels = {}
data_fields = [
    ("Placa", left_frame), ("Tipo", left_frame), ("Chassi", left_frame), ("Marca", left_frame), 
    ("Modelo", left_frame), ("Cor", left_frame), ("Ano Fab", left_frame), 
    ("Ano Mod", left_frame), ("País", left_frame), ("Cidade", left_frame), 
    ("UF", left_frame), ("PBT", right_frame), ("CMT", right_frame), ("Potência", right_frame), 
    ("Cilindrada", right_frame), ("Passageiros", right_frame), ("Eixos", right_frame), 
    ("Nr Motor", right_frame), ("Combustível", right_frame), ("Carga Útil", right_frame), 
    ("Valor FIPE", right_frame)
]

for field, frame in data_fields:
    sub_frame = tk.Frame(frame)
    sub_frame.pack(anchor=tk.W, pady=3, fill=tk.X)
    
    tk.Label(sub_frame, text=f"{field}:", font=("Helvetica", 10, "bold")).pack(side=tk.LEFT)
    label = tk.Label(sub_frame, text="", font=("Helvetica", 10, "bold"))
    label.pack(side=tk.LEFT, fill=tk.X, expand=True)
    data_labels[field] = label
    
    copy_button = tk.Button(sub_frame, text="COPIAR", command=lambda l=label: copy_to_clipboard(l.cget("text")), font=("Helvetica", 10, "bold"))
    copy_button.pack(side=tk.RIGHT, padx=5)

root.mainloop()
