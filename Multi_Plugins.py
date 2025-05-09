# 8 v
import urllib.request
import collections
import time
import sys
import ctypes
import copy
import zlib
import struct
import pickle
import uuid
import re
import wx
import wx.richtext as rt
import math
from math import ceil
import numpy
import PyMCTranslate
from amulet_map_editor.api.opengl.camera import Projection
from amulet_map_editor.programs.edit.api.behaviour import BlockSelectionBehaviour
from amulet_map_editor.programs.edit.api.behaviour import StaticSelectionBehaviour
from amulet_map_editor.programs.edit.api.key_config import ACT_BOX_CLICK
from amulet_map_editor.programs.edit.api.events import (
    EVT_SELECTION_CHANGE,
)
from typing import TYPE_CHECKING, Type, Any, Callable, Tuple, BinaryIO, Optional, Union, List
from amulet.utils import chunk_coords_to_region_coords
from amulet.utils import block_coords_to_chunk_coords
from amulet.level.formats.anvil_world.region import AnvilRegion
from amulet.level.formats.anvil_world.region import AnvilRegionInterface
from amulet.api.selection import SelectionGroup
from amulet.api.selection import SelectionBox
from amulet_map_editor.programs.edit.api.behaviour.pointer_behaviour import EVT_POINT_CHANGE
from amulet_map_editor.programs.edit.api.behaviour.pointer_behaviour import PointChangeEvent
from amulet_map_editor.programs.edit.api.behaviour.pointer_behaviour import PointerBehaviour
from amulet.api.data_types import PointCoordinates
from amulet_map_editor.programs.edit.api.events import (
    InputPressEvent,
    EVT_INPUT_PRESS,
)
from amulet_map_editor.programs.edit.api.operations import DefaultOperationUI
from amulet_map_editor.api.wx.ui.base_select import BaseSelect
from amulet_map_editor.api.wx.ui.block_select import BlockDefine
from amulet_map_editor.api.wx.ui.block_select import BlockSelect
from amulet.api.block import Block
from amulet.api.block_entity import BlockEntity
from amulet.api.errors import ChunkDoesNotExist
from amulet_map_editor.api.wx.ui import simple
from amulet_map_editor.api import image
from functools import partial, reduce
import operator
from PIL import Image
from amulet_map_editor.api.wx.ui.version_select import VersionSelect
nbt_resources = image.nbt
import json
from collections.abc import MutableMapping, MutableSequence
import abc
from amulet_nbt import *
import os
from os.path import exists
from pathlib import Path
from amulet_map_editor.api.wx.ui.block_select.properties import (
    PropertySelect,
    WildcardSNBTType,
    EVT_PROPERTIES_CHANGE,
)
from amulet_map_editor.programs.edit.api.events import (
    EVT_SELECTION_CHANGE,
)
import base64
import io
import wx.lib.scrolledpanel as scrolled
if TYPE_CHECKING:
    from amulet.api.level import BaseLevel
    from amulet_map_editor.programs.edit.api.canvas import EditCanvas

def find_end_of_compounds(data):
    def parse_compound(data, offset):
        while offset < len(data):
            tag_type = data[offset]
            offset += 1
            if tag_type == 0x00:  # End of compound
                break
            name_length = int.from_bytes(data[offset:offset + 2], byteorder='little')
            offset += 2 + name_length
            offset = parse_tag(data, offset, tag_type)
        return offset

    def parse_tag(data, offset, tag_type):
        size_map = {
            0x01: 1,  # Byte
            0x02: 2,  # Short
            0x03: 4,  # Int
            0x04: 8,  # Long
            0x05: 4,  # Float
            0x06: 8,  # Double
        }
        if tag_type in size_map:
            offset += size_map[tag_type]
        elif tag_type == 0x07:  # Byte array
            length = int.from_bytes(data[offset:offset + 4], byteorder='little')
            offset += 4 + length
        elif tag_type == 0x08:  # String
            length = int.from_bytes(data[offset:offset + 2], byteorder='little')
            offset += 2 + length
        elif tag_type == 0x09:  # List
            list_type = data[offset]
            offset += 1
            length = int.from_bytes(data[offset:offset + 4], byteorder='little')
            offset += 4
            for _ in range(length):
                offset = parse_tag(data, offset, list_type)
        elif tag_type == 0x0A:  # Compound
            offset = parse_compound(data, offset)
        elif tag_type == 0x0B:  # Int array
            length = int.from_bytes(data[offset:offset + 4], byteorder='little')
            offset += 4 + length * 4
        elif tag_type == 0x0C:  # Long array
            length = int.from_bytes(data[offset:offset + 4], byteorder='little')
            offset += 4 + length * 8
        return offset

    offset = 4
    cnt = 0
    num_compounds = int.from_bytes(data[:4], byteorder='little')
    while offset < len(data):
        if data[offset:offset + 3] == b'\x0A\x00\x00':  # Start of a compound
            offset = parse_compound(data, offset + 3)
            cnt += 1
            if cnt == num_compounds:
                break
        elif data[offset] == 0x00:  # End of compounds
            break
        else:
            raise ValueError("Invalid NBT data")

    return offset

def block_enty_raw_cords(x, y, z):  # fast search
    data = CompoundTag({'x': IntTag(), 'y': IntTag(), 'z': IntTag()}).to_nbt(compressed=False, little_endian=True)
    return data[3:-1]

def unpack_nbt_list(raw_nbt: bytes):
    nbt_list = []
    while raw_nbt:
        read_context = ReadContext()
        nbt = load(
            raw_nbt,
            little_endian=True,
            read_context=read_context,
            string_decoder=utf8_escape_decoder,
        )
        raw_nbt = raw_nbt[read_context.offset:]
        nbt_list.append(nbt)
    return nbt_list

def pack_nbt_list(nbt_list):
    return b"".join(
        [
            nbt.save_to(
                compressed=False,
                little_endian=True,
                string_encoder=utf8_escape_encoder,
            )
            for nbt in nbt_list
        ]
    )

def create_new_actor_prefix(start, cnt):
    actorKey = struct.pack('>LL', start, cnt)
    db_key = b''.join([b'actorprefix', actorKey])
    return db_key, actorKey

def uniqueid_to_actorprefix_key(UniqueID: LongTag):
    packed_data = struct.pack('<q', UniqueID.py_data)
    cnt, worldstartcnt = struct.unpack('<LL', packed_data)
    start_cnt = 4294967296 - worldstartcnt
    actorKey = struct.pack('>LL', start_cnt, cnt)
    db_key = b''.join([b'actorprefix', actorKey])
    return db_key

def _genorate_uid(cnt, worldstartcount):
    start_c = worldstartcount
    new_gen = struct.pack('<LL', int(cnt), int(start_c))
    new_tag = LongTag(struct.unpack('<q', new_gen)[0])
    return new_tag

def _storage_key_(val):
    if isinstance(val, bytes):
        return struct.unpack('>II', val)
    if isinstance(val, StringTag):
        return ByteArrayTag([x for x in val.py_data])
    if isinstance(val, ByteArrayTag):
        data = b''
        for b in val: data += b
        return data

def split_bytes(data):
    return [data[i:i + 8] for i in range(0, len(data), 8)]

def get_y_range(test_val):
    if test_val == struct.pack('<i', 1) or 'minecraft:the_nether' == test_val:
        return (0, 127)
    elif test_val == struct.pack('<i', 2) or 'minecraft:the_end' == test_val:
        return (0, 255)
    elif test_val == b'' or 'minecraft:overworld' == test_val:
        return (-64, 319)
############# Start Inventory EDITOR
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
        "Glass": [165, 182, 1047, 1195],
        "Stained_Glass": [(166, 181)],
        "Glass_Panes": [(184, 199), 1736],
        "Wool": [(365, 380)],
        "Carpets": [(381, 396), 705, 707],
        "Concrete": [(413, 428)],
        "Concrete_Powder": [(397, 412)],
        "Terracotta": [(430, 461)],
        "Bricks": [(264, 267), (269, 271), (276, 278), 281, 344, 349, (357, 359), (361, 362), 465, (759, 762), 1378],
        "Blackstone": [(272, 273), 506, 513, 1582, 1599],
        "Basalt": [509, (516, 517)],
        "Tuff": [280, 508, 515],
        "Copper_Blocks": [295, (303, 310), (327, 334), 340, 489, 501, 1367],
        "Amethyst_Blocks": [720, 1380],
        "Prismarine": [348, 350, 1381],
        "Nether_Bricks": [360],
        "Nylium": [(469, 470)],
    },
    "Natural Blocks": {
        "Logs": [(522, 543), (562, 565), 742, 1767],
        "Wood": [544, 546, 548, 550, 552, 554, 556, 558, 560],
        "Stripped_Wood": [545, 547, 549, 551, 553, 555, 557, 559, 561],
        "Leaves": [(568, 578)],
        "Saplings": [(579, 587)],
        "Mushroom_Blocks": [(740, 741)],
        "Ores": [(483, 488), (490, 492), (494, 500), 1750],
        "Raw_Blocks": [202, (293, 294), (335, 339), (341, 343), 346, (352, 356), 363, 462, (466, 467), 473, (566, 567),
                       604, 703, 706, 708, 714, 856, (865, 874), 1359, 1566, 1721, (1725, 1726), 1762],
    },
    "Rails": {
        "Rails": [(1557, 1558)],
    },
    "Redstone": {
        "Redstone_Components": [(1559, 1560), 1563, (1567, 1581), (1584, 1598), 1600, (1602, 1606), (1608, 1609), 1716,
                                (1757, 1758), 1764],
        "Lamps": [1306, 1749],
    },
    "Farming": {
        "Crops": [(589, 593), (595, 600), (605, 606), (609, 611), 686, 992, 994, 996, 1000, 1756],
        "Food": [(602, 603), (990, 991), 993, 997],
        "Animal_Products": [(744, 745), (764, 766), (772, 851), (983, 986), 1754],
    },
    "Mob Drops": {
        "Monster_Drops": [631, 641, 999, (1010, 1017), 1382, (1384, 1386), (1395, 1396), (1403, 1404), 1406,
                          (1409, 1410)],
        "Heads": [(1349, 1355)],
    },
    "Weapons": {
        "Weapons": [(906, 911)],
    },
    "Tools": {
        "Tools": [(912, 935)],
    },
    "Armor": {
        "Armor": [(882, 905), 1044],
    },
    "Horse_Armor": {
        "Horse_Armor": [(1038, 1041)],
    },
    "Fireworks": {
        "Fireworks": [(1682, 1698)],
        "Star": [1408, (1699, 1714)],
    },
    "Containers": {
        "Shulker_Boxes": [(1264, 1280)],
        "Bundles": [(1021, 1037)],
        "Barrel Chests": [1263, (1260, 1262), 1562],

    },
    "Miscellaneous": {
        "Dyes": [(668, 683)],
        "Buckets": [(1339, 1348)],
        "Potions": [(1049, 1189)],
        "Music_Discs": [(1284, 1302)],
        "Boats": [(1537, 1556)],
        "Beds": [854, (1198, 1213), 1737],
        "Signs": [(1308, 1319)],
        "Hanging_Signs": [(1320, 1331)],
        "Banners": [(1613, 1639)],
        "Spawners": [(752, 753)],
        "Coral": [(622, 626), (632, 636)],
        "Dead_Coral": [(627, 630), (637, 640)],
        "Enchanted_Books": [(1415, 1536)],
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
BANNER = {}  # TOP LAYER STENCILS
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
            WINDOW['catalog'].Show()
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
        BANNER['ICONS'] = self.resources.get_json_data['banner']
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


        # Convert to screen coordinates
        screen_pos = event.GetEventObject().ClientToScreen(pos)
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
        self.drag_image.BeginDrag((30, 30), self.list_ctrl, fullScreen=True)
        self.drag_image.Move(screen_pos)
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
            if bedrock_id == 'banner':
                continue

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
        for i, x in enumerate(self._self.editor.selected_player[keys]):
            i += -7 + 26
            try:
                print(i, x['tag']['Patterns'][0]['Pattern'].py_str)
            except:
                pass
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


# Constants

IMAGE_COUNT = 44
ORIGINAL_WIDTH = 880 // IMAGE_COUNT
ORIGINAL_HEIGHT = 40
PATTERN_WIDTH = 30
PATTERN_HEIGHT = 50
PREVIEW_WIDTH = 100
PREVIEW_HEIGHT = 200

MC_COLORS = [
    (249, 255, 254),  # White
    (249, 128, 29),  # Orange
    (199, 78, 189),  # Magenta
    (58, 179, 218),  # Light Blue
    (254, 216, 61),  # Yellow
    (128, 199, 31),  # Lime
    (243, 139, 170),  # Pink
    (71, 79, 82),  # Gray
    (157, 157, 151),  # Light Gray
    (22, 156, 156),  # Cyan
    (137, 50, 184),  # Purple
    (60, 68, 170),  # Blue
    (131, 84, 50),  # Brown
    (94, 124, 22),  # Green
    (176, 46, 38),  # Red
    (29, 29, 33)  # Black
]
COLOR_NAMES = [
    "White", "Orange", "Magenta", "Light Blue",
    "Yellow", "Lime", "Pink", "Gray",
    "Light Gray", "Cyan", "Purple", "Blue",
    "Brown", "Green", "Red", "Black"
]

MC_COLORS = list(reversed(MC_COLORS))
COLOR_NAMES = list(reversed(COLOR_NAMES))
PATTERN_KEY_TO_NAME = {
    0: ("base", "Base 1"),
    1: ("base", "Base 2"),
    2: ("bo", "bordure"),
    3: ("bri", "field masoned"),
    4: ("mc", "roundel"),
    5: ("cre", "Creeper Charger"),
    6: ("cr", "saltire"),
    7: ("cbo", "bordure indented"),
    8: ("ld", "per bend inverted"),
    9: ("rud", "per bend sinister inverted"),
    10: ("flo", "Flower Charge"),
    11: ("gra", "gradient"),
    12: ("hh", "per fess"),
    13: ("vh", "per pale"),
    14: ("moj", "white thing"),
    15: ("mr", "lozenge"),
    16: ("sku", "Skull Charge"),
    17: ("ss", "paly"),
    18: ("bl", "Base dextor canton"),
    19: ("br", "Base Sinister canton"),
    20: ("tl", "Chief Dextor Canton"),
    21: ("tr", "Chief Sinsiter Canton"),
    22: ("sc", "Cross"),
    23: ("bs", "Bass fess"),
    24: ("cs", "Pale"),
    25: ("dls", "Bend Sinister"),
    26: ("drs", "Bend"),
    27: ("ls", "Pale Dexter"),
    28: ("ms", "Fess"),
    29: ("rs", "Pale Sinsiter"),
    30: ("ts", "Chief Fess"),
    31: ("bts", "base indented"),
    32: ("tts", "chief inented"),
    33: ("bt", "Chevron"),
    34: ("tt", "Inverted chevron"),
    35: ("lud", "per bend sinister"),
    36: ("rd", "per bend"),
    37: ("gru", "base gradient"),
    38: ("hhb", "per fess inverted"),
    39: ("vhr", "per pale inverted"),
    40: ("glb", "globe"),
    41: ("pig", "snout"),
    42: ("flw", "Flow"),
    43: ("gus", "guster"),
}

class BannerSelector(wx.Frame):
    def __init__(self, parent, _self):
        super().__init__(None, title="Banner Selector", size=(545, 560),style=wx.DEFAULT_FRAME_STYLE | wx.STAY_ON_TOP)
        self._self = _self
        self.parent = parent
        self.panel = wx.Panel(self)
        self.nbt_data = None
        self.damage_color = None
        self.selected_pattern_button = None
        # Main sizer
        self.layered_selection = []


        self.main_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # Left panel for patterns and colors
        self.left_panel = wx.Panel(self.panel)
        self.left_sizer = wx.BoxSizer(wx.VERTICAL)

        # Pattern selection
        self.pattern_panel = wx.ScrolledWindow(self.left_panel, size=(550, 250))
        self.pattern_panel.SetScrollRate(10, 10)
        self.pattern_sizer = wx.GridSizer(rows=0, cols=7, vgap=5, hgap=5)
        self.pattern_panel.SetSizer(self.pattern_sizer)
        # self.pattern_panel.SetForegroundColour((100,255,100))
        # # self.pattern_panel.SetForegroundColour((0, 0, 0))
        self.left_sizer.Add(self.pattern_panel, 1, wx.EXPAND | wx.ALL, 5)

        # Color selection
        self.color_panel = wx.Panel(self.left_panel)
        self.color_sizer = wx.GridSizer(rows=2, cols=8, vgap=2, hgap=2)
        self.color_buttons = []
        for i in range(16):
            btn = wx.Button(self.color_panel, size=(40, 40))
            btn.SetBackgroundColour(wx.Colour(*MC_COLORS[i]))
            btn.SetToolTip(COLOR_NAMES[i])
            btn.Bind(wx.EVT_BUTTON, lambda evt, idx=i: self.on_color_select(idx))
            self.color_sizer.Add(btn, 0, wx.EXPAND)
            self.color_buttons.append(btn)
        self.color_panel.SetSizer(self.color_sizer)
        self.left_sizer.Add(self.color_panel, 0, wx.ALIGN_CENTER | wx.ALL, 5)

        self.left_panel.SetSizer(self.left_sizer)
        self.main_sizer.Add(self.left_panel, 1, wx.EXPAND)

        # Right panel for preview and NBT
        self.right_panel = wx.Panel(self.panel)
        self.right_sizer = wx.BoxSizer(wx.VERTICAL)

        # Preview
        self.preview_bitmap = wx.StaticBitmap(self.right_panel, size=(PREVIEW_WIDTH, PREVIEW_HEIGHT))
        self.right_sizer.Add(self.preview_bitmap, 0, wx.ALIGN_CENTER | wx.ALL, 10)

        # Base color selection label
        self.base_color_label = wx.StaticText(self.right_panel, label="Base Color:")
        self.right_sizer.Add(self.base_color_label, 0, wx.ALL, 5)

        # Base color preview
        self.base_color_preview = wx.Panel(self.right_panel, size=(50, 50))
        self.base_color_preview.SetBackgroundColour(wx.Colour(*MC_COLORS[0]))
        self.right_sizer.Add(self.base_color_preview, 0, wx.ALL, 5)

        # NBT output
        self.nbt_output = wx.TextCtrl(self.right_panel, style=wx.TE_MULTILINE | wx.TE_READONLY, size=(200, 150))
        self.right_sizer.Add(self.nbt_output, 0, wx.EXPAND | wx.ALL, 5)

        # Buttons
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.build_button = wx.Button(self.right_panel, label="Save")
        self.clear_button = wx.Button(self.right_panel, label="Clear Layers")
        self.undo_button = wx.Button(self.right_panel, label="Undo Last")

        self.build_button.Bind(wx.EVT_BUTTON, self.on_save)
        self.clear_button.Bind(wx.EVT_BUTTON, self.on_clear_layers)
        self.undo_button.Bind(wx.EVT_BUTTON, self.on_undo_pattern)

        button_sizer.Add(self.build_button, 0, wx.ALL, 5)
        button_sizer.Add(self.clear_button, 0, wx.ALL, 5)
        button_sizer.Add(self.undo_button, 0, wx.ALL, 5)

        self.right_sizer.Add(button_sizer, 0, wx.ALIGN_CENTER)

        self.right_panel.SetSizer(self.right_sizer)
        self.main_sizer.Add(self.right_panel, 0, wx.EXPAND)

        self.panel.SetSizer(self.main_sizer)

        # Initialize
        self.selected_pattern_index = None
        self.layered_selection = []
        self.base_color_index = 0  # Default to White
        self.load_images()
        self.display_patterns()
        self.status_bar = self.CreateStatusBar(2)
        self.status_bar.SetStatusWidths([-3, -1])
        self.update_status_bar()

    def on_undo_pattern(self, event):
        if self.layered_selection:
            # Remove the last added pattern
            self.layered_selection.pop()
            self.update_preview()
            self.SetStatusText("Last pattern removed", 0)
        else:
            self.SetStatusText("No patterns to undo", 0)

    def load_images(self):
        banner = base64.b64decode(BANNER['ICONS'])
        buffer = io.BytesIO(banner)
        base = wx.Image()
        # base.LoadFile(buffer, wx.BITMAP_TYPE_PNG)
        base = Image.open(buffer)
        self.base_images = []
        self.pattern_images = []

        for i in range(IMAGE_COUNT):
            # Load and resize the image
            img = base.crop((i * ORIGINAL_WIDTH, 0, (i + 1) * ORIGINAL_WIDTH, ORIGINAL_HEIGHT))
            img = img.resize((PATTERN_WIDTH, PATTERN_HEIGHT), Image.NEAREST)

            # Convert to black while maintaining transparency
            img = img.convert("RGBA")
            data = numpy.array(img)

            # Set all non-transparent pixels to black (29, 29, 33)
            mask = data[:, :, 3] > 0
            data[mask, 0] = 255  # R
            data[mask, 1] = 255  # G
            data[mask, 2] = 255  # B

            # Alpha channel remains unchanged

            black_img = Image.fromarray(data)
            self.base_images.append(black_img)
            self.pattern_images.append(black_img)

    def display_patterns(self):
        """Display patterns with proper ordering and black background"""
        self.pattern_panel.SetBackgroundColour(wx.RED)

        # Create buttons in the correct order (0-42)
        for pattern_idx in (PATTERN_KEY_TO_NAME.keys()):
            if pattern_idx < 2:
                continue

            img = self.pattern_images[pattern_idx]
            rgba_img = img.convert('RGBA')
            data = numpy.array(rgba_img)

            # Create black background for transparent areas
            background = Image.new('RGBA', img.size, (0, 0, 0, 255))
            composite = Image.alpha_composite(background, rgba_img)

            # Create bitmap with black background
            bmp = wx.Bitmap.FromBufferRGBA(*composite.size, numpy.array(composite))

            # Create button with tooltip showing pattern name
            btn = wx.BitmapButton(
                self.pattern_panel,
                id=pattern_idx,
                bitmap=bmp,
                size=(PATTERN_WIDTH, PATTERN_HEIGHT)
            )
            btn.SetBackgroundColour(wx.BLACK)
            btn.SetToolTip(PATTERN_KEY_TO_NAME[pattern_idx][1])
            btn.Bind(wx.EVT_BUTTON, self.on_select_pattern)
            self.pattern_sizer.Add(btn, 0, wx.ALL, 1)

        self.pattern_panel.Layout()
        self.pattern_panel.Refresh()

    def on_select_pattern(self, event):
        # Reset previous selection if exists
        if self.selected_pattern_button:
            self.selected_pattern_button.SetBackgroundColour(wx.Colour(0, 0, 0))  # Black
            self.selected_pattern_button.Refresh()

        # Set new selection
        self.selected_pattern_index = event.GetId()
        self.selected_pattern_button = event.GetEventObject()
        self.selected_pattern_button.SetBackgroundColour(wx.Colour(255, 255, 0))  # Yellow highlight
        self.selected_pattern_button.Refresh()

    def on_color_select(self, color_index):
        if self.selected_pattern_index is None:
            # Set base color
            self.base_color_index = color_index
            self.base_color_preview.SetBackgroundColour(wx.Colour(*MC_COLORS[color_index]))
            self.base_color_preview.Refresh()
        else:
            # Add pattern layer
            self.layered_selection.append((self.selected_pattern_index, color_index))

            # Reset selection after color is chosen
            if self.selected_pattern_button:
                self.selected_pattern_button.SetBackgroundColour(wx.Colour(0, 0, 0))
                self.selected_pattern_button.Refresh()
            self.selected_pattern_index = None
            self.selected_pattern_button = None

        self.update_preview()

    def apply_color_filter(self, img, color):
        """Apply color while preserving transparency"""
        img = img.convert('RGBA')
        data = numpy.array(img)

        # Only modify non-transparent pixels
        mask = data[:, :, 3] > 0
        data[mask, :3] = color  # Set RGB for non-transparent pixels
        # Leave alpha channel as is

        return Image.fromarray(data)

    def update_preview(self):
        # Create blank canvas
        preview = Image.new("RGBA", (PREVIEW_WIDTH, PREVIEW_HEIGHT), (0, 0, 0, 0))

        # Apply base color to a solid rectangle (no pattern)
        base_color = MC_COLORS[self.base_color_index]
        base_layer = Image.new("RGBA", (PREVIEW_WIDTH, PREVIEW_HEIGHT), (*base_color, 255))
        preview = Image.alpha_composite(preview, base_layer)

        # Apply each pattern layer
        for pattern_idx, color_idx in self.layered_selection:
            pattern_img = self.pattern_images[pattern_idx].resize((PREVIEW_WIDTH, PREVIEW_HEIGHT))
            colored_pattern = self.apply_color_filter(pattern_img, MC_COLORS[color_idx])
            preview = Image.alpha_composite(preview, colored_pattern)

        # Convert to wx bitmap and display
        wx_img = wx.Bitmap.FromBufferRGBA(PREVIEW_WIDTH, PREVIEW_HEIGHT, preview.tobytes())
        self.preview_bitmap.SetBitmap(wx_img)
        self.nbt_output.SetValue(self.generate_bedrock_nbt())
        self.panel.Layout()
        self.update_status_bar()

    def update_status_bar(self):
        if not self.layered_selection:
            self.SetStatusText("No patterns added", 0)
        else:
            last_pattern_idx, last_color_idx = self.layered_selection[-1]
            pattern_name = PATTERN_KEY_TO_NAME[last_pattern_idx][1]
            color_name = COLOR_NAMES[last_color_idx]
            self.SetStatusText(f"Last: {pattern_name} ({color_name})", 0)
        self.SetStatusText(f"Total: {len(self.layered_selection)} layers", 1)

    def generate_bedrock_nbt(self):
        """Generate proper Bedrock NBT data with correct pattern names"""
        base_color = COLOR_NAMES[self.base_color_index].lower().replace(" ", "_")

        patterns = ListTag([])
        for pattern_idx, color_idx in self.layered_selection:
            if pattern_idx in PATTERN_KEY_TO_NAME:
                pattern_code = PATTERN_KEY_TO_NAME[pattern_idx][0]
                color_name = COLOR_NAMES[color_idx].lower().replace(" ", "_")
                patterns.append( CompoundTag({
                    "Color": IntTag(color_idx),
                    "Pattern": StringTag(pattern_code)
                }))
        self.damage_color = ShortTag(self.base_color_index)
        self.nbt_data = CompoundTag({
            "Patterns": patterns,
            "Type": IntTag(0),  # Default banner type
        })

        return self.nbt_data.to_snbt(2)

    def on_save(self, event):
        print(self.nbt_data, self.damage_color )
        _self = self._self
        key, slot = _self.Get_slot_map_key()
        keys = _self.editor.keys + [key,slot]
        current_nbt = _self.editor.selected_player[keys]
        if not current_nbt.get('tag', None):
            current_nbt['tag'] = CompoundTag({})
        if 'shield' in current_nbt['Name'].py_str:

            current_nbt['tag']['Patterns'] = self.nbt_data['Patterns']
            current_nbt['tag']['Type'] = self.nbt_data['Type']
            current_nbt['tag']['Base'] =  self.damage_color
        else:
            current_nbt['Damage'] = self.damage_color
            current_nbt['tag']['Patterns'] = self.nbt_data['Patterns']
            current_nbt['tag']['Type'] = self.nbt_data['Type']
        print(current_nbt)

    def on_clear_layers(self, event):
        self.layered_selection = []
        # Clear any pattern selection
        if self.selected_pattern_button:
            self.selected_pattern_button.SetBackgroundColour(wx.Colour(0, 0, 0))
            self.selected_pattern_button.Refresh()
            self.selected_pattern_index = None
            self.selected_pattern_button = None
        self.update_preview()
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
class ColorChoiceDialog(wx.Dialog):
    def __init__(self, parent, label="block"):
        super().__init__(parent, title=f"Choose a {label.lower()} color")
        self.selected_index = None

        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)
        grid_sizer = wx.GridSizer(rows=4, cols=4, hgap=5, vgap=5)

        for i in range(16):
            btn = wx.Button(panel, size=(40, 40))
            btn.SetBackgroundColour(wx.Colour(*MC_COLORS[i]))
            btn.SetToolTip(COLOR_NAMES[i])
            btn.Bind(wx.EVT_BUTTON, self.make_on_color_select(i))
            grid_sizer.Add(btn, 0, wx.EXPAND)

        panel.SetSizer(grid_sizer)
        sizer.Add(panel, 0, wx.ALL | wx.CENTER, 10)
        self.SetSizerAndFit(sizer)

    def make_on_color_select(self, idx):
        def handler(event):
            self.selected_index = idx
            self.EndModal(wx.ID_OK)
        return handler

    def get_selection(self):
        if self.selected_index is not None:
            return COLOR_NAMES[self.selected_index]
        return None
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
                dlg = ColorChoiceDialog(parent_panel, label="Block")
                if dlg.ShowModal() == wx.ID_OK:
                    choice = dlg.get_selection()
                    if choice:
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

    def banner_editor(self, event, _self):
        banner_select = BannerSelector(self, _self)
        banner_select.Show(True)

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
            return# raise ValueError(f"Source slot {source_slot} not found")
        # if target_index is None and target_static:
            # raise ValueError(f"Target slot {target_slot} not found in static list")

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


        # if self.is_mouse_down and event.Dragging() and event.LeftIsDown():
        #     if not self.dragging:
        #         self.StartDrag(event)



        if (
                hasattr(self, "dragging")
                and self.drag_image is not None
                and isinstance(self.drag_image, wx.DragImage)
                and event.Dragging()
                and event.LeftIsDown()
        ):
            pos = event.GetPosition()

            self.drag_image.Move(pos)
    def OnMouseDown(self, event):
        self.drag_start_pos = event.GetPosition()
        self.is_mouse_down = True
        event.Skip()

        """Handles mouse down event to start the copy or delete logic."""
        pos = event.GetPosition()
        screen_pos = event.GetEventObject().ClientToScreen(pos)
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
        self.drag_image.BeginDrag((30, 30), self.button, fullScreen=True)
        self.drag_image.Move(screen_pos)
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


            # Convert to screen coordinates
            screen_pos = event.GetEventObject().ClientToScreen(pos)
            self.drag_image = wx.DragImage(image)
            self.drag_image.BeginDrag((0, 0), button, fullScreen=True)
            self.drag_image.Move(screen_pos)
            self.drag_image.Show()
            self.copy_tag_and_slot(event)
            self.dragging = True
        except:
            # print('some error was ignored')
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

            if any(t in item_name for t in ["shield", "banner"]) and 'pattern' not in item_name:
                banner = wx.MenuItem(menu, wx.ID_ANY, "Edit Banner")
                menu.Append(banner)
                self.Bind(wx.EVT_MENU, lambda e, _self=self: self.tools.banner_editor(e, _self), banner)
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
                                               "chainmail", "sword", "elytra", "mace", "brush", 'shield', 'bow',
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
            "Arrows": range(939, 950),
            "More Arrows": range(950, 979),
            "Most_used(may not work)": [982, 1214, 1696, 1046],
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
#############End Inventory Editor
villager_workstations = {
            "fisherman": "barrel",
            "armorer": "blast_furnace",
            "cleric": "brewing_stand",
            "cartographer": "cartography_table",
            "leatherworker": "cauldron",
            "farmer": "composter",
            "fletcher": "fletching_table",
            "weaponsmith": "grindstone",
            "librarian": "lectern",
            "shepherd": "loom",
            "toolsmith": "smithing_table",
            "butcher": "smoker",
            "mason": "stonecutter",
            "": None
        }
workstation_to_profession = {v: k for k, v in villager_workstations.items() if v is not None}
class RemapVillagers(wx.Frame):
    def __init__(self, parent, canvas, world,  *args, **kw):
        super(RemapVillagers, self).__init__(parent, *args, **kw,
                                              style=(wx.MINIMIZE_BOX | wx.MAXIMIZE_BOX | wx.RESIZE_BORDER |
                                                     wx.SYSTEM_MENU | wx.CAPTION | wx.CLOSE_BOX | wx.CLIP_CHILDREN |
                                                     wx.FRAME_FLOAT_ON_PARENT),
                                              title="Village Data")

        self.parent = parent
        self.canvas = canvas
        self.world = world
        self.village_locations = {}
        self.village_dwellers = {}
        self.platform = self.world.level_wrapper.platform
        self.font = wx.Font(13, wx.FONTFAMILY_ROMAN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        self.SetForegroundColour((0, 255, 0))
        self.SetBackgroundColour((0, 0, 0))
        self.SetFont(self.font)
        self.SetMinSize((510, 320))
        self._sizer = wx.BoxSizer(wx.VERTICAL)
        self._sizer_b = wx.BoxSizer(wx.HORIZONTAL)
        self._sizer_top_buttons = wx.BoxSizer(wx.HORIZONTAL)
        self.SetSizer(self._sizer)
        self.info_text = "Click on an item in list to see more option below:"
        self.info = wx.StaticText(self, label=self.info_text)
        self.list = wx.ListBox(self, style=wx.TE_MULTILINE, size=(510, 320))
        self.del_all = wx.Button(self, label="delete all village data")
        self.re_cal = wx.Button(self, label="rebuild villager data")
        self.save_villager  = wx.Button(self, label="Save Villagers and \n Sync data")
        self.restore_villager = wx.Button(self, label="Restore Villager \n Sync data")
        self.repair_digest = wx.Button(self, label="Experimental Repair \nVillager Chunk Data")
        self.items = [
            "Cut Prices",
            "Unbreakable Diamond Tools",
            "Unlimited Trades",
            "Fully Enchanted Diamond Tools",
            "Everything costs 64",
            "Everything costs 7",
            'Remove all Enchants',
            'Random prices for everything',
            'Unlock All trades'
        ]
        self.check_list = wx.CheckListBox(self, choices=self.items)
        self.check_list.Hide()
        self.list.SetForegroundColour((0, 255, 0))
        self.list.SetBackgroundColour((0, 0, 0))
        self.list.SetFont(self.font)
        self.del_all.Bind(wx.EVT_BUTTON, self.del_village_data)
        self.re_cal.Bind(wx.EVT_BUTTON, self.poi)
        self.list.Bind(wx.EVT_LISTBOX, self.on_select_list)
        self.save_villager.Bind(wx.EVT_BUTTON, self.save_villager_data)
        self.restore_villager.Bind(wx.EVT_BUTTON, self.restore_villager_data)
        self.repair_digest.Bind(wx.EVT_BUTTON, self.repair_villager_digest_pointers)
        self._sizer_top_buttons.Add(self.save_villager, 0,  wx.LEFT, 11)
        self._sizer_top_buttons.Add(self.restore_villager, 0,  wx.LEFT, 11)
        self._sizer_top_buttons.Add(self.del_all, 0,  wx.LEFT, 11)
        self._sizer_top_buttons.Add(self.re_cal, 0,  wx.LEFT, 11) #self.repair_digest
        self._sizer_top_buttons.Add(self.repair_digest, 0, wx.LEFT, 11)  # self.repair_digest
        self._sizer.Add(self._sizer_top_buttons)
        self._sizer.Add(self.info, 0,  wx.LEFT, 21)
        self._sizer_b.Add(self.list)
        self._sizer_b.Add(self.check_list)
        self._sizer.Add(self._sizer_b)

        #self.progress = ProgressBar()
        self.get_villager_locations()
        self.Fit()
        self.Layout()

    def dim_village_name(self):
        dim_name_part = b''
        if 'minecraft:the_end' in self.canvas.dimension:
            dim_name_part = b'VILLAGE_TheEnd_'
        elif 'minecraft:the_nether' in self.canvas.dimension:
            dim_name_part = b'VILLAGE_Nether_'
        elif 'minecraft:overworld' in self.canvas.dimension:
            dim_name_part = b'VILLAGE_Overworld_'
        return dim_name_part

    def make_instances(self, list_of_poi : dict):
        vill_type_map = {
            'butcher': {'SoundEvent': 'block.smoker.smoke', 'Weight': 5, 'InitEvent': 'minecraft:become_butcher'},
            'fletcher': {'SoundEvent': 'block.fletching_table.use', 'Weight': 5,
                         'InitEvent': 'minecraft:become_fletcher'},
            'toolsmith': {'SoundEvent': 'block.smithing_table.use', 'Weight': 5,
                          'InitEvent': 'minecraft:become_toolsmith'},
            'cartographer': {'SoundEvent': 'block.cartography_table.use', 'Weight': 6,
                             'InitEvent': 'minecraft:become_cartographer'},
            'weaponsmith': {'SoundEvent': 'block.grindstone.use', 'Weight': 5,
                            'InitEvent': 'minecraft:become_weaponsmith'},
            'armorer': {'SoundEvent': 'block.blastfurnace.fire_crackle', 'Weight': 5,
                        'InitEvent': 'minecraft:become_armorer'},
            'shepherd': {'SoundEvent': 'block.loom.use', 'Weight': 3, 'InitEvent': 'minecraft:become_shepherd'},
            'leatherworker': {'SoundEvent': 'bucket.fill.water', 'Weight': 5,
                              'InitEvent': 'minecraft:become_leatherworker'},
            'librarian': {'SoundEvent': 'item.book.put', 'Weight': 8, 'InitEvent': 'minecraft:become_librarian'},
            'mason': {'SoundEvent': 'block.stonecutter.use', 'Weight': 3, 'InitEvent': 'minecraft:become_mason'},
            'cleric': {'SoundEvent': 'potion.brewed', 'Weight': 8, 'InitEvent': 'minecraft:become_cleric'},
            'fisherman': {'SoundEvent': 'block.barrel.open', 'Weight': 3, 'InitEvent': 'minecraft:become_fisherman'},
            'farmer': {'SoundEvent': 'block.composter.fill', 'Weight': 1, 'InitEvent': 'minecraft:become_farmer'},
            'none': {'SoundEvent': '', 'Weight': 0, 'InitEvent': ''},
        }
        def instances_of(x,y,z,ie='',name='villager',radius=0.75,_type=0,sound='undefined',weight=1, useaabb=1):
            tag_ = CompoundTag({
                "Capacity" : LongTag(1),
                'InitEvent': StringTag(ie),
                'Name': StringTag(name),
                'OwnerCount': LongTag(1),
                'Radius': FloatTag(radius),
                'Skip': ByteTag(0),
                'SoundEvent': StringTag(sound),
                'Type': IntTag(_type),
                'UseAABB': ByteTag(useaabb),
                'Weight': LongTag(weight),
                'X': IntTag(x),
                'Y': IntTag(y),
                'Z': IntTag(z),
            })
            return tag_

        bed, work, pof = (list_of_poi.get('bed',(0,0,0)),list_of_poi.get('work',(0,0,0)) ,
                          list_of_poi.get('profession', 'none'))
        inst = ListTag([])
        x,y,z = bed
        inst.append(instances_of(x,y,z))
        inst.append(CompoundTag({'Skip':ByteTag(1)}))
        x, y, z = work

        v_data = vill_type_map.get(list_of_poi.get(pof,'none'))

        inst.append(instances_of(x,y,z,
                                ie=v_data['InitEvent'],name=pof,radius=2,_type=2,
                                sound=v_data['SoundEvent'],weight=v_data['Weight'],useaabb=0 ))
        return inst

    def make_new_village_poi(self, list_of_villagers):
        poi_dict = {}
        for v_id,data in list_of_villagers.items():
            poi = CompoundTag({'POI': ListTag([])})
            for uid in data.keys():
                poi["POI"].append(CompoundTag({'VillagerID': LongTag(uid), 'instances': self.make_instances(data[uid])}))
            poi_dict[v_id] = poi
        return poi_dict

    def calculate_village_boundaries(self, clusters, radius=32):
        """
        Calculates village boundaries for each cluster.

        Args:
            clusters (list of list): List of clusters, where each cluster is a list of bed coordinates.
            radius (int): Radius to expand the boundary.

        Returns:
            list of dict: A list of boundaries for each cluster as dictionaries with min/max for x, y, z.
        """
        boundaries = collections.defaultdict(dict)

        for cluster in clusters:
            min_x = min(bed[0] for bed in cluster) - radius
            max_x = min(bed[0] for bed in cluster) + radius
            min_y = min(bed[1] for bed in cluster) - 12
            max_y = max(bed[1] for bed in cluster) + 12
            min_z = max(bed[2] for bed in cluster) - radius
            max_z = max(bed[2] for bed in cluster) + radius

            boundaries[str(uuid.uuid4())].update({
                "X0": min_x,
                "X1": max_x,
                "Y0": min_y,
                "Y1": max_y,
                "Z0": min_z,
                "Z1": max_z,
            })

        return boundaries

    def find_villager_key(self, villager_x, villager_y, villager_z, bounding_dict):
        for key, bounds in bounding_dict.items():
            if (bounds['X0'] <= villager_x <= bounds['X1'] and
                    bounds['Y0'] <= villager_y <= bounds['Y1'] and
                    bounds['Z0'] <= villager_z <= bounds['Z1']):
                return key
        return None  # Return None if no match is found

    def cluster_beds_by_radius(self, beds, radius=32):
        """
        Groups beds into clusters based on a given radius.

        Args:
            beds (list of tuple): List of bed coordinates (x, y, z).
            radius (int): Radius within which beds are clustered.

        Returns:
            list of list: A list of clusters, where each cluster is a list of bed coordinates.
        """
        clusters = []
        visited = set()

        def dfs(bed, cluster):
            visited.add(bed)
            cluster.append(bed)
            for other_bed in beds:
                if other_bed not in visited:
                    dx, dy, dz = abs(bed[0] - other_bed[0]), abs(bed[1] - other_bed[1]), abs(bed[2] - other_bed[2])
                    if dx <= radius and dy <= radius and dz <= radius:
                        dfs(other_bed, cluster)

        for bed in beds:
            if bed not in visited:
                cluster = []
                dfs(bed, cluster)
                clusters.append(cluster)

        return clusters
    def on_select_list(self,_):
        try:
            self._sizer.Remove(self.sizer)
        except:
            pass
        self.sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.go_to = wx.Button(self, label="Go to location")
        self.select_center = wx.Button(self, label="Select Center")
        self.select_village_bounds = wx.Button(self, label="Select Bounds")
        self.super_trade = wx.Button(self, label="Apply Super Trading")

        self.go_to.Bind(wx.EVT_BUTTON, self.set_go_to)
        self.select_center.Bind(wx.EVT_BUTTON, self.set_select_center)
        self.select_village_bounds.Bind(wx.EVT_BUTTON, self.set_village_bounds)
        self.super_trade.Bind(wx.EVT_BUTTON, self.set_villager_trades)
        self.check_list.Show()
        self.sizer.Add(self.go_to, 0,  wx.LEFT, 11)
        self.sizer.Add(self.select_center, 0,  wx.LEFT, 11)
        self.sizer.Add(self.select_village_bounds, 0,  wx.LEFT, 11)
        self.sizer.Add(self.super_trade, 0,  wx.LEFT, 161)
        self._sizer.Add(self.sizer)
        self.Fit()
        self.Layout()

    def set_go_to(self, _):
        data = self.village_locations[self.list.GetStringSelection()]
        a,b,c,d,e,f = data['center']
        self.canvas.camera.set_location((a,b+40,c))

    def set_select_center(self, _):
        data = self.village_locations[self.list.GetStringSelection()]
        a, b, c, d, e, f = data['center']
        sel = SelectionGroup(SelectionBox((a,b,c),(d,e,f)))
        self.canvas.selection.set_selection_group(sel)
        # print((a, b, c), (d, e, f))

    def set_village_bounds(self, _):
        data = self.village_locations[self.list.GetStringSelection()]
        a, b, c, d, e, f = data['bounds']
        sel = SelectionGroup(SelectionBox((a, b, c), (d, e, f)))
        self.canvas.selection.set_selection_group(sel)
        # print((a, b, c), (d, e, f), self.village_locations)


    def set_new_location(self, new_map_bed_and_work, location_station):
        def find_adjacent_key(target_key, key_dict):
            tx, ty, tz = target_key

            for k in key_dict.keys():

                dx, dy, dz = k[0] - tx, k[1] - ty, k[2] - tz
                diffs = [dx, dy, dz]

                # Must have one value as +1 or -1, rest must be 0
                if diffs.count(0) == 2 and any(abs(d) == 1 for d in diffs):
                    return k  # Return the first valid match

            return None  # If no match found
        updated_actors = collections.defaultdict(dict)
        for k,v in list(new_map_bed_and_work.items()):

            for ik,iv in v.items():

                uid = ik
                uuid = struct.pack('<q', uid)
                acnt, wrldcnt = struct.unpack('<LL', uuid)
                wc = 4294967296 - wrldcnt
                prefix = struct.pack('>LL', wc, acnt)  # convert the ID to actor prefix
                data = self.level_db.get(b'actorprefix' + prefix)
                act_nbt = load(data, compressed=False, little_endian=True,
                                          string_decoder=utf8_escape_decoder).compound
                if 'minecraft:villager_v2' in  act_nbt.get('identifier', StringTag()).py_str:
                    newkey = find_adjacent_key(iv['villager'], location_station)

                    act_nbt['PreferredProfession'] = StringTag(workstation_to_profession[location_station[newkey]])
                    act_nbt.pop('Offers', None)#act_nbt['Offers'] = CompoundTag({})
                    preferred_profession = act_nbt['PreferredProfession'].py_str
                    act_nbt['TradeTablePath'] = StringTag(f'trading/economy_trades/{preferred_profession}_trades.json')
                    # act_nbt.pop('definitions')
                    act_nbt['definitions'] = ListTag([
                        StringTag('+minecraft:villager_v2'),
                        StringTag(f'+{preferred_profession}'),
                        StringTag('-trade_resupply_component_group'),
                        StringTag('-play_schedule_villager'),
                        StringTag('-baby'),
                        StringTag('+make_and_receive_love')
                    ])
                    raw_new = act_nbt.save_to(compressed=False, little_endian=True,string_encoder=utf8_escape_encoder)
                    updated_actors[b'actorprefix' + prefix] = raw_new

        for k, v in updated_actors.items():
            self.level_db.put(k, v)

    def set_villager_trades(self, _):
        ENCHANTMENTS = {
            "fletcher": {
                "minecraft:bow": [
                    (19, 5),  # Power V
                    (34, 4),  # Piercing IV
                    (22, 1),  # Infinity I
                    (17, 3),  # Unbreaking III
                ]
            },
            "weaponsmith": {
                "minecraft:diamond_sword": [
                    (14, 4),  # Looting IV
                    (13, 2),  # Fire Aspect II
                    (15, 10),  # Efficiency X
                    (17, 3),  # Unbreaking III
                    (26, 1),  # Mending I
                ],
                "minecraft:diamond_axe": [
                    (16, 1),  # Silk Touch I
                    (18, 4),  # Fortune IV
                    (15, 10),  # Efficiency X
                    (17, 3),  # Unbreaking III
                    (26, 1),  # Mending I
                ]
            },
                "toolsmith": {
                "minecraft:diamond_pickaxe": [
                    (16, 1),  # Silk Touch I
                    (18, 4),  # Fortune IV
                    (15, 10),  # Efficiency X
                    (17, 3),  # Unbreaking III
                    (26, 1),  # Mending I
                ],
                "minecraft:diamond_shovel": [
                    (16, 1),  # Silk Touch I
                    (18, 4),  # Fortune IV
                    (15, 10),  # Efficiency X
                    (17, 3),  # Unbreaking III
                    (26, 1),  # Mending I
                ],
                "minecraft:diamond_hoe": [
                    (16, 1),  # Silk Touch I
                    (18, 4),  # Fortune IV
                    (15, 10),  # Efficiency X
                    (17, 3),  # Unbreaking III
                    (26, 1),  # Mending I
                ],
                    "minecraft:diamond_axe": [
                        (16, 1),  # Silk Touch I
                        (18, 4),  # Fortune IV
                        (15, 10),  # Efficiency X
                        (17, 3),  # Unbreaking III
                        (26, 1),  # Mending I
                    ]
            },
            "armorer": {
                "minecraft:diamond_helmet": [
                    (8, 3),  # Aqua Affinity
                    (6, 3),  # Respiration III
                    (5, 3),  # Thorns III
                    (0, 5),  # Protection IV
                    (1, 5),  # Fire Protection IV
                    (3, 5),  # Blast Protection IV
                    (5, 5),  # Projectile Protection IV
                    (17, 3),  # Unbreaking III
                    (26, 1),  # Mending I
                ],
                "minecraft:diamond_chestplate": [
                    (5, 3),  # Thorns III
                    (0, 5),  # Protection IV
                    (1, 5),  # Fire Protection IV
                    (3, 5),  # Blast Protection IV
                    (5, 5),  # Projectile Protection IV
                    (17, 3),  # Unbreaking III
                    (26, 1),  # Mending I
                ],
                "minecraft:diamond_leggings": [
                    (37, 5),  # Swift Sneak V
                    (5, 3),  # Thorns III
                    (0, 5),  # Protection IV
                    (1, 5),  # Fire Protection IV
                    (3, 5),  # Blast Protection IV
                    (5, 5),  # Projectile Protection IV
                    (17, 3),  # Unbreaking III
                    (26, 1),  # Mending
                ],
                "minecraft:diamond_boots": [

                    (7, 3),  # Deep Walker
                    (25, 2),  # Frost Walker
                    (2, 4),  # Feather Falling
                    (36, 3),  # Soul Speed
                    (5, 3),  # Thorns III
                    (0, 5),  # Protection IV
                    (1, 5),  # Fire Protection IV
                    (3, 5),  # Blast Protection IV
                    (5, 5),  # Projectile Protection IV
                    (17, 3),  # Unbreaking III
                    (26, 1),  # Mending
                ]
            }
        }
        flags = {  # this causes the enchantments to alternate between tools
            'minecraft:diamond_boots': False,
            'minecraft:diamond_pickaxe': False,
            'minecraft:diamond_axe': False,
            'minecraft:diamond_shovel': False,
            'minecraft:diamond_hoe': False
        }
        def split_value(val):
            if val == 1:
                return 1
            half = val // 2
            return half

        def apply_enchantments(r, profession):

            def toggle_enchantment(flag_name):
                if flags[flag_name]:
                    r['sell']['tag']['ench'].pop(0)
                    flags[flag_name] = False
                else:
                    r['sell']['tag']['ench'].pop(1)
                    flags[flag_name] = True
            item_name = str(r['sell'].get('Name'))

            if item_name in ENCHANTMENTS.get(profession, {}):
                if 6 in self.check_list.GetCheckedItems(): # remove ench
                    list_ench = CompoundTag({'ench': ListTag([])})
                    r['sell']['tag'] = list_ench

                if 3 in self.check_list.GetCheckedItems():
                    list_ench = CompoundTag({'ench': ListTag([
                        CompoundTag({'id': ShortTag(e_id), 'lvl': ShortTag(e_lvl)}) for e_id, e_lvl in
                        ENCHANTMENTS[profession][item_name]])})
                    r['sell']['tag'] = list_ench
                    if item_name in flags.keys():
                        toggle_enchantment(item_name)
                if 1 in self.check_list.GetCheckedItems():
                    r['sell']['tag']['Unbreakable'] = ByteTag(1)  # Make item unbreakable

        selection = self.list.GetStringSelection()
        sel_byte = selection.split(':')[1].encode()
        import random
        for k, v in self.level_db.iterate(start=b'VILLAGE', end=b'\xFF' * 40):  # long end
            if sel_byte + b'_DWELLERS' in k:

                updated_actors = {}
                nbt_dwellers = load(v, compressed=False, little_endian=True,
                                string_decoder=utf8_escape_decoder).compound
                for c in nbt_dwellers.get('Dwellers'):
                    if c.get('actors'):
                        for a in c.get('actors'):
                            uid = a.get('ID').py_data
                            uuid = struct.pack('<q', uid)
                            acnt, wrldcnt = struct.unpack('<LL', uuid)
                            wc = 4294967296 - wrldcnt
                            prefix = struct.pack('>LL', wc, acnt) # convert the ID to actor prefix
                            data = self.level_db.get(b'actorprefix'+prefix)
                            act_nbt = load(data,compressed=False, little_endian=True,
                                           string_decoder=utf8_escape_decoder).compound

                            preferred_profession = str(act_nbt.get('PreferredProfession'))

                            definitions = str(act_nbt.get('definitions'))
                            # print(preferred_profession, definitions)
                            if 8 in self.check_list.GetCheckedItems():
                                act_nbt['TradeExperience'] = IntTag(500)
                            if act_nbt.get('Offers', None):
                                offers = act_nbt.get('Offers')
                                recipes = offers.get('Recipes')

                                for r in recipes:

                                    if 7 in self.check_list.GetCheckedItems():
                                        if r.get('buyCountA'):
                                            r['buyCountA'] = IntTag(random.randint(4, 50))
                                            r['buyA']['Count'] = IntTag(random.randint(4, 50))

                                    if 5 in self.check_list.GetCheckedItems():
                                        if r.get('buyCountA'):
                                            r['buyCountA'] = IntTag(7)
                                            r['buyA']['Count'] = IntTag(7)

                                    if 4 in self.check_list.GetCheckedItems():
                                        if r.get('buyCountA'):
                                            r['buyCountA'] = IntTag(64)
                                            r['buyA']['Count'] = IntTag(64)

                                    if 0 in self.check_list.GetCheckedItems():
                                        if r.get('buyCountA'):
                                            current_v = r.get('buyCountA').py_int
                                            new_val = split_value(current_v)
                                            r['buyCountA'] = IntTag(new_val)
                                            r['buyA']['Count'] = IntTag(new_val)

                                    if preferred_profession in ENCHANTMENTS:
                                        apply_enchantments(r, preferred_profession)
                                    if 2 in self.check_list.GetCheckedItems():
                                        r['maxUses'] = IntTag(999999999)

                            raw_new = act_nbt.save_to(compressed=False, little_endian=True,
                                                      string_encoder=utf8_escape_encoder)
                            updated_actors[b'actorprefix'+prefix] = raw_new
                for k, v in updated_actors.items():
                    self.level_db.put(k,v)

    def repair_villager_digest_pointers(self, _):
        for k, v in self.level_db.iterate(start=b'VILLAGE', end=b'\xFF' * 40):
            if b'DWELLERS' in k:
                nbt_dwellers = load(v, compressed=False, little_endian=True,
                                    string_decoder=utf8_escape_decoder).compound
                for c in nbt_dwellers.get('Dwellers'):
                    raw_dig_dict = collections.defaultdict(list)
                    if c.get('actors'):
                        for a in c.get('actors'):
                            uid = a.get('ID').py_data
                            uuid = struct.pack('<q', uid)
                            acnt, wrldcnt = struct.unpack('<LL', uuid)
                            wc = 4294967296 - wrldcnt
                            prefix = struct.pack('>LL', wc, acnt)  # convert the ID to actor prefix
                            data = self.level_db.get(b'actorprefix' + prefix)
                            act_nbt = load(data, compressed=False, little_endian=True,
                                           string_decoder=utf8_escape_decoder).compound
                            x,y,z = act_nbt['Pos']
                            xc,zc = block_coords_to_chunk_coords(x,z)
                            raw_digp = struct.pack('<4sii', b'digp', xc, zc)
                            raw_dig_dict[raw_digp].append(prefix)
                        for k,d in raw_dig_dict.items():

                            real = self.level_db.get(k)
                            for p in d:
                                if p not in real:
                                    print(' ERROR YOU SHOULD NOT SEE')  # Really TODO HERE Just
                        #packed_digp = {}

                        # packed_digp[k] = b''.join(d)
                        # print(packed_digp)
    def get_villager_locations(self):
        items_info = []
        list_dwellers = []
        dwellers = {}
        for k, v in self.level_db.iterate(start=b'VILLAGE', end=b'\xFF' * 40):
            if b'INFO' in k:
                nbt_info = load(v, compressed=False, little_endian=True,
                               string_decoder=utf8_escape_decoder).compound
                x0,y0,z0  = nbt_info.get('X0').py_int, nbt_info.get('Y0').py_int,nbt_info.get('Z0').py_int #radious
                x1, y1, z1 =  nbt_info.get('X1').py_int,nbt_info.get('Y1').py_int,nbt_info.get('Z1').py_int #radious

                mid = tuple((a + b) // 2 for a, b in zip((x0, y0, z0), (x1, y1, z1)))
                key_list = str(k.decode()).split('_')
                items_info.append(f"{key_list[1]}:{key_list[2]}:{mid}")
                self.village_locations[f"{key_list[1]}:{key_list[2]}:{mid}"] = {'dim': key_list[1]  , 'bounds': (x0, y0, z0, x1, y1, z1),
                                                      'center': (
                                                      mid[0], mid[1], mid[2], mid[0] + 1, mid[1] + 1, mid[2] + 1)}
        self.list.SetItems(items_info)

    def restore_villager_data(self, _):
        dialog = wx.FileDialog(
            self,
            "Select a File",
            wildcard="NBT files (*.nbt)|*.nbt|All files (*.*)|*.*",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST  # No FD_MULTIPLE here
        )

        if dialog.ShowModal() == wx.ID_OK:
            file_path = dialog.GetPath()  # Single file path
            file_name = os.path.splitext(os.path.basename(file_path))[0]
            nbt_data = load(file_path, compressed=False, little_endian=True,
                            string_decoder=utf8_escape_decoder).compound
            for k, v in nbt_data.items():
                if 'villager_data' not in k:
                    raw_nbt = v.save_to(compressed=False, little_endian=True, string_encoder=utf8_escape_encoder)
                    self.level_db.put(str(fn).encode(), raw_nbt)
                else:
                    pass
                    #TODO add method to restore missing villagers no duplicates
        dialog.Destroy()

    def save_villager_data(self, _):
        dialog = wx.FileDialog(
            self, "Save Files", defaultFile= 'NAME YOU FILE', wildcard="NBT files (*.nbt)|*.nbt|All files (*.*)|*.*",
            style=wx.DD_DEFAULT_STYLE
        )

        if dialog.ShowModal() == wx.ID_OK:
            file_path = dialog.GetDirectory()  # Gets the selected file path
            # file_name = os.path.splitext(os.path.basename(file_path))[0]  # Extracts the file name without extension
            selected = self.list.GetStringSelection().split(':')[1]
            villager_list = CompoundTag({'villager_data': ListTag([])})
            for k, v in self.level_db.iterate(start=b'VILLAGE', end=b'VILLAGE\xFF' * 40):
                if selected.encode() in k:
                    if b'VILLAGE' in k:
                        nbt = load(v, compressed=False, little_endian=True, string_decoder=utf8_escape_decoder).compound
                        villager_list[k.decode()] = nbt

                    if b'DWELLERS' in k:
                        nbt_dwellers = load(v, compressed=False, little_endian=True,
                                            string_decoder=utf8_escape_decoder).compound
                        for c in nbt_dwellers.get('Dwellers'):
                            if c.get('actors'):
                                for a in c.get('actors'):
                                    uid = a.get('ID').py_data
                                    uuid = struct.pack('<q', uid)
                                    acnt, wrldcnt = struct.unpack('<LL', uuid)
                                    wc = 4294967296 - wrldcnt
                                    prefix = struct.pack('>LL', wc, acnt)  # convert the ID to actor prefix
                                    data = self.level_db.get(b'actorprefix' + prefix)
                                    act_nbt = load(data, compressed=False, little_endian=True,
                                                   string_decoder=utf8_escape_decoder).compound
                                    villager_list['villager_data'].append(act_nbt)
                    villager_list.save_to((file_path + r"\\" + 'villagers ' + ".nbt")
                                                      , compressed=False, little_endian=True,
                                                      string_encoder=utf8_escape_encoder)

        dialog.Destroy()

    def del_village_data(self,_):
        for k, v in self.level_db.iterate(start=b'VILLAGE', end=b'\xFF' * 40): #long end
            if b'VILLAGE' in k:
                self.level_db.delete(k)

        # for k, v in self.level_db.iterate(start=b'actorprefix',end=b'actorprefix\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF'):
        #     nbt = load(v,compressed=False, little_endian=True, string_decoder=utf8_escape_decoder).compound
        #     print(nbt['internalComponents']['EntityStorageKeyComponent']['StorageKey'].save_to(
        #         compressed=False, little_endian=True, string_encoder=utf8_escape_encoder))
        #
        # for k, v in self.level_db.iterate(start=b'digp', end=b'\xFF' * 12):
        #     print(k)
        #     self.level_db.delete(k)

    def poi(self, _):

        self.list.Hide()
        self.info.SetLabel('Loading.......')#self.info_text
        for k, v in self.level_db.iterate(start=b'VILLAGE', end=b'\xFF' * 40):  # long end
            if b'VILLAGE' in k:
                self.level_db.delete(k)

        pallet = self.world.block_palette.blocks
        found_stations = {}
        found_beds = {}
        location_station = {}
        location_beds = {}

        self.all_chunk = [x for x in self.world.level_wrapper.all_chunk_coords(self.canvas.dimension)]

        villager_workstations_values = set(villager_workstations.values())  # Precompute the set for faster lookup
        for i, block in enumerate(pallet):
            if block.base_name in villager_workstations_values:  # O(1) lookup time in set
                found_stations[i] = block.base_name
            elif 'bed' == block.base_name and block.properties.get('part', StringTag('')).py_str == 'head':
                found_beds[i] = block.base_name

        station_keys = set(found_stations.keys())
        bed_keys = set(found_beds.keys())
        for cx, cz in self.all_chunk:
            data = self.world.get_chunk(cx, cz, self.canvas.dimension)
            # Loop through the sections and sub-chunks
            for cy in data.blocks.sections:
                main_sub = data.blocks.get_sub_chunk(cy)
                # Get the indices of all matching stations and beds in one go
                station_locations = numpy.isin(main_sub, list(station_keys))  # Fast boolean array of station locations
                bed_locations = numpy.isin(main_sub, list(bed_keys))  # Fast boolean array of bed locations
                # Use numpy's nonzero to find the indices of matches
                station_coords = numpy.transpose(numpy.nonzero(station_locations))  # Get coordinates of matching stations
                bed_coords = numpy.transpose(numpy.nonzero(bed_locations))  # Get coordinates of matching beds
                # Update locations for stations
                for xx, yy, zz in station_coords:
                    location_station[((cx * 16) + xx, (cy * 16) + yy, (cz * 16) + zz)] = pallet[
                        main_sub[xx, yy, zz]].base_name

                  # Update locations for beds
                for xx, yy, zz in bed_coords:
                    location_beds[((cx * 16) + xx, (cy * 16) + yy, (cz * 16) + zz)] = pallet[
                        main_sub[xx, yy, zz]].base_name

            all_actor_id_location = collections.defaultdict(dict)

        self.all_digp = []
        for k, v in self.level_db.iterate(start=b'digp',end=b'digp\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF'):
            if len(v) > 0:
                self.all_digp.append(k)

        chunk_dkeys = {}
        clusters = self.cluster_beds_by_radius(list(location_beds.keys()))
        bounds = self.calculate_village_boundaries(clusters)

        for cx, cz in self.all_chunk:
            chunk_dig_key = b'digp' + self.get_dim_chunkkey(cx, cz)
            if chunk_dig_key in self.all_digp:
                digest_keys = self.level_db.get(chunk_dig_key)
                chunk_dkeys[chunk_dig_key] = [b'actorprefix' + digest_keys[i:i + 8] for i in
                                              range(0, len(digest_keys), 8)]

        for k, li in chunk_dkeys.items():
            for i, prefix in enumerate(li):
                try:
                    v = self.level_db.get(prefix)
                    nbt = load(v, compressed=False, little_endian=True, string_decoder=utf8_escape_decoder).compound
                    actor_type = nbt.get('identifier', StringTag()).py_str
                except:
                    print(f'skipping {prefix}')
                if 'minecraft:villager_v2' in actor_type:
                    x, y, z = nbt.get('Pos', ListTag()).py_data
                    dewlling_id = self.find_villager_key(int(x), int(y), int(z), bounds)
                    if nbt.get('DwellingUniqueID', None):
                        nbt['DwellingUniqueID'] = StringTag(dewlling_id)
                        raw_nbt = nbt.save_to(compressed=False, little_endian=True, string_encoder=utf8_escape_encoder)
                        self.level_db.put(prefix, raw_nbt)
                    uniqu_id = nbt.get('UniqueID', LongTag(0)).py_data
                    dwelling_unique_id = nbt.get('DwellingUniqueID', StringTag()).py_data
                    preferred_profession = nbt.get('PreferredProfession', StringTag()).py_data  # NEED TO BUILD uuid4
                    all_actor_id_location[dwelling_unique_id].update(
                        {uniqu_id: {'Pos': (int(x), int(y), int(z)),
                                    'profession': preferred_profession}})

        def euclidean_distance(t1, t2): #numpy
                return numpy.linalg.norm(numpy.array(t1) - numpy.array(t2))
        # def euclidean_distance(t1, t2): #old
        #     return math.sqrt(sum((a - b) ** 2 for a, b in zip(t1, t2)))

        takin_beds = set()  # Use sets for faster lookups
        takin_stations = set()
        villager_done = set()
        new_map_bed_and_work = collections.defaultdict(dict)

        for k, v in all_actor_id_location.items():
            for uid, vdata in v.items():
                villager_location = vdata['Pos']
                profession = vdata['profession']

                if villager_location in villager_done:
                    continue

                closest_pair_bed = None
                min_distance_bed = 50.0
                closest_pair_station = None
                min_distance_station = 50.0

                for cbed in location_beds.keys():
                    if cbed not in takin_beds:
                        distance = euclidean_distance(villager_location, cbed)
                        if distance < min_distance_bed:
                            min_distance_bed = distance
                            closest_pair_bed = cbed

                for cloc in location_station.keys():

                    if cloc not in takin_stations:
                        if location_station[cloc] in villager_workstations[profession]:
                            distance = euclidean_distance(villager_location, cloc)
                            if distance < min_distance_station:
                                min_distance_station = distance
                                closest_pair_station = cloc

                if closest_pair_bed and closest_pair_station:
                    takin_beds.add(closest_pair_bed)
                    takin_stations.add(closest_pair_station)
                    new_map_bed_and_work[k][uid] = {
                        'bed': closest_pair_bed,
                        'work': closest_pair_station,
                        'work_block': location_station[closest_pair_station],
                        'profession': profession,
                        'profession_block': villager_workstations[profession],
                        'villager': villager_location,
                        'distance_bed': min_distance_bed,
                        'distance_station': min_distance_station,
                    }
                    villager_done.add(villager_location)
                else:
                    print(f"No match found for villager {uid} at {villager_location}")

        poi_data = self.make_new_village_poi(new_map_bed_and_work)
        # this remaps the villager to the workstation they are next to : Force  changes there profession
        force_villager_typo = wx.MessageBox("You may not need this, Choose yes"
                                            " If you have villagers by the wrong Stations \n ",
                                       "Workstation Match Up ?", wx.YES_NO | wx.ICON_INFORMATION)
        if force_villager_typo == 2:
            self.set_new_location(new_map_bed_and_work, location_station)

        welling_map = {}
        world_tick = self.world.level_wrapper.root_tag.get('currentTick').py_data

        for did, v in poi_data.items():  # Dwellers needs to be in the same order as POI
            welling_map[did] = {}
            dwellers = CompoundTag(
                {'Dwellers': ListTag([CompoundTag({'actors': ListTag([])}),
                                      CompoundTag({'actors': ListTag([])}),
                                      CompoundTag({'actors': ListTag([])}),
                                      CompoundTag({'actors': ListTag([])}),
                                      ])})
            for uniqid in v['POI']:
                _uid = uniqid['VillagerID'].py_data
                d = all_actor_id_location[did][_uid]
                dwellers['Dwellers'][0]['actors'].append(
                    CompoundTag({
                        'ID': LongTag(_uid),
                        'TS': LongTag(world_tick),
                        'last_saved_pos': ListTag([
                            IntTag(d['Pos'][0]),
                            IntTag(d['Pos'][1]),
                            IntTag(d['Pos'][2]),
                        ]),
                        'last_worked': LongTag(world_tick),  # LongTag(world_tick-100),
                    })
                )
            welling_map[did] = dwellers
            # print(welling_map[did].to_snbt(), "welling_map")

        def set_villager_info(uuid_key, bounds):
            # print(f'b: {bounds} , id: {uuid_key}')
            village_info = CompoundTag({
                'BDTime': LongTag(world_tick),
                'GDTime': LongTag(world_tick),
                'Initialized': ByteTag(1),
                'MTick': LongTag(0),
                'PDTime': LongTag(world_tick),
                'RX0': IntTag(0),
                'RX1': IntTag(1),
                'RY0': IntTag(0),
                'RY1': IntTag(1),
                'RZ0': IntTag(0),
                'RZ1': IntTag(1),
                'Tick': LongTag(world_tick),
                'Version': ByteTag(1),
                'X0': IntTag(bounds[uuid_key]['X0']),
                'X1': IntTag(bounds[uuid_key]['X1']),
                'Y0': IntTag(bounds[uuid_key]['Y0']),
                'Y1': IntTag(bounds[uuid_key]['Y1']),
                'Z0': IntTag(bounds[uuid_key]['Z0']),
                'Z1': IntTag(bounds[uuid_key]['Z1']),
            })
            return village_info


        for k, d in poi_data.items():
            if len(k) > 5:  # Skip None String
                info = b''.join([self.dim_village_name(), k.encode(), b'_INFO'])
                village_key_poi = b''.join([self.dim_village_name(), k.encode(), b'_POI'])
                players = b''.join([self.dim_village_name(), k.encode(), b'_PLAYERS'])
                dwellers = b''.join([self.dim_village_name(), k.encode(), b'_DWELLERS'])
                data_dwellers = welling_map[k].save_to(compressed=False, little_endian=True,
                                                       string_encoder=utf8_escape_encoder)
                data_players = CompoundTag(
                    {'Players': ListTag([CompoundTag({'ID': LongTag(-4294967295), 'S': IntTag(10)})])})
                raw_data_player = data_players.save_to(compressed=False, little_endian=True,
                                                       string_encoder=utf8_escape_encoder)
                data = d.save_to(compressed=False, little_endian=True, string_encoder=utf8_escape_encoder)
                village_info = set_villager_info(k, bounds)
                village_info_raw = village_info.save_to(compressed=False, little_endian=True,
                                                        string_encoder=utf8_escape_encoder)
                self.level_db.put(village_key_poi, data)
                self.level_db.put(players, raw_data_player)
                self.level_db.put(dwellers, data_dwellers)
                self.level_db.put(info, village_info_raw)
        self.get_villager_locations()
        self.list.Show()
        self.info.SetLabel(self.info_text)  # self.info_text


    @property
    def level_db(self):
        level_wrapper = self.world.level_wrapper
        if hasattr(level_wrapper, "level_db"):
            return level_wrapper.level_db
        else:
            return level_wrapper._level_manager._db

    def get_dim_chunkkey(self, xx, zz):
        chunkkey = b''
        if 'minecraft:the_end' in self.canvas.dimension:
            chunkkey = struct.pack('<iii', xx, zz, 2)
        elif 'minecraft:the_nether' in self.canvas.dimension:
            chunkkey = struct.pack('<iii', xx, zz, 1)
        elif 'minecraft:overworld' in self.canvas.dimension:
            chunkkey = struct.pack('<ii', xx, zz)
        return chunkkey

class ResetVaults():
    def __init__(self, parent, canvas, world):

        self.parent = parent
        self.canvas = canvas
        self.world = world
        self.platform = self.world.level_wrapper.platform
        self.progress = ProgressBar()

    def reset_vaults(self):

        chunks = self.world.all_chunk_coords(self.canvas.dimension)
        total = len([c for c in chunks])
        cnt = 0
        for chunk in chunks:
            cnt += 1
            self.progress.progress_bar(total, cnt, title="Resetting all vaults", text="Chunk...")
            cx, cz = chunk
            if self.world.level_wrapper.platform == 'bedrock':
                key = self.get_dim_chunkkey(cx, cz)
                try:
                    self.level_db.delete(key + b'w')
                except:
                    pass
                try:
                    be_data = self.level_db.get(key + b"1")
                    nbt_data = unpack_nbt_list(be_data)
                    for d in nbt_data:
                        if "rewarded_players" in d.to_snbt():
                            print(d['data']['rewarded_players'].to_snbt())
                            d['data']['rewarded_players'] = ListTag([])

                    raw_list = pack_nbt_list(nbt_data)
                    self.level_db.put(key + b"1", raw_list)
                except:
                    pass
            else: #java
                if self.world.has_chunk(cx, cz, self.canvas.dimension):
                    chunk = self.world.level_wrapper.get_raw_chunk_data(cx, cz, self.canvas.dimension)

                    if chunk.get('block_entities', None):
                        changed = False
                        for nbt in chunk['block_entities']:
                            if "vault" in nbt.to_snbt():
                                changed = True
                                nbt['server_data'].pop('rewarded_players', None)

                        if changed:
                            self.world.level_wrapper.put_raw_chunk_data(cx, cz, chunk, self.canvas.dimension)
        wx.MessageBox("All Vaults should be reset.",
                      "INFO", wx.OK | wx.ICON_INFORMATION)

    @property
    def level_db(self):
        level_wrapper = self.world.level_wrapper
        if hasattr(level_wrapper, "level_db"):
            return level_wrapper.level_db
        else:
            return level_wrapper._level_manager._db

    def get_dim_chunkkey(self, xx, zz):
        chunkkey = b''
        if 'minecraft:the_end' in self.canvas.dimension:
            chunkkey = struct.pack('<iii', xx, zz, 2)
        elif 'minecraft:the_nether' in self.canvas.dimension:
            chunkkey = struct.pack('<iii', xx, zz, 1)
        elif 'minecraft:overworld' in self.canvas.dimension:
            chunkkey = struct.pack('<ii', xx, zz)
        return chunkkey

class ChunkManager:
    def __init__(self, parent=None, world=None, canvas=None):
        self.parent = parent
        self.canvas = canvas
        self.world = world
        self.chunks = None
        self.platform = self.world.level_wrapper.platform
        self.selection = None
        self.org_key = None
        self.last_offset_move = None
        self.y_range = get_y_range(self.canvas.dimension)
        self.chunk_and_entities = {}
        self.all_chunks = None
        if self.platform == 'bedrock':
            self.world_start_count = self.get_current_entity_count()
            self.next_slot = self.get_current_entity_count()
            self.current_dim_key = self.get_dim_bytes()

    def load_chunks(self):
        self.selection = self.create_selection_map()
        self.org_key = list(self.selection.keys())
        self.last_offset_move = min((x, z) for x, z in self.org_key)

    def the_chunks(self):

        if self.parent._all_chunks.GetValue():
            self.all_chunks = [x for x in self.world.level_wrapper.all_chunk_coords(self.canvas.dimension)]
        else:
            self.all_chunks = [x for x in self.canvas.selection.selection_group.chunk_locations()]

        self.all_chunks = ((x, z) for x, z in self.all_chunks)

    def get_chunk_data(self):
        return copy.deepcopy(self.chunks)

    def get_current_dim_key(self):
        return self.current_dim_key

    def set_current_dim_key(self, dim_key):
        self.current_dim_key = dim_key

    def create_selection_map(self):

        if self.platform == 'bedrock':
            selection_map = {
                (x, z): SelectionBox((x * 16, self.y_range[0], z * 16), (x * 16 + 16, self.y_range[1], z * 16 + 16))
                for k in self.chunks.keys() for x, z in [struct.unpack('<ii', k[0:8])]
            }
            return selection_map
        else:  # "java"
            selection_map = {
                (x, z): SelectionBox((x * 16, self.y_range[0], z * 16), (x * 16 + 16, self.y_range[1], z * 16 + 16))
                for k in self.chunks.keys() for x, z in [k]
            }
            return selection_map

    def outer_chunks(self, _range):

        out_side_chunks = {}
        inside = list(self.selection.keys())
        surrounding_coords = []
        _range -= 1
        for xx, zz in self.selection.keys():
            for i in range(xx - _range - 1, xx + _range + 2):
                for j in range(zz - _range - 1, zz + _range + 2):
                    surrounding_coords.append((i, j))

        for x, z in surrounding_coords:
            if (x, z) not in inside:
                out_side_chunks[(x, z)] = SelectionBox((x * 16, self.y_range[0], z * 16),
                                                       (x * 16 + 16, self.y_range[1], z * 16 + 16))

        return out_side_chunks

    def apply_selection(self):

        tx, tz = self.last_offset_move
        self.move_all_chunks_to(tx, tz)
        self.org_key = list(self.selection.keys())

    def move_all_chunks_to(self, target_x, target_z):
        current_x, current_z = min((x, z) for x, z in self.org_key)
        offset_x = target_x - current_x
        offset_z = target_z - current_z
        new_chunks = {}
        if self.platform == 'bedrock':

            for key in list(self.chunks.keys()):


                x, z = struct.unpack('<ii', key[0:8])
                new_x, new_z = x + offset_x, z + offset_z
                new_key = struct.pack('<ii', new_x, new_z)
                new_chunk_data = self.update_chunk_keys_entities(self.chunks[key].pop('chunk_data')
                                                                 , new_key, new_x, new_z, x, z)
                new_entitie_data = self.update_entities(self.chunks[key].pop('entitie')
                                                        , new_x, new_z)
                new_chunks[new_key] = {'chunk_data': new_chunk_data, 'entitie': new_entitie_data,
                                       'original_chunk_key': self.chunks[key].pop('original_chunk_key'),
                                       'original_digp_actor_keys': self.chunks[key].pop('original_digp_actor_keys')}
        else:
            for key in list(self.chunks.keys()):
                x, z = key
                new_x, new_z = x + offset_x, z + offset_z
                new_key = (new_x, new_z)
                new_chunk_data = self.java_chunk(self.chunks[key].pop('chunk_data')
                                                 , new_key, new_x, new_z, x, z)
                if self.chunks[key].get('entitie_data'):
                    new_entitie_data = self.java_entities(self.chunks[key].pop('entitie_data')
                                                          , new_key, new_x, new_z, x, z)
                else:
                    new_entitie_data = None
                new_chunks[new_key] = {'chunk_data': new_chunk_data, 'entitie_data': new_entitie_data}

        self.chunks = new_chunks
        if self.platform == 'java':
            self.java_save()
        else:
            self.bedrock_save()

    def java_entities(self, _chunk_entities, new_key, new_x, new_z, x, z):
        chunk_entities = _chunk_entities
        chunk_entities['Position'] = IntArrayTag([new_x, new_z])
        for e in chunk_entities.get('Entities'):
            x, y, z = e.get('Pos')
            xc, zc = new_x * 16, new_z * 16
            x_pos = x % 16
            z_pos = z % 16
            raw_pos_x = (x_pos + xc)
            raw_pos_z = (z_pos + zc)
            x, z = raw_pos_x, raw_pos_z
            e['Pos'] = ListTag([DoubleTag(x), DoubleTag(y), DoubleTag(z)])
        return chunk_entities

    def java_chunk(self, _chunk_data, new_key, new_x, new_z, x, z):
        chunk_data = _chunk_data
        chunk_data['xPos'] = IntTag(new_x)
        chunk_data['zPos'] = IntTag(new_z)
        for be in chunk_data.get('block_entities'):
            be['x'] = IntTag(new_x * 16)
            be['z'] = IntTag(new_z * 16)
        return chunk_data

    def update_chunk_keys_entities(self, chunk_dict, new_key, new_x, new_z, x_old, z_old):  # bedrock
        dim = self.current_dim_key

        new_dict = {}
        # for ik, v in list(chunk_dict.items()):
        #     print(ik, v )
        for ik in list(chunk_dict.keys()):

            if len(ik) == 10:

                new_dict[new_key + ik[8:]] = chunk_dict.pop(ik)

            elif 14 <= len(ik) <= 15:
                #print(ik)
                try:
                    new_dict[new_key][new_key + dim + ik[12:]] = chunk_dict.pop(ik)
                except:
                    print(f' key error ?{ik}')
            elif ik[-1] == 64:
                chunk_dict.pop(ik)
            else:
                main_key = int.to_bytes(ik[-1], 1, 'little')
                if main_key == b'1':
                    nbt_data = unpack_nbt_list(chunk_dict[ik])

                    for be in nbt_data:
                        xc, zc = new_x * 16, new_z * 16

                        x_pos = be.tag['x'].py_int % 16
                        z_pos = be.tag['z'].py_int % 16

                        raw_pos_x = (x_pos + xc)
                        raw_pos_z = (z_pos + zc)

                        be.tag['x'] = IntTag(raw_pos_x)
                        be.tag['z'] = IntTag(raw_pos_z)

                        if be.get('pairlead'):
                            same_z = be.tag['pairz'].py_int // 16
                            same_x = be.tag['pairx'].py_int // 16

                            pairz = be.tag['pairz'].py_int % 16
                            pairx = be.tag['pairx'].py_int % 16

                            # Calculate the actual chunk positions of the pairs
                            pair_chunk_x = same_x - x_old + new_x
                            pair_chunk_z = same_z - z_old + new_z

                            # Adjust the chunk coordinates only if they are different
                            if same_x != x_old:
                                raw_pair_x = (pair_chunk_x * 16) + pairx
                            else:
                                raw_pair_x = raw_pos_x + (pairx - x_pos)

                            if same_z != z_old:
                                raw_pair_z = (pair_chunk_z * 16) + pairz
                            else:
                                raw_pair_z = raw_pos_z + (pairz - z_pos)

                            be.tag['pairx'] = IntTag(raw_pair_x)
                            be.tag['pairz'] = IntTag(raw_pair_z)

                    new_raw = pack_nbt_list(nbt_data)
                    new_dict[new_key + dim + main_key] = new_raw
                else:
                    new_dict[new_key + dim + main_key] = chunk_dict.pop(ik)
        return new_dict

    def update_entities(self, entity_dict, new_x, new_z):  # bedrock

        new_dict = {}
        new_digp = b''
        new_digp_entry = {}
        d = self.current_dim_key
        chunk_id = struct.pack('<ii', new_x, new_z)

        if entity_dict:
            for digp_key, e in entity_dict.items():
                for act, raw in e['actorprefix_dict'].items():
                    actor_nbt = load(raw, compressed=False, little_endian=True
                                     , string_decoder=utf8_escape_decoder)
                    actor_type = actor_nbt.get('identifier', StringTag()).py_str
                    #TODO FIND THE POI
                    # if 'minecraft:villager_v2' in actor_type:
                    #     dwelling_unique_id = actor_nbt.get('DwellingUniqueID', StringTag()).py_data
                    #     print(dwelling_unique_id)
                    actor_pos = actor_nbt.get('Pos')
                    actor_nbt.pop('UniqueID')
                    actor_nbt.pop('internalComponents')

                    xc, zc = new_x * 16, new_z * 16

                    x_pos = (actor_pos[0]) % 16
                    z_pos = (actor_pos[2]) % 16

                    raw_pos_x = (x_pos + xc)
                    raw_pos_z = (z_pos + zc)

                    x, z = raw_pos_x, raw_pos_z
                    y = actor_pos[1]

                    actor_nbt.tag['Pos'] = ListTag([FloatTag(x),
                                                    FloatTag(y),
                                                    FloatTag(z)])

                    raw_nbt = actor_nbt.to_nbt(compressed=False, little_endian=True, string_encoder=utf8_escape_encoder)
                    actorprefix, digp_actor = create_new_actor_prefix(self.world_start_count, self.next_slot)
                    new_digp += digp_actor
                    new_dict[actorprefix] = raw_nbt

                    self.next_slot += 1

                new_digp_entry[b'digp' + chunk_id + d] = {'digp_data': new_digp, 'actorprefix_dict': new_dict}
                return new_digp_entry
        else:
            return {}

    def move_all_selection_boxes(self, offset_x, offset_z):

        current_x, current_z = self.last_offset_move
        offset_xx = offset_x + current_x
        offset_zz = offset_z + current_z

        self.last_offset_move = (offset_xx, offset_zz)
        new_selection = {}
        for (x, z), selection_box in self.selection.items():
            new_x, new_z = x + offset_x, z + offset_z
            new_selection[(new_x, new_z)] = SelectionBox(
                (new_x * 16, self.y_range[0], new_z * 16), (new_x * 16 + 16, self.y_range[1], new_z * 16 + 16)
            )
        self.selection = new_selection

    def move_all_selection_boxes_to(self, target_x, target_z):
        self.last_offset_move = (target_x, target_z)
        current_x, current_z = min((x, z) for x, z in self.selection.keys())
        offset_x = target_x - current_x
        offset_z = target_z - current_z

        new_selection = {}
        for (x, z), selection_box in self.selection.items():
            new_x, new_z = x + offset_x, z + offset_z
            new_selection[(new_x, new_z)] = SelectionBox(
                (new_x * 16, self.y_range[0], new_z * 16), (new_x * 16 + 16, self.y_range[1], new_z * 16 + 16)
            )
        self.selection = new_selection

    def get_dim_bytes(self):
        chunkkey = b''
        if 'minecraft:the_end' in self.canvas.dimension:
            chunkkey = struct.pack('<i', 2)
        elif 'minecraft:the_nether' in self.canvas.dimension:
            chunkkey = struct.pack('<i', 1)
        elif 'minecraft:overworld' in self.canvas.dimension:
            chunkkey = b''
        return chunkkey

    def get_dim_chunkkey(self, xx, zz):
        chunkkey = b''
        if 'minecraft:the_end' in self.canvas.dimension:
            chunkkey = struct.pack('<iii', xx, zz, 2)
        elif 'minecraft:the_nether' in self.canvas.dimension:
            chunkkey = struct.pack('<iii', xx, zz, 1)
        elif 'minecraft:overworld' in self.canvas.dimension:
            chunkkey = struct.pack('<ii', xx, zz)
        return chunkkey

    def get_dim_vpath_java_dir(self, regonx, regonz, folder='region'):  # entities
        file = "r." + str(regonx) + "." + str(regonz) + ".mca"
        path = self.world.level_wrapper.path
        full_path = ''
        dim = ''
        if 'minecraft:the_end' in self.canvas.dimension:
            dim = 'DIM1'
        elif 'minecraft:the_nether' in self.canvas.dimension:
            dim = 'DIM-1'
        elif 'minecraft:overworld' in self.canvas.dimension:
            dim = ''

        full_path = os.path.join(path, dim, folder, file)
        return full_path

    def get_current_entity_count(self):
        current_entites_values = []
        world_count = self.world.level_wrapper.root_tag.get('worldStartCount')
        start_count = 4294967294 - world_count
        start_key = struct.pack('>L', start_count)

        for k, v in self.world.level_wrapper.level_db.iterate(start=b'actorprefix' + start_key,
                                                              end=b'actorprefix' + start_key + b'\xff\xff\xff\xff'):
            current_entites_values.append(int.from_bytes(k[15:], 'big'))

        if len(current_entites_values) > 0:
            return max(current_entites_values) + 1  # the next available slot for the last save
        else:
            return 0

    @property
    def level_db(self):
        level_wrapper = self.world.level_wrapper
        if hasattr(level_wrapper, "level_db"):
            return level_wrapper.level_db
        else:
            return level_wrapper._level_manager._db

    def delete_outer(self, _):
        chunk_values = list(self.outer_chunks(int(self.parent._select_outer_in.GetValue())).keys())
        self.canvas.renderer.render_world.chunk_manager.unload()
        self.canvas.renderer.render_world.unload()
        for x, z in chunk_values:
            self.canvas.world.level_wrapper.delete_chunk(x, z, self.canvas.dimension)

        chunk_values_outer_chunks = list(self.outer_chunks(int(self.parent._select_outer_in.GetValue()) + 3).keys())
        loaction_dict = collections.defaultdict(list)
        if self.world.level_wrapper.platform == 'bedrock':
            for xx, zz in chunk_values_outer_chunks:
                chunkkey = self.get_dim_chunkkey(xx, zz)
                self.level_db.delete(chunkkey + b'\x40')
        else:
            for xx, zz in chunk_values_outer_chunks:
                rx, rz = chunk_coords_to_region_coords(xx, zz)
                loaction_dict[(rx, rz)].append((xx, zz))

            for rx, rz in loaction_dict.keys():
                file_exists = exists(self.get_dim_vpath_java_dir(rx, rz))
                if file_exists:
                    for di in loaction_dict[(rx, rz)]:
                        cx, cz = di
                        self.raw_data = AnvilRegion(self.get_dim_vpath_java_dir(rx, rz))
                        if self.raw_data.has_chunk(cx % 32, cz % 32):
                            nbtdata = self.raw_data.get_chunk_data(cx % 32, cz % 32)

                            if nbtdata['sections']:
                                nbtdata['Heightmaps'] = CompoundTag({})
                                nbtdata['blending_data'] = CompoundTag(
                                    {"old_noise": ByteTag(1)})
                                nbtdata['DataVersion'] = IntTag(2860)
                                self.raw_data.put_chunk_data(cx % 32, cz % 32, nbtdata)
                            self.raw_data.save()
                        self.raw_data.unload()

        self.world.save()
        self.world.purge()
        self.canvas.renderer.render_world.enable()
        self.canvas.renderer.render_world.chunk_manager.rebuild()

    def select_outer(self, _):
        selection_values = list(self.outer_chunks(int(self.parent._select_outer_in.GetValue())).values())
        merged = SelectionGroup(selection_values).merge_boxes()
        self.canvas.selection.set_selection_group(merged)

    def go_to_loaded(self, _):

        selection_values = list(self.selection.values())
        location = selection_values[0].point_2
        self.canvas.camera.set_location(location)

    def move_north(self, _):
        self.move_all_selection_boxes(0, -1)
        new_selection = [v for v in self.selection.values()]
        merged = SelectionGroup(new_selection).merge_boxes()
        self.canvas.selection.set_selection_group(merged)

    def move_south(self, _):
        self.move_all_selection_boxes(0, 1)
        new_selection = [v for v in self.selection.values()]
        merged = SelectionGroup(new_selection).merge_boxes()
        self.canvas.selection.set_selection_group(merged)

    def move_east(self, _):
        self.move_all_selection_boxes(1, 0)
        new_selection = [v for v in self.selection.values()]
        merged = SelectionGroup(new_selection).merge_boxes()
        self.canvas.selection.set_selection_group(merged)

    def move_west(self, _):
        self.move_all_selection_boxes(-1, 0)
        new_selection = [v for v in self.selection.values()]
        merged = SelectionGroup(new_selection).merge_boxes()
        self.canvas.selection.set_selection_group(merged)

    def move_int_view(self, _):
        cx, cy, cz = self.canvas.camera.location
        self.move_all_selection_boxes_to(int(cx) // 16, int(cz) // 16)
        new_selection = [v for v in self.selection.values()]
        merged = SelectionGroup(new_selection).merge_boxes()
        self.canvas.selection.set_selection_group(merged)

    def renderer(self, _):

        for c in self.chunks.keys():
            if self.world.level_wrapper.platform == 'bedrock':
                x, z = struct.unpack('<ii', c)
            else:
                x, z = c
            if self.world.has_chunk(x, z, self.canvas.dimension):
                self.world.get_chunk(x, z, self.canvas.dimension).changed = True

            else:
                self.world.create_chunk(x, z, self.canvas.dimension)
                self.world.get_chunk(x, z, self.canvas.dimension).changed = True
        self.world.save()

        _min, _max = -4, 20
        if self.world.level_wrapper.platform == 'bedrock':
            if self.parent._range_top.GetValue() != "":
                _max = int(self.parent._range_top.GetValue())
            if self.parent._range_bottom.GetValue() != "":
                _min = int(self.parent._range_bottom.GetValue())
            for i, (c, v) in enumerate(self.chunks.items()):
                if self.parent.include_blocks.GetValue():
                    for k, d in v["chunk_data"].items():
                        if k[-1] == 58 or k[-1] == 51: #ticking
                            nbt = unpack_nbt_list(d)
                            for x in range(len(nbt)):
                                tick = self.world.level_wrapper.root_tag['currentTick'].py_int
                                nbt[x]['currentTick'] = IntTag(tick)
                                for i in range(len(nbt[x]['tickList'])):
                                    tick += 1
                                    nbt[x]['tickList'][i]['time'] = LongTag(tick)
                                    new_x, new_z = struct.unpack('ii', k[0:8])
                                    x_pos = (nbt[x]['tickList'][i]['x']) % 16
                                    z_pos = (nbt[x]['tickList'][i]['z']) % 16
                                    xc, zc = new_x * 16, new_z * 16
                                    raw_pos_x = (x_pos + xc)
                                    raw_pos_z = (z_pos + zc)
                                    nbt[x]['tickList'][i]['x'] = IntTag(raw_pos_x)
                                    nbt[x]['tickList'][i]['z'] = IntTag(raw_pos_z)
                            d = pack_nbt_list(nbt)
                            self.level_db.put(k, d)
                        if not self.parent.include_biome_key.GetValue():
                            if k[-1] == 43:
                                continue
                        if len(k) == 14 or len(k) == 10:
                            if k[-2] == 47:
                                packed = struct.pack('B', k[-1])
                                signed_value = struct.unpack('b', packed)[0]
                                if _min <= signed_value <= _max:
                                    self.level_db.put(k, d)
                        else:
                            self.level_db.put(k, d)
                if self.parent.include_entities.GetValue():
                    for k, d in v["entitie"].items():
                        self.level_db.put(k, d['digp_data'])
                        for a, e in d['actorprefix_dict'].items():
                            self.level_db.put(a, e)
        else:  # java
            region_file_ready = collections.defaultdict(list)
            self.world.level_wrapper.root_tag['Data']['DataVersion'] = IntTag(2860)
            self.world.level_wrapper.root_tag['Data']['Version'] = CompoundTag(
                {"Snapshot": ByteTag(0), "Id": IntTag(2860),
                 "Name": StringTag("1.18.0")})
            if self.parent._range_top.GetValue() != "":
                _max = int(self.parent._range_top.GetValue())
            if self.parent._range_bottom.GetValue() != "":
                _min = int(self.parent._range_bottom.GetValue())
            chunks = self.get_chunk_data()
            for k, v in chunks.items():
                x, z = k
                rx, rz = chunk_coords_to_region_coords(x, z)
                region_file_ready[(rx, rz)].append({(x, z): {'data': v}})
            for r, v in region_file_ready.items():
                rx, rz = r

                if self.parent.include_entities.GetValue():
                    self.raw_data_entities = AnvilRegion(self.get_dim_vpath_java_dir(rx, rz, folder='entities'))
                if self.parent.include_blocks.GetValue():
                    self.raw_data_chunks = AnvilRegion(self.get_dim_vpath_java_dir(rx, rz))

                for items in v:
                    for c, d in items.items():
                        cx, cz = c
                        if self.parent.include_blocks.GetValue():
                            data = d['data'].get('chunk_data')
                            raw_chunk = self.raw_data_chunks.get_chunk_data(cx % 32, cz % 32)
                            old_sections = {}
                            old_be = {}
                            new_selection = {}
                            new_be = {}
                            if not self.parent.include_biome_key.GetValue():
                                for b in data.get('sections'):
                                    if b.get('biomes'):
                                        b.pop('biomes')
                            for s in raw_chunk.get('sections'):
                                y_level = s['Y'].py_int
                                old_sections[y_level] = s
                            for be in raw_chunk.get('block_entities'):
                                y_level = be.get('y').py_int % 16
                                old_be[y_level] = be
                            for s in data.get('sections'):
                                y_level = s['Y'].py_int
                                new_selection[y_level] = s
                            for be in data.get('block_entities'):
                                y_level = be.get('y').py_int % 16
                                new_be[y_level] = be

                            for us in list(new_selection.keys()):
                                if not (_min <= us <= _max):
                                    new_selection.pop(us, None)
                            for them in list(new_be.keys()):
                                if not (_min <= them <= _max):
                                    new_be.pop(them, None)

                            # new_selection_ready = {**old_sections, **new_selection}
                            # new_be_ready = {**new_be, **old_be}

                            new_selection_ready = old_sections.copy()
                            for k, v in new_selection.items():
                                new_selection_ready[k] = v

                            new_be_ready = old_be.copy()
                            for k, v in new_be.items():
                                new_be_ready[k] = v

                            data['block_entities'] = ListTag([c for c in new_be_ready.values()])
                            # TODO add check box
                            data['sections'] = ListTag([c for c in new_selection_ready.values()])

                            data['DataVersion'] = IntTag(2860)
                            data['Heightmaps'] = CompoundTag({})
                            data['blending_data'] = CompoundTag(
                                {"old_noise": ByteTag(1)})

                            data.pop('isLightOn', None)
                            self.raw_data_chunks.put_chunk_data(cx % 32, cz % 32, data)

                        if self.parent.include_entities.GetValue():
                            if d['data'].get('entitie_data'):
                                data_e = d['data'].get('entitie_data')
                                for i, e in enumerate(data_e['Entities']):
                                    data_e['Entities'][i]['UUID'] = IntArrayTag(
                                        [x for x in struct.unpack('>iiii', uuid.uuid4().bytes)])

                                self.raw_data_entities.put_chunk_data(cx % 32, cz % 32, data_e)

                if self.parent.include_entities.GetValue():
                    self.raw_data_entities.save()
                    self.raw_data_entities.unload()
                if self.parent.include_blocks.GetValue():
                    self.raw_data_chunks.save()
                    self.raw_data_chunks.unload()

    def save_loaded_chunks(self, _):

        self.apply_selection()
        self.canvas.renderer.render_world.chunk_manager.unload()
        self.canvas.run_operation(lambda: self.renderer(_), "chunks", "Starting...")
        self.world.purge()
        self.canvas.renderer.render_world.chunk_manager.rebuild()

    def bedrock_save(self):
        self.the_chunks()
        original_chunk_keys = {}
        original_digp_actor_keys = {}
        for xx, zz in self.all_chunks:

            chunkkey = self.get_dim_chunkkey(xx, zz)  # returns the bytes key for the current dimension
            original_chunk_keys[(xx, zz)] = chunkkey
            chunk_data = {}
            entitiy_data = {}
            new_digp_entry = {}

            for k, v in self.world.level_wrapper.level_db.iterate(start=chunkkey,
                                                                  end=chunkkey + b'\xff\xff\xff'):

                if len(chunkkey) < 9:

                    chunk_data[k] = v
                elif chunkkey == k[:12]:
                    chunk_data[k[:8]] = v

            for k, v in self.world.level_wrapper.level_db.iterate(start=b'digp' + chunkkey[:-1],
                                                                  end=b'digp' + chunkkey + b'\xff'):
                if k == b'digp' + chunkkey and len(v) > 0:
                    digp_actor_list = []
                    actor_count = len(v) // 8
                    pnt = 0
                    for c in range(actor_count):
                        digp_actor_list.append(b'actorprefix' + v[pnt:pnt + 8])
                        raw_actor_nbt = self.level_db.get(b'actorprefix' + v[pnt:pnt + 8])
                        entitiy_data[b'actorprefix' + v[pnt:pnt + 8]] = raw_actor_nbt
                        pnt += 8
                    original_digp_actor_keys[b'digp' + chunkkey] = {'listed': digp_actor_list, 'original_bytes': v}
                    new_digp_entry[k] = {'digp_data': v, 'actorprefix_dict': entitiy_data}
            self.chunk_and_entities[chunkkey] = {'chunk_data': chunk_data, 'entitie': new_digp_entry,
                                                 'original_chunk_key': chunkkey,
                                                 'original_digp_actor_keys': original_digp_actor_keys}

    def java_save(self):
        self.the_chunks()
        original_chunk_keys = {}
        loaction_dict = collections.defaultdict(list)
        for xx, zz in self.all_chunks:
            rx, rz = chunk_coords_to_region_coords(xx, zz)
            loaction_dict[(rx, rz)].append((xx, zz))

        for rx, rz in loaction_dict.keys():
            file_exists_for_region = exists(self.get_dim_vpath_java_dir(rx, rz))
            file_exists_for_entities = exists(self.get_dim_vpath_java_dir(rx, rz, folder='entities'))
            if file_exists_for_region:
                self.raw_data = AnvilRegion(self.get_dim_vpath_java_dir(rx, rz))
                for di in loaction_dict[(rx, rz)]:
                    cx, cz = di

                    if self.raw_data.has_chunk(cx % 32, cz % 32):
                        nbtdata = self.raw_data.get_chunk_data(cx % 32, cz % 32)
                        self.chunk_and_entities[(cx, cz)] = {}
                        self.chunk_and_entities[(cx, cz)]['chunk_data'] = nbtdata
                self.raw_data.unload()

            if file_exists_for_entities:

                self.raw_data = AnvilRegion(self.get_dim_vpath_java_dir(rx, rz, folder='entities'))
                for di in loaction_dict[(rx, rz)]:
                    cx, cz = di
                    if self.raw_data.has_chunk(cx % 32, cz % 32):
                        nbtdata = self.raw_data.get_chunk_data(cx % 32, cz % 32)
                        self.chunk_and_entities[(cx, cz)]['entitie_data'] = nbtdata

                self.raw_data.unload()

class ChunkSaveAndLoad(wx.Frame):
    def __init__(self, parent, canvas, world):
        super().__init__(parent, id=wx.ID_ANY, pos=wx.DefaultPosition, size=(560, 400), title="Position selections",
                         style=(
                                 wx.MINIMIZE_BOX | wx.MAXIMIZE_BOX | wx.RESIZE_BORDER | wx.SYSTEM_MENU | wx.CAPTION | wx.CLOSE_BOX |
                                 wx.CLIP_CHILDREN | wx.FRAME_FLOAT_ON_PARENT | wx.ALIGN_CENTER | wx.STAY_ON_TOP))
        self.parent = parent

        self.canvas = canvas
        self.world = world
        self.platform = self.world.level_wrapper.platform
        self.chunks_mg = ChunkManager(parent=self, world=self.world, canvas=self.canvas)

        self.has_been_loaded = False
        self.raw_data_entities = None
        self.raw_data_chunks = None

        self.Freeze()
        self.font = wx.Font(13, wx.FONTFAMILY_ROMAN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        self.SetFont(self.font)
        self.SetForegroundColour((0, 255, 0))
        self.SetBackgroundColour((0, 0, 0))
        self.info_label = wx.StaticText(self, label="\nThis Directly edited the world ! "
                                                    "\n                     Make sure you have a backup! ")

        self._all_chunks = wx.CheckBox(self, label="Save: All Chunks \n (can be slow)")
        self._all_chunks.SetValue(False)
        self._sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self._sizer)
        self.main_sizer = wx.BoxSizer(wx.VERTICAL)
        self.loaded_sizer = wx.BoxSizer(wx.VERTICAL)
        self._sizer.Add(self.main_sizer)
        self._sizer.Add(self.loaded_sizer)

        self._save_button = wx.Button(self, label="Save Chunks")
        self._save_button.Bind(wx.EVT_BUTTON, self.save_chunks)
        self._load_button = wx.Button(self, label="Load Chunks")
        self._load_button.Bind(wx.EVT_BUTTON, self.load_chunks)

        self._move_chunks_into_view = wx.Button(self, label="Move Loaded Chunks \nInto Camera View", size=(180, 20))
        self._go_to_loaded = wx.Button(self, label="Go to loaded chunks")
        self._move_grid = wx.GridSizer(3, 3, 2, 1)
        self._move_n = wx.Button(self, label="North")
        self.space_1 = wx.StaticText(self, label="")
        self.space_2 = wx.StaticText(self, label="")
        self.space_3 = wx.StaticText(self, label="")
        self.space_4 = wx.StaticText(self, label="")

        self._move_s = wx.Button(self, label="South")
        self._move_e = wx.Button(self, label="East")
        self._move_w = wx.Button(self, label="West")

        self._move_n.Bind(wx.EVT_BUTTON, self.chunks_mg.move_north)
        self._move_s.Bind(wx.EVT_BUTTON, self.chunks_mg.move_south)
        self._move_e.Bind(wx.EVT_BUTTON, self.chunks_mg.move_east)
        self._move_w.Bind(wx.EVT_BUTTON, self.chunks_mg.move_west)

        self._move_grid.Add(self.space_1)
        self._move_grid.Add(self._move_n)
        self._move_grid.Add(self.space_2)
        self._move_grid.Add(self._move_w)
        self._move_grid.Add(self.space_4)
        self._move_grid.Add(self._move_e)
        self._move_grid.Add(self.space_3)
        self._move_grid.Add(self._move_s)

        self.grid_for_outer = wx.GridSizer(2, 2, 5, 3)
        self._select_outer_l = wx.StaticText(self, label="  Outer select / delete range:\n"
                                                         "(This is required for blending)")
        self._select_outer_in = wx.TextCtrl(self, size=(40, 35))
        self._select_outer_in.SetValue('2')
        self._select_outer = wx.Button(self, label="Select Outer\n Chunks", size=(100, 35))
        self._select_outer.Bind(wx.EVT_BUTTON, self.chunks_mg.select_outer)
        self._delete_outer = wx.Button(self, label="Delete Outer\n Chunks", size=(100, 35))
        self._delete_outer.Bind(wx.EVT_BUTTON, self.chunks_mg.delete_outer)

        self.grid_for_outer.Add(self._select_outer_l)
        self.grid_for_outer.Add(self._select_outer_in)
        self.grid_for_outer.Add(self._delete_outer)
        self.grid_for_outer.Add(self._select_outer)

        self.l_range = wx.StaticText(self, label="Set Sub Chunk layer Range(min,max):")
        self.l_min = wx.StaticText(self, label="  min:")
        self.l_max = wx.StaticText(self, label="  max:")

        self.l_range_Info = wx.StaticText(self, label="overworld=24, end=16, nether=8, Sub chunk is 16x16x16 \n"
                                                      "overworld range is -4 to 19, nether is 0 to 7 end is 0 to 15 ")

        self._range_bottom = wx.TextCtrl(self, size=(40, 20))
        self._range_top = wx.TextCtrl(self, size=(40, 20))
        self._range_grid = wx.GridSizer(1, 4, 2, 0)
        self._range_grid.Add(self.l_min)
        self._range_grid.Add(self._range_bottom)
        self._range_grid.Add(self.l_max)
        self._range_grid.Add(self._range_top)
        self._box_l_and_toggle = wx.BoxSizer(wx.HORIZONTAL)

        self._toggel_top_down = wx.Button(self, label="Toggle View")
        self._toggel_top_down.Bind(wx.EVT_BUTTON, self.toggel_top_down)
        self.info_label2 = wx.StaticText(self, label="\nPosition loaded chunks\n"
                                                     "Only Use these Buttons to position chunk")
        self._box_l_and_toggle.Add(self.info_label2)
        self._box_l_and_toggle.Add(self._toggel_top_down)

        self._move_chunks_into_view.Bind(wx.EVT_BUTTON, self.chunks_mg.move_int_view)
        self._go_to_loaded.Bind(wx.EVT_BUTTON, self.chunks_mg.go_to_loaded)
        self._save_loaded_chunks = wx.Button(self, label="Save Loaded chunks:")
        self._save_loaded_chunks.Bind(wx.EVT_BUTTON, self.chunks_mg.save_loaded_chunks)
        self._save_load_grid = wx.GridSizer(2, 2, 0, 0)

        self._save_load_grid.Add(self._save_button)
        self._save_load_grid.Add(self._all_chunks)
        self._save_load_grid.Add(self._load_button)

        self.main_sizer.Add(self.info_label, 1, wx.LEFT, 0)
        self.main_sizer.Add(self._save_load_grid, 1, wx.LEFT, 0)

        # self.main_sizer.Add(self._load_button, 0, wx.LEFT, 11)

        self.loaded_sizer.Add(self._move_chunks_into_view, 1, wx.TOP, 0)
        self.loaded_sizer.Add(self._box_l_and_toggle, 0, wx.LEFT, 0)
        self.loaded_sizer.Add(self._move_grid, 0, wx.BOTTOM, 0)

        self._group = wx.GridSizer(1, 2, 2, 4)
        self._group.Add(self._save_loaded_chunks)
        self._group.Add(self._go_to_loaded)
        self._include = wx.GridSizer(1, 3, 1, 2)
        self.include_blocks = wx.CheckBox(self, label="Include Blocks")
        self.include_blocks.SetValue(True)
        self.include_entities = wx.CheckBox(self, label="Include Entities")
        self.include_entities.SetValue(True)
        self.include_biome_key = wx.CheckBox(self, label="Include Biome")
        self.include_biome_key.SetValue(True)
        self._include.Add(self.include_blocks) #include_biome_key
        self._include.Add(self.include_entities)
        self._include.Add(self.include_biome_key)
        self.loaded_sizer.Add(self._include, 0, wx.LEFT, 0)
        self.loaded_sizer.Add(self._group, 1, wx.LEFT, 0)

        self.loaded_sizer.Add(self.l_range, 0, wx.LEFT, 0)
        self.loaded_sizer.Add(self._range_grid, 0, wx.LEFT, 0)
        self.loaded_sizer.Add(self.l_range_Info, 0, wx.LEFT, 0)
        self.loaded_sizer.Add(self.grid_for_outer, 0, wx.LEFT, 0)
        self.main_sizer.Layout()
        self._sizer.Hide(self.loaded_sizer)
        self.loaded_sizer.Layout()
        self.Fit()
        self.Layout()
        self.Thaw()

    def toggel_top_down(self, _):
        mode = self.canvas.camera.projection_mode.value
        if mode == 0:
            self.canvas.camera.projection_mode = Projection.PERSPECTIVE
        else:
            self.canvas.camera.projection_mode = Projection.TOP_DOWN

    def load_chunks(self, _):
        # self.chunks_mg = ChunkManager(parent=self, world=self.world, canvas=self.canvas)
        platf = self.world.level_wrapper.platform
        fdlg = wx.FileDialog(self.parent, "Load chunks", "", "",
                             f"Chunk (*.chunks_{platf})|*.chunks_{platf}", wx.FD_OPEN)
        if fdlg.ShowModal() == wx.ID_OK:
            pathto = fdlg.GetPath()
            with open(pathto, 'rb') as f:
                self.chunks_mg.chunks = pickle.loads(zlib.decompress(f.read()))
            self.chunks_mg.load_chunks()
            selection_values = list(self.chunks_mg.selection.values())
            merged = SelectionGroup(selection_values).merge_boxes()
            self.canvas.selection.set_selection_group(merged)

            if not self.has_been_loaded:
                self._sizer.Show(self.loaded_sizer)
                self.loaded_sizer.Fit(self)
                self._sizer.Fit(self)
                self.loaded_sizer.Layout()
                self._sizer.Layout()
                self.Fit()
                self.Layout()
                self.has_been_loaded = True

    def save_chunks(self, _):
        if self.platform == 'java':
            self.chunks_mg.java_save()
        else:
            self.chunks_mg.bedrock_save()
        platf = self.platform
        fdlg = wx.FileDialog(self, "Save Chunks", "", "",
                             f"chunk (*.chunks_{platf})|*.chunks_{platf}", wx.FD_SAVE)
        if fdlg.ShowModal() == wx.ID_OK:
            pathto = fdlg.GetPath()

            if ".chunks" not in pathto:
                pathto = pathto + ".chunks"
            with open(pathto, "wb") as file:
                file.write(zlib.compress(pickle.dumps(self.chunks_mg.chunk_and_entities)))

class MyTreeCtrl(wx.TreeCtrl):
    def __init__(self, parent, id, pos, size, style, nbt_data):
        wx.TreeCtrl.__init__(self, parent, id, pos, size, style)
        self.nbt_data = nbt_data

    def Traverse(self, func, startNode):
        def TraverseAux(node, depth, func):
            nc = self.GetChildrenCount(node, 0)
            child, cookie = self.GetFirstChild(node)
            # In wxPython 2.5.4, GetFirstChild only takes 1 argument
            for i in range(nc):
                func(child, depth)
                TraverseAux(child, depth + 1, func)
                child, cookie = self.GetNextChild(node, cookie)

        func(startNode, 0)
        TraverseAux(startNode, 1, func)

    def ItemIsChildOf(self, item1, item2):
        self.result = False

        def test_func(node, depth):
            if node == item1:
                self.result = True

        self.Traverse(test_func, item2)
        return self.result

    def SaveItemsToList(self, startnode):
        global lista
        lista = []

        def save_func(node, depth):
            tmplist = lista
            for x in range(depth):
                if type(tmplist[-1]) is not dict:
                    tmplist.append({})
                tmplist = tmplist[-1].setdefault('children', [])

            item = {}
            item['label'] = self.GetItemText(node)
            item['data'] = self.GetItemData(node)
            item['icon-normal'] = self.GetItemImage(node, wx.TreeItemIcon_Normal)
            item['icon-selected'] = self.GetItemImage(node, wx.TreeItemIcon_Selected)
            item['icon-expanded'] = self.GetItemImage(node, wx.TreeItemIcon_Expanded)
            item['icon-selectedexpanded'] = self.GetItemImage(node, wx.TreeItemIcon_SelectedExpanded)

            tmplist.append(item)

        self.Traverse(save_func, startnode)
        return lista

    def OnCompareItems(self, item1, item2):
        t1 = self.GetItemText(item1)
        t2 = self.GetItemText(item2)

        if t1 < t2: return -1
        if t1 == t2: return 0
        return 1

    def InsertItemsFromList(self, itemlist, parent, insertafter=None, appendafter=False):
        newitems = []
        for item in itemlist:
            if insertafter:
                node = self.InsertItem(parent, insertafter, item['label'])
            elif appendafter:
                node = self.AppendItem(parent, item['label'])
            else:
                node = self.PrependItem(parent, item['label'])
            self.SetItemData(node, item['data'])
            self.SetItemImage(node, item['icon-normal'], wx.TreeItemIcon_Normal)
            self.SetItemImage(node, item['icon-selected'], wx.TreeItemIcon_Selected)
            self.SetItemImage(node, item['icon-expanded'], wx.TreeItemIcon_Expanded)
            self.SetItemImage(node, item['icon-selectedexpanded'], wx.TreeItemIcon_SelectedExpanded)

            newitems.append(node)
            if 'children' in item:
                self.InsertItemsFromList(item['children'], node, appendafter=True)
        return newitems

    def loop_all_tree_keys(self):
        root = self.GetRootItem()
        nc = self.GetChildrenCount(root, 0)
        child, cookie = self.GetFirstChild(root)
        orderit = []
        orderit.append(self.GetItemData(child)[0])
        # In wxPython 2.5.4, GetFirstChild only takes 1 argument
        for i in range(nc):
            child, cookie = self.GetNextChild(child, cookie)
            if child.IsOk():
                orderit.append(self.GetItemData(child)[0])
            else:
                break
        return orderit

class SmallEditDialog(wx.Frame):
    GRID_ROWS = 2
    GRID_COLUMNS = 2

    def __init__(
            self, parent, oper_name, tag_type_name, item, tree, bitmap_icon, image_map
    ):
        super(SmallEditDialog, self).__init__(
            parent, title=f"{oper_name} {tag_type_name}", size=(400, 200)
        )
        if bitmap_icon:
            if isinstance(bitmap_icon, wx.Icon):
                self.SetIcon(bitmap_icon)
            else:
                self.SetIcon(wx.Icon(bitmap_icon))
        self.Centre(50)

        if "SNBT" not in tag_type_name:
            self.image_map = image_map
            self.tree = tree

            self.text = self.tree.GetItemText(item)
            self.data = self.tree.GetItemData(item)
            main_panel = simple.SimplePanel(self)
            button_panel = simple.SimplePanel(main_panel, sizer_dir=wx.HORIZONTAL)
            name_panel = simple.SimplePanel(main_panel, sizer_dir=wx.HORIZONTAL)
            value_panel = simple.SimplePanel(main_panel, sizer_dir=wx.HORIZONTAL)
            name_label = wx.StaticText(name_panel, label="Name: ")
            value_label = wx.StaticText(value_panel, label="Value: ")

            self.name_field = wx.TextCtrl(name_panel)
            self.value_field = wx.TextCtrl(value_panel)
            name_panel.add_object(name_label, space=0, options=wx.ALL | wx.CENTER)
            name_panel.add_object(self.name_field, space=1, options=wx.ALL | wx.EXPAND)

            meta = False
            if isinstance(self.data, tuple):
                name, data = self.data
            else:
                name, data = None, self.data
            if isinstance(data, abc.ABCMeta):
                meta = True
            final_name, final_value = None, None
            self.name_field.Disable(), self.value_field.Disable()
            if oper_name == "Add":
                self.name_field.Enable(), self.value_field.Enable()
                f_child = self.tree.GetFirstChild(item)[0]
                if f_child.IsOk():
                    if isinstance(self.tree.GetItemData(f_child), tuple):
                        name, type_t = self.tree.GetItemData(f_child)
                        self.name_field.SetValue("")
                        self.value_field.SetValue("")
                    else:
                        type_t = self.tree.GetItemData(f_child)
                        self.name_field.Disable()
                        self.value_field.SetValue("")
            else:
                if name:
                    self.name_field.SetValue(name)
                    self.name_field.Enable()
                if not meta:
                    self.value_field.SetValue(str(data.value))
                    self.value_field.Enable()
                else:
                    if name:
                        self.name_field.SetValue(name)
                        self.value_field.SetValue(str(data))

            value_panel.add_object(value_label, space=0, options=wx.ALL | wx.CENTER)
            value_panel.add_object(self.value_field, space=1, options=wx.ALL | wx.EXPAND)
            self.save_button = wx.Button(button_panel, label=oper_name)
            self.cancel_button = wx.Button(button_panel, label="Cancel")
            button_panel.add_object(self.save_button, space=0)
            button_panel.add_object(self.cancel_button, space=0)
            main_panel.add_object(name_panel, space=0, options=wx.ALL | wx.EXPAND)
            main_panel.add_object(value_panel, space=0, options=wx.ALL | wx.EXPAND)
            main_panel.add_object(button_panel, space=0)
            self.save_button.Bind(wx.EVT_BUTTON, lambda evt:
            self.add_edit(evt, oper_name, self.data, item, tag_type_name))
            self.save_button.Bind(wx.EVT_KEY_UP, lambda evt:
            self.key_down_enter(evt, oper_name, self.data, item, tag_type_name))
            self.name_field.Bind(wx.EVT_KEY_UP, lambda evt:
            self.key_down_enter(evt, oper_name, self.data, item, tag_type_name))
            self.value_field.Bind(wx.EVT_KEY_UP, lambda evt:
            self.key_down_enter(evt, oper_name, self.data, item, tag_type_name))
            self.cancel_button.Bind(wx.EVT_BUTTON, lambda evt: self.Close())
            self.Layout()
        else:
            self.tree = tree
            self.SetSize(600, 700)
            main_panel = simple.SimplePanel(self)
            button_panel = simple.SimplePanel(main_panel, sizer_dir=wx.HORIZONTAL)
            value_panel = simple.SimplePanel(main_panel, sizer_dir=wx.HORIZONTAL)
            self.value_field = wx.TextCtrl(value_panel, style=wx.TE_MULTILINE, size=(577, 640))
            self.value_field.SetBackgroundColour((0, 0, 0))
            self.value_field.SetForegroundColour((0, 255, 255))
            font = wx.Font(14, wx.FONTFAMILY_ROMAN, wx.FONTSTYLE_MAX, wx.FONTWEIGHT_BOLD)
            self.value_field.SetFont(font)
            value_panel.add_object(self.value_field)
            self.save_button = wx.Button(button_panel, label="Save")
            self.save_button.Bind(wx.EVT_BUTTON, lambda evt:
            self.update_tree(evt))
            button_panel.add_object(self.save_button)
            self.f_path, self.raw_nbt, sel_snbt = NBTEditor.build_to(self.Parent, None, opt="snbt")
            self.value_field.SetValue(sel_snbt)

            main_panel.add_object(value_panel, options=wx.EXPAND)
            main_panel.add_object(button_panel, space=0)

            self.Layout()

    def update_tree(self, evt):

        def get_real_nbt(map_list):
            return reduce(operator.getitem, map_list[:-1], self.raw_nbt)

        updated_nbt = get_real_nbt(self.f_path)
        if len(self.f_path) == 0:
            self.raw_nbt = from_snbt(self.value_field.GetValue())
        else:
            updated_nbt[self.f_path[-1]] = from_snbt(self.value_field.GetValue())
        if isinstance(self.Parent.Parent, EntitiePlugin):
            EntitiePlugin.update_player_data(self, self.raw_nbt)
        elif isinstance(self.Parent.Parent, Inventory):
            Inventory.update_player_data(self, self.raw_nbt)


    def nbt_clean_array_string(self, strr, ntype):
        import re
        dtyped = {"L": "longs", "B": "bytes", "I": "ints"}
        dtype = dtyped[ntype]
        prog = re.compile(r'(\d*[.-]?\d*)', flags=0)
        result, new_string = (prog.findall(strr), '')
        for x in result:
            if x != '':
                new_string += f"{x}{ntype.replace('I', '')}, "
        new_string = f"[{ntype};{new_string[:-2]}]"
        return from_snbt(new_string), dtype

    def key_down_enter(self, evt, oper_name, data, item, tag_type_name):
        keycode = evt.GetKeyCode()
        if keycode == 13 or keycode == 370:
            self.add_edit(evt, oper_name, data, item, tag_type_name)

    def add_edit(self, evt, oper_name, data, item, tag_type_name):
        def set_data_tree(data):
            name, meta = None, False
            key, value = self.name_field.GetValue(), self.value_field.GetValue()
            set_string = f"{key}: {value}"
            if isinstance(data, tuple):
                name, data = data
            if isinstance(data, abc.ABCMeta):
                data, meta = data(), True
            tag_type = [tag_class for tag_class in self.image_map if tag_class.__name__ ==
                        tag_type_name.replace(" ", "")][0]
            set_data = tag_type(data)
            if isinstance(data, (IntArrayTag, LongArrayTag, ByteArrayTag)):
                value, tipe = self.nbt_clean_array_string(value, str(type(data)).split(".")[-1][0])
                t_value, entries = '' if meta else value, len(value)
                set_string = f"{key}:{t_value} [{entries} {tipe}]" if name else f"{t_value}:[{entries} {tipe}]"
                set_data = (key, value) if name else value
            elif isinstance(data, (ListTag, CompoundTag)):
                entries = self.tree.GetChildrenCount(item, 0)
                t_value = '' if meta else value
                set_string = f"{key}:{t_value} entries {entries}" if name else f"{t_value} entries {entries}"

                set_data = (key, tag_type) if name else tag_type
            else:
                t_value = '' if meta else value
                set_string = f"{key}:{t_value}" if name else f"{t_value}"
                set_data = (key, tag_type(value)) if name else tag_type(value)
            self.tree.SetItemText(item, set_string)

            self.tree.SetItemData(item, set_data)
            entries = self.tree.GetChildrenCount(item, 0)

        def add_data_tree(item, data):
            tag_type_data = [tag_class for tag_class in self.image_map if tag_class.__name__ ==
                             tag_type_name.replace(" ", "")][0]
            self.other = self.image_map[TAG_String]
            name, meta = None, False
            name, value = self.name_field.GetValue(), self.value_field.GetValue()
            if name == '':
                name = None

            tipe = data[1] if isinstance(data, tuple) else data

            entries = 0
            set_string = f"{name}: {value}"

            if isinstance(tag_type_data(), (IntArrayTag, LongArrayTag, ByteArrayTag)):
                value, tipe = self.nbt_clean_array_string(value, str(type(tag_type_data())).split(".")[-1][0])
                t_value, entries = '' if meta else value, len(value)
                set_string = f"{name}:{t_value} [{entries} {tipe}]" if name else f"{t_value}:[{entries} {tipe}]"
                set_data = (name, value) if name else value
            elif isinstance(tag_type_data(), (ListTag, CompoundTag)):
                if isinstance(tipe, ListTag):
                    set_string = f"{name} entries {entries}" if name else f"entries {entries}"
                    set_data = (name, tag_type_data(value)) if name else tag_type_data(value)
                else:
                    set_string = f"{name} entries {entries}" if name else f"entries {entries}"
                    set_data = (name, tag_type_data(value)) if name else tag_type_data(value)
            else:
                if isinstance(tipe, ListTag):  # ????????????????????????????????????
                    set_string = f"{name}:{value}" if name else f"{value}"
                    set_data = (name, tag_type_data(value)) if name else tag_type_data(value)
                else:
                    set_string = f"{name}:{value}" if name else f"{value}"
                    set_data = (name, tag_type_data(value)) if name else tag_type_data(value)

            new_child = self.tree.AppendItem(item, set_string)
            self.tree.SetItemData(new_child, set_data)
            self.tree.SetItemImage(
                new_child,
                self.image_map.get(tag_type_data().__class__, self.other),
                wx.TreeItemIcon_Normal,
            )
            entries = self.tree.GetChildrenCount(item, 0)
            testdata = self.tree.GetItemText(item)
            self.tree.SetItemText(item, testdata.replace(f"{entries - 1} entries", f"{entries} entries"))

        if oper_name == "Edit":
            set_data_tree(data)
        elif oper_name == "Add":
            add_data_tree(item, data)
        self.Close()

    def value_changed(self, evt):
        tag_value = evt.GetString()
        self.value_field.ChangeValue(str(self.data_type_func(tag_value)))

    def change_tag_type_func(self, tag_type, name_value=[False, False]):
        # self.data_type_func = lambda x: x
        if name_value[0]:
            self.name_field.Disable()
        if name_value[1]:
            self.value_field.Disable()
        if tag_type in ("IntTag", "LongTag", "ShortTag", "ByteTag"):
            self.data_type_func = lambda x: int(float(x))
            self.value_field.Enable()

        elif tag_type in ("FloatTag", "DoubleTag"):
            self.data_type_func = lambda x: str(float(x))
            self.value_field.Enable()

        if tag_type in ("ByteArrayTag", "IntArrayTag", "LongArrayTag"):
            self.value_field.ChangeValue(
                str("[0 0 0]")
            )
            self.value_field.Enable()
        if tag_type in ("NamedTag", "CompoundTag"):
            self.value_field.ChangeValue(
                str("")
            )

    def get_selected_tag_type(self):
        for rd_btn in self.radio_buttons:
            if rd_btn.GetValue():
                return rd_btn.nbt_tag_class
        return None

    def save(self, evt):
        self.save_callback(
            self.name_field.GetValue(),
            self.data_type_func(self.value_field.GetValue()),
            self.get_selected_tag_type(),
            self.old_name,
        )
        self.Close()

class NBTEditor(wx.Panel):
    def __init__(self, parent, nbt_data=CompoundTag(), root_tag_name="", callback=None, ):
        # super(NBTEditor, self).__init__(parent)
        # Use the WANTS_CHARS style so the panel doesn't eat the Return key.
        wx.Panel.__init__(self, parent)
        self.sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.SetSizer(self.sizer)
        #  self.SetSize(600, 650)
        self.nbt_new = CompoundTag()
        self.nbt_data = nbt_data
        self.copy_data = None
        self.image_list = wx.ImageList(32, 32)
        self.image_map = {
            TAG_Byte: self.image_list.Add(self.resize_resorce(nbt_resources.nbt_tag_byte.bitmap())),
            TAG_Short: self.image_list.Add(self.resize_resorce(nbt_resources.nbt_tag_short.bitmap())),
            TAG_Int: self.image_list.Add(self.resize_resorce(nbt_resources.nbt_tag_int.bitmap())),
            TAG_Long: self.image_list.Add(self.resize_resorce(nbt_resources.nbt_tag_long.bitmap())),
            TAG_Float: self.image_list.Add(self.resize_resorce(nbt_resources.nbt_tag_float.bitmap())),
            TAG_Double: self.image_list.Add(self.resize_resorce(nbt_resources.nbt_tag_double.bitmap())),
            TAG_String: self.image_list.Add(self.resize_resorce(nbt_resources.nbt_tag_string.bitmap())),
            TAG_Compound: self.image_list.Add(
                self.resize_resorce(nbt_resources.nbt_tag_compound.bitmap())
            ),
            NamedTag: self.image_list.ImageCount - 1,
            TAG_List: self.image_list.Add(self.resize_resorce(nbt_resources.nbt_tag_list.bitmap())),
            TAG_Byte_Array: self.image_list.Add(
                self.resize_resorce(nbt_resources.nbt_tag_array.bitmap())
            ),
            TAG_Int_Array: self.image_list.ImageCount - 1,
            TAG_Long_Array: self.image_list.ImageCount - 1,
        }
        self.other = self.image_map[TAG_String]
        self.tree = self.build_tree(nbt_data)
        self.callback = callback

    def resize_resorce(self, img_path):
        image = img_path.ConvertToImage()
        image = image.Scale(32, 32, wx.IMAGE_QUALITY_HIGH)
        result = wx.Bitmap(image)
        return result

    def build_to(self, evt, opt='raw'):
        tree = self.tree

        # def get_full_path(child):
        #     index = 0
        #     p_type = None
        #     the_sib_items = []
        #     nbt_path_keys = []
        #     if isinstance(tree.GetItemData(child), tuple):
        #         name, data = tree.GetItemData(child)
        #         nbt_path_keys.append(name)
        #     sibl = tree.GetItemParent(child)
        #     while sibl.IsOk():
        #         # print("____",tree.GetItemData(sibl))
        #         the_sib_items.append(sibl)
        #         if isinstance(tree.GetItemData(sibl), tuple):
        #             p_type = tree.GetItemData(sibl)[1]
        #         else:
        #             p_type = tree.GetItemData(sibl)
        #         print(root_path(tree.GetFocusedItem()))
        #         if p_type == ListTag:
        #             item_num = tree.GetChildrenCount(sibl, recursively=True)
        #             f_child, f_c = tree.GetFirstChild(sibl)
        #             f_item = tree.GetFocusedItem()
        #             if f_child.IsOk():
        #                 for c in range(item_num):
        #                     if f_child.IsOk():
        #
        #                         if f_child == f_item:
        #                             index = c
        #                             break
        #                         f_child, f_c = tree.GetNextChild(f_child, f_c)
        #
        #             nbt_path_keys.append(index)
        #         if isinstance(tree.GetItemData(sibl), tuple):
        #             nname, ddata = tree.GetItemData(sibl)
        #             nbt_path_keys.append(nname)
        #         sibl = tree.GetItemParent(sibl)
        #     nbt_path_keys.reverse()
        #
        #     return nbt_path_keys[1:]

        def root_path(child):
            nbt_path_keys = []
            if isinstance(tree.GetItemData(child), tuple):
                name, data = tree.GetItemData(child)
                nbt_path_keys.append(name)
            sibl = tree.GetItemParent(child)
            while sibl.IsOk():

                if isinstance(tree.GetItemData(sibl), tuple):
                    nname, ddata = tree.GetItemData(sibl)
                    if ddata == ListTag:

                        index = 0
                        item_num = tree.GetChildrenCount(sibl, recursively=False)
                        f_child, f_c = tree.GetFirstChild(sibl)
                        f_item = tree.GetFocusedItem()
                        f_par = tree.GetItemParent(f_item)
                        if len(nbt_path_keys) > 0:
                            for xx in range(len(nbt_path_keys) - 1):
                                f_par = tree.GetItemParent(f_par)
                        else:
                            f_par = tree.GetFocusedItem()
                        for c in range(item_num):
                            if f_child == f_par:
                                index = c
                                nbt_path_keys.append(index)
                            f_child, f_c = tree.GetNextChild(f_child, f_c)
                    nbt_path_keys.append(nname)

                sibl = tree.GetItemParent(sibl)
            nbt_path_keys.reverse()
            return nbt_path_keys[1:]

        def get_nbt(data_nbt, map_list):
            return reduce(operator.getitem, map_list[:-1], data_nbt)

        def get_real_nbt(data_nbt, map_list):
            return reduce(operator.getitem, map_list, data_nbt)

        def loop_tree_nodes(node, da_nbt):
            def is_comp(child, da_nbt):
                fcnt = tree.GetChildrenCount(child, 0)
                if isinstance(tree.GetItemData(child), tuple):
                    temp_comp = CompoundTag()
                    if tree.GetItemData(child)[1]() == CompoundTag():
                        for x in range(fcnt):
                            inner_child, cc = tree.GetFirstChild(child)
                            if inner_child.IsOk():
                                for xx in range(fcnt):
                                    if isinstance(tree.GetItemData(inner_child), tuple):
                                        k, v = tree.GetItemData(inner_child)
                                    else:
                                        v = tree.GetItemData(inner_child)
                                    if v == ListTag:
                                        temp_comp[k] = is_list(inner_child, da_nbt)
                                    elif v == CompoundTag:
                                        temp_comp[k] = is_comp(inner_child, da_nbt)
                                    else:
                                        temp_comp[k] = v
                                    inner_child, cc = tree.GetNextChild(inner_child, cc)
                        return temp_comp

            def is_list(child, da_nbt):
                first_child, c = tree.GetFirstChild(child)
                if first_child.IsOk():
                    temp_list = ListTag()
                    fcnt = tree.GetChildrenCount(child, 0)
                    if isinstance(tree.GetItemData(first_child), abc.ABCMeta):
                        for x in range(fcnt):
                            inner_child, cc = tree.GetFirstChild(first_child)  # a loop back
                            if inner_child.IsOk():
                                temp_comp = CompoundTag()
                                icnt = tree.GetChildrenCount(first_child, 0)
                                for xx in range(icnt):
                                    k, v = tree.GetItemData(inner_child)
                                    if isinstance(v, abc.ABCMeta):
                                        if v == CompoundTag:
                                            temp_comp[k] = is_comp(inner_child, da_nbt)
                                        elif v == ListTag:
                                            temp_comp[k] = is_list(inner_child, da_nbt)
                                    else:
                                        temp_comp[k] = v
                                    inner_child, cc = tree.GetNextChild(inner_child, cc)
                                temp_list.append(temp_comp)
                            first_child, c = tree.GetNextChild(first_child, c)
                        return temp_list
                    else:
                        inner_child, cc = tree.GetFirstChild(child)
                        if inner_child.IsOk():
                            for x in range(fcnt):
                                v = tree.GetItemData(inner_child)
                                temp_list.append(v)
                                inner_child, cc = tree.GetNextChild(inner_child, cc)
                        return temp_list
                else:
                    key, value = tree.GetItemData(child)
                    if value == CompoundTag or value == ListTag:
                        return value()
                    else:
                        return value

            nc = tree.GetChildrenCount(node, 0)
            child, cookie = tree.GetFirstChild(node)
            if child.IsOk():
                if isinstance(tree.GetItemData(child), tuple):
                    for i in range(nc):
                        key, value = tree.GetItemData(child)[0], tree.GetItemData(child)[1]
                        if type(value) == abc.ABCMeta:
                            the_path = root_path(child)
                            new = get_nbt(da_nbt, the_path[:-1])
                            if type(value()) == CompoundTag:
                                new[the_path[-1]] = is_comp(child, da_nbt)
                            else:
                                new[the_path[-1]] = is_list(child, da_nbt)
                        else:
                            the_path = root_path(child)
                            new = get_nbt(da_nbt, the_path)
                            new[the_path[-1]] = value
                        child, cookie = tree.GetNextChild(child, cookie)

        if opt == 'snbt':
            f_item = self.tree.GetFocusedItem()
            #
            # i_par = self.tree.GetItemParent(f_item)
            #

            root_tree = self.tree.GetRootItem()
            loop_tree_nodes(root_tree, self.nbt_new)
            t_path = root_path(f_item)

            selected_nbt = get_real_nbt(self.nbt_new, t_path)
            # self.nbt_new.save_to(r"C:\Users\drthe\AppData\Local\Packages\Microsoft.MinecraftUWP_8wekyb3d8bbwe\LocalState\games\com.mojang\minecraftWorlds\wNOGYzAFAQA=\Test.nbt", compressed=False , little_endian=True)
            if hasattr(selected_nbt, 'items'):
                tsnbt = []
                for k, v in selected_nbt.items():
                    tsnbt.append(CompoundTag({k: v}).to_snbt(5))
                snbt = '{' + ''.join([f" {x[1:-2]}," for x in tsnbt]) + "\n}"  # replace("}{", ",").replace("\n,", ",")
                pat = re.compile(r'[A-Za-z0-9._+-:]+(?=":\s)')
                matchs = pat.finditer(snbt)
                for i, x in enumerate(matchs):
                    C1 = x.span()[0] - 1 - (i)  # i*2 if no space
                    C2 = x.span()[1] - 1 - (i)  # i*2 if no space
                    if ":" in x.group():
                        C1 -= 2
                        C2 += 2
                    snbt = snbt[0:C1:] + snbt[C1 + 1::]
                    snbt = snbt[0:C2:] + " " + snbt[C2 + 1::]
            else:
                snbt = selected_to_snbt(5)
                pat = re.compile(r'[A-Za-z0-9._+-:]+(?=":\s)')
                matchs = pat.finditer(snbt)
                for i, x in enumerate(matchs):
                    C1 = x.span()[0] - 1 - (i)  # i*2 if no space
                    C2 = x.span()[1] - 1 - (i)  # i*2 if no space
                    if ":" in x.group():
                        C1 -= 2
                        C2 += 2
                    snbt = snbt[0:C1:] + snbt[C1 + 1::]
                    snbt = snbt[0:C2:] + " " + snbt[C2 + 1::]

            return t_path, self.nbt_new, snbt

        else:
            root_tree = self.tree.GetRootItem()
            loop_tree_nodes(root_tree, self.nbt_new)
            return self.nbt_new

    def close(self, evt, parent):
        parent.Close(True)
        self.Close(True)

    def build_tree(self, data, x=0, y=0, root_tag_name=""):
        try:
            self.sizer.Remove(self.tree)
            self.tree.DeleteAllItems()
        except:
            pass

        self.nbt_data = data

        def add_tree_node(_tree: wx.TreeCtrl, _parent, _items):
            for key, value in _items.items():
                new_child = None
                if isinstance(value, MutableMapping):
                    new_child = _tree.AppendItem(_parent, f"{key} {len(value)} entries")
                    add_tree_node(_tree, new_child, value)
                elif isinstance(value, MutableSequence):
                    new_child = _tree.AppendItem(_parent, f"{key} {len(value)} entries")
                    for i, item in enumerate(value):

                        if isinstance(item, MutableMapping):

                            child_child = _tree.AppendItem(new_child, f"{len(item)} entries")
                            add_tree_node(_tree, child_child, item)
                            tree.SetItemData(child_child, type(item))
                            tree.SetItemImage(
                                child_child,
                                self.image_map.get(item.__class__, self.other),
                                wx.TreeItemIcon_Normal,
                            )
                        else:
                            child_child = _tree.AppendItem(new_child, f"{item}")
                            tree.SetItemData(child_child, item)
                            tree.SetItemImage(
                                child_child,
                                self.image_map.get(item.__class__, self.other),
                                wx.TreeItemIcon_Normal,
                            )

                else:
                    new_child = _tree.AppendItem(_parent, f"{key}: {value}")

                if isinstance(value, (ListTag, CompoundTag)):

                    tree.SetItemData(new_child, (key, type(value)))
                    tree.SetItemImage(
                        new_child, self.image_map.get(value.__class__, self.other)
                    )

                else:
                    tree.SetItemData(new_child, (key, value))
                    tree.SetItemImage(
                        new_child, self.image_map.get(value.__class__, self.other)
                    )

        tree = MyTreeCtrl(self, wx.ID_ANY, wx.DefaultPosition, (10, 10),
                          wx.TR_HAS_BUTTONS, self.nbt_data)
        tree.SetBackgroundColour((0, 0, 0))
        tree.SetForegroundColour((0, 255, 0))
        font = wx.Font(14, wx.FONTFAMILY_ROMAN, wx.FONTSTYLE_MAX, wx.FONTWEIGHT_BOLD)

        tree.SetFont(font)
        tree.AssignImageList(self.image_list)
        root_tag_name = f"{len(self.nbt_data)} entries"
        root = tree.AddRoot(root_tag_name)
        tree.SetItemData(root, ("", self.nbt_data))
        tree.SetItemImage(
            root,
            self.image_map.get(
                self.nbt_data.__class__, self.image_map[TAG_Compound]
            ),
            wx.TreeItemIcon_Normal,
        )

        add_tree_node(tree, root, self.nbt_data)
        tree.Expand(root)
        tree.Bind(wx.EVT_TREE_ITEM_RIGHT_CLICK, self.tree_right_click)
        # tree.Bind(wx.EVT_LEFT_DOWN, self.tree_leftDC_click)
        tree.Bind(wx.EVT_LEFT_UP, self.tree_leftDC_click)
        # self.tree = self.build_tree(data)
        self.sizer.Add(tree, 1, wx.ALL | wx.CENTER | wx.EXPAND)
        tree.Bind(wx.EVT_LEFT_DCLICK, self.OnLeftDClick)
        tree.Bind(wx.EVT_RIGHT_DOWN, self.OnRightDown)
        tree.Bind(wx.EVT_LEFT_DOWN, self.OnLeftDown)

        # These go at the end of __init__
        tree.Bind(wx.EVT_TREE_BEGIN_RDRAG, self.OnBeginRightDrag)
        tree.Bind(wx.EVT_TREE_BEGIN_DRAG, self.OnBeginLeftDrag)
        tree.Bind(wx.EVT_TREE_END_DRAG, self.OnEndDrag)
        return tree

    def tree_leftDC_click(self, evt):
        pt = (evt.x, evt.y)

        item, a = self.tree.HitTest(pt)

        if item == self.tree.GetFocusedItem() and evt.Button(wx.MOUSE_BTN_LEFT) and a == 64:
            try:
                self.edit_dialog.Destroy()
            except:
                pass
            if isinstance(self.tree.GetItemData(item), tuple):
                name, data = self.tree.GetItemData(item)

            else:
                data = self.tree.GetItemData(item)

            if isinstance(data, abc.ABCMeta):
                datat = type(data())
            else:
                datat = type(data)

            self.has_list_type = str(datat).split(".")[-1][:-2]
            icon = self.image_list.GetBitmap(self.image_map[datat])
            try:
                self.edit_dialog.Destroy()
            except:
                pass
            self.edit_dialog = SmallEditDialog(self, "Edit", self.has_list_type, item, self.tree, icon, self.image_map)
            style = self.edit_dialog.GetWindowStyle()
            self.edit_dialog.SetWindowStyle(style | wx.STAY_ON_TOP)
            self.edit_dialog.Show()

        evt.Skip()

    def tree_right_click(self, evt):

        if isinstance(self.tree.GetItemData(evt.GetItem()), tuple):
            tag_name, tag_obj = self.tree.GetItemData(evt.GetItem())
            if type(tag_obj) == abc.ABCMeta:
                tag_obj = tag_obj()
        else:
            tag_obj = self.tree.GetItemData(evt.GetItem())

        menu = self._generate_menu(
            isinstance(tag_obj, (MutableMapping, MutableSequence, NamedTag, CompoundTag, abc.ABCMeta))
        )
        self.PopupMenu(menu, evt.GetPoint())
        menu.Destroy()
        evt.Skip()

    def popup_menu_handler(self, op_map, op_sm_map, icon_sm_map, evt):
        op_id = evt.GetId()
        op_name = None
        continues = True

        if op_id in op_map:
            op_name = op_map[op_id]

        if op_id in op_sm_map:
            tag_type = [tag_class for tag_class in self.image_map if tag_class.__name__ ==
                        op_sm_map[op_id].replace(" ", "")][0]

            item = self.tree.GetFocusedItem()

            root = self.tree.GetRootItem()
            n_child = self.tree.GetFirstChild(item)[0]
            if root == item:
                data = tag_type()
            elif n_child.IsOk():

                child_data = self.tree.GetItemData(n_child)

                if not isinstance(child_data, tuple):
                    data = child_data

                    if type(data) == abc.ABCMeta:
                        entries = self.tree.GetChildrenCount(item, 0)
                        testdata = self.tree.GetItemText(item)
                        self.tree.SetItemText(item, testdata.replace(f"{entries - 1} entries", f"{entries} entries"))
                        new_child = self.tree.AppendItem(item, f"0 entries")
                        self.tree.SetItemData(new_child, child_data())
                        self.tree.SetItemImage(
                            new_child,
                            self.image_map.get(data().__class__, self.other),
                            wx.TreeItemIcon_Normal,
                        )
                        self.tree.Expand(item)
                        continues = False
            else:
                data = tag_type()
            if continues:
                data = tag_type()
                self.has_list_type = str(type(data)).split(".")[-1][:-2]
                try:
                    self.edit_dialog.Destroy()
                except:
                    pass
                icon = self.image_list.GetBitmap(self.image_map[type(data)])
                self.edit_dialog = SmallEditDialog(self, "Add", self.has_list_type, item, self.tree, icon,
                                                   self.image_map)
                style = self.edit_dialog.GetWindowStyle()
                self.edit_dialog.SetWindowStyle(style | wx.STAY_ON_TOP)
                self.edit_dialog.Show()

        elif op_name == "copy":
            self.copy_data = self.tree.SaveItemsToList(self.tree.GetFocusedItem())

        elif op_name == "[paste]":

            self.tree.InsertItemsFromList(self.copy_data, self.tree.GetFocusedItem())
            self.tree.UnselectAll()

        elif op_name == "edit_as":
            try:
                self.edit_dialog.Destroy()
            except:
                pass
            item = self.tree.GetFocusedItem()
            self.edit_dialog = SmallEditDialog(self, "Edit_As", "SNBT", item, self.tree, None,
                                               self.image_map)
            style = self.edit_dialog.GetWindowStyle()
            self.edit_dialog.SetWindowStyle(style | wx.STAY_ON_TOP)
            self.edit_dialog.Show()

        elif op_name == "edit":
            item = self.tree.GetFocusedItem()
            try:
                self.edit_dialog.Destroy()
            except:
                pass
            if isinstance(self.tree.GetItemData(item), tuple):
                name, data = self.tree.GetItemData(item)

            else:
                data = self.tree.GetItemData(item)

            if isinstance(data, abc.ABCMeta):
                datat = type(data())
            else:
                datat = type(data)

            self.has_list_type = str(datat).split(".")[-1][:-2]
            icon = self.image_list.GetBitmap(self.image_map[datat])
            try:
                self.edit_dialog.Destroy()
            except:
                pass
            self.edit_dialog = SmallEditDialog(self, "Edit", self.has_list_type, item, self.tree, icon,
                                               self.image_map)
            style = self.edit_dialog.GetWindowStyle()
            self.edit_dialog.SetWindowStyle(style | wx.STAY_ON_TOP)
            self.edit_dialog.Show()

        elif op_name == "delete":
            selected_tag = self.tree.GetFocusedItem()
            self.tree.Delete(selected_tag)
        else:
            if op_name == "bytetag":
                selected_tag = self.tree.GetFocusedItem()
                name, data = self.tree.GetItemData(selected_tag)
                edit_dialog = SmallEditDialog(self, op_name, data, selected_tag, self.tree, None)
                style = self.edit_dialog.GetWindowStyle()
                edit_dialog.SetWindowStyle(style | wx.STAY_ON_TOP)  ###
                edit_dialog.Show()

    def _generate_menu(self, include_add_tag=False):
        menu = wx.Menu()
        s_menu = wx.Menu()

        path_list = [nbt_resources.path + "\\" + x + ".png" for x in dir(nbt_resources)]
        menu_items = [
            wx.MenuItem(menu, text="Edit", id=wx.ID_ANY),
            wx.MenuItem(menu, text="Copy", id=wx.ID_ANY),
            wx.MenuItem(menu, text="Edit_As SNBT", id=wx.ID_ANY),
            wx.MenuItem(menu, text="Delete", id=wx.ID_ANY),
        ]
        if self.copy_data:
            menu_items.insert(2, wx.MenuItem(menu, text="[Paste]", id=wx.ID_ANY))
        sub_menu = [
            wx.MenuItem(s_menu, text="Byte Tag", id=wx.ID_ANY),
            wx.MenuItem(s_menu, text="Short Tag", id=wx.ID_ANY),
            wx.MenuItem(s_menu, text="Int Tag", id=wx.ID_ANY),
            wx.MenuItem(s_menu, text="Long Tag", id=wx.ID_ANY),
            wx.MenuItem(s_menu, text="Float Tag", id=wx.ID_ANY),
            wx.MenuItem(s_menu, text="Double Tag", id=wx.ID_ANY),
            wx.MenuItem(s_menu, text="String Tag", id=wx.ID_ANY),
            wx.MenuItem(s_menu, text="Compound Tag", id=wx.ID_ANY),
            wx.MenuItem(s_menu, text="List Tag", id=wx.ID_ANY),
            wx.MenuItem(s_menu, text="Byte Array Tag", id=wx.ID_ANY),
            wx.MenuItem(s_menu, text="Long Array Tag", id=wx.ID_ANY),
            wx.MenuItem(s_menu, text="Int Array Tag", id=wx.ID_ANY),
        ]

        sub_menu[0].SetBitmap(wx.Bitmap(path_list[1]))
        sub_menu[1].SetBitmap(wx.Bitmap(path_list[8]))
        sub_menu[2].SetBitmap(wx.Bitmap(path_list[5]))
        sub_menu[3].SetBitmap(wx.Bitmap(path_list[7]))
        sub_menu[4].SetBitmap(wx.Bitmap(path_list[4]))
        sub_menu[5].SetBitmap(wx.Bitmap(path_list[3]))
        sub_menu[6].SetBitmap(wx.Bitmap(path_list[9]))
        sub_menu[7].SetBitmap(wx.Bitmap(path_list[2]))
        sub_menu[8].SetBitmap(wx.Bitmap(path_list[6]))
        sub_menu[9].SetBitmap(wx.Bitmap(path_list[0]))
        sub_menu[10].SetBitmap(wx.Bitmap(path_list[0]))
        sub_menu[11].SetBitmap(wx.Bitmap(path_list[0]))

        if include_add_tag:
            selected_tag = self.tree.GetFocusedItem()
            data_ = self.tree.GetItemData(selected_tag)
            if isinstance(data_, tuple):
                name, data = data_
            else:
                data = data_
            if type(data) == abc.ABCMeta:
                data = data()
            next_d, c = self.tree.GetFirstChild(selected_tag)
            if next_d.IsOk():
                tag_type = self.tree.GetItemData(next_d)
                if type(tag_type) == abc.ABCMeta:
                    tag_type = tag_type()
                cnt = self.tree.GetChildrenCount(selected_tag, 0)
            else:
                tag_type = None
                cnt = 0

            if isinstance(data, ListTag) and cnt > 0:

                self.has_list_type = str(type(tag_type)).split(".")[-1][:-2]
                for s_menu_item in sub_menu:
                    has_tag = s_menu_item.GetItemLabel().replace(" ", "")
                    if has_tag == self.has_list_type:
                        s_menu.Append(s_menu_item)
            else:
                for s_menu_item in sub_menu:
                    s_menu.Append(s_menu_item)

            add_menu = wx.MenuItem(menu, text="Add Tag", id=wx.ID_ANY)
            add_menu.SetSubMenu(s_menu)
            menu_items.insert(0, add_menu)

        for menu_item in menu_items:
            menu.Append(menu_item)

        op_map = {
            item.GetId(): item.GetItemLabelText().split()[0].lower()
            for item in menu_items
        }
        op_sm_map = {
            item.GetId(): item.GetItemLabelText()
            for item in sub_menu
        }
        icon_sm_map = {
            item.GetId(): item.GetBitmap()
            for item in sub_menu
        }
        menu.Bind(wx.EVT_MENU, lambda evt: self.popup_menu_handler(op_map, op_sm_map, icon_sm_map, evt))

        return menu

    def OnBeginLeftDrag(self, event):
        '''Allow drag-and-drop for leaf nodes.'''
        #
        event.Allow()
        self.dragType = "left button"
        self.dragItem = event.GetItem()

    def OnBeginRightDrag(self, event):
        '''Allow drag-and-drop for leaf nodes.'''

        event.Allow()
        self.dragType = "right button"
        self.dragItem = event.GetItem()

    def OnEndDrag(self, event):
        # If we dropped somewhere that isn't on top of an item, ignore the event
        if event.GetItem().IsOk():
            target = event.GetItem()
        else:
            return
        # Make sure this member exists.
        try:
            source = self.dragItem
        except:
            return
        # Prevent the user from dropping an item inside of itself
        if self.tree.ItemIsChildOf(target, source):
            print
            "the tree item can not be moved in to itself! "
            self.tree.Unselect()
            return

        # Get the target's parent's ID
        targetparent = self.tree.GetItemParent(target)
        if not targetparent.IsOk():
            targetparent = self.tree.GetRootItem()

        # One of the following methods of inserting will be called...
        def MoveHere(event):

            # Save + delete the source
            save = self.tree.SaveItemsToList(source)

            self.tree.Delete(source)
            newitems = self.tree.InsertItemsFromList(save, targetparent, target)
            self.tree.UnselectAll()
            for item in newitems:
                self.tree.SelectItem(item)

        def CopyHere(event):

            # Save + delete the source
            save = self.tree.SaveItemsToList(source)
            newitems = self.tree.InsertItemsFromList(save, target)
            self.tree.UnselectAll()
            for item in newitems:
                self.tree.SelectItem(item)

        def InsertInToThisGroup(event):
            # Save + delete the source
            save = self.tree.SaveItemsToList(source)
            self.tree.Delete(source)
            newitems = self.tree.InsertItemsFromList(save, target)
            # self.tree.UnselectAll()
            for item in newitems:
                self.tree.SelectItem(item)

        # ---------------------------------------

        if self.tree.GetItemData(target) and self.dragType == "right button":
            menu = wx.Menu()
            menu.Append(101, "Move to after this group", "")
            menu.Append(102, "Insert into this group", "")
            menu.Append(103, "Copy into this group", "")
            menu.UpdateUI()
            menu.Bind(wx.EVT_MENU, MoveHere, id=101)
            menu.Bind(wx.EVT_MENU, InsertInToThisGroup, id=102)
            menu.Bind(wx.EVT_MENU, CopyHere, id=103)
            self.PopupMenu(menu)
        else:
            if self.tree.IsExpanded(target):
                InsertInToThisGroup(None)
            else:
                MoveHere(None)

    # def OnRightUp(self, event):
    #     pt = event.GetPosition();
    #     item, flags = self.tree.HitTest(pt)
    #
    #     #self.tree.EditLabel(item)
    #     print(item)

    def OnLeftDown(self, event):
        print
        "control key is", event.controlDown

        pt = event.GetPosition();
        item, flags = self.tree.HitTest(pt)
        self.tree.SelectItem(item)
        event.Skip()

    def OnRightDown(self, event):
        print
        "control key is", event.controlDown

        pt = event.GetPosition();
        item, flags = self.tree.HitTest(pt)
        self.tree.SelectItem(item)
        event.Skip()

    def OnLeftDClick(self, event):
        pt = event.GetPosition();
        item, flags = self.tree.HitTest(pt)

        # expand/collapse toggle
        self.tree.Toggle(item)
        print
        "toggled ", item
        # event.Skip()

    def OnSize(self, event):
        w, h = self.GetClientSize()
        self.tree.SetSize(0, 0, w, h)

class Inventory(wx.Frame):
    def __init__(self, parent, canvas, world, *args, **kw):
        super(Inventory, self).__init__(parent, *args, **kw,
                                        style=(wx.MINIMIZE_BOX | wx.MAXIMIZE_BOX | wx.RESIZE_BORDER |
                                               wx.SYSTEM_MENU | wx.CAPTION | wx.CLOSE_BOX | wx.CLIP_CHILDREN |
                                               wx.FRAME_FLOAT_ON_PARENT),
                                        title="NBT Editor For Player Inventory")

        self.parent = parent

        self.canvas = canvas
        self.world = world
        self.platform = self.world.level_wrapper.platform
        self.font = wx.Font(13, wx.FONTFAMILY_ROMAN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        self.SetForegroundColour((0, 255, 0))
        self.SetBackgroundColour((0, 0, 0))
        self.SetFont(self.font)
        self.SetMinSize((520, 800))
        self.storage_key = CompoundTag()
        self.Freeze()

        self._sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self._sizer)

        self.font = wx.Font(11, wx.FONTFAMILY_ROMAN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        self.top_sizer = wx.BoxSizer(wx.VERTICAL)
        self.side_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.bottom_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self._sizer.Add(self.side_sizer, 1, wx.TOP | wx.LEFT, 0)
        self._sizer.Add(self.top_sizer)
        self._sizer.Add(self.bottom_sizer, 1, wx.BOTTOM | wx.LEFT, 2)
        self.items = wx.Choice(self, choices=[])
        self.items.Bind(wx.EVT_CHOICE, self.on_item_focus)

        self.info_list = wx.StaticText(self, label=" ")  # just a hack to force width
        self.top_sizer.Add(self.info_list, 0, wx.LEFT, 450)

        self.blank = wx.StaticText(self, label="")
        self.save_player_data_button = wx.Button(self, label="Save Player")
        self.save_player_snbt_button = wx.Button(self, label="Save File")
        self.remove_player_btn = wx.Button(self, label="Remove Player")
        self.load_file_grid = wx.GridSizer(2, 1, 0, -0)
        self.load_player_snbt = wx.Button(self, label="Load File")
        self.load_player_snbt_info = wx.StaticText(self,
                                                   label="NOTE : \nWhen loading file make sure to select what \n was select from the dropdown when you saved.")
        self.load_file_grid.Add(self.load_player_snbt)
        self.load_file_grid.Add(self.load_player_snbt_info)

        self.save_player_data_button.Bind(wx.EVT_BUTTON, self.save_player_data)
        self.save_player_snbt_button.Bind(wx.EVT_BUTTON, self.export_snbt)
        self.load_player_snbt.Bind(wx.EVT_BUTTON, self.import_snbt)
        self.remove_player_btn.Bind(wx.EVT_BUTTON, self.remove_player)

        self.the_grid = wx.GridSizer(3, 3, -60, -130)

        self.the_grid.Add(self.save_player_snbt_button)
        self.the_grid.Add(self.items, 0, wx.LEFT, -10)
        self.the_grid.Add(self.remove_player_btn, 0, wx.LEFT, 30)
        self.the_grid.Add(self.load_file_grid)
        self.the_grid.Add(self.blank)
        self.the_grid.Add(self.save_player_data_button, 0, wx.LEFT, 30)
        self.bottom_sizer.Add(self.the_grid)
        self.nbt_editor_instance = NBTEditor(self)

        self._sizer.Add(self.nbt_editor_instance, 130, wx.EXPAND, 51)
        if self.world.level_wrapper.platform == "bedrock":
            self._structlist = wx.Choice(self, choices=self._run_get_slist())
            self._structlist.Bind(wx.EVT_CHOICE, self.onFocus)
            self._structlist.SetSelection(0)
        else:
            self._structlist = wx.Choice(self, choices=[])  # self._run_get_slist())
            self._structlist.Bind(wx.EVT_CHOICE, self.onFocus)
            self.java_setup()
            self._structlist.SetSelection(0)
        self.nbt_editor_instance.SetBackgroundColour((0, 0, 0))
        self.nbt_editor_instance.SetForegroundColour((0, 255, 0))
        self.nbt_editor_instance.SetFont(self.font)

        self.nbt_editor_instance.Fit()

        self.top_sizer.Add(self._structlist, 0, wx.LEFT, 11)
        if self.world.level_wrapper.platform == "bedrock":
            self.get_player_data()
        self.Layout()
        self.Thaw()

    def on_item_focus(self, _):
        selcted = self.items.GetStringSelection()
        if self.world.level_wrapper.platform == "bedrock":
            self.Freeze()
            self._sizer.Detach(self.nbt_editor_instance)
            self.nbt_editor_instance.Hide()
            NBTEditor.close(self.nbt_editor_instance, None, self.GetParent())
            if selcted == "Root":

                self.nbt_editor_instance = NBTEditor(self, self.nbt_dic_list)
            else:
                self.nbt_editor_instance = NBTEditor(self, CompoundTag({selcted: self.nbt_dic_list[selcted]}))
            self._sizer.Add(self.nbt_editor_instance, 130, wx.EXPAND, 21)
            self.Layout()
            self.Thaw()
        else:
            self.Freeze()
            self._sizer.Detach(self.nbt_editor_instance)
            self.nbt_editor_instance.Hide()
            NBTEditor.close(self.nbt_editor_instance, None, self.GetParent())
            self.nbt_editor_instance = NBTEditor(self, CompoundTag({selcted: self.nbt_dic_list[selcted]}))
            self._sizer.Add(self.nbt_editor_instance, 130, wx.EXPAND, 21)
            self.Layout()
            self.Thaw()

    def onFocus(self, evt):
        if self.world.level_wrapper.platform == "bedrock":
            setdata = self._structlist.GetString(self._structlist.GetSelection())
            self.get_player_data()
        else:
            s_player = self._structlist.GetStringSelection()
            if s_player == '~local_player':
                path_to = self.world.level_wrapper.path + "/" + "level.dat"
            else:
                path_to = self.world.level_wrapper.path + "/PlayersData/" + s_player + ".dat"
            with open(path_to, "rb") as dat:
                self.data_nbt = load(dat, compressed=True, little_endian=False)
                if s_player == '~local_player':
                    for k, v in self.data_nbt['Data']['Player'].items():
                        self.nbt_dic_list[k] = v
                else:
                    for k, v in self.data_items():
                        self.nbt_dic_list[k] = v

                self._sizer.Detach(self.nbt_editor_instance)
                self.nbt_editor_instance.Hide()
                NBTEditor.close(self.nbt_editor_instance, None, self.GetParent())
                self.nbt_editor_instance = NBTEditor(self, CompoundTag({"Inventory": self.nbt_dic_list["Inventory"]}))
                root = self.nbt_editor_instance.tree.GetRootItem()
                first_c, c = self.nbt_editor_instance.tree.GetFirstChild(root)

                self.nbt_editor_instance.tree.Expand(first_c)
                self._sizer.Add(self.nbt_editor_instance, 130, wx.EXPAND, 21)
                self.Layout()

                # self.nbt_editor_instance.SetValue(self.nbt_dic_list.get('Inventory'))

    def _run_set_data(self, _):
        player = self.level_db.get(b'~local_player')
        data = self.nbt_editor_instance.GetValue()
        nnbt = from_snbt(data)

        data2 = nsave_to(compressed=False, little_endian=True)
        self.level_db.put(b'~local_player', data2)

    def update_player_data(self, new_data):
        self_ = self.Parent.Parent
        seleted_ = self_.items.GetStringSelection()

        save_expanded = []
        # self.Freeze()
        f_root = self_.nbt_editor_instance.tree.GetRootItem()

        r_c = self_.nbt_editor_instance.tree.GetChildrenCount(f_root, 0)

        def get_full_path(child):
            tree = self_.nbt_editor_instance.tree
            index = 0
            p_type = None
            the_sib_items = None
            nbt_path_keys = []
            if isinstance(tree.GetItemData(child), tuple):
                name, data = tree.GetItemData(child)
                nbt_path_keys.append(name)
            sibl = tree.GetItemParent(child)
            while sibl.IsOk():
                the_sib_items = sibl
                if isinstance(tree.GetItemData(sibl), tuple):
                    p_type = type(tree.GetItemData(sibl)[1])
                else:
                    p_type = tree.GetItemData(sibl)

                if p_type == ListTag or p_type == CompoundTag:

                    item_num = tree.GetChildrenCount(sibl, recursively=False)
                    f_child, f_c = tree.GetFirstChild(sibl)
                    f_item = child
                    for c in range(item_num):
                        if f_child == f_item:
                            index = c
                            break
                        f_child, f_c = tree.GetNextChild(f_child, f_c)
                    nbt_path_keys.append(index)
                if isinstance(tree.GetItemData(sibl), tuple):
                    nname, ddata = tree.GetItemData(sibl)
                    nbt_path_keys.append(nname)
                sibl = tree.GetItemParent(sibl)
            nbt_path_keys.reverse()
            return nbt_path_keys[1:]

        def root_path(child):
            tree = self_.nbt_editor_instance.tree
            nbt_path_keys = []
            if isinstance(tree.GetItemData(child), tuple):
                name, data = tree.GetItemData(child)
                nbt_path_keys.append(name)
            sibl = tree.GetItemParent(child)
            while sibl.IsOk():
                if isinstance(tree.GetItemData(sibl), tuple):
                    nname, ddata = tree.GetItemData(sibl)
                    if ddata == ListTag:
                        index = 0
                        item_num = tree.GetChildrenCount(sibl, recursively=False)
                        f_child, f_c = tree.GetFirstChild(sibl)
                        f_item = child
                        f_par = tree.GetItemParent(f_item)
                        if len(nbt_path_keys) > 0:
                            for xx in range(len(nbt_path_keys) - 1):
                                f_par = tree.GetItemParent(f_par)
                        else:
                            f_par = child
                        for c in range(item_num):
                            if f_child == f_par:
                                index = c
                                nbt_path_keys.append(index)
                            f_child, f_c = tree.GetNextChild(f_child, f_c)
                    nbt_path_keys.append(nname)
                sibl = tree.GetItemParent(sibl)
            nbt_path_keys.reverse()
            return nbt_path_keys[1:]

        def recurtree(item):
            # for c in range(r_c):
            if item.IsOk():
                i_c = self_.nbt_editor_instance.tree.GetChildrenCount(item, recursively=True)
                f_ic, cc_i = self_.nbt_editor_instance.tree.GetFirstChild(item)
                for ci in range(i_c):
                    if f_ic.IsOk():

                        if self_.nbt_editor_instance.tree.IsExpanded(f_ic):
                            save_expanded.append(copy.copy(root_path(f_ic)))
                        if self_.nbt_editor_instance.tree.GetChildrenCount(f_ic) > 0:
                            recurtree(f_ic)
                    f_ic, cc_i = self_.nbt_editor_instance.tree.GetNextChild(f_ic, cc_i)

        recurtree(f_root)
        current_scr_h = self_.nbt_editor_instance.tree.GetScrollPos(orientation=wx.VERTICAL)

        self_.Freeze()
        self_._sizer.Detach(self_.nbt_editor_instance)

        self_.nbt_editor_instance.Hide()
        self_.nbt_dic_list[seleted_] = new_data
        NBTEditor.close(self_.nbt_editor_instance, None, self_.GetParent())
        self_.nbt_editor_instance = NBTEditor(self_, self_.nbt_dic_list[seleted_])
        root = self_.nbt_editor_instance.tree.GetRootItem()
        first_c, c = self_.nbt_editor_instance.tree.GetFirstChild(root)

        def re_expand(item):

            if item.IsOk():
                i_c = self_.nbt_editor_instance.tree.GetChildrenCount(item)
                f_ic, cc_i = self_.nbt_editor_instance.tree.GetFirstChild(item)

                for ci in range(i_c):
                    if f_ic.IsOk():

                        if root_path(f_ic) in save_expanded:
                            self_.nbt_editor_instance.tree.Expand(f_ic)
                        if self_.nbt_editor_instance.tree.GetChildrenCount(f_ic) > 0:
                            re_expand(f_ic)
                    f_ic, cc_i = self_.nbt_editor_instance.tree.GetNextChild(f_ic, cc_i)

        self_.nbt_editor_instance.tree.Expand(first_c)
        re_expand(root)
        self_._sizer.Add(self_.nbt_editor_instance, 130, wx.EXPAND, 21)
        self_.nbt_editor_instance.tree.SetScrollPos(wx.VERTICAL, current_scr_h)
        self_.Layout()
        self_.Thaw()
        self.Close()

        # self.nbt_editor_instance.SetValue(self.nbt_dic_list["Inventory"].to_snbt(1))

    def get_player_data(self):

        setdata = self._structlist.GetStringSelection()  # self._structlist.GetString(self._structlist.GetSelection())
        enS = setdata.encode("utf-8")
        try:
            player = self.level_db.get(enS).replace(b'\x08\n\x00StorageKey\x08\x00',
                                                    b'\x07\n\x00StorageKey\x08\x00\x00\x00')
            self.nbt_dic_list = load(player, little_endian=True)
            self.items.SetItems(
                ["Root", "EnderChestInventory", "Inventory", "PlayerLevel", "Armor", "Offhand", "Mainhand", "abilities",
                 "ActiveEffects", "PlayerGameMode", "Attributes", "Pos", "Invulnerable", "Tags"])
            self.items.SetSelection(2)

            self.Freeze()
            self._sizer.Detach(self.nbt_editor_instance)
            self.nbt_editor_instance.Hide()
            NBTEditor.close(self.nbt_editor_instance, None, self.GetParent())
            self.nbt_editor_instance = NBTEditor(self, CompoundTag({"Inventory": self.nbt_dic_list["Inventory"]}))
            root = self.nbt_editor_instance.tree.GetRootItem()
            first_c, c = self.nbt_editor_instance.tree.GetFirstChild(root)

            self.nbt_editor_instance.tree.Expand(first_c)
            self._sizer.Add(self.nbt_editor_instance, 130, wx.EXPAND, 21)
            self.Layout()
            self.Thaw()
            # self.nbt_editor_instance.SetValue(self.nbt_dic_list["Inventory"].to_snbt(1))
        except:
            self.Onmsgbox("Cant Find Local Player", "Open locally In Minecraft to regenerate the player.")

    def Onmsgbox(self, caption, message):  # message
        wx.MessageBox(message, caption, wx.OK | wx.ICON_INFORMATION)

    def save_player_data(self, _):
        new_data = NBTEditor.build_to(self.nbt_editor_instance, _)
        if self.world.level_wrapper.platform == "bedrock":
            theKey = self._structlist.GetStringSelection().encode("utf-8")
            if self.items.GetStringSelection() == "Root":
                self.nbt_dic_list = new_data
            else:
                selcted = self.items.GetStringSelection()
                self.nbt_dic_list[selcted] = new_data[self.items.GetStringSelection()]
            try:
                rawdata = self.nbt_dic_list.save_to(compressed=False, little_endian=True) \
                    .replace(b'\x07\n\x00StorageKey\x08\x00\x00\x00', b'\x08\n\x00StorageKey\x08\x00')
                self.level_db.put(theKey, rawdata)
                self.Onmsgbox("Saved", f"All went well")
            except Exception as e:
                self.Onmsgbox("Error", f"Something went wrong: {e}")


        else:
            data = new_data[self.items.GetStringSelection()].to_snbt()
            selection = self.items.GetStringSelection()
            s_player = self._structlist.GetStringSelection()
            if s_player == '~local_player':
                self.data_nbt['Data']['Player'][selection] = from_snbt(data)
            else:
                self.data_nbt[selection] = from_snbt(data)

            nbt_file = self.data_save_to(compressed=True, little_endian=False)

            if s_player == '~local_player':
                path_to = self.world.level_wrapper.path + "/" + "level.dat"
            else:
                path_to = self.world.level_wrapper.path + "/PlayersData/" + s_player + ".dat"
            with open(path_to, "wb") as dat:
                dat.write(nbt_file)
            self.Onmsgbox("Saved", f"All went well")

    def export_snbt(self, _):
        data = self.nbt_editor_instance.build_to(_, "raw")
        with wx.FileDialog(self, "Save NBT file", wildcard="NBT files (*.NBT)|*.NBT",
                           style=wx.FD_SAVE) as fileDialog:
            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return
            else:
                pathname = fileDialog.GetPath()
        data.save_to(pathname, little_endian=True, compressed=False)

    def import_snbt(self, _):
        with wx.FileDialog(self, "Open NBT file", wildcard="SNBT files (*.NBT)|*.NBT",
                           style=wx.FD_OPEN) as fileDialog:
            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return
            else:
                pathname = fileDialog.GetPath()
        data = load(pathname, little_endian=True, compressed=False).compound
        # print(type(data.compound),len(data.compound))
        # self.nbt_editor_instance.sizer.Hide(self.nbt_editor_instance.tree)
        # self.nbt_editor_instance.tree.DeleteAllItems()
        self.Freeze()
        self._sizer.Detach(self.nbt_editor_instance)
        self.nbt_editor_instance.Hide()
        NBTEditor.close(self.nbt_editor_instance, None, self.GetParent())
        self.nbt_editor_instance = NBTEditor(self, data)
        self._sizer.Add(self.nbt_editor_instance, 130, wx.EXPAND, 21)
        self.Layout()
        self.Thaw()

        # self.nbt_editor_instance.build_tree(self, data)

    def remove_player(self, _):
        if self.world.level_wrapper.platform == "bedrock":
            theKey = self._structlist.GetStringSelection().encode("utf-8")
            wxx = wx.MessageBox("You are going to deleted \n " + str(theKey),
                                "This can't be undone Are you Sure?", wx.OK | wx.CANCEL | wx.ICON_INFORMATION)
            if wxx == int(16):
                return
            self.level_db.delete(theKey)
            wxx = wx.MessageBox("THis " + str(theKey) + "has been deleted \n  Reload plugin to see changes \n"
                                                        "Reloading in minecraft will regenerate the player",
                                "PLAYER " + str(theKey) + " DELETED", wx.OK | wx.ICON_INFORMATION)
        else:
            s_player = self._structlist.GetStringSelection()
            if s_player == '~local_player':
                print("You dont want to delete this")
                pass  # path_to = self.world.level_wrapper.path + "/" + "level.dat"
            else:
                path_to = self.world.level_wrapper.path + "/PlayersData/" + s_player + ".dat"
            os.remove(path_to)
        self._structlist.Clear()
        self._structlist.Append(self._run_get_slist())
        self._structlist.SetSelection(0)

    def _run_get_slist(self):
        l = []
        l.append(b'~local_player')
        for k, v in self.level_db.iterate(start=b'player_server_',
                                          end=b'player_server_\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF'):
            l.append(k)
        return l

    def setup_data(self):
        self.nbt_dic_list = collections.defaultdict()
        self.data_nbt = CompoundTag()
        if self.world.level_wrapper.platform == "bedrock":
            self.get_player_data()
            self._structlist.SetForegroundColour((0, 255, 0))
            self._structlist.SetBackgroundColour((0, 0, 0))
        else:
            s_player = self._structlist.GetStringSelection()
            if s_player == '~local_player':
                path_to = self.world.level_wrapper.path + "/" + "level.dat"
            else:
                path_to = self.world.level_wrapper.path + "/PlayersData/" + s_player + ".dat"
            with open(path_to, "rb") as dat:
                self.data_nbt = load(dat, compressed=True, little_endian=False)
                if s_player == '~local_player':
                    for k, v in self.data_nbt['Data']['Player'].items():
                        self.nbt_dic_list[k] = v
                else:
                    for k, v in self.data_items():
                        self.nbt_dic_list[k] = v
                self.items.SetItems(["EnderItems", "Inventory"])
                self.items.SetSelection(1)
                self.Freeze()
                self._sizer.Detach(self.nbt_editor_instance)
                self.nbt_editor_instance.Hide()
                NBTEditor.close(self.nbt_editor_instance, None, self.GetParent())
                self.nbt_editor_instance = NBTEditor(self,
                                                     CompoundTag({"Inventory": self.nbt_dic_list["Inventory"]}))
                root = self.nbt_editor_instance.tree.GetRootItem()
                first_c, c = self.nbt_editor_instance.tree.GetFirstChild(root)

                self.nbt_editor_instance.tree.Expand(first_c)
                self._sizer.Add(self.nbt_editor_instance, 130, wx.EXPAND, 21)
                self.Layout()
                self.Thaw()
                ##################################################################################################

    def java_setup(self):
        players = []
        for p in self.world.players.all_player_ids():
            players.append(p)
        players.reverse()
        self._structlist.SetItems(players)
        self._structlist.SetSelection(0)
        self.setup_data()

    @property
    def level_db(self):
        level_wrapper = self.world.level_wrapper
        if hasattr(level_wrapper, "level_db"):
            return level_wrapper.level_db
        else:
            return level_wrapper._level_manager._db

class RandomFiller(wx.Frame):
    def __init__(self, parent, canvas, world, *args, **kw):
        super(RandomFiller, self).__init__(parent, *args, **kw,
                                           style=(wx.MINIMIZE_BOX | wx.MAXIMIZE_BOX | wx.RESIZE_BORDER |
                                                  wx.SYSTEM_MENU | wx.CAPTION | wx.CLOSE_BOX | wx.CLIP_CHILDREN |
                                                  wx.FRAME_FLOAT_ON_PARENT),
                                           title="NBT Editor for Entities")
        self.parent = parent
        self.canvas = canvas
        self.world = world
        self.platform = self.world.level_wrapper.platform
        self.font = wx.Font(13, wx.FONTFAMILY_ROMAN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        self.SetForegroundColour((0, 255, 0))
        self.SetBackgroundColour((0, 0, 0))
        self.SetFont(self.font)
        self.SetMinSize((520, 720))
        self.toggle = True
        self.Freeze()
        self.arr = {}
        self._sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self._sizer)
        self.saveload = wx.BoxSizer(wx.HORIZONTAL)
        self._sizer.Add(self.saveload, 0, wx.TOP, 5)
        self.replace_list_txt = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_BESTWRAP, size=(322, 300))
        self.keep_list_txt = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_BESTWRAP, size=(322, 300))
        self.replace = wx.CheckBox(self, label="Replace Blocks Mode( default fill )")
        self._run_buttonA = wx.Button(self, label="Apply")
        self._run_buttonA.Bind(wx.EVT_BUTTON, self._apply_changes)

        self._replace_label = wx.StaticText(self, label="Replace")
        self._keep_label = wx.StaticText(self, label="Keep")

        self.open_block_window = wx.Button(self, label="Select Blocks")
        self.open_block_window.Bind(wx.EVT_BUTTON, self.block_list)

        self.saveload.Add(self.replace, 0, wx.LEFT, 0)

        self.saveload.Add(self._run_buttonA, 10, wx.LEFT, 40)

        self._sizer.Add(self.open_block_window, 0, wx.LEFT, 90)
        self._sizer.Add(self._replace_label)
        self._sizer.Add(self.replace_list_txt)
        self._sizer.Add(self._keep_label)
        self._sizer.Add(self.keep_list_txt)

        self.saveload.Fit(self)
        self._sizer.Fit(self)
        self.toggle_count = 0
        self.Layout()
        self.Thaw()

    def set_block(self, event, data, toggle):

        x, y, z = self.canvas.selection.selection_group.min
        block, enty = self.world.get_version_block(x, y, z, self.canvas.dimension,
                                                   (self.world.level_wrapper.platform,
                                                    self.world.level_wrapper.version))  # self.canvas.selection.selection_group.min

        the_snbt = f"{block.namespaced_name}" \
                   f"\n{CompoundTag(block.properties).to_snbt(1)}"
        try:
            e_block_u = self.world.get_block(x, y, z, self.canvas.dimension).extra_blocks[0]
            pf, vb = self.world.level_wrapper.platform, self.world.level_wrapper.version

            e_block = self.world.translation_manager.get_version(pf, vb).block.from_universal(e_block_u)[0]

            the_extra_snbt = f"\n<Extra_Block>\n{e_block.namespaced_name}\n" \
                             f"{CompoundTag(e_block.properties).to_snbt(1)}"

            the_snbt += f"{the_extra_snbt}"
        except:
            the_e = f"\n<Extra_Block>" \
                    f"\nNone"
            the_snbt += f"{the_e}"
        self.block_prop.SetValue(the_snbt)
        data.block = block

    def get_block(self, event, data, toggle):
        the_snbt = f"{data.block.namespaced_name}" \
                   f"||{CompoundTag(data.properties).to_snbt()}"
        self.block_prop.SetValue(the_snbt)

    def block_list(self, _):
        self.window = wx.Frame(self.parent, title="Add Blocks", size=(550, 570),
                               style=wx.DEFAULT_FRAME_STYLE | wx.STAY_ON_TOP)
        self.window.Centre()
        self.w_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.window.SetSizer(self.w_sizer)
        # if self.univeral_mode.GetValue():
        #     self.chosen_platform = "universal"
        #     self.chosen_name_space = "universal_minecraft"
        if True:
            self.chosen_platform = self.world.level_wrapper.platform
            self.chosen_name_space = "minecraft"
        self._block_define = BlockDefine(
            self.window,
            self.world.translation_manager,
            wx.VERTICAL,
            force_blockstate=False,
            # platform="universal",
            namespace=self.chosen_name_space,
            *([self.chosen_platform]),
            # *(self.options.get("fill_block_options", []) or [self.world.level_wrapper.platform]),
            show_pick_block=False
        )

        self._block_define.Bind(EVT_PROPERTIES_CHANGE, lambda event: self.get_block(event, self._block_define, True))

        self.canvas.Bind(EVT_SELECTION_CHANGE, lambda event: self.set_block(event, self._block_define, False))
        self.block_prop = wx.TextCtrl(
            self.window, style=wx.TE_MULTILINE | wx.TE_BESTWRAP, size=(300, 520)
        )

        self.copy_to_replace_button = wx.Button(self.window, label="Add Replace")
        self.copy_to_replace_button.Bind(wx.EVT_BUTTON, self.copy_to_replace)

        self.copy_to_keep_button = wx.Button(self.window, label="Add Keep")
        self.copy_to_keep_button.Bind(wx.EVT_BUTTON, self.copy_to_keep)

        self.grid_top_ew = wx.GridSizer(1, 2, 0, 0)
        self.grid_top_ew.Add(self.copy_to_replace_button, 0, wx.LEFT, 20)
        self.grid_top_ew.Add(self.copy_to_keep_button, 0, wx.LEFT, 20)

        self.grid_box_pop = wx.BoxSizer(wx.VERTICAL)

        self.grid_box_pop.Add(self.grid_top_ew)

        self.grid_box_pop.Add(self.block_prop)

        self.grid_left = wx.GridSizer(2, 1, -470, 0)

        self.grid_left.Add(self._block_define)
        self.w_sizer.Add(self.grid_left)
        self.w_sizer.Add(self.grid_box_pop)
        self._block_define.Fit()
        self._block_define.Layout()
        self.grid_box_pop.Layout()

        self.window.Bind(wx.EVT_CLOSE, lambda event: self.OnClose(event))
        self.window.Enable()

        self.window.Show(True)

    def copy_find_select(self, _):
        self.textSearch.SetValue(self._block_define.block_name + " ")

    def copy_to_replace(self, _):

        self.replace_list_txt.SetValue(self.replace_list_txt.GetValue() +
                                       self.block_prop.GetValue() + '\n')

    def copy_to_keep(self, _):

        self.keep_list_txt.SetValue(self.keep_list_txt.GetValue() +
                                    self.block_prop.GetValue() + '\n')

    def OnClose(self, event):
        self.canvas.Unbind(EVT_SELECTION_CHANGE)
        self.window.Show(False)

    def block(self, block):
        self._picker.set_namespace(block.namespace)
        self._picker.set_name(block.base_name)
        self._update_properties()
        self.properties = block.properties

    def bind_events(self):
        super().bind_events()
        self._selection.bind_events()
        self._selection.enable()

    def enable(self):
        self._selection = BlockSelectionBehaviour(self.canvas)
        self._selection.enable()

    def _apply_changes(self, _):
        self.canvas.run_operation(self._run_job)

    def _run_job(self):
        import random
        platform = self.world.level_wrapper.platform
        version = self.world.level_wrapper.version

        blocks = []
        rep_blocks = []
        keep_blocks = []
        keep = self.keep_list_txt.GetValue()
        data_keep = keep.split("\n")
        for c in range(0, len(data_keep)):
            if "||" not in data_keep[c]:
                break
            blks, props = data_keep[c].split("||")
            blk_space, blk_name = blks.split(":")

            blk = Block(blk_space, blk_name, dict(from_snbt(props)))
            keep_blocks.append(blk)

        if not self.replace.GetValue():
            data = self.replace_list_txt.GetValue()
            data = data.split("\n")

            for c in range(0, len(data)):
                if "||" not in data[c]:
                    break
                blks, props = data[c].split("||")
                blk_space, blk_name = blks.split(":")

                blk = Block(blk_space, blk_name, dict(from_snbt(props)))
                blocks.append(blk)

            selection = [x for x in self.canvas.selection.selection_group.blocks]
            random.shuffle(selection)
            random.shuffle(blocks)
            rng_inx = 0

        if self.replace.GetValue():
            data = self.replace_list_txt.GetValue()
            data = data.split("\n")
            for c in range(0, len(data)):
                if "||" not in data[c]:
                    break
                blks, props = data[c].split("||")
                blk_space, blk_name = blks.split(":")

                blk = Block(blk_space, blk_name, dict(from_snbt(props)))
                rep_blocks.append(blk)
            random.shuffle(rep_blocks)
            pf, vb = self.world.level_wrapper.platform, self.world.level_wrapper.version
            locate = [l for l in self.canvas.selection.selection_group.blocks]
            blocks_in = [self.world.translation_manager.get_version(pf, vb).block.from_universal(
                self.world.get_block(b[0], b[1], b[2], self.canvas.dimension))[0]
                         for b in locate]
            single_blocks = list(dict.fromkeys(blocks_in))
            random.shuffle(single_blocks)
            for inx, b in enumerate(single_blocks):
                if inx == len(rep_blocks):
                    break
                if "minecraft:air" not in str(b):
                    for i, blk in enumerate(blocks_in):
                        if b == blk:
                            blocks_in[i] = rep_blocks[inx]

            for (x, y, z), b in zip(locate, blocks_in):
                current_b = self.world.translation_manager.get_version(platform, version).block.from_universal(
                    self.world.get_block(x, y, z, self.canvas.dimension))
                if current_b[0] not in keep_blocks:
                    print(current_b, keep_blocks, current_b not in keep_blocks)
                    self.world.set_version_block(x, y, z, self.canvas.dimension, (platform, version), b,
                                                 None)
        else:
            for s in range(0, len(selection), len(blocks)):
                for b in range(len(blocks)):
                    if rng_inx > len(selection) - 1:
                        break
                    x, y, z = selection[rng_inx][0], selection[rng_inx][1], selection[rng_inx][2]
                    rng_inx += 1
                    current_b = (self.world.translation_manager.get_version(platform, version).
                                 block.from_universal(self.world.get_block(x, y, z, self.canvas.dimension)))
                    if current_b[0] not in keep_blocks:
                        self.world.set_version_block(x, y, z, self.canvas.dimension, (platform, version), blocks[b],
                                                     None)

class ShapePainter(wx.Frame):
    def __init__(self, parent, canvas, world, *args, **kw):
        super(ShapePainter, self).__init__(parent, *args, **kw,
                                           style=(wx.MINIMIZE_BOX | wx.MAXIMIZE_BOX | wx.RESIZE_BORDER |
                                                  wx.SYSTEM_MENU | wx.CAPTION | wx.CLOSE_BOX | wx.CLIP_CHILDREN |
                                                  wx.FRAME_FLOAT_ON_PARENT),
                                           title="NBT Editor for Entities")
        self.parent = parent
        self.canvas = canvas
        self.world = world
        self.platform = self.world.level_wrapper.platform
        self.font = wx.Font(13, wx.FONTFAMILY_ROMAN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        self.SetForegroundColour((0, 255, 0))
        self.SetBackgroundColour((0, 0, 0))
        self.SetFont(self.font)
        self.SetMinSize((520, 720))
        self.Freeze()
        self._is_enabled = True
        self._moving = True
        self._sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self._sizer)

        self._block_define = BlockDefine(
            self,
            self.world.translation_manager,
            wx.VERTICAL,
            force_blockstate=False,
            # platform="universal",
            namespace='minecraft',
            *([self.world.level_wrapper.platform]),
            show_pick_block=False
        )
        self.options_sizer = wx.BoxSizer(wx.VERTICAL)
        self.bot_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.move_boxs_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.font = wx.Font(16, wx.FONTFAMILY_ROMAN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)

        self.staus_pause_pointer = wx.StaticText(self, label="Press P To Pause Pointer")
        self.staus_pause_pointer.SetFont(self.font)
        self.staus_pause_pointer.SetForegroundColour((11, 220, 11))
        self._sizer.Add(self.options_sizer, 1, wx.ALL, 0)
        self._sizer.Add(self.bot_sizer, 0, wx.BOTTOM | wx.LEFT, 0)
        self._sizer.Add(self.staus_pause_pointer, 0, wx.BOTTOM | wx.LEFT, 0)
        self._sizer.Add(self.move_boxs_sizer, 25, wx.EXPAND | wx.LEFT | wx.RIGHT, 0)
        self._sizer.Add(self._block_define, 25, wx.EXPAND | wx.LEFT | wx.RIGHT, 0)

        self._up = wx.Button(self, label="Up", size=(36, 35))
        self._up.Bind(wx.EVT_BUTTON, self._boxUp('m'))
        self._down = wx.Button(self, label="Down", size=(36, 35))
        self._down.Bind(wx.EVT_BUTTON, self._boxDown('m'))
        self._east = wx.Button(self, label="East", size=(36, 35))
        self._east.Bind(wx.EVT_BUTTON, self._boxEast('m'))
        self._west = wx.Button(self, label="West", size=(36, 35))
        self._west.Bind(wx.EVT_BUTTON, self._boxWest('m'))
        self._north = wx.Button(self, label="North", size=(36, 35))
        self._north.Bind(wx.EVT_BUTTON, self._boxNorth('m'))
        self._south = wx.Button(self, label="South", size=(36, 35))
        self._south.Bind(wx.EVT_BUTTON, self._boxSouth('m'))

        brush_option = ["Circle", "Diamond", "Square", "Pyramid Up", "Pyramid Down", 'Dome', "bowl", 'walls', "tunnel"]

        self.options = CustomRadioBox(self, 'Brush Type', brush_option, (0, 255, 0), sty=wx.RA_SPECIFY_COLS, md=3)

        self.options_sizer.Add(self.options)

        self.l_int_size = wx.StaticText(self, label=" Size: ")

        self.l_int_y = wx.StaticText(self, label=" Y: ")
        self.l_int_x = wx.StaticText(self, label=" X: ")
        self.l_int_z = wx.StaticText(self, label=" Z: ")
        self.int_size = wx.SpinCtrl(self, initial=4)
        self.int_size.Bind(wx.EVT_SPINCTRL, self.size_on_change)
        self.int_y = wx.SpinCtrl(self, initial=4)
        self.int_x = wx.SpinCtrl(self, initial=4)
        self.int_z = wx.SpinCtrl(self, initial=4)

        self.bot_sizer.Add(self.l_int_size)
        self.bot_sizer.Add(self.int_size)
        self.bot_sizer.Add(self.l_int_y)
        self.bot_sizer.Add(self.int_y)
        self.bot_sizer.Add(self.l_int_x)
        self.bot_sizer.Add(self.int_x)
        self.bot_sizer.Add(self.l_int_z)
        self.bot_sizer.Add(self.int_z)
        self.bot_sizer.Fit(self)

        self.boxgrid_b = wx.GridSizer(1, 6, 1, 5)

        # self.boxgrid_b.Add(self.staus_pause_pointer)
        self.boxgrid_b.Add(self._up)
        self.boxgrid_b.Add(self._down)
        self.boxgrid_b.Add(self._north)
        self.boxgrid_b.Add(self._south)
        self.boxgrid_b.Add(self._east)
        self.boxgrid_b.Add(self._west)

        self.move_boxs_sizer.Add(self.boxgrid_b, 0, wx.LEFT, 50)
        self.move_boxs_sizer.Fit(self)
        self._sizer.Hide(self.move_boxs_sizer, recursive=True)

        self._pause_pointer = True
        self.location_current = []
        self.location_last = [0]
        self._block_define.Fit()
        self.click = False
        self.toggle = False
        self.point_evt = []
        self.location_last = self.point_evt
        self.no_need_to_wait = True
        self.event_cnt = 0
        self.v1, self.v2, self.v3, self.v4, self.v5 = '', 0, 0, 0, 0
        self.sg = SelectionGroup
        self.current_point = ()
        self.Bind(wx.EVT_CLOSE, self.on_close)
        self.bind_events()
        self.Layout()
        self.Thaw()

    @property
    def wx_add_options(self) -> Tuple[int, ...]:

        return (0,)

    def _cls(self):
        print("\033c\033[3J", end='')

    def size_on_change(self, _):
        self.int_y.SetValue(self.int_size.GetValue())
        self.int_x.SetValue(self.int_size.GetValue())
        self.int_z.SetValue(self.int_size.GetValue())

    def cusotome_brush(self, mx, my, mz):
        xx = (mx + mx + 1) >> 1
        yy = (my + 1 + my + 2) >> 1
        zz = (mz + mz + 1) >> 1
        size = self.int_size.GetValue()
        area = {}
        if self.options.GetSelection() == 0:
            diff = size - 1
            o_size = size ** 2
            inner_size = diff ** 2
        elif self.options.GetSelection() == 1:
            diff = size - 1
            o_size = size
            inner_size = diff

        if self.options.GetSelection() < 2:
            for y in range(self.int_y.GetValue() + 1):
                if self.options.GetSelection() == 0:
                    yyy = y ** 2 - 1
                elif self.options.GetSelection() == 1:
                    yyy = y
                for z in range(self.int_z.GetValue() + 1):
                    if self.options.GetSelection() == 0:
                        zzz = z ** 2 - 1
                    elif self.options.GetSelection() == 1:
                        zzz = z
                    for x in range(self.int_x.GetValue() + 1):
                        if self.options.GetSelection() == 0:
                            xxx = x ** 2 - 1
                        elif self.options.GetSelection() == 1:
                            xxx = x
                        sel_box = None
                        overall = yyy + xxx + zzz
                        # if self.options.GetSelection() == 0:
                        #     if overall < o_size:
                        #         sel_box = "Yes"
                        # else:

                        if overall >= inner_size:
                            if overall <= o_size:
                                sel_box = "Yes"

                        if sel_box is not None:
                            area[(xx - x, yy + y, zz - z)] = sel_box
                            area[(xx - x, yy - y, zz + z)] = sel_box
                            area[(xx - x, yy - y, zz - z)] = sel_box
                            area[(xx + x, yy + y, zz + z)] = sel_box
                            area[(xx + x, yy + y, zz - z)] = sel_box
                            area[(xx + x, yy - y, zz + z)] = sel_box
                            area[(xx + x, yy - y, zz - z)] = sel_box
                            area[(xx - x, yy + y, zz + z)] = sel_box

            # dupes = []
            # points = []
            for (x, y, z), sel_box in area.items():
                if sel_box:
                    yield SelectionBox((x - 1, y - 1, z - 1), (x, y, z))

        elif self.options.GetSelection() == 2:
            xx = (xx + xx + 1) >> 1
            yy = (yy + 1 + yy + 2) >> 1
            zz = (zz + zz + 1) >> 1
            size = self.int_size.GetValue()
            diff = size - 1
            area = {}
            o_size = size
            inner_size = diff
            for y in range(self.int_y.GetValue() + 1):
                yyy = y
                for z in range(self.int_z.GetValue() + 1):
                    zzz = z
                    for x in range(self.int_x.GetValue() + 1):
                        xxx = x
                        sel_box = None
                        overall = yyy + xxx + zzz
                        if yyy > inner_size:
                            sel_box = "Yes"
                        if zzz > inner_size:
                            sel_box = "Yes"
                        if xxx > inner_size:
                            sel_box = "Yes"

                        if sel_box is not None:
                            area[(xx - x, yy + y, zz - z)] = sel_box
                            area[(xx - x, yy - y, zz + z)] = sel_box
                            area[(xx - x, yy - y, zz - z)] = sel_box
                            area[(xx + x, yy + y, zz + z)] = sel_box
                            area[(xx + x, yy + y, zz - z)] = sel_box
                            area[(xx + x, yy - y, zz + z)] = sel_box
                            area[(xx + x, yy - y, zz - z)] = sel_box
                            area[(xx - x, yy + y, zz + z)] = sel_box
            for (x, y, z), sel_box in area.items():
                if sel_box:
                    yield SelectionBox((x - 1, y - 1, z - 1), (x, y, z))
        elif self.options.GetSelection() == 3:  # upright pyramid
            x, y, z = self.location_last
            sg = []

            for i in range(size):
                for j in range(-size // 2 + i, size // 2 - i + 1):
                    for k in range(-size // 2 + i, size // 2 - i + 1):
                        if (x + j) in range(x - size // 2, x + size // 2 + 1) and (z + k) in range(z - size // 2,
                                                                                                   z + size // 2 + 1):
                            sg.append(
                                ((x + j, y - size + i + 1, z + k), ((x + j) + 1, (y - size + i + 2), (z + k) + 1)))

            for s in sg:
                yield SelectionBox(s[0], s[1])
        elif self.options.GetSelection() == 4:  # upsidedown pyramid
            x, y, z = self.location_last
            sg = []

            for i in range(size):
                for j in range(-size // 2 + i, size // 2 - i + 1):
                    for k in range(-size // 2 + i, size // 2 - i + 1):
                        if (x + j) in range(x - size // 2, x + size // 2 + 1) and (z + k) in range(z - size // 2,
                                                                                                   z + size // 2 + 1):
                            sg.append(((x + j, y + size - i - 1, z + k), ((x + j) + 1, (y + size - i), (z + k) + 1)))

            for s in sg:
                yield SelectionBox(s[0], s[1])
        elif self.options.GetSelection() == 5:  # Dome
            circle_size = self.int_size.GetValue()
            radius = circle_size // 2
            xx, yy, zz = self.location_last

            # Generate selection boxes for the dome
            for x in range(xx - radius, xx + radius + 1):
                for y in range(yy, yy + radius + 1):  # Iterate only half the height
                    for z in range(zz - radius, zz + radius + 1):
                        # Check if the point is within the dome's surface
                        distance_squared = (x - xx) ** 2 + (y - yy) ** 2 + (z - zz) ** 2
                        if abs(distance_squared - radius ** 2) < radius:
                            # Create a box around the current point
                            min_x = x - 1
                            max_x = x
                            min_y = y - 1
                            max_y = y
                            min_z = z - 1
                            max_z = z
                            yield SelectionBox((min_x, min_y, min_z), (max_x, max_y, max_z))
        elif self.options.GetSelection() == 6:  # Bowl
            circle_size = self.int_size.GetValue()
            radius = circle_size // 2
            xx, yy, zz = self.location_last

            # Generate selection boxes for the upside-down dome
            for x in range(xx - radius, xx + radius + 1):
                for y in range(yy - radius, yy + 1):  # Iterate only half the height, but in reverse
                    for z in range(zz - radius, zz + radius + 1):
                        # Check if the point is within the dome's surface
                        distance_squared = (x - xx) ** 2 + (y - yy) ** 2 + (z - zz) ** 2
                        if abs(distance_squared - radius ** 2) < radius:
                            # Create a box around the current point
                            min_x = x - 1
                            max_x = x
                            min_y = y - 1
                            max_y = y
                            min_z = z - 1
                            max_z = z
                            yield SelectionBox((min_x, min_y, min_z), (max_x, max_y, max_z))

        elif self.options.GetSelection() == 7:  # walls
            length_x = self.int_x.GetValue()
            length_y = self.int_y.GetValue()
            length_z = self.int_z.GetValue()
            middle_area = []
            for x in range(xx, xx + length_x):
                for y in range(yy, yy + length_y):
                    for z in range(zz, zz + length_z):
                        # Skip the top and bottom faces
                        if y == yy or y == yy + length_y - 1:
                            continue
                        # Check if the block is part of the walls with the given thickness
                        if (x < xx + size or x >= xx + length_x - size or
                                z < zz + size or z >= zz + length_z - size):
                            min_x = x
                            max_x = x + 1
                            min_y = y
                            max_y = y + 1
                            min_z = z
                            max_z = z + 1
                            yield SelectionBox((min_x, min_y, min_z), (max_x, max_y, max_z))
                        else:
                            # Collect the interior blocks
                            middle_area.append((x, y, z))

    def _on_pointer_change(self, evt: PointChangeEvent):

        if self._pause_pointer:
            if self._is_enabled or self.click:
                x, y, z = evt.point

                if self.point_evt != (x, y, z):
                    self.point_evt = (x, y, z)
                    if (
                            self.options.GetSelection(), self.int_size.GetValue(), self.int_x.GetValue(),
                            self.int_y.GetValue(),
                            self.int_y.GetValue()) == (self.v1, self.v2, self.v3, self.v4, self.v5):
                        px, py, pz = evt.point
                        lx, ly, lz = self.location_last

                        self.sg = ((((px - lx) + x, (py - ly) + y, (pz - lz) + z),
                                    ((px - lx) + xx, (py - ly) + yy, (pz - lz) + zz))
                                   for ((x, y, z), (xx, yy, zz)) in
                                   ((s._point_1, s._point_2) for s in self.canvas.selection.selection_group))

                        self.canvas.selection.set_selection_corners(self.sg)
                        self.location_last = (px, py, pz)

                    else:
                        self.v1, self.v2, self.v3, self.v4, self.v5 = self.options.GetSelection(), self.int_size.GetValue(), self.int_x.GetValue(), self.int_y.GetValue(), self.int_y.GetValue()
                        self.location_last = evt.point
                        selboxs = self.cusotome_brush(x, y, z)
                        self.sg = SelectionGroup(selboxs)
                        merge = self.sg.merge_boxes()
                        self.canvas.selection.set_selection_group(merge)

                evt.Skip()
        else:
            self.current_point = evt.point
            # print(self.location_last)
            evt.Skip()
        evt.Skip()

    def _refresh_chunk(self, dimension, world, x, z):
        cx, cz = block_coords_to_chunk_coords(x, z)
        if self.world.has_chunk(cx, cz, dimension):
            chunk = self.world.get_chunk(cx, cz, dimension)
            chunk.changed = True

    def mouse_click(self, event):

        blocks = self.canvas.selection.selection_group.merge_boxes().blocks
        if self.location_current != self.location_last:
            self.location_current = self.location_last
            newblock = self._block_define.block
            newEntity = self._block_define.block_entity
            platform = self.world.level_wrapper.platform
            world_version = self.world.level_wrapper.version

            # Place the new block and entity at the selected locations
            for xx, yy, zz in blocks:
                self.world.set_version_block(int(xx), int(yy), int(zz), self.canvas.dimension,
                                             (platform, world_version),
                                             newblock, newEntity)

            # Rebuild the world renderer
            self.canvas.renderer.render_world.rebuild_changed()
        event.Skip()
        # TODO FILL IN THE MIDDLE TO MAKE HOLLOW THIS DONT WORK
        # max_x = self.canvas.selection.selection_group.merge_boxes().max_x
        # max_y = self.canvas.selection.selection_group.merge_boxes().max_y
        # max_z = self.canvas.selection.selection_group.merge_boxes().max_z
        # b1, b2 = self.canvas.selection.selection_group.merge_boxes().bounds
        # xx1,yy1,zz1 = self.canvas.selection.selection_group.merge_boxes().min_array
        # xx2, yy2, zz2 = self.canvas.selection.selection_group.merge_boxes().max_array
        # xx,yy,zz = (xx1+xx2)//2,(yy1+yy2)//2,(zz1+zz2)//2
        # rx,ry,rz = abs(b1[0] - b2[0]), abs(b1[1]) - abs(b2[1]), abs(b1[2]) - abs(b2[2])
        # #outer = abs(max_z) + abs(max_x) + abs(max_y)
        #
        # inner = 3 ** 2 + 1 #rx + ry + rz
        # area = {}
        # # for i, (xx,yy,zz) in enumerate(self.canvas.selection.selection_group.merge_boxes().blocks):
        # for y in range((abs(ry)) +1):
        #     yyy = y ** 2 - 1
        #     for z in range((abs(rz)) + 1):
        #         zzz = z ** 2 - 1
        #         for x in range((abs(rx)) + 1):
        #             xxx = x ** 2 - 1
        #             overall = (abs(xxx) + abs(yyy) + abs(zzz))
        #             # inner = (rx + abs(xx)) + (ry + abs(yy)) +  (rz + abs(zz)) // 3
        #             sel_box = None
        #             # if overall <= inner_size:
        #             if overall <= inner:
        #                 sel_box = "Yes"
        #
        #             if sel_box is not None:
        #                 area[(xx - x, yy + y, zz - z)] = sel_box
        #                 area[(xx - x, yy - y, zz + z)] = sel_box
        #                 area[(xx - x, yy - y, zz - z)] = sel_box
        #                 area[(xx + x, yy + y, zz + z)] = sel_box
        #                 area[(xx + x, yy + y, zz - z)] = sel_box
        #                 area[(xx + x, yy - y, zz + z)] = sel_box
        #                 area[(xx + x, yy - y, zz - z)] = sel_box
        #                 area[(xx - x, yy + y, zz + z)] = sel_box
        #
        # dirt = Block('minecraft', 'air')
        # for (x, y, z), sel_box in area.items():
        #     if sel_box:
        #         self.world.set_version_block(x, y, z, self.canvas.dimension,
        #                    (platform, world_version),
        #                      dirt, None)

        # for p1 in locations:
        #     for p2 in locations:
        #         interpolated = interpolate_points(p1, p2, locations)
        #         for point in interpolated:
        #

        # Fill in all points within the bounding box with dirt blocks, excluding the original selection
        # dirt = Block('minecraft', 'dirt')
        # for x in range(min_x, max_x + 1):
        #     for y in range(min_y, max_y + 1):
        #         for z in range(min_z, max_z + 1):
        #             # Check if the current point is inside the bounding box
        #             if (x, y, z) in locations:
        #                 continue
        #             # Fill in the point with a dirt block
        #             self.world.set_version_block(x, y, z, self.canvas.dimension,
        #                                          (platform, world_version),
        #                                          dirt, None)

    def mouse_tog_on(self, event):
        self.mouse_click(event)
        self.timer.Start(9)
        event.Skip()

    def mouse_tog_off(self, event):
        if self.timer.IsRunning():
            self.timer.Stop()
            self.canvas.run_operation(lambda: self._refresh_chunk(self.canvas.dimension,
                                                                  self.world, self.location_last[0],
                                                                  self.location_last[2]))
        event.Skip()

    def key_down_event(self, evt):
        # print(evt.GetKeyCode())

        if evt.GetKeyCode() == 332 or evt.GetKeyCode() == 315:
            fake_event = wx.CommandEvent(wx.EVT_BUTTON.typeId)
            fake_event.SetEventObject(self._north)
            self._north.ProcessEvent(fake_event)

        if evt.GetKeyCode() == 326 or evt.GetKeyCode() == 317:
            fake_event = wx.CommandEvent(wx.EVT_BUTTON.typeId)
            fake_event.SetEventObject(self._south)
            self._south.ProcessEvent(fake_event)

        if evt.GetKeyCode() == 330 or evt.GetKeyCode() == 316:
            fake_event = wx.CommandEvent(wx.EVT_BUTTON.typeId)
            fake_event.SetEventObject(self._east)
            self._east.ProcessEvent(fake_event)

        if evt.GetKeyCode() == 328 or evt.GetKeyCode() == 314:
            fake_event = wx.CommandEvent(wx.EVT_BUTTON.typeId)
            fake_event.SetEventObject(self._west)
            self._west.ProcessEvent(fake_event)

        if evt.GetKeyCode() == 329 or evt.GetKeyCode() == 305:
            fake_event = wx.CommandEvent(wx.EVT_BUTTON.typeId)
            fake_event.SetEventObject(self._up)
            self._up.ProcessEvent(fake_event)

        if evt.GetKeyCode() == 324 or evt.GetKeyCode() == 384:
            fake_event = wx.CommandEvent(wx.EVT_BUTTON.typeId)
            fake_event.SetEventObject(self._down)
            self._down.ProcessEvent(fake_event)

        if evt.GetKeyCode() == 80:
            self._pause_pointer = not self._pause_pointer

            if self._pause_pointer:
                self._sizer.Hide(self.move_boxs_sizer, recursive=True)
                self._sizer.Layout()
                self.staus_pause_pointer.SetLabelText('Press P To Pause Pointer')
                self.staus_pause_pointer.SetForegroundColour((11, 220, 11))
                try:

                    xx, yy, zz = self.current_point
                    self._on_pointer_change(PointChangeEvent((xx, yy, zz)))
                except:
                    pass
            else:
                self._sizer.Show(self.move_boxs_sizer, recursive=False)
                self._sizer.Layout()

                self.staus_pause_pointer.SetLabelText('Press P To UnPause Pointer')
                self.staus_pause_pointer.SetForegroundColour((220, 111, 11))
        evt.Skip()

    def bind_events(self):

        self.timer = wx.Timer(self.canvas)
        self.canvas.Bind(wx.EVT_KEY_DOWN, self.key_down_event)
        self.canvas.Bind(wx.EVT_LEFT_DOWN, self.mouse_tog_on)
        self.canvas.Bind(wx.EVT_LEFT_UP, self.mouse_tog_off)
        self.canvas.Bind(wx.EVT_TIMER, self.mouse_click, self.timer)
        self.canvas.Bind(EVT_POINT_CHANGE, self._on_pointer_change)

    def on_close(self, event):
        self.canvas.Unbind(wx.EVT_KEY_DOWN, handler=self.key_down_event)
        self.canvas.Unbind(wx.EVT_LEFT_DOWN, handler=self.mouse_tog_on)
        self.canvas.Unbind(wx.EVT_LEFT_UP, handler=self.mouse_tog_off)
        self.canvas.Unbind(wx.EVT_TIMER, handler=self.mouse_click, source=self.timer)
        # self._curs.unbind_events()
        self.canvas.Unbind(EVT_POINT_CHANGE, handler=self._on_pointer_change)
        self.Destroy()

    def location(self) -> PointCoordinates:
        return self._location.value

    def _on_input_press(self, evt: InputPressEvent):
        if self.click == True:
            self._getc()

        evt.Skip()

    def _run_operation(self, _):
        self._is_enabled = False
        self._moving = False
        self.click = False
        self.canvas.Unbind(EVT_POINT_CHANGE)
        self.canvas.Unbind(EVT_INPUT_PRESS)
        data = self._mode_description.GetValue()
        dataxyz = data.split("\n")

        group = []
        for d in dataxyz:
            x, y, z, xx, yy, zz = d.split(",")
            group.append(SelectionBox((int(x), int(y), int(z)), (int(xx), int(yy), int(zz))))
        sel = SelectionGroup(group)
        self.canvas.selection.set_selection_group(sel)

    def _boxUp(self, v):
        def OnClick(event):
            sgs = []

            for box in self.canvas.selection.selection_group.selection_boxes:
                xx, yy, zz = box.max_x, box.max_y, box.max_z
                xm, ym, zm = box.min_x, box.min_y, box.min_z
                sgs.append(SelectionBox((xm, ym + 1, zm), (xx, yy + 1, zz)))

            self.canvas.selection.set_selection_group(SelectionGroup(sgs))

        return OnClick

    def _boxDown(self, v):
        def OnClick(event):
            sgs = []
            for box in self.canvas.selection.selection_group.selection_boxes:
                xx, yy, zz = box.max_x, box.max_y, box.max_z
                xm, ym, zm = box.min_x, box.min_y, box.min_z
                sgs.append(SelectionBox((xm, ym - 1, zm), (xx, yy - 1, zz)))

            self.canvas.selection.set_selection_group(SelectionGroup(sgs))

        return OnClick

    def _boxNorth(self, v):

        def OnClick(event):
            sgs = []
            for box in self.canvas.selection.selection_group.selection_boxes:
                xx, yy, zz = box.max_x, box.max_y, box.max_z
                xm, ym, zm = box.min_x, box.min_y, box.min_z
                sgs.append(SelectionBox((xm, ym, zm - 1), (xx, yy, zz - 1)))

            self.canvas.selection.set_selection_group(SelectionGroup(sgs))

        return OnClick

    def _boxSouth(self, v):
        def OnClick(event):
            sgs = []
            for box in self.canvas.selection.selection_group.selection_boxes:
                xx, yy, zz = box.max_x, box.max_y, box.max_z
                xm, ym, zm = box.min_x, box.min_y, box.min_z
                sgs.append(SelectionBox((xm, ym, zm + 1), (xx, yy, zz + 1)))

            if len(sgs) > 0:
                self.canvas.selection.set_selection_group(SelectionGroup(sgs))

        return OnClick

    def _boxEast(self, v):

        def OnClick(event):
            sgs = []
            for box in self.canvas.selection.selection_group.selection_boxes:
                xx, yy, zz = box.max_x, box.max_y, box.max_z
                xm, ym, zm = box.min_x, box.min_y, box.min_z
                sgs.append(SelectionBox((xm + 1, ym, zm), (xx + 1, yy, zz)))
            self.canvas.selection.set_selection_group(SelectionGroup(sgs))

        return OnClick

    def _boxWest(self, v):
        def OnClick(event):
            sgs = []
            for box in self.canvas.selection.selection_group.selection_boxes:
                xx, yy, zz = box.max_x, box.max_y, box.max_z
                xm, ym, zm = box.min_x, box.min_y, box.min_z
                sgs.append(SelectionBox((xm - 1, ym, zm), (xx - 1, yy, zz)))
            self.canvas.selection.set_selection_group(SelectionGroup(sgs))

        return OnClick

    pass

class MaterialCounter(wx.Frame):
    def __init__(self, parent, canvas, world, *args, **kw):
        super(MaterialCounter, self).__init__(parent, *args, **kw,
                                              style=(wx.MINIMIZE_BOX | wx.MAXIMIZE_BOX | wx.RESIZE_BORDER |
                                                     wx.SYSTEM_MENU | wx.CAPTION | wx.CLOSE_BOX | wx.CLIP_CHILDREN |
                                                     wx.FRAME_FLOAT_ON_PARENT),
                                              title="NBT Editor for Entities")

        self.parent = parent

        self.canvas = canvas
        self.world = world
        self.platform = self.world.level_wrapper.platform
        self.font = wx.Font(13, wx.FONTFAMILY_ROMAN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        self.SetForegroundColour((0, 255, 0))
        self.SetBackgroundColour((0, 0, 0))
        self.SetFont(self.font)
        self.SetMinSize((520, 720))
        self._sizer = wx.BoxSizer(wx.VERTICAL)
        self.text = wx.TextCtrl(self, style=wx.TE_MULTILINE, size=(280, 650), pos=(30, 30))
        self.test = wx.Button(self, label="Get Materials count", pos=(0, 0))
        self.text.SetForegroundColour((0, 255, 0))
        self.text.SetBackgroundColour((0, 0, 0))
        self.text.SetFont(self.font)
        self.test.Bind(wx.EVT_BUTTON, self._run_count)
        self._sizer.Add(self.test)
        self._sizer.Add(self.text)

    def _run_count(self, _):

        block_version = self.world.level_wrapper.version

        block_platform = "universal"

        matrials = collections.defaultdict(list)
        selection = self.canvas.selection.selection_group.selection_boxes
        text = ''

        for g in selection:
            for b in g:
                name, ent = self.world.get_version_block(b[0], b[1], b[2], self.canvas.dimension,
                                                         (block_platform, block_version))
                clean_name = str(name.properties.get('material')).replace('None', '')
                clean_name += str(name.properties.get('plant_type')).replace('None', '')
                if clean_name != '':
                    clean_name += ' '
                clean_name += name.base_name
                matrials[clean_name].append(clean_name)
        for x in matrials.keys():
            text += str(x) + " " + str(len(matrials[x])) + "\n"

        self.text.SetValue(text)

class ExportImportCostomDialog(wx.Dialog):

    def __init__(self, *args, **kw):
        super(ExportImportCostomDialog, self).__init__(*args, **kw)
        self.InitUI()
        self.SetSize(500, 180)

    def InitUI(self, *ar):
        if len(ar) > 0:
            print(ar)
            if ar[0] == 1:
                self.Export()
            if ar[0] == 2:
                self.Import()

    def Export(self):
        self.SetTitle("Export")
        panel = wx.Panel(self)
        vert_box = wx.BoxSizer(wx.VERTICAL)
        static_box = wx.StaticBox(panel)
        static_box_sizer = wx.StaticBoxSizer(static_box, orient=wx.VERTICAL)
        static_box.SetLabel('Select Export Type:')
        image = wx.ArtProvider.GetBitmap(wx.ART_QUESTION)
        image_placer = wx.BoxSizer(wx.HORIZONTAL)
        self.bitmap = wx.StaticBitmap(self, -1, image, pos=(200, 20))
        image_placer.Add(self.bitmap)
        self.selected_chunks = wx.RadioButton(panel, label='Selected Chunks .snbt list')
        self.all_chunks = wx.RadioButton(panel, label='ALL Chunks .snbt list')
        self.nbt_file_option = wx.RadioButton(panel, label='NBT Structure File')
        self.all_entities_nbt = wx.RadioButton(panel, label='ALL Entities NBT ')
        static_box_sizer.Add(self.selected_chunks)
        static_box_sizer.Add(self.all_chunks)
        static_box_sizer.Add(self.nbt_file_option)
        static_box_sizer.Add(self.all_entities_nbt)
        panel.SetSizer(static_box_sizer)
        hor_box = wx.BoxSizer(wx.HORIZONTAL)
        self.okButton = wx.Button(self)
        self.selected_chunks.Bind(wx.EVT_RADIOBUTTON, self.setbuttonEL)
        self.all_chunks.Bind(wx.EVT_RADIOBUTTON, self.setbuttonEL)
        self.nbt_file_option.Bind(wx.EVT_RADIOBUTTON, self.setbuttonEL)
        self.all_entities_nbt.Bind(wx.EVT_RADIOBUTTON, self.setbuttonEL)
        closeButton = wx.Button(self, label='Cancel')
        hor_box.Add(self.okButton)
        hor_box.Add(closeButton, flag=wx.LEFT, border=5)
        vert_box.Add(panel, proportion=1, flag=wx.ALL | wx.EXPAND, border=5)
        vert_box.Add(hor_box, flag=wx.ALIGN_CENTER | wx.TOP | wx.BOTTOM, border=10)
        self.SetSizer(vert_box)
        self.okButton.Bind(wx.EVT_BUTTON, self.OnClose)
        closeButton.Bind(wx.EVT_BUTTON, self.OnCancelEX)
        self.Bind(wx.EVT_CLOSE, self.OnCancelEX)

    def setbuttonEL(self, e):
        if self.selected_chunks.GetValue():
            self.okButton.SetLabel(self.selected_chunks.GetLabel())
        if self.all_chunks.GetValue():
            self.okButton.SetLabel(self.all_chunks.GetLabel())
        if self.nbt_file_option.GetValue():
            self.okButton.SetLabel(self.nbt_file_option.GetLabel())
        if self.all_entities_nbt.GetValue():
            self.okButton.SetLabel(self.all_entities_nbt.GetLabel())

    def Import(self):
        self.SetTitle("Import")

        panel = wx.Panel(self)
        vert_box = wx.BoxSizer(wx.VERTICAL)
        static_box = wx.StaticBox(panel)
        static_box.SetLabel('Select Import Type:')
        static_box_sizer = wx.StaticBoxSizer(static_box, orient=wx.VERTICAL)
        image = wx.ArtProvider.GetBitmap(wx.ART_QUESTION)
        image_placer = wx.BoxSizer(wx.HORIZONTAL)
        self.bitmap = wx.StaticBitmap(self, -1, image, pos=(200, 20))
        image_placer.Add(self.bitmap)
        self.list = wx.RadioButton(panel, label='A Entitie .snbt list to world')
        self.nbt_file = wx.RadioButton(panel, label='NBT Structure File')
        self.ms_file = wx.RadioButton(panel, label='Open and Add Entities to MCStructure File')
        self.ms_file.SetToolTip("This Will go the the location where created and pull the Entities from where they are,"
                                "NOTE:  They wont get added if they are not there")
        static_box_sizer.Add(self.list)
        static_box_sizer.Add(self.nbt_file)
        static_box_sizer.Add(self.ms_file)
        panel.SetSizer(static_box_sizer)
        hor_box = wx.BoxSizer(wx.HORIZONTAL)
        self.okButton = wx.Button(self)
        self.list.Bind(wx.EVT_RADIOBUTTON, self.setbuttonIM)
        self.nbt_file.Bind(wx.EVT_RADIOBUTTON, self.setbuttonIM)
        self.ms_file.Bind(wx.EVT_RADIOBUTTON, self.setbuttonIM)
        closeButton = wx.Button(self, label='Cancel')
        hor_box.Add(self.okButton, flag=wx.TOP)
        hor_box.Add(closeButton, flag=wx.LEFT, border=5)
        vert_box.Add(panel, proportion=1, flag=wx.ALL | wx.EXPAND, border=5)
        vert_box.Add(hor_box, flag=wx.ALIGN_CENTER | wx.TOP | wx.BOTTOM, border=10)
        self.SetSizer(vert_box)
        self.okButton.Bind(wx.EVT_BUTTON, self.OnClose)
        closeButton.Bind(wx.EVT_BUTTON, self.OnCancelIM)
        self.Bind(wx.EVT_CLOSE, self.OnCancelIM)

    def setbuttonIM(self, e):
        if self.list.GetValue():
            self.okButton.SetLabel(self.list.GetLabel())
            self.okButton.SetSize(200, 23)
            self.okButton.SetPosition(pt=(15, 87))
        if self.nbt_file.GetValue():
            self.okButton.SetSize(200, 23)
            self.okButton.SetPosition(pt=(15, 87))
            self.okButton.SetLabel(self.nbt_file.GetLabel())
        if self.ms_file.GetValue():
            self.okButton.SetSize(250, 23)
            self.okButton.SetPosition(pt=(15, 87))
            self.okButton.SetLabel(self.ms_file.GetLabel())

    def OnClose(self, e):
        self.Destroy()

    def OnCancelIM(self, e):
        self.ms_file.SetValue(False)
        self.nbt_file.SetValue(False)
        self.list.SetValue(False)
        self.Destroy()

    def OnCancelEX(self, e):
        self.selected_chunks.SetValue(False)
        self.all_chunks.SetValue(False)
        self.nbt_file_option.SetValue(False)
        self.all_entities_nbt.SetValue(False)
        self.Destroy()

class BedRock(wx.Panel):
    def __int__(self, world, canvas):
        wx.Panel.__init__(self, parent)
        self.world = world
        self.canvas = canvas
        self.actors =  collections.defaultdict(list)
        self.digp = collections.defaultdict(list)

    def get_raw_data_new_version(self, is_export=False, all_enty=False):

        self.get_all_flag = all_enty
        self.EntyData = []
        self.Key_tracker = []
        self.lstOfE = []
        select_chunks = self.canvas.selection.selection_group.chunk_locations()  # selection_group.chunk_locations()
        all_chunks = [x for x in self.world.level_wrapper.all_chunk_coords(self.canvas.dimension)]
        dim = struct.unpack("<i", self.get_dim_value())[0]
        exclude_filter = self.exclude_filter.GetValue().split(",")
        include_filter = self.include_filter.GetValue().split(",")
        if all_enty:
            self.canvas.selection.set_selection_group(SelectionGroup([]))
        if self.canvas.selection.selection_group:
            search_chunks = select_chunks
        else:
            search_chunks = all_chunks
        for xc, zc in search_chunks:
            key = (xc, zc, dim)
            if self.digp.get(key, None):
                for x in self.digp.get(key):
                    if self.actors.get(x, None):

                        for raw in self.actors.get(x):
                            try:
                                nbt_ = self.nbt_loder(raw)
                            except:
                                nbt_ = from_snbt(raw)
                            # print(nbt_)
                            try:
                                name = str(nbt_['identifier']).replace("minecraft:", "")
                            except:
                                name = "unknown"
                            custom_name = ''
                            if nbt_.get("CustomName"):
                                custom_name = str(nbt_['CustomName'])
                            print(custom_name)

                            if exclude_filter != [''] or include_filter != ['']:
                                if name not in exclude_filter and exclude_filter != ['']:
                                    self.lstOfE.append(name + ":" + custom_name)
                                    self.EntyData.append(nbt_.to_snbt(1))
                                    self.Key_tracker.append(x)
                                for f in include_filter:
                                    if f in name:
                                        self.lstOfE.append(name + ":" + custom_name)
                                        self.EntyData.append(nbt_.to_snbt(1))
                                        self.Key_tracker.append(x)
                            else:
                                self.lstOfE.append(name + ":" + custom_name)
                                self.EntyData.append(nbt_.to_snbt(1))
                                self.Key_tracker.append(x)
        if is_export:

            return self.EntyData
        if len(self.EntyData) > 0:
            zipped_lists = zip(self.lstOfE, self.EntyData, self.Key_tracker)
            sorted_pairs = sorted(zipped_lists)
            tuples = zip(*sorted_pairs)
            self.lstOfE, self.EntyData, self.Key_tracker = [list(tuple) for tuple in tuples]

        if len(self.lstOfE) == 0:
            EntitiePlugin.Onmsgbox(self, "No Entities", "No Entities were found within the selecton")
        else:
            return self.EntyData, self.lstOfE

    def delete_un_or_selected_entities(self, event, unseleted):
        res = EntitiePlugin.important_question(self)
        if res == False:
            return
        selection = self.canvas.selection.selection_group
        try:
            chunks = selection.chunk_locations()
            for c in chunks:
                self.world.get_chunk(c[0], c[1], self.canvas.dimension)
        except ChunkDoesNotExist:
            responce = EntitiePlugin.con_boc(self, "Chuck Error", "Empty chunk selected, \n Continue any Ways?")
            if responce:
                print("Exiting")
                return
            else:
                pass
        if "[((0, 0, 0), (0, 0, 0))]" == str(selection):
            responce = EntitiePlugin.con_boc(self, "No selection",
                                             "All Entities will be deleted in " + str(
                                                 self.canvas.dimension) + " \n Continue?")
            if responce:
                print("Exiting")
                return
        sel_res_text = ''
        if unseleted:
            all_chunks = [x for x in self.world.level_wrapper.all_chunk_coords(self.canvas.dimension)]
            selected = self.canvas.selection.selection_group.chunk_locations()
            sel_res_text = "Unselected"
        else:  # Combine Two functions into one
            all_chunks = self.canvas.selection.selection_group.chunk_locations()
            selected = []
            sel_res_text = "Selected"
        if self.world.level_wrapper.version >= (1, 18, 30, 4, 0):
            self._load_entitie_data(event, False, True)
            prefixList = []
            tempPreKe = []
            d = b''
            pdig_to_delete = []
            for ch in all_chunks:
                if ch not in selected:
                    cx, cz = ch[0].to_bytes(4, 'little', signed=True), ch[1].to_bytes(4, 'little', signed=True)
                    if 'minecraft:the_end' in self.canvas.dimension:
                        d = int(2).to_bytes(4, 'little', signed=True)
                    elif 'minecraft:the_nether' in self.canvas.dimension:
                        d = int(1).to_bytes(4, 'little', signed=True)
                    key = b'digp' + cx + cz + d  # build the digp key for the chunk
                    try:
                        if self.level_db.get(key):
                            data = self.level_db.get(key)
                            for CntB in range(0, len(data), 8):  # the actorprefix keys are every 8 bytes , build a list
                                prefixList.append(b'actorprefix' + data[CntB:CntB + 8])
                            pdig_to_delete.append(key)
                    except KeyError as e:
                        print("keyerror")

            for pkey in prefixList:
                self.level_db.delete(pkey)
            for pdig_d in pdig_to_delete:
                self.level_db.delete(pdig_d)
        else:
            for x, z in all_chunks:
                if (x, z) not in selected:
                    raw = self.world.level_wrapper.get_raw_chunk_data(x, z, self.canvas.dimension)
                    raw[b'2'] = b''
                    self.world.level_wrapper.put_raw_chunk_data(x, z, raw, self.canvas.dimension)

        self.world.save()
        self._set_list_of_actors_digp
        self._load_entitie_data(event, False, False)
        EntitiePlugin.Onmsgbox(self, "Deleted ", f"Entities from {sel_res_text}")

    def _export_ALL_nbt(self, _):
        wx.MessageBox("Coming Soon", "Remind me", wx.OK | wx.ICON_INFORMATION)

    def _exp_entitie_data(self, _):
        dlg = ExportImportCostomDialog(None)
        dlg.InitUI(1)
        res = dlg.ShowModal()
        if dlg.selected_chunks.GetValue():
            select_chunks = self.canvas.selection.selection_group.chunk_locations()
        elif dlg.all_chunks.GetValue():
            select_chunks = [x for x in self.world.level_wrapper.all_chunk_coords(self.canvas.dimension)]
        elif dlg.all_entities_nbt.GetValue():
            self._export_ALL_nbt(_)
            return
        elif dlg.nbt_file_option.GetValue():
            self._export_nbt(_)
            return
        else:
            return

        snbt_list = b''
        world = self.world
        dimension = self.canvas.dimension
        selection = self.canvas.selection.selection_group
        snbt_line_list = ""
        dim = struct.unpack("<i", self.get_dim_value())[0]
        if self.world.level_wrapper.version >= (1, 18, 30, 4, 0):
            if self.canvas.selection.selection_group.selection_boxes == ():
                responce = EntitiePlugin.con_boc(self, "Backup: ",
                                                 "No selection, This will back up all Entities within this Dim:\n"
                                                 + self.canvas.dimension)
                if responce:
                    return

            else:
                responce = EntitiePlugin.con_boc(self, "Backup",
                                                 ",This will back up all Entities within this selection/s >" + str(
                                                     self.canvas.selection.selection_group))
                if responce == True:
                    return
            listOfent = self.get_raw_data_new_version(True)
            if len(listOfent) > 0:

                for data in listOfent:
                    format = from_snbt(data)
                    snbt_line_list += format.to_snbt() + "\n"
                responce = EntitiePlugin.save_entities_export(self, snbt_line_list)
                if responce == True:
                    EntitiePlugin.Onmsgbox(self, "Export Complete", "No Erros were detected")
                else:
                    EntitiePlugin.Onmsgbox(self, "Cancel", "Canceled or something went wrong")
                return
        else:
            ent = {}
            chunks = select_chunks
            byteCount = 0
            snbb = []
            self.EntyData.clear()
            for count, (cx, cz) in enumerate(chunks):
                chunk = self.world.level_wrapper.get_raw_chunk_data(cx, cz, self.canvas.dimension)
                if chunk.get(b'2'):
                    max = len(chunk[b'2'])
                    pointer = 0
                    while pointer < max:
                        EntyD, p = load(chunk[b'2'][pointer:], little_endian=True, offset=True)
                        pointer += p
                        self.EntyData.append(EntyD)

            if len(self.EntyData) > 0:
                for elist in self.EntyData:
                    snbt_line_list += elist.to_snbt() + "\n"

        res = EntitiePlugin.save_entities_export(self, snbt_line_list)
        if res == False:
            return
        EntitiePlugin.Onmsgbox(self, "Export", "Saved")

    def _export_nbt(self, _):
        entities = ListTag([])
        blocks = ListTag([])
        palette = ListTag([])
        DataVersion = IntTag(2975)
        selection = self.canvas.selection.selection_group.to_box()
        pallet_key_map = collections.defaultdict(list)
        nbt_state_map = collections.defaultdict(list)
        indx = 0
        sx, sy, sz = 0, 0, 0

        mx, my, mz = self.canvas.selection.selection_group.to_box().shape
        block_pos = []
        reps = EntitiePlugin.con_boc(self, "Air Blocks", 'Do you want to encude air block?')
        # bl = np.zeros(shape, dtype=numpy.uint32)
        for x in range(0, (mx)):
            for y in range(0, (my)):
                for z in range(0, (mz)):
                    block_pos.append((x, y, z))
        entities = self.get_entities_nbt(block_pos)
        prg_max = len(block_pos)
        prg_pre = 0
        prg_pre_th = len(block_pos) / 100
        self.prog = wx.ProgressDialog("Saving blocks", str(0) + " of " + str(prg_max),
                                      style=wx.PD_AUTO_HIDE | wx.PD_CAN_ABORT | wx.PD_ELAPSED_TIME | wx.PD_REMAINING_TIME)
        self.prog.Show(True)
        for i, (s, b) in enumerate(zip(selection, block_pos)):
            if self.prog.WasCancelled():
                self.prog.Hide()
                self.prog.Destroy()
                break
            if i >= prg_pre_th:
                prg_pre_th += len(block_pos) / 100
                prg_pre += 1
                self.prog.Update(prg_pre, "Saving blocks " + str(i) + " of " + str(prg_max))
            block, blockEntity = self.world.get_version_block(s[0], s[1], s[2], self.canvas.dimension,
                                                              ("java", (1, 18, 0)))

            if not reps:
                check_string = ""
            else:
                check_string = 'minecraft:air'
            if str(block) != check_string:
                if pallet_key_map.get((block.namespaced_name, str(block.properties))) == None:
                    pallet_key_map[(block.namespaced_name, str(block.properties))] = indx
                    indx += 1
                    palette_Properties = CompoundTag(
                        {'Properties': CompoundTag(block.properties),
                         'Name': StringTag(block.namespaced_name)})
                    palette.append(palette_Properties)
                state = pallet_key_map[(block.namespaced_name, str(block.properties))]

                if blockEntity == None:
                    blocks_pos = CompoundTag({'pos': ListTag(
                        [IntTag(b[0]), IntTag(b[1]),
                         IntTag(b[2])]), 'state': IntTag(state)})
                    blocks.append(blocks_pos)
                else:
                    blocks_pos = CompoundTag({'nbt': from_snbt(blockEntity.to_snbt()),
                                              'pos': ListTag(
                                                  [IntTag(b[0]),
                                                   IntTag(b[1]),
                                                   IntTag(b[2])]),
                                              'state': IntTag(state)})
                    blocks.append(blocks_pos)
        prg_pre = 99
        self.prog.Update(prg_pre, "Finishing Up " + str(i) + " of " + str(prg_max))
        size = ListTag([IntTag(mx), IntTag(my), IntTag(mz)])

        save_it = CompoundTag({})
        save_it['size'] = size
        save_it['entities'] = entities
        save_it['blocks'] = blocks
        save_it['palette'] = palette
        save_it['DataVersion'] = DataVersion
        raw_data = save_it.save_to(compressed=True, little_endian=False)
        prg_pre = 100
        self.prog.Update(prg_pre, "Done")
        pathto = ""
        fdlg = wx.FileDialog(self, "Save As .nbt", "", "", "nbt files(*.nbt)|*.*", wx.FD_SAVE)
        if fdlg.ShowModal() == wx.ID_OK:
            pathto = fdlg.GetPath()
        else:
            return False
        if ".nbt" not in pathto:
            pathto = pathto + ".nbt"
        with open(pathto, "wb") as tfile:
            tfile.write(raw_data)
            tfile.close()
        wx.MessageBox("Save Complete", "No Issues", wx.OK | wx.ICON_INFORMATION)

    def _import_nbt(self, _):

        fdlg = wx.FileDialog(self, "Load .nbt File", "", "", "nbt files(*.nbt)|*.*", wx.FD_OPEN)
        the_id = fdlg.ShowModal()
        if int(the_id) == 5101:
            return False
        if the_id == wx.ID_OK:
            pathto = fdlg.GetPath()
            nbt_ = load(pathto, compressed=True, little_endian=False,string_decoder=utf8_escape_decoder ).compound
            block_platform = "java"
            block_version = (1, 18, 0)
            b_pos = []
            palette = []
            Name = []
            enbt_ = []
            xx = self.canvas.selection.selection_group.min_x
            yy = self.canvas.selection.selection_group.min_y
            zz = self.canvas.selection.selection_group.min_z
            if True:
                reps = EntitiePlugin.con_boc(self, "Air Blocks", 'Do you want to encude air block?')
                for x in nbt_.get('blocks'):
                    if x['palette'][int(x.get('state'))].get('Properties') != None:
                        palette.append(
                            dict(from_snbt(nbt['palette'][int(x.get('state'))]['Properties'].to_snbt())))
                    else:
                        palette.append(None)
                    b_pos.append(x.get('pos'))
                    Name.append(nbt['palette'][int(x.get('state'))]['Name'])
                    if x.get('nbt') != None:
                        name = str(nbt['palette'][int(x.get('state'))]['Name']).split(':')

                        blockEntity = BlockEntity(name[0], name[1].replace('_', '').capitalize(), 0, 0, 0,
                                                  amulet_NBTFile(x.get('nbt')))
                        eappend(blockEntity)
                    else:
                        eappend(None)
                if not reps:
                    check_string = ""
                else:
                    check_string = 'minecraft:air'
                for x in zip(b_pos, palette, Name, enbt):
                    if x[1] != check_string:
                        block = Block(str(x[2]).split(':')[0], str(x[2]).split(':')[1], x[1])
                        self.world.set_version_block(xx + x[0][0], yy + x[0][1], zz + x[0][2], self.canvas.dimension,
                                                     (block_platform, block_version), block, x[3])
                self.canvas.run_operation(lambda: self._refresh_chunk_now(self.canvas.dimension, self.world, xx, zz))
                dialog = wx.MessageDialog(self, "Including entities directly edits the world and there is no Undo."
                                                "\n Would you like to save changes or discard them,"
                                                "\n Both option will remove all current undo points\n"
                                                "What do you wish to do?", "NOTICE",
                                          wx.ICON_EXCLAMATION | wx.YES_NO | wx.CANCEL | wx.CANCEL_DEFAULT)
                dialog.SetYesNoLabels('Save changes', 'Discard changes')
                responce = dialog.ShowModal()
                dialog.Destroy()
                if responce == wx.ID_YES:
                    self.world.save()
                    self.world.purge()
                    pass
                elif responce == wx.ID_NO:
                    self.world.purge()
                    pass
                else:
                    return
                e_nbt_list = []
                for x in get('entities'):
                    if str(x) != '':
                        e_nbt_ = x.get('nbt')
                        nxx, nyy, nzz = x.get('pos').value
                        if 'Float' in str(type(nxx)):
                            x['nbt']['Pos'] = ListTag([FloatTag(float(nxx + xx)),
                                                               FloatTag(float(nyy + yy)),
                                                               FloatTag(float(nzz + zz))])
                        if 'Double' in str(type(nxx)):
                            x['nbt']['Pos'] = ListTag([amulet_TAG_Double(float(nxx + xx)),
                                                               amulet_TAG_Double(float(nyy + yy)),
                                                               amulet_TAG_Double(float(nzz + zz))])
                        e_nbt_list.append(x['nbt'])
                self.set_entities_nbt(e_nbt_list)

    def _refresh_chunk_now(self, dimension, world, x, z):
        cx, cz = block_coords_to_chunk_coords(x, z)
        chunk = world.get_chunk(cx, cz, dimension)
        chunk.changed = True

    def get_dim_value_bytes(self):
        if 'minecraft:the_end' in self.canvas.dimension:
            dim = int(2).to_bytes(4, 'little', signed=True)
        elif 'minecraft:the_nether' in self.canvas.dimension:
            dim = int(1).to_bytes(4, 'little', signed=True)
        elif 'minecraft:overworld' in self.canvas.dimension:
            dim = b''  # int(0).to_bytes(4, 'little', signed=True)
        return dim

    def get_entities_nbt(self, rpos):
        mapdic = collections.defaultdict()

        entities = ListTag([])
        selection = self.canvas.selection.selection_group.to_box()
        for o, n in zip(selection, rpos):
            mapdic[o] = n
        chunk_min, chunk_max = self.canvas.selection.selection_group.min, \
            self.canvas.selection.selection_group.max
        min_chunk_cords, max_chunk_cords = block_coords_to_chunk_coords(chunk_min[0], chunk_min[2]), \
            block_coords_to_chunk_coords(chunk_max[0], chunk_max[2])
        if self.world.level_wrapper.platform == "bedrock":
            print("ok")
            if self.world.level_wrapper.version >= (1, 18, 30, 4, 0):

                actorprefixs = iter(self.level_db.iterate(start=b'actorprefix',
                                                          end=b'actorprefix\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF'))
                t_start = struct.pack('<ii', min_chunk_cords[0], min_chunk_cords[1])
                t_end = struct.pack('<ii', max_chunk_cords[0], max_chunk_cords[1])
                start = b''.join([b'digp', t_start, self.get_dim_value_bytes()])
                end = b''.join([b'digp', t_end, self.get_dim_value_bytes()])
                for digps_key, digps_val in self.level_db.iterate(start=start, end=end):
                    for x in range(0, len(digps_val), 8):
                        key = b''.join([b'actorprefix', digps_val[x:x + 8]])
                        actor = self.level_db.get(key). \
                            replace(b'\x08\n\x00StorageKey\x08\x00', b'\x07\n\x00StorageKey\x08\x00\x00\x00')
                        nbt_data = load(actor, compressed=False, little_endian=True, string_decoder=utf8_escape_decoder)

                        # print(nbt_data)
                        pos = nbt_data.get("Pos")
                        print(pos)
                        x, y, z = math.floor(pos[0]), math.floor(pos[1]), math.floor(pos[2])

                        if (x, y, z) in selection:
                            # nbt_entitie = ListTag()
                            new_pos = mapdic[(x, y, z)]
                            nbt_pos = ListTag(
                                [FloatTag(sum([new_pos[0],
                                                       math.modf(abs(nbt_data.get("Pos")[0].value))[0]])),
                                 FloatTag(sum([new_pos[1],
                                                       math.modf(abs(nbt_data.get("Pos")[1].value))[0]])),
                                 FloatTag(sum([new_pos[2],
                                                       math.modf(abs(nbt_data.get("Pos")[2].value))[0]]))])

                            nbt_block_pos = ListTag([IntTag(new_pos[0]),
                                                             IntTag(new_pos[1]),
                                                             IntTag(new_pos[2])])
                            # nbt_data.pop('internalComponents')
                            nbt_data.pop('UniqueID')
                            nbt_nbt = from_snbt(nbt_data.to_snbt())
                            main_entry = CompoundTag()
                            main_entry['nbt'] = nbt_nbt
                            main_entry['blockPos'] = nbt_block_pos
                            main_entry['pos'] = nbt_pos
                            entities.append(main_entry)
                return entities

            elif self.world.level_wrapper.version < (1, 18, 30, 4, 0):
                print("<1.18")
                # entitie = ListTag([])
                for cx, cz in self.canvas.selection.selection_group.chunk_locations():
                    chunk = self.world.level_wrapper.get_raw_chunk_data(cx, cz, self.canvas.dimension)
                    if chunk.get(b'2') != None:
                        max = len(chunk[b'2'])
                        cp = 0

                        while cp < max:
                            nbt_data, p = amulet_load(chunk[b'2'][cp:], little_endian=True, offset=True)
                            cp += p
                            pos = nbt_data.get("Pos")
                            print(nbt_data.get('identifier'), selection.blocks)
                            x, y, z = math.floor(pos[0]), math.floor(pos[1]), math.floor(pos[2])
                            print((x, y, z) in selection)
                            if (x, y, z) in selection:
                                new_pos = mapdic[(x, y, z)]
                                nbt_pos = ListTag(
                                    [FloatTag(sum([new_pos[0],
                                                           math.modf(abs(nbt_data.get("Pos")[0].value))[0]])),
                                     FloatTag(sum([new_pos[1],
                                                           math.modf(abs(nbt_data.get("Pos")[1].value))[0]])),
                                     FloatTag(sum([new_pos[2],
                                                           math.modf(abs(nbt_data.get("Pos")[2].value))[0]]))])
                                nbt_block_pos = ListTag([IntTag(new_pos[0]),
                                                                 IntTag(new_pos[1]),
                                                                 IntTag(new_pos[2])])
                                # nbt_data.pop('internalComponents')
                                # nbt_data.pop('UniqueID')
                                nbt_nbt_ = from_snbt(nbt_data.to_snbt())
                                main_entry = CompoundTag()
                                main_entry['nbt'] = nbt_nbt
                                main_entry['blockPos'] = nbt_block_pos
                                main_entry['pos'] = nbt_pos
                                entities.append(main_entry)
                return entities
            else:
                print("no data")

    def set_entities_nbt(self, entities_list):
        entcnt = 0
        if self.world.level_wrapper.platform == "bedrock":
            if self.world.level_wrapper.version >= (1, 18, 30, 4, 0):
                for x in entities_list:
                    xc, zc = block_coords_to_chunk_coords(x.get('Pos')[0], x.get('Pos')[2])

                    world_count = int(str(self.world.level_wrapper.root_tag.get('worldStartCount')).replace('L', ''))
                    start_count = 4294967295 - world_count
                    entcnt += 1
                    actorKey = struct.pack('>LL', start_count, entcnt)
                    put_key = b''.join([b'actorprefix', actorKey])

                    digp = b''.join([b'digp', struct.pack('<ii', xc, zc), self.get_dim_value_bytes()])
                    # try:
                    #     # print(self.level_db.get(digp))
                    #     new_digp = self.level_db.get(digp)
                    #     # print(self.level_db.get(digp))
                    # except:
                    #     new_digp = b''
                    # try:
                    #     new_actor = self.level_db.get(put_key)
                    # except:
                    #     new_actor = b''
                    # new_digp += actorKey
                    new_actor += x.save_to(compressed=False, little_endian=True)

                    self.level_db.put(put_key, new_actor)
                    self.level_db.put(digp, new_digp)

            elif self.world.level_wrapper.version < (1, 18, 30, 4, 0):
                for x in entities_list:
                    xc, zc = block_coords_to_chunk_coords(x.get('Pos')[0], x.get('Pos')[2])
                    chunk = self.world.level_wrapper.get_raw_chunk_data(xc, zc, self.canvas.dimension)
                    try:
                        chunk[b'2'] +=  CompoundTag(x).save_to(little_endian=True, compressed=False,
                                                               string_encoder=utf8_escape_encoder())
                    except:
                        chunk[b'2'] = x.save_to(little_endian=True, compressed=False,
                                                string_encoder=utf8_escape_encoder())
                    self.world.level_wrapper.put_raw_chunk_data(xc, zc, chunk, self.canvas.dimension)
                    self.world.level_wrapper.save()

        self.world.save()

    def _imp_entitie_data(self, _):
        dlg = ExportImportCostomDialog(None)
        dlg.InitUI(2)
        res = dlg.ShowModal()
        # self._set_list_of_actors_digp
        if dlg.ms_file.GetValue():
            fdlg = wx.FileDialog(self, "export Entities", "", "",
                                 f"SNBT (*.snbt_{self.world.level_wrapper.platform})|*.*", wx.FD_OPEN)
            if fdlg.ShowModal() == wx.ID_OK:
                pathto = fdlg.GetPath()
            else:
                return
            anbt = amulet_load(pathto, compressed=False, little_endian=True)
            sx, sy, sz = aget("structure_world_origin")
            egx, egy, egz = aget("size")
            ex, ey, ez = sx + egx, sy + egy, sz + egz
            group = []
            self.canvas.camera.set_location((sx, 70, sz))
            self.canvas.camera._notify_moved()
            s, e = (int(sx), int(sy), int(sz)), (int(ex), int(ey), int(ez))
            group.append(SelectionBox(s, e))
            sel_grp = SelectionGroup(group)
            self.canvas.selection.set_selection_group(sel_grp)
            actors = self.actors
            for xx in self.canvas.selection.selection_group.blocks:
                for nbtlist in actors.values():
                    for anbt in nbtlist:
                        nbtd = amulet_load(anbt, compressed=False, little_endian=True)
                        x, y, z = nbtd.get('Pos').value
                        ex, ey, ez = math.floor(x), math.floor(y), math.floor(z)
                        if (ex, ey, ez) == xx:
                            # print(ex,ey,ez, nbtd.value)
                            anbt['structure']['entities'].append(nbtd.value)
            # nbt_file = amulet_NBTFile(anbt)
            asave_to(pathto, compressed=False, little_endian=True)
            EntitiePlugin.Onmsgbox(self, "Entities Added To Structure File", "Complete")
            return
        elif dlg.nbt_file.GetValue():
            try:
                re = self._import_nbt(_)
                if re == False:
                    return
            except ValueError as e:
                EntitiePlugin.Onmsgbox(self, "No Selection", "You Need to make a selection to set starting point. ")
                return
            EntitiePlugin.Onmsgbox(self, "NBT Import", "Complete")

        elif dlg.list.GetValue():
            res = EntitiePlugin.important_question(self)
            if res == False:
                return
            snbt_loaded_list = EntitiePlugin.load_entities_export(self)
            chunk_dict = collections.defaultdict(list)
            NewRawB = b''

            if self.world.level_wrapper.version >= (1, 18, 30, 4, 0):
                ent_cnt = 2
                print("Importing...")
                self._set_list_of_actors_digp
                xxxx = 0
                for snbt_line in snbt_loaded_list:
                    print(xxxx)
                    xxxx += 1
                    nbt_from_snbt = from_snbt(snbt_line)
                    cx, cz = block_coords_to_chunk_coords(nbt_from_snbt.get('Pos')[0], nbt_from_snbt.get('Pos')[2])
                    chunk_dict[(cx, cz)].append(nbt_from_snbt)

                d = 0
                for lk_data in chunk_dict.keys():

                    key = self.build_digp_chunk_key(lk_data[0], lk_data[1])  # build the digp key for the chunk
                    dig_p_dic = {}
                    dig_byte_list = b''

                    for ent_data in chunk_dict[lk_data]:
                        new_prefix = self.build_actor_key(1, ent_cnt)
                        ent_cnt += 1
                        ent_data["UniqueID"] = self._genorate_uid(ent_cnt)
                        try:
                            print(ByteArrayTag(bytearray(new_prefix[len(b'actorprefix'):])),
                                  "___________________________________")
                            ent_data['internalComponents']['EntityStorageKeyComponent']['StorageKey'] = \
                                ByteArrayTag(bytearray(new_prefix[len(b'actorprefix'):]))
                        except:
                            pass
                        dig_byte_list += new_prefix[len(b'actorprefix'):]
                        final_data = ent_data.save_to(compressed=False, little_endian=True).replace(
                            b'\x07\n\x00StorageKey\x08\x00\x00\x00', b'\x08\n\x00StorageKey\x08\x00')
                        # print(new_prefix, final_data)
                        self.level_db.put(new_prefix, final_data)
                        print(new_prefix, "New")
                    self.level_db.put(key, dig_byte_list)


            else:
                cnt = 0
                for snbt in snbt_loaded_list:
                    nbt_from_snbt_ = from_snbt(snbt)
                    cx, cz = block_coords_to_chunk_coords(nbt_from_snbt_.get('Pos')[0], nbt_from_snbt_.get('Pos')[2])
                    chunk_dict[(cx, cz)].append(nbt_from_snbt)
                for k in chunk_dict.keys():

                    chunk = b''
                    chunk = self.world.level_wrapper.get_raw_chunk_data(k[0], k[1], self.canvas.dimension)
                    NewRawB = []
                    for ent in chunk_dict[k]:
                        cnt += 1
                        ent["UniqueID"] = self._genorate_uid(cnt)
                        NewRawB.append(ent.save_to(compressed=False, little_endian=True))

                    if chunk.get(b'2'):
                        chunk[b'2'] += b''.join(NewRawB)
                    else:
                        chunk[b'2'] = b''.join(NewRawB)

                    self.world.level_wrapper.put_raw_chunk_data(k[0], k[1], chunk, self.canvas.dimension)

            old_start = self.world.level_wrapper.root_tag.get('worldStartCount')
            self.world.level_wrapper.root_tag['worldStartCount'] = TAG_Long((int(old_start) - 1))
            self.world.level_wrapper.root_tag.save()
            self.world.save()
            self._set_list_of_actors_digp
            self._load_entitie_data(_, False, False)
            EntitiePlugin.Onmsgbox(self, "Entitie Import", "Complete")

    def _genorate_uid(self, cnt):
        start_c = self.world.level_wrapper.root_tag.get('worldStartCount')
        new_gen = struct.pack('<LL', int(cnt), int(start_c))
        new_tag = TAG_Long(struct.unpack('<q', new_gen)[0])
        return new_tag

    def _storage_key_(self, val):
        if isinstance(val, bytes):
            return struct.unpack('>II', val)
        if isinstance(val, TAG_String):
            return TAG_Byte_Array([x for x in val.py_data])
        if isinstance(val, TAG_Byte_Array):
            data = b''
            for b in val: data += b
            return data

    def _move_copy_entitie_data(self, event, copy=False):
        res = EntitiePlugin.important_question(self)
        if res == False:
            return
        try:
            data = from_snbt(self.EntyData[self.ui_entitie_choice_list.GetSelection()])
        except:
            data = self.EntyData[self.ui_entitie_choice_list.GetSelection()]
        if data == '':
            EntitiePlugin.Onmsgbox(self, "No Data", "Did you make a selection?")
            return
        x = self._X.GetValue().replace(" X", "")
        y = self._Y.GetValue().replace(" Y", "")
        z = self._Z.GetValue().replace(" Z", "")
        xx, yy, zz = 0, 0, 0

        if float(x) >= 0.0:
            xx = 1
        if float(y) >= 0.0:
            yy = 1
        if float(z) >= 0.0:
            zz = 1

        dim = struct.unpack("<i", self.get_dim_value())[0]
        location = ListTag([FloatTag(float(x) ), FloatTag(float(y) ), FloatTag(float(z)  )])

        if data != '':
            if copy:
                cx, cz = block_coords_to_chunk_coords(data.get('Pos')[0], data.get('Pos')[2])
                actor_key = self.uuid_to_storage_key(data)
                acnt = []
                for x in self.actors.keys():
                    if x[0] == actor_key[0]:
                        acnt.append(x[1])
                acnt.sort()
                max_count_uuid = acnt[-1:][0]
                wc = 4294967296 - actor_key[0]
                new_actor_key = (actor_key[0], max_count_uuid + 1)
                new_actor_key_raw = struct.pack('>LL', new_actor_key[0], new_actor_key[1])
                new_uuid = struct.pack('<LL', max_count_uuid + 1, wc)
                data["UniqueID"] = TAG_Long(struct.unpack('<q', new_uuid)[0])
                data["Pos"] = location
                key_actor = b''.join([b'actorprefix', new_actor_key_raw])
                key_digp = self.build_digp_chunk_key(cx, cz)
                nx, nz = block_coords_to_chunk_coords(location[0], location[2])
                new_digp_key = self.build_digp_chunk_key(nx, nz)

                if data.get("internalComponents") != None:
                    b_a = []
                    for b in struct.pack('>LL', actor_key[0], max_count_uuid + 1):
                        b_a.append(TAG_Byte(b))
                    tb_arry = TAG_Byte_Array([b_a[0], b_a[1], b_a[2], b_a[3], b_a[4], b_a[5], b_a[6], b_a[7]])
                    data["internalComponents"]["EntityStorageKeyComponent"]["StorageKey"] = tb_arry
                if self.world.level_wrapper.version >= (1, 18, 30, 4, 0):
                    try:
                        append_data_key_digp = self.level_db.get(new_digp_key)
                    except:
                        append_data_key_digp = b''
                    append_data_key_digp += new_actor_key_raw
                    self.level_db.put(new_digp_key, append_data_key_digp)
                    self.level_db.put(key_actor, data.save_to(compressed=False, little_endian=True)
                                      .replace(b'\x07\n\x00StorageKey\x08\x00\x00\x00',
                                               b'\x08\n\x00StorageKey\x08\x00'))
                    EntitiePlugin.Onmsgbox(self, "Copy", "Completed")
                    self._finishup(event)
                else:
                    raw_chunk_entitie = NBTFile(data).save_to(compressed=False, little_endian=True)
                    raw = self.world.level_wrapper.get_raw_chunk_data(nx, nz, self.canvas.dimension)
                    if raw.get(b'2'):
                        raw[b'2'] += raw_chunk_entitie
                    else:
                        raw[b'2'] = raw_chunk_entitie
                    self.world.level_wrapper.put_raw_chunk_data(nx, nz, raw, self.canvas.dimension)

                    EntitiePlugin.Onmsgbox(self, "Copy", "Completed")
                    self._finishup(event)
            else:
                cx, cz = block_coords_to_chunk_coords(data.get('Pos')[0], data.get('Pos')[2])
                nx, nz = block_coords_to_chunk_coords(location[0], location[2])
                actor_key = self.uuid_to_storage_key(data)
                actor_key_raw = struct.pack('>LL', actor_key[0], actor_key[1])
                uid = data.get("UniqueID").value
                data["Pos"] = location
                key_digp = self.build_digp_chunk_key(cx, cz)
                new_digp_key = self.build_digp_chunk_key(nx, nz)
                if self.world.level_wrapper.version >= (1, 18, 30, 4, 0):
                    if key_digp != new_digp_key:
                        dpkeys = self.level_db.get(key_digp)
                        try:
                            new_dpkeys = self.level_db.get(new_digp_key)
                        except:
                            new_dpkeys = b''
                        keep = []
                        new_dpkeys = b''.join([new_dpkeys, actor_key_raw])
                        for db in range(0, len(dpkeys), 8):
                            akey = dpkeys[db:db + 8]
                            if akey != actor_key_raw:
                                keep.append(akey)
                        dpkeys = b''.join(keep)
                        self.level_db.put(key_digp, dpkeys)
                        self.level_db.put(new_digp_key, new_dpkeys)
                    actor_key = b''.join([b'actorprefix', actor_key_raw])
                    self.level_db.put(actor_key, data.save_to(compressed=False, little_endian=True)
                                      .replace(b'\x07\n\x00StorageKey\x08\x00\x00\x00',
                                               b'\x08\n\x00StorageKey\x08\x00'))
                    EntitiePlugin.Onmsgbox(self, "Move Position", "Completed")
                    self._finishup(event)
                else:

                    if (cx, cz) != (nx, nz):
                        old_raw = self.world.level_wrapper.get_raw_chunk_data(cx, cz, self.canvas.dimension)
                        new_raw = self.world.level_wrapper.get_raw_chunk_data(nx, nz, self.canvas.dimension)
                        point = 0
                        max = len(old_raw[b'2'])
                        old_raw_keep = []
                        while point < max:
                            data_old, p = load(old_raw[b'2'][point:], compressed=False, little_endian=True, offset=True)
                            point += p
                            if data.get('UniqueID') != data_old.get('UniqueID'):
                                old_raw_keep.append(data_old.save_to(compressed=False, little_endian=True))
                        old_raw[b'2'] = b''.join(old_raw_keep)
                        self.world.level_wrapper.put_raw_chunk_data(cx, cz, old_raw, self.canvas.dimension)
                        raw_chunk_entitie = NBTFile(data).save_to(compressed=False, little_endian=True)

                        if new_raw.get(b'2'):
                            new_raw[b'2'] += raw_chunk_entitie
                        else:
                            new_raw[b'2'] = raw_chunk_entitie
                        self.world.level_wrapper.put_raw_chunk_data(nx, nz, new_raw, self.canvas.dimension)
                        EntitiePlugin.Onmsgbox(self, "Move Position", "Completed")
                        self._finishup(event)
                    else:
                        update_raw = self.world.level_wrapper.get_raw_chunk_data(nx, nz, self.canvas.dimension)
                        point = 0
                        max = len(update_raw[b'2'])
                        update_keep = []
                        while point < max:
                            data_old, p = load(update_raw[b'2'][point:], compressed=False, little_endian=True,
                                               offset=True)
                            point += p
                            if data.get('UniqueID') != data_old.get('UniqueID'):
                                update_keep.append(data_old.save_to(compressed=False, little_endian=True))
                            else:
                                update_keep.append(NBTFile(data).save_to(compressed=False, little_endian=True))
                        update_raw[b'2'] = b''.join(update_keep)
                        self.world.level_wrapper.put_raw_chunk_data(nx, nz, update_raw, self.canvas.dimension)
                        EntitiePlugin.Onmsgbox(self, "Move Position", "Completed")
                        self._finishup(event)

    def _finishup(self, event):
        self.world.save()
        self._set_list_of_actors_digp
        self._load_entitie_data(event, False, False)

    def _save_data_to_world(self, _):

        NewRawB = b''
        selection = self.ui_entitie_choice_list.GetSelection()
        # newData = self.nbt_editor_instance.GetValue()
        res = EntitiePlugin.important_question(self)
        if res == False:
            return
        new_data = NBTEditor.build_to(self.nbt_editor_instance, _)
        self.EntyData[selection] = new_data.to_snbt(1)
        if self.world.level_wrapper.version >= (1, 18, 30, 4, 0):
            for snbt, key in zip(self.EntyData, self.Key_tracker):
                nbt_data = from_snbt(snbt)
                dim = struct.unpack("<i", self.get_dim_value())[0]
                cx, cz = block_coords_to_chunk_coords(nbt_data.get('Pos')[0], nbt_data.get('Pos')[2])
                try:
                    store_key = struct.unpack(">LL", (self._storage_key_(
                        nbt_data.get('internalComponents').get('EntityStorageKeyComponent').get('StorageKey'))))

                except:
                    store_key = key
                for key in self.digp.keys():
                    for i, p in enumerate(self.digp[key]):
                        if store_key == p:
                            self.digp[key].remove(p)
                self.digp[(cx, cz, dim)].append(store_key)
                raw_actor_key = b''.join([b'actorprefix', struct.pack('>II', store_key[0], store_key[1])])
                raw_nbt_data = nbt_data.save_to(compressed=False, little_endian=True) \
                    .replace(b'\x07\n\x00StorageKey\x08\x00\x00\x00', b'\x08\n\x00StorageKey\x08\x00')
                self.level_db.put(raw_actor_key, raw_nbt_data)

            for data in self.digp.keys():
                cx, cz, dim = data
                new_concatination_data = b''
                if dim == 0:
                    raw_digp_key = b''.join([b'digp', struct.pack('<ii', cx, cz)])
                else:
                    raw_digp_key = b''.join([b'digp', struct.pack('<iii', cx, cz, dim)])
                for a, b in self.digp[data]:
                    new_concatination_data += struct.pack('>II', a, b)
                self.level_db.put(raw_digp_key, new_concatination_data)

            EntitiePlugin.Onmsgbox(self, "Entities Saved", "Complete")
        else:
            for snbt, key in zip(self.EntyData, self.Key_tracker):
                nbt_data = from_snbt(snbt)
                dim = struct.unpack("<i", self.get_dim_value())[0]
                cx, cz = block_coords_to_chunk_coords(nbt_data.get('Pos')[0], nbt_data.get('Pos')[2])
                actor_key = self.uuid_to_storage_key(nbt)
                self.actors[actor_key].clear()
                self.actors[actor_key].append(to_snbt(1))
                for k in self.digp.keys():
                    if actor_key in self.digp[k]:
                        self.digp[k].remove(actor_key)

                self.digp[(cx, cz, dim)].append(actor_key)

            for k, v in self.digp.items():
                chunk = self.world.level_wrapper.get_raw_chunk_data(k[0], k[1], self.canvas.dimension)
                chunk[b'2'] = b''
                for ak in v:
                    nbt_data = from_snbt(self.actors.get(ak)[0])
                    chunk[b'2'] += nbt_data.save_to(compressed=False, little_endian=True)

                self.world.level_wrapper.put_raw_chunk_data(k[0], k[1], chunk, self.canvas.dimension)

            EntitiePlugin.Onmsgbox(self, "Entities Saved", "Complete")

    def check_if_key_used(self, l, h):
        pass

    def build_actor_key(self, l, h):
        return b''.join([b'actorprefix', struct.pack('>ii', l, h)])

    def build_digp_chunk_key(self, xc, xz):
        if 'minecraft:the_end' in self.canvas.dimension:
            dim = int(2).to_bytes(4, 'little', signed=True)
        elif 'minecraft:the_nether' in self.canvas.dimension:
            dim = int(1).to_bytes(4, 'little', signed=True)
        elif 'minecraft:overworld' in self.canvas.dimension:
            dim = b''

        return b''.join([b'digp', struct.pack('<ii', xc, xz), dim])

    def digp_chunk_key_to_cords(self, data_key: bytes):
        xc, zc = struct.unpack_from("<ii", data_key, 4)
        if len(data_key) > 12:
            dim = struct.unpack_from("<i", data_key, 12)[0]
            return xc, zc, dim
        else:
            return xc, zc, 0

    def check_if_duplicate(self, nbt_enty):
        unique_id = nbt_enty.get('UniqueID')
        if unique_id in self.all_uniqueids:
            pass

    def convert_uniqueids(self, uid_or_enty_cnt, world_counter=0):
        l, h = 0, 0
        world_cnt, cnt_enty = b'', b''
        if isinstance(uid_or_enty_cnt, bytes):
            l, h = struct.unpack('<II', uid_or_enty_cnt)
            return l, h
        elif isinstance(uid_or_enty_cnt, int):
            cnt_enty = struct.pack('<I', uid_or_enty_cnt)
            world_cnt = struct.pack('<I', world_counter)
            return cnt_enty + world_cnt

    def save_chunk_backup(self, cx, cz, dimension, chunk):
        pathto = ""
        fname = "chk_" + str(cx) + "_" + str(cz) + "_" + str(
            dimension.replace(":", "_")) + "_Dont Remove first part.bak"
        fdlg = wx.FileDialog(self, "Save  Block Data", "", fname, "bakup files(*.bak)|*.*", wx.FD_SAVE)
        fdlg.ShowModal()
        pathto = fdlg.GetPath()
        if ".bak" not in pathto:
            pathto = pathto + ".bak"
        with open(pathto, "wb") as tfile:
            tfile.write(pickle.dumps(chunk))
            tfile.close()

    def load_chunk_backup(self):
        chunk_raw = b''
        fdlg = wx.FileDialog(self, "Load Block Data", "", "cx_cz_dimension_anyName.bak", "json files(*.bak)|*.*",
                             wx.FD_OPEN)
        if fdlg.ShowModal() == wx.ID_OK:
            pathto = fdlg.GetPath()
        with open(pathto, "rb") as tfile:
            chunk_raw = tfile.read()
            tfile.close()
        return chunk_raw

    @property
    def reuse_var(self):
        self.lstOfE = []
        # make sure to start fresh
        self.selection = self.canvas.selection.selection_group

    def get_dim_value(self):
        if 'minecraft:the_end' in self.canvas.dimension:
            dim = int(2).to_bytes(4, 'little', signed=True)
        elif 'minecraft:the_nether' in self.canvas.dimension:
            dim = int(1).to_bytes(4, 'little', signed=True)
        elif 'minecraft:overworld' in self.canvas.dimension:
            dim = int(0).to_bytes(4, 'little', signed=True)
        return dim

    def _load_entitie_data(self, event, bool1, bool2):
        self.reuse_var
        self._set_list_of_actors_digp
        self.get_raw_data_new_version(bool1, bool2)

        self.ui_entitie_choice_list.Set(self.lstOfE)

    @property
    def level_db(self):
        level_wrapper = self.world.level_wrapper
        if hasattr(level_wrapper, "level_db"):
            return level_wrapper.level_db
        else:
            return level_wrapper._level_manager._db

    def uuid_to_storage_key(self, nbt):
        uid = get("UniqueID").value
        uuid = struct.pack('<q', uid)
        # "converted to Long to see real data"
        acnt, wrldcnt = struct.unpack('<LL', uuid)
        wc = 4294967296 - wrldcnt
        actor_key = (wc, acnt)
        return actor_key

    def nbt_loder(self, raw):
        try:
            new_raw = load(raw.replace(b'\x08\n\x00StorageKey\x08\x00',
                                       b'\x07\n\x00StorageKey\x08\x00\x00\x00'), compressed=False, little_endian=True)
        except:
            new_raw = load(raw, compressed=False, little_endian=True)
        return new_raw

    @property
    def _set_list_of_actors_digp(self):
        self.actors = collections.defaultdict(list)
        self.digp = collections.defaultdict(list)
        items = ""

        if self.world.level_wrapper.version >= (1, 18, 30, 4, 0):
            self.not_to_remove = []
            actorprefixs = iter(self.level_db.iterate(start=b'actorprefix',
                                                      end=b'actorprefix\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF'))
            digps = iter(self.level_db.iterate(start=b'digp',
                                               end=b'digp\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF'))
            done_actors = False
            done_digps = False
            while not done_actors:
                try:
                    k, v = next(actorprefixs)
                except StopIteration:
                    done_actors = True
                else:
                    if b"actorprefixb'\\" not in k:
                        # print(k, v)
                        # self.level_db.delete(k)
                        self.actors[struct.unpack('>II', k[11:])].append(v)

            while not done_digps:
                try:
                    k, v = next(digps)

                except StopIteration:
                    done_digps = True
                else:
                    if v != b'':
                        if len(k) == 12:
                            k += b'\x00\x00\x00\x00'
                        for p in range(0, len(v), 8):
                            #  print(v)
                            self.digp[struct.unpack('<iii', k[4:])].append(
                                struct.unpack('>II', v[p:p + 8]))
                            self.not_to_remove.append(struct.unpack('>II', v[p:p + 8]))
        else:

            self.EntyData.clear()  # make sure to start fresh
            nbt_ = CompoundTag({})
            dim = dim = struct.unpack("<i", self.get_dim_value())[0]
            world_start_count = self.world.level_wrapper.root_tag["worldStartCount"]
            all_chunks = [x for x in self.world.level_wrapper.all_chunk_coords(self.canvas.dimension)]
            for cx, cz in all_chunks:
                chunk = self.world.level_wrapper.get_raw_chunk_data(cx, cz, self.canvas.dimension)
                if chunk.get(b'2') != None:
                    max = len(chunk[b'2'])
                    cp = 0
                    while cp < max:
                        nbt, p = load(chunk[b'2'][cp:], little_endian=True, offset=True)
                        cp += p
                        actor_key = self.uuid_to_storage_key(nbt)
                        self.actors[actor_key].append(to_snbt(1))
                        self.digp[(cx, cz, dim)].append(actor_key)

    def _delete_all_the_dead(self, _):
        self._set_list_of_actors_digp
        self.the_dead = collections.defaultdict(list)
        count_deleted = 0
        for dv in self.actors.keys():
            if dv not in self.not_to_remove:
                key = b''.join([b'actorprefix', struct.pack('>II', dv[0], dv[1])])
                self.level_db.delete(key)
                count_deleted += 1
        self.ui_entitie_choice_list.Set([])
        EntitiePlugin.Onmsgbox(self, "DELETED", f"Deleted {count_deleted} ghosted entities . ")

    def _list_the_dead(self, _):
        self._set_list_of_actors_digp
        self.the_dead = collections.defaultdict(list)
        for dv in self.actors.keys():
            if dv not in self.not_to_remove:
                key = b''.join([b'actorprefix', struct.pack('>II', dv[0], dv[1])])
                data = self.level_db.get(key)
                nbt_ = load(data.replace(b'\x08\n\x00StorageKey\x08\x00',
                                         b'\x07\n\x00StorageKey\x08\x00\x00\x00'), little_endian=True)
                self.the_dead[key].append(nbt)

        self.EntyData.clear()
        self.lstOfE = []
        self.current_selection = []

        filter = self.exclude_filter.GetValue().split(",")
        custom_filter = self.include_filter.GetValue().split(",")
        for k, v in self.the_dead.items():
            px, py, pz = '', '', ''
            name = str(v[0]['identifier']).replace("minecraft:", "")
            try:
                px, py, pz = v[0].get('Pos').value
            except:
                print("ERROR WHY")
                pass
            #  print(k, v, name, "wtf went wrong")
            if name not in filter and custom_filter == ['']:
                self.EntyData.append(v[0].to_snbt(1))
                self.lstOfE.append(
                    name + " , " + str(px).split(".")[0] + ", " + str(py).split(".")[0] + ", " + str(pz).split(".")[0])
                self.current_selection.append(k)
            if name in custom_filter:
                self.current_selection.append(k)
                self.EntyData.append(v[0].to_snbt(1))
                self.lstOfE.append(
                    name + " , " + str(px).split(".")[0] + ", " + str(py).split(".")[0] + ", " + str(pz).split(".")[0])
        # print(len(self.lstOfE), len(self.EntyData), len(self.current_selection), len(self.the_dead.items()))
        zipped_lists = zip(self.lstOfE, self.EntyData, self.current_selection)
        sorted_pairs = sorted(zipped_lists)
        tuples = zip(*sorted_pairs)
        self.lstOfE, self.EntyData, self.current_selection = [list(tuple) for tuple in tuples]
        self.ui_entitie_choice_list.Set(self.lstOfE)

    def _make_undead(self, _):
        res = EntitiePlugin.important_question(self)
        if res == False:
            return
        bring_back = from_snbt(self.EntyData[self.ui_entitie_choice_list.GetSelection()])
        raw_dead_actor_key = self.current_selection.pop(self.ui_entitie_choice_list.GetSelection())
        self.the_dead.pop(raw_dead_actor_key)
        try:
            recovory_key = self._storage_key_(
                bring_back["internalComponents"]["EntityStorageKeyComponent"]['StorageKey'])
        except:
            recovory_key = raw_dead_actor_key[11:]
        #  print(recovory_key)

        x, y, z = bring_back.get('Pos').value
        # print(x, y, z)
        try:
            bring_back["Attributes"][1]['Current'] = TAG_Float(20.)
            bring_back["Dead"] = TAG_Byte(0)
        except:
            pass
        raw_nbt_ = NBTFile(bring_back).save_to(compressed=False, little_endian=True) \
            .replace(b'\x07\n\x00StorageKey\x08\x00\x00\x00', b'\x08\n\x00StorageKey\x08\x00')
        self.level_db.put(raw_dead_actor_key, raw_nbt)
        for popoff in self.digp.keys():
            for d in self.digp[popoff]:
                #   print(self._storage_key_(recovory_key), d)
                if self._storage_key_(recovory_key) in d:
                    dd = self.digp[popoff].pop(d)

        xc, zc = block_coords_to_chunk_coords(x, z)
        digp_key = (xc, zc, struct.unpack('i', self.get_dim_value())[0])
        self.digp[digp_key].append(self._storage_key_(recovory_key))
        self.EntyData.pop(self.ui_entitie_choice_list.GetSelection())
        self.lstOfE.pop(self.ui_entitie_choice_list.GetSelection())
        self.ui_entitie_choice_list.Set(self.lstOfE)

        for dig in self.digp.keys():
            new_digp_data = b''
            for dig_data in self.digp[dig]:
                if dig[2] > 0:
                    chunk_loc = b'digp' + struct.pack('<i', dig[0]) + struct.pack('<i', dig[1]) + struct.pack('<i',
                                                                                                              dig[2])
                else:
                    chunk_loc = b'digp' + struct.pack('<i', dig[0]) + struct.pack('<i', dig[1])
                new_digp_data += struct.pack(">II", dig_data[0], dig_data[1])
            self.level_db.put(chunk_loc, new_digp_data)

    def _delete_from_list(self, e):
        res = EntitiePlugin.important_question(self)
        if res == False:
            return
        setdata = from_snbt(self.EntyData[self.ui_entitie_choice_list.GetSelection()])
        xc, xz = block_coords_to_chunk_coords(setdata.get("Pos")[0], setdata.get("Pos")[2])
        if self.world.level_wrapper.version >= (1, 18, 30, 4, 0):
            p_dig_key = self.build_digp_chunk_key(xc, xz)
            s_key = self._storage_key_(
                setdata.get('internalComponents').get("EntityStorageKeyComponent").get("StorageKey"))
            save_keys = []
            the_dig_keys = self.level_db.get(p_dig_key)
            for key_r in range(0, len(the_dig_keys), 8):
                current_key = the_dig_keys[key_r:key_r + 8]
                if s_key != current_key:
                    save_keys.append(current_key)
            if len(save_keys) > 0:
                self.level_db.put(p_dig_key, b''.join(save_keys))
            else:
                self.level_db.delete(p_dig_key)
            self.level_db.delete(b''.join([b'actorprefix', s_key]))
        else:
            raw_chunk = self.world.level_wrapper.get_raw_chunk_data(xc, xz, self.canvas.dimension)
            if raw_chunk[b'2']:
                point = len(raw_chunk[b'2'])
                pos = 0
                find_uuid = setdata.get('UniqueID')
                keep_data = []
                while pos < point:
                    data, p = amulet_load(raw_chunk[b'2'][pos:], compressed=False, little_endian=True, offset=True)
                    uuid = data.get('UniqueID')
                    if find_uuid != uuid:
                        keep_data.append(data)
                    pos += p
                new_data = b''
                for d in keep_data:
                    new_data += d.save_to(compressed=False, little_endian=True)
                raw_chunk[b'2'] = b''
                raw_chunk[b'2'] = new_data
                self.world.level_wrapper.put_raw_chunk_data(xc, xz, raw_chunk, self.canvas.dimension)
        self.world.save()
        self._load_entitie_data(e, False, self.get_all_flag)

class Java(wx.Panel):

    def __int__(self, world, canvas):
        wx.Panel.__init__(self, parent)
        self.world = world
        self.canvas = canvas
        select_chunks = self.canvas.selection.selection_group.chunk_locations()  # selection_group.chunk_locations()
        all_chunks = [x for x in self.world.level_wrapper.all_chunk_coords(self.canvas.dimension)]
        dim = struct.unpack("<i", self.get_dim_value())[0]
        custom_filter = self.filter.GetValue().split(",")

    def _delete_from_list(self, e):
        res = EntitiePlugin.important_question(self)
        if res == False:
            return
        setdata = from_snbt(self.EntyData[self.ui_entitie_choice_list.GetSelection()])
        xc, xz = block_coords_to_chunk_coords(setdata.get("Pos")[0], setdata.get("Pos")[2])
        find_uuid = setdata.get("UUID")
        rx, rz = world_utils.chunk_coords_to_region_coords(xc, xz)
        entitiesPath = self.get_dim_vpath_java_dir(rx, rz)  # full path for file
        self.Entities_region = AnvilRegion(entitiesPath)
        chunk = self.Entities_region.get_chunk_data(xc % 32, xz % 32)
        if self.world.level_wrapper.version >= 2730:
            for i, enty in enumerate(chunk['Entities']):
                if enty.get('UUID') == find_uuid:
                    chunk['Entities'].pop(i)
        else:
            for i, enty in enumerate(chunk['Level']['Entities']):
                if enty.get('UUID') == find_uuid:
                    chunk['Level']['Entities'].pop(i)
        self.Entities_region.put_chunk_data(xc % 32, xz % 32, chunk)
        self.Entities_region.save()

        self.world.save()
        self._load_entitie_data(e, False, self.get_all_flag)

    def _load_entitie_data(self, event, bool1, bool2):
        self.get_all_flag = bool2
        sel = SelectionGroup([])
        if bool2:
            self.canvas.selection.set_selection_group(sel)
        self._set_list_of_actors_digp
        self.ui_entitie_choice_list.Set([])
        self.ui_entitie_choice_list.Set(self.lstOfE)

    @property
    def _set_list_of_actors_digp(self):
        self.found_entities = []
        self.lstOfE = []
        self.EntyData = []
        if self.canvas.selection.selection_group:
            chunks = self.canvas.selection.selection_group.chunk_locations()
        else:
            chunks = [x for x in self.world.level_wrapper.all_chunk_coords(self.canvas.dimension)]
        rcords = collections.defaultdict(list)
        self.found_entities = ListTag()
        for xc, xz in chunks:
            rx, rz = world_utils.chunk_coords_to_region_coords(xc, xz)
            rcords[(rx, rz)].append((xc, xz))

        for rx, rz in rcords.keys():
            path = self.world.level_wrapper.path  # need path for file
            entitiesPath = self.get_dim_vpath_java_dir(rx, rz)  # full path for file
            file_exists = exists(entitiesPath)
            if file_exists:
                self.Entities_region = AnvilRegion(entitiesPath)  # create instance for region data
                for cx, cz in rcords[(rx, rz)]:

                    self.nbt_data = []
                    if self.Entities_region.has_chunk(cx % 32, cz % 32):
                        self.nbt_data_full = self.Entities_region.get_chunk_data(cx % 32, cz % 32)
                        if self.world.level_wrapper.version >= 2730:
                            self.nbt_data = self.nbt_data_full['Entities']
                        else:
                            self.nbt_data = self.nbt_data_full["Level"]['Entities']
                        for x in self.nbt_data:
                            self.found_entities.append(x)

        for nbt_ in self.found_entities:
            exclude_filter = self.exclude_filter.GetValue().split(",")
            include_filter = self.include_filter.GetValue().split(",")
            name = str(nbt_['id']).replace("minecraft:", "")
            if exclude_filter != ['']:
                if name not in exclude_filter:
                    self.lstOfE.append(name)
                    self.EntyData.append(nbt_.to_snbt(1))
            if include_filter != ['']:
                if name in include_filter:
                    self.lstOfE.append(name)
                    self.EntyData.append(nbt_.to_snbt(1))
            else:
                self.lstOfE.append(name)
                self.EntyData.append(nbt_.to_snbt(1))

        if len(self.EntyData) > 0:
            zipped_lists = zip(self.lstOfE, self.EntyData)
            sorted_pairs = sorted(zipped_lists)
            tuples = zip(*sorted_pairs)
            self.lstOfE, self.EntyData = [list(tuple) for tuple in tuples]

        if len(self.lstOfE) == 0:
            EntitiePlugin.Onmsgbox(self, "No Entities", "No Entities were found within the selecton")
            return

    def _move_copy_entitie_data(self, event, copy=False):
        res = EntitiePlugin.important_question(self)
        if res == False:
            return
        try:
            setdata = from_snbt(self.EntyData[self.ui_entitie_choice_list.GetSelection()])
        except:
            setdata = self.EntyData[self.ui_entitie_choice_list.GetSelection()]
        ox, oy, oz = setdata.get('Pos')
        nx = self._X.GetValue().replace(" X", "")
        ny = self._Y.GetValue().replace(" Y", "")
        nz = self._Z.GetValue().replace(" Z", "")
        location = TAG_List([TAG_Double(float(nx)), TAG_Double(float(ny)), TAG_Double(float(nz))])

        setdata["Pos"] = location
        data_nbt_ = setdata

        cx, cz = block_coords_to_chunk_coords(float(ox), float(oz))
        rx, rz = world_utils.chunk_coords_to_region_coords(cx, cz)

        self.Entities_region = AnvilRegion(self.get_dim_vpath_java_dir(rx, rz))
        nbt_reg = self.Entities_region.get_chunk_data(cx % 32, cz % 32)
        main_uuid = data_get('UUID')
        if copy:
            pass
        else:
            if self.world.level_wrapper.version >= 2730:
                for i, x in enumerate(nbt_reg['Entities']):
                    if main_uuid == x.get('UUID'):
                        nbt_reg['Entities'].pop(i)
            else:
                for i, x in enumerate(nbt_reg['Level']['Entities']):
                    if main_uuid == x.get('UUID'):
                        nbt_reg['Level']['Entities'].pop(i)

        self.Entities_region.put_chunk_data(cx % 32, cz % 32, nbt_reg)
        self.Entities_region.save()
        cx, cz = block_coords_to_chunk_coords(float(nx), float(nz))
        rx, rz = world_utils.chunk_coords_to_region_coords(cx, cz)
        file_exists = exists(self.get_dim_vpath_java_dir(rx, rz))
        if file_exists:
            self.Entities_region = AnvilRegion(self.get_dim_vpath_java_dir(rx, rz))
            if self.Entities_region.has_chunk(cx % 32, cz % 32):
                nbt_reg = self.Entities_region.get_chunk_data(cx % 32, cz % 32)
                if copy:
                    uu_id = uuid.uuid4()
                    q, w, e, r = struct.unpack('>iiii', uu_id.bytes)
                    setdata['UUID'] = IntTag_Array(
                        [IntTag(q), IntTag(w), IntTag(e),
                         IntTag(r)])
                if self.world.level_wrapper.version >= 2730:
                    nbt_reg['Entities'].append(setdata)
                else:
                    nbt_reg['Level']['Entities'].append(setdata)
                self.Entities_region.put_chunk_data(cx % 32, cz % 32, nbt_reg)
                self.Entities_region.save()
            else:
                if self.world.level_wrapper.version >= 2730:
                    new_data = CompoundTag({})
                    new_data['Position'] = from_snbt(f'[I; {cx}, {cz}]')
                    new_data['DataVersion'] = IntTag(self.world.level_wrapper.version)
                    new_data['Entities'] = ListTag([])
                    new_data['Entities'].append(setdata)
                    self.Entities_region.put_chunk_data(cx % 32, cz % 32, new_data)
                    self.Entities_region.save()
                else:
                    print("java version would leave hole in world , file")
        else:
            if self.world.level_wrapper.version >= 2730:
                self.Entities_region = AnvilRegion(self.get_dim_vpath_java_dir(rx, rz), create=True)
                new_data = CompoundTag({})
                new_data['Position'] = from_snbt(f'[I; {cx}, {cz}]')
                new_data['DataVersion'] = IntTag(self.world.level_wrapper.version)
                new_data['Entities'] = ListTag([])
                new_data['Entities'].append(setdata)
                self.Entities_region.put_chunk_data(cx % 32, cz % 32, new_data)
                self.Entities_region.save()
                print(f'SAVED CHUNK NEW FILE file r.{rx}, {rz} Chunk: {cx}, {cz}')
            else:
                print("java version would leave hole in world, No file")

        self.world.save()
        self._load_entitie_data(event, False, self.get_all_flag)

    def get_dim_vpath_java_dir(self, regonx, regonz):
        file = "r." + str(regonx) + "." + str(regonz) + ".mca"
        path = self.world.level_wrapper.path
        full_path = ''
        if 'minecraft:the_end' in self.canvas.dimension:
            dim = 'DIM1'
        elif 'minecraft:the_nether' in self.canvas.dimension:
            dim = 'DIM-1'
        elif 'minecraft:overworld' in self.canvas.dimension:
            dim = ''
        if self.world.level_wrapper.version >= 2730:
            version = "entities"
        else:
            version = "region"
        full_path = os.path.join(path, dim, version, file)
        return full_path

    def java_get_ver_path_data(self, nbt):

        if self.world.level_wrapper.version >= 2730:
            return get('Entities')
        else:
            return get("Level").get('Entities')

    def java_set_ver_path_data(self, add, this):

        if self.world.level_wrapper.version >= 2730:
            if this == None:
                add = ListTag([])
            add.append(this)
        else:
            if this == None:
                return
            add.append(this)
        return add

    def delete_un_or_selected_entities(self, event, unseleted):
        res = EntitiePlugin.important_question(self)
        if res == False:
            return
        chunk_regon_dict = collections.defaultdict(list)
        if unseleted:
            chunks = [x for x in self.world.level_wrapper.all_chunk_coords(self.canvas.dimension)]
            selected = self.canvas.selection.selection_group.chunk_locations()
        else:
            chunks = self.canvas.selection.selection_group.chunk_locations()
            selected = []
        for xc, xz in chunks:
            rx, rz = world_utils.chunk_coords_to_region_coords(xc, xz)
            the_file = self.get_dim_vpath_java_dir(rx, rz)
            file_exists = exists(the_file)
            if file_exists:
                chunk_regon_dict[(rx, rz, the_file)].append((xc, xz))
        for rx, rz, f in chunk_regon_dict.keys():
            self.Entities_region = AnvilRegion(f)
            for cx, cz in chunk_regon_dict[(rx, rz, f)]:
                if self.Entities_region.has_chunk(cx % 32, cz % 32):
                    self.chunk_data = self.Entities_region.get_chunk_data(cx % 32, cz % 32)
                    if self.world.level_wrapper.version >= 2730:
                        if (cx, cz) not in selected:
                            self.chunk_data['Entities'].clear()
                    else:
                        if (cx, cz) not in selected:
                            self.chunk_data['Level']['Entities'].clear()
                    self.Entities_region.put_chunk_data(cx % 32, cz % 32, self.chunk_data)
            self.Entities_region.save()
        self.world.save()
        self._load_entitie_data(event, False, self.get_all_flag)

    def _imp_entitie_data(self, _):

        dlg = ExportImportCostomDialog(None)
        dlg.InitUI(2)
        res = dlg.ShowModal()
        snbt_list = b''
        if dlg.nbt_file.GetValue():
            res = EntitiePlugin.important_question(self)
            if res == False:
                return
            try:
                self._import_nbt(_)
            except ValueError as e:
                EntitiePlugin.Onmsgbox(self, "No Selection",
                                       "You must select a area in the world to start from, \n Note: Just one block will work. It builds from the South/West")
            return

        if dlg.list.GetValue():
            res = EntitiePlugin.important_question(self)
            if res == False:
                return
            fdlg = wx.FileDialog(self, "Import Entities from a line list of snbt", "", "",
                                 f"SNBT (*.snbt_{self.world.level_wrapper.platform})|*.*", wx.FD_OPEN)
            if fdlg.ShowModal() == wx.ID_OK:
                pathto = fdlg.GetPath()
            else:
                return
            with open(pathto, "r") as tfile:
                snbt_list = tfile.readlines()
            loaction_dict = collections.defaultdict(list)
            for line in snbt_list:
                nbt_ = from_snbt(line)
                x, y, z = nbt_.get('Pos').value
                uu_id = uuid.uuid4()
                q, w, e, r = struct.unpack('>iiii', uu_id.bytes)
                nbt_['UUID'] = IntTag_Array(
                    [IntTag(q), IntTag(w), IntTag(e), IntTag(r)])
                bc, bz = block_coords_to_chunk_coords(x, z)
                rx, rz = world_utils.chunk_coords_to_region_coords(bc, bz)
                l_nbt_ = {}
                l_nbt_[(bc, bz)] = nbt_
                loaction_dict[(rx, rz)].append(l_nbt_)

            for rx, rz in loaction_dict.keys():
                file_exists = exists(self.get_dim_vpath_java_dir(rx, rz))
                if file_exists:
                    for di in loaction_dict[(rx, rz)]:
                        for k, v in di.items():
                            cx, cz = k
                            nbt_data = v
                            self.Entities_region = AnvilRegion(self.get_dim_vpath_java_dir(rx, rz))
                            if self.Entities_region.has_chunk(cx % 32, cz % 32):
                                nbtdata = self.Entities_region.get_chunk_data(cx % 32, cz % 32)
                                entitiedata = self.java_get_ver_path_data(nbtdata)
                                newData = self.java_set_ver_path_data(entitiedata, nbt_data)
                                self.Entities_region.put_chunk_data(cx % 32, cz % 32, nbtdata)
                                self.Entities_region.save()
                else:
                    if self.world.level_wrapper.version >= 2730:
                        new_data = CompoundTag({})
                        new_data['Position'] = from_snbt(f'[I; {cx}, {cz}]')
                        new_data['DataVersion'] = IntTag(self.world.level_wrapper.version)
                        new_data['Entities'] = ListTag([])
                        new_data['Entities'].append(nbt_data)
                        self.Entities_region.put_chunk_data(cx % 32, cz % 32, new_data)
                        self.Entities_region.save()
                        print(f'SAVED CHUNK file r.{rx}, {rz} Chunk: {cx}, {cz}, world genoration my kill entitiy')
                    else:
                        mc_id = new_data.get('id')
                        print(f'NO CHUNK DATA file r.{rx}, {rz} Chunk: {cx} , {cz} , pos: {(x, y, z)} , id: {mc_id}')
                        #  less than java version 2730
                        # can not store entities without leaving a chunk hole.

            self.canvas.run_operation(lambda: self._refresh_chunk_now(self.canvas.dimension, self.world, cx, cz))
            self.world.save()
            EntitiePlugin.Onmsgbox(self, "SNBT LIST", "Import Complete.")

        if dlg.ms_file.GetValue():
            snbt_list = []
            fdlg = wx.FileDialog(self, "Add Entities into a MCStructure File", "", "",
                                 "MCstructure files(*.mcstructure)|*.*", wx.FD_OPEN)
            if fdlg.ShowModal() == wx.ID_OK:
                pathto = fdlg.GetPath()
            else:
                return
            with open(pathto, "rb") as tfile:
                snbt_list = tfile.read()
                tfile.close()
            anbt_ = amulet_load(snbt_list, compressed=False, little_endian=True)
            sx, sy, sz = aget("structure_world_origin")
            egx, egy, egz = aget("size")
            ex, ey, ez = sx - egx, sy - egy, sz - egz
            group = []
            self.canvas.camera.set_location((sx, 70, sz))
            self.canvas.camera._notify_moved()
            s, e = (int(sx), int(sy), int(sz)), (int(ex), int(ey), int(ez))
            group.append(SelectionBox(s, e))
            sel_grp = SelectionGroup(group)
            self.canvas.selection.set_selection_group(sel_grp)

    def _exp_entitie_data(self, _):

        dlg = ExportImportCostomDialog(None)
        dlg.InitUI(1)
        res = dlg.ShowModal()
        chunks_to_backup = []
        if dlg.all_chunks.GetValue():
            chunks_to_backup = [x for x in self.world.level_wrapper.all_chunk_coords(self.canvas.dimension)]
        elif dlg.selected_chunks.GetValue():
            chunks_to_backup = self.canvas.selection.selection_group.chunk_locations()
        elif dlg.all_entities_nbt.GetValue():
            self._export_ALL_nbt(_)
            return
        elif dlg.nbt_file_option.GetValue():
            self._export_nbt(_)
            return
        else:
            return
        snbt_lines = ""
        self.nbt_data = []
        regon_dict = collections.defaultdict(list)
        for cx, cz in chunks_to_backup:
            rx, rz = world_utils.chunk_coords_to_region_coords(cx, cz)
            regon_dict[(rx, rz)].append((cx, cz))
        for rx, rz in regon_dict.keys():
            entitiesPath = self.get_dim_vpath_java_dir(rx, rz)  # full path for file
            file_exists = exists(entitiesPath)

            if file_exists:
                self.Entities_region = AnvilRegion(entitiesPath)
                for cx, cz in regon_dict[rx, rz]:
                    if self.Entities_region.has_chunk(cx % 32, cz % 32):
                        self.nbt_data_full = self.Entities_region.get_chunk_data(cx % 32, cz % 32)

                        if self.world.level_wrapper.version >= 2730:
                            self.nbt_data = self.nbt_data_full['Entities']
                        else:
                            self.nbt_data = self.nbt_data_full["Level"]['Entities']
                        if len(self.nbt_data) > 0:
                            for x in self.nbt_data:
                                snbt_lines += x.to_snbt() + "\n"
        EntitiePlugin.save_entities_export(self, snbt_lines)
        EntitiePlugin.Onmsgbox(self, "SNBT LIST", "Export Complete.")

    def _save_data_to_world(self, _):
        res = EntitiePlugin.important_question(self)
        if res == False:
            return
        # newData = self.nbt_editor_instance.GetValue()  # get new data
        newData = NBTEditor.build_to(self.nbt_editor_instance, _)
        data = newData
        # data = from_snbt(newData)  # convert to nbt
        cx, cz = block_coords_to_chunk_coords(data.get("Pos")[0].value, data.get("Pos")[2].value)
        loc = data.get("Pos")
        uuid = data.get("UUID")
        rx, rz = world_utils.chunk_coords_to_region_coords(cx, cz)
        self.Entities_region = AnvilRegion(self.get_dim_vpath_java_dir(rx, rz))
        self.old_to_new_data = self.Entities_region.get_chunk_data(cx % 32, cz % 32)
        if self.world.level_wrapper.version >= 2730:
            for i, o in enumerate(self.old_to_new_data['Entities']):
                if o.get("UUID") == uuid:
                    self.old_to_new_data['Entities'][i] = data
        else:
            for i, o in enumerate(self.old_to_new_data["Level"]['Entities']):
                if o.get("UUID") == uuid:
                    self.old_to_new_data["Level"]['Entities'][i] = data
        self.EntyData[self.ui_entitie_choice_list.GetSelection()] = newData
        self.Entities_region.put_chunk_data(cx % 32, cz % 32, self.old_to_new_data)  # put data back where it goes
        self.Entities_region.save()  # save file operation
        self.world.save()
        EntitiePlugin.Onmsgbox(self, "Operation complete",
                               "The operation has completed without error:\n Save world to see the changes")

    def _export_ALL_nbt(self, _):
        wx.MessageBox("Remind me", "To implement this, "
                                   "Java already has all entities in NBT", wx.OK | wx.ICON_INFORMATION)




    def _export_nbt(self, _):
        entities = ListTag([])
        blocks = ListTag([])
        palette = ListTag([])
        DataVersion = IntTag(2975)
        selection = self.canvas.selection.selection_group.to_box()
        pallet_key_map = collections.defaultdict(list)
        nbt_state_map = collections.defaultdict(list)
        indx = 0
        sx, sy, sz = 0, 0, 0
        reps = EntitiePlugin.con_boc(self, "Air Blocks", 'Do you want to encude air block?')
        mx, my, mz = self.canvas.selection.selection_group.to_box().shape
        block_pos = []
        # bl = np.zeros(shape, dtype=numpy.uint32)
        for x in range(0, (mx)):
            for y in range(0, (my)):
                for z in range(0, (mz)):
                    block_pos.append((x, y, z))
        entities = self.get_entities_nbt(block_pos)
        prg_max = len(block_pos)
        prg_pre = 0
        prg_pre_th = len(block_pos) / 100
        self.prog = wx.ProgressDialog("Saving blocks", str(0) + " of " + str(prg_max),
                                      style=wx.PD_AUTO_HIDE | wx.PD_CAN_ABORT | wx.PD_ELAPSED_TIME | wx.PD_REMAINING_TIME)
        self.prog.Show(True)
        for i, (s, b) in enumerate(zip(selection, block_pos)):
            if self.prog.WasCancelled():
                self.prog.Hide()
                self.prog.Destroy()
                break
            if i >= prg_pre_th:
                prg_pre_th += len(block_pos) / 100
                prg_pre += 1
                self.prog.Update(prg_pre, "Saving blocks " + str(i) + " of " + str(prg_max))
            block, blockEntity = self.world.get_version_block(s[0], s[1], s[2], self.canvas.dimension,
                                                              ("java", (1, 18, 0)))
            if not reps:
                check_string = ""
            else:
                check_string = 'minecraft:air'
            if str(block) != check_string:
                if pallet_key_map.get((block.namespaced_name, str(block.properties))) == None:
                    pallet_key_map[(block.namespaced_name, str(block.properties))] = indx
                    indx += 1
                    palette_Properties = amulet_TAG_Compound(
                        {'Properties': from_snbt(str(block.properties)),
                         'Name': amulet_TAG_String(block.namespaced_name)})
                    palette.append(palette_Properties)
                state = pallet_key_map[(block.namespaced_name, str(block.properties))]

                if blockEntity == None:
                    blocks_pos = amulet_TAG_Compound({'pos': ListTag(
                        [IntTag(b[0]), IntTag(b[1]),
                         IntTag(b[2])]), 'state': IntTag(state)})
                    blocks.append(blocks_pos)
                else:
                    blocks_pos = amulet_TAG_Compound({'nbt': from_snbt(blockEntity.to_snbt()),
                                                      'pos': ListTag(
                                                          [IntTag(b[0]),
                                                           IntTag(b[1]),
                                                           IntTag(b[2])]),
                                                      'state': IntTag(state)})
                    blocks.append(blocks_pos)
        prg_pre = 99
        self.prog.Update(prg_pre, "Finishing Up " + str(i) + " of " + str(prg_max))
        size = ListTag([IntTag(mx), IntTag(my), IntTag(mz)])

        save_it = CompoundTag({})
        save_it['size'] = size
        save_it['entities'] = entities
        save_it['blocks'] = blocks
        save_it['palette'] = palette
        save_it['DataVersion'] = DataVersion
        raw_data = save_it.save_to(compressed=True, little_endian=False)
        prg_pre = 100
        self.prog.Update(prg_pre, "Done")
        pathto = ""
        fdlg = wx.FileDialog(self, "Save As .nbt", "", "", "nbt files(*.nbt)|*.*", wx.FD_SAVE)
        if fdlg.ShowModal() == wx.ID_OK:
            pathto = fdlg.GetPath()
        else:
            return False
        if ".nbt" not in pathto:
            pathto = pathto + ".nbt"
        with open(pathto, "wb") as tfile:
            tfile.write(raw_data)
            tfile.close()

        wx.MessageBox("Save Complete", "No Issues", wx.OK | wx.ICON_INFORMATION)

    def _import_nbt(self, _):

        fdlg = wx.FileDialog(self, "Load .nbt", "", "", "nbt files(*.nbt)|*.*", wx.FD_OPEN)
        if fdlg.ShowModal() == wx.ID_OK:
            pathto = fdlg.GetPath()
            nbt_ = amulet_load(pathto, compressed=True, little_endian=False, )
            block_platform = "java"
            block_version = (1, 18, 0)
            b_pos = []
            palette = []
            Name = []
            enbt_ = []
            xx = self.canvas.selection.selection_group.min_x
            yy = self.canvas.selection.selection_group.min_y
            zz = self.canvas.selection.selection_group.min_z
            reps = EntitiePlugin.con_boc(self, "Air Blocks", 'Do you want to encude air block?')
            for x in get('blocks'):
                if nbt['palette'][int(x.get('state'))].get('Properties') != None:
                    palette.append(
                        dict(from_snbt(nbt['palette'][int(x.get('state'))]['Properties'].to_snbt())))
                else:
                    palette.append(None)
                b_pos.append(x.get('pos'))
                Name.append(nbt['palette'][int(x.get('state'))]['Name'])
                if x.get('nbt') != None:
                    name = str(nbt['palette'][int(x.get('state'))]['Name']).split(':')

                    blockEntity = BlockEntity(name[0], name[1].replace('_', '').capitalize(), 0, 0, 0,
                                              amulet_NBTFile(x.get('nbt')))
                    eappend(blockEntity)
                else:
                    eappend(None)

            if not reps:
                check_string = ""
            else:
                check_string = 'minecraft:air'
            for x in zip(b_pos, palette, Name, enbt):
                if x[1] != check_string:
                    block = Block(str(x[2]).split(':')[0], str(x[2]).split(':')[1], x[1])
                    self.world.set_version_block(xx + x[0][0], yy + x[0][1], zz + x[0][2], self.canvas.dimension,
                                                 (block_platform, block_version), block, x[3])

            self.canvas.run_operation(lambda: self._refresh_chunk_now(self.canvas.dimension, self.world, xx, zz))
            self.world.save()  # MUST SAVE NOW OR THIS WILL REMOVE ENTITIES
            e_nbt_list = []
            for x in get('entities'):
                if str(x) != '':
                    e_nbt_ = x.get('nbt')
                    nxx, nyy, nzz = x.get('pos').value

                    x['nbt']['Pos'] = ListTag([amulet_TAG_Double(float(nxx + xx)),
                                                       amulet_TAG_Double(float(nyy + yy)),
                                                       amulet_TAG_Double(float(nzz + zz))])
                    e_nbt_list.append(x['nbt'])
            self.set_entities_nbt(e_nbt_list)

    def _refresh_chunk_now(self, dimension, world, x, z):
        cx, cz = block_coords_to_chunk_coords(x, z)
        chunk = world.get_chunk(cx, cz, dimension)
        chunk.changed = True

    def get_dim_value_bytes(self):
        if 'minecraft:the_end' in self.canvas.dimension:
            dim = int(2).to_bytes(4, 'little', signed=True)
        elif 'minecraft:the_nether' in self.canvas.dimension:
            dim = int(1).to_bytes(4, 'little', signed=True)
        elif 'minecraft:overworld' in self.canvas.dimension:
            dim = b''
        return dim

    def get_entities_nbt(self, rpos):
        mapdic = collections.defaultdict()

        entities = ListTag([])
        selection = self.canvas.selection.selection_group.to_box()
        for o, n in zip(selection, rpos):
            mapdic[o] = n
        chunk_min, chunk_max = self.canvas.selection.selection_group.min, \
            self.canvas.selection.selection_group.max
        min_chunk_cords, max_chunk_cords = block_coords_to_chunk_coords(chunk_min[0], chunk_min[2]), \
            block_coords_to_chunk_coords(chunk_max[0], chunk_max[2])
        cl = self.canvas.selection.selection_group.chunk_locations()
        self.found_entities = ListTag([])
        self.nbt_data = []
        for cx, cz in cl:
            rx, rz = world_utils.chunk_coords_to_region_coords(cx, cz)  # need region cords for file
            self.Entities_region = AnvilRegion(self.get_dim_vpath_java_dir(rx, rz))
            self.nbt_data_full = self.Entities_region.get_chunk_data(cx % 32, cz % 32)

            if self.Entities_region.has_chunk(cx % 32, cz % 32):
                if self.world.level_wrapper.version >= 2730:
                    self.nbt_data = self.nbt_data_full['Entities']
                else:
                    self.nbt_data = self.nbt_data_full["Level"]['Entities']
                if len(self.nbt_data) > 0:
                    for x in self.nbt_data:
                        self.found_entities.append(x)

        if len(self.found_entities) == 0:
            return ListTag([])
        entities = ListTag([])
        for nbt_data in self.found_entities:
            x, y, z = math.floor(nbt_data.get('Pos')[0].value), math.floor(
                nbt_data.get('Pos')[1].value), math.floor(nbt_data.get('Pos')[2].value)
            if (x, y, z) in selection:
                new_pos = mapdic[(x, y, z)]
                nbt_pos = ListTag([amulet_TAG_Double(sum([new_pos[0],
                                                                  math.modf(abs(nbt_data.get("Pos")[0].value))[0]])),
                                           amulet_TAG_Double(sum([new_pos[1],
                                                                  math.modf(abs(nbt_data.get("Pos")[1].value))[0]])),
                                           amulet_TAG_Double(sum([new_pos[2],
                                                                  math.modf(abs(nbt_data.get("Pos")[2].value))[0]]))])
                nbt_block_pos = ListTag([IntTag(new_pos[0]),
                                                 IntTag(new_pos[1]),
                                                 IntTag(new_pos[2])])
                nbt_nbt_ = from_snbt(nbt_data.to_snbt())
                main_entry = CompoundTag()
                main_entry['nbt'] = nbt_nbt
                main_entry['blockPos'] = nbt_block_pos
                main_entry['pos'] = nbt_pos
                entities.append(main_entry)

        return entities

    def set_entities_nbt(self, entities_list):
        entcnt = 0
        if self.world.level_wrapper.platform == "java":
            path = self.world.level_wrapper.path  # need path for file
            self.version_path = ""
            if self.world.level_wrapper.version >= 2730:
                self.version_path = "entities"
            else:
                self.version_path = "region"
            for nbt_data in entities_list:
                import uuid
                uu_id = uuid.uuid4()
                q, w, e, r = struct.unpack('>iiii', uu_id.bytes)
                nbt_data['UUID'] = IntArrayTag(
                    [IntTag(q), IntTag(w), IntTag(e), IntTag(r)])
                x, y, z = math.floor(nbt_data.get('Pos')[0].value), math.floor(
                    nbt_data.get('Pos')[1].value), math.floor(nbt_data.get('Pos')[2].value)
                cx, cz = block_coords_to_chunk_coords(x, z)
                rx, rz = world_utils.chunk_coords_to_region_coords(cx, cz)
                entitiesPath = self.get_dim_vpath_java_dir(rx, rz)  # full path for file
                file_exists = exists(entitiesPath)
                if file_exists:
                    self.Entities_region = AnvilRegion(entitiesPath)
                    if self.Entities_region.has_chunk(cx % 32, cz % 32):
                        self.chunk_raw = self.Entities_region.get_chunk_data(cx % 32, cz % 32)
                        if self.world.level_wrapper.version >= 2730:
                            if not self.chunk_raw.get('Entities'):
                                self.chunk_raw['Entities'] = ListTag([])

                            self.chunk_raw['Entities'].append(nbt_data)

                            self.Entities_region.put_chunk_data(cx % 32, cz % 32, self.chunk_raw)
                            self.Entities_region.save()
                            print(f' 1 SAVED CHUNK NEW FILE file r.{rx}, {rz} Chunk: {cx}, {cz}')
                        else:
                            if not self.chunk_raw.get('Level').get('Entities'):
                                self.chunk_raw["Level"]['Entities'] = ListTag([])
                            self.chunk_raw["Level"]['Entities'].append(nbt_data)
                            self.Entities_region.put_chunk_data(cx % 32, cz % 32, self.chunk_raw)
                            self.Entities_region.save()
                            print(self.chunk_raw["Level"])
                            print(f' 2 SAVED CHUNK NEW FILE file r.{rx}, {rz} Chunk: {cx}, {cz}')
                    else:
                        if self.world.level_wrapper.version >= 2730:
                            self.Entities_region = AnvilRegion(entitiesPath, create=True)
                            new_data = CompoundTag({})
                            new_data['Position'] = from_snbt(f'[I; {cx}, {cz}]')
                            new_data['DataVersion'] = IntTag(self.world.level_wrapper.version)
                            new_data['Entities'] = ListTag([])
                            new_data['Entities'].append(nbt_data)
                            self.Entities_region.put_chunk_data(cx % 32, cz % 32, new_data)
                            self.Entities_region.save()
                            print(f' 3 SAVED CHUNK NEW FILE file r.{rx}, {rz} Chunk: {cx}, {cz}')
                        else:
                            print(
                                f'4 NO CHUNK DATA file r.{rx}, {rz} Chunk: {cx} , {cz} ')
                            # java less than version 2730
                        # can not store entities without leaving hole
                else:
                    if self.world.level_wrapper.version >= 2730:
                        new_data = CompoundTag({})
                        new_data['Position'] = from_snbt(f'[I; {cx}, {cz}]')
                        new_data['DataVersion'] = IntTag(self.world.level_wrapper.version)
                        new_data['Entities'] = ListTag([])
                        new_data['Entities'].append(nbt_data)

                        self.Entities_region.put_chunk_data(cx % 32, cz % 32, new_data)
                        self.Entities_region.save()
                        print(f' 5 SAVED CHUNK NEW FILE file r.{rx}, {rz} Chunk: {cx}, {cz}')
                    else:
                        print(f' 6 NO CHUNK DATA file r.{rx}, {rz} Chunk: {cx} , {cz} ')  # #java less than version 2730
                        # can not store entities without leaving hole
            self.world.save()
            self._load_entitie_data('0', False, self.get_all_flag)

class EntitiePlugin(wx.Frame):
    def __init__(self, parent, canvas, world, *args, **kw):
        super(EntitiePlugin, self).__init__(parent, *args, **kw,
                                            style=(wx.MINIMIZE_BOX | wx.MAXIMIZE_BOX | wx.RESIZE_BORDER |
                                                   wx.SYSTEM_MENU | wx.CAPTION | wx.CLOSE_BOX | wx.CLIP_CHILDREN |
                                                   wx.FRAME_FLOAT_ON_PARENT),
                                            title="NBT Editor for Entities")

        self.parent = parent

        self.canvas = canvas
        self.world = world
        self.platform = self.world.level_wrapper.platform
        self.font = wx.Font(13, wx.FONTFAMILY_ROMAN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        self.SetForegroundColour((0, 255, 0))
        self.SetBackgroundColour((0, 0, 0))
        self.SetFont(self.font)
        self.SetMinSize((520, 720))
        self.lstOfE = ['This List will Contain', 'Entities', "NOTE: the TAB key",
                       " to toggle Perspective", "Canvas must be active", "Mouse over the canvas", "To activate canvas"]
        self.nbt_data = CompoundTag({})
        self.Freeze()
        self.EntyData = []
        self._highlight_edges = numpy.zeros((2, 3), dtype=bool)

        if self.platform == 'bedrock':
            self.operation = BedRock()
            self.operation.world = self.world
            self.operation.canvas = self.canvas
            self.operation.EntyData = self.EntyData

        else:
            self.operation = Java()
            self.operation.world = self.world
            self.operation.canvas = self.canvas
            self.operation.EntyData = self.EntyData
            self.operation.lstOfE = self.lstOfE

        self.operation.select_tracer = collections.defaultdict(list)
        self.get_all_flag = False
        self.operation.get_all_flag = self.get_all_flag

        self._sizer_v_main = wx.BoxSizer(wx.VERTICAL)
        self.left_sizer = wx.BoxSizer(wx.VERTICAL)
        self.right_sizer = wx.BoxSizer(wx.VERTICAL)

        self.bottom_h = wx.BoxSizer(wx.HORIZONTAL)
        self.top_sizer = wx.GridSizer(4, 3, 0, -1)
        self.button_group_one = wx.GridSizer(2, 2, 3, -10)
        self.button_group_two = wx.GridSizer(0, 3, 3, 1)
        self.button_group_three = wx.GridSizer(0, 2, 5, 5)
        self.button_group_four = wx.GridSizer(0, 4, 5, 5)

        self.SetSizer(self._sizer_v_main)
        self.operation.filter_include_label = wx.StaticText(self, label="Include:", size=(76, 25))
        self.operation.filter_exclude_label = wx.StaticText(self, label="Exclude:", size=(76, 25))
        self.operation.exclude_filter = wx.TextCtrl(self, style=wx.TE_LEFT, size=(120, 25))
        self.operation.include_filter = wx.TextCtrl(self, style=wx.TE_LEFT, size=(120, 25))

        self.button_group_four.Add(self.operation.filter_include_label,0, wx.TOP, -2)
        self.button_group_four.Add(self.operation.include_filter, 0, wx.LEFT, 21)
        self.button_group_four.Add(self.operation.filter_exclude_label,0, wx.TOP, -2)
        self.button_group_four.Add(self.operation.exclude_filter, 0, wx.LEFT, 21)
        self.font_ex_in = wx.Font(12, wx.FONTFAMILY_ROMAN, wx.FONTSTYLE_MAX, wx.FONTWEIGHT_BOLD)
        self.operation.exclude_filter.SetForegroundColour((0, 0, 0))
        self.operation.exclude_filter.SetBackgroundColour((255, 0, 0))
        self.operation.include_filter.SetForegroundColour((0, 0, 0))
        self.operation.include_filter.SetBackgroundColour((0, 255, 0))
        self.operation.include_filter.SetFont(self.font_ex_in)
        self.operation.exclude_filter.SetFont(self.font_ex_in)
        self.operation.exclude_filter.SetToolTip(".Seporate with a comma , "
                                                 "to exclude more that one, Dont use Filters together")

        self.operation.include_filter.SetToolTip("Seporate with a comma , "
                                                 "to enclude more that one, Dont use Filters together")

        self._sizer_v_main.Add(self.top_sizer)
        self._sizer_v_main.Add(self.button_group_four, 0, wx.TOP, 5)
        self._sizer_v_main.Add(self.bottom_h)
        self.font = wx.Font(11, wx.FONTFAMILY_ROMAN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)

        self.delete_selected = wx.Button(self, label="Delete All Selected")
        # self.list_dead = wx.Button(self, label="List Dead", size=(60, 20))
        # self.make_undead = wx.Button(self, label="Make UnDead", size=(80, 20))
        self.delete_unselected = wx.Button(self, label="Delete All Un_Selected")
        self._move = wx.Button(self, label="Move", size=(50, 24))
        self._copy = wx.Button(self, label="Copy", size=(50, 24))
        self._delete = wx.Button(self, label="Delete", size=(50, 24))
        self._get_button = wx.Button(self, label="Get Entities", size=(80, 30))
        self._get_all_button = wx.Button(self, label="Get All", size=(50, 30))
        self._get_all_button.SetToolTip("Get All Entities in the dimension and unselects any selections")
        self._get_button.SetToolTip("Get All Entities within the selected chunk area. "
                                    "Note: selection shows the hole chunk")
        self._set_button = wx.Button(self, label="Apply Changes")
        self.operation._imp_button = wx.Button(self, label="Import Entities")
        self.operation._exp_button = wx.Button(self, label="Export Entities")
        self._teleport_check = wx.CheckBox(self, label="Auto teleportation")
        self._teleport_check.SetValue(True)
        self._move.SetToolTip("Prepares the new position (from cords above) for the selected entitiy ")
        self._copy.SetToolTip("Prepares a copy of the entities and sets its location (from cords above)")
        self._delete.SetToolTip("Delete the selected entitie")
        self.delete_selected.SetToolTip(
            "Immediately Deletes All Selected areas with Entities From World, "
            "\n NOTE: There is No Undo, Also Entities may be stored in a different chunk , Be sure to have a Backup! ")
        self.delete_unselected.SetToolTip(
            "Immediately Deletes All Un_Selected Entities From World,  "
            "\n NOTE: There is No Undo, Also Entities may be stored in a different chunk , Be sure to have a Backup! ")

        self.delete_unselected.Bind(wx.EVT_BUTTON,
                                    lambda event: self.operation.delete_un_or_selected_entities(event, True))
        self.delete_selected.Bind(wx.EVT_BUTTON,
                                  lambda event: self.operation.delete_un_or_selected_entities(event, False))
        self._move.Bind(wx.EVT_BUTTON, lambda event: self.operation._move_copy_entitie_data(event, False))
        self._copy.Bind(wx.EVT_BUTTON, lambda event: self.operation._move_copy_entitie_data(event, True))
        self._delete.Bind(wx.EVT_BUTTON, lambda event: self.operation._delete_from_list(event))
        self._get_button.Bind(wx.EVT_BUTTON, lambda event: self.operation._load_entitie_data(event, False, False))
        self._get_all_button.Bind(wx.EVT_BUTTON, lambda event: self.operation._load_entitie_data(event, False, True))
        # self.list_dead.Bind(wx.EVT_BUTTON, lambda event: self.operation._list_the_dead(event))
        # self.make_undead.Bind(wx.EVT_BUTTON, lambda event: self.operation._make_undead(event))
        self._set_button.Bind(wx.EVT_BUTTON, lambda event: self.operation._save_data_to_world(event))
        self.operation._imp_button.Bind(wx.EVT_BUTTON, self.operation._imp_entitie_data)
        self.operation._exp_button.Bind(wx.EVT_BUTTON, self.operation._exp_entitie_data)

        self.operation._X = wx.TextCtrl(self, style=wx.TE_LEFT)  # "X of Selected")
        self.operation._Y = wx.TextCtrl(self, style=wx.TE_LEFT)  # "Y of Selected")
        self.operation._Z = wx.TextCtrl(self, style=wx.TE_LEFT)  # "Z of Selected")
        self.operation._X.SetForegroundColour((0, 255, 255))
        self.operation._Y.SetForegroundColour((255, 0, 0))
        self.operation._Z.SetForegroundColour((255, 255, 0))
        self.operation._X.SetBackgroundColour((255, 0, 0))
        self.operation._Y.SetBackgroundColour((0, 255, 0))
        self.operation._Z.SetBackgroundColour((0, 0, 255))
        self.operation._X.SetLabel("X of Selected")
        self.operation._Y.SetLabel("Y of Selected")
        self.operation._Z.SetLabel("Z of Selected")
        self.operation._X.SetFont(self.font_ex_in)
        self.operation._Y.SetFont(self.font_ex_in)
        self.operation._Z.SetFont(self.font_ex_in)

        self.top_sizer.Add(self.delete_unselected, 0, wx.TOP, 5)
        self.top_sizer.Add(self.operation._imp_button, 0, wx.TOP, 5)
        self.button_group_three.Add(self._get_button, 0, wx.TOP, 5)
        self.button_group_three.Add(self._get_all_button, 0, wx.TOP, 5)
        self.top_sizer.Add(self.button_group_three, 0, wx.TOP, 1)

        self.top_sizer.Add(self.delete_selected)

        self.top_sizer.Add(self.operation._exp_button)
        self.top_sizer.Add(self._set_button)

        self.top_sizer.Add(self.operation._X, 0, wx.TOP, -5)
        self.top_sizer.Add(self.operation._Y, 0, wx.TOP, -5)
        self.top_sizer.Add(self.operation._Z, 0, wx.TOP, -5)
        # self.del_ghosts = wx.Button(self, label="Delete All", size=(60, 20))
        # self.del_ghosts.SetToolTip("Delete all dead unlinked entities.")
        # self.del_ghosts.Bind(wx.EVT_BUTTON, lambda event: self.operation._delete_all_the_dead(event))
        # self.button_group_one.Add(self.list_dead)
        # self.button_group_one.Add(self.make_undead)
        # self.button_group_one.Add(self.del_ghosts)
        if self.world.level_wrapper.platform == "bedrock":
            if self.world.level_wrapper.version < (1, 18, 30, 4, 0):
                self.list_dead.Hide()
                # self.make_undead.Hide()
                # self.del_ghosts.Hide()
        elif self.world.level_wrapper.platform == "java":
            self.list_dead.Hide()
            # self.make_undead.Hide()
            # self.del_ghosts.Hide()
        self.top_sizer.Add(self.button_group_one, 0, wx.TOP, -10)
        self.top_sizer.Add(self._teleport_check, 0, wx.LEFT, 7)

        self.button_group_two.Add(self._move)
        self.button_group_two.Add(self._copy)
        self.button_group_two.Add(self._delete)
        self.top_sizer.Add(self.button_group_two)

        self.operation.ui_entitie_choice_list = wx.ListBox(self, style=wx.LB_HSCROLL, choices=self.lstOfE, pos=(0, 20),
                                                           size=(140, 800))
        self.operation.nbt_editor_instance = NBTEditor(self)
        self.bottom_h.Add(self.operation.nbt_editor_instance, 130, wx.EXPAND, 52)
        self.operation.ui_entitie_choice_list.SetFont(self.font)
        self.operation.ui_entitie_choice_list.Bind(wx.EVT_LISTBOX, lambda event: self.on_focus(event))

        self.bottom_h.Add(self.operation.ui_entitie_choice_list, 50, wx.RIGHT, 0)
        self.operation.ui_entitie_choice_list.SetBackgroundColour((0, 0, 0))
        self.operation.ui_entitie_choice_list.SetForegroundColour((255, 255, 0))

        self.bottom_h.Fit(self)
        self._sizer_v_main.Fit(self)
        self.Layout()
        self.Thaw()

        # self.nbt_editor_instance.Bind(wx.EVT_KEY_UP, self.autoSaveOnKeyPress)

    def bind_events(self):
        super().bind_events()
        self.canvas.Bind(EVT_SELECTION_CHANGE, self._set_new_block)
        self._selection.bind_events()
        self._selection.enable()

    def enable(self):
        # self.canvas.camera.projection_mode = Projection.TOP_DOWN
        self._selection = BlockSelectionBehaviour(self.canvas)
        self._selection.enable()

    def con_boc(self, caption="", message=""):  # message, yes Know
        r = wx.MessageDialog(
            self, message,
            caption,
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION
        ).ShowModal()
        if r != wx.ID_YES:
            return True
        else:
            return False

    def update_player_data(self, new_data):
        self_ = self.Parent.Parent
        # from_snbt(self.operation.EntyData[self.operation.ui_entitie_choice_list.GetSelection()])
        save_expanded = []
        f_root = self_.operation.nbt_editor_instance.tree.GetRootItem()
        r_c = self_.operation.nbt_editor_instance.tree.GetChildrenCount(f_root, 0)

        def get_full_path(child):
            tree = self_.operation.nbt_editor_instance.tree
            index = 0
            p_type = None
            the_sib_items = None
            nbt_path_keys = []
            if isinstance(tree.GetItemData(child), tuple):
                name, data = tree.GetItemData(child)
                nbt_path_keys.append(name)
            sibl = tree.GetItemParent(child)
            while sibl.IsOk():
                the_sib_items = sibl
                if isinstance(tree.GetItemData(sibl), tuple):
                    p_type = type(tree.GetItemData(sibl)[1])
                else:
                    p_type = tree.GetItemData(sibl)

                if p_type == ListTag or p_type == CompoundTag:

                    item_num = tree.GetChildrenCount(sibl, recursively=False)
                    f_child, f_c = tree.GetFirstChild(sibl)
                    f_item = child
                    for c in range(item_num):
                        if f_child == f_item:
                            index = c
                            break
                        f_child, f_c = tree.GetNextChild(f_child, f_c)
                    nbt_path_keys.append(index)
                if isinstance(tree.GetItemData(sibl), tuple):
                    nname, ddata = tree.GetItemData(sibl)
                    nbt_path_keys.append(nname)
                sibl = tree.GetItemParent(sibl)
            nbt_path_keys.reverse()
            return nbt_path_keys[1:]

        def root_path(child):
            tree = self_.operation.nbt_editor_instance.tree
            nbt_path_keys = []
            if isinstance(tree.GetItemData(child), tuple):
                name, data = tree.GetItemData(child)
                nbt_path_keys.append(name)
            sibl = tree.GetItemParent(child)
            while sibl.IsOk():
                if isinstance(tree.GetItemData(sibl), tuple):
                    nname, ddata = tree.GetItemData(sibl)
                    if ddata == ListTag:
                        index = 0
                        item_num = tree.GetChildrenCount(sibl, recursively=False)
                        f_child, f_c = tree.GetFirstChild(sibl)
                        f_item = child
                        f_par = tree.GetItemParent(f_item)
                        if len(nbt_path_keys) > 0:
                            for xx in range(len(nbt_path_keys) - 1):
                                f_par = tree.GetItemParent(f_par)
                        else:
                            f_par = child
                        for c in range(item_num):
                            if f_child == f_par:
                                index = c
                                nbt_path_keys.append(index)
                            f_child, f_c = tree.GetNextChild(f_child, f_c)
                    nbt_path_keys.append(nname)
                sibl = tree.GetItemParent(sibl)
            nbt_path_keys.reverse()
            return nbt_path_keys[1:]

        def recurtree(item):
            # for c in range(r_c):
            if item.IsOk():
                i_c = self_.operation.nbt_editor_instance.tree.GetChildrenCount(item, recursively=True)
                f_ic, cc_i = self_.operation.nbt_editor_instance.tree.GetFirstChild(item)
                for ci in range(i_c):
                    if f_ic.IsOk():

                        if self_.operation.nbt_editor_instance.tree.IsExpanded(f_ic):
                            save_expanded.append(copy.copy(root_path(f_ic)))
                        if self_.operation.nbt_editor_instance.tree.GetChildrenCount(f_ic) > 0:
                            recurtree(f_ic)
                    f_ic, cc_i = self_.operation.nbt_editor_instance.tree.GetNextChild(f_ic, cc_i)

        recurtree(f_root)
        current_scr_h = self_.operation.nbt_editor_instance.tree.GetScrollPos(orientation=wx.VERTICAL)

        self_.bottom_h.Detach(self_.operation.nbt_editor_instance)
        self_.bottom_h.Detach(self_.operation.ui_entitie_choice_list)
        self_.operation.nbt_editor_instance.Hide()
        NBTEditor.close(self_.operation.nbt_editor_instance, None, self_.GetParent())
        self_.operation.nbt_editor_instance = NBTEditor(self_, new_data)
        self_.bottom_h.Add(self_.operation.nbt_editor_instance, 130, wx.EXPAND, 21)
        self_.bottom_h.Add(self_.operation.ui_entitie_choice_list, 50, wx.RIGHT, 0)

        self_.nbt_editor_instance = NBTEditor(self_, new_data)
        root = self_.operation.nbt_editor_instance.tree.GetRootItem()
        first_c, c = self_.operation.nbt_editor_instance.tree.GetFirstChild(root)

        def re_expand(item):
            if item.IsOk():
                i_c = self_.operation.nbt_editor_instance.tree.GetChildrenCount(item)
                f_ic, cc_i = self_.operation.nbt_editor_instance.tree.GetFirstChild(item)
                for ci in range(i_c):
                    if f_ic.IsOk():
                        if root_path(f_ic) in save_expanded:
                            self_.operation.nbt_editor_instance.tree.Expand(f_ic)
                        if self_.operation.nbt_editor_instance.tree.GetChildrenCount(f_ic) > 0:
                            re_expand(f_ic)
                    f_ic, cc_i = self_.operation.nbt_editor_instance.tree.GetNextChild(f_ic, cc_i)

        self_.operation.nbt_editor_instance.tree.Expand(first_c)
        re_expand(root)
        self_.operation.nbt_editor_instance.tree.SetScrollPos(wx.VERTICAL, current_scr_h)
        self_.bottom_h.Layout()
        self_.bottom_h.Fit(self_)
        self_._sizer_v_main.Fit(self_)
        self_._sizer_v_main.Layout()
        self_.Fit()
        self_.Layout()

        self.Close()

    def get_dir_path(self, foldername, cx, cz):
        return os.path.join(os.getcwd(), "plugins", "operations", foldername,
                            "chunk_bk_up" + str(cx) + "." + str(cz) + ".txt")

    def create_saved_entities_dir(self, foldername):
        if not os.path.exists(os.path.join(os.getcwd(), "plugins", "operations", foldername)):
            os.makedirs(os.path.join(os.getcwd(), "plugins", "operations", foldername))
            print("Created Save Dir")

    def Onmsgbox(self, caption, message):  # message
        wx.MessageBox(message, caption, wx.OK | wx.ICON_INFORMATION)

    def autoSaveOnKeyPress(self, _):

        selection = self.operation.ui_entitie_choice_list.GetSelection()
        # newData = self.operation.nbt_editor_instance.GetValue()
        try:
            self.operation.EntyData[selection] = NBTFile(from_snbt(newData))
        except:
            self.Onmsgbox("syntax error", "Try agian")
            setdata = self.operation.EntyData[selection]
            # try:
            #     self.operation.nbt_editor_instance.SetValue(from_snbt(setdata).to_snbt(1))
            # except:
            #     self.operation.nbt_editor_instance.SetValue(setdata.to_snbt(1))

    def on_focus(self, evt):

        setdata = from_snbt(self.operation.EntyData[self.operation.ui_entitie_choice_list.GetSelection()])
        self.bottom_h.Detach(self.operation.nbt_editor_instance)
        self.bottom_h.Detach(self.operation.ui_entitie_choice_list)
        self.operation.nbt_editor_instance.Hide()
        NBTEditor.close(self.operation.nbt_editor_instance, evt, self.GetParent())
        self.operation.nbt_editor_instance = NBTEditor(self, setdata)
        self.bottom_h.Add(self.operation.nbt_editor_instance, 130, wx.EXPAND, 21)
        self.bottom_h.Add(self.operation.ui_entitie_choice_list, 50, wx.RIGHT, 0)
        self.bottom_h.Layout()
        self.bottom_h.Fit(self)
        self._sizer_v_main.Fit(self)
        self._sizer_v_main.Layout()
        self.Fit()
        self.Layout()

        # self.operation.nbt_editor_instance.SetValue(setdata.to_snbt(1))
        # self.operation.nbt_editor_instance.
        (x, y, z) = setdata.get('Pos')[0], setdata.get('Pos')[1], setdata.get('Pos')[2]
        self.operation._X.SetLabel(str(x).replace("f", " X").replace("d", " X"))
        self.operation._Y.SetLabel(str(y).replace("f", " Y").replace("d", " Y"))
        self.operation._Z.SetLabel(str(z).replace("f", " Z").replace("d", " Z"))
        X = int(str(self.operation._X.GetValue()).replace(" X", "").split(".")[0])
        Y = int(str(self.operation._Y.GetValue()).replace(" Y", "").split(".")[0])
        Z = int(str(self.operation._Z.GetValue()).replace(" Z", "").split(".")[0])
        blockPosdata = {}
        group = []
        xx, zz = 1, 1
        v = (
            (X),
            (Y),
            (Z))
        if X < 0:
            xx = -1
        if Z < 0:
            zz = -1
        vv = ((X + xx),
              (Y + 1),
              (Z + zz))
        group.append(SelectionBox(v, vv))
        sel = SelectionGroup(group)
        self.canvas.selection.set_selection_group(sel)
        if self._teleport_check.GetValue():
            x, y, z = (x, y, z)
            self.canvas.camera.set_location((x, Y + 10, z))
            self.canvas.camera.set_rotation((34.720000000000006, 90))
            self.canvas.camera._notify_moved()

    def _refresh_chunk(self, dimension, world, x, z):
        self.world.level_wrapper.load_chunk(x, z, dimension).changed = True
        self.world.create_undo_point()

    def _undo_it(self, _):
        cx, cz = block_coords_to_chunk_coords(self.canvas.selection.selection_group.selection_boxes[0].min_x,
                                              self.canvas.selection.selection_group.selection_boxes[0].min_z)
        enty = self.canvas.world.get_native_entities(cx, cz, self.canvas.dimension)

    def _set_new_block(self, _):
        if self.canvas.selection.selection_group:
            if 'Y of Selected' not in self.operation._Y.GetValue():
                fx = float(self.operation._X.GetValue().replace(" X", ""))
                fy = float(self.operation._Y.GetValue().replace(" Y", ""))
                fz = float(self.operation._Z.GetValue().replace(" Z", ""))
                s_x_, s_y_, s_z_ = self.canvas.selection.selection_group.max
                self.operation._X.SetLabel(str(s_x_) + "." + str(fx).split('.')[1] + " X")
                self.operation._Y.SetLabel(str(s_y_) + "." + str(fy).split('.')[1] + " Y")
                self.operation._Z.SetLabel(str(s_z_) + "." + str(fz).split('.')[1] + " Z")

    def save_entities_export(self, snbt_list):

        pathto = ""
        fname = "one entity per line.snbt"
        fdlg = wx.FileDialog(self, "Export Entities", "", "",
                             f"SNBT (*.snbt_{self.world.level_wrapper.platform})|*.*", wx.FD_SAVE)
        if fdlg.ShowModal() == wx.ID_OK:
            pathto = fdlg.GetPath()
        else:
            return False
        if ".snbt" not in pathto:
            pathto = pathto + ".snbt"
        with open(pathto, "w") as tfile:
            tfile.write(snbt_list)
            tfile.close()
        return True

    def load_entities_export(self):
        snbt_list = []
        fdlg = wx.FileDialog(self, "Import Entities", "", "",
                             f"SNBT (*.snbt_{self.world.level_wrapper.platform})|*.*", wx.FD_OPEN)
        if fdlg.ShowModal() == wx.ID_OK:
            pathto = fdlg.GetPath()
        else:
            return
        with open(pathto, "r") as tfile:
            snbt_list = tfile.readlines()
            tfile.close()
        return snbt_list

    def important_question(self):
        dialog = wx.MessageDialog(self, "   Including entities directly edits the world and there is no (Ctrl-Z ) Undo."
                                        "\n Would you like to save any current pending changes or discard them?"
                                        "\n     This needs to remove all current undo points"
                                        "\n To prevent conflicts that could occur"
                                        "\n    I suggest making a .snbt list all chunk entities export, "
                                        "\nso you can start over easy."
                                        "\nWhat do you wish to do?", "NOTICE",
                                  wx.ICON_EXCLAMATION | wx.YES_NO | wx.CANCEL | wx.CANCEL_DEFAULT)
        dialog.SetYesNoLabels('Save changes', 'Discard changes')
        responce = dialog.ShowModal()
        dialog.Destroy()
        if responce == wx.ID_YES:
            self.world.save()
            self.world.purge()
            pass
        elif responce == wx.ID_NO:
            self.world.purge()
            pass
        else:
            return False
        pass

class DataPopOutFrame(wx.Frame):
    def __init__(self, parent, found_data, page, platform, canvas, world):
        super().__init__(parent, title="Data Viewer", size=(600, 600), style=wx.DEFAULT_FRAME_STYLE | wx.STAY_ON_TOP)
        self.canvas = canvas
        self.world = world
        self.found_data = found_data
        self.page = page
        self.platform = platform
        parent_position = parent.GetScreenPosition()
        self.SetPosition(parent_position + (50, 50))
        self.InitUI()

    def InitUI(self):
        self._the_data = wx.grid.Grid(self, size=(540, 540), style=5)

        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self.sizer)
        self.above_grid = wx.BoxSizer(wx.HORIZONTAL)
        self.sizer.Add(self.above_grid, 0, wx.ALL, 5)
        self.sizer.Add(self._the_data, 1, wx.EXPAND | wx.ALL, 5)

        self.check_for_pages()

        if self.platform == 'java':
            self._the_data.HideCol(4)

        self.Layout()

    def pageContol(self, page):
        if page:
            self.resetData(page)

        def OnClick(event):
            self.Freeze()
            self.resetData(int(event.GetString()))
            self.Thaw()

        return OnClick

    def hide_columns(self, columns_to_hide):
        def OnClick(event):
            hide = event.IsChecked()
            for col in columns_to_hide:
                if hide:
                    self._the_data.ShowCol(col)
                else:
                    self._the_data.HideCol(col)
            self._the_data.ForceRefresh()

        return OnClick

    def resetData(self, page):
        try:
            self.sizer.Detach(self._the_data)
            self._the_data.Hide()
            self._the_data.Destroy()
            self._the_data = wx.grid.Grid(self, size=(540, 540), style=5)
        except:
            pass

        tableCount = len(self.found_data.get_page(page))
        self._the_data.CreateGrid(tableCount, 6)
        self._the_data.SetRowLabelSize(0)
        self._the_data.SetColLabelValue(0, "x")
        self._the_data.SetColLabelValue(1, "y")
        self._the_data.SetColLabelValue(2, "z")
        self._the_data.SetColLabelSize(20)
        self._the_data.SetColLabelValue(3, "Block")
        self._the_data.SetColLabelValue(4, "Extra_Block")
        self._the_data.SetColLabelValue(5, "Entity Data")

        for ind, (xyz, data) in enumerate(self.found_data.get_page(page).items()):
            self._the_data.SetCellValue(ind, 0, str(xyz[0]))
            self._the_data.SetCellValue(ind, 1, str(xyz[1]))
            self._the_data.SetCellValue(ind, 2, str(xyz[2]))
            self._the_data.SetCellBackgroundColour(ind, 0, "#ef476f")
            self._the_data.SetCellBackgroundColour(ind, 1, "#06d6a0")
            self._the_data.SetCellBackgroundColour(ind, 2, "#118ab2")
            self._the_data.SetCellValue(ind, 3, data['block_data'].to_snbt(1))
            self._the_data.SetCellBackgroundColour(ind, 3, "#8ecae6")
            self._the_data.SetCellValue(ind, 4, data['extra_block'].to_snbt(1))
            self._the_data.SetCellValue(ind, 5, data['entity_data'].to_snbt(1))

        self._the_data.Bind(wx.grid.EVT_GRID_CELL_RIGHT_CLICK, self.gridClick)
        self._the_data.Bind(wx.grid.EVT_GRID_CELL_LEFT_CLICK, self.gridClick)

        self.sizer.Add(self._the_data, 1, wx.EXPAND | wx.ALL, 5)
        self._the_data.Fit()
        self._the_data.Show()
        self.Layout()

    def check_for_pages(self):
        try:
            for item in self.above_grid.GetChildren():
                window = item.GetWindow()
                if window:
                    window.Hide()
                    window.Destroy()
                else:
                    self.sizer.Detach(item)
        except:
            pass

        pages = self.found_data.paginate(500)
        if pages > 1:
            self.p_label = wx.StaticText(self, label="Pages:")
            self.lpage = wx.Choice(self, choices=[])
            self.lpage.AppendItems([str(x) for x in range(1, pages + 1)])
            self.lpage.Bind(wx.EVT_CHOICE, self.pageContol(None))
            self.lpage.SetSelection(0)

            self.c_label = wx.StaticText(self, label="Show Columns:         ")
            self.hide_xyz = wx.CheckBox(self, label="X,Y,Z")
            self.hide_block = wx.CheckBox(self, label="Block")
            self.hide_extra = wx.CheckBox(self, label="Extra_block ")
            self.hide_entity = wx.CheckBox(self, label="Entity Data")
            self.hide_xyz.SetValue(True)
            self.hide_block.SetValue(True)
            self.hide_extra.SetValue(True)
            self.hide_entity.SetValue(True)
            if self.platform == 'java':
                self.hide_extra.Hide()
            self.hide_xyz.Bind(wx.EVT_CHECKBOX, self.hide_columns([0, 1, 2]))
            self.hide_block.Bind(wx.EVT_CHECKBOX, self.hide_columns([3]))
            self.hide_extra.Bind(wx.EVT_CHECKBOX, self.hide_columns([4]))
            self.hide_entity.Bind(wx.EVT_CHECKBOX, self.hide_columns([5]))
            self.above_grid.Add(self.c_label, 0, wx.LEFT, 0)
            self.above_grid.Add(self.hide_xyz, 0, wx.LEFT, 0)
            self.above_grid.Add(self.hide_block, 0, wx.LEFT, 0)
            self.above_grid.Add(self.hide_extra, 0, wx.LEFT, 0)
            self.above_grid.Add(self.hide_entity, 0, wx.LEFT, 0)
            self.above_grid.Add(self.p_label, 0, wx.LEFT, 0)
            self.above_grid.Add(self.lpage, 0, wx.LEFT, 0)

            self.pageContol(1)
            self.Layout()
        else:
            self.c_label = wx.StaticText(self, label="Show Columns: ")
            self.hide_xyz = wx.CheckBox(self, label="X,Y,Z")
            self.hide_block = wx.CheckBox(self, label="Block")
            self.hide_extra = wx.CheckBox(self, label="Extra_block ")
            self.hide_entity = wx.CheckBox(self, label="Entity Data")
            self.hide_xyz.SetValue(True)
            self.hide_block.SetValue(True)
            self.hide_extra.SetValue(True)
            self.hide_entity.SetValue(True)
            if self.platform == 'java':
                self.hide_extra.Hide()
            self.hide_xyz.Bind(wx.EVT_CHECKBOX, self.hide_columns([0, 1, 2]))
            self.hide_block.Bind(wx.EVT_CHECKBOX, self.hide_columns([3]))
            self.hide_extra.Bind(wx.EVT_CHECKBOX, self.hide_columns([4]))
            self.hide_entity.Bind(wx.EVT_CHECKBOX, self.hide_columns([5]))
            self.above_grid.Add(self.c_label, 0, wx.LEFT, 0)
            self.above_grid.Add(self.hide_xyz, 0, wx.LEFT, 0)
            self.above_grid.Add(self.hide_block, 0, wx.LEFT, 0)
            self.above_grid.Add(self.hide_extra, 0, wx.LEFT, 0)
            self.above_grid.Add(self.hide_entity, 0, wx.LEFT, 0)

            self.pageContol(1)
            self.Layout()

    def copy_text_to_find(self, _):
        self.Parent.textF.SetValue(self.textGrid.GetValue())

    def copy_text_to_replace(self, _):
        self.Parent.textR.SetValue(self.textGrid.GetValue())

    def ex_save_close(self, r, c, x, y, z):
        sub_keys = [x, y, z, 'block_data', 'extra_block', 'entity_data']

        def OnClick(event):
            if c < 3:
                pass
            else:
                val = self.textGrid.GetValue()
                self._the_data.SetCellValue(r, c, val)
                data = self.found_data.get_data()
                key = (int(x), int(y), int(z))
                block_data, extra_block, entity_data = data[key]['block_data'], data[key]['extra_block'], data[key][
                    'entity_data']
                new_dict = {'x': x, 'y': y, 'z': z, 'block_data': block_data, 'extra_block': extra_block,
                            'entity_data': entity_data}
                new_dict[sub_keys[c]] = self.Parent.test_nbt(val)
                new_dict.pop('x')
                new_dict.pop('y')
                new_dict.pop('z')
                if data[key][sub_keys[c]] != self.Parent.test_nbt(val):
                    data[key] = new_dict
            self.frame.Close()

        return OnClick

    def gridClick(self, event):
        try:
            self.frame.Hide()
            self.frame.Close()
        except:
            pass

        ox, oy, oz = self.canvas.camera.location

        x, y, z = (self._the_data.GetCellValue(event.Row, 0),
                   self._the_data.GetCellValue(event.Row, 1),
                   self._the_data.GetCellValue(event.Row, 2))
        xx, yy, zz = float(x), float(y), float(z)

        def goto(_):
            self.canvas.camera.set_location((xx, yy + 25, zz))
            self.canvas.camera._notify_moved()

        def gobak(_):
            self.canvas.camera.set_location((ox, oy, oz))
            self.canvas.camera._notify_moved()

        self.frame = wx.Frame(self, id=wx.ID_ANY, pos=wx.DefaultPosition, size=(425, 400),
                              style=(
                                      wx.MINIMIZE_BOX | wx.MAXIMIZE_BOX | wx.RESIZE_BORDER
                                      | wx.SYSTEM_MENU | wx.CAPTION | wx.CLOSE_BOX
                                      | wx.CLIP_CHILDREN | wx.FRAME_FLOAT_ON_PARENT | wx.STAY_ON_TOP),
                              name="Panel",
                              title="Cell (Row: " + str(event.GetRow()) + " Col: " + str(event.GetCol()) + ")")
        self.font = wx.Font(14, wx.FONTFAMILY_ROMAN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        self.frame.SetFont(self.font)
        self.frame.SetForegroundColour((0, 255, 0))
        self.frame.SetBackgroundColour((0, 0, 0))
        self.frame.Centre(direction=wx.VERTICAL)
        row, col = event.GetRow(), event.GetCol()
        sizer_P = wx.BoxSizer(wx.VERTICAL)
        sizer_H = wx.BoxSizer(wx.HORIZONTAL)
        sizer_H2 = wx.BoxSizer(wx.HORIZONTAL)
        self.frame.SetSizer(sizer_P)
        save_close = wx.Button(self.frame, label="Save_Close")
        save_close.Bind(wx.EVT_BUTTON, self.ex_save_close(row, col, x, y, z))
        sizer_P.Add(sizer_H)
        sizer_P.Add(sizer_H2)

        self.textGrid = wx.TextCtrl(self.frame, style=wx.TE_MULTILINE | wx.TE_BESTWRAP, size=(400, 550))
        copy_to_find = wx.Button(self.frame, label="Copy To Find")
        copy_to_find.Bind(wx.EVT_BUTTON, self.copy_text_to_find)
        copy_to_replace = wx.Button(self.frame, label="Copy To Replace")
        goto_button = wx.Button(self.frame, label="Go to Location")
        goto_button.Bind(wx.EVT_BUTTON, goto)
        gobak_button = wx.Button(self.frame, label="Go Back to old Location")
        gobak_button.Bind(wx.EVT_BUTTON, gobak)
        copy_to_replace.Bind(wx.EVT_BUTTON, self.copy_text_to_replace)
        sizer_H.Add(save_close)
        sizer_H.Add(copy_to_find)
        sizer_H.Add(copy_to_replace)

        sizer_H2.Add(goto_button, 0, wx.TOP, 20)
        sizer_H2.Add(gobak_button, 0, wx.TOP, 20)
        sizer_P.Add(self.textGrid)

        if event.GetCol() < 3:
            self.textGrid.SetValue(f'Block location: {x, y, z}\nyour old location: {ox, oy, oz}')
            self.canvas.camera.set_location((xx, yy + 25, zz))
            self.canvas.camera._notify_moved()
            save_close.SetLabel("Close")
        else:
            self.textGrid.SetValue(self._the_data.GetCellValue(row, col))
        self.frame.Show(True)
        save_close.Show(True)

class ProgressBar:
    def __init__(self):
        self.parent = None
        self.prog = None
        self.pos_start = False

    def progress_bar(self, total, cnt, title=None, text=None, update_interval=50):
        """Manage progress bar updates."""
        if self.prog and self.prog.WasCancelled():
            self.stop()
            return True
        update, start = False, False

        if cnt > 0:
            cnt -= 1
            self.pos_start = True

        if cnt == 0:
            start = True
            update = False
        elif cnt > 0:
            start = False
            update = True
        if self.pos_start:
            cnt += 1

        if start:
            self.start_progress(total, cnt, title, text, update_interval)
            return None

        if update:
            if self.prog and self.prog.WasCancelled():
                self.stop()
                return True
            else:
                return self.update_progress(cnt, total, title, text, update_interval)

        return False

    def stop(self):
        if self.prog:
            self.prog.Hide()
            self.prog.Destroy()
        return True

    def start_progress(self, total, cnt, title, text, update_interval):
        """Start the progress dialog."""
        if total > update_interval:
            self.prog = wx.ProgressDialog(
                f"{title}",
                f"{text}: {cnt} / {total}\n  ", total,
                style=wx.PD_AUTO_HIDE | wx.PD_CAN_ABORT | wx.PD_ELAPSED_TIME | wx.PD_REMAINING_TIME,
                parent=self.parent
            )
            self.prog.Show(True)

    def update_progress(self, cnt, total, title, text, update_interval):
        """Update the progress dialog."""
        if cnt % update_interval == 0 or cnt == total:
            if self.prog:
                if self.prog.WasCancelled():
                    self.prog.Destroy()
                    return True
                else:
                    self.prog.Update(cnt, f"{text}: {cnt} / {total}\n  ")

        return False

class ProcessAnvilBD:
    def __init__(self, found_data, parent=None, world=None, canvas=None):
        self.pause_count = None
        self.parent = parent
        self.found_data = found_data
        self.p_bar = ProgressBar()
        self.canvas = canvas
        self.world = world
        self.search = ''

    def get_dim_vpath_java_dir(self, regonx, regonz):
        file = "r." + str(regonx) + "." + str(regonz) + ".mca"
        path = self.world.level_wrapper.path
        full_path = ''
        dim = ''
        if 'minecraft:the_end' in self.canvas.dimension:
            dim = 'DIM1'
        elif 'minecraft:the_nether' in self.canvas.dimension:
            dim = 'DIM-1'
        elif 'minecraft:overworld' in self.canvas.dimension:
            dim = ''

        print(self.canvas.dimension)
        version = "region"
        full_path = os.path.join(path, dim, version, file)
        return full_path

    def progress_bar(self, total, cnt, title=None, text=None, update_interval=50):
        return self.p_bar.progress_bar(total, cnt, title=title, text=text, update_interval=update_interval)

    def search_raw(self, block_search_keys, block_e_search_keys, search, mode, chunks_done=None):

        chunks = None
        self.found_data.clear()
        if mode <= 1:
            if chunks_done:
                chunks = [(xx, zz)
                          for (xx, zz) in self.canvas.selection.selection_group.chunk_locations()
                          if (xx, zz) not in chunks_done]
            else:
                chunks = [(xx, zz) for (xx, zz) in self.canvas.selection.selection_group.chunk_locations()]
        elif mode == 2:
            if chunks_done:
                self.found_data.clear()
                chunks = [(xx, zz) for (xx, zz) in self.world.all_chunk_coords(self.canvas.dimension)
                          if (xx, zz) not in chunks_done]
            else:
                chunks = [(xx, zz) for (xx, zz) in self.world.all_chunk_coords(self.canvas.dimension)]

        total = len(chunks)
        cnt = 0
        chunk_done = set()
        chunk_pause = None
        location_dict = collections.defaultdict(list)

        for xx, zz in chunks:
            rx, rz = chunk_coords_to_region_coords(xx, zz)
            location_dict[(rx, rz)].append((xx, zz))

        for rx, rz in location_dict.keys():
            data = AnvilRegionInterface(self.get_dim_vpath_java_dir(rx, rz), mcc=True)
            for cx, cz in location_dict[(rx, rz)]:

                nbtdata = data.get_data(cx % 32, cz % 32)
                for be in nbtdata['block_entities']:
                    if any(item.lower() in be.to_snbt().lower() for item in block_e_search_keys):
                        x, y, z = be.get('x').py_int, be.get('y').py_int, be.get('z').py_int
                        if be.get('id').py_str.lower() not in str(block_search_keys):
                            block_search_keys.append(be.get('id').py_str.lower())
                        if mode == 0 and (x, y, z) in self.canvas.selection.selection_group.blocks:
                            self.found_data.set_data(x, y, z, CompoundTag({}), CompoundTag({}), be,
                                                     create_backup=True)
                        elif mode > 0:
                            self.found_data.set_data(x, y, z, CompoundTag({}), CompoundTag({}), be,
                                                     create_backup=True)

                for sec in nbtdata.get('sections'):
                    level = sec['Y'].py_int

                    if sec.get('block_states', None):
                        palette = sec['block_states'].get('palette', None)
                        for nbt in palette:
                            if any(item.lower() in nbt.to_snbt(1).lower() for item in block_search_keys):
                                p_data = sec['block_states'].get('data', None)
                                palette_length = len(palette) - 1
                                bits_per_entry = max(palette_length.bit_length(), 4)

                                if p_data is not None:
                                    arr = decode_long_array(p_data.py_data, 16 * 16 * 16,
                                                            bits_per_entry=bits_per_entry, dense=False)
                                    arr = arr.reshape(16, 16, 16).swapaxes(0, 2).swapaxes(1, 2)
                                else:
                                    arr = numpy.zeros((16, 16, 16), dtype=int)

                                for bit, block in enumerate(palette):
                                    if any(item.lower() in block.to_snbt(1).lower() for item in block_search_keys):
                                        indices = numpy.where(arr == bit)
                                        cords = list(zip(*indices))
                                        xc, xy, xz = cx * 16, level * 16, cz * 16

                                        for x, y, z in cords:
                                            kx, ky, kz = (x + xc, xy + y, z + xz)
                                            existing_data = self.found_data.get((kx, ky, kz))
                                            entity_data = existing_data.get(
                                                'entity_data') if existing_data else CompoundTag({})
                                            if mode == 0 and (
                                                    kx, ky, kz) in self.canvas.selection.selection_group.blocks:
                                                self.found_data.set_data(kx, ky, kz, block, CompoundTag({}),
                                                                         entity_data,
                                                                         create_backup=True)
                                            elif mode > 0:
                                                self.found_data.set_data(kx, ky, kz, block, CompoundTag({}),
                                                                         entity_data, create_backup=True)

                chunk_done.add((cx, cz))
                cnt += 1
                pause_cnt = self.pause_count
                found_blocks = len(self.found_data.get_data())
                self.status = self.progress_bar(total, cnt, title='Searching....',
                                                text=f'{search} found: {found_blocks}.. pause after: {pause_cnt} \n'
                                                     f' Cancel will also pause and allow you to continue')
                if self.status:
                    break
                if found_blocks > pause_cnt:
                    chunk_pause = True
                    self.progress_bar(total, total, text=search)
                    break

        if len(self.found_data.get_data()) > 0:

            if chunk_pause or self.status:
                return chunk_done, self.found_data
            else:
                return chunk_pause, self.found_data
        else:
            return None, None

    def get_blocks_by_locations(self, data):

        new_data = UniqueObjectDict()
        location_dict = collections.defaultdict(lambda: collections.defaultdict(list))
        total = data.get_keys_len()
        cnt = 0
        for x, y, z in data.keys():
            xx, yy, zz = block_coords_to_chunk_coords(x, y, z)
            rx, rz = chunk_coords_to_region_coords(xx, zz)

            if (xx, yy, zz) in location_dict[(rx, rz)]:
                location_dict[(rx, rz)][(xx, yy, zz)].append((x, y, z))
            else:
                location_dict[(rx, rz)][(xx, yy, zz)] = [(x, y, z)]

        # self.progress_bar(total, cnt, update_interval=1000)
        for (rx, rz), chunk_data in location_dict.items():
            data = AnvilRegionInterface(self.get_dim_vpath_java_dir(rx, rz), mcc=True)

            for (cx, cy, cz), block_locations in chunk_data.items():  #
                nbtdata = data.get_data(cx % 32, cz % 32)

                for sec in nbtdata.get('sections'):
                    level = sec['Y'].py_int
                    if level == cy:

                        be_loc = collections.defaultdict(list)
                        for be in nbtdata['block_entities']:
                            x, y, z = be.get('x').py_int, be.get('y').py_int, be.get('z').py_int
                            for xx, yy, zz in block_locations:
                                if (x, y, z) == (xx, yy, zz):
                                    be_loc[(x, y, z)] = be
                                else:
                                    be_loc[(x, y, z)] = CompoundTag({})

                        if sec.get('block_states', None):
                            if sec['block_states'].get('palette', None):
                                if sec['block_states'].get('data', None):
                                    for xx, yy, zz in block_locations:
                                        palette = sec['block_states'].get('palette', None)
                                        p_data = sec['block_states'].get('data', None)
                                        palette_length = len(palette) - 1
                                        bits_per_entry = max(palette_length.bit_length(), 4)
                                        arr = decode_long_array(p_data.py_data, 16 * 16 * 16,
                                                                bits_per_entry=bits_per_entry, dense=False)
                                        arr = arr.reshape(16, 16, 16).swapaxes(0, 2).swapaxes(1, 2)
                                        block_nbt = palette[arr[xx % 16][yy % 16][zz % 16]]
                                        new_data[(xx, yy, zz)] = {'block_data': block_nbt,
                                                                  "extra_block": CompoundTag({}),
                                                                  "entity_data": be_loc[xx, yy, zz]}
                                        cnt += 1
                                        close = self.progress_bar(total, cnt, title='Matching Blocks',
                                                                  text='Current Progress', update_interval=10000)
                                        if close:
                                            break
        self.found_data.backup = new_data

    def fast_apply(self, old=None, new=None, mode=None, name=None, ex_old=None, ex_new=None, ex_name=None):

        if mode == 0:
            return

        if mode == 1:
            chunks = [(xx, zz) for (xx, zz) in self.canvas.selection.selection_group.chunk_locations()]
        elif mode == 2:
            chunks = [(xx, zz) for (xx, zz) in self.world.all_chunk_coords(self.canvas.dimension)]
        else:
            raise ValueError("Invalid mode value")
        no_property_mode = False
        if old.get('Properties', None) == "*":
            no_property_mode = True
        total = len(chunks)
        cnt = 0
        region_dict = collections.defaultdict(list)

        for (chunk_x, chunk_z) in chunks:
            region_x, region_z = chunk_coords_to_region_coords(chunk_x, chunk_z)
            region_dict[(region_x, region_z)].append((chunk_x, chunk_z))

        for (region_coords, chunk_list) in region_dict.items():
            region_x, region_z = region_coords
            world_data = AnvilRegion(self.get_dim_vpath_java_dir(region_x, region_z))

            for (chunk_x, chunk_z) in chunk_list:

                world_nbt = None
                try:
                    world_nbt = world_data.get_chunk_data(chunk_x % 32, chunk_z % 32)
                except ChunkDoesNotExist:
                    print(chunk_x % 32, chunk_z % 32, "Does NOT exist")
                    pass
                except ChunkLoadError:
                    print(chunk_x % 32, chunk_z % 32, "Error Loading")
                    pass
                change = False
                if world_nbt:

                    for section in world_nbt.get('sections', []):
                        palette = None
                        if section.get('block_states', None):
                            palette = section['block_states'].get('palette', None)

                        if palette:
                            if no_property_mode:
                                old_snbt = old.get('Name').to_snbt()
                            else:
                                old_snbt = old.to_snbt()
                            if old_snbt in palette.to_snbt():
                                for i, block in enumerate(palette):
                                    if no_property_mode:
                                        if block.get('Name') == old.get('Name'):
                                            change = True
                                            palette[i] = new
                                    else:
                                        if block == old:
                                            change = True
                                            palette[i] = new

                                section['block_states']['palette'] = palette
                if change:
                    world_data.put_chunk_data(chunk_x % 32, chunk_z % 32, world_nbt)
                cnt += 1
                self.progress_bar(total, cnt, text="Chunk Progress...", title='Replacing Blocks')

            world_data.save()
            world_data.unload()

    def apply(self, mode):

        new_data = self.found_data.get_data()
        old_data = self.found_data.get_copy()
        changed_chunks = UniqueObjectDict()

        for key in old_data.keys():
            if key in new_data and new_data[key] != old_data[key]:
                changed_chunks[key] = {**new_data[key], "old_block": old_data[key]["block_data"],
                                       "old_entity": old_data[key]["entity_data"]}

        total = changed_chunks.get_keys_len()
        cnt = 0
        self.progress_bar(total, cnt, title="Applying Blocks", text="Current Progress",
                          update_interval=10000)
        region_dict = collections.defaultdict(lambda: collections.defaultdict(list))
        for (x, y, z), data in changed_chunks.items():
            xx, yy, zz = block_coords_to_chunk_coords(x, y, z)
            rx, rz = chunk_coords_to_region_coords(xx, zz)

            if (xx, yy, zz) in region_dict[(rx, rz)]:
                region_dict[(rx, rz)][(xx, yy, zz)].append({(x, y, z): data})
            else:
                region_dict[(rx, rz)][(xx, yy, zz)] = [{(x, y, z): data}]

        for (rx, rz), chunk_data in region_dict.items():
            world_data = AnvilRegion(self.get_dim_vpath_java_dir(rx, rz))
            # chunk_changes = collections.defaultdict(list)

            for (cx, cy, cz), block_locations_data in chunk_data.items():
                world_nbt = world_data.get_chunk_data(cx % 32, cz % 32)
                sections = {sec['Y'].value: sec for sec in world_nbt['sections']} if 'sections' in world_nbt else {}
                for block_list in block_locations_data:
                    for (x, y, z), data in block_list.items():
                        ix, iy, iz = x % 16, y % 16, z % 16
                        block_data, block_entitie = data['block_data'], data['entity_data']
                        old_data, old_entitie = data['old_block'], data['old_entity']

                        change_needed = False
                        new_block_needed = True
                        sec = sections.get(cy)
                        if len(block_entitie) > 0:
                            if all(block_entitie.get(k) is not None for k in ('x', 'y', 'z')):
                                bx, by, bz = block_entitie['x'], block_entitie['y'], block_entitie['z']
                                index = next(
                                    (i for i, be in enumerate(world_nbt['block_entities']) if
                                     (bx, by, bz) == (be['x'], be['y'], be['z'])),
                                    None
                                )

                                if index is not None:
                                    if world_nbt['block_entities'][index] != block_entitie:
                                        world_nbt['block_entities'][index] = block_entitie
                                else:
                                    world_nbt['block_entities'].append(block_entitie)
                            else:
                                wx.MessageBox('Block Entities require location keys x, y, z',
                                              "Could not locate Keys",
                                              wx.OK | wx.ICON_INFORMATION)

                        if sec and 'block_states' in sec:
                            p_data = sec['block_states'].get('data', None)
                            palette = sec['block_states'].get('palette', None)
                            if mode > 0:
                                for i, blk in enumerate(palette):
                                    if old_data == blk:
                                        palette[i] = block_data
                                sec['block_states']['palette'] = palette
                                cnt += 1
                                cancel = self.progress_bar(total, cnt, title="Applying Blocks", text="Current Progress",
                                                           update_interval=10000)
                                if cancel:
                                    break
                            else:
                                cnt += 1
                                palette_length = len(palette) - 1
                                bits_per_entry = max(palette_length.bit_length(), 4)
                                arr = (decode_long_array(p_data.py_data, 16 * 16 * 16,
                                                         bits_per_entry=bits_per_entry,
                                                         dense=False).reshape(16, 16, 16)
                                       .swapaxes(0, 2).swapaxes(1, 2)) \
                                    if p_data is not None else numpy.zeros((16, 16, 16), dtype=int)

                                for inx, n in enumerate(palette):
                                    if block_data == n:
                                        new_block_needed = False
                                        if arr[ix][iy][iz] != inx:
                                            arr[ix][iy][iz] = inx
                                            change_needed = True
                                        break

                                if new_block_needed:

                                    used_indices = set(arr.flatten())
                                    unused_index = next((i for i in range(len(palette)) if i not in used_indices), None)

                                    if unused_index is not None:
                                        palette[unused_index] = block_data
                                        arr[ix][iy][iz] = unused_index
                                    else:
                                        palette.append(block_data)
                                        new_inx = len(palette) - 1
                                        arr[ix][iy][iz] = new_inx

                                arr = arr.swapaxes(0, 2).swapaxes(0, 1).flatten()
                                palette_length = len(palette) - 1
                                bits_per_entry = max(palette_length.bit_length(), 4)
                                arr_compact = encode_long_array(arr, bits_per_entry=bits_per_entry, dense=False)
                                sec['block_states']['data'] = LongArrayTag(arr_compact)
                                sec['block_states']['palette'] = palette

                                cancel = self.progress_bar(total, cnt, title="Applying Blocks", text="Current Progress",
                                                           update_interval=10000)
                                if cancel:
                                    break

                world_data.put_chunk_data(cx % 32, cz % 32, world_nbt)
            world_data.save()
            world_data.unload()
        return self.found_data

class ProcessLevelDB:
    def __init__(self, found_data, parent=None, world=None, canvas=None):
        # self.v_byte = 9
        self.pause_count = None
        self.block_version = None
        self.parent = parent
        self.found_data = found_data
        self.p_bar = ProgressBar()
        self.canvas = canvas
        self.world = world
        self.search = ''

    @property
    def level_db(self):
        return self.world.level_wrapper.level_db

    @property
    def get_dim(self):
        return self.canvas.dimension

    def leveldb(self, key):
        try:
            return self.level_db.get(key)
        except:
            return None

    def byte_dim(self):
        dim = self.canvas.dimension
        byte_dim = b''
        if dim == "minecraft:the_end":
            byte_dim = b'\x02\x00\x00\x00'
        elif dim == "minecraft:the_nether":
            byte_dim = b'\x01\x00\x00\x00'
        return byte_dim

    def progress_bar(self, total, cnt, title=None, text=None, update_interval=50):
        return self.p_bar.progress_bar(total, cnt, title=title, text=text, update_interval=update_interval)

    def block_cords_to_bedrock_db_keys(self, cords):
        dim = self.canvas.dimension
        x, y, z = cords
        if dim == "minecraft:the_nether":
            be_key = struct.pack("<iiib", x, z, 1, 49)
            sub_key = struct.pack("<iiibb", x, z, 1, 47, y)
        elif dim == "minecraft:the_end":
            be_key = struct.pack("<iiib", x, z, 2, 49)
            sub_key = struct.pack("<iiibb", x, z, 2, 47, y)
        else:
            be_key = struct.pack("<iib", x, z, 49)
            sub_key = struct.pack("<iibb", x, z, 47, y)
        return sub_key, be_key

    def get_v_off(self, data):
        version = data[0]
        offset = 3
        self.v_byte = 9
        if version == 8:
            self.v_byte = 8
            offset = 2
        return offset

    def get_pallets_and_extra(self, raw_sub_chunk):
        block_pal_dat, block_bits, bpv = self.get_blocks(raw_sub_chunk)

        # Unpack the initial block palette data
        if bpv < 1:
            pallet_size, pallet_data = 1, block_pal_dat
        else:
            pallet_size, pallet_data = struct.unpack('<I', block_pal_dat[:4])[0], block_pal_dat[4:]

        op = ReadContext()
        nbt_p = load(pallet_data, count=pallet_size, little_endian=True, read_context=op)
        pallet_data = pallet_data[op.offset:]

        blocks = [n.compound for n in nbt_p]

        # Extra block data
        extra_blocks, extra_pnt_bits = [], None
        if pallet_data:
            block_pal_dat, extra_block_bits, bpv = self.get_blocks(pallet_data)
            if bpv < 1:
                pallet_size, pallet_data = 1, block_pal_dat
            else:
                pallet_size, pallet_data = struct.unpack('<I', block_pal_dat[:4])[0], block_pal_dat[4:]
            extra_pnt_bits = extra_block_bits

            op = ReadContext()
            nbt_p2 = load(pallet_data, count=pallet_size, little_endian=True, read_context=op)
            extra_blocks = [n.compound for n in nbt_p2]

        return blocks, block_bits, extra_blocks, extra_pnt_bits

    def get_blocks(self, raw_sub_chunk):
        bpv, rawdata = struct.unpack("b", raw_sub_chunk[0:1])[0] >> 1, raw_sub_chunk[1:]
        if bpv > 0:
            bpw = 32 // bpv
            wc = -(-4096 // bpw)
            buffer = numpy.frombuffer(bytes(reversed(rawdata[:4 * wc])), dtype="uint8")
            unpack = numpy.unpackbits(buffer).reshape(-1, 32)[:, -bpw * bpv:].reshape(-1, bpv)[-4096:, :]
            unpacked = numpy.pad(unpack, [(0, 0), (16 - bpv, 0)], "constant")
            block_bits = numpy.packbits(unpacked).view(dtype=">i2")[::-1].reshape((16, 16, 16)).swapaxes(1, 2)
            rawdata = rawdata[wc * 4:]
        else:
            block_bits = numpy.zeros((16, 16, 16), dtype=numpy.int16)
        return rawdata, block_bits, bpv

    def back_2_raw(self, lay_one, pal_one, lay_two, pal_two, y_level):
        byte_blocks = []
        bytes_nbt = []
        header, lays = b'', 1
        if len(pal_two) > 0:
            lays = 2
        if self.v_byte > 8:
            header = struct.pack('bbb', self.v_byte, lays, y_level)
        else:
            header = struct.pack('bb', self.v_byte, lays)

        if len(pal_two) > 0:
            block_list = [lay_one, lay_two]
            pal_len = [len(pal_one), len(pal_two)]
            raw = b''
            for rnbt in pal_one:
                raw += rnbt.save_to(compressed=False, little_endian=True)
            bytes_nbt.append(raw)
            raw = b''
            for rnbt in pal_two:
                raw += rnbt.save_to(compressed=False, little_endian=True)
            bytes_nbt.append(raw)
        else:
            block_list = [lay_one]
            pal_len = [len(pal_one)]
            raw = b''
            for rnbtx in pal_one:
                raw += rnbtx.save_to(compressed=False, little_endian=True)
            bytes_nbt.append(raw)
        for ii, b in enumerate(block_list):
            bpv = max(int(numpy.amax(b)).bit_length(), 1)
            if bpv == 7:
                bpv = 8
            elif 9 <= bpv <= 15:
                bpv = 16
            if ii > 0:
                header = b''
            compact_level = bytes([bpv << 1])
            bpw = (32 // bpv)
            wc = -(-4096 // bpw)
            compact = b.swapaxes(1, 2).ravel()
            compact = numpy.ascontiguousarray(compact[::-1], dtype=">i").view(dtype="uint8")
            compact = numpy.unpackbits(compact)
            compact = compact.reshape(4096, -1)[:, -bpv:]
            compact = numpy.pad(compact, [(wc * bpw - 4096, 0), (0, 0)], "constant", )
            compact = compact.reshape(-1, bpw * bpv)
            compact = numpy.pad(compact, [(0, 0), (32 - bpw * bpv, 0)], "constant", )
            compact = numpy.packbits(compact).view(dtype=">i4").tobytes()
            compact = bytes(reversed(compact))
            byte_blocks.append(header + compact_level + compact + struct.pack("<I", pal_len[ii]) + bytes_nbt[ii])
        return b''.join(byte_blocks)

    def block_internal_raw_cords(self, cords):
        x, y, z = cords
        data = CompoundTag({'x': IntTag(x), 'y': IntTag(y), 'z': IntTag(z)}).to_nbt(compressed=False,
                                                                                    little_endian=True)
        return data[3:-1]

    def get_blocks_by_locations(self, data):

        location_dict = collections.defaultdict(list)

        for x, y, z in data.keys():
            xx, yy, zz = block_coords_to_chunk_coords(x, y, z)
            location_dict[(xx, yy, zz)].append((x, y, z))

        total = len(location_dict)
        cnt = 0
        block_entity = UniqueObjectDict()
        new_data = UniqueObjectDict()
        for key, b_list in location_dict.items():
            sub_key, be_key = self.block_cords_to_bedrock_db_keys(key)
            for k, v in self.level_db.iterate(start=be_key, end=be_key + b'\xff\xff\xff'):
                if k[-1] == 49:
                    data = unpack_nbt_list(v)
                    for nbt in data:
                        x, y, z = nbt.get('x').py_int, nbt.get('y').py_int, nbt.get('z').py_int
                        if (x, y, z) in b_list:
                            block_entity[(x, y, z)] = {"entity_data": nbt}

            # Iterate over level DB for blocks
            for k, v in self.level_db.iterate(start=sub_key, end=sub_key + b'\xff\xff\xff'):
                if k[-2] == 47:  # sublevel chunks 16x16x16 blocks

                    level = struct.unpack('b', struct.pack('B', k[-1]))[0]
                    blocks, block_bits, extra_blk, extra_blk_bits = self.get_pallets_and_extra(v[3:])
                    cc, xx = struct.unpack('<ii', k[:8])
                    xc, xy, xz = cc * 16, level * 16, xx * 16
                    for bit, block in enumerate(blocks):
                        indices = numpy.where(block_bits == bit)
                        cords = list(zip(*indices))

                        for x, y, z in cords:
                            kx, ky, kz = (x + xc, xy + y, z + xz)
                            if (kx, ky, kz) in b_list:
                                block_data = blocks[bit]
                                extra_block = extra_blk[extra_blk_bits[x][y][z]] if (
                                    isinstance(extra_blk_bits, numpy.ndarray)) else CompoundTag({})

                                entity_data = block_entity.get('entity_data') if block_entity else CompoundTag({})
                                new_data.add((kx, ky, kz), {
                                    'block_data': block_data,
                                    "extra_block": extra_block,
                                    "entity_data": entity_data
                                })

            cnt += 1
            stop = self.progress_bar(total, cnt,
                                     text=f'Progress...', title='Matchin blocks', update_interval=200)
            if stop:
                break

        self.found_data.backup = new_data

    def add_remove_version_tag(self, remove=False):
        if remove:
            self.found_data.data.update_dict_list('block_data', 'version')
            self.found_data.data.update_dict_list('extra_block', 'version')
            self.found_data.backup.update_dict_list('block_data', 'version')
            self.found_data.backup.update_dict_list('extra_block', 'version')
        else:
            self.found_data.data.update_dict_list('block_data', 'version', self.block_version)
            self.found_data.data.update_dict_list('extra_block', 'version', self.block_version)
            self.found_data.backup.update_dict_list('block_data', 'version', self.block_version)
            self.found_data.backup.update_dict_list('extra_block', 'version', self.block_version)

    def search_raw(self, block_search_keys, block_e_search_keys, search, mode, chunks_done=None):
        byte_dim = self.byte_dim()
        chunks = None
        self.found_data.clear()
        if mode <= 1:

            if chunks_done:
                chunks = [struct.pack('<ii', xx, zz) + byte_dim
                          for (xx, zz) in self.canvas.selection.selection_group.chunk_locations()
                          if struct.pack('<ii', xx, zz) + byte_dim not in chunks_done]
            else:
                chunks = [struct.pack('<ii', xx, zz) + byte_dim for (xx, zz) in
                          self.canvas.selection.selection_group.chunk_locations()]

        if mode == 2:
            if chunks_done:
                self.found_data.clear()
                chunks = [struct.pack('<ii', xx, zz) + byte_dim
                          for (xx, zz) in self.world.all_chunk_coords(self.canvas.dimension)
                          if struct.pack('<ii', xx, zz) + byte_dim not in chunks_done]
            else:
                chunks = [struct.pack('<ii', xx, zz) + byte_dim for (xx, zz) in
                          self.world.all_chunk_coords(self.canvas.dimension)]

        total = len(chunks)
        cnt = 0
        chunk_done = set()
        chunk_pause = None
        for chunkkey in chunks:
            chunk_done.add(chunkkey)

            for k, v in self.level_db.iterate(start=chunkkey, end=chunkkey + b'\xff\xff\xff'):
                if k[-1] == 49:
                    if any(item.encode()[1:-1] in v for item in block_e_search_keys):
                        data = unpack_nbt_list(v)

                        for nbt in data:
                            x, y, z = nbt.get('x').py_int, nbt.get('y').py_int, nbt.get('z').py_int
                            nbtlower = nbt.to_snbt(1).lower()
                            if any(item.lower() in nbtlower for item in block_e_search_keys):
                                x, y, z = nbt.get('x').py_int, nbt.get('y').py_int, nbt.get('z').py_int
                                if mode == 0 and (x, y, z) in self.canvas.selection.selection_group.blocks:
                                    self.found_data.set_data(x, y, z, CompoundTag({}), CompoundTag({}), nbt,
                                                             create_backup=True)
                                elif mode > 0:
                                    self.found_data.set_data(x, y, z, CompoundTag({}), CompoundTag({}), nbt,
                                                             create_backup=True)

            # Iterate over level DB for blocks

            for k, v in self.level_db.iterate(start=chunkkey, end=chunkkey + b'\xff\xff\xff'):

                if k[-2] == 47 and len(k) == len(chunkkey) + 2:  # sublevel chunks 16x16x16 blocks

                    if any(item.encode()[1:-1] in v for item in block_search_keys):
                        level = struct.unpack('b', struct.pack('B', k[-1]))[0]
                        offset = self.get_v_off(v)
                        blocks, block_bits, extra_blk, extra_blk_bits = self.get_pallets_and_extra(v[offset:])
                        for bit, block in enumerate(blocks):
                            if any(item.lower() in block.to_snbt().lower() for item in block_search_keys):
                                indices = numpy.where(block_bits == bit)
                                cords = list(zip(*indices))
                                cc, xx = struct.unpack('<ii', k[:8])
                                xc, xy, xz = cc * 16, level * 16, xx * 16
                                for x, y, z in cords:
                                    kx, ky, kz = (x + xc, xy + y, z + xz)
                                    block_data = blocks[bit]
                                    extra_block = extra_blk[extra_blk_bits[x][y][z]] if (
                                        isinstance(extra_blk_bits, numpy.ndarray)) else CompoundTag({})
                                    existing_data = self.found_data.get((kx, ky, kz))
                                    entity_data = existing_data.get('entity_data') if existing_data else CompoundTag({})
                                    if mode == 0 and (kx, ky, kz) in self.canvas.selection.selection_group.blocks:
                                        self.found_data.set_data(kx, ky, kz, block_data, extra_block, entity_data,
                                                                 create_backup=True)
                                    elif mode > 0:
                                        self.found_data.set_data(kx, ky, kz, block_data, extra_block, entity_data,
                                                                 create_backup=True)

            cnt += 1
            pause_cnt = self.pause_count
            found_blocks = len(self.found_data.get_data())
            self.status = self.progress_bar(total, cnt,
                                            text=f'{search} found: {found_blocks}, Pause after: {pause_cnt} \n'
                                                 f' ccncel will also pause')
            if self.status:
                break
            if found_blocks > pause_cnt:
                chunk_pause = True
                self.progress_bar(total, total, text=search)

                break

        if len(self.found_data.get_data()) > 0:
            self.add_remove_version_tag(True)
            if chunk_pause or self.status:
                return chunk_done, self.found_data
            else:
                return chunk_pause, self.found_data
        else:
            return None, None

    def fast_apply(self, old=None, new=None, mode=None, name=None, ex_old=None, ex_new=None,
                   ex_name=None):  # ,new,old, mode
        ignore_property = False
        e_ignore_property = False
        if new and old and name:
            ignore_property = False
            old['version'] = IntTag(self.block_version)
            if old.get('states') == "*":
                ignore_property = True
            new['version'] = IntTag(self.block_version)
            old_raw = old.to_nbt(compressed=False, little_endian=True)[:-5]  # ignore version value
            new_raw = new.to_nbt(compressed=False, little_endian=True)[:-5]  # ignore version value

        if ex_new and ex_old and ex_name:

            ex_old['version'] = IntTag(self.block_version)
            if ex_old.get('states') == "*":
                e_ignore_property = True
            ex_new['version'] = IntTag(self.block_version)
            ex_old_raw = old.to_nbt(compressed=False, little_endian=True)[:-5]  # ignore version value
            ex_new_raw = new.to_nbt(compressed=False, little_endian=True)[:-5]  # ignore version value

        byte_dim = self.byte_dim()
        if mode == 0:
            pass
        else:
            if mode == 1:
                chunks = [struct.pack('<ii', xx, zz) + byte_dim for (xx, zz) in
                          self.canvas.selection.selection_group.chunk_locations()]
            elif mode == 2:
                chunks = [struct.pack('<ii', xx, zz) + byte_dim for (xx, zz) in
                          self.world.all_chunk_coords(self.canvas.dimension)]
            total = len(chunks)
            cnt = 0
            for chunkkey in chunks:
                for k, v in self.level_db.iterate(start=chunkkey, end=chunkkey + b'\xff\xff\xff'):
                    if k[-2] == 47:

                        if new and old and name:
                            if name in v:

                                extra_block = v[1:2]
                                if extra_block == b'\x01':
                                    v = v.replace(old_raw, new_raw)
                                    print(v)
                                    print(old_raw == new_raw)
                                    print(old_raw, new_raw)
                                    self.level_db.put(k, v)
                                elif extra_block == b'\x02':
                                    bpv = struct.unpack("b", v[3:4])[0] >> 1
                                    if bpv > 0:
                                        bpw = 32 // bpv
                                        wc = -(-4096 // bpw)
                                        offset = wc * 4
                                        end_of_palet = find_end_of_compounds(v[offset + 4:])

                                        a = v[:end_of_palet + offset + 4].replace(old_raw, new_raw)

                                        if ex_new and ex_old and ex_name:
                                            v = a + v[end_of_palet + offset + 4:].replace(ex_old_raw, ex_new_raw)

                                        else:
                                            v = a + v[end_of_palet + offset + 4:]

                                        self.level_db.put(k, v)

                        elif ex_new and ex_old and ex_name:
                            extra_block = v[1:2]
                            if extra_block == b'\x02':
                                if ex_name in v:
                                    bpv = struct.unpack("b", v[3:4])[0] >> 1
                                    if bpv > 0:
                                        bpw = 32 // bpv
                                        wc = -(-4096 // bpw)
                                        offset = wc * 4
                                        end_of_palet = find_end_of_compounds(v[offset + 4:])
                                        b = v[:end_of_palet + offset + 4]
                                        a = v[end_of_palet + offset + 4:].replace(ex_old_raw, ex_new_raw)
                                        v = b + a
                                        self.level_db.put(k, v)
                cnt += 1
                self.progress_bar(total, cnt, text="Chunk Progress...", title='Replaceing Blocks')

    def apply(self, mode):
        self.add_remove_version_tag()
        new_data = self.found_data.get_data()
        old_data = self.found_data.get_copy()

        changed_chunks = {}
        location_dict = collections.defaultdict(list)
        for key in old_data.keys():
            if new_data[key] != old_data[key]:
                changed_chunks[key] = new_data[key]
        for x, y, z in changed_chunks.keys():
            xx, yy, zz = block_coords_to_chunk_coords(x, y, z)
            location_dict[(xx, yy, zz)].append(((x, y, z), (block_enty_raw_cords(x, y, z))))
        total = len(location_dict)
        cnt = 0
        air_block = from_snbt('{"name": "minecraft:air","states": {}}')
        air_block['version'] = self.block_version

        for key, b_list in location_dict.items():
            sub_key, be_key = self.block_cords_to_bedrock_db_keys(key)
            cnt += 1
            db_data = self.level_db.get(sub_key)
            y_level = struct.unpack('b', struct.pack('B', sub_key[-1]))[0]
            off = self.get_v_off(db_data)
            b, bits, eb, eb_bits = self.get_pallets_and_extra(db_data[off:])
            for (x, y, z), r in b_list:

                block_data, extra_block = changed_chunks[(x, y, z)]['block_data'], changed_chunks[(x, y, z)][
                    'extra_block']
                if len(block_data) > 0:

                    if b[bits[x % 16][y % 16][z % 16]] != block_data:
                        if block_data in b:
                            inx = b.index(block_data)
                            bits[x % 16][y % 16][z % 16] = inx
                        else:
                            b.append(block_data)
                            inx = b.index(block_data)
                            bits[x % 16][y % 16][z % 16] = inx
                    else:
                        if block_data in b:
                            inx = b.index(block_data)
                            bits[x % 16][y % 16][z % 16] = inx
                        else:
                            b.append(block_data)
                            inx = b.index(block_data)
                            bits[x % 16][y % 16][z % 16] = inx

                    if len(extra_block) > 0:
                        if eb_bits is not None:
                            if eb[eb_bits[x % 16][y % 16][z % 16]] != extra_block:

                                if extra_block in eb:
                                    inx = eb.index(extra_block)
                                    eb_bits[x % 16][y % 16][z % 16] = inx
                                else:
                                    eb.append(extra_block)
                                    inx = eb.index(extra_block)
                                    eb_bits[x % 16][y % 16][z % 16] = inx
                        else:
                            eb_bits = numpy.zeros((16, 16, 16), dtype=numpy.int16)
                            eb.append(air_block)
                            eb.append(extra_block)
                            inx = eb.index(extra_block)
                            eb_bits[x % 16][y % 16][z % 16] = inx

            new_raw = self.back_2_raw(bits, b, eb_bits, eb, y_level)
            self.level_db.put(sub_key, new_raw)

            raw_be = self.leveldb(be_key)
            b_enty_list = []
            has_had_data = False
            if raw_be:
                b_enty_list = unpack_nbt_list(raw_be)
                has_had_data = True
            for (x, y, z), r in b_list:
                is_in_raw = False
                is_in_new = False
                if raw_be:
                    if r in raw_be:
                        is_in_raw = True
                if len(changed_chunks[(x, y, z)]['entity_data']) > 0:
                    is_in_new = True
                if is_in_raw or is_in_new:
                    if is_in_raw:
                        not_exsist = True
                        for i, o_nbt in enumerate(b_enty_list):
                            ox, oy, oz = o_nbt.get('x').py_int, o_nbt.get('y').py_int, o_nbt.get('z').py_int
                            if (ox, oy, oz) == (x, y, z):
                                b_enty_list[i] = changed_chunks[(x, y, z)]['entity_data']
                                not_exsist = False
                        if not_exsist:
                            b_enty_list.append(en['entity_data'])
                    elif is_in_new:
                        if len(changed_chunks[(x, y, z)]['entity_data']) > 0:
                            b_enty_list.append(changed_chunks[(x, y, z)]['entity_data'])
            if len(b_enty_list) > 0 or has_had_data:
                raw_list = pack_nbt_list(b_enty_list)
                self.level_db.put(be_key, raw_list)

            self.progress_bar(total, cnt, title='Applying Block changes..', text='Progress...', update_interval=100)
        self.add_remove_version_tag(True)
        return self.found_data  # #

class UniqueObjectDict:
    def __init__(self):
        # Initialize with separate data structures
        self.obj_dict = {}  # Maps (x, y, z) keys to indices in obj_list
        self.obj_list = []  # Stores unique dictionary objects

    def add(self, key, obj):
        """Add a dictionary object with the given (x, y, z) key."""
        if not isinstance(obj, dict):
            raise ValueError("Only dictionaries can be stored in UniqueObjectDict.")

        try:
            index = self.obj_list.index(obj)
        except ValueError:
            index = len(self.obj_list)
            self.obj_list.append(obj)

        self.obj_dict[key] = index

    def update_dict_list(self, key, nbt_key, data=None):
        if data:
            for d in self.obj_list:
                t = d[key]
                if len(t) > 0:
                    t[nbt_key] = data
        else:
            for d in self.obj_list:
                d[key].pop(nbt_key, None)

    def get(self, key):
        """Retrieve the dictionary object associated with the given (x, y, z) key."""
        index = self.obj_dict.get(key)
        if index is not None:
            return self.obj_list[index]
        return None

    def get_keys_len(self):
        return len(self.obj_dict)

    def keys(self):
        """Return an iterator of all keys."""
        return iter(self.obj_dict.keys())

    def items(self):
        """Return an iterator of key-value pairs (key, dict object)."""
        return ((key, self.obj_list[index]) for key, index in self.obj_dict.items())

    def __getitem__(self, key):
        """Retrieve the dictionary object using index-style access."""
        return self.get(key)

    def __setitem__(self, key, value):
        """Add or update the dictionary object using index-style access."""
        self.add(key, value)

    def __delitem__(self, key):
        """Remove the dictionary object associated with the given (x, y, z) key."""
        if key in self.obj_dict:
            index = self.obj_dict.pop(key)
            if index not in self.obj_dict.values():
                self.obj_list.pop(index)
                self.obj_dict = {k: (v if v < index else v - 1) for k, v in self.obj_dict.items()}

    def __contains__(self, key):
        """Check if a dictionary object with the given (x, y, z) key exists."""
        return key in self.obj_dict

    def __len__(self):
        """Return the number of dictionary objects stored."""
        return len(self.obj_dict)

    def __repr__(self):
        return f"UniqueObjectDict(obj_dict={self.obj_dict}, obj_list={self.obj_list})"

    def pop(self, key, default=None):
        """Remove the dictionary object associated with the given (x, y, z) key."""
        if key in self.obj_dict:
            index = self.obj_dict.pop(key)
            obj = self.obj_list[index]
            if index not in self.obj_dict.values():
                self.obj_list.pop(index)
                # Update indices in obj_dict
                self.obj_dict = {k: (v if v < index else v - 1) for k, v in self.obj_dict.items()}
            return obj
        return default

    def clear(self):
        """Clear all stored dictionary objects."""
        self.obj_dict.clear()
        self.obj_list.clear()

class FoundData:
    def __init__(self, world=None, canvas=None):

        self.canvas = canvas
        self.world = world
        self.pages = 0
        self.page_size = None
        self.backup = UniqueObjectDict()
        self.data = UniqueObjectDict()

    def get_data(self):
        return self.data

    def get(self, key):
        return self.data.get(key)

    def get_key_len(self):
        return self.data.get_keys_len()

    def set_data(self, x, y, z, block_data, extra_block, entity_data, create_backup=False):
        self.data.add((x, y, z),
                      {'block_data': block_data,
                       "extra_block": extra_block,
                       "entity_data": entity_data})
        if create_backup:
            self.backup.add((x, y, z),
                            {'block_data': block_data,
                             "extra_block": extra_block,
                             "entity_data": entity_data})

    def get_copy(self):
        return self.backup

    def reset_backup(self, data):
        self.backup = UniqueObjectDict()
        for (x, y, z), block_nbt in data.items():
            self.backup.add((x, y, z),
                            {'block_data': block_nbt.get('block_data'),
                             "extra_block": block_nbt.get('extra_block'),
                             "entity_data": block_nbt.get('entity_data')})  # Update backup with current data

    def paginate(self, page_size):
        self.page_size = page_size
        self.pages = (len(self.data) + page_size - 1) // page_size
        return self.pages

    def get_page(self, page_number):
        if page_number < 1 or page_number > self.pages:
            return None
        start = (page_number - 1) * self.page_size
        end = start + self.page_size
        keys = list(self.data.obj_dict.keys())[start:end]
        return {key: self.data.get(key) for key in keys}

    def clear(self):
        self.pages = 0
        self.page_size = 0
        self.data.clear()
        self.backup.clear()

class CustomRadioBox(wx.Panel):
    def __init__(self, parent, label, choices, foreground_color, sty=None, md=1):
        super().__init__(parent)

        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.label = wx.StaticText(self, label=label)
        self.label.SetForegroundColour(foreground_color)
        self.sizer.Add(self.label, 0, wx.ALL, 5)

        self.radio_buttons = []
        self.radio_buttons_map = {}

        if sty == wx.RA_SPECIFY_ROWS:
            self.radio_sizer = wx.FlexGridSizer(rows=md, cols=(len(choices) + md - 1) // md, vgap=5, hgap=5)
        elif sty == wx.RA_SPECIFY_COLS:
            self.radio_sizer = wx.FlexGridSizer(rows=(len(choices) + md - 1) // md, cols=md, vgap=5, hgap=5)
        else:
            self.radio_sizer = wx.BoxSizer(wx.VERTICAL if md == 1 else wx.HORIZONTAL)

        for i, choice in enumerate(choices):
            style = wx.RB_GROUP if i == 0 else 0
            radio_btn = wx.RadioButton(self, label=choice, style=style)
            radio_btn.SetForegroundColour(foreground_color)
            self.radio_sizer.Add(radio_btn, 0, wx.ALL, 5)
            self.radio_buttons.append(radio_btn)
            self.radio_buttons_map[radio_btn] = i

        self.sizer.Add(self.radio_sizer, 0, wx.ALL, 5)
        self.SetSizer(self.sizer)

    def GetString(self, index):
        if 0 <= index < len(self.radio_buttons):
            return self.radio_buttons[int(index)].GetLabel()

    def SetSelection(self, index):
        if 0 <= index < len(self.radio_buttons):
            self.radio_buttons[int(index)].SetValue(True)

    def GetSelection(self):
        for index, radio_btn in enumerate(self.radio_buttons):
            if radio_btn.GetValue():
                return index
        return None

def scale_bitmap(bitmap, width, height):
    image = bitmap.ConvertToImage()
    image = image.Scale(width, height, wx.IMAGE_QUALITY_HIGH)
    return wx.Bitmap(image)

class ImportImageSettings(wx.Frame):
    def __init__(self, parent, world=None):
        super(ImportImageSettings, self).__init__(parent, title="Import Settings", size=(300, 600),
                                                  style=wx.DEFAULT_FRAME_STYLE | wx.STAY_ON_TOP)
        parent_position = parent.GetScreenPosition()
        self.world = world
        self.SetPosition(parent_position + (50, 50))
        self.parent = parent
        self.font = wx.Font(14, wx.FONTFAMILY_ROMAN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        self.SetFont(self.font)
        self.SetForegroundColour((0, 255, 0))
        self.SetBackgroundColour((0, 0, 0))

        # Color picker control

        self.transparent_border = wx.CheckBox(self, label="Transparent Border?")
        self.transparent_border.Bind(wx.EVT_CHECKBOX, self.is_color_picker_visable)
        self.transparent_border.SetValue(True)
        self.color_picker_label = wx.StaticText(self, label="Select A Color For Border:")
        self.color_picker = wx.ColourPickerCtrl(self, size=(150, 40))

        self.selected_file = wx.StaticText(self, label=" ( Dont Select File if Reusing Custom Maps )\n"
                                                       "No File Selected")
        self.selected_block = wx.StaticText(self, label=str(self.parent.selected_block))
        self.ok_btn = wx.Button(self, label="OK")
        self.ok_btn.Bind(wx.EVT_BUTTON, self.done)

        # Custom radio box for frame type
        self.rb_frame_type = CustomRadioBox(self, 'Frame type?', self.parent.frame_types, (0, 255, 0), md=2)

        # Image file selection button
        self._set_images_on_frames = wx.Button(self, size=(160, 40), label="Select Image File")
        self._set_images_on_frames.Bind(wx.EVT_BUTTON, self.open_file_dialof)

        # Block type selection button
        self.apply_back_block = wx.Button(self, size=(160, 40), label="Select Backing Block")
        self.apply_back_block.Bind(wx.EVT_BUTTON, self.parent.apply_backblock)

        # Bind close event
        self.Bind(wx.EVT_CLOSE, self.on_close)

        # Layout
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.color_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.SetSizer(self.sizer)
        self.mode_sizer = wx.BoxSizer(wx.VERTICAL)
        self.sizer.Add(self._set_images_on_frames, 0, wx.LEFT, 10)
        self.sizer.Add(self.selected_file, 0, wx.LEFT, 10)
        self.sizer.Add(self.apply_back_block, 0, wx.LEFT, 10)
        self.sizer.Add(self.selected_block, 0, wx.LEFT, 10)
        if self.world.level_wrapper.platform == 'java':
            modes = ["Fast", "Better", "Lab(slow closer)"]
            self.color_find_modes = CustomRadioBox(self, 'How to Match Colors?', modes, (0, 255, 0), md=2)
            self.fixed_frame = wx.CheckBox(self, label="Fixed Frames No Backing Block Required")
            self.invisible_frames = wx.CheckBox(self, label="Make Item Frames Invisible")
            self.fixed_frame.SetValue(True)
            self.invisible_frames.SetValue(True)
            self.sizer.Add(self.fixed_frame, 0, wx.LEFT, 10)
            self.sizer.Add(self.invisible_frames, 0, wx.LEFT, 10)
            self.mode_sizer.Add(self.color_find_modes, 0, wx.LEFT, 10)

        self.sizer.Add(self.rb_frame_type, 0, wx.LEFT, 50)
        self.mode_sizer.Add(self.transparent_border, 0, wx.LEFT, 10)
        self.color_sizer.Add(self.color_picker_label, 0, wx.LEFT, 0)
        self.color_sizer.Add(self.color_picker, 0, wx.LEFT, 0)

        self.sizer.Add(self.mode_sizer)
        self.sizer.Add(self.color_sizer, 0, wx.LEFT, 10)

        self.sizer.Add(self.ok_btn, 0, wx.LEFT, 150)
        self.sizer.Hide(self.color_sizer)
        self.sizer.Hide(self.mode_sizer)
        self.Layout()

        self.Fit()

    def on_close(self, _):

        if self.world.level_wrapper.platform == 'java':
            self.java_options()
        color = self.color_picker.GetColour()
        # Update parent frame type and color properties
        self.parent.rb_frame_type = self.rb_frame_type.GetString(self.rb_frame_type.GetSelection())
        if self.transparent_border.IsChecked():
            self.parent.color = (0, 0, 0, 0)
        else:
            self.parent.color = (color.Red(), color.Green(), color.Blue(), 255)
        self.Destroy()
        if self.parent.selected_file:
            self.parent.set_images_on_frames(None)

    def done(self, _):
        # Similar to on_close, handles OK button press
        self.on_close(None)

    def is_color_picker_visable(self, _):
        if self.transparent_border.IsChecked():

            self.sizer.Hide(self.color_sizer)
        else:
            self.sizer.Show(self.color_sizer)
        self.Fit()  # Adjust the frame size to fit the new layout

    def java_options(self):
        self.parent.fixed_frame = self.fixed_frame.GetValue()
        self.parent.invisible_frames = self.invisible_frames.GetValue()
        selection = self.color_find_modes.GetSelection()
        if selection == 1:
            self.parent.map_data_manager.color_match_mode = 'closer'
        elif selection == 2:
            self.parent.map_data_manager.color_match_mode = 'lab'
        else:
            self.parent.map_data_manager.color_match_mode = None  # fast default

    def open_file_dialof(self, _):

        with wx.FileDialog(self, "Open Image file", wildcard="*", style=wx.FD_OPEN) as file_dialog:
            if file_dialog.ShowModal() == wx.ID_CANCEL:
                return
            else:
                self.selected_file.SetLabel(file_dialog.GetPath())
                self.parent.selected_file = file_dialog.GetPath()
                self.sizer.Show(self.mode_sizer)
                self.Fit()
                self.Layout()

    def GetSelectedFrame(self):
        return self.rb_frame_type

    def GetSelectedBlock(self):
        pass

    def SetBlock(self, text):
        self.selected_block.SetLabel(text)

class BuildWallSettings(wx.Frame):
    def __init__(self, parent, maps_img_data, world=None):
        super(BuildWallSettings, self).__init__(parent, title="Map Wall Settings", size=(300, 300),
                                                style=wx.DEFAULT_FRAME_STYLE | wx.STAY_ON_TOP)
        parent_position = parent.GetScreenPosition()
        self.world = world
        self.maps_img_data = maps_img_data
        self.SetPosition(parent_position + (50, 50))
        self.parent = parent
        self.font = wx.Font(16, wx.FONTFAMILY_ROMAN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        self.SetFont(self.font)
        self.SetForegroundColour((0, 255, 0))
        self.SetBackgroundColour((0, 0, 0))
        self.vsizer = wx.BoxSizer(wx.VERTICAL)
        self.label_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.input_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.vsizer.Add(self.label_sizer)
        self.vsizer.Add(self.input_sizer)
        self.vsizer.Add(self.button_sizer)

        self.label_col = wx.StaticText(self, label="Height: ")
        self.label_row = wx.StaticText(self, label="Width:  ")
        self.label_sizer.Add(self.label_col, 0, wx.LEFT, 5)
        self.label_sizer.Add(self.label_row, 0, wx.LEFT, 35)
        self.text_cols = wx.TextCtrl(self, size=(120, 30))
        self.text_rows = wx.TextCtrl(self, size=(120, 30))
        self.input_sizer.Add(self.text_cols, 0, wx.LEFT, 5)
        self.input_sizer.Add(self.text_rows, 0, wx.LEFT, 15)
        self.text_cols.SetValue('4')
        self.text_rows.SetValue('4')
        self.ok_btn = wx.Button(self, label="OK")
        self.ok_btn.Bind(wx.EVT_BUTTON, self.done)
        self.button_sizer.Add(self.ok_btn)
        self.SetSizer(self.vsizer)
        self.Layout()
        self.Fit()
        self.Show()

    def done(self, _):
        cols, rows = int(self.text_cols.GetValue()), int(self.text_rows.GetValue())
        BuildMapWall(cols, rows, self.maps_img_data, parent=self.parent)
        self.Close()

class JavaMapColorsResolver:

    def __init__(self):
        self.MAP_SHADE_MODIFIERS = [180, 220, 255, 135]
        self.map_colors = [
            (0, 0, 0, 0), (127, 178, 56, 255), (247, 233, 163, 255),
            (199, 199, 199, 255), (255, 0, 0, 255), (160, 160, 255, 255),
            (167, 167, 167, 255), (0, 124, 0, 255), (255, 255, 255, 255),
            (164, 168, 184, 255), (151, 109, 77, 255), (112, 112, 112, 255),
            (64, 64, 255, 255), (143, 119, 72, 255), (255, 252, 245, 255),
            (216, 127, 51, 255), (178, 76, 216, 255), (102, 153, 216, 255),
            (229, 229, 51, 255), (127, 204, 25, 255), (242, 127, 165, 255),
            (76, 76, 76, 255), (153, 153, 153, 255), (76, 127, 153, 255),
            (127, 63, 178, 255), (51, 76, 178, 255), (102, 76, 51, 255),
            (102, 127, 51, 255), (153, 51, 51, 255), (25, 25, 25, 255),
            (250, 238, 77, 255), (92, 219, 213, 255), (74, 128, 255, 255),
            (0, 217, 58, 255), (129, 86, 49, 255),
            # Colors added in version 1.12
            (112, 2, 0, 255), (209, 177, 161, 255), (159, 82, 36, 255),
            (149, 87, 108, 255), (112, 108, 138, 255), (186, 133, 36, 255),
            (103, 117, 53, 255), (160, 77, 78, 255), (57, 41, 35, 255),
            (135, 107, 98, 255), (87, 92, 92, 255), (122, 73, 88, 255),
            (76, 62, 92, 255), (76, 50, 35, 255), (76, 82, 42, 255),
            (142, 60, 46, 255), (37, 22, 16, 255),
            # Colors added in version 1.16
            (189, 48, 49, 255), (148, 63, 97, 255), (92, 25, 29, 255),
            (22, 126, 134, 255), (58, 142, 140, 255), (86, 44, 62, 255),
            (20, 180, 133, 255), (100, 100, 100, 255), (216, 175, 147, 255),
            (127, 167, 150, 255)
        ]
        self.map_colors_shaded = self.generate_shaded_colors()

    def generate_shaded_colors(self) -> numpy.ndarray:
        return numpy.array([
            [
                (r * shade) // 255,
                (g * shade) // 255,
                (b * shade) // 255,
                a
            ]
            for r, g, b, a in self.map_colors
            for shade in self.MAP_SHADE_MODIFIERS
        ])

    # Helper function to convert RGB to XYZ color space using numpy
    def rgb_to_xyz_np(self, rgb):
        # Normalize the RGB values to [0, 1]
        rgb = rgb / 255.0

        # Apply sRGB companding (inverse gamma correction)
        mask = rgb > 0.04045
        rgb[mask] = ((rgb[mask] + 0.055) / 1.055) ** 2.4
        rgb[~mask] = rgb[~mask] / 12.92

        # Convert to XYZ using the sRGB matrix
        matrix = numpy.array([[0.4124, 0.3576, 0.1805],
                              [0.2126, 0.7152, 0.0722],
                              [0.0193, 0.1192, 0.9505]])
        xyz = numpy.dot(rgb, matrix.T)

        return xyz

    # Helper function to convert XYZ to Lab color space using numpy
    def xyz_to_lab_np(self, xyz):
        # Reference white point (D65)
        ref_white = numpy.array([0.95047, 1.00000, 1.08883])
        xyz = xyz / ref_white

        # Convert to Lab
        epsilon = 0.008856
        kappa = 903.3

        mask = xyz > epsilon
        xyz[mask] = numpy.cbrt(xyz[mask])
        xyz[~mask] = (kappa * xyz[~mask] + 16) / 116

        L = 116 * xyz[:, 1] - 16
        a = 500 * (xyz[:, 0] - xyz[:, 1])
        b = 200 * (xyz[:, 1] - xyz[:, 2])

        return numpy.stack([L, a, b], axis=1)

    # Function to compute CIE76 color difference using numpy
    def cie76_np(self, lab1, lab2):
        return numpy.sqrt(numpy.sum((lab1 - lab2) ** 2, axis=1))

    def find_closest_java_color_fast(self, rr: int, gg: int, bb: int, aa: int) -> int:

        cr = self.map_colors_shaded[:, 0]
        cg = self.map_colors_shaded[:, 1]
        cb = self.map_colors_shaded[:, 2]
        ca = self.map_colors_shaded[:, 3]

        # Calculate the weighted differences
        r_diff = (cr * 0.71 - rr * 0.71) ** 2
        g_diff = (cg * 0.86 - gg * 0.986) ** 2
        b_diff = (cb * 0.654 - bb * 0.754) ** 2
        a_diff = (ca * 0.53 - aa * 0.53) ** 2

        # Calculate the score
        score = r_diff + g_diff + b_diff + a_diff

        # Find the index with the minimum score
        min_index = numpy.argmin(score)

        return int(min_index)

    def find_closest_java_color_closer(self, rr: int, gg: int, bb: int, aa: int) -> int:

        cr = self.map_colors_shaded[:, 0]
        cg = self.map_colors_shaded[:, 1]
        cb = self.map_colors_shaded[:, 2]
        ca = self.map_colors_shaded[:, 3]

        rmean = (cr + rr) // 2
        r = cr - rr
        g = cg - gg
        b = cb - bb
        a = ca - aa
        score = numpy.sqrt((((512 + rmean) * r * r) >> 8) + (4 * g * g) + (((747 - rmean) * b * b) >> 8) + a)

        min_index = numpy.argmin(score)
        return int(min_index)

    def find_closest_java_color_lab(self, rr: int, gg: int, bb: int, aa: int) -> int:
        # Convert the target color to Lab
        target_rgb = numpy.array([rr, gg, bb])
        target_xyz = self.rgb_to_xyz_np(target_rgb)
        target_lab = self.xyz_to_lab_np(numpy.array([target_xyz]))

        # Convert all candidate colors to Lab
        candidate_rgb = self.map_colors_shaded[:, :3]  # Ignore alpha for color comparison
        candidate_xyz = self.rgb_to_xyz_np(candidate_rgb)
        candidate_lab = self.xyz_to_lab_np(candidate_xyz)

        # Calculate CIE76 color differences
        distances = self.cie76_np(candidate_lab, target_lab)

        # Find the index of the minimum distance
        min_index = numpy.argmin(distances)

        return int(min_index)

    def from_chunker_colors(self, chunker_map_colors: bytes, mode=None) -> bytes:
        output_bytes = bytearray(len(chunker_map_colors) // 4)
        for i in range(0, len(chunker_map_colors), 4):
            r = chunker_map_colors[i] & 0xFF
            g = chunker_map_colors[i + 1] & 0xFF
            b = chunker_map_colors[i + 2] & 0xFF
            a = chunker_map_colors[i + 3] & 0xFF
            if mode == 'lab':
                output_bytes[i // 4] = self.find_closest_java_color_lab(r, g, b, a)
            elif mode == 'closer':
                output_bytes[i // 4] = self.find_closest_java_color_closer(r, g, b, a)
            else:
                output_bytes[i // 4] = self.find_closest_java_color_fast(r, g, b, a)

        return bytes(output_bytes)

    def to_java_colors(self, java_map_colors: bytes) -> bytes:
        output_bytes = bytearray(len(java_map_colors) * 4)
        for i, value in enumerate(java_map_colors):
            if 0 <= value < len(self.map_colors_shaded):
                rgba = self.map_colors_shaded[value]
                new_index = i * 4
                output_bytes[new_index] = rgba[0]
                output_bytes[new_index + 1] = rgba[1]
                output_bytes[new_index + 2] = rgba[2]
                output_bytes[new_index + 3] = rgba[3]
        return bytes(output_bytes)

class ImageGridManager(wx.StaticBitmap):
    def __init__(self, parent, bitmap, img_id, grid):
        super().__init__(parent, bitmap=bitmap)
        self.parent = parent
        self.img_id = img_id
        self.grid = grid
        self.pos_in_grid = None
        self.Bind(wx.EVT_LEFT_DOWN, self.OnLeftClick)

    def OnLeftClick(self, event):
        if self.pos_in_grid is None:
            self.grid.PlaceImageInFirstAvailableSlot(self)
        else:
            self.grid.RemoveImageFromGrid(self)

    def Copy(self):
        # Create a copy of the image
        return ImageGridManager(self.parent, self.GetBitmap(), self.img_id, self.grid)

class ImageGrid(wx.Panel):
    def __init__(self, parent, rows, cols):
        super().__init__(parent)
        self.rows = rows
        self.cols = cols
        self.sizer = wx.GridSizer(rows, cols, 0, 0)
        self.SetSizer(self.sizer)
        self.image_positions = {}

        for i in range(rows * cols):
            placeholder = wx.Panel(self, size=(120, 120))
            placeholder.SetBackgroundColour(wx.Colour(200, 200, 200))
            self.sizer.Add(placeholder, 0, wx.ALL | wx.EXPAND, 1)
            self.image_positions[i] = placeholder

    def PlaceImageInFirstAvailableSlot(self, image):
        # Check if image is already placed in the grid
        if image.pos_in_grid is not None:
            return
        available_slot_found = False
        for i in range(self.rows * self.cols):
            if isinstance(self.image_positions[i], wx.Panel):  # Placeholder check
                available_slot_found = True
                break

        if not available_slot_found:
            # Handle case where the grid is full
            wx.MessageBox("The grid is full. Cannot place more images.", "Error", wx.ICON_ERROR)
            return
        # Create a copy of the image and add it to the grid
        copied_image = image.Copy()
        copied_image.Hide()
        self.AddImageToGrid(copied_image)

    def AddImageToGrid(self, image, from_last=False):
        # Get grid cell size dynamically
        grid_width, grid_height = self.get_grid_cell_size()

        # Resize the image before adding it to the grid, keeping the img_id intact
        resized_image = self.resize_image_to_fit_grid(image.GetBitmap(), grid_width, grid_height, image.img_id)

        # Remove image from any existing sizer (including the ImageSourcePanel)
        if image.GetContainingSizer() is not None:
            image.GetContainingSizer().Detach(image)

        # Reparent the resized image to the grid's panel
        resized_image.Reparent(self)

        if from_last:
            for i in range(self.rows * self.cols - 1, -1, -1):
                if isinstance(self.image_positions[i], wx.Panel):  # Placeholder check
                    self.sizer.Hide(self.image_positions[i])  # Hide the placeholder
                    self.image_positions[i] = resized_image

                    # Add the resized image to the grid's sizer
                    self.sizer.Replace(self.sizer.GetChildren()[i].GetWindow(), resized_image)

                    resized_image.pos_in_grid = i
                    self.sizer.Layout()
                    break
        else:
            for i in range(self.rows * self.cols):
                if isinstance(self.image_positions[i], wx.Panel):  # Placeholder check
                    self.sizer.Hide(self.image_positions[i])  # Hide the placeholder
                    self.image_positions[i] = resized_image

                    # Add the resized image to the grid's sizer
                    self.sizer.Replace(self.sizer.GetChildren()[i].GetWindow(), resized_image)

                    resized_image.pos_in_grid = i
                    self.sizer.Layout()
                    break

    def get_grid_cell_size(self):
        # Dynamically retrieve the size of a single grid cell
        grid_size = self.GetSize()
        rows, cols = self.rows, self.cols
        grid_width = grid_size.GetWidth() // cols
        grid_height = grid_size.GetHeight() // rows

        return grid_width, grid_height

    def resize_image_to_fit_grid(self, bitmap, grid_width, grid_height, img_id):
        # Convert the bitmap to wx.Image, resize it, and convert it back to wx.Bitmap
        img = bitmap.ConvertToImage()
        img = img.Rescale(grid_width, grid_height, wx.IMAGE_QUALITY_HIGH)
        resized_bitmap = wx.Bitmap(img)

        # Return a new ImageGridManager with the resized bitmap, preserving the img_id
        return ImageGridManager(self.GetParent(), resized_bitmap, img_id=img_id, grid=self)

    def RemoveImageFromGrid(self, image):
        if image.pos_in_grid is not None:
            pos = image.pos_in_grid
            self.sizer.Hide(image)
            placeholder = wx.Panel(self, size=(120, 120))
            placeholder.SetBackgroundColour(wx.Colour(200, 200, 200))
            self.image_positions[pos] = placeholder
            self.sizer.Replace(image, placeholder)
            image.pos_in_grid = None
            self.sizer.Layout()

class ImageSourcePanel(wx.ScrolledWindow):
    def __init__(self, parent, grid):
        super().__init__(parent)
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self.sizer)
        self.SetScrollRate(5, 5)
        self.grid = grid

    def AddImage(self, bitmap, img_id):
        img = ImageGridManager(self, bitmap, img_id, self.grid)
        self.sizer.Add(img, 0, wx.ALL, 5)
        self.Layout()
        self.FitInside()

class BuildMapWall(wx.Frame):
    def __init__(self, col, rows, map_img_list, parent=None):
        super().__init__(parent=None, title="Build Map Wall", size=(800, 800),
                         style=wx.DEFAULT_FRAME_STYLE | wx.STAY_ON_TOP)
        self.parent = parent
        panel = wx.Panel(self)
        parent_position = parent.GetScreenPosition()

        self.SetPosition(parent_position + (50, 50))
        self.font = wx.Font(16, wx.FONTFAMILY_ROMAN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        self.SetFont(self.font)
        self.SetForegroundColour((0, 255, 0))
        self.SetBackgroundColour((0, 0, 0))
        self.grid_rows = col
        self.grid_cols = rows

        self.grid = ImageGrid(panel, self.grid_rows, self.grid_cols)

        self.image_source = ImageSourcePanel(panel, self.grid)
        for map_image, map_id in map_img_list:
            self.image_source.AddImage(map_image, map_id)

        self.image_source.SetMinSize((160, 168))
        get_image_order = wx.Button(panel, size=(80, 50), label="Apply")
        get_image_order.Bind(wx.EVT_BUTTON, self.GetImageOrder)
        _close = wx.Button(panel, size=(80, 50), label="Close")
        _close.Bind(wx.EVT_BUTTON, self.close)
        vbox = wx.BoxSizer(wx.VERTICAL)
        hbox = wx.BoxSizer(wx.HORIZONTAL)
        hbox.Add(self.image_source, 0, wx.EXPAND | wx.ALL, 5)
        hbox.Add(self.grid, 5, wx.EXPAND | wx.ALL, 0)
        vbox.Add(hbox, 10, wx.EXPAND | wx.ALL, 0)
        vbox.Add(get_image_order, 0, wx.CENTER, 0)
        panel.SetSizer(vbox)
        self.Show()

    def close(self, ):
        self.Close()

    def GetImageOrder(self, _):
        map_order_list = []
        for i in range(self.grid_rows * self.grid_cols):

            if self.grid.image_positions.get(i, None):
                if hasattr(self.grid.image_positions.get(i), 'img_id'):
                    map_order_list.append(self.grid.image_positions.get(i).img_id)
                else:
                    map_order_list.append(None)
        self.parent.custom_map_wall = (map_order_list, self.grid_rows, self.grid_cols)

        if None in map_order_list:
            wx.MessageBox(f"The Grid need to be full",
                          "Can Not Apply",
                          wx.OK | wx.ICON_ERROR)
            return
        self.parent.custom_map_wall_add()
        self.Close()

class JavaMapData:
    facing = {
        "Facing Down": 0,
        "Facing Up": 1,
        "Facing North": 2,
        "Facing South": 3,
        "Facing West": 4,
        "Facing East": 5,
    }
    pointing = {
        "Flip Right": 0,
        "Flip Left": 1,
        "Up (Like Preview)": 2,
        "Upside Down": 3
    }

    def __init__(self, parent=None, canvas=None, world=None):

        self.parent = parent
        self.world = world
        self.canvas = canvas
        self.map_data_converter = JavaMapColorsResolver()
        self.color_match_mode = None
        self.maps_path = os.path.join(self.world.level_wrapper.path, 'data')
        self.cols_rows = (0, 0)
        self.progress = ProgressBar()
        self.maps_tobe = {}
        self.c_map_counts = -1
        self.maps_tobe_color_ready = []

        self.custom_map_tobe = {}

        self.all_map = {}
        self.custom_map = {}

        self.temp_new_custom_keys = []
        self.temp_new_map_keys = []
        self.load_all_maps()

    def convert_images(self):
        maps_tobe_new = []
        total = len(self.maps_tobe)
        cnt = 0
        for v in self.maps_tobe:
            cnt += 1
            stop = self.progress.progress_bar(total, cnt, update_interval=1,
                                              title="Converting Image to Java Image Preview",
                                              text=f"Processing...")
            if stop:
                return
            java_colors = self.map_data_converter.from_chunker_colors(v[0], mode=self.color_match_mode)
            java_rgba = self.map_data_converter.to_java_colors(java_colors)
            maps_tobe_new.append((java_rgba, v[1], v[2]))
            self.maps_tobe_color_ready.append((java_colors, v[1], v[2]))
        self.maps_tobe = maps_tobe_new

    def get_map_img(self, img_bytes):

        colors = self.map_data_converter.to_java_colors(bytes(img_bytes))
        bb = wx.Bitmap.FromBufferRGBA(128, 128, colors)
        img = scale_bitmap(bb, 128, 128)
        return img

    def apply(self, map_key_list=None):

        if not map_key_list:
            map_key_list = self.apply_compund_maps()
        self.java_region_data_apply()
        self.custom_map_location_entry(map_key_list)
        wx.MessageBox(
            f'Amulet does not render Item Frames.\n'
            f'They will be where you placed them.\n'
            f'Also note: You can reuse this by selecting\n'
            f'{self.custom_key_str} from the custom maps list.\n'
            f'After clicking ok this will auto select your custom map'
            f'Click once somewhere in the world\n'
            f'to trigger mouse move selection.',
            "Operation Completed",
            wx.OK | wx.ICON_INFORMATION
        )
        self.refresh_all()

        self.parent._custom_map_list.Clear()

        self.parent._custom_map_list.AppendItems([x for x in self.custom_map.keys()])

        self.parent._custom_map_list.SetStringSelection(self.custom_key_str)
        self.parent._custom_event = wx.CommandEvent(wx.EVT_LISTBOX.evtType[0], self.parent._custom_map_list.GetId())
        self.parent._custom_event.SetEventObject(self.parent._custom_map_list)
        self.parent._custom_map_list.GetEventHandler().ProcessEvent(self.parent._custom_event)

    def get_block_placement_offset(self, xx, yy, zz):
        facing = self.parent.facing.GetSelection()
        block_offset = {
            0: (0, -1, 0),
            # Facing Up
            1: (0, 1, 0),
            # Facing North
            2: (0, 0, -1),
            # Facing South
            3: (0, 0, 1),
            # Facing West
            4: (-1, 0, 0),
            # Facing East
            5: (1, 0, 0)
        }
        x, y, z = block_offset[facing]
        return xx - x, yy - y, zz - z

    def get_item_rotation(self):
        pointing, facing = self.parent.pointing.GetSelection(), self.parent.facing.GetSelection()

        rotation_data = {
            # Facing Down
            (0, 0): (0, 6, [0, 90]),  # North or Right
            (0, 1): (0, 5, [0, 90]),  # East or Left
            (0, 2): (0, 4, [0, 90]),  # South or Up
            (0, 3): (0, 7, [0, 90]),  # West or Down

            # Facing Up
            (1, 0): (1, 0, [0, -90]),  # North or Right
            (1, 1): (1, 5, [0, -90]),  # East or Left
            (1, 2): (1, 2, [0, -90]),  # South or Up
            (1, 3): (1, 7, [0, -90]),  # West or Down

            # Facing North
            (2, 0): (2, 5, [180, 0]),  # North or Right
            (2, 1): (2, 7, [180, 0]),  # East or Left
            (2, 2): (2, 4, [180, 0]),  # South or Up
            (2, 3): (2, 6, [180, 0]),  # West or Down

            # Facing South
            (3, 0): (3, 5, [180, 0]),  # North or Right
            (3, 1): (3, 7, [180, 0]),  # East or Left
            (3, 2): (3, 4, [180, 0]),  # South or Up
            (3, 3): (3, 6, [180, 0]),  # West or Down

            # Facing West
            (4, 0): (4, 5, [0, 0]),  # North or Right
            (4, 1): (4, 7, [90, 0]),  # East or Left
            (4, 2): (4, 4, [90, 0]),  # South or Up
            (4, 3): (4, 6, [90, 0]),  # West or Down

            # Facing East
            (5, 0): (5, 1, [270, 0]),  # North or Right
            (5, 1): (5, 7, [270, 0]),  # East or Left
            (5, 2): (5, 4, [270, 0]),  # South or Up
            (5, 3): (5, 6, [270, 0]),  # West or Down
        }

        _facing, _item_rotation, (rx, ry) = rotation_data[(facing, pointing)]
        return ByteTag(_facing), ByteTag(_item_rotation), ListTag([FloatTag(rx), FloatTag(ry)])

    def get_dim_vpath_java_dir(self, regonx, regonz, folder='region'):  # entities
        file = "r." + str(regonx) + "." + str(regonz) + ".mca"
        path = self.world.level_wrapper.path
        full_path = ''
        dim = ''
        if 'minecraft:the_end' in self.canvas.dimension:
            dim = 'DIM1'
        elif 'minecraft:the_nether' in self.canvas.dimension:
            dim = 'DIM-1'
        elif 'minecraft:overworld' in self.canvas.dimension:
            dim = ''

        full_path = os.path.join(path, dim, folder, file)
        return full_path

    def custom_map_location_entry(self, maps_keys: list[str]):

        idcounts_dat = os.path.join(self.maps_path, 'idcounts.dat')
        count_data = None
        if os.path.exists(idcounts_dat):
            count_data = load(idcounts_dat)
            count = count_data['data'].get('map').py_int
            count += len(maps_keys)
            count_data['data']['map'] = IntTag(count)
        else:
            count_data = CompoundTag({
                'data': CompoundTag({
                    'map': IntTag(len(maps_keys))}),
                'DataVersion': IntTag(self.world.level_wrapper.version)
            })
        count_data.save_to(idcounts_dat, compressed=True, little_endian=False,
                           string_encoder=utf8_encoder)

        custom_pre_fix = self.get_available_custom_key

        self.custom_key_str = custom_pre_fix + ":" + self.parent.custom_map_name.GetValue()
        custom_path_file = os.path.join(self.maps_path, f'{custom_pre_fix}.dat')

        pointing = self.parent.pointing.GetSelection()
        facing = self.parent.facing.GetSelection()
        cols, rows = self.cols_rows

        nbt_maps = [StringTag(m) for m in maps_keys]
        x, y, z = self.canvas.camera.location
        xz, yy = self.canvas.camera.rotation
        sg = self.canvas.selection.selection_group
        (sx, sy, sg), (xs, xy, xg) = sg.min, sg.max
        c_data = CompoundTag({
            "name": StringTag(self.custom_key_str),
            "pointing": IntTag(pointing),
            "facing": IntTag(facing),
            "cols": IntTag(cols),
            "rows": IntTag(rows),
            "map_list": ListTag(nbt_maps),
            "dimension": StringTag(self.canvas.dimension),
            "rotation": IntArrayTag([xz, yy]),
            "location": IntArrayTag([x, y, z]),
            "selectionGp": IntArrayTag([sx, sy, sg, xs, xy, xg])
        })

        c_data.save_to(custom_path_file, compressed=True, little_endian=False,
                       string_encoder=utf8_encoder)
        return self.custom_key_str

    def get_map_colors(self, map_name):
        nbt = load(self.all_map[map_name])

        colors = nbt['data'].get('colors', None)
        name = map_name
        map_id = int(name[4:])

        self.maps_tobe_color_ready.append((name, map_id, name))
        rgba_colors = self.map_data_converter.to_java_colors(bytes(colors.py_data))
        return rgba_colors

    def get_custom_map_nbt(self, selection):
        custom_data = load(self.custom_map[selection])

        return custom_data

    def item_frame_entitle(self, item_map_id, position):
        fixed_frame, invisible_frame = 0, 0
        if self.parent.fixed_frame:
            fixed_frame = 1
        if self.parent.invisible_frames:
            invisible_frame = 1
        cord_pos = {
            0: (0.5, 0.03125, 0.5),
            1: (0.5, 0.96875, 0.5),
            2: (0.5, 0.5, 0.03125),
            3: (0.5, 0.5, 0.96875),  # 96875
            4: (0.03125, 0.5, 0.5),
            5: (0.96875, 0.5, 0.5)
        }
        facing, item_rotation, rotation = self.get_item_rotation()

        item_name = None
        if self.parent.rb_frame_type == "Regular Frame":
            item_name = 'minecraft:item_frame'
        elif self.parent.rb_frame_type == "Glow Frame":
            item_name = 'minecraft:glow_item_frame'
        x, y, z = position
        if x >= 0:
            x = x + cord_pos[facing.py_int][0]
        else:
            x = -(abs(x) + cord_pos[facing.py_int][0])

        # Handle y-coordinate
        if y >= 0:
            y = y + cord_pos[facing.py_int][1]
        else:
            y = -(abs(y) + cord_pos[facing.py_int][1])

        # Handle z-coordinate
        if z >= 0:
            z = z + cord_pos[facing.py_int][2]
        else:
            z = -(abs(z) + cord_pos[facing.py_int][2])

        print(x, y, z, position)
        entitle_compound = CompoundTag({
            'Motion': ListTag([DoubleTag(0), DoubleTag(0), DoubleTag(0)]),
            'Facing': facing,
            'ItemRotation': item_rotation,
            'Invulnerable': ByteTag(0),
            'Air': ShortTag(300),
            'OnGround': ByteTag(0),
            'PortalCooldown': IntTag(0),
            'Rotation': rotation,
            'FallDistance': FloatTag(0),
            'Item': CompoundTag({
                'components': CompoundTag({
                    "minecraft:map_id": IntTag(item_map_id)
                }),
                'count': ByteTag(1),
                'id': StringTag("minecraft:filled_map")
            }),
            'ItemDropChance': FloatTag(1),
            'Pos': ListTag([DoubleTag(x), DoubleTag(y), DoubleTag(z)]),
            'Fire': ShortTag(-1),
            'TileY': IntTag(y),
            'id': StringTag(item_name),
            'TileX': IntTag(x),
            'Invisible': ByteTag(invisible_frame),
            'UUID': IntArrayTag([x for x in struct.unpack('>iiii', uuid.uuid4().bytes)]),
            'TileZ': IntTag(z),
            'Fixed': ByteTag(fixed_frame)
        })
        return entitle_compound

    def java_region_data_apply(self):
        self.raw_data_chunks = None
        self.raw_data_entities = None
        sorted_blocks, rotation = self.parent.reorder_coordinates()
        # blk_location_dict = collections.defaultdict(lambda: collections.defaultdict(list))
        location_dict = collections.defaultdict(lambda: collections.defaultdict(list))
        platform = self.world.level_wrapper.platform
        version = self.world.level_wrapper.version
        chunk_list = []
        blk_location = []
        for map_inx, (x, y, z) in enumerate(sorted_blocks):
            xx, yy, zz = block_coords_to_chunk_coords(x, y, z)
            rx, rz = chunk_coords_to_region_coords(xx, zz)
            if (xx, yy, zz) in location_dict[(rx, rz)]:
                location_dict[(rx, rz)][(xx, yy, zz)].append(((x, y, z), map_inx))
            else:
                location_dict[(rx, rz)][(xx, yy, zz)] = [((x, y, z), map_inx)]
        for x, y, z in sorted_blocks:
            bx, by, bz = self.get_block_placement_offset(x, y, z)
            blk_location.append((bx, by, bz))

        item_map_id = [x[1] for x in self.maps_tobe_color_ready]

        for (rx, rz), chunk_data in location_dict.items():
            self.raw_data_entities = AnvilRegion(self.get_dim_vpath_java_dir(rx, rz, folder='entities'))
            for (cx, cy, cz), block_locations in chunk_data.items():  #
                chunk_list.append((cx, cz))

                if self.raw_data_entities.has_chunk(cx % 32, cz % 32):
                    entities_data = self.raw_data_entities.get_chunk_data(cx % 32, cz % 32)
                    for block_loc, map_inx in block_locations:
                        print(item_map_id[map_inx], block_loc, cx % 32, cz % 32)
                        entities_data['Entities'].append(self.item_frame_entitle(item_map_id[map_inx], block_loc))
                    self.raw_data_entities.put_chunk_data(cx % 32, cz % 32, entities_data)
                else:
                    entities_data = CompoundTag({
                        'Position': IntArrayTag([cx, cz]),
                        'DataVersion': IntTag(self.world.level_wrapper.version),
                        'Entities': ListTag([])
                    })
                    for block_loc, map_inx in block_locations:
                        entities_data['Entities'].append(self.item_frame_entitle(item_map_id[map_inx], block_loc))
                    self.raw_data_entities.put_chunk_data(cx % 32, cz % 32, entities_data)

            self.raw_data_entities.save()
            self.raw_data_entities.unload()

        if self.parent.selected_block:

            for x, y, z in blk_location:
                self.world.set_version_block(x, y, z, self.canvas.dimension,
                                             (platform, version), self.parent.selected_block, None)
            self.canvas.run_operation(
                lambda: self.parent._refresh_chunk(self.canvas.dimension, self.world,
                                                   self.canvas.selection.selection_group.min_x,
                                                   self.canvas.selection.selection_group.min_z))
            self.world.save()
        for cx, cz in chunk_list:
            chunk_data = self.world.level_wrapper.get_raw_chunk_data(cx, cz, self.canvas.dimension)
            if chunk_data.get('isLightOn', None):
                chunk_data['isLightOn'] = ByteTag(0)
            self.world.level_wrapper.put_raw_chunk_data(cx, cz, chunk_data, self.canvas.dimension)

    def apply_compund_maps(self):  # .dat files
        version = self.world.level_wrapper.version
        map_data = CompoundTag({'DataVersion': IntTag(version)})
        map_data['data'] = CompoundTag({
            'zCenter': IntTag(2147483647),
            'xCenter': IntTag(2147483647),
            "trackingPosition": ByteTag(1),
            "unlimitedTracking": ByteTag(0),
            "dimension": StringTag(self.canvas.dimension),
            "colors": ByteArrayTag(0)
        })
        map_key_list = []
        cols, rows = self.cols_rows
        total = cols * rows
        cnt = 0
        for raw_color_data, map_id, name in self.maps_tobe_color_ready:
            cnt += 1
            stop = self.progress.progress_bar(total, cnt, update_interval=1, title="Adding Images To World",
                                              text=f"Processing...{name}")
            if stop:
                break
            map_key_list.append(name)
            map_data['data']['colors'] = ByteArrayTag(bytearray(raw_color_data))
            file_path = os.path.join(self.maps_path, name + '.dat')
            map_data.save_to(file_path, compressed=True, little_endian=False,
                             string_encoder=utf8_encoder)

        return map_key_list

    def get_colors_from_map(self, _file_path):
        nbt = load(_file_path)
        colors = nbt['data'].get('colors', None)
        rgba_colors = self.map_data_converter.to_java_colors(bytes(colors.py_data))
        return rgba_colors

    def load_all_maps(self):
        idcounts_dat = os.path.join(self.maps_path, 'idcounts.dat')
        if os.path.exists(idcounts_dat):
            pass
        all_maps = [f"{f}" for f in os.listdir(self.maps_path)
                    if os.path.isfile(os.path.join(self.maps_path, f)) and "map_" in f[0:4]]
        self.c_map_counts = -len([x for x in all_maps if 'map_-' in x[0:5]]) - 1

        custom_map = [f"{f}" for f in os.listdir(self.maps_path)
                      if os.path.isfile(os.path.join(self.maps_path, f)) and "cmap_" in f[0:5]]

        for map_ in all_maps:  # 2147483647
            if 'map_' in map_:
                nbt = load(os.path.join(self.maps_path, map_))
                if max(nbt['data'].get('colors').py_data) > 0:
                    self.all_map[map_[:-4]] = f"{self.maps_path}\\{map_}"
                # if nbt['data'].get('xCenter').py_int != 2147483647 and nbt['data'].get('zCenter').py_int != 2147483647:

        for cmap_ in custom_map:
            if 'cmap_' in cmap_:
                nbt = load(os.path.join(self.maps_path, cmap_))
                name_str = nbt.get('name').py_str
                self.custom_map[name_str] = f"{self.maps_path}\\{cmap_}"

    @property
    def get_available_custom_key(self):
        if len(self.custom_map) == 0 and len(self.temp_new_custom_keys) == 0:
            self.temp_new_custom_keys.append(f'cmap_{0}')
            return f'cmap_{0}'
        else:
            for i in range(len(self.custom_map) + len(self.temp_new_custom_keys)):
                next_map_key = f'cmap_{i + 1}'
                if next_map_key not in str(self.custom_map.keys()):
                    if next_map_key not in str(self.temp_new_custom_keys):
                        self.temp_new_custom_keys.append(next_map_key)
                        return next_map_key

    @property
    def get_available_map_key(self):
        if self.c_map_counts == -1 and len(self.temp_new_map_keys) == 0:
            self.temp_new_map_keys.append(f'map_{self.c_map_counts}')
            self.c_map_counts -= 1
            return f'map_{-1}'
        else:
            next_map_key = f'map_{self.c_map_counts}'
            self.temp_new_map_keys.append(next_map_key)
            self.c_map_counts -= 1
            return next_map_key

    def del_selected_map(self, file_):

        def check_for_matching_cmap(name, current_map_list):

            for n, f in self.custom_map.items():
                if n != name:
                    nbt = load(f)
                    map_list = nbt.get('map_list').py_data
                    for m in map_list:
                        if m in current_map_list:
                            current_map_list.remove(m)

            for rm in current_map_list:  # safe to delete no other cmaps contain map
                f = self.all_map[rm.py_str]
                os.remove(f)

        def check_for_matching_map(name):
            map_in_cmap = []
            for f in self.custom_map.values():

                nbt = load(f)
                map_list = nbt.get('map_list').py_data
                cmap_name = nbt.get('name').py_str
                if name in str(map_list):
                    map_in_cmap.append(cmap_name)
            if len(map_in_cmap) > 0:
                wx.MessageBox(f"This {name} is part of custom map/'s\n"
                              f"Remove theses custom maps and try again: \n{map_in_cmap} ",
                              "Can Not Remove",
                              wx.OK | wx.ICON_ERROR)
            else:
                f = self.all_map[name]
                os.remove(f)

        if 'cmap_' in file_:
            f = self.custom_map[file_]
            nbt = load(f)
            map_list = nbt.get('map_list').py_data
            if 'map_-' in map_list[0].py_str:
                check_for_matching_cmap(file_, map_list)
                os.remove(f)
            else:
                os.remove(f)
        else:
            check_for_matching_map(file_)

    def delete_all_maps(self):
        for f in self.all_map.values():
            os.remove(f)
        for f in self.custom_map.values():
            os.remove(f)
        idcounts_dat = os.path.join(self.maps_path, 'idcounts.dat')
        count_data = CompoundTag({
            'data': CompoundTag({
                'map': IntTag(0),
                'DataVersion': IntTag(self.world.level_wrapper.version)
            })
        })
        count_data.save_to(idcounts_dat, compressed=True, little_endian=False,
                           string_encoder=utf8_encoder)
        self.refresh_all()

    def refresh_all(self):
        self.maps_tobe = []
        self.custom_map_tobe = {}
        self.all_map = {}
        self.custom_map = {}
        self.maps_tobe_color_ready = []
        self.temp_new_custom_keys = []
        self.temp_new_map_keys = []
        self.load_all_maps()

    def get_cmap_list_of_map_images(self, cmap):
        f = self.custom_map[cmap]
        nbt = load(f)
        list_or_maps = nbt['map_list'].py_data
        imgs = []
        for i in list_or_maps:
            rgba = self.get_map_colors(i.py_str)
            img = Image.frombytes('RGBA', (128, 128), rgba)
            imgs.append(img)
        return imgs

class BedrockMapData:
    facing = {
        "Facing Down": 0,
        "Facing Up": 1,
        "Facing North": 2,
        "Facing South": 3,
        "Facing West": 4,
        "Facing East": 5,
    }
    pointing = {
        "Flip Right": 0,
        "Flip Left": 1,
        "Up (Like Preview)": 2,
        "Upside Down": 3
    }

    def __init__(self, parent=None, canvas=None, world=None):
        self.parent = parent
        self.world = world
        self.canvas = canvas

        self.cols_rows = (0, 0)
        self.progress = ProgressBar()
        self.maps_tobe = []
        self.custom_map_tobe = {}

        self.all_map = {}
        self.custom_map = {}

        self.temp_new_custom_keys = []
        self.temp_new_map_keys = []
        self.load_all_maps()

    def get_map_img(self, name):

        colors = self.all_map[name]
        bb = wx.Bitmap.FromBufferRGBA(128, 128, colors.get('colors').py_data)
        img = scale_bitmap(bb, 128, 128)
        return img

    def get_block_placement_offset(self, xx, yy, zz):
        facing = self.parent.facing.GetSelection()
        block_offset = {
            0: (0, -1, 0),
            # Facing Up
            1: (0, 1, 0),
            # Facing North
            2: (0, 0, -1),
            # Facing South
            3: (0, 0, 1),
            # Facing West
            4: (-1, 0, 0),
            # Facing East
            5: (1, 0, 0)
        }
        x, y, z = block_offset[facing]

        return (xx - x, yy - y, zz - z)

    def apply(self, map_key_list=None):
        platform = self.world.level_wrapper.platform
        version = self.world.level_wrapper.version
        block_name, block_entiy_name = None, None
        if self.parent.rb_frame_type == "Regular Frame":
            block_name, block_entiy_name = ("frame", "ItemFrame")
        elif self.parent.rb_frame_type == "Glow Frame":
            block_name, block_entiy_name = ("glow_frame", "GlowItemFrame")
        c_map_key = None
        if not map_key_list:
            map_key_list = self.put_map_data()
            c_map_key = [x[1] for x in self.maps_tobe]
        self.parent.custom_key_str = self.custom_map_location_entry(map_key_list)

        facing_direction, pointed = self.parent.facing.GetSelection(), self.parent.pointing.GetSelection()
        block_coordinates, rotation_angle = self.parent.reorder_coordinates()
        sorted_blocks, rotation = self.parent.reorder_coordinates()
        blk_location = []
        for x, y, z in sorted_blocks:
            bx, by, bz = self.get_block_placement_offset(x, y, z)
            blk_location.append((bx, by, bz))
        map_keys_tobe = [k[1] for k in self.maps_tobe]
        for idx in range(len(block_coordinates)):
            if self.parent.custom_map_loaded:
                uuid = LongTag(int(self.parent.selected_maps[idx].replace('map_', '')))
            else:
                uuid = LongTag(map_keys_tobe[idx])

            x, y, z = block_coordinates[idx][0], block_coordinates[idx][1], block_coordinates[idx][2]
            block_nbt = CompoundTag({
                "facing_direction": IntTag(facing_direction),
                "item_frame_map_bit": ByteTag(1)
            })
            block = Block("minecraft", block_name, dict(block_nbt))
            entity_nbt = CompoundTag({
                "isMovable": ShortTag(1),
                "Item": CompoundTag({
                    "Count": ByteTag(1),
                    "Damage": ByteTag(6),
                    "Name": StringTag("minecraft:filled_map"),
                    "WasPickedUp": ByteTag(0),
                    "tag": CompoundTag({
                        "map_name_index": IntTag(-1),
                        "map_uuid": uuid,
                    })
                }),
                "ItemDropChance": FloatTag(1.0),
                "ItemRotation": FloatTag(rotation_angle),
            })
            block_entity = BlockEntity("minecraft", block_entiy_name, 0, 0, 0, NamedTag(entity_nbt))
            self.world.set_version_block(x, y, z, self.canvas.dimension,
                                         (platform, version), block, block_entity)

        if self.parent.selected_block:
            for x, y, z in blk_location:
                self.world.set_version_block(x, y, z, self.canvas.dimension,
                                             (platform, version), self.parent.selected_block, None)

        self.canvas.run_operation(
            lambda: self.parent._refresh_chunk(self.canvas.dimension, self.world,
                                               self.canvas.selection.selection_group.min_x,
                                               self.canvas.selection.selection_group.min_z))
        self.world.save()
        wx.MessageBox(
            f'Amulet does not render Item Frames.\n'
            f'They will be where you placed them.\n'
            f'Also note: You can reuse this by selecting\n'
            f'{c_map_key} from the custom maps list.\n'
            f'After clicking ok this will auto select your custom map'
            f'Click once somewhere in the world\n'
            f'to trigger mouse move selection.',
            "Operation Completed",
            wx.OK | wx.ICON_INFORMATION
        )
        self.refresh_all()

        self.parent._custom_map_list.Clear()

        self.parent._custom_map_list.AppendItems([x for x in self.custom_map.keys()])

        self.parent._custom_map_list.SetStringSelection(self.parent.custom_key_str)
        self.parent._custom_event = wx.CommandEvent(wx.EVT_LISTBOX.evtType[0], self.parent._custom_map_list.GetId())
        self.parent._custom_event.SetEventObject(self.parent._custom_map_list)
        self.parent._custom_map_list.GetEventHandler().ProcessEvent(self.parent._custom_event)

    def get_map_colors(self, key):
        return self.all_map[key]['colors'].py_data

    def get_colors_from_map(self, _file_path):
        color_data = _file_path.get('colors', None)
        return bytes(color_data.py_data)

    def custom_map_location_entry(self, maps_keys: list[str]):
        pointing = self.parent.pointing.GetSelection()
        facing = self.parent.facing.GetSelection()
        cols, rows = self.cols_rows
        # if self.parent.custom_map_loaded:
        #
        # else:
        #     custom_pre_fix = [x for x in self.maps_tobe.keys()][0]
        custom_pre_fix = self.get_available_custom_key
        self.custom_key_str = custom_pre_fix + ":" + self.parent.custom_map_name.GetValue()
        custom_key = self.custom_key_str.encode()
        nbt_maps = [StringTag(m) for m in maps_keys]
        x, y, z = self.canvas.camera.location
        xz, yy = self.canvas.camera.rotation
        sg = self.canvas.selection.selection_group
        (sx, sy, sg), (xs, xy, xg) = sg.min, sg.max
        c_data = CompoundTag({
            "pointing": IntTag(pointing),
            "facing": IntTag(facing),
            "cols": IntTag(cols),
            "rows": IntTag(rows),
            "map_list": ListTag(nbt_maps),
            "dimension": StringTag(self.canvas.dimension),
            "rotation": IntArrayTag([xz, yy]),
            "location": IntArrayTag([x, y, z]),
            "selectionGp": IntArrayTag([sx, sy, sg, xs, xy, xg])
        })
        raw_nbt = c_data.to_nbt(compressed=False, little_endian=True, string_encoder=utf8_escape_encoder)
        self.level_db.put(custom_key, raw_nbt)
        return self.custom_key_str

    def get_custom_map_nbt(self, selection):

        return self.custom_map[selection]

    def put_map_data(self):
        map_key_list = self.apply_compund_maps()
        return map_key_list

    def apply_compund_maps(self):
        map_data = CompoundTag({
            "name": StringTag(''),
            "dimension": ByteTag(0),
            "fullyExplored": ByteTag(1),
            "scale": ByteTag(4),
            "mapId": LongTag(0),
            "parentMapId": LongTag(-1),
            "mapLocked": ByteTag(1),
            "unlimitedTracking": ByteTag(0),
            "xCenter": IntTag(2147483647),
            "zCenter": IntTag(2147483647),
            "height": ShortTag(128),
            "width": ShortTag(128),
            "colors": ByteArrayTag(0)
        })
        map_key_list = []
        cols, rows = self.cols_rows
        total = cols * rows
        cnt = 0
        for raw_color_data, map_id, name in self.maps_tobe:
            cnt += 1
            stop = self.progress.progress_bar(total, cnt, update_interval=1, title="Adding Images To World",
                                              text=f"Processing...{name}")
            if stop:
                break
            map_key_list.append(name)
            map_key = name.encode()
            map_data['name'] = StringTag(name)
            map_data['mapId'] = LongTag(map_id)
            map_data['colors'] = ByteArrayTag(bytearray(raw_color_data))
            raw_map = map_data.to_nbt(compressed=False, little_endian=True,
                                      string_encoder=utf8_escape_encoder)
            self.level_db.put(map_key, raw_map)

        return map_key_list

    def load_all_maps(self):
        self.custom_map = self.get_nbt_data(b'cmap')
        self.all_map = self.get_nbt_data(b'map_')

    def get_nbt_data(self, byte_key: bytes):
        _map = {}
        for k, v in self.level_db.iterate(start=byte_key,
                                          end=byte_key + b'\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF'):
            nbt = load(v, compressed=False, little_endian=True, string_decoder=utf8_escape_decoder).tag
            if nbt.get('colors', None):
                if max(nbt['colors'].py_data) > 0:
                    _map[k.decode()] = nbt
            else:
                _map[k.decode()] = nbt
        return _map

    def del_selected_map(self, key):

        def check_for_matching_cmap(name, current_map_list):

            for n, f in self.custom_map.items():
                if n != name:
                    nbt = f
                    map_list = nbt.get('map_list').py_data
                    for m in map_list:
                        if m in current_map_list:
                            current_map_list.remove(m)
            for rm in current_map_list:  # safe to delete no other cmaps contain map
                self.level_db.delete(rm.encode())

        def check_for_matching_map(name):
            map_in_cmap = []
            for k, f in self.custom_map.items():

                nbt = f
                map_list = nbt.get('map_list').py_data
                cmap_name = k
                if name in str(map_list):
                    map_in_cmap.append(cmap_name)
            if len(map_in_cmap) > 0:
                wx.MessageBox(f"This {name} is part of custom map/'s\n"
                              f"Remove theses custom maps and try again: \n{map_in_cmap} ",
                              "Can Not Remove",
                              wx.OK | wx.ICON_ERROR)
            else:
                self.level_db.delete(name.encode())

        if 'cmap_' in key:
            nbt = self.custom_map[key]
            map_list = nbt.get('map_list').py_data
            if 'map_-' not in map_list[0].py_str:
                check_for_matching_cmap(key, map_list)
                self.level_db.delete(key.encode())
            else:
                self.level_db.delete(key.encode())
        else:
            check_for_matching_map(key)
        # self.all_map
        # self.custom_map
        # self.level_db.delete(k)

    def delete_all_maps(self):

        for k, v in self.level_db.iterate(start=b'cmap',
                                          end=b'cmap' + b'\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF'):
            self.level_db.delete(k)
        for k, v in self.level_db.iterate(start=b'map_',
                                          end=b'map_' + b'\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF'):
            self.level_db.delete(k)

    def refresh_all(self):
        self.maps_tobe = []
        self.custom_map_tobe = {}
        self.all_map = {}
        self.custom_map = {}
        self.temp_new_custom_keys = []
        self.temp_new_map_keys = []
        self.load_all_maps()

    def convert_images(self):
        pass  # holder for java

    def get_cmap_list_of_map_images(self, cmap):
        nbt = self.custom_map[cmap]
        list_or_maps = nbt['map_list'].py_data
        imgs = []
        for i in list_or_maps:
            rgba = self.get_map_colors(i.py_str)
            img = Image.frombytes('RGBA', (128, 128), bytes(rgba))
            imgs.append(img)
        return imgs

    @property
    def get_available_custom_key(self):
        if len(self.custom_map) == 0 and len(self.temp_new_custom_keys) == 0:
            self.temp_new_custom_keys.append(f'cmap_{0}')
            return f'cmap_{0}'
        else:
            for i in range(len(self.custom_map) + len(self.temp_new_custom_keys)):
                next_map_key = f'cmap_{i + 1}'
                if next_map_key not in str(self.custom_map.keys()):
                    if next_map_key not in str(self.temp_new_custom_keys):
                        self.temp_new_custom_keys.append(next_map_key)
                        return next_map_key

    @property
    def get_available_map_key(self):
        if len(self.all_map) == 0 and len(self.temp_new_map_keys) == 0:
            self.temp_new_map_keys.append(f'map_{0}')
            return f'map_{0}'
        else:
            for i in range(len(self.all_map) + len(self.temp_new_map_keys)):
                next_map_key = f'map_{i + 1}'
                if not self.all_map.get(next_map_key, None):
                    if next_map_key not in self.temp_new_map_keys:
                        self.temp_new_map_keys.append(next_map_key)
                        return next_map_key

    @property
    def level_db(self):
        level_wrapper = self.world.level_wrapper
        if hasattr(level_wrapper, "level_db"):
            return level_wrapper.level_db
        else:
            return level_wrapper._level_manager._db

class SetFrames(wx.Frame):
    def __init__(self, parent, canvas, world, *args, **kw):
        super(SetFrames, self).__init__(parent, *args, **kw,
                                        style=(wx.MINIMIZE_BOX | wx.MAXIMIZE_BOX | wx.RESIZE_BORDER |
                                               wx.SYSTEM_MENU | wx.CAPTION | wx.CLOSE_BOX | wx.CLIP_CHILDREN |
                                               wx.FRAME_FLOAT_ON_PARENT),
                                        title="Image or Maps To Frames")
        self.parent = parent

        self.canvas = canvas
        self.world = world
        self.font = wx.Font(13, wx.FONTFAMILY_ROMAN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        self.SetFont(self.font)
        # wx.Panel.__init__(self, parent)
        # DefaultOperationUI.__init__(self, parent, canvas, world, options_path)
        self.platform = world.level_wrapper.platform
        self.world_version = world.level_wrapper.version

        if self.platform == 'bedrock':
            self.map_data_manager = BedrockMapData(parent=self, canvas=self.canvas, world=self.world)
        else:
            self.map_data_manager = JavaMapData(parent=self, canvas=self.canvas, world=self.world)
        self.fixed_frame = True
        self.invisible_frames = True
        self.back_block = None
        self.custom_map_loaded = False
        self.custom_map_wall = 'The Wall Data'
        self.color = (0, 0, 0, 0)
        self.pointer_shape = []
        self.progress = ProgressBar()
        self.Freeze()
        self.selected_block = None
        self.old_ponter_shape = None
        self._is_enabled = True
        self._moving = True

        self._sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self._sizer)

        self.button_menu_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.top_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.middle_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.bottom_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self._sizer.Add(self.button_menu_sizer)
        self._sizer.Add(self.top_sizer)
        self._sizer.Add(self.middle_sizer)
        self._sizer.Add(self.bottom_sizer)
        self.font = wx.Font(11, wx.FONTFAMILY_ROMAN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        self.SetFont(self.font)
        self.SetForegroundColour((0, 255, 0))
        self.SetBackgroundColour((0, 0, 0))
        self.selected_file = None
        self.frame_types = ["Glow Frame", "Regular Frame"]
        self.rb_frame_type = "Glow Frame"
        self._save_map_image = wx.Button(self, size=(70, 50), label="Save Map\n Image")
        self._save_map_image.Bind(wx.EVT_BUTTON, self.save_image_grid)
        self._save_map_image.Hide()
        self._go_to_maps = wx.Button(self, size=(70, 50), label="Go To\n Location")
        self._go_to_maps.Bind(wx.EVT_BUTTON, self.go_to_maps)
        self._go_to_maps.Hide()

        # self.top_sizer.Add(self.rb_frame_type, 0, wx.LEFT, 2)

        self.top_sizer.Add(self._go_to_maps, 0, wx.LEFT, 170)
        self.top_sizer.Add(self._save_map_image, 0, wx.LEFT, 5)
        real_maps = []
        if self.platform == 'java':
            real_maps = [x for x in self.map_data_manager.all_map.keys() if "map_-" not in x[0:5]]
        else:
            real_maps = [x for x in self.map_data_manager.all_map.keys() if "map_-" in x[0:5]]
        self._map_list = wx.ListBox(self, style=wx.LB_SINGLE, size=(175, 165),
                                    choices=real_maps)
        self._map_list.Bind(wx.EVT_LISTBOX, self.on_focus_map_list)

        self._custom_map_list = wx.ListBox(self, style=wx.LB_SINGLE, size=(175, 165),
                                           choices=[x for x in self.map_data_manager.custom_map.keys()])
        self._custom_map_list.Bind(wx.EVT_LISTBOX, self.on_focus_custom_map_list)

        self._import_image = wx.Button(self, size=(80, 50), label="Import \n and \n Settings")
        self._import_image.Bind(wx.EVT_BUTTON, self.import_image)

        self._del_sel_map = wx.Button(self, size=(80, 50), label="Delete \n Selected")
        self._del_sel_map.Bind(wx.EVT_BUTTON, self.del_sel_map)

        self._build_map_wall = wx.Button(self, size=(80, 50), label="Build \n Map Wall")
        self._build_map_wall.Bind(wx.EVT_BUTTON, self.build_map_wall)

        self._delete_all_maps = wx.Button(self, size=(80, 50), label="Delete All \n Maps")
        self._delete_all_maps.Bind(wx.EVT_BUTTON, self._run_del_maps)

        self.button_menu_sizer.Add(self._delete_all_maps, 0, wx.LEFT, 5)

        self.button_menu_sizer.Add(self._del_sel_map, 0, wx.LEFT, 5)
        self.button_menu_sizer.Add(self._build_map_wall, 0, wx.LEFT, 5)
        self.button_menu_sizer.Add(self._import_image, 0, wx.LEFT, 5)
        # self.button_menu_sizer.Add(self.apply_back_block, 0, wx.LEFT, 11)
        # self.button_menu_sizer.Add(self._set_images_on_frames, 0, wx.LEFT, 11)

        self.middle_sizer.Add(self._map_list)
        self.middle_sizer.Add(self._custom_map_list)

        self._up = wx.Button(self, label="up", size=(40, 20))
        self._up.Bind(wx.EVT_BUTTON, self._boxUp)
        self._down = wx.Button(self, label="down", size=(40, 20))
        self._down.Bind(wx.EVT_BUTTON, self._boxDown)
        self._east = wx.Button(self, label="east", size=(40, 20))
        self._east.Bind(wx.EVT_BUTTON, self._boxEast)
        self._west = wx.Button(self, label="west", size=(40, 20))
        self._west.Bind(wx.EVT_BUTTON, self._boxWest)
        self._north = wx.Button(self, label="north", size=(40, 20))
        self._north.Bind(wx.EVT_BUTTON, self._boxNorth)
        self._south = wx.Button(self, label="south", size=(40, 20))
        self._south.Bind(wx.EVT_BUTTON, self._boxSouth)

        self.move_grid = wx.GridSizer(3, 2, 1, 1)
        self.move_grid.Add(self._up)
        self.move_grid.Add(self._down)
        self.move_grid.Add(self._east)
        self.move_grid.Add(self._west)
        self.move_grid.Add(self._north)
        self.move_grid.Add(self._south)

        # Preview UI
        self.box = wx.BoxSizer(wx.VERTICAL)
        self.custom_name_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.label_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.grid_preview = wx.GridSizer(0, 0, 1, 1)

        self.box.Add(self.grid_preview, 0, wx.LEFT, 0)

        self.grid_options = wx.GridSizer(0, 3, 1, 1)
        self.button_grid_sizer = wx.BoxSizer(wx.VERTICAL)
        self.custom_map_name_label = wx.StaticText(self, label="Name Custom Map Entry:", size=(160, 25))
        self.custom_map_name = wx.TextCtrl(self, style=wx.TEXT_ALIGNMENT_LEFT)
        self.direction_label = wx.StaticText(self, label="Set The Orientation:↓", size=(125, 22))
        self.position_label = wx.StaticText(self, label="Fine Tune Box Area:↓", size=(129, 22))

        self.pointing = wx.ListBox(self, style=wx.LB_SINGLE, size=(115, 110),
                                   choices=[x for x in self.map_data_manager.pointing.keys()])

        self.facing = wx.ListBox(self, style=wx.LB_SINGLE, size=(115, 110),
                                 choices=[x for x in self.map_data_manager.facing.keys()])

        self.apply_preview = wx.Button(self, size=(80, 40), label="Place Image\n  On Frames")

        self.pointing.Bind(wx.EVT_LISTBOX, self.pointing_onclick)
        self.facing.Bind(wx.EVT_LISTBOX, self.facing_onclick)
        self.apply_preview.Bind(wx.EVT_BUTTON, self.apply_placement)
        self.custom_name_sizer.Add(self.custom_map_name_label)
        self.custom_name_sizer.Add(self.custom_map_name)
        self.label_sizer.Add(self.direction_label)
        self.label_sizer.Add(self.position_label, 0, wx.LEFT, 40)

        self.button_grid_sizer.Add(self.move_grid, 0, wx.TOP, 2)
        self.button_grid_sizer.Add(self.apply_preview, 0, wx.TOP, 6)

        self.grid_options.Add(self.pointing)
        self.grid_options.Add(self.facing)
        self.grid_options.Add(self.button_grid_sizer)

        self._sizer.Add(self.custom_name_sizer)
        self._sizer.Add(self.label_sizer)

        self._sizer.Add(self.grid_options, 0, wx.TOP, -3)
        self._sizer.Hide(self.custom_name_sizer)
        self._sizer.Hide(self.label_sizer)
        self._sizer.Hide(self.grid_options)

        self._sizer.Add(self.box)
        self._sizer.Fit(self)

        self.Layout()
        self.Thaw()

    def build_map_wall(self, _):
        map_data = []
        for name, file in self.map_data_manager.all_map.items():
            if self.platform == 'java':
                if 'map_-' not in name:
                    nbt = load(file)
                    img = self.map_data_manager.get_map_img(nbt['data'].get('colors').py_data)
                    map_data.append((img, name))
            else:
                if 'map_-' in name:
                    nbt = self.map_data_manager.all_map[name]

                    img = self.map_data_manager.get_map_img(name)
                    map_data.append((img, name))

        BuildWallSettings(self, map_data, world=self.world)

    def custom_map_wall_add(self):
        self.map_data_manager.refresh_all()
        self._map_list.SetSelection(-1)
        self._map_list.Hide()

        self._go_to_maps.Hide()

        self.clear_grid_preview()

        self.custom_map_loaded = True
        map_list, rows, cols = self.custom_map_wall
        print(self.custom_map_wall, 'yea', map_list, rows, cols)
        self.pointing.SetSelection(2)
        self.facing.SetSelection(2)
        self.map_data_manager.cols_rows = (cols, rows)
        self.selected_maps = map_list
        self.map_data_manager.maps_tobe = map_list
        self.map_data = []
        total = len(self.selected_maps)

        for m in self.selected_maps:
            # print(m,self.map_data_manager.all_map)
            self.map_data.append(self.map_data_manager.get_map_colors(m))

        def add_images(grid):
            cnt = 0
            for m in self.map_data:
                cnt += 1
                self.progress.progress_bar(total, cnt, text="Loading Map Images", title='Loading', update_interval=1)
                bb = wx.Bitmap.FromBufferRGBA(128, 128, m)
                grid.Add(wx.StaticBitmap(self, bitmap=scale_bitmap(bb, size, size)))
            return grid

        max_cell_width = 350 // cols
        max_cell_height = 350 // rows
        size = min(max_cell_width, max_cell_height)

        self.grid_preview.SetRows(rows)
        self.grid_preview.SetCols(cols)

        self.grid_preview = add_images(self.grid_preview)
        self.grid_preview.Fit(self)

        self._sizer.Show(self.custom_name_sizer)
        self._sizer.Show(self.label_sizer)
        self._sizer.Show(self.grid_options)
        self.shape_of_image()
        self._selection = StaticSelectionBehaviour(self.canvas)
        self._cursor = PointerBehaviour(self.canvas)
        self._selection.bind_events()
        self._cursor.bind_events()
        self.canvas.Bind(EVT_POINT_CHANGE, self._on_pointer_change)
        self.canvas.Bind(EVT_INPUT_PRESS, self._on_input_press)

        self._is_enabled = False
        self._moving = False
        self._map_list.Show()
        self.Fit()
        self.Update()
        self.Layout()

    def del_sel_map(self, _):
        if len(self._map_list.GetStringSelection()) > 0:
            map_ = self._map_list.GetStringSelection()
            self.map_data_manager.del_selected_map(map_)
        if len(self._custom_map_list.GetStringSelection()) > 0:
            cmap_ = self._custom_map_list.GetStringSelection()
            self.map_data_manager.del_selected_map(cmap_)
        self.map_data_manager.refresh_all()
        self._map_list.Update()
        self._custom_map_list.Update()
        self._map_list.Clear()
        self._custom_map_list.Clear()
        real_maps = None
        if self.platform == 'java':
            real_maps = [x for x in self.map_data_manager.all_map.keys() if "map_-" not in x[0:5]]
        else:
            real_maps = [x for x in self.map_data_manager.all_map.keys() if "map_-" in x[0:5]]
        self._custom_map_list.AppendItems([x for x in self.map_data_manager.custom_map.keys()])

        self._map_list.AppendItems(real_maps)

    def apply_backblock(self, _):
        if self.pointer_shape and self.pointer_shape != (1, 1, 1):
            self.old_pointer_shape = copy.copy(self.pointer_shape)

        if not hasattr(self, 'window'):
            self._initialize_window()
            self._input_press_handler = functools.partial(self._on_input_press_block_define,
                                                          block_define=self._block_define)
            self.canvas.Bind(EVT_POINT_CHANGE, self._on_pointer_change_blk)
            self.canvas.Bind(EVT_INPUT_PRESS, self._input_press_handler)
            self._block_define.Bind(EVT_PROPERTIES_CHANGE, self._on_properties_change)
        else:

            self._input_press_handler = functools.partial(self._on_input_press_block_define,
                                                          block_define=self._block_define)
            self.canvas.Bind(EVT_POINT_CHANGE, self._on_pointer_change_blk)
            self.canvas.Bind(EVT_INPUT_PRESS, self._input_press_handler)
            self._block_define.Bind(EVT_PROPERTIES_CHANGE, self._on_properties_change)
        # Show the window again if it was hidden
        self.pointer_shape = (1, 1, 1)
        self.window.Show()

    def _initialize_window(self):
        """Initialize the window and its components."""
        translation_manager = PyMCTranslate.new_translation_manager()
        self.window = wx.Frame(self, title="Choose back block", size=(500, 400),
                               style=wx.DEFAULT_FRAME_STYLE | wx.STAY_ON_TOP)
        self.window.Centre(direction=wx.VERTICAL)

        self._block_define = BlockDefine(self.window, translation_manager, wx.VERTICAL,
                                         platform=self.world.level_wrapper.platform)

        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.ok_sizer = wx.BoxSizer(wx.VERTICAL)
        self.window.SetSizer(self.sizer)
        self.ok_btn = wx.Button(self.window, label="OK", size=(100, 25))
        self.ok_btn.Bind(wx.EVT_BUTTON, self.done)

        # Set proportion to 0 to avoid stretching and align center
        self.ok_sizer.Add(self._block_define, 0, wx.LEFT, 0)
        self.ok_sizer.Add(self.ok_btn, 0, wx.ALIGN_CENTER)

        self.sizer.Add(self.ok_sizer, 1, wx.LEFT, 0)

        self.sizer.Fit(self.window)
        self.window.Layout()
        self._hide_version_select()
        self.window.Bind(wx.EVT_CLOSE, self._unbind_events)

    def done(self, _):
        self._unbind_events(None)

    def bind_events(self):
        super().bind_events()

        self.pointer_shape = (1, 1, 1)
        self._selection = StaticSelectionBehaviour(self.canvas)
        self._cursor = PointerBehaviour(self.canvas)
        self._selection.bind_events()
        self._cursor.bind_events()

        self.canvas.Bind(EVT_POINT_CHANGE, self._on_pointer_change)
        self.canvas.Bind(EVT_INPUT_PRESS, self._on_input_press)

        self._is_enabled = True
        self._moving = False

    def _unbind_events(self, event):

        self.canvas.Unbind(EVT_POINT_CHANGE, handler=self._on_pointer_change_blk)
        self.canvas.Unbind(EVT_INPUT_PRESS, handler=self._input_press_handler)
        self.canvas.Unbind(EVT_SELECTION_CHANGE)
        self._selection = StaticSelectionBehaviour(self.canvas)
        self._cursor = PointerBehaviour(self.canvas)
        self._selection.bind_events()
        self._cursor.bind_events()
        self.canvas.Bind(EVT_POINT_CHANGE, self._on_pointer_change)
        self.canvas.Bind(EVT_INPUT_PRESS, self._on_input_press)

        if hasattr(self, 'old_pointer_shape'):
            self.pointer_shape = self.old_pointer_shape

        self.window.Hide()  # Instead of destroying, just hide the window

    def _on_properties_change(self, event):
        """Handle the block properties change event."""
        self.get_block(event, self._block_define)

    def _on_selection_change(self, event):
        """Handle the selection change event."""
        self.set_block(event, self._block_define)

    def _hide_version_select(self):
        """Hide the VersionSelect component if it is shown."""
        for child in self._block_define.GetChildren():
            if isinstance(child, VersionSelect) and child.IsShown():
                child.Hide()

    def get_block(self, event, data):
        # print(data.block_name, data.properties)
        self.selected_block = data.block

        if self.world.level_wrapper.platform == 'bedrock':
            self.back_block = data.block
        else:
            block_data = CompoundTag({'Name': StringTag("minecraft:" + data.block_name)})
            if data.properties:
                block_data['Properties'] = CompoundTag(data.properties)
            self.back_block = block_data
        self.dlg.SetBlock(data.block_name)

    def set_block(self, event):
        x, y, z = self.canvas.selection.selection_group.min
        cx, cz = block_coords_to_chunk_coords(x, z)
        if self.world.has_chunk(cx, cz, self.canvas.dimension):
            block, enty = self.world.get_version_block(x, y, z, self.canvas.dimension,
                                                       (self.world.level_wrapper.platform,
                                                        self.world.level_wrapper.version))
            self.selected_block = block

            # if self.world.level_wrapper.platform == 'bedrock':
            #     self.back_block = block
            # else:
            #     block_data = CompoundTag({'Name': StringTag("minecraft:" + block.base_name)})
            #     if block.properties:
            #         block_data['Properties'] = CompoundTag(block.properties)
            #     self.back_block = block_data
            #     print(data.block_name, data.properties)

        event.Skip()

    def _on_pointer_change(self, evt: PointChangeEvent):

        if self._is_enabled:
            x, y, z = evt.point
            a, b, c = self.pointer_shape
            sg = SelectionGroup(SelectionBox((x, y, z), (x + a, y + b, z + c)))
            self.canvas.selection.set_selection_group(sg)

        evt.Skip()

    def _on_input_press_block_define(self, evt: InputPressEvent, block_define=None):

        if evt.action_id == ACT_BOX_CLICK:
            if block_define and self.selected_block:
                block_define.block = self.selected_block
                print(block_define.block)
            if self._is_enabled:
                self._moving = not self._moving
                self._is_enabled = False
                return

            if not self._is_enabled:
                self._is_enabled = True
                return
        evt.Skip()

    def import_image(self, evt):
        evt.Skip()
        self.dlg = ImportImageSettings(self, world=self.world)
        self.dlg.Show()
        # if dlg.ShowModal() == wx.ID_OK:
        #     r, g, b, a = dlg.GetSelectedColor()
        #     self.color = (r, g, b, a)

    def _on_pointer_change_blk(self, evt: PointChangeEvent):

        if self._is_enabled:
            self.set_block(evt)
            self.canvas.renderer.fake_levels.active_transform = evt.point
            x, y, z = evt.point
            a, b, c = self.pointer_shape
            sg = SelectionGroup(SelectionBox((x, y, z), (x + a, y + b, z + c)))

            self.canvas.selection.set_selection_group(sg)

        evt.Skip()

    def _on_input_press(self, evt: InputPressEvent):

        if evt.action_id == ACT_BOX_CLICK:

            if self._is_enabled:
                self._moving = not self._moving
                self._is_enabled = False
                return

            if not self._is_enabled:
                self._is_enabled = True
                return
        evt.Skip()

    def go_to_maps(self, _):
        lx, ly, lz, rx, ry, rz, cx, cy, cz, r1, r2 = self.selected_data
        self.canvas.selection.set_selection_group(SelectionGroup(SelectionBox((lx, ly, lz), (rx, ry, rz))))
        self.canvas.camera.location = (cx, cy, cz)
        self.canvas.camera.rotation = (r1, r2)

    def clear_grid_preview(self):
        sizer = self.grid_preview
        while sizer.GetItemCount() > 0:
            item = sizer.GetItem(0).GetWindow()
            sizer.Detach(0)
            if item:
                item.Destroy()

    def save_image_grid(self, _):
        grid_rows, grid_cols = self.grid_preview.GetRows(), self.grid_preview.GetCols()
        cmap = self._custom_map_list.GetStringSelection()
        imgs = self.map_data_manager.get_cmap_list_of_map_images(cmap)
        combined_img = Image.new('RGBA', (grid_cols * 128, grid_rows * 128))
        for index, img in enumerate(imgs):
            row = index // grid_cols
            col = index % grid_cols
            position = (col * 128, row * 128)
            combined_img.paste(img, position)

        with wx.FileDialog(self, "Save file", wildcard="PNG files (*.png)|*.png|All files (*.*)|*.*",
                           style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as save_dialog:

            # Show the dialog and check if the user clicked "Save"
            if save_dialog.ShowModal() == wx.ID_CANCEL:
                return  # User canceled, exit the function

            # Get the path selected by the user
            save_path = save_dialog.GetPath()
            combined_img.save(save_path, format='PNG')

    def on_focus_custom_map_list(self, evt):
        self.map_data_manager.refresh_all()
        self._map_list.SetSelection(-1)
        self._map_list.Hide()

        self._go_to_maps.Hide()

        self.clear_grid_preview()
        self._go_to_maps.Show()
        self._save_map_image.Show()
        self.custom_map_loaded = True

        custom_map_nbt = self.map_data_manager.get_custom_map_nbt(self._custom_map_list.GetStringSelection())
        lx, ly, lz, rx, ry, rz = custom_map_nbt.get('selectionGp').py_data
        cx, cy, cz = custom_map_nbt.get('location').py_data
        r1, r2 = custom_map_nbt.get('rotation').py_data
        self.selected_data = (lx, ly, lz, rx, ry, rz, cx, cy, cz, r1, r2)

        cols, rows = custom_map_nbt.get('cols').py_int, custom_map_nbt.get('rows').py_int
        pointing, facing = custom_map_nbt.get('pointing').py_int, custom_map_nbt.get('facing').py_int
        self.pointing.SetSelection(pointing)
        self.facing.SetSelection(facing)
        self.map_data_manager.cols_rows = (cols, rows)
        self.selected_maps = [s.py_str for s in custom_map_nbt.get('map_list').py_data]
        self.map_data = []
        total = len(self.selected_maps)

        for m in self.selected_maps:
            # print(m,self.map_data_manager.all_map)
            self.map_data.append(self.map_data_manager.get_map_colors(m))

        def add_images(grid):
            cnt = 0
            for m in self.map_data:
                cnt += 1
                self.progress.progress_bar(total, cnt, text="Loading Map Images", title='Loading', update_interval=1)
                bb = wx.Bitmap.FromBufferRGBA(128, 128, m)
                grid.Add(wx.StaticBitmap(self, bitmap=scale_bitmap(bb, size, size)))
            return grid

        max_cell_width = 350 // cols
        max_cell_height = 350 // rows
        size = min(max_cell_width, max_cell_height)

        self.grid_preview.SetRows(rows)
        self.grid_preview.SetCols(cols)

        self.grid_preview = add_images(self.grid_preview)
        self.grid_preview.Fit(self)

        self._sizer.Show(self.custom_name_sizer)
        self._sizer.Show(self.label_sizer)
        self._sizer.Show(self.grid_options)
        self.shape_of_image()
        self._selection = StaticSelectionBehaviour(self.canvas)
        self._cursor = PointerBehaviour(self.canvas)
        self._selection.bind_events()
        self._cursor.bind_events()
        self.canvas.Bind(EVT_POINT_CHANGE, self._on_pointer_change)
        self.canvas.Bind(EVT_INPUT_PRESS, self._on_input_press)

        self._is_enabled = False
        self._moving = False
        self._map_list.Show()
        self.Fit()
        self.Update()
        self.Layout()

        self.canvas.selection.set_selection_group(SelectionGroup(SelectionBox((lx, ly, lz), (rx, ry, rz))))

    def on_focus_map_list(self, evt):
        self.map_data_manager.refresh_all()
        self.Freeze()
        self._map_list.Hide()
        self._map_list.Show()
        self._go_to_maps.Show()
        self._go_to_maps.Hide()
        self._save_map_image.Hide()
        self._custom_map_list.SetSelection(-1)
        self.clear_grid_preview()
        self.grid_preview.Clear()
        selected_map = self._map_list.GetStringSelection()
        data_path = self.map_data_manager.all_map[selected_map]
        colors = self.map_data_manager.get_colors_from_map(data_path)
        bb = wx.Bitmap.FromBufferRGBA(128, 128, colors)
        img = wx.StaticBitmap(self, bitmap=scale_bitmap(bb, 256, 256))
        self.grid_preview.SetRows(1)
        self.grid_preview.SetCols(1)
        self.grid_preview.Add(img)

        self.grid_preview.Fit(self)
        self._sizer.Layout()  # Update layout of the parent sizer
        self.Fit()  # Adjust the size of the window to fit its content
        self.Layout()
        self.Thaw()

    def _refresh_chunk(self, dimension, world, x, z):
        cx, cz = block_coords_to_chunk_coords(x, z)
        chunk = world.get_chunk(cx, cz, dimension)
        chunk.changed = True

    def set_images_on_frames(self, event):
        self.box.Hide(self.grid_preview)
        self.custom_map_loaded = False
        self.map_data_manager.refresh_all()

        image = Image.open(self.selected_file).convert("RGBA")

        cols, rows = ceil(image.size[0] / 128), ceil(image.size[1] / 128)
        self.map_data_manager.cols_rows = (cols, rows)
        self.process_image(image)
        self.preview_ui()

    def preview_ui(self):

        self.map_data_manager.convert_images()

        def add_images(grid):
            for v in self.map_data_manager.maps_tobe:
                bb = wx.Bitmap.FromBufferRGBA(128, 128, v[0])
                grid.Add(wx.StaticBitmap(self, bitmap=scale_bitmap(bb, size, size)))
            return grid

        cols, rows = self.map_data_manager.cols_rows
        max_cell_width = 350 // cols
        max_cell_height = 350 // rows
        size = min(max_cell_width, max_cell_height)
        self.grid_preview.Hide(self, recursive=True)
        self.grid_preview.Clear()
        self.grid_preview.SetRows(rows)
        self.grid_preview.SetCols(cols)
        self.grid_preview = add_images(self.grid_preview)

        self.grid_preview.Fit(self)

        self._sizer.Show(self.custom_name_sizer)
        self._sizer.Show(self.label_sizer)
        self._sizer.Show(self.grid_options)

        self.pointing.SetSelection(2)
        self.facing.SetSelection(2)
        self._sizer.Layout()  # Update layout of the parent sizer
        self.Fit()  # Adjust the size of the window to fit its content
        self.Layout()  # Adjust the layout of the window
        self.shape_of_image()
        self._selection = StaticSelectionBehaviour(self.canvas)
        self._cursor = PointerBehaviour(self.canvas)
        self._selection.bind_events()
        self._cursor.bind_events()
        self.canvas.Bind(EVT_POINT_CHANGE, self._on_pointer_change)
        self.canvas.Bind(EVT_INPUT_PRESS, self._on_input_press)

        self._is_enabled = True
        self._moving = True

    def shape_of_image(self):
        dimensions = self.map_data_manager.cols_rows
        current_facing_direction, pointed_direction = self.facing.GetSelection(), self.pointing.GetSelection()
        if (pointed_direction in [1, 3]) and (current_facing_direction <= 1):
            self.pointer_shape = ((dimensions[1]), 1, (dimensions[0]))
        elif (pointed_direction in [0, 2]) and (current_facing_direction <= 1):
            self.pointer_shape = ((dimensions[0]), 1, (dimensions[1]))
        elif (pointed_direction in [0, 1]) and (2 <= current_facing_direction < 4):
            self.pointer_shape = ((dimensions[1]), (dimensions[0]), 1)
        elif (pointed_direction in [2, 3]) and (2 <= current_facing_direction < 4):
            self.pointer_shape = ((dimensions[0]), (dimensions[1]), 1)
        elif (pointed_direction in [0, 1]) and (current_facing_direction >= 4):
            self.pointer_shape = (1, (dimensions[0]), (dimensions[1]))
        elif (pointed_direction in [2, 3]) and (current_facing_direction >= 4):
            self.pointer_shape = (1, (dimensions[1]), (dimensions[0]))

    def pointing_onclick(self, _):

        self.shape_of_image()
        self._is_enabled = True
        self._moving = True

    def facing_onclick(self, _):
        facing_selected = self.facing.GetSelection()
        pointing_selected = self.pointing.GetSelection()
        if facing_selected <= 1:
            self.pointing.Clear()
            self.pointing.AppendItems(["Top Image North", "Top Image East", "Top Image South", "Top Image West"])
            self.pointing.SetSelection(pointing_selected)
        elif facing_selected >= 2:
            self.pointing.Clear()
            self.pointing.AppendItems(["Flip Right", "Flip Left", "Up (Like Preview)", "Upside Down"])
            self.pointing.SetSelection(pointing_selected)

        self.shape_of_image()
        self._is_enabled = True
        self._moving = True

    def apply_placement(self, _):
        if self.custom_map_loaded:
            self.boxSetter(map_key_list=self.selected_maps)
        else:
            self.boxSetter()

    def process_image(self, image, tile_size=128):
        color = self.color
        image_array = numpy.array(image)
        height, width = image_array.shape[:2]
        new_height = (height + tile_size - 1) // tile_size * tile_size
        new_width = (width + tile_size - 1) // tile_size * tile_size
        new_image_array = numpy.full((new_height, new_width, 4), color, dtype=numpy.uint8)
        pad_top = (new_height - height) // 2
        pad_left = (new_width - width) // 2
        new_image_array[pad_top:pad_top + height, pad_left:pad_left + width] = image_array

        for y in range(0, new_height, tile_size):
            for x in range(0, new_width, tile_size):
                tile = new_image_array[y:y + tile_size, x:x + tile_size]
                flattened_pixels = tile.reshape(-1).tobytes()
                self.map_key = self.map_data_manager.get_available_map_key
                print(self.map_key)
                map_id = int(self.map_key.replace('map_', ''))
                self.map_data_manager.maps_tobe.append((flattened_pixels, map_id, self.map_key))

    def boxSetter(self, map_key_list=None):
        self.map_data_manager.apply(map_key_list=map_key_list)

    def reorder_coordinates(self):
        pointing_value, facing_value = self.pointing.GetSelection(), self.facing.GetSelection()
        cords = []
        for x, y, z in self.canvas.selection.selection_group.blocks:
            cords.append((x, y, z))
        transformation_data = {
            # Facing Down
            (0, 0): (2, 0, 270, False, [0]),  # North or Right
            (0, 1): (0, 2, 225, False, [0, 2]),  # East or Left
            (0, 2): (2, 0, 180, True, [0]),  # South or Up
            (0, 3): (0, 2, 315, True, [0, 2]),  # West or Down
            # Facing Up
            (1, 0): (2, 0, 0, False, None),  # North or Right
            (1, 1): (0, 2, 225, False, [0]),  # East or Left
            (1, 2): (2, 0, 270, True, None),  # South or Up
            (1, 3): (0, 2, 315, True, [0]),  # West or Down
            # Facing North
            (2, 0): (0, 1, 225, False, [1]),  # North or Right
            (2, 1): (0, 1, 315, True, [1]),  # East or Left
            (2, 2): (1, 0, 180, True, None),  # South or Up
            (2, 3): (1, 0, 270, False, None),  # West or Down
            # Facing South
            (3, 0): (0, 1, 45, False, [1, 0]),  # North or Right
            (3, 1): (0, 1, 315, True, [1, 0]),  # East or Left
            (3, 2): (1, 0, 0, True, [0]),  # South or Up
            (3, 3): (1, 0, 270, False, [0]),  # West or Down
            # Facing West
            (4, 0): (2, 1, 225, False, [1, 2]),  # North or Right
            (4, 1): (2, 1, 315, True, [1, 2]),  # East or Left
            (4, 2): (1, 2, 180, True, [2]),  # South or Up
            (4, 3): (1, 2, 270, False, [2]),  # West or Down
            # Facing East
            (5, 0): (2, 1, 45, False, [1]),  # North or Right
            (5, 1): (2, 1, 315, True, [1]),  # East or Left
            (5, 2): (1, 2, 180, True, None),  # South or Up
            (5, 3): (1, 2, 270, False, None),  # West or Down
        }

        primary_sort_axis, secondary_sort_axis, rotation, reverse, axis_reverse = (
            transformation_data)[(facing_value, pointing_value)]

        coords_array = numpy.array(cords)
        coords_array = coords_array[
            numpy.lexsort((coords_array[:, secondary_sort_axis], coords_array[:, primary_sort_axis]))]

        if axis_reverse:
            for x in axis_reverse:
                coords_array[:, x] = coords_array[:, x][::-1]
        if reverse:
            coords_array = coords_array[::-1]

        cords_sorted = [tuple(coord) for coord in coords_array]
        return cords_sorted, rotation

    def _run_del_maps(self, _):

        wxx = wx.MessageBox("You are going to deleted EVERY MAP \n Every entry in the list",
                            "This can't be undone Are you Sure?", wx.OK | wx.CANCEL | wx.ICON_INFORMATION)
        if wxx == int(16):
            return
        self.Freeze()
        self.map_data_manager.delete_all_maps()
        self.map_data_manager.refresh_all()
        self._map_list.Update()
        self._custom_map_list.Update()
        self._map_list.Clear()
        self._custom_map_list.Clear()
        self._custom_map_list.AppendItems([x for x in self.map_data_manager.custom_map.keys()])
        self._map_list.AppendItems([x for x in self.map_data_manager.all_map.keys()])
        self.clear_grid_preview()
        self.grid_preview.Hide(self, recursive=True)
        self.grid_preview.Clear()
        self._sizer.Hide(self.custom_name_sizer)
        self._sizer.Hide(self.label_sizer)
        self._sizer.Hide(self.grid_options)
        self._sizer.Fit(self)
        self.Fit()
        self.Layout()
        self.Thaw()

    def _move_box(self, dx=0, dy=0, dz=0):
        for box in self.canvas.selection.selection_group.selection_boxes:
            xx, yy, zz = box.max_x, box.max_y, box.max_z
            xm, ym, zm = box.min_x, box.min_y, box.min_z
            sg = SelectionGroup(SelectionBox((xm + dx, ym + dy, zm + dz), (xx + dx, yy + dy, zz + dz)))
            self.canvas.selection.set_selection_group(sg)

    def _boxUp(self, _):
        self._move_box(dy=1)

    def _boxDown(self, _):
        self._move_box(dy=-1)

    def _boxNorth(self, _):
        self._move_box(dz=-1)

    def _boxSouth(self, _):
        self._move_box(dz=1)

    def _boxEast(self, _):
        self._move_box(dx=1)
        for box in self.canvas.selection.selection_group.selection_boxes:
            xx, yy, zz = box.max_x + 1, box.max_y, box.max_z  # Reflect the updated position
            self.pointer_shape = [xx, yy, zz]

    def _boxWest(self, _):
        self._move_box(dx=-1)

class FinderReplacer(wx.Frame):
    def __init__(self, parent, canvas, world, *args, **kw):
        super(FinderReplacer, self).__init__(parent, *args, **kw,
                                             style=(wx.MINIMIZE_BOX | wx.MAXIMIZE_BOX | wx.RESIZE_BORDER |
                                                    wx.SYSTEM_MENU | wx.CAPTION | wx.CLOSE_BOX | wx.CLIP_CHILDREN |
                                                    wx.FRAME_FLOAT_ON_PARENT),
                                             title="Finder Replacer")

        self.parent = parent

        self.canvas = canvas
        self.world = world
        self.font = wx.Font(13, wx.FONTFAMILY_ROMAN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        self.SetFont(self.font)
        self.SetMinSize((320, 600))

        self.version = self.world.level_wrapper.version
        self.platform = self.world.level_wrapper.platform
        self.chunks_done = None
        if self.platform == 'bedrock':
            self.found_data = FoundData(world=self.world, canvas=self.canvas)
            self.find_level_data = ProcessLevelDB(self.found_data, parent=self, world=self.world, canvas=self.canvas)

        else:
            self.found_data = FoundData(world=self.world, canvas=self.canvas)
            self.find_level_data = ProcessAnvilBD(self.found_data, parent=self, world=self.world, canvas=self.canvas)

        self.Freeze()
        self.font = wx.Font(14, wx.FONTFAMILY_ROMAN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        self.SetFont(self.font)
        self.SetForegroundColour((0, 255, 0))
        self.SetBackgroundColour((0, 0, 0))
        self.arr = {}
        self._sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self._sizer)
        self.toggle = True
        self.Pages = []
        self.OrgCopy = []
        self.top_sizer = wx.BoxSizer(wx.VERTICAL)
        self.top = wx.BoxSizer(wx.HORIZONTAL)
        self.top_layer_two = wx.BoxSizer(wx.HORIZONTAL)
        self.topTable = wx.BoxSizer(wx.HORIZONTAL)
        self.top_text = wx.BoxSizer(wx.HORIZONTAL)
        self.side_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.saveload = wx.BoxSizer(wx.HORIZONTAL)
        self.above_grid = wx.BoxSizer(wx.HORIZONTAL)
        self.selectionOptions = wx.BoxSizer(wx.VERTICAL)

        self._sizer.Add(self.top, 0, wx.TOP | wx.LEFT, 0)
        self._sizer.Add(self.top_layer_two, 0, wx.TOP | wx.LEFT, 0)
        self._sizer.Add(self.selectionOptions, 0, wx.TOP | wx.LEFT, 0)
        self._sizer.Add(self.side_sizer, 1, wx.TOP | wx.LEFT, 0)
        self._sizer.Add(self.saveload, 0, wx.TOP | wx.LEFT, 0)
        self._sizer.Add(self.above_grid, 0, wx.TOP | wx.LEFT, 0)

        self._sizer.Add(self.topTable, 0, wx.TOP | wx.LEFT, 0)

        self._run_buttonF = wx.Button(self, label="Find", size=(70, 30))
        self._run_buttonF.Bind(wx.EVT_BUTTON, self._start_the_search)

        self.labelFindBlocks = wx.StaticText(self, label=" Search For Blocks:    ")
        self.labelFind = wx.StaticText(self, label="Find: ")
        self.labelRep = wx.StaticText(self, label="Replace: ")
        self.labelFind_e = wx.StaticText(self, label="Find Extra Block: ")
        self.labelRep_e = wx.StaticText(self, label="Replace Extra Block: ")

        self.textSearch = wx.TextCtrl(self, style=wx.TE_LEFT | wx.TE_BESTWRAP, size=(180, 30))
        self.textF = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_BESTWRAP, size=(272, 120))
        self.textF_Extra = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_BESTWRAP, size=(272, 120))
        self.textR = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_BESTWRAP, size=(272, 120))
        self.textR_Extra = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_BESTWRAP, size=(272, 120))
        self.grid_tc_find = wx.GridSizer(0, 2, 4, 4)
        self.grid_tc_find.Add(self.labelFindBlocks, 0, wx.LEFT, 0)
        self.grid_tc_find.Add(self.textSearch, 0, wx.LEFT, -20)
        self.top.Add(self.grid_tc_find, 0, wx.TOP, 20)

        self.gsizer_but_and_chk = wx.GridSizer(3, 2, 5, 5)

        self._position_selection = wx.Button(self, label="Position Selection", size=(138, 24))
        self._position_selection.Bind(wx.EVT_BUTTON, self.position_selection)
        self._fast_apply = wx.Button(self, label="Fast_apply")
        self._SPACE_2 = wx.StaticText(self, label=" ")
        self._SPACE = wx.StaticText(self, label=" ")
        self._fast_apply.Bind(wx.EVT_BUTTON, self.fast_apply)
        self._set_max_found = wx.StaticText(self, label="Pause After this many items Found:    ")
        self.set_max_found_input = wx.TextCtrl(self, style=wx.TE_LEFT | wx.TE_BESTWRAP, size=(120, 22))
        self.set_max_found_input.SetValue("12345")
        self._set_is_pop_out = wx.CheckBox(self, label='Pop Out table as window')

        self.gsizer_but_and_chk.Add(self._position_selection, 0, wx.LEFT, 5)
        self.gsizer_but_and_chk.Add(self._run_buttonF, 0, wx.LEFT, 0)
        self.gsizer_but_and_chk.Add(self._set_is_pop_out, 0, wx.LEFT, 15)
        self.gsizer_but_and_chk.Add(self._fast_apply, 0, wx.LEFT, -50)

        self.gsizer_but_and_chk.Add(self._set_max_found, 0, wx.LEFT, 0)
        self.gsizer_but_and_chk.Add(self.set_max_found_input, 0, wx.LEFT, 0)

        self.top_layer_two.Add(self.gsizer_but_and_chk, 0, wx.TOP, -70)
        self.SearchFGrid = wx.GridSizer(4, 0, 0, 0)
        self.SearchFGrid.Add(self.labelFind)
        self.SearchFGrid.Add(self.textF, 0, wx.TOP, -50)
        self.SearchFGrid.Add(self.labelRep)
        self.SearchFGrid.Add(self.textR, 0, wx.TOP, -50)
        self.SearchFGrid_Extra = wx.GridSizer(4, 0, 0, 0)
        self.SearchFGrid_Extra.Add(self.labelFind_e)
        self.SearchFGrid_Extra.Add(self.textF_Extra, 0, wx.TOP, -50)
        self.SearchFGrid_Extra.Add(self.labelRep_e)
        self.SearchFGrid_Extra.Add(self.textR_Extra, 0, wx.TOP, -50)

        self.fr_sizer = wx.BoxSizer(wx.HORIZONTAL)
        if self.platform == 'java':
            self.textF_Extra.Hide()
            self.textR_Extra.Hide()
            self.labelFind_e.Hide()
            self.labelRep_e.Hide()
            self.fr_sizer.Add(self.SearchFGrid, 0, wx.LEFT, 120)
        else:
            self.fr_sizer.Add(self.SearchFGrid, 0, wx.TOP, 0)

        self.fr_sizer.Add(self.SearchFGrid_Extra, 0, wx.TOP, 0)
        self.selectionOptions.Add(self.fr_sizer, 0, wx.TOP, 0)

        self.raw_apply = wx.Button(self, label="Direct Apply")
        self.raw_apply.Bind(wx.EVT_BUTTON, self.apply_raw)  # apply_raw
        self.open_block_window = wx.Button(self, label="Find Replace Helper")
        self.open_block_window.Bind(wx.EVT_BUTTON, self.block_list)

        self.labelfilter = wx.StaticText(self, label="Filter Whats selected:")
        self.textfilter = wx.TextCtrl(self, style=wx.TE_LEFT | wx.TE_BESTWRAP, size=(70, 20))
        self.selPosAbove = wx.Button(self, label="Select Found")
        self.selPosAbove.Bind(wx.EVT_BUTTON, self.select_the_blocks)

        self.listSearchType = {
            "Strict Selection": 0,
            "Selection to Chucks": 1,
            "Every Chunk": 2
        }

        self.lst_mode = CustomRadioBox(self, 'Select Search Mode', [*self.listSearchType], (0, 255, 0))

        # self.sel = wx.Button(self, label="Un/Select")
        # self.sel.Bind(wx.EVT_BUTTON, self._sel)
        self.loadJ = wx.Button(self, label="Load")
        self.loadJ.Bind(wx.EVT_BUTTON, self.loadjson)
        self.saveJ = wx.Button(self, label="Save")
        self.saveJ.Bind(wx.EVT_BUTTON, self.savejson)
        self.find_rep = wx.Button(self, label="Replace")
        self.find_rep.Bind(wx.EVT_BUTTON, self.findReplace)

        self.saveload.Add(self.loadJ, 5, wx.LEFT, 2)
        self.saveload.Add(self.saveJ, 0, wx.TOP, 0)
        self.saveload.Add(self.find_rep, 5, wx.LEFT, 10)
        self.saveload.Add(self.raw_apply, 0, wx.LEFT, 10)
        self.continue_button = wx.Button(self, label="Continue \nSearching Chunks")
        self.continue_button.Bind(wx.EVT_BUTTON, self.continue_search)
        self.saveload.Add(self.continue_button, 0, wx.LEFT, 10)
        self.continue_button.Hide()
        self.saveload.Fit(self)

        self.top.Add(self.lst_mode, 10, wx.LEFT, 35)
        self.bottom_buttons = wx.BoxSizer(wx.HORIZONTAL)
        self.bottom_buttons.Add(self.open_block_window, 0, wx.LEFT, 2)
        self.bottom_buttons.Add(self.labelfilter, 0, wx.LEFT, 2)
        self.bottom_buttons.Add(self.textfilter, 0, wx.LEFT, 2)
        self.bottom_buttons.Add(self.selPosAbove, 0, wx.LEFT, 2)
        self.selectionOptions.Add(self.bottom_buttons)

        self._the_data = wx.grid.Grid(self, size=(520, 440), style=5)
        self._the_data.Hide()
        self._sizer.Fit(self)
        self.toggle_count = 0
        if self.platform == 'bedrock':
            self.set_version_block()
        self.Layout()
        self.Thaw()

    def position_selection(self, _):
        position_ = PositionSelection(self.parent, self.font, self.canvas, self.world)
        position_.Show()

    def set_version_block(self):
        for k, v in self.find_level_data.level_db.iterate(start=b'\x00',
                                                          end=b'\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff'):
            if k[-2] == 47:
                d = v.find(b'version')
                version = struct.unpack('<i', v[d + 7:d + 7 + 4])[0]
                self.find_level_data.block_version = IntTag(version)
                break

    def fast_apply(self, _):
        mode = self.lst_mode.GetSelection()
        if mode < 1:
            wx.MessageBox(f'Only Works on Selection To Chunks \n'
                          f'Or Every Chunk Modes', "Unsupported Mode", wx.OK | wx.ICON_INFORMATION)
        else:
            old, new, mode, name, ex_old, ex_new, ex_name = None, None, mode, None, None, None, None

            old_snbt, new_snbt = self.textF.GetValue(), self.textR.GetValue()
            old_snbt_e, new_snbt_e = self.textF_Extra.GetValue(), self.textR_Extra.GetValue()
            self.test_nbt(old_snbt)
            self.test_nbt(new_snbt)
            if len(old_snbt) > 2 and len(new_snbt) > 2:
                old, new = from_snbt(old_snbt), from_snbt(new_snbt)
                if self.platform == 'bedrock':
                    name = old.get('name').py_str.encode()
                else:
                    name = old.get('Name').py_str

            self.test_nbt(old_snbt_e)
            self.test_nbt(new_snbt_e)
            if len(old_snbt_e) > 2 and len(new_snbt_e) > 2:
                ex_old, ex_new = from_snbt(old_snbt_e), from_snbt(new_snbt_e)
                if self.platform == 'bedrock':
                    ex_name = ex_old.get('name').py_str.encode()
                else:
                    ex_name = ex_old.get('Name').py_str

            self.world.purge()
            self.find_level_data.fast_apply(old=old, new=new, mode=mode, name=name,
                                            ex_old=ex_old, ex_new=ex_new, ex_name=ex_name)

            self.canvas.renderer.render_world.chunk_manager.unload()
            self.canvas.renderer.render_world.unload()
            self.canvas.renderer.render_world.enable()
            self.canvas.renderer.render_world.chunk_manager.rebuild()

    def set_block(self, event, data):
        x, y, z = self.canvas.selection.selection_group.min
        block, enty = self.world.get_version_block(x, y, z, self.canvas.dimension,
                                                   (self.platform,
                                                    self.version))
        try:
            e_block_u = self.world.get_block(x, y, z, self.canvas.dimension).extra_blocks[0]
            pf, vb = self.platform, self.version
            e_block = self.world.translation_manager.get_version(pf, vb).block.from_universal(e_block_u)[0]
            the_extra_snbt = f'{{\n "name":"{e_block.namespaced_name}"\n' \
                             f'"states":{amulet_nbt.from_snbt(str(e_block.properties)).to_snbt(1)},'
            eblock = the_extra_snbt
            self.block_prop_extra.SetValue(eblock)
        except:
            the_e = f"None"
            self.block_prop_extra.SetValue(the_e)
        if self.platform == 'java':
            if len(CompoundTag(block.properties)) > 0:
                the_snbt = f'{{\n"Name":"{block.namespaced_name}",' \
                           f'\n "Properties":{CompoundTag(block.properties).to_snbt(1)}\n}}'
            else:
                the_snbt = f'{{\n"Name":"{block.namespaced_name}"\n}}'

        else:
            the_snbt = f'{{\n"name":"{block.namespaced_name}",' \
                       f'\n "states":{CompoundTag(block.properties).to_snbt(1)}\n}}'

        self.block_prop.SetValue(the_snbt)

        data.block = block
        self.toggle = False

    def get_block(self, event, data):
        if self.platform == 'java':
            if len(CompoundTag(data.block.properties)) > 0:

                the_snbt = f'{{\n "Name":"{data.block.namespaced_name}",' \
                           f'\n "Properties":{CompoundTag(data.block.properties).to_snbt(1)}\n}}'
            else:
                the_snbt = f'{{\n "Name":"{data.block.namespaced_name}"\n}}'

        else:
            the_snbt = f'{{\n "name":"{data.block.namespaced_name}",' \
                       f'\n "states":{CompoundTag(data.block.properties).to_snbt(1)}\n}}'

        self.block_prop.SetValue(the_snbt)

    def block_list(self, _):
        try:
            self.window.Hide()
            self.window.Close()
        except:
            pass
        self.window = wx.Frame(self.parent, title="Find Replace Helper", size=(880, 870),
                               style=wx.DEFAULT_FRAME_STYLE | wx.STAY_ON_TOP)
        self.window.SetFont(self.font)

        self.window.SetBackgroundColour((120, 220, 255))

        self.window.Centre(direction=wx.VERTICAL)
        self.w_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.window.SetSizer(self.w_sizer)
        if True:
            self.chosen_platform = self.platform
            self.chosen_name_space = "minecraft"
        self._block_define = BlockDefine(
            self.window,
            self.world.translation_manager,
            wx.VERTICAL,
            force_blockstate=False,
            namespace=self.chosen_name_space,
            *([self.chosen_platform]),
            show_pick_block=True
        )

        self._block_define.Bind(EVT_PROPERTIES_CHANGE, lambda event: self.get_block(event, self._block_define))
        self.canvas.Bind(EVT_SELECTION_CHANGE, lambda event: self.set_block(event, self._block_define))
        self.block_prop = wx.TextCtrl(
            self.window, style=wx.TE_MULTILINE | wx.TE_BESTWRAP, size=(422, 280))
        self.block_prop_extra = wx.TextCtrl(
            self.window, style=wx.TE_MULTILINE | wx.TE_BESTWRAP, size=(422, 280))

        self.copy_find = wx.Button(self.window, label="Copy Block \n to Search")
        self.copy_find.Bind(wx.EVT_BUTTON, self.copy_find_select)
        self.copy_find_ra = wx.Button(self.window, label="Copy to Find \n match all existing properties"
                                      )
        self.copy_find_ra.Bind(wx.EVT_BUTTON, self.copy_find_select_ra)
        self.copy_to_find_button = wx.Button(self.window, label="Copy To Find")
        self.copy_to_find_extra_button = wx.Button(self.window, label="Copy To Find Extra")
        self.copye_to_replace_button = wx.Button(self.window, label="Copy To Replace")
        self.copye_to_replace_extra_button = wx.Button(self.window, label="Copy To Replace Extra")
        self.copyex_to_replace_extra_button = wx.Button(self.window, label="Copy To Replace Extra")

        self.label_info = wx.StaticText(self.window, label="You Can also Select A Block To get the info")
        self.block_info = wx.StaticText(self.window, label="Block")
        self.extrablock_info = wx.StaticText(self.window, label="Extra Block")

        self.copy_to_find_button.Bind(wx.EVT_BUTTON, self.copy_to_find)
        self.copy_to_find_extra_button.Bind(wx.EVT_BUTTON, self.copy_to_find_extra)
        self.copye_to_replace_button.Bind(wx.EVT_BUTTON, self.copy_to_replace)
        self.copye_to_replace_extra_button.Bind(wx.EVT_BUTTON, self.copy_to_repace_extra)
        self.copyex_to_replace_extra_button.Bind(wx.EVT_BUTTON, self.copy_extra_to_find_extra)

        self.grid_top_ew = wx.GridSizer(1, 2, 0, 0)

        self.grid_top_ew.Add(self.copy_to_find_button, 0, wx.LEFT, 0)
        self.grid_top_ew.Add(self.copy_to_find_extra_button, 0, wx.LEFT, 0)

        self.grid_bot_ew = wx.GridSizer(1, 2, 0, 0)
        self.grid_bot_ew.Add(self.copye_to_replace_button, 0, wx.LEFT, 0)
        self.grid_bot_ew.Add(self.copye_to_replace_extra_button, 0, wx.LEFT, 0)

        self.grid_box_pop = wx.BoxSizer(wx.VERTICAL)
        if self.platform == 'java':
            self.extrablock_info.Hide()
            self.copy_to_find_extra_button.Hide()
            self.copye_to_replace_extra_button.Hide()
            self.copyex_to_replace_extra_button.Hide()
            self.block_prop_extra.Hide()
            self.grid_box_pop.Add(self.label_info, 0, wx.TOP, 100)
            self.grid_box_pop.Add(self.copy_find_ra, 0, wx.TOP, 0)

            self.window.SetSize((880, 770))

        else:
            self.grid_box_pop.Add(self.label_info, 0, wx.TOP, 20)
            self.grid_box_pop.Add(self.copy_find_ra, 0, wx.TOP, 0)

        self.grid_box_pop.Add(self.grid_top_ew)
        self.grid_box_pop.Add(self.block_info)
        self.grid_box_pop.Add(self.block_prop)
        self.grid_box_pop.Add(self.grid_bot_ew)

        self.grid_box_pop.Add(self.extrablock_info, 0, wx.TOP, 60)
        self.grid_box_pop.Add(self.block_prop_extra, 0, wx.TOP, 1)
        self.grid_box_pop.Add(self.copyex_to_replace_extra_button, wx.TOP, 5)

        self.grid_left = wx.GridSizer(2, 1, -470, 0)
        self.grid_left.Add(self.copy_find, 0, wx.LEFT, 120)
        self.grid_left.Add(self._block_define, 0, wx.TOP, -55)
        self.w_sizer.Add(self.grid_left)
        self.w_sizer.Add(self.grid_box_pop)

        self._block_define.Fit()
        self._block_define.Layout()
        self.grid_box_pop.Layout()

        self.window.Bind(wx.EVT_CLOSE, lambda event: self.OnClose(event))
        self.window.Enable()
        self.window.Show(True)

    def copy_find_select(self, _):
        if self.platform == 'java':
            block_name = f'"minecraft:{self._block_define.block_name}"'
            self.textSearch.SetValue(block_name)
        else:
            block_name = f'"minecraft:{self._block_define.block_name}"'
            self.textSearch.SetValue(block_name)

    def copy_find_select_ra(self, _):

        if self.platform == "java":
            self.textF.SetValue(f'{{\n'
                                f'"Name":"{self._block_define.block.namespaced_name}",\n"Properties":"*"\n}}')
        else:
            self.textF.SetValue(f'{{\n'f'"name":"{self._block_define.block.namespaced_name}",\n"states":"*"\n}}')

    def copy_to_find(self, _):
        self.textF.SetValue(self.block_prop.GetValue())

    def copy_to_find_extra(self, _):
        self.textF_Extra.SetValue(self.block_prop.GetValue())

    def copy_to_replace(self, _):
        self.textR.SetValue(self.block_prop.GetValue())

    def copy_to_repace_extra(self, _):
        self.textR_Extra.SetValue(self.block_prop.GetValue())

    def copy_extra_to_find_extra(self, _):
        self.textF_Extra.SetValue(self.block_prop_extra.GetValue())

    def OnClose(self, event):
        self.canvas.Unbind(EVT_SELECTION_CHANGE)
        self.window.Show(False)

    def block(self, block):
        self._picker.set_namespace(block.namespace)
        self._picker.set_name(block.base_name)
        self._update_properties()
        self.properties = block.properties

    def _boxMove(self, direction, v):
        def OnClick(event):
            sgs = []
            # Define movement operations for each direction
            move_operations = {
                'up': lambda xm, ym, zm, xx, yy, zz, v: (
                    (xm, ym + (1 if v == 'm' else 0), zm),
                    (xx, yy + (1 if v == 'm' else v), zz)
                ),
                'down': lambda xm, ym, zm, xx, yy, zz, v: (
                    (xm, ym - (1 if v == 'm' else v), zm),
                    (xx, yy - (1 if v == 'm' else 0), zz)
                ),
                'north': lambda xm, ym, zm, xx, yy, zz, v: (
                    (xm, ym, zm - (1 if v == 'm' else v)),
                    (xx, yy, zz - (1 if v == 'm' else 0))
                ),
                'south': lambda xm, ym, zm, xx, yy, zz, v: (
                    (xm, ym, zm + (1 if v == 'm' else 0)),
                    (xx, yy, zz + (1 if v == 'm' else v))
                ),
                'east': lambda xm, ym, zm, xx, yy, zz, v: (
                    (xm + (1 if v == 'm' else 0), ym, zm),
                    (xx + (1 if v == 'm' else v), yy, zz)
                ),
                'west': lambda xm, ym, zm, xx, yy, zz, v: (
                    (xm - (1 if v == 'm' else v), ym, zm),
                    (xx - (1 if v == 'm' else 0), yy, zz)
                )
            }

            move_fn = move_operations.get(direction)
            if move_fn:
                for box in self.canvas.selection.selection_group.selection_boxes:
                    xm, ym, zm = box.min_x, box.min_y, box.min_z
                    xx, yy, zz = box.max_x, box.max_y, box.max_z

                    new_min, new_max = move_fn(xm, ym, zm, xx, yy, zz, v)
                    sgs.append(SelectionBox(new_min, new_max))

                self.canvas.selection.set_selection_group(SelectionGroup(sgs))

        return OnClick

    def onFocus(self, evt):
        setdata = res[self._history.GetString(self._history.GetSelection())]
        self._the_data.SetValue(setdata)

    def test_nbt(self, data):
        if data == '':
            data = "{}"
        try:
            nbt = from_snbt(data)
            return nbt
        except SNBTParseError as e:
            wx.MessageBox(f'Data Needs to be SNBT this "{data}" has {e}', "From SNBT Failed"
                          , wx.OK | wx.ICON_INFORMATION)

    def findReplace(self, _):

        data = self.found_data.get_data()  # Get the data
        block_find = self.test_nbt(self.textF.GetValue())
        block_replace = self.test_nbt(self.textR.GetValue())
        e_block_find = self.test_nbt(self.textF_Extra.GetValue())
        e_block_replace = self.test_nbt(self.textR_Extra.GetValue())
        key_for_state = 'states'
        block_name = 'name'
        if self.platform == 'java':
            key_for_state = 'Properties'
            block_name = 'Name'
        nbt_state = False
        e_nbt_state = False

        if block_find.get(key_for_state, None) == StringTag("*"):
            nbt_state = True

        if e_block_find.get(key_for_state, None) == StringTag("*"):
            e_nbt_state = True

        for key, value in data.items():
            for sub_key in value:
                if sub_key == "block_data":

                    if nbt_state:
                        if data[key][sub_key][block_name].py_str == block_find[block_name].py_str:
                            data[key][sub_key] = block_replace
                    else:
                        if data[key][sub_key] == block_find:
                            data[key][sub_key] = block_replace

                elif sub_key == "extra_block":
                    if e_nbt_state:
                        if data[key][sub_key][block_name].py_str == e_block_find[block_name].py_str:
                            data[key][sub_key] = e_block_replace
                    else:
                        if data[key][sub_key] == e_block_find:
                            data[key][sub_key] = e_block_replace
                else:
                    if e_block_replace.get('id', None):
                        if data[key][sub_key] == e_block_find:
                            data[key][sub_key] = e_block_replace

        self.check_for_pages()

    def savejson(self, _):

        fdlg = wx.FileDialog(self, "Save Block Data", "", "",
                             f"{self.platform}_block_data: "
                             f"(*.{self.platform}_block_data)|*.{self.platform}_block_data", wx.FD_SAVE)
        if fdlg.ShowModal() == wx.ID_OK:
            pathto = fdlg.GetPath()
            if f".{self.platform}_block_data" not in pathto:
                pathto = pathto + f".{self.platform}_block_data"
            with open(pathto, "wb") as file:
                file.write(zlib.compress(pickle.dumps((self.found_data.data, self.found_data.backup))))

    def loadjson(self, _):
        fdlg = wx.FileDialog(self, "Load Block Data", "", "",
                             f"{self.platform}_block_data: "
                             f"(*.{self.platform}_block_data)|*.{self.platform}_block_data", wx.FD_OPEN)
        if fdlg.ShowModal() == wx.ID_OK:
            pathto = fdlg.GetPath()
            with open(pathto, 'rb') as f:
                found_data_backup = pickle.loads(zlib.decompress(f.read()))

            self.found_data.data, self.found_data.backup = found_data_backup
            if self.found_data.data.obj_list == self.found_data.backup.obj_list:
                difference = ("match each other \n Direct Apply will not do anything until you make a change or "
                              "\n maybe click Yes unless eveything is still the same.")
            else:
                difference = "DO NOT matching each other\n Direct Apply will make some changes without replacing"

            result = wx.MessageBox(
                f'Do you want to update the block comparison \n'
                f'layer to match the blocks in the world? This is good for directly restoring Origanl Blocks\n'
                f'Click "NO" to use the saved comparison layer from the file.\n\n'
                f'The comparison layers : {difference}\n\n'
                f'Note: If this is used in a different world than the original, you may encounter errors.',
                f"QUESTION",
                wx.YES | wx.NO | wx.ICON_ASTERISK
            )

            if result == wx.YES:
                self.find_level_data.get_blocks_by_locations(self.found_data.data)
            else:
                self.check_for_pages()

    def apply_raw(self, _):
        mode = self.lst_mode.GetSelection()
        self.world.purge()

        self.found_data = self.find_level_data.apply(mode)
        self.found_data.reset_backup(self.found_data.data)

        self.canvas.renderer.render_world.chunk_manager.unload()
        self.canvas.renderer.render_world.unload()
        self.canvas.renderer.render_world.enable()
        self.canvas.renderer.render_world.chunk_manager.rebuild()

    def search_data(self):
        search = self.textSearch.GetValue()
        mode = self.lst_mode.GetSelection()
        if search == '':
            wx.MessageBox(f'Search cant be empty', "Search Empty"
                          , wx.OK | wx.ICON_INFORMATION)
            return None, None, None, None
        if "|" in search:
            platform_entitiy = search.replace('minecraft:', '').replace('_', '. .').title().replace(". .", '')
            search_ = search.split("|")
            block_search_keys = [x.lower() for x in search_]
            if self.platform == 'bedrock':
                for s in platform_entitiy:
                    search_.append(s)
            block_e_search_keys = [x for x in search_]
        else:
            platform_entitiy = search.replace('minecraft:', '').replace('_', '. .').title().replace(". .", '')
            block_search_keys = [search.lower()]
            block_e_search_keys = [search.lower()]
            if self.platform == 'bedrock':
                block_e_search_keys.append(platform_entitiy)

        return search, mode, block_search_keys, block_e_search_keys

    def hide_the_row_with_cols(self):
        try:
            for item in self.above_grid.GetChildren():
                window = item.GetWindow()
                if window:
                    window.Hide()
                    window.Destroy()
                else:
                    self.sizer.Detach(item)
        except:
            pass

    def _start_the_search(self, _):

        pause_count = int(self.set_max_found_input.GetValue())
        self.find_level_data.pause_count = pause_count
        self.continue_button.Hide()
        self.chunks_done = None
        search, mode, block_search_keys, block_e_search_keys = self.search_data()
        if search:
            if self.platform == 'bedrock':

                self.chunks_done, self.found_data = self.find_level_data.search_raw(
                    block_search_keys, block_e_search_keys, search, mode)
                if self.chunks_done:
                    self.Freeze()
                    self.continue_button.Show()
                    # self.check_for_pages()
                    self.Layout()
                    self.Thaw()
            else:
                self.chunks_done, self.found_data = self.find_level_data.search_raw(
                    block_search_keys, block_e_search_keys, search, mode)
                if self.chunks_done:
                    self.Freeze()
                    self.continue_button.Show()
                    # self.check_for_pages()
                    self.Layout()
                    self.Thaw()

            if len(self.found_data.data) > 0 and search:
                self.Freeze()
                self.check_for_pages()
                self.Layout()
                self.Thaw()
            else:
                self.hide_the_row_with_cols()
                self.Freeze()
                self._the_data.Hide()
                self.Layout()
                self.parent.Layout()
                self.Thaw()
                wx.MessageBox(f'Could not find "{search}" in any blocks \n'
                              f'Maybe yry a differnt mode or selection', "No Blocks Found", wx.OK | wx.ICON_INFORMATION)

    def continue_search(self, _):
        pause_count = int(self.set_max_found_input.GetValue())
        self.find_level_data.pause_count = pause_count
        search, mode, block_search_keys, block_e_search_keys = self.search_data()
        chunks_done, self.found_data = (
            self.find_level_data.search_raw(block_search_keys, block_e_search_keys,
                                            search, mode, chunks_done=self.chunks_done))
        if chunks_done:
            self.chunks_done = [*chunks_done, *self.chunks_done]
            self.Freeze()
            self.continue_button.Show()
        else:
            self.chunks_done = None
            self.Freeze()
            self.continue_button.Hide()

        self.check_for_pages()
        self.Layout()
        self.Thaw()

    def pageContol(self, page):
        if page:
            self.resetData(page)

        def OnClick(event):
            self.Freeze()
            self.resetData(int(event.GetString()))
            self.Thaw()

        return OnClick

    def hide_columns(self, columns_to_hide):
        def OnClick(event):
            hide = event.IsChecked()
            for col in columns_to_hide:
                if hide:
                    self._the_data.ShowCol(col)
                    self._the_data.Fit()
                    self._the_data.Layout()
                    self.Fit()
                    self.Layout()
                    self.parent.Layout()
                    self.Layout()
                else:
                    self._the_data.HideCol(col)
                    self._the_data.Fit()
                    self._the_data.Layout()
                    self.Fit()
                    self.Layout()
                    self.parent.Layout()
                    self.Layout()

        return OnClick

    def resetData(self, page):
        pop_out_table = self._set_is_pop_out.GetValue()

        try:
            if pop_out_table:
                self.topTable.Detach(self._the_data)
                self._the_data.Hide()

                self._the_data.Fit()
                self._the_data.Layout()
                self.Fit()
                self.Layout()
                self.parent.Layout()
                # self._the_data.Destroy()
            else:

                self.topTable.Detach(self._the_data)
                self._the_data.Hide()
                # self._the_data.Destroy()
                self._the_data = wx.grid.Grid(self, size=(540, 540), style=5)
        except:
            pass

        if pop_out_table:
            self.pop_out_frame = DataPopOutFrame(self, self.found_data, page, self.platform, self.canvas, self.world)
            self.pop_out_frame.Show()
            self.hide_the_row_with_cols()
        else:
            tableCount = len(self.found_data.get_page(page))
            self._the_data.CreateGrid(tableCount, 6)
            self._the_data.SetRowLabelSize(0)
            self._the_data.SetColLabelValue(0, "x")
            self._the_data.SetColLabelValue(1, "y")
            self._the_data.SetColLabelValue(2, "z")
            self._the_data.SetColLabelSize(20)
            self._the_data.SetColLabelValue(3, "Block")

            self._the_data.SetColLabelValue(4, "Extra_Block")
            self._the_data.SetColLabelValue(5, "Entity Data")

            for ind, (xyz, data) in enumerate(self.found_data.get_page(page).items()):
                # self.progress_bar(tableCount, ind, text=f'page:{ind}/{tableCount}')
                self._the_data.SetCellValue(ind, 0, str(xyz[0]))
                self._the_data.SetCellValue(ind, 1, str(xyz[1]))
                self._the_data.SetCellValue(ind, 2, str(xyz[2]))
                self._the_data.SetCellBackgroundColour(ind, 0, "#ef476f")
                self._the_data.SetCellBackgroundColour(ind, 1, "#06d6a0")
                self._the_data.SetCellBackgroundColour(ind, 2, "#118ab2")
                self._the_data.SetCellValue(ind, 3, data['block_data'].to_snbt(1))
                self._the_data.SetCellBackgroundColour(ind, 3, "#8ecae6")
                # self._the_data.SetCellBackgroundColour(ind, 4, "#95d5b2")
                self._the_data.SetCellValue(ind, 4, data['extra_block'].to_snbt(1))
                self._the_data.SetCellValue(ind, 5, data['entity_data'].to_snbt(1))

            self._the_data.Bind(wx.grid.EVT_GRID_CELL_RIGHT_CLICK, self.gridClick)
            self._the_data.Bind(wx.grid.EVT_GRID_CELL_LEFT_CLICK, self.gridClick)
            self.topTable.Add(self._the_data, 0, wx.TOP, 0)
            if self.platform == 'java':
                self._the_data.HideCol(4)

            self._the_data.Fit()
            self._the_data.Layout()
            self.Fit()
            self.Layout()
            self.parent.Layout()

    def gridClick(self, event):
        try:
            self.frame.Hide()
            self.frame.Close()
        except:
            pass

        ox, oy, oz = self.canvas.camera.location

        x, y, z = (self._the_data.GetCellValue(event.Row, 0),
                   self._the_data.GetCellValue(event.Row, 1),
                   self._the_data.GetCellValue(event.Row, 2))
        xx, yy, zz = float(x), float(y), float(z)

        def goto(_):
            self.canvas.camera.set_location((xx, yy + 25, zz))
            self.canvas.camera._notify_moved()

        def gobak(_):
            self.canvas.camera.set_location((ox, oy, oz))
            self.canvas.camera._notify_moved()

        self.frame = wx.Frame(self.parent, id=wx.ID_ANY, pos=wx.DefaultPosition, size=(425, 400),
                              style=(
                                      wx.MINIMIZE_BOX | wx.MAXIMIZE_BOX | wx.RESIZE_BORDER
                                      | wx.SYSTEM_MENU | wx.CAPTION | wx.CLOSE_BOX
                                      | wx.CLIP_CHILDREN | wx.FRAME_FLOAT_ON_PARENT | wx.STAY_ON_TOP),
                              name="Panel",
                              title="Cell (Row: " + str(event.GetRow()) + " Col: " + str(event.GetCol()) + ")")
        self.frame.SetFont(self.font)
        self.frame.SetForegroundColour((0, 255, 0))
        self.frame.SetBackgroundColour((0, 0, 0))
        self.frame.Centre(direction=wx.VERTICAL)
        row, col = event.GetRow(), event.GetCol()
        sizer_P = wx.BoxSizer(wx.VERTICAL)
        sizer_H = wx.BoxSizer(wx.HORIZONTAL)
        sizer_H2 = wx.BoxSizer(wx.HORIZONTAL)
        self.frame.SetSizer(sizer_P)
        save_close = wx.Button(self.frame, label="Save_Close")
        save_close.Bind(wx.EVT_BUTTON, self.ex_save_close(row, col, x, y, z))
        sizer_P.Add(sizer_H)
        sizer_P.Add(sizer_H2)

        self.textGrid = wx.TextCtrl(self.frame, style=wx.TE_MULTILINE | wx.TE_BESTWRAP, size=(400, 550))
        copy_to_find = wx.Button(self.frame, label="Copy To Find")
        copy_to_find.Bind(wx.EVT_BUTTON, self.copy_text_to_find)
        copy_to_replace = wx.Button(self.frame, label="Copy To Replace")
        goto_button = wx.Button(self.frame, label="Go to Location")
        goto_button.Bind(wx.EVT_BUTTON, goto)
        gobak_button = wx.Button(self.frame, label="Go Back to old Location")
        gobak_button.Bind(wx.EVT_BUTTON, gobak)
        copy_to_replace.Bind(wx.EVT_BUTTON, self.copy_text_to_replace)
        sizer_H.Add(save_close)
        sizer_H.Add(copy_to_find)
        sizer_H.Add(copy_to_replace)

        sizer_H2.Add(goto_button, 0, wx.TOP, 20)
        sizer_H2.Add(gobak_button, 0, wx.TOP, 20)
        sizer_P.Add(self.textGrid)

        if event.GetCol() < 3:
            self.textGrid.SetValue(f'Block location: {x, y, z}\nyour old location: {ox, oy, oz}')
            self.canvas.camera.set_location((xx, yy + 25, zz))
            self.canvas.camera._notify_moved()
            save_close.SetLabel("Close")
        else:
            self.textGrid.SetValue(self._the_data.GetCellValue(row, col))
        self.frame.Show(True)
        save_close.Show(True)

    def copy_text_to_find(self, _):
        self.textF.SetValue(self.textGrid.GetValue())

    def copy_text_to_replace(self, _):
        self.textR.SetValue(self.textGrid.GetValue())

    def ex_save_close(self, r, c, x, y, z):
        sub_keys = [x, y, z, 'block_data', 'extra_block', 'entity_data']

        def OnClick(event):
            if c < 3:
                pass
            else:
                val = self.textGrid.GetValue()
                self._the_data.SetCellValue(r, c, val)
                data = self.found_data.get_data()
                key = (int(x), int(y), int(z))
                block_data, extra_block, entity_data = data[key]['block_data'], data[key]['extra_block'], data[key][
                    'entity_data']
                new_dict = {'x': x, 'y': y, 'z': z, 'block_data': block_data, 'extra_block': extra_block,
                            'entity_data': entity_data}
                new_dict[sub_keys[c]] = self.test_nbt(val)
                new_dict.pop('x')
                new_dict.pop('y')
                new_dict.pop('z')

                if data[key][sub_keys[c]] != self.test_nbt(val):
                    data[key] = new_dict

            self.frame.Close()

        return OnClick

    def check_for_pages(self):

        self.hide_the_row_with_cols()
        pages = self.found_data.paginate(500)

        if pages > 1:

            self.p_label = wx.StaticText(self, label="Pages:")
            self.lpage = wx.Choice(self, choices=[])
            self.lpage.AppendItems([str(x) for x in range(1, pages + 1)])
            self.lpage.Bind(wx.EVT_CHOICE, self.pageContol(None))
            self.lpage.SetSelection(0)

            self.c_label = wx.StaticText(self, label="Show Columns:         ")
            self.hide_xyz = wx.CheckBox(self, label="X,Y,Z")
            self.hide_block = wx.CheckBox(self, label="Block")
            self.hide_extra = wx.CheckBox(self, label="Extra_block ")
            self.hide_entity = wx.CheckBox(self, label="Entity Data")
            self.hide_xyz.SetValue(True)
            self.hide_block.SetValue(True)
            self.hide_extra.SetValue(True)
            self.hide_entity.SetValue(True)
            if self.platform == 'java':
                self.hide_extra.Hide()
            self.hide_xyz.Bind(wx.EVT_CHECKBOX, self.hide_columns([0, 1, 2]))
            self.hide_block.Bind(wx.EVT_CHECKBOX, self.hide_columns([3]))
            self.hide_extra.Bind(wx.EVT_CHECKBOX, self.hide_columns([4]))
            self.hide_entity.Bind(wx.EVT_CHECKBOX, self.hide_columns([5]))
            self.above_grid.Add(self.c_label, 0, wx.LEFT, 0)
            self.above_grid.Add(self.hide_xyz, 0, wx.LEFT, 0)
            self.above_grid.Add(self.hide_block, 0, wx.LEFT, 0)
            self.above_grid.Add(self.hide_extra, 0, wx.LEFT, 0)
            self.above_grid.Add(self.hide_entity, 0, wx.LEFT, 0)

            self.above_grid.Add(self.p_label, 0, wx.LEFT, 0)
            self.above_grid.Add(self.lpage, 0, wx.LEFT, 0)
            self.above_grid.Fit(self)
            self._sizer.Fit(self)
            self._sizer.Layout()
            self.pageContol(1)

        else:

            self.c_label = wx.StaticText(self, label="Show Columns: ")
            self.hide_xyz = wx.CheckBox(self, label="X,Y,Z")
            self.hide_block = wx.CheckBox(self, label="Block")
            self.hide_extra = wx.CheckBox(self, label="Extra_block ")
            self.hide_entity = wx.CheckBox(self, label="Entity Data")
            self.hide_xyz.SetValue(True)
            self.hide_block.SetValue(True)
            self.hide_extra.SetValue(True)
            self.hide_entity.SetValue(True)
            if self.platform == 'java':
                self.hide_extra.Hide()
            self.hide_xyz.Bind(wx.EVT_CHECKBOX, self.hide_columns([0, 1, 2]))
            self.hide_block.Bind(wx.EVT_CHECKBOX, self.hide_columns([3]))
            self.hide_extra.Bind(wx.EVT_CHECKBOX, self.hide_columns([4]))
            self.hide_entity.Bind(wx.EVT_CHECKBOX, self.hide_columns([5]))
            self.above_grid.Add(self.c_label, 0, wx.LEFT, 0)
            self.above_grid.Add(self.hide_xyz, 0, wx.LEFT, 0)
            self.above_grid.Add(self.hide_block, 0, wx.LEFT, 0)
            self.above_grid.Add(self.hide_extra, 0, wx.LEFT, 0)
            self.above_grid.Add(self.hide_entity, 0, wx.LEFT, 0)
            self.above_grid.Fit(self)
            self._sizer.Fit(self)
            self._sizer.Layout()
            self.pageContol(1)

    def select_the_blocks(self, _):
        def set_boxes():
            selections = []
            block_items = (s for s in self.found_data.data.items())
            for (x, y, z), data in block_items:
                if self.textfilter.GetValue() in str(data):
                    selections.append(SelectionBox((x, y, z), (x + 1, y + 1, z + 1)))
            merge = SelectionGroup(selections).merge_boxes()
            self.canvas.selection.set_selection_group(merge)

        if self.found_data.get_key_len() > 5000:
            selected_blocks = self.found_data.get_key_len()

            message = (
                f'Rendering the selection can take a significant amount of time.\n'
                f'To avoid long delays, try to keep the number of selected blocks below 5,000.\n'
                f'This operation may cause the application to become unresponsive for a prolonged period.\n\n'
                f'You are trying to select: {selected_blocks} blocks.\n\n'
                f'Are you sure you want to continue?'
            )

            result = wx.MessageBox(
                message,
                "WARNING",
                wx.YES_NO | wx.ICON_WARNING
            )

            if result == wx.YES:
                set_boxes()
        else:
            set_boxes()

    def bind_events(self):
        super().bind_events()
        self._selection.bind_events()
        # self._selection.enable()

    def enable(self):
        self._selection = BlockSelectionBehaviour(self.canvas)
        self._selection.enable()

class SetPlayersData(wx.Frame):
    def __init__(self, parent, canvas, world, *args, **kw):
        super(SetPlayersData, self).__init__(parent, *args, **kw,
                                            style=(wx.MINIMIZE_BOX | wx.MAXIMIZE_BOX | wx.RESIZE_BORDER |
                                                   wx.SYSTEM_MENU | wx.CAPTION | wx.CLOSE_BOX | wx.CLIP_CHILDREN |
                                                   wx.FRAME_FLOAT_ON_PARENT),
                                            title="Set Player Data and Achievements")

        self.parent = parent

        self.canvas = canvas
        self.world = world
        self.platform = self.world.level_wrapper.platform
        self.font = wx.Font(13, wx.FONTFAMILY_ROMAN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        self.SetForegroundColour((0, 255, 0))
        self.SetBackgroundColour((0, 0, 0))
        self.SetFont(self.font)
        self.SetMinSize((320, 600))
        self.Freeze()
        self.data = None
        self._sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self._sizer)
        self.info = wx.StaticText(self, wx.LEFT)
        self.info.SetLabel("Select player:")
        if self.platform == "bedrock":
            self.infoRe = wx.StaticText(self, wx.LEFT)
            self.infoRe.SetLabel("Remove any Behavior Packs!")
            self.infoRai = wx.StaticText(self, wx.LEFT)
            self.infoRai.SetLabel(".. Personal GameMode?")
        self.XL = wx.StaticText(self, wx.LEFT)
        self.XL.SetLabel("X:")
        self.YL = wx.StaticText(self, wx.LEFT)
        self.YL.SetLabel("Y:")
        self.ZL = wx.StaticText(self, wx.LEFT)
        self.ZL.SetLabel("Z:")
        self.facingL = wx.StaticText(self, wx.LEFT)
        self.facingL.SetLabel("Facing:")
        self.lookingL = wx.StaticText(self, wx.LEFT)
        self.lookingL.SetLabel("Looking:")
        self.X = wx.TextCtrl(
            self, style=wx.TE_LEFT | wx.TE_BESTWRAP, size=(150, 20),
        )
        self.Y = wx.TextCtrl(
            self, style=wx.TE_LEFT | wx.TE_BESTWRAP, size=(150, 20),
        )
        self.Z = wx.TextCtrl(
            self, style=wx.TE_LEFT | wx.TE_BESTWRAP, size=(150, 20),
        )
        self.facing = wx.TextCtrl(
            self, style=wx.TE_LEFT | wx.TE_BESTWRAP, size=(150, 20),
        )
        self.looking = wx.TextCtrl(
            self, style=wx.TE_LEFT | wx.TE_BESTWRAP, size=(150, 20),
        )
        self.dimDict = {
            "Overworld": 0,
            "Nether": 1,
            "End": 2
        }
        # self.lst_mode = CustomRadioBox(self, 'Select Search Mode', [*self.listSearchType], (0, 255, 0))
        self.dim = CustomRadioBox(self, 'Select Dimension', list(self.dimDict.keys()), (0, 255, 0), sty=1)
        self.apply = wx.Button(self, size=(60, 30), label="Apply")
        if self.platform == "bedrock":
            self.apply.Bind(wx.EVT_BUTTON, self.savePosData)
        else:
            self.apply.Bind(wx.EVT_BUTTON, self.savePosDataJava)
        self.getSet = wx.Button(self, size=(155, 25), label="Get Current Position")
        self.getSet.Bind(wx.EVT_BUTTON, self.getsetCurrentPos)
        self.tpUser = wx.CheckBox(self, size=(155, 25), label="Enable TP for select")
        self.fcords = wx.CheckBox(self, size=(155, 25), label="lock Cord Values")

        if self.platform == "bedrock":
            self.achieve = wx.Button(self, size=(165, 25), label="Re-enable achievements")
            self.is_hardcore = self.world.level_wrapper.root_tag.get('IsHardcore', None)


            if self.is_hardcore == 1:
                self.set_hardcore = wx.Button(self, size=(165, 25), label="Disable Hardcore")
                self.set_hardcore.Bind(wx.EVT_BUTTON, self.set_hardcore_mode)
                self._sizer.Add(self.set_hardcore, 0, wx.LEFT, 0)
            if self.is_hardcore == 0:
                self.set_hardcore = wx.Button(self, size=(165, 25), label="Enable Hardcore")
                self.set_hardcore.Bind(wx.EVT_BUTTON, self.set_hardcore_mode)
                self._sizer.Add(self.set_hardcore, 0, wx.LEFT, 0)
            # self.make_hardcore = wx.Button(self, size=(165, 25), label="Make Hardcore")
            self.achieve.Bind(wx.EVT_BUTTON, self.re_enable_achievements)

        self.listRadio = {
            "Survival": 0,
            "Creative": 1
        }
        self.listRadiojava = {
            "Survival": 0,
            "Creative": 1,
            "Adventure": 2,
            "Spectator": 3,
            "Recover Hardcore World": 4
        }
        if self.platform == "bedrock":
            self.gm_mode = CustomRadioBox(self, 'Both Do NOT disable achievements',
                                          list(self.listRadio.keys()), (0, 255, 0), sty=wx.RA_SPECIFY_ROWS | 1)
        if self.platform == "java":
            self.gm_mode = CustomRadioBox(self, 'Set Gamemode', list(self.listRadiojava.keys()),
                                          (0, 255, 0))

        player = ['']
        if self.platform == "bedrock":
            for x in self.world.players.all_player_ids():
                if "server_" in x or "~" in x:
                    if "server_" in x:
                        player.append("player_" + x)
                    else:
                        player.append(x)
        else:
            for x in self.world.players.all_player_ids():
                player.append(x)

        self.playerlist = wx.ListBox(self, size=(160, 95), choices=player)
        self.playerlist.SetSelection(0)
        self.playerlistrun(None)
        self.playerlist.Bind(wx.EVT_LISTBOX, self.playerlistrun)

        if self.platform == "bedrock":
            self._sizer.Add(self.infoRe, 0, wx.LEFT, 10)
            self._sizer.Add(self.achieve, 0, wx.LEFT, 20)
        self._sizer.Add(self.info, 0, wx.LEFT, 10)
        self._sizer.Add(self.playerlist, 0, wx.LEFT, 10)

        self._sizer.Add(self.tpUser, 0, wx.LEFT, 20)

        self._sizer.Add(self.fcords, 0, wx.LEFT, 20)
        self._sizer.Add(self.getSet, 0, wx.LEFT, 40)
        self.Grid = wx.GridSizer(5, 2, 0, 0)
        self.Grid.Add(self.XL, 0, wx.LEFT, 5)
        self.Grid.Add(self.X, 0, wx.LEFT, -60)
        self.Grid.Add(self.YL, 0, wx.LEFT, 5)
        self.Grid.Add(self.Y, 0, wx.LEFT, -60)
        self.Grid.Add(self.ZL, 0, wx.LEFT, 5)
        self.Grid.Add(self.Z, 0, wx.LEFT, -60)

        self.Grid.Add(self.facingL, 0, wx.LEFT, 10)
        self.Grid.Add(self.facing, 0, wx.LEFT, -40)
        self.Grid.Add(self.lookingL, 0, wx.LEFT, 10)
        self.Grid.Add(self.looking, 0, wx.LEFT, -40)

        self._sizer.Add(self.Grid)
        self.Grid.Fit(self)

        self._sizer.Add(self.dim, 0, wx.LEFT, 0)

        if self.platform == "bedrock":
            self._sizer.Add(self.infoRai, 0, wx.LEFT, 0)


        self._sizer.Add(self.gm_mode, 0, wx.LEFT, 0)

        self._sizer.Add(self.apply, 0, wx.LEFT, 160)
        self._sizer.Fit(self)

        self.Layout()
        self.Thaw()

    @property
    def level_db(self):
        level_wrapper = self.world.level_wrapper
        if hasattr(level_wrapper, "level_db"):
            return level_wrapper.level_db
        else:
            return level_wrapper._level_manager._db

    @property
    def wx_add_options(self) -> Tuple[int, ...]:
        return (0,)

    def getPlayersData(self, pl):
        data = "None"
        if self.platform == "bedrock":

            try:
                enS = pl.encode("utf-8")

                player = self.level_db.get(enS)

                data = load(player, little_endian=True, compressed=False, string_decoder=utf8_escape_decoder)

            except:
                data = "None"
        else:

            try:
                path = self.world.level_path + "\\level.dat"
                if pl != "~local_player":
                    path = self.world.level_path + "\\PlayersData\\" + pl + ".dat"
                with open(path, "rb") as f:
                    r = f.read()
                if pl != "~local_player":
                    data = load(r, compressed=True, little_endian=False)
                else:
                    self.data = load(r, compressed=True, little_endian=False)
                    data = self.data["Data"]["Player"]

            except:
                data = "None"

        return data

    def playerlistrun(self, _):
        print(self.playerlist.GetString(self.playerlist.GetSelection()))
        if self.platform == "bedrock":

            player = self.playerlist.GetString(self.playerlist.GetSelection())
            pdata = self.getPlayersData(player)
            if pdata != "None":
                X, Y, Z = pdata.get("Pos")
                facing, looking = pdata.get("Rotation")

                if self.tpUser.GetValue():
                    self.canvas.camera.location = [float(str(X).replace('f', '')), float(str(Y).replace('f', '')),
                                                   float(str(Z).replace('f', ''))]
                    self.canvas.camera.rotation = [float(str(facing).replace('f', '')),
                                                   float(str(looking).replace('f', ''))]
                if self.fcords.GetValue():
                    return
                self.X.SetValue(str(X))
                self.Y.SetValue(str(Y))
                self.Z.SetValue(str(Z))
                self.facing.SetValue(str(facing))
                self.looking.SetValue(str(looking))
                self.dim.SetSelection(pdata.get("DimensionId"))
        else:
            player = self.playerlist.GetString(self.playerlist.GetSelection())
            pdata = self.getPlayersData(player)
            if pdata != "None":
                X, Y, Z = pdata.get("Pos")
                facing, looking = pdata.get("Rotation")

                if self.tpUser.GetValue() == True:
                    self.canvas.camera.location = [float(str(X).replace('d', '')), float(str(Y).replace('d', '')),
                                                   float(str(Z).replace('d', ''))]
                    self.canvas.camera.rotation = [float(str(facing).replace('f', '')),
                                                   float(str(looking).replace('f', ''))]
                if self.fcords.GetValue() == True:
                    return
                self.X.SetValue(str(X))
                self.Y.SetValue(str(Y))
                self.Z.SetValue(str(Z))
                self.facing.SetValue(str(facing))
                self.looking.SetValue(str(looking))
                dim = {
                    'minecraft:overworld': 0,
                    'minecraft:the_nether': 1,
                    'minecraft:the_end': 2
                }
                self.canvas.dimension = str(pdata.get("Dimension"))
                self.dim.SetSelection(dim[str(pdata.get("Dimension"))])

    def getsetCurrentPos(self, _):

        X, Y, Z = self.canvas.camera.location
        facing, looking = self.canvas.camera.rotation
        self.X.SetValue(str(X))
        self.Y.SetValue(str(Y))
        self.Z.SetValue(str(Z))
        self.facing.SetValue(str(facing))
        self.looking.SetValue(str(looking))
        dim = {
            'minecraft:overworld': 0,
            'minecraft:the_nether': 1,
            'minecraft:the_end': 2
        }
        self.dim.SetSelection(dim[self.canvas.dimension])

    def savePosData(self, _):
        player = self.playerlist.GetString(self.playerlist.GetSelection())
        pdata = self.getPlayersData(player)
        mode = self.gm_mode.GetString(self.gm_mode.GetSelection())
        print(mode)
        dim = {
            0: "Over World",
            1: "Nether",
            2: "The End"
        }
        facing, looking = pdata.get("Rotation")
        if self.platform == "bedrock":
            pdata["PlayerGameMode"] = TAG_Int(int(self.listRadio.get(mode)))

        pdata["DimensionId"] = TAG_Int(int(self.dim.GetSelection()))
        pdata["Rotation"] = TAG_List()
        pdata['Rotation'].append(TAG_Float(float(self.facing.GetValue().replace("f", ""))))
        pdata['Rotation'].append(TAG_Float(float(self.looking.GetValue().replace("f", ""))))
        pdata['Pos'] = TAG_List()
        pdata['Pos'].append(TAG_Float(float(self.X.GetValue().replace("f", ""))))
        pdata['Pos'].append(TAG_Float(float(self.Y.GetValue().replace("f", ""))))
        pdata['Pos'].append(TAG_Float(float(self.Z.GetValue().replace("f", ""))))
        save = pdata.save_to(compressed=False, little_endian=True)
        self.level_db.put(player.encode("utf-8"), save)
        wx.MessageBox(player + "\nPersonal Mode: " + mode + "\nLocation is set to\n" + dim.get(
            int(self.dim.GetSelection())) + " \nX: "
                      + self.X.GetValue().replace("f", "") + "\nY: " + self.Y.GetValue().replace("f",
                                                                                                 "") + "\nZ: " + self.Z.GetValue().replace(
            "f", "") +
                      "\nFacing: " + self.facing.GetValue().replace("f", "") +
                      "\nLooking: " + self.looking.GetValue().replace("f", "") +
                      "\nNOTE: You MUST CLOSE This world Before Opening in MineCraft",
                      "INFO", wx.OK | wx.ICON_INFORMATION)

    def savePosDataJava(self, _):
        player = self.playerlist.GetString(self.playerlist.GetSelection())
        pdata = self.getPlayersData(player)

        if len(player) < 1:
            wx.MessageBox(player + "Need to make a player selection",
                          "INFO", wx.OK | wx.ICON_INFORMATION)
            return

        dim = {
            0: 'minecraft:overworld',
            1: 'minecraft:the_nether',
            2: 'minecraft:the_end'
        }
        facing, looking = pdata.get("Rotation")

        pdata["Dimension"] = TAG_String(dim[int(self.dim.GetSelection())])
        pdata["Rotation"] = TAG_List()
        pdata['Rotation'].append(TAG_Float(float(self.facing.GetValue().replace("f", ""))))
        pdata['Rotation'].append(TAG_Float(float(self.looking.GetValue().replace("f", ""))))
        pdata['Pos'] = TAG_List()
        pdata['Pos'].append(TAG_Double(float(self.X.GetValue().replace("d", ""))))
        pdata['Pos'].append(TAG_Double(float(self.Y.GetValue().replace("d", ""))))
        pdata['Pos'].append(TAG_Double(float(self.Z.GetValue().replace("d", ""))))
        print(self.gm_mode.GetSelection())
        if self.gm_mode.GetSelection() == 0:
            pdata['playerGameType'] = TAG_Int(0)
        if self.gm_mode.GetSelection() == 1:
            pdata['playerGameType'] = TAG_Int(1)
        if self.gm_mode.GetSelection() == 2:
            pdata['playerGameType'] = TAG_Int(2)
        if self.gm_mode.GetSelection() == 3:
            pdata['playerGameType'] = TAG_Int(3)
        if self.gm_mode.GetSelection() == 4:
            pdata.pop('previousPlayerGameType')
            pdata.pop('abilities')
            pdata.pop('playerGameType')
        if player != "~local_player":

            save = pdata.save_to(compressed=True, little_endian=False)
            with open(self.world.level_path + "\\PlayersData\\" + player + ".dat", "wb") as f:
                f.write(save)
        else:

            self.data["Data"]["Player"] = pdata

            save = self.data.save_to(compressed=True, little_endian=False)

            with open(self.world.level_path + "\\level.dat", "wb") as f:
                f.write(save)

        wx.MessageBox(player + "\nLocation is set to\n" + dim.get(
            int(self.dim.GetSelection())) + " \nX: "
                      + self.X.GetValue().replace("f", "") + "\nY: " + self.Y.GetValue().replace("f",
                                                                                                 "") + "\nZ: " + self.Z.GetValue().replace(
            "f", "") +
                      "\nFacing: " + self.facing.GetValue().replace("f", "") +
                      "\nLooking: " + self.looking.GetValue().replace("f", "") +
                      "\nNOTE: You MUST CLOSE This world Before Opening in MineCraft",
                      "INFO", wx.OK | wx.ICON_INFORMATION)

    # def saveData(self, head, data):
    #     with open(self.world.level_path + "\\" + "level.dat", "wb") as f:
    #         f.write(head + data)
    #         wx.MessageBox("Achievements are Re-enable",
    #                       "INFO", wx.OK | wx.ICON_INFORMATION)
    def set_hardcore_mode(self, _):
        self.is_hardcore = self.world.level_wrapper.root_tag.get('IsHardcore', None)
        if self.is_hardcore == 1:
            self.set_hardcore.SetLabel("Enable Hardcore")
            self.world.level_wrapper.root_tag['IsHardcore'] = ByteTag(0)
        if self.is_hardcore == 0:
            self.set_hardcore.SetLabel("Disable Hardcore")
            self.world.level_wrapper.root_tag['IsHardcore'] = ByteTag(1)
        self.world.level_wrapper.root_tag.save()


    def re_enable_achievements(self, _):

        self.world.level_wrapper.root_tag['hasBeenLoadedInCreative'] = ByteTag(0)
        self.world.level_wrapper.root_tag['commandsEnabled'] = ByteTag(0)
        self.world.level_wrapper.root_tag['GameType'] = IntTag(0)

        self.world.level_wrapper.root_tag.save()
        wx.MessageBox("Achievements are Re-enable",
                              "INFO", wx.OK | wx.ICON_INFORMATION)

class HardCodedSpawns(wx.Frame):
    def __init__(self, parent, canvas, world, *args, **kw):
        super(HardCodedSpawns, self).__init__(parent, *args, **kw,
                                              style=(wx.MINIMIZE_BOX | wx.MAXIMIZE_BOX | wx.RESIZE_BORDER |
                                                     wx.SYSTEM_MENU | wx.CAPTION | wx.CLOSE_BOX | wx.CLIP_CHILDREN |
                                                     wx.FRAME_FLOAT_ON_PARENT),
                                              title="Hard Coded Spawn Editor")

        self.parent = parent

        self.canvas = canvas
        self.world = world
        self.font = wx.Font(13, wx.FONTFAMILY_ROMAN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        self.SetFont(self.font)
        self.SetMinSize((320, 600))
        self.SetForegroundColour((0, 255, 0))
        self.SetBackgroundColour((0, 0, 0))
        self.type_dic = {1: "Fortress", 3: "Monument", 5: "Villager Outpost", 2: "Witch Hut"}
        self.abc = []
        self.cord_dic = collections.defaultdict(list)
        self.Freeze()
        self.sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.side = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self.sizer)
        if self.world.level_wrapper.platform == "java":
            wx.MessageBox("Java Not Supported", "Not Supported", wx.OK | wx.ICON_INFORMATION)
        else:
            self._up = wx.Button(self, label="Up", size=(36, 35))
            self._up.Bind(wx.EVT_BUTTON, self._boxUp('m'))
            self._down = wx.Button(self, label="Down", size=(36, 35))
            self._down.Bind(wx.EVT_BUTTON, self._boxDown('m'))
            self._east = wx.Button(self, label="East", size=(36, 35))
            self._east.Bind(wx.EVT_BUTTON, self._boxEast('m'))
            self._west = wx.Button(self, label="West", size=(36, 35))
            self._west.Bind(wx.EVT_BUTTON, self._boxWest('m'))
            self._north = wx.Button(self, label="North", size=(36, 35))
            self._north.Bind(wx.EVT_BUTTON, self._boxNorth('m'))
            self._south = wx.Button(self, label="South", size=(36, 35))
            self._south.Bind(wx.EVT_BUTTON, self._boxSouth('m'))

            self.lbct = wx.StaticText(self, label="Step:")

            self.control = wx.SpinCtrl(self, value="1", min=1, max=1000)

            self.get_button = wx.Button(self, label="Get All")
            self.get_button.Bind(wx.EVT_BUTTON, self.get_all_)

            self.search_button = wx.Button(self, label="Within Selection")
            self.search_button.Bind(wx.EVT_BUTTON, self.search_button_)

            self.gsel = wx.Button(self, label="Set Boxs")
            self.gsel.Bind(wx.EVT_BUTTON, self._gsel)
            self.copy_boxs = wx.Button(self, label="Copy Boxs")
            self.copy_boxs.Bind(wx.EVT_BUTTON, self._copy_boxs)
            self.paste_boxs = wx.Button(self, label="Paste Boxs")
            self.paste_boxs.Bind(wx.EVT_BUTTON, self._paste_boxs)
            self.locationlist = wx.ListBox(self, size=(260, 480))
            self.locationlist.Bind(wx.EVT_LISTBOX, self.go_to_and_sel)
            self.locationlist.SetBackgroundColour((0, 0, 0))
            self.locationlist.SetForegroundColour((0, 255, 0))
            self.lb_info_move = wx.StaticText(self, label="Move All Box/s\n Step == Faster")
            self.lb_info_delete = wx.StaticText(self, label="Delete Spawns\n From Selected")
            self.lb_info = wx.StaticText(self, label="Set Bounding Boxes:\n")

            self.drop = wx.Choice(self, choices=[x for x in self.type_dic.values()], size=(150, 30))
            if "overworld" in self.canvas.dimension:
                self.drop.Clear()
                self.drop.Append([x for x in self.type_dic.values()][1:4])

            elif 'nether' in self.canvas.dimension:
                self.drop.Clear()
                self.drop.Append([x for x in self.type_dic.values()][0])
            else:
                self.drop.Clear()
                self.drop.Append("None")

            self.drop.SetSelection(0)

            self.delete_spawns = wx.Button(self, label="Delete Spawns")
            self.delete_spawns.Bind(wx.EVT_BUTTON, self._delete_spawns)

            self.sizer.Add(self.locationlist)
            self.side.Add(self.get_button, 0, wx.TOP, 5)
            self.side.Add(self.search_button, 0, wx.TOP, 5)

            self.side.Add(self.copy_boxs, 0, wx.TOP, 5)
            self.side.Add(self.paste_boxs, 0, wx.TOP, 5)

            self.grid = wx.GridSizer(4, 2, 0, -6)
            self.grid.Add(self.lbct)
            self.grid.Add(self.control, 0, wx.LEFT, -10)
            self.grid.Add(self._up)
            self.grid.Add(self._down)
            self.grid.Add(self._north)
            self.grid.Add(self._south)
            self.grid.Add(self._west)
            self.grid.Add(self._east)

            self._is_enabled = True
            self._moving = True
            self.Bind(wx.EVT_MOUSE_EVENTS, self._on_canvas_change)
            self.dim_c = ""

            self.side.Add(self.lb_info_move, 0, wx.TOP, 5)
            self.side.Add(self.grid, 0, wx.TOP, 5)
            self.side.Add(self.lb_info, 0, wx.TOP, 5)
            self.side.Add(self.drop, 0, wx.TOP, 5)
            self.side.Add(self.gsel, 0, wx.TOP, 5)
            self.side.Add(self.lb_info_delete, 0, wx.TOP, 5)
            self.side.Add(self.delete_spawns, 0, wx.TOP, 5)
            self.sizer.Add(self.side)
            self.Layout()
            self.Thaw()

    def _on_input_press(self, evt: InputPressEvent):

        if evt.action_id == ACT_BOX_CLICK:
            if self._is_enabled == True:
                self._moving = not self._moving
                self.canvas.Unbind(EVT_POINT_CHANGE)
                self._selection = BlockSelectionBehaviour(self.canvas)
                self._selection.enable()
                self._selection.bind_events()
                self._is_enabled = False
                self._moving = False
                return
            if self._is_enabled == False:
                self._is_enabled = True
                self._on_pointer_change
                return
            if self._moving:
                self.canvas.renderer.fake_levels.active_transform = ()
        evt.Skip()

    def bind_events(self):
        super().bind_events()
        self._selection.bind_events()
        self._selection.enable()

    def enable(self):

        self._selection = BlockSelectionBehaviour(self.canvas)
        self._selection.enable()

    def _on_canvas_change(self, evt):
        dim = self.canvas.dimension

        if dim != self.dim_c:
            if "overworld" in self.canvas.dimension:
                self.drop.Clear()
                self.drop.Append([x for x in self.type_dic.values()][1:4])
                self.drop.SetSelection(0)
                self.dim_c = self.canvas.dimension
            elif 'nether' in self.canvas.dimension:
                self.drop.Clear()
                self.drop.Append([x for x in self.type_dic.values()][0])
                self.drop.SetSelection(0)
                self.dim_c = self.canvas.dimension
            else:
                self.drop.Clear()
                self.drop.Append("None")
                self.drop.SetSelection(0)
                self.dim_c = self.canvas.dimension
        evt.Skip()

    def _on_pointer_change(self, evt: PointChangeEvent):
        if self._is_enabled:
            self.canvas.renderer.fake_levels.active_transform = (
                evt.point
            )
            x, y, z = evt.point
            groups = []
            for (a, b, c, aa, bb, cc) in self.abc:
                groups.append(SelectionBox((x + a, y + b, z + c), (x + aa, y + bb, z + cc)))
            sg = SelectionGroup(groups)
            self.canvas.selection.set_selection_group(sg)
        evt.Skip()

    def search_button_(self, _):
        self.cord_dic.clear()
        self.locationlist.Clear()
        sel_chunks = self.canvas.selection.selection_group.chunk_locations()

        def get_dim_value_bytes():
            if 'minecraft:the_end' in self.canvas.dimension:
                dim = int(2).to_bytes(4, 'little', signed=True)
            elif 'minecraft:the_nether' in self.canvas.dimension:
                dim = int(1).to_bytes(4, 'little', signed=True)
            elif 'minecraft:overworld' in self.canvas.dimension:
                dim = b''  # int(0).to_bytes(4, 'little', signed=True)
            return dim

        found = []
        for x, z in sel_chunks:
            xx, zz = int(x).to_bytes(4, 'little', signed=True), int(z).to_bytes(4, 'little', signed=True)
            dim = get_dim_value_bytes()
            k = xx + zz + dim + b'\x39'

            try:
                v = self.level_db.get(k)
                num_of = int.from_bytes(v[:4], 'little', signed=True)
                if len(k) > 9:  # Only Nether and Overworld Contain Hard Spawns
                    for gc, c in enumerate(range(4, 1 + (num_of * 6) * 4, 4)):
                        g = int(gc / 6)
                        self.cord_dic[f"{self.type_dic[v[-1]]} Nether:{x, z}"].append(
                            int.from_bytes(v[c + g:g + c + 4], 'little', signed=True))
                else:
                    for gc, c in enumerate(range(4, 1 + (num_of * 6) * 4, 4)):
                        g = int(gc / 6)
                        self.cord_dic[f"{self.type_dic[v[-1]]} Overworld:{x, z}"].append(
                            int.from_bytes(v[c + g:g + c + 4], 'little', signed=True))
                found.append((x, z))
            except:
                pass

        try:
            self.locationlist.InsertItems([x for x in self.cord_dic.keys()], 0)
            group = []
            for k in self.cord_dic.keys():
                cords = self.cord_dic[k]
                cx, cy, cz = self.cord_dic[k][:3]
                cx1, cy1, cz1 = self.cord_dic[k][3:6]
                lenth = int(len(cords) / 6)
                for d in range(0, (lenth * 6), 6):
                    x, y, z, xx, yy, zz = cords[d:d + 6]
                    group.append(SelectionBox((int(x), int(y), int(z)), (int(xx + 1), int(yy), int(zz + 1))))
            sel = SelectionGroup(group)
            self.canvas.selection.set_selection_group(sel)
            wx.MessageBox(f"Found and selected Spawns From Chunks: {found}", "Completed", wx.OK | wx.ICON_INFORMATION)
        except:
            wx.MessageBox(f"No Spawns Found", "Completed", wx.OK | wx.ICON_INFORMATION)

    def _delete_spawns(self, _):
        sel_chunks = self.canvas.selection.selection_group.chunk_locations()

        def get_dim_value_bytes():
            if 'minecraft:the_end' in self.canvas.dimension:
                dim = int(2).to_bytes(4, 'little', signed=True)
            elif 'minecraft:the_nether' in self.canvas.dimension:
                dim = int(1).to_bytes(4, 'little', signed=True)
            elif 'minecraft:overworld' in self.canvas.dimension:
                dim = b''  # int(0).to_bytes(4, 'little', signed=True)
            return dim

        for x, z in sel_chunks:
            xx, zz = int(x).to_bytes(4, 'little', signed=True), int(z).to_bytes(4, 'little', signed=True)
            dim = get_dim_value_bytes()
            chunk_key = xx + zz + dim + b'\x39'
            removed = []
            try:
                self.level_db.delete(chunk_key)
                removed.append((x, z))
            except:
                pass

        wx.MessageBox(f"Removed Spawns From Chunks: {removed}", "Completed", wx.OK | wx.ICON_INFORMATION)

    def _copy_boxs(self, _):
        sizes = []
        points = []
        self.abc.clear()
        for box in self.canvas.selection.selection_group.selection_boxes:
            px, py, pz = box.min
            px2, py2, pz2 = box.max
            sx, sy, sz = px2 - px, py2 - py, pz2 - pz
            sizes.append((box.size_x, box.size_y, box.size_z))
            points.append((px, py, pz))
        box_cords = []
        fpx, fpy, fpz = 0, 0, 0
        for i, ((px, py, pz), (sx, sy, sz)) in enumerate(zip(points, sizes)):

            if i > 0:
                ax, ay, az = box_cords[i - 1][:3]
                fpx, fpy, fpz = ((px) - (fpx)) + (ax), ((py) - (fpy)) + (ay), ((pz) - (fpz)) + (az)
                box_cords.append(((fpx), (fpy), (fpz), sx, sy, sz))
            else:
                box_cords.append(((fpx), (fpy), (fpz), sx, sy, sz))
            fpx, fpy, fpz = px, py, pz

        for (a, b, c, aa, bb, cc) in box_cords:
            tx, ty, tz = 0, 0, 0
            tx1, ty1, tz1 = 0, 0, 0
            self.abc.append((tx + a, ty + b, tz + c, (tx1 + aa) + a, (ty1 + bb) + b, (tz1 + cc) + c))

    def _paste_boxs(self, evt):
        self.canvas.Bind(EVT_POINT_CHANGE, self._on_pointer_change)  # , id=300, id2=400)
        self.canvas.Bind(EVT_INPUT_PRESS, self._on_input_press)  # , id=301, id2=401)
        self._is_enabled = True
        self._moving = True
        self._on_pointer_change

    def _gsel(self, _):
        added = []
        set_it = collections.defaultdict(list)
        for box in self.canvas.selection.selection_group.selection_boxes:
            for chunk, box in box.chunk_boxes():
                x, y, z, xx, yy, zz = box.min_x.to_bytes(4, 'little', signed=True), \
                    box.min_y.to_bytes(4, 'little', signed=True), \
                    box.min_z.to_bytes(4, 'little', signed=True), \
                    (box.max_x - 1).to_bytes(4, 'little', signed=True), \
                    box.max_y.to_bytes(4, 'little', signed=True), \
                    (box.max_z - 1).to_bytes(4, 'little', signed=True)  # convert to the raw format.
                xc, zc = chunk  # [xcc for xcc in box.chunk_locations()][0]
                xcb, zcb = xc.to_bytes(4, 'little', signed=True), zc.to_bytes(4, 'little', signed=True)
                added.append((self.drop.GetStringSelection(), xc, zc))
                if xcb + zcb + self.get_dim_value_bytes() in set_it.keys():
                    set_it[xcb + zcb + self.get_dim_value_bytes()].append((b'\x01' + x + y + z + xx + yy + zz))
                else:
                    set_it[xcb + zcb + self.get_dim_value_bytes()].append((x + y + z + xx + yy + zz))

        t = list(self.type_dic.keys())[list(self.type_dic.values()).index(self.drop.GetStringSelection())]
        for x in set_it.values():  # set the selected type
            x.append(t.to_bytes(1, 'little', signed=True))

        for kb, vb in set_it.items():  # join and append
            lenth = (len(vb) - 1).to_bytes(4, 'little', signed=True)
            data = lenth + b''.join(vb)
            key = kb + b'\x39'
            self.level_db.put(key, data)

        f_added = set(added)
        wx.MessageBox(f"Added Spawn Type to Chunks: {f_added}", "Completed", wx.OK | wx.ICON_INFORMATION)

    def get_dim_value_bytes(self):
        if 'minecraft:the_end' in self.canvas.dimension:
            dim = int(2).to_bytes(4, 'little', signed=True)
        elif 'minecraft:the_nether' in self.canvas.dimension:
            dim = int(1).to_bytes(4, 'little', signed=True)
        elif 'minecraft:overworld' in self.canvas.dimension:
            dim = b''
        return dim

    def go_to_and_sel(self, _):
        group = []
        cords = self.cord_dic[self.locationlist.GetStringSelection()]
        cx, cy, cz = self.cord_dic[self.locationlist.GetStringSelection()][:3]
        cx1, cy1, cz1 = self.cord_dic[self.locationlist.GetStringSelection()][3:6]
        self.canvas.camera.set_location(
            (float(((cx + cx1) / 2) + 10), float(((cy + cy1) / 2) + 40), float(((cz + cz1) / 2)) - 10))
        self.canvas.camera.set_rotation((float(0), float(90)))
        lenth = int(len(cords) / 6)
        for d in range(0, (lenth * 6), 6):
            x, y, z, xx, yy, zz = cords[d:d + 6]
            group.append(SelectionBox((int(x), int(y), int(z)), (int(xx + 1), int(yy), int(zz + 1))))
        sel = SelectionGroup(group)
        if "Overworld" in self.locationlist.GetStringSelection():
            self.canvas.dimension = 'minecraft:overworld'
        else:
            self.canvas.dimension = 'minecraft:the_nether'
        self.canvas.selection.set_selection_group(sel)
        self.canvas.camera._notify_moved()

    def get_all_(self, _):
        self.cord_dic.clear()
        self.locationlist.Clear()
        for k, v in self.level_db.iterate():
            if k[-1] == 57 and (len(k) == 9 or len(k) == 13):
                num_of = int.from_bytes(v[:4], 'little', signed=True)
                xc, zc = int.from_bytes(k[:4], 'little', signed=True), int.from_bytes(k[4:8], 'little', signed=True)
                if len(k) > 9:  # Only Nether and Overworld Contain Hard Spawns
                    for gc, c in enumerate(range(4, 1 + (num_of * 6) * 4, 4)):
                        g = int(gc / 6)
                        self.cord_dic[f"{self.type_dic[v[-1]]} Nether:{xc, zc}"].append(
                            int.from_bytes(v[c + g:g + c + 4], 'little', signed=True))
                        # if gc%6 == 5 and g > 0: # located the ... I guess spacer bytes
                        #     print(xc,zc, int.from_bytes(v[c+g+4:g+4+c+1], 'little', signed=True),''.join('{:02x}'.format(x) for x in v) )
                else:
                    for gc, c in enumerate(range(4, 1 + (num_of * 6) * 4, 4)):
                        g = int(gc / 6)
                        self.cord_dic[f"{self.type_dic[v[-1]]} Overworld:{xc, zc}"].append(
                            int.from_bytes(v[c + g:g + c + 4], 'little', signed=True))
        self.locationlist.InsertItems([x for x in self.cord_dic.keys()], 0)

    @property
    def level_db(self):
        level_wrapper = self.world.level_wrapper
        if hasattr(level_wrapper, "level_db"):
            return level_wrapper.level_db
        else:
            return level_wrapper._level_manager._db

    def _boxUp(self, v):
        def OnClick(event):
            sgs = []
            print(self.control.GetValue())
            for box in self.canvas.selection.selection_group.selection_boxes:
                xx, yy, zz = box.max_x, box.max_y, box.max_z
                xm, ym, zm = box.min_x, box.min_y, box.min_z
                sgs.append(SelectionBox((xm, ym + self.control.GetValue(), zm), (xx, yy + self.control.GetValue(), zz)))
            self.canvas.selection.set_selection_group(SelectionGroup(sgs))

        return OnClick

    def _boxDown(self, v):
        def OnClick(event):
            sgs = []
            for box in self.canvas.selection.selection_group.selection_boxes:
                xx, yy, zz = box.max_x, box.max_y, box.max_z
                xm, ym, zm = box.min_x, box.min_y, box.min_z
                sgs.append(SelectionBox((xm, ym - self.control.GetValue(), zm), (xx, yy - self.control.GetValue(), zz)))
            self.canvas.selection.set_selection_group(SelectionGroup(sgs))

        return OnClick

    def _boxNorth(self, v):

        def OnClick(event):
            sgs = []
            for box in self.canvas.selection.selection_group.selection_boxes:
                xx, yy, zz = box.max_x, box.max_y, box.max_z
                xm, ym, zm = box.min_x, box.min_y, box.min_z
                sgs.append(SelectionBox((xm, ym, zm - self.control.GetValue()), (xx, yy, zz - self.control.GetValue())))
            self.canvas.selection.set_selection_group(SelectionGroup(sgs))

        return OnClick

    def _boxSouth(self, v):
        def OnClick(event):
            sgs = []
            for box in self.canvas.selection.selection_group.selection_boxes:
                xx, yy, zz = box.max_x, box.max_y, box.max_z
                xm, ym, zm = box.min_x, box.min_y, box.min_z
                sgs.append(SelectionBox((xm, ym, zm + self.control.GetValue()), (xx, yy, zz + self.control.GetValue())))
            if len(sgs) > 0:
                self.canvas.selection.set_selection_group(SelectionGroup(sgs))

        return OnClick

    def _boxEast(self, v):
        def OnClick(event):
            sgs = []
            for box in self.canvas.selection.selection_group.selection_boxes:
                xx, yy, zz = box.max_x, box.max_y, box.max_z
                xm, ym, zm = box.min_x, box.min_y, box.min_z
                sgs.append(SelectionBox((xm + self.control.GetValue(), ym, zm), (xx + self.control.GetValue(), yy, zz)))
            self.canvas.selection.set_selection_group(SelectionGroup(sgs))

        return OnClick

    def _boxWest(self, v):
        def OnClick(event):
            sgs = []
            for box in self.canvas.selection.selection_group.selection_boxes:
                xx, yy, zz = box.max_x, box.max_y, box.max_z
                xm, ym, zm = box.min_x, box.min_y, box.min_z
                sgs.append(SelectionBox((xm - self.control.GetValue(), ym, zm), (xx - self.control.GetValue(), yy, zz)))
            self.canvas.selection.set_selection_group(SelectionGroup(sgs))

        return OnClick

class BufferWorldTool(wx.Frame):
    def __init__(self, parent, canvas, world, *args, **kw):
        super(BufferWorldTool, self).__init__(parent, *args, **kw,
                                              style=(wx.MINIMIZE_BOX | wx.MAXIMIZE_BOX | wx.RESIZE_BORDER |
                                                     wx.SYSTEM_MENU | wx.CAPTION | wx.CLOSE_BOX | wx.CLIP_CHILDREN |
                                                     wx.FRAME_FLOAT_ON_PARENT),
                                              title="Selection, Organizer")

        self.parent = parent

        self.canvas = canvas
        self.world = world
        self.font = wx.Font(13, wx.FONTFAMILY_ROMAN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        self.SetFont(self.font)
        self.SetMinSize((320, 600))
        self.SetForegroundColour((0, 255, 0))
        self.SetBackgroundColour((0, 0, 0))
        self.Centre(direction=wx.VERTICAL)
        self.Freeze()
        self.world_location = ''
        self._sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self._sizer)
        self.font = wx.Font(11, wx.FONTFAMILY_ROMAN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        top_sizer = wx.BoxSizer(wx.VERTICAL)
        self._sizer.Add(top_sizer)
        self.label_main = wx.StaticText(self, label="Setup a blank world to work with\n"
                                                    "You Then would open that World with amulet\n"
                                                    " to pull in chunks from this One")
        self.label = wx.StaticText(self, label="Set The Range of chunks from Source Its Times 4: ")

        self.make_world_buffer = wx.Button(self, label="Build Buffer World")
        self.make_world_buffer.Bind(wx.EVT_BUTTON, self.make_world)
        self.world_load = wx.Button(self, label="Change/Add Source World Location\n"
                                                "(Make open world a buffer or changes the source world)\n"
                                                "Note: Simply adds a main_dir.txt with the source location.")
        self.world_load.Bind(wx.EVT_BUTTON, self.operation_run)
        self.keep_chunks = wx.CheckBox(self, label="Keep Previously Sourced Chunks\n"
                                                   "( uncheck to overwrite local from source )")
        self.keep_chunks.SetValue(True)
        self.the_range = wx.SpinCtrl(self, min=1, max=25)
        self.the_range.SetValue(6)
        self.source_new_data = wx.Button(self, label="Pull In Chunks")
        self.source_new_data.Bind(wx.EVT_BUTTON, self.operation_run_source)
        self.source_enty = wx.Button(self, label="Pull In All Entities")
        self.source_enty.Bind(wx.EVT_BUTTON, self.source_entities)
        self.send_enty = wx.Button(self, label="Send Entities Back")
        self.send_enty.Bind(wx.EVT_BUTTON, self.put_entities_back)

        self.source_players = wx.Button(self, label="Get All Player Data")
        self.source_players.Bind(wx.EVT_BUTTON, self.get_player_data)
        self.set_players = wx.Button(self, label="Send Back All Player Data")
        self.set_players.Bind(wx.EVT_BUTTON, self.set_player_data)

        self.save_new_data = wx.Button(self, label="Send Chunks Back")
        self.save_new_data.Bind(wx.EVT_BUTTON, self.put_data_back)

        self.del_chk = wx.Button(self, label="Delete Selected Chunks \n( Both Locations )")
        self.del_chk.Bind(wx.EVT_BUTTON, self.del_selected_chunks)

        self._sizer.Add(self.label_main)
        self._sizer.Add(self.make_world_buffer)
        self._sizer.Add(self.world_load, 0, wx.TOP, 10)

        self._sizer.Add(self.label, 0, wx.TOP, 15)
        self._sizer.Add(self.the_range, 0, wx.TOP, 5)
        self._sizer.Add(self.keep_chunks, 0, wx.TOP, 5)
        self._sizer.Add(self.source_new_data, 0, wx.TOP, 5)
        self._sizer.Add(self.save_new_data, 0, wx.TOP, 5)

        if self.world.level_wrapper.platform == 'bedrock':
            self._sizer.Add(self.source_enty, 0, wx.TOP, 15)
            self._sizer.Add(self.send_enty, 0, wx.TOP, 5)
        else:
            if self.world.level_wrapper.version >= 2730:
                self._sizer.Add(self.source_enty, 0, wx.TOP, 15)
                self._sizer.Add(self.send_enty, 0, wx.TOP, 5)

            else:
                self.source_enty.Hide()
                self.send_enty.Hide()

        self._sizer.Add(self.source_players, 0, wx.TOP, 5)
        self._sizer.Add(self.set_players, 0, wx.TOP, 5)
        self._sizer.Add(self.del_chk, 0, wx.TOP, 5)

        self.Layout()
        self.Thaw()

    def Onmsgbox(self, caption, message):  # message
        wx.MessageBox(message, caption, wx.OK | wx.ICON_INFORMATION)

    def con_boc(self, caption="", message=""):  # message, yes Know
        r = wx.MessageDialog(
            self, message,
            caption,
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION
        ).ShowModal()
        if r != wx.ID_YES:
            return True
        else:
            return False

    def make_world(self, _):
        if self.world.level_wrapper.platform == "bedrock":
            pathlocal = os.getenv('LOCALAPPDATA')
            mc_path = ''.join([pathlocal,
                               r'/Packages/Microsoft.MinecraftUWP_8wekyb3d8bbwe/LocalState/games/com.mojang/minecraftWorlds/'])
            with wx.DirDialog(None, "Select The World folder For the would you want to buffer", mc_path,
                              wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST) as fileDialog:
                if fileDialog.ShowModal() == wx.ID_CANCEL:
                    return
                else:
                    pathname = fileDialog.GetPath()
            if self.world.level_wrapper.path == pathname:
                self.Onmsgbox("Can Not Use Buffer as Source!", "This Would break!")
                return
            the_dir = pathname.split("\\")
            pathhome = ''.join([x + '/' for x in the_dir[:-1]])
            world_buffer_f = pathhome + "buffer" + str(the_dir[-1])
            os.mkdir(world_buffer_f)
            os.mkdir(world_buffer_f + "/db")
            shutil.copy(pathname + "/level.dat", world_buffer_f + "/level.dat")
            shutil.copy(pathname + "/world_icon.jpeg", world_buffer_f + "/world_icon.jpeg")
            header, new_raw = b'', b''

            with open(world_buffer_f + "/levelname.txt", "w") as data:
                data.write("BufferLevel")

            with open(world_buffer_f + '/main_dir.txt', "w") as data:
                data.write(pathname + "/db")

            with open(world_buffer_f + "/level.dat", "rb") as data:
                the_data = data.read()
                header = the_data[:4]
                nbt_leveldat = load(the_data[8:], compressed=False, little_endian=True)
                nbt_leveldat['LevelName'] = StringTag("BufferLevel")
                new_raw = nbt_leveldat.save_to(compressed=False, little_endian=True)
                header += struct.pack("<I", len(new_raw))

            with open(world_buffer_f + "/level.dat", "wb") as data:
                data.write(header + new_raw)

            self.raw_level = LevelDB(pathname + "/db", create_if_missing=False)
            self.new_raw_level = LevelDB(world_buffer_f + "/db", create_if_missing=True)

            player_d = self.raw_level.get(b'~local_player')
            self.new_raw_level.put(b'~local_player', player_d)
            self.raw_level.close(compact=False)
            self.new_raw_level.close(compact=False)
            folder = world_buffer_f.split("/")[-1]
            self.Onmsgbox("World is Ready to open and to pull chunks", f"Created {folder}")
        else:  # java
            pathlocal = os.getenv('APPDATA')
            pathname = ''
            mc_path = ''.join([pathlocal,
                               r'/.minecraft/saves'])
            with wx.DirDialog(None, "Select The World folder For the would you want to buffer", mc_path,
                              wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST) as fileDialog:
                if fileDialog.ShowModal() == wx.ID_CANCEL:
                    return
                else:
                    pathname = fileDialog.GetPath()
            if self.world.level_wrapper.path == pathname:
                self.Onmsgbox("Can Not Use Buffer as Source!", "This Would break!")
                return

            the_dir = pathname.split("\\")
            pathhome = ''.join([x + '/' for x in the_dir[:-1]])
            world_buffer_f = pathhome + "buffer" + str(the_dir[-1])
            os.mkdir(world_buffer_f)
            os.mkdir(world_buffer_f + "/region")
            os.mkdir(world_buffer_f + "/DIM-1")
            os.mkdir(world_buffer_f + "/DIM1")
            # if self.world.level_wrapper.version >= 2730:
            #     os.mkdir(world_buffer_f + "/entities")

            shutil.copy(pathname + "/level.dat", world_buffer_f + "/level.dat")

            try:
                shutil.copy(pathname + "/icon.png", world_buffer_f + "/icon.png")
            except:
                pass
            with open(world_buffer_f + '/main_dir.txt', "w") as data:
                data.write(pathname)
            # with open(f"{world_buffer_f}/level.dat", "bw+", ) as dat:
            data = load(f"{world_buffer_f}/level.dat", compressed=True, little_endian=False)
            data["Data"]["LevelName"] = StringTag("buffer" + str(the_dir[-1]))
            save = data.save_to(compressed=True, little_endian=False)
            with open(f"{world_buffer_f}/level.dat", "wb") as f:
                f.write(save)

    def close(self, _):
        self.raw_level.close(compact=False)

    def operation_run(self, _):

        self.world_load_data()

    def del_selected_chunks(self, _):
        if exists(self.world.level_wrapper.path + '/main_dir.txt'):
            self.world.save()
            with open(self.world.level_wrapper.path + '/main_dir.txt', "r") as d:
                self.world_location = d.read()
                d.close()
            self.raw_level = LevelDB(self.world_location, create_if_missing=False)
            the_chunks = self.canvas.selection.selection_group.chunk_locations()
            to_delete_list = []

            for xx, zz in the_chunks:
                chunkkey = struct.pack('<ii', xx, zz) + self.get_dim_value_bytes()
                key_len = len(chunkkey)
                contin = False
                for k, v in self.raw_level.iterate(start=chunkkey, end=chunkkey + b'\xff\xff'):
                    if len(k) > key_len + 1:
                        contin = True
                        break
                if contin:
                    for k, v in self.raw_level.iterate(start=chunkkey, end=chunkkey + b'\xff\xff'):
                        if key_len <= len(k) <= key_len + 3:
                            to_delete_list.append(k)

            for d in to_delete_list:
                self.raw_level.delete(d)
            self.raw_level.close(compact=False)
            self.canvas.run_operation(
                lambda: delete_chunk(
                    self.canvas.world,
                    self.canvas.dimension,
                    self.canvas.selection.selection_group,
                    False,

                ))

            self.world.unload()
            self.canvas.renderer.render_world._rebuild()

            self.Onmsgbox("Chunks Deleted", f"Deleted chunks {the_chunks}")

    def operation_run_source(self, _):

        self.source_new()
        self.world.unload()
        self.canvas.renderer.render_world._rebuild()

    def get_player_data(self, _):
        if self.world.level_wrapper.platform == 'bedrock':
            if exists(self.world.level_wrapper.path + '/main_dir.txt'):
                with open(self.world.level_wrapper.path + '/main_dir.txt', "r") as d:
                    self.world_location = d.read()

                self.raw_level = LevelDB(self.world_location, create_if_missing=False)
                player_d = self.raw_level.get(b'~local_player')
                for k, v in self.raw_level.iterate(start=b'player_server_',
                                                   end=b'player_server_\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF'):
                    self.level_db.put(k, v)

                self.level_db.put(b'~local_player', player_d)
                self.raw_level.close(compact=False)
        else:  # java
            if exists(self.world.level_wrapper.path + '/main_dir.txt'):
                with open(self.world.level_wrapper.path + '/main_dir.txt', "r") as d:
                    self.world_location = d.read()
                # buffer_world = os.path.join(self.world_location, 'PlayersData' )
                buffer_world = ''.join(self.world_location + "/PlayersData")
                os.system(f"cp -rf \"{buffer_world}\" \"{self.world.level_wrapper.path}\"")

    def set_player_data(self, _):
        if self.world.level_wrapper.platform == 'bedrock':
            if exists(self.world.level_wrapper.path + '/main_dir.txt'):
                with open(self.world.level_wrapper.path + '/main_dir.txt', "r") as d:
                    self.world_location = d.read()
                self.raw_level = LevelDB(self.world_location, create_if_missing=False)
                player_d = self.level_db.get(b'~local_player')
                for k, v in self.level_db.iterate(start=b'player_server_',
                                                  end=b'player_server_\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF'):
                    self.raw_level.put(k, v)

                self.raw_level.put(b'~local_player', player_d)
                self.raw_level.close(compact=False)
        else:
            if exists(self.world.level_wrapper.path + '/main_dir.txt'):
                with open(self.world.level_wrapper.path + '/main_dir.txt', "r") as d:
                    self.world_location = d.read()

                buffer_world = ''.join(self.world_location)
                os.system(f"cp -rf \"{self.world.level_wrapper.path}/PlayersData\" \"{buffer_world}\"")

    def world_load_data(self):

        if self.world.level_wrapper.platform == 'bedrock':
            pathname = ''
            pathlocal = os.getenv('LOCALAPPDATA')
            mc_path = ''.join([pathlocal,
                               r'/Packages/Microsoft.MinecraftUWP_8wekyb3d8bbwe/LocalState/games/com.mojang/minecraftWorlds/'])
            with wx.DirDialog(None, "Pick A SOURCE World Directory", "",
                              wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST) as fileDialog:
                if fileDialog.ShowModal() == wx.ID_CANCEL:
                    return
                else:
                    pathname = fileDialog.GetPath()

            if self.world.level_wrapper.path == pathname:
                self.Onmsgbox("Can Not Use Buffer as Source!", "This Would not work")
                return
            self.world_location = pathname + '/db'
            with open(self.world.level_wrapper.path + '/main_dir.txt', "w") as fdata:
                print(self.world_location)
                fdata.write(self.world_location)

            set_player = self.con_boc("Source World Location added ",
                                      f"Do You want Replace local player data from this world? "
                                      "\n After reloading world you will spawn in that location same"
                                      "Click No To Keep this Local players data\n"
                                      f" and to manually set location")
            if set_player:
                self.raw_level = LevelDB(pathname + '/db', create_if_missing=False)
                player_d = self.raw_level.get(b'~local_player')
                self.level_db.put(b'~local_player', player_d)
                self.raw_level.close(compact=False)
            self.Onmsgbox(f"This World can now pull data from {pathname}", "Updated")
        else:
            pathlocal = os.getenv('APPDATA')
            pathname = ''
            mc_path = ''.join([pathlocal,
                               r'/.minecraft/saves'])
            with wx.DirDialog(None, "Select The World folder For the would you want to buffer", mc_path,
                              wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST) as fileDialog:
                if fileDialog.ShowModal() == wx.ID_CANCEL:
                    return
                else:
                    pathname = fileDialog.GetPath()
            if self.world.level_wrapper.path == pathname:
                self.Onmsgbox("Can Not Use Buffer as Source!", "This Would break!")
                return

            the_dir = pathname.split("\\")
            pathhome = ''.join([x + '/' for x in the_dir[:-1]])

            with open(self.world.level_wrapper.path + '/main_dir.txt', "w") as data:
                data.write(pathname)
            self.Onmsgbox("Updated", f"This World can now pull data from {pathname}")

    def get_dim_value_bytes(self):
        if 'minecraft:the_end' in self.canvas.dimension:
            dim = int(2).to_bytes(4, 'little', signed=True)
        elif 'minecraft:the_nether' in self.canvas.dimension:
            dim = int(1).to_bytes(4, 'little', signed=True)
        elif 'minecraft:overworld' in self.canvas.dimension:
            dim = b''  # int(0).to_bytes(4, 'little', signed=True)
        return dim

    def put_data_back(self, _):
        if exists(self.world.level_wrapper.path + '/main_dir.txt'):
            self.world.save()
            with open(self.world.level_wrapper.path + '/main_dir.txt', "r") as d:
                self.world_location = d.read()

            ###############################################################
            if self.world.level_wrapper.platform == "bedrock":
                self.raw_level = LevelDB(self.world_location, create_if_missing=False)
                the_chunks = [c for c in self.world.level_wrapper.all_chunk_coords(self.canvas.dimension)]
                for xx, zz in the_chunks:
                    chunkkey = struct.pack('<ii', xx, zz) + self.get_dim_value_bytes()
                    key_len = len(chunkkey)
                    contin = False
                    for k, v in self.raw_level.iterate(start=chunkkey, end=chunkkey + b'\xff\xff'):
                        if len(k) > key_len + 1:
                            contin = True
                            break
                    if contin:
                        for k, v in self.level_db.iterate(start=chunkkey, end=chunkkey + b'\xff\xff'):
                            if key_len <= len(k) <= key_len + 3:
                                self.raw_level.put(k, v)
                self.raw_level.close(compact=False)
                self.Onmsgbox("Chunks Saved to Source", f"Chunks Saved {the_chunks}")
            else:  # java
                buffer_world = ''.join(self.world.level_wrapper.path + "/" + self.get_dim_path_name())
                os.system(f"cp -rf \"{buffer_world}\" \"{self.world_location}\"")
                # shutil.copytree(buffer_world, source_world)
                self.Onmsgbox("Chunks Saved to Source", f"Copied {buffer_world} to {source_world}")

    def source_new(self):

        if exists(self.world.level_wrapper.path + '/main_dir.txt'):
            chunk_range, the_chunks, the_data = [], [], []
            with open(self.world.level_wrapper.path + '/main_dir.txt', "r") as d:
                self.world_location = d.read()
            if self.world.level_wrapper.platform == "java":
                loc = self.canvas.camera.location
                cx, cz = block_coords_to_chunk_coords(loc[0], loc[2])
                prang = self.the_range.GetValue()
                loaction_dict = collections.defaultdict(list)
                for x in range(-prang, prang):
                    for z in range(-prang, prang):
                        chunk_range.append((cx + x, cz + z))
                total = len(chunk_range)
                copy_set = set()
                chunk_set = set()
                for xx, zz in chunk_range:
                    rx, rz = world_utils.chunk_coords_to_region_coords(xx, zz)
                    loaction_dict[(rx, rz)].append((xx, zz))
                for rx, rz in loaction_dict.keys():
                    source_world = self.get_nbt_reg_file(rx, rz, self.world_location)
                    if exists(source_world):
                        buffer_world = self.get_nbt_reg_file(rx, rz, self.world.level_wrapper.path)
                        source_chunks = AnvilRegion(source_world)
                        for xx, zz in source_chunks.all_chunk_coords():
                            chunk_set.add((xx, zz))
                            copy_set.add((source_world, buffer_world))
                for xx, zz in chunk_set:
                    self.world.create_chunk(xx, zz, self.canvas.dimension).changed = True
                self.world.purge()
                for s, d in copy_set:
                    shutil.copy(s, d)

            else:  # bedrock
                self.raw_level = LevelDB(self.world_location, create_if_missing=False)
                chunk_range, the_chunks, the_data = [], [], []
                loc = self.canvas.camera.location
                cx, cz = block_coords_to_chunk_coords(loc[0], loc[2])
                prang = self.the_range.GetValue()
                for x in range(-prang, prang):
                    for z in range(-prang, prang):
                        chunk_range.append((cx + x, cz + z))
                for xx, zz in chunk_range:
                    chunkkey = struct.pack('<ii', xx, zz) + self.get_dim_value_bytes()
                    key_len = len(chunkkey)
                    contin = False
                    for k, v in self.raw_level.iterate(start=chunkkey, end=chunkkey + b'\xff\xff'):
                        if len(k) > key_len + 1:
                            contin = True
                            break
                    if contin:
                        for k, v in self.raw_level.iterate(start=chunkkey, end=chunkkey + b'\xff\xff'):
                            if key_len <= len(k) <= key_len + 3:
                                if self.keep_chunks.GetValue():
                                    if not self.world.has_chunk(xx, zz, self.canvas.dimension):
                                        the_chunks.append((xx, zz))
                                        the_data.append((k, v))
                                else:
                                    the_chunks.append((xx, zz))
                                    the_data.append((k, v))
                for xx, zz in the_chunks:
                    self.world.create_chunk(xx, zz, self.canvas.dimension).changed = True
                self.world.save()
                for k, v in the_data:
                    self.level_db.put(k, v)
                self.raw_level.close(compact=False)

    def source_entities(self, _):
        if self.world.level_wrapper.platform == 'bedrock':
            if exists(self.world.level_wrapper.path + '/main_dir.txt'):
                with open(self.world.level_wrapper.path + '/main_dir.txt', "r") as d:
                    self.world_location = d.read()
                    d.close()
                self.raw_level = LevelDB(self.world_location, create_if_missing=False)
                actorprefixs = iter(self.raw_level.iterate(start=b'actorprefix',
                                                           end=b'actorprefix\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF'))
                digps = iter(self.raw_level.iterate(start=b'digp',
                                                    end=b'digp\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF'))
                for k, v in actorprefixs:
                    self.level_db.put(k, v)
                for k, v in digps:
                    self.level_db.put(k, v)
                self.raw_level.close(compact=False)
                self.Onmsgbox("Entities Added", f"All Entities from source world are now in this world.")
        else:  # java
            if exists(self.world.level_wrapper.path + '/main_dir.txt'):
                with open(self.world.level_wrapper.path + '/main_dir.txt', "r") as d:
                    self.world_location = d.read()

                buffer_world = ''.join(self.world_location + "/entities")
                os.system(f"cp -rf \"{buffer_world}\" \"{self.world.level_wrapper.path}\" ")
                self.Onmsgbox("Entities Added", f"All Entities from source world are now in this world.")

    def put_entities_back(self, _):
        if self.world.level_wrapper.platform == 'bedrock':
            if exists(self.world.level_wrapper.path + '/main_dir.txt'):
                confirm = self.con_boc("PLEASE NOTE:",
                                       "This Removes all entities and then copies them Back from this copy\n"
                                       "If you have Not pulled in entities all entities will be removed\n"
                                       "are you sure you want to continue?")
                if confirm:
                    with open(self.world.level_wrapper.path + '/main_dir.txt', "r") as d:
                        self.world_location = d.read()
                    to_remove = []
                    self.raw_level = LevelDB(self.raw_level, create_if_missing=False)
                    actorprefixs_b = iter(self.raw_level.iterate(start=b'actorprefix',
                                                                 end=b'actorprefix\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF'))
                    digps_b = iter(self.raw_level.iterate(start=b'digp',
                                                          end=b'digp\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF'))
                    for k, v in actorprefixs_b:
                        to_remove.append(k)
                    for k, v in digps_b:
                        to_remove.append(k)
                    for dk in to_remove:
                        self.raw_level.delete(dk)  # TODO Find a better way to accomplish this

                    actorprefixs = iter(self.level_db.iterate(start=b'actorprefix',
                                                              end=b'actorprefix\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF'))
                    digps = iter(self.level_db.iterate(start=b'digp',
                                                       end=b'digp\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF'))
                    for k, v in actorprefixs:
                        self.raw_level.put(k, v)
                    for k, v in digps:
                        self.raw_level.put(k, v)

                    self.raw_level.close(compact=False)
                    self.Onmsgbox("Done", "Entities Have been copied back to source world")
            else:  # java
                if exists(self.world.level_wrapper.path + '/main_dir.txt'):
                    with open(self.world.level_wrapper.path + '/main_dir.txt', "r") as d:
                        self.world_location = d.read()
                buffer_world = ''.join(self.world_location)
                os.system(f"cp -rf {self.world.level_wrapper.path}/entities {buffer_world}")
                self.Onmsgbox("Done", "Entities Have been copied back to source world")

    @property
    def level_db(self):
        level_wrapper = self.world.level_wrapper
        if hasattr(level_wrapper, "level_db"):
            return level_wrapper.level_db
        else:
            return level_wrapper._level_manager._db

    @property
    def big_level_db(self):
        level_wrapper = self.big_world.level_wrapper
        if hasattr(level_wrapper, "level_db"):
            return level_wrapper.level_db
        else:
            return level_wrapper._level_manager._db

    def get_root(self):
        return self.world.level_wrapper.path

    def get_dim_path_name(self):
        if 'minecraft:the_end' in self.canvas.dimension:
            dim = 'DIM1'
        elif 'minecraft:the_nether' in self.canvas.dimension:
            dim = 'DIM-1'
        elif 'minecraft:overworld' in self.canvas.dimension:
            dim = ''

        full_path = os.path.join(dim, "region")
        return full_path

    def get_nbt_reg_file(self, regonx, regonz, path):
        file = "r." + str(regonx) + "." + str(regonz) + ".mca"
        if 'minecraft:the_end' in self.canvas.dimension:
            dim = 'DIM1'
        elif 'minecraft:the_nether' in self.canvas.dimension:
            dim = 'DIM-1'
        elif 'minecraft:overworld' in self.canvas.dimension:
            dim = ''
        version = "region"
        full_path = os.path.join(path, dim, version, file)
        return full_path

class PositionSelection(wx.Frame):
    def __init__(self, parent, canvas, world, *args, **kw):
        super(PositionSelection, self).__init__(parent, *args, **kw,
                                                style=(wx.MINIMIZE_BOX | wx.MAXIMIZE_BOX | wx.RESIZE_BORDER |
                                                       wx.SYSTEM_MENU | wx.CAPTION | wx.CLOSE_BOX | wx.CLIP_CHILDREN |
                                                       wx.FRAME_FLOAT_ON_PARENT),
                                                title="Selection, Organizer")

        self.parent = parent

        self.canvas = canvas
        self.world = world
        self.font = wx.Font(13, wx.FONTFAMILY_ROMAN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        self.SetFont(self.font)
        self.SetForegroundColour((0, 255, 0))
        self.SetBackgroundColour((0, 0, 0))
        self.Centre(direction=wx.VERTICAL)

        self.pos_sizer = wx.BoxSizer(wx.VERTICAL)
        self.top_h = wx.BoxSizer(wx.HORIZONTAL)
        self.bot_h = wx.BoxSizer(wx.HORIZONTAL)
        self.side_sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self.pos_sizer)

        self._create_buttons()
        self._create_main_buttons()
        self._arrange_main_buttons()

        self.Fit()
        self.Layout()
        self.Show(True)

    def _create_buttons(self):
        button_size = (60, 60)

        self._up = self._create_button("U", button_size, self._boxUp('m'))
        self._down = self._create_button("D", button_size, self._boxDown('m'))
        self._east = self._create_button("E", button_size, self._boxEast('m'))
        self._west = self._create_button("W", button_size, self._boxWest('m'))
        self._north = self._create_button("N", button_size, self._boxNorth('m'))
        self._south = self._create_button("S", button_size, self._boxSouth('m'))

        self._upp = self._create_button("u+", button_size, self._boxUp('p'))
        self._downp = self._create_button("d+", button_size, self._boxDown('p'))
        self._eastp = self._create_button("e+", button_size, self._boxEast('p'))
        self._westp = self._create_button("w+", button_size, self._boxWest('p'))
        self._northp = self._create_button("n+", button_size, self._boxNorth('p'))
        self._southp = self._create_button("s+", button_size, self._boxSouth('p'))

        self._upm = self._create_button("u-", button_size, self._boxUp('n'))
        self._downm = self._create_button("d-", button_size, self._boxDown('n'))
        self._eastm = self._create_button("e-", button_size, self._boxEast('n'))
        self._westm = self._create_button("w-", button_size, self._boxWest('n'))
        self._northm = self._create_button("n-", button_size, self._boxNorth('n'))
        self._southm = self._create_button("s-", button_size, self._boxSouth('n'))

        self._arrange_buttons()

    def _create_main_buttons(self):

        diag_button_size = (120, 30)
        self._southeast = self._create_button("South East", diag_button_size, self._boxDiag('se'))
        self._northeast = self._create_button("North East", diag_button_size, self._boxDiag('ne'))
        self._northwest = self._create_button("North West", diag_button_size, self._boxDiag('nw'))
        self._southwest = self._create_button("South West", diag_button_size, self._boxDiag('sw'))

        diag_button_size_large = (120, 66)
        self._dnorth = self._create_button("Down && North", diag_button_size, self._boxDiag('dan'))
        self._dsouth = self._create_button("Down && South", diag_button_size, self._boxDiag('das'))
        self._deast = self._create_button("Down && East", diag_button_size, self._boxDiag('dae'))
        self._dwest = self._create_button("Down && West", diag_button_size, self._boxDiag('daw'))

        self._unorth = self._create_button("Up && North", diag_button_size, self._boxDiag('uan'))
        self._usouth = self._create_button("Up && South", diag_button_size, self._boxDiag('uas'))
        self._ueast = self._create_button("Up && East", diag_button_size, self._boxDiag('uae'))
        self._uwest = self._create_button("Up && West", diag_button_size, self._boxDiag('uaw'))

        self._usoutheast = self._create_button("Up\n South East", diag_button_size_large, self._boxDiag('use'))
        self._unortheast = self._create_button("Up\n North East", diag_button_size_large, self._boxDiag('une'))
        self._unorthwest = self._create_button("Up\n North West", diag_button_size_large, self._boxDiag('unw'))
        self._usouthwest = self._create_button("Up\n South West", diag_button_size_large, self._boxDiag('usw'))

        self._dsoutheast = self._create_button("Down\n South East", diag_button_size_large, self._boxDiag('dse'))
        self._dnortheast = self._create_button("Down\n North East", diag_button_size_large, self._boxDiag('dne'))
        self._dnorthwest = self._create_button("Down\n North West", diag_button_size_large, self._boxDiag('dnw'))
        self._dsouthwest = self._create_button("Down\n South West", diag_button_size_large, self._boxDiag('dsw'))

        self.lbct = wx.StaticText(self, label="Step:")

        self.lbstrech = wx.StaticText(self, label="Stretch Last Selection:")

        self.control = wx.SpinCtrl(self, value="1", min=1, max=1000)

    def _create_button(self, label, size, handler):
        button = wx.Button(self, label=label, size=size)
        button.Bind(wx.EVT_BUTTON, handler)
        return button

    def _arrange_buttons(self):
        self.boxgrid = wx.GridSizer(3, 4, 2, 2)
        self.boxgrid_b = wx.GridSizer(3, 2, 2, 2)

        self.boxgrid.Add(self._upp)
        self.boxgrid.Add(self._upm)
        self.boxgrid.Add(self._downp)
        self.boxgrid.Add(self._downm)
        self.boxgrid_b.Add(self._up)
        self.boxgrid_b.Add(self._down)
        self.boxgrid.Add(self._eastp)
        self.boxgrid.Add(self._eastm)
        self.boxgrid.Add(self._westp)
        self.boxgrid.Add(self._westm)
        self.boxgrid_b.Add(self._east)
        self.boxgrid_b.Add(self._west)
        self.boxgrid.Add(self._northp)
        self.boxgrid.Add(self._northm)
        self.boxgrid.Add(self._southp)
        self.boxgrid.Add(self._southm)
        self.boxgrid_b.Add(self._north)
        self.boxgrid_b.Add(self._south)

        self.grid_and_text = wx.GridSizer(0, 2, 10, 5)
        self.label_grid_mover_l = wx.StaticText(self, label="Size ↑ ")
        self.label_grid_mover_l2 = wx.StaticText(self, label="        Move all ↑")

        self.grid_and_text.Add(self.label_grid_mover_l, 0, wx.LEFT, 0)
        self.grid_and_text.Add(self.label_grid_mover_l2, 0, wx.LEFT, 25)
        self.top_h.Add(self.boxgrid, 0, wx.LEFT, 2)
        self.top_h.Add(self.boxgrid_b, 0, wx.LEFT, 50)
        self.bot_h.Add(self.grid_and_text, 0, wx.LEFT, 80)
        self.pos_sizer.Add(self.top_h)
        self.pos_sizer.Add(self.bot_h)

    def _arrange_main_buttons(self):
        self.boxgrid_b = wx.GridSizer(1, 2, 1, 5)

        self.boxgrid_b.Add(self.lbct)
        self.boxgrid_b.Add(self.control)

        self.boxgrid_dandd = wx.GridSizer(1, 4, 1, 5)
        self.boxgrid_dandd.Add(self._dnorth)
        self.boxgrid_dandd.Add(self._dsouth)
        self.boxgrid_dandd.Add(self._deast)
        self.boxgrid_dandd.Add(self._dwest)

        self.boxgrid_dandu = wx.GridSizer(1, 4, 1, 5)
        self.boxgrid_dandu.Add(self._unorth)
        self.boxgrid_dandu.Add(self._usouth)
        self.boxgrid_dandu.Add(self._ueast)
        self.boxgrid_dandu.Add(self._uwest)

        self.boxgrid_d = wx.GridSizer(1, 4, 1, 5)
        self.boxgrid_d.Add(self._northeast)
        self.boxgrid_d.Add(self._southeast)
        self.boxgrid_d.Add(self._northwest)
        self.boxgrid_d.Add(self._southwest)

        self.boxgrid_u = wx.GridSizer(1, 4, 2, 5)
        self.boxgrid_u.Add(self._unortheast)
        self.boxgrid_u.Add(self._usoutheast)
        self.boxgrid_u.Add(self._unorthwest)
        self.boxgrid_u.Add(self._usouthwest)

        self.boxgrid_down = wx.GridSizer(1, 4, 1, 5)
        self.boxgrid_down.Add(self._dnortheast)
        self.boxgrid_down.Add(self._dsoutheast)
        self.boxgrid_down.Add(self._dnorthwest)
        self.boxgrid_down.Add(self._dsouthwest)

        self.side_sizer.Add(self.boxgrid_b, 0, wx.LEFT, 70)
        self.side_sizer.Add(self.lbstrech)
        self.side_sizer.Add(self.boxgrid_dandd, 0, wx.TOP | wx.LEFT, 0)
        self.side_sizer.Add(self.boxgrid_dandu, 0, wx.TOP | wx.LEFT, 0)
        self.side_sizer.Add(self.boxgrid_d, 0, wx.TOP | wx.LEFT, 0)
        self.side_sizer.Add(self.boxgrid_u, 0, wx.TOP | wx.LEFT, 0)
        self.side_sizer.Add(self.boxgrid_down, 0, wx.TOP | wx.LEFT, 0)

        self.pos_sizer.Add(self.side_sizer)
        self.pos_sizer.Layout()

    def _move_box(self, mode, dx=0, dy=0, dz=0):
        def OnClick(event):

            sgs = []

            for box in self.canvas.selection.selection_group.selection_boxes:
                xx, yy, zz = box.max_x, box.max_y, box.max_z
                xm, ym, zm = box.min_x, box.min_y, box.min_z
                if mode == 'p':
                    sgs.append(SelectionBox(
                        (xm, ym, zm),
                        (xx + dx * self.control.GetValue(), yy - dy * self.control.GetValue(),
                         zz + dz * self.control.GetValue())
                    ))
                elif mode == 'n':
                    sgs.append(SelectionBox(
                        (xm + dx * self.control.GetValue(), ym + dy * self.control.GetValue(),
                         zm + dz * self.control.GetValue()),
                        (xx, yy, zz)
                    ))
                else:
                    sgs.append(SelectionBox(
                        (xm + dx * self.control.GetValue(), ym - dy * self.control.GetValue(),
                         zm + dz * self.control.GetValue()),
                        (xx + dx * self.control.GetValue(), yy - dy * self.control.GetValue(),
                         zz + dz * self.control.GetValue())
                    ))

            self.canvas.selection.set_selection_group(SelectionGroup(sgs))

        return OnClick

    def _boxUp(self, mode):
        return self._move_box(mode, dy=-1)

    def _boxDown(self, mode):
        return self._move_box(mode, dy=1)

    def _boxNorth(self, mode):
        return self._move_box(mode, dz=-1)

    def _boxSouth(self, mode):
        return self._move_box(mode, dz=1)

    def _boxEast(self, mode):
        return self._move_box(mode, dx=1)

    def _boxWest(self, mode):
        return self._move_box(mode, dx=-1)

    def _move_box_diag(self, dx, dy, dz, reverse_condition):
        def OnClick(event):
            group = self.canvas.selection.selection_group
            glist = list(group)
            x, y, z = glist[0].point_1
            xx, yy, zz = glist[-1].point_2

            if reverse_condition(x, xx, y, yy, z, zz):
                glist.reverse()

            for _ in range(self.control.GetValue()):
                x, y, z = glist[-1].point_1
                xx, yy, zz = glist[-1].point_2
                new = SelectionBox((x + dx, y + dy, z + dz), (xx + dx, yy + dy, zz + dz))
                glist.append(new)
                merg = SelectionGroup(glist).merge_boxes()
                self.canvas.selection.set_selection_group(merg)

        return OnClick

    def _boxDiag(self, v):
        if v == 'se':
            return self._move_box_diag(1, 0, 1, lambda x, xx, y, yy, z, zz: x > xx and z < zz)
        if v == 'nw':
            return self._move_box_diag(-1, 0, -1, lambda x, xx, y, yy, z, zz: x < xx and z > zz)
        if v == 'ne':
            return self._move_box_diag(1, 0, -1, lambda x, xx, y, yy, z, zz: z < zz)
        if v == 'sw':
            return self._move_box_diag(-1, 0, 1, lambda x, xx, y, yy, z, zz: z > zz)
        if v == 'use':
            return self._move_box_diag(1, 1, 1, lambda x, xx, y, yy, z, zz: x > xx and z < zz and y > yy)
        if v == 'unw':
            return self._move_box_diag(-1, 1, -1, lambda x, xx, y, yy, z, zz: x > xx and z > zz and y > yy)
        if v == 'une':
            return self._move_box_diag(1, 1, -1, lambda x, xx, y, yy, z, zz: x < xx and z < zz and y < yy)
        if v == 'usw':
            return self._move_box_diag(-1, 1, 1, lambda x, xx, y, yy, z, zz: x > xx and z < zz and y > yy)
        if v == 'dse':
            return self._move_box_diag(1, -1, 1, lambda x, xx, y, yy, z, zz: x < xx and z < zz and y < yy)
        if v == 'dnw':
            return self._move_box_diag(-1, -1, -1, lambda x, xx, y, yy, z, zz: x > xx and z > zz and y < yy)
        if v == 'dne':
            return self._move_box_diag(1, -1, -1, lambda x, xx, y, yy, z, zz: x < xx and z > zz and y < yy)
        if v == 'dsw':
            return self._move_box_diag(-1, -1, 1, lambda x, xx, y, yy, z, zz: x > xx and z < zz and y < yy)

        if v == 'dan':
            return self._move_box_diag(0, -1, -1, lambda x, xx, y, yy, z, zz: x < xx and z < zz and y < yy)
        if v == 'das':
            return self._move_box_diag(0, -1, 1, lambda x, xx, y, yy, z, zz: x > xx and z > zz and y < yy)
        if v == 'dae':
            return self._move_box_diag(1, -1, 0, lambda x, xx, y, yy, z, zz: x < xx and z > zz and y < yy)
        if v == 'daw':
            return self._move_box_diag(-1, -1, 0, lambda x, xx, y, yy, z, zz: x < xx and z < zz and y < yy)

        if v == 'uan':
            return self._move_box_diag(0, 1, -1, lambda x, xx, y, yy, z, zz: x < xx and z < zz and y < yy)
        if v == 'uas':
            return self._move_box_diag(0, 1, 1, lambda x, xx, y, yy, z, zz: x > xx and z > zz and y < yy)
        if v == 'uae':
            return self._move_box_diag(1, 1, 0, lambda x, xx, y, yy, z, zz: x < xx and z > zz and y < yy)
        if v == 'uaw':
            return self._move_box_diag(-1, 1, 0, lambda x, xx, y, yy, z, zz: x < xx and z < zz and y < yy)

class SelectionOrganizer(wx.Frame):

    def __init__(self, parent, world, canvas, *args, **kw):
        super(SelectionOrganizer, self).__init__(parent, *args, **kw,
                                                 style=(wx.MINIMIZE_BOX | wx.MAXIMIZE_BOX | wx.RESIZE_BORDER |
                                                        wx.SYSTEM_MENU | wx.CAPTION | wx.CLOSE_BOX | wx.CLIP_CHILDREN |
                                                        wx.FRAME_FLOAT_ON_PARENT),
                                                 name="Blending Panel", title="Selection, Organizer")
        self.parent = parent
        self.canvas = canvas
        self.world = world

        self._sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self._sizer)

        self._initialize_ui()
        self._set_font_and_colors()
        self._create_controls()
        self._setup_layout()

        self.Fit()
        self.Layout()
        self.Show(True)

    def _initialize_ui(self):
        self.Freeze()
        self._sizer.Clear(True)
        self._sizer.Add(wx.BoxSizer(wx.VERTICAL), 1, wx.EXPAND, 0)
        self._sizer.Add(wx.BoxSizer(wx.VERTICAL), 0, wx.EXPAND | wx.TOP, 5)
        self._sizer.Add(wx.BoxSizer(wx.VERTICAL), 0, wx.EXPAND | wx.TOP, 290)
        self.Thaw()

    def _set_font_and_colors(self):
        self.font = wx.Font(13, wx.FONTFAMILY_ROMAN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        self.SetForegroundColour((0, 255, 0))
        self.SetBackgroundColour((0, 0, 0))

    def _create_controls(self):
        self._create_buttons()
        self._create_text_controls()

    def _create_buttons(self):
        self.g_load = wx.Button(self, label="Load", size=(80, 50))
        self.g_save = wx.Button(self, label="Save", size=(80, 50))
        self._delete_unselected_chunks = wx.Button(self, label="DELETE \n Unselected \nChunks", size=(80, 50))
        self._run_button = wx.Button(self, label="Set \n Selection Boxs", size=(80, 50))
        self.gsel = wx.Button(self, label="Get \n Selection Boxs", size=(80, 50))
        self.g_merge = wx.Button(self, label="Merge Dupes\nDels Text", size=(80, 50))

        self._delete_unselected_chunks.SetOwnForegroundColour((0, 0, 0))
        self._delete_unselected_chunks.SetOwnBackgroundColour((255, 0, 0))

        self._bind_events()

    def _bind_events(self):
        self.g_load.Bind(wx.EVT_BUTTON, self.load_data)
        self.g_load.SetDefault()
        self._delete_unselected_chunks.Bind(wx.EVT_BUTTON, self.delete_unselected)
        self._run_button.Bind(wx.EVT_BUTTON, self._run_operation)
        self.gsel.Bind(wx.EVT_BUTTON, self._gsel)
        self.g_save.Bind(wx.EVT_BUTTON, self.save_data)
        self.g_merge.Bind(wx.EVT_BUTTON, self.merge)

    def _create_text_controls(self):
        self._area_size_for_point = wx.TextCtrl(
            self, style=wx.TE_PROCESS_ENTER, size=(100,26)
        )
        self.lbl = wx.StaticText(self, label="For one point area size")
        self._area_size_for_point.SetValue("10,10,10")
        self._location_data = wx.TextCtrl(
            self, style=wx.TE_MULTILINE | wx.TE_BESTWRAP, size=(200, 300)
        )
        self.chk = wx.CheckBox(self, label="Enable:")
        self.lbl.SetFont(self.font)
        self.lbl.SetForegroundColour((0, 255, 0))
        self.lbl.SetBackgroundColour((0, 0, 0))
        self._area_size_for_point.SetFont(self.font)
        self._area_size_for_point.SetForegroundColour((0, 255, 0))
        self._area_size_for_point.SetBackgroundColour((0, 0, 0))
        self._location_data.SetFont(self.font)
        self._location_data.SetForegroundColour((0, 255, 0))
        self._location_data.SetBackgroundColour((0, 0, 0))

    def _setup_layout(self):
        side_sizer = wx.BoxSizer(wx.HORIZONTAL)
        mid_sizer = wx.BoxSizer(wx.HORIZONTAL)
        top_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # Set up the button grid
        grid = wx.GridSizer(1, 5, 0, 0)
        grid.Add(self._delete_unselected_chunks, 0, wx.LEFT, 1)
        grid.Add(self.lbl, 0, wx.RIGHT, -80)
        grid.Add(self.chk, 0, wx.TOP, 20)
        grid.Add(self._area_size_for_point, 0, wx.LEFT, -10)
        grid.Add(self.g_merge, 0, wx.LEFT, 0)

        side_sizer.Add(grid, 0, wx.EXPAND | wx.TOP | wx.LEFT, 0)

        mid_sizer.Add(self.g_save)
        mid_sizer.Add(self.g_load)
        mid_sizer.Add(self._run_button, 0, wx.LEFT, 30)
        mid_sizer.Add(self.gsel, 0, wx.LEFT, 20)

        # Add sizers to the main sizer
        self._sizer.Add(side_sizer, 0, wx.EXPAND)
        self._sizer.Add(mid_sizer, 0, wx.EXPAND | wx.TOP, 5)
        self._sizer.Add(top_sizer, 1, wx.EXPAND | wx.TOP | wx.LEFT, 50)

        self._sizer.Add(self._location_data, 1, wx.EXPAND | wx.ALL, 5)

        self._location_data.Fit()

    def _gsel(self, _):
        for box in self.canvas.selection.selection_group.selection_boxes:
            newl = ""
            if self._location_data.GetValue() != "":
                newl = "\n"
            print(str(box.min_z) + "," + str(box.min_y) + "," + str(box.min_z) + "," + str(box.max_x) + "," + str(
                box.max_y) + "," + str(box.max_z))
            self._location_data.SetValue(
                self._location_data.GetValue() + newl + str(box.min_x) + "," + str(box.min_y) + "," + str(
                    box.min_z) + "," + str(box.max_x) + "," + str(box.max_y) + "," + str(box.max_z))

    def _getc(self):
        print(str(self.canvas.selection.selection_group.selection_boxes).replace("(SelectionBox((", "").replace(")),)",
                                                                                                                "")
              .replace("(", "").replace(")", "").replace(" ", ""))
        newl = ""
        if self._location_data.GetValue() != "":
            newl = "\n"
        self._location_data.SetValue(
            self._location_data.GetValue() + newl + str(self.canvas.selection.selection_group.selection_boxes).replace(
                "(SelectionBox((", "").replace(")),)", "")
            .replace("(", "").replace(")", "").replace(" ", ""))

    def save_data(self, _):
        pathto = ""
        fname = ""
        fdlg = wx.FileDialog(self, "Export locations", "", "",
                             f"txt (*.txt)|*.*", wx.FD_SAVE)
        if fdlg.ShowModal() == wx.ID_OK:
            pathto = fdlg.GetPath()
        else:
            return False
        if ".txt" not in pathto:
            pathto = pathto + ".txt"
        with open(pathto, "w") as tfile:
            tfile.write(self._location_data.GetValue())
            tfile.close()

    def load_data(self, _):
        pathto = ""
        fdlg = wx.FileDialog(self, "Import Locations", "", "",
                             f"TXT x,y,z,x,y,z (*.txt)|*.*", wx.FD_OPEN)
        if fdlg.ShowModal() == wx.ID_OK:
            pathto = fdlg.GetPath()
        else:
            return False
        with open(pathto, "r") as tfile:
            self._location_data.SetValue(tfile.read())
            tfile.close()

    def merge(self, _):
        data = self._location_data.GetValue()
        prog = re.compile(r'([-+]?\d[\d+]*)(?:\.\d+)?', flags=0)
        result = prog.findall(data)
        lenofr = len(result)
        cnt = 0
        new_data = ''
        for i, x in enumerate(result):
            cnt += 1
            if cnt < 6:
                new_data += str(int(x)) + ", "
            else:
                new_data += str(int(x)) + '\n'
                cnt = 0
                lenofr -= 6
                if not lenofr > 5:
                    break
        sp = new_data[:-1]
        group = []
        for d in sp.split("\n"):
            x, y, z, xx, yy, zz = d.split(",")
            group.append(SelectionBox((int(x), int(y), int(z)), (int(xx), int(yy), int(zz))))
        sel = SelectionGroup(group)
        cleaner = sel.merge_boxes()
        cleaner_data = ''
        for data in cleaner:
            cleaner_data += f'{data.min[0]},{data.min[1]},{data.min[2]},{data.max[0]},{data.max[1]},{data.max[2]}\n'
        self._location_data.SetValue(cleaner_data[:-1])

    def move_chunks(self, _):
        pass

    def find_chunks(self, _):
        pass

    def delete_unselected(self, _):
        try:
            self.frame.Hide()
            self.frame.Close()
        except:
            pass
        self._gsel(_)
        self.merge(_)
        self._set_seletion()
        selected_chunks = self.canvas.selection.selection_group.chunk_locations()
        self.frame = wx.Frame(self.parent.Parent, id=wx.ID_ANY, pos=wx.DefaultPosition, size=(400, 700),
                              style=(wx.MINIMIZE_BOX | wx.MAXIMIZE_BOX | wx.RESIZE_BORDER |
                                     wx.SYSTEM_MENU | wx.CAPTION | wx.CLOSE_BOX | wx.CLIP_CHILDREN |
                                     wx.FRAME_FLOAT_ON_PARENT),
                              name="Panel",
                              title="CHUNKS")
        sizer_P = wx.BoxSizer(wx.VERTICAL)
        self.frame.SetSizer(sizer_P)
        self.textGrid = wx.TextCtrl(self.frame, style=wx.TE_MULTILINE | wx.TE_BESTWRAP, size=(400, 750))
        self.textGrid.SetValue("This is the list of Chunk That will be saved:\n" + str(selected_chunks))
        self.textGrid.SetFont(self.font)
        self.textGrid.SetForegroundColour((0, 255, 0))
        self.textGrid.SetBackgroundColour((0, 0, 0))
        sizer_P.Add(self.textGrid, 1, wx.EXPAND)

        self.frame.Show(True)
        result = wx.MessageBox(" Delete All other Chunks? ", "Question", style=wx.YES_NO | wx.STAY_ON_TOP | wx.CENTRE,
                               parent=self.frame, )
        if result == 2:
            all_chunks = self.world.all_chunk_coords(self.canvas.dimension)
            self.textGrid.AppendText("These Chunks were deleted:")
            for chunk in all_chunks:
                if chunk not in selected_chunks:
                    self.textGrid.AppendText(str(chunk))
                    self.canvas.world.level_wrapper.delete_chunk(chunk[0], chunk[1], self.canvas.dimension)
            self.world.save()
            self.world.purge()
            self.canvas.renderer.render_world.unload()
            self.canvas.renderer.render_world.enable()
            result = wx.MessageBox(" All These Chunks Deleted,  Close Chunk Window info list",
                                   "Information, Question", style=wx.YES_NO | wx.STAY_ON_TOP | wx.CENTRE,
                                   parent=self.Parent)
            if result == 2:
                self.frame.Hide()
                self.frame.Close()
        else:
            self.frame.Hide()
            self.frame.Close()

    def _set_seletion(self):
        data = self._location_data.GetValue()
        prog = re.compile(r'([-+]?\d[\d+]*)(?:\.\d+)?', flags=0)
        result = prog.findall(data)
        lenofr = len(result)
        cnt = 0
        new_data = ''
        group = []
        if not self.chk.GetValue():
            step = 6
        else:
            step = 3
        for i, x in enumerate(result):
            cnt += 1
            if cnt < step:
                new_data += str(int(x)) + ", "
            else:
                new_data += str(int(x)) + '\n'
                cnt = 0
                lenofr -= step
                if not lenofr > step-1:
                    break
        new_data = new_data[:-1]
        for d in new_data.split("\n"):


            if not self.chk.GetValue(): #len(d.split(",")) >= 6:
                x, y, z, xx, yy, zz = d.split(",")
            else:

                sx,sy,sz = map(int, self._area_size_for_point.GetValue().split(","))

                x, y, z = map(int, d.split(","))
                xx, yy, zz = x - sx, y - sy, z - sz
                x, y, z = x + sx, y + sy, z + sz
            group.append(SelectionBox((int(x), int(y), int(z)), (int(xx), int(yy), int(zz))))
        sel = SelectionGroup(group)
        cleaner = sel.merge_boxes()
        self.canvas.selection.set_selection_group(cleaner)

    def _run_operation(self, _):
        self._set_seletion()

class BlendingWindow(wx.Frame):
    def __init__(self, parent, canvas, world, *args, **kw):
        super(BlendingWindow, self).__init__(parent, *args, **kw,
                                             style=(wx.MINIMIZE_BOX | wx.MAXIMIZE_BOX | wx.RESIZE_BORDER |
                                                    wx.SYSTEM_MENU | wx.CAPTION | wx.CLOSE_BOX | wx.CLIP_CHILDREN |
                                                    wx.FRAME_FLOAT_ON_PARENT),
                                             name="Blending Panel", title="Force Blending")
        self.parent = parent
        self.world = world
        self.canvas = canvas

        # Setup font
        self.font2 = wx.Font(16, wx.FONTFAMILY_ROMAN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)

        # Create UI elements
        self.create_ui()

        # # Bind events
        self._run_button.Bind(wx.EVT_BUTTON, self._refresh_chunk)
        self.seed.Bind(wx.EVT_BUTTON, self.set_seed)

        self.SetSize((460, 500))
        self.Fit()
        self.Layout()
        self.Show(True)

    def create_ui(self):
        self.info_label = wx.StaticText(self, label="There is No Undo Make a backup!", size=(440, 20))
        self.info_label2 = wx.StaticText(self, label=self.get_info_text(), size=(440, 492))

        self.info_label.SetFont(self.font2)
        self.info_label.SetForegroundColour((255, 0, 0))
        self.info_label.SetBackgroundColour((0, 0, 0))

        self.info_label2.SetFont(self.font2)
        self.info_label2.SetForegroundColour((0, 200, 0))
        self.info_label2.SetBackgroundColour((0, 0, 0))

        self._all_chunks = wx.CheckBox(self, label="All Chunks")
        self._all_chunks.SetFont(self.font2)
        self._all_chunks.SetValue(True)

        self._recal_heightmap = wx.CheckBox(self,
                                            label="Recalculate Heightmap \n(only needed in overworld for pasted chunks or structures)")
        self._recal_heightmap.SetFont(self.font2)
        self._recal_heightmap.SetValue(False)

        self._run_button = wx.Button(self, label="Force Blending")
        self._run_button.SetFont(self.font2)

        self.seed = wx.Button(self, label="(Save new seed)")
        self.seed_input = wx.TextCtrl(self, style=wx.TE_LEFT, size=(220, 25))
        self.seed_input.SetFont(self.font2)
        self.seed_input.SetValue(self.get_initial_seed_value())

        # Layout
        self._sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self._sizer)
        side_sizer = wx.BoxSizer(wx.VERTICAL)
        self._sizer.Add(side_sizer)

        side_sizer.Add(self.info_label, 0, wx.LEFT, 11)
        side_sizer.Add(self.info_label2, 0, wx.LEFT, 11)
        side_sizer.Add(self._run_button, 0, wx.LEFT, 11)
        side_sizer.Add(self._all_chunks, 0, wx.LEFT, 11)
        side_sizer.Add(self._recal_heightmap, 0, wx.LEFT, 11)
        side_sizer.Add(self.seed_input, 0, wx.LEFT, 11)
        side_sizer.Add(self.seed, 0, wx.LEFT, 11)

    def get_info_text(self):
        return ("How It Works:\n"
                "The Overworld:\n "
                "Requires at least one chunk border of deleted chunks. Blending happens when existing terrain blends in with seed "
                "generated terrain. Water surrounds if below 62 and the cut off is 255.\n"
                "The Nether:  !Untested In Java\n"
                "You will want chunks to be around your builds. Not really blending, but it looks better than 16x16 flat walls.  "
                "The End:\n"
                "Has not been updated yet and does not appear to have any blending options as of yet.\n"
                "Blending does not require a seed change,\n"
                "A simple biome change, pasted in chunks, higher terrain blocks or structures (Recalculate Heightmap)\n"
                "Terrain blocks are also required for the overworld. It will blend from them, it won't blend from non-terrain type blocks"
                "\nManual Seed changes or algorithmic seed changes are what make old terrain not match up to existing chunks without blending.\n")

    def get_initial_seed_value(self):
        if self.world.level_wrapper.platform == "java":
            return str(self.world.level_wrapper.root_tag['Data']['WorldGenSettings']['seed'])
        else:
            return str(self.world.level_wrapper.root_tag['RandomSeed'])

    def set_seed(self, _):
        if self.world.level_wrapper.platform == "java":
            self.world.level_wrapper.root_tag['Data']['WorldGenSettings']['seed'] = LongTag(
                int(self.seed_input.GetValue()))
        else:
            self.world.level_wrapper.root_tag['RandomSeed'] = LongTag(int(self.seed_input.GetValue()))
        self.world.save()

    @property
    def level_db(self):
        level_wrapper = self.world.level_wrapper
        if hasattr(level_wrapper, "level_db"):
            return level_wrapper.level_db
        else:
            return level_wrapper._level_manager._db

    def _refresh_chunk(self, _):
        self.set_seed(_)
        self.world.save()
        self.start(_)
        self.world.purge()
        self.world.save()
        self.canvas.renderer.render_world._rebuild()
        wx.MessageBox("If you had no errors it worked. \n Close World and Open in Minecraft", "IMPORTANT",
                      wx.OK | wx.ICON_INFORMATION)

    def start(self, _):
        if self._all_chunks.GetValue():
            self.all_chunks = [x for x in self.world.level_wrapper.all_chunk_coords(self.canvas.dimension)]
        else:
            self.all_chunks = self.canvas.selection.selection_group.chunk_locations()

        total = len(self.all_chunks)
        count = 0
        location_dict = collections.defaultdict(list)
        self.progress = ProgressBar()
        if self.world.level_wrapper.platform == "java":

            self.process_java_chunks(location_dict, count, total)

        else:  # BEDROCK
            self.process_bedrock_chunks(count, total)

    def process_java_chunks(self, location_dict, count, total):

        for xx, zz in self.all_chunks:
            rx, rz = chunk_coords_to_region_coords(xx, zz)
            location_dict[(rx, rz)].append((xx, zz))

        for rx, rz in location_dict.keys():
            file_exists = exists(self.get_dim_vpath_java_dir(rx, rz))
            if file_exists:

                for cx, cz in location_dict[(rx, rz)]:
                    count += 1
                    self.progress.progress_bar(total, count, update_interval=1, title='Blending', text='Chunks')

                    self.raw_data = AnvilRegion(self.get_dim_vpath_java_dir(rx, rz))
                    if self.raw_data.has_chunk(cx % 32, cz % 32):
                        nbtdata = self.raw_data.get_chunk_data(cx % 32, cz % 32)

                        if nbtdata['sections']:
                            nbtdata['Heightmaps'] = CompoundTag({})
                            nbtdata['blending_data'] = CompoundTag(
                                {"old_noise": ByteTag(1)})
                            nbtdata['DataVersion'] = IntTag(2860)
                            self.raw_data.put_chunk_data(cx % 32, cz % 32, nbtdata)
                        self.raw_data.save()
                    self.raw_data.unload()


    def process_bedrock_chunks(self, count, total):
        for xx, zz in self.all_chunks:

            if ('minecraft:the_end' in self.canvas.dimension):
                wx.MessageBox(
                    "The End: This does not have any effect. Overworld works and the Nether does not have biome blending. It only rounds the chunk walls.",
                    "IMPORTANT", wx.OK | wx.ICON_INFORMATION)
                return

            if 'minecraft:the_nether' in self.canvas.dimension:
                count += 1
                self.progress.progress_bar(total, count, update_interval=1, title='Blending', text='Chunks')
                try:  # If Nether
                    self.level_db.put(self.get_dim_chunkkey(xx, zz) + b'v', b'\x07')
                except Exception as e:
                    print("A", e)
                try:
                    self.level_db.delete(self.get_dim_chunkkey(xx, zz) + b',')
                except Exception as e:
                    print("B", e)
            else:
                count += 1
                self.progress.progress_bar(total, count, update_interval=1, title='Blending', text='Chunks')
                try:
                    self.level_db.delete(self.get_dim_chunkkey(xx, zz) + b'@')
                except Exception as e:
                    print("C", e)
                if self._recal_heightmap.GetValue():
                    self.process_heightmap_update(count, total)


    def process_heightmap_update(self, count, total):
        lower_keys = {-1: 4, -2: 3, -3: 2, -4: 1}
        self.over_under_blending_limits = False
        for xx, zz in self.all_chunks:
            count += 1
            chunkkey = self.get_dim_chunkkey(xx, zz)
            self.height = numpy.frombuffer(numpy.zeros(512, 'b'), "<i2").reshape((16, 16))
            for k, v in self.world.level_wrapper.level_db.iterate(start=chunkkey + b'\x2f\x00',
                                                                  end=chunkkey + b'\x2f\xff\xff'):
                if len(k) > 8 < 10:
                    key = self.unsignedToSigned(k[-1], 1)
                    blocks, block_bits, extra_blk, extra_blk_bits = self.get_pallets_and_extra(v[3:])

                    for x in range(16):
                        for z in range(16):
                            for y in range(16):
                                if "minecraft:air" not in str(blocks[block_bits[x][y][z]]):
                                    if key > 0:
                                        if self.height[z][x] < (y + 1) + (key * 16) + 64:
                                            self.height[z][x] = (y + 1) + (key * 16) + 64
                                    elif key == 0:
                                        if self.height[z][x] < (y + 1) + 64:
                                            self.height[z][x] = (y + 1) + 64
                                    else:
                                        if self.height[z][x] < (y + 1) + (lower_keys[key] * 16) - 16:
                                            self.height[z][x] = (y + 1) + (lower_keys[key] * 16) - 16

            if (self.height.max() > 320) or (self.height.min() < 127):
                self.over_under_blending_limits = True

            height_biome_key = b'+'
            biome = self.level_db.get(chunkkey + height_biome_key)[512:]
            print(self.height)
            height = self.height.tobytes()

            self.level_db.put(chunkkey + height_biome_key, height + biome)

        if self.over_under_blending_limits:
            wx.MessageBox(
                "The Height has been updated. Complete some height issues were detected. If below y 62, water spawns around. 255 is the height limit for blending.",
                "IMPORTANT", wx.OK | wx.ICON_INFORMATION)
        else:
            wx.MessageBox("The Chunks Have Been Updated. No issues detected.",
                          "IMPORTANT", wx.OK | wx.ICON_INFORMATION)

    def get_dim_vpath_java_dir(self, regonx, regonz):
        file = f"r.{regonx}.{regonz}.mca"
        path = self.world.level_wrapper.path
        if 'minecraft:the_end' in self.canvas.dimension:
            dim = 'DIM1'
        elif 'minecraft:the_nether' in self.canvas.dimension:
            dim = 'DIM-1'
        elif 'minecraft:overworld' in self.canvas.dimension:
            dim = ''
        version = "region"
        full_path = os.path.join(path, dim, version, file)
        return full_path

    def get_pallets_and_extra(self, raw_sub_chunk):
        block_pal_dat, block_bits, bpv = self.get_blocks(raw_sub_chunk)
        if bpv < 1:
            pallet_size, pallet_data, off = 1, block_pal_dat, 0
        else:
            pallet_size, pallet_data, off = struct.unpack('<I', block_pal_dat[:4])[0], block_pal_dat[4:], 0
        blocks = []
        block_pnt_bits = block_bits
        extra_pnt_bits = None

        for x in range(pallet_size):
            nbt, p = load(pallet_data, little_endian=True, offset=True)
            pallet_data = pallet_data[p:]
            blocks.append(nbt.value)

        extra_blocks = []
        if pallet_data:
            block_pal_dat, extra_block_bits, bpv = self.get_blocks(pallet_data)
            if bpv < 1:
                pallet_size, pallet_data, off = 1, block_pal_dat, 0
            else:
                pallet_size, pallet_data, off = struct.unpack('<I', block_pal_dat[:4])[0], block_pal_dat[4:], 0
            extra_pnt_bits = extra_block_bits
            for aa in range(pallet_size):
                nbt, p = load(pallet_data, little_endian=True, offset=True)
                pallet_data = pallet_data[p:]
                extra_blocks.append(nbt.value)
        return blocks, block_pnt_bits, extra_blocks, extra_pnt_bits

    def get_blocks(self, raw_sub_chunk):
        bpv, rawdata = struct.unpack("b", raw_sub_chunk[0:1])[0] >> 1, raw_sub_chunk[1:]
        if bpv > 0:
            bpw = (32 // bpv)
            wc = -(-4096 // bpw)
            buffer = numpy.frombuffer(bytes(reversed(rawdata[:4 * wc])), dtype="uint8")
            unpack = numpy.unpackbits(buffer)
            unpack = unpack.reshape(-1, 32)[:, -bpw * bpv:]
            unpack = unpack.reshape(-1, bpv)[-4096:, :]
            unpacked = numpy.pad(unpack, [(0, 0), (16 - bpv, 0)], "constant")
            p_arr = numpy.packbits(unpacked).view(dtype=">i2")[::-1]
            block_bits = p_arr.reshape((16, 16, 16)).swapaxes(1, 2)
            rawdata = rawdata[wc * 4:]
        else:
            block_bits = numpy.zeros((16, 16, 16), dtype=numpy.int16)
        return rawdata, block_bits, bpv

    def get_dim_chunkkey(self, xx, zz):
        if 'minecraft:the_end' in self.canvas.dimension:
            return struct.pack('<iii', xx, zz, 2)
        elif 'minecraft:the_nether' in self.canvas.dimension:
            return struct.pack('<iii', xx, zz, 1)
        elif 'minecraft:overworld' in self.canvas.dimension:
            return struct.pack('<ii', xx, zz)
        return b''

    def unsignedToSigned(self, n, byte_count):
        return int.from_bytes(n.to_bytes(byte_count, 'little', signed=False), 'little', signed=True)

class CustomToolTip(wx.PopupWindow):
    def __init__(self, parent=None, btn=None, text=None, font_size=None):
        super().__init__(parent)  # Initialize wx.PopupWindow
        self.SetBackgroundColour(wx.Colour(255, 255, 225))  # Light yellow background
        self.parent = parent
        self.font_size = font_size
        self.text = text
        self._create_ui()

        # Bind event handlers
        btn.Bind(wx.EVT_ENTER_WINDOW, self.on_mouse_enter)
        btn.Bind(wx.EVT_LEAVE_WINDOW, self.on_mouse_leave)

    def _create_ui(self):
        sizer = wx.BoxSizer(wx.VERTICAL)

        label = wx.StaticText(self, label=self.text)
        font = label.GetFont()
        font.SetPointSize(self.font_size)
        label.SetFont(font)

        sizer.Add(label, 0, wx.ALL, 5)
        self.SetSizerAndFit(sizer)

    def Popup(self, pos):
        self.Position(pos, wx.Size(-1, -1))
        self.Show()
        self.Raise()

    def on_mouse_enter(self, event):
        btn = event.GetEventObject()
        pos = btn.ClientToScreen(wx.Point(btn.GetSize().GetWidth(), 0))
        self.Popup(pos)

    def on_mouse_leave(self, event):
        self.Hide()

class Tools(wx.Frame):
    def __init__(self, parent, world, canvas, *args, **kw):
        super(Tools, self).__init__(parent, *args, **kw,
                                    style=(wx.SYSTEM_MENU | wx.CAPTION | wx.CLOSE_BOX | wx.CLIP_CHILDREN |
                                           wx.FRAME_FLOAT_ON_PARENT),
                                    name="Blending Panel", title="Tools For Amulet")
        self.parent = parent
        self.world = world
        self.canvas = canvas

        # Main vertical sizer
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self.sizer)

        # Grid sizer with 2 columns for layout
        self._top_horz_sizer = wx.GridSizer(cols=2, hgap=5, vgap=5)
        self.sizer.Add(self._top_horz_sizer, 1, wx.EXPAND | wx.ALL, 5)

        self.SetMinSize((80, 80))

        self.font = wx.Font(15, wx.FONTFAMILY_ROMAN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        self.SetFont(self.font)
        self.SetForegroundColour((0, 255, 0))
        self.SetBackgroundColour((0, 0, 0))

        self.create_buttons()
        self.bind_buttons()
        self.layout_ui()

        self.Fit()
        self.Layout()
        self.Show(True)

    def create_buttons(self):
        _size = (170, 50)
        self._position = wx.Button(self, label='Selection \nPosition Tool', size=_size)
        self._force_blending = wx.Button(self, label='Force \nBlending Tool', size=_size)
        self._chunk_data = wx.Button(self, label='Chunk Tool', size=_size)
        self._selection_org = wx.Button(self, label='Selection \nOrganizer Tool', size=_size)
        self._buffer_world = wx.Button(self, label='Buffer World\n Tool', size=_size)
        self._finder_replacer = wx.Button(self, label='Finder Replacer', size=_size)
        self._set_player_data = wx.Button(self, label='Set Player Data', size=_size)
        self._hard_coded_spawn = wx.Button(self, label='Hard Coded \n Spawn Tool', size=_size)
        self._portals_and_border_walls = wx.Button(self, label='Del Portals, Items\n Border Walls', size=_size)
        self._player_inventory = wx.Button(self, label='NBT Editor\n For Inventory ', size=_size)
        self._entities_data = wx.Button(self, label='NBT Editor \n For Entities', size=_size)
        self._material_counter = wx.Button(self, label='Material Counter', size=_size)
        self._shape_painter = wx.Button(self, label='Shape Painter', size=_size)
        self._random_filler = wx.Button(self, label='Random Filler', size=_size)
        self._set_frames = wx.Button(self, label='Image Or Maps \n To Frames', size=_size)
        self._reset_vaults = wx.Button(self, label='Reset Vaults', size=_size)
        self._remap_villager_workstations = wx.Button(self, label='Remap Villager\n Workstations', size=_size)
        self._inventory_editor = wx.Button(self, label='Inventory Editor', size=_size)

    def bind_buttons(self):
        color_back, color_front = (0, 0, 0), (0, 255, 0)
        self._position.Bind(wx.EVT_BUTTON, self.position)
        self._force_blending.Bind(wx.EVT_BUTTON, self.force_blending)
        self._chunk_data.Bind(wx.EVT_BUTTON, self.chunk_data)
        self._selection_org.Bind(wx.EVT_BUTTON, self.selection_org)
        self._buffer_world.Bind(wx.EVT_BUTTON, self.buffer_world)
        self._hard_coded_spawn.Bind(wx.EVT_BUTTON, self.hard_coded_spawn)
        self._set_player_data.Bind(wx.EVT_BUTTON, self.set_player_data)
        self._finder_replacer.Bind(wx.EVT_BUTTON, self.finder_replacer)
        self._portals_and_border_walls.Bind(wx.EVT_BUTTON, self.protals_and_border_walls)  ## _player_inventory
        self._player_inventory.Bind(wx.EVT_BUTTON, self.player_inventory)
        self._entities_data.Bind(wx.EVT_BUTTON, self.entites_data)
        self._material_counter.Bind(wx.EVT_BUTTON, self.material_counter)
        self._shape_painter.Bind(wx.EVT_BUTTON, self.shape_painter)
        self._random_filler.Bind(wx.EVT_BUTTON, self.random_filler)
        self._set_frames.Bind(wx.EVT_BUTTON, self.set_frames)
        self._reset_vaults.Bind(wx.EVT_BUTTON, self.reset_vaults)
        self._remap_villager_workstations.Bind(wx.EVT_BUTTON, self.remap_villager_workstations)
        self._inventory_editor.Bind(wx.EVT_BUTTON, self.inventory_editor)
        CustomToolTip(self, self._position,
                      text="Tool for positioning all selections.\n"
                           "You can stretch and move all selections.\n"
                           "Create different patterns, like areas to fill in for stairs.",
                      font_size=14)

        CustomToolTip(self, self._force_blending,
                      text="This tool allows you to change the seed\n"
                           "and force blending of newly generated chunks.\n"
                           "Works well after using the Selection Organizer tool\n"
                           "after deleting unselected areas.",
                      font_size=14)

        CustomToolTip(self, self._chunk_data,
                      text="Tool for saving and loading chunks.\n"
                           "Easily save, load, copy, and move your chunks around.\n"
                           "Note: The Move button in this tool moves all loaded chunks.\n"
                           "You can also load only the sub-layers you need.",
                      font_size=14)

        CustomToolTip(self, self._selection_org,
                      text="Tool for saving your selection locations.\n"
                           "Also provides the ability to quickly delete all other chunks.",
                      font_size=14)

        CustomToolTip(self, self._buffer_world,
                      text="Allows you to create a empty world to speed up loading in amulet.\n"
                           "You can also make an existing world pull from\n"
                           "the same version and platform, mirroring the same location.",
                      font_size=14)

        CustomToolTip(self, self._hard_coded_spawn,
                      text="Set or delete hardcoded spawns, and view their\n"
                           "bounding box locations. Note: you cannot make fortress\n"
                           "spawns happen in the overworld.",
                      font_size=14)

        CustomToolTip(self, self._set_player_data,
                      text="Set player position, recover achievements, or re-enable\n"
                           "hardcore mode for Java worlds.",
                      font_size=14)

        CustomToolTip(self, self._finder_replacer,
                      text="The latest Finder Replacer now has a fast apply feature.\n"
                           "Directly use the find and replace text boxes.\n"
                           "Use the Helper tool to speed up block listing.",
                      font_size=14)

        CustomToolTip(self, self._portals_and_border_walls,
                      text="Delete all portals and/or border walls. and delete all items from item containers\n"
                           "More features will be added soon.",
                      font_size=14)

        CustomToolTip(self, self._player_inventory,
                      text="Edit server or local player inventory and settings.",
                      font_size=14)

        CustomToolTip(self, self._entities_data,
                      text="Edit, move, and copy mobs. Some features need updating.",
                      font_size=14)

        CustomToolTip(self, self._material_counter,
                      text="Get a list of blocks used within a selection.",
                      font_size=14)

        CustomToolTip(self, self._shape_painter,
                      text="An attempt at creating a brush tool. Still needs work.",
                      font_size=14)

        CustomToolTip(self, self._random_filler,
                      text="Fill a selection area with random blocks.\n"
                           "You can also replace only specific blocks with random ones.",
                      font_size=14)

        CustomToolTip(self, self._set_frames,
                      text="Easily place images or build a map wall on\n"
                           "glow item frames or normal item frames.",
                      font_size=14)

        CustomToolTip(self, self._reset_vaults,
                      text="Removes the rewarded players data, so vaults can be reused",
                      font_size=14)

        CustomToolTip(self, self._remap_villager_workstations,
                      text = "This will rebuild villager data, fixing the iron farm and restocking. \n"
                             "It also adds a fast way to manage trades, including unlimited trades,\n"
                             " lowering costs, adding all enchantments, etc.",font_size=14)

        CustomToolTip(self, self._inventory_editor,
                      "Inventory Editor only supports the latest version.\n"
                      "Features a simple UI with support for editing armor trims, fireworks, enchants, and more.\n"
                      "Left-click menu for block selection, with filtering for large menus.\n"
                      "Large menus may take a few seconds to load initially but are fast afterward.\n"
                      "Edit Bundles, Chests, Shulker Boxes, Barrels, and the Ender Chest Inventory with unlimited nesting.\n"
                      "Right-click menu allows copy and paste, and access to the editor for supported editable items.",
                      font_size=14)

        self._position.SetForegroundColour(color_front)
        self._position.SetBackgroundColour(color_back)

        self._force_blending.SetForegroundColour(color_front)
        self._force_blending.SetBackgroundColour(color_back)

        self._chunk_data.SetForegroundColour(color_front)
        self._chunk_data.SetBackgroundColour(color_back)

        self._selection_org.SetForegroundColour(color_front)
        self._selection_org.SetBackgroundColour(color_back)

        self._buffer_world.SetForegroundColour(color_front)
        self._buffer_world.SetBackgroundColour(color_back)

        self._set_player_data.SetForegroundColour(color_front)
        self._set_player_data.SetBackgroundColour(color_back)

        self._hard_coded_spawn.SetForegroundColour(color_front)
        self._hard_coded_spawn.SetBackgroundColour(color_back)

        self._position.SetForegroundColour(color_front)
        self._position.SetBackgroundColour(color_back)

        self._finder_replacer.SetForegroundColour(color_front)
        self._finder_replacer.SetBackgroundColour(color_back)

        self._portals_and_border_walls.SetForegroundColour(color_front)
        self._portals_and_border_walls.SetBackgroundColour(color_back)

        self._player_inventory.SetForegroundColour(color_front)
        self._player_inventory.SetBackgroundColour(color_back)

        self._entities_data.SetForegroundColour(color_front)
        self._entities_data.SetBackgroundColour(color_back)

        self._material_counter.SetForegroundColour(color_front)
        self._material_counter.SetBackgroundColour(color_back)

        self._shape_painter.SetForegroundColour(color_front)
        self._shape_painter.SetBackgroundColour(color_back)

        self._random_filler.SetForegroundColour(color_front)
        self._random_filler.SetBackgroundColour(color_back)

        self._set_frames.SetForegroundColour(color_front)
        self._set_frames.SetBackgroundColour(color_back)

        self._reset_vaults.SetForegroundColour(color_front)
        self._reset_vaults.SetBackgroundColour(color_back)

        self._remap_villager_workstations.SetForegroundColour(color_front)
        self._remap_villager_workstations.SetBackgroundColour(color_back)

        self._inventory_editor.SetForegroundColour(color_front)
        self._inventory_editor.SetBackgroundColour(color_back)

    def layout_ui(self):
        _left_size = 5
        self._top_horz_sizer.Add(self._position, 0, wx.LEFT, _left_size)
        self._top_horz_sizer.Add(self._force_blending, 0, wx.LEFT, _left_size)
        self._top_horz_sizer.Add(self._chunk_data, 0, wx.LEFT, _left_size)
        self._top_horz_sizer.Add(self._selection_org, 0, wx.LEFT, _left_size)
        self._top_horz_sizer.Add(self._buffer_world, 0, wx.LEFT, _left_size)
        self._top_horz_sizer.Add(self._finder_replacer, 0, wx.LEFT, _left_size)
        self._top_horz_sizer.Add(self._set_player_data, 0, wx.LEFT, _left_size)
        self._top_horz_sizer.Add(self._hard_coded_spawn, 0, wx.LEFT, _left_size)
        self._top_horz_sizer.Add(self._portals_and_border_walls, 0, wx.LEFT, _left_size)
        self._top_horz_sizer.Add(self._player_inventory, 0, wx.LEFT, _left_size)
        self._top_horz_sizer.Add(self._entities_data, 0, wx.LEFT, _left_size)
        self._top_horz_sizer.Add(self._material_counter, 0, wx.LEFT, _left_size)
        self._top_horz_sizer.Add(self._shape_painter, 0, wx.LEFT, _left_size)
        self._top_horz_sizer.Add(self._random_filler, 0, wx.LEFT, _left_size)
        self._top_horz_sizer.Add(self._set_frames, 0, wx.LEFT, _left_size)
        self._top_horz_sizer.Add(self._reset_vaults, 0, wx.LEFT, _left_size)
        if self.world.level_wrapper.platform in "java":
            self._remap_villager_workstations.Hide()
            self._inventory_editor.Hide()
        else:
            self._top_horz_sizer.Add(self._remap_villager_workstations, 0, wx.LEFT, _left_size)
            self._top_horz_sizer.Add(self._inventory_editor, 0, wx.LEFT, _left_size)

        self._top_horz_sizer.Fit(self)
        self._top_horz_sizer.Layout()

    def set_frames(self, _):
        setframes = SetFrames(self.parent, self.canvas, self.world)
        setframes.Show()

    def position(self, _):
        position_ = PositionSelection(self.parent, self.canvas, self.world)
        position_.Show()

    def force_blending(self, _):
        self.blening_window = BlendingWindow(self.parent, self.canvas, self.world)
        self.blening_window.Show()

    def chunk_data(self, _):
        self.chunk_save_load = ChunkSaveAndLoad(self.parent, self.canvas, self.world)
        self.chunk_save_load.Show()

    def selection_org(self, _):
        self.selection_organizer = SelectionOrganizer(self.parent, self.world, self.canvas)
        self.selection_organizer.Show()

    def buffer_world(self, _):
        self.buffer_world = BufferWorldTool(self.parent, self.canvas, self.world)
        self.buffer_world.Show()

    def hard_coded_spawn(self, _):
        self.hard_spawn = HardCodedSpawns(self.parent, self.canvas, self.world)
        self.hard_spawn.Show()

    def finder_replacer(self, _):
        self.finderreplacer = FinderReplacer(self.parent, self.canvas, self.world)
        self.finderreplacer.Show()

    def protals_and_border_walls(self, _):
        portal = "portals"
        theKey = portal.encode("utf-8")

        delete_portals = wx.MessageBox("You are going to deleted all Portal Data \n ",
                                       "This can't be undone Are you Sure?", wx.YES_NO | wx.ICON_INFORMATION)

        if delete_portals == 2:
            self.world.level_wrapper.level_db.delete(theKey)
            wx.MessageBox("Done",
                          "All Portal date Should be gone", wx.OK | wx.ICON_INFORMATION)
        delete_borders = wx.MessageBox("You are going to deleted all the border walls?",
                                       "This can't be undone Are you Sure?", wx.YES_NO | wx.ICON_INFORMATION)

        if delete_borders == 2:

            for k, v in self.world.level_wrapper.level_db.iterate(
                    start=b'\x00', end=b'\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff'):
                if k[-1] == 0x38 and 9 <= len(k) <= 13:
                    self.world.level_wrapper.level_db.delete(k)
            wx.MessageBox("Done",
                          "Border Walls Should all be gone", wx.OK | wx.ICON_INFORMATION)
        delete_chest_data = wx.MessageBox("You are going to deleted all items in all chests? Note \n"
                                    "this will avoid items in hoppers that are 41 <= 60 and the other slots have  1 \n"
                                     "and Dispenser with one item ",
                                       "This can't be undone Are you Sure?", wx.YES_NO | wx.ICON_INFORMATION)

        if delete_chest_data == 2:
            updated_nbt_data = {}
            for k, v in self.world.level_wrapper.level_db.iterate(
                    start=b'\x00', end=b'\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff'):
                if k[-1] == 0x31 and 9 <= len(k) <= 13:
                    nbt =  unpack_nbt_list(v)#load(v, compressed=False, little_endian=True, string_decoder=utf8_escape_decoder)
                    for x in nbt:
                        if x.get('Items'):
                            items = x.get('Items')
                            if x.get('id') == 'Hopper':

                                if (41 <= items[0]['Count'] <= 60 and
                                        all(item['Count'] == 1 for item in items[1:5])):
                                    continue
                                else:
                                    x['Items'] = ListTag([])
                            elif x.get('id') == 'Dispenser':
                                if (items[0]['Count']== 1 and 'bucket' in items[0]['Name'].py_str):
                                    continue
                                else:
                                    x['Items'] = ListTag([])
                            else:
                                x['Items'] = ListTag([])

                    new_nbt = pack_nbt_list(nbt)
                    if new_nbt != nbt:
                        updated_nbt_data[k] = new_nbt
            for k,v in updated_nbt_data.items():
                self.world.level_wrapper.level_db.put(k,v)

            wx.MessageBox("Done",
                          "Border Walls Should all be gone", wx.OK | wx.ICON_INFORMATION)

    def set_player_data(self, _):
        self.set_player = SetPlayersData(self.parent, self.canvas, self.world)
        self.set_player.Show()

    def player_inventory(self, _):
        self.playerinventoy = Inventory(self.parent, self.canvas, self.world)
        self.playerinventoy.Show()

    def entites_data(self, _):
        self.entitesdata = EntitiePlugin(self.parent, self.canvas, self.world)
        self.entitesdata.Show()

    def material_counter(self, _):
        self.materialcounter = MaterialCounter(self.parent, self.canvas, self.world)
        self.materialcounter.Show()

    def shape_painter(self, _):
        self.shapepainter = ShapePainter(self.parent, self.canvas, self.world)
        self.shapepainter.Show()

    def random_filler(self, _):
        self.randomfiller = RandomFiller(self.parent, self.canvas, self.world)
        self.randomfiller.Show()

    def reset_vaults(self, _):
        self.resetvaults = ResetVaults(self.parent, self.canvas, self.world)
        self.resetvaults.reset_vaults()

    def remap_villager_workstations(self, _):
        self.remapvillagerstations = RemapVillagers(self.parent, self.canvas, self.world)
        self.remapvillagerstations.Show()

    def inventory_editor(self, _):

        self.inventoryeditor = InventoryEditorList(self.parent, self.canvas, self.world)
        self.inventoryeditor.Show()

class MultiTools(wx.Panel, DefaultOperationUI):

    def __init__(
            self,
            parent: wx.Window,
            canvas: "EditCanvas",
            world: "BaseLevel",
            options_path: str,
    ):

        wx.Panel.__init__(self, parent)
        DefaultOperationUI.__init__(self, parent, canvas, world, options_path)

        self.version = 8
        self.remote_version = self.get_top_of_remote_file(
            r'https://raw.githubusercontent.com/PREMIEREHELL/Amulet-Plugins/main/Multi_Plugins.py')

        if self.remote_version > self.version and self.remote_version is not None:

            self.download_latest_script()

            event = [x for x in parent.GetChildren() if isinstance(x, wx.BitmapButton)][1]
            custom_event = wx.CommandEvent(wx.wxEVT_COMMAND_BUTTON_CLICKED, event.GetId())
            custom_event.SetEventObject(event)
            event.GetEventHandler().ProcessEvent(custom_event)
        else:
            self.is_file_recent()
            self.Freeze()
            self._is_enabled = True
            self._moving = True
            self._sizer = wx.BoxSizer(wx.VERTICAL)
            self.SetSizer(self._sizer)
            self.font = wx.Font(33, wx.FONTFAMILY_ROMAN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
            self._window_button = wx.Button(self, label=f"Multi \n Tools \n V: {self.version} ", size=(270, 240))
            self._window_button.SetFont(self.font)
            self._window_button.Bind(wx.EVT_BUTTON, self._window_tools)
            self._sizer.Add(self._window_button)
            self.Layout()
            self.Thaw()
            tools = Tools(self.parent, self.world, self.canvas)
            tools.Show()


    def download_latest_script(self):
        try:
            url = r'https://raw.githubusercontent.com/PREMIEREHELL/Amulet-Plugins/main/Multi_Plugins.py'
            response = urllib.request.urlopen(url)
            if response.status == 200:
                with open(self.get_script_path(), 'w', encoding='utf-8') as file:
                    file.write(response.read().decode('utf-8'))
            else:
                print('Could not get a response to auto apply, please visit the repo.')
        except Exception as e:
            print(f"Error downloading the latest script: {e}")
    def download_latest_json(self):
        try:
            url = r'https://raw.githubusercontent.com/PREMIEREHELL/Amulet-Plugins/main/item_atlas.json'
            response = urllib.request.urlopen(url)
            if response.status == 200:
                with open(self.get_script_path_for_json(), 'w', encoding='utf-8') as file:
                    file.write(response.read().decode('utf-8'))
            else:
                print('Could not get a response to auto apply, please visit the repo.')
        except Exception as e:
            print(f"Error downloading the latest script: {e}")

    def get_script_path(self):
        return os.path.abspath(__file__)
    def get_script_path_for_json(self):
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'item_atlas.json')

    def get_top_of_remote_file(self, url, num_bytes=100):
        try:
            req = urllib.request.Request(url)
            req.add_header('Range', f'bytes=0-{num_bytes - 1}')
            response = urllib.request.urlopen(req)

            if response.status == 206:  # HTTP 206 Partial Content
                raw = response.read().decode('utf-8').split('#')
                version = raw[1].split('v')
                return int(version[0])
            elif response.status == 200:
                return response.read().decode('utf-8')
            else:
                print(f"Error: {response.status} could not check for update")
                return None
        except Exception as e:
            print(f"Error fetching remote file: {e}")
            return None

    def bind_events(self):
        super().bind_events()
        self._selection.bind_events()
        self._selection.enable()

    def enable(self):
        self._selection = BlockSelectionBehaviour(self.canvas)
        self._selection.enable()

    def _window_tools(self, _):
        if self.version == self.remote_version:
            tools = Tools(self.parent, self.world, self.canvas)
            tools.Show()

    def is_file_recent(self,  age_limit=25):
        file_path = self.get_script_path()
        if os.path.exists(file_path):
            current_time = time.time()
            file_mod_time = os.path.getmtime(file_path)
            file_age = current_time - file_mod_time
            if file_age < age_limit:
                self.download_latest_json()
                wx.MessageBox(f"A new version has been apply was v 7 now version 8"
                           f" {self.remote_version}\n"
                              f"V: 3 and 4\n"
                              f"The update has been automatically applyed:\n"
                              f"Fixed issue with force blending on Bedrock,\n"
                              f"Added message to select player for Set Player Data,\n"
                              f"Added New button to Reset Vaults in Java and Bedrock.\n"
                              f"v:5 Fixed Java Force Blending Tool\n"
                              f"v:6 Added missing imports for NBT Editor For Inventory\n"
                              f"v:7 dded Feature Villager Tool For bedrock , fixed iron farns, \n"
                              f"v:7 Added Simple Inventory Editor For Bedrock  Tool, \n"
                              f"auto repostion to workstation, edited trades \n "
                              f"Added Feature to Chunktool to exclude the biome , may need more work\n "
                              f"Added Feature to Selection organizer to work with only one point and set the range"
                              f"Fixed Bedrock height maps for blending tool\n"
                              f"Added enable disable hardcore button in Set player data for bedrock\n"
                              f"________________List of recent changes___________________________\n"
                              f"v:8 Added Drag and drop to Inventory Editor and some bug fixes\n",
                              f"v:8 Added Banner tools ad updated fierwork editor\n",
                              "The Plugin has Been Updated", wx.OK | wx.ICON_INFORMATION)


export = dict(name="# Multi TOOLS", operation=MultiTools)  # By PremiereHell