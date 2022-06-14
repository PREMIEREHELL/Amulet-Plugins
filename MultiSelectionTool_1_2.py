from typing import TYPE_CHECKING, Tuple

import amulet_nbt
from amulet.api.wrapper import Interface, EntityIDType, EntityCoordType

import numpy
import urllib.request
import wx
import ast
import os
import string
import os.path
from os import path

from distutils.version import LooseVersion, StrictVersion
from amulet.api.data_types import Dimension
from amulet.api.selection import SelectionGroup
from amulet.api.selection import SelectionBox
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
import datetime
from pathlib import Path
from ctypes import windll
from amulet.api.data_types import PointCoordinates
from amulet_map_editor.programs.edit.api.behaviour import StaticSelectionBehaviour
from amulet_map_editor.programs.edit.api.events import EVT_SELECTION_CHANGE
from amulet_map_editor.programs.edit.api.behaviour import BlockSelectionBehaviour
from amulet_map_editor.programs.edit.api.behaviour.pointer_behaviour import EVT_POINT_CHANGE
from amulet_map_editor.programs.edit.api.behaviour.pointer_behaviour import PointChangeEvent
from amulet_map_editor.programs.edit.api.behaviour.pointer_behaviour import PointerBehaviour
from amulet_map_editor.programs.edit.api.key_config import ACT_BOX_CLICK
from amulet_map_editor.programs.edit.api.events import (
    EVT_PASTE,
    InputPressEvent,
    EVT_INPUT_PRESS,
)
if TYPE_CHECKING:
    from amulet.api.level import BaseLevel
    from amulet_map_editor.programs.edit.api.canvas import EditCanvas
operation_modes = {
    "Java": "java",
    "Bedrock": "bedrock",
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
        self._is_enabled = True
        self._moving = True
        self._sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self._sizer)

        options = self._load_options({})
        top_sizer = wx.BoxSizer(wx.VERTICAL)
        side_sizer = wx.BoxSizer(wx.VERTICAL)
        self.font = wx.Font(16, wx.FONTFAMILY_ROMAN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        self._sizer.Add(side_sizer, 1, wx.TOP | wx.LEFT, 0)
        self._sizer.Add(top_sizer, 0, wx.TOP | wx.LEFT, 290)
        # choicebox for operation mode selection.

        self._run_button = wx.Button(self, label="Set Selection Boxs")
        self.info = wx.StaticText(self, label="Each line = x,y,z,x,y,z \n Hold Ctrl for muti Selections ")
        self._run_button.Bind(wx.EVT_BUTTON, self._run_operation)
        self.info.SetFont(self.font)

        side_sizer.Add(self.info)

        # self.sel = wx.Button(self, label="Select")
        # self.sel.Bind(wx.EVT_BUTTON, self._sel)
        # side_sizer.Add(self.sel, 10, wx.TOP | wx.LEFT, 5)

        self.gsel = wx.Button(self, label="Get Selection /'s")
        self.gsel.Bind(wx.EVT_BUTTON, self._gsel)
        self.g_save = wx.Button(self, label="Save")
        self.g_save.Bind(wx.EVT_BUTTON, self.save_data)
        self.g_load = wx.Button(self, label="Load")
        self.g_load.Bind(wx.EVT_BUTTON, self.load_data)
        self.g_merge = wx.Button(self, label="Merge")
        self.g_merge.Bind(wx.EVT_BUTTON, self.merge)

        self.grid = wx.GridSizer(3,2,8,8)
        self.grid.Add(self.g_save)
        self.grid.Add(self.g_load)
        self.grid.Add(self._run_button)
        self.grid.Add(self.gsel)
        self.grid.Add(self.g_merge)
        side_sizer.Add(self.grid, 10, wx.TOP | wx.LEFT, 5)

        # self.getc = wx.Button(self, label="Get Cords")
        # self.getc.Bind(wx.EVT_BUTTON, self._getc)
        # side_sizer.Add(self.getc, 10, wx.TOP | wx.LEFT, 5)

        self._location_data = wx.TextCtrl(
            self, style=wx.TE_MULTILINE | wx.TE_BESTWRAP
        )
        
        self._sizer.Add(self._location_data, 25, wx.EXPAND | wx.LEFT | wx.RIGHT, 0)
        self._location_data.SetFont(self.font)
        self._location_data.SetForegroundColour((0, 255, 0))
        self._location_data.SetBackgroundColour((0, 0, 0))
        self._location_data.Fit()

        self.Layout()
        self.Thaw()




    @property
    def wx_add_options(self) -> Tuple[int, ...]:

        return (0,)

    def _cls(self):

        print("\033c\033[3J", end='')

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

    def location(self) -> PointCoordinates:
        return self._location.value

    def _gsel(self, _):
        for box in self.canvas.selection.selection_group.selection_boxes:
            newl = ""
            if self._location_data.GetValue() != "":
                newl = "\n"
            print(str(box.min_z) +","+ str(box.min_y) +","+str(box.min_z)+","+str(box.max_x)+","+str(box.max_y)+","+str(box.max_z))
            self._location_data.SetValue(self._location_data.GetValue()+newl+str(box.min_x) +","+ str(box.min_y) +","+str(box.min_z)+","+str(box.max_x)+","+str(box.max_y)+","+str(box.max_z))

    def _getc(self):

        print(str(self.canvas.selection.selection_group.selection_boxes).replace("(SelectionBox((","").replace(")),)","")
              .replace("(","").replace(")","").replace(" ",""))
        newl = ""
        if self._location_data.GetValue() != "":
            newl = "\n"
        self._location_data.SetValue(self._location_data.GetValue()+ newl + str(self.canvas.selection.selection_group.selection_boxes).replace("(SelectionBox((","").replace(")),)","")
              .replace("(","").replace(")","").replace(" ","") )

    def merge(self, _):
        data = self._location_data.GetValue()
        dataxyz = data.split("\n")
        group = []
        for d in dataxyz:
            x, y, z, xx, yy, zz = d.split(",")
            group.append(SelectionBox((int(x), int(y), int(z)), (int(xx), int(yy), int(zz))))
        sel = SelectionGroup(group)
        new_text = ''
        new_data = sel.merge_boxes()
        for data  in new_data:

            new_text += f'{data.min[0]},{data.min[1]},{data.min[2]},{data.max[0]},{data.max[1]},{data.max[2]}\n'
        self._location_data.SetValue(new_text[:-1])


    def _run_operation(self, _):

        data = self._location_data.GetValue()
        dataxyz = data.split("\n")

        group = []
        for d in dataxyz:
            x,y,z,xx,yy,zz = d.split(",")
            group.append(SelectionBox((int(x),int(y),int(z)),(int(xx),int(yy),int(zz))))
        sel = SelectionGroup(group)
        print(sel.merge_boxes())
        self.canvas.selection.set_selection_group(sel.merge_boxes())


    pass

export = dict(name="Multi Selection Tool, v1.22", operation=SetBlock) #By PremiereHell