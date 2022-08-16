#By PremiereHell  ,
# Thanks To StealthyX https://github.com/StealthyExpertX/Amulet-Plugins
# For Getting me started on this, He provided some code that got me started on this.
import math
import time
import struct
from amulet_map_editor.programs.edit.api.events import (
    EVT_SELECTION_CHANGE,
)
import amulet_nbt
import wx
import collections
import os
from os.path import exists
import numpy
import uuid
from amulet.api.block_entity import BlockEntity
from amulet.api.block import Block
from typing import TYPE_CHECKING, Type, Any, Callable, Tuple, BinaryIO, Optional, Union
from amulet.utils import world_utils
from amulet_map_editor.api.opengl.camera import Projection
from amulet_map_editor.programs.edit.api.behaviour import BlockSelectionBehaviour
from amulet.api.selection import SelectionGroup
from amulet.api.selection import SelectionBox
from amulet.utils import block_coords_to_chunk_coords
from amulet.level.formats.anvil_world.region import AnvilRegion
from amulet_map_editor.programs.edit.api.operations import DefaultOperationUI
from amulet_map_editor.api.wx.ui.base_select import BaseSelect
from amulet.api.errors import ChunkDoesNotExist
import amulet_nbt as Nbt

if TYPE_CHECKING:
    from amulet.api.level import BaseLevel
    from amulet_map_editor.programs.edit.api.canvas import EditCanvas


