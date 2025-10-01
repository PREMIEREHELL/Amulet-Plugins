import amulet_nbt
import wx
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
from amulet_map_editor.programs.edit.api.events import (
    EVT_SELECTION_CHANGE,
)


if TYPE_CHECKING:
    from amulet.api.level import BaseLevel
    from amulet_map_editor.programs.edit.api.canvas import EditCanvas

class SetBlocks(wx.Panel, DefaultOperationUI):

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
        options = self._load_options({})
        top_sizer = wx.BoxSizer(wx.VERTICAL)
        side_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.f_label = wx.StaticText(self, label="Find: ")
        self.r_label = wx.StaticText(self, label="Replace: ")
        self.find = wx.TextCtrl(self, style=wx.TE_LEFT, size=(100, 25))
        self.rep = wx.TextCtrl(self, style=wx.TE_LEFT, size=(100, 25))
        self._sizer.Add(side_sizer, 1, wx.TOP | wx.LEFT, 0)
        self._sizer.Add(top_sizer, 0, wx.TOP | wx.LEFT, 20)
        self._run_button = wx.Button(self, label="Save")
        self._run_button.Bind(wx.EVT_BUTTON, self._run_operation)
        self.apply_rep = wx.Button(self, label="Replace")
        self.apply_rep.Bind(wx.EVT_BUTTON, self._apply_rep)
        side_sizer.Add(self.f_label)
        side_sizer.Add(self.find)
        side_sizer.Add(self.r_label)
        side_sizer.Add(self.rep)
        self.grid_size = wx.GridSizer(2,0,7,0)
        self.grid_size.Add(self.apply_rep)
        self.grid_size.Add(self._run_button)

        self.univeral_mode = wx.CheckBox(self, label="Use Universal Block \n (Good to see and edit extra blocks)", pos=(35,25))
        self.univeral_mode.SetValue(True)

        side_sizer.Add(self.grid_size, 1, wx.LEFT, 0)

        self._raw_text = wx.TextCtrl(
            self, style=wx.TE_MULTILINE | wx.TE_BESTWRAP, size=(340,600)
        )
        #self._sizer.Add(self.univeral_mode)
        self._sizer.Add(self._raw_text, 25, wx.EXPAND | wx.TOP | wx.RIGHT, 0)
        self._raw_text.Fit()
        self.Layout()
        self.Thaw()

    def _apply_rep(self, _):
        data = self._raw_text.GetValue()
        new_data = data.replace(self.find.GetValue(),self.rep.GetValue())
        self._raw_text.SetValue(new_data)

    def bind_events(self):
        super().bind_events()
        self.canvas.Bind(EVT_SELECTION_CHANGE, self._run2_operation)
        self._selection.bind_events()
        self._selection.enable()

    def enable(self):
        self._selection = BlockSelectionBehaviour(self.canvas)
        self._selection.enable()

    def _run_operation(self, _):
        block_platform = self.world.level_wrapper.platform
        block_version = self.world.level_wrapper.version
        the_name_space = "minecraft"
        if self.univeral_mode.GetValue():
            block_platform = "universal"
            the_name_space = "universal_minecraft"
        data = self._raw_text.GetValue()
        data_arr = data.split('<Block_Location>\n')
        x , y , z = 0, 0, 0
        for i, da in enumerate(data_arr):
            if i > 0:
                pos_block = da.split('\n<Block_name>\n')
                pos_s = pos_block[0][1:].replace("(","").replace(")","").replace(' ',"") .split(",")
                x , y , z  = int(pos_s[0]),int(pos_s[1]),int(pos_s[2])
                block_name = pos_block[1].split("\n<Block_properties>\n")[0]
                block_pro = pos_block[1].split("\n<Block_properties>\n")[1].split('\n<Block_Entity>\n')[0]

                block_enty_extra_q = pos_block[1].split("<Block_properties>"
                                                          "\n")[1].split('\n<Block_Entity>\n')[1].split("\n<Extra_Block>\n")


                block_enty_data_snbt = block_enty_extra_q[0]
                extra_block = block_enty_extra_q[1].split('\n_EOF\n')[0]

                block_enty_name = block_enty_data_snbt.split(':\n:')[0]
                if "None" not in str(extra_block):
                    extra_block_name = extra_block.split("<ExtraBlockName>"
                                            "\nuniversal_minecraft:")[1].split("\n<ExtraBlockProperties>\n")[0]
                    extra_block_properties = amulet_nbt.from_snbt(extra_block.split("<ExtraBlockName>"
                                            "\nuniversal_minecraft:")[1].split("\n<ExtraBlockProperties>\n")[1])
                    an_extra_block = Block('universal_minecraft',extra_block_name, dict(extra_block_properties))
                if "None" not in str(block_enty_data_snbt):
                    _data_snbt = block_enty_data_snbt.split(':\n:')[1]
                else:
                    _data_snbt = None
                if "None" not in str(extra_block):
                    new_block = Block(block_name.split(":")[0], block_name.split(":")[1],
                                      dict(amulet_nbt.from_snbt(block_pro)),an_extra_block)
                else:
                    new_block = Block(block_name.split(":")[0], block_name.split(":")[1],
                                      dict(amulet_nbt.from_snbt(block_pro)))
                block_entitiy = None
                if "None" not in str(block_enty_data_snbt):
                    block_entitiy = BlockEntity( the_name_space,block_enty_name
                                                , 0, 0, 0, amulet_nbt.NBTFile(amulet_nbt.from_snbt(_data_snbt)))
                self.world.set_version_block(x,y,z,self.canvas.dimension,
                ((block_platform, block_version)),new_block,block_entitiy)
        self.canvas.run_operation(lambda: self._refresh_chunk(self.canvas.dimension, self.world, x, z))

    def _refresh_chunk(self, dimension, world, x, z):
        cx, cz = block_coords_to_chunk_coords(x, z)
        chunk = world.get_chunk(cx, cz, dimension)
        chunk.changed = True

    def _run2_operation(self, _):
        block_platform = self.world.level_wrapper.platform
        block_version =  self.world.level_wrapper.version
        if self.univeral_mode.GetValue():
            block_platform = "universal"
        string_data = ""

        for x , y ,z  in (self.canvas.selection.selection_group.blocks):
            extra_block = None
            block, blockEntity = self.world.get_version_block(x, y, z, self.canvas.dimension,
                                                              (block_platform, block_version))

            data_str = "None"
            try:
                SpData = blockEntity.nbt
                data_str = f"{blockEntity._base_name}:\n:{SpData.to_snbt(1)}"
            except:
                SpData = None
            if block._extra_blocks:
                extra = block._extra_blocks[0]
                extra_property = amulet_nbt.from_snbt(str(extra.properties))
                extra_block = f"<ExtraBlockName>\n{extra._namespaced_name}\n<ExtraBlockProperties>\n" \
                              f"{extra_property.to_snbt(1)}"

            block_property = amulet_nbt.from_snbt(str(block.properties))
            string_data += f"<Block_Location>\n{x,y,z}\n<Block_name>\n{block._namespaced_name}\n<Block_properties>" \
                           f"\n{block_property.to_snbt(1)}\n<Block_Entity>\n{data_str}\n<Extra_Block>\n{extra_block}\n_EOF\n"
        self._raw_text.SetValue(string_data)
    pass
export = dict(name="# A Muti Block editor v.1.00", operation=SetBlocks) #By PremiereHell