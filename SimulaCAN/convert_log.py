import csv
import os

# --- Configuration ---

# Input and Output file names
INPUT_CSV_FILE = '00000002_CAN.csv'
OUTPUT_TXT_FILE = 'sim_log_injected_final.txt'

# --- PGNs to be Injected ---
# 'can_id_hex': The full 29-bit CAN ID to use for the broadcast.
# 'repetition_ms': The standard broadcast rate in milliseconds.
# 'payload_template': The 8-byte data payload. Unused bytes are 00.
#                     Parameter bytes are set to FF as placeholders.

PGNS_TO_INJECT = {
    'Total_Hours': {
        'can_id_hex': '18FEE500',
        'repetition_ms': 1000, # On Request PGN, 1s is a good rate for simulation
        'payload_template': 'FFFFFFFF00000000' # SPN 247 is bytes 1-4
    },
    'Accel_Pedal': {
        'can_id_hex': '0CF00300',
        'repetition_ms': 50,
        'payload_template': '00FF000000000000' # SPN 91 is byte 2
    },
    'Total_Fuel': {
        'can_id_hex': '18FEE900',
        'repetition_ms': 1000, # On Request PGN, 1s is a good rate for simulation
        'payload_template': '00000000FFFFFFFF' # SPN 250 is bytes 5-8
    },
    'Turbo_Pressure': {
        'can_id_hex': '18FEF600',
        'repetition_ms': 500,
        'payload_template': '00FF000000000000' # SPN 102 is byte 2
    },
    'Total_Distance': {
        'can_id_hex': '18FEE000',
        'repetition_ms': 500, # On Request PGN, 1s is a good rate for simulation
        'payload_template': '00000000FFFFFFFF' # SPN 245 is bytes 5-8
    }
}

# --- Output File Header and Footer ---
OUTPUT_HEADER = """date Mon Jun 09 08:32:13.606 2025
base hex  timestamps absolute
internal events logged
Begin Triggerblock Thu Jan 01 00:10:30.432 1970
 0.000000 Start of measurement
"""
OUTPUT_FOOTER = "End TriggerBlock\n"

def parse_custom_timestamp(ts_str):
    """
    Correctly converts the custom dot-separated timestamp to a standard float.
    Example: '1.618.222.004.012.500' becomes 1618222004.012500
    """
    clean_ts_str = ts_str.replace('.', '')
    # The first 10 digits are the seconds (Unix epoch), the rest are the fraction.
    if len(clean_ts_str) > 10:
        return float(f"{clean_ts_str[:10]}.{clean_ts_str[10:]}")
    else:
        return float(clean_ts_str)

def format_output_line(timestamp_sec, can_id, dlc, data_bytes, is_extended=False):
    """Formats a single line for the output TXT file with proper extended frame support."""
    # ✅ ADD 'x' SUFFIX FOR EXTENDED FRAMES (python-can ASC format requirement)
    can_id_formatted = f"{can_id}x" if is_extended else can_id
    return f" {timestamp_sec:0.6f} 1  {can_id_formatted:<9s} Rx   d {dlc} {data_bytes}\n"

def convert_and_inject():
    """
    Reads the source CSV, converts it to the target TXT format,
    and injects missing PGN data at standard intervals.
    """
    if not os.path.exists(INPUT_CSV_FILE):
        print(f"Error: Input file '{INPUT_CSV_FILE}' not found.")
        return

    print(f"Starting conversion of '{INPUT_CSV_FILE}'...")

    # Initialize trackers
    first_timestamp = None
    # Start at -1 to ensure timers can fire at time 0 or shortly after
    last_injection_time_ms = {pgn_name: -1.0 for pgn_name in PGNS_TO_INJECT}

    with open(INPUT_CSV_FILE, 'r', newline='') as infile, open(OUTPUT_TXT_FILE, 'w') as outfile:
        outfile.write(OUTPUT_HEADER)

        reader = csv.reader(infile, delimiter=';')
        header = next(reader)  # Read and store the header

        try:
            data_bytes_index = header.index('DataBytes')
        except ValueError:
            print("Error: 'DataBytes' column not found in CSV header. Assuming index 11.")
            data_bytes_index = 11
        
        # Get total lines for progress indicator
        total_lines = sum(1 for line in infile)
        infile.seek(0) # Reset file pointer
        next(reader) # Skip header again

        for i, row in enumerate(reader):
            if not row: continue

            try:
                # --- 1. Parse the original log line ---
                current_timestamp = parse_custom_timestamp(row[0])
                can_id = row[2]
                ide = int(row[3])  # ✅ READ IDE FIELD: 1=Extended, 0=Standard
                dlc = row[4]
                data_bytes = row[data_bytes_index]
                
                # ✅ DETERMINE IF FRAME IS EXTENDED
                is_extended = (ide == 1)

                # --- 2. Establish time base on the first valid frame ---
                if first_timestamp is None:
                    first_timestamp = current_timestamp

                current_relative_time_ms = (current_timestamp - first_timestamp) * 1000

                # --- 3. Inject new frames if their time has come ---
                for pgn_name, pgn_info in PGNS_TO_INJECT.items():
                    repetition_ms = pgn_info['repetition_ms']
                    while current_relative_time_ms >= last_injection_time_ms[pgn_name] + repetition_ms:
                        injection_time_ms = last_injection_time_ms[pgn_name] + repetition_ms
                        
                        template = pgn_info['payload_template']
                        injected_data = ' '.join(template[i:i+2] for i in range(0, len(template), 2))
                        
                        # ✅ CHECK IF INJECTED FRAME IS EXTENDED (J1939 frames are typically extended)
                        injection_can_id = pgn_info['can_id_hex']
                        injection_is_extended = int(injection_can_id, 16) > 0x7FF
                        
                        injected_line = format_output_line(
                            injection_time_ms / 1000.0,
                            injection_can_id,
                            '8',
                            injected_data,
                            injection_is_extended
                        )
                        outfile.write(injected_line)
                        
                        last_injection_time_ms[pgn_name] = injection_time_ms

                # --- 4. Write the original frame to the output file ---
                formatted_data_bytes = ' '.join(data_bytes[i:i+2] for i in range(0, len(data_bytes), 2))
                
                # ✅ USE EXTRACTED EXTENDED FRAME INFORMATION
                original_line = format_output_line(
                    current_relative_time_ms / 1000.0,
                    can_id,
                    dlc,
                    formatted_data_bytes,
                    is_extended
                )
                outfile.write(original_line)
                
                # Progress indicator
                if (i + 1) % 500 == 0:
                    print(f"  Processed {i + 1} of {total_lines} lines...")

            except (IndexError, ValueError, TypeError) as e:
                print(f"Skipping malformed row: {row} | Error: {e}")
                continue

        outfile.write(OUTPUT_FOOTER)

    print(f"\nConversion complete. Output saved to '{OUTPUT_TXT_FILE}'.")

# --- Run the script ---
if __name__ == "__main__":
    convert_and_inject()