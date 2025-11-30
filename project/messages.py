# This script provides the module for message-related functions.
# Note: Message data will be constructed as a dict and then put
# together as plain text before sending

from enum import Enum


class MessageType(Enum):
    """ An enumeration type that defines
    the different types of messages that
    a user may send"""

    HANDSHAKE_REQUEST = "HANDSHAKE_REQUEST"
    HANDSHAKE_RESPONSE = "HANDSHAKE_RESPONSE"
    SPECTATOR_REQUEST = "SPECTATOR_REQUEST"
    BATTLE_SETUP = "BATTLE_SETUP"
    ATTACK_ANNOUNCE = "ATTACK_ANNOUNCE"
    DEFENSE_ANNOUNCE = "DEFENSE_ANNOUNCE"
    CALCULATION_REPORT = "CALCULATION_REPORT"
    CALCULATION_CONFIRM = "CALCULATION_CONFIRM"
    RESOLUTION_REQUEST = "RESOLUTION_REQUEST"
    GAME_OVER = "GAME_OVER"
    CHAT_MESSAGE = "CHAT_MESSAGE"
    ACK = "ACK"


class CommunicationMode(Enum):
    P2P = "P2P"
    BROADCAST = "BROADCAST"


class ChatMessageType(Enum):
    TEXT = "TEXT"
    STICKER = "STICKER"


class InvalidMessageType(Exception):
    """ An exception type thrown for when the provided message
    type is not a valid message type"""

    def __init__(self, given_type):
        self.message = f"The message you tried to send is not valid! The message type {given_type} does not exist!"
        super().__init__(self.message)


class InvalidMessageData(Exception):
    """ An exception type thrown for when a
    message is incorrectly formatted. """

    def __init__(self, message="The message you tried to send is not valid"):
        self.message = message
        super().__init__(self.message)


# Defenition of each message class
class Message:
    """ A class that allows for the construction of a message, providing its
    basic structure, and simple methods that can be inherited by each message
    type """

    def __init__(self, message_type: MessageType, **message_data):
        self.type = message_type
        self.data = dict()

        for key in message_data:
            self.data[key] = message_data[key]

    def as_text(self):
        """ returns the message and its data in plain text format """
        message_text = ""

        message_text += "message_type: " + self.type.value
        for key in self.data.keys():
            message_text += f"\n{key}: {self.data[key]}"

        return message_text


class HandshakeRequestMessage(Message):
    """ Provides the sublass for the HANDSHAKE_REQUEST message"""
    def __init__(self):
        super().__init__(MessageType.HANDSHAKE_REQUEST)


class HandshakeResponseMessage(Message):
    """ Provides the sublass for the HANDSHAKE_RESPONSE message """
    def __init__(self, seed: int):
        super().__init__(MessageType.HANDSHAKE_RESPONSE, seed=seed)


class SpectatorRequestMessage(Message):
    """ Provides the sublass for the SPECTATOR_REQUEST message """
    def __init__(self):
        super().__init__(MessageType.SPECTATOR_REQUEST)


class BattleSetupMessage(Message):
    """ Provides the sublass for the BATTLE_SETUP message """
    def __init__(self,
                 communication_mode: CommunicationMode,
                 pokemon_name: str,
                 stat_boosts: dict):
        super().__init__(MessageType.BATTLE_SETUP,
                         communication_mode=communication_mode.value,
                         pokemon_name=pokemon_name,
                         stat_boosts=stat_boosts)


class AttackAnnounceMessage(Message):
    """ Provides the sublass for the ATTACK_ANNOUNCE message """
    def __init__(self,
                 move_name: str,
                 sequence_number: int):
        super().__init__(MessageType.ATTACK_ANNOUNCE,
                         move_name=move_name,
                         sequence_number=sequence_number)


class DefenseAnnounceMessage(Message):
    """ Provides the sublass for the DEFENSE_ANNOUNCE message """
    def __init__(self,
                 sequence_number: int):
        super().__init__(MessageType.DEFENSE_ANNOUNCE,
                         sequence_number=sequence_number)


class CalculationReportMessage(Message):
    """ Provides the sublass for the CALCULATION_REPORT message """
    def __init__(self,
                 attacker: str,
                 move_used: str,
                 remaining_health: int,
                 damage_dealt: int,
                 defender_hp_remaining: int,
                 status_message: str,
                 sequence_number: int):
        super().__init__(MessageType.CALCULATION_REPORT,
                         attacker=attacker,
                         move_used=move_used,
                         remaining_health=remaining_health,
                         damage_dealt=damage_dealt,
                         defender_hp_remaining=defender_hp_remaining,
                         status_message=status_message,
                         sequence_number=sequence_number)


class CalculationConfirmMessage(Message):
    """ Provides the sublass for the CALCULATION_CONFIRM message """
    def __init__(self,
                 sequence_number: int):
        super().__init__(MessageType.CALCULATION_CONFIRM,
                         sequence_number=sequence_number)


class ResolutionRequestMessage(Message):
    """ Provides the sublass for the RESOLUTION_REQUEST message """
    def __init__(self,
                 attacker: str,
                 move_used: str,
                 damage_dealt: int,
                 defender_hp_remaining: int,
                 sequence_number: int):
        super().__init__(MessageType.RESOLUTION_REQUEST,
                         attacker=attacker,
                         move_used=move_used,
                         damage_dealt=damage_dealt,
                         defender_hp_remaining=defender_hp_remaining,
                         sequence_number=sequence_number)


class GameOverMessage(Message):
    """ Provides the sublass for the GAME_OVER message """
    def __init__(self,
                 winner: str,
                 loser: str,
                 sequence_number: int):
        super().__init__(MessageType.GAME_OVER,
                         winner=winner,
                         loser=loser,
                         sequence_number=sequence_number)


class ChatMessage(Message):
    """ Provides the sublass for the CHAT_MESSAGE message"""
    def __init__(self,
                 sender_name: str,
                 content_type: ChatMessageType,
                 content,
                 sequence_number: int):

        if content_type == ChatMessageType.TEXT:
            content_type_key = "message_text"
        elif content_type == ChatMessageType.STICKER:
            content_type_key = "sticker_data"

        # parsing dict as kwargs instead for this message type
        super().__init__(MessageType.CHAT_MESSAGE, **{
                         "sender_name": sender_name,
                         "content_type": content_type.value,
                         f"{content_type_key}": content,
                         "sequence_number": sequence_number
                         })


class AckReplyMessage(Message):
    """ Provides the sublass for the ACK message"""
    def __init__(self,
                 ack_number: int):
        super().__init__(MessageType.ACK,
                         ack_number=ack_number)