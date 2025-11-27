from client import Client
import messages
import config
from protocol import GameProtocolHandler
from pokemon import load_pokemon_data
import battleLogic
from threading import Thread


# ---------------------------------------------------------
# Helper functions (same as Host)
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

def choose_communication_mode():
    print("\n=== Communication Mode===")
    while True:
        print("Select communication mode")
        print("1. P2P Mode")
        print("2. Broadcast Mode")

        inp = input()
        if (inp == "1"):
            return messages.CommunicationMode.P2P
        elif (inp == "2"):
            return messages.CommunicationMode.BROADCAST
        else:
            print("Please try again...")

# ---------------------------------------------------------
# PLAYER CLASS
# ---------------------------------------------------------

class Player:
    def __init__(self, host_ip, host_port, local_ip, local_port=0):
        self.net_client = Client()
        if not self.net_client.bind_socket(local_ip, local_port):
            exit()

        self.host_addr = (host_ip, host_port)

        self.is_listening = False
        self.listener_thread = Thread(target=self.__listener__)

        # input buffers
        # 0 - default input buffer
        # 1 - for most input methods
        # 2 - for chat related functions
        self.input_buff = ["", "", ""]

        self.taking_input = False
        self.input_thread = Thread(target=self.__take_input__)

        self.protocol_handler = GameProtocolHandler(self.net_client)

        self.game_running = True

    # -----------------------------------------------------
    # CONNECTION HANDSHAKE
    # -----------------------------------------------------
    def connect(self):
        request_msg = messages.HandshakeRequestMessage()

        try:
            print(f"\n[PLAYER] Connecting to HOST...")
            self.net_client.send_to(request_msg.as_text(), self.host_addr)

            timeout = config.HANDSHAKE_TIMEOUT
            message_text, address = self.net_client.receive_from(timeout=timeout)

            if not message_text:
                print(f"\n[PLAYER] Connection timed out. Host not found")
                return False

            if address != self.host_addr:
                print(f"\n[PLAYER] Received response from unexpected address {address}. Ignoring.")
                return False

            message_dict = self.protocol_handler._parse_message(message_text)
            if message_dict.get('message_type') == messages.MessageType.HANDSHAKE_RESPONSE.value:
                print(f"[PLAYER] Handshake successful!.")

                seed = int(message_dict.get('seed', 0))
                match_data = {'seed': seed}
                print(f"Received seed: {seed}")

                self.protocol_handler.set_opponent(self.host_addr, match_data, is_host=False)
                self.__start_listening__()
                return True

            else:
                print(f"[PLAYER] Received unexpected message response {message_text}.")
                return False
        except Exception as e:
            print(f"\n[PLAYER] Error during connection: {e}")
            return False

    # The main game loop for the player
    def run_game_loop(self):
        protocol = self.protocol_handler

        while self.game_running:

            # SETUP PHASE
            if protocol.game_state == "SETUP":
                self.handle_setup_phase()
                while protocol.game_state == "SETUP":
                    pass  # wait until game exists setup stage

            # WAITING_FOR_MOVE PHASE
            elif protocol.game_state == "WAITING_FOR_MOVE":
                if protocol.is_my_turn():
                    self.handle_my_turn()
                else:
                    self.handle_defense_phase()

            elif protocol.game_state == "PROCESSING_TURN":
                self.handle_damage_resolution()

            elif protocol.game_state == "GAME_OVER":
                print("\n=== GAME OVER ===")
                break

    # -----------------------------------------------------
    # SETUP PHASE
    # -----------------------------------------------------
    def handle_setup_phase(self):
        protocol = self.protocol_handler
        my_ip = protocol.get_local_ip()

        # Already selected?
        if my_ip in protocol.match_data and "pokemon_name" in protocol.match_data[my_ip]:
            protocol._check_battle_setup_complete()
            return

        pokemon_db = load_pokemon_data()

        print("\n[PLAYER] === BATTLE SETUP ===")
        pokemon_name = choose_pokemon(pokemon_db)
        boosts = choose_stat_boosts()
        comm_mode = choose_communication_mode()

        protocol.start_battle_setup(pokemon_name, boosts, comm_mode)

    # -----------------------------------------------------
    # ATTACK PHASE
    # -----------------------------------------------------
    def handle_my_turn(self):
        protocol = self.protocol_handler
        print("\n=== YOUR TURN (PLAYER) ===")
        print("Available moves: Tackle, Quick Attack, Ember, Water Gun, Vine Whip")
        move = input("Choose move: ").strip()

        protocol.send_attack_announce(move)

    # -----------------------------------------------------
    # DEFENSE PHASE
    # -----------------------------------------------------
    def handle_defense_phase(self):
        protocol = self.protocol_handler

        if (
                protocol.last_attack_announce
                and not protocol.last_defense_announce
        ):
            attacker_ip = protocol.last_attack_announce["attacker_ip"]
            if attacker_ip == protocol.get_opponent_ip():
                move = protocol.last_attack_announce["move_name"]
                print(f"\n[PLAYER] Opponent used {move}!")
                protocol.send_defense_announce()

    # -----------------------------------------------------
    # DAMAGE CALCULATION & REPORTING
    # -----------------------------------------------------
    def handle_damage_resolution(self):
        protocol = self.protocol_handler
        attack = protocol.last_attack_announce

        if not attack:
            return

        attacker_ip = attack["attacker_ip"]
        move_name = attack["move_name"]

        # Determine defender IP
        defender_ip = (
            protocol.get_joiner_ip()
            if attacker_ip == protocol.get_host_ip()
            else protocol.get_host_ip()
        )

        # Calculate RFC deterministic damage
        dmg = battleLogic.calculate_damage(
            protocol.get_match_data(),
            attacker_ip=attacker_ip,
            defender_ip=defender_ip,
            move_name=move_name,
        )

        old_hp = protocol.get_hp(defender_ip)
        new_hp = max(0, old_hp - dmg)
        protocol.set_hp(defender_ip, new_hp)

        status = f"{move_name} dealt {dmg} damage! {defender_ip} HP is now {new_hp}"

        # Send calculation report
        protocol.send_calculation_report(
            attacker=protocol.match_data[attacker_ip]["pokemon_name"],
            move_used=move_name,
            remaining_health=old_hp,
            damage_dealt=dmg,
            defender_hp_remaining=new_hp,
            status_message=status,
        )

        # If KO ⇒ send GAME_OVER
        if new_hp <= 0:
            protocol.send_game_over(
                winner=protocol.match_data[attacker_ip]["pokemon_name"],
                loser=protocol.match_data[defender_ip]["pokemon_name"],
            )

    def __start_listening__(self):
        """ Starts the listener thread that listens for messages """
        if self.is_listening:
            print("[WARN] Already listening...")
            return

        self.is_listening = True
        self.listener_thread.start()

    def __stop_listening__(self):
        """ Stops the listener thread """
        if not self.is_listening:
            print("[WARN] Already not listening")
            return

        self.is_listening = False

    def __listener__(self):
        """ Listens for messages on a loop and puts them into a buffer"""

        while self.is_listening:
            message_text, address = self.net_client.receive_from()

            # Handle incoming message
            if message_text and address == self.host_addr:
                self.protocol_handler.process_message(message_text, address)
            elif message_text:
                print(f"Received message from unknown sender {address}. Ignoring.")

    def __start_taking_input__(self):
        if self.taking_input:
            print("[WARN] Already taking input")
            return

        self.taking_input = True
        self.input_thread.start()

    def __stop_taking_input__(self):
        if not self.taking_input:
            print("[WARN] Already not taking input")
            return

        self.taking_input = False

    def __take_input__(self):
        """ Takes user input and stores it into a buffer """

        while self.taking_input:
            inp = input()

            self.input_buff[0] = inp