import tkinter as tk
from tkinter import ttk, scrolledtext
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
from datetime import datetime, timedelta
from matplotlib.ticker import MultipleLocator
import psycopg2
import psycopg2.extras
from configparser import ConfigParser
from tkcalendar import DateEntry
import threading
import os
import time
import subprocess
import sys

# Determine the application's path
application_path = os.path.dirname(os.path.abspath(__file__))

# Path to the Windows 'Downloads' folder
downloads_path = os.path.join(os.path.expanduser('~'), 'Downloads')
# Path for the 'resultados_tpms' folder within 'Downloads'
results_path = os.path.join(downloads_path, 'resultados_tpms')

# Check if 'resultados_tpms' exists, and create it if it doesn't
if not os.path.exists(results_path):
    os.makedirs(results_path)

def load_db_config(config_filename='config_tpms.ini'):
    config_file = os.path.join(application_path, config_filename)
    parser = ConfigParser()
    if not os.path.exists(config_file):
        raise FileNotFoundError(f"Configuration file not found: {config_file}")
    parser.read(config_file)
    return {param: parser.get('server', param) for param in parser.options('server')}

def log_to_textbox(text):
    app.text_box.insert(tk.END, text + "\n")
    app.text_box.see(tk.END)

def update_vehicle_combobox(vehicles):
    vehicle_plates = [plate for _, plate in vehicles]  # Extract just the plate names
    app.vehicle_combobox['values'] = vehicle_plates  # Update combobox values
    if vehicle_plates:
        app.vehicle_combobox.current(0)  # Set the first item as the current item
    # Store the vehicles data for later use
    app.vehicles_data = {plate: id for id, plate in vehicles}

def start_fetch_vehicle_data_thread():
    """Starts the fetch_vehicle_data function in a separate thread."""
    fetch_thread = threading.Thread(target=fetch_vehicle_data)
    fetch_thread.start()

def fetch_vehicle_data():
    """Fetches vehicle data from the database and updates the combobox with retries."""
    db_params = load_db_config()
    conn = None
    max_retries = 3  # Maximum number of retries
    retry_delay = 5  # Delay in seconds before retrying
    for attempt in range(max_retries):
        try:
            app.text_box.insert(tk.END, "Conectando ao banco de dados...\n")
            app.text_box.see(tk.END)
            # Attempt to connect with a timeout
            conn = psycopg2.connect(**db_params, connect_timeout=5)
            cursor = conn.cursor()
            app.text_box.insert(tk.END, "Conexão realizada com sucesso.\n")
            app.text_box.see(tk.END)
            cursor.execute("SELECT id, placa FROM scm_setera.tb_terminal WHERE ativo is true AND id_terminal_protocolo in (21) ORDER BY placa ASC")
            vehicles = cursor.fetchall()
            app.text_box.insert(tk.END, "Veículos listados com sucesso.\n")
            app.text_box.see(tk.END)
            # Update combobox in the main thread
            root.after(0, update_vehicle_combobox, vehicles)
            break  # Break out of the loop on success
        except psycopg2.OperationalError as e:
            if "timeout expired" in str(e):
                app.text_box.insert(tk.END, "Timeout ao conectar ao banco de dados. Tentando novamente...\n")
                app.text_box.see(tk.END)
                time.sleep(retry_delay)  # Wait before retrying
            else:
                app.text_box.insert(tk.END, f"Falha ao conectar ao banco de dados: {e}\n")
                app.text_box.see(tk.END)
                break  # Break on other operational errors
        except Exception as e:
            app.text_box.insert(tk.END, f"Erro ao listar veículos: {e}\n")
            app.text_box.see(tk.END)
            break  # Break on any other exception
        finally:
            if conn:
                conn.close()
                app.text_box.insert(tk.END, "Conexão com o banco de dados fechada.\n")
                app.text_box.see(tk.END)

