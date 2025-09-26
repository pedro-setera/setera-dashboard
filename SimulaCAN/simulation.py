#!/usr/bin/env python3
"""
J1939 Real-Time Simulation Window
Modern simulation control interface for real-time parameter modification.

Author: Pedro Silva  
Date: June 2025
"""

import sys
from typing import Dict, Optional
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider, 
    QCheckBox, QGroupBox, QPushButton, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QIcon

from simulation_params import SimulationParameters, ParameterConversions, get_simulation_params


class ParameterControl(QWidget):
    """Individual parameter control widget with slider and value display."""
    
    value_changed = pyqtSignal(str, float, bool)  # param_name, value, enabled
    
    def __init__(self, param_name: str, parent=None):
        super().__init__(parent)
        self.param_name = param_name
        self.conversion = ParameterConversions.get_conversion(param_name)
        
        # Internal state
        self._updating = False
        
        self.setup_ui()
        self.setup_connections()
        
    def setup_ui(self):
        """Setup the parameter control UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)  # Increased spacing for better layout
        layout.setContentsMargins(8, 8, 8, 8)
        
        # Get parameter info
        label_text = self.conversion.get('label', self.param_name)
        param_range = self.conversion.get('range', (0, 100))
        unit = self.conversion.get('unit', '')
        
        # Title label
        self.title_label = QLabel(label_text)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        self.title_label.setStyleSheet("color: #666666; font-weight: bold;")  # Start grey (disabled)
        layout.addWidget(self.title_label)
        
        # Max value label (top of slider)
        self.max_label = QLabel(f"{param_range[1]:.0f}")
        self.max_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.max_label.setFont(QFont("Arial", 9))
        self.max_label.setStyleSheet("color: #ffffff; font-size: 9px;")
        layout.addWidget(self.max_label)
        
        # Enable checkbox
        self.enable_checkbox = QCheckBox()
        self.enable_checkbox.setChecked(False)
        self.enable_checkbox.setStyleSheet("""
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
        layout.addWidget(self.enable_checkbox, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Vertical slider
        self.slider = QSlider(Qt.Orientation.Vertical)
        self.slider.setMinimum(int(param_range[0] * 10))  # x10 for better precision
        self.slider.setMaximum(int(param_range[1] * 10))  # x10 for better precision
        self.slider.setValue(int(param_range[0] * 10))  # Start at minimum
        self.slider.setEnabled(False)  # Disabled until checkbox is checked
        self.slider.setMinimumHeight(300)  # Increased height to fix layout
        self.slider.setStyleSheet("""
            QSlider::groove:vertical {
                background: #404040;
                width: 8px;
                border-radius: 4px;
            }
            QSlider::handle:vertical {
                background: #00D4AA;
                border: 2px solid #00D4AA;
                height: 20px;
                border-radius: 10px;
                margin: 0 -6px;
            }
            QSlider::handle:vertical:hover {
                background: #00E4BA;
            }
            QSlider::handle:vertical:disabled {
                background: #606060;
                border-color: #606060;
            }
        """)
        layout.addWidget(self.slider, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Min value label (bottom of slider)
        self.min_label = QLabel(f"{param_range[0]:.0f}")
        self.min_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.min_label.setFont(QFont("Arial", 9))
        self.min_label.setStyleSheet("color: #ffffff; font-size: 9px;")
        layout.addWidget(self.min_label)
        
        # Current value label
        initial_value = param_range[0]
        self.value_label = QLabel(f"{initial_value:.1f}")
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.value_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        self.value_label.setStyleSheet("color: #666666; font-weight: bold; font-size: 12px;")  # Start grey (disabled)
        layout.addWidget(self.value_label)
        
        # Unit label
        self.unit_label = QLabel(unit)
        self.unit_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.unit_label.setFont(QFont("Arial", 9))
        self.unit_label.setStyleSheet("color: #ffffff; font-size: 9px;")
        layout.addWidget(self.unit_label)
        
        # Set fixed width for consistent layout
        self.setFixedWidth(100)
        
    def setup_connections(self):
        """Setup signal connections."""
        self.enable_checkbox.toggled.connect(self.on_enable_changed)
        self.slider.valueChanged.connect(self.on_slider_changed)
        
    def on_enable_changed(self, enabled: bool):
        """Handle enable checkbox state change."""
        self.slider.setEnabled(enabled)
        
        if enabled:
            # Enable slider and emit current value
            current_value = self.get_current_value()
            self.value_changed.emit(self.param_name, current_value, True)
        else:
            # Disable simulation for this parameter
            self.value_changed.emit(self.param_name, 0.0, False)
            
        # Update styling based on state
        if enabled:
            self.title_label.setStyleSheet("color: #00D4AA; font-weight: bold;")
            self.value_label.setStyleSheet("color: #00D4AA; font-weight: bold; font-size: 12px;")
        else:
            self.title_label.setStyleSheet("color: #666666; font-weight: bold;")
            self.value_label.setStyleSheet("color: #666666; font-weight: bold; font-size: 12px;")
    
    def on_slider_changed(self, slider_value: int):
        """Handle slider value change."""
        if self._updating:
            return
            
        # Convert slider value (x10 precision) to actual value
        actual_value = slider_value / 10.0
        
        # Update value display
        if self.param_name == 'fuel_economy':
            self.value_label.setText(f"{actual_value:.2f}")
        elif self.param_name in ['total_mileage', 'engine_rpm']:
            self.value_label.setText(f"{actual_value:.0f}")
        else:
            self.value_label.setText(f"{actual_value:.1f}")
        
        # Emit signal if enabled
        if self.enable_checkbox.isChecked():
            self.value_changed.emit(self.param_name, actual_value, True)
    
    def get_current_value(self) -> float:
        """Get current slider value as float."""
        return self.slider.value() / 10.0
    
    def set_value(self, value: float):
        """Set slider value programmatically."""
        self._updating = True
        slider_value = int(value * 10)
        self.slider.setValue(slider_value)
        
        # Update display
        if self.param_name == 'fuel_economy':
            self.value_label.setText(f"{value:.2f}")
        elif self.param_name in ['total_mileage', 'engine_rpm']:
            self.value_label.setText(f"{value:.0f}")
        else:
            self.value_label.setText(f"{value:.1f}")
            
        self._updating = False
    
    def set_enabled(self, enabled: bool):
        """Set parameter enabled state programmatically."""
        self.enable_checkbox.setChecked(enabled)


class SimulationWindow(QMainWindow):
    """J1939 Real-Time Simulation Control Window."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.simulation_params = get_simulation_params()
        
        # Parameter controls storage
        self.parameter_controls: Dict[str, ParameterControl] = {}
        
        # Update timer for real-time feedback
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_status)
        self.update_timer.start(100)  # Update every 100ms
        
        self.setup_ui()
        self.setup_connections()
        
    def setup_ui(self):
        """Setup the simulation window UI."""
        self.setWindowTitle("SETERA - Simulação CANBUS")
        self.setFixedSize(650, 650)  # Increased height by 50%
        
        # Set window icon (same as main window)
        try:
            icon_path = "favicon.ico"
            self.setWindowIcon(QIcon(icon_path))
        except:
            pass
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(15, 15, 15, 15)
        
        # Title
        title_label = QLabel("Simulação de Parâmetros CANBUS em Tempo Real")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #00D4AA; font-weight: bold; margin-bottom: 10px;")
        main_layout.addWidget(title_label)
        
        # Parameter controls group
        controls_group = QGroupBox("Controles de Simulação")
        controls_group.setStyleSheet("""
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
        """)
        
        # Horizontal layout for parameter controls
        controls_layout = QHBoxLayout(controls_group)
        controls_layout.setSpacing(10)
        controls_layout.setContentsMargins(10, 20, 10, 10)
        
        # Create parameter controls
        parameter_order = [
            'total_mileage', 'fuel_level', 'vehicle_speed', 'engine_rpm', 
            'coolant_temp', 'fuel_economy', 'engine_torque'
        ]
        
        for param_name in parameter_order:
            control = ParameterControl(param_name)
            self.parameter_controls[param_name] = control
            controls_layout.addWidget(control)
        
        main_layout.addWidget(controls_group)
        
        # Control buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        # Reset all button
        self.btn_reset_all = QPushButton("🔄 Resetar Todos")
        self.btn_reset_all.setToolTip("Resetar todos os parâmetros para valores mínimos")
        self.btn_reset_all.clicked.connect(self.reset_all_parameters)
        button_layout.addWidget(self.btn_reset_all)
        
        # Disable all button
        self.btn_disable_all = QPushButton("❌ Desativar Todos")
        self.btn_disable_all.setToolTip("Desativar todas as simulações de parâmetros")
        self.btn_disable_all.clicked.connect(self.disable_all_parameters)
        button_layout.addWidget(self.btn_disable_all)
        
        button_layout.addStretch()
        
        # Status label
        self.status_label = QLabel("Pronto - Nenhum parâmetro ativo")
        self.status_label.setStyleSheet("color: #ffffff; font-size: 11px;")
        button_layout.addWidget(self.status_label)
        
        main_layout.addLayout(button_layout)
        
        # Apply dark theme
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e1e;
                color: #ffffff;
            }
            QPushButton {
                background-color: #404040;
                border: 2px solid #606060;
                border-radius: 6px;
                padding: 6px 12px;
                font-weight: bold;
                font-size: 11px;
                color: #ffffff;
                min-width: 80px;
                max-height: 30px;
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
        """)
        
    def setup_connections(self):
        """Setup signal connections."""
        # Connect each parameter control to the update handler
        for param_name, control in self.parameter_controls.items():
            control.value_changed.connect(self.on_parameter_changed)
    
    def on_parameter_changed(self, param_name: str, value: float, enabled: bool):
        """Handle parameter value change."""
        # Update simulation parameters
        self.simulation_params.set_parameter(param_name, enabled, value)
        
        # Update status
        self.update_status()
    
    def reset_all_parameters(self):
        """Reset all parameters to their minimum values."""
        for param_name, control in self.parameter_controls.items():
            conversion = ParameterConversions.get_conversion(param_name)
            min_value = conversion.get('range', (0, 100))[0]
            control.set_value(min_value)
    
    def disable_all_parameters(self):
        """Disable all parameter simulations."""
        for control in self.parameter_controls.values():
            control.set_enabled(False)
    
    def update_status(self):
        """Update status display."""
        active_params = []
        for param_name, control in self.parameter_controls.items():
            if control.enable_checkbox.isChecked():
                conversion = ParameterConversions.get_conversion(param_name)
                label = conversion.get('label', param_name)
                active_params.append(label)
        
        if active_params:
            status_text = f"Ativo: {', '.join(active_params)} ({len(active_params)} parâmetros)"
            self.status_label.setStyleSheet("color: #00D4AA; font-size: 11px; font-weight: bold;")
        else:
            status_text = "Pronto - Nenhum parâmetro ativo"
            self.status_label.setStyleSheet("color: #ffffff; font-size: 11px;")
        
        self.status_label.setText(status_text)
    
    def closeEvent(self, event):
        """Handle window close event."""
        # Disable all simulations when window is closed
        self.disable_all_parameters()
        
        # Stop update timer
        if self.update_timer.isActive():
            self.update_timer.stop()
        
        super().closeEvent(event)


def create_simulation_window(parent=None) -> SimulationWindow:
    """Factory function to create simulation window."""
    return SimulationWindow(parent)


if __name__ == "__main__":
    # Test the simulation window standalone
    from PyQt6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    window = SimulationWindow()
    window.show()
    sys.exit(app.exec())