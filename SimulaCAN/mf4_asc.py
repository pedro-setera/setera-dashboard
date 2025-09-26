#!/usr/bin/env python3
"""
MF4 to ASC Converter for J1939 CAN Bus Data
Converts MDF4 files directly to ASC format for use with python-can simulator.

This converter preserves the exact original log data without any frame injection,
ensuring compatibility with J1939 devices and proper extended frame handling.

Requirements:
    pip install asammdf

Usage:
    python mf4_asc.py

Author: Pedro Silva
Date: June 2025
"""

import os
import sys
from pathlib import Path

try:
    from asammdf import MDF
except ImportError:
    print("❌ Error: asammdf library not found!")
    print("Install it with: pip install asammdf")
    sys.exit(1)

# Configuration
INPUT_MF4_FILE = '00000001.MF4'
OUTPUT_ASC_FILE = 'original_truck_log.asc'
LOG_FILE = 'converter_log.txt'

# Global log file handle
log_file = None

def log_print(message):
    """Print to both console and log file."""
    print(message)
    if log_file:
        log_file.write(message + '\n')
        log_file.flush()

def create_asc_header():
    """Create standard ASC file header compatible with python-can."""
    return """date Mon Jun 09 08:32:13.606 2025
base hex  timestamps absolute
internal events logged
Begin Triggerblock Thu Jan 01 00:10:30.432 1970
 0.000000 Start of measurement
"""

def create_asc_footer():
    """Create standard ASC file footer."""
    return "End TriggerBlock\n"

def format_asc_line(timestamp, can_id, dlc, data_bytes, is_extended=False):
    """
    Format a single CAN message line for ASC output.
    
    Args:
        timestamp: Relative timestamp in seconds
        can_id: CAN identifier as integer
        dlc: Data Length Code
        data_bytes: Raw data bytes
        is_extended: True for 29-bit extended frames, False for 11-bit standard
        
    Returns:
        Formatted ASC line string
    """
    # Format CAN ID with proper extended frame suffix
    if is_extended:
        can_id_str = f"{can_id:08X}x"  # 29-bit with 'x' suffix
    else:
        can_id_str = f"{can_id:03X}"   # 11-bit standard format
    
    # Format data bytes as space-separated hex
    if isinstance(data_bytes, (list, tuple)):
        data_str = ' '.join(f'{b:02X}' for b in data_bytes)
    else:
        # Handle bytes object or other formats
        data_str = ' '.join(f'{b:02X}' for b in data_bytes)
    
    # Create ASC line: timestamp channel ID direction type DLC data
    return f" {timestamp:0.6f} 1  {can_id_str:<9s} Rx   d {dlc} {data_str}\n"

