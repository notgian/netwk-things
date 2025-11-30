import random
import messages
from user import User

# ---------------------------------------------------------
# HOST CLASS
# ---------------------------------------------------------

class Host(User):
    """
    Manages the game as the Host (Player 1).
    Uses the Client to handle networking.
    Manages connections for one Player 2 and multiple Spectators.
    """
    def __init__(self, host_ip, port):
        super().__init__(host_ip, port)
        print(f"[HOST] Host Client running at {host_ip}:{port}")

    # Connection Handshake
    def joiner_listen(self, as_spectator=False):
        """ Listens for only the joiner client's handshake request. Spectators
            handshake requests are handled separately.
        """
        connected = False
        while not connected:
            message_text, address = self.net_client.receive_from()

            if not message_text:
                continue

            message_dict = self.protocol_handler._parse_message(message_text)
            msg_type = message_dict.get('message_type')

            # -----------------------------------------------------
            # 1. CONNECTION REQUESTS (Can happen anytime)
            # -----------------------------------------------------
            if msg_type == messages.MessageType.HANDSHAKE_REQUEST.value:
                self.handle_player_join(address)
                connected = True
                continue
            # elif msg_type == messages.MessageType.SPECTATOR_REQUEST.value:
            #     self.handle_spectator_join(address)
            #     continue

    def __listener__(self):
        """ Listens for messages on a loop and puts them into a buffer"""
        while self.is_listening:
            message_text, address = self.net_client.receive_from()
            message_text = message_text.strip()

            # host specific behavior to handle a msg
            message_dict = self.protocol_handler._parse_message(message_text=message_text)
            if message_dict["message_type"] == messages.MessageType.SPECTATOR_REQUEST.value:
                self.handle_spectator_join(address=address)
                continue

            # Handle incoming message
            peers = self.protocol_handler.spectator_addrs + [self.protocol_handler.opponent_addr]
            if message_text and address in peers:
                self.protocol_handler.process_message(message_text, address)
            elif message_text:
                print(f"Received message from unknown sender {address}. Ignoring.")

    # =====================================================
    # NETWORK HANDLERS
    # =====================================================
    def handle_player_join(self, joiner_address):
        if self.protocol_handler.opponent_addr is not None:
            print(f"[Host] Player join attempt from {joiner_address} denied (game full).")
            return

        print(f"[HOST] Player (P2) connected from {joiner_address}.")

        seed = random.randint(1, 99999)
        match_data = {'seed': seed}

        self.protocol_handler.set_opponent(joiner_address, match_data, is_host=True)
        self.__start_listening__()
        self.asyncInput.start()

        response_msg = messages.HandshakeResponseMessage(seed=seed)
        self.net_client.send_to(response_msg.as_text(), joiner_address)
        print("[HOST] Player handshake complete.")
        # TODO Get pokemon name from user
        # self.protocol_handler.start_battle_setup(pokemon_name="Pikachu") #example

    def handle_spectator_join(self, spectator_address):
        print(f"\n[HOST] Spectator connected from {spectator_address}.")
        if spectator_address not in self.protocol_handler.spectator_addrs:
            self.spectator_addrs.append(spectator_address)
            print(f"[HOST] Spectator added. Total: {len(self.protocol_handler.spectator_addrs)}")

        seed = self.protocol_handler.match_data.get('seed', 0)

        # 1. Handshake
        response_msg = messages.HandshakeResponseMessage(seed=seed)

        self.net_client.send_to(response_msg.as_text(), spectator_address)
        print("[HOST] Spectator handshake complete.")

        # 2. State Sync (kind of brute forcing it rn)
        if self.protocol_handler.game_state not in ['CONNECTED', 'SETUP']:
            host_data = self.protocol_handler.match_data[self.protocol_handler.local_addr]
            msg = messages.BattleSetupMessage(
                communication_mode=messages.CommunicationMode.P2P,
                pokemon_name=host_data['pokemon_name'],
                stat_boosts=host_data['stat_boosts'],
            )
            self.net_client.send_to(msg.as_text(), spectator_address)
        if self.player_opponent_addr and self.player_opponent_addr[0] in self.protocol_handler.match_data:
            opp_data = self.protocol_handler.match_data[self.player_opponent_addr[0]]
            msg = messages.BattleSetupMessage(
                communication_mode=messages.CommunicationMode.P2P,
                pokemon_name=opp_data['pokemon_name'],
                stat_boosts=opp_data['stat_boosts'],
            )
            self.net_client.send_to(msg.as_text(), spectator_address)

        self.broadcast_to_spectators(msg.as_text())

    # def handle_spectator_message(self, message_text: str):
    #     message_dict = self.protocol_handler._parse_message(message_text)
    #
    #     message_dict = self.protocol_handler._parse_message(message_text)
    #     if message_dict.get('message_type') == messages.MessageType.CHAT_MESSAGE.value:
    #         sender = message_dict.get('sender_name', 'Spectator')
    #         print(f"[CHAT] {sender}: {message_dict.get('message_text', '')}")
    #         self.broadcast_to_all(message_text, exclude_sender=message_dict.get('sender_name'))

    # def broadcast_host_message(self, message_text: str):
    #     """Called when HOST sends a message."""
    #     # Append Host's IP
    #     tagged_text = f"HOST\n" + message_text
    #     self._send_to_spectators(tagged_text)

    # def broadcast_player_message(self, message_text: str):
    #     """Called when PLAYER sends a message."""
    #     # Append Player's IP
    #     tagged_text = f"PLAYER\n" + message_text
    #     self._send_to_spectators(tagged_text)

    # def _send_to_spectators(self, message_text: str):
    #     """Low-level sender"""
    #     for addr in self.spectator_addrs:
    #         self.net_client.send_to(message_text, addr)

    # def broadcast_to_all(self, message_text: str, exclude_sender=None):
    #     peers = [self.player_opponent_addr] + self.spectator_addrs
    #     for addr in peers:
    #         if addr and addr != exclude_sender:
    #             self.net_client.send_to(message_text, addr)
