"""
SETERA API Manager - v1.0 - 20Oct2025
API Integration for GPS Camera Device Management
Handles authentication and terminal fetching from SETERA platform
"""

import requests
import json
import base64
import uuid
import platform
from typing import List, Dict, Optional, Tuple
from datetime import datetime


# =============================================================================
# API CONFIGURATION
# =============================================================================

# SETERA API Endpoints
API_OAUTH_URL = "https://api-manager.hgdigital.io/oauth2/token"
API_TERMINALS_URL = "https://api.hgdigital.io/setera-core/v1/v2/terminals/find-terminal"

# Production API Credentials (same as config_fota_str1010.pyw)
API_CLIENT_ID = "6lMalZXG3wmNZkMn9hFpTGScFAQa"
API_CLIENT_SECRET = "VEJvermoiIIEh0anfYPliNsr_YQa"

# Hard-coded Profile ID
API_PROFILE_ID = 1
API_USER_ID = 4

# Request timeout (seconds)
API_TIMEOUT = 30


# =============================================================================
# SETERA API MANAGER CLASS
# =============================================================================

class SeteraAPIManager:
    """Manages authentication and terminal fetching from SETERA API"""

    def __init__(self, log_callback=None):
        """
        Initialize API Manager

        Args:
            log_callback: Optional callback function for logging (func(message, level))
        """
        self.oauth_token = None
        self.is_authenticated = False
        self.cached_terminals = []
        self.last_fetch_time = None
        self.log_callback = log_callback

    def log(self, message, level="INFO"):
        """Send log message to callback if available"""
        if self.log_callback:
            self.log_callback(message, level)

    def authenticate(self) -> Tuple[bool, str]:
        """
        Authenticate with SETERA API using OAuth2 client credentials

        Returns:
            Tuple[bool, str]: (success, message)
        """
        try:
            self.log("🔐 Iniciando autenticação com API SETERA...", "INFO")

            # Encode credentials in Base64
            auth_string = f"{API_CLIENT_ID}:{API_CLIENT_SECRET}"
            auth_bytes = auth_string.encode('ascii')
            auth_b64 = base64.b64encode(auth_bytes).decode('ascii')

            headers = {
                'Accept': 'application/json',
                'Authorization': f'Basic {auth_b64}',
                'Content-Type': 'application/json'
            }

            payload = {
                'grant_type': 'client_credentials',
                'scope': str(uuid.uuid4())  # Use UUID like Electron app
            }

            self.log(f"📤 Solicitando token OAuth...", "INFO")

            response = requests.post(
                API_OAUTH_URL,
                headers=headers,
                data=json.dumps(payload),
                timeout=API_TIMEOUT
            )

            if response.status_code == 200:
                data = response.json()
                self.oauth_token = data['access_token']
                self.is_authenticated = True
                self.log("✅ Autenticação realizada com sucesso", "SUCCESS")
                return True, "Autenticação bem-sucedida"
            else:
                error_msg = f"Falha na autenticação: HTTP {response.status_code}"
                self.log(f"❌ {error_msg}", "ERROR")
                self.is_authenticated = False
                return False, error_msg

        except requests.exceptions.Timeout:
            error_msg = "Timeout ao conectar com API (> 30s)"
            self.log(f"❌ {error_msg}", "ERROR")
            self.is_authenticated = False
            return False, error_msg

        except requests.exceptions.ConnectionError:
            error_msg = "Erro de conexão com API - Verifique internet"
            self.log(f"❌ {error_msg}", "ERROR")
            self.is_authenticated = False
            return False, error_msg

        except Exception as e:
            error_msg = f"Erro inesperado na autenticação: {e}"
            self.log(f"❌ {error_msg}", "ERROR")
            self.is_authenticated = False
            return False, error_msg

    def get_str_cam_terminals(self, force_refresh=False) -> Tuple[bool, List[Dict], str]:
        """
        Fetch and filter STR-CAM terminals from SETERA API

        Args:
            force_refresh: If True, bypass cache and fetch fresh data

        Returns:
            Tuple[bool, List[Dict], str]: (success, terminals_list, message)

            terminals_list format:
            [
                {
                    'id': 17635,
                    'plate': 'CARGA-1823',
                    'sim': '16999281300',
                    'imei': '865413057420555',
                    'model': 'STR-CAM',
                    'company': 'TAMBASA CARGA'
                },
                ...
            ]
        """
        try:
            # Check authentication
            if not self.is_authenticated or not self.oauth_token:
                return False, [], "Não autenticado - Execute autenticação primeiro"

            # Return cached data if available and not forcing refresh
            if not force_refresh and self.cached_terminals and self.last_fetch_time:
                self.log(f"📋 Usando cache: {len(self.cached_terminals)} terminais STR-CAM", "INFO")
                return True, self.cached_terminals, "Dados do cache"

            self.log("🔍 Buscando terminais STR-CAM da API...", "INFO")

            # Build request
            headers = {
                'Authorization': f'Bearer {self.oauth_token}',
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }

            params = {
                'size': 5000,
                'page': 0,
                'sort': 'dhUltimaAlteracao',
                'sortDirections': 'DESC',
                'profileId': API_PROFILE_ID,
                'userId': API_USER_ID
            }

            # Make API request
            response = requests.get(
                API_TERMINALS_URL,
                headers=headers,
                params=params,
                timeout=API_TIMEOUT
            )

            if response.status_code != 200:
                error_msg = f"Erro ao buscar terminais: HTTP {response.status_code}"
                self.log(f"❌ {error_msg}", "ERROR")
                return False, [], error_msg

            # Parse response
            data = response.json()
            all_elements = data.get('elements', [])

            self.log(f"📊 Total de terminais recebidos: {len(all_elements)}", "INFO")

            # Filter STR-CAM devices only
            str_cam_terminals = []

            for element in all_elements:
                tracker_model_name = element.get('trackerModelName', '')

                # Filter: Only STR-CAM devices
                if tracker_model_name == 'STR-CAM':
                    plate = element.get('cdPlaca', 'SEM PLACA')
                    sim = element.get('cdSim', 'SEM SIM')
                    imei = element.get('cdNumeroTerminal', 'SEM IMEI')
                    terminal_id = element.get('id')

                    # Get company name (nmempresa or nmdivisao)
                    company = element.get('nmempresa') or element.get('nmdivisao') or 'SEM EMPRESA'

                    # Only add if we have essential data
                    if terminal_id and plate and sim:
                        terminal_dict = {
                            'id': terminal_id,
                            'plate': plate,
                            'sim': sim,
                            'imei': imei,
                            'model': 'STR-CAM',
                            'company': company
                        }
                        str_cam_terminals.append(terminal_dict)

            # Sort by plate name (alphabetically)
            str_cam_terminals.sort(key=lambda x: x['plate'].upper())

            # Cache results
            self.cached_terminals = str_cam_terminals
            self.last_fetch_time = datetime.now()

            success_msg = f"✅ {len(str_cam_terminals)} terminais STR-CAM encontrados"
            self.log(success_msg, "SUCCESS")

            if len(str_cam_terminals) == 0:
                self.log("⚠️ Nenhum terminal STR-CAM encontrado no sistema", "WARNING")

            return True, str_cam_terminals, success_msg

        except requests.exceptions.Timeout:
            error_msg = "Timeout ao buscar terminais (> 30s)"
            self.log(f"❌ {error_msg}", "ERROR")
            return False, [], error_msg

        except requests.exceptions.ConnectionError:
            error_msg = "Erro de conexão ao buscar terminais"
            self.log(f"❌ {error_msg}", "ERROR")
            return False, [], error_msg

        except Exception as e:
            error_msg = f"Erro ao processar terminais: {e}"
            self.log(f"❌ {error_msg}", "ERROR")
            return False, [], error_msg

    def get_cached_terminals(self) -> List[Dict]:
        """
        Get cached terminals without making API call

        Returns:
            List[Dict]: Cached terminals list (empty if no cache)
        """
        return self.cached_terminals

    def clear_cache(self):
        """Clear cached terminals"""
        self.cached_terminals = []
        self.last_fetch_time = None
        self.log("🗑️ Cache de terminais limpo", "INFO")

    def is_ready(self) -> bool:
        """Check if API manager is authenticated and has terminal data"""
        return self.is_authenticated and len(self.cached_terminals) > 0


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def format_terminal_for_display(terminal: Dict) -> str:
    """
    Format terminal data for display in dropdown

    Args:
        terminal: Terminal dictionary

    Returns:
        str: Formatted string like "CARGA-1823 (SIM: 16999281300)"
    """
    plate = terminal.get('plate', 'DESCONHECIDO')
    sim = terminal.get('sim', 'SEM SIM')
    return f"{plate} (SIM: {sim})"


def search_terminals(terminals: List[Dict], search_text: str) -> List[Dict]:
    """
    Filter terminals by search text (searches plate and SIM)

    Args:
        terminals: List of terminal dictionaries
        search_text: Search query

    Returns:
        List[Dict]: Filtered terminals
    """
    if not search_text:
        return terminals

    search_text = search_text.upper()
    filtered = []

    for terminal in terminals:
        plate = terminal.get('plate', '').upper()
        sim = terminal.get('sim', '').upper()
        company = terminal.get('company', '').upper()

        # Match if search text appears in plate, SIM, or company
        if search_text in plate or search_text in sim or search_text in company:
            filtered.append(terminal)

    return filtered
