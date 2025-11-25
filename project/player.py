import messages as m
from client import Client
from config import HANDSHAKE_TIMEOUT
from protocol import GameProtocolHandler
from threading import Thread
from ast import literal_eval

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


# ---------------------------------------------------------
# PLAYER CLASS
# ---------------------------------------------------------

class Player:
    def __init__(self, host_ip, host_port, local_port):
        self.net_client = Client()
        self.protocol = None
        self.host_addr = (host_ip, host_port)

        self.is_listening = False
        self.listener_thread = Thread(target=self.__listen_loop__)
        self.is_taking_input = False
        self.input_thread = Thread(target=self.__user_input__)

        # a buffer to hold the last input. Can be used by the game loop
        self.input_buff = ""

        # initialize client by binding the socket
        if not self.net_client.bind_socket('', local_port):
            exit()
        print(f"Player client initialized. Will connect to {host_ip}:{host_port}")

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

            self.protocol = GameProtocolHandler(self.net_client)
            message_dict = self.protocol._parse_message(message)

            # Handle handshake response here
            if message_dict.get('message_type') == m.MessageType.HANDSHAKE_RESPONSE.value:
                print("[PLAYER] Handshake successful!.")

                seed = int(message_dict.get('seed', 0))
                match_data = {'seed': seed}
                print(f"[PLAYER] Received seed: {seed}")

                self.protocol.set_opponent(self.host_addr, match_data, is_host=False)
                # begin listening to prepare for battle setup
                self.__start_listening__()
                self.start_battle_setup()
                return True

            else:
                print(f"[PLAYER] Received unexpected message response {message}.")
                return False

        except Exception as e:
            print(f"[PLAYER] Error during connection: {e}")
            return False

    # start battle setup
    def start_battle_setup(self):
        """ Called after establishing a connection to start setting up the
            battle. Asks user for the name of the pokemon and the preferred
            communication mode. After setup, it starts the game loop.
        """
        # get pokemon data
        self.protocol._get_pokemon_db()
        pokemon_db = self.protocol._pokemon_db
        # ask for pokemon from user
        selected_pokemon = None
        while selected_pokemon is None:
            # Use title case: capitalized first letter of pokemon name
            select_temp = input("Enter the name of your pokemon...").title()
            if select_temp in pokemon_db.keys():
                selected_pokemon = select_temp
                continue
            print("Invalid Pokemon name... please try again.")

        selected_mode = None
        while selected_mode is None:
            print("Please select your preferred mode of communication: ")
            print("[1] P2P Mode")
            print("[2] Broadcast Mode")
            select_temp = input().strip()
            if (select_temp == "1"):
                selected_mode = m.CommunicationMode.P2P
            elif (select_temp == "2"):
                selected_mode = m.CommunicationMode.BROADCAST

        stat_boosts = {
            "special_attack_uses": 5,
            "special_defense_uses": 5
        }

        self.protocol.start_battle_setup(pokemon_name=selected_pokemon,
                                         stat_boosts=stat_boosts,
                                         communication_mode=selected_mode)

        # game loop is called here.
        # the game loop becomes self-contained and will be responsible
        self.start_game_loop()

    # game loop
    def start_game_loop(self):
        """ Starts the main game loop. Assumes the battle setup
            was run immediately before, making it so the game state
            is at WAITING_FOR_MOVE from the start """

        # input will be taken from the input buffer
        self.__start_taking_input__()

        # Termination condition: protocol is set to none
        while self.protocol is not None:
            # Game state at this point: WAITING_FOR_MOVE

            # Player is attacking
            if self.protocol.current_turn_ip == self.protocol_handler.local_ip:
                print("[PLAYER] It's your turn to attack!")
                print("Enter name of move: ")
                while self.input_buff == "":
                    pass  # Do nothing until we get an input
                move_name = self.input_buff
                self.input_buff = ""

                self.protocol.send_attack_announce(move_name=move_name)

            # Player is defending
            else:
                print("Waiting for opponent to attack...")
                # I set the defense announce to just be sent right after
                # handling an attack announce. AKA immediately send
                # DEFENSE_ANNOUCE after getting attacked.

            # Wait before proceeding to next part
            while self.protocol.game_state == "WAITING_FOR_MOVE":
                pass

            # Game state at this point: PROCESSING TURN

            # Perform calculations


            # Send calculations
            self.protocol.send_calculation_report()


            # check if attacker or defender
            #   if attacker: send an attack
            #   elif defender: wait for attack

            # after attacking/defending
            #   perform calculations
            #   send calculation report
            #   receive calculation report
            #   if discrepacny:
            pass

    def __start_listening__(self):
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

    def __stop_listening__(self):
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

            self.protocol.process_message(message_text, address)

    def __user_input__(self):
        while self.is_taking_input:
            inp = input()
            # process input here

    def __start_taking_input__(self):
        if self.is_taking_input:
            print("[PLAYER] Already taking input!")
            return

        self.input_thread.start()
        self.is_taking_input = True

    def __stop_taking_input__(self):
        if not self.is_taking_input:
            print("[PLAYER] Already not taking input!")
            return

        self.is_taking_input = False