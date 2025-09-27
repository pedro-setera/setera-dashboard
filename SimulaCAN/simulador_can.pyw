#!/usr/bin/env python3
"""
Aplicação de Gravação/Reprodução CAN Bus
Uma aplicação baseada em PyQt6 para gravar e reproduzir mensagens do barramento CAN
usando o dispositivo CANalyst-II.

Autor: Pedro Silva
Data: 06 de Junho de 2025

Requisitos de Instalação:
pip install PyQt6 python-can canalystii pywin32 pyqtgraph matplotlib numpy scipy 

Uso:
python can_bus_app.py
"""

import sys
import time
import traceback
import re
import threading
from pathlib import Path
from datetime import datetime
from typing import Optional
from collections import deque

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextEdit, QLabel, QStatusBar, QMessageBox,
    QSplitter, QGroupBox, QProgressBar, QFileDialog, QSizePolicy, QCheckBox, QComboBox
)
from PyQt6.QtCore import (
    QThread, pyqtSignal, QTimer, Qt, QSize
)
from PyQt6.QtGui import QFont, QIcon, QPalette, QColor

import can

# Importar módulos de simulação
from simulation_params import get_simulation_params
from frame_modifier import create_frame_modifier

# Importar módulo de gráficos (verificando disponibilidade)
import os
import sys

# Garantir que o diretório do script está no path do Python
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

try:
    from grafico_can import GraficoCANDialog, verificar_dependencias
    GRAFICOS_DISPONIVEL = verificar_dependencias()
except ImportError:
    GRAFICOS_DISPONIVEL = False
    GraficoCANDialog = None
except Exception:
    GRAFICOS_DISPONIVEL = False
    GraficoCANDialog = None

# Importar módulo de simulação (verificando disponibilidade)
try:
    from simulation import create_simulation_window
    SIMULACAO_DISPONIVEL = True
except ImportError:
    SIMULACAO_DISPONIVEL = False
    create_simulation_window = None
except Exception:
    SIMULACAO_DISPONIVEL = False
    create_simulation_window = None


class RecordingWorker(QThread):
    """
    Thread de trabalho para gravação de mensagens CAN bus.
    Executa em thread separada para evitar travamento da GUI.
    """
    
    # Sinais customizados para comunicação com thread principal
    message_received = pyqtSignal(str)  # Emitido quando uma mensagem CAN é recebida
    status_update = pyqtSignal(str)     # Emitido para atualizações de status
    error_occurred = pyqtSignal(str)    # Emitido quando ocorre um erro
    recording_stopped = pyqtSignal()    # Emitido quando a gravação para
    actual_transmission = pyqtSignal()  # Emitido quando uma mensagem é realmente recebida via CAN (para FPS real)
    
    def __init__(self, log_filename: str = "truck_log.asc", channel: int = 0, bitrate: int = 250000):
        super().__init__()
        self.log_filename = log_filename
        self.channel = channel
        self.bitrate = bitrate
        self.bus: Optional[can.interface.Bus] = None
        self.writer: Optional[can.ASCWriter] = None
        self.is_recording = False
        
    def run(self):
        """Loop principal de gravação - executa em thread separada."""
        try:
            self.status_update.emit("Tentando conectar ao CANalyst-II...")
            
            # ✅ SAFE SINGLE CHANNEL PASSIVE MONITORING - Channel 1 only with LISTEN-ONLY mode
            self.bus = can.interface.Bus(
                channel=0,  # Always Channel 1 (ch0) for safety
                interface='canalystii',
                bitrate=self.bitrate,
                # ✅ CRITICAL: Enable listen-only mode for passive monitoring
                listen_only=True,  # Prevents any transmission including ACK frames
                receive_timeout=1.0,
                # ✅ EXTENDED FRAME SUPPORT FOR J1939
                extended_id=True
            )
            
            self.status_update.emit(f"Conectado! Gravando para '{self.log_filename}'...")
            self.is_recording = True
            
            # Iniciar gravação com escritor ASC
            with can.ASCWriter(self.log_filename) as self.writer:
                for msg in self.bus:
                    if not self.is_recording:
                        break
                        
                    # Emitir sinal de transmissão real para FPS correto
                    self.actual_transmission.emit()
                    
                    # Formatar mensagem para exibição
                    msg_str = f"{msg.timestamp:.6f} | {msg.arbitration_id:08X} | {' '.join(f'{b:02X}' for b in msg.data)}"
                    self.message_received.emit(msg_str)
                    
                    # Salvar mensagem no arquivo
                    self.writer.on_message_received(msg)
                    
        except Exception as e:
            self.error_occurred.emit(f"Erro na gravação: {str(e)}")
        finally:
            self.cleanup()
            self.recording_stopped.emit()
            
    def stop_recording(self):
        """Parar o processo de gravação."""
        self.is_recording = False
        self.status_update.emit("Parando gravação...")
        
    def cleanup(self):
        """Limpar recursos."""
        if self.bus is not None:
            self.bus.shutdown()
            self.bus = None
        self.status_update.emit("Gravação parada e recursos limpos.")


