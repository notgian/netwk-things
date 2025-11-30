
# Damage calculator (Hiniwalay ko na lang)

import random
from typing import Dict
import messages

# Fixed battle level
LEVEL = 50

# Stat boost bonus per use (RFC allows this simplification)
SPECIAL_ATTACK_BOOST = 10
SPECIAL_DEFENSE_BOOST = 10

# Deterministic random range
RANDOM_MIN = 0.85
RANDOM_MAX = 1.00

# Type effectiveness must match pokemon.csv naming
# Moves table – expand anytime
MOVES: Dict[str, Dict] = {
    "Tackle":    {"power": 40, "type": "normal", "category": "physical"},
    "Quick Attack": {"power": 40, "type": "normal", "category": "physical"},
    "Ember":     {"power": 40, "type": "fire",   "category": "special"},
    "Water Gun": {"power": 40, "type": "water",  "category": "special"},
    "Vine Whip": {"power": 45, "type": "grass",  "category": "physical"},
}


def deterministic_random(seed_value: int) -> float:
    rng = random.Random(seed_value)  # deterministic RNG with fixed seed
    return rng.uniform(RANDOM_MIN, RANDOM_MAX)


def calculate_damage(match_data: dict, attacker_addr: str, defender_addr: str, move_name: str) -> int:
    """

        NOTE: EXPECTS A FORMATTED ADDRESS
    """
    # ---- Retrieve attacker/defender data ----
    attacker = match_data[attacker_addr]
    defender = match_data[defender_addr]
    move = MOVES.get(move_name)

    if move is None:
        print(f"[BATTLE_LOGIC] Unknown move '{move_name}'. Defaulting to 10 damage.")
        return 10

    # ---- Determine attack & defense stats ----
    category = move["category"]
    power = move["power"]

    attacker_stats = attacker["data"]
    defender_stats = defender["data"]

    atk_boost = attacker["stat_boosts"].get("special_attack_uses", 0) * SPECIAL_ATTACK_BOOST
    def_boost = defender["stat_boosts"].get("special_defense_uses", 0) * SPECIAL_DEFENSE_BOOST

    if category == "physical":
        atk = attacker_stats.get("attack", 50)
        defense = defender_stats.get("defense", 50)
    else:  # special
        atk = attacker_stats.get("sp_attack", 50)
        defense = defender_stats.get("sp_defense", 50)

    # Apply stat boosts
    atk += atk_boost
    defense += def_boost

    if defense <= 0:
        defense = 1

    # ---- Type effectiveness using CSV ----
    move_type = move["type"]
    type_key = f"against_{move_type}"
    type_modifier = defender_stats.get(type_key, 1.0)  # default neutral

    # ---- Deterministic randomness (RFC requirement) ----
    seed = match_data["seed"]
    rand_factor = deterministic_random(seed)

    # ---- RFC Simplified Pokémon Damage Formula ----
    # base = (((2 * L / 5 + 2) * power * (atk / def)) / 50) + 2
    base_damage = (((2 * LEVEL / 5 + 2) * power * (atk / defense)) / 50) + 2

    final_damage = base_damage * type_modifier * rand_factor

    # Must deal at least 1 damage
    damage = max(1, int(final_damage))

    print(f"[BATTLE_LOGIC] move={move_name}, atk={atk}, def={defense}, power={power}")
    print(f"[BATTLE_LOGIC] type_mod={type_modifier}, rand={rand_factor}, base={base_damage}")
    print(f"[BATTLE_LOGIC] FINAL DAMAGE = {damage}")

    return damage


# ---------------------------------------------------------
# Helper functions (same as Host)
# ---------------------------------------------------------

def choose_pokemon(pokemon_db, input_function=input):
    """Simple CLI Pokémon selection menu."""
    names = list(pokemon_db.keys())
    print("\n=== Choose Your Pokémon ===")
    for i, name in enumerate(names):
        print(f"{i+1}. {name}")

    while True:
        choice = input_function("Enter Pokémon name or number: ").strip()
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(names):
                return names[idx]

        for n in names:
            if n.lower() == choice.lower():
                return n

        print("Invalid Pokémon. Try again.")

def choose_stat_boosts(input_function=input):
    """Ask user for RFC-allowed stat boosts."""
    print("\n=== Stat Boost Allocation ===")
    while True:
        try:
            sa = int(input_function("Special Attack Boost Uses (0–5): "))
            sd = int(input_function("Special Defense Boost Uses (0–5): "))
            if 0 <= sa <= 5 and 0 <= sd <= 5:
                return {
                    "special_attack_uses": sa,
                    "special_defense_uses": sd,
                }
        except ValueError:
            pass
        print("Invalid input. Enter numbers between 0 and 5.")

def choose_communication_mode(input_function=input):
    print("\n=== Communication Mode===")
    while True:
        print("Select communication mode")
        print("1. P2P Mode")
        print("2. Broadcast Mode")

        inp = input_function()
        if (inp == "1"):
            return messages.CommunicationMode.P2P
        elif (inp == "2"):
            return messages.CommunicationMode.BROADCAST
        else:
            print("Please try again...")