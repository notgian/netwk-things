import random
from client import Client
import messages
from protocol import GameProtocolHandler
from pokemon import load_pokemon_data
import battleLogic


# ---------------------------------------------------------
# Helper UI functions for Host
# ---------------------------------------------------------

def choose_pokemon(pokemon_db):
    """Simple CLI Pokémon selection menu."""
    names = list(pokemon_db.keys())
    print("\n=== Choose Your Pokémon ===")
    for i, name in enumerate(names):
        print(f"{i+1}. {name}")

    while True:
        choice = input("Enter Pokémon name or number: ").strip()
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(names):
                return names[idx]

        for n in names:
            if n.lower() == choice.lower():
                return n

        print("Invalid Pokémon. Try again.")


def choose_stat_boosts():
    """Ask user for RFC-allowed stat boosts."""
    print("\n=== Stat Boost Allocation ===")
    while True:
        try:
            sa = int(input("Special Attack Boost Uses (0–5): "))
            sd = int(input("Special Defense Boost Uses (0–5): "))
            if 0 <= sa <= 5 and 0 <= sd <= 5:
                return {
                    "special_attack_uses": sa,
                    "special_defense_uses": sd,
                }
        except ValueError:
            pass
        print("Invalid input. Enter numbers between 0 and 5.")


# ---------------------------------------------------------
# HOST CLASS
# ---------------------------------------------------------

