import collections
import math
import struct

import wx
from amulet.api.block_entity import BlockEntity
from amulet.api.block import Block
from typing import TYPE_CHECKING, Type, Any, Callable, Tuple, BinaryIO, Optional, Union
from amulet.utils import world_utils
from amulet.api.selection import SelectionGroup
from amulet.api.selection import SelectionBox
from amulet.utils import block_coords_to_chunk_coords
from amulet_map_editor.programs.edit.api.operations import DefaultOperationUI
from amulet_map_editor.api.wx.ui.base_select import BaseSelect
from amulet.api.errors import ChunkDoesNotExist
import amulet_nbt
import numpy

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
        self._sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self._sizer)
        side_sizer = wx.BoxSizer(wx.VERTICAL)
        self._sizer.Add(side_sizer)
        self._run_button = wx.Button(self, label="Convert Chunks to 1.17")
        self.setup = wx.Button(self, label="(Save new seed)")
        self.seed_input = wx.TextCtrl(self, style=wx.TE_LEFT, size=(120, 25))
        if self.seed_input.GetValue() == "":
            self.seed_input.SetValue(str(self.world.level_wrapper.root_tag['RandomSeed'])[:-1])
        self.label = wx.StaticText(self, label="SEED")
        self._run_button.Bind(wx.EVT_BUTTON, self._refresh_chunk)
        self.setup.Bind(wx.EVT_BUTTON,self.set_world_version)
        side_sizer.Add(self._run_button, 10, wx.TOP | wx.LEFT, 5)
        side_sizer.Add(self.seed_input, 10, wx.TOP | wx.LEFT, 5)
        side_sizer.Add(self.label, 10, wx.TOP | wx.LEFT, 5)
        side_sizer.Add(self.setup, 10, wx.TOP | wx.LEFT, 5)
        self.Layout()
        self.Thaw()

    @property
    def wx_add_options(self) -> Tuple[int, ...]:
        return (0,)

    def _cls(self):
        print("\033c\033[3J", end='')
    def set_world_version(self, _):
        self.world.level_wrapper.root_tag['FlatWorldLayers'] = amulet_nbt.TAG_String("null")
        self.world.level_wrapper.root_tag['InventoryVersion'] = amulet_nbt.TAG_String("1.17.11")
        i1 = amulet_nbt.TAG_Int(1)
        i2 = amulet_nbt.TAG_Int(17)
        i3 = amulet_nbt.TAG_Int(11)
        i4 = amulet_nbt.TAG_Int(1)
        i5 = amulet_nbt.TAG_Int(0)
        self.world.level_wrapper.root_tag['lastOpenedWithVersion'] = amulet_nbt.TAG_List([i1, i2, i3, i4, i5])
        self.world.level_wrapper.root_tag['RandomSeed'] = amulet_nbt.TAG_Long((int(self.seed_input.GetValue())))
        self.world.level_wrapper.root_tag.save()
        self.world.save()
        self.world.purge()
        # if self.world.level_wrapper.version != (1, 17, 11, 1, 0):
        #     wx.MessageBox( "Close and reload within amulet you should see (1,17,11,1,0) at the top."
        #                            "\n  If you see this message you need close and reload the world agian in Amulet\n"
        #                            "you should not see this twice","IMPORTANT", wx.OK | wx.ICON_INFORMATION)


    @property
    def level_db(self):
        level_wrapper = self.world.level_wrapper
        if hasattr(level_wrapper, "level_db"):
            return level_wrapper.level_db
        else:
            return level_wrapper._level_manager._db

    def _run_operation(self, _):
        block_platform = self.world.level_wrapper.platform
        block_version = (1,17,11,1,0)
        # self.xx, self.zz = 0,0
        get_total = [x for x in self.world.level_wrapper.all_chunk_coords(self.canvas.dimension)]
        total = len(get_total)
        count = 0
        prg_max = total
        prg_pre = 0
        prg_pre_th = total / 100
        y_prog = 1 / 100
        y_tot = 0
        self.world.purge()
        cntt = 0
        #custom = [(65, 18)] custom:#
        for xc, xz in self.world.level_wrapper.all_chunk_coords(self.canvas.dimension):
            chunkkey = struct.pack('<ii', xc, xz)
            try:
                self.level_db.put(chunkkey + b'\x2c', b'\x16')
                #pass
                # print(self.level_db.get(chunkkey + b"\x31"), "NNNN")
                # self.level_db.delete(chunkkey + b"+")
            except Exception as e:
                print("eee",e)
            sub_layers = {-4: b'/\xff', -3: b'/\xfe', -2: b'/\xfd', -1: b'/\xfc', 0: b'/\x00', 1: b'/\x01',
                          # ff fe fd fc
                          2: b'/\x02', 3: b'/\x03', 4: b'/\x04', 5: b'/\x05', 6: b'/\x06', 7: b'/\x07', 8: b'/\x08',
                          9: b'/\x09', 10: b'/\x0a', 11: b'/\x0b', 12: b'/\x0c', 13: b'/\x0d', 14: b'/\xfe',
                          15: b'/\x0f',
                          16: b'/\x10', 17: b'/\x20', 18: b'/\x30', 19: b'/\x40', 20: b'/\x50', }
            try:
                for sub_layer in sub_layers.values():
                    if sub_layer == b'/\xff' or sub_layer == b'/\xfe' or sub_layer == b'/\xfd' or sub_layer == b'/\xfc':
                        pass#self.level_db.delete(chunkkey + sub_layer)

                    else: #if sub_layer == b'/\x00':
                        sub_chunk_bytes = self.level_db.get(chunkkey + b"\x31")


                        pallet_nbt_cnk, palletXZYkeys3d, ver, extra_layer = self.chunk_edit(sub_chunk_bytes,
                                                                                    sub_layer, xc, xz)
                        for nbt in pallet_nbt_cnk[(xc, xz, sub_layer)]:
                            nbt['version'] = amulet_nbt.TAG_Int(17879555)
                        if sub_layer == b'/\x00':
                            p_len = len(pallet_nbt_cnk[(xc, xz, sub_layer)])
                            new_block_add = amulet_nbt.NBTFile(
                                amulet_nbt.from_snbt(
                                    '{name: "minecraft:bedrock", states: {"infiniburn_bit": 0b}, version: 17879555}'))
                            if new_block_add not in pallet_nbt_cnk[(xc, xz, sub_layer)]:
                                pallet_nbt_cnk[(xc, xz, sub_layer)].append(new_block_add)
                                for x, z, y, chunk in palletXZYkeys3d:
                                    sim = '\n'
                                    if y == 0:
                                        palletXZYkeys3d[(x, z, y, chunk)] = p_len
                        ver = 8 # force version
                        extra_layer = extra_layer\
                        .replace(b'\x03\x07\x00version\x01\n\x12\x01\x00',b'\x03\x07\x00version\x03\xd2\x10\x01\x00')\
                        .replace(b'\x03\x07\x00version\x03\xd2\x10\x01\x00',b'\x03\x07\x00version\x03\xd2\x10\x01\x00')
                        test = self.compactiion(pallet_nbt_cnk, palletXZYkeys3d, ver, extra_layer)
                        new_raw = [x for x in test][0]

                        #print(sub_chunk_bytes, "OLD" , len(sub_chunk_bytes))
                        #(new_raw, "new", len(new_raw))
                        if sub_chunk_bytes == new_raw:
                        #
                           pass# print('YES')
                        else:
                            print("No0000000000000000000000000000000000000000000000000000000000000000000")
                            print(sub_chunk_bytes, "OLD" , len(sub_chunk_bytes))
                            print(new_raw, "NEW", len(new_raw))
                            print("No0000000000000000000000000000000000000000000000000000000000000000000")
                        #self.level_db.put(chunkkey + sub_layer, new_raw)

            except Exception as e:
                print(e, "error")
            self.world.get_chunk(xc, xz, self.canvas.dimension).cnk_chng = True
            if count >= prg_pre_th:
                y_tot += y_prog
                prg_pre_th += total / 100
                yield y_tot, f"Chunk: {xc, xz} Done.... {count} of {total}"
            count += 1


    def make_raw_nbt(self, tag_name, value):

        name_pay = struct.pack('<H', len(tag_name.encode()))
        name = tag_name.encode()
        val_pay = b''
        val = b''
        if isinstance(str, value):
            val_pay = struct.pack('<H', len(value.encode()))
            val = value.encode()
        pass

    def chunk_edit(self, chunk_data, sub_l, xc , xz):
        print(chunk_data)
        count = 0
        self.palletXZYkeys3d = collections.defaultdict(int)
        self.pallet_nbt_cnk = collections.defaultdict(list)
        self.raw_test = collections.defaultdict(list)
        sub_chunk_bytes = chunk_data
        current_sub_l = sub_l
        self.ver = sub_chunk_bytes[0]
        indx_for_bits = 0
        ver_offset = 0
        print("VERSION BYTE", self.ver)
        if self.ver == 8:
            ver_offset = 3
            indx_for_bits = 2
        elif self.ver == 9:
            ver_offset = 4
            indx_for_bits = 3

        BitsPerBlock = struct.unpack("b",sub_chunk_bytes[indx_for_bits:indx_for_bits+1])[0] >> 1  # 1.17 2 and 18 + = 3
        BlocksBitsPerWord = 32 // BitsPerBlock  # (32 // BitsPerBlock) #m
        paading = 0
        if BitsPerBlock == 3 or BitsPerBlock == 5 or BitsPerBlock == 6:
            paading = 4
        WordCount = -(-4096 // BlocksBitsPerWord) + paading
        bit_p_size = (WordCount * 4) + paading


        block = 0
        pos = 0
        word_step = 0
        word_steper = -(-4096 // bit_p_size)
        #print(word_steper, bit_p_size, "STEPPER")
        cnt = 0

        words_bytes = sub_chunk_bytes[ver_offset:bit_p_size + ver_offset]  # [3:bit_p_size 1.17
        pallet_size = struct.unpack('<I', sub_chunk_bytes[ver_offset + bit_p_size + paading:ver_offset + bit_p_size + 4 + paading])[0]
        pallet_raw_nbt = (sub_chunk_bytes[ver_offset + bit_p_size + 4 + paading:]) # x03\x07\x00version\x01\n\x12\x01\x00  OLD      # )[bit_p_size+7:] 1.17

        bx, bz = world_utils.chunk_coords_to_block_coords(xc, xz)
        point = len(pallet_raw_nbt) - 1
        pos = 0
        tag_ = b'\n\x00\x00\x08\x04\x00name'
        pal_stop = 0
        pal_end_size = 0

        import re
        print("SUB CHUNK",current_sub_l)
        for match in re.finditer(tag_, pallet_raw_nbt):
            start = match.start()
            self.pallet_nbt_cnk[(xc, xz, current_sub_l)].append(amulet_nbt.load(pallet_raw_nbt[start:]
                                                                        ,compressed=False,little_endian=True))
            pal_stop += 1
            if pallet_size == pal_stop: # if there is a second block layor
                pal_end_size = start + len(self.pallet_nbt_cnk[(xc, xz, current_sub_l)][pal_stop-1]
                                           .save_to(compressed=False,little_endian=True))
                break
        extra_layer = pallet_raw_nbt[pal_end_size:]
        pos = 0
        text_data = ''
        total_test = 0
        while cnt < (WordCount):  # (   bx+ (position  >> 8 & 0xF) , bz + (position >> 4 & 0xF)  ,(position & 0xF)  ) raal
            word = int.from_bytes(words_bytes[word_step:word_step + 4], "little", signed=False)
            for block in range(BlocksBitsPerWord):

                state = ((word >> ((pos % BlocksBitsPerWord) * BitsPerBlock)) & ((1 << BitsPerBlock) - 1))
                self.palletXZYkeys3d[
                    ((pos >> 8 & 0xF), (pos >> 4 & 0xF), (pos & 0xF), (xc, xz, current_sub_l))] = state
                text_data += str(state) + '  '

                # if pos == 4097:
                #     break
                pos += 1
                block += 1
               # print("State", state)
            word_step += 4
            cnt += 1
        #print(text_data, xc, xz, current_sub_l)

        print("WTF", BitsPerBlock, BlocksBitsPerWord, "PADDING", paading, "PAL", pallet_size)
        print("cnt", cnt, total_test,"total_test", "POS", pos, "total", cnt*BlocksBitsPerWord)
        return self.pallet_nbt_cnk, self.palletXZYkeys3d, self.ver, extra_layer

    def _refresh_chunk(self, _):

        self.canvas.run_operation(lambda: self._run_operation(_),"Filling Y_Zero with bedrock", "Starting...")
        wx.MessageBox("It Worked"
                      "\n Close World and Open in Minecraft", "IMPORTANT",
                      wx.OK | wx.ICON_INFORMATION)
        self.world.purge()

    def compactiion(self, pallet_s, xyz_l_k , ver, extra_layer):
        chunk = ""
        for x, z, y, chunk in self.palletXZYkeys3d:
            chunk = chunk
            break
        p_l = len(pallet_s[chunk])
        bpv = max(p_l.bit_length(), 1)
        if bpv == 7:
            bpv = 8
        elif 9 <= bpv <= 15:
            bpv = 16
        pallet_type_bpb = bytes([bpv << 1])
        pos = 0
        thebytes = b''
        b_inx_v = 0
        blocks_bpw = 32 // bpv
        # WordCount = math.ceil(4096.0 / blocks_bpw)
        BlocksBitsPerWord = 32 // bpv  # (32 // BitsPerBlock) #m
        WordCount =  -(-4096 // BlocksBitsPerWord)
        bit_p_size = (WordCount * 4)
        block = 0
        pos = 0
        word_step = 0
        #word_steper = -(bit_p_size // )
        wcnt = 0

        paading = b''
        # if bpv == 3 or bpv == 5 or bpv == 6:
        #     paading = b'\x00\x00\x00\x00'
        while wcnt < (WordCount):
            for w in range(BlocksBitsPerWord):
                #print(xyz_l_k[((pos >> 8 & 0xF), (pos >> 4 & 0xF), (pos & 0xF), chunk)] , "BOCK")((1 >> bpv) 1) &
                b_inx_v += ((xyz_l_k[((pos >> 8 & 0xF), (pos >> 4 & 0xF), (pos & 0xF), chunk)]) <<  (pos % BlocksBitsPerWord) * bpv)
                pos += 1

            #if b_inx_v.to_bytes(4, 'little', signed=False) != b'\x00\x00\x00\x00':
            thebytes += b_inx_v.to_bytes(4, 'little', signed=False)
            #thebytes += b"\xff"
            #print(b_inx_v.to_bytes(4, 'little', signed=False), "Bytes")
            b_inx_v = 0
            wcnt +=1
            # if pos == 4096:
            #     thebytes += b_inx_v.to_bytes(4, 'little', signed=False)
            #     b_inx_v = 0
            # print(pos)
        sub_l = b''
        if ver == 9:
            sub_l = chunk[2]
        raw_nbt_pallet =b''
        layers = b'\x01'
        if extra_layer != b'':
            layers = b'\x02'
        for nbt in pallet_s[chunk]:
            raw_nbt_pallet += nbt.save_to(compressed=False, little_endian=True)
        # print(struct.pack('B',ver),layers,sub_l.replace(b'/',b''), pallet_type_bpb,
        #                 thebytes, struct.pack('<I',len(pallet_s[chunk])), raw_nbt_pallet, extra_layer)
        print(bpv, "bpv", "PALS", p_l, "Bytes Struck",struct.pack('<I',len(pallet_s[chunk])), "new pos", pos)
        yield b''.join([struct.pack('B',ver),layers,sub_l.replace(b'/',b''), pallet_type_bpb,
                        thebytes + paading, struct.pack('<I',pallet_type_bpb), raw_nbt_pallet, extra_layer])


export = dict(name="Force negitive Y Refresh and Blending v1.11", operation=ForceHeightUpdate) #By PremiereHell


# def py_str(self) -> str:
#     string_decoded = ''
#     try:
#         string_decoded = self.py_bytes.decode('utf-8')
#     except UnicodeDecodeError as err:
#         try:
#             string_decoded = decode_modified_utf8(self.py_bytes)
#         except UnicodeDecodeError as err:
#             string_decoded = self.py_bytes.decode(errors="escapereplace")
#     return string_decoded

