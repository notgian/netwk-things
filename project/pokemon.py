# This file provides a way to load the pokemon data into the
# program memory in a dictionary format

import csv


def load_pokemon_data():
    pokemon_dict = dict()

    with open("./pokemon.csv", encoding="utf-8") as f:
        csv_file = csv.DictReader(f)
        for entry in csv_file:
            name = entry["name"]
            pokemon_dict[name] = dict()

            # Which entities do we keep as a string
            # The rest are to be converted to floats
            keep_str = [
                "classfication",
                "japanese_name",
                "type1",
                "type2",
            ]

            keep_bool = [
                "is_legendary"
            ]

            for key in entry.keys():
                if (key == "name"):
                    continue

                elif (key == "abilities"):
                    abilities = [ability.strip()[1:-1] for ability in entry[key][1:-1].split(',')]
                    pokemon_dict[name]["abilities"] = abilities
                    continue
                elif (key in keep_str):
                    pokemon_dict[name][key] = entry[key]
                    continue
                elif (key in keep_bool):
                    pokemon_dict[name][key] = bool(entry[key])
                    continue
                else:
                    try:
                        pokemon_dict[name][key] = float(entry[key])
                    except ValueError:
                        pokemon_dict[name][key] = 0.0

    return pokemon_dict