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
#  (
#     PointerBehaviour,
#     EVT_POINT_CHANGE,
#     PointChangeEvent,
# )
from amulet_map_editor.programs.edit.api.events import (
    EVT_PASTE,
    InputPressEvent,
    EVT_INPUT_PRESS,
)
from amulet_map_editor.programs.edit.api.behaviour.block_selection_behaviour import (
    BlockSelectionBehaviour,
    EVT_RENDER_BOX_CHANGE,
    RenderBoxChangeEvent,
    EVT_RENDER_BOX_DISABLE_INPUTS,
    EVT_RENDER_BOX_ENABLE_INPUTS,
)

# from amulet.level.formats.leveldb_world import  format

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
        side_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self._sizer.Add(side_sizer, 1, wx.TOP | wx.LEFT, 0)
        self._sizer.Add(top_sizer, 0, wx.TOP | wx.LEFT, 290)
        # choicebox for operation mode selection.






        self._run_button = wx.Button(self, label="Set Selection Boxs")
        self.info = wx.StaticText(self, label="Each line ( x,y,z,x,y,z ) ")
        self._run_button.Bind(wx.EVT_BUTTON, self._run_operation)
        side_sizer.Add(self._run_button, 10, wx.TOP | wx.LEFT, 5)
        side_sizer.Add(self.info)

        self.sel = wx.Button(self, label="Select")
        self.sel.Bind(wx.EVT_BUTTON, self._sel)
        side_sizer.Add(self.sel, 10, wx.TOP | wx.LEFT, 5)

        # self.getc = wx.Button(self, label="Get Cords")
        # self.getc.Bind(wx.EVT_BUTTON, self._getc)
        # side_sizer.Add(self.getc, 10, wx.TOP | wx.LEFT, 5)


        self._mode_description = wx.TextCtrl(
            self, style=wx.TE_MULTILINE | wx.TE_BESTWRAP
        )
        self._sizer.Add(self._mode_description, 25, wx.EXPAND | wx.LEFT | wx.RIGHT, 0)

        self._mode_description.Fit()
        self.click = False

        self.Layout()
        self.Thaw()

        self._sel


        #self._on_pointer_change()

    @property
    def wx_add_options(self) -> Tuple[int, ...]:

        return (0,)

    def _cls(self):

        print("\033c\033[3J", end='')

    def location(self) -> PointCoordinates:
        return self._location.value

    def _getc(self):

        print(str(self.canvas.selection.selection_group.selection_boxes).replace("(SelectionBox((","").replace(")),)","")
              .replace("(","").replace(")","").replace(" ",""))
        newl = ""
        if self._mode_description.GetValue() != "":
            newl = "\n"
        self._mode_description.SetValue(self._mode_description.GetValue()+ newl + str(self.canvas.selection.selection_group.selection_boxes).replace("(SelectionBox((","").replace(")),)","")
              .replace("(","").replace(")","").replace(" ","") )

    def _sel(self, _):
        self._selection = StaticSelectionBehaviour(self.canvas)
        self._curs = PointerBehaviour(self.canvas)
        self._selection.bind_events()
        self._curs.bind_events()
        self.canvas.Bind(EVT_POINT_CHANGE, self._on_pointer_change)
        self.canvas.Bind(EVT_INPUT_PRESS, self._on_input_press)
        self.click = True
        self._is_enabled = True
        self._moving = True
        self._on_pointer_change

    def _on_pointer_change(self, evt: PointChangeEvent):
        if self._is_enabled or self.click:
            self.canvas.renderer.fake_levels.active_transform = (
                evt.point
            )
            x, y, z = evt.point
            #a, b, c = self.abc
            a, b, c = 1,1,1
            sg = SelectionGroup(SelectionBox((x, y, z), (x + a, y + b, z + c)))
            self.canvas.selection.set_selection_group(sg)

        evt.Skip()

    def _on_input_press(self, evt: InputPressEvent):

        if self.click == True:
            self._getc()

        if evt.action_id == ACT_BOX_CLICK:

            if self._is_enabled == True:
                self._moving = not self._moving
                self._is_enabled = False


                return
            if self._is_enabled == False:

                self._is_enabled = True


                return
            if self._moving:
                self.canvas.renderer.fake_levels.active_transform = ()

        evt.Skip()
    def _run_operation(self, _):
        self._is_enabled = False
        self._moving = False
        self.click = False
        self.canvas.Unbind(EVT_POINT_CHANGE)
        self.canvas.Unbind(EVT_INPUT_PRESS)

        data = self._mode_description.GetValue()
        dataxyz = data.split("\n")
        print(dataxyz)
        group = []
        for d in dataxyz:
            x,y,z,xx,yy,zz = d.split(",")
            group.append(SelectionBox((int(x),int(y),int(z)),(int(xx),int(yy),int(zz))))
        sel = SelectionGroup(group)

        self.canvas.selection.set_selection_group(sel)

    pass


# simple export options.
export = dict(name="Multi Selection Tool, v1.1", operation=SetBlock) #By PremiereHell