
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
import amulet_nbt
from amulet.level.formats import mcstructure
import datetime
from pathlib import Path
 

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

        top_sizer = wx.BoxSizer(wx.VERTICAL)
        side_sizer = wx.BoxSizer(wx.HORIZONTAL)
        bottom_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self._sizer.Add(side_sizer, 1, wx.TOP | wx.LEFT, 0)
        self._sizer.Add(top_sizer, 0, wx.TOP| wx.LEFT, 290)
        self._sizer.Add(bottom_sizer, 1, wx.BOTTOM | wx.LEFT,0)



        # choicebox for operation mode selection.
        self._mode = wx.Choice(self, choices=list(operation_modes.keys()))
        self._mode.SetSelection(0)

        side_sizer.Add(self._mode, 0,  wx.TOP | wx.LEFT , 5)



        self._run_getSData_button = wx.Button(self, label="Get Portal Data")
        self._run_getSData_button.Bind(wx.EVT_BUTTON, self._run_get_sdata)
        side_sizer.Add(self._run_getSData_button, 25, wx.BOTTOM | wx.LEFT, 20)

        self._run_setSData_button = wx.Button(self, label="Save Portal \n Data to world ")
        self._run_setSData_button.Bind(wx.EVT_BUTTON, self._run_set_sdata)
        side_sizer.Add(self._run_setSData_button, 0,   wx.TOP | wx.LEFT, 0)
        self._run_setSData_button.Fit()


        self._run_Del_button = wx.Button(self, label="DELETE Portal DATA \n from World")
        self._run_Del_button.Bind(wx.EVT_BUTTON, self._run_Del)
        side_sizer.Add(self._run_Del_button, 0, wx.LEFT, 0)



        self._mode_description = wx.TextCtrl(
            self, style=wx.TE_MULTILINE | wx.TE_BESTWRAP
        )
        self._sizer.Add(self._mode_description, 25, wx.EXPAND | wx.TOP | wx.RIGHT, 0)

        self._mode_description.Fit()

        self.Layout()
        self.Thaw()
    

    @property
    def wx_add_options(self) -> Tuple[int, ...]:
        return (0,)

    def _cls(self):
        print("\033c\033[3J", end='')
    def _fileSave(self):
        print("SAVE")

    def onFocus(self,evt):
        setdata = self._structlist.GetString(self._structlist.GetSelection())
        self._run_text.SetValue(setdata)

    def _refresh_chunk(self, dimension, world, x, z):
       cx, cz = block_coords_to_chunk_coords(x, z)
       chunk = world.get_chunk(cx, cz, dimension)
       chunk.changed = True

    def _run_get_data(self, _):
        world = self.world.level_wrapper._level_manager._db.keys()
        for w in world:
            if b'\xff' not in w:
                if b'\x00' not in w:
                    print(w)
        player = self.world.level_wrapper._level_manager._db.get(b'~local_player')
        data = amulet_nbt.load(player, little_endian=True)
        data2 = []
        self._mode_description.SetValue(str(data))
        #back to bytes
        data2 = data.save_to(compressed=False,little_endian=True)
        print(data2)

    def _run_set_data(self, _):  #b'structuretemplate_mystructure:test'

        player = self.world.level_wrapper._level_manager._db.get(b'~local_player')
        data = self._mode_description.GetValue()
        nbt = from_snbt(data.replace('NBTFile("":',''))
        nbtf = NBTFile(nbt)
        #back to bytes
        data2 = nbtf.save_to(compressed=False,little_endian=True)
        print(data2)
        self.world.level_wrapper._level_manager._db.put(b'~local_player', data2)
        #for p in player:
           #print(p)
    def _run_get_sdata(self, _):

        #sel = self._structlist.GetSelection()
        setdata ="portals"#self._structlist.GetString(self._structlist.GetSelection())
        enS = setdata.encode("utf-8")

        player = self.world.level_wrapper._level_manager._db.get(enS)
        #
        data = amulet_nbt.load(player, little_endian=True)
        data2 = []
        self._mode_description.SetValue(str(data))
        # back to bytes
        data2 = data.save_to(compressed=False, little_endian=True)


        # for p in player:
        #     print(p)

    def _run_set_sdata(self, _):  # b'structuretemplate_mystructure:test'

        portal = "portals"
        theKey = portal.encode("utf-8")
        data = self._mode_description.GetValue()
        nbt = from_snbt(data.replace('NBTFile("":', ''))
        nbtf = NBTFile(nbt)
        # back to bytes
        data2 = nbtf.save_to(compressed=False, little_endian=True)
        print(data2)
        self.world.level_wrapper._level_manager._db.put(theKey, data2)
        # for p in player:
        # print(p)



    def _run_Del(self, _):
        portal = "portals"
        theKey = portal.encode("utf-8")

        wxx = wx.MessageBox("You are going to deleted \n " + str(theKey),
                      "This can't be undone Are you Sure?", wx.OK | wx.CANCEL | wx.ICON_INFORMATION)
        if wxx == int(16):
            return
        self.world.level_wrapper._level_manager._db.delete(theKey)



    pass


#simple export options.
export = dict(name="Edit / Delete Portal Data", operation=SetBlock)