class TPMSAnalysisApp:
    def __init__(self, master):
        self.master = master
        self.master.title("SETERA - Análise de TPMS")
        self.master.geometry("1100x600")
        self.master.resizable(False, False)
        self.vehicles_data = {}
        
        # Load and set the window icon
        self.master.iconbitmap(os.path.join(application_path, 'favicon.ico'))
        
        # Top frame for controls
        self.top_frame = tk.Frame(self.master)
        self.top_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # List vehicles button
        self.list_vehicles_button = tk.Button(self.top_frame, text="1. LISTAR VEÍCULOS", command=start_fetch_vehicle_data_thread)
        self.list_vehicles_button.pack(side=tk.LEFT, padx=(0, 5), pady=5)
        
        # Vehicle combobox
        self.vehicle_label = tk.Label(self.top_frame, text="Veículo:")
        self.vehicle_label.pack(side=tk.LEFT, padx=(10, 0))
        
        self.vehicle_combobox = ttk.Combobox(self.top_frame, width=15)
        self.vehicle_combobox.pack(side=tk.LEFT, padx=(0, 10), pady=5)

        # Date pickers
        self.start_date_label = tk.Label(self.top_frame, text="2. Início:")
        self.start_date_label.pack(side=tk.LEFT, padx=(10, 2), pady=5)
        self.start_date_picker = DateEntry(self.top_frame, width=9, background='darkblue', foreground='white', borderwidth=2)
        self.start_date_picker.pack(side=tk.LEFT, padx=(0, 10), pady=5)

        self.end_date_label = tk.Label(self.top_frame, text="3. Fim:")
        self.end_date_label.pack(side=tk.LEFT, padx=(10, 2), pady=5)
        self.end_date_picker = DateEntry(self.top_frame, width=9, background='darkblue', foreground='white', borderwidth=2)
        self.end_date_picker.pack(side=tk.LEFT, padx=(0, 10), pady=5)

        # Pressure Max label and entry box
        self.pressure_max_label = tk.Label(self.top_frame, text="4. Press Máx:")
        self.pressure_max_label.pack(side=tk.LEFT, padx=(10, 2), pady=5)
        self.pressure_max_entry = tk.Entry(self.top_frame, width=5)
        self.pressure_max_entry.pack(side=tk.LEFT, padx=(0, 10), pady=5)
        self.pressure_max_entry.insert(0, "140")

        # Temperature Max label and entry box
        self.temperature_max_label = tk.Label(self.top_frame, text="5. Temp Máx:")
        self.temperature_max_label.pack(side=tk.LEFT, padx=(10, 2), pady=5)
        self.temperature_max_entry = tk.Entry(self.top_frame, width=4)
        self.temperature_max_entry.pack(side=tk.LEFT, padx=(0, 10), pady=5)
        self.temperature_max_entry.insert(0, "95")

        # Process button
        self.process_button = tk.Button(self.top_frame, text="6. PROCESSAR", bg='orange', command=self.start_process_data_thread)
        self.process_button.pack(side=tk.LEFT, padx=10, pady=5)
        self.is_processing = False

        # Result button
        self.result_button = tk.Button(self.top_frame, text="7. RESULTADOS", bg='green', command=self.open_results_folder)
        self.result_button.pack(side=tk.LEFT, padx=10, pady=5)
        
        # Text box
        self.text_box = scrolledtext.ScrolledText(self.master, bg="black", fg="white")
        self.text_box.pack(expand=True, fill=tk.BOTH, padx=5, pady=(0, 5))

    def open_results_folder(self):
        # Determine the path to the 'results' folder within the user's Downloads folder
        results_path = os.path.join(os.path.expanduser('~'), 'Downloads', 'resultados_tpms')
        
        # Check if the folder exists before attempting to open it
        if not os.path.exists(results_path):
            log_to_textbox(f"A pasta '{results_path}' não existe.")
            return

        # Open the folder using the appropriate command based on the operating system
        if sys.platform == 'win32':
            # Windows
            os.startfile(results_path)
        elif sys.platform == 'darwin':
            # macOS
            subprocess.run(['open', results_path])
        else:
            # Linux and other Unix-like systems
            subprocess.run(['xdg-open', results_path])
        
    def start_process_data_thread(self):
        if not self.is_processing:
            self.is_processing = True
            self.process_button.config(state='disabled')  # Disable the button
            processing_thread = threading.Thread(target=self.process_data_wrapper)
            processing_thread.start()

    def process_data_wrapper(self):
        self.process_data()
        self.is_processing = False
        # Safely re-enable the button on the main thread
        self.master.after(0, lambda: self.process_button.config(state='normal'))

    def process_data(self):
        selected_vehicle = self.vehicle_combobox.get()
        start_date = self.start_date_picker.get_date().strftime('%Y-%m-%d 00:00:00.000')
        end_date = (self.end_date_picker.get_date() + timedelta(days=1)).strftime('%Y-%m-%d 23:59:59.999')

        # Fetch user-defined limits
        temperature_limit = int(self.temperature_max_entry.get())  # Convert to integer
        pressure_limit = int(self.pressure_max_entry.get())  # Convert to integer

        vehicle_id = self.vehicles_data.get(selected_vehicle)
        if not vehicle_id:
            log_to_textbox("Veículo não selecionado ou ID não encontrado.")
            app.text_box.see(tk.END)
            return

        db_params = load_db_config()
        max_retries = 3  # Maximum number of retries
        retry_delay = 5  # Delay in seconds before retrying
        for attempt in range(max_retries):
            try:
                log_to_textbox("Conectando ao banco de dados...")
                conn = psycopg2.connect(**db_params, connect_timeout=5)
                cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
                log_to_textbox("Conexão realizada com sucesso.")
                log_to_textbox(f"Terminal id = {vehicle_id}.")
                query = f"""SELECT mensagem FROM scm_setera.tb_terminal_mensagem_processada
                            WHERE id_terminal = {vehicle_id} AND mensagem like '%FR1,2,%'
                            AND data_recebimento_mensagem BETWEEN '{start_date}' AND '{end_date}'"""
                cursor.execute(query)
                data_strings = cursor.fetchall()

                parsed_data = []
                for row in data_strings:
                    parsed_data.extend(parse_telemetry_data(row['mensagem']))

                if parsed_data:
                    columns = ['DateTime', 'SensorID', 'Alarm', 'Pressure', 'Temperature']
                    parsed_df = pd.DataFrame(parsed_data, columns=columns)
                    parsed_df.sort_values(by=['SensorID', 'DateTime'], inplace=True)
                    
                    sensor_ids = parsed_df['SensorID'].unique()
                    # Assuming fetch_sensor_names is correctly implemented and db_params is correctly passed
                    sensor_names_mapping = fetch_sensor_names(sensor_ids, db_params)
                    
                    # Now parsed_df is ready to be used in plotting functions
                    save_sensor_plots(parsed_df, selected_vehicle, pressure_limit, temperature_limit, sensor_names_mapping)
                    save_combined_plots(parsed_df, 'temperature', selected_vehicle, temperature_limit, pressure_limit, sensor_names_mapping)
                    save_combined_plots(parsed_df, 'pressure', selected_vehicle, temperature_limit, pressure_limit, sensor_names_mapping)
                else:
                    log_to_textbox("Sem dados para esse terminal no período selecionado.")
                    break  # No data, exit loop
            except psycopg2.OperationalError as e:
                if "timeout expired" in str(e):
                    log_to_textbox("Timeout ao conectar ao banco de dados. Tentando novamente...")
                    time.sleep(retry_delay)  # Wait before retrying
                else:
                    log_to_textbox(f"Falha ao conectar ao banco de dados: {e}")
                    break  # Break on other operational errors
            except Exception as e:
                log_to_textbox(f"Falha ao requisitar dados: {e}")
                break  # Break on any other exception
            finally:
                if 'conn' in locals() and conn is not None:
                    conn.close()
                    log_to_textbox("Conexão com o banco de dados fechada.")