class PlaybackWorker(QThread):
    """
    Thread de trabalho para reprodução de mensagens CAN bus.
    Pode manter o tempo original entre mensagens ou usar intervalo fixo.
    ENHANCED: Agora com tratamento robusto de timeouts USB.
    """
    
    # Sinais customizados
    message_sent = pyqtSignal(str)      # Emitido quando uma mensagem é enviada
    status_update = pyqtSignal(str)     # Atualizações de status
    error_occurred = pyqtSignal(str)    # Notificações de erro
    playback_stopped = pyqtSignal()     # Conclusão da reprodução
    progress_update = pyqtSignal(int)   # Porcentagem de progresso (0-100)
    actual_transmission = pyqtSignal()  # Emitido quando uma mensagem é realmente enviada via CAN (para FPS real)
    
    def __init__(self, log_filename: str = "truck_log.asc", continuous_mode: bool = False, channel: int = 0, bitrate: int = 250000, simulation_params=None, test_mode: bool = False):
        super().__init__()
        self.log_filename = log_filename
        self.channel = channel
        self.bitrate = bitrate
        self.bus: Optional[can.interface.Bus] = None
        self.is_playing = False
        self.continuous_mode = continuous_mode  # True = 10ms fixo, False = timestamp original
        self.continuous_interval = 0.01  # 10ms em segundos
        self.test_mode = test_mode  # True = offline mode without CAN interface
        # Remover limite de loops - estava causando parada prematura
        # self.loop_count = 0
        # self.max_loops = 1000
        
        # NOVO: Configurações para tratamento de timeouts USB (SEM interferir no timing)
        self.max_usb_retries = 2
        self.usb_retry_delay = 0.0  # NO delay for maximum throughput
        
        # Estatísticas apenas (SEM backpressure que interfere no timing)
        self.usb_error_count = 0
        
        # Diagnóstico de performance CAN
        self.transmission_times = deque(maxlen=50)  # Reduzir para 50 transmissões para melhor performance
        self.slow_transmission_threshold = 0.010  # 10ms considerado lento
        
        # ✅ SIMULATION INTEGRATION WITH IMMEDIATE RESPONSE
        self.simulation_params = simulation_params
        self.frame_modifier = None
        if self.simulation_params:
            self.frame_modifier = create_frame_modifier(self.simulation_params)
            # Register for immediate parameter change notifications
            self.simulation_params.register_update_callback(self._on_parameter_changed)
        
        # Disable immediate injection for maximum performance
        self._immediate_injection_enabled = False

        # Dynamic FPS adaptation system
        self._fps_measurement_window = deque(maxlen=100)  # Last 100 frames for FPS calculation
        self._last_fps_calculation = 0.0
        self._analysis_mode_active = False  # Track analysis mode for special handling

        # ✅ HIGH-LEVEL RETRY MECHANISM for bus-off recovery
        self.max_connection_retries = 5  # Total attempts (1 initial + 4 retries)
        self.current_retry_attempt = 0   # Track current attempt number
        
    def run(self):
        """Loop principal de reprodução - executa em thread separada."""
        # ✅ HIGH-LEVEL RETRY LOOP for handling bus-off timeout errors
        while self.current_retry_attempt < self.max_connection_retries:
            self.current_retry_attempt += 1

            # ✅ Status message for retry attempts
            if self.current_retry_attempt > 1:
                self.status_update.emit(f"Tentativa de reconexão {self.current_retry_attempt}/{self.max_connection_retries}...")

            try:
                if self.test_mode:
                    # ✅ TEST MODE: Skip CAN interface connection completely
                    self.status_update.emit("Modo TESTE ativado - Reprodução offline sem interface CAN...")
                    mode_text = "10ms" if self.continuous_mode else "com tempo original"
                    self.status_update.emit(f"Iniciando reprodução TESTE {mode_text} de '{self.log_filename}'...")
                    self.bus = None  # No CAN interface in test mode
                else:
                    # ✅ NORMAL PLAYBACK MODE: Active transmission enabled (no listen-only)
                    self.status_update.emit("Conectando à interface CANBUS...")

                    self.bus = can.interface.Bus(
                        channel=0,  # Always Channel 1 (ch0) for safety
                        interface='canalystii',
                        bitrate=self.bitrate,
                        # Configurações otimizadas para receptores lentos
                        receive_timeout=0.1,
                        # Configurações específicas do CANalyst-II para melhor flow control
                        can_filters=None,  # Aceitar todos os frames
                        # NOTE: No listen_only=True for playback - we need to transmit frames
                        # ✅ EXTENDED FRAME SUPPORT FOR J1939
                        extended_id=True
                    )

                    mode_text = "10ms" if self.continuous_mode else "com tempo original"
                    self.status_update.emit(f"Conectado! Iniciando reprodução {mode_text} de '{self.log_filename}'...")

                self.is_playing = True

                # Contar total de mensagens para rastreamento de progresso
                total_messages = self._count_messages()
                current_message = 0

                # Contadores para estatísticas de erro
                total_usb_errors = 0
                total_retries = 0

                # Counter to reset error stats periodically (prevent accumulation effects)
                loop_iteration = 0

                # Loop de reprodução (sem limite artificial)
                while self.is_playing:
                    try:
                        # Abrir arquivo de log para leitura
                        log_reader = can.LogReader(self.log_filename)
                        self.status_update.emit("--- Iniciando novo loop ---")

                        # PONTO CHAVE: Inicialização da temporização de alta precisão
                        playback_start_time = None
                        log_start_time = None

                        current_message = 0
                        messages_sent_in_batch = 0

                        # Reset performance counters every loop
                        if hasattr(self, 'transmission_times'):
                            self.transmission_times.clear()

                        # Reset error counters periodically
                        loop_iteration += 1
                        if loop_iteration % 10 == 0:
                            total_usb_errors = 0
                            self.usb_error_count = 0

                        # Processar cada mensagem no log
                        for msg in log_reader:
                            if not self.is_playing:
                                self.status_update.emit("Parando reprodução (início do loop)...")
                                break

                            # Inicializa a temporização no primeiro frame
                            if playback_start_time is None:
                                playback_start_time = time.perf_counter()
                                log_start_time = msg.timestamp

                            # --- TEMPORIZAÇÃO DE ALTA PRECISÃO ---
                            if self.continuous_mode:
                                # Modo contínuo: delay fixo
                                self.precise_sleep(self.continuous_interval)
                            else:
                                # Modo original: Sincronizar com o tempo do log
                                elapsed_log_time = msg.timestamp - log_start_time
                                target_send_time = playback_start_time + elapsed_log_time

                                # Calcular o tempo de espera necessário para compensar o overhead do loop
                                wait_time = target_send_time - time.perf_counter()

                                if wait_time > 0:
                                    self.precise_sleep(wait_time)

                            # Verificar novamente se deve parar APÓS o delay
                            if not self.is_playing:
                                self.status_update.emit("Parando reprodução (após delay)...")
                                break

                            # ✅ APLICAR SIMULAÇÃO EM TEMPO REAL
                            if self.frame_modifier:
                                msg = self.frame_modifier.modify_frame(msg)

                            # Enviar mensagem com retry (SEM afetar timing)
                            success = self._send_message_with_retry(msg)

                            if success:
                                # Emitir sinal de transmissão real para FPS correto
                                self.actual_transmission.emit()

                                messages_sent_in_batch += 1

                                # Medição de FPS dinâmica (com amostragem para performance)
                                if messages_sent_in_batch % 20 == 0:
                                    current_time = time.perf_counter()
                                    self._fps_measurement_window.append(current_time)

                                # A amostragem foi removida. Emitir sinal para CADA frame.
                                msg_str = f"{msg.timestamp:.6f} | {msg.arbitration_id:08X} | {' '.join(f'{b:02X}' for b in msg.data)}"
                                self.message_sent.emit(msg_str)

                                current_message += 1

                                # Progress updates - fixed interval
                                if total_messages > 0 and current_message % 100 == 0:
                                    progress = int((current_message / total_messages) * 100)
                                    self.progress_update.emit(progress)
                            else:
                                # Silent failure for maximum performance - no status updates
                                total_usb_errors += 1
                                self.usb_error_count += 1

                            # Verificar se deve parar a cada 50 mensagens para responsividade (menos frequente)
                            if current_message % 50 == 0 and not self.is_playing:
                                self.status_update.emit("Parando reprodução...")
                                break

                    except FileNotFoundError:
                        self.error_occurred.emit(f"Arquivo de log '{self.log_filename}' não encontrado!")
                        break
                    except Exception as e:
                        # ✅ CHECK IF TIMEOUT ERROR: Let it bubble up to retry logic
                        error_str = str(e).lower()
                        is_timeout_error = ('timeout' in error_str or 'errno 10060' in error_str or
                                           'usb' in error_str or '_usb_reap_async' in error_str)

                        # ✅ DEBUG: Log which path the exception takes
                        self.status_update.emit(f"DEBUG: Inner exception caught: {str(e)}")
                        self.status_update.emit(f"DEBUG: Is timeout error: {is_timeout_error}")

                        if is_timeout_error:
                            # Re-raise timeout errors so they reach the outer retry handler
                            self.status_update.emit("DEBUG: Re-raising timeout error to retry logic")
                            raise e
                        else:
                            # Non-timeout errors should be handled immediately as before
                            self.status_update.emit("DEBUG: Handling non-timeout error immediately")
                            self.error_occurred.emit(f"Erro na reprodução: {str(e)}")
                            break

                    # Verificar se deve parar entre loops
                    if not self.is_playing:
                        break

                    # Remove inter-loop delay to prevent throughput degradation
                    # if self.is_playing:
                    #     time.sleep(0.01)  # This might be causing the 45-second FPS drop

                # Reportar estatísticas finais
                if total_usb_errors > 0:
                    self.status_update.emit(f"Reprodução concluída. Mensagens perdidas: {total_usb_errors} (temporização preservada)")

                # ✅ If we reach here, playback completed successfully - break out of retry loop
                break

            except Exception as e:
                # ✅ HIGH-LEVEL RETRY LOGIC: Check if this is a timeout error and we have retries left
                error_str = str(e).lower()
                is_timeout_error = ('timeout' in error_str or 'errno 10060' in error_str or
                                   'usb' in error_str or '_usb_reap_async' in error_str)

                # ✅ DEBUG: Log outer exception handler
                self.status_update.emit(f"DEBUG: Outer exception caught: {str(e)}")
                self.status_update.emit(f"DEBUG: Retry attempt {self.current_retry_attempt}/{self.max_connection_retries}")
                self.status_update.emit(f"DEBUG: Is timeout error: {is_timeout_error}")

                if is_timeout_error and self.current_retry_attempt < self.max_connection_retries:
                    # This is a timeout error and we have retries left
                    self.status_update.emit(f"Erro de timeout detectado. Tentativa {self.current_retry_attempt}/{self.max_connection_retries}. Reconectando...")

                    # Clean up current resources before retry
                    self.cleanup()

                    # Wait a brief moment before retry
                    time.sleep(1.0)

                    # Continue to next retry attempt
                    continue
                else:
                    # Either not a timeout error, or we've exhausted retries
                    if is_timeout_error:
                        self.error_occurred.emit(f"Erro na reprodução após {self.max_connection_retries} tentativas: {str(e)}")
                    else:
                        self.error_occurred.emit(f"Erro de conexão: {str(e)}")
                    break

        # ✅ Final cleanup and signal emission (moved outside retry loop)
        self.cleanup()
        self.playback_stopped.emit()
    
    def _send_message_with_retry(self, msg: can.Message) -> bool:
        """
        Enviar mensagem CAN com retry automático SEM afetar timing do log.
        In test mode, always returns True without sending to CAN interface.
        
        Returns:
            bool: True se a mensagem foi enviada com sucesso, False caso contrário
        """
        # ✅ TEST MODE: Always return success without CAN transmission
        if self.test_mode:
            return True
        
        # ✅ NORMAL MODE: Actual CAN transmission with retry
        for attempt in range(self.max_usb_retries):
            try:
                self.bus.send(msg)
                return True  # SUCESSO - timing do próximo frame não é afetado
                
            except Exception as e:
                error_str = str(e).lower()
                
                # Verificar se é um erro de timeout USB/CAN
                if 'timeout' in error_str or 'errno 10060' in error_str or 'usb' in error_str or '_usb_reap_async' in error_str:
                    if attempt < self.max_usb_retries - 1:  # Não é a última tentativa
                        # Aguardar antes de tentar novamente (SÓ entre retries, não afeta timing)
                        time.sleep(self.usb_retry_delay)
                        continue
                    else:
                        # Última tentativa falhou - timing do próximo frame não é afetado
                        self.usb_error_count += 1
                        return False
                else:
                    # Erro não relacionado a USB/timeout - propagar imediatamente
                    raise e
                    
        return False
    
    def _should_update_gui(self, messages_sent_in_batch: int) -> bool:
        """Determina se a GUI deve ser atualizada para este frame (APENAS MODO ANÁLISE)."""
        # No modo de análise, todos os frames são processados para garantir a precisão dos dados.
        # A atualização da tela, no entanto, é feita em lote.
        if self._analysis_mode_active:
            return True
        
        # No modo normal, a GUI é atualizada diretamente, então este método não é mais usado.
        # Retornar True por padrão para não quebrar a lógica se for chamado acidentalmente.
        return True
    
    def set_analysis_mode(self, enabled: bool):
        """Set analysis mode state to adjust sampling behavior."""
        self._analysis_mode_active = enabled
        if enabled:
            # Force immediate recalculation for analysis mode
            self._dynamic_sample_rate = 1
    
    def _on_parameter_changed(self, param_name: str, enabled: bool, raw_value: int):
        """
        Callback for immediate parameter changes - provides instant responsiveness.
        Injects modified frames immediately when parameters change, regardless of timing.
        """
        if not self.is_playing or not self._immediate_injection_enabled:
            return
        
        if not self.simulation_params:
            return
        
        # Get frame IDs that contain this parameter
        frame_ids = self.simulation_params.get_parameter_frames(param_name)
        
        for frame_id in frame_ids:
            # Get the last known frame data for this frame ID
            if frame_id in self._last_frame_data:
                try:
                    with self._frame_injection_lock:
                        frame_data = self._last_frame_data[frame_id]
                        original_msg = frame_data['original_msg']
                        
                        # Apply simulation to the stored frame
                        if self.frame_modifier:
                            modified_msg = self.frame_modifier.modify_frame(original_msg)
                            
                            # Inject immediately for responsive feel
                            self._inject_immediate_frame(modified_msg, f"Parameter '{param_name}' changed")
                            
                except Exception as e:
                    # Silent failure to prevent callback issues
                    pass
    
    def _inject_immediate_frame(self, msg: can.Message, reason: str = ""):
        """
        Inject frame immediately for instant parameter response.
        Uses minimal retry for speed while preserving responsiveness.
        In test mode, skips CAN transmission but still emits signals.
        """
        if self.test_mode:
            # ✅ TEST MODE: Skip CAN transmission but emit signals
            self.actual_transmission.emit()
            
            # Optional: Log injection for debugging (reduce frequency to avoid spam)
            if time.perf_counter() % 2 < 0.1:  # Log roughly every 2 seconds
                msg_str = f"{msg.timestamp:.6f} | {msg.arbitration_id:08X} | {' '.join(f'{b:02X}' for b in msg.data)} (IMMEDIATE TESTE: {reason})"
                self.message_sent.emit(msg_str)
            return
        
        if not self.bus:
            return
        
        try:
            # Fast injection with minimal retry (1 attempt only for speed)
            self.bus.send(msg)
            
            # Emit signals for tracking
            self.actual_transmission.emit()
            
            # Optional: Log injection for debugging (reduce frequency to avoid spam)
            if time.perf_counter() % 2 < 0.1:  # Log roughly every 2 seconds
                msg_str = f"{msg.timestamp:.6f} | {msg.arbitration_id:08X} | {' '.join(f'{b:02X}' for b in msg.data)} (IMMEDIATE: {reason})"
                self.message_sent.emit(msg_str)
        
        except Exception:
            # Silent failure for immediate injections to maintain responsiveness
            pass
            
    def precise_sleep(self, delay: float):
        """
        Dorme por um período de tempo com alta precisão.
        Usa time.sleep() para a maior parte do tempo e um busy-wait para o final.
        """
        end_time = time.perf_counter() + delay
        
        # Deixar uma pequena margem (e.g., 1.5ms) para o busy-wait.
        # Um valor muito baixo pode fazer com que o time.sleep() retorne tarde demais.
        # Um valor muito alto aumenta o uso da CPU. 1.5ms é um bom equilíbrio.
        sleep_threshold = 0.0015
        if delay > sleep_threshold:
            try:
                # O sleep pode ser impreciso, mas é bom para economizar CPU
                time.sleep(delay - sleep_threshold)
            except Exception:
                pass # Ignorar erros no sleep
                
        # Busy-wait para o tempo restante para garantir a precisão
        while time.perf_counter() < end_time:
            pass

    def _count_messages(self) -> int:
        """Contar total de mensagens no arquivo de log para cálculo de progresso."""
        try:
            log_reader = can.LogReader(self.log_filename)
            return sum(1 for _ in log_reader)
        except:
            return 0
            
    def stop_playback(self):
        """Parar o processo de reprodução."""
        self.status_update.emit("Solicitação de parada recebida...")
        self.is_playing = False
        # ✅ Reset retry counter for next playback session
        self.current_retry_attempt = 0
        # Dar tempo para a thread processar a parada
        self.msleep(100)  # 100ms para garantir que a thread veja a mudança
        
    def cleanup(self):
        """Limpar recursos."""
        # Unregister callback to prevent memory leaks
        if self.simulation_params and hasattr(self, '_on_parameter_changed'):
            try:
                self.simulation_params.unregister_update_callback(self._on_parameter_changed)
            except:
                pass
        
        # ✅ TEST MODE: Skip CAN interface cleanup
        if not self.test_mode and self.bus is not None:
            self.bus.shutdown()
            self.bus = None
        
        status_msg = "Reprodução TESTE parada e recursos limpos." if self.test_mode else "Reprodução parada e recursos limpos."
        self.status_update.emit(status_msg)


