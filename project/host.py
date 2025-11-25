import random
from client import Client
import messages
from protocol import GameProtocolHandler


class Host:
    """
    Manages the game as the Host (Player 1).
    Uses the Client to handle networking.
    Manages connections for one Player 2 and multiple Spectators.
    """
    def __init__(self, host_ip, port):
        self.net_client = Client()
        if not self.net_client.bind_socket(host_ip, port):
            exit()

        self.player_opponent_addr = None
        self.spectator_addrs = []

        self.protocol_handler = GameProtocolHandler(self.net_client)
        print(f"[HOST] Host Client running at {host_ip}:{port}")

    def run_host_loop(self):
        print("[Host] Waiting for connections...")
        while True:
            message_text, address = self.net_client.receive_from()

            if not message_text:
                continue

            elif address == self.player_opponent_addr:
                self.handle_player_message(message_text)
            elif address in self.spectator_addrs:
                self.handle_spectator_message(message_text)
            else:
                self.handle_new_connection(message_text, address)

    def handle_new_connection(self, message_text: str, address: tuple):
        print(f"[Host] Received data from new address {address}")

        # --- Use the protocol handler's parser ---
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

        #TODO Get pokemon name from user
        #self.protocol_handler.start_battle_setup(pokemon_name="Pikachu") #example

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
        print(f"[HOST] Received from P2: {message_text}")
        #self.protocol_handler.process_message(message_text, self.player_opponent_addr)

        self.broadcast_to_spectators(message_text)

    def handle_spectator_message(self, message_text: str):
        print(f"[HOST] Received from Spectator: {message_text}")

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
