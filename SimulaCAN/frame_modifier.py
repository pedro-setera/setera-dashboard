#!/usr/bin/env python3
"""
High-Performance CAN Frame Modifier
Ultra-fast frame modification engine for real-time J1939 parameter simulation.

Author: Pedro Silva
Date: June 2025
"""

import can
import struct
from typing import Dict, List
from simulation_params import SimulationParameters


class FrameModifier:
    """High-performance frame modification with minimal overhead."""
    
    def __init__(self, simulation_params: SimulationParameters):
        """Initialize frame modifier with simulation parameters."""
        self.simulation_params = simulation_params
        
        # Pre-compile byte manipulation functions for maximum speed
        self._byte_injectors = {
            'uint8': self._inject_uint8,
            'uint16_le': self._inject_uint16_le,
            'uint32_le': self._inject_uint32_le
        }
    
    def modify_frame(self, msg: can.Message) -> can.Message:
        """
        Modify frame with simulation parameters if applicable.
        OPTIMIZED: Prioritizes recently changed parameters for immediate responsiveness.
        
        Performance target: <0.1ms execution time
        
        Args:
            msg: Original CAN message
            
        Returns:
            Modified CAN message (or original if no modifications needed)
        """
        # Fast path: Early exit if no simulation is active
        if not self.simulation_params.is_simulation_enabled():
            return msg
        
        # Fast path: Check if this frame needs modification (O(1) lookup)
        frame_id = msg.arbitration_id
        if not self.simulation_params.has_frame_modifications(frame_id):
            return msg
        
        # Get modification instructions for this frame
        modifications = self.simulation_params.get_frame_modifications(frame_id)
        
        # Check if any parameters are actually enabled for this frame
        has_modifications = False
        for param_name in modifications.keys():
            enabled, _ = self.simulation_params.get_parameter_state(param_name)
            if enabled:
                has_modifications = True
                break
        
        # Fast path: Return original message if no modifications needed
        if not has_modifications:
            return msg
        
        # Create a copy of the message data for modification
        modified_data = bytearray(msg.data)
        
        # Apply enabled parameter modifications
        for param_name, byte_info in modifications.items():
            enabled, raw_value = self.simulation_params.get_parameter_state(param_name)
            if enabled:
                self._inject_parameter(modified_data, byte_info, raw_value)
        
        # Create new message with modified data
        modified_msg = can.Message(
            arbitration_id=msg.arbitration_id,
            data=bytes(modified_data),
            is_extended_id=msg.is_extended_id,
            timestamp=msg.timestamp
        )
        
        return modified_msg
    
    def should_prioritize_frame(self, frame_id: int, within_seconds: float = 2.0) -> bool:
        """
        Check if frame should be prioritized due to recent parameter changes.
        Used for immediate responsiveness optimization.
        """
        return self.simulation_params.has_recent_changes_for_frame(frame_id, within_seconds)
    
    def _inject_parameter(self, data: bytearray, byte_info: Dict, raw_value: int):
        """
        Inject parameter value into specific bytes.
        
        Args:
            data: Message data bytearray to modify
            byte_info: Byte positions and type information
            raw_value: Raw parameter value to inject
        """
        byte_positions = byte_info['bytes']
        data_type = byte_info['type']
        
        # Use pre-compiled injector function
        injector = self._byte_injectors.get(data_type)
        if injector:
            injector(data, byte_positions, raw_value)
    
    def _inject_uint8(self, data: bytearray, byte_positions: List[int], raw_value: int):
        """Inject 8-bit unsigned integer (1 byte)."""
        if len(byte_positions) == 1:
            byte_pos = byte_positions[0]
            if 0 <= byte_pos < len(data):
                data[byte_pos] = raw_value & 0xFF
    
    def _inject_uint16_le(self, data: bytearray, byte_positions: List[int], raw_value: int):
        """Inject 16-bit unsigned integer, little endian (2 bytes)."""
        if len(byte_positions) == 2:
            byte_pos_low = byte_positions[0]
            byte_pos_high = byte_positions[1]
            
            if (0 <= byte_pos_low < len(data) and 
                0 <= byte_pos_high < len(data)):
                
                # Little endian: LSB first, MSB second
                data[byte_pos_low] = raw_value & 0xFF          # Low byte
                data[byte_pos_high] = (raw_value >> 8) & 0xFF  # High byte
    
    def _inject_uint32_le(self, data: bytearray, byte_positions: List[int], raw_value: int):
        """Inject 32-bit unsigned integer, little endian (4 bytes)."""
        if len(byte_positions) == 4:
            # Validate all byte positions
            if all(0 <= pos < len(data) for pos in byte_positions):
                # Little endian: LSB first
                data[byte_positions[0]] = raw_value & 0xFF         # Byte 0 (LSB)
                data[byte_positions[1]] = (raw_value >> 8) & 0xFF  # Byte 1
                data[byte_positions[2]] = (raw_value >> 16) & 0xFF # Byte 2
                data[byte_positions[3]] = (raw_value >> 24) & 0xFF # Byte 3 (MSB)
    
    def get_modification_stats(self) -> Dict[str, int]:
        """Get performance statistics for debugging."""
        stats = {
            'frames_processed': 0,
            'frames_modified': 0,
            'parameters_active': 0
        }
        
        # Count active parameters
        for param_name in self.simulation_params.parameters:
            enabled, _ = self.simulation_params.get_parameter_state(param_name)
            if enabled:
                stats['parameters_active'] += 1
        
        return stats


