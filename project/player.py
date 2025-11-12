from client import Client
import messages
import config
from protocol import GameProtocolHandler

class Player:
    def __init__(self, host_ip, host_port, local_port=0):
        self.net_client = Client()
        if not self.net_client.bind_socket('', local_port):
            exit()

        self.host_addr = (host_ip, host_port)
        self.is_spectator = False

        self.protocol_handler = GameProtocolHandler(self.net_client)
        print(f"Player client initialized. Will connect to {host_ip}:{host_port}")

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
                print(f"\n{log_prefix} Connection timed out. Host not found")
                return False

            if address != self.host_addr:
                print(f"\n{log_prefix} Received response from unexpected address {address}. Ignoring.")
                return False

            message_dict = self.protocol_handler._parse_message(message_text)
            if message_dict.get('message_type') == messages.MessageType.HANDSHAKE_RESPONSE:
                print(f"{log_prefix} Handshake successful!.")

                seed = int(message_dict.get('seed', 0))
                match_data = {'seed': seed}
                print(f"Received seed: {seed}")

                self.protocol_handler.set_opponent(self.host_addr, match_data, is_host=False)
                return True

            else:
                print(f"{log_prefix} Received unexpected message response {message_text}.")
                return False
        except Exception as e:
            print(f"\n{log_prefix} Error during connection: {e}")
            return False

    def run_game_loop(self):
        if self.is_spectator:
            self.run_spectator_loop()
        else:
            #elf.protocol_handler.start_battle_setup(pokemon_name="Charmander") # Example

            self.run_player_loop()

    def run_player_loop(self):
        print("Waiting for messages from Host...")
        while True:
            message_text, address = self.net_client.receive_from()

            if message_text and address == self.host_addr:
                self.protocol_handler.process_message(message_text, address)

            elif message_text:
                print(f"Received message from unknown sender {address}. Ignoring.")

    def run_spectator_loop(self):
        print("\n--- Joined as Spectator. Now listening for all battle messages... ---")
        while True:
            message_text, address = self.net_client.receive_from()
            if message_text and address == self.host_addr:
                print(f"\n[SPECTATOR VIEW (from Host)]:\n{message_text}")
            elif message_text:
                print(f"Received message from unknown sender {address}. Ignoring.")