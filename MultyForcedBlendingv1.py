import math
from typing import TYPE_CHECKING, Tuple
from amulet.utils import world_utils
import amulet_nbt
from amulet.api.wrapper import Interface, EntityIDType, EntityCoordType
import re
import numpy
import urllib.request
import wx
import ast
import os
from os.path import exists
from amulet.level.formats.anvil_world.region import AnvilRegion
import string
import os.path
from os import path
import math
import collections
import struct
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
import leveldb
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
class MultiForcedBlending(wx.Panel, DefaultOperationUI):

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
        mid_sizer = wx.BoxSizer(wx.VERTICAL)
        side_sizer = wx.BoxSizer(wx.VERTICAL)
        self.font = wx.Font(13, wx.FONTFAMILY_ROMAN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        self._sizer.Add(side_sizer, 1, wx.TOP | wx.LEFT, 0)
        self._sizer.Add(mid_sizer, 0, wx.TOP | wx.LEFT, 5)
        self._sizer.Add(top_sizer, 0, wx.TOP | wx.LEFT, 290)
        # choicebox for operation mode selection.

        self._delete_unselected_chunks = wx.Button(self, label="Delete \n Unselected \nChunks", size=(100, 40))
        self._force_blending = wx.Button(self, label="Force \n Blending", size=(100, 40))
        self._force_blending.Bind(wx.EVT_BUTTON, self._force_blening_window)
        self._force_relighting = wx.Button(self, label="Force\n Relighting", size=(100, 40))
        self._force_relighting.Bind(wx.EVT_BUTTON, self.force_relighting)
        self._delete_unselected_chunks.Bind(wx.EVT_BUTTON, self.delete_unselected)

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

        if self.world.level_wrapper.platform == "java":

            self.box_mid = wx.GridSizer(1, 3, 1, -11)
            self.box_mid.Add(self._force_relighting)
        else:
            self._force_relighting.Hide()
            self.box_mid = wx.GridSizer(1, 2, 1, 1)
        self.box_mid.Add(self._delete_unselected_chunks)
        self.box_mid.Add(self._force_blending)

        mid_sizer.Add(self.box_mid)
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

    def force_relighting(self, _):
        self._gsel(_)
        self.merge(_)
        self._set_seletion()
        selected_chunks = self.canvas.selection.selection_group.chunk_locations()
        if len(selected_chunks) == 0:
            wx.MessageBox(" You Must Select An area or have an area in the list",
                          "Information", style=wx.OK | wx.STAY_ON_TOP | wx.CENTRE,
                          parent=self.Parent)

        loaction_dict = collections.defaultdict(list)
        if self.world.level_wrapper.platform == "java":

            for xx, zz in selected_chunks:
                rx, rz = world_utils.chunk_coords_to_region_coords(xx, zz)
                loaction_dict[(rx, rz)].append((xx, zz))

            for rx, rz in loaction_dict.keys():
                file_exists = exists(self.get_dim_vpath_java_dir(rx, rz))
                if file_exists:
                    for di in loaction_dict[(rx, rz)]:
                        cx, cz = di

                        self.raw_data = AnvilRegion(self.get_dim_vpath_java_dir(rx, rz))
                        if self.raw_data.has_chunk(cx % 32, cz % 32):
                            nbt_data = self.raw_data.get_chunk_data(cx % 32, cz % 32)
                            nbt_data.pop('isLightOn', None)
                            
                            self.raw_data.put_chunk_data(cx % 32, cz % 32, nbt_data)
                        self.raw_data.save()
            self.world.save()
            wx.MessageBox(" Lighting will now regenerate in the selected chunk\s",
                          "Information", style=wx.OK | wx.STAY_ON_TOP | wx.CENTRE,
                          parent=self.Parent)


    def delete_unselected(self, _):
        try:
            self.frame.Hide()
            self.frame.Close()
        except:
            pass
        self._gsel(_)
        self.merge(_)
        self._set_seletion()
        selected_chunks = self.canvas.selection.selection_group.chunk_locations()
        self.frame = wx.Frame(self.parent.Parent, id=wx.ID_ANY, pos=wx.DefaultPosition, size=(400, 700),
                              style=(
                                      wx.MINIMIZE_BOX | wx.MAXIMIZE_BOX | wx.RESIZE_BORDER | wx.SYSTEM_MENU | wx.CAPTION | wx.CLOSE_BOX | wx.CLIP_CHILDREN | wx.FRAME_FLOAT_ON_PARENT),
                              name="Panel",
                              title="CHUNKS")
        sizer_P = wx.BoxSizer(wx.VERTICAL)
        self.frame.SetSizer(sizer_P)
        self.textGrid = wx.TextCtrl(self.frame, style=wx.TE_MULTILINE | wx.TE_BESTWRAP, size=(400, 750))
            #self.buttons = wx.Button(self.frame, label=str(x)+","+str(z), size=(60, 50))
        self.textGrid.SetValue("This is the list of Chunk That will be saved:\n" +str(selected_chunks))
        self.textGrid.SetFont(self.font)
        self.textGrid.SetForegroundColour((0, 255, 0))
        self.textGrid.SetBackgroundColour((0, 0, 0))
        sizer_P.Add(self.textGrid)

        self.frame.Show(True)
        result = wx.MessageBox(" Delete All other Chunks? ", "Question", style=wx.YES_NO|wx.STAY_ON_TOP|wx.CENTRE, parent=self.frame,  )
        if result == 2:
            all_chunks = self.world.all_chunk_coords(self.canvas.dimension)
            self.textGrid.AppendText("These Chunks were deleted:")
            for chunk in all_chunks:
                if chunk not in selected_chunks:
                    self.textGrid.AppendText(str(chunk))
                    self.canvas.world.level_wrapper.delete_chunk(chunk[0], chunk[1], self.canvas.dimension)
            self.world.save()
            self.world.purge()
            self.canvas.renderer.render_world.unload()
            self.canvas.renderer.render_world.enable()
            result = wx.MessageBox(" All These Chunks Deleted,  Close Chunk Window info list",
                                       "Information, Question", style=wx.YES_NO | wx.STAY_ON_TOP | wx.CENTRE,
                                       parent=self.Parent)
            if result == 2:
                self.frame.Hide()
                self.frame.Close()
        else:
            self.frame.Hide()
            self.frame.Close()






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

    def _set_seletion(self):
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
    def _run_operation(self, _):
        self._set_seletion()

    def _force_blening_window(self, _):
        self.frame = wx.Frame(self.parent.Parent, id=wx.ID_ANY, pos=wx.DefaultPosition, size=(460, 500),
                              style=(
                                      wx.MINIMIZE_BOX | wx.MAXIMIZE_BOX | wx.RESIZE_BORDER | wx.SYSTEM_MENU | wx.CAPTION | wx.CLOSE_BOX | wx.CLIP_CHILDREN | wx.FRAME_FLOAT_ON_PARENT),
                              name="Panel")
        self.font2 = wx.Font(16, wx.FONTFAMILY_ROMAN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)

        self.info_label = wx.StaticText(self.frame, label="There is No Undo Make a backup!", size=(440, 20))
        self.info_label2 = wx.StaticText(self.frame, label="How It Works:\n"
                                                           "The Overworld:\n "
                                                           "Requires at least one chunk border of deleted chunks"
                                                           " Blending happens when existing terrain blends in with seed "
                                                           "generated terrain.\n Water surrounds if below 62 and the cut off is 255\n"
                                                            "The Nether:  !Untested In Java\n"
                                                           "You will want chunks to be around your builds. "
                                                           "Not Really blending, But it looks better than 16x16 flat walls.  "
                                                           "The End:\n"
                                                           "Has not been updated yet and does not appear to have any "
                                                           "blending options as of yet.\n"
                                                           "Blending Does not require a seed change,\n"
                                                           "A simple biome change, pasted in chunks, higher terrain blocks "
                                                           "or structures(Recalculate Heightmap)\n "
                                                           "Terrain blocks are also required for the overworld it will "
                                                           "blend from them, it wont blend from none terrain type blocks"
                                                           "\nManual Seed changes or algorithmic seed changes are what make old "
                                                           "terrain not match up to existing chunks without blending.\n"

                                                           , size=(440, 492))

        self.info_label2.SetFont(self.font2)
        self.info_label.SetFont(self.font2)
        self.info_label.SetForegroundColour((255, 0, 0))
        self.info_label.SetBackgroundColour((0, 0, 0))
        self.info_label2.SetForegroundColour((0, 200, 0))
        self.info_label2.SetBackgroundColour((0, 0, 0))
        self._all_chunks = wx.CheckBox(self.frame, label="All Chunks")

        self._all_chunks.SetFont(self.font2)

        self._recal_heightmap = wx.CheckBox(self.frame, label="Recalculate Heightmap( only needed in overworld \nfor pasted chunks or structures)")
        self._recal_heightmap.SetFont(self.font2)
        self._all_chunks.SetValue(True)
        self._recal_heightmap.SetValue(False)
        self._sizer = wx.BoxSizer(wx.VERTICAL)
        self.frame.SetSizer(self._sizer)
        side_sizer = wx.BoxSizer(wx.VERTICAL)
        self._sizer.Add(side_sizer)

        self._run_button = wx.Button(self.frame, label="Force Blending")
        self._run_button.SetFont(self.font2)
        self.seed = wx.Button(self.frame, label="(Save new seed)")
        self.seed_input = wx.TextCtrl(self.frame, style=wx.TE_LEFT, size=(220, 25))
        self.seed_input.SetFont(self.font2)
        if self.seed_input.GetValue() == "":
            if self.world.level_wrapper.platform == "java":
                self.seed_input.SetValue(
                    str(self.world.level_wrapper.root_tag['Data']['WorldGenSettings']['seed']))
                self._recal_heightmap.Hide()

            else:
                self.seed_input.SetValue(str(self.world.level_wrapper.root_tag['RandomSeed']))
        self._run_button.Bind(wx.EVT_BUTTON, self._refresh_chunk)
        self.seed.Bind(wx.EVT_BUTTON, self.set_seed)
        side_sizer.Add(self.info_label, 0, wx.LEFT, 11)
        side_sizer.Add(self.info_label2, 0, wx.LEFT, 11)
        side_sizer.Add(self._run_button, 0, wx.LEFT, 11)
        side_sizer.Add(self._all_chunks, 0, wx.LEFT, 11)
        side_sizer.Add(self._recal_heightmap, 0, wx.LEFT, 11)
        side_sizer.Add(self.seed_input, 0, wx.LEFT, 11)

        # side_sizer.Add(self.label, 10, wx.TOP | wx.LEFT, 5)
        side_sizer.Add(self.seed, 0, wx.LEFT, 11)
        #side_sizer.Fit(self)
        self.frame.Fit()
        self.frame.Layout()
        self.frame.Show(True)



    def set_seed(self, _):
        if self.world.level_wrapper.platform == "java":
            self.world.level_wrapper.root_tag['Data']['WorldGenSettings']['seed'] = amulet_nbt.LongTag(
                (int(self.seed_input.GetValue())))
            self.world.save()
        else:
            self.world.level_wrapper.root_tag['RandomSeed'] = amulet_nbt.LongTag((int(self.seed_input.GetValue())))
            self.world.level_wrapper.root_tag.save()

    @property
    def level_db(self):
        level_wrapper = self.world.level_wrapper
        if hasattr(level_wrapper, "level_db"):
            return level_wrapper.level_db
        else:
            return level_wrapper._level_manager._db

    def _refresh_chunk(self, _):
        self.set_seed(_)
        self.world.save()
        self.canvas.run_operation(lambda: self.start(_), "Converting chunks", "Starting...")
        # if 'minecraft:the_nether' in self.canvas.dimension:
        #     self.canvas.run_operation(lambda: self.set_nether(_), "Converting chunks", "Starting...")

        self.world.purge()
        self.world.save()
        self.canvas.renderer.render_world._rebuild()

        wx.MessageBox("If you Had no errors It Worked "
                      "\n Close World and Open in Minecraft", "IMPORTANT",
                      wx.OK | wx.ICON_INFORMATION)

    def start(self, _):
        if self._all_chunks.GetValue():
            self.all_chunks = [x for x in self.world.level_wrapper.all_chunk_coords(self.canvas.dimension)]
        else:
            self.all_chunks = self.canvas.selection.selection_group.chunk_locations()
        # self.all_chunks = [(4, 119)]
        total = len(self.all_chunks)
        count = 0
        loaction_dict = collections.defaultdict(list)
        if self.world.level_wrapper.platform == "java":

            for xx, zz in self.all_chunks:
                rx, rz = world_utils.chunk_coords_to_region_coords(xx, zz)
                loaction_dict[(rx, rz)].append((xx, zz))

            for rx, rz in loaction_dict.keys():
                file_exists = exists(self.get_dim_vpath_java_dir(rx, rz))
                self.world.level_wrapper.root_tag['Data']['DataVersion'] = amulet_nbt.IntTag(2860)
                self.world.level_wrapper.root_tag['Data']['Version'] = amulet_nbt.CompoundTag(
                    {"Snapshot": amulet_nbt.ByteTag(0), "Id": amulet_nbt.IntTag(2860),
                     "Name": amulet_nbt.StringTag("1.18.0")})
                self.world.save()
                if file_exists:
                    for di in loaction_dict[(rx, rz)]:
                        cx, cz = di
                        count += 1
                        yield count / total, f"Chunk: {xx, zz} Done.... {count} of {total}"
                        self.raw_data = AnvilRegion(self.get_dim_vpath_java_dir(rx, rz))
                        if self.raw_data.has_chunk(cx % 32, cz % 32):
                            nbtdata = self.raw_data.get_chunk_data(cx % 32, cz % 32)

                            if nbtdata['sections']:
                                nbtdata['Heightmaps'] = amulet_nbt.CompoundTag({})
                                nbtdata['blending_data'] = amulet_nbt.CompoundTag(
                                    {"old_noise": amulet_nbt.ByteTag(1)})
                                nbtdata['DataVersion'] = amulet_nbt.IntTag(2860)
                                self.raw_data.put_chunk_data(cx % 32, cz % 32, nbtdata)
                            self.raw_data.save()
            yield count / total, f"Chunk: {xx, zz} Done.... {count} of {total}"


        else:  # BEDROCK

            if ('minecraft:the_nether') or ('minecraft:overworld') in self.canvas.dimension:
                self.height = numpy.frombuffer(numpy.zeros(512, 'b'), "<i2").reshape((16, 16))
                self.over_under_blending_limits = False
                for xx, zz in self.all_chunks:

                    count += 1
                    chunkkey = self.get_dim_chunkkey(xx, zz)
                    if 'minecraft:the_end' in self.canvas.dimension:
                        wx.MessageBox("The End THis does not have any effect "
                                      "\n overworld works and the nether does not have biome blending only rounds the "
                                      "chunk walls", "IMPORTANT", wx.OK | wx.ICON_INFORMATION)
                        return

                    if 'minecraft:the_nether' in self.canvas.dimension:

                        try:  # if nether

                            self.level_db.put(chunkkey + b'v', b'\x07')
                        except Exception as e:
                            print("A", e)
                        try:  # if nether
                            self.level_db.delete(chunkkey + b',')
                        except Exception as e:
                            print("B", e)
                    else:
                        try:
                            self.level_db.delete(chunkkey + b'@')  # ?
                        except Exception as e:
                            print("C", e)
                        if self._recal_heightmap:

                            lower_keys = {-1: 4, -2: 3, -3: 2, -4: 1}

                            for k, v in self.world.level_wrapper.level_db.iterate(start=chunkkey + b'\x2f\x00',
                                                                                  end=chunkkey + b'\x2f\xff\xff'):
                                if len(k) > 8 < 10:
                                    key = self.unsignedToSigned(k[-1], 1)
                                    blocks, block_bits, extra_blk, extra_blk_bits = self.get_pallets_and_extra(
                                        v[3:])

                                    for x in range(16):
                                        for z in range(16):
                                            for y in range(16):
                                                if "minecraft:air" not in str(blocks[block_bits[x][y][z]]):
                                                    if key > 0:
                                                        if self.height[z][x] < (y + 1) + (key * 16) + 64:
                                                            self.height[z][x] = (y + 1) + (key * 16) + 64
                                                    elif key == 0:
                                                        if self.height[z][x] < (y + 1) + 64:
                                                            self.height[z][x] = (y + 1) + 64
                                                    else:
                                                        if self.height[z][x] < (y + 1) + (lower_keys[key] * 16) - 16:
                                                            self.height[z][x] = (y + 1) + (lower_keys[key] * 16) - 16

                            if (self.height.max() > 320) or (self.height.min() < 127):
                                self.over_under_blending_limits = True

                            height_biome_key = b'+'
                            biome = self.level_db.get(chunkkey + height_biome_key)[512:]

                            height = self.height.tobytes()

                            self.level_db.put(chunkkey + height_biome_key, height + biome)
                    if self._recal_heightmap:
                        yield count / total, f"Preparing Chunks and new HeightMaps, Current:  {xx, zz}  Prosessing: {count} of {total}"
                    else:
                        yield count / total, f"Preparing Chunks,  Current {xx, zz}  Prosessing: {count} of {total}"

            if self._recal_heightmap:
                if self.over_under_blending_limits:
                    wx.MessageBox("The Height has been updated"
                                  "Complete Some Height issues were detected , \n If below y 62 water spawns around,"
                                  "\n 255 is the height limit for blending  ", "IMPORTANT",
                                  wx.OK | wx.ICON_INFORMATION)
                else:
                    wx.MessageBox("The Chunks Have Been Updated"
                                  "\nComplete no issues detected", "IMPORTANT", wx.OK | wx.ICON_INFORMATION)

    def get_dim_vpath_java_dir(self, regonx, regonz):
        file = "r." + str(regonx) + "." + str(regonz) + ".mca"
        path = self.world.level_wrapper.path
        full_path = ''
        if 'minecraft:the_end' in self.canvas.dimension:
            dim = 'DIM1'
        elif 'minecraft:the_nether' in self.canvas.dimension:
            dim = 'DIM-1'
        elif 'minecraft:overworld' in self.canvas.dimension:
            dim = ''
        version = "region"
        full_path = os.path.join(path, dim, version, file)
        return full_path

    def get_pallets_and_extra(self, raw_sub_chunk):
        block_pal_dat, block_bits, bpv = self.get_blocks(raw_sub_chunk)
        if bpv < 1:
            pallet_size, pallet_data, off = 1, block_pal_dat, 0
        else:
            pallet_size, pallet_data, off = struct.unpack('<I', block_pal_dat[:4])[0], block_pal_dat[4:], 0
        blocks = []
        block_pnt_bits = block_bits
        extra_pnt_bits = None

        for x in range(pallet_size):
            nbt, p = amulet_nbt.load(pallet_data, little_endian=True, offset=True)
            pallet_data = pallet_data[p:]
            blocks.append(nbt.value)

        extra_blocks = []
        if pallet_data:
            block_pal_dat, extra_block_bits, bpv = self.get_blocks(pallet_data)
            if bpv < 1:
                pallet_size, pallet_data, off = 1, block_pal_dat, 0
            else:
                pallet_size, pallet_data, off = struct.unpack('<I', block_pal_dat[:4])[0], block_pal_dat[4:], 0
            extra_pnt_bits = extra_block_bits
            for aa in range(pallet_size):
                nbt, p = amulet_nbt.load(pallet_data, little_endian=True, offset=True)

                pallet_data = pallet_data[p:]
                extra_blocks.append(nbt.value)
        return blocks, block_pnt_bits, extra_blocks, extra_pnt_bits

    def get_blocks(self, raw_sub_chunk):
        bpv, rawdata = struct.unpack("b", raw_sub_chunk[0:1])[0] >> 1, raw_sub_chunk[1:]
        if bpv > 0:
            bpw = (32 // bpv)
            wc = -(-4096 // bpw)
            buffer = numpy.frombuffer(bytes(reversed(rawdata[: 4 * wc])), dtype="uint8")  # reversed
            unpack = numpy.unpackbits(buffer)
            unpack = unpack.reshape(-1, 32)[:, -bpw * bpv:]
            unpack = unpack.reshape(-1, bpv)[-4096:, :]
            unpacked = numpy.pad(unpack, [(0, 0), (16 - bpv, 0)], "constant")
            p_arr = numpy.packbits(unpacked).view(dtype=">i2")[::-1]
            block_bits = p_arr.reshape((16, 16, 16)).swapaxes(1, 2)
            rawdata = rawdata[wc * 4:]
        else:
            block_bits = numpy.zeros((16, 16, 16), dtype=numpy.int16)
        return rawdata, block_bits, bpv

    def get_dim_chunkkey(self, xx, zz):
        chunkkey = b''
        if 'minecraft:the_end' in self.canvas.dimension:
            chunkkey = b''  # struct.pack('<iii',  xx, zz, 2)
        elif 'minecraft:the_nether' in self.canvas.dimension:
            chunkkey = struct.pack('<iii', xx, zz, 1)
        elif 'minecraft:overworld' in self.canvas.dimension:
            chunkkey = struct.pack('<ii', xx, zz)
        return chunkkey

    def unsignedToSigned(self, n, byte_count):
        return int.from_bytes(n.to_bytes(byte_count, 'little', signed=False), 'little', signed=True)

    pass

export = dict(name="# Multi Forced Blending 1.0", operation=MultiForcedBlending) #By PremiereHell
