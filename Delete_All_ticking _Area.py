
from typing import TYPE_CHECKING, Tuple

import amulet.level
from amulet.api.wrapper import Interface, EntityIDType, EntityCoordType

import numpy
import urllib.request
import wx
import wx.dataview
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
from amulet.libs.leveldb.leveldb import LevelDB
import amulet_nbt
from amulet.level.formats import mcstructure
import datetime
from pathlib import Path
#from amulet.level.formats.leveldb_world import  format

if TYPE_CHECKING:


    from amulet.api.level import BaseLevel
    from amulet_map_editor.programs.edit.api.canvas import EditCanvas


operation_modes = {
        #"Java": "java",
        "Bedrock ONLY for now": "bedrock",
    }
class SetBlock(wx.Panel, DefaultOperationUI):


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
        hbox = wx.wxEVT_VLBOX


        wx.Panel.__init__(self, parent)
        DefaultOperationUI.__init__(self, parent, canvas, world, options_path)
        self.Freeze()

        self._sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self._sizer)


        side_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self._sizer.Add(side_sizer, 1, wx.TOP | wx.LEFT, 0)



        self._run_Del_button = wx.Button(self, label="DELETE tickingarea DATA \n from World")
        self._run_Del_button.Bind(wx.EVT_BUTTON, self._run_del_tdata)
        side_sizer.Add(self._run_Del_button, 0, wx.LEFT, 0)





        self.Layout()
        self.Thaw()
    

    @property
    def wx_add_options(self) -> Tuple[int, ...]:
        return (0,)

    def _cls(self):
        print("\033c\033[3J", end='')
    def _run_del_tdata(self, _):
        world = self.world.level_wrapper._level_manager._db.keys()

        for w in world:
            if b'\xff' not in w:
                if b'\x00' not in w:
                    print(w, "LIST Of readable Keys")
                    if b'tickingarea_' in w:
                        self.world.level_wrapper._level_manager._db.delete(w)
                        print("deleted", w)

    pass


#simple export options.
export = dict(name="=Delete All tickingarea Data", operation=SetBlock)
