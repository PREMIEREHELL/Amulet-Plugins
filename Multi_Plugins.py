# 6 v
import urllib.request
import collections
import time
import copy
import zlib
import struct
import pickle
import uuid
import re
import wx
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

nbt_resources = image.nbt
from collections.abc import MutableMapping, MutableSequence
import abc
from amulet_nbt import *

import os
from os.path import exists
#import requests
from amulet_map_editor.api.wx.ui.block_select.properties import (
    PropertySelect,
    WildcardSNBTType,
    EVT_PROPERTIES_CHANGE,
)
from amulet_map_editor.programs.edit.api.events import (
    EVT_SELECTION_CHANGE,
)

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
        for ik in list(chunk_dict.keys()):
            # print(ik, dim)
            if len(ik) == 10:
                new_dict[new_key + ik[8:]] = chunk_dict.pop(ik)

            elif 14 <= len(ik) <= 15:

                new_dict[new_key][new_key + dim + ik[12:]] = chunk_dict.pop(ik)

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

        selection_values = list(self.chunks_mg.selection.values())
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
        self._include = wx.GridSizer(1, 2, 1, 2)
        self.include_blocks = wx.CheckBox(self, label="Include Blocks")
        self.include_blocks.SetValue(True)
        self.include_entities = wx.CheckBox(self, label="Include Entities")
        self.include_entities.SetValue(True)
        self._include.Add(self.include_blocks)
        self._include.Add(self.include_entities)
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

        EntitiePlugin.update_player_data(self, self.raw_nbt)
        # print("UPDATE",self.raw_nbt)

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
                # else:
                #     index = 0
                #     nname, ddata = "", tree.GetItemData(sibl)
                #     if ddata == ListTag:
                #         print("????", nname)
                #         index = 0
                #         item_num = tree.GetChildrenCount(sibl, recursively=False)
                #         f_child, f_c = tree.GetFirstChild(sibl)
                #         f_item = tree.GetFocusedItem()
                #         f_par = tree.GetItemParent(f_item)
                #         for xx in range(len(nbt_path_keys)):
                #             f_par = tree.GetItemParent(f_par)
                #         print(len(nbt_path_keys), "KKKKKKK")
                #         for c in range(item_num):
                #             if f_child == f_par:
                #                 index = c
                #                 nbt_path_keys.append(index)
                #
                #             f_child, f_c = tree.GetNextChild(f_child, f_c)
                #
                #         print(index, "DEX")
                # print(type(ddata),"DtN", ddata)
                # nbt_path_keys.append(index)

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
                for k, v in selected_items():
                    tsappend(CompoundTag({k: v}).to_snbt(5))
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
                path_to = self.world.level_wrapper.path + "/playerdata/" + s_player + ".dat"
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
                path_to = self.world.level_wrapper.path + "/playerdata/" + s_player + ".dat"
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
                path_to = self.world.level_wrapper.path + "/playerdata/" + s_player + ".dat"
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
                path_to = self.world.level_wrapper.path + "/playerdata/" + s_player + ".dat"
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
        self.SetSize(500, 160)

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
        self.all_chunks = wx.RadioButton(panel, label='All Chunks .snbt list')
        self.nbt_file_option = wx.RadioButton(panel, label='NBT Structure File')
        static_box_sizer.Add(self.selected_chunks)
        static_box_sizer.Add(self.all_chunks)
        static_box_sizer.Add(self.nbt_file_option)
        panel.SetSizer(static_box_sizer)
        hor_box = wx.BoxSizer(wx.HORIZONTAL)
        self.okButton = wx.Button(self)
        self.selected_chunks.Bind(wx.EVT_RADIOBUTTON, self.setbuttonEL)
        self.all_chunks.Bind(wx.EVT_RADIOBUTTON, self.setbuttonEL)
        self.nbt_file_option.Bind(wx.EVT_RADIOBUTTON, self.setbuttonEL)
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
        self.Destroy()


