import collections
import copy
import gzip
import struct
import pickle
import uuid

import wx
from amulet_map_editor.api.opengl.camera import Projection
from amulet_map_editor.programs.edit.api.behaviour import BlockSelectionBehaviour
from amulet_map_editor.programs.edit.api.events import (
    EVT_SELECTION_CHANGE,
)
from typing import TYPE_CHECKING, Type, Any, Callable, Tuple, BinaryIO, Optional, Union
from amulet.utils import chunk_coords_to_region_coords
from amulet.level.formats.anvil_world.region import AnvilRegion
from amulet.api.selection import SelectionGroup
from amulet.api.selection import SelectionBox

from amulet_map_editor.programs.edit.api.operations import DefaultOperationUI
from amulet_map_editor.api.wx.ui.base_select import BaseSelect
from amulet.api.errors import ChunkDoesNotExist
from amulet_nbt import *
import os
from os.path import exists

if TYPE_CHECKING:
    from amulet.api.level import BaseLevel
    from amulet_map_editor.programs.edit.api.canvas import EditCanvas


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
    if test_val == struct.pack('<i', 1)or 'minecraft:the_nether' == test_val:
        return (0,127)
    elif test_val == struct.pack('<i', 2) or 'minecraft:the_end' == test_val:
        return (0,255)
    elif test_val == b'' or 'minecraft:overworld' == test_val:
        return (-64,319)

class ChunkManager:
    def __init__(self, chunks, current_dim_key,platform, world_start_count, next_slot):
        self.platform = platform
        self.world_start_count = world_start_count
        self.next_slot = next_slot
        self.current_dim_key = current_dim_key
        self.y_range = get_y_range(current_dim_key)
        self.chunks = chunks
        self.selection = self.create_selection_map()
        self.org_key = list(self.selection.keys())
        self.last_offset_move = min((x, z) for x, z in self.org_key)
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
        else: #"java"
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
            for i in range(xx - _range-1, xx + _range+2):
                for j in range(zz - _range-1, zz + _range+2):
                    surrounding_coords.append((i,j))

        for x, z in surrounding_coords:
            if (x, z) not in inside:
                out_side_chunks[(x, z)] = SelectionBox((x * 16, self.y_range[0], z * 16),
                                                       (x * 16 + 16, self.y_range[1], z * 16 + 16))

        return out_side_chunks

    def apply_selection(self):
       tx,tz = self.last_offset_move
       self.move_all_chunks_to(tx,tz)
       self.org_key = list(self.selection.keys())
       # self.last_offset_move = min((x, z) for x, z in self.org_key)


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
                print(key, new_key)
                new_chunk_data = self.java_chunk(self.chunks[key].pop('chunk_data')
                                                                 , new_key, new_x, new_z, x, z)
                if self.chunks[key].get('entitie_data'):
                    new_entitie_data = self.java_entities(self.chunks[key].pop('entitie_data')
                                                 , new_key, new_x, new_z, x, z)
                else:
                    new_entitie_data = None

                new_chunks[new_key] = {'chunk_data': new_chunk_data, 'entitie_data': new_entitie_data}

        self.chunks = new_chunks

    def java_entities(self, _chunk_entities, new_key, new_x, new_z, x, z):
        chunk_entities = _chunk_entities
        chunk_entities['Position'] = IntArrayTag([new_x, new_z])
        for e in chunk_entities.get('Entities'):
            x,y,z = e.get('Pos')
            xc, zc = new_x * 16, new_z * 16
            x_pos = x % 16
            z_pos = z % 16
            raw_pos_x = (x_pos + xc)
            raw_pos_z = (z_pos + zc)
            x, z = raw_pos_x, raw_pos_z
            e['Pos'] = ListTag([DoubleTag(x),DoubleTag(y),DoubleTag(z)])
        return chunk_entities

    def java_chunk(self, _chunk_data, new_key, new_x, new_z, x, z ):
        chunk_data = _chunk_data
        chunk_data['xPos'] = IntTag(new_x)
        chunk_data['zPos'] = IntTag(new_z)
        for be in chunk_data.get('block_entities'):
            be['x'] = IntTag(new_x * 16)
            be['z'] = IntTag(new_z * 16)
        return chunk_data

    def update_chunk_keys_entities(self, chunk_dict, new_key, new_x, new_z, x_old, z_old): #bedrock
        dim = self.current_dim_key
        new_dict = {}
        for ik in list(chunk_dict.keys()):
            if len(ik) == 10:
                new_dict[new_key + ik[8:]] = chunk_dict.pop(ik)

            elif len(ik) == 14:
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

    def update_entities(self, entity_dict, new_x, new_z): #bedrock

        new_dict = {}
        new_digp = b''
        new_digp_entry = {}
        d = self.current_dim_key
        chunk_id = struct.pack('<ii', new_x, new_z)

        if entity_dict:
            for digp_key, e in entity_dict.items():
                for act, raw in e['actorprefix_dict'].items():
                    actor_nbt = load(raw,compressed=False,little_endian=True
                    ,string_decoder=utf8_escape_decoder)

                    actor_pos = actor_nbt.get('Pos')
                    actor_nbt.pop('UniqueID')
                    actor_nbt.pop('internalComponents')
                    xc, zc = new_x * 16, new_z * 16

                    x_pos = (actor_pos[0]) % 16
                    z_pos = (actor_pos[2]) % 16

                    raw_pos_x = (x_pos + xc)
                    raw_pos_z = (z_pos + zc)

                    x,z = raw_pos_x, raw_pos_z
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

