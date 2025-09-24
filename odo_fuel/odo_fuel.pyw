import tkinter as tk
from tkinter import ttk, scrolledtext
from configparser import ConfigParser
import psycopg2
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
import pandas as pd
import os
import time
import subprocess
from tkcalendar import DateEntry
import threading
from pathlib import Path

# Global variables for process control
conn = None  # Database connection
running = True  # Process control flag
vehicles = []

application_path = os.path.dirname(os.path.abspath(__file__))

def load_db_config(config_filename='config_odo.ini'):
    config_file = os.path.join(application_path, config_filename)
    parser = ConfigParser()
    if not os.path.exists(config_file):
        raise FileNotFoundError(f"Arquivo de configuração '{config_file}' não encontrado.")
    parser.read(config_file)
    return {param: parser.get('server', param) for param in parser.options('server')}

def log_to_textbox(text):
    log_textbox.insert(tk.END, text + "\n")
    log_textbox.see(tk.END)
    root.update_idletasks()

def update_vehicle_selection_widget(vehicles):
    vehicle_selection_combobox['values'] = [plate_name for id_terminal, plate_name in vehicles]  # Populate ComboBox
    if vehicles:
        vehicle_selection_combobox.current(0)  # Set the first item as the default selection

def fetch_vehicle_data():
    global vehicles  # Declare vehicles as global to modify it
    db_params = load_db_config()
    try:
        log_to_textbox("Conectando ao banco de dados...")
        conn = psycopg2.connect(**db_params)
        cursor = conn.cursor()
        log_to_textbox("Conexão realizada com sucesso.")
        cursor.execute("SELECT id, placa FROM scm_setera.tb_terminal WHERE ativo is true AND id_terminal_protocolo in (21) ORDER BY placa ASC")
        vehicles = cursor.fetchall()  # Update the global vehicles variable
        log_to_textbox("Veículos listados com sucesso.")
        update_vehicle_selection_widget(vehicles)
    except Exception as e:
        log_to_textbox(f"Falha ao listar veículos: {e}")
    finally:
        if conn is not None:
            conn.close()
            log_to_textbox("Conexão com o banco de dados fechada.")

def get_selected_vehicle_ids():
    selected_plate_name = vehicle_selection_combobox.get()
    selected_vehicle = next(((id, placa) for id, placa in vehicles if placa == selected_plate_name), None)
    return [selected_vehicle] if selected_vehicle else []

# Ensure the 'resultados_consumo' directory exists
def ensure_resultados_consumo_dir():
    # Locate the Downloads folder (works for Windows and most Unix-like OSes)
    downloads_path = Path.home() / 'Downloads'
    resultados_consumo_dir = downloads_path / 'resultados_consumo'
    if not resultados_consumo_dir.exists():
        resultados_consumo_dir.mkdir(parents=True, exist_ok=True)
    return str(resultados_consumo_dir)

def open_resultados_consumo_folder():
    """Opens the 'resultados_consumo' folder in the file explorer."""
    resultados_consumo_dir = ensure_resultados_consumo_dir()
    try:
        # For Windows
        os.startfile(resultados_consumo_dir)
    except AttributeError:
        # For Unix-based systems, adjust as needed
        subprocess.Popen(['xdg-open', resultados_consumo_dir])

def interrupt_process():
    global running, conn
    running = False
    if conn:
        try:
            conn.close()
        except Exception as e:
            log_to_textbox(f"Error closing the database connection: {e}")
    log_to_textbox("Processo interrompido pelo usuário.")
    # The connection is reset to None after ensuring it's closed
    conn = None