class BedRock(wx.Panel):
    def __int__(self, world, canvas):
        wx.Panel.__init__(self, parent)
        self.world = world
        self.canvas = canvas

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
                                nbt = self.nbt_loder(raw)
                            except:
                                nbt = Nbt.from_snbt(raw)
                            name = str(nbt['identifier']).replace("minecraft:", "")
                            if exclude_filter != [''] or include_filter != ['']:
                                if name not in exclude_filter:
                                    self.lstOfE.append(name)
                                    self.EntyData.append(nbt.to_snbt(1))
                                    self.Key_tracker.append(x)
                                if name in include_filter:
                                    self.lstOfE.append(name)
                                    self.EntyData.append(nbt.to_snbt(1))
                                    self.Key_tracker.append(x)
                            else:
                                self.lstOfE.append(name)
                                self.EntyData.append(nbt.to_snbt(1))
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
        except amulet.api.errors.ChunkDoesNotExist:
            responce = self.con_boc("Chuck Error", "Empty chunk selected, \n Continue any Ways?")
            if responce:
                print("Exiting")
                return
            else:
                pass
        if "[((0, 0, 0), (0, 0, 0))]" == str(selection):
            responce = self.con_boc("No selection",
                                    "All Entities will be deleted in " + str(self.canvas.dimension) + " \n Continue?")
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
            self._load_entitie_data(event,False,True)
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
                        print(e)

            for pkey in prefixList:
                self.level_db.delete(pkey)
            for pdig_d in pdig_to_delete:
                self.level_db.delete(pdig_d)
        else:
            for x, z in all_chunks:
                if (x,z) not in selected:
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
                    format = Nbt.from_snbt(data)
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
                        EntyD, p = Nbt.load(chunk[b'2'][pointer:], little_endian=True, offset=True)
                        pointer += p
                        self.EntyData.append(EntyD)

            if len(self.EntyData) > 0:
                for elist in self.EntyData:
                    snbt_line_list += elist.to_snbt() + "\n"

        res = EntitiePlugin.save_entities_export(self,snbt_line_list)
        if res == False:
            return
        EntitiePlugin.Onmsgbox(self,"Export", "Saved")

    def _export_nbt(self, _):
        entities = amulet_nbt.TAG_List()
        blocks = amulet_nbt.TAG_List()
        palette = amulet_nbt.TAG_List()
        DataVersion = amulet_nbt.TAG_Int(2975)
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
                    palette_Properties = amulet_nbt.TAG_Compound(
                        {'Properties': amulet_nbt.from_snbt(str(block.properties)),
                         'Name': amulet_nbt.TAG_String(block.namespaced_name)})
                    palette.append(palette_Properties)
                state = pallet_key_map[(block.namespaced_name, str(block.properties))]

                if blockEntity == None:
                    blocks_pos = amulet_nbt.TAG_Compound({'pos': amulet_nbt.TAG_List(
                        [amulet_nbt.TAG_Int(b[0]), amulet_nbt.TAG_Int(b[1]),
                         amulet_nbt.TAG_Int(b[2])]), 'state': amulet_nbt.TAG_Int(state)})
                    blocks.append(blocks_pos)
                else:
                    blocks_pos = amulet_nbt.TAG_Compound({'nbt': amulet_nbt.from_snbt(blockEntity.nbt.to_snbt()),
                                                          'pos': amulet_nbt.TAG_List(
                                                              [amulet_nbt.TAG_Int(b[0]),
                                                               amulet_nbt.TAG_Int(b[1]),
                                                               amulet_nbt.TAG_Int(b[2])]),
                                                          'state': amulet_nbt.TAG_Int(state)})
                    blocks.append(blocks_pos)
        prg_pre = 99
        self.prog.Update(prg_pre, "Finishing Up " + str(i) + " of " + str(prg_max))
        size = amulet_nbt.TAG_List([amulet_nbt.TAG_Int(mx), amulet_nbt.TAG_Int(my), amulet_nbt.TAG_Int(mz)])

        save_it = amulet_nbt.NBTFile()
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
            nbt = amulet_nbt.load(pathto, compressed=True, little_endian=False, )
            block_platform = "java"
            block_version = (1, 18, 0)
            b_pos = []
            palette = []
            Name = []
            enbt = []
            xx = self.canvas.selection.selection_group.min_x
            yy = self.canvas.selection.selection_group.min_y
            zz = self.canvas.selection.selection_group.min_z
            if True:
                reps = EntitiePlugin.con_boc(self, "Air Blocks", 'Do you want to encude air block?')
                for x in nbt.get('blocks'):
                    if nbt['palette'][int(x.get('state'))].get('Properties') != None:
                        palette.append(
                            dict(amulet_nbt.from_snbt(nbt['palette'][int(x.get('state'))]['Properties'].to_snbt())))
                    else:
                        palette.append(None)
                    b_pos.append(x.get('pos'))
                    Name.append(nbt['palette'][int(x.get('state'))]['Name'])
                    if x.get('nbt') != None:
                        name = str(nbt['palette'][int(x.get('state'))]['Name']).split(':')

                        blockEntity = BlockEntity(name[0], name[1].replace('_', '').capitalize(), 0, 0, 0,
                                                  amulet_nbt.NBTFile(x.get('nbt')))
                        enbt.append(blockEntity)
                    else:
                        enbt.append(None)
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
                for x in nbt.get('entities'):
                    if str(x) != '':
                        e_nbt = x.get('nbt')
                        nxx, nyy, nzz = x.get('pos').value
                        if 'Float' in str(type(nxx)):
                            x['nbt']['Pos'] = amulet_nbt.TAG_List([amulet_nbt.TAG_Float(float(nxx + xx)),
                                                                   amulet_nbt.TAG_Float(float(nyy + yy)),
                                                                   amulet_nbt.TAG_Float(float(nzz + zz))])
                        if 'Double' in str(type(nxx)):
                            x['nbt']['Pos'] = amulet_nbt.TAG_List([amulet_nbt.TAG_Double(float(nxx + xx)),
                                                                   amulet_nbt.TAG_Double(float(nyy + yy)),
                                                                   amulet_nbt.TAG_Double(float(nzz + zz))])
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

        entities = amulet_nbt.TAG_List()
        selection = self.canvas.selection.selection_group.to_box()
        for o, n in zip(selection, rpos):
            mapdic[o] = n
        chunk_min, chunk_max = self.canvas.selection.selection_group.min, \
                               self.canvas.selection.selection_group.max
        min_chunk_cords, max_chunk_cords = block_coords_to_chunk_coords(chunk_min[0], chunk_min[2]), \
                                           block_coords_to_chunk_coords(chunk_max[0], chunk_max[2])
        if self.world.level_wrapper.platform == "bedrock":
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
                        actor = self.level_db.get(key)
                        nbt_data = amulet_nbt.load(actor, compressed=False, little_endian=True)
                        pos = nbt_data.get("Pos")
                        x, y, z = math.floor(pos[0]), math.floor(pos[1]), math.floor(pos[2])

                        if (x, y, z) in selection:
                            nbt_entitie = amulet_nbt.TAG_List()
                            new_pos = mapdic[(x, y, z)]
                            nbt_pos = amulet_nbt.TAG_List(
                                [amulet_nbt.TAG_Float(sum([new_pos[0],
                                                           math.modf(abs(nbt_data.get("Pos")[0].value))[0]])),
                                 amulet_nbt.TAG_Float(sum([new_pos[1],
                                                           math.modf(abs(nbt_data.get("Pos")[1].value))[0]])),
                                 amulet_nbt.TAG_Float(sum([new_pos[2],
                                                           math.modf(abs(nbt_data.get("Pos")[2].value))[0]]))])

                            nbt_block_pos = amulet_nbt.TAG_List([amulet_nbt.TAG_Int(new_pos[0]),
                                                                 amulet_nbt.TAG_Int(new_pos[1]),
                                                                 amulet_nbt.TAG_Int(new_pos[2])])
                            nbt_data.pop('internalComponents')
                            nbt_data.pop('UniqueID')
                            nbt_nbt = amulet_nbt.from_snbt(nbt_data.to_snbt())
                            main_entry = amulet_nbt.TAG_Compound()
                            main_entry['nbt'] = nbt_nbt
                            main_entry['blockPos'] = nbt_block_pos
                            main_entry['pos'] = nbt_pos
                            entities.append(main_entry)
                return entities

            elif self.world.level_wrapper.version < (1, 18, 30, 4, 0):

                entitie = amulet_nbt.TAG_List()
                for cx, cz in self.canvas.selection.selection_group.chunk_locations():
                    chunk = self.world.level_wrapper.get_raw_chunk_data(cx, cz, self.canvas.dimension)
                    if chunk.get(b'2') != None:
                        max = len(chunk[b'2'])
                        cp = 0

                        while cp < max:
                            nbt_data, p = amulet_nbt.load(chunk[b'2'][cp:], little_endian=True, offset=True)
                            cp += p
                            pos = nbt_data.get("Pos")
                            print(nbt_data.get('identifier'), selection.blocks)
                            x, y, z = math.floor(pos[0]), math.floor(pos[1]), math.floor(pos[2])
                            print((x, y, z) in selection)
                            if (x, y, z) in selection:
                                new_pos = mapdic[(x, y, z)]
                                nbt_pos = amulet_nbt.TAG_List(
                                    [amulet_nbt.TAG_Float(sum([new_pos[0],
                                                               math.modf(abs(nbt_data.get("Pos")[0].value))[0]])),
                                     amulet_nbt.TAG_Float(sum([new_pos[1],
                                                               math.modf(abs(nbt_data.get("Pos")[1].value))[0]])),
                                     amulet_nbt.TAG_Float(sum([new_pos[2],
                                                               math.modf(abs(nbt_data.get("Pos")[2].value))[0]]))])
                                nbt_block_pos = amulet_nbt.TAG_List([amulet_nbt.TAG_Int(new_pos[0]),
                                                                     amulet_nbt.TAG_Int(new_pos[1]),
                                                                     amulet_nbt.TAG_Int(new_pos[2])])
                                nbt_data.pop('internalComponents')
                                nbt_data.pop('UniqueID')
                                nbt_nbt = amulet_nbt.from_snbt(nbt_data.to_snbt())
                                main_entry = amulet_nbt.TAG_Compound()
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
                    print(xc, zc)
                    world_count = int(str(self.world.level_wrapper.root_tag.get('worldStartCount')).replace('L', ''))
                    start_count = 4294967295 - world_count
                    entcnt += 1
                    actorKey = struct.pack('>LL', start_count, entcnt)
                    put_key = b''.join([b'actorprefix', actorKey])
                    digp = b''.join([b'digp', struct.pack('<ii', xc, zc), self.get_dim_value_bytes()])
                    try:
                        print(self.level_db.get(digp))
                        new_digp = self.level_db.get(digp)
                        print(self.level_db.get(digp))
                    except:
                        new_digp = b''
                    try:
                        new_actor = self.level_db.get(put_key)
                    except:
                        new_actor = b''
                    new_digp += actorKey
                    new_actor += amulet_nbt.NBTFile(x).save_to(compressed=False, little_endian=True)
                    self.level_db.put(put_key, new_actor)
                    self.level_db.put(digp, new_digp)

            elif self.world.level_wrapper.version < (1, 18, 30, 4, 0):
                for x in entities_list:
                    xc, zc = block_coords_to_chunk_coords(x.get('Pos')[0], x.get('Pos')[2])
                    chunk = self.world.level_wrapper.get_raw_chunk_data(xc, zc, self.canvas.dimension)
                    try:
                        chunk[b'2'] += amulet_nbt.NBTFile(x).save_to(little_endian=True, compressed=False)
                    except:
                        chunk[b'2'] = amulet_nbt.NBTFile(x).save_to(little_endian=True, compressed=False)
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
            anbt = amulet_nbt.load(pathto, compressed=False, little_endian=True)
            sx, sy, sz = anbt.get("structure_world_origin")
            egx, egy, egz = anbt.get("size")
            ex, ey, ez = sx + egx, sy + egy, sz + egz
            group = []
            self.canvas.camera.set_location((sx, 70, sz))
            self.canvas.camera._notify_moved()
            s, e = (int(sx), int(sy), int(sz)), (int(ex), int(ey), int(ez))
            group.append(SelectionBox(s, e))
            sel_grp = SelectionGroup(group)
            self.canvas.selection.set_selection_group(sel_grp)
            for xx in self.canvas.selection.selection_group.blocks:
                for nbtlist in self.actors.values():
                    for nbt in nbtlist:
                        nbtd = amulet_nbt.load(nbt, compressed=False, little_endian=True)
                        x,y,z = nbtd.get('Pos').value
                        ex,ey,ez = math.floor(x),math.floor(y),math.floor(z)
                        if (ex,ey,ez) == xx:
                            print(ex,ey,ez, nbtd.value)
                            anbt['structure']['entities'].append(nbtd.value)
            #nbt_file = amulet_nbt.NBTFile(anbt)
            anbt.save_to(pathto, compressed=False, little_endian=True)
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
                for snbt_line in snbt_loaded_list:
                    nbt_from_snbt = Nbt.from_snbt(snbt_line)
                    cx, cz = block_coords_to_chunk_coords(nbt_from_snbt.get('Pos')[0], nbt_from_snbt.get('Pos')[2])
                    chunk_dict[(cx, cz)].append(nbt_from_snbt)

                d = 0
                for lk_data in chunk_dict.keys():
                    print(lk_data)
                    key = self.build_digp_chunk_key(lk_data[0], lk_data[1])  # build the digp key for the chunk
                    dig_p_dic = {}
                    dig_byte_list = b''

                    for ent_data in chunk_dict[lk_data]:
                        new_prefix = self.build_actor_key(1, ent_cnt)
                        ent_cnt += 1
                        ent_data["UniqueID"] = self._genorate_uid(ent_cnt)
                        try:
                            ent_data['internalComponents']['EntityStorageKeyComponent']['StorageKey'] = \
                                amulet_nbt.TAG_String(new_prefix[len(b'actorprefix'):])
                        except:
                            pass
                        dig_byte_list += new_prefix[len(b'actorprefix'):]
                        final_data = amulet_nbt.NBTFile(ent_data).save_to(compressed=False, little_endian=True)
                        print(new_prefix, final_data)
                        self.level_db.put(new_prefix, final_data)

                    self.level_db.put(key, dig_byte_list)

            else:
                cnt = 0
                for snbt in snbt_loaded_list:
                    nbt_from_snbt = Nbt.from_snbt(snbt)
                    cx, cz = block_coords_to_chunk_coords(nbt_from_snbt.get('Pos')[0], nbt_from_snbt.get('Pos')[2])
                    chunk_dict[(cx, cz)].append(nbt_from_snbt)
                for k in chunk_dict.keys():

                    chunk = b''
                    chunk = self.world.level_wrapper.get_raw_chunk_data(k[0], k[1], self.canvas.dimension)
                    NewRawB = []
                    for ent in chunk_dict[k]:
                        cnt += 1
                        ent["UniqueID"] = self._genorate_uid(cnt)
                        NewRawB.append(Nbt.NBTFile(ent).save_to(compressed=False, little_endian=True))

                    if chunk.get(b'2'):
                        chunk[b'2'] += b''.join(NewRawB)
                    else:
                        chunk[b'2'] = b''.join(NewRawB)

                    self.world.level_wrapper.put_raw_chunk_data(k[0], k[1], chunk, self.canvas.dimension)

            old_start = self.world.level_wrapper.root_tag.get('worldStartCount')
            self.world.level_wrapper.root_tag['worldStartCount'] = Nbt.TAG_Long((int(old_start) - 1))
            self.world.level_wrapper.root_tag.save()
            self.world.save()
            self._set_list_of_actors_digp
            self._load_entitie_data(_, False,False)
            EntitiePlugin.Onmsgbox(self,"Entitie Import", "Complete")
    def _genorate_uid(self, cnt):
        start_c = self.world.level_wrapper.root_tag.get('worldStartCount')
        new_gen = struct.pack('<LL', int(cnt), int(start_c))
        new_tag = Nbt.TAG_Long(struct.unpack('<q', new_gen)[0])
        return new_tag

    def _storage_key_(self, val):
        if isinstance(val, bytes):
            return struct.unpack('>II', val)
        if isinstance(val, Nbt.TAG_String):
            return Nbt.TAG_Byte_Array([x for x in val.py_data])
        if isinstance(val, Nbt.TAG_Byte_Array):
            data = b''
            for b in val: data += b
            return data

    def _move_copy_entitie_data(self, event, copy=False):
        res = EntitiePlugin.important_question(self)
        if res == False:
            return
        try:
            data = Nbt.from_snbt(self.EntyData[self.ui_entitie_choice_list.GetSelection()])
        except:
            data = self.EntyData[self.ui_entitie_choice_list.GetSelection()]
        if data == '':
            EntitiePlugin.Onmsgbox(self,"No Data", "Did you make a selection?")
            return
        x = self._X.GetValue().replace(" X", "")
        y = self._Y.GetValue().replace(" Y", "")
        z = self._Z.GetValue().replace(" Z", "")
        dim = struct.unpack("<i", self.get_dim_value())[0]
        location = Nbt.TAG_List([Nbt.TAG_Float(float(x)), Nbt.TAG_Float(float(y)), Nbt.TAG_Float(float(z))])

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
                new_actor_key = (actor_key[0],max_count_uuid+1)
                new_actor_key_raw = struct.pack('>LL', new_actor_key[0], new_actor_key[1] )
                new_uuid = struct.pack('<LL', max_count_uuid+1, wc )
                data["UniqueID"] = Nbt.TAG_Long(struct.unpack('<q', new_uuid)[0])
                data["Pos"] = location
                key_actor = b''.join([b'actorprefix',new_actor_key_raw])
                key_digp = self.build_digp_chunk_key(cx, cz)
                nx,nz = block_coords_to_chunk_coords(location[0],location[2])
                new_digp_key = self.build_digp_chunk_key(nx, nz)

                if data.get("internalComponents") != None:
                    b_a = []
                    for b in struct.pack('>LL', actor_key[0], max_count_uuid+1 ):
                        b_a.append(Nbt.TAG_Byte(b))
                    tb_arry = Nbt.TAG_Byte_Array([b_a[0],b_a[1],b_a[2],b_a[3],b_a[4],b_a[5],b_a[6],b_a[7]])
                    data["internalComponents"]["EntityStorageKeyComponent"]["StorageKey"] = tb_arry
                if self.world.level_wrapper.version >= (1, 18, 30, 4, 0):
                    try:
                        append_data_key_digp = self.level_db.get(new_digp_key)
                    except:
                        append_data_key_digp = b''
                    append_data_key_digp += new_actor_key_raw
                    self.level_db.put(new_digp_key, append_data_key_digp)
                    self.level_db.put(key_actor, Nbt.NBTFile(data).save_to(compressed=False, little_endian=True)
                            .replace(b'\x07\n\x00StorageKey\x08\x00\x00\x00', b'\x08\n\x00StorageKey\x08\x00'))
                    EntitiePlugin.Onmsgbox(self, "Copy", "Completed")
                    self._finishup(event)
                else:
                    raw_chunk_entitie = Nbt.NBTFile(data).save_to(compressed=False, little_endian=True)
                    raw = self.world.level_wrapper.get_raw_chunk_data(nx, nz, self.canvas.dimension)
                    if raw.get(b'2'):
                        raw[b'2'] += raw_chunk_entitie
                    else:
                        raw[b'2'] = raw_chunk_entitie
                    self.world.level_wrapper.put_raw_chunk_data(nx,nz, raw, self.canvas.dimension)

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
                        new_dpkeys =  b''.join([new_dpkeys, actor_key_raw])
                        for db in range(0, len(dpkeys), 8):
                            akey = dpkeys[db:db + 8]
                            if akey != actor_key_raw:
                                keep.append(akey)
                        dpkeys =  b''.join(keep)
                        self.level_db.put(key_digp, dpkeys)
                        self.level_db.put(new_digp_key, new_dpkeys)
                    actor_key = b''.join([b'actorprefix', actor_key_raw])
                    self.level_db.put(actor_key, Nbt.NBTFile(data).save_to(compressed=False, little_endian=True)
                                          .replace(b'\x07\n\x00StorageKey\x08\x00\x00\x00',
                                                   b'\x08\n\x00StorageKey\x08\x00'))
                    EntitiePlugin.Onmsgbox(self, "Move Position", "Completed")
                    self._finishup(event)
                else:

                    if (cx,cz) != (nx,nz):
                        old_raw = self.world.level_wrapper.get_raw_chunk_data(cx,cz, self.canvas.dimension)
                        new_raw = self.world.level_wrapper.get_raw_chunk_data(nx,nz, self.canvas.dimension)
                        point = 0
                        max = len(old_raw[b'2'])
                        old_raw_keep = []
                        while point < max:
                            data_old, p = Nbt.load(old_raw[b'2'][point:],compressed=False, little_endian=True, offset=True)
                            point += p
                            if data.get('UniqueID') != data_old.get('UniqueID'):
                                old_raw_keep.append(data_old.save_to(compressed=False, little_endian=True))
                        old_raw[b'2'] = b''.join(old_raw_keep)
                        self.world.level_wrapper.put_raw_chunk_data(cx, cz, old_raw, self.canvas.dimension)
                        raw_chunk_entitie = Nbt.NBTFile(data).save_to(compressed=False, little_endian=True)

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
                            data_old, p = Nbt.load(update_raw[b'2'][point:], compressed=False, little_endian=True,
                                                   offset=True)
                            point += p
                            if data.get('UniqueID') != data_old.get('UniqueID'):
                                update_keep.append(data_old.save_to(compressed=False, little_endian=True))
                            else:
                                update_keep.append(Nbt.NBTFile(data).save_to(compressed=False, little_endian=True))
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
        newData = self._snbt_edit_data.GetValue()
        res = EntitiePlugin.important_question(self)
        if res == False:
            return
        self.EntyData[selection] = Nbt.NBTFile(Nbt.from_snbt(newData)).to_snbt(1)
        if self.world.level_wrapper.version >= (1, 18, 30, 4, 0):
            for snbt, key in zip(self.EntyData, self.Key_tracker):
                nbt = Nbt.from_snbt(snbt)
                dim = struct.unpack("<i", self.get_dim_value())[0]
                cx, cz = block_coords_to_chunk_coords(nbt.get('Pos')[0], nbt.get('Pos')[2])
                try:
                    store_key = struct.unpack(">LL", (self._storage_key_(
                        nbt.get('internalComponents').get('EntityStorageKeyComponent').get('StorageKey'))))

                except:
                    store_key = key
                for key in self.digp.keys():
                    for i, p in enumerate(self.digp[key]):
                        if store_key == p:
                            self.digp[key].remove(p)
                self.digp[(cx, cz, dim)].append(store_key)
                raw_actor_key = b''.join([b'actorprefix', struct.pack('>II', store_key[0], store_key[1])])
                raw_nbt_data = Nbt.NBTFile(nbt).save_to(compressed=False, little_endian=True) \
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
                nbt = Nbt.from_snbt(snbt)
                dim = struct.unpack("<i", self.get_dim_value())[0]
                cx, cz = block_coords_to_chunk_coords(nbt.get('Pos')[0], nbt.get('Pos')[2])
                actor_key = self.uuid_to_storage_key(nbt)
                self.actors[actor_key].clear()
                self.actors[actor_key].append(nbt.to_snbt(1))
                for k in self.digp.keys():
                    if actor_key in self.digp[k]:
                        self.digp[k].remove(actor_key)

                self.digp[(cx, cz, dim)].append(actor_key)

            for k, v in self.digp.items():
                chunk = self.world.level_wrapper.get_raw_chunk_data(k[0], k[1], self.canvas.dimension)
                chunk[b'2'] = b''
                for ak in v:
                    nbt = Nbt.from_snbt(self.actors.get(ak)[0])
                    chunk[b'2'] += Nbt.NBTFile(nbt).save_to(compressed=False, little_endian=True)

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

    def _load_entitie_data(self, event, bool1, bool2 ):
        self.reuse_var
        self._set_list_of_actors_digp
        self.get_raw_data_new_version(bool1,bool2)

        self.ui_entitie_choice_list.Set(self.lstOfE)

    @property
    def level_db(self):
        level_wrapper = self.world.level_wrapper
        if hasattr(level_wrapper, "level_db"):
            return level_wrapper.level_db
        else:
            return level_wrapper._level_manager._db

    def uuid_to_storage_key(self, nbt):
        uid = nbt.get("UniqueID").value
        uuid = struct.pack('<q', uid)
        # "converted to Long to see real data"
        acnt, wrldcnt = struct.unpack('<LL', uuid)
        wc = 4294967296 - wrldcnt
        actor_key = (wc, acnt)
        return actor_key

    def nbt_loder(self, raw):
        try:
            new_raw = Nbt.load(raw.replace(b'\x08\n\x00StorageKey\x08\x00',
                       b'\x07\n\x00StorageKey\x08\x00\x00\x00'),compressed=False,little_endian=True)
        except:
            new_raw = Nbt.load(raw,compressed=False, little_endian=True)
        return new_raw
    @property
    def _set_list_of_actors_digp(self):
        self.actors = collections.defaultdict(list)
        self.digp = collections.defaultdict(list)
        items = ""
        st = time.time_ns()

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
                    k,v = next(actorprefixs)
                except StopIteration:
                    done_actors = True
                else:
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
                            self.digp[struct.unpack('<iii', k[4:])].append(
                                struct.unpack('>II', v[p:p + 8]))
                            self.not_to_remove.append(struct.unpack('>II', v[p:p + 8]))
        else:

            self.EntyData.clear()  # make sure to start fresh
            nbt = Nbt.NBTFile()
            dim = dim = struct.unpack("<i", self.get_dim_value())[0]
            world_start_count = self.world.level_wrapper.root_tag["worldStartCount"]
            all_chunks = [x for x in self.world.level_wrapper.all_chunk_coords(self.canvas.dimension)]
            for cx, cz in all_chunks:
                chunk = self.world.level_wrapper.get_raw_chunk_data(cx, cz, self.canvas.dimension)
                if chunk.get(b'2') != None:
                    max = len(chunk[b'2'])
                    cp = 0
                    while cp < max:
                        nbt, p = Nbt.load(chunk[b'2'][cp:], little_endian=True, offset=True)
                        cp += p
                        actor_key = self.uuid_to_storage_key(nbt)
                        self.actors[actor_key].append(nbt.to_snbt(1))
                        self.digp[(cx, cz, dim)].append(actor_key)

    def _delete_all_the_dead(self, _):
        self._set_list_of_actors_digp
        self.the_dead = collections.defaultdict(list)
        count_deleted = 0
        for dv in self.actors.keys():
            if dv not in self.not_to_remove:
                key = b''.join([b'actorprefix', struct.pack('>II', dv[0], dv[1])])
                self.level_db.delete(key)
                count_deleted +=1
        self.ui_entitie_choice_list.Set([])
        EntitiePlugin.Onmsgbox(self,"DELETED",f"Deleted {count_deleted} ghosted entities . ")




    def _list_the_dead(self, _):
        self._set_list_of_actors_digp
        self.the_dead = collections.defaultdict(list)
        for dv in self.actors.keys():
            if dv not in self.not_to_remove:
                key = b''.join([b'actorprefix', struct.pack('>II', dv[0], dv[1])])
                data = self.level_db.get(key)
                nbt = Nbt.load(data.replace(b'\x08\n\x00StorageKey\x08\x00',
                                            b'\x07\n\x00StorageKey\x08\x00\x00\x00'), little_endian=True)
                self.the_dead[key].append(nbt)

        self.EntyData.clear()
        self.lstOfE = []
        self.current_selection = []


        filter = self.exclude_filter.GetValue().split(",")
        custom_filter =  self.include_filter.GetValue().split(",")
        for k, v in self.the_dead.items():
            px, py, pz = '', '', ''
            name = str(v[0]['identifier']).replace("minecraft:", "")
            try:
                px, py, pz = v[0].get('Pos').value
            except:
                print(k, v, name, "wtf went wrong")
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
        print(len(self.lstOfE), len(self.EntyData), len(self.current_selection), len(self.the_dead.items()))
        zipped_lists = zip(self.lstOfE, self.EntyData, self.current_selection)
        sorted_pairs = sorted(zipped_lists)
        tuples = zip(*sorted_pairs)
        self.lstOfE, self.EntyData, self.current_selection = [list(tuple) for tuple in tuples]
        self.ui_entitie_choice_list.Set(self.lstOfE)

    def _make_undead(self, _):
        res = EntitiePlugin.important_question(self)
        if res == False:
            return
        bring_back = Nbt.from_snbt(self.EntyData[self.ui_entitie_choice_list.GetSelection()])
        raw_dead_actor_key = self.current_selection.pop(self.ui_entitie_choice_list.GetSelection())
        self.the_dead.pop(raw_dead_actor_key)
        try:
            recovory_key = self._storage_key_(
                bring_back["internalComponents"]["EntityStorageKeyComponent"]['StorageKey'])
        except:
            recovory_key = raw_dead_actor_key[11:]
            print(recovory_key)

        x, y, z = bring_back.get('Pos').value
        print(x, y, z)
        try:
            bring_back["Attributes"][1]['Current'] = Nbt.TAG_Float(20.)
            bring_back["Dead"] = Nbt.TAG_Byte(0)
        except:
            pass
        raw_nbt = Nbt.NBTFile(bring_back).save_to(compressed=False, little_endian=True) \
            .replace(b'\x07\n\x00StorageKey\x08\x00\x00\x00', b'\x08\n\x00StorageKey\x08\x00')
        self.level_db.put(raw_dead_actor_key, raw_nbt)
        for popoff in self.digp.keys():
            for d in self.digp[popoff]:
                print(self._storage_key_(recovory_key), d)
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
        setdata = Nbt.from_snbt(self.EntyData[self.ui_entitie_choice_list.GetSelection()])
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
                    data, p = amulet_nbt.load(raw_chunk[b'2'][pos:], compressed=False, little_endian=True, offset=True)
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
        setdata = Nbt.from_snbt(self.EntyData[self.ui_entitie_choice_list.GetSelection()])
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

    def _load_entitie_data(self, event, bool1, bool2 ):
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
        self.found_entities = Nbt.TAG_List()
        for xc , xz in chunks:
            rx, rz = world_utils.chunk_coords_to_region_coords(xc , xz)
            rcords[(rx, rz)].append((xc , xz))

        for rx, rz in rcords.keys():
            path = self.world.level_wrapper.path  # need path for file
            entitiesPath = self.get_dim_vpath_java_dir(rx,rz)  # full path for file
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

        for nbt in self.found_entities:
            exclude_filter = self.exclude_filter.GetValue().split(",")
            include_filter = self.include_filter.GetValue().split(",")
            name = str(nbt['id']).replace("minecraft:", "")
            if exclude_filter != ['']:
                if name not in exclude_filter:
                    self.lstOfE.append(name)
                    self.EntyData.append(nbt.to_snbt(1))
            if include_filter != ['']:
                if name in include_filter:
                    self.lstOfE.append(name)
                    self.EntyData.append(nbt.to_snbt(1))
            else:
                self.lstOfE.append(name)
                self.EntyData.append(nbt.to_snbt(1))

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
            setdata = Nbt.from_snbt(self.EntyData[self.ui_entitie_choice_list.GetSelection()])
        except:
            setdata = self.EntyData[self.ui_entitie_choice_list.GetSelection()]
        ox, oy, oz = setdata.get('Pos')
        nx = self._X.GetValue().replace(" X", "")
        ny = self._Y.GetValue().replace(" Y", "")
        nz = self._Z.GetValue().replace(" Z", "")
        location = Nbt.TAG_List([Nbt.TAG_Double(float(nx)), Nbt.TAG_Double(float(ny)), Nbt.TAG_Double(float(nz))])

        setdata["Pos"] = location
        data_nbt = setdata

        cx, cz = block_coords_to_chunk_coords(float(ox), float(oz))
        rx, rz = world_utils.chunk_coords_to_region_coords(cx, cz)

        self.Entities_region = AnvilRegion(self.get_dim_vpath_java_dir(rx, rz))
        nbt_reg = self.Entities_region.get_chunk_data(cx % 32, cz % 32)
        main_uuid = data_nbt.get('UUID')
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
                    setdata['UUID'] = amulet_nbt.TAG_Int_Array(
                        [amulet_nbt.TAG_Int(q), amulet_nbt.TAG_Int(w), amulet_nbt.TAG_Int(e),
                         amulet_nbt.TAG_Int(r)])
                if self.world.level_wrapper.version >= 2730:
                    nbt_reg['Entities'].append(setdata)
                else:
                    nbt_reg['Level']['Entities'].append(setdata)
                self.Entities_region.put_chunk_data(cx % 32, cz % 32, nbt_reg)
                self.Entities_region.save()
            else:
                if self.world.level_wrapper.version >= 2730:
                    new_data = amulet_nbt.NBTFile()
                    new_data['Position'] = amulet_nbt.from_snbt(f'[I; {cx}, {cz}]')
                    new_data['DataVersion'] = amulet_nbt.TAG_Int(self.world.level_wrapper.version)
                    new_data['Entities'] = amulet_nbt.TAG_List()
                    new_data['Entities'].append(setdata)
                    self.Entities_region.put_chunk_data(cx % 32, cz % 32, new_data)
                    self.Entities_region.save()
                else:
                    print("java version would leave hole in world , file")
        else:
            if self.world.level_wrapper.version >= 2730:
                self.Entities_region = AnvilRegion(self.get_dim_vpath_java_dir(rx, rz), create=True)
                new_data = amulet_nbt.NBTFile()
                new_data['Position'] = amulet_nbt.from_snbt(f'[I; {cx}, {cz}]')
                new_data['DataVersion'] = amulet_nbt.TAG_Int(self.world.level_wrapper.version)
                new_data['Entities'] = amulet_nbt.TAG_List()
                new_data['Entities'].append(setdata)
                self.Entities_region.put_chunk_data(cx % 32, cz % 32, new_data)
                self.Entities_region.save()
                print(f'SAVED CHUNK NEW FILE file r.{rx}, {rz} Chunk: {cx}, {cz}')
            else:
                print("java version would leave hole in world, No file")

        self.world.save()
        self._load_entitie_data(event, False, self.get_all_flag)

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
        if self.world.level_wrapper.version >= 2730:
            version = "entities"
        else:
            version = "region"
        full_path =  os.path.join(path,dim,version,file)
        return full_path

    def java_get_ver_path_data(self, nbt):

        if self.world.level_wrapper.version >= 2730:
            return nbt.get('Entities')
        else:
            return nbt.get("Level").get('Entities')

    def java_set_ver_path_data(self, add, this ):

        if self.world.level_wrapper.version >= 2730:
             if this == None:
                 add = amulet_nbt.TAG_List()
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
            rx,rz = world_utils.chunk_coords_to_region_coords(xc,xz)
            the_file = self.get_dim_vpath_java_dir(rx,rz)
            file_exists = exists(the_file)
            if file_exists:
                chunk_regon_dict[(rx,rz, the_file)].append((xc, xz))
        for rx, rz, f in chunk_regon_dict.keys():
            self.Entities_region = AnvilRegion(f)
            for cx,cz in chunk_regon_dict[(rx, rz, f)]:
                if self.Entities_region.has_chunk(cx % 32, cz % 32):
                    self.chunk_data = self.Entities_region.get_chunk_data(cx % 32, cz % 32)
                    if self.world.level_wrapper.version >= 2730:
                        if (cx, cz) not in selected:
                            self.chunk_data['Entities'].clear()
                    else:
                        if (cx,cz) not in selected:
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
                EntitiePlugin.Onmsgbox(self, "No Selection", "You must select a area in the world to start from, \n Note: Just one block will work. It builds from the South/West")
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
                nbt = amulet_nbt.from_snbt(line)
                x,y,z = nbt.get('Pos').value
                uu_id = uuid.uuid4()
                q, w, e, r = struct.unpack('>iiii', uu_id.bytes)
                nbt['UUID'] = amulet_nbt.TAG_Int_Array(
                    [amulet_nbt.TAG_Int(q), amulet_nbt.TAG_Int(w), amulet_nbt.TAG_Int(e), amulet_nbt.TAG_Int(r)])
                bc,bz = block_coords_to_chunk_coords(x,z)
                rx,rz = world_utils.chunk_coords_to_region_coords(bc,bz)
                l_nbt = {}
                l_nbt[(bc,bz)] = nbt
                loaction_dict[(rx,rz)].append(l_nbt)

            for rx,rz in loaction_dict.keys():
                file_exists = exists(self.get_dim_vpath_java_dir(rx,rz))
                if file_exists:
                    for di in loaction_dict[(rx,rz)]:
                        for k,v in di.items():
                            cx, cz = k
                            nbt_data = v
                            self.Entities_region = AnvilRegion(self.get_dim_vpath_java_dir(rx,rz))
                            if self.Entities_region.has_chunk(cx % 32, cz % 32):
                                nbtdata = self.Entities_region.get_chunk_data(cx % 32, cz % 32)
                                entitiedata = self.java_get_ver_path_data(nbtdata)
                                newData = self.java_set_ver_path_data(entitiedata, nbt_data)
                                self.Entities_region.put_chunk_data(cx % 32, cz % 32, nbtdata)
                                self.Entities_region.save()
                else:
                    if self.world.level_wrapper.version >= 2730:
                        new_data = amulet_nbt.NBTFile()
                        new_data['Position'] = amulet_nbt.from_snbt(f'[I; {cx}, {cz}]')
                        new_data['DataVersion'] = amulet_nbt.TAG_Int(self.world.level_wrapper.version)
                        new_data['Entities'] = amulet_nbt.TAG_List()
                        new_data['Entities'].append(nbt_data)
                        self.Entities_region.put_chunk_data(cx % 32, cz % 32, new_data)
                        self.Entities_region.save()
                        print(f'SAVED CHUNK file r.{rx}, {rz} Chunk: {cx}, {cz}, world genoration my kill entitiy')
                    else:
                        mc_id = new_data.get('id')
                        print(f'NO CHUNK DATA file r.{rx}, {rz} Chunk: {cx} , {cz} , pos: {(x,y,z)} , id: {mc_id}')
                        #  less than java version 2730
                            # can not store entities without leaving a chunk hole.

            self.canvas.run_operation(lambda: self._refresh_chunk_now(self.canvas.dimension, self.world, cx, cz))
            self.world.save()
            EntitiePlugin.Onmsgbox(self,"SNBT LIST", "Import Complete.")

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
            anbt = amulet_nbt.load(snbt_list, compressed=False, little_endian=True)
            sx,sy,sz = anbt.get("structure_world_origin")
            egx,egy,egz = anbt.get("size")
            ex, ey, ez = sx-egx,sy-egy,sz-egz
            group = []
            self.canvas.camera.set_location((sx, 70, sz))
            self.canvas.camera._notify_moved()
            s, e = (int(sx),int(sy),int(sz)), (int(ex), int(ey), int(ez))
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
            regon_dict[(rx,rz)].append((cx,cz))
        for rx,rz in regon_dict.keys():
            entitiesPath = self.get_dim_vpath_java_dir(rx, rz)  # full path for file
            file_exists = exists(entitiesPath)

            if file_exists:
                self.Entities_region = AnvilRegion(entitiesPath)
                for cx,cz in regon_dict[rx,rz]:
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
        newData = self._snbt_edit_data.GetValue()  # get new data
        data = Nbt.from_snbt(newData)  # convert to nbt
        cx , cz = block_coords_to_chunk_coords(data.get("Pos")[0].value,data.get("Pos")[2].value)
        loc = data.get("Pos")
        uuid = data.get("UUID")
        rx, rz = world_utils.chunk_coords_to_region_coords(cx,cz)
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
        EntitiePlugin.Onmsgbox(self,"Operation complete",
                      "The operation has completed without error:\n Save world to see the changes")

    def _export_nbt(self, _):
        entities = amulet_nbt.TAG_List()
        blocks = amulet_nbt.TAG_List()
        palette = amulet_nbt.TAG_List()
        DataVersion = amulet_nbt.TAG_Int(2975)
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
                    palette_Properties = amulet_nbt.TAG_Compound(
                        {'Properties': amulet_nbt.from_snbt(str(block.properties)),
                         'Name': amulet_nbt.TAG_String(block.namespaced_name)})
                    palette.append(palette_Properties)
                state = pallet_key_map[(block.namespaced_name, str(block.properties))]

                if blockEntity == None:
                    blocks_pos = amulet_nbt.TAG_Compound({'pos': amulet_nbt.TAG_List(
                        [amulet_nbt.TAG_Int(b[0]), amulet_nbt.TAG_Int(b[1]),
                         amulet_nbt.TAG_Int(b[2])]), 'state': amulet_nbt.TAG_Int(state)})
                    blocks.append(blocks_pos)
                else:
                    blocks_pos = amulet_nbt.TAG_Compound({'nbt': amulet_nbt.from_snbt(blockEntity.nbt.to_snbt()),
                                                          'pos': amulet_nbt.TAG_List(
                                                              [amulet_nbt.TAG_Int(b[0]),
                                                               amulet_nbt.TAG_Int(b[1]),
                                                               amulet_nbt.TAG_Int(b[2])]),
                                                          'state': amulet_nbt.TAG_Int(state)})
                    blocks.append(blocks_pos)
        prg_pre = 99
        self.prog.Update(prg_pre, "Finishing Up " + str(i) + " of " + str(prg_max))
        size = amulet_nbt.TAG_List([amulet_nbt.TAG_Int(mx), amulet_nbt.TAG_Int(my), amulet_nbt.TAG_Int(mz)])

        save_it = amulet_nbt.NBTFile()
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
            nbt = amulet_nbt.load(pathto, compressed=True, little_endian=False, )
            block_platform = "java"
            block_version = (1, 18, 0)
            b_pos = []
            palette = []
            Name = []
            enbt = []
            xx = self.canvas.selection.selection_group.min_x
            yy = self.canvas.selection.selection_group.min_y
            zz = self.canvas.selection.selection_group.min_z
            reps = EntitiePlugin.con_boc(self, "Air Blocks", 'Do you want to encude air block?')
            for x in nbt.get('blocks'):
                if nbt['palette'][int(x.get('state'))].get('Properties') != None:
                    palette.append(
                        dict(amulet_nbt.from_snbt(nbt['palette'][int(x.get('state'))]['Properties'].to_snbt())))
                else:
                    palette.append(None)
                b_pos.append(x.get('pos'))
                Name.append(nbt['palette'][int(x.get('state'))]['Name'])
                if x.get('nbt') != None:
                    name = str(nbt['palette'][int(x.get('state'))]['Name']).split(':')

                    blockEntity = BlockEntity(name[0], name[1].replace('_', '').capitalize(), 0, 0, 0,
                                              amulet_nbt.NBTFile(x.get('nbt')))
                    enbt.append(blockEntity)
                else:
                    enbt.append(None)

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
            self.world.save() # MUST SAVE NOW OR THIS WILL REMOVE ENTITIES
            e_nbt_list = []
            for x in nbt.get('entities'):
                if str(x) != '':
                    e_nbt = x.get('nbt')
                    nxx, nyy, nzz = x.get('pos').value

                    x['nbt']['Pos'] = amulet_nbt.TAG_List([amulet_nbt.TAG_Double(float(nxx + xx)),
                                                           amulet_nbt.TAG_Double(float(nyy + yy)),
                                                           amulet_nbt.TAG_Double(float(nzz + zz))])
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

        entities = amulet_nbt.TAG_List()
        selection = self.canvas.selection.selection_group.to_box()
        for o, n in zip(selection, rpos):
            mapdic[o] = n
        chunk_min, chunk_max = self.canvas.selection.selection_group.min, \
                               self.canvas.selection.selection_group.max
        min_chunk_cords, max_chunk_cords = block_coords_to_chunk_coords(chunk_min[0], chunk_min[2]), \
                                           block_coords_to_chunk_coords(chunk_max[0], chunk_max[2])
        cl = self.canvas.selection.selection_group.chunk_locations()
        self.found_entities = amulet_nbt.TAG_List()
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
            return amulet_nbt.TAG_List()
        entities = amulet_nbt.TAG_List()
        for nbt_data in self.found_entities:
            x, y, z = math.floor(nbt_data.get('Pos')[0].value), math.floor(
                nbt_data.get('Pos')[1].value), math.floor(nbt_data.get('Pos')[2].value)
            if (x, y, z) in selection:
                new_pos = mapdic[(x, y, z)]
                nbt_pos = amulet_nbt.TAG_List([amulet_nbt.TAG_Double(sum([new_pos[0],
                                               math.modf(abs(nbt_data.get("Pos")[0].value))[0]])),
                                               amulet_nbt.TAG_Double(sum([new_pos[1],
                                               math.modf(abs(nbt_data.get("Pos")[1].value))[0]])),
                                               amulet_nbt.TAG_Double(sum([new_pos[2],
                                               math.modf(abs(nbt_data.get("Pos")[2].value))[0]]))])
                nbt_block_pos = amulet_nbt.TAG_List([amulet_nbt.TAG_Int(new_pos[0]),
                                                     amulet_nbt.TAG_Int(new_pos[1]),
                                                     amulet_nbt.TAG_Int(new_pos[2])])
                nbt_nbt = amulet_nbt.from_snbt(nbt_data.to_snbt())
                main_entry = amulet_nbt.TAG_Compound()
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
                nbt_data['UUID'] = amulet_nbt.TAG_Int_Array(
                    [amulet_nbt.TAG_Int(q), amulet_nbt.TAG_Int(w), amulet_nbt.TAG_Int(e), amulet_nbt.TAG_Int(r)])
                x, y, z = math.floor(nbt_data.get('Pos')[0].value), math.floor(
                    nbt_data.get('Pos')[1].value), math.floor(nbt_data.get('Pos')[2].value)
                cx, cz = block_coords_to_chunk_coords(x, z)
                rx, rz = world_utils.chunk_coords_to_region_coords(cx, cz)
                entitiesPath = self.get_dim_vpath_java_dir(rx,rz)  # full path for file
                file_exists = exists(entitiesPath)
                if file_exists:
                    self.Entities_region = AnvilRegion(entitiesPath)
                    if self.Entities_region.has_chunk(cx % 32, cz % 32):
                        self.chunk_raw = self.Entities_region.get_chunk_data(cx % 32, cz % 32)
                        if self.world.level_wrapper.version >= 2730:
                            if not self.chunk_raw.get('Entities'):
                                self.chunk_raw['Entities'] = amulet_nbt.TAG_List()

                            self.chunk_raw['Entities'].append(nbt_data)

                            self.Entities_region.put_chunk_data(cx % 32, cz % 32, self.chunk_raw)
                            self.Entities_region.save()
                            print(f' 1 SAVED CHUNK NEW FILE file r.{rx}, {rz} Chunk: {cx}, {cz}')
                        else:
                            if not self.chunk_raw.get('Level').get('Entities'):
                                self.chunk_raw["Level"]['Entities'] = amulet_nbt.TAG_List()
                            self.chunk_raw["Level"]['Entities'].append(nbt_data)
                            self.Entities_region.put_chunk_data(cx % 32, cz % 32, self.chunk_raw)
                            self.Entities_region.save()
                            print(self.chunk_raw["Level"])
                            print(f' 2 SAVED CHUNK NEW FILE file r.{rx}, {rz} Chunk: {cx}, {cz}')
                    else:
                        if self.world.level_wrapper.version >= 2730:
                            self.Entities_region = AnvilRegion(entitiesPath, create=True)
                            new_data = amulet_nbt.NBTFile()
                            new_data['Position'] = amulet_nbt.from_snbt(f'[I; {cx}, {cz}]')
                            new_data['DataVersion'] = amulet_nbt.TAG_Int(self.world.level_wrapper.version)
                            new_data['Entities'] = amulet_nbt.TAG_List()
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
                        new_data = amulet_nbt.NBTFile()
                        new_data['Position'] = amulet_nbt.from_snbt(f'[I; {cx}, {cz}]')
                        new_data['DataVersion'] = amulet_nbt.TAG_Int(self.world.level_wrapper.version)
                        new_data['Entities'] = amulet_nbt.TAG_List()
                        new_data['Entities'].append(nbt_data)

                        self.Entities_region.put_chunk_data(cx % 32, cz % 32, new_data)
                        self.Entities_region.save()
                        print(f' 5 SAVED CHUNK NEW FILE file r.{rx}, {rz} Chunk: {cx}, {cz}')
                    else:
                        print(f' 6 NO CHUNK DATA file r.{rx}, {rz} Chunk: {cx} , {cz} ')  # #java less than version 2730
                        # can not store entities without leaving hole
            self.world.save()
            self._load_entitie_data('0',False,self.get_all_flag)