# Function to fetch sensor names
def fetch_sensor_names(sensor_ids, db_params):
    sensor_id_str = ",".join(f"'{sid}'" for sid in sensor_ids)  # Format sensor IDs for SQL query
    query = f"""SELECT s.codigo_sensor, pp.posicao_pneu
                FROM scm_setera.tb_veiculo_sensor vs
                INNER JOIN scm_setera.tb_sensor s ON vs.id_sensor = s.id AND s.ativo = true
                INNER JOIN scm_setera.tb_posicao_pneu pp ON vs.id_posicao_pneu = pp.id AND pp.ativo = true
                WHERE vs.ativo = true AND s.codigo_sensor IN ({sensor_id_str})
                ORDER BY vs.id_posicao_pneu ASC"""

    conn = psycopg2.connect(**db_params)
    cursor = conn.cursor()
    cursor.execute(query)
    result = cursor.fetchall()
    conn.close()

    return {sensor_id: sensor_name for sensor_id, sensor_name in result}


# Function to parse the telemetry data
def parse_telemetry_data(row):
    blocks = row.split(';')
    tpms_data = []

    for block in blocks:
        if block.startswith('DR') or block.startswith('DG') or block.startswith('DM'):
            elements = block.split(',')
            date_time = datetime.strptime(elements[1], '%y%m%d%H%M%S') - timedelta(hours=3)
            sensors = elements[2:]

            for i in range(0, len(sensors), 5):
                sensor_data = sensors[i:i+5]
                if len(sensor_data) == 5:
                    sensor_id = sensor_data[0]
                    alarm = int(sensor_data[1])
                    pressure = int(sensor_data[2])
                    temperature = int(sensor_data[3])
                    # Check if pressure and temperature are not equal to -1 before appending
                    #if pressure != -2 and temperature != -2:
                    tpms_data.append((date_time, sensor_id, alarm, pressure, temperature))

    return tpms_data

