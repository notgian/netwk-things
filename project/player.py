import messages as m
from client import Client
from config import HANDSHAKE_TIMEOUT
from protocol import GameProtocolHandler
from threading import Thread
from ast import literal_eval

class Player:
    def __init__(self, host_ip, host_port, local_port):
        self.net_client = Client()
        self.protocol_handler = GameProtocolHandler(self.net_client)
        self.host_addr = (host_ip, host_port)

        self.states = []

        self.is_listening = False
        self.listener_thread = Thread(target=self.__listen_loop__())

        # initialize client by binding the socket
        if not self.net_client.bind_socket('', local_port):
            exit()
        print(f"Player client initialized. Will connect to {host_ip}:{host_port}")

    # Network protocol related things
    def connect_to_host(self):
        """ Connects to the host client by sending a HANDSHAKE_REQUEST message.
            Also waits for a corresponding HANDSHAKE_RESPONSE message and
            begins the initialization of the game.

            returns a boolean representing whether the connection was 
            successful or not.
        """
        request_msg = m.HandshakeRequestMessage()

        try:
            print("[PLAYER] Connecting to HOST...")
            self.net_client.send_to(request_msg.as_text(), self.host_addr)

            message, address = self.net_client.receive_from(timeout=HANDSHAKE_TIMEOUT)

            if not message:
                print("[PLAYER] Connection timed out. Host not found")
                return False
            if address != self.host_addr:
                print(f"[PLAYER] Received response from unexpected address {address}. Ignoring.")
                return False

            message_dict = self.protocol_handler._parse_message(message)

            # Handle handshake response here
            if message_dict.get('message_type') == m.MessageType.HANDSHAKE_RESPONSE.value:
                print("[PLAYER] Handshake successful!.")

                seed = int(message_dict.get('seed', 0))
                match_data = {'seed': seed}
                print(f"[PLAYER] Received seed: {seed}")

                self.protocol_handler.set_opponent(self.host_addr, match_data, is_host=False)
                # begin listening to prepare for battle setup
                self.start_listening()
                return True

            else:
                print(f"[PLAYER] Received unexpected message response {message}.")
                return False

        except Exception as e:
            print(f"[PLAYER] Error during connection: {e}")
            return False

    def battle_setup_send(self,
                          mode: m.CommunicationMode,
                          pokemon: str,
                          stat_boosts: dict):
        """ Sends a battle setup message an initializes the battle mode """

        setup_msg = m.BattleSetupMessage(mode, pokemon, stat_boosts)
        self.net_client.send_to(setup_msg, self.host_addr)

        # TODO: call method in game protocol handler to update the match data
        #       to add the data of this player to the match data

        # self.protocol_handler.match_data["insert_joiner_ip"] = {
        #     "pokemon_name" : pokemon,
        #     "stat_boosts" : stat_boosts,
        #     "data" :  # insert pokemon data here. Get from game protocol handler
        # }

        self.states.append("PLAYER_READY")
        if "HOST_READY" in self.states:
            self.battle_start()
        else:
            print("Player is ready! Waiting for host to start the battle.")
            # NOTE: "Start the battle" just means for the other user to send
            #       their own battle setup message

    def battle_setup_receive(self,
                             msg_dict: dict):
        """ Called from the listening loop to initialize the data of
        the opponent
        """

        # parse the string val of stat_boosts as dict
        msg_dict["stat_boosts"] = literal_eval(msg_dict.get("stat_boosts"))

        # TODO: call method in game protocol handler to update the match data
        #       to add the data of this player to the match data

        # self.protocol_handler.match_data["insert_host_ip"] = {
        #         "pokemon_name" : msg_dict.get("pokemon_name"),
        #         "stat_boosts" : msg_dict.get("stat_boosts"),
        #         "data":  # insert pokemon data here. Get from game protocol handler
        # }

        self.states.append("HOST_READY")
        if "PLAYER_READY" in self.states:
            self.battle_start()
        else:
            print("Host is ready! Waiting for you to start the battle.")
            # NOTE: "Start the battle" just means for the other user to send
            #       their own battle setup message

    def start_battle(self):
        self.states = ["DEFENDING", "WAITING_FOR_TURN"]
        print("[PLAYER] Battle has begun. Waiting for opponent to move.")
        # no other setup needed. Now wait for messages

    def defend_attack(self, ability: str):
        # TODO: replace the placeholder sequence number here
        def_msg = m.DefenseAnnounceMessage(1)
        self.net_client.send_to(def_msg.as_text(), self.host_addr)

        # do the calculations here

        # send the calculation report
        calc_report_msg = m.CalculationReportMessage(attacker=None,
                                                     move_used=None,
                                                     remaining_health=None,
                                                     damage_dealt=None,
                                                     defender_hp_remaining=None,
                                                     status_message=None,
                                                     sequence_number=1)

        self.net_client.send_to(calc_report_msg.as_text(), self.host_addr)


    def start_listening(self):
        """ Starts a thread that loops, listening for  This is called
            after the handshake to allow for listening for all messages
            afterwhich. Also allows for seemingly synchronous (not really)
            handling of chat messages and game events.
        """
        if self.is_listening:
            print("[PLAYER] Already listening!")
            return

        self.listener_thread.start()
        self.is_listening = True

    def stop_listening(self):
        """ Stops the thread that is listening for messages """

        if not self.is_listening:
            print("[PLAYER] Already NOT listening!")
            return

        self.is_alive = False

    def __listen_loop__(self):
        """ Not to be called. Is only used as the method passed into the
        thread """
        while self.is_alive:
            message_text, address = self.net_client.receive_from()

            if message_text and address != self.host_addr:
                print(f"Received message from unknown sender {address}. Ignoring.")
                continue

            msg_dict = self.protocol_handler._parse_message(message_text)
            mtype = msg_dict.get("message_type")
            # switch here to handle what to do with the message
            match mtype:
                case m.MessageType.BATTLE_SETUP.value:
                    self.battle_setup_receive(msg_dict)
                case m.MessageType.ATTACK_ANNOUNCE:
                    self.defend_attack(msg_dict.get("move_name"))

            # self.protocol_handler.process_message(message_text, address)

