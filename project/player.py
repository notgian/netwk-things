import config
import messages
from user import User


# ---------------------------------------------------------
# PLAYER CLASS
# ---------------------------------------------------------
class Player(User):
    def __init__(self, host_ip, host_port, local_ip, local_port=0):
        super().__init__(local_ip, local_port, host_ip, host_port)
        print(f"Player client initialized. Will connect to {host_ip}:{host_port}")

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
                self.player_opponent_addr = self.host_addr

                seed = int(message_dict.get('seed', 0))
                match_data = {'seed': seed}
                print(f"Received seed: {seed}")

                self.protocol_handler.set_opponent(self.player_opponent_addr, match_data, is_host=False)
                self.__start_listening__()
                self.asyncInput.start()
                return True

            else:
                print(f"[PLAYER] Received unexpected message response {message_text}.")
                return False
        except Exception as e:
            print(f"\n[PLAYER] Error during connection: {e}")
            return False