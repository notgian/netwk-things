import messages
import config
from messages import CommunicationMode

class GameProtocolHandler:

    def __init__(self, net_client):
        self.net_client = net_client
        self.game_state = "CONNECTED"
        self.match_data = {}
        self.opponent_addr = None
        self.is_host = False

    def set_opponent(self, opponent_addr: tuple, match_data: dict, is_host=False):
        self.opponent_addr = opponent_addr
        self.match_data = match_data
        self.is_host = is_host
        print(f"[PROTOCOL] Opponent set to {opponent_addr}. Seed: {match_data.get('seed')}")

    def start_battle_setup(self, pokemon_name: str):
        #TODO
        pass

    def process_message(self, message_text: str, from_address: tuple):
        #TODO
        pass

    def handle_battle_setup_responses(self, message_dict: dict):
        #TODO
        pass

    def _parse_message(self, message_text: str) -> dict:
        data = {}
        try:
            for line in message_text.split("\n"):
                if ":" in line:
                    key, value = line.split(":", 1)
                    data[key.strip()] = value.strip()
        except Exception as e:
            print(f"Error parsing message: {e}, Message: {message_text}")
        return data