import collections
import copy
import gzip
import struct
import pickle
import uuid
import re
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
        self._multi_tool = wx.Button(self, label="Multi Selection Tool")
        self._multi_tool.Bind(wx.EVT_BUTTON, self.MultiForcedBlending)
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
        self._save_load_grid = wx.GridSizer(2, 2, 2, -30)

        self._save_load_grid.Add(self._save_button)
        self._save_load_grid.Add(self._all_chunks)
        self._save_load_grid.Add(self._load_button)
        self._save_load_grid.Add(self._multi_tool)

        self.main_sizer.Add(self.info_label, 1, wx.LEFT, 12)
        self.main_sizer.Add(self._save_load_grid, 1, wx.LEFT, 11)

        #self.main_sizer.Add(self._load_button, 0, wx.LEFT, 11)

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

    def MultiForcedBlending(self, _):
        self.frame1 = wx.Frame(
            self.parent.Parent, id=wx.ID_ANY, pos=wx.DefaultPosition, size=(360, 600), title=" Multi Force Blending",
            style=(
                    wx.MINIMIZE_BOX | wx.MAXIMIZE_BOX | wx.RESIZE_BORDER | wx.SYSTEM_MENU | wx.CAPTION | wx.CLOSE_BOX |
                    wx.CLIP_CHILDREN | wx.FRAME_FLOAT_ON_PARENT | wx.ALIGN_CENTER
            ),
            name="Panel"
        )

        self.frame1.Freeze()
        self._is_enabled = True
        self._moving = True
        self.frame1._sizer1 = wx.BoxSizer(wx.VERTICAL)
        self.frame1.SetSizer(self.frame1._sizer1)

        options = self._load_options({})
        self.frame1.top_sizer1 = wx.BoxSizer(wx.VERTICAL)
        self.frame1.mid_sizer1 = wx.BoxSizer(wx.VERTICAL)
        self.frame1.side_sizer1 = wx.BoxSizer(wx.VERTICAL)
        self.font = wx.Font(13, wx.FONTFAMILY_ROMAN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        self.frame1._sizer1.Add(self.frame1.side_sizer1, 1, wx.TOP | wx.LEFT, 0)
        self.frame1._sizer1.Add(self.frame1.mid_sizer1, 0, wx.TOP | wx.LEFT, 5)
        self.frame1._sizer1.Add(self.frame1.top_sizer1, 0, wx.TOP | wx.LEFT, 290)

        self._delete_unselected_chunks = wx.Button(self.frame1, label="Delete \n Unselected \nChunks", size=(70, 40))
        self._force_blending = wx.Button(self.frame1, label="Force \n Blending", size=(70, 40))
        self._force_blending.Bind(wx.EVT_BUTTON, self._force_blening_window)
        self._force_relighting = wx.Button(self.frame1, label="Force\n Relighting", size=(70, 40))
        self._force_relighting.Bind(wx.EVT_BUTTON, self.force_relighting)
        self._delete_unselected_chunks.Bind(wx.EVT_BUTTON, self.delete_unselected)

        self._run_button = wx.Button(self.frame1, label="Set \n Selection Boxs", size=(60, 50))
        self._run_button.Bind(wx.EVT_BUTTON, self._run_operation)

        self.gsel = wx.Button(self.frame1, label="Get \n Selection Boxs", size=(60, 50))
        self.gsel.Bind(wx.EVT_BUTTON, self._gsel)
        self.g_save = wx.Button(self.frame1, label="Save", size=(60, 50))
        self.g_save.Bind(wx.EVT_BUTTON, self.save_data)
        self.g_load = wx.Button(self.frame1, label="Load", size=(60, 50))
        self.g_load.Bind(wx.EVT_BUTTON, self.load_data)
        self.g_merge = wx.Button(self.frame1, label="Merge Dupes\nDels Text", size=(60, 50))
        self.g_merge.Bind(wx.EVT_BUTTON, self.merge)

        self._up = wx.Button(self.frame1, label="Up", size=(36, 35))
        self._up.Bind(wx.EVT_BUTTON, lambda evt: self._boxUp('m')(evt))
        self._down = wx.Button(self.frame1, label="Down", size=(36, 35))
        self._down.Bind(wx.EVT_BUTTON, lambda evt: self._boxDown('m')(evt))
        self._east = wx.Button(self.frame1, label="East", size=(36, 35))
        self._east.Bind(wx.EVT_BUTTON, lambda evt: self._boxEast('m')(evt))
        self._west = wx.Button(self.frame1, label="West", size=(36, 35))
        self._west.Bind(wx.EVT_BUTTON, lambda evt: self._boxWest('m')(evt))
        self._north = wx.Button(self.frame1, label="North", size=(36, 35))
        self._north.Bind(wx.EVT_BUTTON, lambda evt: self._boxNorth('m')(evt))
        self._south = wx.Button(self.frame1, label="South", size=(36, 35))
        self._south.Bind(wx.EVT_BUTTON, lambda evt: self._boxSouth('m')(evt))
        self._southeast = wx.Button(self.frame1, label="South East", size=(77, 25))
        self._southeast.Bind(wx.EVT_BUTTON, lambda evt: self._boxDiag('se')(evt))
        self._northeast = wx.Button(self.frame1, label="North East", size=(77, 25))
        self._northeast.Bind(wx.EVT_BUTTON, lambda evt: self._boxDiag('ne')(evt))
        self._northwest = wx.Button(self.frame1, label="North West", size=(77, 25))
        self._northwest.Bind(wx.EVT_BUTTON, lambda evt: self._boxDiag('nw')(evt))
        self._southwest = wx.Button(self.frame1, label="South West", size=(77, 25))
        self._southwest.Bind(wx.EVT_BUTTON, lambda evt: self._boxDiag('sw')(evt))

        self._usoutheast = wx.Button(self.frame1, label="Up\n South East", size=(77, 30))
        self._usoutheast.Bind(wx.EVT_BUTTON, lambda evt: self._boxDiag('use')(evt))
        self._unortheast = wx.Button(self.frame1, label="Up\n North East", size=(77, 30))
        self._unortheast.Bind(wx.EVT_BUTTON, lambda evt: self._boxDiag('une')(evt))
        self._unorthwest = wx.Button(self.frame1, label="Up\n North West", size=(77, 30))
        self._unorthwest.Bind(wx.EVT_BUTTON, lambda evt: self._boxDiag('unw')(evt))
        self._usouthwest = wx.Button(self.frame1, label="Up\n South West", size=(77, 30))
        self._usouthwest.Bind(wx.EVT_BUTTON, lambda evt: self._boxDiag('usw')(evt))

        self._dsoutheast = wx.Button(self.frame1, label="Down\n South East", size=(77, 30))
        self._dsoutheast.Bind(wx.EVT_BUTTON, lambda evt: self._boxDiag('dse')(evt))
        self._dnortheast = wx.Button(self.frame1, label="Down\n North East", size=(77, 30))
        self._dnortheast.Bind(wx.EVT_BUTTON, lambda evt: self._boxDiag('dne')(evt))
        self._dnorthwest = wx.Button(self.frame1, label="Down\n North West", size=(77, 30))
        self._dnorthwest.Bind(wx.EVT_BUTTON, lambda evt: self._boxDiag('dnw')(evt))
        self._dsouthwest = wx.Button(self.frame1, label="Down\n South West", size=(77, 30))
        self._dsouthwest.Bind(wx.EVT_BUTTON, lambda evt: self._boxDiag('dsw')(evt))
        self.lbct = wx.StaticText(self.frame1, label="Step:")

        self.lbmove = wx.StaticText(self.frame1, label="Move All Selection:")
        self.lbstrech = wx.StaticText(self.frame1, label="Stretch Last Selection:")

        self.control = wx.SpinCtrl(self.frame1, value="1", min=1, max=1000)

        self.boxgrid_down = wx.GridSizer(1, 4, 1, 1)
        self.boxgrid_u = wx.GridSizer(1, 4, 2, 1)
        self.boxgrid_d = wx.GridSizer(1, 4, 1, 1)
        self.boxgrid_b = wx.GridSizer(1, 8, 1, -16)
        self.boxgrid_b.Add(self._up)
        self.boxgrid_b.Add(self._down)
        self.boxgrid_b.Add(self._east)
        self.boxgrid_b.Add(self._west)
        self.boxgrid_b.Add(self._north)
        self.boxgrid_b.Add(self._south)
        self.boxgrid_b.Add(self.lbct)
        self.boxgrid_b.Add(self.control)

        self.boxgrid_d.Add(self._northeast)
        self.boxgrid_d.Add(self._southeast)
        self.boxgrid_d.Add(self._northwest)
        self.boxgrid_d.Add(self._southwest)

        self.boxgrid_u.Add(self._unortheast)
        self.boxgrid_u.Add(self._usoutheast)
        self.boxgrid_u.Add(self._unorthwest)
        self.boxgrid_u.Add(self._usouthwest)

        self.boxgrid_down.Add(self._dnortheast)
        self.boxgrid_down.Add(self._dsoutheast)
        self.boxgrid_down.Add(self._dnorthwest)
        self.boxgrid_down.Add(self._dsouthwest)

        self.frame1.grid1 = wx.GridSizer(1, 5, 0, 0)
        self.frame1.grid1.Add(self.g_save)
        self.frame1.grid1.Add(self.g_load)
        self.frame1.grid1.Add(self._run_button)
        self.frame1.grid1.Add(self.gsel)
        self.frame1.grid1.Add(self.g_merge)
        self.frame1.side_sizer1.Add(self.frame1.grid1, 1, wx.TOP | wx.LEFT, 1)
        self.frame1.side_sizer1.Add(self.lbmove)
        self.frame1.side_sizer1.Add(self.boxgrid_b, 0, wx.TOP | wx.LEFT, 1)
        self.frame1.side_sizer1.Add(self.lbstrech)
        self.frame1.side_sizer1.Add(self.boxgrid_d, 0, wx.TOP | wx.LEFT, 1)
        self.frame1.side_sizer1.Add(self.boxgrid_u, 0, wx.TOP | wx.LEFT, 1)
        self.frame1.side_sizer1.Add(self.boxgrid_down, 0, wx.TOP | wx.LEFT, 1)

        if self.world.level_wrapper.platform == "java":
            self.box_mid = wx.GridSizer(1, 3, 1, -11)
            self.box_mid.Add(self._force_relighting)
            # self._find_chunks.Hide()
        else:
            self._force_relighting.Hide()
            self.box_mid = wx.GridSizer(1, 4, 1, 1)
            # self.box_mid.Add(self._find_chunks)
            # self.box_mid.Add(self._move_chunks)
        self.box_mid.Add(self._delete_unselected_chunks)
        self.box_mid.Add(self._force_blending)

        self.frame1.mid_sizer1.Add(self.box_mid)

        self._location_data = wx.TextCtrl(
            self.frame1, style=wx.TE_MULTILINE | wx.TE_BESTWRAP
        )
        self.frame1._sizer1.Add(self._location_data, 25, wx.EXPAND | wx.LEFT | wx.RIGHT, 0)

        self._location_data.SetFont(self.font)
        self._location_data.SetForegroundColour((0, 255, 0))
        self._location_data.SetBackgroundColour((0, 0, 0))
        self._location_data.Fit()
        print("F")
        self.frame1.Layout()
        self.frame1.Thaw()
        self.frame1.Show(True)

    def move_chunks(self, _):
        pass

    def find_chunks(self, _):
        pass

    def force_relighting(self, _):
        self._gsel(_)
        self.merge(_)
        self._set_seletion()
        selected_chunks = self.canvas.selection.selection_group.chunk_locations()
        if len(selected_chunks) == 0:
            wx.MessageBox(" You Must Select An area or have an area in the list",
                          "Information", style=wx.OK | wx.STAY_ON_TOP | wx.CENTRE,
                          parent=self.Parent)

        loaction_dict = collections.defaultdict(list)
        if self.world.level_wrapper.platform == "java":

            for xx, zz in selected_chunks:
                rx, rz = world_utils.chunk_coords_to_region_coords(xx, zz)
                loaction_dict[(rx, rz)].append((xx, zz))

            for rx, rz in loaction_dict.keys():
                file_exists = exists(self.get_dim_vpath_java_dir(rx, rz))
                if file_exists:
                    for di in loaction_dict[(rx, rz)]:
                        cx, cz = di

                        self.raw_data = AnvilRegion(self.get_dim_vpath_java_dir(rx, rz))
                        if self.raw_data.has_chunk(cx % 32, cz % 32):
                            nbt_data = self.raw_data.get_chunk_data(cx % 32, cz % 32)
                            nbt_data.pop('isLightOn', None)

                            self.raw_data.put_chunk_data(cx % 32, cz % 32, nbt_data)
                        self.raw_data.save()
            self.world.save()
            wx.MessageBox(" Lighting will now regenerate in the selected chunk\s",
                          "Information", style=wx.OK | wx.STAY_ON_TOP | wx.CENTRE,
                          parent=self.Parent)

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
                              style=(
                                      wx.MINIMIZE_BOX | wx.MAXIMIZE_BOX | wx.RESIZE_BORDER | wx.SYSTEM_MENU | wx.CAPTION | wx.CLOSE_BOX | wx.CLIP_CHILDREN | wx.FRAME_FLOAT_ON_PARENT),
                              name="Panel",
                              title="CHUNKS")
        sizer_P = wx.BoxSizer(wx.VERTICAL)
        self.frame.SetSizer(sizer_P)
        self.textGrid = wx.TextCtrl(self.frame, style=wx.TE_MULTILINE | wx.TE_BESTWRAP, size=(400, 750))
        # self.buttons = wx.Button(self.frame, label=str(x)+","+str(z), size=(60, 50))
        self.textGrid.SetValue("This is the list of Chunk That will be saved:\n" + str(selected_chunks))
        self.textGrid.SetFont(self.font)
        self.textGrid.SetForegroundColour((0, 255, 0))
        self.textGrid.SetBackgroundColour((0, 0, 0))
        sizer_P.Add(self.textGrid)

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

    def _boxDiag(self, v):
        def OnClick(event):
            if v == 'se':
                group = self.canvas.selection.selection_group
                glist = list(group)
                x, y, z = glist[0].point_1
                xx, yy, zz = glist[-1].point_2
                if x > xx and z < zz:
                    glist.reverse()
                for x in range(0, self.control.GetValue()):
                    x, y, z = glist[-1].point_1
                    xx, yy, zz = glist[-1].point_2
                    new = SelectionBox((x + 1, y, z + 1), (xx + 1, yy, zz + 1))
                    glist.append(new)
                    merg = SelectionGroup(glist).merge_boxes()
                    self.canvas.selection.set_selection_group(merg)

            if v == 'nw':
                group = self.canvas.selection.selection_group
                glist = list(group)
                x, y, z = glist[0].point_1
                xx, yy, zz = glist[-1].point_2
                if x < xx and z > zz:
                    glist.reverse()
                for x in range(0, self.control.GetValue()):
                    x, y, z = glist[-1].point_1
                    xx, yy, zz = glist[-1].point_2
                    new = SelectionBox((x - 1, y, z - 1), (xx - 1, yy, zz - 1))
                    glist.append(new)
                    merg = SelectionGroup(glist).merge_boxes()
                    self.canvas.selection.set_selection_group(merg)

            if v == 'ne':
                group = self.canvas.selection.selection_group
                glist = list(group)
                x, y, z = glist[0].point_1
                xx, yy, zz = glist[-1].point_2
                if z < zz:
                    glist.reverse()
                for x in range(0, self.control.GetValue()):
                    x, y, z = glist[-1].point_1
                    xx, yy, zz = glist[-1].point_2
                    new = SelectionBox((x + 1, y, z - 1), (xx + 1, yy, zz - 1))
                    glist.append(new)
                    merg = SelectionGroup(glist).merge_boxes()
                    self.canvas.selection.set_selection_group(merg)

            if v == 'sw':
                group = self.canvas.selection.selection_group
                glist = list(group)
                x, y, z = glist[0].point_1
                xx, yy, zz = glist[-1].point_2
                if z > zz:
                    glist.reverse()
                for x in range(0, self.control.GetValue()):
                    x, y, z = glist[-1].point_1
                    xx, yy, zz = glist[-1].point_2
                    new = SelectionBox((x - 1, y, z + 1), (xx - 1, yy, zz + 1))
                    glist.append(new)
                    merg = SelectionGroup(glist).merge_boxes()
                    self.canvas.selection.set_selection_group(merg)
            if v == 'use':
                group = self.canvas.selection.selection_group
                glist = list(group)
                x, y, z = glist[0].point_1
                xx, yy, zz = glist[-1].point_2
                print(x, xx, y, yy, z, zz)

                if x < xx and z < zz:  # and y > yy:
                    glist.reverse()
                for x in range(0, self.control.GetValue()):
                    x, y, z = glist[-1].point_1
                    xx, yy, zz = glist[-1].point_2
                    yy += 1
                    y += 1
                    new = SelectionBox((x + 1, y, z + 1), (xx + 1, yy, zz + 1))
                    glist.append(new)
                    merg = SelectionGroup(glist).merge_boxes()
                    self.canvas.selection.set_selection_group(merg)

            if v == 'unw':
                group = self.canvas.selection.selection_group
                glist = list(group)
                x, y, z = glist[0].point_1
                xx, yy, zz = glist[-1].point_2
                if x > xx and z > zz and y > yy:
                    glist.reverse()
                for x in range(0, self.control.GetValue()):
                    x, y, z = glist[-1].point_1
                    xx, yy, zz = glist[-1].point_2
                    yy += 1
                    y += 1
                    new = SelectionBox((x - 1, y, z - 1), (xx - 1, yy, zz - 1))
                    glist.append(new)
                    merg = SelectionGroup(glist).merge_boxes()
                    self.canvas.selection.set_selection_group(merg)

            if v == 'une':
                group = self.canvas.selection.selection_group
                glist = list(group)
                x, y, z = glist[0].point_1
                xx, yy, zz = glist[-1].point_2
                if x < xx and z > zz and y > yy:
                    glist.reverse()
                for x in range(0, self.control.GetValue()):
                    x, y, z = glist[-1].point_1
                    xx, yy, zz = glist[-1].point_2
                    yy += 1
                    y += 1
                    new = SelectionBox((x + 1, y, z - 1), (xx + 1, yy, zz - 1))
                    glist.append(new)
                    merg = SelectionGroup(glist).merge_boxes()
                    self.canvas.selection.set_selection_group(merg)

            if v == 'usw':
                group = self.canvas.selection.selection_group
                glist = list(group)
                x, y, z = glist[0].point_1
                xx, yy, zz = glist[-1].point_2
                print(x, xx)
                if x > xx and z < zz and y > yy:
                    glist.reverse()
                for x in range(0, self.control.GetValue()):
                    x, y, z = glist[-1].point_1
                    xx, yy, zz = glist[-1].point_2
                    yy += 1
                    y += 1
                    new = SelectionBox((x - 1, y, z + 1), (xx - 1, yy, zz + 1))
                    glist.append(new)
                    merg = SelectionGroup(glist).merge_boxes()
                    self.canvas.selection.set_selection_group(merg)

            if v == 'dse':
                group = self.canvas.selection.selection_group
                glist = list(group)
                x, y, z = glist[0].point_1
                xx, yy, zz = glist[-1].point_2
                print(x, xx, y, yy, z, zz)

                if x < xx and z < zz and y < yy:
                    glist.reverse()
                for x in range(0, self.control.GetValue()):
                    x, y, z = glist[-1].point_1
                    xx, yy, zz = glist[-1].point_2
                    yy -= 1
                    y -= 1
                    new = SelectionBox((x + 0, y, z + 1), (xx + 0, yy, zz + 1))
                    glist.append(new)
                    merg = SelectionGroup(glist).merge_boxes()
                    self.canvas.selection.set_selection_group(merg)

            if v == 'dnw':
                group = self.canvas.selection.selection_group
                glist = list(group)
                x, y, z = glist[0].point_1
                xx, yy, zz = glist[-1].point_2
                if x > xx and z > zz and y < yy:
                    glist.reverse()
                for x in range(0, self.control.GetValue()):
                    x, y, z = glist[-1].point_1
                    xx, yy, zz = glist[-1].point_2
                    yy -= 1
                    y -= 1
                    new = SelectionBox((x - 1, y, z - 1), (xx - 1, yy, zz - 1))
                    glist.append(new)
                    merg = SelectionGroup(glist).merge_boxes()
                    self.canvas.selection.set_selection_group(merg)

            if v == 'dne':
                group = self.canvas.selection.selection_group
                glist = list(group)
                x, y, z = glist[0].point_1
                xx, yy, zz = glist[-1].point_2
                if x < xx and z > zz and y < yy:
                    glist.reverse()
                for x in range(0, self.control.GetValue()):
                    x, y, z = glist[-1].point_1
                    xx, yy, zz = glist[-1].point_2
                    yy -= 1
                    y -= 1
                    new = SelectionBox((x + 1, y, z - 1), (xx + 1, yy, zz - 1))
                    glist.append(new)
                    merg = SelectionGroup(glist).merge_boxes()
                    self.canvas.selection.set_selection_group(merg)

            if v == 'dsw':
                group = self.canvas.selection.selection_group
                glist = list(group)
                x, y, z = glist[0].point_1
                xx, yy, zz = glist[-1].point_2
                print(x, xx)
                if x > xx and z < zz and y < yy:
                    glist.reverse()
                for x in range(0, self.control.GetValue()):
                    x, y, z = glist[-1].point_1
                    xx, yy, zz = glist[-1].point_2
                    yy -= 1
                    y -= 1
                    new = SelectionBox((x - 1, y, z + 1), (xx - 1, yy, zz + 1))
                    glist.append(new)
                    merg = SelectionGroup(glist).merge_boxes()
                    self.canvas.selection.set_selection_group(merg)

        return OnClick

    def bind_events(self):
        super().bind_events()
        self._selection.bind_events()
        self._selection.enable()

    def enable(self):
        self._selection = BlockSelectionBehaviour(self.canvas)
        self._selection.enable()

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

    # def location(self) -> PointCoordinates:
    #     return self._location.value

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

    def merge(self, _):
        data = self._location_data.GetValue()
        prog = re.compile(r'([-+]?\d[\d+]*)(?:\.\d+)?',
                          flags=0)  # (?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?  r'[-+]?[^(\.\d*)](\d+)+'
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
        # self._location_data.SetValue(sp)
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

    def _set_seletion(self):
        data = self._location_data.GetValue()
        prog = re.compile(r'([-+]?\d[\d+]*)(?:\.\d+)?',
                          flags=0)  # (?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?  r'[-+]?[^(\.\d*)](\d+)+'
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

    def _force_blening_window(self, _):
        self.frame = wx.Frame(self.parent.Parent, id=wx.ID_ANY, pos=wx.DefaultPosition, size=(460, 500),
                              style=(
                                      wx.MINIMIZE_BOX | wx.MAXIMIZE_BOX | wx.RESIZE_BORDER | wx.SYSTEM_MENU | wx.CAPTION | wx.CLOSE_BOX | wx.CLIP_CHILDREN | wx.FRAME_FLOAT_ON_PARENT),
                              name="Panel")
        self.font2 = wx.Font(16, wx.FONTFAMILY_ROMAN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)

        self.info_label = wx.StaticText(self.frame, label="There is No Undo Make a backup!", size=(440, 20))
        self.info_label2 = wx.StaticText(self.frame, label="How It Works:\n"
                                                           "The Overworld:\n "
                                                           "Requires at least one chunk border of deleted chunks"
                                                           " Blending happens when existing terrain blends in with seed "
                                                           "generated terrain.\n Water surrounds if below 62 and the cut off is 255\n"
                                                           "The Nether:  !Untested In Java\n"
                                                           "You will want chunks to be around your builds. "
                                                           "Not Really blending, But it looks better than 16x16 flat walls.  "
                                                           "The End:\n"
                                                           "Has not been updated yet and does not appear to have any "
                                                           "blending options as of yet.\n"
                                                           "Blending Does not require a seed change,\n"
                                                           "A simple biome change, pasted in chunks, higher terrain blocks "
                                                           "or structures(Recalculate Heightmap)\n "
                                                           "Terrain blocks are also required for the overworld it will "
                                                           "blend from them, it wont blend from none terrain type blocks"
                                                           "\nManual Seed changes or algorithmic seed changes are what make old "
                                                           "terrain not match up to existing chunks without blending.\n"

                                         , size=(440, 492))

        self.info_label2.SetFont(self.font2)
        self.info_label.SetFont(self.font2)
        self.info_label.SetForegroundColour((255, 0, 0))
        self.info_label.SetBackgroundColour((0, 0, 0))
        self.info_label2.SetForegroundColour((0, 200, 0))
        self.info_label2.SetBackgroundColour((0, 0, 0))
        self._all_chunks = wx.CheckBox(self.frame, label="All Chunks")

        self._all_chunks.SetFont(self.font2)

        self._recal_heightmap = wx.CheckBox(self.frame,
                                            label="Recalculate Heightmap( only needed in overworld \nfor pasted chunks or structures)")
        self._recal_heightmap.SetFont(self.font2)
        self._all_chunks.SetValue(True)
        self._recal_heightmap.SetValue(False)
        self._sizer = wx.BoxSizer(wx.VERTICAL)
        self.frame.SetSizer(self._sizer)
        side_sizer = wx.BoxSizer(wx.VERTICAL)
        self._sizer.Add(side_sizer)

        self._run_button = wx.Button(self.frame, label="Force Blending")
        self._run_button.SetFont(self.font2)
        self.seed = wx.Button(self.frame, label="(Save new seed)")
        self.seed_input = wx.TextCtrl(self.frame, style=wx.TE_LEFT, size=(220, 25))
        self.seed_input.SetFont(self.font2)
        if self.seed_input.GetValue() == "":
            if self.world.level_wrapper.platform == "java":
                self.seed_input.SetValue(
                    str(self.world.level_wrapper.root_tag['Data']['WorldGenSettings']['seed']))
                self._recal_heightmap.Hide()

            else:
                self.seed_input.SetValue(str(self.world.level_wrapper.root_tag['RandomSeed']))
        self._run_button.Bind(wx.EVT_BUTTON, self._refresh_chunk)
        self.seed.Bind(wx.EVT_BUTTON, self.set_seed)
        side_sizer.Add(self.info_label, 0, wx.LEFT, 11)
        side_sizer.Add(self.info_label2, 0, wx.LEFT, 11)
        side_sizer.Add(self._run_button, 0, wx.LEFT, 11)
        side_sizer.Add(self._all_chunks, 0, wx.LEFT, 11)
        side_sizer.Add(self._recal_heightmap, 0, wx.LEFT, 11)
        side_sizer.Add(self.seed_input, 0, wx.LEFT, 11)

        # side_sizer.Add(self.label, 10, wx.TOP | wx.LEFT, 5)
        side_sizer.Add(self.seed, 0, wx.LEFT, 11)
        # side_sizer.Fit(self)
        self.frame.Fit()
        self.frame.Layout()
        self.frame.Show(True)

    def set_seed(self, _):
        if self.world.level_wrapper.platform == "java":
            self.world.level_wrapper.root_tag['Data']['WorldGenSettings']['seed'] = amulet_nbt.LongTag(
                (int(self.seed_input.GetValue())))
            self.world.save()
        else:
            self.world.level_wrapper.root_tag['RandomSeed'] = amulet_nbt.LongTag((int(self.seed_input.GetValue())))
            self.world.level_wrapper.root_tag.save()

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
        self.canvas.run_operation(lambda: self.start(_), "Converting chunks", "Starting...")
        # if 'minecraft:the_nether' in self.canvas.dimension:
        #     self.canvas.run_operation(lambda: self.set_nether(_), "Converting chunks", "Starting...")

        self.world.purge()
        self.world.save()
        self.canvas.renderer.render_world._rebuild()

        wx.MessageBox("If you Had no errors It Worked "
                      "\n Close World and Open in Minecraft", "IMPORTANT",
                      wx.OK | wx.ICON_INFORMATION)

    def start(self, _):
        if self._all_chunks.GetValue():
            self.all_chunks = [x for x in self.world.level_wrapper.all_chunk_coords(self.canvas.dimension)]
        else:
            self.all_chunks = self.canvas.selection.selection_group.chunk_locations()
        # self.all_chunks = [(4, 119)]
        total = len(self.all_chunks)
        count = 0
        loaction_dict = collections.defaultdict(list)
        if self.world.level_wrapper.platform == "java":

            for xx, zz in self.all_chunks:
                rx, rz = world_utils.chunk_coords_to_region_coords(xx, zz)
                loaction_dict[(rx, rz)].append((xx, zz))

            for rx, rz in loaction_dict.keys():
                file_exists = exists(self.get_dim_vpath_java_dir(rx, rz))
                self.world.level_wrapper.root_tag['Data']['DataVersion'] = amulet_nbt.IntTag(2860)
                self.world.level_wrapper.root_tag['Data']['Version'] = amulet_nbt.CompoundTag(
                    {"Snapshot": amulet_nbt.ByteTag(0), "Id": amulet_nbt.IntTag(2860),
                     "Name": amulet_nbt.StringTag("1.18.0")})
                self.world.save()
                if file_exists:
                    for di in loaction_dict[(rx, rz)]:
                        cx, cz = di
                        count += 1
                        yield count / total, f"Chunk: {xx, zz} Done.... {count} of {total}"
                        self.raw_data = AnvilRegion(self.get_dim_vpath_java_dir(rx, rz))
                        if self.raw_data.has_chunk(cx % 32, cz % 32):
                            nbtdata = self.raw_data.get_chunk_data(cx % 32, cz % 32)

                            if nbtdata['sections']:
                                nbtdata['Heightmaps'] = amulet_nbt.CompoundTag({})
                                nbtdata['blending_data'] = amulet_nbt.CompoundTag(
                                    {"old_noise": amulet_nbt.ByteTag(1)})
                                nbtdata['DataVersion'] = amulet_nbt.IntTag(2860)
                                self.raw_data.put_chunk_data(cx % 32, cz % 32, nbtdata)
                            self.raw_data.save()
            yield count / total, f"Chunk: {xx, zz} Done.... {count} of {total}"


        else:  # BEDROCK

            if ('minecraft:the_nether') or ('minecraft:overworld') in self.canvas.dimension:
                self.height = numpy.frombuffer(numpy.zeros(512, 'b'), "<i2").reshape((16, 16))
                self.over_under_blending_limits = False
                for xx, zz in self.all_chunks:

                    count += 1
                    chunkkey = self.get_dim_chunkkey(xx, zz)
                    if 'minecraft:the_end' in self.canvas.dimension:
                        wx.MessageBox("The End THis does not have any effect "
                                      "\n overworld works and the nether does not have biome blending only rounds the "
                                      "chunk walls", "IMPORTANT", wx.OK | wx.ICON_INFORMATION)
                        return

                    if 'minecraft:the_nether' in self.canvas.dimension:

                        try:  # if nether

                            self.level_db.put(chunkkey + b'v', b'\x07')
                        except Exception as e:
                            print("A", e)
                        try:  # if nether
                            self.level_db.delete(chunkkey + b',')
                        except Exception as e:
                            print("B", e)
                    else:
                        try:
                            self.level_db.delete(chunkkey + b'@')  # ?
                        except Exception as e:
                            print("C", e)
                        if self._recal_heightmap.GetValue():

                            lower_keys = {-1: 4, -2: 3, -3: 2, -4: 1}

                            for k, v in self.world.level_wrapper.level_db.iterate(start=chunkkey + b'\x2f\x00',
                                                                                  end=chunkkey + b'\x2f\xff\xff'):
                                if len(k) > 8 < 10:
                                    key = self.unsignedToSigned(k[-1], 1)
                                    blocks, block_bits, extra_blk, extra_blk_bits = self.get_pallets_and_extra(
                                        v[3:])

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

                            height = self.height.tobytes()

                            self.level_db.put(chunkkey + height_biome_key, height + biome)
                    if self._recal_heightmap.GetValue():
                        yield count / total, f"Preparing Chunks and new HeightMaps, Current:  {xx, zz}  Prosessing: {count} of {total}"
                    else:
                        yield count / total, f"Preparing Chunks,  Current {xx, zz}  Prosessing: {count} of {total}"

            if self._recal_heightmap.GetValue():
                if self.over_under_blending_limits:
                    wx.MessageBox("The Height has been updated"
                                  "Complete Some Height issues were detected , \n If below y 62 water spawns around,"
                                  "\n 255 is the height limit for blending  ", "IMPORTANT",
                                  wx.OK | wx.ICON_INFORMATION)
                else:
                    wx.MessageBox("The Chunks Have Been Updated"
                                  "\nComplete no issues detected", "IMPORTANT", wx.OK | wx.ICON_INFORMATION)

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
            nbt, p = amulet_nbt.load(pallet_data, little_endian=True, offset=True)
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
                nbt, p = amulet_nbt.load(pallet_data, little_endian=True, offset=True)

                pallet_data = pallet_data[p:]
                extra_blocks.append(nbt.value)
        return blocks, block_pnt_bits, extra_blocks, extra_pnt_bits

    def get_blocks(self, raw_sub_chunk):
        bpv, rawdata = struct.unpack("b", raw_sub_chunk[0:1])[0] >> 1, raw_sub_chunk[1:]
        if bpv > 0:
            bpw = (32 // bpv)
            wc = -(-4096 // bpw)
            buffer = numpy.frombuffer(bytes(reversed(rawdata[: 4 * wc])), dtype="uint8")  # reversed
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
        chunkkey = b''
        if 'minecraft:the_end' in self.canvas.dimension:
            chunkkey = b''  # struct.pack('<iii',  xx, zz, 2)
        elif 'minecraft:the_nether' in self.canvas.dimension:
            chunkkey = struct.pack('<iii', xx, zz, 1)
        elif 'minecraft:overworld' in self.canvas.dimension:
            chunkkey = struct.pack('<ii', xx, zz)
        return chunkkey

    def unsignedToSigned(self, n, byte_count):
        return int.from_bytes(n.to_bytes(byte_count, 'little', signed=False), 'little', signed=True)


export = dict(name="Chunk Data v1.3", operation=ChunkSaveAndLoad)  # By PremiereHell
