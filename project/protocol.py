import ast
import messages
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
from reliability_layer import ReliabilityLayer


class GameProtocolHandler:

    # -----------------------------
    #  INITIALIZATION & STATE
    # -----------------------------
    def __init__(self, net_client, local_address, is_host=False):
        self.net_client = net_client

        # RFC 5.2 / 5.3: battle states
        # CONNECTED -> SETUP -> WAITING_FOR_MOVE -> PROCESSING_TURN -> GAME_OVER | TERMINATED
        # NOTE: Connected is a misnomer, as even a host waiting for a client is considered "CONNECTED" but I will not change this just in case
        self.game_state = "CONNECTED"

        # RFC: shared battle state, keyed by IP strings plus a 'seed'
        # {
        #   "seed": int,
        #   "<host_addr>": { "pokemon_name": str, "data": {...}, "hp": int, "stat_boosts": {...} },
        #   "<joiner_addr>": { ... }
        # }
        self.match_data = {}

        # networking / identity
        self.is_host = is_host
        self.local_addr = local_address
        self.opponent_addr = None
        self.current_turn_addr = None
        self.host_addr = None
        self.joiner_addr = None
        self.spectator_addrs = []

        self.communication_mode = None

        # Track last local calculation so CALCULATION_REPORT / CONFIRM / RESOLUTION_REQUEST make sense
        self.last_local_calculation = None

        # cache Pokémon CSV so we don't reload repeatedly
        self._pokemon_db = None

        self.on_message_sent_hook = None
        # -------- GAME-LOOP HOOKS (for Host/Player to read) --------
        # Last announced attack (attacker_addr, move_name)
        self.last_attack_announce = None
        # Whether DEFENSE_ANNOUNCE has been seen for the current turn
        self.last_defense_announce = False
        # Last calculation report we received from the opponent
        self.last_remote_calculation = None
        # Last status_message received in a CALCULATION_REPORT (for printing)
        self.last_received_status = None

        self.calc_confirm_local = False
        self.calc_confirm_remote = False

        self.reliability_layer = ReliabilityLayer(self.disconnect)
        self.reliability_layer.start()

    def disconnect(self, address: tuple):
        print(f"[PROTOCOL] {self.fmt_address(address)} disconnected!")

        potential_peers = [self.host_addr, self.joiner_addr] + self.spectator_addrs

        # putting in an edge case but it realistically should never happen
        if address not in potential_peers:
            print("[PROTOCOL] Unknown address disconnected? This should not be happening!")
        elif address == self.joiner_addr or address == self.host_addr:
            print("[PROTOCOL] Opponent Disconnected.")
            self.end_game("Opponent disconnected")
            return
        elif address in self.spectator_addrs:
            spectator_i = self.spectator_addrs.index(address)
            disconnected_spectator = self.spectator_addrs.pop(spectator_i)

        print(f"[PROTOCOL] Spectator disconnected ({self.fmt_address(disconnected_spectator)})")

    def end_game(self, reason=""):
        if self.game_state == "TERMINATED":
            return
        self.reliability_layer.stop()
        self.game_state = "TERMINATED"
        print("[PROTOCOL] GAME ENDED.")
        if reason == "":
            return
        print(f"           REASON: {reason}")

    # -----------------------------
    #  UTILITY HELPERS
    # -----------------------------
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

        non_ack_messages = [
            messages.MessageType.HANDSHAKE_REQUEST,
            messages.MessageType.HANDSHAKE_RESPONSE,
            messages.MessageType.SPECTATOR_REQUEST,
            messages.MessageType.BATTLE_SETUP,
            messages.MessageType.ACK
        ]

        if msg_obj.type not in non_ack_messages:
            self.reliability_layer.await_ack(self.opponent_addr)

        if self.on_message_sent_hook and msg_obj.type != messages.MessageType.ACK_REPLY:
            self.on_message_sent_hook(message_text)

    # -----------------------------
    #  SETUP OPPONENT & MATCH DATA
    # -----------------------------
    def set_opponent(self, opponent_addr: tuple, match_data: dict, is_host=False):
        self.opponent_addr = opponent_addr
        self.match_data = match_data
        self.is_host = is_host
        print(f"[PROTOCOL] Opponent set to {self.fmt_address(opponent_addr)}. Seed: {match_data.get('seed')}")

        # initialize match_data with at least the shared seed
        self.match_data = match_data.copy()
        if "seed" not in self.match_data:
            self.match_data["seed"] = 0

        # determine which IP is host/joiner from our perspective
        if is_host:
            self.host_addr = self.local_addr
            self.joiner_addr = opponent_addr
        else:
            self.host_addr = opponent_addr
            self.joiner_addr = self.local_addr

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

        # IP-keyed structure
        self.match_data[self.fmt_address(self.local_addr)] = {
            "pokemon_name": pokemon_name,
            "data": base_stats,
            "hp": base_hp,
            "stat_boosts": stat_boosts,
        }

        print(
            f"[PROTOCOL] Local BATTLE_SETUP: address={self.fmt_address(self.local_addr)}"
            f"pokemon={pokemon_name}, hp={base_hp}, boosts={stat_boosts}"
        )

        battle_setup_msg = BattleSetupMessage(
            communication_mode=self.communication_mode,
            pokemon_name=pokemon_name,
            stat_boosts=stat_boosts,
        )

        self._send_message(battle_setup_msg)
        self._check_battle_setup_complete()

    # -----------------------------
    #  CHECK IF BOTH SIDES FINISHED BATTLE_SETUP
    # -----------------------------
    def _check_battle_setup_complete(self):
        """Called after sending or receiving BATTLE_SETUP.
        Moves game into WAITING_FOR_MOVE when both sides are ready."""
        if (
                self.opponent_addr
                and self.fmt_address(self.opponent_addr) in self.match_data
                and self.fmt_address(self.local_addr) in self.match_data
        ):
            print("[PROTOCOL] BATTLE_SETUP complete on both sides.")

            # RFC 5.2: Host goes first
            self.current_turn_addr = self.host_addr
            self.game_state = "WAITING_FOR_MOVE"
            print(
                f"[PROTOCOL] STATE -> WAITING_FOR_MOVE. "
                f"First turn: {self.fmt_address(self.current_turn_addr)} "
                f"({'HOST' if self.current_turn_addr == self.host_addr else 'JOINER'})"
            )
            return True
        return False

    # -----------------------------
    #  MAIN MESSAGE ENTRYPOINT
    # -----------------------------
    def process_message(self, message_text: str, from_address: tuple):
        message_dict = self._parse_message(message_text)

        msg_type_str = message_dict.get("message_type", "")
        if not msg_type_str:
            print("[PROTOCOL] Received malformed message (no message_type).")
            return

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
        elif msg_type_str == MessageType.ACK.value:
            self._handle_ack(message_dict, from_address)
        elif msg_type_str == MessageType.SPECTATOR_REQUEST.value:
            self._handle_spectator_request(message_dict, from_address)
        else:
            print(f"[PROTOCOL] Unknown or unhandled message_type: {msg_type_str}")

        # Auto-send ACK for any message with a sequence_number (RFC 5.1)
        seq_str = message_dict.get("sequence_number")
        if seq_str is not None:
            try:
                seq_num = int(seq_str)
                self._send_ack(seq_num)
            except ValueError:
                pass  # ignore bad sequence numbers for ACK purposes

    # -----------------------------
    #  PROTOCOL 5.1: RELIABILITY
    # -----------------------------
    def _send_ack(self, sequence_number: int):
        ack_msg = AckReplyMessage(ack_number=sequence_number+1)
        self._send_message(ack_msg)

    def _handle_ack(self, message_dict: dict, from_address: tuple):
        ack_num = int(message_dict.get("ack_number"))
        self.reliability_layer.handle_ack(from_address, ack_num)
        print(f"[PROTOCOL] Received ACK ack_num={ack_num} from {from_address}")

    # -----------------------------
    #  PROTOCOL 4.4: BATTLE_SETUP (RECEIVE)
    # -----------------------------
    def _handle_battle_setup(self, message_dict: dict, from_address: tuple):
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

        self.match_data[self.fmt_address(self.opponent_addr)] = {
            "pokemon_name": pokemon_name,
            "data": base_stats,
            "hp": base_hp,
            "stat_boosts": stat_boosts,
        }

        # overwrite the communication_mode with the host's chosen mode
        msg_cmode = message_dict["communication_mode"]
        if (self.joiner_addr == self.local_addr):
            if self.communication_mode is not None and msg_cmode != self.communication_mode.value:
                print(f"Host chose a different communication mode. Setting to {msg_cmode}")
            if msg_cmode == messages.CommunicationMode.BROADCAST.value:
                self.communication_mode = messages.CommunicationMode.BROADCAST
            elif msg_cmode == messages.CommunicationMode.P2P.value:
                self.communication_mode = messages.CommunicationMode.P2P

        print(
            f"\n\n[PROTOCOL] Opponent BATTLE_SETUP: "
            f"\n           address={self.fmt_address(self.opponent_addr)} "
            f"\n           pokemon={pokemon_name}, "
            f"\n           hp={base_hp}, "
            f"\n           boosts={stat_boosts}\n"
        )

        # Check after receiving opponent setup
        self._check_battle_setup_complete()

    # -----------------------------
    #  PROTOCOL 4.5: ATTACK_ANNOUNCE
    # -----------------------------
    def send_attack_announce(self, move_name: str):
        # This does not form any calculation
        if self.game_state != "WAITING_FOR_MOVE":
            print(f"[PROTOCOL] Cannot ATTACK_ANNOUNCE in state {self.game_state}.")
            return

        if self.current_turn_addr != self.local_addr:
            print("[PROTOCOL] It is not our turn to attack.")
            return

        # seq = self._next_seq()
        seq = self.reliability_layer.get_sequence(self.get_opponent_addr())
        msg = AttackAnnounceMessage(move_name=move_name, sequence_number=seq)
        self._send_message(msg)

        # GAME-LOOP HOOK: record our own attack announce too (for local logic/UI)
        self.last_attack_announce = {
            "attacker_address": f"{self.fmt_address(self.local_addr)}",
            "move_name": move_name,
        }

    def _handle_attack_announce(self, message_dict: dict, from_address: tuple):
        move_name = message_dict.get("move_name", "UnknownMove")
        print(f"[PROTOCOL] Received ATTACK_ANNOUNCE from opponent: {move_name}")

        # GAME-LOOP HOOK: store last attack from opponent
        self.last_attack_announce = {
            "attacker_address": f"{self.fmt_address(from_address)}",
            "move_name": move_name,
        }

        # The defender (us) should now respond with DEFENSE_ANNOUNCE when ready.
        # Actual UI logic (asking the user) is handled outside this class.

    # -----------------------------
    #  PROTOCOL 4.6: DEFENSE_ANNOUNCE
    # -----------------------------
    def send_defense_announce(self):
        # seq = self._next_seq()
        seq = self.reliability_layer.get_sequence(self.get_opponent_addr())
        msg = DefenseAnnounceMessage(sequence_number=seq)
        self._send_message(msg)

        # RFC 5.2 / 5.3: after defense announce, both peers move to PROCESSING_TURN
        self.game_state = "PROCESSING_TURN"
        # GAME-LOOP HOOK
        self.last_defense_announce = True

    def _handle_defense_announce(self, message_dict: dict, from_address: tuple):
        print(f"[PROTOCOL] Received DEFENSE_ANNOUNCE from {from_address}.")
        self.game_state = "PROCESSING_TURN"
        # GAME-LOOP HOOK
        self.last_defense_announce = True

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
        """
        NOTE: All of these values must be computed by the GAME LOGIC
        (battleLogic + main loop). Handler only wraps & sends them.
        """

        # seq = self._next_seq()
        seq = self.reliability_layer.get_sequence(self.get_opponent_addr())
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
        print("[PROTOCOL] CONFIRMING CALCULATION...")

        while (self.last_remote_calculation is None or self.last_local_calculation is None):
            pass

        self.do_calculation_resolution()

    def _handle_calculation_report(self, message_dict: dict, from_address: tuple):
        print(f"[PROTOCOL] Received CALCULATION_REPORT from {from_address}.")

        # Extract opponent's values
        try:
            remaining_health = int(message_dict.get("remaining_health", 0))
        except ValueError:
            remaining_health = 0
        try:
            damage_dealt = int(message_dict.get("damage_dealt", 0))
        except ValueError:
            damage_dealt = 0
        try:
            defender_hp_remaining = int(message_dict.get("defender_hp_remaining", 0))
        except ValueError:
            defender_hp_remaining = 0

        opp_calc = {
            "attacker": message_dict.get("attacker"),
            "move_used": message_dict.get("move_used"),
            "remaining_health": remaining_health,
            "damage_dealt": damage_dealt,
            "defender_hp_remaining": defender_hp_remaining,
        }

        # GAME-LOOP HOOK: store remote calc + status message for UI
        self.last_remote_calculation = opp_calc
        self.last_received_status = message_dict.get("status_message", "")

    def do_calculation_resolution(self):
        if self.last_remote_calculation == self.last_local_calculation:
            # All good – send CALCULATION_CONFIRM
            print("[PROTOCOL] Calculation matches. Sending CALCULATION_CONFIRM.")
            # seq = self._next_seq()
            seq = self.reliability_layer.get_sequence(self.get_opponent_addr())
            confirm = CalculationConfirmMessage(sequence_number=seq)
            self._send_message(confirm)

            self.calc_confirm_local = True
            while self.calc_confirm_local is None or self.calc_confirm_remote is None:
                pass

            self.move_turnover()
        else:
            # Discrepancy → Send RESOLUTION_REQUEST first (RFC 5)
            print("[PROTOCOL] Calculation mismatch. Sending RESOLUTION_REQUEST.")

            # seq = self._next_seq()
            seq = self.reliability_layer.get_sequence(self.get_opponent_addr())
            req = ResolutionRequestMessage(
                attacker=self.last_local_calculation["attacker"],
                move_used=self.last_local_calculation["move_used"],
                damage_dealt=self.last_local_calculation["damage_dealt"],
                defender_hp_remaining=self.last_local_calculation[
                    "defender_hp_remaining"
                ],
                sequence_number=seq,
            )
            self._send_message(req)

    # -----------------------------
    #  PROTOCOL 4.8: CALCULATION_CONFIRM
    # -----------------------------
    def _handle_calculation_confirm(self, message_dict: dict, from_address: tuple):
        print(f"[PROTOCOL] Received CALCULATION_CONFIRM from {from_address}.")
        self.calc_confirm_remote = True

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
        local_hp = (
            self.last_local_calculation["defender_hp_remaining"]
            if self.last_local_calculation
            else None
        )

        if local_hp is None:
            print(
                "[PROTOCOL] No local calculation stored during RESOLUTION_REQUEST. "
                "Cannot compare; terminating match for safety."
            )
            # seq = self._next_seq()
            seq = self.reliability_layer.get_sequence(self.get_opponent_addr())
            msg = GameOverMessage(
                winner="NONE",
                loser="NONE",
                sequence_number=seq,
            )
            self._send_message(msg)
            self.game_state = "GAME_OVER"
            return

        if defender_hp_remaining != local_hp:
            # TERMINATE MATCH — fundamental desync
            print("[PROTOCOL] Fundamental mismatch after RESOLUTION_REQUEST.")
            print("[PROTOCOL] TERMINATING MATCH (RFC 4.9 / 5.3).")

            # Notify opponent with GAME_OVER — no winner/loser due to desync
            # seq = self._next_seq()
            seq = self.reliability_layer.get_sequence(self.get_opponent_addr())
            msg = GameOverMessage(
                winner="NONE",
                loser="NONE",
                sequence_number=seq,
            )
            self._send_message(msg)

            self.game_state = "GAME_OVER"
            return

        # If values match → adopt their value (RFC reconciliation)
        fmt_from_address = self.fmt_address(from_address)
        if self.fmt_address(fmt_from_address) in self.match_data:
            self.match_data[fmt_from_address]["hp"] = defender_hp_remaining
            print(
                f"[PROTOCOL] RESOLUTION_REQUEST accepted. "
                f"Synced HP for {fmt_from_address} = {defender_hp_remaining}"
            )

        # After successful reconciliation → proceed to next turn
        self.game_state = "WAITING_FOR_MOVE"
        self.current_turn_addr = (
            self.host_addr if self.current_turn_addr == self.joiner_addr else self.joiner_addr
        )
        print(
            f"[PROTOCOL] STATE -> WAITING_FOR_MOVE. "
            f"Next turn: {self.current_turn_addr}"
        )

        # Clean up for next turn
        self.last_local_calculation = None
        self.last_remote_calculation = None
        self.last_defense_announce = False
        self.last_attack_announce = None

    # -----------------------------
    #  PROTOCOL 4.10: GAME_OVER
    # -----------------------------
    def send_game_over(self, winner: str, loser: str):
        # seq = self._next_seq()
        seq = self.reliability_layer.get_sequence(self.get_opponent_addr())
        msg = GameOverMessage(winner=winner, loser=loser, sequence_number=seq)
        self._send_message(msg)
        print(f"[PROTOCOL] GAME_OVER sent (winner={winner}, loser={loser}, seq={seq}).")

        self.game_state = "GAME_OVER"
        self.end_game("GAME OVER")

    def _handle_game_over(self, message_dict: dict, from_address: tuple):
        winner = message_dict.get("winner", "???")
        loser = message_dict.get("loser", "???")
        print(f"[PROTOCOL] GAME_OVER received. Winner={winner}, Loser={loser}")
        self.game_state = "GAME_OVER"

    # -----------------------------
    #  PROTOCOL 4.11: CHAT_MESSAGE
    # -----------------------------
    def send_chat_message(self, sender_name: str, content_type: ChatMessageType, content):
        # seq = self._next_seq()
        seq = self.reliability_layer.get_sequence(self.get_opponent_addr())
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
            print(f"[CHAT | {self.fmt_address(sender)}] {text}")
        elif content_type == ChatMessageType.STICKER.value:
            sticker_data_preview = message_dict.get("sticker_data", "")[:20] + "..."
            print(f"[CHAT | {self.fmt_address(sender)}] <STICKER> {sticker_data_preview}")
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

    # -----------------------------
    #  GAME-LOOP HELPER METHODS
    # -----------------------------

    def move_turnover(self):
        self.current_turn_addr = (
            self.host_addr if self.current_turn_addr == self.joiner_addr else self.joiner_addr
        )

        # Clean up for next turn
        self.last_local_calculation = None
        self.last_remote_calculation = None
        self.last_defense_announce = False
        self.last_attack_announce = None
        self.calc_confirm_local = False
        self.calc_confirm_local = False

        self.game_state = "WAITING_FOR_MOVE"

        print(
            f"[PROTOCOL] STATE -> WAITING_FOR_MOVE. "
            f"Next turn: {self.fmt_address(self.current_turn_addr)}"
        )

    def fmt_address(self, address):
        return f"{address[0]}:{address[1]}"

    def get_match_data(self) -> dict:
        """Return the entire match_data dict (for game logic / UI)."""
        return self.match_data

    def get_local_addr(self) -> str | None:
        """Return our local IP (ensuring it's initialized)."""
        return self.local_addr

    def get_host_addr(self) -> str | None:
        return self.host_addr

    def get_joiner_addr(self) -> str | None:
        return self.joiner_addr

    def get_current_turn_addr(self) -> str | None:
        """Whose turn is it currently (IP string)."""
        return self.current_turn_addr

    def is_my_turn(self) -> bool:
        """Convenience: True if it's our turn to ATTACK_ANNOUNCE."""
        return self.current_turn_addr == self.local_addr

    def get_opponent_addr(self) -> str | None:
        """Return only the opponent's address """
        return self.opponent_addr if self.opponent_addr else None

    def get_hp(self, addr: str) -> int | None:
        """ Get current HP for a given IP.

            EXPECTS A FORMATTED ADDRESS
        """
        data = self.match_data.get(addr)
        if not data:
            return None
        return data.get("hp")

    def set_hp(self, addr: str, new_hp: int):
        """ Set HP for a given IP (game logic should call this after damage calc).

            EXPECTS A FORMATTED ADDRESS
        """
        if addr in self.match_data:
            self.match_data[addr]["hp"] = max(0, int(new_hp))

    def clear_turn_flags(self):
        """Reset per-turn hooks (optional, if game loop wants manual control)."""
        self.last_attack_announce = None
        self.last_defense_announce = False
        self.last_remote_calculation = None
        self.last_received_status = None
