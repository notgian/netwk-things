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


def print_pokemon_paginated(pokemon_names, page_size=10):
    total = len(pokemon_names)
    index = 0

    while index < total:
        end = min(index + page_size, total)
        for i in range(index, end):
            print(f"{i+1:03d}. {pokemon_names[i]}")
        if end < total:
            input(f"\n-- Showing {index+1}-{end} of {total}. Press ENTER for next page... --\n")
        index = end