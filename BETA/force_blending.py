import collections
import math
import struct
import pickle
import wx
from amulet_map_editor.api.opengl.camera import Projection
from amulet_map_editor.programs.edit.api.behaviour import BlockSelectionBehaviour
from amulet_map_editor.programs.edit.api.events import (
    EVT_SELECTION_CHANGE,
)
from amulet.api.block_entity import BlockEntity
from amulet.api.block import Block
from typing import TYPE_CHECKING, Type, Any, Callable, Tuple, BinaryIO, Optional, Union
from amulet.utils import world_utils
from amulet.level.formats.anvil_world.region import AnvilRegion
from amulet.api.selection import SelectionGroup
from amulet.api.selection import SelectionBox
from amulet.utils import block_coords_to_chunk_coords
from amulet_map_editor.programs.edit.api.operations import DefaultOperationUI
from amulet_map_editor.api.wx.ui.base_select import BaseSelect
from amulet.api.errors import ChunkDoesNotExist
import amulet_nbt
import numpy
import os
from os.path import exists
import copy

if TYPE_CHECKING:
    from amulet.api.level import BaseLevel
    from amulet_map_editor.programs.edit.api.canvas import EditCanvas
class ForceHeightUpdate(wx.Panel, DefaultOperationUI):

    def __init__(
            self,
            parent: wx.Window,
            canvas: "EditCanvas",
            world: "BaseLevel",
            options_path: str,
    ):

        wx.Panel.__init__(self, parent)
        DefaultOperationUI.__init__(self, parent, canvas, world, options_path)
        self.Freeze()
        self.save_data = collections.defaultdict()
        self.height_cal = collections.defaultdict()
        self.info_label = wx.StaticText(self, label="This force save's\n There is No Undo \n Make a backup!")
        self._save_backup = wx.CheckBox(self, label="Backup Y15 and below")
        self._save_backup.SetValue(False)
        self._all_chunks = wx.CheckBox(self, label="All Chunks")
        self.regen_below = wx.CheckBox(self, label="RegenBelow")
        self.regen_below.SetValue(True)
        self._all_chunks.SetValue(True)
        self._sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self._sizer)
        side_sizer = wx.BoxSizer(wx.VERTICAL)
        self._sizer.Add(side_sizer)
        self._restore_button = wx.Button(self, label="Restore Y15 and below")
        self._restore_button.Bind(wx.EVT_BUTTON, self.restore_sub)
        self._run_button = wx.Button(self, label="Force Blending")
        self.seed = wx.Button(self, label="(Save new seed)")
        self.seed_input = wx.TextCtrl(self, style=wx.TE_LEFT, size=(120, 25))
        if self.seed_input.GetValue() == "":
            if self.world.level_wrapper.platform == "java":
                self.regen_below = wx.CheckBox(self, label="RegenBelow")
                self.regen_below.SetValue(True)
                if "b" in str(self.world.level_wrapper.root_tag['Data']['WorldGenSettings']['seed']):
                    self.seed_input.SetValue(
                        str(self.world.level_wrapper.root_tag['Data']['WorldGenSettings']['seed'])[:-1])
                else:
                    self.seed_input.SetValue(str(self.world.level_wrapper.root_tag['Data']['WorldGenSettings']['seed']))

            else:
                if "b" in str(self.world.level_wrapper.root_tag['RandomSeed']):
                    self.seed_input.SetValue(str(self.world.level_wrapper.root_tag['RandomSeed'])[:-1])
                else:
                    self.seed_input.SetValue(str(self.world.level_wrapper.root_tag['RandomSeed']))


        self._run_button.Bind(wx.EVT_BUTTON, self._refresh_chunk)
        self.seed.Bind(wx.EVT_BUTTON,self.set_seed)
        side_sizer.Add(self.info_label, 0,  wx.LEFT, 11)
        side_sizer.Add(self._run_button, 0, wx.LEFT, 11)
        side_sizer.Add(self._all_chunks, 0,  wx.LEFT, 11)
        side_sizer.Add(self.seed_input, 0,  wx.LEFT, 11)
        #side_sizer.Add(self.label, 10, wx.TOP | wx.LEFT, 5)
        side_sizer.Add(self.seed,0,  wx.LEFT, 11)
        if self.world.level_wrapper.platform == "bedrock":
            side_sizer.Add(self._save_backup, 0,   wx.LEFT, 11)
            side_sizer.Add(self._restore_button, 0,  wx.LEFT, 11)
        else:
            side_sizer.Add(self.regen_below, 0,  wx.LEFT, 11)
        self.Layout()
        self.Thaw()

    def bind_events(self):
        super().bind_events()
        self._selection.bind_events()
        self._selection.enable()

    def enable(self):
        self.canvas.camera.projection_mode = Projection.TOP_DOWN
        self._selection = BlockSelectionBehaviour(self.canvas)
        self._selection.enable()

    def set_seed(self, _):
        if self.world.level_wrapper.platform == "java":
            self.world.level_wrapper.root_tag['Data']['WorldGenSettings']['seed'] = amulet_nbt.TAG_Long(
                (int(self.seed_input.GetValue())))
            self.world.save()
        else:
            self.world.level_wrapper.root_tag['RandomSeed'] = amulet_nbt.TAG_Long((int(self.seed_input.GetValue())))
            self.world.level_wrapper.root_tag.save()

    @property
    def level_db(self):
        level_wrapper = self.world.level_wrapper
        if hasattr(level_wrapper, "level_db"):
            return level_wrapper.level_db
        else:
            return level_wrapper._level_manager._db

    def save_it(self, data):

        pathto = ""
        fdlg = wx.FileDialog(self, "Save sublayers", "", "",
                             f"Subchunk (*.sub_chunks)|*.sub_chunks", wx.FD_SAVE)
        if fdlg.ShowModal() == wx.ID_OK:
            pathto = fdlg.GetPath()
        else:
            return False
        if ".sub_chunks" not in pathto:
            pathto = pathto + ".sub_chunks"
        with open(pathto, "wb") as tfile:
            pickle.dump(data, tfile)
            tfile.close()
        yield 1

    def run_restore(self):

        fdlg = wx.FileDialog(self, "Restore sublayers", "", "",
                             f"Subchunk (*.sub_chunks)|*.sub_chunks", wx.FD_OPEN)
        if fdlg.ShowModal() == wx.ID_OK:
            pathto = fdlg.GetPath()
        else:
            return
        with open(pathto, "rb") as tfile:
            self.sublayers = pickle.load(tfile)

            tfile.close()
        count = 0
        total = len(self.sublayers)
        for k, v in self.sublayers.items():
            self.level_db.put(k, v)
            count +=1
            yield count / total, f"Restoing {count} of {total}"

    def restore_sub(self, _):

        self.canvas.run_operation(self.run_restore, "Restoring Data", "Restoring...")
        self.canvas.renderer.render_world._rebuild()

    def _refresh_chunk(self, _):
        self.set_seed(_)
        self.world.save()
        self.canvas.run_operation(lambda: self.start(_), "Converting chunks", "Starting...")

        if self._save_backup.GetValue():
            self.canvas.run_operation(lambda:
                                      self.save_it(self.save_data), "Saving Data", "Saving...")

        self.world.purge()
        self.canvas.renderer.render_world._rebuild()
        # print(self.donechunks, "The Last Chunk Just If it had an error check it out.")
        wx.MessageBox("If you Had no errors It Worked "
                      "\n Close World and Open in Minecraft", "IMPORTANT",
                      wx.OK | wx.ICON_INFORMATION)

    def get_v_off(self, data):
        version = data[0]
        offset = 3
        self.v_byte = 9
        if version == 8:
            self.v_byte = 8
            offset = 2
        return offset

    def start(self, _):
        if self._all_chunks.GetValue():
            self.all_chunks = [x for x in self.world.level_wrapper.all_chunk_coords(self.canvas.dimension)]
        else:
            self.all_chunks = self.canvas.selection.selection_group.chunk_locations()
        #self.all_chunks = [(4, 119)]
        total = len(self.all_chunks)
        count = 0
        loaction_dict = collections.defaultdict(list)
        if self.world.level_wrapper.platform == "java":

            for xx, zz in self.all_chunks:
                rx, rz = world_utils.chunk_coords_to_region_coords(xx, zz)
                loaction_dict[(rx, rz)].append((xx, zz))

            for rx, rz in loaction_dict.keys():
                file_exists = exists(self.get_dim_vpath_java_dir(rx, rz))
                # self.world.level_wrapper.root_tag['Data']['DataVersion'] = amulet_nbt.TAG_Int(2860)
                # self.world.level_wrapper.root_tag['Data']['Version'] = amulet_nbt.TAG_Compound(
                #     {"Snapshot": amulet_nbt.TAG_Byte(0), "Id": amulet_nbt.TAG_Int(2860),
                #      "Name": amulet_nbt.TAG_String("1.18.0")})
                # self.world.save()
                if file_exists:
                    self.raw_data = AnvilRegion(self.get_dim_vpath_java_dir(rx, rz))

                    for di in loaction_dict[(rx, rz)]:
                        cx, cz = di
                        count += 1


                        if self.raw_data.has_chunk(cx % 32, cz % 32):
                            self.nbtdata = self.raw_data.get_chunk_data(cx % 32, cz % 32)


                            if self.nbtdata['sections']:  # [0]['block_states']['palette']:
                                if self.nbtdata.get('isLightOn'):
                                    self.nbtdata.pop("isLightOn")
                                #nbtdata.pop('PostProcessing')
                                if self.nbtdata.get('Heightmaps'):
                                    self.nbtdata.pop('Heightmaps')# = amulet_nbt.TAG_Compound({})
                                self.nbtdata['Status'] = amulet_nbt.TAG_String("empty")
                                if self.world.level_wrapper.root_tag['Data']['DataVersion'].value <= 2860:
                                    self.nbtdata['blending_data'] = amulet_nbt.TAG_Compound(
                                        {"old_noise": amulet_nbt.TAG_Byte(1)})
                                elif self.world.level_wrapper.root_tag['Data']['DataVersion'].value > 2860:
                                    self.nbtdata['blending_data'] = amulet_nbt.TAG_Compound(
                                    {"max_section": amulet_nbt.TAG_Int(16),"min_section": amulet_nbt.TAG_Int(0)})
                                if self.regen_below:
                                    self.nbtdata['below_zero_retrogen'] = amulet_nbt.TAG_Compound({
                                                'target_status': amulet_nbt.TAG_String('heightmaps'),
                                                'missing_bedrock': amulet_nbt.TAG_Long_Array([])})

                                # revove_list = numpy.array()
                                revove_list = [sec for sec in self.nbtdata['sections'] if sec.get('Y') < 0 or sec.get('Y') > 15]
                                for r in revove_list:
                                    self.nbtdata['sections'].remove(r)
                                for i, sec in enumerate(self.nbtdata['sections']):
                                    if sec.get('SkyLight'):
                                        sec.pop('SkyLight')
                                    if sec.get('BlockLight'):
                                        sec.pop('BlockLight')
                                    # if sec.get('Y') < 0 or sec.get('Y') > 15:
                                    #     revove_list.append(sec)
                                    # else:






                                # # print(sec.get('SkyLight'))
                                        #if (sec.get('SkyLight') is not None) and (16 > sec.get('Y').value > 0):
                                # if self.nbtdata['sections'][i].get('SkyLight'):
                                #     self.nbtdata['sections'][i].pop('SkyLight')
                                # if self.nbtdata['sections'][i].get('BlockLight'):
                                #     self.nbtdata['sections'][i].pop('BlockLight')
                                #     try:
                                #         self.nbtdata['sections'][i].pop('SkyLight')
                                #     except:
                                #         pass
                                #     try:
                                #         self.nbtdata['sections'][i].pop('BlockLight')
                                #     except:
                                #         pass

                                    #if "NoneType" not in str(type(sec.get('SkyLight'))):
                                    #if isinstance(sec.get('SkyLight'), amulet_nbt.TAG_Byte_Array):
                                    #print(dir(sec))


                                    #     if 'SkyLight' in str(sec):
                                    #     self.nbtdata['sections'][i].pop('SkyLight')
                                    # if 'BlockLight' in str(sec):
                                    #     self.nbtdata['sections'][i].pop('BlockLight')

                                # try:
                                #     nbtdata['sections'][i].pop('biomes')
                                # except:
                                #     pass

                                    #nbtdata['sections'][i].pop('SkyLight')






                        yield count / total, f"On Region: {rx, rz} ....On Chunk:{cx % 32, cz % 32}, {count} of {total}"
                        self.raw_data.put_chunk_data(cx % 32, cz % 32, self.nbtdata)

                    self.raw_data.save()



        else:    #BEDROCK
            try:
                self.level_db.delete(b'LevelChunkMetaDataDictionary')
            except Exception as e:
                print("B", e)

            for xx, zz in self.all_chunks:
                count += 1
                chunkkey = struct.pack('<ii', xx, zz)
                try:  # TODO check all and make sure they are needed
                    self.level_db.put(chunkkey + b';', b'')
                except Exception as e:
                    print("A", e)
                try:
                    self.level_db.put(chunkkey + b'\x2c', b'\x16')  # NEEDED ?
                except Exception as e:
                    print("C", e)
                try:
                    self.level_db.delete(chunkkey + b'@')  # ?
                except Exception as e:
                    print("D", e)
                try:
                    self.level_db.delete(chunkkey + b'?')  # ?
                except Exception as e:
                    print("E", e)
                try:
                    self.level_db.delete(chunkkey + b'A')  # ?
                except Exception as e:
                    print("F", e)
                test = []
                subchunks = {}
                chunk_data = {}
                heigh_next_layer = []
                self.donechunks = []

                new_air = amulet_nbt.from_snbt(
                    '{name: "minecraft:air", states: {}, version: 17879555}')
                new_block = amulet_nbt.from_snbt(
                    '{name: "minecraft:bedrock", states: {"infiniburn_bit": 0b}, version: 17879555}')
                for k, v in self.world.level_wrapper.level_db.iterate(start=chunkkey + b'\x2f\x00',
                                                                      end=chunkkey + b'\x2f\xff\xff'):
                    #print(v[0], "version")
                    self.v_byte = v[0]
                    if v[0] > 8:
                        chunk_data[struct.unpack('b', k[-1::])[0]] = v
                    if self._save_backup.GetValue():
                        if v[0] > 8:
                            if struct.unpack('b', k[-1::])[0] <= 0: #240, 0, 1584
                                self.save_data[k] = v

                self.donechunks.append(
                    (xx, zz, "CHUNK !!!!!", world_utils.chunk_coords_to_block_coords(xx, zz), self.v_byte))
                key_s = [k for k in sorted(chunk_data.keys(), reverse=False)]
                self.height = numpy.frombuffer(numpy.zeros(512, 'b'), "<i2").reshape((16, 16))
                for y_ld in key_s.copy():
                    if y_ld < 0:
                        self.level_db.delete(chunkkey + b'/' + struct.pack('b', y_ld))
                        key_s.remove(y_ld)
               # min_y, max_y = key_s[-1], key_s[0]
                if 0 not in chunk_data: #Build the chunk
                    if self.v_byte >= 8:
                        header_e = struct.pack('bbbb', self.v_byte, 1, 0,0)
                    else:
                        header_e = struct.pack('bbb', self.v_byte, 1, 0)#
                    new_raw_block = amulet_nbt.NBTFile(new_air).save_to(compressed=False, little_endian=True)
                    chunk_data[0] = header_e  + new_raw_block
                only_needed_ylevel = (0,)
                for y_h in chunk_data:
                    if self.v_byte > 8:
                        v_off = self.get_v_off(chunk_data[y_h])
                        blocks, block_bits, extra_blk, extra_blk_bits = self.get_pallets_and_extra(
                            chunk_data[y_h][v_off:])
                        for x in range(16):
                            for z in range(16):
                                for y in range(16):
                                    # self.height[z][x] = (y + 1) + (y_h * 16) + 64
                                    if "minecraft:air" not in str(blocks[block_bits[x][y][z]]):
                                        self.height[z][x] = (y+1) + (y_h * 16) + 64
                                        #print((y+1) + (y_h * 16) + 64)
                                        # else:
                                        #     self.height[z][x] = (y + 1) + (
                                        #             y_h * 16)
                for y_level in only_needed_ylevel:
                    if self.v_byte > 8:
                        v_off = self.get_v_off(chunk_data[y_level])
                        blocks, block_bits, extra_blk, extra_blk_bits = self.get_pallets_and_extra(
                            chunk_data[y_level][v_off:])

                        for x in range(16):
                            for z in range(16):
                                for y in range(16):
                                    yy = y + (16 * (y_level))
                                    if (x, yy, z) == (x, 0, z):
                                        if new_block in blocks:
                                            inx = blocks.index(new_block)
                                        else:
                                            inx = numpy.amax(block_bits) + 1
                                            blocks.append(new_block)
                                        block_bits[x][y][z] = inx
                        # y + (16 * (key_s.index(y_level) + 1) - 15)
                        final_data = b''.join(self.back_2_raw(block_bits, blocks, extra_blk_bits, extra_blk, y_level))
                        b_layer = struct.pack('b', y_level)
                        self.world.level_wrapper.level_db.put(chunkkey + b'/' + b_layer, final_data)

                #biome_key = b''
                # if self.v_byte == 9:
                #     biome_key = b'+'
                # else:
                #     biome_key = b'-'
                biome_key = b'+'
                #print(xx, zz, "CHUNK !!!!!", world_utils.chunk_coords_to_block_coords(xx,zz), self.v_byte)
                if self.v_byte > 8:
                    try:
                        # print('Before ', self.world.level_wrapper.level_db.get(chunkkey + biome_key)[:512])
                        biome = self.world.level_wrapper.level_db.get(chunkkey + biome_key)[512:]
                        height = self.height.tobytes()
                        self.world.level_wrapper.level_db.put(chunkkey + biome_key, height + biome)
                        # print(height, biome_key)
                        # print("EERRE no + key")
                    except:
                        # print("EERRE no + key")
                        pass

                    # # print("EERRE no - key")
                    # biome_key = b'-'
                    # try:
                    #     biome = self.world.level_wrapper.level_db.get(chunkkey + biome_key)[512:]
                    #     height = self.height.tobytes()
                    #     self.world.level_wrapper.level_db.put(chunkkey + biome_key, height + biome)
                    #     # print(height, biome_key)
                    # except:
                    #     # print("EERRE no - key")
                    # pass
            yield count / total, f"Chunk: {xx, zz} Done.... {count} of {total}"






    def get_dim_vpath_java_dir(self, regonx,regonz):
        file =  "r." + str(regonx) + "." + str(regonz) + ".mca"
        path = self.world.level_wrapper.path
        full_path = ''
        if 'minecraft:the_end' in self.canvas.dimension:
            dim = 'DIM1'
        elif 'minecraft:the_nether' in self.canvas.dimension:
            dim = 'DIM-1'
        elif 'minecraft:overworld' in self.canvas.dimension:
            dim = ''
        version = "region"
        full_path =  os.path.join(path,dim,version,file)
        return full_path

    def cal_height_map(self, data):
        return numpy.frombuffer(data[:512], "<i2").reshape((16, 16))

    def back_2_raw(self, lay_one, pal_one, lay_two, pal_two, y_level):
        block_list = []
        byte_blocks = []
        bytes_nbt = []
        pal_len = []
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
                raw += amulet_nbt.NBTFile(rnbt).save_to(compressed=False, little_endian=True)
            bytes_nbt.append(raw)
            raw = b''
            for rnbt in pal_two:
                raw += amulet_nbt.NBTFile(rnbt).save_to(compressed=False, little_endian=True)
            bytes_nbt.append(raw)
        else:
            block_list = [lay_one]
            pal_len = [len(pal_one)]
            raw = b''
            for rnbt in pal_one:
                raw += amulet_nbt.NBTFile(rnbt).save_to(compressed=False, little_endian=True)
            bytes_nbt.append(raw)
        for ii, b in enumerate(block_list):
            bpv = max(int(numpy.amax(b)).bit_length(), 1)
            if bpv == 7:
                bpv = 8
            elif 9 <= bpv <= 15:
                bpv = 16
            if ii == 1:
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

        return byte_blocks



    def get_pallets_and_extra(self, raw_sub_chunk):

        block_pal_dat, block_bits, bpv = self.get_blocks(raw_sub_chunk)
        if bpv < 1:
            pallet_size = 1
            pallet_size, pallet_data, off = 1, block_pal_dat, 0
        else:
            pallet_size, pallet_data, off = struct.unpack('<I', block_pal_dat[:4])[0], block_pal_dat[4:], 0
        blocks = []
        block_pnt_bits = block_bits
        extra_block = None
        extra_pnt_bits = None

        for x in range(pallet_size):
            nbt, p = amulet_nbt.load(pallet_data, little_endian=True, offset=True)
            pallet_data = pallet_data[p:]
            blocks.append(nbt.value)

        extra_blocks = []
        if pallet_data:
            block_pal_dat, extra_block_bits, bpv = self.get_blocks(pallet_data)
            if bpv < 1:
                pallet_size = 1
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
        #print(bpv)
        if bpv > 0:
            bpw = (32 // bpv)
            wc = -(-4096 // bpw)
            buffer = numpy.frombuffer(bytes(reversed(rawdata[: 4 * wc])), dtype="uint8")
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


export = dict(name="Force_Blending v1.09", operation=ForceHeightUpdate) #By PremiereHell

