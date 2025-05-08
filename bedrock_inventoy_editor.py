from leveldb import LevelDB
from amulet_nbt import *
import base64
import numpy
import wx
import wx.richtext as rt
import collections
import os
import io
import json
import re
import copy
import sys  # for making embedded exe
# import importlib.resources
from typing import Union
# import wx
import wx.lib.scrolledpanel as scrolled
# Use importlib.resources to load the embedded tem_atlas.json



APPDATA = os.getenv('LOCALAPPDATA')
WORLDS_DIR = os.path.join(APPDATA, "Packages", "Microsoft.MinecraftUWP_8wekyb3d8bbwe", "LocalState", "games",
                          "com.mojang", "minecraftWorlds")

WINDOW = {}
TAGITEMS = ['firework, bundle, chest, barrel, dispenser, shulker_box',
            'enchanted_book', 'helmet', 'chestplate', 'leggings','boots',
            'sword','axe', 'pickaxe','shovel', 'hoe', 'bow', 'mace', 'crossbow','shield','fishing_rod','carrot_on_a_stick']
CONTAINERS = {
    "bundle": ("storage_item_component_content", "Bundle"),
    "shulker": ("Items", "Shulker Box"),
    "dispenser": ("Items", "Dispenser"),
    "chest": ("Items", "Chest"),
    "barrel": ("Items", "Barrel"),
}
CONTAINER_TYPES = ["Shulker Box", "Dispenser", "Chest", "Barrel", "Bundle"]
categories = {
        "Building Blocks": {
        "Planks": [(0, 9), (11, 12)],
        "Walls": [(13, 38)],
        "Fences": [(39, 51)],
        "Fence_Gates": [(53, 63)],
        "Stairs": [(64, 121)],
        "Doors": [(122, 142)],
        "Trapdoors": [(143, 163)],
        "Glass": [165, 182, 1045, 1193],
        "Stained_Glass": [(166, 181)],
        "Glass_Panes": [(184, 199), 1734],
        "Wool": [(365, 380)],
        "Carpets": [(381, 396), 705, 707],
        "Concrete": [(413, 428)],
        "Concrete_Powder": [(397, 412)],
        "Terracotta": [(430, 461)],
        "Bricks": [(264, 267), (269, 271), (276, 278), 281, 344, 349, (357, 359), (361, 362), 465, (759, 762), 1376],
        "Blackstone": [(272, 273), 506, 513, 1580, 1597],
        "Basalt": [509, (516, 517)],
        "Tuff": [280, 508, 515],
        "Copper_Blocks": [295, (303, 310), (327, 334), 340, 489, 501, 1365],
        "Amethyst_Blocks": [720, 1378],
        "Prismarine": [348, 350, 1379],
        "Nether_Bricks": [360],
        "Nylium": [(469, 470)],
    },
    "Natural Blocks": {
        "Logs": [(522, 543), (562, 565), 742, 1765],
        "Wood": [544, 546, 548, 550, 552, 554, 556, 558, 560],
        "Stripped_Wood": [545, 547, 549, 551, 553, 555, 557, 559, 561],
        "Leaves": [(568, 578)],
        "Saplings": [(579, 587)],
        "Mushroom_Blocks": [(740, 741)],
        "Ores": [(483, 488), (490, 492), (494, 500), 1748],
        "Raw Blocks": [202, (293, 294), (335, 339), (341, 343), 346, (352, 356), 363, 462, (466, 467), 473, (566, 567), 604, 703, 706, 708, 714, 854, (863, 872), 1357, 1564, 1719, (1723, 1724), 1760],
    },
    "Rails": {
        "Rails": [(1555, 1556)],
    },
    "Water & Fire, Lava": [1762,(1730,1731)],
    "Redstone": {
        "Redstone Components 1": [(1557, 1558), 1561, (1565, 1579), (1582, 1596), 1598],
        "Redstone Components 2": [ (1600, 1604), (1606, 1607), 1714, (1755, 1756)],
        "Lamps": [1304, 1747],
    },
    "Farming": {
        "Crops": [(589, 593), (595, 600), (605, 606), (609, 611), 686, 990, 992, 994, 998, 1754],
        "Food": [(602, 603), (988, 989), 991, 995],
        "Animal_Products": [(744, 745), (764, 766), (771, 849), (981, 984), 1752],
    },
    "Mob Drops": {
        "Monster_Drops": [631, 641, 997, (1008, 1015), 1380, (1382, 1384), (1393, 1394), (1401, 1402), 1404, (1407, 1408)],
        "Heads": [(1347, 1353)],
    },
    "Weapons": {
        "Weapons": [(904, 909)],
    },
    "Tools": {
        "Tools": [(910, 933)],
    },
    "Armor": {
        "Armor": [(880, 903), 1042],
    },
    "Horse_Armor": {
        "Horse_Armor": [(1036, 1039)],
    },
    "Fireworks": {
        "Fireworks": [(1680, 1696)],
        "Star": [1406, (1697, 1712)],
    },
    "Containers": {

        "Shulker_Boxes": [(1262, 1278)],
        "Bundles": [(1019, 1035)],
        "Chests": [(1258, 1260), 1560],
        "Barrel": [1261],
        "Dispenser": [1604],
    },
    "Miscellaneous": {
        "Dyes": [(668, 683)],
        "Buckets": [(1337, 1346)],
        "Potions": [(1047, 1187)],
        "Music_Discs": [(1282, 1300)],
        "Boats": [(1535, 1554)],
        "Beds": [852, (1196, 1211), 1735],
        "Signs": [(1306, 1317)],
        "Hanging_Signs": [(1318, 1329)],
        "Banners": [(1611, 1637)],
        "Spawners": [(752, 753)],
        "Coral": [(622, 626), (632, 636)],
        "Dead_Coral": [(627, 630), (637, 640)],
        "Enchanted_Books": [(1413, 1534)],
    },
}
armor_item_range = {
    0: list(range(880, 886)) + [1042, 610] + list(range(1347, 1354)),  # "Helmet"
    1: list(range(886, 892)) + [1043],  # "Chest"
    2: range(892, 898),  # "Leggings"
    3: range(898, 904),  # "Boots"


}
color_dict = {
            0: 'black',
            8: 'gray',
            7: 'light_gray',
            15: 'white',
            12: 'light_blue',
            14: 'orange',
            1: 'red',
            4: 'blue',
            5: 'purple',
            13: 'magenta',
            9: 'pink',
            3: 'brown',
            11: 'yellow',
            10: 'lime',
            2: 'green',
            6: 'cyan',
        }
enchanted_books_map = {
    0: {'ench': [{'id': 'Aqua Affinity', 'lvl': 1}]},
    1: {'ench': [{'id': 'Bane of Arthropods', 'lvl': 1}]},
    2: {'ench': [{'id': 'Bane of Arthropods', 'lvl': 2}]},
    3: {'ench': [{'id': 'Bane of Arthropods', 'lvl': 3}]},
    4: {'ench': [{'id': 'Bane of Arthropods', 'lvl': 4}]},
    5: {'ench': [{'id': 'Bane of Arthropods', 'lvl': 5}]},
    6: {'ench': [{'id': 'Blast Protection', 'lvl': 1}]},
    7: {'ench': [{'id': 'Blast Protection', 'lvl': 2}]},
    8: {'ench': [{'id': 'Blast Protection', 'lvl': 3}]},
    9: {'ench': [{'id': 'Blast Protection', 'lvl': 4}]},
    10: {'ench': [{'id': 'Channeling', 'lvl': 1}]},
    11: {'ench': [{'id': 'Depth Strider', 'lvl': 1}]},
    12: {'ench': [{'id': 'Depth Strider', 'lvl': 2}]},
    13: {'ench': [{'id': 'Depth Strider', 'lvl': 3}]},
    14: {'ench': [{'id': 'Efficiency', 'lvl': 1}]},
    15: {'ench': [{'id': 'Efficiency', 'lvl': 2}]},
    16: {'ench': [{'id': 'Efficiency', 'lvl': 3}]},
    17: {'ench': [{'id': 'Efficiency', 'lvl': 4}]},
    18: {'ench': [{'id': 'Efficiency', 'lvl': 5}]},
    19: {'ench': [{'id': 'Feather Falling', 'lvl': 1}]},
    20: {'ench': [{'id': 'Feather Falling', 'lvl': 2}]},
    21: {'ench': [{'id': 'Feather Falling', 'lvl': 3}]},
    22: {'ench': [{'id': 'Feather Falling', 'lvl': 4}]},
    23: {'ench': [{'id': 'Fire Aspect', 'lvl': 1}]},
    24: {'ench': [{'id': 'Fire Aspect', 'lvl': 2}]},
    25: {'ench': [{'id': 'Fire Protection', 'lvl': 1}]},
    26: {'ench': [{'id': 'Fire Protection', 'lvl': 2}]},
    27: {'ench': [{'id': 'Fire Protection', 'lvl': 3}]},
    28: {'ench': [{'id': 'Fire Protection', 'lvl': 4}]},
    29: {'ench': [{'id': 'Flame', 'lvl': 1}]},
    30: {'ench': [{'id': 'Fortune', 'lvl': 1}]},
    31: {'ench': [{'id': 'Fortune', 'lvl': 2}]},
    32: {'ench': [{'id': 'Fortune', 'lvl': 3}]},
    33: {'ench': [{'id': 'Frost Walker', 'lvl': 1}]},
    34: {'ench': [{'id': 'Frost Walker', 'lvl': 2}]},
    35: {'ench': [{'id': 'Impaling', 'lvl': 1}]},
    36: {'ench': [{'id': 'Impaling', 'lvl': 2}]},
    37: {'ench': [{'id': 'Impaling', 'lvl': 3}]},
    38: {'ench': [{'id': 'Impaling', 'lvl': 4}]},
    39: {'ench': [{'id': 'Impaling', 'lvl': 5}]},
    40: {'ench': [{'id': 'Infinity', 'lvl': 1}]},
    41: {'ench': [{'id': 'Knockback', 'lvl': 1}]},
    42: {'ench': [{'id': 'Knockback', 'lvl': 2}]},
    43: {'ench': [{'id': 'Looting', 'lvl': 1}]},
    44: {'ench': [{'id': 'Looting', 'lvl': 2}]},
    45: {'ench': [{'id': 'Looting', 'lvl': 3}]},
    46: {'ench': [{'id': 'Loyalty', 'lvl': 1}]},
    47: {'ench': [{'id': 'Loyalty', 'lvl': 2}]},
    48: {'ench': [{'id': 'Loyalty', 'lvl': 3}]},
    49: {'ench': [{'id': 'Luck of the Sea', 'lvl': 1}]},
    50: {'ench': [{'id': 'Luck of the Sea', 'lvl': 2}]},
    51: {'ench': [{'id': 'Luck of the Sea', 'lvl': 3}]},
    52: {'ench': [{'id': 'Lure', 'lvl': 1}]},
    53: {'ench': [{'id': 'Lure', 'lvl': 2}]},
    54: {'ench': [{'id': 'Lure', 'lvl': 3}]},
    55: {'ench': [{'id': 'Mending', 'lvl': 1}]},
    56: {'ench': [{'id': 'Multishot', 'lvl': 1}]},
    57: {'ench': [{'id': 'Piercing', 'lvl': 1}]},
    58: {'ench': [{'id': 'Piercing', 'lvl': 2}]},
    59: {'ench': [{'id': 'Piercing', 'lvl': 3}]},
    60: {'ench': [{'id': 'Piercing', 'lvl': 4}]},
    61: {'ench': [{'id': 'Power', 'lvl': 1}]},
    62: {'ench': [{'id': 'Power', 'lvl': 2}]},
    63: {'ench': [{'id': 'Power', 'lvl': 3}]},
    64: {'ench': [{'id': 'Power', 'lvl': 4}]},
    65: {'ench': [{'id': 'Power', 'lvl': 5}]},
    66: {'ench': [{'id': 'Projectile Protection', 'lvl': 1}]},
    67: {'ench': [{'id': 'Projectile Protection', 'lvl': 2}]},
    68: {'ench': [{'id': 'Projectile Protection', 'lvl': 3}]},
    69: {'ench': [{'id': 'Projectile Protection', 'lvl': 4}]},
    70: {'ench': [{'id': 'Protection', 'lvl': 1}]},
    71: {'ench': [{'id': 'Protection', 'lvl': 2}]},
    72: {'ench': [{'id': 'Protection', 'lvl': 3}]},
    73: {'ench': [{'id': 'Protection', 'lvl': 4}]},
    74: {'ench': [{'id': 'Punch', 'lvl': 1}]},
    75: {'ench': [{'id': 'Punch', 'lvl': 2}]},
    76: {'ench': [{'id': 'Quick Charge', 'lvl': 1}]},
    77: {'ench': [{'id': 'Quick Charge', 'lvl': 2}]},
    78: {'ench': [{'id': 'Quick Charge', 'lvl': 3}]},
    79: {'ench': [{'id': 'Respiration', 'lvl': 1}]},
    80: {'ench': [{'id': 'Respiration', 'lvl': 2}]},
    81: {'ench': [{'id': 'Respiration', 'lvl': 3}]},
    82: {'ench': [{'id': 'Riptide', 'lvl': 1}]},
    83: {'ench': [{'id': 'Riptide', 'lvl': 2}]},
    84: {'ench': [{'id': 'Riptide', 'lvl': 3}]},
    85: {'ench': [{'id': 'Sharpness', 'lvl': 1}]},
    86: {'ench': [{'id': 'Sharpness', 'lvl': 2}]},
    87: {'ench': [{'id': 'Sharpness', 'lvl': 3}]},
    88: {'ench': [{'id': 'Sharpness', 'lvl': 4}]},
    89: {'ench': [{'id': 'Sharpness', 'lvl': 5}]},
    90: {'ench': [{'id': 'Silk Touch', 'lvl': 1}]},
    91: {'ench': [{'id': 'Smite', 'lvl': 1}]},
    92: {'ench': [{'id': 'Smite', 'lvl': 2}]},
    93: {'ench': [{'id': 'Smite', 'lvl': 3}]},
    94: {'ench': [{'id': 'Smite', 'lvl': 4}]},
    95: {'ench': [{'id': 'Smite', 'lvl': 5}]},
    96: {'ench': [{'id': 'Thorns', 'lvl': 1}]},
    97: {'ench': [{'id': 'Thorns', 'lvl': 2}]},
    98: {'ench': [{'id': 'Thorns', 'lvl': 3}]},
    99: {'ench': [{'id': 'Unbreaking', 'lvl': 1}]},
    100: {'ench': [{'id': 'Unbreaking', 'lvl': 2}]},
    101: {'ench': [{'id': 'Unbreaking', 'lvl': 3}]},
    102: {'ench': [{'id': 'Soul Speed', 'lvl': 1}]},
    103: {'ench': [{'id': 'Soul Speed', 'lvl': 2}]},
    104: {'ench': [{'id': 'Soul Speed', 'lvl': 3}]},
    105: {'ench': [{'id': 'Curse of Binding', 'lvl': 1}]},
    106: {'ench': [{'id': 'Curse of Vanishing', 'lvl': 1}]},
    107: {'ench': [{'id': 'Swift Sneak', 'lvl': 1}]},
    108: {'ench': [{'id': 'Swift Sneak', 'lvl': 2}]},
    109: {'ench': [{'id': 'Swift Sneak', 'lvl': 3}]},
    110: {'ench': [{'id': 'Density', 'lvl': 1}]},
    111: {'ench': [{'id': 'Density', 'lvl': 2}]},
    112: {'ench': [{'id': 'Density', 'lvl': 3}]},
    113: {'ench': [{'id': 'Density', 'lvl': 4}]},
    114: {'ench': [{'id': 'Density', 'lvl': 5}]},
    115: {'ench': [{'id': 'Wind Burst', 'lvl': 1}]},
    116: {'ench': [{'id': 'Wind Burst', 'lvl': 2}]},
    117: {'ench': [{'id': 'Wind Burst', 'lvl': 3}]},
    118: {'ench': [{'id': 'Breach', 'lvl': 1}]},
    119: {'ench': [{'id': 'Breach', 'lvl': 2}]},
    120: {'ench': [{'id': 'Breach', 'lvl': 3}]},
    121: {'ench': [{'id': 'Breach', 'lvl': 4}]},
}
enchantments = {
    8: "Aqua Affinity",
    11: "Bane of Arthropods",
    3: "Blast Protection",
    32: "Channeling",
    27: "Curse of Binding",
    28: "Curse of Vanishing",
    7: "Depth Strider",
    15: "Efficiency",
    2: "Feather Falling",
    13: "Fire Aspect",
    1: "Fire Protection",
    21: "Flame",
    18: "Fortune",
    25: "Frost Walker",
    29: "Impaling",
    22: "Infinity",
    12: "Knockback",
    14: "Looting",
    31: "Loyalty",
    23: "Luck of the Sea",
    24: "Lure",
    26: "Mending",
    33: "Multishot",
    34: "Piercing",
    19: "Power",
    4: "Projectile Protection",
    0: "Protection",
    20: "Punch",
    35: "Quick Charge",
    6: "Respiration",
    30: "Riptide",
    9: "Sharpness",
    16: "Silk Touch",
    10: "Smite",
    36: "Soul Speed",
    5: "Thorns",
    17: "Unbreaking",
    37: "Swift Sneak",
    40: "Breach",
    39: "Density",
    38: "Wind Burst"
}
valid_enchants = {
            "helmet": [0, 1, 3, 4, 5, 6, 8, 17, 26, 27, 28],
            "chestplate": [0, 1, 3, 4, 5, 17, 26, 27, 28],
            "elytra": [17,26,27,28],
            "leggings": [0, 1, 3, 4, 5, 37, 17, 26, 27, 28],
            "boots": [0, 1, 2, 3, 4, 5, 7, 25, 36, 17, 26, 27, 28],
            "sword": [9, 10, 11, 12, 13, 14, 16, 17, 26, 27, 28],
            "axe": [9, 10, 11, 13, 14, 15, 16, 17, 18, 26, 27, 28],
            "pickaxe": [15, 16, 17, 18, 26, 27, 28],
            "shovel": [15, 16, 17, 18, 26, 27, 28],
            "hoe": [15, 16, 17, 26, 27, 28],
            "bow": [19, 20, 21, 22, 17, 26, 27, 28],
            "crossbow": [19, 33, 34, 35, 17, 26, 27, 28],
            "trident": [13, 16, 17, 26, 29, 30, 31, 32, 27, 28],
            "fishing_rod": [16, 17, 23, 24, 26, 27, 28],
            "shears": [16, 17, 26, 27, 28],
            "mace": [17, 26, 38, 39, 40, 27, 28],
            'enchanted_book': list(enchantments.keys()),
            'shield' : [17,26, 27, 28]
        }
