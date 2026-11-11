"""Turn raw Steam lobby metadata into readable fields.

Codes not listed here show as "#<n>" so nothing is guessed. Confirmed against the
in-game browser: Ranked (1=RM, 2=DM), MapType 24=Random and 12=Black Forest,
and the Players column = SlotsFilled/SlotCount.
"""
from __future__ import annotations

import re

RANKED = {"0": "--", "1": "RM", "2": "DM"}
GAME_TYPE = {"0": "Random Map", "1": "Regicide", "2": "Death Match", "3": "Scenario",
             "5": "King of the Hill", "6": "Wonder Race", "7": "Defend the Wonder",
             "8": "Turbo Random Map"}
MAP_STYLE = {"-1": "Scenario", "0": "Standard", "1": "Real World", "2": "Custom"}
MAP = {"9": "Arabia", "10": "Archipelago", "11": "Baltic", "12": "Black Forest", "13": "Coastal",
       "14": "Continental", "15": "Crater Lake", "16": "Fortress", "17": "Gold Rush",
       "18": "Highland", "19": "Islands", "20": "Mediterranean", "21": "Migration",
       "22": "Rivers", "23": "Team Islands", "24": "Random", "25": "Scandinavia",
       "26": "Mongolia", "27": "Yucatan", "28": "Salt Marsh", "29": "Arena",
       "30": "King of the Hill", "31": "Oasis", "32": "Ghost Lake", "33": "Nomad",
       "34": "Iberia", "35": "Britain", "36": "Mideast", "37": "Texas", "38": "Italy",
       "39": "Central America", "40": "France", "41": "Norse Lands", "42": "Sea of Japan",
       "43": "Byzantium"}
MAP_SIZE = {"0": "Tiny", "1": "Small", "2": "Medium", "3": "Normal", "4": "Large", "5": "Giant"}
SPEED = {"0": "Slow", "1": "Normal", "2": "Fast"}
RESOURCES = {"0": "Standard", "1": "Low", "2": "Medium", "3": "High"}
AGE = {"0": "Standard", "2": "Dark", "3": "Feudal", "4": "Castle", "5": "Imperial", "6": "Post-Imperial"}

_PLAYER = re.compile(r"^\[(-?\d+)\]\s*(.*)$")


def _lookup(table: dict, value) -> str | None:
    if value is None or value == "":
        return None
    return table.get(str(value), f"#{value}")


def _int(value, default=None):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def parse_slot(desc: str) -> dict:
    m = _PLAYER.match(desc or "")
    if m:
        return {"kind": "human", "name": m.group(2), "elo": int(m.group(1))}
    kind = {"Open": "open", "Closed": "closed", "AI Player": "ai"}.get(desc, "human")
    return {"kind": kind, "name": desc, "elo": None}


def describe(lobby: dict) -> dict:
    md = lobby.get("metadata", {})
    slot_count = _int(md.get("SlotCount"), lobby.get("max_members", 8))
    slots = [parse_slot(md[f"player{i}_desc"]) for i in range(slot_count) if f"player{i}_desc" in md]
    style = str(md.get("MapStyleType", ""))
    map_name = (md.get("ScenarioName") if style == "-1" and md.get("ScenarioName")
                else "Custom" if style == "2" else _lookup(MAP, md.get("MapType")))
    return {
        "id": str(lobby["steam_id"]),
        "title": md.get("title_salt") or md.get("name_salt") or f"Lobby {lobby['steam_id']}",
        "filled": _int(md.get("SlotsFilled"), lobby.get("num_members")),
        "slots": slot_count,
        "members": lobby.get("num_members"),
        "rank": _lookup(RANKED, md.get("Ranked")),
        "lobby_elo": _int(md.get("LobbyElo")) or None,
        "avg_elo": _int(md.get("SkillAverage")) or None,
        "game_type": _lookup(GAME_TYPE, md.get("GameType")),
        "map": map_name,
        "map_style": _lookup(MAP_STYLE, style),
        "map_size": _lookup(MAP_SIZE, md.get("MapSize")),
        "pop": _int(md.get("Pop")),
        "speed": _lookup(SPEED, md.get("Speed")),
        "resources": _lookup(RESOURCES, md.get("Resource")),
        "start_age": _lookup(AGE, md.get("Age")),
        "end_age": _lookup(AGE, md.get("EndAge")),
        "mod": md.get("DatasetWorkshopTitle") or None,
        "cheats": md.get("CheatsEnabled") == "1",
        "host_steamid": md.get("__gameserverSteamID"),
        "players": slots,
        "raw": md,
    }