def save_sensor_plots(parsed_df, plate_name, pressure_limit, temperature_limit, sensor_names_mapping):
    sensor_ids = parsed_df['SensorID'].unique()

    for sensor_id in sensor_ids:
        fig, ax1 = plt.subplots(figsize=(10, 6))
        ax2 = ax1.twinx()
        sensor_df = parsed_df[parsed_df['SensorID'] == sensor_id]

        # Filter out '-1' values
        filtered_sensor_df = sensor_df[(sensor_df['Pressure'] != -1) & (sensor_df['Temperature'] != -1)]
        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
        plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45)

        # Horizontal dashed line for pressure and temperarture limits
        ax1.axhline(y=pressure_limit, color='blue', linestyle='--', label=f'Limite Pressão ({pressure_limit} PSI)')
        ax2.axhline(y=temperature_limit, color='green', linestyle='--', label=f'Limite Temp ({temperature_limit}°C)')

        sensor_name = sensor_names_mapping.get(sensor_id, sensor_id)
        ax1.set_title(f'Sensor {sensor_name}')

        # Plotting pressure and temperature
        ax1.plot(filtered_sensor_df['DateTime'], filtered_sensor_df['Pressure'], 'b-', label='Pressão(PSI)')
        ax2.plot(filtered_sensor_df['DateTime'], filtered_sensor_df['Temperature'], 'g-', label='Temperatura(°C)')

        # Marking alarms on the correct line
        pressure_alarms = filtered_sensor_df[filtered_sensor_df['Alarm'] == 1]
        temperature_alarms = filtered_sensor_df[filtered_sensor_df['Alarm'] == 2]
        ax1.plot(pressure_alarms['DateTime'], pressure_alarms['Pressure'], 'ro', label='Alarme Pressão')  # Red for pressure alarm
        ax2.plot(temperature_alarms['DateTime'], temperature_alarms['Temperature'], 'mo', label='Alarme Temperatura')  # Purple for temperature alarm

        # Filter out '-1' values for calculations
        valid_pressure_df = sensor_df[sensor_df['Pressure'] != -1]
        valid_temperature_df = sensor_df[sensor_df['Temperature'] != -1]

        # Calculate max and min values excluding '-1'
        max_pressure = valid_pressure_df['Pressure'].max() if not valid_pressure_df.empty else 'N/A'
        min_pressure = valid_pressure_df['Pressure'].min() if not valid_pressure_df.empty else 'N/A'
        max_temp = valid_temperature_df['Temperature'].max() if not valid_temperature_df.empty else 'N/A'
        min_temp = valid_temperature_df['Temperature'].min() if not valid_temperature_df.empty else 'N/A'

        # Annotate max and min pressure excluding '-1' values
        ax1.annotate(f'P.Máx: {max_pressure}\nP.Mín: {min_pressure}', xy=(0.015, 0.97), xycoords='axes fraction', 
                    verticalalignment='top', bbox=dict(boxstyle='round,pad=0.5', fc='yellow', alpha=0.5), fontsize='small')

        # Annotate max and min temperature excluding '-1' values
        ax2.annotate(f'T.Máx: {max_temp}\nT.Mín: {min_temp}', xy=(0.015, 0.87), xycoords='axes fraction', 
                    verticalalignment='top', bbox=dict(boxstyle='round,pad=0.5', fc='yellow', alpha=0.5), fontsize='small')

        ax1.set_xlabel('Hora')
        ax1.set_ylabel('Pressão(PSI)', color='b')
        ax2.set_ylabel('Temp(°C)', color='g')
        ax1.set_title(f'Sensor {sensor_name}')
        ax1.set_ylim(0, 150)  # Pressure scale
        ax2.set_ylim(10, 100)  # Temperature scale

        lines, labels = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines + lines2, labels + labels2, loc='lower right', fontsize='small')

        # Adjust x-axis to display more labels
        ax1.xaxis.set_major_locator(mdates.AutoDateLocator(maxticks=30))

        # Add grid lines
        ax1.grid(True, color='lightgray', linestyle='-', linewidth=0.5)
        ax2.grid(True, color='lightgray', linestyle='-', linewidth=0.5)

        # Save the plot as a high-resolution JPEG
        plt.tight_layout()
        file_name = os.path.join(results_path, f"{plate_name}_sensor_{sensor_name}.jpg")
        plt.savefig(file_name, format='jpg', dpi=300)
        plt.close(fig)

