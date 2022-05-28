import json
from typing import TYPE_CHECKING, Tuple
from math import ceil
from math import floor
from math import sin
from math import cos
import io
import amulet.level
from amulet.api.wrapper import Interface, EntityIDType, EntityCoordType
from PIL import Image
import numpy
import wx
import ast
import os
import string
import numpy as np
import os.path
from os import path
from ctypes import windll
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
from amulet.api.data_types import PointCoordinates
from amulet_map_editor.programs.edit.api.behaviour import BlockSelectionBehaviour
from amulet_map_editor.programs.edit.api.behaviour import PointerBehaviour
from amulet_map_editor.programs.edit.api.behaviour import StaticSelectionBehaviour
from amulet_map_editor.programs.edit.api.key_config import ACT_BOX_CLICK
from amulet_map_editor.api import image
from amulet.utils import block_coords_to_chunk_coords
from amulet.api.block import Block
import PyMCTranslate
from amulet_map_editor.api.wx.ui.base_select import BaseSelect
import amulet_nbt
from amulet_map_editor.programs.edit.api.operations.manager.loader import BaseOperationLoader
from pathlib import Path
from amulet.level.formats.leveldb_world import format
from amulet_map_editor.programs.edit.api.events import (
    EVT_PASTE,
    InputPressEvent,
    EVT_INPUT_PRESS,
)
from amulet_map_editor.programs.edit.api.behaviour.pointer_behaviour import (
    PointerBehaviour,
    EVT_POINT_CHANGE,
    PointChangeEvent,
)

if TYPE_CHECKING:
    from amulet.api.level import BaseLevel
    from amulet_map_editor.programs.edit.api.canvas import EditCanvas
facing = {

    "Face Dn": 0,
    "Face Up": 1,
    "Face N": 2,
    "Face S": 3,
    "Face W": 4,
    "Face E": 5,
}
pointingD = {
    "N/Right ": 0,
    "E/Left": 1,
    "S/Up": 2,
    "W/Down": 3
}
theBlockData = {}
mapData = {}
cMaps = {}
currentMaps = {}
newMaps = {}
MapPV = []
Maps = []


def scale_bitmap(bitmap, width, height):
    image = wx.Bitmap.ConvertToImage(bitmap)
    image = image.Scale(width, height, wx.IMAGE_QUALITY_HIGH)
    wxBitmap = image.ConvertToBitmap()
    result = wx.Bitmap(wxBitmap)
    return result


def create_map(mapColorIds, id, name, c, r):
    tNBT = TAG_Compound({
        "name": TAG_String(name),
        "col": TAG_Int(c),
        "row": TAG_Int(r),
        "dimension": TAG_Byte(0),
        "fullyExplored": TAG_Byte(1),
        "scale": TAG_Byte(4),
        "mapId": TAG_Long(id),
        "parentMapId": TAG_Long(-1),
        "dimension": TAG_Byte(0),
        "mapLocked": TAG_Byte(1),
        "unlimitedTracking": TAG_Byte(0),
        "xCenter": TAG_Int(2147483647),
        "zCenter": TAG_Int(2147483647),
        "height": TAG_Short(128),
        "width": TAG_Short(128),
        "colors": TAG_Byte_Array(mapColorIds)
    })
    nbtfile = NBTFile(tNBT)
    return nbtfile


