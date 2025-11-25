import ast
import messages
import config
from messages import CommunicationMode
from messages import MessageType, ChatMessageType
from messages import (
    BattleSetupMessage,
    AttackAnnounceMessage,
    DefenseAnnounceMessage,
    CalculationReportMessage,
    CalculationConfirmMessage,
    ResolutionRequestMessage,
    GameOverMessage,
    ChatMessage,
    AckReplyMessage,
)
from pokemon import load_pokemon_data


class GameProtocolHandler:

    # -----------------------------
    #  INITIALIZATION & STATE
    # -----------------------------
    def __init__(self, net_client):
        self.net_client = net_client

        # RFC 5.2 / 5.3: battle states
        self.game_state = "CONNECTED" # CONNECTED -> SETUP -> WAITING_FOR_MOVE -> PROCESSING_TURN -> GAME_OVER

        # RFC: shared battle state, keyed by IP strings plus a 'seed'
        # {
        #   "seed": int,
        #   "<host_ip>": { "pokemon_name": str, "data": {...}, "hp": int, "stat_boosts": {...} },
        #   "<joiner_ip>": { ... }
        # }
        self.match_data = {}

        # networking / identity
        self.opponent_addr = None
        self.is_host = False
        self.local_ip = None
        self.host_ip = None
        self.joiner_ip = None

        # communication mode (P2P / BROADCAST – RFC 3 & 4.4)
        self.communication_mode = CommunicationMode.P2P

        # RFC 5.1: reliability layer — sequence numbers
        self.next_sequence_number = 1
        # Track last local calculation so CALCULATION_REPORT / CONFIRM / RESOLUTION_REQUEST make sense
        self.last_local_calculation = None

        # whose turn (IP string), used in WAITING_FOR_MOVE / PROCESSING_TURN
        self.current_turn_ip = None

        # cache Pokémon CSV so we don't reload repeatedly
        self._pokemon_db = None

    # -----------------------------
    #  UTILITY HELPERS
    # -----------------------------
    def _ensure_local_identity(self):
        if self.local_ip is None:
            try:
                self.local_ip = self.net_client.sock.getsockname()[0]
            except Exception:
                # fallback if something weird happens
                self.local_ip = "0.0.0.0"

    def _next_seq(self) -> int:
        seq = self.next_sequence_number
        self.next_sequence_number += 1
        return seq

    def _get_pokemon_db(self):
        if self._pokemon_db is None:
            self._pokemon_db = load_pokemon_data()
        return self._pokemon_db

    def _send_message(self, msg_obj: messages.Message):
        if not self.opponent_addr:
            print("[PROTOCOL] Cannot send message: opponent address not set.")
            return

        message_text = msg_obj.as_text()
        print(f"[PROTOCOL SEND]\n{message_text}\n---")
        self.net_client.send_to(message_text, self.opponent_addr)

    # -----------------------------
    #  SETUP OPPONENT & MATCH DATA
    # -----------------------------
    def set_opponent(self, opponent_addr: tuple, match_data: dict, is_host=False):
        self._ensure_local_identity()

        self.opponent_addr = opponent_addr
        self.is_host = is_host

        # initialize match_data with at least the shared seed
        self.match_data = match_data.copy()
        if "seed" not in self.match_data:
            self.match_data["seed"] = 0

        # determine which IP is host/joiner from our perspective
        if is_host:
            self.host_ip = self.local_ip
            self.joiner_ip = opponent_addr[0]
        else:
            self.host_ip = opponent_addr[0]
            self.joiner_ip = self.local_ip

        print(
            f"[PROTOCOL] Opponent set to {opponent_addr}. "
            f"Seed: {self.match_data.get('seed')} | is_host={self.is_host}"
        )

        # After handshake, RFC 5.2 initial state: SETUP (waiting for BATTLE_SETUP)
        self.game_state = "SETUP"

    # -----------------------------
    #  PROTOCOL 4.4: BATTLE_SETUP
    # -----------------------------
    def start_battle_setup(
        self,
        pokemon_name: str,
        stat_boosts: dict | None = None,
        communication_mode: CommunicationMode = CommunicationMode.P2P,
    ):

        self._ensure_local_identity()

        if stat_boosts is None:
            stat_boosts = {
                "special_attack_uses": 0,
                "special_defense_uses": 0,
            }

        self.communication_mode = communication_mode

        # Load Pokémon stats from CSV and store in match_data under our IP
        pokemon_db = self._get_pokemon_db()
        if pokemon_name not in pokemon_db:
            print(f"[PROTOCOL] Unknown Pokémon '{pokemon_name}' – check CSV file.")
            return

        base_stats = pokemon_db[pokemon_name]
        # Default to 100 if hp cannot be accessed.
        base_hp = int(base_stats.get("hp", 100))

        # IP-keyed structure (Ganire??)
        self.match_data[self.local_ip] = {
            "pokemon_name": pokemon_name,
            "data": base_stats,
            "hp": base_hp,
            "stat_boosts": stat_boosts,
        }

        print(
            f"[PROTOCOL] Local BATTLE_SETUP: ip={self.local_ip}, "
            f"pokemon={pokemon_name}, hp={base_hp}, boosts={stat_boosts}"
        )

        # Construct & send BATTLE_SETUP message using messages.BattleSetupMessage
        battle_setup_msg = BattleSetupMessage(
            communication_mode=self.communication_mode,
            pokemon_name=pokemon_name,
            stat_boosts=stat_boosts,
        )
        self._send_message(battle_setup_msg)

        # Remain in SETUP state until we also receive opponent's BATTLE_SETUP.
        # When both are known, we'll transition in _handle_battle_setup().

    # -----------------------------
    #  MAIN MESSAGE ENTRYPOINT
    # -----------------------------
    def process_message(self, message_text: str, from_address: tuple):
        message_dict = self._parse_message(message_text)

        msg_type_str = message_dict.get("message_type", "")
        if not msg_type_str:
            print("[PROTOCOL] Received malformed message (no message_type).")
            return

        # Auto-send ACK for any message with a sequence_number (RFC 5.1)
        seq_str = message_dict.get("sequence_number")
        if seq_str is not None:
            try:
                seq_num = int(seq_str)
                self._send_ack(seq_num)
            except ValueError:
                pass  # ignore bad sequence numbers for ACK purposes

        # Dispatch based on message_type string value
        if msg_type_str == MessageType.BATTLE_SETUP.value:
            self._handle_battle_setup(message_dict, from_address)

        elif msg_type_str == MessageType.ATTACK_ANNOUNCE.value:
            self._handle_attack_announce(message_dict, from_address)

        elif msg_type_str == MessageType.DEFENSE_ANNOUNCE.value:
            self._handle_defense_announce(message_dict, from_address)

        elif msg_type_str == MessageType.CALCULATION_REPORT.value:
            self._handle_calculation_report(message_dict, from_address)

        elif msg_type_str == MessageType.CALCULATION_CONFIRM.value:
            self._handle_calculation_confirm(message_dict, from_address)

        elif msg_type_str == MessageType.RESOLUTION_REQUEST.value:
            self._handle_resolution_request(message_dict, from_address)

        elif msg_type_str == MessageType.GAME_OVER.value:
            self._handle_game_over(message_dict, from_address)

        elif msg_type_str == MessageType.CHAT_MESSAGE.value:
            self._handle_chat_message(message_dict, from_address)

        elif msg_type_str == MessageType.ACK_REPLY.value:
            self._handle_ack_reply(message_dict, from_address)

        else:
            print(f"[PROTOCOL] Unknown or unhandled message_type: {msg_type_str}")

    # -----------------------------
    #  PROTOCOL 5.1: RELIABILITY
    # -----------------------------
    def _send_ack(self, sequence_number: int):

        ack_msg = AckReplyMessage(ack_number=sequence_number)
        self._send_message(ack_msg)

    def _handle_ack_reply(self, message_dict: dict, from_address: tuple):

        ack_num = message_dict.get("ack_number")
        print(f"[PROTOCOL] Received ACK for seq={ack_num} from {from_address}")

    # -----------------------------
    #  PROTOCOL 4.4: BATTLE_SETUP (RECEIVE)
    # -----------------------------
    def _handle_battle_setup(self, message_dict: dict, from_address: tuple):

        self._ensure_local_identity()

        opponent_ip = from_address[0]
        pokemon_name = message_dict.get("pokemon_name", "Unknown")

        # Parse stat_boosts string into dict (RFC: object; our wire format is dict-as-string)
        raw_boosts = message_dict.get("stat_boosts", "{}")
        try:
            stat_boosts = ast.literal_eval(raw_boosts)
            if not isinstance(stat_boosts, dict):
                stat_boosts = {}
        except Exception:
            stat_boosts = {}

        # Load Pokémon stats for opponent
        pokemon_db = self._get_pokemon_db()
        if pokemon_name not in pokemon_db:
            print(f"[PROTOCOL] Opponent sent unknown Pokémon '{pokemon_name}'.")
            base_stats = {}
            base_hp = 100
        else:
            base_stats = pokemon_db[pokemon_name]
            base_hp = int(base_stats.get("hp", 100))

        self.match_data[opponent_ip] = {
            "pokemon_name": pokemon_name,
            "data": base_stats,
            "hp": base_hp,
            "stat_boosts": stat_boosts,
        }

        print(
            f"[PROTOCOL] Opponent BATTLE_SETUP: ip={opponent_ip}, "
            f"pokemon={pokemon_name}, hp={base_hp}, boosts={stat_boosts}"
        )

        # If both locals are ready, move into WAITING_FOR_MOVE
        if self.local_ip in self.match_data and opponent_ip in self.match_data:
            print("[PROTOCOL] BATTLE_SETUP complete on both sides.")
            # RFC 5.2: Host goes first
            self.current_turn_ip = self.host_ip
            self.game_state = "WAITING_FOR_MOVE"
            print(
                f"[PROTOCOL] STATE -> WAITING_FOR_MOVE. "
                f"First turn: {self.current_turn_ip} "
                f"({'HOST' if self.current_turn_ip == self.host_ip else 'JOINER'})"
            )

    # -----------------------------
    #  PROTOCOL 4.5: ATTACK_ANNOUNCE
    # -----------------------------
    def send_attack_announce(self, move_name: str):
        # This does not form any calculation
        if self.game_state != "WAITING_FOR_MOVE":
            print(f"[PROTOCOL] Cannot ATTACK_ANNOUNCE in state {self.game_state}.")
            return

        self._ensure_local_identity()
        if self.current_turn_ip != self.local_ip:
            print("[PROTOCOL] It is not our turn to attack.")
            return

        seq = self._next_seq()
        msg = AttackAnnounceMessage(move_name=move_name, sequence_number=seq)
        self._send_message(msg)

        # After announcing, we wait for DEFENSE_ANNOUNCE & move to PROCESSING_TURN on receipt (RFC 5.2)
        print(f"[PROTOCOL] ATTACK_ANNOUNCE sent (move={move_name}, seq={seq}).")

    def _handle_attack_announce(self, message_dict: dict, from_address: tuple):

        move_name = message_dict.get("move_name", "UnknownMove")
        print(f"[PROTOCOL] Received ATTACK_ANNOUNCE from opponent: {move_name}")

        # The defender (us) should now respond with DEFENSE_ANNOUNCE when ready.
        # Actual UI logic (asking the user) is handled outside this class.

    # -----------------------------
    #  PROTOCOL 4.6: DEFENSE_ANNOUNCE
    # -----------------------------
    def send_defense_announce(self):
        seq = self._next_seq()
        msg = DefenseAnnounceMessage(sequence_number=seq)
        self._send_message(msg)
        print(f"[PROTOCOL] DEFENSE_ANNOUNCE sent (seq={seq}).")

        # RFC 5.2 / 5.3: after defense announce, both peers move to PROCESSING_TURN
        self.game_state = "PROCESSING_TURN"

    def _handle_defense_announce(self, message_dict: dict, from_address: tuple):
        print(f"[PROTOCOL] Received DEFENSE_ANNOUNCE from {from_address}.")
        self.game_state = "PROCESSING_TURN"

    # -----------------------------
    #  PROTOCOL 4.7: CALCULATION_REPORT
    # -----------------------------
    def send_calculation_report(
        self,
        attacker: str,
        move_used: str,
        remaining_health: int,
        damage_dealt: int,
        defender_hp_remaining: int,
        status_message: str,
    ):

        seq = self._next_seq()
        msg = CalculationReportMessage(
            attacker=attacker,
            move_used=move_used,
            remaining_health=remaining_health,
            damage_dealt=damage_dealt,
            defender_hp_remaining=defender_hp_remaining,
            status_message=status_message,
            sequence_number=seq,
        )

        # Remember what we sent so we can compare with opponent's report
        self.last_local_calculation = {
            "attacker": attacker,
            "move_used": move_used,
            "remaining_health": remaining_health,
            "damage_dealt": damage_dealt,
            "defender_hp_remaining": defender_hp_remaining,
        }

        self._send_message(msg)
        print(f"[PROTOCOL] CALCULATION_REPORT sent (seq={seq}).")

    def _handle_calculation_report(self, message_dict: dict, from_address: tuple):

        print(f"[PROTOCOL] Received CALCULATION_REPORT from {from_address}.")

        # Extract opponent's values
        opp_calc = {
            "attacker": message_dict.get("attacker"),
            "move_used": message_dict.get("move_used"),
            "remaining_health": int(message_dict.get("remaining_health", 0)),
            "damage_dealt": int(message_dict.get("damage_dealt", 0)),
            "defender_hp_remaining": int(
                message_dict.get("defender_hp_remaining", 0)
            ),
        }

        if not self.last_local_calculation:
            # If we haven't sent ours yet, just log; full reconciliation would require buffering both sides.
            print("[PROTOCOL] No local calculation stored yet; cannot compare. "
                  "Consider calling send_calculation_report() before expecting a comparison.")
            return

        # Compare all main fields for equality
        if opp_calc == self.last_local_calculation:
            # All good – send CALCULATION_CONFIRM
            print("[PROTOCOL] Calculation matches. Sending CALCULATION_CONFIRM.")
            seq = self._next_seq()
            confirm = CalculationConfirmMessage(sequence_number=seq)
            self._send_message(confirm)

            # Turn over; reverse order and go back to WAITING_FOR_MOVE (RFC 5.3)
            self.game_state = "WAITING_FOR_MOVE"
            self.current_turn_ip = (
                self.host_ip if self.current_turn_ip == self.joiner_ip else self.joiner_ip
            )
            print(
                f"[PROTOCOL] STATE -> WAITING_FOR_MOVE. "
                f"Next turn: {self.current_turn_ip}"
            )
        else:
            # Discrepancy → Send RESOLUTION_REQUEST first (RFC 5)
            print("[PROTOCOL] Calculation mismatch. Sending RESOLUTION_REQUEST.")

            seq = self._next_seq()
            req = ResolutionRequestMessage(
                attacker=self.last_local_calculation["attacker"],
                move_used=self.last_local_calculation["move_used"],
                damage_dealt=self.last_local_calculation["damage_dealt"],
                defender_hp_remaining=self.last_local_calculation["defender_hp_remaining"],
                sequence_number=seq,
            )
            self._send_message(req)

    # -----------------------------
    #  PROTOCOL 4.8: CALCULATION_CONFIRM
    # -----------------------------
    def _handle_calculation_confirm(self, message_dict: dict, from_address: tuple):

        print(f"[PROTOCOL] Received CALCULATION_CONFIRM from {from_address}.")
        self.game_state = "WAITING_FOR_MOVE"
        self.current_turn_ip = (
            self.host_ip if self.current_turn_ip == self.joiner_ip else self.joiner_ip
        )
        print(
            f"[PROTOCOL] STATE -> WAITING_FOR_MOVE. "
            f"Next turn: {self.current_turn_ip}"
        )

    # -----------------------------
    #  PROTOCOL 4.9: RESOLUTION_REQUEST
    # -----------------------------
    def _handle_resolution_request(self, message_dict: dict, from_address: tuple):

        print(f"[PROTOCOL] Received RESOLUTION_REQUEST from {from_address}.")

        # Extract the values peer believes are correct
        try:
            defender_hp_remaining = int(message_dict.get("defender_hp_remaining", 0))
        except ValueError:
            defender_hp_remaining = 0

        # This is Turn Processing State (RFC): If mismatch STILL happens → TERMINATE MATCH
        local_hp = self.last_local_calculation["defender_hp_remaining"]

        if defender_hp_remaining != local_hp:
            # TERMINATE MATCH — fundamental desync
            print("[PROTOCOL] Fundamental mismatch after RESOLUTION_REQUEST.")
            print("[PROTOCOL] TERMINATING MATCH (RFC 4.9 / 5.3).")

            # Notify opponent with GAME_OVER — no winner/loser due to desync
            seq = self._next_seq()
            msg = GameOverMessage(
                winner="NONE",
                loser="NONE",
                sequence_number=seq
            )
            self._send_message(msg)

            self.game_state = "GAME_OVER"
            return

        # If values match → adopt their value (RFC reconciliation)
        opp_ip = from_address[0]
        if opp_ip in self.match_data:
            self.match_data[opp_ip]["hp"] = defender_hp_remaining
            print(
                f"[PROTOCOL] RESOLUTION_REQUEST accepted. Synced HP for {opp_ip} = {defender_hp_remaining}"
            )

        # After successful reconciliation → proceed to next turn
        self.game_state = "WAITING_FOR_MOVE"
        self.current_turn_ip = (
            self.host_ip if self.current_turn_ip == self.joiner_ip else self.joiner_ip
        )
        print(
            f"[PROTOCOL] STATE -> WAITING_FOR_MOVE. "
            f"Next turn: {self.current_turn_ip}"
        )

    # -----------------------------
    #  PROTOCOL 4.10: GAME_OVER
    # -----------------------------
    def send_game_over(self, winner: str, loser: str):

        seq = self._next_seq()
        msg = GameOverMessage(winner=winner, loser=loser, sequence_number=seq)
        self._send_message(msg)
        print(f"[PROTOCOL] GAME_OVER sent (winner={winner}, loser={loser}, seq={seq}).")

        self.game_state = "GAME_OVER"

    def _handle_game_over(self, message_dict: dict, from_address: tuple):

        winner = message_dict.get("winner", "???")
        loser = message_dict.get("loser", "???")
        print(f"[PROTOCOL] GAME_OVER received. Winner={winner}, Loser={loser}")
        self.game_state = "GAME_OVER"

    # -----------------------------
    #  PROTOCOL 4.11: CHAT_MESSAGE
    # -----------------------------
    def send_chat_message(self, sender_name: str, content_type: ChatMessageType, content):

        seq = self._next_seq()
        msg = ChatMessage(
            sender_name=sender_name,
            content_type=content_type,
            content=content,
            sequence_number=seq,
        )
        self._send_message(msg)
        print(f"[PROTOCOL] CHAT_MESSAGE sent (type={content_type}, seq={seq}).")

    def _handle_chat_message(self, message_dict: dict, from_address: tuple):

        sender = message_dict.get("sender_name", "Unknown")
        content_type = message_dict.get("content_type", "TEXT")
        if content_type == ChatMessageType.TEXT.value:
            text = message_dict.get("message_text", "")
            print(f"[CHAT][{sender}] {text}")
        elif content_type == ChatMessageType.STICKER.value:
            sticker_data_preview = message_dict.get("sticker_data", "")[:20] + "..."
            print(f"[CHAT][{sender}] <STICKER> {sticker_data_preview}")
        else:
            print(f"[CHAT][{sender}] <UNKNOWN CONTENT TYPE>")

    # -----------------------------
    #  MESSAGE PARSING
    # -----------------------------
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