class Host:
    """
    Manages the game as the Host (Player 1).
    Uses the Client to handle networking.
    Handles exactly one player + any spectators.
    """

    def __init__(self, host_ip, port):
        self.net_client = Client()
        if not self.net_client.bind_socket(host_ip, port):
            exit()

        self.player_opponent_addr = None
        self.spectator_addrs = []

        self.protocol_handler = GameProtocolHandler(self.net_client)
        print(f"[HOST] Host Client running at {host_ip}:{port}")

    # =====================================================
    # MAIN HOST LOOP
    # =====================================================
    def run_host_loop(self):
        print("\n[HOST] Waiting for player connection...")

        while True:
            try: 
                message_text, address = self.net_client.receive_from()

                # No message
                if not message_text:
                    continue

                # Existing player
                if address == self.player_opponent_addr:
                    self.handle_player_message(message_text)

                # Existing spectator
                elif address in self.spectator_addrs:
                    self.handle_spectator_message(message_text)

                # New connection
                else:
                    self.handle_new_connection(message_text, address)

                # ---------------------------------------------------------
                # GAME STATE HANDLING (BATTLE LOGIC)
                # ---------------------------------------------------------

                state = self.protocol_handler.game_state

                # =========== BATTLE SETUP ===========
                if state == "SETUP":
                    self.handle_setup_phase()

                # =========== TURN: HOST ATTACKS/DEFENDS ===========
                elif state == "WAITING_FOR_MOVE":
                    if self.protocol_handler.is_my_turn():
                        self.handle_my_turn()
                    else:
                        self.handle_defense_phase()

                # =========== DAMAGE CALCULATION ===========
                elif state == "PROCESSING_TURN":
                    self.handle_defense_phase()
                    self.handle_damage_resolution()

                # =========== GAME OVER ===========
                elif state == "GAME_OVER":
                    print("\n[HOST] GAME OVER detected. Closing host session.")
                    break
                
            except Exception as e:
                print(f"[HOST] Error: {e}")

    # =====================================================
    # SETUP PHASE
    # =====================================================
    def handle_setup_phase(self):
        """Host chooses Pokémon + boosts then sends BATTLE_SETUP."""
        if "pokemon_name" in self.protocol_handler.match_data.get(
            self.protocol_handler.get_local_ip(), {}
        ):
            return  # Already chosen

        pokemon_db = load_pokemon_data()

        print("\n[HOST] === BATTLE SETUP ===")
        pokemon_name = choose_pokemon(pokemon_db)
        boosts = choose_stat_boosts()

        self.protocol_handler.start_battle_setup(pokemon_name, boosts)

    # =====================================================
    # ATTACK ANNOUNCEMENT (HOST TURN)
    # =====================================================
    def handle_my_turn(self):
        """Host chooses a move and sends ATTACK_ANNOUNCE."""
        print("\n=== YOUR TURN (HOST) ===")
        print("Available moves: Tackle, Quick Attack, Ember, Water Gun, Vine Whip")
        move = input("Choose move: ").strip()

        self.protocol_handler.send_attack_announce(move)

    # =====================================================
    # DEFENSE PHASE
    # =====================================================
    def handle_defense_phase(self):
        """Respond with DEFENSE_ANNOUNCE when attacker is opponent."""
        if (
            self.protocol_handler.last_attack_announce
            and not self.protocol_handler.last_defense_announce
        ):
            attacker_ip = self.protocol_handler.last_attack_announce["attacker_ip"]
            if attacker_ip == self.protocol_handler.get_opponent_ip():
                move = self.protocol_handler.last_attack_announce["move_name"]
                print(f"\n[HOST] Opponent used {move}!")
                input("Press ENTER to defend...")
                self.protocol_handler.send_defense_announce()

    # =====================================================
    # DAMAGE + CALCULATION REPORT
    # =====================================================
    def handle_damage_resolution(self):
        """Run deterministic damage and send CALCULATION_REPORT."""
        attack = self.protocol_handler.last_attack_announce
        if not attack:
            return

        attacker_ip = attack["attacker_ip"]
        move_name = attack["move_name"]

        # Determine defender IP
        defender_ip = (
            self.protocol_handler.get_joiner_ip()
            if attacker_ip == self.protocol_handler.get_host_ip()
            else self.protocol_handler.get_host_ip()
        )

        # Actual damage calculation (RFC deterministic)
        dmg = battleLogic.calculate_damage(
            self.protocol_handler.get_match_data(),
            attacker_ip=attacker_ip,
            defender_ip=defender_ip,
            move_name=move_name,
        )

        old_hp = self.protocol_handler.get_hp(defender_ip)
        new_hp = max(0, old_hp - dmg)
        self.protocol_handler.set_hp(defender_ip, new_hp)

        status = f"{move_name} dealt {dmg} damage! {defender_ip} HP is now {new_hp}"

        # Send calculation report to joiner
        self.protocol_handler.send_calculation_report(
            attacker=self.protocol_handler.match_data[attacker_ip]["pokemon_name"],
            move_used=move_name,
            remaining_health=old_hp,
            damage_dealt=dmg,
            defender_hp_remaining=new_hp,
            status_message=status,
        )

        # If defender died => send GAME_OVER
        if new_hp <= 0:
            self.protocol_handler.send_game_over(
                winner=self.protocol_handler.match_data[attacker_ip]["pokemon_name"],
                loser=self.protocol_handler.match_data[defender_ip]["pokemon_name"],
            )

    # =====================================================
    # NETWORK HANDLERS
    # =====================================================

    def handle_new_connection(self, message_text: str, address: tuple):
        print(f"[Host] Received data from new address {address}")

        message_dict = self.protocol_handler._parse_message(message_text)
        msg_type = message_dict.get('message_type')

        if msg_type == messages.MessageType.HANDSHAKE_REQUEST.value:
            self.handle_player_join(address)

        elif msg_type == messages.MessageType.SPECTATOR_REQUEST.value:
            self.handle_spectator_join(address)

        else:
            print(f"[Host] Ignoring unknown message type from {address}")

    def handle_player_join(self, address):
        if self.player_opponent_addr is not None:
            print(f"[Host] Player join attempt from {address} denied (game full).")
            return

        print(f"[HOST] Player (P2) connected from {address}.")
        self.player_opponent_addr = address

        seed = random.randint(1, 99999)
        match_data = {'seed': seed}

        response_msg = messages.HandshakeResponseMessage(seed=seed)
        self.net_client.send_to(response_msg.as_text(), self.player_opponent_addr)
        print("[HOST] Player handshake complete.")

        self.protocol_handler.set_opponent(self.player_opponent_addr, match_data, is_host=True)

    def handle_spectator_join(self, address):
        print(f"\n[HOST] Spectator connected from {address}.")
        if address not in self.spectator_addrs:
            self.spectator_addrs.append(address)
            print(f"[HOST] Spectator added. Total: {len(self.spectator_addrs)}")

        seed = self.protocol_handler.match_data.get('seed', 0)
        response_msg = messages.HandshakeResponseMessage(seed=seed)
        self.net_client.send_to(response_msg.as_text(), address)
        print("[HOST] Spectator handshake complete.")

    def handle_player_message(self, message_text: str):
        print(f"[HOST] Received from P2:\n{message_text}")
        self.protocol_handler.process_message(message_text, self.player_opponent_addr)
        self.broadcast_to_spectators(message_text)

    def handle_spectator_message(self, message_text: str):
        print(f"[HOST] Received from Spectator:\n{message_text}")
        message_dict = self.protocol_handler._parse_message(message_text)

        if message_dict.get('message_type') == messages.MessageType.CHAT_MESSAGE.value:
            self.broadcast_to_all(message_text, exclude_sender=message_dict.get('sender_name'))

    def broadcast_to_spectators(self, message_text: str):
        for addr in self.spectator_addrs:
            self.net_client.send_to(message_text, addr)

    def broadcast_to_all(self, message_text: str, exclude_sender=None):
        peers = [self.player_opponent_addr] + self.spectator_addrs
        for addr in peers:
            if addr and addr != exclude_sender:
                self.net_client.send_to(message_text, addr)
