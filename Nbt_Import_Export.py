import wx
import struct
from typing import TYPE_CHECKING
from amulet_map_editor.programs.edit.api.operations import DefaultOperationUI
import amulet_nbt
from amulet_map_editor.api.wx.ui.base_select import BaseSelect
from amulet.api.block_entity import BlockEntity
from amulet.api.block import Block
from amulet.utils import block_coords_to_chunk_coords
import collections
from amulet_map_editor.programs.edit.api.behaviour import BlockSelectionBehaviour
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

        wx.Panel.__init__(self, parent)
        DefaultOperationUI.__init__(self, parent, canvas, world, options_path)
        self._sizer = wx.BoxSizer(wx.VERTICAL)
        self.export_nbt = wx.Button(self, label="Export")
        self.import_nbt = wx.Button(self, label="Import", pos=(70, 0))
        self.import_nbt.Bind(wx.EVT_BUTTON, self._import_nbt)
        self.export_nbt.Bind(wx.EVT_BUTTON, self._export_nbt)  ## YOUR UI SETUP
        self._sizer.Add(self.import_nbt)

    def bind_events(self):
        super().bind_events()
        self._selection.bind_events()

    def enable(self):
        self._selection = BlockSelectionBehaviour(self.canvas)

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

        maxX, maxY, MaxZ = self.canvas.selection.selection_group.max_x, \
                           self.canvas.selection.selection_group.max_y, \
                           self.canvas.selection.selection_group.max_z
        minX, minY, minZ = self.canvas.selection.selection_group.min_x, \
                           self.canvas.selection.selection_group.min_y, \
                           self.canvas.selection.selection_group.min_z
        x_m, y_m, z_m = maxX - minX, maxY - minY, MaxZ - minZ
        block_pos = []
        for x in range(0, (x_m)):
            for y in range(0, (y_m)):
                for z in range(0, (z_m)):
                    block_pos.append((x, y, z))
        mx = block_pos[-1][0] 
        my = block_pos[-1][1]
        mz = block_pos[-1][2]

        for i, (s, b) in enumerate(zip(selection, block_pos)):

            block, blockEntity = self.world.get_version_block(s[0], s[1], s[2], self.canvas.dimension,
                                                              ("java", (1, 18, 0)))
            bbb = self.world.get_block(s[0], s[1], s[2], self.canvas.dimension)
            block, blockEntity = self.world.get_version_block(s[0], s[1], s[2], self.canvas.dimension,
                                                              ("java", (1, 18, 0)))
            bbb = self.world.get_block(s[0], s[1], s[2], self.canvas.dimension)
            if pallet_key_map.get((block.namespaced_name, str(block.properties))) == None:
                pallet_key_map[(block.namespaced_name, str(block.properties))] = (indx, blockEntity)
                indx += 1
            nbt_state_map[(block.namespaced_name, str(block.properties))].append((blockEntity, (b[0], b[1], b[2]),
                                                                        pallet_key_map[(block.namespaced_name,
                                                                        str(block.properties))][0]))
        size = amulet_nbt.TAG_List([amulet_nbt.TAG_Int(mx), amulet_nbt.TAG_Int(my), amulet_nbt.TAG_Int(mx)])
        for i, (pal, v) in enumerate(pallet_key_map.items()):
            palette_Properties = amulet_nbt.TAG_Compound(
                {'Properties': amulet_nbt.from_snbt(pal[1]), 'Name': amulet_nbt.TAG_String(pal[0])})
            palette.append(palette_Properties)

        for name, datal in nbt_state_map.items():
            for data in datal:
                if data[0] == None:
                    blocks_pos = amulet_nbt.TAG_Compound({'pos': amulet_nbt.TAG_List(
                        [amulet_nbt.TAG_Int(data[1][0]), amulet_nbt.TAG_Int(data[1][1]),
                         amulet_nbt.TAG_Int(data[1][2])]), 'state': amulet_nbt.TAG_Int(data[2])})
                    blocks.append(blocks_pos)
                else:
                    blocks_pos = amulet_nbt.TAG_Compound({'nbt': amulet_nbt.from_snbt(data[0].nbt.to_snbt()),
                                                          'pos': amulet_nbt.TAG_List(
                                                              [amulet_nbt.TAG_Int(data[1][0]),
                                                               amulet_nbt.TAG_Int(data[1][1]),
                                                               amulet_nbt.TAG_Int(data[1][2])]),
                                                          'state': amulet_nbt.TAG_Int(data[2])})
                    blocks.append(blocks_pos)

        save_it = amulet_nbt.NBTFile()
        save_it['size'] = size
        save_it['entities'] = entities
        save_it['blocks'] = blocks
        save_it['palette'] = palette
        save_it['DataVersion'] = DataVersion
        raw_data = save_it.save_to(compressed=True, little_endian=False)
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

            for x in zip(b_pos, palette, Name, enbt):
                if x[1] != "air":
                    block = Block(str(x[2]).split(':')[0], str(x[2]).split(':')[1], x[1])
                    self.world.set_version_block(xx + x[0][0], yy + x[0][1], zz + x[0][2], self.canvas.dimension,
                                                 (block_platform, block_version), block, x[3])

            self.canvas.run_operation(lambda: self._refresh_chunk(self.canvas.dimension, self.world, xx, zz))

    def _refresh_chunk(self, dimension, world, x, z):
        cx, cz = block_coords_to_chunk_coords(x, z)
        chunk = world.get_chunk(cx, cz, dimension)
        chunk.changed = True

    pass


# simple export options.
export = dict(name="#Nbt Import Export v1.0", operation=NbtImportExport)  # by PremiereHell
