import messages as msg
import socket
import config
import os
from host import Host
from player import Player
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

def main_menu():
    loop_menu = True
    while loop_menu:
        my_ip = get_my_ip()
        print(f"Local IP: {my_ip}")
        print(f"Default Port: {config.DEFAULT_PORT}")

        choice = ""
        while choice not in ['H', 'J', 'S']:
            choice = input("Run as (H)ost, (J)oiner, or (S)pectator? ").strip().upper()

        # HOST MODE
        if choice == 'H':
            # --- Run as Host ---
            host = Host(my_ip, config.DEFAULT_PORT)
            print("\n[MAIN] Host mode started. Waiting for connections...")
            host.joiner_listen()
            host.run_game_loop()

        # Joiner Mode
        elif choice == 'J':
            host_ip = input(f"Enter Host IP (leave blank for {my_ip}): ").strip()

            if not host_ip:
                host_ip = my_ip

            player = Player(host_ip, config.DEFAULT_PORT,local_ip=my_ip, local_port=0)
            player.connect()
            player.run_game_loop()

        # Spectator Mode
        elif choice == 'S':
            host_ip = input(f"Enter Host IP (leave blank for {my_ip}): ").strip()

            if not host_ip:
                host_ip = my_ip

            spectator = Spectator(host_ip, config.DEFAULT_PORT,local_ip=my_ip, local_port=0)
            spectator.connect_to_host()

        choice = ""
        while choice not in ["Y", "N"]:
            choice = input("Start a new game? [Y/N]").strip().upper()

        if choice == "N":
            loop_menu = False


if __name__ == "__main__":
    print_header()
    main_menu()