class FrameAnalyzer:
    """Frame analysis utilities for debugging and validation."""
    
    @staticmethod
    def analyze_frame_bytes(frame_id: int, data: bytes) -> Dict[str, any]:
        """
        Analyze frame bytes and extract parameter values.
        
        Args:
            frame_id: CAN frame ID
            data: Frame data bytes
            
        Returns:
            Dictionary with extracted parameter values
        """
        analysis = {
            'frame_id': f"0x{frame_id:08X}",
            'data_hex': ' '.join(f'{b:02X}' for b in data),
            'parameters': {}
        }
        
        # Get frame modifications map
        frame_map = SimulationParameters.FRAME_MAP.get(frame_id, {})
        
        for param_name, byte_info in frame_map.items():
            try:
                raw_value = FrameAnalyzer._extract_raw_value(data, byte_info)
                analysis['parameters'][param_name] = {
                    'raw_value': raw_value,
                    'bytes': byte_info['bytes'],
                    'type': byte_info['type']
                }
            except Exception as e:
                analysis['parameters'][param_name] = {
                    'error': str(e)
                }
        
        return analysis
    
    @staticmethod
    def _extract_raw_value(data: bytes, byte_info: Dict) -> int:
        """Extract raw value from frame data."""
        byte_positions = byte_info['bytes']
        data_type = byte_info['type']
        
        if data_type == 'uint8' and len(byte_positions) == 1:
            return data[byte_positions[0]]
        
        elif data_type == 'uint16_le' and len(byte_positions) == 2:
            low_byte = data[byte_positions[0]]
            high_byte = data[byte_positions[1]]
            return low_byte | (high_byte << 8)
        
        elif data_type == 'uint32_le' and len(byte_positions) == 4:
            byte0 = data[byte_positions[0]]
            byte1 = data[byte_positions[1]]
            byte2 = data[byte_positions[2]]
            byte3 = data[byte_positions[3]]
            return byte0 | (byte1 << 8) | (byte2 << 16) | (byte3 << 24)
        
        return 0
    
    @staticmethod
    def validate_parameter_injection(param_name: str, expected_value: float, 
                                   frame_data: bytes, frame_id: int) -> bool:
        """
        Validate that parameter was correctly injected into frame.
        
        Args:
            param_name: Parameter name
            expected_value: Expected parameter value
            frame_data: Frame data to validate
            frame_id: CAN frame ID
            
        Returns:
            True if injection was successful
        """
        from simulation_params import ParameterConversions
        
        # Get expected raw value
        expected_raw = ParameterConversions.to_raw(param_name, expected_value)
        
        # Extract actual raw value from frame
        frame_map = SimulationParameters.FRAME_MAP.get(frame_id, {})
        byte_info = frame_map.get(param_name)
        
        if byte_info:
            actual_raw = FrameAnalyzer._extract_raw_value(frame_data, byte_info)
            return actual_raw == expected_raw
        
        return False


def create_frame_modifier(simulation_params: SimulationParameters) -> FrameModifier:
    """Factory function to create frame modifier instance."""
    return FrameModifier(simulation_params)