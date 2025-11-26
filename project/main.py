import messages as msg
import socket
from host import Host
from player import Player
import config


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
        host.joiner_listen()
        host.run_host_loop()  # This loop runs indefinitely

    # ---------------------------------------------------------
    # JOINER / SPECTATOR MODES
    # ---------------------------------------------------------
    elif choice in ['J', 'S']:
        is_spectator = (choice == 'S')

        host_ip = input(f"Enter Host IP (leave blank for {my_ip}): ").strip()

        if not host_ip:
            host_ip_check = input("Is the host running on this same machine? (Y/N): ").strip().upper()
            host_ip = '127.0.0.1' if host_ip_check == 'Y' else my_ip

        # Use any available port for the local client
        player = Player(host_ip, config.DEFAULT_PORT, local_port=0)

        print("\n[MAIN] Attempting to connect to host...\n")

        if player.connect(as_spectator=is_spectator):
            print("\n[MAIN] Connection successful!\n")

            if is_spectator:
                print("[MAIN] Joined as Spectator.")
            else:
                print("[MAIN] Joined as Player.")

            player.run_game_loop()

        else:
            print("[MAIN] Connection failed. Exiting.\n")

    else:
        print("Invalid mode selected. Exiting.")


# ---------------------------------------------------------
# DEBUG MESSAGE GENERATOR (optional, unused in gameplay)
# ---------------------------------------------------------
def main():
    """
    This function prints sample messages for developers.
    Not used in gameplay.
    """
    messages = [
        msg.HandshakeRequestMessage(),
        msg.HandshakeResponseMessage(seed=12345),
        msg.SpectatorRequestMessage(),
        msg.BattleSetupMessage(communication_mode=msg.CommunicationMode.P2P,
                               pokemon_name="Pikachu",
                               stat_boosts={"sp_attack_uses": 5, "sp_def_uses": 5}),
        msg.AttackAnnounceMessage(move_name="Thunderbolt",
                                  sequence_number=4),
        msg.DefenseAnnounceMessage(sequence_number=5),
        msg.CalculationReportMessage(attacker="Pikachu",
                                     move_used="Thunderbolt",
                                     remaining_health=23,
                                     damage_dealt=4,
                                     defender_hp_remaining=45,
                                     status_message="Sample status message",
                                     sequence_number=6),
        msg.CalculationConfirmMessage(sequence_number=7),
        msg.ResolutionRequestMessage(attacker="Pikachu",
                                     move_used="Thunderbolt",
                                     damage_dealt="4",
                                     defender_hp_remaining=45,
                                     sequence_number=8),
        msg.GameOverMessage(winner="Pikachu",
                            loser="Charmander",
                            sequence_number=9),
        msg.ChatMessage(sender_name="Player1",
                        content_type=msg.ChatMessageType.TEXT,
                        content="Good luck",
                        sequence_number=10),
        msg.ChatMessage(sender_name="Player2",
                        content_type=msg.ChatMessageType.STICKER,
                        content="base64_encoded_data_here",
                        sequence_number=11),
        msg.AckReplyMessage(ack_number=12),
    ]

    print("==============================")
    for message in messages:
        print(message.as_text())
        print("==============================")
