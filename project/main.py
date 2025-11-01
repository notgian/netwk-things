import messages as msg


def main():
    messages = [
        msg.HandshakeRequestMessage(),
        msg.HandshakeResponseMessage(seed=12345),
        msg.SpectatorRequestMessage(),
        msg.BattleSetupMessage(communication_mode=msg.CommunicationMode.P2P,
                               pokemon_name="Pikachu",
                               stat_boosts={"sp_attack_uses": 5, "sp_def_uses": 5}),
        msg.AttackAnnounceMessage(move_name="Thunderbolt",
                                  sequence_number=4),
        msg.DefenseAnnounceMessage(sequence_number=5),
        msg.CalculationReportMessage(attacker="Pikachu",
                                     move_used="Thunderbolt",
                                     remaining_health=23,
                                     damage_dealt=4,
                                     defender_hp_remaining=45,
                                     status_message="Sample status message am too lazy",
                                     sequence_number=6),
        msg.CalculationConfirmMessage(sequence_number=7),
        msg.ResolutionRequestMessage(attacker="Pikachu",
                                     move_used="Thunderbolt",
                                     damage_dealt="4",
                                     defender_hp_remaining=45,
                                     sequence_number=8),
        msg.GameOverMessage(winner="Pikachu",
                            loser="Charmander",
                            sequence_number=9),
        msg.ChatMessage(sender_name="Player1",
                        content_type=msg.ChatMessageType.TEXT,
                        content="Good luck",
                        sequence_number=10),
        msg.ChatMessage(sender_name="Player2",
                        content_type=msg.ChatMessageType.STICKER,
                        content="Imagine this is b64 data",
                        sequence_number=11),
        msg.AckReplyMessage(ack_number=12),
    ]

    print("==============================")
    for message in messages:
        print(message.as_text())
        print("==============================")


if __name__ == "__main__":
    main()