def process_data_thread():
    global conn, running
    running = True
    
    resultados_consumo_dir = ensure_resultados_consumo_dir()  # Ensure the resultados_consumo directory exists before proceeding
    
    # Retrieve the dates from the DateEntry widgets
    start_date_str = start_date_picker.get_date().strftime('%Y-%m-%d')
    end_date_str = end_date_picker.get_date().strftime('%Y-%m-%d')
    
    # Format adjustment
    start_date = f"{start_date_str} 00:00:00.000"
    end_date = f"{end_date_str} 23:59:59.999"

    db_params = load_db_config()
    try:
        log_to_textbox("Conectando ao banco de dados...")
        conn = psycopg2.connect(**db_params)
        log_to_textbox("Conexão realizada com sucesso.")
    except Exception as e:
        log_to_textbox(f"Falha ao conectar com o banco de dados: {e}")
        return

    time.sleep(2)
    selected_vehicle_ids = get_selected_vehicle_ids()
    selected_vehicles = get_selected_vehicle_ids()

    with conn:
        cursor = conn.cursor()
        for id_terminal, plate_name in selected_vehicles:  # Iterate over each tuple
            if not running:
                break
            try:
                log_to_textbox(f"Data Inicial: {start_date}")
                log_to_textbox(f"Data Final: {end_date}")
                log_to_textbox(f"Processando terminal id {id_terminal}...")
                # Query adjustment for dynamic date range
                query = f"""
                SELECT mensagem FROM scm_setera.tb_terminal_mensagem_processada
                WHERE id_terminal = {id_terminal}
                AND data_recebimento_mensagem BETWEEN '{start_date}' AND '{end_date}'
                """
                cursor.execute(query)
                rows = cursor.fetchall()
                if not rows:
                    log_to_textbox(f"Sem dados para o terminal {id_terminal} no período escolhido. Continuando para o próximo terminal.")
                    continue

                mileage = []
                fuel_consumption = []
                gps_dates = []

                filtered_message_count = 0

                for row in rows:
                    mensagem = row[0]
                    if 'FR1,2,' in mensagem or 'FR1,1,' in mensagem:
                        filtered_message_count += 1  # Increment the counter
                        parts = mensagem.split(',')
                        try:
                            gps_date_str = parts[2]
                            gps_date = datetime.strptime(gps_date_str, '%y%m%d%H%M%S')

                            fr_parts = mensagem.split('FR1,')[1].split(',')
                            mileage_value = float(fr_parts[1])
                            fuel_consumption_value = float(fr_parts[2])

                            mileage.append(mileage_value)
                            fuel_consumption.append(fuel_consumption_value)
                            gps_dates.append(gps_date)
                        except (ValueError, IndexError):
                            continue

                # After processing all rows for the current terminal, log the count
                log_to_textbox(f"Total de mensagens filtradas para o terminal {id_terminal}: {filtered_message_count}")

                if not gps_dates:
                    log_to_textbox(f"Sem dados válidos para o terminal {id_terminal}. Continuando para o próximo terminal.")
                    continue

                sorted_data = sorted(zip(gps_dates, mileage, fuel_consumption), key=lambda x: x[0])
                sorted_gps_dates, sorted_mileage, sorted_fuel_consumption = zip(*sorted_data)

                # Plotting
                fig, ax1 = plt.subplots(figsize=(10, 6))
                ax1.set_xlabel('Data-Hora')
                ax1.set_ylabel('Odômetro', color='tab:green')
                ax1.plot(sorted_gps_dates, sorted_mileage, color='tab:green')
                ax1.tick_params(axis='y', labelcolor='tab:green')

                ax1.xaxis.set_major_locator(mdates.DayLocator())
                ax1.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m/%y'))
                plt.xticks(rotation=45)

                ax2 = ax1.twinx()
                ax2.set_ylabel('Consumo', color='tab:blue')
                ax2.plot(sorted_gps_dates, sorted_fuel_consumption, color='tab:blue')
                ax2.tick_params(axis='y', labelcolor='tab:blue')

                # Adjust layout to make space for the title
                fig.tight_layout(pad=2.0)  # Adjust padding as necessary
                plt.subplots_adjust(top=0.9)  # Make space at the top of the plot

                # Set the title with enough space above the plot
                fig.suptitle(f'Análise do veículo {plate_name}', fontsize=12)

                # Calculate and annotate the requested info
                if sorted_mileage and sorted_fuel_consumption:
                    odometer_range = sorted_mileage[-1] - sorted_mileage[0]
                    total_fuel_consumption = sorted_fuel_consumption[-1] - sorted_fuel_consumption[0]
                    average_consumption = odometer_range / total_fuel_consumption if total_fuel_consumption else 0

                    plt.annotate(f"Odômetro no período: {odometer_range:.1f}Km\n"
                                f"Consumo no período: {total_fuel_consumption:.1f}Litros\n"
                                f"Média no período: {average_consumption:.1f}Km/L",
                                xy=(0.05, 0.95), xycoords='axes fraction',
                                va='top', ha='left')

                # Save the figure
                resultados_consumo_dir = Path(ensure_resultados_consumo_dir())
                fig.savefig(resultados_consumo_dir / f'grafico_{plate_name}.jpg', dpi=300)
                plt.close(fig)

                # DataFrame for Excel
                df = pd.DataFrame({
                    'Data-Hora GPS': sorted_gps_dates,
                    'Odômetro': sorted_mileage,
                    'Consumo': sorted_fuel_consumption
                })
                excel_path = resultados_consumo_dir / f'valores_odometro_consumo_{plate_name}.xlsx'
                df.to_excel(excel_path, index=False)

            except (Exception, psycopg2.DatabaseError) as error:
                log_to_textbox(f"Erro ao processar terminal id {id_terminal}: {error}")
    if running:
        log_to_textbox("Processamento finalizado. Clique no botão \"RESULTADOS\" para acessar os gráficos.")

