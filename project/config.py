"""
Central configuration file for the PokeProtocol project.
Stores all shared constants, ports, timeouts, and file paths.
"""

# --- Network Configuration ---
DEFAULT_PORT = 4566
BUFFER_SIZE = 10485760

# --- Connection Timeouts ---
HANDSHAKE_TIMEOUT = 5.0  # 5 seconds
BATTLE_SETUP_TIMEOUT = 10.0  # 10 seconds
ACK_TIMEOUT = 0.5  # 500 ms
