import messages as msg
import socket
from host import Host
from player import Player
import config
from spectator import Spectator


def get_my_ip():
    """Attempts to get the local network IP. Falls back to localhost."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP


def print_header():
    print("\n====================================")
    print("        POKE-PROTOCOL v1.0")
    print("      RFC-Compliant Battle Game")
    print("====================================\n")


if __name__ == "__main__":

    print_header()

    my_ip = get_my_ip()
    print(f"Your Local IP is: {my_ip}")
    print(f"Default Port is: {config.DEFAULT_PORT}\n")

    choice = ""
    while choice not in ['H', 'J', 'S']:
        choice = input("Run as (H)ost, (J)oiner, or (S)pectator? ").strip().upper()

    # ---------------------------------------------------------
    # HOST MODE
    # ---------------------------------------------------------
    if choice == 'H':
        host = Host(my_ip, config.DEFAULT_PORT)
        print("\n[MAIN] Host mode started. Waiting for connections...")
        host.run_host_loop()  # This loop runs indefinitely

    # ---------------------------------------------------------
    # JOINER / SPECTATOR MODES
    # ---------------------------------------------------------
    elif choice == 'J':
        host_ip = input(f"Enter Host IP (leave blank for {my_ip}): ").strip()

        if not host_ip:
            host_ip_check = input("Is the host running on this same machine? (Y/N): ").strip().upper()
            host_ip = '127.0.0.1' if host_ip_check == 'Y' else my_ip

        player = Player(host_ip, config.DEFAULT_PORT, local_port=0)
        player.connect_to_host()

    elif choice == 'S':
        host_ip = input(f"Enter Host IP (leave blank for {my_ip}): ").strip()

        if not host_ip:
            host_ip_check = input("Is the host running on this same machine? (Y/N): ").strip().upper()
            host_ip = '127.0.0.1' if host_ip_check == 'Y' else my_ip

        spectator = Spectator(host_ip, config.DEFAULT_PORT, local_port=0)
        spectator.connect_to_host()

    else:
        print("Invalid mode selected. Exiting.")
