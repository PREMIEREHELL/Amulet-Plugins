import math
import os
from os.path import exists

import amulet_nbt
import wx
import struct
from typing import TYPE_CHECKING
from amulet_map_editor.programs.edit.api.operations import DefaultOperationUI
from amulet_nbt import *
from amulet_map_editor.api.wx.ui.base_select import BaseSelect
from amulet.api.block_entity import BlockEntity
from amulet.api.block import Block
from amulet.utils import block_coords_to_chunk_coords
from amulet.utils import world_utils
from amulet.level.formats.anvil_world.region import AnvilRegion

import collections
from amulet_map_editor.programs.edit.api.behaviour import BlockSelectionBehaviour
from amulet.api.errors import ChunkDoesNotExist

if TYPE_CHECKING:
    from amulet.api.level import BaseLevel
    from amulet_map_editor.programs.edit.api.canvas import EditCanvas
class NbtImportExport(wx.Panel, DefaultOperationUI):
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
        self.enabled = False
        wx.Panel.__init__(self, parent)
        DefaultOperationUI.__init__(self, parent, canvas, world, options_path)
        self._sizer = wx.BoxSizer(wx.VERTICAL)
        self.only_e = wx.CheckBox(self, label="Only Entities (Import)", pos=(83, 30))
        self.air_check = wx.CheckBox(self, label="Include Air blocks",pos=(150, 0))
        self.entitie_check = wx.CheckBox(self, label="Include Entities", pos=(150, 15))
        self.export_nbt = wx.Button(self, label="Export", pos=(3, 3))
        self.import_nbt = wx.Button(self, label="Import", pos=(75, 3))
        self.import_nbt.Bind(wx.EVT_BUTTON, self._import_nbt)
        self.export_nbt.Bind(wx.EVT_BUTTON, self._export_nbt)

        self._sizer.Add(self.export_nbt)
        self._sizer.Add(self.import_nbt)
        self._sizer.Add(self.air_check)
        self._sizer.Add(self.entitie_check)
        self._sizer.Add(self.only_e)
        self.enable()

    def bind_events(self):
        super().bind_events()
        self._selection.bind_events()

    def enable(self):
         self._selection = BlockSelectionBehaviour(self.canvas)
         self._selection.enable()


    def _export_nbt(self, _):
        entities = ListTag()
        blocks = ListTag()
        palette = ListTag()
        DataVersion = IntTag(2975)
        selection = self.canvas.selection.selection_group.to_box()
        pallet_key_map = collections.defaultdict(list)
        nbt_state_map = collections.defaultdict(list)
        indx = 0
        sx, sy, sz = 0, 0, 0

        mx, my, mz = self.canvas.selection.selection_group.to_box().shape
        block_pos = []
        # bl = np.zeros(shape, dtype=numpy.uint32)
        for x in range(0, (mx)):
            for y in range(0, (my)):
                for z in range(0, (mz)):
                    block_pos.append((x, y, z))

        print(self.entitie_check.GetValue())
        if self.entitie_check.GetValue() == False:
            entities = ListTag()
        else:
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

            if self.air_check.GetValue() == False:
                check_string = ""
            else:
                check_string = 'minecraft:air'
            if str(block) != check_string:
                if pallet_key_map.get((block.namespaced_name, CompoundTag(block.properties).to_snbt())) == None:
                    pallet_key_map[(block.namespaced_name, CompoundTag(block.properties).to_snbt())] = indx
                    indx += 1
                    palette_Properties = CompoundTag(
                        {'Properties': from_snbt(CompoundTag(block.properties).to_snbt()),
                         'Name': StringTag(block.namespaced_name)})
                    palette.append(palette_Properties)
                state = pallet_key_map[(block.namespaced_name, CompoundTag(block.properties).to_snbt())]

                if blockEntity == None:
                    blocks_pos = CompoundTag({'pos': ListTag(
                        [IntTag(b[0]), IntTag(b[1]),
                         IntTag(b[2])]), 'state': IntTag(state)})
                    blocks.append(blocks_pos)
                else:
                    blocks_pos = CompoundTag({'nbt': from_snbt(blockEntity.nbt.to_snbt()),
                                                          'pos': ListTag(
                                                              [IntTag(b[0]),
                                                               IntTag(b[1]),
                                                               IntTag(b[2])]),
                                                          'state': IntTag(state)})
                    blocks.append(blocks_pos)
        prg_pre = 99
        self.prog.Update(prg_pre, "Finishing Up " + str(i) + " of " + str(prg_max))
        size = ListTag([IntTag(mx), IntTag(my), IntTag(mz)])

        save_it = CompoundTag()
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
            nbt = load(pathto, compressed=True, little_endian=False)
            block_platform = "java"
            block_version = (1, 21, 0)
            b_pos = []
            palette = []
            Name = []
            enbt = []
            xx = self.canvas.selection.selection_group.min_x
            yy = self.canvas.selection.selection_group.min_y
            zz = self.canvas.selection.selection_group.min_z

            if self.only_e.GetValue() == False:
                for i, x in enumerate(nbt.get('blocks')):
                    print(i)
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
                                                  NamedTag(x.get('nbt')))
                        enbt.append(blockEntity)
                    else:
                        enbt.append(None)

                if self.air_check.GetValue() == False:
                    check_string = ""
                else:
                    check_string = 'minecraft:air'
                for x in zip(b_pos, palette, Name, enbt):
                    if x[1] != check_string:
                        block = Block(str(x[2]).split(':')[0], str(x[2]).split(':')[1], x[1])
                        self.world.set_version_block(xx + x[0][0], yy + x[0][1], zz + x[0][2], self.canvas.dimension,
                                                     (block_platform, block_version), block, x[3])
                print("done")
                self.canvas.run_operation(lambda: self._refresh_chunk_now(self.canvas.dimension, self.world, xx, zz))
            if self.entitie_check.GetValue() == False:
                entities = ListTag()
                responce = None
            else:
                dialog = wx.MessageDialog(self,  "Including entities directly edits the world and there is no Undo."
                    "\n Would you like to save changes or discard them,\n Both option will remove all current undo points\n"
                   "What do you wish to do?", "NOTICE",
                                          wx.ICON_EXCLAMATION | wx.YES_NO | wx.CANCEL | wx.CANCEL_DEFAULT  )  # FYI, `ICON_QUESTION` doesn't work on Windows!
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
                            x['nbt']['Pos'] = ListTag([FloatTag(float(nxx + xx)),
                                                                   FloatTag(float(nyy + yy)),
                                                                   FloatTag(float(nzz + zz))])
                        if 'Double' in str(type(nxx)):
                            x['nbt']['Pos'] = ListTag([DoubleTag(float(nxx + xx)),
                                                                   DoubleTag(float(nyy + yy)),
                                                                   DoubleTag(float(nzz + zz))])
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
            dim = b''#int(0).to_bytes(4, 'little', signed=True)
        return dim

    def get_dim_java_dir(self):
        if 'minecraft:the_end' in self.canvas.dimension:
            dim = 'DIM1'
        elif 'minecraft:the_nether' in self.canvas.dimension:
            dim = 'DIM-1'
        elif 'minecraft:overworld' in self.canvas.dimension:
            dim = ''
        return dim

    def get_entities_nbt(self, rpos):
        mapdic = collections.defaultdict()

        entities = amulet_nbt.TAG_List()
        selection = self.canvas.selection.selection_group.to_box()
        for o,n in zip(selection, rpos):
            mapdic[o] = n
        chunk_min, chunk_max = self.canvas.selection.selection_group.min, \
                               self.canvas.selection.selection_group.max
        min_chunk_cords, max_chunk_cords = block_coords_to_chunk_coords(chunk_min[0],chunk_min[2]), \
                                           block_coords_to_chunk_coords(chunk_max[0],chunk_max[2])
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
                            nbt_entitie = ListTag()
                            new_pos = mapdic[(x, y, z)]
                            nbt_pos = amulet_nbt.TAG_List(
                                [amulet_nbt.TAG_Float(sum([new_pos[0],
                                math.modf(abs(nbt_data.get("Pos")[0].value))[0]])),
                                amulet_nbt.TAG_Float(sum([new_pos[1],
                                math.modf(abs(nbt_data.get("Pos")[1].value))[0]])),
                                amulet_nbt.TAG_Float(sum([new_pos[2],
                                math.modf(abs(nbt_data.get("Pos")[2].value))[0]]))])

                            nbt_block_pos = ListTag([IntTag(new_pos[0]),
                                                                 IntTag(new_pos[1]),
                                                                 IntTag(new_pos[2])])
                            nbt_data.pop('internalComponents')
                            nbt_data.pop('UniqueID')
                            nbt_nbt = from_snbt(nbt_data.to_snbt())
                            main_entry = CompoundTag()
                            main_entry['nbt'] = nbt_nbt
                            main_entry['blockPos'] = nbt_block_pos
                            main_entry['pos'] = nbt_pos
                            entities.append(main_entry)
                return entities

            elif self.world.level_wrapper.version < (1, 18, 30, 4, 0):


                entitie = ListTag()
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
                                nbt_data.pop('internalComponents')
                                nbt_data.pop('UniqueID')
                                nbt_nbt = from_snbt(nbt_data.to_snbt())
                                main_entry = CompoundTag()
                                main_entry['nbt'] = nbt_nbt
                                main_entry['blockPos'] = nbt_block_pos
                                main_entry['pos'] = nbt_pos
                                entities.append(main_entry)
                return entities


        elif self.world.level_wrapper.platform == "java":
            cl  = self.canvas.selection.selection_group.chunk_locations()
            self.found_entities = ListTag()
            self.nbt_data = []
            for cx , cz in cl:
                rx, rz = world_utils.chunk_coords_to_region_coords(cx, cz)  # need region cords for file
                path = self.world.level_wrapper.path  # need path for file
                self.version_path = ""
                if self.world.level_wrapper.version >= 2730:
                    self.version_path = "entities"
                else:
                    self.version_path = "region"
                entitiesPath = os.path.join(path, self.get_dim_java_dir(), self.version_path,
                                            "r." + str(rx) + "." + str(rz) + ".mca")  # full path for file
                self.Entities_region = AnvilRegion(entitiesPath)  # create instance for region data
                # the " % 32 " calulates the location of the chunk in the header,
                if self.Entities_region.has_chunk(cx % 32, cz % 32):
                    try:
                        self.nbt_data_full = self.Entities_region.get_chunk_data(cx % 32, cz % 32)
                        if self.version_path == "region":
                            self.nbt_data = self.nbt_data_full["Level"]['Entities']
                        else:
                            try:
                                self.nbt_data = self.nbt_data_full['Entities']
                            except:
                                pass
                        if len(self.nbt_data) > 0:
                            for x in self.nbt_data:
                                self.found_entities.append(x)
                    except ChunkDoesNotExist:
                        print("No Chunk Data")
                        pass
                entities = amulet_nbt.TAG_List()
                for nbt_data in self.found_entities:
                    x, y, z = math.floor(nbt_data.get('Pos')[0].value), math.floor(
                        nbt_data.get('Pos')[1].value), math.floor(nbt_data.get('Pos')[2].value)
                    if (x, y, z) in selection:

                        new_pos = mapdic[(x, y, z)]
                        nbt_pos = ListTag([DoubleTag(sum([new_pos[0],
                                  math.modf(abs(nbt_data.get("Pos")[0].value))[0]])),
                                  DoubleTag(sum([new_pos[1],
                                  math.modf(abs(nbt_data.get("Pos")[1].value))[0]])),
                                  DoubleTag(sum([new_pos[2],
                                  math.modf(abs(nbt_data.get("Pos")[2].value))[0]]))])
                        nbt_block_pos = amulet_nbt.TAG_List([IntTag(new_pos[0]),
                                                             IntTag(new_pos[1]),
                                                             IntTag(new_pos[2])])
                        nbt_nbt = from_snbt(nbt_data.to_snbt())
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
                    new_actor += x.save_to(compressed=False, little_endian=True)
                    self.level_db.put(put_key, new_actor)
                    self.level_db.put(digp, new_digp)

            elif self.world.level_wrapper.version < (1, 18, 30, 4, 0):
                for x in entities_list:
                    print(type(x))
                    xc, zc = block_coords_to_chunk_coords(x.get('Pos')[0], x.get('Pos')[2])
                    chunk = self.world.level_wrapper.get_raw_chunk_data(xc, zc, self.canvas.dimension)
                    try:
                        chunk[b'2'] += amulet_nbt.NBTFile(x).save_to(little_endian=True, compressed=False)
                    except:
                        chunk[b'2'] = amulet_nbt.NBTFile(x).save_to(little_endian=True, compressed=False)
                    self.world.level_wrapper.put_raw_chunk_data(xc, zc, chunk, self.canvas.dimension)
                    self.world.level_wrapper.save()

        elif self.world.level_wrapper.platform == "java":

            path = self.world.level_wrapper.path  # need path for file
            self.version_path = ""
            if self.world.level_wrapper.version >= 2730:
                self.version_path = "entities"
            else:
                self.version_path = "region"
            for nbt_data in entities_list:
                import uuid
                uu_id = uuid.uuid4()
                q,w,e,r = struct.unpack('>iiii', uu_id.bytes)
                nbt_data['UUID'] = IntArrayTag([IntTag(q),amulet_nbt.TAG_Int(w),IntTag(e),IntTag(r)])
                x, y, z = math.floor(nbt_data.get('Pos')[0].value), math.floor(
                    nbt_data.get('Pos')[1].value), math.floor(nbt_data.get('Pos')[2].value)
                cx, cz = block_coords_to_chunk_coords(x,z)
                rx, rz = world_utils.chunk_coords_to_region_coords(cx, cz)
                entitiesPath = os.path.join(path, self.get_dim_java_dir(), self.version_path,
                                            "r." + str(rx) + "." + str(rz) + ".mca")  # full path for file
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
                            print(f'SAVED CHUNK NEW FILE file r.{rx}, {rz} Chunk: {cx}, {cz}')
                        else:
                            if not self.chunk_raw.get('Level').get('Entities'):
                                self.chunk_raw["Level"]['Entities'] = amulet_nbt.TAG_List()
                            self.chunk_raw["Level"]['Entities'].append(nbt_data)
                            self.Entities_region.put_chunk_data(cx % 32, cz % 32, self.chunk_raw)
                            self.Entities_region.save()
                            print(f'SAVED CHUNK NEW FILE file r.{rx}, {rz} Chunk: {cx}, {cz}')
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
                            print(f'SAVED CHUNK NEW FILE file r.{rx}, {rz} Chunk: {cx}, {cz}')
                        else:
                            print(f'NO CHUNK DATA file r.{rx}, {rz} Chunk: {cx} , {cz} ')# #java less than version 2730
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
                        print(f'SAVED CHUNK NEW FILE file r.{rx}, {rz} Chunk: {cx}, {cz}')
                    else:
                        print(f'NO CHUNK DATA file r.{rx}, {rz} Chunk: {cx} , {cz} ') # #java less than version 2730
                        # can not store entities without leaving hole
            self.world.save()
    @property
    def level_db(self):
        level_wrapper = self.world.level_wrapper
        if hasattr(level_wrapper, "level_db"):
            return level_wrapper.level_db
        else:
            return level_wrapper._level_manager._db
    pass
export = dict(name="##Nbt Import Export v2.02", operation=NbtImportExport)  # by PremiereHell
