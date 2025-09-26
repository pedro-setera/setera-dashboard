#!/usr/bin/env python3
"""
Módulo de Gráficos em Tempo Real para Análise CAN Bus
Permite visualização gráfica de bytes específicos de Frame IDs para descoberta de dados.

Autor: Pedro Silva
Data: 08 de Dezembro de 2025
"""

import sys
import time
from collections import deque
from typing import Optional, List, Dict, Any
import struct

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, QPushButton,
    QButtonGroup, QRadioButton, QGroupBox, QScrollArea, QWidget,
    QSizePolicy, QMessageBox, QLineEdit
)
from PyQt6.QtCore import QTimer, pyqtSignal, Qt
from PyQt6.QtGui import QFont

try:
    import pyqtgraph as pg
    PYQTGRAPH_AVAILABLE = True
except ImportError:
    PYQTGRAPH_AVAILABLE = False
    try:
        import matplotlib.pyplot as plt
        from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
        from matplotlib.figure import Figure
        import matplotlib.animation as animation
        MATPLOTLIB_AVAILABLE = True
    except ImportError:
        MATPLOTLIB_AVAILABLE = False


class GraficoCANDialog(QDialog):
    """
    Janela de diálogo para exibição de gráficos em tempo real de dados CAN.
    Permite seleção de bytes específicos e conversão big/little endian.
    """
    
    # Sinal emitido quando a janela é fechada
    janela_fechada = pyqtSignal()
    
    def __init__(self, frame_id: str, parent=None):
        super().__init__(parent)
        self.frame_id = frame_id
        self.parent_window = parent
        
        # Dados e configuração
        self.bytes_selecionados = []  # Lista de índices de bytes selecionados
        self.big_endian = True  # Modo de endianness
        self.dados_historicos = deque(maxlen=4500)  # Buffer para 30 segundos a 150 FPS
        self.timestamps = deque(maxlen=4500)
        self.dados_atuais = []  # Últimos dados do frame
        
        # Controle de escala Y (nunca reduz)
        self.y_min_absoluto = float('inf')  # Menor valor já visto
        self.y_max_absoluto = float('-inf')  # Maior valor já visto
        
        # Operação matemática
        self.operacao_matematica = ""  # String da operação (ex: "/8", "*0.5", "+100")
        
        # Tracking de valores min/max
        self.valor_min_absoluto = float('inf')
        self.valor_max_absoluto = float('-inf')
        
        # Timer para atualização do gráfico
        self.timer_atualizacao = QTimer()
        self.timer_atualizacao.timeout.connect(self.atualizar_grafico)
        self.timer_atualizacao.setInterval(50)  # 20 FPS de atualização do gráfico
        
        # Configurar UI
        self.setup_ui()
        self.setup_grafico()
        
        # Conectar com a janela principal para receber dados
        if parent and hasattr(parent, 'frame_id_data'):
            self.timer_dados = QTimer()
            self.timer_dados.timeout.connect(self.coletar_dados)
            self.timer_dados.start(10)  # Coletar dados a cada 10ms
        
    def setup_ui(self):
        """Configurar a interface do usuário."""
        self.setWindowTitle(f"SETERA - Gráfico em Tempo Real - Frame ID: {self.frame_id}")
        self.setMinimumSize(800, 700)
        self.resize(800, 700)
        
        # Layout principal
        layout_principal = QVBoxLayout(self)
        layout_principal.setSpacing(10)
        layout_principal.setContentsMargins(15, 15, 15, 15)
        
        # === SEÇÃO DE CONTROLES ===
        grupo_controles = QGroupBox("Configurações de Análise")
        layout_controles = QVBoxLayout(grupo_controles)
        
        # Informações do Frame ID
        info_label = QLabel(f"<b>Frame ID Analisado:</b> {self.frame_id}")
        info_label.setStyleSheet("color: #00D4AA; font-size: 12px; font-weight: bold;")
        layout_controles.addWidget(info_label)
        
        # === SELEÇÃO DE BYTES (COMPACTA) ===
        grupo_bytes = QGroupBox("Seleção de Bytes para Análise")
        layout_bytes_main = QVBoxLayout(grupo_bytes)
        layout_bytes_main.setContentsMargins(10, 15, 10, 10)  # Reduzir margens
        layout_bytes_main.setSpacing(5)  # Reduzir espaçamento
        
        # Layout horizontal direto para checkboxes (sem scroll area)
        self.layout_bytes = QHBoxLayout()
        self.layout_bytes.setSpacing(15)  # Mais espaçamento entre checkboxes
        self.layout_bytes.setContentsMargins(5, 0, 5, 0)
        
        # Criar checkboxes para até 8 bytes (padrão CAN) - estilo compacto
        self.checkboxes_bytes = []
        for i in range(8):
            checkbox = QCheckBox(f"Byte {i}")
            checkbox.setToolTip(f"Incluir byte {i} na análise gráfica")
            checkbox.toggled.connect(self.on_byte_selecionado)
            checkbox.setStyleSheet("""
                QCheckBox {
                    color: #ffffff;
                    font-weight: bold;
                    font-size: 10px;
                    spacing: 3px;
                }
                QCheckBox::indicator {
                    width: 14px;
                    height: 14px;
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
            self.checkboxes_bytes.append(checkbox)
            self.layout_bytes.addWidget(checkbox)
        
        # Adicionar stretch para centralizar os checkboxes
        self.layout_bytes.addStretch()
        
        # Adicionar layout diretamente ao grupo (sem scroll area)
        layout_bytes_main.addLayout(self.layout_bytes)
        
        # Definir altura máxima menor para o grupo
        grupo_bytes.setMaximumHeight(60)
        
        # === CONFIGURAÇÃO DE ENDIANNESS E OPERAÇÕES MATEMÁTICAS ===
        # Container horizontal para dividir o espaço 50/50
        configuracao_container = QWidget()
        configuracao_layout = QHBoxLayout(configuracao_container)
        configuracao_layout.setSpacing(15)
        
        # === SEÇÃO ESQUERDA: ORDEM DOS BYTES ===
        grupo_endian = QGroupBox("Ordem dos Bytes")
        layout_endian = QHBoxLayout(grupo_endian)
        
        self.radio_big_endian = QRadioButton("Big Endian")
        self.radio_little_endian = QRadioButton("Little Endian")
        self.radio_big_endian.setChecked(True)  # Padrão
        
        self.radio_big_endian.toggled.connect(self.on_endianness_changed)
        self.radio_little_endian.toggled.connect(self.on_endianness_changed)
        
        # Estilo para radio buttons
        radio_style = """
            QRadioButton {
                color: #ffffff;
                font-weight: bold;
                font-size: 11px;
                spacing: 8px;
            }
            QRadioButton::indicator {
                width: 16px;
                height: 16px;
                border: 2px solid #606060;
                border-radius: 8px;
                background-color: #404040;
            }
            QRadioButton::indicator:checked {
                background-color: #00D4AA;
                border-color: #00D4AA;
            }
            QRadioButton::indicator:hover {
                border-color: #00D4AA;
            }
        """
        self.radio_big_endian.setStyleSheet(radio_style)
        self.radio_little_endian.setStyleSheet(radio_style)
        
        layout_endian.addWidget(self.radio_big_endian)
        layout_endian.addSpacing(20)  # Mais espaço entre Big e Little Endian
        layout_endian.addWidget(self.radio_little_endian)
        layout_endian.addStretch()
        
        # === SEÇÃO DIREITA: OPERAÇÕES MATEMÁTICAS ===
        grupo_operacoes = QGroupBox("Operações Matemáticas")
        layout_operacoes = QVBoxLayout(grupo_operacoes)
        
        # Input para operação matemática
        self.input_operacao = QLineEdit()
        self.input_operacao.setPlaceholderText("Ex: /8, *0.5, +100, -32")
        self.input_operacao.setToolTip("Digite uma operação matemática: /8 (dividir por 8), *2 (multiplicar por 2), +100 (somar 100), etc.")
        self.input_operacao.textChanged.connect(self.on_operacao_changed)
        self.input_operacao.setStyleSheet("""
            QLineEdit {
                background-color: #404040;
                border: 2px solid #606060;
                border-radius: 4px;
                color: #ffffff;
                padding: 6px;
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
        layout_operacoes.addWidget(self.input_operacao)
        
        # Adicionar ambos os grupos ao container
        configuracao_layout.addWidget(grupo_endian, 1)  # 50% do espaço
        configuracao_layout.addWidget(grupo_operacoes, 1)  # 50% do espaço
        
        # === CONTROLES DE AÇÃO ===
        layout_acoes = QHBoxLayout()
        
        self.btn_iniciar = QPushButton("🚀 Iniciar Análise")
        self.btn_iniciar.setToolTip("Iniciar captura e exibição do gráfico em tempo real")
        self.btn_iniciar.clicked.connect(self.iniciar_analise)
        
        self.btn_parar = QPushButton("⏹️ Parar")
        self.btn_parar.setToolTip("Parar a análise gráfica")
        self.btn_parar.clicked.connect(self.parar_analise)
        self.btn_parar.setEnabled(False)
        
        self.btn_limpar = QPushButton("🗑️ Limpar")
        self.btn_limpar.setToolTip("Limpar dados históricos do gráfico")
        self.btn_limpar.clicked.connect(self.limpar_dados)
        
        # Container para valores (Atual, Min, Max) - layout horizontal
        self.valores_container = QWidget()
        valores_layout = QHBoxLayout(self.valores_container)
        valores_layout.setContentsMargins(0, 0, 0, 0)
        valores_layout.setSpacing(25)  # Mais espaço entre Atual, Min, Max
        
        # Labels para valores atuais, mínimo e máximo
        self.label_atual = QLabel("Atual: --")
        self.label_atual.setStyleSheet("color: #00D4AA; font-weight: bold; font-size: 11px;")
        self.label_atual.setToolTip("Valor atual sendo plotado no gráfico")
        
        self.label_min = QLabel("Min: --")
        self.label_min.setStyleSheet("color: #ffffff; font-weight: bold; font-size: 11px;")
        self.label_min.setToolTip("Menor valor alcançado durante a análise")
        
        self.label_max = QLabel("Max: --")
        self.label_max.setStyleSheet("color: #ffffff; font-weight: bold; font-size: 11px;")
        self.label_max.setToolTip("Maior valor alcançado durante a análise")
        
        valores_layout.addWidget(self.label_atual)
        valores_layout.addWidget(self.label_min)
        valores_layout.addWidget(self.label_max)
        valores_layout.addStretch()  # Empurrar para a esquerda
        
        # Estilo dos botões
        button_style = """
            QPushButton {
                background-color: #404040;
                border: 2px solid #606060;
                border-radius: 6px;
                padding: 8px 12px;
                font-weight: bold;
                font-size: 11px;
                color: #ffffff;
                min-width: 100px;
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
        """
        
        for btn in [self.btn_iniciar, self.btn_parar, self.btn_limpar]:
            btn.setStyleSheet(button_style)
        
        layout_acoes.addWidget(self.btn_iniciar)
        layout_acoes.addSpacing(15)  # Espaço entre Iniciar e Parar
        layout_acoes.addWidget(self.btn_parar)
        layout_acoes.addSpacing(15)  # Espaço entre Parar e Limpar
        layout_acoes.addWidget(self.btn_limpar)
        layout_acoes.addSpacing(25)  # Mais espaço entre Limpar e valores
        layout_acoes.addWidget(self.valores_container)
        layout_acoes.addStretch()
        
        # Status
        self.label_status = QLabel("Status: Aguardando configuração...")
        self.label_status.setStyleSheet("color: #FFD700; font-weight: bold; font-size: 11px;")
        
        # Montar layout de controles
        layout_controles.addWidget(grupo_bytes)
        layout_controles.addWidget(configuracao_container)
        layout_controles.addLayout(layout_acoes)
        layout_controles.addWidget(self.label_status)
        
        layout_principal.addWidget(grupo_controles)
        
        # === ÁREA DO GRÁFICO ===
        self.widget_grafico = QWidget()
        self.widget_grafico.setMinimumHeight(350)
        self.widget_grafico.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout_principal.addWidget(self.widget_grafico)
        
        # Aplicar tema escuro
        self.setStyleSheet("""
            QDialog {
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
            QLabel {
                color: #ffffff;
            }
        """)
    
    def setup_grafico(self):
        """Configurar o widget de gráfico."""
        layout_grafico = QVBoxLayout(self.widget_grafico)
        layout_grafico.setContentsMargins(0, 0, 0, 0)
        
        if PYQTGRAPH_AVAILABLE:
            # Usar PyQtGraph para melhor performance
            pg.setConfigOption('background', '#1e1e1e')
            pg.setConfigOption('foreground', '#ffffff')
            
            self.plot_widget = pg.PlotWidget()
            self.plot_widget.setLabel('left', 'Valor (Decimal)', color='#ffffff', size='12pt')
            self.plot_widget.setLabel('bottom', 'Tempo (s)', color='#ffffff', size='12pt')
            self.plot_widget.setTitle(f'Análise em Tempo Real - {self.frame_id}', color='#00D4AA', size='14pt')
            self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
            self.plot_widget.setYRange(0, 255, padding=0.1)  # Iniciar com range de 1 byte
            
            # Configurar aparência
            self.plot_widget.getAxis('left').setPen(color='#ffffff')
            self.plot_widget.getAxis('bottom').setPen(color='#ffffff')
            self.plot_widget.getAxis('left').setTextPen(color='#ffffff')
            self.plot_widget.getAxis('bottom').setTextPen(color='#ffffff')
            
            # Linha do gráfico
            self.linha_grafico = self.plot_widget.plot(pen=pg.mkPen(color='#00D4AA', width=2))
            
            layout_grafico.addWidget(self.plot_widget)
            
        elif MATPLOTLIB_AVAILABLE:
            # Fallback para matplotlib
            self.figura = Figure(figsize=(10, 6), facecolor='#1e1e1e')
            self.canvas = FigureCanvas(self.figura)
            self.eixo = self.figura.add_subplot(111, facecolor='#2a2a2a')
            
            # Configurar aparência
            self.eixo.set_xlabel('Tempo (s)', color='#ffffff')
            self.eixo.set_ylabel('Valor (Decimal)', color='#ffffff')
            self.eixo.set_title(f'Análise em Tempo Real - {self.frame_id}', color='#00D4AA')
            self.eixo.tick_params(colors='#ffffff')
            self.eixo.grid(True, alpha=0.3)
            
            self.linha_grafico, = self.eixo.plot([], [], color='#00D4AA', linewidth=2)
            
            layout_grafico.addWidget(self.canvas)
        else:
            # Sem bibliotecas de gráfico disponíveis
            error_label = QLabel("❌ Erro: PyQtGraph ou Matplotlib não encontrados!\n\n"
                                "Para usar esta funcionalidade, instale uma das bibliotecas:\n"
                                "pip install pyqtgraph\n"
                                "ou\n"
                                "pip install matplotlib")
            error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            error_label.setStyleSheet("color: #FF6B6B; font-size: 14px; font-weight: bold;")
            layout_grafico.addWidget(error_label)
    
    def on_byte_selecionado(self):
        """Callback quando bytes são selecionados/desmarcados."""
        self.bytes_selecionados = []
        for i, checkbox in enumerate(self.checkboxes_bytes):
            if checkbox.isChecked():
                self.bytes_selecionados.append(i)
        
        # Verificar disponibilidade dos dados atuais para feedback inteligente
        if hasattr(self, 'dados_atuais') and self.dados_atuais:
            frame_length = len(self.dados_atuais)
            valid_bytes = [b for b in self.bytes_selecionados if 0 <= b < frame_length]
            invalid_bytes = [b for b in self.bytes_selecionados if b >= frame_length]
            
            if invalid_bytes:
                # Alertar sobre bytes inválidos
                status = f"⚠️ Frame atual tem {frame_length} bytes (0-{frame_length-1}). "
                if valid_bytes:
                    status += f"Válidos: {valid_bytes}, Inválidos: {invalid_bytes}"
                    self.label_status.setStyleSheet("color: #FFD700; font-weight: bold; font-size: 11px;")
                else:
                    status += f"Todos os bytes selecionados são inválidos: {invalid_bytes}"
                    self.label_status.setStyleSheet("color: #FF6B6B; font-weight: bold; font-size: 11px;")
                self.label_status.setText(f"Status: {status}")
                return
        
        # Status normal
        if self.bytes_selecionados:
            status = f"Bytes selecionados: {', '.join(map(str, self.bytes_selecionados))}"
            if len(self.bytes_selecionados) > 1:
                endian_text = "Big Endian" if self.big_endian else "Little Endian"
                status += f" ({endian_text})"
            if self.operacao_matematica:
                status += f" | Operação: {self.operacao_matematica}"
            self.label_status.setText(f"Status: {status}")
            self.label_status.setStyleSheet("color: #FFD700; font-weight: bold; font-size: 11px;")
        else:
            self.label_status.setText("Status: Nenhum byte selecionado")
            self.label_status.setStyleSheet("color: #FFD700; font-weight: bold; font-size: 11px;")
    
    def on_endianness_changed(self):
        """Callback quando o endianness é alterado."""
        self.big_endian = self.radio_big_endian.isChecked()
        self.on_byte_selecionado()  # Atualizar status
    
    def on_operacao_changed(self, texto: str):
        """Callback quando a operação matemática é alterada."""
        self.operacao_matematica = texto.strip()
        # Validar operação básica
        if self.operacao_matematica and not self._validar_operacao(self.operacao_matematica):
            self.label_status.setText("Status: ⚠️ Operação matemática inválida")
            self.label_status.setStyleSheet("color: #FF6B6B; font-weight: bold; font-size: 11px;")
        else:
            self.on_byte_selecionado()  # Atualizar status
    
    def _validar_operacao(self, operacao: str) -> bool:
        """Validar se a operação matemática é segura."""
        if not operacao:
            return True
        
        # Permitir apenas operações básicas e números
        import re
        # Permite: +, -, *, /, números decimais, parênteses, espaços
        padrao = r'^[\+\-\*/\(\)\d\.\s]+$'
        return bool(re.match(padrao, operacao))
    
    def _aplicar_operacao_matematica(self, valor: float) -> float:
        """Aplicar operação matemática ao valor."""
        if not self.operacao_matematica:
            return valor
        
        try:
            # Construir expressão segura
            if self.operacao_matematica.startswith(('*', '/', '+', '-')):
                # Operação direta: /8, *2, +100, -32
                expressao = f"{valor}{self.operacao_matematica}"
            else:
                # Expressão completa: (valor+100)/8
                expressao = self.operacao_matematica.replace('x', str(valor)).replace('X', str(valor))
                if 'x' not in self.operacao_matematica.lower():
                    # Se não tem 'x', assumir que é uma operação direta
                    expressao = f"{valor}{self.operacao_matematica}"
            
            # Avaliar expressão de forma segura
            resultado = eval(expressao, {"__builtins__": {}}, {})
            return float(resultado)
        except:
            # Em caso de erro, retornar valor original
            return valor
    
    def converter_bytes_para_decimal(self, dados_bytes: List[str]) -> Optional[float]:
        """
        Converter lista de bytes hex para valor decimal com operação matemática.
        
        Args:
            dados_bytes: Lista de strings hex (ex: ['A1', 'B2', 'C3'])
            
        Returns:
            Valor decimal (pode ser float após operação) ou None se erro
        """
        if not self.bytes_selecionados or not dados_bytes:
            if hasattr(self, 'label_valor_atual'):
                self.label_valor_atual.setText("Valor Atual: -- (sem dados)")
            return None
        
        try:
            # DIAGNÓSTICO: Verificar disponibilidade dos bytes
            frame_length = len(dados_bytes)
            valid_indices = []
            invalid_indices = []
            
            # Extrair bytes selecionados - ANÁLISE COMPLETA
            bytes_selecionados_dados = []
            for idx in self.bytes_selecionados:
                if 0 <= idx < frame_length:
                    # Índice válido - tentar extrair byte
                    byte_hex = dados_bytes[idx]
                    if isinstance(byte_hex, str):
                        # CORREÇÃO CRÍTICA: Remover tags HTML antes da validação
                        import re
                        byte_hex_clean = re.sub(r'<[^>]*>', '', byte_hex)  # Remove todas as tags HTML
                        byte_hex_clean = byte_hex_clean.strip().upper()
                        
                        # Verificar se é um valor hex válido após limpeza
                        if len(byte_hex_clean) >= 1 and all(c in '0123456789ABCDEF' for c in byte_hex_clean):
                            # Garantir formato de 2 dígitos
                            if len(byte_hex_clean) == 1:
                                byte_hex_clean = '0' + byte_hex_clean
                            bytes_selecionados_dados.append(byte_hex_clean)
                            valid_indices.append(idx)
                        else:
                            # Mostrar tanto o valor original quanto o limpo para debug
                            invalid_indices.append(f"{idx}(inválido-orig:{byte_hex[:20]}...)")
                    else:
                        invalid_indices.append(f"{idx}(não-string)")
                else:
                    # Índice fora do range do frame atual
                    invalid_indices.append(f"{idx}(fora-range)")
            
            # FEEDBACK PARA O USUÁRIO sobre problemas
            if invalid_indices:
                status_msg = f"Frame tem {frame_length} bytes (0-{frame_length-1}). "
                if not bytes_selecionados_dados:
                    # Nenhum byte válido encontrado
                    status_msg += f"Bytes inválidos: {', '.join(invalid_indices)}"
                    if hasattr(self, 'label_status'):
                        self.label_status.setText(f"Status: ⚠️ {status_msg}")
                        self.label_status.setStyleSheet("color: #FF6B6B; font-weight: bold; font-size: 11px;")
                    if hasattr(self, 'label_valor_atual'):
                        self.label_valor_atual.setText("Valor Atual: -- (bytes inválidos)")
                    return None
                else:
                    # Alguns bytes válidos, alguns inválidos
                    status_msg += f"Usando bytes válidos: {valid_indices}. Ignorando: {', '.join(invalid_indices)}"
                    if hasattr(self, 'label_status'):
                        self.label_status.setText(f"Status: ⚠️ {status_msg}")
                        self.label_status.setStyleSheet("color: #FFD700; font-weight: bold; font-size: 11px;")
            
            if not bytes_selecionados_dados:
                return None
            
            # Converter para valor decimal
            valor_decimal = 0
            
            if len(bytes_selecionados_dados) == 1:
                # Um byte: conversão direta
                valor_decimal = int(bytes_selecionados_dados[0], 16)
            
            elif len(bytes_selecionados_dados) > 1:
                # Múltiplos bytes: aplicar endianness
                bytes_valores = [int(b, 16) for b in bytes_selecionados_dados]
                
                if self.big_endian:
                    # Big endian: primeiro byte é o mais significativo
                    for byte_val in bytes_valores:
                        valor_decimal = (valor_decimal << 8) + byte_val
                else:
                    # Little endian: primeiro byte é o menos significativo
                    for i, byte_val in enumerate(bytes_valores):
                        valor_decimal += byte_val << (8 * i)
            
            # Aplicar operação matemática se configurada
            valor_final = self._aplicar_operacao_matematica(float(valor_decimal))
            
            return valor_final
            
        except (ValueError, IndexError, TypeError) as e:
            # Debug: print para identificar problemas
            # print(f"Erro na conversão: {e}, dados: {dados_bytes}, selecionados: {self.bytes_selecionados}")
            return None
        
        return None
    
    def coletar_dados(self):
        """Coletar dados do frame ID da janela principal."""
        if not self.parent_window or not hasattr(self.parent_window, 'frame_id_data'):
            return
        
        # Obter dados atuais do frame
        frame_data = self.parent_window.frame_id_data.get(self.frame_id)
        if not frame_data:
            return
        
        # Extrair bytes
        byte_values = frame_data.get('byte_values', [])
        if not byte_values:
            return
        
        # LIMPEZA CRÍTICA: Garantir que os bytes estão limpos de HTML
        import re
        byte_values_clean = []
        for byte_val in byte_values:
            if isinstance(byte_val, str):
                # Remover qualquer HTML que possa ter vazado
                clean_byte = re.sub(r'<[^>]*>', '', byte_val).strip().upper()
                if clean_byte:  # Só adicionar se não ficou vazio
                    byte_values_clean.append(clean_byte)
            else:
                byte_values_clean.append(str(byte_val))
        
        self.dados_atuais = byte_values_clean
        byte_values = byte_values_clean  # Usar dados limpos daqui em diante
        
        # Se análise está ativa, processar dados
        if self.timer_atualizacao.isActive() and self.bytes_selecionados:
            valor_decimal = self.converter_bytes_para_decimal(byte_values)
            if valor_decimal is not None:
                timestamp_atual = time.time()
                
                # Adicionar aos buffers
                self.dados_historicos.append(valor_decimal)
                self.timestamps.append(timestamp_atual)
                
                # Atualizar tracking de min/max
                if valor_decimal < self.valor_min_absoluto:
                    self.valor_min_absoluto = valor_decimal
                if valor_decimal > self.valor_max_absoluto:
                    self.valor_max_absoluto = valor_decimal
                
                # Atualizar labels de valores
                if hasattr(self, 'label_atual'):
                    # Atual
                    if self.operacao_matematica:
                        self.label_atual.setText(f"Atual: {valor_decimal:.2f}")
                    else:
                        self.label_atual.setText(f"Atual: {int(valor_decimal) if valor_decimal == int(valor_decimal) else valor_decimal:.2f}")
                    
                    # Min
                    if self.valor_min_absoluto != float('inf'):
                        if self.operacao_matematica:
                            self.label_min.setText(f"Min: {self.valor_min_absoluto:.2f}")
                        else:
                            min_val = self.valor_min_absoluto
                            self.label_min.setText(f"Min: {int(min_val) if min_val == int(min_val) else min_val:.2f}")
                    
                    # Max
                    if self.valor_max_absoluto != float('-inf'):
                        if self.operacao_matematica:
                            self.label_max.setText(f"Max: {self.valor_max_absoluto:.2f}")
                        else:
                            max_val = self.valor_max_absoluto
                            self.label_max.setText(f"Max: {int(max_val) if max_val == int(max_val) else max_val:.2f}")
                
                # Manter apenas últimos 20 segundos
                while (self.timestamps and
                       timestamp_atual - self.timestamps[0] > 30.0):
                    self.dados_historicos.popleft()
                    self.timestamps.popleft()
    
    def atualizar_grafico(self):
        """Atualizar o gráfico com novos dados."""
        if not self.timestamps or not self.dados_historicos:
            return
        
        # Converter timestamps para tempo relativo (últimos 10 segundos)
        timestamp_atual = time.time()
        tempos_relativos = [t - timestamp_atual for t in self.timestamps]
        
        # Atualizar valores mínimo e máximo absolutos (nunca reduz)
        if self.dados_historicos:
            min_atual = min(self.dados_historicos)
            max_atual = max(self.dados_historicos)
            
            # Atualizar apenas se encontrarmos novos extremos
            if min_atual < self.y_min_absoluto:
                self.y_min_absoluto = min_atual
            if max_atual > self.y_max_absoluto:
                self.y_max_absoluto = max_atual
            
            # Se ainda não temos histórico, inicializar
            if self.y_min_absoluto == float('inf'):
                self.y_min_absoluto = min_atual
            if self.y_max_absoluto == float('-inf'):
                self.y_max_absoluto = max_atual
        
        if PYQTGRAPH_AVAILABLE and hasattr(self, 'linha_grafico'):
            # Atualizar PyQtGraph
            self.linha_grafico.setData(tempos_relativos, list(self.dados_historicos))
            
            # Ajustar ranges - usar valores absolutos (nunca reduz)
            if len(self.dados_historicos) > 0:
                # Calcular padding baseado na diferença total
                range_total = self.y_max_absoluto - self.y_min_absoluto
                padding = max(range_total * 0.1, 10)  # Mínimo de 10 unidades de padding
                
                y_min_display = self.y_min_absoluto - padding
                y_max_display = self.y_max_absoluto + padding
                
                self.plot_widget.setYRange(y_min_display, y_max_display, padding=0)
            
            self.plot_widget.setXRange(-30, 0, padding=0)
            
        elif MATPLOTLIB_AVAILABLE and hasattr(self, 'linha_grafico'):
            # Atualizar Matplotlib
            self.linha_grafico.set_data(tempos_relativos, list(self.dados_historicos))
            
            # Ajustar ranges - usar valores absolutos (nunca reduz)
            if len(self.dados_historicos) > 0:
                # Calcular padding baseado na diferença total
                range_total = self.y_max_absoluto - self.y_min_absoluto
                padding = max(range_total * 0.1, 10)  # Mínimo de 10 unidades de padding
                
                y_min_display = self.y_min_absoluto - padding
                y_max_display = self.y_max_absoluto + padding
                
                self.eixo.set_ylim(y_min_display, y_max_display)
            
            self.eixo.set_xlim(-30, 0)
            self.canvas.draw()
    
    def iniciar_analise(self):
        """Iniciar a análise gráfica."""
        if not self.bytes_selecionados:
            QMessageBox.warning(self, "Aviso", "Por favor, selecione pelo menos um byte para análise.")
            return
        
        if not (PYQTGRAPH_AVAILABLE or MATPLOTLIB_AVAILABLE):
            QMessageBox.critical(self, "Erro", "Bibliotecas de gráfico não encontradas!\n\n"
                               "Instale PyQtGraph ou Matplotlib:\n"
                               "pip install pyqtgraph")
            return
        
        # Limpar dados anteriores
        self.limpar_dados()
        
        # Iniciar timers
        self.timer_atualizacao.start()
        
        # Atualizar UI
        self.btn_iniciar.setEnabled(False)
        self.btn_parar.setEnabled(True)
        
        # Desabilitar controles durante análise
        for checkbox in self.checkboxes_bytes:
            checkbox.setEnabled(False)
        self.radio_big_endian.setEnabled(False)
        self.radio_little_endian.setEnabled(False)
        self.input_operacao.setEnabled(False)
        
        self.label_status.setText("Status: 🔴 Análise ativa - Coletando dados...")
        self.label_status.setStyleSheet("color: #00FF80; font-weight: bold; font-size: 11px;")
    
    def parar_analise(self):
        """Parar a análise gráfica."""
        self.timer_atualizacao.stop()
        
        # Atualizar UI
        self.btn_iniciar.setEnabled(True)
        self.btn_parar.setEnabled(False)
        
        # Reabilitar controles
        for checkbox in self.checkboxes_bytes:
            checkbox.setEnabled(True)
        self.radio_big_endian.setEnabled(True)
        self.radio_little_endian.setEnabled(True)
        self.input_operacao.setEnabled(True)
        
        self.label_status.setText("Status: ⏹️ Análise parada")
        self.label_status.setStyleSheet("color: #FFD700; font-weight: bold; font-size: 11px;")
    
    def limpar_dados(self):
        """Limpar dados históricos do gráfico."""
        self.dados_historicos.clear()
        self.timestamps.clear()
        
        # Reset dos valores absolutos de escala Y
        self.y_min_absoluto = float('inf')
        self.y_max_absoluto = float('-inf')
        
        # Limpar gráfico
        if PYQTGRAPH_AVAILABLE and hasattr(self, 'linha_grafico'):
            self.linha_grafico.setData([], [])
        elif MATPLOTLIB_AVAILABLE and hasattr(self, 'linha_grafico'):
            self.linha_grafico.set_data([], [])
            self.canvas.draw()
        
        self.label_status.setText("Status: 🗑️ Dados limpos")
        
        # Reset dos valores min/max
        self.valor_min_absoluto = float('inf')
        self.valor_max_absoluto = float('-inf')
        
        # Limpar labels de valores
        if hasattr(self, 'label_atual'):
            self.label_atual.setText("Atual: --")
            self.label_min.setText("Min: --")
            self.label_max.setText("Max: --")
    
    def _atualizar_tooltips_bytes(self, byte_values: List[str]):
        """Atualizar tooltips dos checkboxes de bytes baseado no frame atual."""
        if not byte_values:
            return
            
        frame_length = len(byte_values)
        
        for i, checkbox in enumerate(self.checkboxes_bytes):
            if i < frame_length:
                # Byte disponível - mostrar valor atual (limpar HTML primeiro)
                byte_value = byte_values[i] if i < len(byte_values) else "??"
                # Limpar qualquer HTML que possa estar presente
                import re
                byte_value_clean = re.sub(r'<[^>]*>', '', str(byte_value)).strip().upper()
                checkbox.setToolTip(f"Byte {i}: {byte_value_clean} (disponível)")
                checkbox.setEnabled(True)
                # Resetar estilo para disponível
                checkbox.setStyleSheet("""
                    QCheckBox {
                        color: #ffffff;
                        font-weight: bold;
                        font-size: 11px;
                        spacing: 5px;
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
            else:
                # Byte não disponível no frame atual
                checkbox.setToolTip(f"Byte {i}: Não disponível no frame atual (frame tem apenas {frame_length} bytes: 0-{frame_length-1})")
                # Manter habilitado mas com visual diferente
                checkbox.setStyleSheet("""
                    QCheckBox {
                        color: #808080;
                        font-weight: bold;
                        font-size: 11px;
                        spacing: 5px;
                    }
                    QCheckBox::indicator {
                        width: 16px;
                        height: 16px;
                        border: 2px solid #404040;
                        border-radius: 3px;
                        background-color: #2a2a2a;
                    }
                    QCheckBox::indicator:checked {
                        background-color: #FF6B6B;
                        border-color: #FF6B6B;
                    }
                    QCheckBox::indicator:hover {
                        border-color: #FF6B6B;
                    }
                """)

    def closeEvent(self, event):
        """Cleanup quando a janela é fechada."""
        # Parar timers
        if hasattr(self, 'timer_atualizacao'):
            self.timer_atualizacao.stop()
        if hasattr(self, 'timer_dados'):
            self.timer_dados.stop()
        
        # Emitir sinal de fechamento
        self.janela_fechada.emit()
        
        event.accept()


def verificar_dependencias():
    """Verificar se as dependências para gráficos estão disponíveis."""
    return PYQTGRAPH_AVAILABLE or MATPLOTLIB_AVAILABLE


if __name__ == "__main__":
    # Teste básico do módulo
    from PyQt6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    # Verificar dependências
    if not verificar_dependencias():
        print("❌ Erro: PyQtGraph ou Matplotlib não encontrados!")
        print("Instale uma das bibliotecas:")
        print("pip install pyqtgraph")
        print("ou")
        print("pip install matplotlib")
        sys.exit(1)
    
    # Criar janela de teste
    janela = GraficoCANDialog("7E0")
    janela.show()
    
    sys.exit(app.exec())