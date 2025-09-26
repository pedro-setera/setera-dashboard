#!/usr/bin/env python3
"""
Real-Time J1939 Simulation Parameters
Thread-safe parameter storage with atomic operations for high-performance frame modification.

Author: Pedro Silva
Date: June 2025
"""

import threading
import time
from typing import Dict, Tuple, Any, Callable, Optional
from dataclasses import dataclass


@dataclass
class AtomicParameter:
    """Lock-free atomic parameter storage with immediate update notifications."""
    enabled: bool = False
    raw_value: int = 0
    last_update_time: float = 0.0
    
    def set_enabled(self, enabled: bool):
        """Set enabled state (atomic for primitive types in Python)."""
        self.enabled = enabled
        self.last_update_time = time.time()
    
    def set_value(self, raw_value: int):
        """Set raw value (atomic for primitive types in Python)."""
        self.raw_value = raw_value
        self.last_update_time = time.time()
    
    def get_state(self) -> Tuple[bool, int]:
        """Get both enabled state and value (lock-free read)."""
        return self.enabled, self.raw_value
    
    def get_state_with_time(self) -> Tuple[bool, int, float]:
        """Get state with last update timestamp for change detection."""
        return self.enabled, self.raw_value, self.last_update_time


class ParameterConversions:
    """Bidirectional parameter conversions with validation."""
    
    CONVERSIONS = {
        'total_mileage': {
            'to_raw': lambda km: int(km * 1000 / 5),
            'from_raw': lambda raw: (raw * 5) / 1000,
            'range': (0, 200000),
            'unit': 'Km',
            'precision': 0.005,
            'label': 'Odo'
        },
        'fuel_level': {
            'to_raw': lambda pct: int(pct / 0.4),
            'from_raw': lambda raw: raw * 0.4,
            'range': (0, 100),
            'unit': '%',
            'precision': 0.4,
            'label': 'Tanque'
        },
        'vehicle_speed': {
            'to_raw': lambda kmh: int(kmh * 256),
            'from_raw': lambda raw: raw / 256,
            'range': (0, 200),
            'unit': 'Km/h',
            'precision': 1/256,
            'label': 'Vel'
        },
        'engine_rpm': {
            'to_raw': lambda rpm: int(rpm / 0.125),
            'from_raw': lambda raw: raw * 0.125,
            'range': (0, 5000),
            'unit': 'RPM',
            'precision': 0.125,
            'label': 'RPM'
        },
        'coolant_temp': {
            'to_raw': lambda celsius: int(celsius + 40),
            'from_raw': lambda raw: raw - 40,
            'range': (0, 120),
            'unit': '°C',
            'precision': 1,
            'label': 'Temp'
        },
        'fuel_economy': {
            'to_raw': lambda kml: int(kml * 512),
            'from_raw': lambda raw: raw / 512,
            'range': (0, 50),
            'unit': 'Km/L',
            'precision': 1/512,
            'label': 'Cons Inst'
        },
        'engine_torque': {
            'to_raw': lambda pct: int(pct + 125),  # J1939: User 0-130% → Raw 125-255
            'from_raw': lambda raw: raw - 125,     # J1939: Raw 125-255 → User 0-130%
            'range': (0, 130),                     # User-friendly 0% to 130% (max possible)
            'unit': '%',
            'precision': 1,
            'label': 'Torque'
        }
    }
    
    @classmethod
    def get_conversion(cls, param_name: str) -> Dict[str, Any]:
        """Get conversion functions and metadata for parameter."""
        return cls.CONVERSIONS.get(param_name, {})
    
    @classmethod
    def to_raw(cls, param_name: str, value: float) -> int:
        """Convert human value to raw CAN value."""
        conversion = cls.CONVERSIONS.get(param_name)
        if conversion:
            raw_value = conversion['to_raw'](value)
            # Validate range for raw value based on byte size
            if param_name in ['fuel_level', 'coolant_temp', 'engine_torque']:
                return max(0, min(255, raw_value))  # 8-bit
            elif param_name in ['vehicle_speed', 'engine_rpm', 'fuel_economy']:
                return max(0, min(65535, raw_value))  # 16-bit
            else:  # total_mileage (32-bit)
                return max(0, min(4294967295, raw_value))  # 32-bit
        return 0
    
    @classmethod
    def from_raw(cls, param_name: str, raw_value: int) -> float:
        """Convert raw CAN value to human value."""
        conversion = cls.CONVERSIONS.get(param_name)
        if conversion:
            return conversion['from_raw'](raw_value)
        return 0.0