def convert_mf4_to_asc():
    """
    Convert MF4 file to ASC format with proper J1939 extended frame support.
    FIXED: Properly correlate structured CAN data channels.
    """
    global log_file
    
    # Open log file for writing
    log_file = open(LOG_FILE, 'w', encoding='utf-8')
    
    # Check if input file exists
    if not Path(INPUT_MF4_FILE).exists():
        log_print(f"❌ Error: Input file '{INPUT_MF4_FILE}' not found!")
        log_print(f"Current directory: {os.getcwd()}")
        log_print(f"Available MF4 files:")
        for f in Path('.').glob('*.MF4'):
            log_print(f"  - {f}")
        log_file.close()
        return False
    
    log_print(f"🔧 Converting '{INPUT_MF4_FILE}' to '{OUTPUT_ASC_FILE}'...")
    log_print("="*60)
    
    try:
        # Open MF4 file
        log_print("📖 Reading MF4 file...")
        with MDF(INPUT_MF4_FILE) as mdf:
            log_print(f"✅ MF4 file opened successfully")
            log_print(f"   Version: {mdf.version}")
            log_print(f"   Channels: {len(mdf.channels_db)}")
            
            # List all channels for debugging
            all_channels = list(mdf.channels_db.keys())
            can_channels = [ch for ch in all_channels if 'CAN' in ch.upper()]
            
            log_print(f"📡 Found {len(can_channels)} CAN-related channels:")
            for ch in can_channels[:10]:  # Show first 10
                log_print(f"   - {ch}")
            if len(can_channels) > 10:
                log_print(f"   ... and {len(can_channels) - 10} more")
            
            # ✅ FIXED APPROACH: Prioritize CAN_DataFrame channels
            # Try to find the main CAN DataFrame channels first
            can_id_channel = None
            can_ide_channel = None
            can_dlc_channel = None
            can_data_channel = None
            
            # First, try to find CAN_DataFrame channels (preferred)
            dataframe_channels = [ch for ch in can_channels if 'CAN_DataFrame.' in ch]
            
            if dataframe_channels:
                log_print(f"   Using CAN_DataFrame channels (preferred)")
                for ch_name in dataframe_channels:
                    if ch_name.endswith('.ID'):
                        can_id_channel = ch_name
                    elif ch_name.endswith('.IDE'):
                        can_ide_channel = ch_name
                    elif ch_name.endswith('.DLC'):
                        can_dlc_channel = ch_name
                    elif ch_name.endswith('.DataBytes'):
                        can_data_channel = ch_name
            else:
                # Fallback to any CAN channels
                log_print(f"   Using fallback CAN channel detection")
                for ch_name in can_channels:
                    if 'ID' in ch_name and 'IDE' not in ch_name and can_id_channel is None:
                        can_id_channel = ch_name
                    elif 'IDE' in ch_name and can_ide_channel is None:
                        can_ide_channel = ch_name
                    elif 'DLC' in ch_name and can_dlc_channel is None:
                        can_dlc_channel = ch_name
                    elif 'DataBytes' in ch_name and can_data_channel is None:
                        can_data_channel = ch_name
            
            log_print(f"\n🔍 Structured CAN channels found:")
            log_print(f"   ID Channel: {can_id_channel}")
            log_print(f"   IDE Channel: {can_ide_channel}")
            log_print(f"   DLC Channel: {can_dlc_channel}")
            log_print(f"   Data Channel: {can_data_channel}")
            
            if not all([can_id_channel, can_ide_channel, can_dlc_channel, can_data_channel]):
                log_print("❌ Missing required CAN channels! Cannot proceed with structured approach.")
                log_print(f"   Missing channels:")
                if not can_id_channel: log_print(f"     - ID channel")
                if not can_ide_channel: log_print(f"     - IDE channel")
                if not can_dlc_channel: log_print(f"     - DLC channel")
                if not can_data_channel: log_print(f"     - Data channel")
                log_print(f"\n💡 Available channels for manual selection:")
                for ch in sorted(can_channels):
                    log_print(f"     - {ch}")
                log_file.close()
                return False
            
            # ✅ EXTRACT CORRELATED CAN DATA
            log_print(f"\n📡 Extracting correlated CAN messages...")
            
            # Get all required signals
            id_signal = mdf.get(can_id_channel)
            ide_signal = mdf.get(can_ide_channel)
            dlc_signal = mdf.get(can_dlc_channel)
            data_signal = mdf.get(can_data_channel)
            
            if not all([id_signal, ide_signal, dlc_signal, data_signal]):
                log_print("❌ Failed to extract required CAN signals!")
                log_file.close()
                return False
            
            # Verify all signals have same length
            lengths = [len(s.samples) for s in [id_signal, ide_signal, dlc_signal, data_signal]]
            log_print(f"   Signal lengths: ID={lengths[0]}, IDE={lengths[1]}, DLC={lengths[2]}, Data={lengths[3]}")
            
            if len(set(lengths)) != 1:
                log_print("⚠️  Warning: Signal lengths don't match! Using minimum length.")
                min_length = min(lengths)
            else:
                min_length = lengths[0]
            
            log_print(f"   Processing {min_length} CAN messages...")
            
            # Extract CAN messages by correlating channels
            all_messages = []
            unique_frame_ids = set()  # Track unique frame IDs
            
            for i in range(min_length):
                try:
                    timestamp = float(id_signal.timestamps[i])
                    can_id = int(id_signal.samples[i])
                    ide = int(ide_signal.samples[i])
                    dlc = int(dlc_signal.samples[i])
                    
                    # Extract data bytes
                    data_sample = data_signal.samples[i]
                    if isinstance(data_sample, (bytes, bytearray)):
                        data_bytes = list(data_sample[:dlc])
                    elif hasattr(data_sample, '__iter__'):
                        data_bytes = list(data_sample)[:dlc]
                    else:
                        data_bytes = []
                    
                    # Validate CAN message
                    if can_id <= 0 or can_id > 0x1FFFFFFF:
                        continue
                    if dlc < 0 or dlc > 8:
                        continue
                    
                    # ✅ USE IDE FIELD FOR EXTENDED DETECTION
                    is_extended = (ide == 1)
                    
                    # Track unique frame IDs
                    unique_frame_ids.add(can_id)
                    
                    # Store message
                    all_messages.append({
                        'timestamp': timestamp,
                        'can_id': can_id,
                        'dlc': dlc,
                        'data': data_bytes,
                        'is_extended': is_extended
                    })
                    
                    # Progress indicator
                    if (i + 1) % 10000 == 0:
                        log_print(f"   Processed {i + 1:,}/{min_length:,} messages...")
                
                except (ValueError, TypeError, IndexError) as e:
                    # Skip malformed messages
                    continue
            
            if not all_messages:
                log_print("❌ No valid CAN messages found in MF4 file!")
                log_file.close()
                return False
            
            log_print(f"✅ Extracted {len(all_messages)} CAN messages")
            
            # Sort messages by timestamp
            all_messages.sort(key=lambda x: x['timestamp'])
            
            # Calculate relative timestamps
            first_timestamp = all_messages[0]['timestamp']
            for msg in all_messages:
                msg['relative_time'] = msg['timestamp'] - first_timestamp
            
            # Write ASC file
            log_print(f"💾 Writing ASC file...")
            with open(OUTPUT_ASC_FILE, 'w') as outfile:
                # Write header
                outfile.write(create_asc_header())
                
                # Write CAN messages
                extended_count = 0
                standard_count = 0
                
                for msg in all_messages:
                    asc_line = format_asc_line(
                        msg['relative_time'],
                        msg['can_id'],
                        msg['dlc'],
                        msg['data'],
                        msg['is_extended']
                    )
                    outfile.write(asc_line)
                    
                    if msg['is_extended']:
                        extended_count += 1
                    else:
                        standard_count += 1
                
                # Write footer
                outfile.write(create_asc_footer())
            
            log_print("="*60)
            log_print(f"✅ Conversion completed successfully!")
            log_print(f"📊 Statistics:")
            log_print(f"   Total messages: {len(all_messages)}")
            log_print(f"   Extended frames (29-bit): {extended_count}")
            log_print(f"   Standard frames (11-bit): {standard_count}")
            log_print(f"   Output file: {OUTPUT_ASC_FILE}")
            log_print(f"   Duration: {all_messages[-1]['relative_time']:.3f} seconds")
            
            # ✅ UNIQUE FRAME IDs ANALYSIS
            sorted_unique_ids = sorted(unique_frame_ids)
            log_print(f"\n📋 Unique Frame IDs Found (Alphabetical Order):")
            for frame_id in sorted_unique_ids:
                log_print(f"   0x{frame_id:08X}")
            
            log_print(f"\n📊 Unique Frame IDs Statistics:")
            log_print(f"   Total unique frame IDs: {len(sorted_unique_ids)}")
            
            # ✅ ENHANCED DIAGNOSTICS
            # Show sample messages with IDE analysis
            log_print(f"\n🔍 Frame Type Analysis:")
            extended_samples = [msg for msg in all_messages[:100] if msg['is_extended']]
            standard_samples = [msg for msg in all_messages[:100] if not msg['is_extended']]
            
            if extended_samples:
                log_print(f"\n📋 Sample Extended Frames (IDE=1):")
                for i, msg in enumerate(extended_samples[:5]):
                    data_str = ' '.join(f'{b:02X}' for b in msg['data'])
                    log_print(f"   {i+1}. {msg['relative_time']:8.3f}s | 0x{msg['can_id']:08X}x | {data_str}")
            
            if standard_samples:
                log_print(f"\n📋 Sample Standard Frames (IDE=0):")
                for i, msg in enumerate(standard_samples[:5]):
                    data_str = ' '.join(f'{b:02X}' for b in msg['data'])
                    log_print(f"   {i+1}. {msg['relative_time']:8.3f}s | 0x{msg['can_id']:03X}  | {data_str}")
            
            # ✅ ID RANGE ANALYSIS
            extended_ids = [msg['can_id'] for msg in all_messages if msg['is_extended']]
            standard_ids = [msg['can_id'] for msg in all_messages if not msg['is_extended']]
            
            if extended_ids:
                log_print(f"\n📊 Extended Frame ID Range:")
                log_print(f"   Min: 0x{min(extended_ids):08X} | Max: 0x{max(extended_ids):08X}")
            
            if standard_ids:
                log_print(f"\n📊 Standard Frame ID Range:")
                log_print(f"   Min: 0x{min(standard_ids):03X} | Max: 0x{max(standard_ids):03X}")
            
            log_file.close()
            return True
            
    except Exception as e:
        log_print(f"❌ Error converting MF4 file: {e}")
        import traceback
        log_print(traceback.format_exc())
        if log_file:
            log_file.close()
        return False

def main():
    """Main entry point."""
    print("🚛 MF4 to ASC Converter for J1939 CAN Bus Data")
    print("="*60)
    
    success = convert_mf4_to_asc()
    
    if success:
        print(f"\n🎯 Ready for testing!")
        print(f"   Use this command to test: python simulador_can.pyw")
        print(f"   Load file: {OUTPUT_ASC_FILE}")
        print(f"   Detailed log saved to: {LOG_FILE}")
        print(f"\n💡 This converter preserves the exact original truck data")
        print(f"   without any frame injection or modification.")
    else:
        print(f"\n❌ Conversion failed. Check the error messages in {LOG_FILE}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())