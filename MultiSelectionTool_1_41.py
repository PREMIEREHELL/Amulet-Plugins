import math
from typing import TYPE_CHECKING, Tuple

import amulet_nbt
from amulet.api.wrapper import Interface, EntityIDType, EntityCoordType
import re
import numpy
import urllib.request
import wx
import ast
import os
import string
import os.path
from os import path
import math
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
from leveldb import LevelDB
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
        self.font = wx.Font(13, wx.FONTFAMILY_ROMAN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        self._sizer.Add(side_sizer, 1, wx.TOP | wx.LEFT, 0)
        self._sizer.Add(top_sizer, 0, wx.TOP | wx.LEFT, 290)
        # choicebox for operation mode selection.

        self._run_button = wx.Button(self, label="Set \n Selection Boxs", size=(60, 50))
        #self.info = wx.StaticText(self, label="Need groups of 6 values! \n"
                                              # "Corners Side X,Y,Z, OtherSide X,Y,Z \n "
                                              # "0,0,0,1,1,1 & 1,1,1,0,0,0 Same Block at 0,0,0\n"
                                              # " Hold Ctrl for muti Selections ")
        self._run_button.Bind(wx.EVT_BUTTON, self._run_operation)
        #self.info.SetFont(self.font)

        # side_sizer.Add(self.info)
        self.sx1 = 0
        self.sgb = []
        # self.sel = wx.Button(self, label="Select")
        # self.sel.Bind(wx.EVT_BUTTON, self._sel)
        # side_sizer.Add(self.sel, 10, wx.TOP | wx.LEFT, 5)

        self.gsel = wx.Button(self, label="Get \n Selection Boxs", size=(60, 50))
        self.gsel.Bind(wx.EVT_BUTTON, self._gsel)
        self.g_save = wx.Button(self, label="Save", size=(60, 50))
        self.g_save.Bind(wx.EVT_BUTTON, self.save_data)
        self.g_load = wx.Button(self, label="Load", size=(60, 50))
        self.g_load.Bind(wx.EVT_BUTTON, self.load_data)
        self.g_merge = wx.Button(self, label="Merge Dupes\nDels Text", size=(60, 50))
        self.g_merge.Bind(wx.EVT_BUTTON, self.merge)

        self._up = wx.Button(self, label="Up", size=(36, 35) )
        self._up.Bind(wx.EVT_BUTTON, self._boxUp('m'))
        self._down = wx.Button(self, label="Down", size=(36, 35))
        self._down.Bind(wx.EVT_BUTTON, self._boxDown('m'))
        self._east = wx.Button(self, label="East", size=(36, 35))
        self._east.Bind(wx.EVT_BUTTON, self._boxEast('m'))
        self._west = wx.Button(self, label="West", size=(36, 35))
        self._west.Bind(wx.EVT_BUTTON, self._boxWest('m'))
        self._north = wx.Button(self, label="North", size=(36, 35))
        self._north.Bind(wx.EVT_BUTTON, self._boxNorth('m'))
        self._south = wx.Button(self, label="South", size=(36, 35))
        self._south.Bind(wx.EVT_BUTTON, self._boxSouth('m'))
        self._southeast = wx.Button(self, label="South East", size=(77, 25))
        self._southeast.Bind(wx.EVT_BUTTON, self._boxDiag('se'))
        self._northeast = wx.Button(self, label="North East", size=(77, 25))
        self._northeast.Bind(wx.EVT_BUTTON, self._boxDiag('ne'))
        self._northwest = wx.Button(self, label="North West", size=(77, 25))
        self._northwest.Bind(wx.EVT_BUTTON, self._boxDiag('nw'))
        self._southwest = wx.Button(self, label="South West", size=(77, 25))
        self._southwest.Bind(wx.EVT_BUTTON, self._boxDiag('sw'))

        self._usoutheast = wx.Button(self, label="Up\n South East", size=(77, 30))
        self._usoutheast.Bind(wx.EVT_BUTTON, self._boxDiag('use'))
        self._unortheast = wx.Button(self, label="Up\n North East", size=(77, 30))
        self._unortheast.Bind(wx.EVT_BUTTON, self._boxDiag('une'))
        self._unorthwest = wx.Button(self, label="Up\n North West", size=(77, 30))
        self._unorthwest.Bind(wx.EVT_BUTTON, self._boxDiag('unw'))
        self._usouthwest = wx.Button(self, label="Up\n South West", size=(77, 30))
        self._usouthwest.Bind(wx.EVT_BUTTON, self._boxDiag('usw'))

        self._dsoutheast = wx.Button(self, label="Down\n South East", size=(77, 30))
        self._dsoutheast.Bind(wx.EVT_BUTTON, self._boxDiag('dse'))
        self._dnortheast = wx.Button(self, label="Down\n North East", size=(77, 30))
        self._dnortheast.Bind(wx.EVT_BUTTON, self._boxDiag('dne'))
        self._dnorthwest = wx.Button(self, label="Down\n North West", size=(77, 30))
        self._dnorthwest.Bind(wx.EVT_BUTTON, self._boxDiag('dnw'))
        self._dsouthwest = wx.Button(self, label="Down\n South West", size=(77, 30))
        self._dsouthwest.Bind(wx.EVT_BUTTON, self._boxDiag('dsw'))
        self.lbct = wx.StaticText(self, label="Step:")

        self.lbmove = wx.StaticText(self, label="Move All Selection:")
        self.lbstrech = wx.StaticText(self, label="Stretch Last Selection:")

        self.control = wx.SpinCtrl(self, value="1", min=1, max=1000)


        self.boxgrid_down = wx.GridSizer(1, 4, 1, 1)
        self.boxgrid_u = wx.GridSizer(1, 4, 2, 1)
        self.boxgrid_d = wx.GridSizer(1, 4, 1, 1)
        self.boxgrid_b = wx.GridSizer(1, 8, 1, -16)
        self.boxgrid_b.Add(self._up)
        self.boxgrid_b.Add(self._down)
        self.boxgrid_b.Add(self._east)
        self.boxgrid_b.Add(self._west)
        self.boxgrid_b.Add(self._north)
        self.boxgrid_b.Add(self._south)
        self.boxgrid_b.Add(self.lbct)
        self.boxgrid_b.Add(self.control)

        self.boxgrid_d.Add(self._northeast)
        self.boxgrid_d.Add(self._southeast)
        self.boxgrid_d.Add(self._northwest)
        self.boxgrid_d.Add(self._southwest)


        self.boxgrid_u.Add(self._unortheast)
        self.boxgrid_u.Add(self._usoutheast)
        self.boxgrid_u.Add(self._unorthwest)
        self.boxgrid_u.Add(self._usouthwest)

        self.boxgrid_down.Add(self._dnortheast)
        self.boxgrid_down.Add(self._dsoutheast)
        self.boxgrid_down.Add(self._dnorthwest)
        self.boxgrid_down.Add(self._dsouthwest)

        self.grid = wx.GridSizer(1,5,0,0)
        self.grid.Add(self.g_save)
        self.grid.Add(self.g_load)
        self.grid.Add(self._run_button)
        self.grid.Add(self.gsel)
        self.grid.Add(self.g_merge)
        side_sizer.Add(self.grid, 1, wx.TOP | wx.LEFT, 1)
        side_sizer.Add(self.lbmove)
        side_sizer.Add(self.boxgrid_b, 0, wx.TOP | wx.LEFT, 1)
        side_sizer.Add(self.lbstrech)
        side_sizer.Add(self.boxgrid_d, 0, wx.TOP | wx.LEFT, 1)
        side_sizer.Add(self.boxgrid_u, 0, wx.TOP | wx.LEFT, 1)
        side_sizer.Add(self.boxgrid_down, 0, wx.TOP | wx.LEFT, 1)
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

    def _boxUp(self, v):
        def OnClick(event):
            sgs = []
            print(self.control.GetValue())
            for box in self.canvas.selection.selection_group.selection_boxes:
                xx, yy, zz = box.max_x, box.max_y, box.max_z
                xm, ym, zm = box.min_x, box.min_y, box.min_z
                sgs.append(SelectionBox((xm, ym + self.control.GetValue(), zm), (xx, yy + self.control.GetValue(), zz)))



            self.canvas.selection.set_selection_group(SelectionGroup(sgs))

        return OnClick

    def _boxDown(self, v):
        def OnClick(event):
            sgs = []
            for box in self.canvas.selection.selection_group.selection_boxes:
                xx, yy, zz = box.max_x, box.max_y, box.max_z
                xm, ym, zm = box.min_x, box.min_y, box.min_z
                sgs.append(SelectionBox((xm, ym - self.control.GetValue(), zm), (xx, yy - self.control.GetValue(), zz)))

            self.canvas.selection.set_selection_group(SelectionGroup(sgs))

        return OnClick

    def _boxNorth(self, v):

        def OnClick(event):
            sgs = []
            for box in self.canvas.selection.selection_group.selection_boxes:
                xx, yy, zz = box.max_x, box.max_y, box.max_z
                xm, ym, zm = box.min_x, box.min_y, box.min_z
                sgs.append(SelectionBox((xm, ym, zm - self.control.GetValue()), (xx, yy, zz - self.control.GetValue())))

            self.canvas.selection.set_selection_group(SelectionGroup(sgs))

        return OnClick

    def _boxSouth(self, v):
        def OnClick(event):
            sgs = []
            for box in self.canvas.selection.selection_group.selection_boxes:
                xx, yy, zz = box.max_x, box.max_y, box.max_z
                xm, ym, zm = box.min_x, box.min_y, box.min_z
                sgs.append(SelectionBox((xm, ym, zm + self.control.GetValue()), (xx, yy, zz + self.control.GetValue())))

            if len(sgs) > 0:
                self.canvas.selection.set_selection_group(SelectionGroup(sgs))
        return OnClick

    def _boxEast(self, v):

        def OnClick(event):
            sgs = []
            for box in self.canvas.selection.selection_group.selection_boxes:
                xx, yy, zz = box.max_x, box.max_y, box.max_z
                xm, ym, zm = box.min_x, box.min_y, box.min_z
                sgs.append(SelectionBox((xm + self.control.GetValue(), ym, zm), (xx + self.control.GetValue(), yy, zz)))
            self.canvas.selection.set_selection_group(SelectionGroup(sgs))

        return OnClick

    def _boxWest(self, v):
        def OnClick(event):
            sgs = []
            for box in self.canvas.selection.selection_group.selection_boxes:
                xx, yy, zz = box.max_x, box.max_y, box.max_z
                xm, ym, zm = box.min_x, box.min_y, box.min_z
                sgs.append(SelectionBox((xm - self.control.GetValue(), ym, zm), (xx - self.control.GetValue(), yy, zz)))
            self.canvas.selection.set_selection_group(SelectionGroup(sgs))

        return OnClick


    def _boxDiag(self, v):
        def OnClick(event):
            if v == 'se':
                group = self.canvas.selection.selection_group
                glist = list(group)
                x, y, z = glist[0].point_1
                xx, yy, zz = glist[-1].point_2
                if x > xx and z < zz:
                    glist.reverse()
                for x in range(0, self.control.GetValue()):
                    x, y, z = glist[-1].point_1
                    xx, yy, zz = glist[-1].point_2
                    new = SelectionBox((x + 1, y, z + 1), (xx + 1, yy, zz + 1))
                    glist.append(new)
                    merg = SelectionGroup(glist).merge_boxes()
                    self.canvas.selection.set_selection_group(merg)

            if v == 'nw':
                group = self.canvas.selection.selection_group
                glist = list(group)
                x, y, z = glist[0].point_1
                xx, yy, zz = glist[-1].point_2
                if x < xx and z > zz:
                    glist.reverse()
                for x in range(0, self.control.GetValue()):
                    x, y, z = glist[-1].point_1
                    xx, yy, zz = glist[-1].point_2
                    new = SelectionBox((x - 1, y, z - 1), (xx - 1, yy, zz - 1))
                    glist.append(new)
                    merg = SelectionGroup(glist).merge_boxes()
                    self.canvas.selection.set_selection_group(merg)


            if v == 'ne':
                group = self.canvas.selection.selection_group
                glist = list(group)
                x, y, z = glist[0].point_1
                xx, yy, zz = glist[-1].point_2
                if z < zz:
                    glist.reverse()
                for x in range(0, self.control.GetValue()):
                    x, y, z = glist[-1].point_1
                    xx, yy, zz = glist[-1].point_2
                    new = SelectionBox((x + 1, y, z - 1), (xx + 1, yy, zz - 1))
                    glist.append(new)
                    merg = SelectionGroup(glist).merge_boxes()
                    self.canvas.selection.set_selection_group(merg)

            if v == 'sw':
                group = self.canvas.selection.selection_group
                glist = list(group)
                x, y, z = glist[0].point_1
                xx, yy, zz = glist[-1].point_2
                if z > zz:
                    glist.reverse()
                for x in range(0, self.control.GetValue()):
                    x, y, z = glist[-1].point_1
                    xx, yy, zz = glist[-1].point_2
                    new = SelectionBox((x - 1, y, z + 1), (xx - 1, yy, zz + 1))
                    glist.append(new)
                    merg = SelectionGroup(glist).merge_boxes()
                    self.canvas.selection.set_selection_group(merg)
            if v == 'use':
                group = self.canvas.selection.selection_group
                glist = list(group)
                x, y, z = glist[0].point_1
                xx, yy, zz = glist[-1].point_2
                print(x, xx, y, yy, z, zz)

                if x < xx and z < zz:# and y > yy:
                    glist.reverse()
                for x in range(0, self.control.GetValue()):
                    x, y, z = glist[-1].point_1
                    xx, yy, zz = glist[-1].point_2
                    yy += 1
                    y += 1
                    new = SelectionBox((x + 1, y, z + 1), (xx + 1, yy, zz + 1))
                    glist.append(new)
                    merg = SelectionGroup(glist).merge_boxes()
                    self.canvas.selection.set_selection_group(merg)

            if v == 'unw':
                group = self.canvas.selection.selection_group
                glist = list(group)
                x, y, z = glist[0].point_1
                xx, yy, zz = glist[-1].point_2
                if x > xx and z > zz  and y > yy:
                    glist.reverse()
                for x in range(0, self.control.GetValue()):
                    x, y, z = glist[-1].point_1
                    xx, yy, zz = glist[-1].point_2
                    yy += 1
                    y += 1
                    new = SelectionBox((x - 1, y, z - 1), (xx - 1, yy, zz - 1))
                    glist.append(new)
                    merg = SelectionGroup(glist).merge_boxes()
                    self.canvas.selection.set_selection_group(merg)


            if v == 'une':
                group = self.canvas.selection.selection_group
                glist = list(group)
                x, y, z = glist[0].point_1
                xx, yy, zz = glist[-1].point_2
                if x < xx and z > zz and y > yy:
                    glist.reverse()
                for x in range(0, self.control.GetValue()):
                    x, y, z = glist[-1].point_1
                    xx, yy, zz = glist[-1].point_2
                    yy += 1
                    y += 1
                    new = SelectionBox((x + 1, y, z - 1), (xx + 1, yy, zz - 1))
                    glist.append(new)
                    merg = SelectionGroup(glist).merge_boxes()
                    self.canvas.selection.set_selection_group(merg)

            if v == 'usw':
                group = self.canvas.selection.selection_group
                glist = list(group)
                x, y, z = glist[0].point_1
                xx, yy, zz = glist[-1].point_2
                print(x,xx)
                if x > xx and z < zz  and y > yy:
                    glist.reverse()
                for x in range(0, self.control.GetValue()):
                    x, y, z = glist[-1].point_1
                    xx, yy, zz = glist[-1].point_2
                    yy += 1
                    y += 1
                    new = SelectionBox((x - 1, y, z + 1), (xx - 1, yy, zz + 1))
                    glist.append(new)
                    merg = SelectionGroup(glist).merge_boxes()
                    self.canvas.selection.set_selection_group(merg)






            if v == 'dse':
                group = self.canvas.selection.selection_group
                glist = list(group)
                x, y, z = glist[0].point_1
                xx, yy, zz = glist[-1].point_2
                print(x, xx, y, yy, z, zz)

                if x < xx and z < zz and y < yy:
                    glist.reverse()
                for x in range(0, self.control.GetValue()):
                    x, y, z = glist[-1].point_1
                    xx, yy, zz = glist[-1].point_2
                    yy -= 1
                    y -= 1
                    new = SelectionBox((x + 1, y, z + 1), (xx + 1, yy, zz + 1))
                    glist.append(new)
                    merg = SelectionGroup(glist).merge_boxes()
                    self.canvas.selection.set_selection_group(merg)

            if v == 'dnw':
                group = self.canvas.selection.selection_group
                glist = list(group)
                x, y, z = glist[0].point_1
                xx, yy, zz = glist[-1].point_2
                if x > xx and z > zz and y < yy:
                    glist.reverse()
                for x in range(0, self.control.GetValue()):
                    x, y, z = glist[-1].point_1
                    xx, yy, zz = glist[-1].point_2
                    yy -= 1
                    y -= 1
                    new = SelectionBox((x - 1, y, z - 1), (xx - 1, yy, zz - 1))
                    glist.append(new)
                    merg = SelectionGroup(glist).merge_boxes()
                    self.canvas.selection.set_selection_group(merg)


            if v == 'dne':
                group = self.canvas.selection.selection_group
                glist = list(group)
                x, y, z = glist[0].point_1
                xx, yy, zz = glist[-1].point_2
                if x < xx and z > zz and y < yy:
                    glist.reverse()
                for x in range(0, self.control.GetValue()):
                    x, y, z = glist[-1].point_1
                    xx, yy, zz = glist[-1].point_2
                    yy -= 1
                    y -= 1
                    new = SelectionBox((x + 1, y, z - 1), (xx + 1, yy, zz - 1))
                    glist.append(new)
                    merg = SelectionGroup(glist).merge_boxes()
                    self.canvas.selection.set_selection_group(merg)

            if v == 'dsw':
                group = self.canvas.selection.selection_group
                glist = list(group)
                x, y, z = glist[0].point_1
                xx, yy, zz = glist[-1].point_2
                print(x,xx)
                if x > xx and z < zz and y < yy:
                    glist.reverse()
                for x in range(0, self.control.GetValue()):
                    x, y, z = glist[-1].point_1
                    xx, yy, zz = glist[-1].point_2
                    yy -= 1
                    y -= 1
                    new = SelectionBox((x - 1, y, z + 1), (xx - 1, yy, zz + 1))
                    glist.append(new)
                    merg = SelectionGroup(glist).merge_boxes()
                    self.canvas.selection.set_selection_group(merg)


        return OnClick

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
        prog = re.compile(r'([-+]?\d[\d+]*)(?:\.\d+)?',flags=0) #(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?  r'[-+]?[^(\.\d*)](\d+)+'
        result = prog.findall(data)
        lenofr = len(result)
        cnt = 0
        new_data = ''
        for i, x in enumerate(result):
            cnt += 1
            if cnt < 6:
                new_data += str(int(x))+", "
            else:
                new_data += str(int(x))+'\n'
                cnt = 0
                lenofr -= 6
                if not lenofr > 5:
                    break
        sp = new_data[:-1]
        #self._location_data.SetValue(sp)
        group = []
        for d in sp.split("\n"):
            x, y, z, xx, yy, zz = d.split(",")
            group.append(SelectionBox((int(x), int(y), int(z)), (int(xx), int(yy), int(zz))))
        sel = SelectionGroup(group)
        cleaner = sel.merge_boxes()
        cleaner_data = ''
        for data  in cleaner:
            cleaner_data += f'{data.min[0]},{data.min[1]},{data.min[2]},{data.max[0]},{data.max[1]},{data.max[2]}\n'
        self._location_data.SetValue(cleaner_data[:-1])

    def _run_operation(self, _):
        data = self._location_data.GetValue()
        prog = re.compile(r'([-+]?\d[\d+]*)(?:\.\d+)?',
                          flags=0)  # (?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?  r'[-+]?[^(\.\d*)](\d+)+'
        result = prog.findall(data)
        lenofr = len(result)
        cnt = 0
        new_data = ''
        group = []
        for i, x in enumerate(result):
            cnt += 1
            if cnt < 6:
                new_data += str(int(x)) + ", "
            else:
                new_data += str(int(x)) + '\n'
                cnt = 0
                lenofr -= 6
                if not lenofr > 5:
                    break
        new_data = new_data[:-1]
        for d in new_data.split("\n"):
            x, y, z, xx, yy, zz = d.split(",")
            group.append(SelectionBox((int(x), int(y), int(z)), (int(xx), int(yy), int(zz))))
        sel = SelectionGroup(group)
        cleaner = sel.merge_boxes()
        self.canvas.selection.set_selection_group(cleaner)



    pass

export = dict(name="Multi Selection Tool, v1.41", operation=SetBlock) #By PremiereHell