def save_combined_plots(parsed_df, plot_type, plate_name, temperature_limit, pressure_limit, sensor_names_mapping):
    fig, ax = plt.subplots(figsize=(10, 6))
    sensor_ids = parsed_df['SensorID'].unique()

    # Determine the absolute lowest and highest values
    valid_values_df = parsed_df[(parsed_df['Pressure'] != -1) & (parsed_df['Temperature'] != -1)]
    if plot_type == 'temperature':
        ax.yaxis.set_major_locator(MultipleLocator(5))
        all_values = valid_values_df['Temperature']
    else:  # 'pressure'
        ax.yaxis.set_major_locator(MultipleLocator(2))
        all_values = valid_values_df['Pressure']
    min_value = all_values.min()
    max_value = all_values.max()

    for sensor_id in sensor_ids:
        sensor_df = valid_values_df[valid_values_df['SensorID'] == sensor_id]
        sensor_name = sensor_names_mapping.get(sensor_id, sensor_id)  # Fallback to sensor_id if not found
        if plot_type == 'temperature':
            ax.plot(sensor_df['DateTime'], sensor_df['Temperature'], label=f'{sensor_name}')
        elif plot_type == 'pressure':
            ax.plot(sensor_df['DateTime'], sensor_df['Pressure'], label=f'{sensor_name}')

    ax.set_xlabel('Hora')
    # Translated labels for temperature and pressure
    translated_label = 'Temperatura(°C)' if plot_type == 'temperature' else 'Pressão(PSI)'
    ax.set_ylabel(translated_label)
    translated_title = 'Temperatura dos Pneus' if plot_type == 'temperature' else 'Pressão dos Pneus'
    ax.set_title(translated_title)
    ax.legend(loc='upper left', fontsize='small')
    ax.xaxis.set_major_locator(mdates.AutoDateLocator(maxticks=40))
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)

    # Add grid lines
    ax.grid(True, color='lightgray', linestyle='-', linewidth=0.5)

    # Add horizontal dashed red line for the limit
    limit = temperature_limit if plot_type == 'temperature' else pressure_limit
    ax.axhline(y=limit, color='red', linestyle='--', label=f'Limite ({limit})')

    # Add label for absolute lowest and highest values
    unit = "°C" if plot_type == 'temperature' else "PSI"
    ax.annotate(f'Mín {min_value} {unit}\nMáx {max_value} {unit}', xy=(0.25, 0.97), xycoords='axes fraction', 
                horizontalalignment='right', verticalalignment='top', 
                bbox=dict(boxstyle='round,pad=0.5', fc='yellow', alpha=0.5), fontsize='small')

    # Save the plot as a high-resolution JPEG
    plt.tight_layout()
    file_name = os.path.join(results_path, f"{plate_name}_{plot_type}.jpg")
    plt.savefig(file_name, format='jpg', dpi=300)
    plt.close(fig)

if __name__ == "__main__":
    root = tk.Tk()
    app = TPMSAnalysisApp(root)  # Pass the 'root' to your application class
    root.mainloop()