enchantment_applicability = {
    0: ["armor"],  # Protection
    1: ["armor"],  # Fire Protection
    2: ["boots"],  # Feather Falling
    3: ["armor"],  # Blast Protection
    4: ["armor"],  # Projectile Protection
    5: ["armor"],  # Thorns
    6: ["helmet"],  # Respiration
    7: ["boots"],  # Depth Strider
    8: ["helmet"],  # Aqua Affinity
    9: ["sword", "axe"],  # Sharpness
    10: ["sword", "axe"],  # Smite
    11: ["sword", "axe"],  # Bane of Arthropods
    12: ["sword"],  # Knockback
    13: ["sword"],  # Fire Aspect
    14: ["sword"],  # Looting
    15: ["tool"],  # Efficiency
    16: ["tool"],  # Silk Touch
    17: ["armor", "tool", "weapon", "elytra", "mace", "shield"],  # Unbreaking
    18: ["tool"],  # Fortune
    19: ["bow"],  # Power
    20: ["bow"],  # Punch
    21: ["bow"],  # Flame
    22: ["bow"],  # Infinity
    23: ["fishing_rod"],  # Luck of the Sea
    24: ["fishing_rod"],  # Lure
    25: ["boots"],  # Frost Walker
    26: ["armor", "tool", "weapon", "elytra", "mace", "shield"],  # Mending
    27: ["armor", "elytra", "shield"],  # Curse of Binding
    28: ["armor", "tool", "weapon", "elytra", "mace", "shield"],  # Curse of Vanishing
    29: ["trident"],  # Impaling
    30: ["trident"],  # Riptide
    31: ["trident"],  # Loyalty
    32: ["trident"],  # Channeling
    33: ["crossbow"],  # Multishot
    34: ["crossbow"],  # Piercing
    35: ["crossbow"],  # Quick Charge
    36: ["boots"],  # Soul Speed
    37: ["leggings"],  # Swift Sneak
    38: ["mace"],  # Wind Burst
    39: ["mace"],  # Density
    40: ["mace"],  # Breach
}
max_levels = {
    8: 1,    # Aqua Affinity
    11: 5,   # Bane of Arthropods
    3: 4,    # Blast Protection
    32: 1,   # Channeling
    27: 1,   # Curse of Binding
    28: 1,   # Curse of Vanishing
    7: 3,    # Depth Strider
    15: 5,   # Efficiency
    2: 4,    # Feather Falling
    13: 2,   # Fire Aspect
    1: 4,    # Fire Protection
    21: 1,   # Flame
    18: 3,   # Fortune
    25: 2,   # Frost Walker
    29: 5,   # Impaling
    22: 1,   # Infinity
    12: 2,   # Knockback
    14: 3,   # Looting
    31: 3,   # Loyalty
    23: 1,   # Luck of the Sea
    24: 1,   # Lure
    26: 1,   # Mending
    33: 1,   # Multishot
    34: 1,   # Piercing
    19: 5,   # Power
    4: 4,    # Projectile Protection
    0: 4,    # Protection
    20: 2,   # Punch
    35: 3,   # Quick Charge
    6: 3,    # Respiration
    30: 3,   # Riptide
    9: 5,    # Sharpness
    16: 1,   # Silk Touch
    10: 5,   # Smite
    36: 3,   # Soul Speed
    5: 3,    # Thorns
    17: 3,   # Unbreaking
    37: 3,   # Swift Sneak
    40: 4,   # Breach (not known)
    39: 5,   # Density (not known)
    38: 3    # Wind Burst (not known)
}
trims_dict = {
    "Sentry": "sentry", "Vex": "vex", "Wild": "wild", "Coast": "coast",
    "Dune": "dune", "Wayfinder": "wayfinder", "Shaper": "shaper",
    "Raiser": "raiser", "Host": "host", "Ward": "ward", "Silence": "silence",
    "Tide": "tide", "Snout": "snout", "Rib": "rib", "Eye": "eye",
    "Spire": "spire", "Flow": "flow", "Bolt": "bolt"
}
custom_color_dict = {
    "None": None, "Black": -14869215, "Red": -5231066, "Green": -10585066, "Brown": -8170446,
    "Blue": -12827478, "Purple": -7785800, "Cyan": -15295332, "Light Gray": -6447721,
    "Gray": -12103854, "Pink": -816214, "Lime": -8337633, "Yellow": -14869215,
    "Light Blue": -12930086, "Magenta": -3715395, "Orange": -425955, "White": -986896
}
material_dict = {
    "Iron": "iron", "Copper": "copper", "Gold": "gold", "Lapis": "lapis",
    "Emerald": "emerald", "Diamond": "diamond", "Redstone": "redstone",
    "Amethyst": "amethyst", "Quartz": "quartz", "Resin": "resin", "Netherite": "netherite"
}
TAG_CLASSES = {
    "ByteTag": ByteTag, "ShortTag": ShortTag, "IntTag": IntTag, "LongTag": LongTag,
    "FloatTag": FloatTag, "DoubleTag": DoubleTag, "StringTag": StringTag,
    "ListTag": ListTag, "CompoundTag": CompoundTag,
    "ByteArrayTag": ByteArrayTag, "IntArrayTag": IntArrayTag, "LongArrayTag": LongArrayTag
}
INPUT_SIZES = {
    'ByteTag': 40, 'ShortTag': 60, 'IntTag': 80, 'LongTag': 100,
    'FloatTag': 100, 'DoubleTag': 100, 'StringTag': 150,
    'ListTag': 100, 'CompoundTag': 20, 'ByteArrayTag': 25,
    'IntArrayTag': 100, 'LongArrayTag': 120
}
CLIP_BOARD = {}
DRAG_DATA_SOURCE = collections.defaultdict(dict)
DRAG_DATA_TARGET = collections.defaultdict(dict)
def get_item_type(item_id):
    """Returns the type of item in the slot based on its ID or tag."""
    types = [
        "sword", "pickaxe", "axe", "shovel", "hoe",
        "helmet", "chestplate", "leggings", "boots",
        "bow", "crossbow", "trident", "elytra",
        "fishing_rod", "mace", "enchanted_book", "shield"
    ]
    return next((t for t in types if t in item_id), "Not in list")

def check_set_default_book(bedrock_id): #check and set book
    if "enchanted_book:" in str(bedrock_id):
        tag_key = int(str(bedrock_id).split(':')[1])
        selected = enchanted_books_map[tag_key]
        ench_id = next((k for k, v in enchantments.items() if v == selected['ench'][0]['id']), None)
        ench_lvl = selected['ench'][0]['lvl']
        default_tag = CompoundTag({
            "ench": ListTag([
                CompoundTag({
                    "id": ByteTag(ench_id),
                    "lvl": ByteTag(ench_lvl)
                })
            ])
        })
        return (default_tag)

class PlayersData:
    def __init__(self, world):
        self.dict_of_player_data = collections.defaultdict(dict)
        self.world = world
        self.load_players_data()
        self._player = {}

    def get_player_data(self):
        return self._player
    @property
    def get_loaded_players_list(self):
        return [x for x in self.dict_of_player_data.keys()]

    def load_players_data(self):  # made it faster by using iterate 2 ranges
        for k, v in self.leveldb.iterate(start=b'~local_player'
                , end=b'~local_player' * 2):
            if b'~local_player' in k:
                nbt_dwellers = load(v, compressed=False, little_endian=True,
                                    string_decoder=utf8_escape_decoder).compound
                self.dict_of_player_data[k.decode()] = nbt_dwellers
        for k, v in self.leveldb.iterate(start=b'player_server'
                , end=b'player_server' * 14):
            if b'player_server' in k:
                nbt_dwellers = load(v, compressed=False, little_endian=True,
                                    string_decoder=utf8_escape_decoder).compound
                self.dict_of_player_data[k.decode()] = nbt_dwellers

    def get_player(self, player_id):
        if player_id not in self._player:
            self._player[player_id] = self.Player(self.dict_of_player_data[player_id], player_id, self.world)
        return self._player[player_id]

    @property
    def leveldb(self):
        if hasattr(self.world, "level_wrapper"):
            return self.world.level_wrapper.level_db
        else:
            return self.world

    class Player:

        def __init__(self, player_data, player_id, world):
            self.player_data = player_data
            self.player_id = player_id
            self.world = world
        def update(self, nbt):
            self.player_data = nbt
        def clear(self):
            self.player_data = CompoundTag({})
        def _traverse(self, keys):
            current = self.player_data
            for key in keys[:-1]:
                if isinstance(current, (collections.defaultdict, dict, CompoundTag)):
                    current = current[key]
                elif isinstance(current, (list, ListTag)):
                    for i, x in enumerate(current):
                        if x.get('Slot', IntTag(-9999)).py_int == key:
                            key = i
                            break
                        else:
                            pass
                    current = current[key]

                else:
                    raise KeyError(f"Invalid key/index during traversal: {key}")
            return current, keys[-1]

        def __getitem__(self, keys):
            if isinstance(keys, ListTag) and keys and isinstance(keys[-1], CompoundTag) and "Slot" in keys[-1]:
                # Special inventory-style access with {"Slot": N}
                slot_target = keys[-1]["Slot"]
                list_keys = keys[:-1]
                return self.get_or_create_slot_item(list_keys, slot_target)
            else:
                # Normal nested traversal
                current = self.player_data

                for key in keys:

                    if isinstance(current, (collections.defaultdict, dict, CompoundTag)):
                        current = current[key]
                    elif isinstance(current, (list, ListTag)):
                        if len(current) == 0:
                            raise KeyError(f"No Entrys: {key}")
                        else:
                            for i,x in enumerate(current):
                                if x.get('Slot', IntTag(-9999)).py_int == key:
                                    key = i
                                    break
                                else:
                                    pass
                            current = current[key]
                    else:
                        raise KeyError(f"Invalid key/index: {key}")
                return current

        def __setitem__(self, keys, value):

            current, last_key = self._traverse(keys)
            current[last_key] = value

        def __delitem__(self, keys):
            current, last_key = self._traverse(keys)
            del current[last_key]

        def pop(self, keys, default=None):
            current, last_key = self._traverse(keys)
            return current.pop(last_key, default)

        def keys(self, keys=None):
            if keys is None:
                return self.player_data.keys()
            nested = self[keys]
            if hasattr(nested, 'keys'):
                return nested.keys()
            raise TypeError("Target object does not support .keys()")

        def items(self, keys=None):
            if keys is None:
                return self.player_data.items()
            nested = self[keys]
            if hasattr(nested, 'items'):
                return nested.items()
            raise TypeError("Target object does not support .items()")

        @property
        def leveldb(self):
            if hasattr(self.world, "level_wrapper"):
                return self.world.level_wrapper.level_db
            else:
                return self.world

        def save_player(self):
            """Updates NBT data based on the current input fields."""

            nbt = self.player_data
            raw_nbt = nbt.save_to(compressed=False, little_endian=True,
                                  string_encoder=utf8_escape_encoder)
            self.leveldb.put(self.player_id.encode(), raw_nbt)
            print("Saved to World Updated NBT Data:", self.player_id.encode())

        def get_or_create_slot_item(self, keys, slot_value):
            """Finds or creates a CompoundTag with Slot=slot_value inside a ListTag."""
            current = self[keys]
            if not isinstance(current, ListTag):
                raise TypeError("Target is not a list")

            # Try to find existing item with Slot == slot_value
            for item in current:
                if isinstance(item, CompoundTag) and item.get("Slot") == slot_value:
                    return item

            # If not found, create and append it
            new_item = CompoundTag({"Slot": slot_value})
            current.append(new_item)
            return new_item

class IconResources:
    _instance = None  # Class-level instance reference

    def __new__(cls, *args, **kwargs):
        """
        The `__new__` method is responsible for creating and returning the instance.
        It ensures that only one instance of IconResources is ever created.
        """
        if not cls._instance:
            cls._instance = super(IconResources, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self):
        if not hasattr(self, '_initialized'):
            def get_resource_path(filename):
                if hasattr(sys, "_MEIPASS"):
                    # Running in PyInstaller bundle
                    return os.path.join(sys._MEIPASS, filename)
                else:
                    current_dir = os.path.dirname(os.path.abspath(__file__))
                    file_path = os.path.join(current_dir, 'item_atlas.json')
                    return file_path

            # Check to avoid reinitialization
            self._initialized = True
            self.catalog_window = None
            # Initialize the current directory and file path
            # current_dir = os.path.dirname(os.path.abspath(__file__))
            # file_path = os.path.join(current_dir, 'item_atlas.json')
            #
            # # Load the icon data from the file
            # with open(file_path, 'r') as file:
            #     self.data = json.load(file)
            json_path = get_resource_path("data/item_atlas.json")

            with open(json_path, "r") as f:
                self.data = json.load(f)
            self.items_id = []  # List to store item ids
            self.icon_cache = {}  # Cache for item icons
            self.scaled_cache = {}  # Cache for scaled item icons
            self.scaled_cache32 = {}
            self.icon_list_window = None  # Placeholder for the icon list window (not currently used)

            # Load the icon cache from the data
            self.load_icon_cache(self.data)

            # Remove the 'atlas' key from the data (unnecessary)
            self.data.pop('atlas', None)


    @property
    def get_items_id(self):
        """Returns the list of item IDs."""
        return self.items_id

    @property
    def get_json_data(self):
        """Returns the JSON data for the items."""
        return self.data

    @property
    def get_icon_cache(self):
        """Returns the icon cache dictionary."""
        return self.icon_cache

    @property
    def get_scaled_cache(self):
        """Returns the icon cache dictionary."""
        return self.scaled_cache

    @property
    def get_scaled_cache32(self):
        """Returns the icon cache dictionary."""
        return self.scaled_cache32

    def load_icon_cache(self, atlas):
        """Loads icons from the item atlas."""

        def load_base64_imagefile(data):
            """Decodes and loads the base64-encoded image from the atlas data."""
            atlas_data = base64.b64decode(data['atlas'])
            buffer = io.BytesIO(atlas_data)
            atlas_image = wx.Image()
            atlas_image.LoadFile(buffer, wx.BITMAP_TYPE_PNG)
            return atlas_image

        # Load the atlas image (either from base64 or direct file path)
        if isinstance(atlas, dict):
            atlas_image = load_base64_imagefile(atlas)
        else:
            atlas_image = wx.Image(atlas, wx.BITMAP_TYPE_PNG)

        # Extract icons from the atlas and add to the cache
        for item_id, data in self.data.items():
            if "icon_position" in data:
                x, y = data["icon_position"]["x"], data["icon_position"]["y"]
                icon_image = atlas_image.GetSubImage(wx.Rect(x, y, 32, 32))
                self.icon_cache[item_id] = icon_image
                self.items_id.append(item_id)

        target_width = 64
        target_height = 64

        for item_id, img in self.icon_cache.items():
            scaled_img = img.Scale(target_width, target_height, wx.IMAGE_QUALITY_HIGH)
            bmp = scaled_img.ConvertToBitmap()
            self.scaled_cache[item_id] = bmp

    def get_bitmap(self, bedrock_id):
        return self.scaled_cache.get(bedrock_id)

    def get(self, item_id, default=None):
        """Returns the data for a given item ID, or a default value if not found."""
        return self.data.get(item_id, default)

    def open_catalog(self, parent, data, slot):
        """Open the catalog window, ensuring only one instance exists."""
        if WINDOW.get('catalog', None) is None:  # If window is not created yet
            WINDOW['catalog'] = IconListCtrl(parent, "Catalog", data, slot)
        else:
            self.catalog_window.update_data(data)
            self.catalog_window.update_slot(slot)
            # Calculate position to place the catalog window next to the parent window
        mouse_x, mouse_y = wx.GetMousePosition()

        # Optionally, add some offset to the mouse position so that the window doesn't overlap the mouse
        offset_x = 10  # Horizontal offset from the mouse position
        offset_y = 10  # Vertical offset from the mouse position

        # Set the position of the catalog window to be near the mouse position
        WINDOW['catalog'].Move(mouse_x + offset_x, mouse_y + offset_y)

        # Ensure the window stays within the screen bounds (on the same monitor)
        screen_width, screen_height = wx.GetDisplaySize()  # Get screen size (monitor resolution)

        # Check if the catalog window would go off the screen on the right or bottom
        catalog_x, catalog_y = WINDOW['catalog'].GetPosition()
        catalog_width, catalog_height = WINDOW['catalog'].GetSize()
        if catalog_x + catalog_width > screen_width:
            # If it's too far to the right, position it to the left of the mouse
            WINDOW['catalog'].Move(mouse_x - catalog_width - offset_x, mouse_y + offset_y)
        if catalog_y + catalog_height > screen_height:
            # If it's too far down, position it above the mouse
            WINDOW['catalog'].Move(mouse_x + offset_x, mouse_y - catalog_height - offset_y)
        WINDOW['catalog'].Show()  # Show the window
        WINDOW['catalog'].Raise()  # Bring it to the front

    def close_catalog(self):
        """Close (hide) the catalog window."""
        if WINDOW.get('catalog', None):
            WINDOW['catalog'].Hide()  # Hide the window, but don't destroy it

    def toggle_catalog_h(self, parent, data, slot):
        if WINDOW.get('catalog', None) is None:
            WINDOW['catalog'](parent, data, slot)

            WINDOW['catalog'].Hide()

    def toggle_catalog(self, parent, data, slot):
        """Toggle between showing and hiding the catalog window."""
        def poss():
            # Calculate position to place the catalog window next to the parent window
            mouse_x, mouse_y = wx.GetMousePosition()

            # Optionally, add some offset to the mouse position so that the window doesn't overlap the mouse
            offset_x = -800  # Horizontal offset from the mouse position
            offset_y = -50  # Vertical offset from the mouse position

            # Set the position of the catalog window to be near the mouse position
            WINDOW['catalog'].Move(mouse_x + offset_x, mouse_y + offset_y)

            # Ensure the window stays within the screen bounds (on the same monitor)
            screen_width, screen_height = wx.GetDisplaySize()  # Get screen size (monitor resolution)

            # Check if the catalog window would go off the screen on the right or bottom
            catalog_x, catalog_y = WINDOW['catalog'].GetPosition()
            catalog_width, catalog_height = WINDOW['catalog'].GetSize()
            if catalog_x + catalog_width > screen_width:
                # If it's too far to the right, position it to the left of the mouse
                WINDOW['catalog'].Move(mouse_x - catalog_width - offset_x, mouse_y + offset_y)
            if catalog_y + catalog_height > screen_height:
                # If it's too far down, position it above the mouse
                WINDOW['catalog'].Move(mouse_x + offset_x, mouse_y - catalog_height - offset_y)
        if WINDOW.get('catalog', None) is None:
            self.open_catalog(parent, data, slot)
            poss()
            self.catalog_window.Show()
        else:
            # self.catalog_window.update_data(data)
            # self.catalog_window.update_slot(slot)

            if WINDOW['catalog'].IsShown():
                WINDOW['catalog'].Hide()
            else:
                # Calculate position to place the catalog window next to the parent window
                if WINDOW['catalog'] is None:  # If window is not created yet
                    WINDOW['catalog'] = IconListCtrl(parent, "Catalog", data, slot)

                poss()
                WINDOW['catalog'].Show()

