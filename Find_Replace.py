import json
from typing import TYPE_CHECKING, Tuple
import amulet_nbt
from amulet.api.wrapper import Interface, EntityIDType, EntityCoordType
import wx
import wx.grid
import os
import os.path
from os import path
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
from leveldb import LevelDB
from pathlib import Path
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
class Finder_Replacer(wx.Panel, DefaultOperationUI):

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
        self._is_enabled = True
        self._moving = True
        wx.Panel.__init__(self, parent)
        DefaultOperationUI.__init__(self, parent, canvas, world, options_path)
        self.Freeze()
        self.arr = {}
        self._sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self._sizer)

        self.OrgCopy = []
        self.top_sizer = wx.BoxSizer(wx.VERTICAL)
        self.top = wx.BoxSizer(wx.HORIZONTAL)
        self.top_layer_two = wx.BoxSizer(wx.HORIZONTAL)
        self.topTable = wx.BoxSizer(wx.HORIZONTAL)
        self.top_text = wx.BoxSizer(wx.HORIZONTAL)
        self.side_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.saveload = wx.BoxSizer(wx.HORIZONTAL)
        self.selectionOptions = wx.BoxSizer(wx.HORIZONTAL)

        self._sizer.Add(self.top, 0, wx.TOP | wx.LEFT, 0)
        self._sizer.Add(self.top_layer_two, 0, wx.TOP | wx.LEFT, 0)
        self._sizer.Add(self.selectionOptions, 0, wx.TOP | wx.LEFT, 0)
        self._sizer.Add(self.side_sizer, 1, wx.TOP | wx.LEFT, 0)
        self._sizer.Add(self.saveload, 0, wx.TOP | wx.LEFT, 0)

        self._sizer.Add(self.topTable, 0, wx.TOP | wx.LEFT, 0)


        self._run_buttonF = wx.Button(self, label="Find",size=(40,25))
        self._run_buttonF.Bind(wx.EVT_BUTTON, self._start_the_search)

        self.labelFindBlocks = wx.StaticText(self, label=" Find Blocks: ")
        self.labelFind = wx.StaticText(self, label="Find: ")

        self.labelRep = wx.StaticText(self, label="Replace: ")
        self.textSearch = wx.TextCtrl(self, style=wx.TE_LEFT | wx.TE_BESTWRAP, size=(170, 20))
        self.textF = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_BESTWRAP, size=(170, 50))
        self.textR = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_BESTWRAP, size=(170, 50))
        self.grid_tc_find = wx.GridSizer(0,2,0,0)
        self.grid_tc_find.Add(self.labelFindBlocks, 0, wx.LEFT, 0)
        self.grid_tc_find.Add(self.textSearch, 0, wx.LEFT, -50)
        self.top.Add(self.grid_tc_find, 0, wx.TOP, 0)

        self.gsizer_but_and_chk = wx.GridSizer(0,3,0,-50)
        self.cb_search_only_entities = wx.CheckBox(self, label="Entities Only")
        self.cb_entity_nbt = wx.CheckBox(self, label="Search Entitiy Nbt")

        self.gsizer_but_and_chk.Add(self.cb_search_only_entities, 0, wx.LEFT,5)
        self.gsizer_but_and_chk.Add(self.cb_entity_nbt, 0, wx.LEFT,15)
        self.gsizer_but_and_chk.Add(self._run_buttonF, 0, wx.LEFT ,50)


        self.top_layer_two.Add(self.gsizer_but_and_chk, 0, wx.TOP ,-70)
        self.SearchFGrid = wx.GridSizer(2, 2, 4, 0)
        self.SearchFGrid.Add(self.labelFind)
        self.SearchFGrid.Add(self.textF,0, wx.LEFT, -55)
        self.SearchFGrid.Add(self.labelRep)
        self.SearchFGrid.Add(self.textR,0,  wx.LEFT, -55)
        self.selectionOptions.Add(self.SearchFGrid, 0, wx.TOP,-30)

        self._up = wx.Button(self, label="U", size=(22, 15))
        self._up.Bind(wx.EVT_BUTTON, self._boxUp('m'))
        self._down = wx.Button(self, label="D", size=(22, 15))
        self._down.Bind(wx.EVT_BUTTON, self._boxDown('m'))
        self._east = wx.Button(self, label="E", size=(22, 15))
        self._east.Bind(wx.EVT_BUTTON, self._boxEast('m'))
        self._west = wx.Button(self, label="W", size=(22, 15))
        self._west.Bind(wx.EVT_BUTTON, self._boxWest('m'))
        self._north = wx.Button(self, label="N", size=(22, 15))
        self._north.Bind(wx.EVT_BUTTON, self._boxNorth('m'))
        self._south = wx.Button(self, label="S", size=(22, 15))
        self._south.Bind(wx.EVT_BUTTON, self._boxSouth('m'))

        self._upp = wx.Button(self, label="u+", size=(22, 15))
        self._upp.Bind(wx.EVT_BUTTON, self._boxUp(1))
        self._downp = wx.Button(self, label="d+", size=(22, 15))
        self._downp.Bind(wx.EVT_BUTTON, self._boxDown(1))
        self._eastp = wx.Button(self, label="e+", size=(22, 15))
        self._eastp.Bind(wx.EVT_BUTTON, self._boxEast(1))
        self._westp = wx.Button(self, label="w+", size=(22, 15))
        self._westp.Bind(wx.EVT_BUTTON, self._boxWest(1))
        self._northp = wx.Button(self, label="n+", size=(22, 15))
        self._northp.Bind(wx.EVT_BUTTON, self._boxNorth(1))
        self._southp = wx.Button(self, label="s+", size=(22, 15))
        self._southp.Bind(wx.EVT_BUTTON, self._boxSouth(1))

        self._upm = wx.Button(self, label="u-", size=(22, 15))
        self._upm.Bind(wx.EVT_BUTTON, self._boxUp(-1))
        self._downm = wx.Button(self, label="d-", size=(22, 15))
        self._downm.Bind(wx.EVT_BUTTON, self._boxDown(-1))
        self._eastm = wx.Button(self, label="e-", size=(22, 15))
        self._eastm.Bind(wx.EVT_BUTTON, self._boxEast(-1))
        self._westm = wx.Button(self, label="w-", size=(22, 15))
        self._westm.Bind(wx.EVT_BUTTON, self._boxWest(-1))
        self._northm = wx.Button(self, label="n-", size=(22, 15))
        self._northm.Bind(wx.EVT_BUTTON, self._boxNorth(-1))
        self._southm = wx.Button(self, label="s-", size=(22, 15))
        self._southm.Bind(wx.EVT_BUTTON, self._boxSouth(-1))


        self.boxgrid = wx.GridSizer(6, 3, 0)

        self.boxgrid.Add(self._upp)
        self.boxgrid.Add(self._upm)
        self.boxgrid.Add(self._downp)
        self.boxgrid.Add(self._downm)
        self.boxgrid.Add(self._up)
        self.boxgrid.Add(self._down)
        self.boxgrid.Add(self._eastp)
        self.boxgrid.Add(self._eastm)
        self.boxgrid.Add(self._westp)
        self.boxgrid.Add(self._westm)
        self.boxgrid.Add(self._east)
        self.boxgrid.Add(self._west)
        self.boxgrid.Add(self._northp)
        self.boxgrid.Add(self._northm)
        self.boxgrid.Add(self._southp)
        self.boxgrid.Add(self._southm)
        self.boxgrid.Add(self._north)
        self.boxgrid.Add(self._south)

        self._run_buttonA = wx.Button(self, label="Apply")
        self._run_buttonA.Bind(wx.EVT_BUTTON, self._apply_changes)

        self.listSearchType = {
            "Strict Selection": 0,
            "Selection to Chucks": 1,
            "Every Chunk": 2
        }

        self.lst_mode = wx.RadioBox(self, label='Select Search Mode', choices=list(self.listSearchType.keys()),majorDimension=1)
        self.grid_and_text = wx.GridSizer(2, 0,0, 0)
        self.sel = wx.Button(self, label="Un/Select")
        self.sel.Bind(wx.EVT_BUTTON, self._sel)
        self.loadJ = wx.Button(self, label="Load Json")
        self.loadJ.Bind(wx.EVT_BUTTON, self.loadjson)
        self.saveJ = wx.Button(self, label="Save Json")
        self.saveJ.Bind(wx.EVT_BUTTON, self.savejson)
        self.find_rep = wx.Button(self, label="Replace")
        self.find_rep.Bind(wx.EVT_BUTTON, self.findReplace)

        self.saveload.Add(self.find_rep, 5, wx.TOP, -25)
        self.saveload.Add(self.loadJ, 0, wx.LEFT, -10)
        self.saveload.Add(self.saveJ, 0, wx.TOP, 0)
        self.saveload.Add(self._run_buttonA, 0, wx.LEFT, 10)
        self.saveload.Add(self.sel, 0,  wx.TOP ,-25 ) #, 10, wx.TOP, 70

        self.label_grid_mover = wx.StaticText(self, label="↑ Size Or Move Selection ↑")

        self.grid_and_text.Add(self.boxgrid, 10, wx.LEFT, 0)
        self.grid_and_text.Add(self.label_grid_mover, 0, wx.LEFT, 0)

        self.top.Add(self.lst_mode, 10, wx.LEFT, 15)
        self.selectionOptions.Add(self.grid_and_text, 0, wx.LEFT, 20)
        self._the_data = wx.grid.Grid(self)
        self._the_data.Hide()
        self._sizer.Fit(self)

        self.Layout()
        self.Thaw()

    def _boxUp(self, v):
        def OnClick(event):
            for box in self.canvas.selection.selection_group.selection_boxes:
                xx, yy, zz = box.max_x, box.max_y, box.max_z
                xm, ym, zm = box.min_x, box.min_y, box.min_z
                if v == 'm':
                    sg = SelectionGroup(SelectionBox((xm, ym + 1, zm), (xx, yy + 1, zz)))
                elif v == 1:
                    yy += v
                    sg = SelectionGroup(SelectionBox((xm, ym, zm), (xx, yy, zz)))
                elif v == -1:
                    yy -= 1
                    sg = SelectionGroup(SelectionBox((xm, ym, zm), (xx, yy, zz)))
                self.canvas.selection.set_selection_group(sg)

        return OnClick

    def _boxDown(self, v):
        def OnClick(event):
            for box in self.canvas.selection.selection_group.selection_boxes:
                xx, yy, zz = box.max_x, box.max_y, box.max_z
                xm, ym, zm = box.min_x, box.min_y, box.min_z
                if v == 'm':
                    sg = SelectionGroup(SelectionBox((xm, ym - 1, zm), (xx, yy - 1, zz)))
                elif v == 1:
                    ym -= v
                    sg = SelectionGroup(SelectionBox((xm, ym, zm), (xx, yy, zz)))
                elif v == -1:
                    ym += 1
                    sg = SelectionGroup(SelectionBox((xm, ym, zm), (xx, yy, zz)))
                self.canvas.selection.set_selection_group(sg)

        return OnClick

    def _boxNorth(self, v):
        def OnClick(event):
            for box in self.canvas.selection.selection_group.selection_boxes:
                xx, yy, zz = box.max_x, box.max_y, box.max_z
                xm, ym, zm = box.min_x, box.min_y, box.min_z
                if v == 'm':
                    sg = SelectionGroup(SelectionBox((xm, ym, zm - 1), (xx, yy, zz - 1)))
                elif v == 1:
                    zz += v
                    sg = SelectionGroup(SelectionBox((xm, ym, zm), (xx, yy, zz)))
                elif v == -1:
                    zz -= 1
                    sg = SelectionGroup(SelectionBox((xm, ym, zm), (xx, yy, zz)))
                self.canvas.selection.set_selection_group(sg)

        return OnClick

    def _boxSouth(self, v):
        def OnClick(event):
            for box in self.canvas.selection.selection_group.selection_boxes:
                xx, yy, zz = box.max_x, box.max_y, box.max_z
                xm, ym, zm = box.min_x, box.min_y, box.min_z
                if v == 'm':
                    sg = SelectionGroup(SelectionBox((xm, ym, zm + 1), (xx, yy, zz + 1)))
                elif v == 1:
                    zm -= v
                    sg = SelectionGroup(SelectionBox((xm, ym, zm), (xx, yy, zz)))
                elif v == -1:
                    zm += 1
                    sg = SelectionGroup(SelectionBox((xm, ym, zm), (xx, yy, zz)))
                self.canvas.selection.set_selection_group(sg)

        return OnClick

    def _boxEast(self, v):
        def OnClick(event):
            for box in self.canvas.selection.selection_group.selection_boxes:
                xx, yy, zz = box.max_x, box.max_y, box.max_z
                xm, ym, zm = box.min_x, box.min_y, box.min_z
                if v == 'm':
                    sg = SelectionGroup(SelectionBox((xm + 1, ym, zm), (xx + 1, yy, zz)))
                elif v == 1:
                    xx += v
                    sg = SelectionGroup(SelectionBox((xm, ym, zm), (xx, yy, zz)))
                elif v == -1:
                    xx -= 1
                    sg = SelectionGroup(SelectionBox((xm, ym, zm), (xx, yy, zz)))
                self.canvas.selection.set_selection_group(sg)
                self.abc = [xx + 1, yy, zz]

        return OnClick

    def _boxWest(self, v):
        def OnClick(event):
            for box in self.canvas.selection.selection_group.selection_boxes:
                xx, yy, zz = box.max_x, box.max_y, box.max_z
                xm, ym, zm = box.min_x, box.min_y, box.min_z
                if v == 'm':
                    sg = SelectionGroup(SelectionBox((xm - 1, ym, zm), (xx - 1, yy, zz)))
                elif v == 1:
                    xm -= 1
                    sg = SelectionGroup(SelectionBox((xm, ym, zm), (xx, yy, zz)))
                elif v == -1:
                    xm += 1
                    sg = SelectionGroup(SelectionBox((xm, ym, zm), (xx, yy, zz)))
                self.canvas.selection.set_selection_group(sg)

        return OnClick

    def Onmsgbox(self, text):
        re = wx.MessageBox(text,
                      "Something Maybe Wrong", wx.OK | wx.CANCEL | wx.ICON_WARNING)
        return re

    def onFocus(self, evt):
        setdata = res[self._history.GetString(self._history.GetSelection())]
        self._the_data.SetValue(setdata)
    def findReplace(self, _):
        newd = []
        data = self.Pages
        newd = str(data).replace(self.textF.GetValue().replace("\n","\\n"),self.textR.GetValue().replace("\n","\\n"))[2:-2].replace("\\n","\n").split("', '")
        self.checkForPages(newd)

    def findChanges(self):
        changedItems = []

        for x in range(0, len(self.Pages), 5):
            if self.Pages[x] != self.OrgCopy[x] or\
                self.Pages[x+1] != self.OrgCopy[x+1] or\
                self.Pages[x+2] != self.OrgCopy[x+2] or\
                self.Pages[x+3] != self.OrgCopy[x+3] or\
                self.Pages[x+4] != self.OrgCopy[x+4]:
                changedItems += self.Pages[x],self.Pages[x+1], self.Pages[x+2], self.Pages[x+3], self.Pages[x+4]

        return changedItems


    def savejson(self, _):
        fdlg = wx.FileDialog(self, "Save  Block Data", "", "", "json files(*.json)|*.*", wx.FD_SAVE)
        if fdlg.ShowModal() == wx.ID_OK:
            pathto = fdlg.GetPath()
            if ".json" not in pathto:
                pathto = pathto + ".json"
        data = self.Pages
        with open(pathto, "w") as file:
            file.write(json.dumps(data))


    def loadjson(self, _):
        fdlg = wx.FileDialog(self, "Load Block Data", "", "", "json files(*.json)|*.*", wx.FD_OPEN)
        if fdlg.ShowModal() == wx.ID_OK:
            pathto = fdlg.GetPath()
        with open(pathto, "r") as file:
            j = file.read()
        data = json.loads(j)
        self.json = data
        self.checkForPages(data)

    def _sel(self, _):

        self.canvas.selection.set_selection_group(SelectionGroup([]))
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
        if self._is_enabled:
            self.canvas.renderer.fake_levels.active_transform = (
                evt.point
            )
            x, y, z = evt.point
            a, b, c = 1, 1, 1  # self.abc
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

    def _apply_changes(self, _): #TODO Add Progess indicator
        try:
            changedData = self.findChanges()
        except:
            changedData = []
        try:
            if len(self.json) > 0:
                changedData = self.json
                self.json = []
        except:
            self.json = []
        if len(changedData) == 0:
            wx.MessageBox("No Changes were Made or Nothing to Apply",
                          "No Changes to save", wx.OK | wx.ICON_INFORMATION)
            return
        cords = ()
        block = None
        entity = None
        org_blk_data = ""
        exblk_data = "["
        the_Ent = None
        cx, cz = 0,0
        for x in range(0,len(changedData), 5):
            cords = ((int(changedData[x]),int(changedData[x+1]),int(changedData[x+2])))
            cx, cz = cords[0], cords[2]
            bbbb, eeee = self.world.get_version_block(cords[0], cords[1], cords[2], self.canvas.dimension,
                                                (self.world.level_wrapper.platform, self.world.level_wrapper.version))
            abc = self.world.get_block(cords[0], cords[1], cords[2], self.canvas.dimension)
            row_three = str(changedData[x + 3]).replace("\n",",\n").split("\n")

            try:
                self.world.translation_manager.get_version(self.world.level_wrapper.platform,
                                                                  self.world.level_wrapper.version).block.get_specification(
                    "minecraft", row_three[0].replace(",",""))
            except KeyError:
                re = self.Onmsgbox("block: \""  +row_three[0].replace(",","")+ "\" Can't be found , If you sure this is correct Click OK")
                if re == wx.OK:
                    pass
                else:
                    return

            ex_block_name = ""
            enty = str(changedData[x + 4]).split("\n")
            if enty[0] != 'null':
                snb = "{"+str(changedData[x + 4]).replace("DIR_B\n","{").replace("DIR_E","}") +"}"
                try:

                    the_Ent = BlockEntity("minecraft", row_three[0].replace(",",""), 0, 0, 0, NBTFile(from_snbt(snb)))
                except:
                    wx.MessageBox("Syntax Error in: \n" + snb + " \nMake Sure you have not removed a comma or somthing important \n Use null for None.",
                                      "Error Applying snbt, please try agian", wx.OK | wx.ICON_INFORMATION)
                    return
            if len(row_three) > 1:
                org_blk_data = ""
                if "extra_block" not in row_three[1]:
                    org_blk_data = "["
                for inx, bb in enumerate(row_three[1:]):
                    if "extra_block" in bb:
                        ex_block_name = bb.split("=")[1]
                        exblk_data += str(row_three[inx+2:]).replace("[","").replace("'","").replace(' ',"").replace("[]","")
                        if "[" in org_blk_data and "]" not in org_blk_data:
                            org_blk_data += "]"
                            org_blk_data = org_blk_data.replace(",]", "]")
                        break
                    else:
                        org_blk_data += bb
                        if inx == len(row_three[1:])-1:
                            org_blk_data += "]"
                            org_blk_data = org_blk_data.replace(",]","]")
            if ex_block_name != "":
                oblock = Block.from_snbt_blockstate("minecraft:" + row_three[0].replace(",", "") + org_blk_data)
                eblock = Block.from_snbt_blockstate("minecraft:" + ex_block_name.replace(",", "") + exblk_data)
                U_block_O = self.world.translation_manager.get_version(
                    self.world.level_wrapper.platform,
                    self.world.level_wrapper.version).block.to_universal(oblock)[0]
                U_block_E = self.world.translation_manager.get_version(
                    self.world.level_wrapper.platform,
                    self.world.level_wrapper.version).block.to_universal(eblock)[0]
                block = U_block_O + U_block_E
                try:
                    self.world.translation_manager.get_version(self.world.level_wrapper.platform,
                                                               self.world.level_wrapper.version).block.get_specification(
                        "minecraft", ex_block_name.replace(",",""))
                except KeyError:
                    re = self.Onmsgbox("block: \"" +ex_block_name.replace(",","") + "\" Can't be found , If you sure this is correct Click OK")
                    if re == wx.OK:
                        pass
                    else:
                        return
            else:
                block = Block.from_snbt_blockstate("minecraft:" + row_three[0].replace(",", "") + org_blk_data)
            self.world.set_version_block(cords[0],cords[1],cords[2], self.canvas.dimension,(self.world.level_wrapper.platform,self.world.level_wrapper.version),block,the_Ent)
        self.canvas.run_operation(lambda: self._refresh_chunk(self.canvas.dimension, self.world,cx, cz))

    def _refresh_chunk(self, dimension, world, x, z):
        cx, cz = block_coords_to_chunk_coords(x, z)
        chunk = world.get_chunk(cx, cz, dimension)
        chunk.changed = True

    def finder(self, look, block=False):

        search_also_nbt = self.cb_entity_nbt.GetValue()
        found = {}
        foundcnt = 0
        cnt = 0
        prg = 0
        self.blocks_entity_dic = {}

        try:
            self.ldrop.Hide()
            self.labelTagSel.Hide()
            self.labelTagList.Hide()
            self.ShowAll.Hide()
            self.labelTagList.Hide()
        except:
            pass
        if block:

            cnt = len(look)
            self.prog = wx.ProgressDialog("Searching for : " + str(self.textSearch.GetValue()),
                                          "Searched: " + str(cnt) + " Current Block: ", cnt,
                                          style=wx.PD_AUTO_HIDE | wx.PD_CAN_ABORT | wx.PD_ELAPSED_TIME | wx.PD_REMAINING_TIME)

            self.prog.Show(True)
            for x,y,z in look:
                if self.prog.WasCancelled():
                    self.prog.Hide()
                    self.prog.Destroy()
                    break
                prg += 1
                self.prog.Update(prg, "\n" + str(prg) + " / " + str(cnt) + " Current Block: " + str(x) + " "+str(y)+" "+str(z) +
                                 " Results Found: " + str(foundcnt))
                blockdata = self.world.get_version_block(x,y,z,self.canvas.dimension,(self.world.level_wrapper.platform,self.world.level_wrapper.version))
                extra_blk = self.world.get_block(x, y, z, self.canvas.dimension).extra_blocks
                c_extra_block = []
                if len(extra_blk) > 0:
                    for ex_blk in extra_blk:
                        c_extra_block += self.world.translation_manager.get_version(
                            self.world.level_wrapper.platform,
                            self.world.level_wrapper.version).block.from_universal(ex_blk)[0]
                search_string = str(blockdata[0])
                if search_also_nbt:
                    if blockdata[1] != None:
                        search_string += " " + blockdata[1].nbt.to_snbt(0)
                if str(self.textSearch.GetValue()) in search_string:
                    if blockdata[1] != None:
                        blockE = blockdata[1].nbt.to_snbt(0)
                    else:
                        blockE = None
                    foundcnt +=1
                    self.blocks_entity_dic[str((x,y,z))] = {
                        blockdata[0].base_name: {blockdata[0].full_blockstate.replace("]","")+
                                                str(c_extra_block).replace("Block(","extra_block=").replace("\n}","").replace("])]","").replace("]","")
                                                : blockE}} # str(blockd).replace("(Block","\nextra_block=").replace("(","").replace(")","")

        else:
            total = 0
            for x,z in look:
                chunk = self.world.get_chunk(x,z, self.canvas.dimension)
                total += len(chunk.blocks.sub_chunks)*16*16*16
            self.prog = wx.ProgressDialog("Finding: " + str(self.textSearch.GetValue()),
                                          "Searching " + str(total) + " Block: ", total, style=wx.PD_AUTO_HIDE | wx.PD_CAN_ABORT | wx.PD_ELAPSED_TIME | wx.PD_REMAINING_TIME)

            self.prog.Show(True)
            ent_found = ()
            for x,z in look:
                chunk = self.world.get_chunk(x,z, self.canvas.dimension)
                for xx in self.world.block_palette.items():
                    if str(self.textSearch.GetValue()) in str(xx[1]):
                        found[xx[0]] = xx[0]
                if search_also_nbt:
                    for ee in chunk.block_entities.items():########
                        if str(self.textSearch.GetValue()) in ee[1].nbt.to_snbt():
                            ent_found += ((ee[0][0],ee[0][1],ee[0][2]),)

                for cy in chunk.blocks.sub_chunks:
                    if self.prog.WasCancelled():
                        self.prog.Hide()
                        self.prog.Destroy()
                        break
                    for dx in range(16):
                        for dy in range(16):
                            for dz in range(16):
                                prg += 1
                                if search_also_nbt:
                                    for ent_nbt in ent_found:
                                        if ((x * 16 + dx), (cy * 16 + dy), (z * 16 + dz)) == ent_nbt:
                                            found[int(chunk.blocks.get_sub_chunk(cy)[dx, dy, dz])] = \
                                                int(chunk.blocks.get_sub_chunk(cy)[dx, dy, dz])
                                for k in found:
                                    if chunk.blocks.get_sub_chunk(cy)[dx, dy, dz] == k:
                                        foundcnt += 1
                                        o_block_name = chunk.block_palette[
                                            chunk.blocks.get_sub_chunk(cy)[dx, dy, dz]].base_name
                                        o_block_main = chunk.block_palette[
                                            chunk.blocks.get_sub_chunk(cy)[dx, dy, dz]].base_block
                                        o_extra_block = chunk.block_palette[
                                            chunk.blocks.get_sub_chunk(cy)[dx, dy, dz]].extra_blocks
                                        c_extra_block = []
                                        if len(o_extra_block) > 0:
                                            for ex_blk in o_extra_block:
                                                c_extra_block += self.world.translation_manager.get_version(
                                                    self.world.level_wrapper.platform,
                                                    self.world.level_wrapper.version).block.from_universal(ex_blk)[
                                                    0]
                                        if ((x * 16 + dx), (cy * 16 + dy),
                                            (z * 16 + dz)) in chunk.block_entities.keys():
                                            entitiy_main = chunk.block_entities[
                                                ((x * 16 + dx), (cy * 16 + dy), (z * 16 + dz))]
                                        else:
                                            entitiy_main = None
                                        c_block_main_entitiy = self.world.translation_manager.get_version(
                                            self.world.level_wrapper.platform,
                                            self.world.level_wrapper.version).block.from_universal(o_block_main,
                                                                                                   entitiy_main)
                                        if c_block_main_entitiy[1] != None:
                                            Entity_data = c_block_main_entitiy[1].nbt.to_snbt(0)
                                        else:
                                            Entity_data = None
                                        self.blocks_entity_dic[
                                            str(((x * 16 + dx), (cy * 16 + dy), (z * 16 + dz)))] = \
                                            {
                                                c_block_main_entitiy[0].base_name:
                                                    {
                                                        c_block_main_entitiy[0].full_blockstate.replace("]", "") +
                                                        str(c_extra_block).replace("Block(",
                                                                                   "extra_block=").replace("\n}",
                                                                                                           "").replace(
                                                            "])]", "").replace("]", "")
                                                        : Entity_data}}


                    self.prog.Update(prg, "Searching Blocks: " + str(prg) + " / " + str(total) + " Results Found: " + str(foundcnt))
        self.setdata(None)
        self.OrgCopy = tuple(self.setOrg())

    def _start_the_search(self, _):
        chunks = []
        blocks =[]
        search_only_for_e = self.cb_search_only_entities.GetValue()
        only_be = ()
        prg = 0
        if self.lst_mode.GetSelection() != 2:
            for sc in self.canvas.selection.selection_group.chunk_locations(16):
                if sc not in self.world.level_wrapper.all_chunk_coords(self.canvas.dimension):
                    wx.MessageBox("Please Make sure your selection does Not have any Empty Chunks",
                                  "INFO", wx.OK | wx.ICON_INFORMATION)
                    return


        if str(self.canvas.selection.selection_group) in "[]" and self.lst_mode.GetSelection() != 2:
            wx.MessageBox("This mode requries a selection, Please make a selection and try agian.",
                          "INFO", wx.OK | wx.ICON_INFORMATION)
            return

        if self.lst_mode.GetSelection() == 0:
            tmp = ()
            for x in self.canvas.selection.selection_group.blocks:
                blocks.append(x)
            if search_only_for_e:
                self.prog = wx.ProgressDialog("Gathering List of Entitiies (Strict Selection) ", "Searching: " +
                                              str(len(self.canvas.selection.selection_group.chunk_locations(16))) +
                                              " / Chunks Selected ", len(self.canvas.selection.selection_group.chunk_locations(16)),
                                              style=wx.PD_AUTO_HIDE | wx.PD_CAN_ABORT| wx.PD_ELAPSED_TIME | wx.PD_REMAINING_TIME)
                self.prog.Show(True)
                for c in self.canvas.selection.selection_group.chunk_locations(16):
                    if self.prog.WasCancelled():
                        self.prog.Hide()
                        self.prog.Destroy()
                        break
                    prg += 1

                    self.prog.Update(prg,
                                     "Searching: "+str(prg) + " / Chunks Selected" + str(len(self.canvas.selection.selection_group.chunk_locations(16))))
                    chunk = self.world.get_chunk(c[0], c[1], self.canvas.dimension)
                    for ee in chunk.block_entities.items():
                        tmp += (ee[0],)
                for eb in tmp:
                    try:
                        only_be +=  (blocks[blocks.index(eb)],)
                    except:
                        pass
                if len(only_be) == 0:
                    wx.MessageBox("Sorry No entities Found", "INFO", wx.OK | wx.ICON_INFORMATION)
                    return
                self.finder(only_be, True)
            else:
                self.finder(blocks, True)
        elif self.lst_mode.GetSelection() == 1:
            ent_Only = ()
            if search_only_for_e:
                self.prog = wx.ProgressDialog("Finding: Entitiy within selected chunks ", "Searching: " +
                                              str(len(self.canvas.selection.selection_group.chunk_locations(16))) +
                                              " / Chunks Selected: ", len(self.canvas.selection.selection_group.chunk_locations(16)),
                                              style=wx.PD_AUTO_HIDE | wx.PD_CAN_ABORT | wx.PD_ELAPSED_TIME | wx.PD_REMAINING_TIME)
                self.prog.Show(True)
                for c in self.canvas.selection.selection_group.chunk_locations(16):
                    if self.prog.WasCancelled():
                        self.prog.Hide()
                        self.prog.Destroy()
                        break
                    prg += 1
                    self.prog.Update(prg,
                                     "Searching: " + str(prg) + " / Chunks Selected: " + str(
                                         len(self.canvas.selection.selection_group.chunk_locations(16))))
                    chunk = self.world.get_chunk(c[0], c[1], self.canvas.dimension)
                    for ee in chunk.block_entities.items():
                        ent_Only += (ee[0],)
                if len(ent_Only) == 0:
                    wx.MessageBox("Sorry No entities Found", "INFO", wx.OK | wx.ICON_INFORMATION)
                    return
                self.finder(ent_Only, True)
            else:
                for c in self.canvas.selection.selection_group.chunk_locations(16):
                    blocks.append(c)
                self.finder(blocks)
        elif  self.lst_mode.GetSelection() == 2:
            ent_Only = ()
            if search_only_for_e:
                tot = 0
                for c in self.world.level_wrapper.all_chunk_coords(self.canvas.dimension):
                    tot += 1 # Get Total Chunks in world
                self.prog = wx.ProgressDialog("Gathering List of Entitiies ", "Searching: " +
                                              str(tot) +
                                              " Chunks", tot,
                                              style=wx.PD_AUTO_HIDE | wx.PD_CAN_ABORT | wx.PD_ELAPSED_TIME | wx.PD_REMAINING_TIME)
                self.prog.Show(True)
                for c in self.world.level_wrapper.all_chunk_coords(self.canvas.dimension):
                    if self.prog.WasCancelled():
                        self.prog.Hide()
                        self.prog.Destroy()
                        break

                    prg += 1
                    self.prog.Update(prg,
                                     "Searching: " + str(prg) + " /of Chunks" + str(
                                         len(self.canvas.selection.selection_group.chunk_locations(16))))

                    chunk = self.world.get_chunk(c[0], c[1], self.canvas.dimension)
                    for ee in chunk.block_entities.items():
                        ent_Only += (ee[0],)
                if len(ent_Only) == 0:
                    wx.MessageBox("Sorry No entities Found", "INFO", wx.OK | wx.ICON_INFORMATION)
                    return
                self.finder(ent_Only, True)
            else:
                for c in self.world.level_wrapper.all_chunk_coords(self.canvas.dimension):
                    chunks.append(c)
                self.finder(chunks)

    def pageContol(self, _):
        self.resetData(self.Pages[self.pg["Page: "+str(self.lpage.GetSelection())][0]:self.pg["Page: "+str(self.lpage.GetSelection())][1]])

    def resetData(self, data):
        try:
            self.Freeze()
            self._the_data.Hide()
            self._the_data.Destroy()
            self._the_data = wx.grid.Grid(self, size=(400,500),style=4)
            self.Thaw()
        except:
            pass

        tableCount = int(int(len(data) / 5))
        self._the_data.CreateGrid(tableCount, 5)
        self._the_data.SetRowLabelSize(0)
        self._the_data.SetColLabelValue(0, "x")
        self._the_data.SetColLabelValue(1, "y")
        self._the_data.SetColLabelValue(2, "z")
        self._the_data.SetColLabelSize(20)
        self._the_data.SetColLabelValue(3, "Block")
        self._the_data.SetColLabelValue(4, "Entity Data")

        for ind, dd in enumerate(range(0,len(data), 5) ):
            self._the_data.SetCellValue(ind, 0, str(data[dd+0]).replace("'",""))
            self._the_data.SetCellValue(ind, 1,   str(data[dd+1]).replace("'",""))
            self._the_data.SetCellValue(ind, 2,   str(data[dd+2]).replace("'",""))
            self._the_data.SetCellBackgroundColour(ind, 0, "#ef476f")
            self._the_data.SetCellBackgroundColour(ind, 1, "#06d6a0")
            self._the_data.SetCellBackgroundColour(ind, 2, "#118ab2")
            self._the_data.SetCellValue(ind, 3,  str(data[dd+3]).replace("'","").replace("\\n","\n"))
            self._the_data.SetCellBackgroundColour(ind, 3, "#8ecae6")
            if "null" not in data[dd+4]:
                self._the_data.SetCellBackgroundColour(ind, 4, "#95d5b2")
            self._the_data.SetCellValue(ind, 4,  str(data[dd+4]).replace("'","").replace("\\n","\n"))

        self._the_data.Bind(wx.grid.EVT_GRID_CELL_RIGHT_CLICK, self.gridClick)
        self._the_data.Bind(wx.grid.EVT_GRID_CELL_LEFT_CLICK, self.gridClick)
        self._the_data.AutoSize()

        self.topTable.Add(self._the_data,0,wx.TOP,0 )
        self._the_data.Fit()

        self._the_data.Layout()
        self._sizer.Fit(self)
        self._sizer.Layout()

    def gridClick(self, event):
        try:
            self.frame.Hide()
            self.frame.Close()
        except:
            pass
        self.frame = wx.Frame(self.parent, id=wx.ID_ANY, pos=wx.DefaultPosition, size=(400, 700),
                              style=(
                                      wx.MINIMIZE_BOX | wx.MAXIMIZE_BOX | wx.RESIZE_BORDER | wx.SYSTEM_MENU | wx.CAPTION | wx.CLOSE_BOX | wx.CLIP_CHILDREN | wx.FRAME_FLOAT_ON_PARENT),
                              name="Panel",
                              title="Cell (Row: " + str(event.GetRow()) + " Col: " + str(event.GetCol()) + ")")
        sizer_P = wx.BoxSizer(wx.VERTICAL)
        self.frame.SetSizer(sizer_P)
        save_close = wx.Button(self.frame, label="save_close")
        save_close.Bind(wx.EVT_BUTTON, self.ex_save_close(event.GetRow(), event.GetCol()))
        sizer_P.Add(save_close)
        self.textGrid = wx.TextCtrl(self.frame, style=wx.TE_MULTILINE | wx.TE_BESTWRAP, size=(400, 750))
        sizer_P.Add(self.textGrid)
        self.textGrid.SetValue(self._the_data.GetCellValue(event.GetRow(), event.GetCol()))
        self.frame.Show(True)
        save_close.Show(True)

    def gridTreeClick(self, event):
        try:
            self.frame.Hide()
            self.frame.Close()
        except:
            pass
        self.frame = wx.Frame(self.parent, id=wx.ID_ANY, pos=wx.DefaultPosition, size=(400, 700),
                              style=(
                                      wx.MINIMIZE_BOX | wx.MAXIMIZE_BOX | wx.RESIZE_BORDER | wx.SYSTEM_MENU | wx.CAPTION | wx.CLOSE_BOX | wx.CLIP_CHILDREN | wx.FRAME_FLOAT_ON_PARENT),
                              name="Panel",
                              title="Cell (Row: " + str(event.GetRow()) + " Col: " + str(event.GetCol()) + ")")
        sizer_P = wx.BoxSizer(wx.VERTICAL)
        self.frame.SetSizer(sizer_P)
        save_close = wx.Button(self.frame, label="save_close")
        save_close.Bind(wx.EVT_BUTTON, self.ex_save_close(event.GetRow(), event.GetCol()))
        sizer_P.Add(save_close)
        self.textGrid = wx.TextCtrl(self.frame, style=wx.TE_MULTILINE | wx.TE_BESTWRAP, size=(400, 750))
        sizer_P.Add(self.textGrid)
        self.textGrid.SetValue(self._the_data.GetCellValue(event.GetRow(), event.GetCol()))
        self.frame.Show(True)
        save_close.Show(True)

    def ex_save_close(self, r,c):
        def OnClick(event):

            val = self.textGrid.GetValue()
            self._the_data.SetCellValue(r, c,val)
            try:
                current_page = self.lpage.GetSelection()
            except:
                current_page = 0
            self.Pages[(current_page * 500) + ((r * 5 + c))] = val
            self.frame.Close()
        return OnClick

    def checkForPages(self, data):
        try:
            self.Pages = data
            self.lpage.Hide()
            self.lpage.Destroy()

        except:
            pass
        self.pageSize = 500
        self.start = 0
        self.end = 0

        if len(data) >= 500:
            ps = self.pageSize
            Max = len(data)
            Pages = [(x - ps, x) for x in range(ps, Max, ps)]
            if Pages[-1][1] < Max:
                Pages.append((Pages[-1][1], Max))
            self.pg = {"Page: " + str(i): x for i, x in enumerate(Pages)}
            self.lpage = wx.Choice(self, choices=list(self.pg))
            self.lpage.Bind(wx.EVT_CHOICE, self.pageContol)
            self.lpage.SetSelection(0)
            self.saveload.Add(self.lpage, 0 ,wx.LEFT,-70)
            self.saveload.Fit(self.lpage)
            self._sizer.Fit(self)
            self._sizer.Layout()
            self.pageContol(None)

        else:
            self.resetData(data)
    def setOrg(self):
        self.Org = self.Pages
        return self.Org

    def setdata(self, _):

        tableCount = 0
        self.Pages = []
        for k, v in self.blocks_entity_dic.items():
            for kk, vv in v.items():
                tableCount += 1
        for ind, (k,v) in enumerate(self.blocks_entity_dic.items()):
            for kk,vv in v.items():
                 x = k.split(" ")[0].replace("(", "").replace(",", "")
                 y = k.split(" ")[1].replace(",", "")
                 z = k.split(" ")[2].replace(")", "").replace(",", "")
                 for kkk,vvv in vv.items():
                    Block = str(kkk).replace("[","\n").replace(",","\n").replace("universal_","").replace("minecraft:","").replace("]\n","")
                    if "None" != str(vvv):
                        Enty = amulet_nbt.from_snbt(str(vvv).replace(";B",";")).to_snbt(0).replace("}","DIR_E").replace("{\n","DIR_B\n")\
                        .replace("\"utags\": ","").replace("DIR_B\nDIR_B\n","").replace("DIR_E\nDIR_E\n","")[::-1].replace("E_RID\n","",1).replace("E_RID\n]\n","]",1)[::-1].replace("DIR_B\n","",1)
                    else:
                        Enty = str("null")
            self.Pages += x,y,z,Block,Enty
        self.checkForPages(self.Pages)

    pass

export = dict(name="Finder_Replacer v.1.22", operation=Finder_Replacer) #By PremiereHell