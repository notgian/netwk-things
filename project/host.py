import random
from client import Client
import messages
from protocol import GameProtocolHandler
from pokemon import load_pokemon_data
import battleLogic
from threading import Thread
import config

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
    def joiner_listen(self, as_spectator=False):
        connected = False
        while not connected:
            message_text, address = self.net_client.receive_from()

            # No message
            if not message_text:
                continue

            message_dict = self.protocol_handler._parse_message(message_text)
            msg_type = message_dict.get('message_type')

            if msg_type == messages.MessageType.HANDSHAKE_REQUEST.value:
                self.handle_player_join(address)
                self.__start_listening__()
                connected=True

            else:
                print(f"[Host] Ignoring unknown message type from {address}")

    # =====================================================
    # MAIN HOST LOOP
    # =====================================================
    def run_host_loop(self):
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
                    while protocol.game_state == "WAITING_FOR_MOVE":
                        pass
                else:
                    self.handle_defense_phase()

            elif protocol.game_state == "PROCESSING_TURN":
                self.handle_damage_resolution()
                while protocol.game_state == "PROCESSING_TURN":
                    pass  # wait until game exists setup stage

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
        pokemon_name = battleLogic.choose_pokemon(pokemon_db)
        boosts = battleLogic.choose_stat_boosts()
        comm_mode = battleLogic.choose_communication_mode()

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
            if message_text and address == self.player_opponent_addr:
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

    # =====================================================
    # NETWORK HANDLERS
    # =====================================================

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