class BedRock(wx.Panel):
    def __int__(self, world, canvas):
        wx.Panel.__init__(self, parent)
        self.world = world
        self.canvas = canvas
        self.actors = collections.defaultdict(list)
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
            if self.digp.get(key) != None:
                for x in self.digp.get(key):
                    if self.actors.get(x) != None:

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
            print("Exporting")
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

    def _exp_entitie_data(self, _):
        dlg = ExportImportCostomDialog(None)
        dlg.InitUI(1)
        res = dlg.ShowModal()
        if dlg.selected_chunks.GetValue():
            select_chunks = self.canvas.selection.selection_group.chunk_locations()
        elif dlg.all_chunks.GetValue():
            select_chunks = [x for x in self.world.level_wrapper.all_chunk_coords(self.canvas.dimension)]
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
                if responce == True:
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
        entities = amulet_TAG_List()
        blocks = amulet_TAG_List()
        palette = amulet_TAG_List()
        DataVersion = amulet_TAG_Int(2975)
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
                    blocks_pos = amulet_TAG_Compound({'pos': amulet_TAG_List(
                        [IntTag(b[0]), IntTag(b[1]),
                         IntTag(b[2])]), 'state': IntTag(state)})
                    blocks.append(blocks_pos)
                else:
                    blocks_pos = CompoundTag({'nbt': from_snbt(blockEntity.to_snbt()),
                                              'pos': ListTag(
                                                  [IntTag(b[0]),
                                                   IntTag(b[1]),
                                                   IntTag(b[2])]),
                                              'state': amulet_TAG_Int(state)})
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
            if True:
                reps = EntitiePlugin.con_boc(self, "Air Blocks", 'Do you want to encude air block?')
                for x in nbt_.get('blocks'):
                    if x['palette'][int(x.get('state'))].get('Properties') != None:
                        palette.append(
                            dict(amulet_from_snbt(nbt['palette'][int(x.get('state'))]['Properties'].to_snbt())))
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
                            x['nbt']['Pos'] = amulet_TAG_List([amulet_TAG_Float(float(nxx + xx)),
                                                               amulet_TAG_Float(float(nyy + yy)),
                                                               amulet_TAG_Float(float(nzz + zz))])
                        if 'Double' in str(type(nxx)):
                            x['nbt']['Pos'] = amulet_TAG_List([amulet_TAG_Double(float(nxx + xx)),
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

        entities = amulet_TAG_List()
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
                        nbt_data = amulet_load(actor, compressed=False, little_endian=True)

                        # print(nbt_data)
                        pos = nbt_data.get("Pos")
                        x, y, z = math.floor(pos[0]), math.floor(pos[1]), math.floor(pos[2])

                        if (x, y, z) in selection:
                            nbt_entitie = amulet_TAG_List()
                            new_pos = mapdic[(x, y, z)]
                            nbt_pos = amulet_TAG_List(
                                [amulet_TAG_Float(sum([new_pos[0],
                                                       math.modf(abs(nbt_data.get("Pos")[0].value))[0]])),
                                 amulet_TAG_Float(sum([new_pos[1],
                                                       math.modf(abs(nbt_data.get("Pos")[1].value))[0]])),
                                 amulet_TAG_Float(sum([new_pos[2],
                                                       math.modf(abs(nbt_data.get("Pos")[2].value))[0]]))])

                            nbt_block_pos = amulet_TAG_List([amulet_TAG_Int(new_pos[0]),
                                                             amulet_TAG_Int(new_pos[1]),
                                                             amulet_TAG_Int(new_pos[2])])
                            # nbt_data.pop('internalComponents')
                            # nbt_data.pop('UniqueID')
                            nbt_nbt = amulet_from_snbt(nbt_data.to_snbt())
                            main_entry = amulet_TAG_Compound()
                            main_entry['nbt'] = nbt_nbt
                            main_entry['blockPos'] = nbt_block_pos
                            main_entry['pos'] = nbt_pos
                            entities.append(main_entry)
                return entities

            elif self.world.level_wrapper.version < (1, 18, 30, 4, 0):

                entitie = amulet_TAG_List()
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
                                nbt_pos = amulet_TAG_List(
                                    [amulet_TAG_Float(sum([new_pos[0],
                                                           math.modf(abs(nbt_data.get("Pos")[0].value))[0]])),
                                     amulet_TAG_Float(sum([new_pos[1],
                                                           math.modf(abs(nbt_data.get("Pos")[1].value))[0]])),
                                     amulet_TAG_Float(sum([new_pos[2],
                                                           math.modf(abs(nbt_data.get("Pos")[2].value))[0]]))])
                                nbt_block_pos = amulet_TAG_List([amulet_TAG_Int(new_pos[0]),
                                                                 amulet_TAG_Int(new_pos[1]),
                                                                 amulet_TAG_Int(new_pos[2])])
                                # nbt_data.pop('internalComponents')
                                # nbt_data.pop('UniqueID')
                                nbt_nbt_ = amulet_from_snbt(nbt_data.to_snbt())
                                main_entry = amulet_TAG_Compound()
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
                        chunk[b'2'] += amulet_NBTFile(x).save_to(little_endian=True, compressed=False)
                    except:
                        chunk[b'2'] = amulet_NBTFile(x).save_to(little_endian=True, compressed=False)
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
                    cx, cz = block_coords_to_chunk_coords(nbt_from_sget('Pos')[0], nbt_from_sget('Pos')[2])
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
                    cx, cz = block_coords_to_chunk_coords(nbt_from_sget('Pos')[0], nbt_from_sget('Pos')[2])
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
        location = ListTag([FloatTag(float(x) - xx), FloatTag(float(y) - yy), FloatTag(float(z) - zz)])

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
            nbt_ = amulet_NBTFile()
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
                    setdata['UUID'] = amulet_TAG_Int_Array(
                        [amulet_TAG_Int(q), amulet_TAG_Int(w), amulet_TAG_Int(e),
                         amulet_TAG_Int(r)])
                if self.world.level_wrapper.version >= 2730:
                    nbt_reg['Entities'].append(setdata)
                else:
                    nbt_reg['Level']['Entities'].append(setdata)
                self.Entities_region.put_chunk_data(cx % 32, cz % 32, nbt_reg)
                self.Entities_region.save()
            else:
                if self.world.level_wrapper.version >= 2730:
                    new_data = amulet_NBTFile()
                    new_data['Position'] = amulet_from_snbt(f'[I; {cx}, {cz}]')
                    new_data['DataVersion'] = amulet_TAG_Int(self.world.level_wrapper.version)
                    new_data['Entities'] = amulet_TAG_List()
                    new_data['Entities'].append(setdata)
                    self.Entities_region.put_chunk_data(cx % 32, cz % 32, new_data)
                    self.Entities_region.save()
                else:
                    print("java version would leave hole in world , file")
        else:
            if self.world.level_wrapper.version >= 2730:
                self.Entities_region = AnvilRegion(self.get_dim_vpath_java_dir(rx, rz), create=True)
                new_data = amulet_NBTFile()
                new_data['Position'] = amulet_from_snbt(f'[I; {cx}, {cz}]')
                new_data['DataVersion'] = amulet_TAG_Int(self.world.level_wrapper.version)
                new_data['Entities'] = amulet_TAG_List()
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
                add = amulet_TAG_List()
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
                nbt_ = amulet_from_snbt(line)
                x, y, z = nbt_.get('Pos').value
                uu_id = uuid.uuid4()
                q, w, e, r = struct.unpack('>iiii', uu_id.bytes)
                nbt_['UUID'] = amulet_TAG_Int_Array(
                    [amulet_TAG_Int(q), amulet_TAG_Int(w), amulet_TAG_Int(e), amulet_TAG_Int(r)])
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
                        new_data = amulet_NBTFile()
                        new_data['Position'] = amulet_from_snbt(f'[I; {cx}, {cz}]')
                        new_data['DataVersion'] = amulet_TAG_Int(self.world.level_wrapper.version)
                        new_data['Entities'] = amulet_TAG_List()
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

    def _export_nbt(self, _):
        entities = amulet_TAG_List()
        blocks = amulet_TAG_List()
        palette = amulet_TAG_List()
        DataVersion = amulet_TAG_Int(2975)
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
                        {'Properties': amulet_from_snbt(str(block.properties)),
                         'Name': amulet_TAG_String(block.namespaced_name)})
                    palette.append(palette_Properties)
                state = pallet_key_map[(block.namespaced_name, str(block.properties))]

                if blockEntity == None:
                    blocks_pos = amulet_TAG_Compound({'pos': amulet_TAG_List(
                        [amulet_TAG_Int(b[0]), amulet_TAG_Int(b[1]),
                         amulet_TAG_Int(b[2])]), 'state': amulet_TAG_Int(state)})
                    blocks.append(blocks_pos)
                else:
                    blocks_pos = amulet_TAG_Compound({'nbt': amulet_from_snbt(blockEntity.to_snbt()),
                                                      'pos': amulet_TAG_List(
                                                          [amulet_TAG_Int(b[0]),
                                                           amulet_TAG_Int(b[1]),
                                                           amulet_TAG_Int(b[2])]),
                                                      'state': amulet_TAG_Int(state)})
                    blocks.append(blocks_pos)
        prg_pre = 99
        self.prog.Update(prg_pre, "Finishing Up " + str(i) + " of " + str(prg_max))
        size = amulet_TAG_List([amulet_TAG_Int(mx), amulet_TAG_Int(my), amulet_TAG_Int(mz)])

        save_it = amulet_NBTFile()
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
                        dict(amulet_from_snbt(nbt['palette'][int(x.get('state'))]['Properties'].to_snbt())))
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

                    x['nbt']['Pos'] = amulet_TAG_List([amulet_TAG_Double(float(nxx + xx)),
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

        entities = amulet_TAG_List()
        selection = self.canvas.selection.selection_group.to_box()
        for o, n in zip(selection, rpos):
            mapdic[o] = n
        chunk_min, chunk_max = self.canvas.selection.selection_group.min, \
            self.canvas.selection.selection_group.max
        min_chunk_cords, max_chunk_cords = block_coords_to_chunk_coords(chunk_min[0], chunk_min[2]), \
            block_coords_to_chunk_coords(chunk_max[0], chunk_max[2])
        cl = self.canvas.selection.selection_group.chunk_locations()
        self.found_entities = amulet_TAG_List()
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
            return amulet_TAG_List()
        entities = amulet_TAG_List()
        for nbt_data in self.found_entities:
            x, y, z = math.floor(nbt_data.get('Pos')[0].value), math.floor(
                nbt_data.get('Pos')[1].value), math.floor(nbt_data.get('Pos')[2].value)
            if (x, y, z) in selection:
                new_pos = mapdic[(x, y, z)]
                nbt_pos = amulet_TAG_List([amulet_TAG_Double(sum([new_pos[0],
                                                                  math.modf(abs(nbt_data.get("Pos")[0].value))[0]])),
                                           amulet_TAG_Double(sum([new_pos[1],
                                                                  math.modf(abs(nbt_data.get("Pos")[1].value))[0]])),
                                           amulet_TAG_Double(sum([new_pos[2],
                                                                  math.modf(abs(nbt_data.get("Pos")[2].value))[0]]))])
                nbt_block_pos = amulet_TAG_List([amulet_TAG_Int(new_pos[0]),
                                                 amulet_TAG_Int(new_pos[1]),
                                                 amulet_TAG_Int(new_pos[2])])
                nbt_nbt_ = amulet_from_snbt(nbt_data.to_snbt())
                main_entry = amulet_TAG_Compound()
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
                nbt_data['UUID'] = amulet_TAG_Int_Array(
                    [amulet_TAG_Int(q), amulet_TAG_Int(w), amulet_TAG_Int(e), amulet_TAG_Int(r)])
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
                                self.chunk_raw['Entities'] = amulet_TAG_List()

                            self.chunk_raw['Entities'].append(nbt_data)

                            self.Entities_region.put_chunk_data(cx % 32, cz % 32, self.chunk_raw)
                            self.Entities_region.save()
                            print(f' 1 SAVED CHUNK NEW FILE file r.{rx}, {rz} Chunk: {cx}, {cz}')
                        else:
                            if not self.chunk_raw.get('Level').get('Entities'):
                                self.chunk_raw["Level"]['Entities'] = amulet_TAG_List()
                            self.chunk_raw["Level"]['Entities'].append(nbt_data)
                            self.Entities_region.put_chunk_data(cx % 32, cz % 32, self.chunk_raw)
                            self.Entities_region.save()
                            print(self.chunk_raw["Level"])
                            print(f' 2 SAVED CHUNK NEW FILE file r.{rx}, {rz} Chunk: {cx}, {cz}')
                    else:
                        if self.world.level_wrapper.version >= 2730:
                            self.Entities_region = AnvilRegion(entitiesPath, create=True)
                            new_data = amulet_NBTFile()
                            new_data['Position'] = amulet_from_snbt(f'[I; {cx}, {cz}]')
                            new_data['DataVersion'] = amulet_TAG_Int(self.world.level_wrapper.version)
                            new_data['Entities'] = amulet_TAG_List()
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
                        new_data = amulet_NBTFile()
                        new_data['Position'] = amulet_from_snbt(f'[I; {cx}, {cz}]')
                        new_data['DataVersion'] = amulet_TAG_Int(self.world.level_wrapper.version)
                        new_data['Entities'] = amulet_TAG_List()
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
        self.button_group_one = wx.GridSizer(2, 2, 0, -20)
        self.button_group_two = wx.GridSizer(0, 3, 0, 1)
        self.button_group_three = wx.GridSizer(0, 2, 0, -1)
        self.button_group_four = wx.GridSizer(0, 4, 1, 1)

        self.SetSizer(self._sizer_v_main)
        self.operation.filter_include_label = wx.StaticText(self, label=" Include Filter:", size=(76, 25))
        self.operation.filter_exclude_label = wx.StaticText(self, label=" Exclude Filter:", size=(76, 25))
        self.operation.exclude_filter = wx.TextCtrl(self, style=wx.TE_LEFT, size=(120, 25))
        self.operation.include_filter = wx.TextCtrl(self, style=wx.TE_LEFT, size=(120, 25))

        self.button_group_four.Add(self.operation.filter_include_label)
        self.button_group_four.Add(self.operation.include_filter, 3, wx.LEFT, -20)
        self.button_group_four.Add(self.operation.filter_exclude_label)
        self.button_group_four.Add(self.operation.exclude_filter, 3, wx.LEFT, -20)
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
        self._sizer_v_main.Add(self.button_group_four)
        self._sizer_v_main.Add(self.bottom_h)
        self.font = wx.Font(11, wx.FONTFAMILY_ROMAN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)

        self.delete_selected = wx.Button(self, label="Delete All Selected")
        self.list_dead = wx.Button(self, label="List Dead", size=(60, 20))
        self.make_undead = wx.Button(self, label="Make UnDead", size=(80, 20))
        self.delete_unselected = wx.Button(self, label="Delete All Un_Selected")
        self._move = wx.Button(self, label="Move", size=(40, 24))
        self._copy = wx.Button(self, label="Copy", size=(40, 24))
        self._delete = wx.Button(self, label="Delete", size=(40, 24))
        self._get_button = wx.Button(self, label="Get Entities", size=(70, 20))
        self._get_all_button = wx.Button(self, label="Get All", size=(60, 20))
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
        self.list_dead.Bind(wx.EVT_BUTTON, lambda event: self.operation._list_the_dead(event))
        self.make_undead.Bind(wx.EVT_BUTTON, lambda event: self.operation._make_undead(event))
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
        self.del_ghosts = wx.Button(self, label="Delete All", size=(60, 20))
        self.del_ghosts.SetToolTip("Delete all dead unlinked entities.")
        self.del_ghosts.Bind(wx.EVT_BUTTON, lambda event: self.operation._delete_all_the_dead(event))
        self.button_group_one.Add(self.list_dead)
        self.button_group_one.Add(self.make_undead)
        self.button_group_one.Add(self.del_ghosts)
        if self.world.level_wrapper.platform == "bedrock":
            if self.world.level_wrapper.version < (1, 18, 30, 4, 0):
                self.list_dead.Hide()
                self.make_undead.Hide()
                self.del_ghosts.Hide()
        elif self.world.level_wrapper.platform == "java":
            self.list_dead.Hide()
            self.make_undead.Hide()
            self.del_ghosts.Hide()
        self.top_sizer.Add(self.button_group_one, 0, wx.TOP, -10)
        self.top_sizer.Add(self._teleport_check, 0, wx.LEFT, 7)

        self.button_group_two.Add(self._move)
        self.button_group_two.Add(self._copy)
        self.button_group_two.Add(self._delete)
        self.top_sizer.Add(self.button_group_two)

        self.operation.ui_entitie_choice_list = wx.ListBox(self, style=wx.LB_HSCROLL, choices=self.lstOfE, pos=(0, 20),
                                                           size=(140, 800))
        self.operation.nbt_editor_instance = NBTEditor(self)
        self.bottom_h.Add(self.operation.nbt_editor_instance, 130, wx.EXPAND, 21)
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

                world_nbt = world_data.get_chunk_data(chunk_x % 32, chunk_z % 32)
                change = False
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


class SetPlayerData(wx.Frame):
    def __init__(self, parent, canvas, world, *args, **kw):
        super(SetPlayerData, self).__init__(parent, *args, **kw,
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

    def getPlayerData(self, pl):
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
                    path = self.world.level_path + "\\playerdata\\" + pl + ".dat"
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
            pdata = self.getPlayerData(player)
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
            pdata = self.getPlayerData(player)
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
        pdata = self.getPlayerData(player)
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
        pdata = self.getPlayerData(player)

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
            with open(self.world.level_path + "\\playerdata\\" + player + ".dat", "wb") as f:
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
            wx.MessageBox(f"Found and selected Spawns From Chunk\s: {found}", "Completed", wx.OK | wx.ICON_INFORMATION)
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

        wx.MessageBox(f"Removed Spawns From Chunk\s: {removed}", "Completed", wx.OK | wx.ICON_INFORMATION)

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
        wx.MessageBox(f"Added Spawn Type to Chunk\s: {f_added}", "Completed", wx.OK | wx.ICON_INFORMATION)

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
                # buffer_world = os.path.join(self.world_location, 'playerdata' )
                buffer_world = ''.join(self.world_location + "/playerdata")
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
                os.system(f"cp -rf \"{self.world.level_wrapper.path}/playerdata\" \"{buffer_world}\"")

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
        self._location_data = wx.TextCtrl(
            self, style=wx.TE_MULTILINE | wx.TE_BESTWRAP, size=(200, 300)
        )
        self._location_data.SetFont(self.font)
        self._location_data.SetForegroundColour((0, 255, 0))
        self._location_data.SetBackgroundColour((0, 0, 0))

    def _setup_layout(self):
        side_sizer = wx.BoxSizer(wx.HORIZONTAL)
        mid_sizer = wx.BoxSizer(wx.HORIZONTAL)
        top_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # Set up the button grid
        grid = wx.GridSizer(1, 2, 0, 0)
        grid.Add(self._delete_unselected_chunks, 0, wx.LEFT, 1)

        grid.Add(self.g_merge, 0, wx.LEFT, 85)

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
        new_data = new_data[:-1]
        for d in new_data.split("\n"):
            x, y, z, xx, yy, zz = d.split(",")
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

        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self.sizer)
        self._top_horz_sizer = wx.BoxSizer(wx.VERTICAL)

        self.sizer.Add(self._top_horz_sizer)
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
        self._portals_and_border_walls = wx.Button(self, label='Portals &&||\n Border Walls ', size=_size)
        self._player_inventory = wx.Button(self, label='NBT Editor\n For Inventory ', size=_size)
        self._entities_data = wx.Button(self, label='NBT Editor \n For Entities', size=_size)
        self._material_counter = wx.Button(self, label='Material Counter', size=_size)
        self._shape_painter = wx.Button(self, label='Shape Painter', size=_size)
        self._random_filler = wx.Button(self, label='Random Filler', size=_size)
        self._set_frames = wx.Button(self, label='Image Or Maps \n To Frames', size=_size)
        self._reset_vaults = wx.Button(self, label='Reset Vaults', size=_size)

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
                      text="Delete all portals and/or border walls.\n"
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

    def set_player_data(self, _):
        self.set_player = SetPlayerData(self.parent, self.canvas, self.world)
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

        self.version = 6
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
            self._force_blending = wx.Button(self, label=f"Multi \n Tools \n V: {self.version} ", size=(270, 240))
            self._force_blending.SetFont(self.font)
            self._force_blending.Bind(wx.EVT_BUTTON, self._force_blening_window)
            self._sizer.Add(self._force_blending)
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

    def get_script_path(self):
        return os.path.abspath(__file__)

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

    def _force_blening_window(self, _):
        if self.version == self.remote_version:
            tools = Tools(self.parent, self.world, self.canvas)
            tools.Show()

    def is_file_recent(self,  age_limit=20):
        file_path = self.get_script_path()
        if os.path.exists(file_path):
            current_time = time.time()
            file_mod_time = os.path.getmtime(file_path)
            file_age = current_time - file_mod_time
            if file_age < age_limit:
                wx.MessageBox(f"A new version has been apply was v 4 now version"
                              f" {self.remote_version}\n"
                              f"V: 3 and 4\n"
                              f"The update has been automatically applyed:\n"
                              f"Fixed issue with force blending on Bedrock,\n"
                              f"Added message to select player for Set Player Data,\n"
                              f"Added New button to Reset Vaults in Java and Bedrock.\n"
                              f"v:5 Fixed Java Force Blending Tool\n"
                              f"v:6 Added missing imports for NBT Editor For Inventory\n"
                              f"Fixed Bedrock height maps for blending tool\n"
                              f"Added enable disable hardcore button in Set player data for bedrock\n", #List of changes....
                              "Plugin has Been Updated", wx.OK | wx.ICON_INFORMATION)

export = dict(name="# Multi TOOLS", operation=MultiTools)  # By PremiereHell
