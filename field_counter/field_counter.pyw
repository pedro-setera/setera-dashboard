import tkinter as tk
from tkinter import ttk
import os

application_path = os.path.dirname(os.path.abspath(__file__))

# Function to update log area
def add_log(text):
    log_textbox.insert(tk.END, text + "\n")
    log_textbox.see(tk.END)

# Function to analyze data
def analyze():
    separator = separator_combobox.get()
    separator_dict = {
        "Vírgula": ",",
        "Ponto": ".",
        "Ponto-e-vírgula": ";",
        "Dois pontos": ":",
        "Hífen": "-",
        "Barra": "/",
        "Barra invertida": "\\",
        "Underscore": "_",
        "Pipe": "|",
        "Espaço": " "
    }
    actual_separator = separator_dict[separator]
    input_string = input_textbox.get("1.0", "end-1c").strip()
    
    if not input_string:
        add_log("Sem dados para analisar.")
        return
    
    if actual_separator not in input_string:
        add_log(f"Essa string não contem o separador selecionado: {separator}.")
        return
    
    fields = input_string.split(actual_separator)
    number_of_fields = len(fields)
    add_log(f"Essa string possui {number_of_fields} campos separados por {separator}.")

def clear():
    input_textbox.delete("1.0", tk.END)
    log_textbox.delete("1.0", tk.END)

# Create the main window
root = tk.Tk()
root.title("SETERA - Contador de campos")
root.geometry("900x500")
root.resizable(False, False)
root.iconbitmap(os.path.join(application_path, 'favicon.ico'))

# Create a frame for the top controls
top_frame = tk.Frame(root)
top_frame.pack(fill=tk.X, padx=5, pady=5)

# Separator combobox
separator_label = tk.Label(top_frame, text="Separador:")
separator_label.pack(side=tk.LEFT, padx=(10, 0))
separator_combobox = ttk.Combobox(top_frame, width=20, values=["Vírgula", "Ponto", "Ponto-e-vírgula", "Dois pontos", "Hífen", "Barra", "Barra invertida", "Underscore", "Pipe", "Espaço"], state="readonly")
separator_combobox.set("Vírgula")  # Default value
separator_combobox.pack(side=tk.LEFT, padx=(0, 10))

# Analyze button
analyze_button = tk.Button(top_frame, text="ANALISAR", bg='green', fg='white', command=analyze)
analyze_button.pack(side=tk.LEFT, padx=20)

# Clear button
clear_button = tk.Button(top_frame, text="LIMPAR", bg='yellow', fg='black', command=clear)
clear_button.pack(side=tk.LEFT, padx=20)

# Input textbox
input_textbox = tk.Text(root, height=5)
input_textbox.pack(fill=tk.X, padx=5, pady=(0, 5))

# Log textbox
log_textbox = tk.Text(root, bg="black", fg="white")
log_textbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))

root.mainloop()