class MonitorWorker(QThread):
    """
    Thread de trabalho para monitoramento de mensagens CAN bus.
    Apenas exibe mensagens sem gravar.
    """
    
    # Sinais customizados
    message_received = pyqtSignal(str)  # Emitido quando uma mensagem é recebida
    status_update = pyqtSignal(str)     # Atualizações de status
    error_occurred = pyqtSignal(str)    # Notificações de erro
    monitoring_stopped = pyqtSignal()   # Monitoramento parado
    actual_transmission = pyqtSignal()  # Emitido quando uma mensagem é realmente recebida via CAN (para FPS real)
    
    def __init__(self, channel: int = 0, bitrate: int = 250000):
        super().__init__()
        self.channel = channel
        self.bitrate = bitrate
        self.bus: Optional[can.interface.Bus] = None
        self.is_monitoring = False
        
    def run(self):
        """Loop principal de monitoramento - executa em thread separada."""
        try:
            self.status_update.emit("Conectando ao CANalyst-II para monitoramento...")
            
            # ✅ SAFE SINGLE CHANNEL PASSIVE MONITORING - Channel 1 only with LISTEN-ONLY mode
            self.bus = can.interface.Bus(
                channel=0,  # Always Channel 1 (ch0) for safety
                interface='canalystii',
                bitrate=self.bitrate,
                # ✅ CRITICAL: Enable listen-only mode for passive monitoring
                listen_only=True,  # Prevents any transmission including ACK frames
                receive_timeout=1.0,
                # ✅ EXTENDED FRAME SUPPORT FOR J1939
                extended_id=True
            )
            
            self.status_update.emit("Conectado! Monitorando mensagens CAN...")
            self.is_monitoring = True
            
            # Loop de monitoramento
            for msg in self.bus:
                if not self.is_monitoring:
                    break
                    
                # Emitir sinal de transmissão real para FPS correto
                self.actual_transmission.emit()
                
                # Formatar mensagem para exibição
                msg_str = f"{msg.timestamp:.6f} | {msg.arbitration_id:08X} | {' '.join(f'{b:02X}' for b in msg.data)}"
                self.message_received.emit(msg_str)
                    
        except Exception as e:
            self.error_occurred.emit(f"Erro no monitoramento: {str(e)}")
        finally:
            self.cleanup()
            self.monitoring_stopped.emit()
            
    def stop_monitoring(self):
        """Parar o processo de monitoramento."""
        self.is_monitoring = False
        self.status_update.emit("Parando monitoramento...")
        
    def cleanup(self):
        """Limpar recursos."""
        if self.bus is not None:
            self.bus.shutdown()
            self.bus = None
        self.status_update.emit("Monitoramento parado e recursos limpos.")