class EntitiePlugin(wx.Panel, DefaultOperationUI):

    def __init__(
            self,
            parent: wx.Window,
            canvas: "EditCanvas",
            world: "BaseLevel",
            options_path: str,
    ):
        platform = world.level_wrapper.platform
        world_version = world.level_wrapper.version
        plat = (platform, world_version)
        wx.Panel.__init__(self, parent)
        DefaultOperationUI.__init__(self, parent, canvas, world, options_path)
        self.lstOfE = ['This List will Contain', 'Entities', "NOTE: the TAB key",
                       " to toggle Perspective", "Canvas must be active","Mouse over the canvas", "To activate canvas"]
        self.nbt_data = Nbt.NBTFile()
        self.Freeze()
        self.EntyData = []
        self._highlight_edges = numpy.zeros((2, 3), dtype=bool)

        if platform == 'bedrock':
            self.operation = BedRock()
            self.operation.world = self.world
            self.operation.canvas = self.canvas
            self.operation.EntyData = self.EntyData

        else:
            self.operation = Java()
            self.operation.world = self.world
            self.operation.canvas = self.canvas
            self.operation.EntyData = self.EntyData
            self.operation.lstOfE =self.lstOfE

        self.operation.select_tracer = collections.defaultdict(list)
        self.get_all_flag = False
        self.operation.get_all_flag = self.get_all_flag

        self._sizer_v_main = wx.BoxSizer(wx.VERTICAL)
        self.left_sizer = wx.BoxSizer(wx.VERTICAL)
        self.right_sizer = wx.BoxSizer(wx.VERTICAL)

        self.bottom_h = wx.BoxSizer(wx.HORIZONTAL)
        self.top_sizer = wx.GridSizer(4, 3, 0, -1)
        self.button_group_one = wx.GridSizer(2, 2, 0, -20)
        self.button_group_two = wx.GridSizer(0, 3, 0,  1)
        self.button_group_three = wx.GridSizer(0, 2, 0, -1)
        self.button_group_four = wx.GridSizer(0, 4, 1, 1)

        self.SetSizer(self._sizer_v_main)
        self.operation.filter_include_label = wx.StaticText(self, label=" Include Filter:", size=(76,25))
        self.operation.filter_exclude_label = wx.StaticText(self, label=" Exclude Filter:", size=(76,25))
        self.operation.exclude_filter = wx.TextCtrl(self, style=wx.TE_LEFT, size=(120, 25))
        self.operation.include_filter = wx.TextCtrl(self, style=wx.TE_LEFT, size=(120, 25))

        self.button_group_four.Add(self.operation.filter_include_label)
        self.button_group_four.Add(self.operation.include_filter, 3, wx.LEFT, -20)
        self.button_group_four.Add(self.operation.filter_exclude_label)
        self.button_group_four.Add(self.operation.exclude_filter,3, wx.LEFT, -20)
        self.font_ex_in = wx.Font(12, wx.FONTFAMILY_ROMAN, wx.FONTSTYLE_MAX, wx.FONTWEIGHT_BOLD)
        self.operation.exclude_filter.SetForegroundColour((0,  0, 0))
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
        self._get_all_button = wx.Button(self, label="Get All",size=(60, 20))
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
        self._get_button.Bind(wx.EVT_BUTTON, lambda event: self.operation._load_entitie_data(event,False , False))
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
        self.operation._Y.SetBackgroundColour((0,255, 0))
        self.operation._Z.SetBackgroundColour((0, 0, 255))
        self.operation._X.SetLabel("X of Selected")
        self.operation._Y.SetLabel("Y of Selected")
        self.operation._Z.SetLabel("Z of Selected")
        self.operation._X.SetFont(self.font_ex_in)
        self.operation._Y.SetFont(self.font_ex_in)
        self.operation._Z.SetFont(self.font_ex_in)

        self.top_sizer.Add(self.delete_unselected,0 ,wx.TOP, 5)
        self.top_sizer.Add(self.operation._imp_button,0 ,wx.TOP, 5)
        self.button_group_three.Add(self._get_button,0 ,wx.TOP, 5)
        self.button_group_three.Add(self._get_all_button ,0 ,wx.TOP, 5)
        self.top_sizer.Add(self.button_group_three,0 ,wx.TOP, 1)

        self.top_sizer.Add(self.delete_selected)

        self.top_sizer.Add(self.operation._exp_button)
        self.top_sizer.Add(self._set_button )

        self.top_sizer.Add(self.operation._X ,0 ,wx.TOP, -5)
        self.top_sizer.Add(self.operation._Y,0 ,wx.TOP, -5)
        self.top_sizer.Add(self.operation._Z,0 ,wx.TOP, -5)
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
        self.top_sizer.Add(self.button_group_one,0 ,wx.TOP, -10)
        self.top_sizer.Add(self._teleport_check, 0 ,wx.LEFT, 7)

        self.button_group_two.Add(self._move)
        self.button_group_two.Add(self._copy)
        self.button_group_two.Add(self._delete)
        self.top_sizer.Add(self.button_group_two )

        self._snbt_edit_data = wx.TextCtrl(self, style=wx.TE_MULTILINE, size=(280, 650))
        self._snbt_edit_data.SetFont(self.font)
        self.bottom_h.Add(self._snbt_edit_data, 0, wx.ALIGN_LEFT, 20)


        self.operation._snbt_edit_data = self._snbt_edit_data
        self._snbt_edit_data.Bind(wx.EVT_KEY_UP, self.autoSaveOnKeyPress)
        self.ui_entitie_choice_list = wx.ListBox(self, style=wx.LB_HSCROLL , choices=self.lstOfE, pos=(0, 20),
                                                 size=(148, 200))
        self.ui_entitie_choice_list.SetFont(self.font)
        self.ui_entitie_choice_list.Bind(wx.EVT_LISTBOX, lambda event: self.on_focus(event))

        self.bottom_h.Add(self.ui_entitie_choice_list, 1, wx.EXPAND)
        self._snbt_edit_data.SetBackgroundColour((0, 0, 0))
        self._snbt_edit_data.SetForegroundColour((0, 255, 0))
        self.ui_entitie_choice_list.SetBackgroundColour((0, 0, 0))
        self.ui_entitie_choice_list.SetForegroundColour((255, 255, 0))
        self.operation.ui_entitie_choice_list = self.ui_entitie_choice_list
        self._sizer_v_main.Fit(self)
        self.Layout()
        self.Thaw()

    def bind_events(self):
        super().bind_events()
        self.canvas.Bind(EVT_SELECTION_CHANGE, self._set_new_block)
        self._selection.bind_events()
        self._selection.enable()

    def enable(self):
        self.canvas.camera.projection_mode = Projection.TOP_DOWN
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
        newData = self.operation._snbt_edit_data.GetValue()
        try:
            self.operation.EntyData[selection] = Nbt.NBTFile(Nbt.from_snbt(newData))
        except:
            self.Onmsgbox("syntax error", "Try agian")
            setdata = self.operation.EntyData[selection]
            try:
                self.operation._snbt_edit_data.SetValue(Nbt.from_snbt(setdata).to_snbt(1))
            except:
                self.operation._snbt_edit_data.SetValue(setdata.to_snbt(1))


    def on_focus(self, evt):

        setdata = Nbt.from_snbt(self.operation.EntyData[self.ui_entitie_choice_list.GetSelection()])

        self.operation._snbt_edit_data.SetValue(setdata.to_snbt(1))
        (x, y, z) = setdata.get('Pos')[0], setdata.get('Pos')[1], setdata.get('Pos')[2]
        self.operation._X.SetLabel(str(x).replace("f", " X").replace("d", " X"))
        self.operation._Y.SetLabel(str(y).replace("f", " Y").replace("d", " Y"))
        self.operation._Z.SetLabel(str(z).replace("f", " Z").replace("d", " Z"))
        X = int(str(self.operation._X.GetValue()).replace(" X", "").split(".")[0])
        Y = int(str(self.operation._Y.GetValue()).replace(" Y", "").split(".")[0])
        Z = int(str(self.operation._Z.GetValue()).replace(" Z", "").split(".")[0])
        blockPosdata = {}
        group = []
        v = (
            X-1,
            Y-1,
            Z-1)
        vv = (X,
              Y,
              Z)
        group.append(SelectionBox(v, vv))
        sel = SelectionGroup(group)
        self.canvas.selection.set_selection_group(sel)
        if self._teleport_check.GetValue():
            x, y, z = (x, y, z)
            self.canvas.camera.set_location((x, 320, z))
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
            self.okButton.SetSize(250,23)
            self.okButton.SetPosition(pt=(15,87))
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

export = dict(name="# The Entitie's Plugin v1.03", operation=EntitiePlugin) #PremiereHell
