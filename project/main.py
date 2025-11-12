import messages as msg
import socket
from host import Host
from player import Player
import config

def get_my_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        # Fallback to localhost
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

if __name__ == "__main__":

    my_ip = get_my_ip()
    print(f"Your Local IP is: {my_ip}")
    print(f"Default Port is: {config.DEFAULT_PORT}")

    choice = ""
    while choice not in ['H', 'J', 'S']:
        choice = input("Run as (H)ost, (J)oiner, or (S)pectator? ").strip().upper()

    if choice == 'H':
        # --- Run as Host ---
        host = Host(my_ip, config.DEFAULT_PORT)
        host.run_host_loop() # This loop runs forever

    elif choice == 'J' or choice == 'S':
        # --- Run as Joiner or Spectator ---
        host_ip = input(f"Enter Host IP (leave blank for {my_ip}): ").strip()
        if not host_ip:
            # Check if we are running the joiner on the same machine as host
            host_ip_check = input(f"Is host on this machine? (Y/N) ").strip().upper()
            if host_ip_check == 'Y':
                host_ip = '127.0.0.1' # Use localhost if on same machine
            else:
                host_ip = my_ip # Use local network IP

        # Use port 0 to let the OS pick any available port for the client
        player = Player(host_ip, config.DEFAULT_PORT, local_port=0)

        is_spectator = (choice == 'S')

        # 1. Try to connect
        if player.connect(as_spectator=is_spectator):
            print("[Main] Connection to host successful.")
            # 2. If successful, run the main game/spectator loop
            player.run_game_loop()
        else:
            print("[Main] Failed to connect to host. Exiting.")

    else:
        print("Invalid choice.")


def main():
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
                                     status_message="Sample status message am too lazy",
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
                        content="Imagine this is b64 data",
                        sequence_number=11),
        msg.AckReplyMessage(ack_number=12),
    ]

    print("==============================")
    for message in messages:
        print(message.as_text())
        print("==============================")

