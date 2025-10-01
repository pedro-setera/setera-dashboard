import tkinter as tk
from tkinter import font, messagebox, scrolledtext
import os

# Try to import pynmea2, show error if not available
try:
    import pynmea2
except ImportError:
    def show_import_error():
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "Erro de Importação",
            "A biblioteca 'pynmea2' não está instalada.\n\n"
            "Para instalar, execute:\npip install pynmea2"
        )
        root.destroy()
        exit(1)
    show_import_error()

# Determine application path for portable Python environment
application_path = os.path.dirname(os.path.abspath(__file__))

class NMEAParser:
    def __init__(self, root):
        self.root = root
        self.root.title("PARSER SENTENÇAS NMEA - SETERA TELEMETRIA")
        self.root.state('zoomed')

        # Set icon
        icon_path = os.path.join(application_path, 'favicon.ico')
        if os.path.exists(icon_path):
            self.root.iconbitmap(icon_path)

        # Define fonts
        self.bold_font = font.Font(weight='bold', size=10)
        self.title_font = font.Font(weight='bold', size=11)

        self.setup_ui()

    def setup_ui(self):
        # Main container
        main_frame = tk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Input section
        input_frame = tk.LabelFrame(main_frame, text="ENTRADA", font=self.title_font, padx=10, pady=10)
        input_frame.pack(fill=tk.X, pady=(0, 10))

        tk.Label(input_frame, text="Cole a sentença NMEA abaixo:", font=self.bold_font).pack(anchor='w', pady=(0, 5))

        self.input_text = tk.Text(input_frame, height=3, borderwidth=2, relief='solid', font=("Courier New", 10))
        self.input_text.pack(fill=tk.X, pady=(0, 10))

        # Button frame
        button_frame = tk.Frame(input_frame)
        button_frame.pack()

        self.process_button = tk.Button(
            button_frame,
            text="PROCESSAR",
            command=self.process_sentence,
            bg='green',
            fg='white',
            font=self.bold_font,
            padx=30,
            pady=10,
            cursor='hand2'
        )
        self.process_button.pack(side=tk.LEFT, padx=5)

        self.clear_button = tk.Button(
            button_frame,
            text="LIMPAR",
            command=self.clear_all,
            bg='orange',
            fg='white',
            font=self.bold_font,
            padx=30,
            pady=10,
            cursor='hand2'
        )
        self.clear_button.pack(side=tk.LEFT, padx=5)

        # Output section
        output_frame = tk.LabelFrame(main_frame, text="RESULTADO DA ANÁLISE", font=self.title_font, padx=10, pady=10)
        output_frame.pack(fill=tk.BOTH, expand=True)

        self.output_text = scrolledtext.ScrolledText(
            output_frame,
            borderwidth=2,
            relief='solid',
            font=("Courier New", 10),
            wrap=tk.WORD,
            state='disabled'
        )
        self.output_text.pack(fill=tk.BOTH, expand=True)

        # Configure text tags for formatting
        self.output_text.tag_configure('header', font=("Courier New", 11, 'bold'), foreground='#0066CC')
        self.output_text.tag_configure('label', font=("Courier New", 10, 'bold'), foreground='#006600')
        self.output_text.tag_configure('value', font=("Courier New", 10))
        self.output_text.tag_configure('error', font=("Courier New", 10, 'bold'), foreground='#CC0000')
        self.output_text.tag_configure('separator', foreground='#666666')

    def clear_all(self):
        """Clear both input and output text boxes"""
        self.input_text.delete('1.0', tk.END)
        self.output_text.config(state='normal')
        self.output_text.delete('1.0', tk.END)
        self.output_text.config(state='disabled')

    def write_output(self, text, tag=None):
        """Helper method to write to output text box"""
        self.output_text.config(state='normal')
        if tag:
            self.output_text.insert(tk.END, text, tag)
        else:
            self.output_text.insert(tk.END, text)
        self.output_text.config(state='disabled')

    def process_sentence(self):
        """Process the NMEA sentence from input"""
        # Clear previous output
        self.output_text.config(state='normal')
        self.output_text.delete('1.0', tk.END)
        self.output_text.config(state='disabled')

        # Get input text
        sentence = self.input_text.get('1.0', tk.END).strip()

        if not sentence:
            messagebox.showwarning("Aviso", "Por favor, insira uma sentença NMEA.")
            return

        try:
            # Parse the NMEA sentence
            msg = pynmea2.parse(sentence)

            # Display parsed data based on sentence type
            self.display_parsed_data(msg, sentence)

        except pynmea2.ParseError as e:
            self.write_output("ERRO DE ANÁLISE\n", 'error')
            self.write_output("="*80 + "\n", 'separator')
            self.write_output(f"\nA sentença NMEA não pôde ser processada.\n\n", 'error')
            self.write_output(f"Detalhes do erro: {str(e)}\n\n", 'value')
            self.write_output("Verifique se:\n", 'label')
            self.write_output("  • A sentença começa com $ ou !\n", 'value')
            self.write_output("  • O formato está correto\n", 'value')
            self.write_output("  • Não há caracteres extras ou espaços\n", 'value')

        except Exception as e:
            self.write_output("ERRO INESPERADO\n", 'error')
            self.write_output("="*80 + "\n", 'separator')
            self.write_output(f"\nOcorreu um erro ao processar a sentença.\n\n", 'error')
            self.write_output(f"Detalhes: {str(e)}\n", 'value')

    def display_parsed_data(self, msg, original_sentence):
        """Display parsed NMEA data with descriptions in Portuguese"""

        # Header
        self.write_output(f"ANÁLISE DA SENTENÇA NMEA\n", 'header')
        self.write_output("="*80 + "\n\n", 'separator')

        # Original sentence
        self.write_output("Sentença Original:\n", 'label')
        self.write_output(f"  {original_sentence}\n\n", 'value')

        # Sentence info
        self.write_output("Informações da Sentença:\n", 'label')
        self.write_output(f"  Tipo: {msg.sentence_type}\n", 'value')
        self.write_output(f"  Talker ID: {msg.talker} ", 'value')
        self.write_output(f"({self.get_talker_description(msg.talker)})\n\n", 'value')

        self.write_output("="*80 + "\n\n", 'separator')

        # Parse based on sentence type
        sentence_type = msg.sentence_type

        if sentence_type == 'GGA':
            self.parse_gga(msg)
        elif sentence_type == 'RMC':
            self.parse_rmc(msg)
        elif sentence_type == 'GSA':
            self.parse_gsa(msg)
        elif sentence_type == 'GSV':
            self.parse_gsv(msg)
        elif sentence_type == 'VTG':
            self.parse_vtg(msg)
        elif sentence_type == 'GLL':
            self.parse_gll(msg)
        elif sentence_type == 'ZDA':
            self.parse_zda(msg)
        elif sentence_type == 'GBS':
            self.parse_gbs(msg)
        elif sentence_type == 'HDT':
            self.parse_hdt(msg)
        elif sentence_type == 'VBW':
            self.parse_vbw(msg)
        else:
            self.parse_generic(msg)

    def get_talker_description(self, talker):
        """Return description for talker ID"""
        talker_descriptions = {
            'GP': 'GPS',
            'GL': 'GLONASS',
            'GA': 'Galileo',
            'GB': 'BeiDou',
            'GN': 'GNSS (Combinado)',
            'GQ': 'QZSS',
            'BD': 'BeiDou',
            'QZ': 'QZSS'
        }
        return talker_descriptions.get(talker, 'Desconhecido')

    def format_field(self, label, value, unit=''):
        """Format and write a field to output"""
        if value is None or value == '':
            value_str = 'N/A'
        else:
            # Round latitude/longitude to 6 decimal places
            if isinstance(value, (int, float)) and ('Latitude' in label or 'Longitude' in label):
                value_str = f"{value:.6f}"
            else:
                value_str = str(value)

            if unit:
                value_str += f' {unit}'

        self.write_output(f"  {label}: ", 'label')
        self.write_output(f"{value_str}\n", 'value')

    def parse_gga(self, msg):
        """Parse GGA - Global Positioning System Fix Data"""
        self.write_output("DADOS DE POSICIONAMENTO GPS (GGA)\n", 'header')
        self.write_output("-"*80 + "\n\n", 'separator')

        self.format_field("Horário UTC", msg.timestamp)
        self.format_field("Latitude", msg.latitude, "°")
        self.format_field("Longitude", msg.longitude, "°")
        self.format_field("Direção Lat", msg.lat_dir)
        self.format_field("Direção Lon", msg.lon_dir)

        # GPS Quality
        quality_desc = {
            '0': 'Inválido',
            '1': 'GPS fix (SPS)',
            '2': 'DGPS fix',
            '3': 'PPS fix',
            '4': 'RTK',
            '5': 'Float RTK',
            '6': 'Estimado (dead reckoning)',
            '7': 'Modo manual',
            '8': 'Modo simulação'
        }
        quality = quality_desc.get(str(msg.gps_qual), 'Desconhecido')
        self.format_field("Qualidade GPS", f"{msg.gps_qual} ({quality})")

        self.format_field("Número de Satélites", msg.num_sats)
        self.format_field("HDOP (Diluição Horizontal)", msg.horizontal_dil)
        self.format_field("Altitude", msg.altitude, msg.altitude_units if hasattr(msg, 'altitude_units') else 'M')
        self.format_field("Separação Geoidal", msg.geo_sep, msg.geo_sep_units if hasattr(msg, 'geo_sep_units') else 'M')
        self.format_field("Idade dos Dados DGPS", msg.age_gps_data, "s" if msg.age_gps_data else "")
        self.format_field("ID Estação DGPS", msg.ref_station_id)

    def parse_rmc(self, msg):
        """Parse RMC - Recommended Minimum Navigation Information"""
        self.write_output("INFORMAÇÕES MÍNIMAS DE NAVEGAÇÃO (RMC)\n", 'header')
        self.write_output("-"*80 + "\n\n", 'separator')

        self.format_field("Horário UTC", msg.timestamp)

        # Status
        status_desc = {'A': 'Ativo (Válido)', 'V': 'Void (Inválido)'}
        status = status_desc.get(msg.status, 'Desconhecido')
        self.format_field("Status", f"{msg.status} ({status})")

        self.format_field("Latitude", msg.latitude, "°")
        self.format_field("Longitude", msg.longitude, "°")
        self.format_field("Direção Lat", msg.lat_dir)
        self.format_field("Direção Lon", msg.lon_dir)
        self.format_field("Velocidade sobre o solo", msg.spd_over_grnd, "nós")

        # Convert knots to km/h
        if msg.spd_over_grnd:
            try:
                speed_kmh = float(msg.spd_over_grnd) * 1.852
                self.format_field("Velocidade", f"{speed_kmh:.2f}", "km/h")
            except:
                pass

        self.format_field("Curso sobre o solo", msg.true_course, "°")
        self.format_field("Data", msg.datestamp)

        # Magnetic variation
        if hasattr(msg, 'mag_variation') and msg.mag_variation:
            mag_var_dir = getattr(msg, 'mag_var_dir', '')
            self.format_field("Variação Magnética", f"{msg.mag_variation}° {mag_var_dir}")

        # Mode indicator (NMEA 2.3+)
        if hasattr(msg, 'mode_indicator'):
            mode_desc = {
                'A': 'Autônomo',
                'D': 'Diferencial',
                'E': 'Estimado',
                'M': 'Manual',
                'S': 'Simulador',
                'N': 'Dados inválidos'
            }
            mode = mode_desc.get(msg.mode_indicator, 'Desconhecido')
            self.format_field("Modo", f"{msg.mode_indicator} ({mode})")

    def parse_gsa(self, msg):
        """Parse GSA - GPS DOP and Active Satellites"""
        self.write_output("SATÉLITES ATIVOS E DOP (GSA)\n", 'header')
        self.write_output("-"*80 + "\n\n", 'separator')

        # Mode
        mode_desc = {'M': 'Manual', 'A': 'Automático'}
        mode = mode_desc.get(msg.mode, 'Desconhecido')
        self.format_field("Modo de Seleção", f"{msg.mode} ({mode})")

        # Fix type
        fix_desc = {
            '1': 'Sem fix',
            '2': 'Fix 2D',
            '3': 'Fix 3D'
        }
        fix = fix_desc.get(str(msg.mode_fix_type), 'Desconhecido')
        self.format_field("Tipo de Fix", f"{msg.mode_fix_type} ({fix})")

        # Satellites
        self.write_output("\n  Satélites Utilizados:\n", 'label')
        sv_ids = []
        for i in range(1, 13):
            sv_id = getattr(msg, f'sv_id{i:02d}', None)
            if sv_id:
                sv_ids.append(sv_id)

        if sv_ids:
            self.write_output(f"    {', '.join(sv_ids)}\n\n", 'value')
        else:
            self.write_output("    Nenhum satélite\n\n", 'value')

        self.format_field("PDOP (Diluição de Precisão)", msg.pdop)
        self.format_field("HDOP (Diluição Horizontal)", msg.hdop)
        self.format_field("VDOP (Diluição Vertical)", msg.vdop)

    def parse_gsv(self, msg):
        """Parse GSV - Satellites in View"""
        self.write_output("SATÉLITES VISÍVEIS (GSV)\n", 'header')
        self.write_output("-"*80 + "\n\n", 'separator')

        self.format_field("Número de Mensagens", msg.num_messages)
        self.format_field("Número da Mensagem", msg.msg_num)
        self.format_field("Total de Satélites Visíveis", msg.num_sv_in_view)

        self.write_output("\n  Detalhes dos Satélites:\n", 'label')
        self.write_output("-"*80 + "\n", 'separator')

        # Parse satellite data
        for i in range(1, 5):
            sv_prn = getattr(msg, f'sv_prn_num_{i}', None)
            if sv_prn:
                elevation = getattr(msg, f'elevation_deg_{i}', 'N/A')
                azimuth = getattr(msg, f'azimuth_{i}', 'N/A')
                snr = getattr(msg, f'snr_{i}', 'N/A')

                self.write_output(f"\n  Satélite #{sv_prn}:\n", 'label')
                self.write_output(f"    Elevação: {elevation}°\n", 'value')
                self.write_output(f"    Azimute: {azimuth}°\n", 'value')
                self.write_output(f"    SNR: {snr} dB\n", 'value')

    def parse_vtg(self, msg):
        """Parse VTG - Track made good and Ground speed"""
        self.write_output("VELOCIDADE E RUMO (VTG)\n", 'header')
        self.write_output("-"*80 + "\n\n", 'separator')

        self.format_field("Rumo Verdadeiro", msg.true_track, "°")
        self.format_field("Rumo Magnético", msg.mag_track, "°")
        self.format_field("Velocidade", msg.spd_over_grnd_kts, "nós")
        self.format_field("Velocidade", msg.spd_over_grnd_kmph, "km/h")

        if hasattr(msg, 'faa_mode'):
            mode_desc = {
                'A': 'Autônomo',
                'D': 'Diferencial',
                'E': 'Estimado',
                'M': 'Manual',
                'S': 'Simulador',
                'N': 'Dados inválidos'
            }
            mode = mode_desc.get(msg.faa_mode, 'Desconhecido')
            self.format_field("Modo FAA", f"{msg.faa_mode} ({mode})")

    def parse_gll(self, msg):
        """Parse GLL - Geographic Position - Latitude/Longitude"""
        self.write_output("POSIÇÃO GEOGRÁFICA (GLL)\n", 'header')
        self.write_output("-"*80 + "\n\n", 'separator')

        self.format_field("Latitude", msg.latitude, "°")
        self.format_field("Longitude", msg.longitude, "°")
        self.format_field("Direção Lat", msg.lat_dir)
        self.format_field("Direção Lon", msg.lon_dir)
        self.format_field("Horário UTC", msg.timestamp)

        status_desc = {'A': 'Ativo (Válido)', 'V': 'Void (Inválido)'}
        status = status_desc.get(msg.status, 'Desconhecido')
        self.format_field("Status", f"{msg.status} ({status})")

        if hasattr(msg, 'faa_mode'):
            mode_desc = {
                'A': 'Autônomo',
                'D': 'Diferencial',
                'E': 'Estimado',
                'M': 'Manual',
                'S': 'Simulador',
                'N': 'Dados inválidos'
            }
            mode = mode_desc.get(msg.faa_mode, 'Desconhecido')
            self.format_field("Modo FAA", f"{msg.faa_mode} ({mode})")

    def parse_zda(self, msg):
        """Parse ZDA - Time & Date"""
        self.write_output("DATA E HORA (ZDA)\n", 'header')
        self.write_output("-"*80 + "\n\n", 'separator')

        self.format_field("Horário UTC", msg.timestamp)
        self.format_field("Dia", msg.day)
        self.format_field("Mês", msg.month)
        self.format_field("Ano", msg.year)
        self.format_field("Fuso Horário (horas)", msg.local_zone)
        self.format_field("Fuso Horário (minutos)", msg.local_zone_minutes)

    def parse_gbs(self, msg):
        """Parse GBS - GPS Satellite Fault Detection"""
        self.write_output("DETECÇÃO DE FALHAS DE SATÉLITE (GBS)\n", 'header')
        self.write_output("-"*80 + "\n\n", 'separator')

        self.format_field("Horário UTC", msg.timestamp)
        self.format_field("Erro Latitude Esperado", msg.lat_err, "m")
        self.format_field("Erro Longitude Esperado", msg.lon_err, "m")
        self.format_field("Erro Altitude Esperado", msg.alt_err, "m")
        self.format_field("ID Satélite com Falha", msg.sv_id)
        self.format_field("Probabilidade de Falha", msg.prob)
        self.format_field("Estimativa de Erro", msg.bias, "m")
        self.format_field("Desvio Padrão", msg.stddev, "m")

    def parse_hdt(self, msg):
        """Parse HDT - Heading True"""
        self.write_output("RUMO VERDADEIRO (HDT)\n", 'header')
        self.write_output("-"*80 + "\n\n", 'separator')

        self.format_field("Rumo Verdadeiro", msg.heading, "°")

    def parse_vbw(self, msg):
        """Parse VBW - Dual Ground/Water Speed"""
        self.write_output("VELOCIDADE ÁGUA/SOLO (VBW)\n", 'header')
        self.write_output("-"*80 + "\n\n", 'separator')

        self.format_field("Velocidade Longitudinal (Água)", msg.lon_water_spd, "nós")
        self.format_field("Velocidade Transversal (Água)", msg.trans_water_spd, "nós")
        self.format_field("Status Velocidade Água", msg.water_spd_status)
        self.format_field("Velocidade Longitudinal (Solo)", msg.lon_grnd_spd, "nós")
        self.format_field("Velocidade Transversal (Solo)", msg.trans_grnd_spd, "nós")
        self.format_field("Status Velocidade Solo", msg.grnd_spd_status)

    def parse_generic(self, msg):
        """Parse generic/unknown sentence types"""
        self.write_output(f"SENTENÇA GENÉRICA ({msg.sentence_type})\n", 'header')
        self.write_output("-"*80 + "\n\n", 'separator')

        self.write_output("Campos Disponíveis:\n", 'label')

        # Get all fields from the message object
        fields = [attr for attr in dir(msg) if not attr.startswith('_') and
                  not callable(getattr(msg, attr)) and
                  attr not in ['render', 'sentence_type', 'talker', 'data', 'name_to_idx']]

        if fields:
            for field in fields:
                value = getattr(msg, field, None)
                if value is not None and value != '':
                    self.format_field(field.replace('_', ' ').title(), value)
        else:
            self.write_output("  Nenhum campo reconhecido para esta sentença.\n", 'value')
            self.write_output("\n  Dados Brutos:\n", 'label')
            if hasattr(msg, 'data'):
                for i, field in enumerate(msg.data, 1):
                    self.write_output(f"    Campo {i}: {field}\n", 'value')


def main():
    root = tk.Tk()
    app = NMEAParser(root)
    root.mainloop()


if __name__ == "__main__":
    main()