class SetFrames(wx.Panel, DefaultOperationUI):

    def __init__(
            self,
            parent: wx.Window,
            canvas: "EditCanvas",
            world: "BaseLevel",
            options_path: str,

    ):
        # TODO... ADD MAP name support for all versions, and DISABLE GLOW FRAME OPTION FOR OLDER VERSIONS
        platform = world.level_wrapper.platform
        world_version = world.level_wrapper.version

        wx.Panel.__init__(self, parent)
        DefaultOperationUI.__init__(self, parent, canvas, world, options_path)
        self.Freeze()
        self._is_enabled = True
        self._moving = True
        self.thePCount = 0
        self.startP = 0
        self.idCount = 0
        self.mapveiwing = 0
        self.customMaps = 0
        self._sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self._sizer)

        self.top_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.side_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.bottom_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.bottomImage_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.right_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self._sizer.Add(self.side_sizer, 0, wx.TOP | wx.LEFT, 0)
        self._sizer.Add(self.bottom_sizer, 1, wx.BOTTOM | wx.LEFT, 0)
        self._sizer.Add(self.bottomImage_sizer, 0, wx.BOTTOM | wx.LEFT, 0)
        self.listRadio = ["Glow Frame", "Regular Frame"]
        self.radio_frameC = wx.RadioBox(self, label='Frame type?', choices=self.listRadio)
        self._run_text = wx.TextCtrl(
            self, style=wx.TE_LEFT | wx.TE_BESTWRAP, size=(90, 20),
        )

        self.bottom_sizer.Add(self._run_text, 0, wx.LEFT, 0)
        self._run_text.SetValue("map_0")
        self._run_text.Hide()

        self._mapList = wx.ListBox(self, style=wx.LB_MULTIPLE, size=(70, 165), choices=self._run_get_slist)
        self._mapList.Bind(wx.EVT_LISTBOX, self.onFocus)
        self._custommapList = wx.ListBox(self, style=wx.LB_SINGLE, size=(70, 165), choices=list(currentMaps.keys()))
        self._custommapList.Bind(wx.EVT_LISTBOX, self.onFocusCmap)

        self._run_Del_button = wx.Button(self, size=(60, 35), label="DEL \n Map/'s")
        self._run_Del_button.Bind(wx.EVT_BUTTON, self._run_Del)
        self.side_sizer.Add(self._mapList, 0, wx.TOP | wx.LEFT, 0)
        self.side_sizer.Add(self._custommapList, 0, wx.TOP | wx.LEFT, 0)
        self.right_sizer.Add(self._run_Del_button, 20, wx.LEFT, 2)



        self._bot = wx.BoxSizer(wx.VERTICAL)
        self._up = wx.Button(self, label="up", size=(40, 20))
        self._up.Bind(wx.EVT_BUTTON, self._boxUp)
        self._down = wx.Button(self, label="down", size=(40, 20))
        self._down.Bind(wx.EVT_BUTTON, self._boxDown)
        self._east = wx.Button(self, label="east", size=(40, 20))
        self._east.Bind(wx.EVT_BUTTON, self._boxEast)
        self._west = wx.Button(self, label="west", size=(40, 20))
        self._west.Bind(wx.EVT_BUTTON, self._boxWest)
        self._north = wx.Button(self, label="north", size=(40, 20))
        self._north.Bind(wx.EVT_BUTTON, self._boxNorth)
        self._south = wx.Button(self, label="south", size=(40, 20))
        self._south.Bind(wx.EVT_BUTTON, self._boxSouth)

        self._run_AllMaps_button = wx.Button(self, label="DELETE ALL MAPS")
        self._run_AllMaps_button.Bind(wx.EVT_BUTTON, self._run_del_maps)
        self._run_setSData_button = wx.Button(self, label="Apply Images Finish")
        self._run_setSData_button.Bind(wx.EVT_BUTTON, self.Finish)

        self._bot2 = wx.GridSizer(0, 2, 30)
        self._bot2.Add(self._run_AllMaps_button, 0, wx.LEFT | wx.BOTTOM, 0)
        self._bot2.Add(self._run_setSData_button, 0, wx.TOP | wx.LEFT, 0)

        self._run_setImData_button = wx.Button(self, size=(50, 35), label="Import \n Image")
        self._run_setImData_button.Bind(wx.EVT_BUTTON, self._run_import)
        self._inf = wx.Button(self, size=(50, 25), label="HELP")
        self._inf.Bind(wx.EVT_BUTTON, self._info)
        self.buttonGrid = wx.GridSizer(3, 0, 0,0)

        self.boxgrid = wx.GridSizer(2, 2, 1)
        self.boxgrid.Add(self._up)
        self.boxgrid.Add(self._down)
        self.boxgrid.Add(self._east)
        self.boxgrid.Add(self._west)
        self.boxgrid.Add(self._north)
        self.boxgrid.Add(self._south)

        self.buttonGrid.Add(self._run_setImData_button)
        self.buttonGrid.Add(self._inf)
        self.buttonGrid.Add(self.boxgrid)
        self.right_sizer.Add(self.buttonGrid, 0, wx.LEFT, 30)
        self._run_setImData_button.Fit()
        self.side_sizer.Add(self.right_sizer, 0, wx.TOP | wx.LEFT, 0)

        # self._Final_operations = wx.TextCtrl(
        #     self, size=(200, 100), style=wx.TE_MULTILINE
        # )

        self.dis_pnt = wx.BoxSizer(wx.VERTICAL)

       # self.dis_pnt.Add(self._Final_operations, 5, wx.TOP | wx.RIGHT, 0)
       # self.dis_pnt.Add(self.boxgrid, 0, wx.LEFT ,200)
        self.range = wx.TextCtrl(
            self, style=wx.TE_LEFT | wx.TE_BESTWRAP, size=(90, 20)
        )

        self.range_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self._l_map = wx.StaticText(self, wx.LEFT)
        self._l_map.SetLabel(
            "Width_Height: \n Unselect then reselect to apply Ratio.\nThe values can not be 0 !")
        self.range.SetValue("5_5")

        self.range_sizer.Add(self._l_map, wx.LEFT)
        self.range_sizer.Add(self.range, 0, wx.LEFT, 0)
        self.bottom_sizer.Add(self.range_sizer)
        self.bottom_sizer.Hide(self.range_sizer)

        self._sizer.Add(self.dis_pnt)
        self._sizer.Add(self._bot2)
        self._sizer.Add(self._bot, 0, wx.RIGHT | wx.ALIGN_RIGHT | wx.TOP, 0)
        self._sizer.Add(self.radio_frameC, 0, wx.LEFT, 2)
        self._bot.Fit(self)
        #self.dis_pnt.Fit(self)
        self._run_AllMaps_button.Fit()
       # self._Final_operations.Fit()
        self._sizer.Fit(self)
        self.boxgrid.Fit(self)
        self.abc = []
        self.Layout()
        self.Thaw()

    @property
    def wx_add_options(self) -> Tuple[int, ...]:
        return (0,)

    def _info(self, _):
        wx.MessageBox("     Once you add images to your world they will appear in the second list.\n"
                      "You don't need to add it twice, use that list \nAfter your image is imported \n"
                      " select the direction, then hit Place. \n "
                      "Click on screen to place your Image\n"
                      "Once Box/s are in place hit set ,\n Barrels are used as place holders \n"
                      "This allows you to see what you are done \nHit Apply images Finish,"
                      "\nIf All barrels disappears:\n The Operation was successful\n "
                      "Unless there was an update and frames become visible....\n"
                      "The text box below contains\n the final placement data for all images  "
                      "\n NOTE: You can place your maps that are already in your world\n  with the first selection box\n"
                      "Don't Forget to set the Ratio W_H  the spacer _ is needed",
                      "INFO", wx.OK | wx.ICON_INFORMATION)

    def _on_pointer_change(self, evt: PointChangeEvent):
        if self._is_enabled:
            self.canvas.renderer.fake_levels.active_transform = (
                evt.point
            )
            x, y, z = evt.point
            a, b, c = self.abc
            sg = SelectionGroup(SelectionBox((x, y, z), (x + a, y + b, z + c)))
            self.canvas.selection.set_selection_group(sg)
        evt.Skip()

    def _on_input_press(self, evt: InputPressEvent):
        if evt.action_id == ACT_BOX_CLICK:


            if self._is_enabled == True:

                self._moving = not self._moving
                self._is_enabled = False
                return
            if self._is_enabled == False:

                self._is_enabled = True
                self._on_pointer_change
                return
            if self._moving:
                self.canvas.renderer.fake_levels.active_transform = ()
        evt.Skip()

    def location(self) -> PointCoordinates:
        return self._location.value

    def _boxUp(self, _):
        for box in self.canvas.selection.selection_group.selection_boxes:
            xx, yy, zz = box.max_x, box.max_y, box.max_z
            xm, ym, zm = box.min_x, box.min_y, box.min_z
            sg = SelectionGroup(SelectionBox((xm, ym + 1, zm), (xx, yy + 1, zz)))
            self.canvas.selection.set_selection_group(sg)

    def _boxDown(self, _):
        for box in self.canvas.selection.selection_group.selection_boxes:
            xx, yy, zz = box.max_x, box.max_y, box.max_z
            xm, ym, zm = box.min_x, box.min_y, box.min_z
            sg = SelectionGroup(SelectionBox((xm, ym - 1, zm), (xx, yy - 1, zz)))
            self.canvas.selection.set_selection_group(sg)

    def _boxNorth(self, _):
        for box in self.canvas.selection.selection_group.selection_boxes:
            xx, yy, zz = box.max_x, box.max_y, box.max_z
            xm, ym, zm = box.min_x, box.min_y, box.min_z
            sg = SelectionGroup(SelectionBox((xm, ym, zm - 1), (xx, yy, zz - 1)))
            self.canvas.selection.set_selection_group(sg)

    def _boxSouth(self, _):
        for box in self.canvas.selection.selection_group.selection_boxes:
            xx, yy, zz = box.max_x, box.max_y, box.max_z
            xm, ym, zm = box.min_x, box.min_y, box.min_z
            sg = SelectionGroup(SelectionBox((xm, ym, zm + 1), (xx, yy, zz + 1)))
            self.canvas.selection.set_selection_group(sg)

    def _boxEast(self, _):
        for box in self.canvas.selection.selection_group.selection_boxes:
            xx, yy, zz = box.max_x, box.max_y, box.max_z
            xm, ym, zm = box.min_x, box.min_y, box.min_z
            sg = SelectionGroup(SelectionBox((xm + 1, ym, zm), (xx + 1, yy, zz)))
            self.canvas.selection.set_selection_group(sg)
            self.abc = [xx + 1, yy, zz]

    def _boxWest(self, _):
        for box in self.canvas.selection.selection_group.selection_boxes:
            xx, yy, zz = box.max_x, box.max_y, box.max_z
            xm, ym, zm = box.min_x, box.min_y, box.min_z
            sg = SelectionGroup(SelectionBox((xm - 1, ym, zm), (xx - 1, yy, zz)))
            self.canvas.selection.set_selection_group(sg)

    def labelChanger(self, event):
        btnCtrls = [widget for widget in self.GetChildren() if isinstance(widget, wx.Button)]
        for btn in btnCtrls:
            if btn.GetLabel() == "Set" and btn.GetId() == event.GetId() or event.GetId() == btn.GetId() + 929 and btn.GetLabel() == "Set":
                btn.SetLabel("Place")

    def imageP(self, imagedata):

        maps, c, r, mips = imagedata.get("maps"), int(imagedata.get("col")), int(imagedata.get("row")), imagedata.get(
            'mapsD')
        # Maps = maps
        id = self.idCount
        self.idCount += 1
        self._direct = wx.ListBox(self, size=(70, 95), choices=list(facing.keys()), id=id + 929)
        self._Pdirect = wx.ListBox(self, size=(50, 65), choices=list(pointingD.keys()), id=id)
        self._direct.Bind(wx.EVT_LISTBOX, self.labelChanger)
        self._Pdirect.Bind(wx.EVT_LISTBOX, self.labelChanger)
        self._direct.SetSelection(0)
        self._Pdirect.SetSelection(0)
        self.grid = wx.GridSizer(r, c, 1, 1)
        self.grid1 = wx.GridSizer(0, 2, 0)
        self.grid2 = wx.GridSizer(0, 2, 0)
        self.lgrd = wx.GridSizer(0, 0, 0, 0)
        self.grid2.Add(self._direct)
        self.grid2.Add(self._Pdirect)
        self.box = wx.BoxSizer(wx.VERTICAL)
        self.text = wx.TextCtrl(
            self, style=wx.TE_MULTILINE, size=(0, 0), id=id + 777
        )
        self.text.SetValue(str(maps))
        # print(maps)

        self.delSelf = wx.Button(self, size=(30, 20), label="Hide", name=str(c) + "_" + str(r), id=id + 1111)
        self.delSelf.Bind(wx.EVT_BUTTON, self.onRemoveWidget)
        self.AddSelf = wx.Button(self, size=(50, 20), label="Place", name=str(c) + "_" + str(r), id=id)
        self.AddSelf.Bind(wx.EVT_BUTTON, self.onAddPicture)
        self.box.Add(self.text, 0, wx.LEFT | wx.TOP, 0)
        self.info = wx.StaticText(self)

        msort = {}
        order = []
        for m in mips:
            msort[str(m['mapId']).replace('L', '')] = np.reshape(m['colors'], (128, 128, 4))
        for mm in msort.keys():
            order.append(int(mm))
        order.sort()
        for x in order:
            size = 356/(c+r)
            self.img = Image.fromarray(msort.get(str(x)), 'RGBA')
            self.imm = wx.StaticBitmap(self,
                                       bitmap=scale_bitmap(wx.Bitmap.FromBufferRGBA(128, 128, self.img.tobytes()), size,
                                                           size))
            self.grid.Add(self.imm, wx.TOP)
        self.box.Add(self.grid, 0, wx.LEFT , 0)
        self.grid1.Add(self.delSelf, 0, wx.LEFT , 110)
        self.grid1.Add(self.AddSelf, 0, wx.LEFT , 0)
        self.box.Add(self.grid2, 0, wx.LEFT , 110)
        self.box.Add(self.grid1, 0,wx.LEFT | wx.BOTTOM , 30)

        self.grid.Fit(self)
        self.bottomImage_sizer.Add(self.box, 0, wx.LEFT, 20)
        self.bottomImage_sizer.Fit(self)
        self.box.Fit(self)
        self._sizer.Fit(self)

    def onAddPicture(self, event):
        # sg = None
        rng = self.range.GetValue().split('_')
        max = int(rng[0]) * int(rng[1])
        min = len(self._mapList.GetSelections()) - 1
        if min > max:
            print(max, min)
            wx.MessageBox("RATIO NOT CORRECT",
                          "INFO", wx.OK | wx.ICON_INFORMATION)
            return

        print(max)
        txtCtrls = [widget for widget in self.GetChildren() if isinstance(widget, wx.TextCtrl)]
        btnCtrls = [widget for widget in self.GetChildren() if isinstance(widget, wx.Button)]
        lstCtrls = [widget for widget in self.GetChildren() if isinstance(widget, wx.ListBox)]
        id, uuid, rot, pntd, faced, = event.GetId(), [], 0.0, 0, 0


        for x in txtCtrls:
            if x.GetId() == id + 777:
                uuid = x.GetValue().replace('[', '').replace(']', '').replace('"', '').replace(' ', '').replace('\'',
                                                                                                                '').split(
                    ',')
        for lst in lstCtrls:
            if lst.GetId() == id:
                pntd = pointingD[lst.GetStringSelection()]

            if lst.GetId() == id + 929:
                faced = facing[lst.GetStringSelection()]


        for btn in btnCtrls:
            if btn.GetLabel() == "Set" and btn.GetId() != id:
                btn.SetLabel("Place")
            if btn.GetId() == id:
                dim = btn.GetName().split("_")
                fac = faced

                if btn.GetLabel() == "Set":
                    self.boxSetter(int(uuid[0]), rot, "Barrel", "barrel", dim,
                                   fac, pntd)
                # if fac < 2:
                #     self.abc = [int(dim[0]), 1, int(dim[1])]
                # if fac >= 2:
                #     self.abc = [int(dim[0]), int(dim[1]), 1]

                # if fac >= 4:
                #     self.abc = [1,int(dim[0]), int(dim[1])]
                if (pntd == 0 or pntd == 2) and (fac <= 1):

                    self.abc = (int(dim[1]), 1, int(dim[0]))
                if (pntd == 3 or pntd == 1) and (fac <= 1):

                    self.abc = (int(dim[0]), 1, int(dim[1]))

                if (pntd == 0 or pntd == 1) and (fac >= 2 and fac < 4):

                    self.abc = ( int(dim[1]), int(dim[0]), 1)
                if (pntd == 2 or pntd == 3) and (fac >= 2 and fac < 4):

                    self.abc = ( int(dim[0]), int(dim[1]), 1)
                if (pntd == 0 or pntd == 1) and (fac > 3):

                    self.abc = (1, int(dim[0]), int(dim[1]))
                if (pntd == 2 or pntd == 3) and (fac > 3):

                    self.abc = (1, int(dim[1]), int(dim[0]))

                if btn.GetLabel() == "Place":
                    self._selection = StaticSelectionBehaviour(self.canvas)
                    self._curs = PointerBehaviour(self.canvas)
                    self._selection.bind_events()
                    self._curs.bind_events()
                    self.canvas.Bind(EVT_POINT_CHANGE, self._on_pointer_change)
                    self.canvas.Bind(EVT_INPUT_PRESS, self._on_input_press)

                    self._is_enabled = True
                    self._moving = True
                    self._on_pointer_change
                if btn.GetLabel() != "Set" and btn.GetLabel() != "Hide":
                    btn.SetLabel("Set")


        self._is_enabled == True
        self._moving = True

    def onRemoveWidget(self, event):
        id = event.GetId()
        self._custommapList.SetSelection(-1)
        self.bottomImage_sizer.Hide(id - 1111)
        self.bottomImage_sizer.Layout()
        self._sizer.Fit(self)

    def _mapPre(self, _):

        if self.bottomImage_sizer.GetChildren():
            self.bottomImage_sizer.Hide(self.delSelf.GetId())
            self.idCount += 1
            self.bottomImage_sizer.Fit(self)
            self._sizer.Fit(self)

    def _cls(self):
        print("\033c\033[3J", end='')

    def _fileSave(self):
        self.world.pre_save_operation()
        print("SAVE")

    def onFocusCmap(self, evt):

        self.bottom_sizer.Hide(self.range_sizer)
        self._mapList.SetSelection(-1)
        cnt = self.bottomImage_sizer.GetChildren()
        for x in range(0, len(cnt)):
            self.bottomImage_sizer.Hide(x)
            self._sizer.Fit(self)
            self._sizer.Layout()
            self.mapveiwing = 1
        self.imageP(currentMaps[self._custommapList.GetString(self._custommapList.GetSelection())])

    def onFocus(self, evt):
        self._custommapList.SetSelection(-1)
        cnt = self.bottomImage_sizer.GetChildren()
        for x in range(0, len(cnt)):
            self.bottomImage_sizer.Hide(x)
            self._sizer.Fit(self)
            self._sizer.Layout()
            self.mapveiwing = 1
        self.bottom_sizer.Show(self.range_sizer)
        self._run_get_sdata()

    def _refresh_chunk(self, dimension, world, x, z):
        cx, cz = block_coords_to_chunk_coords(x, z)
        chunk = world.get_chunk(cx, cz, dimension)
        chunk.changed = True

    def _run_get_sdata(self):
        setdata = []
        data2 = []
        MapDic = {}

        rng = self.range.GetValue().split('_')

        max = int(rng[0]) * int(rng[1])
        min = len(self._mapList.GetSelections())
        if min > max:
            print(max, min)
            wx.MessageBox("TO MANY FOR SELECTED RATIO,\n Change ratio or Unselect and try again",
                          "INFO", wx.OK | wx.ICON_INFORMATION)
            return

        for x in self._mapList.GetSelections():
            setdata.append(self._mapList.GetString(x))
        for cnt, x in enumerate(setdata):
            Maps.append(x.replace('map_', ''))
            kk = str(x).encode("utf-8")
            mapp = self.world.level_wrapper._level_manager._db.get(kk)
            data = amulet_nbt.load(mapp, little_endian=True)
            data2.append(data)
            MapDic[cnt] = {
                "name": "cmap_" + str(self.customMaps),
                "mapsD": dict(data),
                "cols": str(rng[0]),
                "rows": str(rng[1]),
                "maps": Maps
            }
            cnt += 1
        self.cmapDic2(MapDic)
        self.imageP(newMaps["cmap_" + str(self.customMaps)])  # .tobytes()

    def _run_set_sdata(self, _):

        theKey = self._run_text.GetValue().encode("utf-8")
        #data = self._Final_operations.GetValue()
        nbt = from_snbt(data.replace('NBTFile("":', ''))
        nbtf = NBTFile(nbt)
        data2 = nbtf.save_to(compressed=False, little_endian=True)
        self.world.level_wrapper._level_manager._db.put(theKey, data2)
        self._mapList.Clear()
        self._mapList.Append(self._run_get_slist)
        self._mapList.SetSelection(0)

    def _run_import(self, _):

        if self.mapveiwing == 1:
            cnt = self.bottomImage_sizer.GetChildren()
            for x in range(0, len(cnt)):
                self.bottomImage_sizer.Hide(x)
                self._sizer.Fit(self)
                self._sizer.Layout()

                self.mapveiwing = 0
        getintUUID = self._run_text.GetValue().split('_')
        uuid = int(getintUUID[1])

        with wx.FileDialog(self, "Open Image file", wildcard="*",
                           style=wx.FD_OPEN) as fileDialog:
            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return
            else:
                pathname = fileDialog.GetPath()
        # dialog = wx.ProgressDialog("Loading", "Please Wait" )
        imgs = []
        im = Image.open(pathname)
        self.customMaps += 1
        im = im.convert("RGBA")
        box_dim = ceil(im.size[0] / 128), ceil(im.size[1] / 128)
        newim = Image.new('RGBA', (box_dim[0] * 128, box_dim[1] * 128), color=(0, 0, 0, 255))
        paddingLeft = (newim.size[0] - im.size[0]) // 2
        paddingTop = (newim.size[1] - im.size[1]) // 2
        newim.paste(im, (paddingLeft, paddingTop))
        im = newim
        #   print(self.customMaps)
        cnt = 0
        imgwidth, imgheight = im.size

        for y in range(0, imgheight, 128):
            for x in range(0, imgwidth, 128):
                boxs = (x, y, x + 128, y + 128)
                imgs.append(im.crop(boxs))
        uuid = int(getintUUID[1])
        sp = 0
        MapDic = {}
        Mapss = []
        for x in range(0, len(imgs)):
            image = imgs[x].convert("RGBA")
            pix = image.load()
            px = []

            for y in range(0, image.height):
                for x in range(0, image.width):
                    px.append(pix[x, y][0])
                    px.append(pix[x, y][1])
                    px.append(pix[x, y][2])
                    px.append(pix[x, y][3])
            Map = create_map(px, uuid, "cmap_" + str(self.customMaps), box_dim[0], box_dim[1])
            Mapss.append(str(uuid))
            MapDic[uuid] = {
                "name": "cmap_" + str(self.customMaps),
                "mapsD": dict(Map),
                "cols": str(box_dim[0]),
                "rows": str(box_dim[1]),
                "maps": Mapss
            }

            uuid = uuid + 1
            sp += 1
        self.cmapDic2(MapDic)
        self.imageP(newMaps["cmap_" + str(self.customMaps)])
        self.startP = sp

    #def jgeterseter(self):
        #theBlockData = json.loads(self._Final_operations.GetValue())
        #return theBlockData

    def boxSetter(self, uuid, fRotation, ItemId, ID, box_dim, facing, pntd):
        block_platform = "bedrock"
        block_version = (1, 17, 0)

        fx, fy, fz = [], [], []
        blocks = {}
        xyz = []
        # TODO , MAKE A FUNCTION TO DO THIS

        for x, y, z in self.canvas.selection.selection_group.bounds:
            fx.append(x);
            fy.append(y);
            fz.append(z)
        #  print(x,y,z,"Bounds")
        if facing == 0 and pntd == 0:
            xyz = self.xyzOrder(fx, fy, fz);
            fx, fy, fz = [], [], []
            for x, y, z in xyz:
                fx.append(x), fy.append(y), fz.append(z)
            fRotation = 315;
            blocks["xyz"] = fx, fy, fz
        if facing == 0 and pntd == 1:
            xyz = self.xyzOrder(fz, fy, fx);
            fx, fy, fz = [], [], []
            for x, y, z in xyz:
                fx.append(x), fy.append(y), fz.append(z)
            fx.reverse();
            fRotation = 180;
            blocks["xyz"] = fz, fy, fx
        if facing == 0 and pntd == 2:
            xyz = self.xyzOrder(fx, fy, fz);
            fx, fy, fz = [], [], []
            for x, y, z in xyz:
                fx.append(x), fy.append(y), fz.append(z)
            fRotation = 225;
            fx.reverse();
            fz.reverse();
            blocks["xyz"] = fx, fy, fz
        if facing == 0 and pntd == 3:
            xyz = self.xyzOrder(fz, fy, fx);
            fx, fy, fz = [], [], []
            for x, y, z in xyz:
                fx.append(x), fy.append(y), fz.append(z)
            fRotation = 270;
            fz.reverse();
            blocks["xyz"] = fz, fy, fx
        if facing == 1 and pntd == 0:
            xyz = self.xyzOrder(fx, fy, fz);
            fx, fy, fz = [], [], []
            for x, y, z in xyz:
                fx.append(x), fy.append(y), fz.append(z)
            fRotation = 315;
            fz.reverse();
            blocks["xyz"] = fx, fy, fz
        if facing == 1 and pntd == 1:
            xyz = self.xyzOrder(fz, fy, fx);
            fx, fy, fz = [], [], []
            for x, y, z in xyz:
                fx.append(x), fy.append(y), fz.append(z)
            fx.reverse();
            fz.reverse();
            fRotation = 270;
            blocks["xyz"] = fz, fy, fx
        if facing == 1 and pntd == 2:
            xyz = self.xyzOrder(fx, fy, fz);
            fx, fy, fz = [], [], []
            for x, y, z in xyz:
                fx.append(x), fy.append(y), fz.append(z)
            fRotation = 225;
            fx.reverse();
            blocks["xyz"] = fx, fy, fz
        if facing == 1 and pntd == 3:
            xyz = self.xyzOrder(fz, fy, fx);
            fx, fy, fz = [], [], []
            for x, y, z in xyz:
                fx.append(x), fy.append(y), fz.append(z)
            fRotation = 0;
            blocks["xyz"] = fz, fy, fx
        if facing == 2 and pntd == 0:
            xyz = self.xyzOrder(fx, fy, fz);
            fx, fy, fz = [], [], []
            for x, y, z in xyz:
                fx.append(x), fy.append(y), fz.append(z)
            fy.reverse();
            fRotation = 225;
            blocks["xyz"] = fx, fy, fz
        if facing == 2 and pntd == 1:
            xyz = self.xyzOrder(fx, fy, fz);
            fx, fy, fz = [], [], []
            for x, y, z in xyz:
                fx.append(x), fy.append(y), fz.append(z)
            fRotation = 315;
            fx.reverse();
            blocks["xyz"] = fx, fy, fz
        if facing == 2 and pntd == 2:
            xyz = self.xyzOrder(fy, fx, fz);
            fx, fy, fz = [], [], []
            for x, y, z in xyz:
                fx.append(x), fy.append(y), fz.append(z)
            fRotation = 180;
            fy.reverse();
            fx.reverse();
            blocks["xyz"] = fy, fx, fz
        if facing == 2 and pntd == 3:
            xyz = self.xyzOrder(fy, fx, fz);
            fx, fy, fz = [], [], []
            for x, y, z in xyz:
                fx.append(x), fy.append(y), fz.append(z)
            fRotation = 270;
            blocks["xyz"] = fy, fx, fz
        if facing == 3 and pntd == 0:
            xyz = self.xyzOrder(fx, fy, fz);
            fx, fy, fz = [], [], []
            for x, y, z in xyz:
                fx.append(x), fy.append(y), fz.append(z)
            fRotation = 45;
            fx.reverse();
            fy.reverse();
            blocks["xyz"] = fx, fy, fz
        if facing == 3 and pntd == 1:
            xyz = self.xyzOrder(fx, fy, fz);
            fx, fy, fz = [], [], []
            for x, y, z in xyz:
                fx.append(x), fy.append(y), fz.append(z)
            fRotation = 315;
            blocks["xyz"] = fx, fy, fz
        if facing == 3 and pntd == 2:
            xyz = self.xyzOrder(fy, fx, fz);
            fx, fy, fz = [], [], []
            for x, y, z in xyz:
                fx.append(x), fy.append(y), fz.append(z)
            fRotation = 0;
            fx.reverse();
            blocks["xyz"] = fy, fx, fz

        if facing == 3 and pntd == 3:
            xyz = self.xyzOrder(fy, fx, fz);
            fx, fy, fz = [], [], []
            for x, y, z in xyz:
                fx.append(x), fy.append(y), fz.append(z)
            fRotation = 270;
            fy.reverse();
            blocks["xyz"] = fy, fx, fz
        if facing == 4 and pntd == 0:
            xyz = self.xyzOrder(fx, fz, fy);
            fx, fy, fz = [], [], []
            for x, y, z in xyz:
                fx.append(x), fy.append(y), fz.append(z)
            fz.reverse();
            fy.reverse();
            fRotation = 225;
            blocks["xyz"] = fx, fz, fy
        if facing == 4 and pntd == 1:
            xyz = self.xyzOrder(fx, fz, fy);
            fx, fy, fz = [], [], [];
            for x, y, z in xyz:
                fx.append(x), fy.append(y), fz.append(z)
            fRotation = 315;
            blocks["xyz"] = fx, fz, fy
        if facing == 4 and pntd == 2:
            xyz = self.xyzOrder(fy, fx, fz);
            fx, fy, fz = [], [], []
            for x, y, z in xyz:
                fx.append(x), fy.append(y), fz.append(z)
            fRotation = 180;
            fy.reverse();
            fx.reverse();
            blocks["xyz"] = fy, fx, fz
        if facing == 4 and pntd == 3:
            xyz = self.xyzOrder(fy, fx, fz);
            fx, fy, fz = [], [], []
            for x, y, z in xyz:
                fx.append(x), fy.append(y), fz.append(z)
            fRotation = 270;
            fz.reverse();
            fy.reverse();
            blocks["xyz"] = fy, fx, fz

        if facing == 5 and pntd == 0:
            xyz = self.xyzOrder(fx, fz, fy);
            fx, fy, fz = [], [], [];
            for x, y, z in xyz:
                fx.append(x), fy.append(y), fz.append(z)
            fRotation = 45;
            fz.reverse();
            blocks["xyz"] = fx, fz, fy
        if facing == 5 and pntd == 1:
            xyz = self.xyzOrder(fx, fz, fy);
            fx, fy, fz = [], [], []
            for x, y, z in xyz:
                fx.append(x), fy.append(y), fz.append(z)
            fy.reverse();
            fRotation = 315;
            blocks["xyz"] = fx, fz, fy

        if facing == 5 and pntd == 2:
            xyz = self.xyzOrder(fy, fx, fz);
            fx, fy, fz = [], [], []
            for x, y, z in xyz:
                fx.append(x), fy.append(y), fz.append(z)
            fz.reverse();
            fy.reverse();
            fRotation = 180;
            fy.reverse();
            fx.reverse();
            blocks["xyz"] = fy, fx, fz
        if facing == 5 and pntd == 3:
            xyz = self.xyzOrder(fy, fx, fz);
            fx, fy, fz = [], [], []
            for x, y, z in xyz:
                fx.append(x), fy.append(y), fz.append(z)
            fRotation = 270;
            blocks["xyz"] = fy, fx, fz

        for b in range(0, len(blocks["xyz"][0])):
            x, y, z = blocks["xyz"][0][b], blocks["xyz"][1][b], blocks["xyz"][2][b]
            Snbt = TAG_Compound({
                "facing_direction": TAG_Int(facing),
                "item_frame_map_bit": TAG_Byte(1)
            })
            block = Block("minecraft", ID, dict(Snbt))
            theNBT = TAG_Compound({
                "isMovable": TAG_Short(1),
                "Item": TAG_Compound({
                    "Count": TAG_Byte(1),
                    "Damage": TAG_Byte(6),
                    "Name": TAG_String("minecraft:" + ID),  # filled_map
                    "WasPickedUp": TAG_Byte(0),
                    "tag": TAG_Compound({
                        "map_name_index": TAG_Int(-1),
                        "map_uuid": TAG_Long(uuid),
                    })}),
                "ItemDropChance": TAG_Float(1.0),
                "ItemRotation": TAG_Float(fRotation),
            })
            blockEntity = BlockEntity("minecraft", ItemId, 0, 0, 0, NBTFile(theNBT))
            self.world.set_version_block(x, y, z, self.canvas.dimension,
                                         (block_platform, block_version), block, blockEntity)
            theBlockData[str(self.thePCount)] = [x, y, z, uuid, facing, fRotation, 'map_' + str(uuid)]
           # self._Final_operations.SetValue(str(theBlockData).replace('\'', '"'))
            self.thePCount += 1
            uuid += 1
            self._run_text.SetValue("map_" + str(uuid))

        self.canvas.run_operation(
            lambda: self._refresh_chunk(self.canvas.dimension, self.world, self.canvas.selection.selection_group.min_x,
                                        self.canvas.selection.selection_group.min_z))

    def xyzOrder(self, x, y, z):
        res = []
        for fbx in range(x[0], x[1]):
            for fby in range(y[0], y[1]):
                for fbz in range(z[0], z[1]):
                    res.append([fbx, fby, fbz])
        return res

    def Finish(self, _):
        if self.radio_frameC.GetStringSelection() == "Regular Frame":
            self.Finisher("frame", "ItemFrame")
        if self.radio_frameC.GetStringSelection() == "Glow Frame":
            self.Finisher("glow_frame", "GlowItemFrame")
        for id in newMaps:
            for maps in newMaps[id]['mapsD']:
                Key = 'map_' + str(maps['mapId']).replace('L', '')
                theKey = Key.encode()
                nbt = from_snbt(str(maps))
                nbtFile = NBTFile(nbt)
                n = nbtFile.save_to(compressed=False, little_endian=True)
                self.world.level_wrapper._level_manager._db.put(theKey, n)
        newMaps.clear()
        self._mapList.Clear()
        self._mapList.Append(self._run_get_slist)
        self._mapList.SetSelection(-1)
        self._custommapList.Clear()
        self._custommapList.Append(list(currentMaps.keys()))
        self._custommapList.SetSelection(-1)

    def Finisher(self, ID, BE):
        block_platform = "bedrock"
        block_version = (1, 17, 0)

        for x in theBlockData:
            x, y, z, uuid, facing, fRotation, k = theBlockData[x]
            Snbt = TAG_Compound({
                "facing_direction": TAG_Int(facing),
                "item_frame_map_bit": TAG_Byte(1)
            })
            block = Block("minecraft", ID, dict(Snbt))
            theNBT = TAG_Compound({
                "isMovable": TAG_Short(1),
                "Item": TAG_Compound({
                    "Count": TAG_Byte(1),
                    "Damage": TAG_Byte(6),
                    "Name": TAG_String("minecraft:filled_map"),  #
                    "WasPickedUp": TAG_Byte(0),
                    "tag": TAG_Compound({
                        "map_name_index": TAG_Int(-1),
                        "map_uuid": TAG_Long(uuid),  # locIID.get(str(x) + str(y))
                    })}),
                "ItemDropChance": TAG_Float(1.0),
                "ItemRotation": TAG_Float(fRotation),
            })

            blockEntity = BlockEntity("minecraft", BE, 0, 0, 0, NBTFile(theNBT))
            self.world.set_version_block(x, y, z, self.canvas.dimension,
                                         (block_platform, block_version), block,
                                         blockEntity)
       # self._Final_operations.Clear()
        self.canvas.run_operation(
            lambda: self._refresh_chunk(self.canvas.dimension, self.world, self.canvas.selection.selection_group.min_x,
                                        self.canvas.selection.selection_group.min_z))

    def _run_Del(self, _):
        setdata = []
        wxx = wx.MessageBox("You are going to deleted \n THE SELECTED ITEM/S",
                            "This can't be undone Are you Sure?", wx.OK | wx.CANCEL | wx.ICON_INFORMATION)
        if wxx == int(16):
            return
        if self._custommapList.GetSelections() != '':
            for x in self._custommapList.GetSelections():
                setdata.append(self._custommapList.GetString(x))
                for x in setdata:
                    for i in range(0, len(currentMaps[x]["maps"])):
                        currentMaps[x]["maps"][i] = int(currentMaps[x]["maps"][i])
                        # print(currentMaps[x]["maps"][i])
                        Key = ("map_" + str(currentMaps[x]["maps"][i])).encode()
                        # print(Key)
                        self.world.level_wrapper._level_manager._db.delete(Key)

        if self._mapList.GetSelections() != '':
            for x in self._mapList.GetSelections():
                Key = self._mapList.GetString(x).encode()
                self.world.level_wrapper._level_manager._db.delete(Key)

        self._mapList.Clear()
        self._mapList.Append(self._run_get_slist)
        self._mapList.SetSelection(0)

    @property
    def _run_get_slist(self):
        world = self.world.level_wrapper._level_manager._db.keys()
        currentIMAPS = []
        dic = {}
        for w in world:
            if b'\xff' not in w:
                if b'\x00' not in w:
                    if b'map' in w:
                        mapd = self.world.level_wrapper._level_manager._db.get(w)
                        data = amulet_nbt.load(mapd, little_endian=True)
                        if data.get("name") != None:
                            dic[str(w)] = {
                                "name": str(data.get("name")),
                                "map": str(w),
                                "cols": str(data.get("col")),
                                "rows": str(data.get("row")),
                                "mapsD": dict(data)
                            }
                        currentIMAPS.append(w)
                        a = str(w).split('_')
                        n = int(a[1].replace("'", ""))
                        getintUUID = self._run_text.GetValue().split('_')
                        uuid = int(getintUUID[1])
                        if n > 0 and n > uuid:
                            self._run_text.SetValue("map_" + str(n + 2))
        nameForC = ""
        self.cmapDic(dic)
        for x in currentMaps:
            nameForC = x
        if nameForC != "":
            getnum = nameForC.split('_')
            self.customMaps = int(getnum[1])
        return currentIMAPS

    def cmapDic(self, dic):
        for x in dic:
            currentMaps[dic[x]["name"]] = {}
            currentMaps[dic[x]["name"]]["maps"] = []
            currentMaps[dic[x]["name"]]["col"] = int
            currentMaps[dic[x]["name"]]["row"] = int
            currentMaps[dic[x]["name"]]["mapsD"] = []
        for x in dic:
            currentMaps[dic[x]["name"]]["mapsD"].append(dict(dic[x]["mapsD"]))
            currentMaps[dic[x]["name"]]["col"] = dic[x]["cols"]
            currentMaps[dic[x]["name"]]["row"] = dic[x]["rows"]
            currentMaps[dic[x]["name"]]["maps"].append(
                dic[x]["map"].replace('b', '').replace("\'", "").replace('map_', ''))

    def cmapDic2(self, dic):
        for x in dic:
            newMaps[dic[x]["name"]] = {}
            newMaps[dic[x]["name"]]["maps"] = []
            newMaps[dic[x]["name"]]["col"] = int
            newMaps[dic[x]["name"]]["row"] = int
            newMaps[dic[x]["name"]]["mapsD"] = []
        for x in dic:
            newMaps[dic[x]["name"]]["mapsD"].append(dict(dic[x]["mapsD"]))
            newMaps[dic[x]["name"]]["col"] = dic[x]["cols"]
            newMaps[dic[x]["name"]]["row"] = dic[x]["rows"]
            newMaps[dic[x]["name"]]["maps"] = dic[x]["maps"]

    def _run_del_maps(self, _):
        wxx = wx.MessageBox("You are going to deleted EVERY MAP \n Every entry in the list",
                            "This can't be undone Are you Sure?", wx.OK | wx.CANCEL | wx.ICON_INFORMATION)
        if wxx == int(16):
            return
        world = self.world.level_wrapper._level_manager._db.keys()
        for w in world:
            if b'\xff' not in w:
                if b'\x00' not in w:
                    if b'map_' in w:
                        self.world.level_wrapper._level_manager._db.delete(w)
        self._mapList.Clear()
        self._mapList.Append(self._run_get_slist)
        self._mapList.SetSelection(0)
        cnt = self.bottomImage_sizer.GetChildren()
        for x in range(0, len(cnt)):
            self.bottomImage_sizer.Hide(x)
            self._sizer.Fit(self)
            self._sizer.Layout()
        #self._Final_operations.SetValue("")
        self._run_text.SetValue("map_0")

    pass


export = dict(name="#A_Image to Frames, Plugin V2.02b", operation=SetFrames)  # by PreimereHell
