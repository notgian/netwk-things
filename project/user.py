from client import Client
from protocol import GameProtocolHandler
from async_input import AsyncInput
from threading import Thread
from pokemon import load_pokemon_data

import battleLogic
import messages
import os


class User:
    def __init__(self, local_ip, local_port, remote_addr=None, remote_port=None):
        self.net_client = Client()
        if not self.net_client.bind_socket(local_ip, local_port):
            exit()

        self.protocol_handler = GameProtocolHandler(self.net_client, (local_ip, local_port), is_host=True)

        self.is_listening = False
        self.listener_thread = Thread(target=self.__listener__, daemon=True)

        self.asyncInput = AsyncInput(self.__process_command__)

        self.game_running = False

        if remote_addr == remote_port and remote_addr is None:
            self.host_addr = (local_ip, local_port)
            self.is_host = True
        else:
            self.host_addr = (remote_addr, remote_port)
            self.is_host = False

    def run_game_loop(self):
        protocol = self.protocol_handler

        self.game_running = True
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
                print("\n=== GAME END ===")

            elif protocol.game_state in ["TERMINATED"]:
                self.game_running = False
                self.__stop_listening__()
                self.asyncInput.stop()
                print("Press enter to continue...")


    def handle_setup_phase(self):
        protocol = self.protocol_handler
        my_addr = protocol.get_local_addr()

        # Already selected?
        if my_addr in protocol.match_data and "pokemon_name" in protocol.match_data[my_addr]:
            protocol._check_battle_setup_complete()
            return

        pokemon_db = load_pokemon_data()

        print("\n[PLAYER] === BATTLE SETUP ===")
        pokemon_name = battleLogic.choose_pokemon(pokemon_db, self.asyncInput.awaitInput)
        boosts = battleLogic.choose_stat_boosts(self.asyncInput.awaitInput)
        comm_mode = battleLogic.choose_communication_mode(self.asyncInput.awaitInput)

        protocol.start_battle_setup(pokemon_name, boosts, comm_mode)

    # -----------------------------------------------------
    # ATTACK PHASE
    # -----------------------------------------------------
    def handle_my_turn(self):
        protocol = self.protocol_handler
        print("\n=== YOUR TURN (PLAYER) ===")
        print("Available moves: Tackle, Quick Attack, Ember, Water Gun, Vine Whip")
        move = self.asyncInput.awaitInput("Choose move: ").strip()

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
            attacker_addr = protocol.last_attack_announce["attacker_address"]
            print(attacker_addr)
            if attacker_addr == protocol.fmt_address(protocol.get_opponent_addr()):
                move = protocol.last_attack_announce["move_name"]
                print(f"\n[PLAYER] Opponent used {move}!")
                protocol.send_defense_announce()
                print("SENT!")

    # -----------------------------------------------------
    # DAMAGE CALCULATION & REPORTING
    # -----------------------------------------------------
    def handle_damage_resolution(self):
        protocol = self.protocol_handler
        attack = protocol.last_attack_announce

        if not attack:
            return

        attacker_addr = attack["attacker_address"]
        move_name = attack["move_name"]

        # Determine defender IP
        defender_addr = protocol.fmt_address(
            protocol.get_joiner_addr()
            if attacker_addr == protocol.fmt_address(protocol.get_host_addr())
            else protocol.get_host_addr()
        )

        print(attacker_addr, defender_addr)

        # Calculate RFC deterministic damage
        dmg = battleLogic.calculate_damage(
            protocol.get_match_data(),
            attacker_addr=attacker_addr,
            defender_addr=defender_addr,
            move_name=move_name,
        )

        old_hp = protocol.get_hp(defender_addr)
        print(dmg, old_hp)
        new_hp = max(0, old_hp - dmg)
        protocol.set_hp(defender_addr, new_hp)

        status = f"{move_name} dealt {dmg} damage! {defender_addr} HP is now {new_hp}"

        # Send calculation report
        protocol.send_calculation_report(
            attacker=protocol.match_data[attacker_addr]["pokemon_name"],
            move_used=move_name,
            remaining_health=old_hp,
            damage_dealt=dmg,
            defender_hp_remaining=new_hp,
            status_message=status,
        )

        # If KO ⇒ send GAME_OVER
        if new_hp <= 0:
            protocol.send_game_over(
                winner=protocol.match_data[attacker_addr]["pokemon_name"],
                loser=protocol.match_data[defender_addr]["pokemon_name"],
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
            peers = self.protocol_handler.spectator_addrs + [self.protocol_handler.opponent_addr]
            if message_text and address in peers:
                self.protocol_handler.process_message(message_text, address)
            elif message_text:
                print(f"Received message from unknown sender {address}. Ignoring.")

    def __process_command__(self, text: str):
        """ Processes the text, attepting to detect the command prefix (/)
            and executing the necessary user action based on this
        """
        # Cannot process empty strings
        if len(text) == 0:
            return False

        # Only process stuff with the prefix (/)
        text = text.strip()
        prefix = text[0]
        tokenized_text = text.split(" ")
        if prefix != "/":
            return False

        # Chat message that sends text
        # syntax: /message all message text follows here
        sender = f"{self.protocol_handler.local_addr}:{self.protocol_handler.local_addr}"

        if tokenized_text[0][1:] == "message":
            message = text[len("/message "):]
            self.protocol_handler.send_chat_message(sender_name=sender,
                                                    content_type=messages.ChatMessageType.TEXT, 
                                                    content=message)

        # Chat message that sends a sticker
        # syntax: /sticker sticker_filename
        elif tokenized_text[0][1:] == "sticker":
            filename = tokenized_text[1]

            sticker_path_exists = os.path.isdir("stickers")
            if not sticker_path_exists:
                os.mkdir("stickers")
                print("[COMMAND] There are no stickers in the directory... please try again.")
                return True

            sticker_exists = os.path.isfile(f"stickers/{filename}")
            if not sticker_exists:
                print(f"[COMMAND] No stickers named f{filename} found... please try again.")
                return True

        else:
            print(f"[COMMAND] Unknown command {tokenized_text[0]} was run.")

        return True