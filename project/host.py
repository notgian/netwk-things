import random
from typing import Tuple, Optional

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
    def joiner_listen(self):
        """ Listens for only the joiner client's handshake request. Spectators
            handshake requests are handled separately.
        """
        print("\n[MAIN] Host mode started. Waiting for connections...")

        while self.protocol_handler.opponent_addr is None:
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
                break
            elif msg_type == messages.MessageType.SPECTATOR_REQUEST.value:
                self.handle_spectator_join(address)

    def broadcast_to_all(self, message_text: str, exclude_address: Optional[Tuple[str, int]] = None):
        """
        Sends a message to the opponent (Joiner) and all Spectators.
        This enables critical game state updates (like attacks, damage)
        and chat messages to be relayed to everyone connected.
        """

        peers = set(self.protocol_handler.spectator_addrs)
        if self.protocol_handler.opponent_addr:
            peers.add(self.protocol_handler.opponent_addr)

        recipients = 0
        for addr in peers:
            if addr != exclude_address:
                self.net_client.send_to(message_text, addr)
                recipients += 1

        if recipients > 0:
            # Use protocol_handler's formatter since address tuples are used here
            print(f"[HOST BROADCAST] Sent message to {recipients} peers (Excluding: {self.protocol_handler.fmt_address(exclude_address)})")
        else:
            print("[HOST BROADCAST] No peers to send message to.")


    def __listener__(self):
        """ Listens for messages on a loop and puts them into a buffer"""
        while self.is_listening:
            message_text, address = self.net_client.receive_from()
            message_text = message_text.strip()

            # host specific behavior to handle a msg
            message_dict = self.protocol_handler._parse_message(message_text=message_text)
            if message_dict["message_type"] == messages.MessageType.SPECTATOR_REQUEST.value:
                self.handle_spectator_join(spectator_address=address)
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

    def handle_spectator_join(self, spectator_address):
        print(f"\n[HOST] Spectator connected from {spectator_address}.")
        if spectator_address not in self.protocol_handler.spectator_addrs:
            self.protocol_handler.spectator_addrs.append(spectator_address)
            print(f"[HOST] Spectator added. Total: {len(self.protocol_handler.spectator_addrs)}")

        seed = self.protocol_handler.match_data.get('seed', 0)

        # 1. Handshake
        response_msg = messages.HandshakeResponseMessage(seed=seed)
        self.net_client.send_to(response_msg.as_text(), spectator_address)
        print("[HOST] Spectator handshake complete.")

        # 2. State Sync (kind of brute forcing it rn)
        if self.protocol_handler.game_state not in ['CONNECTED', 'SETUP']:

            host_addr_str = self.protocol_handler.host_addr
            joiner_addr_str = self.protocol_handler.joiner_addr

            # Send Host's setup data
            if host_addr_str in self.protocol_handler.match_data:
                host_data = self.protocol_handler.match_data[host_addr_str]
                host_setup_msg = messages.BattleSetupMessage(
                    communication_mode=self.protocol_handler.communication_mode,
                    pokemon_name=host_data['pokemon_name'],
                    stat_boosts=host_data['stat_boosts'],
                )
                self.net_client.send_to(host_setup_msg.as_text(), spectator_address)

            # Send Joiner's setup data (if opponent is connected)
            if self.protocol_handler.opponent_addr and joiner_addr_str in self.protocol_handler.match_data:
                joiner_data = self.protocol_handler.match_data[joiner_addr_str]
                joiner_setup_msg = messages.BattleSetupMessage(
                    communication_mode=self.protocol_handler.communication_mode,
                    pokemon_name=joiner_data['pokemon_name'],
                    stat_boosts=joiner_data['stat_boosts'],
                )
                self.net_client.send_to(joiner_setup_msg.as_text(), spectator_address)

    def fmt_address(self, address: Optional[Tuple[str, int]]) -> str:
        """ Alias for protocol handler's formatter. """
        return self.protocol_handler.fmt_address(address)