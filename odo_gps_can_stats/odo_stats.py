#!/usr/bin/env python3
import psycopg2
import configparser
from datetime import datetime
import sys
import pandas as pd
import logging
import os
import matplotlib.pyplot as plt
import seaborn as sns

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

def read_config():
    """Read database configuration from config.ini"""
    try:
        config = configparser.ConfigParser()
        config.read('config.ini')
        return {
            'host': config['server']['host'],
            'port': config['server']['port'],
            'database': config['server']['database'],
            'user': config['server']['user'],
            'password': config['server']['password']
        }
    except Exception as e:
        logging.error(f"Error reading config file: {e}")
        sys.exit(1)

def connect_to_db(db_params):
    """Establish database connection"""
    try:
        logging.info("Connecting to database...")
        conn = psycopg2.connect(**db_params)
        logging.info("Successfully connected to database")
        return conn
    except Exception as e:
        logging.error(f"Error connecting to database: {e}")
        sys.exit(1)

def get_vehicle_plate(conn, terminal_id):
    """Get vehicle plate number from terminal ID"""
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT placa
            FROM db_setera.scm_setera.tb_terminal
            WHERE id = %s
        """, (terminal_id,))
        result = cursor.fetchone()
        cursor.close()
        return result[0] if result else f"Unknown-{terminal_id}"
    except Exception as e:
        logging.error(f"Error getting plate for terminal {terminal_id}: {e}")
        return f"Unknown-{terminal_id}"

def extract_mileage(message):
    """Extract GPS and CANBUS mileage from message string"""
    try:
        # GPS mileage is 15th field (in meters)
        fields = message.split(',')
        if len(fields) >= 15 and fields[14].strip():  # Check if field exists and is not empty
            gps_km = float(fields[14].strip()) / 1000.0  # Convert to km
        else:
            logging.warning(f"Invalid GPS mileage field in message: {message}")
            return None, None

        # Find FR1,2 section and extract CANBUS mileage
        if 'FR1,2,' not in message:
            logging.warning(f"FR1,2 not found in message: {message}")
            return None, None

        fr1_parts = message.split('FR1,2,')[1].split(',')
        if len(fr1_parts) >= 1 and fr1_parts[0].strip():  # Check if field exists and is not empty
            try:
                canbus_km = float(fr1_parts[0].strip())
                return gps_km, canbus_km
            except ValueError:
                logging.warning(f"Invalid CANBUS mileage value: {fr1_parts[0]}")
                return None, None
        else:
            logging.warning("CANBUS mileage field not found or empty")
            return None, None

    except Exception as e:
        logging.error(f"Error parsing message: {message}")
        logging.error(f"Error details: {e}")
        return None, None

def create_distribution_plot(df):
    """Create and save error distribution plot"""
    try:
        plt.figure(figsize=(10, 6))
        sns.histplot(data=df, x='Erro %', bins=20, kde=True)
        plt.title('Distribuição dos Erros de Hodômetro (Valores Negativos)')
        plt.xlabel('Erro (%)')
        plt.ylabel('Frequência')
        
        # Add vertical line at mean
        mean_error = df['Erro %'].mean()
        plt.axvline(x=mean_error, color='r', linestyle='--', label=f'Média: {mean_error:.2f}%')
        plt.legend()
        
        # Save plot with same timestamp as Excel file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        plot_file = f'distribution_{timestamp}.png'
        plt.savefig(plot_file)
        plt.close()
        
        logging.info(f"Distribution plot saved to {plot_file}")
    except Exception as e:
        logging.error(f"Error creating distribution plot: {e}")

def get_terminal_data(conn, terminal_ids):
    """Fetch and process data for given terminal IDs"""
    results = []
    cursor = conn.cursor()

    for terminal_id in terminal_ids:
        try:
            logging.info(f"Processing terminal ID: {terminal_id}")

            # Get vehicle plate
            plate = get_vehicle_plate(conn, terminal_id)

            # Get latest FR1,2 message
            cursor.execute("""
                SELECT data_recebimento_mensagem, mensagem 
                FROM scm_setera.tb_terminal_mensagem_processada 
                WHERE id_terminal = %s 
                AND mensagem LIKE '%%FR1,2%%' 
                ORDER BY data_recebimento_mensagem DESC 
                LIMIT 1
            """, (terminal_id,))
            latest = cursor.fetchone()

            if not latest:
                logging.warning(f"No FR1,2 messages found for terminal {terminal_id}")
                continue

            # Get oldest FR1,2 message
            cursor.execute("""
                SELECT data_recebimento_mensagem, mensagem 
                FROM scm_setera.tb_terminal_mensagem_processada 
                WHERE id_terminal = %s 
                AND mensagem LIKE '%%FR1,2%%' 
                ORDER BY data_recebimento_mensagem ASC 
                LIMIT 1
            """, (terminal_id,))
            oldest = cursor.fetchone()

            if not oldest:
                continue

            # Extract mileage data
            latest_gps, latest_canbus = extract_mileage(latest[1])
            oldest_gps, oldest_canbus = extract_mileage(oldest[1])

            if None in (latest_gps, latest_canbus, oldest_gps, oldest_canbus):
                logging.warning(f"Could not extract mileage data for terminal {terminal_id}")
                continue

            # Calculate differences and error percentage
            gps_diff = latest_gps - oldest_gps
            canbus_diff = latest_canbus - oldest_canbus
            
            # Skip if difference is less than 5000 km
            if gps_diff < 5000 or canbus_diff < 5000:
                logging.warning(f"Terminal {terminal_id} skipped: Insufficient mileage difference (GPS: {round(gps_diff, 3)}km, CAN: {round(canbus_diff, 3)}km)")
                continue
            
            if canbus_diff == 0:
                error_pct = 0
            else:
                error_pct = ((gps_diff - canbus_diff) / canbus_diff) * 100

            # Skip if error percentage is positive or outside acceptable range
            if error_pct > 0:
                logging.warning(f"Terminal {terminal_id} skipped: Positive error percentage ({round(error_pct, 3)}%)")
                continue
                
            if abs(error_pct) > 15:
                logging.warning(f"Terminal {terminal_id} skipped: Error percentage ({round(error_pct, 3)}%) exceeds ±15% threshold")
                continue

            # Calculate days between readings
            days_diff = (latest[0] - oldest[0]).days

            results.append({
                'Placa': plate,
                'Dias': days_diff,
                'Diferença GPS (km)': round(gps_diff, 3),
                'Diferença CAN (km)': round(canbus_diff, 3),
                'Erro %': round(error_pct, 3)
            })

        except Exception as e:
            logging.error(f"Error processing terminal {terminal_id}: {e}")
            continue

    cursor.close()
    return results

def save_to_excel(results):
    """Save results to Excel file with formatting"""
    try:
        if not results:
            logging.warning("No results to save to Excel")
            return
        
        # Create DataFrame
        df = pd.DataFrame(results)
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f'results_{timestamp}.xlsx'
        
        # Create distribution plot
        create_distribution_plot(df)
        
        # Create Excel writer with context manager
        with pd.ExcelWriter(output_file, engine='xlsxwriter') as writer:
            # Write the dataframe to Excel
            df.to_excel(writer, sheet_name='Análise de Hodômetro', index=False)
            
            # Get workbook and worksheet objects
            workbook = writer.book
            worksheet = writer.sheets['Análise de Hodômetro']
            
            # Add formats
            header_format = workbook.add_format({
                'bold': True,
                'text_wrap': True,
                'valign': 'vcenter',
                'bg_color': '#D3D3D3',
                'border': 1
            })
            
            # Format for numbers with 3 decimal places
            number_format = workbook.add_format({
                'num_format': '#,##0.000',
                'border': 1
            })
            
            # Format for percentages
            percent_format = workbook.add_format({
                'num_format': '#,##0.000"%"',
                'border': 1
            })
            
            # Format for integers
            integer_format = workbook.add_format({
                'num_format': '#,##0',
                'border': 1
            })
            
            # Set column widths and formats
            worksheet.set_column('A:A', 15)          # Placa
            worksheet.set_column('B:B', 10, integer_format)  # Dias
            worksheet.set_column('C:D', 18, number_format)   # Diferenças
            worksheet.set_column('E:E', 15, percent_format)  # Erro %
            
            # Format headers
            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_format)
            
            # Add average error at the bottom
            last_row = len(df) + 2
            avg_error = df['Erro %'].mean()
            worksheet.write(last_row, 0, 'Erro Médio %', header_format)
            worksheet.write(last_row, 1, avg_error, percent_format)
            
        logging.info(f"Results saved to {output_file}")
        
    except Exception as e:
        logging.error(f"Error saving to Excel: {e}")

def main():
    # Terminal IDs to process
    terminal_ids = [16427,16300,16254,16433,16316,16245,16291,16307,16309,16285,16252,16253,16259,16393,16270,16419,16305,16383,16278,16396,16494,16391,16552,16436,16407,16400,16318,16349,16287,16432,16281,16256,16501,16332,16551,16384,16264,16690,16429,16266,16413,16277,16686,16275,16299,16313,16478,16482,16292,16365,16260,16327,17257,16483,16249,16272,16726,16619,16265,16312,16481,16289,16248,16632,16636,16642,16640,16261,16398,16370,16375,16414,16348,16369,16355,16363,16353,16660,16725,16356,16669,16727,16677,16668,16505,16459,16360,16500,16702,16723,16655,16599,16605,16518,16358,16530,16534,16571,16662,16503,16622,16467,16469,16431,16659,16423,16342,16453,16443,16422,16456,16458,16525,16330,16532,16351,16572,16380,16315,16341,16665,16484,16388,16717,16549,16598,16623,16732,16381,16573,16649,16336,16508,16547,16674,16504,16335,16506,16692,16521,16575,16626,16542,16558,16650,16576,16509,16625,16589,16519,16577,16522,16603,16528,16510,16516,16529,16627,16527,16601,16498,16540,16445,16596,16585,16587,16567,16446,16556,16564,16569,16653,16582,16389,16562,16708,16462,16455,16466,16595,16583,16730,16465,16611,16705,16610,16612,16729,16696,16733,16681,16609,16704,16680,16618,16614,16593,16617,16616,16368,16471,16475,16594,16678,16302,16377,16474,16493,16276,17127,16735,16477,17124,16246,17128,17126,16294,17136,17129,16658,16545,17144,17231,17243,17242,16687,17137,17253,17252,17251,17256,16641,16357,17260,17258,16447,16563,16392,17262,17265,17279,17280,17287,16250,17274,16269,17264,16395,17277,17250,17297,16274,17404,17408,17407,17298,17532,16652,16661,16350,16373,17293,17548,17553,17559,17557,17585,17589,16268,17699,17702,17722,17721,17724,17723,17725,17726,17730,17692,17733,17738,17732,17564,16533,17746]  # Add more IDs as needed

    # Read configuration and connect to database
    db_params = read_config()
    conn = connect_to_db(db_params)

    try:
        # Get and process data
        results = get_terminal_data(conn, terminal_ids)
        
        if results:
            # Save results to Excel
            save_to_excel(results)
            logging.info(f"Successfully processed {len(results)} terminals")
        else:
            logging.warning("No valid results found after applying filters")

    except Exception as e:
        logging.error(f"Error in main execution: {e}")

    finally:
        # Close database connection
        logging.info("Closing database connection")
        conn.close()

if __name__ == "__main__":
    main()