class CANBusMainWindow(QMainWindow):
    """
    Janela principal da aplicação com tema escuro moderno.
    Fornece controles para operações de gravação e reprodução.
    """
    
    def __init__(self):
        super().__init__()
        
        # Estado da aplicação
        self.recording_worker: Optional[RecordingWorker] = None
        self.playback_worker: Optional[PlaybackWorker] = None
        self.monitor_worker: Optional[MonitorWorker] = None
        self.log_filename = "truck_log.asc"
        
        # Estados dos botões toggle
        self.is_recording = False
        self.is_playing = False
        self.is_monitoring = False
        
        # Simple manual bitrate selection - no auto-detection
        
        # ✅ SIMULATION INTEGRATION
        self.simulation_params = get_simulation_params()
        self.simulation_window = None
        
        # Timer para operações
        self.operation_timer = QTimer()
        self.operation_timer.timeout.connect(self.update_timer)
        self.elapsed_seconds = 0
        
        # Cálculo de FPS real (baseado em transmissões CAN reais)
        self.actual_transmission_timestamps = deque(maxlen=1000)  # Últimas 5000 transmissões (suficiente para 5s a 1000fps)
        self.real_fps_timer = QTimer()
        self.real_fps_timer.timeout.connect(self.update_real_fps)
        self.real_fps_timer.start(250)  # Atualizar a cada segundo
        self.real_fps = 0.0
        
        # Circular buffer para armazenar as últimas 5000 mensagens
        self.message_buffer = deque(maxlen=5000)
        
        # Analysis buffer for the center pane
        self.analysis_buffer = deque(maxlen=5000)
        
        # Controle de atualização da GUI para evitar travamentos
        self._gui_update_timer = QTimer()
        self._gui_update_timer.timeout.connect(self._update_message_display)
        self._gui_update_timer.setSingleShot(False)
        self._gui_update_timer.setInterval(100)  # Atualizar display a cada 100ms - more realistic for 420 FPS
        self._pending_messages = deque()
        self._gui_update_pending = False
        
        # Frame ID grouping mode data structures - ALWAYS ENABLED
        self.frame_id_data = {}  # Dictionary to store unique Frame IDs and their latest data
        self.group_frameid_mode = True  # Always enabled for analysis pane
        self._frameid_pending_updates = deque()  # Batch Frame ID updates for performance
        self._frameid_update_counter = 0  # Counter to limit update frequency
        
        # Change tracking for dynamic blue shading
        self.frame_id_change_history = {}  # Track byte changes over time for each Frame ID
        self._change_window_seconds = 10.0  # Time window for change rate calculation
        
        # Enhanced Analysis State Management - ALWAYS ENABLED WITH VOLATILITY
        self.analysis_state = {
            'enabled': True,                     # Analysis mode ALWAYS active
            'sort_mode': 'volatility',           # ALWAYS volatility sorting
            'search_filter': '',                 # Real-time search filter text
            'sort_cache': {                      # Performance optimization
                'last_sort_time': 0.0,
                'sorted_frame_ids': [],
                'sort_mode_used': 'volatility'
            },
            'frame_statistics': {                # Cached aggregate stats
                'total_frames': 0,
                'active_frames': 0,
                'last_calculated': 0.0
            }
        }
        
        # Fire/Ember style color palette with pure colors for easy identification
        self.change_colors = [
            None,          # No change - no background
            '#FFFFFF',     # White - minimal changes (<0.5/sec)
            '#F5F5DC',     # Beige - low changes (<1/sec) - darker than white, distinct from yellow
            '#FFFF00',     # Yellow - moderate changes (<3/sec)
            '#FFA500',     # Orange - frequent changes (<6/sec)
            '#FF0000',     # Red - very frequent changes (<10/sec)
            '#800080'      # Purple - ultra-fast changes (10+/sec)
        ]
        
        # Precompiled regex pattern for Frame ID extraction (performance optimization)
        self._frameid_pattern = re.compile(r'<span[^>]*>([^<]+):</span>[^|]*\|\s*([A-F0-9]+)\s*\|(.+)')
        
        # Controle de janelas de gráfico abertas
        self.janelas_graficos = {}  # Dict: frame_id -> GraficoCANDialog
        
        # Inicializar UI
        self.setup_ui()
        self.setup_theme()
        self.setup_connections()
    
    def _create_frame_filter_widget(self):
        """Create a simple frame filter widget with just a search input for real-time filtering."""
        from PyQt6.QtWidgets import QLineEdit, QHBoxLayout, QWidget
        from PyQt6.QtCore import Qt
        
        # Container widget with horizontal layout and proper alignment
        filter_widget = QWidget()
        filter_widget.setMinimumWidth(200)
        filter_widget.setMaximumWidth(250)
        filter_widget.setMinimumHeight(35)  # Match button height
        filter_widget.setMaximumHeight(35)
        filter_widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        filter_layout = QHBoxLayout(filter_widget)
        filter_layout.setContentsMargins(0, 0, 0, 0)  # Remove margins for better alignment
        filter_layout.setSpacing(0)
        filter_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)  # Center vertically
        
        # Search input - match button height exactly
        self.frame_search_input = QLineEdit()
        self.frame_search_input.setPlaceholderText("Filtrar FrameID")
        self.frame_search_input.setMinimumWidth(200)
        self.frame_search_input.setMaximumWidth(250)
        self.frame_search_input.setMinimumHeight(35)  # Match button height
        self.frame_search_input.setMaximumHeight(35)
        self.frame_search_input.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.frame_search_input.setStyleSheet("""
            QLineEdit {
                background-color: #2a2a2a;
                border: 1px solid #606060;
                border-radius: 4px;
                color: #ffffff;
                padding: 8px;
                font-size: 11px;
                font-weight: bold;
            }
            QLineEdit:focus {
                border-color: #00D4AA;
            }
            QLineEdit:hover {
                border-color: #00D4AA;
            }
        """)
        filter_layout.addWidget(self.frame_search_input)
        
        return filter_widget
        
        # Open application in full screen for more space
        self.showMaximized()
        
    def setup_ui(self):
        """Inicializar os componentes da interface do usuário."""
        self.setWindowTitle("SETERA - Simulador CANBUS - Pedro Silva + IA")
        self.setMinimumSize(QSize(900, 600))  # Tamanho mínimo mais flexível
        
        # Definir ícone da janela (favicon da empresa)
        try:
            icon_path = Path("favicon.ico")
            if icon_path.exists():
                self.setWindowIcon(QIcon(str(icon_path)))
        except Exception:
            pass  # Falha silenciosa para distribuição
        
        # Widget central e layout principal
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)
        
        # === CONTROL AREA: UNIFIED CONTROL PANEL (full width) ===
        control_container = QWidget()
        control_container.setMaximumHeight(90)
        control_container.setMinimumHeight(90)
        control_main_layout = QHBoxLayout(control_container)
        control_main_layout.setSpacing(0)
        control_main_layout.setContentsMargins(0, 0, 0, 0)
        
        # === UNIFIED CONTROL PANEL ===
        control_group = QGroupBox("Painel de Controle")
        control_layout = QHBoxLayout(control_group)
        control_layout.setSpacing(12)
        control_layout.setContentsMargins(15, 15, 15, 15)
        
        # Botões toggle
        self.btn_toggle_record = QPushButton("🔴 REC")
        self.btn_toggle_record.setToolTip("Iniciar/encerra a gravação dos dados CAN")
        
        # Dropdown de baudrate
        self.baudrate_combo = QComboBox()
        self.baudrate_combo.addItems(["125 kbps", "250 kbps", "500 kbps", "1000 kbps"])
        self.baudrate_combo.setCurrentText("500 kbps")  # Padrão
        self.baudrate_combo.setToolTip("Selecione a velocidade do barramento CAN")
        self.baudrate_combo.setStyleSheet("""
            QComboBox {
                background-color: #404040;
                border: 2px solid #606060;
                border-radius: 6px;
                padding: 6px 8px;
                font-weight: bold;
                font-size: 11px;
                color: #ffffff;
                min-width: 60px;
            }
            QComboBox:hover {
                border-color: #00D4AA;
            }
            QComboBox::drop-down {
                border: none;
                width: 0px;
                height: 0px;
            }
            QComboBox::down-arrow {
                width: 0px;
                height: 0px;
                border: none;
                background: none;
            }
            QComboBox QAbstractItemView {
                background-color: #404040;
                border: 1px solid #606060;
                color: #ffffff;
                selection-background-color: #00D4AA;
            }
        """)
        
        # TESTE checkbox for offline playback
        self.checkbox_teste = QCheckBox("TESTE")
        self.checkbox_teste.setStyleSheet("""
            QCheckBox {
                color: #ffffff;
                font-size: 10px;
                font-weight: bold;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 2px solid #606060;
                border-radius: 3px;
                background-color: #404040;
            }
            QCheckBox::indicator:checked {
                background-color: #FF6B6B;
                border-color: #FF6B6B;
            }
            QCheckBox::indicator:hover {
                border-color: #FF6B6B;
            }
        """)
        self.checkbox_teste.setToolTip("Modo TESTE: Reprodução offline sem interface CAN (ideal para análise de logs)")
        self.checkbox_teste.setChecked(False)
        
        self.btn_toggle_playback = QPushButton("▶️ PLAY")
        self.btn_toggle_playback.setToolTip("Inicia/encerra a simulação da rede CAN")
        
        # Checkbox para modo de reprodução contínua
        self.checkbox_continuous = QCheckBox("Play\n10ms")
        self.checkbox_continuous.setStyleSheet("""
            QCheckBox {
                color: #ffffff;
                font-size: 10px;
                font-weight: bold;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 2px solid #606060;
                border-radius: 3px;
                background-color: #404040;
            }
            QCheckBox::indicator:checked {
                background-color: #00D4AA;
                border-color: #00D4AA;
            }
            QCheckBox::indicator:hover {
                border-color: #00D4AA;
            }
        """)
        self.checkbox_continuous.setToolTip("Marque para enviar frames a cada 10ms")
        self.checkbox_continuous.setChecked(False)  # Enabled by default
        
        self.btn_toggle_monitor = QPushButton("👁️ MON")
        self.btn_toggle_monitor.setToolTip("Inicia/encerra a visualização dos dados da rede CAN em tempo real")
        
        # ✅ SIMULATION BUTTON - Initially disabled, only enabled during playback
        self.btn_simulation = QPushButton("🔬 SIM")
        self.btn_simulation.setToolTip("Abrir simulação em tempo real de parâmetros J1939 (disponível apenas durante reprodução)")
        self.btn_simulation.setEnabled(False)  # Disabled until playback starts
        
        # Seleção de arquivo
        self.btn_select_file = QPushButton("📁 LOG")
        self.btn_select_file.setToolTip("Seleciona o arquivo de log a ser simulado")
        
        # Timer display
        self.timer_label = QLabel("T: 00:00:00")
        self.timer_label.setStyleSheet("color: #00D4AA; font-weight: bold; font-size: 12px;")
        self.timer_label.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Preferred)
        
        # FPS display
        self.fps_label = QLabel("FPS: 0.0")
        self.fps_label.setStyleSheet("color: #FFD700; font-weight: bold; font-size: 12px;")
        self.fps_label.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Preferred)
        
        # Button height will be set after all buttons are created
        button_height = 35
        
        # Frame filter widget (moved from analysis panel)
        self.frame_filter_widget = self._create_frame_filter_widget()
        self.frame_filter_widget.setToolTip("Filtrar frames específicos para análise")
        
        # Graphics button (moved from analysis panel)
        graph_button_container = QWidget()
        graph_button_layout = QHBoxLayout(graph_button_container)
        graph_button_layout.setContentsMargins(0, 0, 0, 0)
        graph_button_layout.setSpacing(0)
        graph_button_container.setMinimumHeight(35)
        graph_button_container.setMaximumHeight(35)
        graph_button_container.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        
        self.btn_grafico = QPushButton("📊 Gráfico")
        self.btn_grafico.setMinimumHeight(35)
        self.btn_grafico.setMaximumHeight(35)
        self.btn_grafico.setMinimumWidth(80)
        self.btn_grafico.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.btn_grafico.setToolTip("Abrir gráfico em tempo real para análise visual do frame filtrado")
        self.btn_grafico.setEnabled(False)
        graph_button_layout.addWidget(self.btn_grafico, alignment=Qt.AlignmentFlag.AlignVCenter)
        
        # Layout dos controles - UNIFIED CONTROL PANEL (single line)
        control_layout.addWidget(self.btn_toggle_record)
        control_layout.addWidget(self.baudrate_combo)
        control_layout.addWidget(self.checkbox_teste)
        control_layout.addWidget(self.btn_toggle_playback)
        control_layout.addWidget(self.checkbox_continuous)
        control_layout.addWidget(self.btn_toggle_monitor)
        control_layout.addWidget(self.btn_simulation)
        control_layout.addWidget(self.btn_select_file)
        control_layout.addWidget(self.frame_filter_widget)
        control_layout.addWidget(graph_button_container)
        control_layout.addStretch()  # Espaço flexível
        
        # Timer e FPS à direita do painel de controle (vertical stack)
        info_layout = QVBoxLayout()
        info_layout.addWidget(self.timer_label)
        info_layout.addWidget(self.fps_label)
        control_layout.addLayout(info_layout)
        
        # Add unified panel to main layout (full width)
        control_main_layout.addWidget(control_group, 1)
        
        main_layout.addWidget(control_container)
        
        # Configure button and combo box sizes after all are created
        for btn in [self.btn_toggle_record, self.btn_toggle_playback,
                   self.btn_toggle_monitor, self.btn_simulation, self.btn_select_file, self.btn_grafico]:
            btn.setMinimumHeight(button_height)
            btn.setMaximumHeight(button_height)
            btn.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
            btn.setMinimumWidth(80)
        
        # Configure combo box sizes
        self.baudrate_combo.setMinimumHeight(button_height)
        self.baudrate_combo.setMaximumHeight(button_height)
        
        # Configure checkbox sizes
        self.checkbox_teste.setMinimumHeight(button_height)
        self.checkbox_teste.setMaximumHeight(button_height)
        
        # Frame filter widget has its own internal sizing
        
        # === BARRA DE PROGRESSO ===
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setMaximumHeight(25)
        main_layout.addWidget(self.progress_bar)
        
        # === ÁREA DE CONTEÚDO (3 SEÇÕES: 1/3 cada) ===
        content_widget = QWidget()
        content_layout = QHBoxLayout(content_widget)
        content_layout.setSpacing(15)  # Espaçamento entre as áreas
        content_layout.setContentsMargins(0, 0, 0, 0)
        
        # Área de mensagens CAN (LADO ESQUERDO - 1/3)
        message_group = QGroupBox("Mensagens CAN")
        message_layout = QVBoxLayout(message_group)
        message_layout.setContentsMargins(10, 20, 10, 10)
        
        self.message_display = QTextEdit()
        self.message_display.setReadOnly(True)
        self.message_display.setFont(QFont("Consolas", 10))
        # Política de redimensionamento responsiva
        self.message_display.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        message_layout.addWidget(self.message_display)
        
        # Área de análise (CENTRO - 1/3)
        analysis_group = QGroupBox("Análise")
        analysis_layout = QVBoxLayout(analysis_group)
        analysis_layout.setContentsMargins(10, 20, 10, 10)
        
        self.analysis_display = QTextEdit()
        self.analysis_display.setReadOnly(True)
        self.analysis_display.setFont(QFont("Consolas", 10))
        # Política de redimensionamento responsiva
        self.analysis_display.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        analysis_layout.addWidget(self.analysis_display)
        
        # Área de status/log (LADO DIREITO - 1/3)
        status_group = QGroupBox("Status e Logs")
        status_layout = QVBoxLayout(status_group)
        status_layout.setContentsMargins(10, 20, 10, 10)
        
        self.status_display = QTextEdit()
        self.status_display.setReadOnly(True)
        self.status_display.setFont(QFont("Consolas", 9))
        # Política de redimensionamento responsiva
        self.status_display.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        status_layout.addWidget(self.status_display)
        
        # Adicionar ao layout de conteúdo com proporções iguais (1/3 cada)
        content_layout.addWidget(message_group, 1)     # 1/3 do espaço - CAN Messages
        content_layout.addWidget(analysis_group, 1)    # 1/3 do espaço - Analysis
        content_layout.addWidget(status_group, 1)      # 1/3 do espaço - Status & Logs
        
        main_layout.addWidget(content_widget)
        
        # === BARRA DE STATUS ===
        self.status_bar = QStatusBar()
        self.status_bar.setMaximumHeight(25)
        self.setStatusBar(self.status_bar)
        
        # Label do arquivo atual
        self.file_label = QLabel(f"Arquivo atual: {self.log_filename}")
        self.file_label.setStyleSheet("color: #00D4AA; font-weight: bold;")
        self.status_bar.addPermanentWidget(self.file_label)
        
        # Status inicial
        self.status_bar.showMessage("Pronto - Temporização Precisa - Carimbos de tempo do log exatos preservados")
        
    def setup_theme(self):
        """Aplicar tema escuro moderno com visibilidade adequada do texto."""
        
        # Estilo principal da aplicação com texto brilhante e legível
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e1e;
                color: #ffffff;
            }
            
            QGroupBox {
                font-weight: bold;
                font-size: 12px;
                border: 2px solid #404040;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 8px;
                background-color: #2a2a2a;
                color: #ffffff;
            }
            
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 8px 0 8px;
                color: #00D4AA;
                font-size: 13px;
                font-weight: bold;
            }
            
            QPushButton {
                background-color: #404040;
                border: 2px solid #606060;
                border-radius: 6px;
                padding: 6px 12px;
                font-weight: bold;
                font-size: 11px;
                color: #ffffff;
            }
            
            QPushButton:hover {
                background-color: #505050;
                border-color: #00D4AA;
                color: #00D4AA;
            }
            
            QPushButton:pressed {
                background-color: #353535;
                border-color: #00A085;
            }
            
            QPushButton:disabled {
                background-color: #2a2a2a;
                border-color: #3a3a3a;
                color: #666666;
            }
            
            QTextEdit {
                background-color: #1a1a1a;
                border: 1px solid #404040;
                border-radius: 4px;
                padding: 8px;
                color: #ffffff;
                font-family: "Consolas", "Courier New", monospace;
                selection-background-color: #2A82DA;
                selection-color: #ffffff;
            }
            
            QProgressBar {
                border: 1px solid #404040;
                border-radius: 4px;
                text-align: center;
                background-color: #2a2a2a;
                color: #ffffff;
                font-weight: bold;
            }
            
            QProgressBar::chunk {
                background-color: #00D4AA;
                border-radius: 3px;
            }
            
            QStatusBar {
                background-color: #2a2a2a;
                border-top: 1px solid #404040;
                color: #ffffff;
                font-size: 11px;
            }
            
            QLabel {
                color: #ffffff;
            }
            
            /* Estilo para QMessageBox (caixas de diálogo de erro) */
            QMessageBox {
                background-color: #2a2a2a;
                color: #ffffff;
            }
            QMessageBox QLabel {
                color: #ffffff;
                background-color: transparent;
            }
            QMessageBox QPushButton {
                background-color: #404040;
                border: 2px solid #606060;
                border-radius: 6px;
                padding: 6px 12px;
                color: #ffffff;
                font-weight: bold;
                min-width: 70px;
            }
            QMessageBox QPushButton:hover {
                background-color: #505050;
                border-color: #00D4AA;
                color: #00D4AA;
            }
        """)
        
    def get_selected_bitrate(self) -> int:
        """Obter o bitrate selecionado no dropdown."""
        baudrate_text = self.baudrate_combo.currentText()
        baudrate_map = {
            "125 kbps": 125000,
            "250 kbps": 250000,
            "500 kbps": 500000,
            "1000 kbps": 1000000
        }
        return baudrate_map.get(baudrate_text, 250000)
    
    
    def cleanup_all_workers(self):
        """Ensure all workers are completely stopped and cleaned up."""
        try:
            # Stop recording worker
            if self.recording_worker is not None and self.recording_worker.isRunning():
                self.recording_worker.stop_recording()
                if not self.recording_worker.wait(2000):
                    self.recording_worker.terminate()
                    self.recording_worker.wait(1000)
                self.recording_worker = None
            
            # Stop playback worker
            if self.playback_worker is not None and self.playback_worker.isRunning():
                self.playback_worker.stop_playback()
                if not self.playback_worker.wait(2000):
                    self.playback_worker.terminate()
                    self.playback_worker.wait(1000)
                self.playback_worker = None
            
            # Stop monitor worker
            if self.monitor_worker is not None and self.monitor_worker.isRunning():
                self.monitor_worker.stop_monitoring()
                if not self.monitor_worker.wait(2000):
                    self.monitor_worker.terminate()
                    self.monitor_worker.wait(1000)
                self.monitor_worker = None
                
        except Exception as e:
            self.log_status(f"Erro durante limpeza de workers: {str(e)}")
    
    def get_bitrate_text(self, bitrate: int) -> str:
        """Converter bitrate numérico para texto."""
        bitrate_map = {
            125000: "125 kbps",
            250000: "250 kbps",
            500000: "500 kbps",
            1000000: "1000 kbps"
        }
        return bitrate_map.get(bitrate, f"{bitrate} bps")
    
    
    def setup_connections(self):
        """Conectar sinais e slots para interações da UI."""
        # Conexões dos botões
        self.btn_toggle_record.clicked.connect(self.toggle_recording)
        self.btn_toggle_playback.clicked.connect(self.toggle_playback)
        self.btn_toggle_monitor.clicked.connect(self.toggle_monitoring)
        self.btn_simulation.clicked.connect(self.toggle_simulation)
        self.btn_select_file.clicked.connect(self.select_log_file)
        
        # Analysis connections (no longer toggleable)
        self.frame_search_input.textChanged.connect(self.on_frame_search_changed)
        self.btn_grafico.clicked.connect(self.abrir_janela_grafico)
        
    def update_timer(self):
        """Atualizar o display do timer."""
        self.elapsed_seconds += 1
        hours = self.elapsed_seconds // 3600
        minutes = (self.elapsed_seconds % 3600) // 60
        seconds = self.elapsed_seconds % 60
        self.timer_label.setText(f"Tempo: {hours:02d}:{minutes:02d}:{seconds:02d}")
        
    def reset_timer(self):
        """Resetar o timer."""
        self.elapsed_seconds = 0
        self.timer_label.setText("Tempo: 00:00:00")
        
    def update_fps(self):
        """MÉTODO DESABILITADO - Usar apenas FPS real."""
        pass
        
    def add_message_timestamp(self):
        """MÉTODO DESABILITADO - Usar apenas FPS real."""
        pass
        
    def add_actual_transmission_timestamp(self):
        """Adicionar timestamp de transmissão real para cálculo de FPS real."""
        current_time = time.perf_counter()
        self.actual_transmission_timestamps.append(current_time)
        
    def update_real_fps(self):
        """Atualizar o cálculo de FPS real baseado em transmissões CAN."""
        current_time = time.perf_counter()
        
        # Remover timestamps antigos (mais de 5 segundos)
        while self.actual_transmission_timestamps and current_time - self.actual_transmission_timestamps[0] > 5.0:
            self.actual_transmission_timestamps.popleft()
        
        # Calcular FPS real baseado nos últimos 5 segundos
        if len(self.actual_transmission_timestamps) > 1:
            time_span = current_time - self.actual_transmission_timestamps[0]
            if time_span > 0:
                self.real_fps = len(self.actual_transmission_timestamps) / time_span
            else:
                self.real_fps = 0.0
        else:
            self.real_fps = 0.0
            
        # Atualizar display com FPS real
        self.fps_label.setText(f"Frames/s: {self.real_fps:.1f}")
        
    def log_status(self, message: str):
        """Adicionar uma mensagem com timestamp ao display de status."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"<span style='color: #00D4AA;'>[{timestamp}]</span> <span style='color: #ffffff;'>{message}</span>"
        self.status_display.append(formatted_message)
        
        # Ensure auto-scroll to bottom for status display
        scrollbar = self.status_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        
        self.status_bar.showMessage(message)
        
    def toggle_recording(self):
        """Alternar gravação de mensagens CAN bus."""
        if not self.is_recording:
            self.start_recording()
        else:
            self.stop_recording()
            
    def toggle_playback(self):
        """Alternar reprodução de mensagens CAN bus."""
        if not self.is_playing:
            self.start_playback()
        else:
            self.stop_playback()
            
    def toggle_monitoring(self):
        """Alternar monitoramento de mensagens CAN bus."""
        if not self.is_monitoring:
            self.start_monitoring()
        else:
            self.stop_monitoring()
    
    def toggle_simulation(self):
        """Alternar janela de simulação J1939."""
        if not SIMULACAO_DISPONIVEL:
            QMessageBox.critical(self, "Erro",
                               "Funcionalidade de simulação não disponível!\n\n"
                               "Verifique se o módulo simulation.py está presente.")
            return
        
        if self.simulation_window is None or not self.simulation_window.isVisible():
            # Abrir janela de simulação
            try:
                self.simulation_window = create_simulation_window(self)
                self.simulation_window.show()
                self.log_status("Janela de simulação J1939 aberta")
            except Exception as e:
                QMessageBox.critical(self, "Erro",
                                   f"Erro ao abrir janela de simulação:\n{str(e)}")
        else:
            # Fechar janela de simulação
            self.simulation_window.close()
            self.simulation_window = None
            self.log_status("Janela de simulação J1939 fechada")
    
    # Removed toggle_analysis_mode and toggle_sort_mode methods
    # Analysis mode is now always enabled with volatility sorting
    
    def on_frame_search_changed(self, text: str):
        """Handle search input changes for real-time filtering."""
        if not self.analysis_state['enabled']:
            return
        
        # Store the search filter text
        self.analysis_state['search_filter'] = text.upper().strip()
        
        # Trigger display update immediately for real-time filtering
        if not self._gui_update_pending:
            self._gui_update_pending = True
            self._gui_update_timer.setInterval(100)  # Faster update for real-time feel
            self._gui_update_timer.start()
        
        # No verbose logging - only log when filter is cleared
        if not text.strip():
            self.log_status("Filtro removido - mostrando todos os frames")
    
    def _update_graphics_button_state(self):
        """Update graphics button state based on basic availability."""
        if not GRAFICOS_DISPONIVEL:
            self.btn_grafico.setEnabled(False)
            self.btn_grafico.setToolTip("Gráficos não disponíveis - Instale PyQtGraph ou Matplotlib")
            return
        
        # Analysis mode is always enabled now, so skip that check
        # Default state - will be updated by display method
        self.btn_grafico.setEnabled(False)
        self.btn_grafico.setToolTip("Digite um filtro para selecionar um frame específico")
    
    def _update_graphics_button_state_from_display(self, filtered_frame_ids: list):
        """Update graphics button state based on frames actually displayed."""
        if not GRAFICOS_DISPONIVEL:
            self.btn_grafico.setEnabled(False)
            self.btn_grafico.setToolTip("Gráficos não disponíveis - Instale PyQtGraph ou Matplotlib")
            return
        
        # Analysis mode is always enabled now, so skip that check
        
        # Check number of filtered frames actually being displayed
        if len(filtered_frame_ids) == 1:
            # Exactly one frame displayed - enable button
            frame_id = filtered_frame_ids[0]
            self.btn_grafico.setEnabled(True)
            self.btn_grafico.setToolTip(f"Abrir gráfico em tempo real para o frame {frame_id}")
        elif len(filtered_frame_ids) > 1:
            # Multiple frames displayed - disable button
            self.btn_grafico.setEnabled(False)
            self.btn_grafico.setToolTip(f"Filtro exibe {len(filtered_frame_ids)} frames - seja mais específico")
        else:
            # No frames displayed - disable button
            self.btn_grafico.setEnabled(False)
            self.btn_grafico.setToolTip("Nenhum frame sendo exibido - ajuste o filtro")
    
    def abrir_janela_grafico(self):
        """Open graphics window for the currently filtered frame."""
        if not GRAFICOS_DISPONIVEL:
            QMessageBox.critical(self, "Erro",
                               "Funcionalidade de gráficos não disponível!\n\n"
                               "Instale uma das bibliotecas:\n"
                               "pip install pyqtgraph\n"
                               "ou\n"
                               "pip install matplotlib")
            return
        
        if not self.analysis_state['enabled']:
            QMessageBox.warning(self, "Aviso", "Ative o modo de análise primeiro.")
            return
        
        # Get currently filtered frames (same logic as display)
        sorted_frame_ids = self._get_sorted_frame_ids()
        
        # Apply frame filtering if in analysis mode with search filter
        if self.analysis_state['enabled'] and self.analysis_state['search_filter']:
            search_filter = self.analysis_state['search_filter']
            filtered_frame_ids = [fid for fid in sorted_frame_ids
                                 if search_filter in fid.upper()]
        else:
            filtered_frame_ids = sorted_frame_ids
        
        if len(filtered_frame_ids) != 1:
            if len(filtered_frame_ids) == 0:
                QMessageBox.warning(self, "Aviso", "Nenhum frame encontrado com este filtro.")
            else:
                QMessageBox.warning(self, "Aviso",
                                  f"Filtro exibe {len(filtered_frame_ids)} frames.\n"
                                  "Seja mais específico para selecionar apenas um frame.")
            return
        
        frame_id = filtered_frame_ids[0]
        
        # Check if window is already open for this frame
        if frame_id in self.janelas_graficos:
            # Bring existing window to front
            janela = self.janelas_graficos[frame_id]
            janela.show()
            janela.raise_()
            janela.activateWindow()
            return
        
        # Create new graphics window
        try:
            janela_grafico = GraficoCANDialog(frame_id, self)
            janela_grafico.janela_fechada.connect(lambda: self._on_janela_grafico_fechada(frame_id))
            
            # Store reference
            self.janelas_graficos[frame_id] = janela_grafico
            
            # Show window
            janela_grafico.show()
            
            self.log_status(f"Janela de gráfico aberta para frame {frame_id}")
            
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao abrir janela de gráfico:\n{str(e)}")
    
    def _on_janela_grafico_fechada(self, frame_id: str):
        """Handle when a graphics window is closed."""
        if frame_id in self.janelas_graficos:
            del self.janelas_graficos[frame_id]
        self.log_status(f"Janela de gráfico fechada para frame {frame_id}")
        
    def start_recording(self):
        """Iniciar gravação de mensagens CAN bus."""
        if self.recording_worker is not None and self.recording_worker.isRunning():
            return
            
        # Parar outras operações
        if self.is_playing:
            self.stop_playback()
        if self.is_monitoring:
            self.stop_monitoring()
            
        # Manual bitrate selection
        selected_bitrate = self.get_selected_bitrate()
        self.start_recording_with_bitrate(selected_bitrate)
    
    def start_recording_with_bitrate(self, bitrate: int):
        """Iniciar gravação com bitrate específico (Canal 1 apenas)."""
        self.log_status("Inicializando gravação...")
        
        # Atualizar estado da UI
        self.is_recording = True
        self.btn_toggle_record.setText("⏹️ STOP")
        self.btn_toggle_playback.setEnabled(False)
        self.btn_toggle_monitor.setEnabled(False)
        self.checkbox_continuous.setEnabled(False)
        self.baudrate_combo.setEnabled(False)
        self.message_display.clear()
        self.message_buffer.clear()
        self._pending_messages.clear()
        self.frame_id_change_history.clear()
        
        # Clear analysis state for fresh start
        self.analysis_state['sort_cache']['last_sort_time'] = 0.0
        self.analysis_state['sort_cache']['sorted_frame_ids'] = []
        
        # Start the GUI update timer to process messages
        self._gui_update_timer.start()
        
        # Iniciar timer
        self.reset_timer()
        self.operation_timer.start(1000)
        
        # Criar e iniciar worker de gravação (Canal 1 apenas)
        self.recording_worker = RecordingWorker(self.log_filename, 0, bitrate)
        
        # Conectar sinais do worker
        self.recording_worker.message_received.connect(self.on_message_received)
        self.recording_worker.actual_transmission.connect(self.add_actual_transmission_timestamp)
        self.recording_worker.status_update.connect(self.log_status)
        self.recording_worker.error_occurred.connect(self.on_error)
        self.recording_worker.recording_stopped.connect(self.on_recording_stopped)
        
        self.recording_worker.start()
        
    def stop_recording(self):
        """Parar gravação de mensagens CAN bus."""
        if self.recording_worker is not None and self.recording_worker.isRunning():
            self.log_status("Parando gravação...")
            self.recording_worker.stop_recording()
            
            # Aguardar a parada da thread com timeout
            if not self.recording_worker.wait(3000):  # 3 segundos
                self.log_status("Forçando parada da gravação...")
                self.recording_worker.terminate()
                self.recording_worker.wait(1000)
            
    def start_playback(self):
        """Iniciar reprodução de mensagens CAN bus."""
        if self.playback_worker is not None and self.playback_worker.isRunning():
            return
            
        # Verificar se o arquivo de log existe
        if not Path(self.log_filename).exists():
            QMessageBox.warning(
                self,
                "Arquivo Não Encontrado",
                f"Arquivo de log '{self.log_filename}' não encontrado!\nPor favor, grave alguns dados primeiro ou selecione um arquivo existente."
            )
            return
            
        # Parar outras operações
        if self.is_recording:
            self.stop_recording()
        if self.is_monitoring:
            self.stop_monitoring()
            
        # Manual bitrate selection
        selected_bitrate = self.get_selected_bitrate()
        continuous_mode = self.checkbox_continuous.isChecked()
        self.start_playback_with_bitrate(selected_bitrate, continuous_mode)
    
    def start_playback_with_bitrate(self, bitrate: int, continuous_mode: bool = None):
        """Iniciar reprodução com bitrate específico (Canal 1 apenas)."""
        if continuous_mode is None:
            continuous_mode = self.checkbox_continuous.isChecked()
        
        test_mode = self.checkbox_teste.isChecked()
        mode_text = "10ms" if continuous_mode else "com tempo original"
        
        if test_mode:
            self.log_status(f"Inicializando reprodução TESTE {mode_text} (sem interface CAN)")
        else:
            self.log_status(f"Inicializando reprodução {mode_text}")
        
        # Atualizar estado da UI
        self.is_playing = True
        self.btn_toggle_playback.setText("⏹️ STOP")
        self.btn_toggle_record.setEnabled(False)
        self.btn_toggle_monitor.setEnabled(False)
        self.checkbox_continuous.setEnabled(False)
        self.checkbox_teste.setEnabled(False)
        self.baudrate_combo.setEnabled(False if not test_mode else True)  # Keep baudrate enabled in test mode for reference
        self.message_display.clear()
        self.message_buffer.clear()
        self._pending_messages.clear()
        self.frame_id_change_history.clear()
        
        # Clear analysis state for fresh start
        self.analysis_state['sort_cache']['last_sort_time'] = 0.0
        self.analysis_state['sort_cache']['sorted_frame_ids'] = []
        
        # Start the GUI update timer to process messages
        self._gui_update_timer.start()
        
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        # Iniciar timer
        self.reset_timer()
        self.operation_timer.start(1000)
        
        # Criar e iniciar worker de reprodução (Canal 1 apenas)
        self.playback_worker = PlaybackWorker(self.log_filename, continuous_mode, 0, bitrate, self.simulation_params, test_mode)
        
        # Conectar sinais do worker
        self.playback_worker.message_sent.connect(self.on_message_sent)
        self.playback_worker.actual_transmission.connect(self.add_actual_transmission_timestamp)
        self.playback_worker.status_update.connect(self.log_status)
        self.playback_worker.error_occurred.connect(self.on_error)
        self.playback_worker.playback_stopped.connect(self.on_playback_stopped)
        self.playback_worker.progress_update.connect(self.progress_bar.setValue)
        
        self.playback_worker.start()
        
        # ✅ Initialize analysis mode state in worker
        self.playback_worker.set_analysis_mode(self.analysis_state['enabled'])
        
        # ✅ Enable simulation button only when playback is active
        self.btn_simulation.setEnabled(True)
        
    def stop_playback(self):
        """Parar reprodução de mensagens CAN bus."""
        if self.playback_worker is not None and self.playback_worker.isRunning():
            self.log_status("Parando reprodução...")
            self.playback_worker.stop_playback()
            
            # ✅ Disable simulation button and close simulation window immediately
            self.btn_simulation.setEnabled(False)
            if self.simulation_window is not None and self.simulation_window.isVisible():
                try:
                    self.simulation_window.close()
                    self.simulation_window = None
                except:
                    pass
            
            # Aguardar a parada da thread com timeout
            if not self.playback_worker.wait(3000):  # 3 segundos
                self.log_status("Forçando parada da reprodução...")
                self.playback_worker.terminate()
                self.playback_worker.wait(1000)  # 1 segundo para terminar
            
    def start_monitoring(self):
        """Iniciar monitoramento de mensagens CAN bus."""
        if self.monitor_worker is not None and self.monitor_worker.isRunning():
            return
            
        # Parar outras operações
        if self.is_recording:
            self.stop_recording()
        if self.is_playing:
            self.stop_playback()
            
        # Manual bitrate selection
        selected_bitrate = self.get_selected_bitrate()
        self.start_monitoring_with_bitrate(selected_bitrate)
    
    def start_monitoring_with_bitrate(self, bitrate: int):
        """Iniciar monitoramento com bitrate específico (Canal 1 apenas)."""
        self.log_status("Inicializando monitoramento...")
        
        # Atualizar estado da UI
        self.is_monitoring = True
        self.btn_toggle_monitor.setText("⏹️ STOP")
        self.btn_toggle_record.setEnabled(False)
        self.btn_toggle_playback.setEnabled(False)
        self.checkbox_continuous.setEnabled(False)
        self.baudrate_combo.setEnabled(False)
        self.message_display.clear()
        self.message_buffer.clear()
        self._pending_messages.clear()
        self.frame_id_change_history.clear()
        
        # Clear analysis state for fresh start
        self.analysis_state['sort_cache']['last_sort_time'] = 0.0
        self.analysis_state['sort_cache']['sorted_frame_ids'] = []
        
        # Start the GUI update timer to process messages
        self._gui_update_timer.start()
        
        # Iniciar timer
        self.reset_timer()
        self.operation_timer.start(1000)
        
        # Criar e iniciar worker de monitoramento (Canal 1 apenas)
        self.monitor_worker = MonitorWorker(0, bitrate)
        
        # Conectar sinais do worker
        self.monitor_worker.message_received.connect(self.on_message_monitored)
        self.monitor_worker.actual_transmission.connect(self.add_actual_transmission_timestamp)
        self.monitor_worker.status_update.connect(self.log_status)
        self.monitor_worker.error_occurred.connect(self.on_error)
        self.monitor_worker.monitoring_stopped.connect(self.on_monitoring_stopped)
        
        self.monitor_worker.start()
        
    def stop_monitoring(self):
        """Parar monitoramento de mensagens CAN bus."""
        if self.monitor_worker is not None and self.monitor_worker.isRunning():
            self.log_status("Parando monitoramento...")
            self.monitor_worker.stop_monitoring()
            
            # Aguardar a parada da thread com timeout
            if not self.monitor_worker.wait(5000):  # Increased timeout to 5 seconds for better reliability
                self.log_status("Forçando parada do monitoramento...")
                self.monitor_worker.terminate()
                self.monitor_worker.wait(2000)  # Increased termination wait time
            
    def select_log_file(self):
        """Abrir diálogo de arquivo para selecionar um arquivo de log."""
        file_dialog = QFileDialog(self)
        file_dialog.setNameFilter("Arquivos de Log ASC (*.asc);;Todos os Arquivos (*)")
        file_dialog.setDefaultSuffix("asc")
        
        if file_dialog.exec() == QFileDialog.DialogCode.Accepted:
            selected_files = file_dialog.selectedFiles()
            if selected_files:
                self.log_filename = selected_files[0]
                self.file_label.setText(f"Arquivo atual: {Path(self.log_filename).name}")
                self.log_status(f"Arquivo selecionado: {self.log_filename}")
                
    def on_message_received(self, message: str):
        """Lidar com mensagem CAN recebida durante gravação."""
        # Não usar mais add_message_timestamp para FPS - usar apenas para GUI
        formatted_msg = f"<span style='color: #00FF80;'>RX:</span> <span style='color: #ffffff;'>{message}</span>"
        self._queue_message_update(formatted_msg)
        
    def on_message_sent(self, message: str):
        """Lidar com mensagem CAN enviada durante reprodução."""
        # Não usar mais add_message_timestamp para FPS - usar apenas para GUI
        formatted_msg = f"<span style='color: #FFD700;'>TX:</span> <span style='color: #ffffff;'>{message}</span>"
        self._queue_message_update(formatted_msg)
        
    def on_message_monitored(self, message: str):
        """Lidar com mensagem CAN monitorada."""
        # Não usar mais add_message_timestamp para FPS - usar apenas para GUI
        formatted_msg = f"<span style='color: #87CEEB;'>MON:</span> <span style='color: #ffffff;'>{message}</span>"
        self._queue_message_update(formatted_msg)
    
    def _queue_message_update(self, formatted_msg: str):
        """
        Enfileirar mensagem para atualização em lote da GUI.
        Evita travamentos por excesso de atualizações da interface.
        Agora suporta exibição simultânea: fluxo normal (esquerda) + análise (centro).
        """
        # Always add to normal flow (LEFT PANE - message_display)
        self.message_buffer.append(formatted_msg)
        self._pending_messages.append(formatted_msg)
        
        # Always process for Frame ID grouping (CENTER PANE - analysis_display)
        # since analysis mode is always enabled
        should_update_gui = self._process_frameid_message(formatted_msg)
        
        # Update GUI when batching threshold is reached for analysis pane
        if should_update_gui and not self._gui_update_pending:
            self._gui_update_pending = True
            # Use optimal interval for smooth frame flow display
            self._gui_update_timer.setInterval(100)  # 100ms for smooth real-time display
            self._gui_update_timer.start()
    
    def _process_frameid_message(self, formatted_msg: str):
        """
        Process message for Frame ID grouping mode.
        Extract Frame ID and update the grouped data structure.
        Optimized for performance with precompiled regex and batching.
        Tracks byte changes for dynamic blue shading visualization.
        """
        # Use precompiled regex pattern for better performance
        match = self._frameid_pattern.search(formatted_msg)
        
        if match:
            prefix = match.group(1).strip()  # RX, TX, or MON
            frame_id = match.group(2).strip()  # Frame ID in hex
            data_part = match.group(3).strip()  # Byte data
            
            current_time = time.perf_counter()
            
            # Parse byte data into individual bytes
            byte_values = data_part.split()
            
            # Track byte changes for blue shading
            self._track_byte_changes(frame_id, byte_values, current_time)
            
            # Calculate volatility metrics if in analysis mode
            volatility_metrics = {}
            if self.analysis_state['enabled']:
                volatility_metrics = self._calculate_frame_volatility(frame_id)
            
            # Store/update Frame ID data efficiently with enhanced analysis data
            self.frame_id_data[frame_id] = {
                'prefix': prefix,
                'data': data_part,
                'byte_values': byte_values,
                'formatted_msg': formatted_msg,
                'last_update': current_time,
                # Enhanced fields for analysis
                'aggregate_change_rate': volatility_metrics.get('aggregate_change_rate', 0.0),
                'max_byte_change_rate': volatility_metrics.get('max_byte_change_rate', 0.0),
                'active_bytes_count': volatility_metrics.get('active_bytes_count', 0),
                'volatility_score': volatility_metrics.get('volatility_score', 0.0)
            }
            
            # No need to update filter options - using real-time search filtering
            
            # Reduced batching for smooth real-time display - trigger GUI update every 2 messages
            self._frameid_update_counter += 1
            if self._frameid_update_counter >= 2:
                self._frameid_update_counter = 0
                # Only trigger GUI update for batched updates
                return True
            else:
                # Skip GUI update for this message
                return False
        return False
    
    def _calculate_frame_volatility(self, frame_id: str) -> dict:
        """
        Calculate comprehensive volatility metrics for a frame.
        Returns dict with aggregate_change_rate, max_byte_change_rate, active_bytes_count, volatility_score.
        """
        if frame_id not in self.frame_id_change_history:
            return {
                'aggregate_change_rate': 0.0,
                'max_byte_change_rate': 0.0,
                'active_bytes_count': 0,
                'volatility_score': 0.0
            }
        
        frame_history = self.frame_id_change_history[frame_id]
        
        # Calculate metrics
        aggregate_change_rate = 0.0
        max_byte_change_rate = 0.0
        active_bytes_count = 0
        
        for byte_pos, byte_data in frame_history.items():
            change_rate = byte_data.get('change_rate', 0.0)
            aggregate_change_rate += change_rate
            
            if change_rate > 0:
                active_bytes_count += 1
            
            if change_rate > max_byte_change_rate:
                max_byte_change_rate = change_rate
        
        # Calculate weighted volatility score
        # 40% weight on total change rate, 30% on peak rate, 20% on active bytes, 10% on consistency
        volatility_score = (
            (aggregate_change_rate * 0.4) +
            (max_byte_change_rate * 0.3) +
            (active_bytes_count * 0.2) +
            (min(aggregate_change_rate / max(active_bytes_count, 1), 10.0) * 0.1)  # Consistency factor
        )
        
        return {
            'aggregate_change_rate': aggregate_change_rate,
            'max_byte_change_rate': max_byte_change_rate,
            'active_bytes_count': active_bytes_count,
            'volatility_score': volatility_score
        }
    
    def _get_sorted_frame_ids(self) -> list:
        """
        Get Frame IDs sorted by volatility (always).
        Uses caching for performance optimization.
        """
        current_time = time.perf_counter()
        cache = self.analysis_state['sort_cache']
        
        # Check if cache is valid (1 second TTL)
        cache_valid = (
            current_time - cache['last_sort_time'] < 1.0 and
            len(cache['sorted_frame_ids']) == len(self.frame_id_data)
        )
        
        if cache_valid:
            return cache['sorted_frame_ids']
        
        # Cache is invalid, recalculate
        frame_ids = list(self.frame_id_data.keys())
        
        # Always sort by volatility score (high to low)
        frame_ids.sort(key=lambda fid: self.frame_id_data[fid].get('volatility_score', 0.0), reverse=True)
        
        # Update cache
        cache['last_sort_time'] = current_time
        cache['sorted_frame_ids'] = frame_ids
        
        return frame_ids
    
    def _track_byte_changes(self, frame_id: str, byte_values: list, current_time: float):
        """
        Track byte value changes over time for dynamic blue shading.
        Maintains change history for each byte position in each Frame ID.
        """
        # Initialize change history for this Frame ID if needed
        if frame_id not in self.frame_id_change_history:
            self.frame_id_change_history[frame_id] = {}
        
        frame_history = self.frame_id_change_history[frame_id]
        
        # Track changes for each byte position
        for byte_pos, byte_value in enumerate(byte_values):
            if byte_pos not in frame_history:
                frame_history[byte_pos] = {
                    'last_value': byte_value,
                    'change_times': deque(maxlen=100),  # Keep last 100 changes
                    'change_rate': 0
                }
            
            byte_history = frame_history[byte_pos]
            
            # Check if byte value changed
            if byte_history['last_value'] != byte_value:
                byte_history['change_times'].append(current_time)
                byte_history['last_value'] = byte_value
            
            # Clean old change times outside the window
            while (byte_history['change_times'] and
                   current_time - byte_history['change_times'][0] > self._change_window_seconds):
                byte_history['change_times'].popleft()
            
            # Calculate change rate (changes per second)
            if len(byte_history['change_times']) > 1:
                time_span = current_time - byte_history['change_times'][0]
                if time_span > 0:
                    byte_history['change_rate'] = len(byte_history['change_times']) / time_span
                else:
                    byte_history['change_rate'] = 0
            else:
                byte_history['change_rate'] = 0
    
    def _update_message_display(self):
        """
        Atualizar ambos os displays: normal flow (esquerda) e análise (centro).
        Suporta exibição simultânea de fluxo contínuo e análise por Frame ID.
        """
        # Update normal flow display (LEFT PANE - message_display)
        if self._pending_messages:
            messages_to_add = list(self._pending_messages)
            self._pending_messages.clear()

            # Otimização: se o painel estiver muito cheio, recarregue do buffer.
            doc = self.message_display.document()
            if doc.blockCount() > 5500:
                self.message_display.setHtml('<br>'.join(self.message_buffer))
            else:
                # Adicionar o bloco de novas mensagens de uma vez
                self.message_display.append('<br>'.join(messages_to_add))

            # Auto-scroll para o final
            scrollbar = self.message_display.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
        
        # Update analysis display (CENTER PANE - analysis_display)
        # Always update Frame ID grouping display since analysis is always enabled
        self._update_frameid_grouped_display()
    
    def _update_frameid_grouped_display(self):
        """
        Update display for Frame ID grouping mode in the ANALYSIS PANE (center).
        Shows unique Frame IDs sorted by volatility with their latest data.
        Optimized for performance with minimal DOM operations.
        Preserves user scroll position to allow viewing Frame IDs at bottom.
        """
        if not self.frame_id_data:
            self._gui_update_pending = False
            return
        
        # Save current scroll position to preserve user's view (analysis pane)
        scrollbar = self.analysis_display.verticalScrollBar()
        current_scroll_pos = scrollbar.value()
        scroll_at_top = (current_scroll_pos == 0)
        
        # Get sorted Frame IDs - always volatility sorting now
        sorted_frame_ids = self._get_sorted_frame_ids()
        
        # Apply frame filtering if search filter is active
        if self.analysis_state['search_filter']:
            search_filter = self.analysis_state['search_filter']
            filtered_frame_ids = [fid for fid in sorted_frame_ids
                                 if search_filter in fid.upper()]
        else:
            filtered_frame_ids = sorted_frame_ids
        
        # Build display content efficiently using list comprehension with sequential numbering
        display_lines = [self._format_frameid_line(idx + 1, frame_id, self.frame_id_data[frame_id])
                        for idx, frame_id in enumerate(filtered_frame_ids)]
        
        # Update ANALYSIS display with grouped content in one operation
        if display_lines:
            html_content = '<br>'.join(display_lines)
            self.analysis_display.setHtml(html_content)
            
            # Restore scroll position to preserve user's view
            # Only auto-scroll to top if user was already at top (first load or intentional)
            if scroll_at_top:
                scrollbar.setValue(0)
            else:
                # Restore previous scroll position to allow user to view bottom Frame IDs
                scrollbar.setValue(current_scroll_pos)
        else:
            self.analysis_display.clear()
        
        # Update graphics button state based on currently displayed frames
        self._update_graphics_button_state_from_display(filtered_frame_ids)
        
        # Reset update pending flag
        self._gui_update_pending = False
    
    def _format_frameid_line(self, seq_num: int, frame_id: str, frame_data: dict) -> str:
        """
        Format a single Frame ID line for display with sequential numbering and dynamic blue shading.
        Separated for better performance and code reuse.
        """
        prefix = frame_data['prefix']
        byte_values = frame_data.get('byte_values', frame_data['data'].split())
        
        # Create formatted line with color coding based on prefix
        if prefix == 'RX':
            color = '#00FF80'
        elif prefix == 'TX':
            color = '#FFD700'
        else:  # MON
            color = '#87CEEB'
        
        # Format bytes with dynamic blue shading based on change rate
        formatted_bytes = self._format_bytes_with_shading(frame_id, byte_values)
        
        # Create line with sequential numbering (3-digit format for alignment)
        return (f"<span style='color: {color};'>{seq_num:03d}. {prefix}:</span> "
                f"<span style='color: #ffffff;'>{frame_id} | {formatted_bytes}</span>")
    
    def _format_bytes_with_shading(self, frame_id: str, byte_values: list) -> str:
        """
        Format byte values with dynamic color backgrounds based on change rate.
        Fire/Ember style progression: White → Pastel → Yellow → Orange → Red → Purple.
        """
        if frame_id not in self.frame_id_change_history:
            # No change history yet, display normally
            return ' '.join(byte_values)
        
        frame_history = self.frame_id_change_history[frame_id]
        formatted_bytes = []
        
        for byte_pos, byte_value in enumerate(byte_values):
            if byte_pos in frame_history:
                change_rate = frame_history[byte_pos]['change_rate']
                shade_index = self._get_shade_index(change_rate)
                
                if shade_index > 0:  # Apply background color
                    bg_color = self.change_colors[shade_index]
                    # Use white font for red and purple backgrounds, black for others
                    font_color = '#FFFFFF' if shade_index >= 5 else '#000000'
                    formatted_bytes.append(f'<span style="background-color: {bg_color}; color: {font_color}; padding: 1px 2px;">{byte_value}</span>')
                else:
                    formatted_bytes.append(byte_value)
            else:
                formatted_bytes.append(byte_value)
        
        return ' '.join(formatted_bytes)
    
    def _get_shade_index(self, change_rate: float) -> int:
        """
        Map change rate to color index (0-6) using Fire/Ember style progression.
        Returns appropriate pure color based on change frequency.
        """
        if change_rate == 0:
            return 0  # No changes - no background
        elif change_rate < 0.5:  # Less than 0.5 changes per second
            return 1  # White - minimal changes
        elif change_rate < 1.0:  # Less than 1 change per second
            return 2  # Beige - low changes
        elif change_rate < 3.0:  # Less than 3 changes per second
            return 3  # Yellow - moderate changes
        elif change_rate < 6.0:  # Less than 6 changes per second
            return 4  # Orange - frequent changes
        elif change_rate < 10.0:  # Less than 10 changes per second
            return 5  # Red - very frequent changes
        else:  # 10+ changes per second
            return 6  # Purple - ultra-fast changes
        
    def on_recording_stopped(self):
        """Lidar com conclusão da gravação."""
        self.is_recording = False
        self.btn_toggle_record.setText("🔴 REC")
        self.btn_toggle_playback.setEnabled(True)
        self.btn_toggle_monitor.setEnabled(True)
        self.checkbox_continuous.setEnabled(True)  # Reabilitar checkbox
        self.baudrate_combo.setEnabled(True)  # Reabilitar dropdown
        self.operation_timer.stop()
        self._gui_update_timer.stop()
        # Drenar quaisquer mensagens restantes na fila
        self._update_message_display()
        
        self.log_status("Gravação concluída com sucesso.")
        
    def on_playback_stopped(self):
        """Lidar com conclusão da reprodução."""
        self.is_playing = False
        self.btn_toggle_playback.setText("▶️ PLAY")
        self.btn_toggle_record.setEnabled(True)
        self.btn_toggle_monitor.setEnabled(True)
        self.checkbox_continuous.setEnabled(True)  # Reabilitar checkbox
        self.checkbox_teste.setEnabled(True)  # Reabilitar checkbox TESTE
        self.baudrate_combo.setEnabled(True)  # Reabilitar dropdown
        self.progress_bar.setVisible(False)
        self.operation_timer.stop()
        self._gui_update_timer.stop()
        # Drenar quaisquer mensagens restantes na fila
        self._update_message_display()
        
        # ✅ Disable simulation button and close simulation window when playback stops
        self.btn_simulation.setEnabled(False)
        if self.simulation_window is not None and self.simulation_window.isVisible():
            try:
                self.simulation_window.close()
                self.simulation_window = None
            except:
                pass
        
        self.log_status("Reprodução concluída.")
        
    def on_monitoring_stopped(self):
        """Lidar com conclusão do monitoramento."""
        self.is_monitoring = False
        self.btn_toggle_monitor.setText("👁️ Monitor")
        self.btn_toggle_record.setEnabled(True)
        self.btn_toggle_playback.setEnabled(True)
        self.checkbox_continuous.setEnabled(True)  # Reabilitar checkbox
        self.baudrate_combo.setEnabled(True)  # Reabilitar dropdown
        self.operation_timer.stop()
        self._gui_update_timer.stop()
        # Drenar quaisquer mensagens restantes na fila
        self._update_message_display()
        
        self.log_status("Monitoramento concluído.")
        
    def on_error(self, error_message: str):
        """Lidar com mensagens de erro dos workers."""
        error_formatted = f"<span style='color: #FF6B6B; font-weight: bold;'>ERRO:</span> <span style='color: #ffffff;'>{error_message}</span>"
        self.status_display.append(error_formatted)
        
        # ENHANCED: Não mostrar diálogo crítico para timeouts USB (são esperados)
        if 'timeout' not in error_message.lower() and 'usb' not in error_message.lower():
            QMessageBox.critical(self, "Erro", error_message)
        else:
            # Apenas log para timeouts USB
            self.log_status(f"Aviso USB: {error_message}")
        
        # Resetar estado da UI em caso de erro
        self.is_recording = False
        self.is_playing = False
        self.is_monitoring = False
        
        self.btn_toggle_record.setText("🔴 REC")
        self.btn_toggle_playback.setText("▶️ PLAY")
        self.btn_toggle_monitor.setText("👁️ Monitor")
        
        self.btn_toggle_record.setEnabled(True)
        self.btn_toggle_playback.setEnabled(True)
        self.btn_toggle_monitor.setEnabled(True)
        self.checkbox_continuous.setEnabled(True)  # Reabilitar checkbox
        self.checkbox_teste.setEnabled(True)  # Reabilitar checkbox TESTE
        self.baudrate_combo.setEnabled(True)  # Reabilitar dropdown
        
        # ✅ Disable simulation button and close simulation window on error
        self.btn_simulation.setEnabled(False)
        if self.simulation_window is not None and self.simulation_window.isVisible():
            try:
                self.simulation_window.close()
                self.simulation_window = None
            except:
                pass
        
        self.progress_bar.setVisible(False)
        self.operation_timer.stop()
        
    def closeEvent(self, event):
        """Lidar com fechamento da aplicação - limpar workers."""
        # ✅ Fechar janela de simulação se estiver aberta
        if self.simulation_window is not None:
            try:
                self.simulation_window.close()
                self.simulation_window = None
            except:
                pass
        
        # Fechar todas as janelas de gráfico abertas
        for frame_id, janela in list(self.janelas_graficos.items()):
            try:
                janela.close()
            except:
                pass
        self.janelas_graficos.clear()
        
        # Parar timers da GUI
        if hasattr(self, '_gui_update_timer') and self._gui_update_timer.isActive():
            self._gui_update_timer.stop()
        if hasattr(self, 'real_fps_timer') and self.real_fps_timer.isActive():
            self.real_fps_timer.stop()
        # if hasattr(self, 'fps_update_timer') and self.fps_update_timer.isActive():
        #     self.fps_update_timer.stop()
        
        # Parar qualquer operação em execução com timeout mais curto
        if self.recording_worker is not None and self.recording_worker.isRunning():
            self.recording_worker.stop_recording()
            if not self.recording_worker.wait(2000):  # 2 segundos
                self.recording_worker.terminate()
                self.recording_worker.wait(1000)
            
        if self.playback_worker is not None and self.playback_worker.isRunning():
            self.playback_worker.stop_playback()
            if not self.playback_worker.wait(2000):  # 2 segundos
                self.playback_worker.terminate()
                self.playback_worker.wait(1000)
            
        if self.monitor_worker is not None and self.monitor_worker.isRunning():
            self.monitor_worker.stop_monitoring()
            if not self.monitor_worker.wait(2000):  # 2 segundos
                self.monitor_worker.terminate()
                self.monitor_worker.wait(1000)
            
        event.accept()


def main():
    """Ponto de entrada principal da aplicação."""
    # Criar QApplication
    app = QApplication(sys.argv)
    app.setApplicationName("SETERA - Simulador CANBUS")
    app.setApplicationVersion("1.0")
    app.setOrganizationName("Pedro Silva")
    
    # Definir fonte para toda a aplicação
    font = QFont("Segoe UI", 10)
    app.setFont(font)
    
    try:
        # Criar e mostrar janela principal
        window = CANBusMainWindow()
        window.showMaximized()
        
        # Iniciar loop de eventos
        sys.exit(app.exec())
        
    except Exception as e:
        print(f"Erro crítico: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()