def process_data():
    # Start the data processing in a separate thread
    thread = threading.Thread(target=process_data_thread, daemon=True)
    thread.start()

def clear_log():
    log_textbox.delete('1.0', tk.END)

# Tkinter GUI setup adjustments for DateEntry widgets
root = tk.Tk()
root.title("SETERA - Análise de Odômetro e Consumo")
root.geometry("1000x600")
root.resizable(False, False)
root.iconbitmap(os.path.join(application_path, 'favicon.ico'))

top_frame = tk.Frame(root)
top_frame.pack(side=tk.TOP, fill=tk.X, expand=False)
main_frame = tk.Frame(root)
main_frame.pack(fill=tk.BOTH, expand=True)

list_vehicles_button = tk.Button(top_frame, text="1. Listar Veículos", command=fetch_vehicle_data)
list_vehicles_button.pack(side=tk.LEFT, padx=(5,10), pady=5)

# Frame for Combobox vehicle selection
vehicle_selection_frame = tk.Frame(top_frame)  # Creating a frame to hold the Combobox and its label
vehicle_selection_frame.pack(side=tk.LEFT, padx=5)

# Combobox vehicle selection
tk.Label(vehicle_selection_frame, text="Veículo").pack(side=tk.LEFT)
vehicle_selection_combobox = ttk.Combobox(vehicle_selection_frame, state="readonly", width=15)  # Adjust width as needed
vehicle_selection_combobox.pack(side=tk.LEFT, padx=(5, 0), pady=5)  # Add some padding for spacing between label and combobox

# Update the "Listar Veículos" button command to fetch vehicle data
list_vehicles_button.config(command=fetch_vehicle_data)

# Date pickers
tk.Label(top_frame, text="3. Início:").pack(side=tk.LEFT, padx=(10, 2), pady=5)
start_date_picker = DateEntry(top_frame, width=9, background='green', foreground='white', borderwidth=2)
start_date_picker.pack(side=tk.LEFT, padx=(0, 10), pady=5)

tk.Label(top_frame, text="4. Fim:").pack(side=tk.LEFT, padx=(10, 2), pady=5)
end_date_picker = DateEntry(top_frame, width=9, background='green', foreground='white', borderwidth=2)
end_date_picker.pack(side=tk.LEFT, padx=(0, 10), pady=5)

process_button = tk.Button(top_frame, text="5. Analisar", bg='green', command=process_data)
process_button.pack(side=tk.LEFT, padx=10, pady=5)

# RESULTADOS button
resultados_consumo_button = tk.Button(top_frame, text="6. Resultados", command=open_resultados_consumo_folder)
resultados_consumo_button.pack(side=tk.LEFT, padx=10, pady=5)

interrupt_button = tk.Button(top_frame, text="INTERROMPER", bg='orange', command=interrupt_process)
interrupt_button.pack(side=tk.LEFT, padx=10, pady=5)

# LIMPAR LOG button
clear_log_button = tk.Button(top_frame, text="LIMPAR LOG", command=clear_log)
clear_log_button.pack(side=tk.LEFT, padx=10, pady=5)

log_textbox = scrolledtext.ScrolledText(main_frame, bg="black", fg="white")
log_textbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

root.mainloop()