class ChunkSaveAndLoad(wx.Panel, DefaultOperationUI):

    def __init__(
            self,
            parent: wx.Window,
            canvas: "EditCanvas",
            world: "BaseLevel",
            options_path: str,
    ):

        wx.Panel.__init__(self, parent)
        DefaultOperationUI.__init__(self, parent, canvas, world, options_path)

        self.has_been_loaded = False
        self.raw_data_entities = None
        self.raw_data_chunks = None
        self.chunks_mg = None
        self.Freeze()
        self.font = wx.Font(13, wx.FONTFAMILY_ROMAN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        self.SetFont(self.font)
        self.SetForegroundColour((0, 255, 0))
        self.SetBackgroundColour((0, 0, 0))
        self.info_label = wx.StaticText(self, label="\nThis Directly edited the world Make sure you have a backup! ")

        self._all_chunks = wx.CheckBox(self, label="All Chunks (can be slow)")
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
        self._move_chunks_into_view = wx.Button(self, label="Move Loaded Chunks \nInto Camera View", size=(180,20) )
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
        self._move_n.Bind(wx.EVT_BUTTON, self.move_north)
        self._move_s.Bind(wx.EVT_BUTTON, self.move_south)
        self._move_e.Bind(wx.EVT_BUTTON, self.move_east)

        self._move_w.Bind(wx.EVT_BUTTON, self.move_west)
        self._move_grid.Add(self.space_1)
        self._move_grid.Add(self._move_n)
        self._move_grid.Add(self.space_2)
        self._move_grid.Add(self._move_w)
        self._move_grid.Add(self.space_4)
        self._move_grid.Add(self._move_e)
        self._move_grid.Add(self.space_3)
        self._move_grid.Add(self._move_s)

        self.grid_for_outer = wx.GridSizer(2,2,5,3)
        self._select_outer_l = wx.StaticText(self, label="  Outer select / delete range:\n"
                                                         "(This is required for blending)")
        self._select_outer_in = wx.TextCtrl(self, size=(40, 35))
        self._select_outer_in.SetValue('2')
        self._select_outer = wx.Button(self, label="Select Outer\n Chunks", size=(100,35))
        self._select_outer.Bind(wx.EVT_BUTTON, self.select_outer)
        self._delete_outer = wx.Button(self, label="Delete Outer\n Chunks", size=(100, 35))
        self._delete_outer.Bind(wx.EVT_BUTTON, self.delete_outer)

        self.grid_for_outer.Add(self._select_outer_l)
        self.grid_for_outer.Add(self._select_outer_in)
        self.grid_for_outer.Add(self._delete_outer)
        self.grid_for_outer.Add(self._select_outer)

        self.l_range = wx.StaticText(self, label="Set Sub Chunk layer Range(min,max):")
        self.l_min = wx.StaticText(self, label="  min:")
        self.l_max = wx.StaticText(self, label="  max:")

        self.l_range_Info = wx.StaticText(self, label="overworld=24, end=16, nether=8, Sub chunk is 16x16x16 \n"
                                                      "overworld range is -4 to 19, nether is 0 to 7 end is 0 to 15 ")

        self._range_bottom = wx.TextCtrl(self, size=(40,20))
        self._range_top = wx.TextCtrl(self, size=(40, 20))
        self._range_grid = wx.GridSizer(1, 4, 2, 0)
        self._range_grid.Add(self.l_min)
        self._range_grid.Add(self._range_bottom)
        self._range_grid.Add(self.l_max)
        self._range_grid.Add(self._range_top)
        self._grid_l_and_toggle = wx.GridSizer(1,2,2,2)

        self._toggel_top_down = wx.Button(self, label="Toggle View")
        self._toggel_top_down.Bind(wx.EVT_BUTTON, self.toggel_top_down)
        self.info_label2 = wx.StaticText(self, label="Position loaded chunks")
        self._grid_l_and_toggle.Add(self.info_label2)
        self._grid_l_and_toggle.Add(self._toggel_top_down)

        self._move_chunks_into_view.Bind(wx.EVT_BUTTON, self.move_int_view)
        self._go_to_loaded.Bind(wx.EVT_BUTTON, self.go_to_loaded)
        self._save_loaded_chunks = wx.Button(self, label="Save Loaded chunks:")
        self._save_loaded_chunks.Bind(wx.EVT_BUTTON, self.save_loaded_chunks)
        self._save_grid = wx.GridSizer(1, 2, 2, -30)

        self._save_grid.Add(self._save_button)
        self._save_grid.Add(self._all_chunks)

        self.main_sizer.Add(self.info_label, 1, wx.LEFT, 12)
        self.main_sizer.Add(self._save_grid, 1, wx.LEFT, 11)

        self.main_sizer.Add(self._load_button, 0, wx.LEFT, 11)

        self.loaded_sizer.Add(self._move_chunks_into_view, 1, wx.TOP, 11)
        self.loaded_sizer.Add(self._grid_l_and_toggle, 0, wx.LEFT, 11)
        self.loaded_sizer.Add(self._move_grid, 2, wx.BOTTOM, 11)

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
        self.loaded_sizer.Add(self._include, 0, wx.LEFT, 11)
        self.loaded_sizer.Add(self._group, 1, wx.LEFT, 11)

        self.loaded_sizer.Add(self.l_range, 0, wx.LEFT, 11)
        self.loaded_sizer.Add(self._range_grid, 0, wx.LEFT, 11)
        self.loaded_sizer.Add(self.l_range_Info, 0, wx.LEFT, 11)
        self.loaded_sizer.Add(self.grid_for_outer, 0, wx.LEFT, 11)
        self.main_sizer.Layout()
        self._sizer.Hide(self.loaded_sizer)
        self.loaded_sizer.Layout()
        self.Fit()
        self.Layout()
        self.Thaw()

    def bind_events(self):
        super().bind_events()
        self._selection.bind_events()
        self._selection.enable()

    def enable(self):

        self._selection = BlockSelectionBehaviour(self.canvas)
        self._selection.enable()

    @property
    def level_db(self):
        level_wrapper = self.world.level_wrapper
        if hasattr(level_wrapper, "level_db"):
            return level_wrapper.level_db
        else:
            return level_wrapper._level_manager._db

    def toggel_top_down(self, _):
        mode = self.canvas.camera.projection_mode.value
        if mode == 0:
            self.canvas.camera.projection_mode = Projection.PERSPECTIVE
        else:
            self.canvas.camera.projection_mode = Projection.TOP_DOWN

    def delete_outer(self, _):
        chunk_values = list(self.chunks_mg.outer_chunks(int(self._select_outer_in.GetValue())).keys())
        self.canvas.renderer.render_world.chunk_manager.unload()
        self.canvas.renderer.render_world.unload()
        for x,z in chunk_values:
            self.canvas.world.level_wrapper.delete_chunk(x,z,self.canvas.dimension)

        chunk_values_outer_chunks = list(self.chunks_mg.outer_chunks(int(self._select_outer_in.GetValue())+3).keys())
        loaction_dict = collections.defaultdict(list)
        if self.world.level_wrapper.platform == 'bedrock':
            for xx,zz in chunk_values_outer_chunks:
                chunkkey = self.get_dim_chunkkey(xx, zz)
                self.level_db.delete(chunkkey+b'\x40')
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
        selection_values = list(self.chunks_mg.outer_chunks(int(self._select_outer_in.GetValue())).values())
        merged = SelectionGroup(selection_values).merge_boxes()
        self.canvas.selection.set_selection_group(merged)

    def go_to_loaded(self, _):

        selection_values = list(self.chunks_mg.selection.values())
        location = selection_values[0].point_2
        self.canvas.camera.set_location(location)

    def move_north(self, _):
        self.chunks_mg.move_all_selection_boxes(0,-1)
        new_selection = [v for v in self.chunks_mg.selection.values()]
        merged = SelectionGroup(new_selection).merge_boxes()
        self.canvas.selection.set_selection_group(merged)

    def move_south(self, _):
        self.chunks_mg.move_all_selection_boxes(0,1)
        new_selection = [v for v in self.chunks_mg.selection.values()]
        merged = SelectionGroup(new_selection).merge_boxes()
        self.canvas.selection.set_selection_group(merged)

    def move_east(self, _):
        self.chunks_mg.move_all_selection_boxes(1,0)
        new_selection = [v for v in self.chunks_mg.selection.values()]
        merged = SelectionGroup(new_selection).merge_boxes()
        self.canvas.selection.set_selection_group(merged)

    def move_west(self, _):
        self.chunks_mg.move_all_selection_boxes(-1, 0)
        new_selection = [v for v in self.chunks_mg.selection.values()]
        merged = SelectionGroup(new_selection).merge_boxes()
        self.canvas.selection.set_selection_group(merged)

    def move_int_view(self, _):
        cx, cy, cz = self.canvas.camera.location
        self.chunks_mg.move_all_selection_boxes_to(int(cx) // 16, int(cz) // 16)
        #self.chunks_mg.move_all_chunks_to(int(cx) // 16, int(cz) // 16)
        new_selection = [v for v in self.chunks_mg.selection.values()]
        merged = SelectionGroup(new_selection).merge_boxes()
        self.canvas.selection.set_selection_group(merged)


    def renderer(self, _):

        #TODO add Status Updates
        # total_chunks = len(self.chunks_mg.chunks)
        # print(total_chunks)
        # for i,(c, v) in enumerate(self.chunks_mg.chunks.items()):
        #
        #     x, z = struct.unpack('<ii', c)
        #     self.world.create_chunk(x,z,self.canvas.dimension)
        #     for k, d in v["chunk_data"].items():
        #         self.level_db.put(k, d)
        #     yield 1/ total_chunks

        for c in self.chunks_mg.chunks.keys():
            if self.world.level_wrapper.platform == 'bedrock':
                x, z = struct.unpack('<ii', c)
            else:
                x, z = c
            if self.world.has_chunk(x,z,self.canvas.dimension):
                self.world.get_chunk(x,z,self.canvas.dimension).changed = True

            else:
                self.world.create_chunk(x,z,self.canvas.dimension)
                self.world.get_chunk(x, z, self.canvas.dimension).changed = True
        self.world.save()

        _min, _max = -4,20
        if self.world.level_wrapper.platform == 'bedrock':
            if self._range_top.GetValue() != "":
                _max = int(self._range_top.GetValue())
            if self._range_bottom.GetValue() != "":
                _min = int(self._range_bottom.GetValue())
            for i, (c, v) in enumerate(self.chunks_mg.chunks.items()):
                if self.include_blocks.GetValue():
                    for k, d in v["chunk_data"].items():
                        if len(k) == 14 or len(k) == 10:
                            if k[-2] == 47:
                                packed = struct.pack('B', k[-1])
                                signed_value = struct.unpack('b', packed)[0]
                                if _min <= signed_value <= _max:
                                    self.level_db.put(k, d)
                        else:
                            self.level_db.put(k, d)
                if self.include_entities.GetValue():
                    for k, d in v["entitie"].items():
                        self.level_db.put(k, d['digp_data'])
                        for a, e in d['actorprefix_dict'].items():
                            self.level_db.put(a, e)
        else: #java
            region_file_ready = collections.defaultdict(list)
            self.world.level_wrapper.root_tag['Data']['DataVersion'] = IntTag(2860)
            self.world.level_wrapper.root_tag['Data']['Version'] = CompoundTag(
                {"Snapshot": ByteTag(0), "Id": IntTag(2860),
                 "Name": StringTag("1.18.0")})
            if self._range_top.GetValue() != "":
                _max = int(self._range_top.GetValue())
            if self._range_bottom.GetValue() != "":
                _min = int(self._range_bottom.GetValue())
            chunks = self.chunks_mg.get_chunk_data()
            for k, v in chunks.items():
                x,z = k
                rx, rz = chunk_coords_to_region_coords(x,z)
                region_file_ready[(rx, rz)].append({(x,z):{'data': v}})
            for r,v in region_file_ready.items():
                rx, rz = r

                if self.include_entities.GetValue():
                    self.raw_data_entities = AnvilRegion(self.get_dim_vpath_java_dir(rx, rz, folder='entities'))
                if self.include_blocks.GetValue():
                    self.raw_data_chunks = AnvilRegion(self.get_dim_vpath_java_dir(rx, rz))

                for items in v:
                    for c, d in items.items():
                        cx, cz = c
                        if self.include_blocks.GetValue():
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

                        if self.include_entities.GetValue():
                            if d['data'].get('entitie_data'):
                                data_e = d['data'].get('entitie_data')
                                for i, e in enumerate(data_e['Entities']):
                                    data_e['Entities'][i]['UUID'] = IntArrayTag(
                                        [ x for x in struct.unpack('>iiii', uuid.uuid4().bytes)])

                                self.raw_data_entities.put_chunk_data(cx % 32, cz % 32, data_e)

                if self.include_entities.GetValue():
                    self.raw_data_entities.save()
                    self.raw_data_entities.unload()
                if self.include_blocks.GetValue():
                    self.raw_data_chunks.save()
                    self.raw_data_chunks.unload()

    def save_loaded_chunks(self, _):

        self.chunks_mg.apply_selection()
        self.canvas.renderer.render_world.chunk_manager.unload()
        self.canvas.run_operation(lambda: self.renderer(_), "chunks", "Starting...")
        self.world.purge()
        self.canvas.renderer.render_world.chunk_manager.rebuild()

    def load_chunks(self, _):
        platf = self.world.level_wrapper.platform
        fdlg = wx.FileDialog(self, "Load chunks", "", "",
                             f"Chunk (*.chunks_{platf})|*.chunks_{platf}", wx.FD_OPEN)
        if fdlg.ShowModal() == wx.ID_OK:
            pathto = fdlg.GetPath()
        else:
            return
        with gzip.open(pathto, "rb") as tfile:
            self.chunks = pickle.load(tfile)
        if self.world.level_wrapper.platform == 'bedrock':
            current_entites_values = []
            world_count = self.world.level_wrapper.root_tag.get('worldStartCount')
            start_count = 4294967294 - world_count
            start_key = struct.pack('>L', start_count)
            for k, v in self.world.level_wrapper.level_db.iterate(start=b'actorprefix' + start_key,
                                                                  end=b'actorprefix' + start_key + b'\xff\xff\xff\xff'):
                current_entites_values.append(int.from_bytes(k[15:], 'big'))
            entcnt = 0
            if len(current_entites_values) > 0:
                entcnt = max(current_entites_values) + 1  # the next available slot for the last save

            self.chunks_mg = ChunkManager(self.chunks, self.get_dim_bytes(),
                                          self.world.level_wrapper.platform,
                                          start_count, entcnt)
            selection_values = list(self.chunks_mg.selection.values())
            merged = SelectionGroup(selection_values).merge_boxes()
            self.canvas.selection.set_selection_group(merged)
        else: #java
            self.chunks_mg = ChunkManager(self.chunks, self.canvas.dimension,
                                          self.world.level_wrapper.platform, 0, 0)


            selection_values = list(self.chunks_mg.selection.values())
            merged = SelectionGroup(selection_values).merge_boxes()
            self.canvas.selection.set_selection_group(merged)
        if not self.has_been_loaded:
            self._sizer.Show(self.loaded_sizer)
            self.loaded_sizer.Fit(self)
            self._sizer.Fit(self)
            self.loaded_sizer.Layout()
            self._sizer.Layout()
            self.has_been_loaded = True



    def save_chunks(self, _):
        if self._all_chunks.GetValue():
            self.all_chunks = [x for x in self.world.level_wrapper.all_chunk_coords(self.canvas.dimension)]
        else:
            self.all_chunks = self.canvas.selection.selection_group.chunk_locations()
        if self.world.level_wrapper.platform == "bedrock":

            self.chunk_and_entities = {}
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
                    chunk_data[k] = v

                for k, v in self.world.level_wrapper.level_db.iterate(start=b'digp' + chunkkey[:-1],
                                                                      end=b'digp' + chunkkey + b'\xff'):
                    if k == b'digp' + chunkkey and len(v) > 0:
                        digp_actor_list = []
                        actor_count = len(v) // 8
                        pnt = 0
                        for c in range(actor_count):
                            digp_actor_list.append(b'actorprefix' + v[pnt:pnt + 8])
                            raw_actor_nbt = self.level_db.get(b'actorprefix' + v[pnt:pnt + 8])
                            # actor_nbt = load(raw_actor_nbt, compressed=False, little_endian=True
                            #                             , string_decoder=utf8_escape_decoder)
                            # raw_nbt = actor_nbt.to_nbt(compressed=False, little_endian=True,
                            #                            string_encoder=utf8_escape_encoder)
                            entitiy_data[b'actorprefix' + v[pnt:pnt + 8]] = raw_actor_nbt
                            pnt += 8
                        original_digp_actor_keys[b'digp' + chunkkey] = {'listed': digp_actor_list, 'original_bytes': v}
                        new_digp_entry[k] = {'digp_data': v, 'actorprefix_dict': entitiy_data}
                self.chunk_and_entities[chunkkey] = {'chunk_data': chunk_data, 'entitie': new_digp_entry,
                                                     'original_chunk_key': chunkkey,
                                                     'original_digp_actor_keys': original_digp_actor_keys}
        else: #java
            self.chunk_and_entities = {}
            original_chunk_keys = {}
            loaction_dict = collections.defaultdict(list)
            for xx, zz in self.all_chunks:
                rx, rz = world_utils.chunk_coords_to_region_coords(xx, zz)
                loaction_dict[(rx, rz)].append((xx, zz))

            for rx, rz in loaction_dict.keys():
                file_exists_for_region = exists(self.get_dim_vpath_java_dir(rx, rz))
                file_exists_for_entities= exists(self.get_dim_vpath_java_dir(rx, rz, folder='entities'))
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
                    print("OK")
                    self.raw_data = AnvilRegion(self.get_dim_vpath_java_dir(rx, rz, folder='entities'))
                    for di in loaction_dict[(rx, rz)]:
                        cx, cz = di
                        if self.raw_data.has_chunk(cx % 32, cz % 32):
                            nbtdata = self.raw_data.get_chunk_data(cx % 32, cz % 32)
                            self.chunk_and_entities[(cx, cz)]['entitie_data'] = nbtdata

                    self.raw_data.unload()

        pathto = ""
        platf = self.world.level_wrapper.platform
        fdlg = wx.FileDialog(self, "Save Chunks", "", "",
                             f"chunk (*.chunks_{platf})|*.chunks_{platf}", wx.FD_SAVE)
        if fdlg.ShowModal() == wx.ID_OK:
            pathto = fdlg.GetPath()
        else:
            return False
        if ".chunks" not in pathto:
            pathto = pathto + ".chunks"
        with gzip.open(pathto, "wb") as tfile:
            pickle.dump(self.chunk_and_entities, tfile)

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

    def get_dim_vpath_java_dir(self, regonx, regonz, folder='region' ):#entities
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


export = dict(name="Chunk Data v1.1", operation=ChunkSaveAndLoad)  # By PremiereHell