class InventoryEditor(wx.Frame):
    def __init__(self, parent, selected_player, keys, title="Inventory Editor"):
        super().__init__(parent, title=title, size=(810, 740), style=wx.DEFAULT_FRAME_STYLE | wx.STAY_ON_TOP)

        self.armor_types = ['helmet', 'chestplate', 'leggings', 'boots']
        self.resources = IconResources()
        self.parent = parent
        self.selected_player = selected_player
        # self.resources.icon_cache = self.resources.icon_cache
        # self.data = self.resources.get_json_data
        self.keys = keys
        self.inventory = selected_player[keys]
        self.slot_map = collections.defaultdict(list)
        self.items_id = []
        self.armor_tags = {}
        self.current_slot = 0
        main_vbox = wx.BoxSizer(wx.VERTICAL)
        self.scroll_panel = wx.ScrolledWindow(self, style=wx.VSCROLL)
        self.font = wx.Font(18, wx.FONTFAMILY_ROMAN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        self.SetFont(self.font)
        self.SetForegroundColour((0, 255, 0))
        self.SetBackgroundColour(wx.Colour(0, 0, 0, 0))
        self.dragged_index = None
        self.dragged_id = None
        self.drag_image = None

        menubar = wx.MenuBar()
        file_menu = wx.Menu()

        # 1. Predefined ID: wx.ID_OPEN
        file_menu.Append(wx.ID_OPEN, "Import Inventory\tCtrl+O", "Open a file")
        self.Bind(wx.EVT_MENU, self.on_open, id=wx.ID_OPEN)

        file_menu.Append(wx.ID_SAVE, "Export Inventory\tCtrl+S", "Save")
        self.Bind(wx.EVT_MENU, self.on_save, id=wx.ID_SAVE)

        # 2. Custom ID using NewIdRef
        self.items_id = wx.NewIdRef()
        file_menu.Append(self.items_id, "Items Menu\tCtrl+I", "Show items")
        self.Bind(wx.EVT_MENU, self.on_items_menu, id=self.items_id)

        # 3. Custom ID using NewIdRef (Clear All)
        self.clear_id = wx.NewIdRef()
        file_menu.Append(self.clear_id, "Clear All\tCtrl+Shift+C", "Clear everything")
        self.Bind(wx.EVT_MENU, self.on_clear_all, id=self.clear_id)

        menubar.Append(file_menu, "&Menu")
        self.SetMenuBar(menubar)

        # Accelerator table
        accel_tbl = wx.AcceleratorTable([
            (wx.ACCEL_CTRL, ord('O'), wx.ID_OPEN),  # Open
            (wx.ACCEL_CTRL, ord('I'), self.items_id),  # Items Menu
            (wx.ACCEL_CTRL | wx.ACCEL_SHIFT, ord('C'), self.clear_id),  # Clear All
        ])
        self.SetAcceleratorTable(accel_tbl)
        # Layout sections
        self.grid_sizer = wx.GridSizer(4, 9, 5, 5)  # Max columns set to 9

        self.populate_grid()  # Fill the grid with items
   #     self.map_drop_buttons()
        self.scroll_panel.SetSizer(self.grid_sizer)
        main_vbox.Add(self.scroll_panel, 1, wx.EXPAND | wx.ALL, 5)
        # self.Bind(wx.EVT_CLOSE, self.on_close)
        self.SetSizer(main_vbox)
        self.Centre()
        # self.Move(self.GetPosition())
        self.Show()


    def on_open(self, event):
        with wx.FileDialog(self, "Open NBT file", wildcard="NBT files (*.nbt)|*.nbt",
                           style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as file_dialog:
            if file_dialog.ShowModal() == wx.ID_CANCEL:
                return

            pathname = file_dialog.GetPath()
            print(f"Opening file: {pathname}")
            loaded_nbt = load(pathname, compressed=False, little_endian=True,
                 string_decoder=utf8_escape_decoder).compound

            self.selected_player.clear()
            self.selected_player.update(loaded_nbt)
            self.selected_player.save_player()

    def on_save(self, event):

        with wx.FileDialog(self, "Save NBT file", wildcard="NBT files (*.nbt)|*.nbt",
                           style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as file_dialog:
            if file_dialog.ShowModal() == wx.ID_CANCEL:
                return  # user cancelled

            pathname = file_dialog.GetPath()
            if not pathname.lower().endswith('.nbt'):
                pathname += '.nbt'
            self.selected_player[[]].save_to(pathname,compressed=False, little_endian=True,
                                  string_encoder=utf8_escape_encoder)

            print(f"Saving file to: {pathname}")
            # TODO: Save your NBT file here
    def on_items_menu(self, event):
        self.icon_resources = IconResources()
        self.icon_resources.toggle_catalog(self.parent, self, None)

    def on_clear_all(self, event):
        for x in self.slot_map.values():
            x.button.SetName('Empty')
            x.button.SetBitmap(wx.NullBitmap)
            x.button.SetToolTip('Empty')
            x.SetValue(0)
            current = self.keys + list(x.Get_slot_map_key())
            self.selected_player[current]['Name'] = StringTag('')
            self.selected_player[current]['tag'] = CompoundTag({})
            self.selected_player[current]['Damage'] = ShortTag(0)
        self.Refresh()

    def get_selected_slot(self):
        return self.current_slot

    def set_selected_slot(self, selected):
        self.current_slot = selected

    def update_slot(self, slot_index, bedrock_id, icon, display_name, tagdata):
        """Updates an existing button in the grid with new item data."""
        if slot_index in self.slot_map:  # Ensure the button exists
            button = self.slot_map[slot_index]

            if isinstance(button, IconButton):  # Ensure it's an IconButton
                button.SetBitmap(icon, display_name)
                button.SetLabelText(bedrock_id)
                button.count_box.SetValue("1")
                button.count_box.Parent.SetTagData(tagdata)
                button.SetName(bedrock_id)
                button.set_slot(slot_index)
                self.set_selected_slot(slot_index)
            self.scroll_panel.Layout()
            self.scroll_panel.Refresh()

    def save_button(self, event):

        for x in self.slot_map.values():

            key, slot = x.Get_slot_map_key()
            current_keys = self.keys + [key]
            current = self.selected_player[current_keys]
            slot_id = slot  # save original slot value for clarity

            # Find the item with the matching 'Slot'
            item_index = next(
                (i for i, item in enumerate(current)
                 if item.get('Slot', IntTag(-99)).py_int == slot_id),
                None
            )

            if item_index is None:
                # print(f"Slot {slot_id} not found in {current_keys}")
                continue  # or handle this gracefully

            # Now it's safe to assign the value
            current[item_index]['Count'] = x.GetValue()

            if x.GetValue().py_int == 0:
                current[item_index]['Name'] = StringTag('')



        self.selected_player.save_player()

    def ender_chest(self, event):
        InventoryEditor(self, self.selected_player, [], title='Ender Chest')

    def populate_grid(self):
        self.grid_sizer.Clear(delete_windows=False)

        armor_buttons = []
        data_damage_tag_list_of = ['firework_star', 'bed', 'splash_potion', 'lingering_potion', 'potion',
                                   'ominous_bottle', 'goat_horn']

        def more_display_info(display_name, item):
            if not item:
                return display_name or "Empty"

            def get_items_info(tag_list):
                result = ""
                for i, (name, count) in enumerate(tag_list):
                    name_item = self.inventory.get(name[10:], {}).get("display_name", "Empty")
                    if i % 8 == 0:
                        result += f"\n{name_item} {count}   ||  "
                    else:
                        result += f"{name_item} {count}  ||   "
                return result

            bundle = item.get('tag', {}).get('storage_item_component_content')
            if bundle:
                tag_list = [(x.get('Name').py_str, x.get('Count').py_int) for x in bundle]
                display_name += "\n Items:" + get_items_info(tag_list)
            try:
                item_list = item.get('tag', {}).get('Items')
            except  (KeyError, IndexError, TypeError):
                item_list = False
                print('key error on empty list')
                pass
            if item_list:
                if len(item_list) > 0:
                    try:
                        tag_list = [(x.get('Name').py_str, x.get('Count').py_int) for x in item_list]
                        display_name += "\n Items:" + get_items_info(tag_list)
                    except:
                        pass
            ench = item.get('tag', {}).get('ench')
            if ench:
                display_name += "\n Enchantments:"
                for x in ench:
                    display_name += f"\n{enchantments[x.get('id').py_int]} {x.get('lvl').py_int}"

            return display_name or "Empty"

        def processes_item_iter_next(item):
            item_name = ''
            if item and "Name" in item:
                item_name = item["Name"].py_str[10:]
                damage = item.get('Damage', {}).py_int
                if item_name == 'banner':
                    item_name = f'{color_dict.get(damage, "white")}_{item_name}'
                elif item_name in data_damage_tag_list_of:
                    item_name = f"{item_name}:{damage}"

                if item.get('tag'):
                    for k, v in item['tag'].items():
                        if '_' in item_name and item_name.split('_')[0] in self.armor_types:
                            self.armor_tags[k] = v
            return item_name

        def middle_slots(count, main=True, not_extra=True):
            for i in range(count):
                if i == 1 and not_extra:
                    save_bmp = wx.ArtProvider.GetBitmap(wx.ART_FILE_SAVE, wx.ART_TOOLBAR, (80, 80))
                    button = IconButton(self.scroll_panel, None, "Save", 2000, save_bmp, -200, self)
                    button.HideButtonValue()
                    button.UnbindButtonMenu()
                    button.Bind(wx.EVT_BUTTON, self.save_button)
                    button.SetName('Save')
                    button.SetForegroundColour((0, 255, 0))
                    self.grid_sizer.Add(button, 0, wx.TOP, 5)
                elif i == 2 and main:
                    icon = self.resources.get_scaled_cache['ender_chest']
                    button = IconButton(self.scroll_panel, 'ender_chest', "Player EnderChest", 2000, icon, -201, self)
                    button.HideButtonValue()
                    button.UnbindButtonMenu()
                    button.SetName('EnderButton')
                    button.Bind(wx.EVT_BUTTON, self.ender_chest)
                    button.SetForegroundColour((0, 255, 0))
                    self.grid_sizer.Add(button, 0, wx.TOP, 5)
                else:
                    divider_line = wx.StaticLine(self.scroll_panel, style=wx.LI_HORIZONTAL)
                    self.grid_sizer.Add(divider_line, 0, wx.TOP, 15)
        if "Inventory Editor" in self.GetTitle():
            self.grid_sizer = wx.GridSizer(6, 9, -10, 5)

            for i in range(4):
                item = self.inventory.get('Armor', [None] * 4)[i]
                item_name = item["Name"].py_str[10:] if item and "Name" in item else ''
                display_name = self.resources.get(item_name, {}).get("display_name", "Empty")
                display_name = more_display_info(display_name, item)
                count = item.get("Count", 1) if item else 0


                # Try to get icon, fallback to NullBitmap
                icon_bitmap = self.resources.get_scaled_cache.get(item_name, wx.NullBitmap)

                button = IconButton(self.scroll_panel, item_name, display_name, count, icon_bitmap, i , self)
                button.HideButtonValue()
                button.Set_slot_map_key('Armor', i)
                self.grid_sizer.Add(button, 0, wx.CENTRE, 1)
                self.slot_map[('Armor' , i)] = button
                armor_buttons.append(button)

            middle_slots(4)

            offhand_item = next((item for item in self.inventory.get('Offhand', [])), None)
            item_name = offhand_item["Name"].py_str[10:] if offhand_item and "Name" in offhand_item else ''
            display_name = self.resources.get(item_name, {}).get("display_name", "Empty")
            display_name = more_display_info(display_name, offhand_item)
            count = offhand_item.get("Count", 1) if offhand_item else 0
            icon_bitmap = self.resources.get_scaled_cache.get(item_name)

            offhand_button = IconButton(self.scroll_panel, item_name, display_name, count, icon_bitmap, 0, self)

            offhand_button.SetBackgroundColour((0, 255, 0))

            self.grid_sizer.Add(offhand_button, 0, wx.ALIGN_TOP, 1)
            self.slot_map[('Offhand',0)] = offhand_button
            offhand_button.Set_slot_map_key('Offhand',0)
            range_order = list(range(9, 36)) + list(range(0, 9))
            for slot in range_order:
                item = next((i for i in self.inventory.get('Inventory', []) if i.get("Slot").py_int == slot), None)
                item_name = processes_item_iter_next(item)
                display_name = self.resources.get(item_name, {}).get("display_name", item_name)
                display_name = more_display_info(display_name, item)
                count = item.get("Count", 1) if item else 0
                icon_bitmap = self.resources.get_scaled_cache.get(item_name)
                if icon_bitmap:
                    icon_bitmap = icon_bitmap
                button = IconButton(self.scroll_panel, item_name, display_name, count, icon_bitmap, slot, self)

                if slot == 0:
                    middle_slots(9, main=False, not_extra=False)
                self.grid_sizer.Add(button, 0, wx.TOP, -15 if slot < 9 else 10)
                self.slot_map[('Inventory', slot)] = button
                button.Set_slot_map_key('Inventory', slot)
        else:
            CONTAINER_CONFIG = {
                "Bundle": {
                    "size": (1400, -1),
                    "grid": (0, 16),  # 0 rows = auto, 16 columns
                    "key": "storage_item_component_content",
                    "order": list(range(64)),
                    "middle": 16,
                },
                "Ender": {
                    "size": (805, 560),
                    "grid": (4, 9),
                    "key": "EnderChestInventory",
                    "order": list(range(27)),
                    "middle": 9,
                },
                "Shulker Box": {
                    # no explicit size = leave window default
                    "grid": (4, 9),
                    "key": "Items",
                    "order": list(range(27)),
                    "middle": 9,
                },
                "Dispenser": {
                    "size": (500, 555),
                    "grid": (4, 3),
                    "key": "Items",
                    "order": list(range(9)),
                    "middle": 3,
                },
                "Chest": {
                    # A single chest has 27 slots, arranged 3 rows × 9 columns
                    "grid": (4, 9),
                    "key": "Items",
                    "order": list(range(27)),
                    "middle": 9,
                },
                "Barrel": {
                    # Barrel also has 27 slots, 3 rows × 9 columns
                    "grid": (4, 9),
                    "key": "Items",
                    "order": list(range(27)),
                    "middle": 9,
                },
            }
            title = self.GetTitle()

            for keyword, cfg in CONTAINER_CONFIG.items():
                if keyword in title:
                    # 1) Apply size if given
                    if "size" in cfg:
                        self.SetSize(*cfg["size"])

                    # 2) Create the grid sizer
                    rows, cols = cfg["grid"]
                    self.grid_sizer = wx.GridSizer(rows, cols, 5, 5)

                    # 3) Pick the NBT key and slot order
                    key = cfg["key"]
                    range_order = cfg["order"]

                    # 4) Call your helper to center mid‐row slots
                    middle_slots(cfg["middle"], main=False)
                    break
            else:
                # Fallback if nothing matched
                raise ValueError(f"Unknown container type in title: {title}")

            for slot in range_order:
                item = next((i for i in self.inventory[key] if i.get("Slot").py_int == slot), None)

                item_name = processes_item_iter_next(item)
                display_name = self.resources.get(item_name, {}).get("display_name", "Empty")
                display_name = more_display_info(display_name, item)

                if not item:
                    display_name = "Empty"
                    count = 0
                    icon_bitmap = None
                else:
                    count = item.get("Count", 0)
                    icon_bitmap = self.resources.get_scaled_cache.get(item_name)
                    if icon_bitmap:
                        icon_bitmap = icon_bitmap

                button = IconButton(
                    self.scroll_panel,
                    item_name,
                    display_name,
                    count,
                    icon_bitmap,
                    slot,
                    self
                )

                self.grid_sizer.Add(button, 0, wx.BOTTOM, 10)
                self.slot_map[(key,slot)] = button
                button.Set_slot_map_key(key,slot)
        self.scroll_panel.SetSizer(self.grid_sizer)
        self.grid_sizer.Layout()
        self.scroll_panel.FitInside()
        self.scroll_panel.SetScrollRate(10, 10)
        self.scroll_panel.Layout()
        self.Layout()

class IconListCtrl(wx.Frame):
    def __init__(self, parent, title, data, slot):
        super().__init__(parent, title=title, size=(1110, 800), style=wx.DEFAULT_FRAME_STYLE | wx.STAY_ON_TOP)
        self.parent = parent
        self.data = data
        self.editor = self.data
        self.font = wx.Font(11, wx.FONTFAMILY_ROMAN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        self.SetFont(self.font)
        self.bmp = 0
        self.icon_size = 64
        self.panel = wx.Panel(self)
        self.list_ctrl = wx.ListCtrl(self.panel, style=wx.LC_ICON)
        self.image_list = wx.ImageList(self.icon_size, self.icon_size)
        self.list_ctrl.AssignImageList(self.image_list, wx.IMAGE_LIST_NORMAL)

        self.list_ctrl.SetForegroundColour((0, 255, 0))
        self.list_ctrl.SetBackgroundColour((0, 0, 0))

        self.drag_image =None
        self.dragging = False
        self.index_to_bedrock = {}
        self.all_items = []

        panel_sizer = wx.BoxSizer(wx.VERTICAL)
        panel_horz = wx.BoxSizer(wx.HORIZONTAL)
        self.button = wx.Button(self.panel, size=(100, 30), label="Filter")
        self.filterstring = wx.TextCtrl(self.panel, size=(100, 30), style=wx.TE_PROCESS_ENTER)

        self.list_ctrl.Bind(wx.EVT_LEFT_DOWN, self.OnMouseDown)
        self.list_ctrl.Bind(wx.EVT_MOTION, self.OnMouseMove)
        self.list_ctrl.Bind(wx.EVT_LEFT_UP, self.OnMouseUp)

        self.button.Bind(wx.EVT_BUTTON, self.filter_string)
        self.filterstring.Bind(wx.EVT_TEXT_ENTER, self.filter_string)

        panel_horz.Add(self.button)
        panel_horz.Add(self.filterstring)
        panel_sizer.Add(panel_horz)
        panel_sizer.Add(self.list_ctrl, 3, flag=wx.EXPAND)
        self.panel.SetSizerAndFit(panel_sizer)

        self.Bind(wx.EVT_CLOSE, self.on_close)
        self.item_index = -1
        self.load_all_items()
        self.Layout()

    def OnMouseMove(self, event):
        if hasattr(self, "drag_image") and event.Dragging() and event.LeftIsDown():
            self.drag_image.Move(event.GetPosition())

    def OnMouseDown(self, event):
        pos = event.GetPosition()
        index = self.list_ctrl.HitTest(pos)[0]

        if index == wx.NOT_FOUND:
            return

        bedrock_id = self.index_to_bedrock.get(index)
        if not bedrock_id:
            return

        DRAG_DATA_SOURCE['id'] = bedrock_id

        image_index = self.list_ctrl.GetItem(index).GetImage()
        bmp = self.image_list.GetBitmap(image_index)

        self.dragged_index = index
        self.drag_image = wx.DragImage(bmp)
        self.drag_image.BeginDrag((0, 0), self.list_ctrl, fullScreen=True)
        self.drag_image.Move(pos)
        self.drag_image.Show()

        self.list_ctrl.CaptureMouse()

    def OnMouseUp(self, evt):

        if hasattr(self, "drag_image"):
            self.drag_image.Hide()

        if self.list_ctrl.HasCapture():
            try:
                self.list_ctrl.ReleaseMouse()
            except Exception:
                pass  # swallow any error

        if hasattr(self, "drag_image"):
            try:
                self.drag_image.EndDrag()
            except Exception:
                pass
            finally:
                del self.drag_image


        screen_pt = self.list_ctrl.ClientToScreen(evt.GetPosition())
        if self.button.GetScreenRect().Contains(screen_pt):
            bmp = self.image_list.GetBitmap(self.dragged_index)
            self.button.SetBitmap(bmp)
            self.button.SetToolTip(self.dragged_id)

        if hasattr(self, "dragged_index"):
            del self.dragged_index
        if hasattr(self, "dragged_id"):
            del self.dragged_id

        # Here, simulate a successful drop by directly handling the position

    def on_close(self, event):
        self.HideWithEffect(effect=wx.SHOW_EFFECT_BLEND)

    def update_data(self, data):
        self.data = data

    def update_slot(self, slot):
        self.inv_slot = slot[1]
        self.key_slot = slot

    def load_all_items(self):
        self.all_items.clear()
        self.image_list.RemoveAll()
        self.list_ctrl.DeleteAllItems()

        scaled_cache = self.data.resources.get_scaled_cache  # Cache shortcut
        json_data = self.data.resources.get_json_data

        for bedrock_id, info in json_data.items():
            display_name = info.get('display_name', '')
            bmp = scaled_cache.get(bedrock_id)
            if bmp:
                icon_index = self.image_list.Add(bmp)
                self.all_items.append((bedrock_id, display_name, icon_index))

        self.show_filtered_items()

    def show_filtered_items(self, filter_text=''):
        self.list_ctrl.DeleteAllItems()
        self.index_to_bedrock.clear()
        filter_text = filter_text.lower()

        for bedrock_id, display_name, icon_index in self.all_items:
            if not filter_text or filter_text in display_name.lower():
                index = self.list_ctrl.InsertItem(self.list_ctrl.GetItemCount(), display_name, icon_index)
                self.index_to_bedrock[index] = bedrock_id

    def filter_string(self, _):
        filter_val = self.filterstring.GetValue()
        self.show_filtered_items(filter_val)

    def create_catalog_menu(self):
        for category, item_range in categories.items():
            menu_item = wx.MenuItem(self.catalog_menu, wx.ID_ANY, category)
            self.catalog_menu.Append(menu_item)
            self.Bind(wx.EVT_MENU, self.create_filter_callback(category, item_range), menu_item)

    def create_filter_callback(self, category, item_range):
        def filter_items(event):
            if category == "All":
                self.show_filtered_items('')
            else:
                valid_keys = [key for i, key in enumerate(self.data.resources.get_json_data.keys()) if i in item_range]
                self.show_filtered_items_for_keys(valid_keys)
        return filter_items

    def show_filtered_items_for_keys(self, allowed_keys):
        self.list_ctrl.DeleteAllItems()
        self.index_to_bedrock.clear()
        for bedrock_id, display_name, icon_index in self.all_items:
            if bedrock_id in allowed_keys:
                index = self.list_ctrl.InsertItem(self.list_ctrl.GetItemCount(), display_name, icon_index)
                self.index_to_bedrock[index] = bedrock_id

class TAGEditor(wx.Frame):
    def __init__(self, parent,title, _self, last_key, slot):
        super().__init__(parent, title=title, size=(600, 500), style=wx.DEFAULT_FRAME_STYLE | wx.STAY_ON_TOP)
        self._self = _self
        title = _self.Parent.Parent.GetTitle()
        # Determine the slot number, ensuring it is valid
        key, slot = _self.Get_slot_map_key()
        keys = _self.editor.keys + [key]
        current_nbt = _self.editor.selected_player[keys]
        if key != 'Armor' and key  != 'Offhand':
            for i, x in enumerate(current_nbt):
                if x['Slot'].py_int == slot:
                    slot = i

        self.nbt_data = current_nbt[slot]
        panel = scrolled.ScrolledPanel(self, style=wx.VSCROLL)
        panel.SetScrollRate(5, 5)
        self.font = wx.Font(20, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        snbt_text = self.nbt_data.to_snbt(4)

        self.text_ctrl = wx.TextCtrl(
            panel,
            value=snbt_text,
            style=wx.TE_MULTILINE
        )
        self.text_ctrl.SetFont(self.font)
        self.text_ctrl.SetForegroundColour((0, 255, 0))
        self.text_ctrl.SetBackgroundColour((0, 0, 0))
        self.sizer.Add(self.text_ctrl, 1, wx.EXPAND | wx.ALL, 10)

        save_button = wx.Button(panel, label="Save SNBT")
        save_button.Bind(wx.EVT_BUTTON, self.on_save)
        self.sizer.Add(save_button, 0, wx.CENTER | wx.BOTTOM, 10)

        panel.SetSizer(self.sizer)
        panel.Layout()

        self.Show()


    def on_save(self, event):
        title = self._self.Parent.Parent.GetTitle()
        data = self.text_ctrl.GetValue()
        nbt = from_snbt(data)
        key, slot = self._self.Get_slot_map_key()
        keys = self._self.editor.keys + [key]
        # for i, x in enumerate(self._self.editor.selected_player[keys]):
        #     i += 32
        #     print(i, x['tag']['Patterns'][0]['Pattern'].py_str)
        current_nbt = self._self.editor.selected_player[keys]

        if "Shulker Box" in title or "Dispenser" in title:
            if len(current_nbt) > 0:
                for i, x in enumerate(current_nbt):
                    if x['Slot'].py_int == slot:
                        slot = i
                        break
        current_nbt[slot] = nbt

        self._self.editor.selected_player.save_player()
        self._self.SetTagData(nbt)
        # self._self.onclick_get_set_tag_data
        self._self.Refresh()

COLOR_CODES = {
    "Dark Aqua": ("§3", wx.Colour(0, 139, 139)),
    "Gold": ("§6", wx.Colour(255, 215, 0)),
    "Red": ("§c", wx.Colour(255, 0, 0)),
    "Green": ("§a", wx.Colour(0, 255, 0)),
    "Blue": ("§9", wx.Colour(0, 0, 255)),
    "White": ("§f", wx.Colour(255, 255, 255)),
    "Yellow": ("§e", wx.Colour(255, 255, 0)),
    "Gray": ("§7", wx.Colour(128, 128, 128)),
    "Black": ("§0", wx.Colour(0, 0, 0)),
    "Dark Red": ("§4", wx.Colour(139, 0, 0)),
    "Dark Green": ("§2", wx.Colour(0, 100, 0)),
    "Dark Blue": ("§1", wx.Colour(0, 0, 139)),
    "Dark Gray": ("§8", wx.Colour(64, 64, 64)),
    "Light Purple": ("§d", wx.Colour(255, 182, 193)),
    "Aqua": ("§b", wx.Colour(0, 255, 255)),
}
STYLE_CODES = {
    "Bold": ("§l", lambda fmt: fmt.SetFontWeight(wx.FONTWEIGHT_BOLD)),
    "Italic": ("§o", lambda fmt: fmt.SetFontStyle(wx.FONTSTYLE_ITALIC)),
    "Underline": ("§n", lambda fmt: fmt.SetFontUnderlined(True)),
    "Strikethrough": ("§m", lambda fmt: fmt.SetTextEffectFlags(wx.TEXT_ATTR_EFFECT_STRIKETHROUGH) or
                                      fmt.SetTextEffects(wx.TEXT_ATTR_EFFECT_STRIKETHROUGH)),
    "Obfuscated": ("§k", None),  # Handled separately
}

class BedrockNameTagAndLoreEditor(wx.Frame):
    def __init__(self, _self, ):
        super().__init__(None, title="Bedrock Name and Lore Editor", size=(650, 330),style=wx.DEFAULT_FRAME_STYLE | wx.STAY_ON_TOP)
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        self._self = _self
        title = _self.Parent.Parent.GetTitle()
        # Determine the slot number, ensuring it is valid
        key, slot = _self.Get_slot_map_key()
        keys = _self.editor.keys + [key]

        current_nbt = _self.editor.selected_player[keys]
        if key != 'Armor' and key  != 'Offhand':
            for i, x in enumerate(current_nbt):
                if x['Slot'].py_int == slot:
                    slot = i
        lore = None
        name = None
        self.nbt_data = current_nbt[slot]
        if self.nbt_data.get('tag', None):
            if self.nbt_data.get('tag').get("display", None):
                lore = self.nbt_data.get('tag', {}).get("display", {}).get('Lore', None)
                name = self.nbt_data.get('tag', {}).get("display", {}).get('Name', None)
            else:
                self.nbt_data['tag']['display'] = CompoundTag({})
        else:
            self.nbt_data['tag'] =CompoundTag({})
            self.nbt_data['tag']['display'] = CompoundTag({})

        if lore:
            self.lore = lore.py_data
        if name:
            self.name = name.py_str
        # Item Name
        main_sizer.Add(wx.StaticText(panel, label="Item Name:"), 0, wx.ALL, 5)
        self.name_input = rt.RichTextCtrl(panel, style=wx.VSCROLL | wx.HSCROLL | wx.TE_MULTILINE | wx.NO_BORDER,
                                          size=(-1, 30))
        self.name_input.SetFont(wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        main_sizer.Add(self.name_input, 0, wx.EXPAND | wx.ALL, 5)

        # Lore Editor
        main_sizer.Add(wx.StaticText(panel, label="Lore Editor:"), 0, wx.ALL, 5)
        self.lore_input = rt.RichTextCtrl(panel, style=wx.VSCROLL | wx.HSCROLL | wx.TE_MULTILINE | wx.NO_BORDER,
                                          size=(-1, 80))
        self.lore_input.SetFont(wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        main_sizer.Add(self.lore_input, 0, wx.EXPAND | wx.ALL, 5)

        # Format Bar
        format_bar = wx.BoxSizer(wx.HORIZONTAL)
        self.color_choice = wx.Choice(panel, choices=list(COLOR_CODES.keys()))
        self.color_choice.SetSelection(0)
        format_bar.Add(wx.StaticText(panel, label="Color:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        format_bar.Add(self.color_choice, 0, wx.RIGHT, 10)

        self.style_checkboxes = {}


        for style in STYLE_CODES:
            cb = wx.CheckBox(panel, label=style)
            self.style_checkboxes[style] = cb
            format_bar.Add(cb, 0, wx.RIGHT, 5)

        apply_btn = wx.Button(panel, label="Apply to Selection")
        apply_btn.Bind(wx.EVT_BUTTON, self.on_apply_format)
        format_bar.Add(apply_btn, 0, wx.LEFT, 10)
        main_sizer.Add(format_bar, 0, wx.EXPAND | wx.ALL, 5)

        # Preview
        main_sizer.Add(wx.StaticText(panel, label="Preview:"), 0, wx.LEFT | wx.TOP, 5)
        self.preview = wx.StaticText(panel, label="", style=wx.ALIGN_LEFT)
        main_sizer.Add(self.preview, 0, wx.ALL, 5)

        # Generate JSON
        gen_btn = wx.Button(panel, label="Save Name and Lore")
        gen_btn.Bind(wx.EVT_BUTTON, self.on_generate)
        main_sizer.Add(gen_btn, 0, wx.CENTER | wx.ALL, 5)

        # Output Box
        # main_sizer.Add(wx.StaticText(panel, label="Output JSON:"), 0, wx.LEFT | wx.TOP, 5)
        # self.output_box = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY)
        # main_sizer.Add(self.output_box, 1, wx.EXPAND | wx.ALL, 5)

        panel.SetSizer(main_sizer)
        if name:
            self.load_formatted_text(self.name_input, self.name)
        if lore:
            for line in self.lore:
                self.load_formatted_text(self.lore_input, line.py_str)
                self.lore_input.WriteText("\n")

        self.Centre()
        self.Show()

    def load_formatted_text(self, ctrl, formatted_text):
        ctrl.Clear()
        pos = 0
        current_style = rt.RichTextAttr()

        i = 0
        while i < len(formatted_text):
            if formatted_text[i] == '§' and i + 1 < len(formatted_text):
                code = formatted_text[i + 1]
                i += 2
                if code in "0123456789abcdef":
                    # Apply color
                    for name, (mc_code, wx_col) in COLOR_CODES.items():
                        if mc_code[1] == code:
                            current_style.SetTextColour(wx_col)
                            break
                elif code == 'l':
                    current_style.SetFontWeight(wx.FONTWEIGHT_BOLD)
                elif code == 'o':
                    current_style.SetFontStyle(wx.FONTSTYLE_ITALIC)
                elif code == 'n':
                    current_style.SetFontUnderlined(True)
                elif code == 'm':
                    current_style.SetTextEffectFlags(wx.TEXT_ATTR_EFFECT_STRIKETHROUGH)
                    current_style.SetTextEffects(wx.TEXT_ATTR_EFFECT_STRIKETHROUGH)
                elif code == 'r':
                    current_style = rt.RichTextAttr()  # Reset formatting
                continue
            else:
                ctrl.BeginStyle(current_style)
                ctrl.WriteText(formatted_text[i])
                ctrl.EndStyle()
                i += 1

    def on_apply_format(self, event):
        color_name = self.color_choice.GetStringSelection()
        color_code, wx_color = COLOR_CODES[color_name]

        fmt = rt.RichTextAttr()
        fmt.SetTextColour(wx_color)

        for style, (code, applier) in STYLE_CODES.items():
            if self.style_checkboxes[style].GetValue() and applier:
                applier(fmt)

        for ctrl in [self.name_input, self.lore_input]:
            start, end = ctrl.GetSelectionRange()
            if start == end:
                start, end = 0, ctrl.GetLastPosition()
            ctrl.SetStyle(start, end, fmt)

    def on_generate(self, event):
        name_text = self.process_richtext(self.name_input, single_line=True)
        lore_lines = self.process_richtext(self.lore_input, single_line=False)

        data = CompoundTag({"display": CompoundTag ({
                "Name": StringTag(name_text),
                "Lore": ListTag([StringTag(x) for x in lore_lines])
            })})

        self.preview.SetLabel(name_text + "\n" + "\n".join(lore_lines))


        self.nbt_data['tag']['display'] = data['display']
    def process_richtext(self, ctrl, single_line=False):
        result = []
        pos = 0
        end = ctrl.GetLastPosition()
        current_line = ""
        last_format = None

        while pos < end:
            attr = rt.RichTextAttr()
            ctrl.GetStyle(pos, attr)
            char = ctrl.GetRange(pos, pos + 1)

            if char == "\n" and not single_line:
                result.append(current_line)
                current_line = ""
                last_format = None
                pos += 1
                continue

            prefix = ""
            if not last_format or attr != last_format:
                if attr.HasTextColour():
                    prefix += self.get_code_by_color(attr.GetTextColour()) or ""

                if attr.GetFontWeight() == wx.FONTWEIGHT_BOLD:
                    prefix += STYLE_CODES["Bold"][0]
                if attr.GetFontStyle() == wx.FONTSTYLE_ITALIC:
                    prefix += STYLE_CODES["Italic"][0]
                if attr.GetFontUnderlined():
                    prefix += STYLE_CODES["Underline"][0]
                if attr.GetTextEffectFlags() & wx.TEXT_ATTR_EFFECT_STRIKETHROUGH:
                    prefix += STYLE_CODES["Strikethrough"][0]
                # Obfuscated is simulated but applied to full line at end

                last_format = attr

            current_line += prefix + char
            pos += 1

        if current_line:
            if self.style_checkboxes["Obfuscated"].GetValue():
                current_line = self.apply_obfuscation(current_line)
            result.append(current_line)

        return result[0] if single_line else result

    def apply_obfuscation(self, text):
        return ''.join(random.choice([c.upper(), c.lower()]) if c.isalpha() else c for c in text)

    def get_code_by_color(self, wx_color):
        for _, (code, color) in COLOR_CODES.items():
            if wx_color == color:
                return code
        return ""
class ItemTools:
    def __init__(self, parent):
        self.parent = parent
        self.icon_resources = IconResources()

    def copy_tag(self, _self):
        key, slot_number = _self.Get_slot_map_key()
        keys = _self.editor.keys + [key]

        current_nbt_list = _self.editor.selected_player[keys]

        # Try to find the item at the matching slot number
        if keys[0] in ('Armor', 'Offhand'):
            CLIP_BOARD['COPY'] = current_nbt_list[slot_number]
        else:
            for item in current_nbt_list:
                if item['Slot'].py_int == slot_number:
                    CLIP_BOARD['COPY'] = item
                    return

        # If nothing matched, don't copy anything
        #             CLIP_BOARD['COPY'] = None

    def paste_tag(self, _self):
        key, slot_number = _self.Get_slot_map_key()
        keys = _self.editor.keys + [key]
        current_nbt_list = _self.editor.selected_player[keys]

        copy_nbt = CLIP_BOARD.get('COPY')
        if not copy_nbt:
            return  # Nothing to paste

        bedrock_id = copy_nbt['Name'].py_str.split(':')[1]
        slot_index = None

        # Try to find an existing item at the same slot
        for i, item in enumerate(current_nbt_list):
            if item['Slot'].py_int == slot_number:
                slot_index = i
                break

        # Construct a new compound tag for insertion
        new_tag = CompoundTag({
            "Name": copy_nbt['Name'],
            "Damage": copy_nbt['Damage'],
            "Count": copy_nbt['Count'],
            "Slot": ByteTag(slot_number),
            "tag": copy_nbt.get('tag', CompoundTag({}))
        })

        _self.SetValue(int(copy_nbt['Count']))
        title = _self.Parent.Parent.GetTitle()

        # Append or replace
        if slot_index is not None:
            current_nbt_list[slot_index] = new_tag
        else:
            current_nbt_list.append(new_tag)

        # Update visual icon
        display_name = self.icon_resources.get_json_data[bedrock_id]['display_name']
        icon = self.icon_resources.get_scaled_cache[bedrock_id]
        _self.SetBitmap(icon, display_name)
        _self.button.SetName(bedrock_id)

        _self.Layout()
        _self.Refresh()

    def move_tag(self, _self):  # Not really need
        keys = _self.editor.keys + list(_self.Get_slot_map_key())
        current_nbt = _self.editor.selected_player[keys]

        print(current_nbt)

        copy_nbt = CLIP_BOARD['COPY']

        bedrock_id = copy_nbt['Name'].py_str.split(':')[1]
        slot = keys[-1]

        copy_nbt['Slot'] = ByteTag(slot)
        _self.SetValue(int(copy_nbt['Count']))
        title = _self.Parent.Parent.GetTitle()

        display_name = self.icon_resources.get_json_data[bedrock_id]['display_name']
        icon = self.icon_resources.get_scaled_cache[bedrock_id]
        _self.SetBitmap(icon, display_name)
        _self.editor.selected_player[keys] = copy_nbt

        _self.button.SetName(bedrock_id)
        _self.editor.selected_player.save_player()
        _self.Layout()
        _self.Refresh()

    def delete_slot(self, _self):
        _self.bedrock_id = ''

        _self.button.SetName('Empty')
        # _self.tag_data = CompoundTag({
        #     'Name': StringTag(""),
        #     'Count': ByteTag(0),
        #     'Damage': ShortTag(0),
        #     'Slot': ByteTag(_self.slot),
        #     'WasPickedUp': ByteTag(0),
        # 'tag': CompoundTag({
        #     'Damage' : ShortTag(0)
        # })})
        _self.clear_bitmap()
        _self.SetBitmap(wx.NullBitmap, "Empty")
        _self.count_box.SetValue("0")
        _self.Close()
        _self.Layout()
        _self.Refresh()

        # _self.onclick_get_set_tag_data()
        _self.Layout()
        _self.Refresh()

    def make_unbreakable(self, _self):
        keys = _self.editor.keys + list(_self.Get_slot_map_key())
        last_data = _self.editor.selected_player[keys]

        tag = last_data.get('tag', CompoundTag({}))

        if 'Unbreakable' in tag:
            tag.pop('Unbreakable')
        else:
            tag['Unbreakable'] = ByteTag(1)

    def keep_on_death(self, _self):
        keys = _self.editor.keys + list(_self.Get_slot_map_key())
        last_data = _self.editor.selected_player[keys]

        tag = last_data.get('tag', CompoundTag({}))

        if 'minecraft:keep_on_death' in tag:
            tag.pop('minecraft:keep_on_death')
        else:
            tag['minecraft:keep_on_death'] = ByteTag(1)

    def edit_add_armor_trims(self, _self):
        # Reverse dictionary for easy lookup
        reversed_trims_dict = {v: k for k, v in trims_dict.items()}
        reversed_color_dict = {v: k for k, v in custom_color_dict.items()}
        reversed_material_dict = {v: k for k, v in material_dict.items()}

        def save_data(evt):
            selected_trim = trim_choice.GetStringSelection()
            selected_material = material_choice.GetStringSelection()
            selected_color = color_choice.GetStringSelection()
            # Get the corresponding values from the dictionaries
            trim_key = trims_dict.get(selected_trim, None)
            material_key = material_dict.get(selected_material, None)
            color_key = custom_color_dict.get(selected_color, None)

            # If any value is None, we return early or handle the error as needed
            if not trim_key or not material_key:
                print("Error: Invalid selection(s).")
                return

            # Example of how to modify the current NBT data (assuming the data is structured correctly)
            keys = _self.editor.keys + list(_self.Get_slot_map_key())
            current_nbt_data = _self.editor.selected_player[keys]
            # current_nbt_data = _self.GetTheData[-1]  # Fetch the NBT data
            if current_nbt_data.get('tag', None):
                current_nbt_data['tag']['Trim'] = CompoundTag({
                    'Material': StringTag(material_key),
                    'Pattern': StringTag(trim_key)
                })
            else:
                current_nbt_data['tag'] = CompoundTag({'Trim': CompoundTag({
                    'Material': StringTag(material_key),
                    'Pattern': StringTag(trim_key)
                })})

            # Set the color value if it's available
            if color_key:
                current_nbt_data['tag']['customColor'] = IntTag(color_key)
            else:
                current_nbt_data['tag'].pop('customColor', None)


            _self.editor.selected_player.save_player()
            panel.Close()
        def on_remove_all(evt):

            if 'tag' in current_nbt_data:
                current_nbt_data['tag'].pop('Trim', None)
                current_nbt_data['tag'].pop('customColor', None)

            _self.editor.selected_player.save_player()
            panel.Close()

        keys = _self.editor.keys + list(_self.Get_slot_map_key())

        current_nbt_data = _self.editor.selected_player[keys]
        panel = wx.Frame(_self, title="Edit Armor Trim", size=(400, 400),
                         style=wx.DEFAULT_FRAME_STYLE | wx.STAY_ON_TOP)
        sizer = wx.BoxSizer(wx.VERTICAL)
        remove_all_btn = wx.Button(panel, label="Clear All Trims")
        remove_all_btn.Bind(wx.EVT_BUTTON, on_remove_all)
        sizer.Add(remove_all_btn)
        # Trim Selection
        trim_label = wx.StaticText(panel, label="Select Trim")
        sizer.Add(trim_label, 0, wx.ALL, 5)
        trim_choice = wx.Choice(panel, choices=list(trims_dict.keys()))

        # Set current trim value if available
        current_trim = current_nbt_data.get('tag', {}).get('Trim', {}).get('Pattern', None)

        if current_trim and current_trim.py_str in trims_dict.values():
            trim_choice.SetStringSelection(reversed_trims_dict.get(current_trim.py_str, ""))
        else:
            trim_choice.SetSelection(-1)  # Default to first item if no current value
        sizer.Add(trim_choice, 0, wx.ALL, 5)

        # Material Selection
        material_label = wx.StaticText(panel, label="Select Material")
        sizer.Add(material_label, 0, wx.ALL, 5)
        material_choice = wx.Choice(panel, choices=list(material_dict.keys()))

        # Set current material value if available
        current_material = current_nbt_data.get('tag', {}).get('Trim', {}).get('Material', None)
        if current_material and current_material.py_str in material_dict.values():
            material_choice.SetStringSelection(current_material.py_str)
        else:
            material_choice.SetSelection(-1)  # Default to first item if no current value
        sizer.Add(material_choice, 0, wx.ALL, 5)

        # Custom Color Selection

        color_label = wx.StaticText(panel, label="Select Custom Color")
        sizer.Add(color_label, 0, wx.ALL, 5)
        color_choice = wx.Choice(panel, choices=list(custom_color_dict.keys()))
        color_choice.SetSelection(-1)

        # Set current color value if available
        current_color = current_nbt_data.get('tag', {}).get('customColor', None)
        if current_color and current_color.py_int in reversed_color_dict:
            color_name = reversed_color_dict[current_color.py_int]
            color_choice.SetStringSelection(color_name)  # Set the color name based on the hex value
        else:
            color_choice.SetSelection(-1)  # Default to first item if no current value
        sizer.Add(color_choice, 0, wx.ALL, 5)
        if not "leather" in _self.GetTheData[1]:
            color_choice.Hide()

        # Save Button

        save_button = wx.Button(panel, label="Save Changes")
        save_button.Bind(wx.EVT_BUTTON, save_data)
        sizer.Add(save_button, 0, wx.ALL, 10)

        panel.SetSizer(sizer)
        panel.Centre()
        panel.Fit()
        panel.Show()

    def edit_fireworks_data(self, _self):
        # self.onclick_get_set_tag_data()
        title = _self.Parent.Parent.GetTitle()
        # Determine the slot number, ensuring it is valid

        keys = _self.editor.keys + list(_self.Get_slot_map_key())
        current_nbt = _self.editor.selected_player[keys]

        firework_data = current_nbt

        frame = wx.Frame(_self, title="Edit Fireworks Explosions", size=(600, 400),
                         style=wx.DEFAULT_FRAME_STYLE | wx.STAY_ON_TOP)
        frame.Freeze()

        scroll_panel = wx.ScrolledWindow(frame, style=wx.VSCROLL)
        scroll_panel.SetScrollRate(5, 5)
        scroll_panel.SetBackgroundColour(wx.Colour(255, 255, 255))

        main_sizer = wx.BoxSizer(wx.VERTICAL)
        scroll_panel.SetSizer(main_sizer)

        frame_sizer = wx.BoxSizer(wx.VERTICAL)
        frame_sizer.Add(scroll_panel, 1, wx.EXPAND)
        frame.SetSizer(frame_sizer)
        colors = {
            0: "Black", 1: "Red", 2: "Green", 3: "Brown", 4: "Blue",
            5: "Purple", 6: "Cyan", 7: "Light Gray", 8: "Gray", 9: "Pink",
            10: "Lime", 11: "Yellow", 12: "Light Blue", 13: "Magenta",
            14: "Orange", 15: "White"
        }
        firework_types = {
            0: "Small Ball", 1: "Large Ball", 2: "Star", 3: "Creeper", 4: "Burst"
        }
        explosion_rows = []
        scroll_panel.Freeze()
        # Flight input
        flight_sizer = wx.BoxSizer(wx.HORIZONTAL)
        flight_sizer.Add(wx.StaticText(scroll_panel, label="Flight:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        flight_input = wx.SpinCtrl(scroll_panel, min=1, max=127, initial=2)
        flight_sizer.Add(flight_input, 0, wx.RIGHT, 10)
        main_sizer.Add(flight_sizer, 0, wx.ALL, 5)

        def create_color_section(label, parent_panel, picker_list):
            section_sizer = wx.BoxSizer(wx.VERTICAL)
            header = wx.BoxSizer(wx.HORIZONTAL)

            header_label = wx.StaticText(parent_panel, label=f"{label} Colors:")
            add_btn = wx.Button(parent_panel, label="+", size=(25, 25))
            remove_btn = wx.Button(parent_panel, label="-", size=(25, 25))
            listbox = wx.ListBox(parent_panel, style=wx.LB_SINGLE)

            def add_color(evt=None):
                dlg = wx.SingleChoiceDialog(parent_panel, f"Choose a {label.lower()} color", "Colors",
                                            list(colors.values()))
                if dlg.ShowModal() == wx.ID_OK:
                    choice = dlg.GetStringSelection()
                    listbox.Append(choice)
                dlg.Destroy()

            def remove_color(evt=None):
                sel = listbox.GetSelection()
                if sel != wx.NOT_FOUND:
                    listbox.Delete(sel)

            add_btn.Bind(wx.EVT_BUTTON, add_color)
            remove_btn.Bind(wx.EVT_BUTTON, remove_color)

            header.Add(header_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
            header.Add(add_btn, 0, wx.RIGHT, 2)
            header.Add(remove_btn, 0)

            section_sizer.Add(header, 0, wx.TOP | wx.LEFT | wx.RIGHT, 5)
            section_sizer.Add(listbox, 1, wx.EXPAND | wx.ALL, 5)

            picker_list.append(listbox)

            return section_sizer

        def add_explosion(evt=None):
            box = wx.StaticBox(scroll_panel, label="Explosion")
            container = wx.StaticBoxSizer(box, wx.VERTICAL)

            color_pickers = []
            fade_pickers = []

            color_fade_sizer = wx.BoxSizer(wx.HORIZONTAL)
            color_fade_sizer.Add(create_color_section("Color", scroll_panel, color_pickers), 1,
                                 wx.EXPAND | wx.RIGHT,
                                 10)
            color_fade_sizer.Add(create_color_section("Fade", scroll_panel, fade_pickers), 1, wx.EXPAND)
            container.Add(color_fade_sizer, 0, wx.EXPAND | wx.ALL, 5)

            # Options: type, flicker, trail
            options = wx.FlexGridSizer(1, 5, 5, 5)
            flicker_cb = wx.CheckBox(scroll_panel, label="Flicker")
            trail_cb = wx.CheckBox(scroll_panel, label="Trail")
            type_choice = wx.Choice(scroll_panel, choices=list(firework_types.values()))
            type_choice.SetSelection(0)
            remove_btn = wx.Button(scroll_panel, label="Remove Explosion")

            def remove(evt):
                main_sizer.Hide(container)
                main_sizer.Remove(container)
                explosion_rows.remove(container)
                scroll_panel.Layout()
                scroll_panel.FitInside()

            remove_btn.Bind(wx.EVT_BUTTON, remove)

            options.AddMany([
                (wx.StaticText(scroll_panel, label="Type:"), 0, wx.ALIGN_CENTER_VERTICAL),
                (type_choice, 0),
                (flicker_cb, 0),
                (trail_cb, 0),
                (remove_btn, 0)
            ])
            container.Add(options, 0, wx.ALL, 5)

            # Store controls
            container.color_pickers = color_pickers
            container.fade_pickers = fade_pickers
            container.flicker = flicker_cb
            container.trail = trail_cb
            container.type_choice = type_choice

            main_sizer.Add(container, 0, wx.EXPAND | wx.ALL, 5)
            explosion_rows.append(container)

            scroll_panel.Layout()
            scroll_panel.FitInside()

        def save_fireworks(evt):
            explosion_list = ListTag()

            for row in explosion_rows:
                color_ids = [k for box in row.color_pickers for k, v in colors.items() if v in box.GetItems()]
                fade_ids = [k for box in row.fade_pickers for k, v in colors.items() if v in box.GetItems()]

                compound = CompoundTag({
                    'FireworkColor': ByteArrayTag(color_ids),
                    'FireworkFade': ByteArrayTag(fade_ids),
                    'FireworkFlicker': ByteTag(1 if row.flicker.GetValue() else 0),
                    'FireworkTrail': ByteTag(1 if row.trail.GetValue() else 0),
                    'FireworkType': ByteTag(row.type_choice.GetSelection())
                })
                explosion_list.append(compound)

            firework_tag = CompoundTag({
                'Fireworks': CompoundTag({
                    'Explosions': explosion_list,
                    'Flight': ByteTag(flight_input.GetValue())
                })
            })


            current_nbt['tag'] = firework_tag
            # nbt = self.editor.selected_player[self.editor.keys]
            _self.editor.selected_player.save_player()
            frame.Close()
        # Buttons
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        add_btn = wx.Button(scroll_panel, label="Add Explosion")
        save_btn = wx.Button(scroll_panel, label="Save")
        add_btn.Bind(wx.EVT_BUTTON, add_explosion)
        save_btn.Bind(wx.EVT_BUTTON, save_fireworks)
        btn_sizer.Add(add_btn, 0, wx.ALL, 5)
        btn_sizer.Add(save_btn, 0, wx.ALL, 5)
        main_sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER)

        # Prefill if existing data
        if firework_data and "Fireworks" in str(firework_data):
            fw = firework_data['tag']["Fireworks"]
            flight_input.SetValue(fw.get("Flight", ByteTag(1)).py_data)

            for explosion in fw.get("Explosions", []):
                add_explosion()
                container = explosion_rows[-1]

                container.type_choice.SetSelection(explosion.get("FireworkType", ByteTag(0)).py_data)
                container.flicker.SetValue(bool(explosion.get("FireworkFlicker", ByteTag(0))))
                container.trail.SetValue(bool(explosion.get("FireworkTrail", ByteTag(0))))

                def populate_listbox(box, color_data):
                    for color_id in color_data:
                        if color_id in colors:
                            box.Append(colors[color_id])

                for box in container.color_pickers:
                    populate_listbox(box, explosion.get("FireworkColor", ByteArrayTag([])).py_data)

                for box in container.fade_pickers:
                    populate_listbox(box, explosion.get("FireworkFade", ByteArrayTag([])).py_data)
        else:
            add_explosion()

        scroll_panel.Thaw()
        frame.Layout()
        frame.Centre()
        frame.Thaw()
        frame.Show()

    def edit_enchants(self, _self):
        from wx import CheckBox, TextCtrl, Button, StaticText, BoxSizer, Frame, Panel, EVT_CHECKBOX, EVT_BUTTON, \
            ALL, \
            VERTICAL, HORIZONTAL
        font = wx.Font(11, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        BLACK = wx.Colour(0, 0, 0)
        GREEN = wx.Colour(0, 255, 0)

        def on_check(evt):
            """Handle checkbox click to enable/disable level inputs."""
            checkbox = evt.GetEventObject()
            idx = checkbox.GetId()
            level_ctrl = enchant_level_inputs.get(idx)
            if level_ctrl:
                level_ctrl.Enable(checkbox.IsChecked())
        def unselect(evt):
            """Uncheck all enchants and disable their level inputs."""
            for name, cb in enchant_checkboxes.items():
                cb.SetValue(False)
                lvl_ctrl = enchant_level_inputs.get(cb.GetId())
                if lvl_ctrl:
                    lvl_ctrl.SetValue("0")
                    lvl_ctrl.Enable(False)

        def select_best(evt):
            """Select the best enchantments based on the item type."""
            item_type = get_item_type(current_nbt['Name'].py_str.split(':')[1])
            allowed_ids = valid_enchants.get(item_type, [])
            for ench_id in allowed_ids:
                name = enchantments[ench_id]
                cb = enchant_checkboxes.get(name)
                if cb:
                    cb.SetValue(True)  # Check the box
                    enchant_level_inputs[cb.GetId()].SetValue(str(max_levels.get(ench_id, 1)))  # Set level
                    enchant_level_inputs[cb.GetId()].Enable(True)  # Enable the input

        def save_data(evt):
            """Save selected enchantments and their levels to NBT."""
            tag_list = ListTag()
            for name, cb in enchant_checkboxes.items():
                if cb.IsChecked():
                    ench_id = [k for k, v in enchantments.items() if v == name][0]
                    lvl = int(enchant_level_inputs[cb.GetId()].GetValue())
                    tag_list.append(CompoundTag({'id': ShortTag(ench_id), 'lvl': ShortTag(lvl)}))

            # Retrieve the current NBT data
            key, slot = _self.Get_slot_map_key()
            keys = _self.editor.keys + [key]
            current_nbt = _self.editor.selected_player[keys]

            title = _self.Parent.Parent.GetTitle()
            panel.Close()

            if any(ct in title for ct in CONTAINER_TYPES):
                if len(current_nbt) > 0:
                     for i, x in enumerate(current_nbt):
                         if x['Slot'].py_int == slot:
                            slot = i
            tag = current_nbt[slot]['tag']

            tag['Damage'] = IntTag(0)
            tag['ench'] = tag_list

            # Save the modified NBT data
            nbt = _self.editor.selected_player[_self.editor.keys]

            _self.editor.selected_player.save_player()

        # Initial setup and main UI creation
        # self.onclick_get_set_tag_data()

        title = _self.Parent.Parent.GetTitle()
        # Determine the slot number, ensuring it is valid
        key, slot = _self.Get_slot_map_key()
        keys = _self.editor.keys + [key]
        current_nbt = _self.editor.selected_player[keys]

        if any(ct in title for ct in CONTAINER_TYPES):
            if len(current_nbt) > 0:
                for i, x in enumerate(current_nbt):
                    if x['Slot'].py_int == slot:
                        slot = i
                        break

        current_nbt = current_nbt[slot]
        item_type = get_item_type(current_nbt['Name'].py_str.split(':')[1])
        panel = Frame(_self, title="Edit Enchants", style=wx.DEFAULT_FRAME_STYLE | wx.STAY_ON_TOP)
        panel.SetBackgroundColour(BLACK)
        main_sizer = BoxSizer(VERTICAL)
        enchant_checkboxes = {}
        enchant_level_inputs = {}
        # Create top bar with buttons for selecting best enchants and saving data
        top_bar = BoxSizer(HORIZONTAL)
        best_button = Button(panel, label="Select All")
        best_button.Bind(EVT_BUTTON, select_best)
        unselect_button = Button(panel, label="UnSelect All")
        unselect_button.Bind(EVT_BUTTON, unselect)
        save_button = Button(panel, label="Save Enchants")
        save_button.Bind(EVT_BUTTON, save_data)
        best_button.SetForegroundColour(GREEN)
        best_button.SetBackgroundColour(BLACK)

        save_button.SetForegroundColour(GREEN)
        save_button.SetBackgroundColour(BLACK)
        best_button.SetFont(font)
        save_button.SetFont(font)
        top_bar.Add(unselect_button,0, ALL, 5)
        top_bar.Add(best_button, 0, ALL, 5)
        top_bar.Add(save_button, 0, ALL, 5)
        main_sizer.Add(top_bar)

        # Instructions for the user
        main_sizer.Add(StaticText(panel, label="Enchant (Check to apply, set level):"), 0, ALL, 5)
        # Get allowed enchantments for the current item type
        allowed_ids = valid_enchants.get(item_type, [])
        tag_data_ench = current_nbt.get('tag', {}).get('ench', [])
        existing_enchants = {x['id'].py_int: x['lvl'].py_int for x in tag_data_ench}

        # Loop through each allowed enchantment and set up UI controls for it
        from wx import FlexGridSizer

        # Each enchantment takes 2 cells: checkbox + level input
        # 3 enchantments per row = 6 columns total
        grid_sizer = FlexGridSizer(rows=0, cols=6, hgap=10, vgap=5)
        grid_sizer.AddGrowableCol(1)
        grid_sizer.AddGrowableCol(3)
        grid_sizer.AddGrowableCol(5)

        for ench_id in allowed_ids:
            name = enchantments[ench_id]
            level = existing_enchants.get(ench_id, 1)

            cb_id = wx.NewIdRef()
            cb = CheckBox(panel, id=cb_id.GetId(), label=name)
            cb.SetFont(font)
            cb.SetForegroundColour(GREEN)
            cb.SetBackgroundColour(BLACK)
            cb.Bind(EVT_CHECKBOX, on_check)
            if ench_id in existing_enchants:
                cb.SetValue(True)

            lvl = TextCtrl(panel, size=(50, -1), style=wx.TE_CENTER)
            lvl.SetFont(font)
            lvl.SetValue(str(level))
            lvl.Enable(ench_id in existing_enchants)
            lvl.SetForegroundColour(GREEN)
            lvl.SetBackgroundColour(BLACK)
            enchant_checkboxes[name] = cb
            enchant_level_inputs[cb_id.GetId()] = lvl

            # Add both to the grid
            grid_sizer.Add(cb, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 3)
            grid_sizer.Add(lvl, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 3)

        main_sizer.Add(grid_sizer, 0, wx.ALL, 5)

        # Finalize panel setup
        panel.SetSizer(main_sizer)
        panel.Centre()
        panel.Fit()
        panel.Show()

    def open_container(self, event, item_name, editor, last_key):

        CLIP_BOARD.pop('COPY', None) # prevent drag and drop when opening
        title = self.Parent.Parent.GetTitle()

        # Determine the slot number, ensuring it is valid

        last_key, slot = self.Get_slot_map_key()
        keys = self.editor.keys + [last_key]
        current_nbt = self.editor.selected_player[keys]

        if any(ct in title for ct in CONTAINER_TYPES):
            if len(current_nbt) > 0:
                for i, x in enumerate(current_nbt):
                    if x['Slot'].py_int == slot:
                        slot = i

        current_nbt = current_nbt[slot]



        namespace = "minecraft:"

        # … inside your method, after computing `tag_data`, `slot`, `last_key`, `editor`, etc.

        for keyword, (list_key, title) in CONTAINERS.items():

            data_name = item_name.lower()
            if keyword in data_name:
                # Build the keys path
                keys = editor.keys + [last_key, slot, "tag"]

                # If no tag exists yet, create it with an empty list
                parent_nbt = self.editor.selected_player[keys[:-1]]
                if not parent_nbt.get("tag", None):
                    parent_nbt["tag"] = CompoundTag({'Items': ListTag([])})

                tag = parent_nbt["tag"]

                # Finally, open the editor
                InventoryEditor(self, self.editor.selected_player, keys, title=title)
                break

    def edit_name_lore(self, event, _self):

        name_lore = BedrockNameTagAndLoreEditor(_self)
        name_lore.Show(True)

    def edit_tag_window(self, event, _self):

        # Create the TAGEditor window
        tagedit = TAGEditor(_self, "Snbt Editor", _self,_self.last_key, _self.slot )

        # Show the editor window
        tagedit.Show(True)
class IconButton(wx.Panel):
    def __init__(self, parent, bedrock_id, display_name, count, icon_bitmap, slot,
                 editor, *args, **kw):
        super().__init__(parent, *args, **kw)
        self.is_mouse_down = False
        self.motion_fired = False
        self.dragged_index = None
        self.dragged_id = None
        self.drag_image = None
        self.dragging = False
        self.tools = ItemTools(parent)
        self.font = wx.Font(18, wx.FONTFAMILY_ROMAN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        self.SetFont(self.font)
        self.parent = parent
        self.last_key = ''
        self.tag_data = None
        self.icon_bitmap = icon_bitmap
        self.slot_map_key = ()
        self.bedrock_id = bedrock_id
        self.display_name = display_name
        self.count = count
        self.slot = slot
        self.editor = editor
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.current_submenu_index = 0  # Add the attribute here
        self.items_per_page = 0  # Example number, can be modified
        # self.menu_handler = ContextMenuHandler(self, self.editor)
        self.setup_load_check_button_or_text()
        # Input box for count
        self.count_box = wx.TextCtrl(self, value=str(self.count), size=(40, 30), style=wx.TE_PROCESS_ENTER)
        self.count_box.Bind(wx.EVT_TEXT_ENTER, self.OnTextChange)
        self.Bind(wx.EVT_KEY_UP, self.on_key_up)
        self.sizer.Add(self.button, 0, wx.CENTER)
        self.sizer.Add(self.count_box, 0, wx.CENTER | wx.TOP, 2)
        self.panel_leave = False
        self.SetSizer(self.sizer)

    def on_hover_leave(self, event):
        self.panel_leave = True
    def on_hover_enter(self, event):
        self.panel_leave = False

        if CLIP_BOARD.get('SLOT_SOURCE'):
            key, slot_number = self.Get_slot_map_key()
            keys = self.editor.keys + [key]
            current_nbt_list = self.editor.selected_player[keys]

            CLIP_BOARD['SLOT_TARGET'] = (key, slot_number)
          #  print(key, slot_number, 'HOVER', CLIP_BOARD['SLOT_SOURCE'])

            if CLIP_BOARD.get('COPY'):
                self.complete_drag(event)

                return
            self.Layout()
            self.Refresh()


        drag_id = DRAG_DATA_SOURCE.get('id')
        if drag_id:
            ctrl_down = wx.GetKeyState(wx.WXK_CONTROL)
            shift_down = wx.GetKeyState(wx.WXK_SHIFT)
            self.on_menu_item_selected(event, drag_id)

            if not (ctrl_down):
                DRAG_DATA_SOURCE.pop('id', None)

    def complete_drag(self, event):
        def key_from_title(container_title: str) -> Union[list[str], None]:
            for key, (nbt_key, title) in CONTAINERS.items():
                if title == container_title:
                    return nbt_key
            return None

        source_data = CLIP_BOARD.get('SLOT_SOURCE')
        if source_data is None:
            return

        source_key, source_slot = source_data
        source_editor_keys = CLIP_BOARD.get('NESTED_KEYS')
        target_key, target_slot = self.Get_slot_map_key()

        source_path = source_editor_keys + [source_key]
        target_path = self.editor.keys + [target_key]
        test_source = source_editor_keys + [source_key, source_slot]
        test_target = self.editor.keys + [target_key, target_slot]
        if test_target[:len(test_source)] == test_source:
            print('This is not a valid move' )
            CLIP_BOARD.pop('COPY')
            self.dragging = False
            return  # invalid move
        self._target_title = self.Parent.Parent.GetTitle()
        self._source_title = CLIP_BOARD['SOURCE_SELF'].Parent.Parent.GetTitle()
        if not CLIP_BOARD.get('COPY'):

            return

        source_slot_data = CLIP_BOARD.get('SLOT_SOURCE')
        if not source_slot_data:
            return


        source_key, source_slot = source_slot_data
        source_button = CLIP_BOARD['SOURCE_SELF'].editor.slot_map.get(source_slot_data)
        if not source_button:
            return
        if not source_button.button.GetBitmap().IsOk():
            print("Invalid or destroyed source button.")
            return
        self._tar_empty = True


        count_source = CLIP_BOARD['SOURCE_SELF'].GetValue()
        count_target = self.GetValue()
        if count_target.py_int > 0:
            self._tar_empty = False

        self.SetValue(count_source)
        CLIP_BOARD['SOURCE_SELF'].SetValue(count_target)
        button_icon_source = source_button.button.GetBitmap()
        button_tooltip_source = source_button.button.GetToolTip()
        source_tip = button_tooltip_source.GetTip()
        button_name_source = source_button.button.GetName()
        button_icon_target = self.button.GetBitmap()
        button_tooltip_target = self.button.GetToolTip()
        target_tip = button_tooltip_target.GetTip()
        button_name_target = self.button.GetName()
        if not button_icon_source.IsOk():
            return
        if button_icon_target.IsOk():
            source_button.button.SetBitmap(button_icon_target)
            source_button.button.SetToolTip(target_tip)
            source_button.button.SetName(button_name_target)
        else:

            source_button.button.SetName('Empty')
            source_button.button.SetToolTip('Empty')
            source_button.button.SetBitmap(wx.NullBitmap)
            source_button.count_box.SetValue("0")
        if button_icon_source:
            if button_icon_source.IsOk():
                self.button.SetBitmap(button_icon_source)
                self.button.SetToolTip(source_tip)
                self.button.SetName(button_name_source)



        source_list = self.editor.selected_player[source_path]
        target_list = self.editor.selected_player[target_path]
        source_list_key = key_from_title(self._source_title)
        target_list_key = key_from_title(self._target_title)


        def copy_nbt_item_fields(source, target, slot):
            target['Name'] = source.get('Name', StringTag(''))
            target['Slot'] = ByteTag(slot)
            target['Damage'] = source.get('Damage', ShortTag(0))
            target['Count'] = source.get('Count', ByteTag(0))
            target['tag'] = source.get('tag', CompoundTag({}))
            source.pop('Block', None)
            target.pop('Block', None)
        source_static = True
        target_static = True

        if len(source_path) == 1 and source_path[0] in ('Armor', 'Offhand'):
            source_static = True
        elif self._source_title in [t[1] for t in CONTAINERS.values()][1:]:
            source_static = False

        if len(target_path) == 1 and target_path[0] in ('Armor', 'Offhand'):
            target_static = True
        elif self._target_title in [t[1] for t in CONTAINERS.values()][1:]:
            target_static = False

        source_index = next(
            (i for i, item in enumerate(source_list)
             if item.get('Slot', IntTag(-99)).py_int == source_slot),
            None
        )
        target_index = next(
            (i for i, item in enumerate(target_list)
             if item.get('Slot', IntTag(-99)).py_int == target_slot),
            None
        )

        # Safety check
        if source_index is None:
            raise ValueError(f"Source slot {source_slot} not found")
        if target_index is None and target_static:
            raise ValueError(f"Target slot {target_slot} not found in static list")

        # Perform MOVE or SWAP
        # Get source and target NBT compounds
        source_item = source_list[source_index]
        target_item = target_list[target_index] if target_index is not None else None

        source_name = source_item.get('Name', StringTag('')).py_str
        target_name = target_item.get('Name', StringTag('')).py_str if target_item else ''

        source_count = source_item.get('Count', ByteTag(0)).py_int
        target_count = target_item.get('Count', ByteTag(0)).py_int if target_item else 0

        max_stack = 64

        if not self._tar_empty and source_name == target_name:
            # Same item name, try to merge
            combined_count = source_count + target_count
            if combined_count <= max_stack:
                # Consolidate into one stack
                if target_static:
                    target_item['Count'] = ByteTag(combined_count)
                else:
                    target_list[target_index]['Count'] = ByteTag(combined_count)

                # Remove source
                CLIP_BOARD['SOURCE_SELF'].SetValue(0)
                source_button.button.SetBitmap(wx.NullBitmap)
                source_button.button.SetToolTip('Empty')

                source_button.button.SetName('Empty')
                self.SetValue(combined_count)

                if source_static:
                    copy_nbt_item_fields(CompoundTag({}), source_list[source_index], source_slot)
                else:
                    source_list.pop(source_index)

            else:
                # Fill target to max, return remaining to source


                remaining = combined_count - max_stack
                self.SetValue(64)
                CLIP_BOARD['SOURCE_SELF'].SetValue(remaining)

                if target_static:
                    target_item['Count'] = ByteTag(max_stack)
                else:
                    target_list[target_index]['Count'] = ByteTag(max_stack)

                if source_static:
                    source_item['Count'] = ByteTag(remaining)
                else:
                    source_list[source_index]['Count'] = ByteTag(remaining)

        else:
            # Default move/swap logic
            if self._tar_empty:
                # Move: target was empty

                if target_static:
                    copy_nbt_item_fields(source_list[source_index], target_list[target_index], target_slot)
                else:
                    if not target_list or not target_index:
                        target_list.append(CompoundTag({}))
                        target_index = -1
                    copy_nbt_item_fields(source_list[source_index], target_list[target_index], target_slot)

                # Remove source if needed
                if source_static:
                    copy_nbt_item_fields(CompoundTag({}), source_list[source_index], source_slot)
                else:
                    source_list.pop(source_index)

            else:
                # Swap: target was not empty
                temp = CompoundTag({})
                copy_nbt_item_fields(source_list[source_index], temp, target_slot)

                if target_static:
                    copy_nbt_item_fields(target_list[target_index], source_list[source_index], source_slot)
                    copy_nbt_item_fields(temp, target_list[target_index], target_slot)
                else:
                    if not target_list:
                        target_list.append(CompoundTag({}))
                        target_index = -1

                    copy_nbt_item_fields(target_list[target_index], source_list[source_index], source_slot)
                    copy_nbt_item_fields(temp, target_list[target_index], target_slot)


        # Clear clipboard and refresh
        CLIP_BOARD.clear()
        self.Refresh()
    def copy_tag_and_slot(self, event):

        key, slot_number = self.Get_slot_map_key()
        keys = self.editor.keys + [key]

        current_nbt_list = self.editor.selected_player[keys]
        CLIP_BOARD['NESTED_KEYS'] = self.editor.keys
        CLIP_BOARD['SLOT_SOURCE'] = key, slot_number
        CLIP_BOARD['SOURCE_SELF'] = self

        # Try to find the item at the matching slot number
        if len(keys) == 1 and keys[0] in ('Armor', 'Offhand'):
            CLIP_BOARD['COPY'] = current_nbt_list[slot_number]
        else:

            for item in current_nbt_list:
                if item['Slot'].py_int == slot_number:

                    CLIP_BOARD['COPY'] = item
                    break

        # If nothing matched, don't copy anything
        # CLIP_BOARD['COPY'] = None
    def OnMouseMove(self, event):


        if self.is_mouse_down and event.Dragging() and event.LeftIsDown():
            if not self.dragging:
                self.StartDrag(event)

        #

        if (
                hasattr(self, "drag_image")
                and self.drag_image is not None
                and isinstance(self.drag_image, wx.DragImage)
                and event.Dragging()
                and event.LeftIsDown()
        ):
            self.drag_image.Move(event.GetPosition())
    def OnMouseDown(self, event):
        self.drag_start_pos = event.GetPosition()
        self.is_mouse_down = True
        event.Skip()

        """Handles mouse down event to start the copy or delete logic."""
        pos = event.GetPosition()
        button = event.GetEventObject()
        image = button.GetBitmap()
        if not image or not image.IsOk():
            return
        bedrock_id = button.GetName()

        # Store drag data
        CLIP_BOARD['id'] = bedrock_id

        self.dragged_index = bedrock_id
        self.dragged_id = bedrock_id
        self.drag_image = wx.DragImage(image)
        self.drag_image.BeginDrag((0, 0), self.button, fullScreen=True)
        self.drag_image.Move(pos)
        self.drag_image.Show()
        self.copy_tag_and_slot(event)
        self.dragging = True

        # Simulate getting the index (assuming list_ctrl or similar control)
        # In this case, we don't need it because the image is directly related to the button.

        # If there's no image or metadata set on the button, we don't proceed

        # Get the image and associated metadata from the button
        # image = self.button.GetBitmap()
    def StartDrag(self, event):
        mouse_state = wx.GetMouseState()
        if not mouse_state.LeftIsDown():

            return
        pos = event.GetPosition()
        button = event.GetEventObject()
        image = button.GetBitmap()
        if not image or not image.IsOk():
            return
        bedrock_id = button.GetName()

        CLIP_BOARD['id'] = bedrock_id

        self.dragged_index = bedrock_id
        self.dragged_id = bedrock_id
        try:
            self.drag_image = wx.DragImage(image)
            self.drag_image.BeginDrag((0, 0), button, fullScreen=True)
            self.drag_image.Move(pos)
            self.drag_image.Show()
            self.copy_tag_and_slot(event)
            self.dragging = True
        except:
            print('some error was ignored')
            pass
    def on_doubble_click(self, event):
        item_name = self.button.GetName()
        self.dragging = False
        self.drag_image.Hide()
        self.drag_image.EndDrag()

        if any(key in item_name for key in CONTAINERS.keys()):
            ItemTools.open_container(
                self, event, item_name, self.editor, self.last_key
            )

    def on_right_click(self, event):

        self.button.SetFocus()

        # Get and validate button
        button = event.GetEventObject()
        # self.onclick_get_set_tag_data()

        menu = wx.Menu()

        if CLIP_BOARD:
            menu_paste = wx.MenuItem(menu, wx.ID_ANY, "Paste")
            menu.Append(menu_paste)

            self.Bind(wx.EVT_MENU, lambda e, btn=self: self.tools.paste_tag(btn), menu_paste)

        if button.GetName() != "Empty":
            keys = self.editor.keys + list(self.Get_slot_map_key())
            last_data = self.editor.selected_player[keys]
            menu_copy = wx.MenuItem(menu, wx.ID_ANY, "Copy")
            menu.Append(menu_copy)
            # self.Bind(wx.EVT_MENU, lambda e, idx=wx.ID_ANY: self.tools.copy_tag( e), menu_copy)
            self.Bind(wx.EVT_MENU, lambda e, btn=self: self.tools.copy_tag(btn), menu_copy)
            if last_data and last_data.get('tag', CompoundTag({})).get('minecraft:keep_on_death', False):
                self.text_to_keep = 'Drop item after death'
            else:
                self.text_to_keep = 'Keep even after death'

            item_name = self.button.GetName()

            if any(t in item_name for t in ["helmet", "leggings", "chestplate", "boots"]):
                trim_item = wx.MenuItem(menu, wx.ID_ANY, "Edit Armor Trims")
                menu.Append(trim_item)
                self.Bind(wx.EVT_MENU, lambda e, _self=self: self.tools.edit_add_armor_trims(_self), trim_item)

            if (any(t in item_name for t in ["bundle", "shulker", "dispenser", "chest", "barrel"]) and 'chestplate'
                    not in item_name):
                container_item = wx.MenuItem(menu, wx.ID_ANY, "Open Container")
                menu.Append(container_item)

                self.Bind(
                    wx.EVT_MENU,
                    lambda e: ItemTools.open_container(
                        self, e, item_name, self.editor, self.last_key
                    ),
                    container_item
                )

            if any(t in item_name for t in [
                                               "pickaxe", "axe", "shovel", "hoe", "trident",
                                               "helmet", "leggings", "chestplate", "boots",
                                               "chainmail", "sword", "elytra", "mace", "brush", 'shield'
                                           ] + list(enchantments.values())):
                enchant_item = wx.MenuItem(menu, wx.ID_ANY, "Edit Enchants")
                menu.Append(enchant_item)
                self.Bind(wx.EVT_MENU, lambda e, _self=self: self.tools.edit_enchants(_self), enchant_item)

            if any(t in item_name for t in [
                "pickaxe", "axe", "shovel", "hoe", "trident",
                "helmet", "leggings", "chestplate", "boots",
                "chainmail", "sword", "elytra", "mace", "brush", "bow", 'shield'
            ]):
                unbreakable_text = 'Make Breakable' if last_data.get('tag', {}).get('Unbreakable',
                                                                                    False) else 'Make Unbreakable'
                unbreakable_item = wx.MenuItem(menu, wx.ID_ANY, unbreakable_text)
                menu.Append(unbreakable_item)
                self.Bind(wx.EVT_MENU, lambda e, _self=self: self.tools.make_unbreakable(_self), unbreakable_item)

            if 'firework' in self.button.GetName():
                fireworks_item = wx.MenuItem(menu, wx.ID_ANY, "Edit Fireworks")
                menu.Append(fireworks_item)
                self.Bind(wx.EVT_MENU, lambda e, _self=self: self.tools.edit_fireworks_data(_self), fireworks_item)

            name_lore = wx.MenuItem(menu, wx.ID_ANY, "Edit Name and Lore")
            menu.Append(name_lore)
            self.Bind(wx.EVT_MENU, lambda e, _self=self: self.tools.edit_name_lore(e, _self), name_lore)

            tag_item = wx.MenuItem(menu, wx.ID_ANY, "Edit Tag Data")
            menu.Append(tag_item)
            self.Bind(wx.EVT_MENU, lambda e, _self=self: self.tools.edit_tag_window(e, _self), tag_item)

            keep_item = wx.MenuItem(menu, wx.ID_ANY, self.text_to_keep)
            menu.Append(keep_item)
            self.Bind(wx.EVT_MENU, lambda e, _self=self: self.tools.keep_on_death(_self), keep_item)

            delete_item = wx.MenuItem(menu, wx.ID_ANY, "Delete")
            menu.Append(delete_item)
            self.Bind(wx.EVT_MENU, lambda e, _self=self: self.tools.delete_slot(_self), delete_item)

        screen_pos = wx.GetMousePosition()
        client_pos = self.ScreenToClient(screen_pos)

        # Adjust values here (try -5, -10 etc. until it's perfectly aligned)
        adjusted_pos = wx.Point(client_pos.x + 10, client_pos.y + 10)

        self.PopupMenu(menu, adjusted_pos)
        menu.Destroy()
    def on_left_click(self, event):
        self.is_mouse_down = False
        self.dragging = False
        event.Skip()





         # Finalize move or swap
        if getattr(self, "drag_image", None):
            self.drag_image.Hide()
            try:
                self.drag_image.EndDrag()
            except Exception:
                pass
            finally:
                self.drag_image = None

        if self.dragging:

            try:
                self.ReleaseMouse()
            except Exception:
                pass



        self.dragged_bitmap = None
        self.dragged_id = None
        self.button = event.GetEventObject()
        if self.panel_leave:
            return
        self.button.SetFocus()

        if isinstance(self.button, wx.Button):

            if self.button.GetName() != 'Save':
                self.handle_button_click(self.button)
            else:
                return
        else:
            return  # Ignore clicks not on our custom buttons
    def setup_load_check_button_or_text(self):

        if self.bedrock_id and not self.icon_bitmap:
            self.button = wx.Button(self, size=(80, 80), label=bedrock_id)
            font = self.button.GetFont()
            font.SetPointSize(10)  # Make text smaller
            self.button.SetFont(font)
            split_name = bedrock_id.split('_')
            bedrock_id = ''
            for i,s in enumerate(split_name): # Manual wrapping
                if len(s) > 0:
                    bedrock_id += f'{s}_\n' if i != len(split_name)-1 else f'{s}'

            self.button.SetLabel(bedrock_id)
        else:
            if self.bedrock_id:
                self.button = wx.Button(self, size=(80, 80) ,name=self.bedrock_id)

                # self.button.Bind(wx.EVT_LIST_BEGIN_DRAG, self.OnBeginDrag)
                # self.button.Bind(wx.EVT_LEFT_DOWN, self.OnStartDrag)
                # self.button.Bind(wx.EVT_MOTION, self.OnDragMotion)
            else:
                self.button = wx.Button(self, size=(80, 80), name="Empty")
        try:
            valid_bitmap = bool(self.icon_bitmap and self.icon_bitmap.IsOk())
        except Exception as e:
            print(f"Bitmap check failed: {e}")
            valid_bitmap = False

        if valid_bitmap:
            self.button.SetBitmap(wx.Bitmap(self.icon_bitmap))

        else:
            self.button.SetBitmap(wx.NullBitmap)
        self.button.SetToolTip(wx.ToolTip(f"{self.display_name}"))
        self.button.Bind(wx.EVT_ENTER_WINDOW, self.on_hover_enter)
        self.button.Bind(wx.EVT_LEAVE_WINDOW, self.on_hover_leave)
        self.button.Bind(wx.EVT_LEFT_DOWN, self.OnMouseDown)
        self.button.Bind(wx.EVT_LEFT_UP, self.on_left_click)
        self.button.Bind(wx.EVT_RIGHT_DOWN, self.on_right_click)
        self.button.Bind(wx.EVT_MOTION, self.OnMouseMove)
        self.button.Bind(wx.EVT_LEFT_DCLICK, self.on_doubble_click)
    def OnTextChange(self, event):
        value = self.count_box.GetValue()

        if not re.fullmatch(r"-?\d{0,3}", value):
            self.count_box.SetValue(re.sub(r"[^-\d]", "", value)[:3])

    def handle_button_click(self, button):
        if self.dragging:
            return
        try:
            slot, item_id, count, display_name, tag = button.Parent.GetTheData
        except Exception as e:
            print(f"Error retrieving data from button: {e}")
            return

        self.total_items = []  # Reset for this click
        # self.onclick_get_set_tag_data()  # Assuming you have this method

        key, slot = self.Get_slot_map_key()
        # Generate the menu
        menu = wx.Menu()
        menu_item = wx.MenuItem(menu, wx.ID_ANY, "🟦🟦 LARGE MENU 🟦🟦")
        menu.Append(menu_item)
        self.Bind(wx.EVT_MENU, lambda e, idx=wx.ID_ANY: self.edit_click(e, idx), menu_item)

        # Handle specific slot categories
        if key == 'Armor':
            self.total_items = list(armor_item_range[slot])
        elif key == 'Offhand':
            self.handle_offhand(menu)
        else:
            self.add_category_menus(menu)

        if self.total_items:
            self.update_main_menu(menu)

        # Show the popup menu near the mouse position
        self.show_popup_menu(menu)

    def handle_offhand(self, menu):
        off_hand = {
            "Arrows": range(937, 950),
            "More Arrows": range(950, 979),
            "Most_used(may not work)": [980, 1212, 1696, 1044],
        }
        for category, item_range in off_hand.items():
            self.create_submenu(menu, category, item_range)

    def show_popup_menu(self, menu):
        screen_pos = wx.GetMousePosition()
        client_pos = self.ScreenToClient(screen_pos)
        adjusted_pos = wx.Point(client_pos.x + 10, client_pos.y + 10)
        self.PopupMenu(menu, adjusted_pos)
        menu.Destroy()

    def SetName(self, name):
        self.button.SetName(name)

    def create_submenu(self, menu, category, item_range):
        submenu = wx.Menu()
        for item in item_range:
            menu_item = wx.MenuItem(submenu, wx.ID_ANY, f"Item {item}")
            submenu.Append(menu_item)
        menu.AppendSubMenu(submenu, category)

    def on_menu_item_selected(self, event, bedrock_id):
        """Handle selection of an item from the menu."""
        self.namespace = 'minecraft:'
        self.bedrock_id = bedrock_id
        self.title = self.editor.GetTitle()
        self.button.SetName(bedrock_id)
        key, slot = self.Get_slot_map_key()


        current_nbt = self.editor.selected_player[self.editor.keys]
        nbt = current_nbt[key]
        tag_data = check_set_default_book(bedrock_id)

        # Save the slot for later use


        # Initialize default tag structure
        self.tag_data = CompoundTag({
            "Name": StringTag(self.namespace + self.bedrock_id),
            "Damage": ShortTag(0),
            "Count": ByteTag(1),
            "Slot": ByteTag(self.slot),
            "tag": CompoundTag({})
        })
        self.append = False
        # Check if this is a container-type item (like a bundle)
        if any(keyword in bedrock_id for keyword in CONTAINERS):

            if 'bundle' in bedrock_id:
                self.tag_data['tag']['storage_item_component_content'] = ListTag([
                    CompoundTag({
                        "Name": StringTag(''),
                        "Damage": ShortTag(0),
                        "Count": ByteTag(0),
                        "Slot": ByteTag(x),
                        "tag": CompoundTag({})
                    }) for x in range(64)
                ])
            else:
                self.tag_data['tag']["Items"] = ListTag(
                    []
                )

        # If tag_data (e.g., for books) is provided, use it to replace the default
        if tag_data:

            self.tag_data['tag'] = tag_data

        # Handle known container UI titles

        if any(container_type in self.title for container_type in CONTAINER_TYPES):
            slot = None
            if len(nbt) > 0:
                for i, item in enumerate(nbt):
                    if item['Slot'].py_int == self.slot:
                        slot = i
                        break
                if slot is None:
                    self.append = True
            else:
                self.append = True

        ctrl_down = wx.GetKeyState(wx.WXK_CONTROL)
        shift_down = wx.GetKeyState(wx.WXK_SHIFT)

        if ctrl_down:
            self.SetValue(64)
            self.tag_data['Count'] = ByteTag(64)
        else:
            self.SetValue(1)
            self.tag_data['Count'] = ByteTag(1)
        if any(word in self.tag_data['Name'].py_str for word in ("boat", "minecart")):
            self.tag_data.pop('tag', None)
        keys = self.editor.keys + [ key, slot]

        if self.append:
            self.editor.selected_player[keys[:-1]].append(self.tag_data)
        else:
            self.editor.selected_player[keys] = self.tag_data
#
        parent = self.GetParent()
        while parent is not None:
            if hasattr(parent, 'update_slot'):
                parent.update_slot(
                    slot,
                    self.bedrock_id,
                    self.editor.resources.get_scaled_cache[self.bedrock_id],
                    self.editor.resources.data[self.bedrock_id]['display_name'],
                    self.tag_data
                )

                break
            parent = parent.GetParent()
        icon = self.editor.resources.get_scaled_cache[self.bedrock_id],
        display_name = self.editor.resources.data[self.bedrock_id]['display_name']


        self.SetName(bedrock_id)
        self.SetBitmap(icon[0], display_name)
        self.Refresh()

    def add_category_menus(self, parent_menu):
        """Add organized category menus from a single dictionary."""
        for group_name, group_data in categories.items():
            group_menu = wx.Menu()
            parent_menu.AppendSubMenu(group_menu, group_name)

            # If group_data is a dict of subgroups...
            if isinstance(group_data, dict):
                # If it has exactly one subgroup and that subgroup is a list/tuple,
                # collapse it into a single-level menu
                if len(group_data) == 1:
                    _, id_ranges = next(iter(group_data.items()))
                    self._populate_menu_with_ranges(group_menu, id_ranges)
                else:
                    # Multiple subgroups: make a submenu for each
                    for category_name, id_ranges in group_data.items():
                        sub_menu = wx.Menu()
                        group_menu.AppendSubMenu(sub_menu, category_name)
                        self._populate_menu_with_ranges(sub_menu, id_ranges)

            # If group_data is a flat list/tuple of ranges or IDs...
            elif isinstance(group_data, (list, tuple)):
                self._populate_menu_with_ranges(group_menu, group_data)

            else:
                print(f"Skipping {group_name}: unsupported type {type(group_data)}")

    def _populate_menu_with_ranges(self, menu, id_ranges):
        """Helper to expand ranges/IDs and add items to a menu."""
        expanded_ids = []
        for item in id_ranges:
            if isinstance(item, tuple):
                expanded_ids.extend(range(item[0], item[1] + 1))
            else:
                expanded_ids.append(item)

        for item_id in expanded_ids:
            self.add_items_to_menu(menu, item_id)

    def add_items_to_menu(self, menu, item_id):
        """Add a single item to a menu."""
        # Check if the item_id exists in the available items list
        if 0 <= item_id < len(self.editor.resources.get_items_id):
            item_name = self.editor.resources.get_items_id[item_id]
            display_name = self.editor.resources.data.get(item_name, {}).get('display_name', item_name)
            icon_bitmap = self.editor.resources.get_icon_cache.get(item_name, wx.NullBitmap)

            # Create and append the menu item with an optional icon
            menu_item = wx.MenuItem(menu, wx.ID_ANY, display_name)
            if icon_bitmap and icon_bitmap.IsOk():
                menu_item.SetBitmap(icon_bitmap)

            # Append to the submenu
            menu.Append(menu_item)

            # Bind the event handler for the menu item
            self.Bind(wx.EVT_MENU,
                      lambda e, bid=item_name: self.on_menu_item_selected(e, bid),
                      menu_item)

    def update_main_menu(self, menu):
        """Update the main menu with items similar to the submenu behavior."""
        for item_id in self.total_items:
            if 0 <= item_id < len(self.editor.resources.get_items_id):
                item_name = self.editor.resources.get_items_id[item_id]
            else:
                continue

            icon_bitmap = self.editor.resources.get_icon_cache.get(item_name, wx.NullBitmap)
            display_name = self.editor.resources.data.get(item_name, {}).get('display_name', item_name)

            menu_item = wx.MenuItem(menu, wx.ID_ANY, display_name)
            menu_item.SetBitmap(icon_bitmap)
            menu.Append(menu_item)

            self.Bind(wx.EVT_MENU, lambda event, idx=item_id: self.on_menu_item_selected(menu, self.editor.resources.get_items_id[idx]), menu_item)

    def create_submenu(self, parent_menu, submenu_name, item_range):
        """Creates a submenu with the provided item range."""
        submenu = wx.Menu()
        for item_id in item_range:
            if 0 <= item_id < len(self.editor.resources.get_items_id):
                item_name = self.editor.resources.get_items_id[item_id]
                icon_bitmap = self.editor.resources.get_icon_cache.get(item_name, wx.NullBitmap)
                display_name = self.editor.resources.data.get(item_name, {}).get('display_name', item_name)

                menu_item = wx.MenuItem(submenu, wx.ID_ANY, display_name)
                menu_item.SetBitmap(icon_bitmap)
                submenu.Append(menu_item)

                self.Bind(wx.EVT_MENU, lambda event, idx=item_id: self.on_menu_item_selected(parent_menu,
                                        self.editor.resources.get_items_id[idx]), menu_item)

        parent_menu.AppendSubMenu(submenu, submenu_name)

    def Get_slot_map_key(self): # Main Slot Key tracking
        return self.slot_map_key

    def Set_slot_map_key(self, k,i): #Main Slot Key tracking
        self.slot_map_key = (k, i)

    def clear_bitmap(self):
        self.button.SetBitmap(wx.NullBitmap)
        self.Refresh()
        self.Update()

    def SetBitmap(self, icon, display_name):
        self.display_name = display_name

        if icon and icon.IsOk():
            self.button.SetBitmap(icon)

        self.button.SetToolTip(wx.ToolTip(self.display_name))

    def SetLabelText(self, label):
        self.bedrock_id = label

    def SetTagData(self, data):
        self.tag_data = data

    @property
    def GetTheData(self):  # # #
        return (self.slot, self.bedrock_id, self.count_box.GetValue(),
                self.display_name, self.tag_data)

    def SetTheData(self, slot, bedrock_id, count, display_name, tag_data):  # # #
         self.slot = slot
         self.bedrock_id =  bedrock_id
         self.count_box.SetValue(count)
         self.display_name = display_name
         self.tag_data = tag_data

    def SetValue(self, value):
        self.count_box.SetValue(str(value))

    def GetValue(self):
        return ByteTag( int(self.count_box.GetValue()))

    def edit_click(self, _, idx):

        self.icon_resources = IconResources()
        self.icon_resources.toggle_catalog(self.parent, self.editor,  self.Get_slot_map_key())

    def get_slot(self):
        return self.slot

    def set_slot(self, slot):
        self.slot = slot

    def UnbindButtonMenu(self):
        self.button.Unbind(wx.EVT_LEFT_UP, handler=self.on_left_click)
        self.button.Unbind(wx.EVT_ENTER_WINDOW, handler=self.on_hover_enter)
        # self.button.Unbind(wx.EVT_LEAVE_WINDOW, handler=self.on_hover_leave)
        # self.button.Bind(wx.EVT_LEAVE_WINDOW, self.on_left_up)
        self.button.Unbind(wx.EVT_LEFT_DOWN, handler=self.OnMouseDown)
        self.button.Unbind(wx.EVT_LEFT_UP, handler=self.on_left_click)
        self.button.Unbind(wx.EVT_RIGHT_DOWN, handler=self.on_right_click)
        self.button.Unbind(wx.EVT_MOTION, handler=self.OnMouseMove)

    def HideButtonValue(self):
        self.count_box.Hide()

    def delete_slot(self):
        self.bedrock_id = ''
        self.button.SetName('Empty')
        self.clear_bitmap()
        self.SetBitmap(wx.NullBitmap, "Empty")
        self.count_box.SetValue("0")
        self.Layout()
        self.Refresh()

    def on_key_up(self, event):
        if event.GetKeyCode() == wx.WXK_SHIFT:
            DRAG_DATA_SOURCE.pop('keys', None)
        event.Skip()

    def on_shift_up(self, event):
        DRAG_DATA_SOURCE.pop('id', None)

class InventoryEditorList(wx.Frame):

    def __init__(self, parent, canvas, world):
        super().__init__(parent, title="Player List Double Click to Load", size=(400, 800),
                         style=wx.DEFAULT_FRAME_STYLE | wx.STAY_ON_TOP)
        self.parent = parent
        self.canvas = canvas
        self.world = world

        self.open_editors = []  # Store references to open InventoryEditor instances

        self.player_data = PlayersData(world)
        self.player_list = self.player_data.get_loaded_players_list

        self.font = wx.Font(20, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        self.SetFont(self.font)
        self.SetForegroundColour((0, 255, 0))
        self.SetBackgroundColour((0, 0, 0))

        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        self.list_ctrl = wx.ListBox(panel, choices=self.player_list)
        self.list_ctrl.SetFont(self.font)
        self.list_ctrl.SetForegroundColour((0, 255, 0))
        self.list_ctrl.SetBackgroundColour((0, 0, 0))

        vbox.Add(self.list_ctrl, 1, wx.EXPAND | wx.ALL, 10)
        self.list_ctrl.Bind(wx.EVT_LISTBOX_DCLICK, self.on_item_click)
        self.Bind(wx.EVT_CLOSE, self.on_close)
        self.Centre()
        panel.SetSizer(vbox)
        self.Show()
    def on_close(self, event):
        self.Hide()
        if __name__ == "__main__":
            self.world.close()


    def on_item_click(self, event):
        selection = self.list_ctrl.GetStringSelection()
        if selection != wx.NOT_FOUND:
            selected_player = self.player_data.get_player(selection)
            inventory_editor = InventoryEditor(self, selected_player, [])
            inventory_editor.Bind(wx.EVT_CLOSE, lambda evt, ed=inventory_editor: self._on_editor_close(evt, ed))
            inventory_editor.Show(True)
            self.open_editors.append(inventory_editor)

    def _on_editor_close(self, event, editor):
        if editor in self.open_editors:
            self.open_editors.remove(editor)
        event.Skip()

class MinecraftWorldSelector(wx.Frame):
    def __init__(self):
        super().__init__(None, title="Minecraft World Selector", size=(1100, 900))
        self.font = wx.Font(18, wx.FONTFAMILY_ROMAN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        self.SetFont(self.font)
        self.SetForegroundColour((0, 255, 0))
        self.SetBackgroundColour(wx.Colour(0, 0, 0, 0))
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        panel = wx.ScrolledWindow(self)

        panel.SetScrollRate(10, 10)
        grid_sizer = wx.GridSizer(0, 4, 5, -80)  # 0 rows, 4 columns, 10px gap

        if os.path.exists(WORLDS_DIR):
            worlds = []
            for world_folder in os.listdir(WORLDS_DIR):
                world_path = os.path.join(WORLDS_DIR, world_folder)
                if os.path.isdir(world_path):
                    mod_time = os.path.getmtime(world_path)  # Get modification time
                    worlds.append((mod_time, world_path))

            # Sort worlds by most recent modification time (descending)
            worlds.sort(reverse=True, key=lambda x: x[0])

            for _, world_path in worlds:
                world_name = "Unknown World"
                icon_path = os.path.join(world_path, "world_icon.jpeg")
                name_path = os.path.join(world_path, "levelname.txt")

                if os.path.exists(name_path):
                    with open(name_path, "r", encoding="utf-8") as f:
                        world_name = f.read().strip()

                world_panel = wx.Panel(panel)
                world_sizer = wx.BoxSizer(wx.VERTICAL)

                if os.path.exists(icon_path):
                    image = wx.Image(icon_path, wx.BITMAP_TYPE_JPEG).Scale(128, 128)
                    bitmap = wx.StaticBitmap(world_panel, bitmap=wx.Bitmap(image))

                    # Bind hover events correctly
                    bitmap.Bind(wx.EVT_ENTER_WINDOW, self.on_hover)
                    bitmap.Bind(wx.EVT_LEAVE_WINDOW, self.on_leave)
                    bitmap.Bind(wx.EVT_LEFT_DOWN, lambda evt, path=world_path: self.on_world_selected(evt, path))

                    world_sizer.Add(bitmap, 0, wx.ALIGN_CENTER | wx.ALL, 5)
                else:
                    button = wx.Button(world_panel, label="Select")
                    button.Bind(wx.EVT_BUTTON, lambda evt, path=world_path: self.on_world_selected(evt, path))
                    world_sizer.Add(button, 0, wx.ALIGN_CENTER | wx.ALL, 5)

                label = wx.StaticText(world_panel, label=world_name)
                label.Bind(wx.EVT_ENTER_WINDOW, self.on_hover)
                label.Bind(wx.EVT_LEAVE_WINDOW, self.on_leave)

                label.SetFont(self.font)
                label.SetForegroundColour((0, 255, 0))
                label.SetBackgroundColour(wx.Colour(0, 0, 0, 0))
                label.SetMinSize((150, 150))
                world_sizer.Add(label, 0, wx.ALIGN_CENTER | wx.ALL, 5)
                # label.SetTransparent(0)

                world_panel.SetSizer(world_sizer)
                grid_sizer.Add(world_panel, 0, wx.EXPAND | wx.ALL, 5)

        panel.SetSizer(grid_sizer)
        self.Centre()
        self.Show()

    def on_hover(self, event):
        obj = event.GetEventObject()
        parent = obj.GetParent()

        if isinstance(obj, wx.StaticText):
            obj.Hide()
            parent.Layout()  # Layout the parent, not the text itself
            parent.Refresh()

        elif isinstance(obj, wx.StaticBitmap):
            bmp = obj.GetBitmap()
            img = bmp.ConvertToImage().Scale(354, 354)
            obj.SetBitmap(wx.Bitmap(img))
            parent.Layout()
            parent.Refresh()

    def on_leave(self, event):
        obj = event.GetEventObject()
        parent = obj.GetParent()

        if isinstance(obj, wx.StaticText):
            obj.Show()
            parent.Layout()
            parent.Refresh()

        elif isinstance(obj, wx.StaticBitmap):
            bmp = obj.GetBitmap()
            img = bmp.ConvertToImage().Scale(128, 128)
            obj.SetBitmap(wx.Bitmap(img))
            parent.Layout()
            parent.Refresh()

    def on_world_selected(self, event, path):
        world = LevelDB(path + r"\db")
        new_window = InventoryEditorList(None, None, world)
        new_window.Move(self.GetScreenPosition())  # Open next to the parent
        new_window.Show()

if __name__ == "__main__":
    app = wx.App(False)
    MinecraftWorldSelector()
    app.MainLoop()


#by PremiereHell ver 2.00