class SimulationParameters:
    """Thread-safe parameter storage with atomic operations and immediate update notifications."""
    
    # Pre-calculated frame modification map for O(1) lookup
    # NOTE: J1939 docs use 1-based indexing (bytes 1-8), our software uses 0-based (bytes 0-7)
    # All byte positions shifted by -1 to match 0-based indexing
    FRAME_MAP = {
        0x18FEC1EE: {  # High Resolution Total Vehicle Distance
            'total_mileage': {'bytes': [0, 1, 2, 3], 'type': 'uint32_le'}  # J1939 bytes 1-4 → 0-3
        },
        0x18FEFC47: {  # Dash Display - Fuel Level
            'fuel_level': {'bytes': [1], 'type': 'uint8'}  # J1939 byte 2 → 1
        },
        0x18FEF100: {  # Vehicle Position - Vehicle Speed
            'vehicle_speed': {'bytes': [1, 2], 'type': 'uint16_le'}  # J1939 bytes 2-3 → 1-2
        },
        0x0CF00400: {  # Electronic Engine Controller 1 - RPM & Torque
            'engine_rpm': {'bytes': [3, 4], 'type': 'uint16_le'},      # J1939 bytes 4-5 → 3-4
            'engine_torque': {'bytes': [2], 'type': 'uint8'}           # J1939 byte 3 → 2
        },
        0x18FEEE00: {  # Engine Temperature 1 - Coolant Temperature
            'coolant_temp': {'bytes': [0], 'type': 'uint8'}  # J1939 byte 1 → 0
        },
        0x18FEF200: {  # Fuel Economy - Instantaneous Fuel Economy
            'fuel_economy': {'bytes': [2, 3], 'type': 'uint16_le'}  # J1939 bytes 3-4 → 2-3
        }
    }
    
    # Reverse lookup: parameter → frame IDs that contain it
    PARAM_TO_FRAMES = {}
    
    def __init__(self):
        """Initialize atomic parameters storage with immediate update system."""
        self.parameters = {
            'total_mileage': AtomicParameter(),
            'fuel_level': AtomicParameter(),
            'vehicle_speed': AtomicParameter(),
            'engine_rpm': AtomicParameter(),
            'coolant_temp': AtomicParameter(),
            'fuel_economy': AtomicParameter(),
            'engine_torque': AtomicParameter()
        }
        
        # Global simulation enable flag
        self._simulation_enabled = threading.Event()
        
        # Update callbacks for immediate responsiveness
        self._update_callbacks: list[Callable[[str, bool, int], None]] = []
        
        # Build reverse lookup map for performance
        if not self.PARAM_TO_FRAMES:
            for frame_id, frame_params in self.FRAME_MAP.items():
                for param_name in frame_params.keys():
                    if param_name not in self.PARAM_TO_FRAMES:
                        self.PARAM_TO_FRAMES[param_name] = []
                    self.PARAM_TO_FRAMES[param_name].append(frame_id)
        
        # Track recent parameter changes for immediate updates
        self._recent_changes = {}
        self._last_change_check = time.time()
    
    def set_parameter(self, param_name: str, enabled: bool, human_value: float = 0.0):
        """Set parameter state and value with immediate update notifications."""
        if param_name in self.parameters:
            param = self.parameters[param_name]
            old_enabled, old_raw = param.get_state()
            
            param.set_enabled(enabled)
            new_raw = 0
            if enabled:
                new_raw = ParameterConversions.to_raw(param_name, human_value)
                param.set_value(new_raw)
            
            # Track change for immediate updates
            if enabled != old_enabled or new_raw != old_raw:
                self._recent_changes[param_name] = time.time()
                
                # Notify callbacks immediately for responsive UI
                for callback in self._update_callbacks:
                    try:
                        callback(param_name, enabled, new_raw)
                    except Exception:
                        pass  # Silent failure to prevent callback issues
            
            # Update global simulation state
            self._update_simulation_state()
    
    def register_update_callback(self, callback: Callable[[str, bool, int], None]):
        """Register callback for immediate parameter change notifications."""
        if callback not in self._update_callbacks:
            self._update_callbacks.append(callback)
    
    def unregister_update_callback(self, callback: Callable[[str, bool, int], None]):
        """Unregister parameter change callback."""
        if callback in self._update_callbacks:
            self._update_callbacks.remove(callback)
    
    def get_parameter_state(self, param_name: str) -> Tuple[bool, int]:
        """Get parameter enabled state and raw value."""
        if param_name in self.parameters:
            return self.parameters[param_name].get_state()
        return False, 0
    
    def get_parameter_frames(self, param_name: str) -> list[int]:
        """Get list of frame IDs that contain this parameter."""
        return self.PARAM_TO_FRAMES.get(param_name, [])
    
    def was_recently_changed(self, param_name: str, within_seconds: float = 5.0) -> bool:
        """Check if parameter was changed within the specified time window."""
        if param_name in self._recent_changes:
            return time.time() - self._recent_changes[param_name] <= within_seconds
        return False
    
    def get_recent_changes(self, within_seconds: float = 5.0) -> Dict[str, float]:
        """Get dictionary of parameters changed within time window with timestamps."""
        current_time = time.time()
        recent = {}
        for param_name, change_time in self._recent_changes.items():
            if current_time - change_time <= within_seconds:
                recent[param_name] = change_time
        return recent
    
    def is_simulation_enabled(self) -> bool:
        """Check if any parameter simulation is enabled."""
        return self._simulation_enabled.is_set()
    
    def _update_simulation_state(self):
        """Update global simulation enabled state."""
        any_enabled = any(param.enabled for param in self.parameters.values())
        if any_enabled:
            self._simulation_enabled.set()
        else:
            self._simulation_enabled.clear()
    
    def get_frame_modifications(self, frame_id: int) -> Dict[str, Dict]:
        """Get modification instructions for a frame ID."""
        return self.FRAME_MAP.get(frame_id, {})
    
    def has_frame_modifications(self, frame_id: int) -> bool:
        """Check if frame ID has any enabled modifications."""
        if frame_id not in self.FRAME_MAP:
            return False
        
        frame_params = self.FRAME_MAP[frame_id]
        for param_name in frame_params.keys():
            if param_name in self.parameters:
                enabled, _ = self.parameters[param_name].get_state()
                if enabled:
                    return True
        return False
    
    def has_recent_changes_for_frame(self, frame_id: int, within_seconds: float = 2.0) -> bool:
        """Check if frame has any parameters that were recently changed."""
        if frame_id not in self.FRAME_MAP:
            return False
        
        frame_params = self.FRAME_MAP[frame_id]
        for param_name in frame_params.keys():
            if self.was_recently_changed(param_name, within_seconds):
                return True
        return False


# Global simulation parameters instance
simulation_params = SimulationParameters()


def get_simulation_params() -> SimulationParameters:
    """Get the global simulation parameters instance."""
    return simulation_params