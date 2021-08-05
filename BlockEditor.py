
from typing import TYPE_CHECKING, Tuple
from amulet.api.wrapper import Interface, EntityIDType, EntityCoordType

import numpy
import urllib.request
import wx
import ast
import os
import string
import os.path
from os import path
from ctypes import windll
from distutils.version import LooseVersion, StrictVersion
from amulet.api.data_types import Dimension
from amulet.api.selection import SelectionGroup
from amulet_nbt import *
from amulet.api.block_entity import BlockEntity
from amulet_map_editor.api.wx.ui.simple import SimpleDialog
from amulet_map_editor.api.wx.ui.block_select import BlockDefine
from amulet_map_editor.api.wx.ui.block_select import BlockSelect
from amulet_map_editor.programs.edit.api.operations import DefaultOperationUI
from amulet_map_editor.api.wx.ui.base_select import BaseSelect
from amulet_map_editor.api import image
from amulet.utils import block_coords_to_chunk_coords
from amulet.api.block import Block
import PyMCTranslate
from amulet_map_editor.api.wx.ui.base_select import BaseSelect

if TYPE_CHECKING:
    from amulet.api.level import BaseLevel
    from amulet_map_editor.programs.edit.api.canvas import EditCanvas

class SetLootTables(wx.Panel, DefaultOperationUI):
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
        self.Freeze()

        self._sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self._sizer)

        options = self._load_options({})
        top_sizer = wx.BoxSizer(wx.VERTICAL)
        self._sizer.Add(top_sizer, 1, wx.EXPAND | wx.LEFT, 290)

        self._run_button = wx.Button(self, label="Get Block")
        self._run_button.Bind(wx.EVT_BUTTON, self._run2_operation)
        top_sizer.Add(self._run_button, 0,  wx.LEFT, 0)

        self._run_button = wx.Button(self, label="Set Block")
        self._run_button.Bind(wx.EVT_BUTTON, self._run_operation)
        top_sizer.Add(self._run_button, 10,  wx.TOP | wx.LEFT, 0)

        self._mode_description = wx.TextCtrl(
            self, style=wx.TE_MULTILINE | wx.TE_BESTWRAP
        )
        self._sizer.Add(self._mode_description, 15, wx.EXPAND | wx.LEFT | wx.RIGHT, 0)

        self._mode_description.Fit()

        self.Layout()
        self.Thaw()
    

    @property
    def wx_add_options(self) -> Tuple[int, ...]:
        return (0,)

    def _cls(self):
        print("\033c\033[3J", end='')

    def _run_operation(self, _):
        block_platform = "bedrock"
        block_version = (1, 17, 0)
        data = self._mode_description.GetValue()
        NBT = None
        direction = 2
        Snbt = from_snbt("[]")
        posBlocknameStart = data.find(":")+1
        posBlocknameEnd =  data.find("[")
        posBlockDataStart = data.find("[") + 1
        posBlockDataEnd = data.find("]")
        blockName = data[posBlocknameStart:posBlocknameEnd]
        fixedBlockFormat = data[posBlockDataStart:posBlockDataEnd].replace("=", ":")
        if "[" in data:
            Snbt = from_snbt("{"+fixedBlockFormat+"}")
        else:
           blockName = data[posBlocknameStart:data.find("|")]
        block = Block("minecraft", blockName, dict(Snbt))

        if "BlockEntity" in data:
            entity = data.find('NBTFile')+11
            NBT = from_snbt(data[entity:])
            print(NBT)
        blockEntity = BlockEntity("minecraft", blockName.replace('_','').capitalize(),0,0,0, NBTFile(NBT))
        print(str(blockEntity))
        for (box) in (self.canvas.selection.selection_group):
            pos = px, py, pz = box.min_x, box.min_y, box.min_z
            self.world.set_version_block(px, py, pz, self.canvas.dimension, (block_platform, block_version), block, blockEntity)
            self.canvas.run_operation(lambda: self._refresh_chunk(self.canvas.dimension, self.world, px, pz))

    def _refresh_chunk(self, dimension, world, x, z):
       cx, cz = block_coords_to_chunk_coords(x, z)
       chunk = world.get_chunk(cx, cz, dimension)
       chunk.changed = True
    def _run2_operation( self, _):
        block_platform = "bedrock"
        block_version = (1, 17, 0)
        for (box) in (self.canvas.selection.selection_group):
            pos = px, py, pz = box.min_x, box.min_y, box.min_z
            block, blockEntity = self.world.get_version_block(px, py, pz, self.canvas.dimension, (block_platform, block_version))
            self._mode_description.SetValue(str(block) +"|"+ str(blockEntity).replace('\n\n\n',''))


    pass

#simple export options.
export = dict(name="A Block editor", operation=SetLootTables)
