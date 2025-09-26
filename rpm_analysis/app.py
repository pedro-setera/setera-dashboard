import os
import configparser
import psycopg2
from flask import Flask, render_template, jsonify, request
from datetime import datetime, timedelta
import logging
from collections import Counter
import argparse
import webbrowser
import threading
import time

app = Flask(__name__)

# Global database connection cache
_db_connection = None
_db_connection_time = None
CONNECTION_TIMEOUT = 300  # 5 minutes

# Configure logging
# When running without console, log to file instead
log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rpm_analysis.log')
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()  # Still try console if available
    ]
)

# Simplified path determination for portable Python environment
application_path = os.path.dirname(os.path.abspath(__file__))
# Dynamically build the path to the configuration file
config_file_path = os.path.join(application_path, 'config.ini')

def load_config():
    """Load database and alarm configuration from config.ini file."""
    config = configparser.ConfigParser()
    config.read(config_file_path)
    return {
        'server': config['server'],
        'alarms': dict(config['alarms'])
    }

def connect_to_database(db_params, max_retries=3, retry_delay=2):
    """Establish a connection to the PostgreSQL database with retry logic."""
    for attempt in range(max_retries):
        try:
            logging.info(f"Attempting to connect to database (attempt {attempt + 1}/{max_retries})...")

            # Add connection timeout for faster failure detection
            db_params_with_timeout = dict(db_params)
            db_params_with_timeout['connect_timeout'] = 10

            conn = psycopg2.connect(**db_params_with_timeout)

            # Test the connection
            cursor = conn.cursor()
            cursor.execute("SELECT 1;")
            cursor.close()

            logging.info(f"Successfully connected to database on attempt {attempt + 1}")
            return conn

        except (Exception, psycopg2.Error) as error:
            logging.warning(f"Database connection attempt {attempt + 1} failed: {error}")

            if attempt < max_retries - 1:  # Don't sleep on last attempt
                logging.info(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
                retry_delay *= 1.5  # Exponential backoff
            else:
                logging.error(f"Failed to connect to database after {max_retries} attempts")

    return None

def get_cached_connection():
    """Get cached database connection or create a new one if needed."""
    global _db_connection, _db_connection_time

    # Check if we have a valid cached connection
    if _db_connection is not None and _db_connection_time is not None:
        # Check if connection is still fresh (within timeout)
        if time.time() - _db_connection_time < CONNECTION_TIMEOUT:
            try:
                # Test the connection
                cursor = _db_connection.cursor()
                cursor.execute("SELECT 1;")
                cursor.close()
                return _db_connection
            except (Exception, psycopg2.Error):
                logging.warning("Cached connection is invalid, creating new connection")
                _db_connection = None
                _db_connection_time = None

    # Create new connection
    logging.info("Creating new database connection...")
    config_data = load_config()
    new_conn = connect_to_database(config_data['server'])

    if new_conn:
        _db_connection = new_conn
        _db_connection_time = time.time()
        logging.info("Database connection cached successfully")

    return new_conn

def fetch_terminals(conn):
    """Fetch list of terminals from the database."""
    logging.info("Fetching terminals from the database...")
    cursor = conn.cursor()
    query = """
    SELECT id, placa
    FROM scm_setera.tb_terminal
    WHERE ativo is true
    AND tracker_model_id in(3,4,7)
    ORDER BY placa ASC
    """
    cursor.execute(query)
    terminals = cursor.fetchall()
    cursor.close()
    logging.info(f"Fetched {len(terminals)} terminals from the database.")
    return [{'id': id, 'placa': placa} for id, placa in terminals]

def fetch_data(conn, terminal_id, start_time, end_time=None):
    """Execute query and fetch data from the database."""
    logging.info(f"Fetching data from the database for terminal {terminal_id} starting from {start_time}")
    if end_time:
        logging.info(f"Up to {end_time}")
    
    cursor = conn.cursor()
    query = """
    SELECT mensagem
    FROM scm_setera.tb_terminal_mensagem_processada
    WHERE id_terminal = %s
    AND data_recebimento_mensagem > %s
    """
    params = [terminal_id, start_time]

    if end_time:
        query += " AND data_recebimento_mensagem <= %s"
        params.append(end_time)

    query += """
    ORDER BY data_recebimento_mensagem ASC
    """
    
    cursor.execute(query, params)
    data = cursor.fetchall()
    cursor.close()
    logging.info(f"Fetched {len(data)} records from the database.")
    return data

def parse_data(data, alarm_config):
    """Parse the obtained data strings and extract the necessary information."""
    parsed_data = []
    alarm_codes = []
    specific_alarms = []
    max_speed = 0
    max_rpm = 0

    alarm_mapping = {
        '53': 'Entrou',
        '58': 'Saiu',
        '104': 'Cerca',
        '112': 'RPM',
        '101': 'Velocidade',
        '109': 'Abastecimento',
        '108': 'Furto Diesel'
    }

    for index, row in enumerate(data):
        try:
            message = row[0]
            logging.debug(f"Processing message {index}: {message}")
            
            # Split the message into all fields
            fields = message.split(',')
            
            if len(fields) < 6:
                logging.warning(f"Skipping message with insufficient fields: {message}")
                continue

            try:
                # Find the date/time field (it should start with '25' for year 2025)
                date_time_field = next(field for field in fields if field.startswith('25'))
                
                # Parse date/time, assuming year is always 2025
                date_time = datetime.strptime(date_time_field, '%y%m%d%H%M%S')
                date_time = date_time.replace(year=2025)
                
                # No need to adjust for Brazil time zone as the time is already in local time
                
            except (StopIteration, ValueError):
                logging.warning(f"Invalid date/time format in message: {message}")
                continue

            # Extract alarm code (4th field, index 3)
            alarm_code = fields[3]
            logging.debug(f"Alarm code: {alarm_code}")
            
            if alarm_code != '0':
                alarm_codes.append(alarm_code)
                if alarm_code in alarm_mapping:
                    specific_alarms.append({
                        'date_time': date_time.isoformat() + "Z",
                        'code': alarm_code,
                        'label': alarm_mapping[alarm_code]
                    })
            
            # Initialize FR1 data
            odometer = None
            fuel_consumption = None
            rpm_eco_time = None
            speed = 0
            rpm = 0

            # Process FR1 data if present
            fr1_index = message.find('FR1')
            if fr1_index != -1:
                logging.debug("Processing FR1 data")
                fr1_fields = message[fr1_index:].split(',')
                
                try:
                    if len(fr1_fields) > 2:
                        odometer = float(fr1_fields[2]) if fr1_fields[2] else None
                    if len(fr1_fields) > 3:
                        fuel_consumption = float(fr1_fields[3]) if fr1_fields[3] else None
                    if len(fr1_fields) > 23:
                        rpm_eco_time = float(fr1_fields[23]) if fr1_fields[23] else None
                    
                    # Extract speed and RPM
                    if len(fr1_fields) > 7:
                        speed = float(fr1_fields[6]) if fr1_fields[6] else 0.0
                        rpm = float(fr1_fields[7]) if fr1_fields[7] else 0.0
                except ValueError as e:
                    logging.warning(f"Error parsing FR1 data: {e}. Using default values.")

            # Update max speed and RPM
            max_speed = max(max_speed, speed)
            max_rpm = max(max_rpm, rpm)

            # Add data point
            parsed_data.append({
                'date_time': date_time.isoformat() + "Z",
                'odometer': odometer,
                'fuel_consumption': fuel_consumption,
                'rpm_eco_time': rpm_eco_time,
                'event': alarm_mapping.get(alarm_code)
            })

        except Exception as e:
            logging.error(f"Error processing message: {e}")
            logging.error(f"Problematic message: {message}")
            continue

    process_alarm_codes(alarm_codes, alarm_config)
    print_max_speed_and_rpm(max_speed, max_rpm)
    return {
        'data': parsed_data,
        'specific_alarms': specific_alarms,
        'max_speed': round(max_speed, 1),
        'max_rpm': round(max_rpm)
    }

def process_alarm_codes(alarm_codes, alarm_config):
    """Process and print alarm names with their occurrences."""
    alarm_counter = Counter(alarm_codes)
    sorted_alarms = sorted(alarm_counter.items(), key=lambda x: int(x[0]))
    
    print("Alarms (Name: Occurrences):")
    for code, count in sorted_alarms:
        alarm_name = alarm_config.get(code, f"Unknown Alarm (Code: {code})")
        print(f"{alarm_name}: {count}")

def print_max_speed_and_rpm(max_speed, max_rpm):
    """Print maximum speed and RPM."""
    print(f"Maximum speed in the period: {max_speed}")
    print(f"Maximum RPM in the period: {max_rpm}")

@app.route('/loading')
def loading():
    """Serve the loading page"""
    logging.info("Serving loading page")
    return render_template('loading.html')

@app.route('/health')
def health():
    """Simple health check endpoint that doesn't require database"""
    return jsonify({'status': 'alive', 'message': 'Flask server is running'})

@app.route('/check_ready')
def check_ready():
    """Simple endpoint to check if server is ready"""
    logging.info("Server readiness check")
    conn = get_cached_connection()
    if conn:
        return jsonify({'status': 'ready', 'message': 'Server is ready'})
    else:
        return jsonify({'status': 'not_ready', 'message': 'Database connection failed'}), 503

@app.route('/')
def index():
    logging.info("Serving index.html")
    conn = get_cached_connection()
    if conn:
        terminals = fetch_terminals(conn)
        return render_template('index.html', terminals=terminals)
    else:
        return "Error connecting to the database", 500

@app.route('/get_data')
def get_data():
    logging.info("Received data request")
    terminal_id = request.args.get('terminal_id')
    start_time = request.args.get('start_time')
    end_time = request.args.get('end_time')

    if not terminal_id or not start_time:
        return jsonify({'error': 'Missing terminal_id or start_time parameter'}), 400

    config = load_config()
    conn = get_cached_connection()
    if conn:
        try:
            data = fetch_data(conn, terminal_id, start_time, end_time)
            parsed_data = parse_data(data, config['alarms'])
            logging.info("Data processed and returned successfully")
            return jsonify(parsed_data)
        except Exception as e:
            logging.error(f"Error processing data: {e}")
            return jsonify({'error': 'Error processing data'}), 500
    else:
        return jsonify({'error': 'Unable to connect to the database'}), 500

def open_browser(port):
    """Open Chrome browser to the localhost URL after a short delay."""
    time.sleep(2)  # Wait 2 seconds for the server to start
    url = f"http://localhost:{port}"
    try:
        # Try to open with Chrome specifically
        webbrowser.get('chrome').open_new_tab(url)
    except webbrowser.Error:
        # Fallback to default browser if Chrome is not available
        webbrowser.open_new_tab(url)

if __name__ == '__main__':
    # Default to port 5004 if no argument provided
    parser = argparse.ArgumentParser(description='Run the Flask app on a specified port.')
    parser.add_argument('port', type=int, nargs='?', default=5004, help='Port number to run the app on (default: 5004)')
    args = parser.parse_args()

    # Log instead of print (works even without console)
    logging.info(f"Starting Flask server on port {args.port}...")
    logging.info("Server starting... Browser will be opened by dashboard.")

    # Run Flask without debug mode when no console (debug mode requires console output)
    import sys
    debug_mode = hasattr(sys, 'ps1') or sys.stderr.isatty()

    try:
        app.run(debug=debug_mode, port=args.port, use_reloader=False)
    finally:
        # Clean up database connection on shutdown
        if _db_connection:
            try:
                _db_connection.close()
                logging.info("Database connection closed on shutdown")
            except Exception as e:
                logging.warning(f"Error closing database connection: {e}")