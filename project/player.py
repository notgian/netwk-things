from client import Client
import messages
import config
from protocol import GameProtocolHandler
from pokemon import load_pokemon_data
from pokemon import print_pokemon_paginated
import battleLogic


# ---------------------------------------------------------
# Helper functions (same as Host)
# ---------------------------------------------------------

def choose_pokemon(pokemon_db):
    """Simple CLI Pokémon selection menu."""
    names = list(pokemon_db.keys())
    print("\n=== PLAYER: Choose Your Pokémon ===")
    print_pokemon_paginated(list(pokemon_db.keys()))

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
    print("\n=== PLAYER: Stat Boost Allocation ===")
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
# PLAYER CLASS
# ---------------------------------------------------------

class Player:
    def __init__(self, host_ip, host_port, local_port=0):
        self.net_client = Client()
        if not self.net_client.bind_socket('', local_port):
            exit()

        self.host_addr = (host_ip, host_port)
        self.is_spectator = False

        self.protocol_handler = GameProtocolHandler(self.net_client)
        print(f"[PLAYER] Client initialized. Will connect to {host_ip}:{host_port}")

    # -----------------------------------------------------
    # CONNECTION HANDSHAKE
    # -----------------------------------------------------
    def connect(self, as_spectator=False):
        self.is_spectator = as_spectator

        if as_spectator:
            request_msg = messages.SpectatorRequestMessage()
            log_prefix = "[SPECTATOR]"
        else:
            request_msg = messages.HandshakeRequestMessage()
            log_prefix = "[PLAYER]"

        try:
            print(f"\n{log_prefix} Connecting to HOST...")
            self.net_client.send_to(request_msg.as_text(), self.host_addr)

            timeout = config.HANDSHAKE_TIMEOUT
            message_text, address = self.net_client.receive_from(timeout=timeout)

            if not message_text:
                print(f"\n{log_prefix} Connection timed out. Host not found.")
                return False

            if address != self.host_addr:
                print(f"\n{log_prefix} Received response from unexpected address {address}. Ignoring.")
                return False

            message_dict = self.protocol_handler._parse_message(message_text)
            if message_dict.get('message_type') == messages.MessageType.HANDSHAKE_RESPONSE.value:
                print(f"{log_prefix} Handshake successful!")

                seed = int(message_dict.get('seed', 0))
                match_data = {'seed': seed}
                print(f"{log_prefix} Received seed: {seed}")

                self.protocol_handler.set_opponent(self.host_addr, match_data, is_host=False)
                return True

            else:
                print(f"{log_prefix} Received unexpected message response: {message_text}.")
                return False
        except Exception as e:
            print(f"\n{log_prefix} Error during connection: {e}")
            return False

    # -----------------------------------------------------
    # MAIN GAME LOOP DISPATCHER
    # -----------------------------------------------------
    def run_game_loop(self):
        if self.is_spectator:
            self.run_spectator_loop()
        else:
            self.run_player_loop()

    # -----------------------------------------------------
    # FULL PLAYER LOOP (BATTLE LOGIC)
    # -----------------------------------------------------
    def run_player_loop(self):
        print("\n[PLAYER] Waiting for Host messages...")

        while True:
            # 1) Poll for network with small timeout
            message_text, address = self.net_client.receive_from(timeout=0.1)

            # 2) Handle incoming messages
            if message_text and address == self.host_addr:
                self.protocol_handler.process_message(message_text, address)
            elif message_text:
                print(f"[PLAYER] Received message from unknown sender {address}. Ignoring.")

            # 3) Drive game state / logic
            self._drive_game_state()

    def _drive_game_state(self):
        p = self.protocol_handler

        # --------- SETUP PHASE ----------
        if p.game_state == "SETUP":
            self.handle_setup_phase()

        # --------- ATTACK PHASE (JOINER'S TURN) ----------
        if p.game_state == "WAITING_FOR_MOVE" and p.is_my_turn():
            self.handle_my_turn()

        # --------- DEFENSE PHASE ----------
        if p.game_state in ("WAITING_FOR_MOVE", "PROCESSING_TURN"):
            self.handle_defense_phase()

        # --------- DAMAGE CALCULATION ----------
        if p.game_state == "PROCESSING_TURN":
            self.handle_damage_resolution()

        # --------- GAME OVER ----------
        if p.game_state == "GAME_OVER":
            print("\n=== GAME OVER ===")
            self.net_client.close()
            raise SystemExit()

    # -----------------------------------------------------
    # SETUP PHASE
    # -----------------------------------------------------
    def handle_setup_phase(self):
        p = self.protocol_handler
        my_ip = p.get_local_ip()

        # Already selected? Don't spam prompt.
        if my_ip in p.match_data and "pokemon_name" in p.match_data[my_ip]:
            return

        pokemon_db = load_pokemon_data()

        print("\n[PLAYER] === BATTLE SETUP ===")
        pokemon_name = choose_pokemon(pokemon_db)
        boosts = choose_stat_boosts()

        p.start_battle_setup(pokemon_name, boosts)

    # -----------------------------------------------------
    # ATTACK PHASE
    # -----------------------------------------------------
    def handle_my_turn(self):
        p = self.protocol_handler

        # Already announced attack this turn?
        if (
            p.last_attack_announce
            and p.last_attack_announce.get("attacker_ip") == p.get_local_ip()
        ):
            return

        print("\n=== YOUR TURN (PLAYER) ===")
        print("Available moves: Tackle, Quick Attack, Ember, Water Gun, Vine Whip")
        move = input("Choose move (or type 'pass' to cancel): ").strip()

        if move.lower() == "pass" or not move:
            print("[PLAYER] Turn skipped (no attack announced).")
            return

        p.send_attack_announce(move)

    # -----------------------------------------------------
    # DEFENSE PHASE
    # -----------------------------------------------------
    def handle_defense_phase(self):
        p = self.protocol_handler

        if (
            p.last_attack_announce
            and not p.last_defense_announce
        ):
            attacker_ip = p.last_attack_announce["attacker_ip"]
            if attacker_ip == p.get_opponent_ip():
                move = p.last_attack_announce["move_name"]
                print(f"\n[PLAYER] Opponent used {move}!")
                input("Press ENTER to defend...")
                p.send_defense_announce()

    # -----------------------------------------------------
    # DAMAGE CALCULATION & REPORTING
    # -----------------------------------------------------
    def handle_damage_resolution(self):
        p = self.protocol_handler

        # Already reported this turn?
        if p.last_local_calculation is not None:
            return

        attack = p.last_attack_announce
        if not (attack and p.last_defense_announce):
            return

        attacker_ip = attack["attacker_ip"]
        move_name = attack["move_name"]

        # Determine defender IP
        defender_ip = (
            p.get_joiner_ip()
            if attacker_ip == p.get_host_ip()
            else p.get_host_ip()
        )

        # Calculate RFC deterministic damage
        dmg = battleLogic.calculate_damage(
            p.get_match_data(),
            attacker_ip=attacker_ip,
            defender_ip=defender_ip,
            move_name=move_name,
        )

        old_hp = p.get_hp(defender_ip)
        new_hp = max(0, old_hp - dmg)
        p.set_hp(defender_ip, new_hp)

        atk_name = p.match_data[attacker_ip]["pokemon_name"]
        def_name = p.match_data[defender_ip]["pokemon_name"]
        status = f"{atk_name}'s {move_name} dealt {dmg} damage to {def_name}! HP: {old_hp} → {new_hp}"

        print(f"\n[PLAYER] {status}")

        # Send calculation report
        p.send_calculation_report(
            attacker=atk_name,
            move_used=move_name,
            remaining_health=old_hp,
            damage_dealt=dmg,
            defender_hp_remaining=new_hp,
            status_message=status,
        )

        # If KO ⇒ send GAME_OVER
        if new_hp <= 0:
            p.send_game_over(
                winner=atk_name,
                loser=def_name,
            )

    # -----------------------------------------------------
    # SPECTATOR MODE
    # -----------------------------------------------------
    def run_spectator_loop(self):
        print("\n--- Joined as Spectator. Now listening for battle messages... ---")
        while True:
            message_text, address = self.net_client.receive_from(timeout=0.5)
            if message_text and address == self.host_addr:
                print(f"\n[SPECTATOR VIEW (from Host)]:\n{message_text}")
            elif message_text:
                print(f"[SPECTATOR] Received message from unknown sender {address}. Ignoring.")
