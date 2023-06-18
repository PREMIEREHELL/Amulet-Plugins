import copy
import json
from typing import TYPE_CHECKING, Tuple
from amulet.api.data_types import Int, BiomeType
import collections
import PyMCTranslate
import amulet_nbt
import amulet_nbt as nbt
import wx
import wx.grid
import sys
import struct
import numpy
from amulet.api.block import Block
from amulet.api.block_entity import BlockEntity
from amulet.api.data_types import Dimension
from amulet.api.selection import SelectionBox
from amulet.api.selection import SelectionGroup
from amulet.api.wrapper import Interface, EntityIDType, EntityCoordType
from leveldb import LevelDB
from amulet.utils import block_coords_to_chunk_coords
from amulet_map_editor.api import image
from amulet_map_editor.api.wx.ui.base_select import BaseSelect
from amulet_map_editor.api.wx.ui.block_select import BlockDefine
from amulet_map_editor.api.wx.ui.block_select import BlockSelect
from amulet_map_editor.api.wx.ui.simple import SimpleDialog
from amulet_map_editor.programs.edit.api.behaviour import BlockSelectionBehaviour
from amulet_map_editor.programs.edit.api.behaviour import StaticSelectionBehaviour
from amulet_map_editor.programs.edit.api.behaviour.pointer_behaviour import EVT_POINT_CHANGE
from amulet_map_editor.programs.edit.api.behaviour.pointer_behaviour import PointChangeEvent
from amulet_map_editor.programs.edit.api.behaviour.pointer_behaviour import PointerBehaviour

from amulet_map_editor.programs.edit.api.events import EVT_SELECTION_CHANGE
from amulet_map_editor.programs.edit.api.key_config import ACT_BOX_CLICK
from amulet_map_editor.programs.edit.api.operations import DefaultOperationUI
from amulet_map_editor.api.wx.ui.block_select.properties import (
    PropertySelect,
    WildcardSNBTType,
    EVT_PROPERTIES_CHANGE,
)
from amulet_map_editor.programs.edit.api.events import (
    EVT_SELECTION_CHANGE,
)

if TYPE_CHECKING:
    from amulet.api.level import BaseLevel
    from amulet_map_editor.programs.edit.api.canvas import EditCanvas

class FinderReplacer(wx.Panel, DefaultOperationUI):

    def __init__(
            self,
            parent: wx.Window,
            canvas: "EditCanvas",
            world: "BaseLevel",
            options_path: str,

    ):
        self.eblock = None
        self._is_enabled = True
        self._moving = True
        wx.Panel.__init__(self, parent)
        DefaultOperationUI.__init__(self, parent, canvas, world, options_path)
        self.options = self._load_options({})
        self.Freeze()
        self.arr = {}
        self._sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self._sizer)
        self.toggle = True
        self.Pages = []
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

        self._run_buttonF = wx.Button(self, label="Find", size=(40, 25))
        self._run_buttonF.Bind(wx.EVT_BUTTON, self._start_the_search)

        self.labelFindBlocks = wx.StaticText(self, label=" Find Blocks: ")
        self.labelFind = wx.StaticText(self, label="Find: ")

        self.labelRep = wx.StaticText(self, label="Replace: ")
        self.textSearch = wx.TextCtrl(self, style=wx.TE_LEFT | wx.TE_BESTWRAP, size=(170, 20))
        self.textF = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_BESTWRAP, size=(222, 100))
        self.textR = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_BESTWRAP, size=(222, 100))
        self.grid_tc_find = wx.GridSizer(0, 2, 4, 4)
        self.grid_tc_find.Add(self.labelFindBlocks, 0, wx.LEFT, 0)
        self.grid_tc_find.Add(self.textSearch, 0, wx.LEFT, -50)
        self.top.Add(self.grid_tc_find, 0, wx.TOP, 0)

        self.gsizer_but_and_chk = wx.GridSizer(0, 3, 0, -50)
        self.cb_search_only_entities = wx.CheckBox(self, label="Entities Only")
        self.cb_entity_nbt = wx.CheckBox(self, label="Search Entitiy Nbt")

        self.gsizer_but_and_chk.Add(self.cb_search_only_entities, 0, wx.LEFT, 5)
        self.gsizer_but_and_chk.Add(self.cb_entity_nbt, 0, wx.LEFT, 15)
        self.gsizer_but_and_chk.Add(self._run_buttonF, 0, wx.LEFT, 50)

        self.top_layer_two.Add(self.gsizer_but_and_chk, 0, wx.TOP, -70)
        self.SearchFGrid = wx.GridSizer(4, 0, 0, 0)
        self.SearchFGrid.Add(self.labelFind)
        self.SearchFGrid.Add(self.textF, 0, wx.TOP, -40)
        self.SearchFGrid.Add(self.labelRep)
        self.SearchFGrid.Add(self.textR, 0, wx.TOP, -40)
        self.selectionOptions.Add(self.SearchFGrid, 0, wx.TOP, -45)

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

        self.boxgrid = wx.GridSizer(3, 4, 4,4)
        self.boxgrid_b = wx.GridSizer(3, 2, 4, 4)

        self.boxgrid.Add(self._upp)
        self.boxgrid.Add(self._upm)
        self.boxgrid.Add(self._downp)
        self.boxgrid.Add(self._downm)
        self.boxgrid_b.Add(self._up)
        self.boxgrid_b.Add(self._down)
        self.boxgrid.Add(self._eastp)
        self.boxgrid.Add(self._eastm)
        self.boxgrid.Add(self._westp)
        self.boxgrid.Add(self._westm)
        self.boxgrid_b.Add(self._east)
        self.boxgrid_b.Add(self._west)
        self.boxgrid.Add(self._northp)
        self.boxgrid.Add(self._northm)
        self.boxgrid.Add(self._southp)
        self.boxgrid.Add(self._southm)
        self.boxgrid_b.Add(self._north)
        self.boxgrid_b.Add(self._south)

        self._run_buttonA = wx.Button(self, label="Apply")
        self._run_buttonA.Bind(wx.EVT_BUTTON, self._apply_changes)
        self.raw_apply = wx.Button(self, label="Direct Apply")
        self.raw_apply.Bind(wx.EVT_BUTTON, self.apply_raw)
        self.open_block_window = wx.Button(self, label="Find Replace Helper")
        self.open_block_window.Bind(wx.EVT_BUTTON, self.block_list)

        self.labelfilter = wx.StaticText(self, label="Filter Whats selected:")
        self.textfilter = wx.TextCtrl(self, style=wx.TE_LEFT | wx.TE_BESTWRAP, size=(70, 20))

        self.selPosAbove = wx.Button(self, label="Select Found")
        self.selPosAbove.Bind(wx.EVT_BUTTON, self.select_the_blocks)

        self.listSearchType = {
            "Strict Selection": 0,
            "Selection to Chucks": 1,
            "Every Chunk": 2
        }

        self.lst_mode = wx.RadioBox(self, label='Select Search Mode', choices=[*self.listSearchType], majorDimension=1)
        self.grid_and_text = wx.GridSizer(2, 0, 0, 0)
        # self.sel = wx.Button(self, label="Un/Select")
        # self.sel.Bind(wx.EVT_BUTTON, self._sel)
        self.loadJ = wx.Button(self, label="Load Json")
        self.loadJ.Bind(wx.EVT_BUTTON, self.loadjson)
        self.saveJ = wx.Button(self, label="Save Json")
        self.saveJ.Bind(wx.EVT_BUTTON, self.savejson)
        self.find_rep = wx.Button(self, label="Replace")
        self.find_rep.Bind(wx.EVT_BUTTON, self.findReplace)

        self.giid_box = wx.GridSizer(3, 2, 1, 0)
        self.giid_box.Add(self.open_block_window)
        self.giid_box.Add(self.selPosAbove)
        self.giid_box.Add(self.labelfilter)
        self.giid_box.Add(self.textfilter)

        self.giid_box.Add(self.raw_apply, 0, wx.LEFT, 10)
        self.saveload.Add(self.loadJ, 5, wx.LEFT, 2)
        self.saveload.Add(self.saveJ, 0, wx.TOP, 0)
        self.saveload.Add(self.find_rep, 5, wx.LEFT, 10)
        self.saveload.Add(self._run_buttonA, 0, wx.LEFT, 10)
        self.saveload.Add(self.giid_box, 0, wx.TOP | wx.LEFT, -100)

        #self.raw_apply

        # self.giid_box.Add(self.open_block_window, 11, wx.LEFT | wx.TOP, -110)
        # self.giid_box.Add(self.selPosAbove, 0, wx.LEFT, -90)
        # self.giid_box.Add(self.textfilter, 0, wx.LEFT, -80)
        # self.giid_box.Add(self.labelfilter, 0, wx.LEFT, -200)

        self.saveload.Fit(self)
        #self.saveload.Add(self.sel, 0, wx.TOP, -25)  # , 10, wx.TOP, 70

        self.label_grid_mover_l = wx.StaticText(self, label="Size ↑ ")
        self.label_grid_mover_l2 = wx.StaticText(self, label=" Move all ↑")

        self.grid_and_text.Add(self.boxgrid, 10, wx.LEFT, -10)
        self.grid_and_text.Add(self.boxgrid_b, 0, wx.LEFT, 20)
        self.grid_and_text.Add(self.label_grid_mover_l, 0, wx.LEFT, -10)
        self.grid_and_text.Add(self.label_grid_mover_l2, 0, wx.LEFT, -30)



        self.top.Add(self.lst_mode, 10, wx.LEFT, 35)
        self.selectionOptions.Add(self.grid_and_text, 0, wx.LEFT, 20)
        self._the_data = wx.grid.Grid(self)
        self._the_data.Hide()
        self._sizer.Fit(self)
        self.toggle_count = 0
        #self.search_raw_level_db("lava")
        self.Layout()
        self.Thaw()

    def set_block(self, event, data ,toggle):
        self.toggle = toggle
        x,y,z =self.canvas.selection.selection_group.min
        block, enty = self.world.get_version_block(x,y,z,self.canvas.dimension,
                (self.world.level_wrapper.platform, self.world.level_wrapper.version))# self.canvas.selection.selection_group.min
        #print(block.namespaced_name,block.properties,dir(block.properties))
        the_snbt = f"{block.namespaced_name}" \
                   f"\n{amulet_nbt.CompoundTag(block.properties).to_snbt(1)}"
        try:
            e_block_u = self.world.get_block(x,y,z,self.canvas.dimension).extra_blocks[0]
            pf, vb = self.world.level_wrapper.platform, self.world.level_wrapper.version

            e_block =  self.world.translation_manager.get_version(pf, vb).block.from_universal(e_block_u)[0]
            the_extra_snbt = f"\n<Extra_Block>\n{e_block.namespaced_name}\n" \
                             f"{amulet_nbt.from_snbt(str(e_block.properties)).to_snbt(1)}"
            eblock =  the_extra_snbt
            self.extra_block_prop.SetValue(eblock)
        except:
            the_e = f"\n<Extra_Block>" \
                       f"\nNone"
            self.extra_block_prop.SetValue(the_snbt)
        self.block_prop.SetValue(the_snbt)
        data.block = block
        self.toggle = False

    def get_block(self, event, data, toggle):

        if self.toggle:
            the_snbt = f"{data.block.namespaced_name}" \
                       f"\n{amulet_nbt.TAG_Compound(data.properties).to_snbt(1)}"
            the_extra_snbt = f"\n<Extra_Block>\n{data.block.namespaced_name}" \
                             f"\n{amulet_nbt.TAG_Compound(data.properties).to_snbt(1)}"

            self.block_prop.SetValue(the_snbt)
            self.extra_block_prop.SetValue(the_extra_snbt)
        else:
            self.toggle_count += 1
        if self.toggle_count == 2:
            self.toggle = True
            self.toggle_count = 0

    def block_list(self, _):
        try:
            self.window.Hide()
            self.window.Close()
        except:
            pass
        self.window = wx.Frame(self.parent, title="Find Replace Helper", size=(550, 570),
                                            style=wx.DEFAULT_FRAME_STYLE | wx.STAY_ON_TOP)
        self.window.Centre()
        self.w_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.window.SetSizer(self.w_sizer)
        if True:

            self.chosen_platform = self.world.level_wrapper.platform
            self.chosen_name_space = "minecraft"
        self._block_define = BlockDefine(
            self.window,
            self.world.translation_manager,
            wx.VERTICAL,
            force_blockstate=False,
            namespace=self.chosen_name_space,
            *(self.options.get("fill_block_options", []) or [self.chosen_platform]),
            show_pick_block=True
        )

        self._block_define.Bind(EVT_PROPERTIES_CHANGE,lambda event:  self.get_block(event, self._block_define, True))

        self.canvas.Bind(EVT_SELECTION_CHANGE, lambda event: self.set_block(event, self._block_define, False))
        self.block_prop = wx.TextCtrl(
            self.window, style=wx.TE_MULTILINE | wx.TE_BESTWRAP, size=(300, 220)
        )
        self.extra_block_prop = wx.TextCtrl(
            self.window, style=wx.TE_MULTILINE | wx.TE_BESTWRAP, size=(300, 220)
        )
        self.copy_find = wx.Button(self.window, label="Find Selected Block")
        self.copy_find.Bind(wx.EVT_BUTTON, self.copy_find_select)
        self.copy_to_find_button = wx.Button(self.window, label="Copy To Find")
        self.copy_to_replace_button = wx.Button(self.window, label="Copy To Replace")
        self.copye_to_find_button = wx.Button(self.window, label="Add To Find")
        self.copye_to_replace_button = wx.Button(self.window, label="Add To Replace")
        self.b_r_label = wx.StaticText(self.window, label="Block" )
        self.label_info = wx.StaticText(self.window, label="You Can also Select A Block To get the info")
        # self.labele_info = wx.StaticText(self.window, label="Select Platform universal First ")

        self.copy_to_find_button.Bind(wx.EVT_BUTTON, self.copy_to_find)
        self.copy_to_replace_button.Bind(wx.EVT_BUTTON, self.copy_to_replace)
        self.copye_to_find_button.Bind(wx.EVT_BUTTON, self.copy_e_to_find)
        self.copye_to_replace_button.Bind(wx.EVT_BUTTON, self.copy_e_to_replace)
        self.b_e_label = wx.StaticText(self.window, label="Extra Block")
        self.grid_top_ew = wx.GridSizer(1, 3, 0, 0)
        self.grid_top_ew.Add(self.b_r_label)
        self.grid_top_ew.Add(self.copy_to_find_button, 0, wx.LEFT, -20)
        self.grid_top_ew.Add(self.copy_to_replace_button, 0, wx.LEFT, -20)

        self.grid_bot_ew = wx.GridSizer(1, 3, 0, 0)
        self.grid_bot_ew.Add(self.b_e_label)
        self.grid_bot_ew.Add(self.copye_to_find_button, 0, wx.LEFT, -20)
        self.grid_bot_ew.Add(self.copye_to_replace_button, 0, wx.LEFT, -20)

        #self.grid_box = #wx.GridSizer(4,0,-100,-0)
        self.grid_box_pop = wx.BoxSizer(wx.VERTICAL)
        self.grid_box_pop.Add(self.label_info)
        self.grid_box_pop.Add(self.grid_top_ew)

        self.grid_box_pop.Add(self.block_prop)
        # self.grid_box_pop.Add(self.labele_info)
        self.grid_box_pop.Add(self.grid_bot_ew)

        self.grid_box_pop.Add(self.extra_block_prop)

        #button.Bind(wx.EVT_BUTTON, lambda event: self.get_block(event, _block_define) )
        self.grid_left = wx.GridSizer(2,1,-470,0)
        self.grid_left.Add(self.copy_find, 0, wx.LEFT, 120)
        self.grid_left.Add(self._block_define)
        self.w_sizer.Add(self.grid_left)
        self.w_sizer.Add(self.grid_box_pop )
        self._block_define.Fit()
        self._block_define.Layout()
        self.grid_box_pop.Layout()

        self.window.Bind(wx.EVT_CLOSE, lambda event: self.OnClose(event))
        self.window.Enable()

        self.window.Show(True)

    def copy_find_select(self, _):
        self.textSearch.SetValue(self._block_define.block_name + " ")

    def copy_to_find(self,_):
        self.textF.SetValue("")
        self.textF.SetValue(self.block_prop.GetValue())

    def copy_to_replace(self,_):
        self.textR.SetValue("")
        self.textR.SetValue(self.block_prop.GetValue())

    def copy_e_to_find(self,_):
        self.textF.SetValue(self.textF.GetValue().partition('\n<Extra_Block>\n')[0] +self.extra_block_prop.GetValue())

    def copy_e_to_replace(self,_):
        self.textR.SetValue(self.textR.GetValue().partition('\n<Extra_Block>\n')[0] +self.extra_block_prop.GetValue())

    def OnClose(self, event):
        self.canvas.Unbind(EVT_SELECTION_CHANGE)
        self.window.Show(False)

    def block(self, block):
        self._picker.set_namespace(block.namespace)
        self._picker.set_name(block.base_name)
        self._update_properties()
        self.properties = block.properties

    def bind_events(self):
        super().bind_events()
        self._selection.bind_events()
        self._selection.enable()

    def enable(self):
        self._selection = BlockSelectionBehaviour(self.canvas)
        self._selection.enable()

    def _boxUp(self, v):
        def OnClick(event):
            sgs = []
            for box in self.canvas.selection.selection_group.selection_boxes:
                xx, yy, zz = box.max_x, box.max_y, box.max_z
                xm, ym, zm = box.min_x, box.min_y, box.min_z
                if v == 'm':
                    sgs.append(SelectionBox((xm, ym + 1, zm), (xx, yy + 1, zz)))
                elif v == 1:
                    yy += v
                    sgs.append(SelectionBox((xm, ym, zm), (xx, yy, zz)))
                elif v == -1:
                    yy -= 1
                    sgs.append(SelectionBox((xm, ym, zm), (xx, yy, zz)))
            self.canvas.selection.set_selection_group(SelectionGroup(sgs))
        return OnClick

    def _boxDown(self, v):
        def OnClick(event):
            sgs = []
            for box in self.canvas.selection.selection_group.selection_boxes:
                xx, yy, zz = box.max_x, box.max_y, box.max_z
                xm, ym, zm = box.min_x, box.min_y, box.min_z
                if v == 'm':
                    sgs.append(SelectionBox((xm, ym - 1, zm), (xx, yy - 1, zz)))
                elif v == 1:
                    ym -= v
                    sgs.append(SelectionBox((xm, ym, zm), (xx, yy, zz)))
                elif v == -1:
                    ym += 1
                    sgs.append(SelectionBox((xm, ym, zm), (xx, yy, zz)))
            self.canvas.selection.set_selection_group(SelectionGroup(sgs))

        return OnClick

    def _boxNorth(self, v):

        def OnClick(event):
            sgs = []
            for box in self.canvas.selection.selection_group.selection_boxes:
                xx, yy, zz = box.max_x, box.max_y, box.max_z
                xm, ym, zm = box.min_x, box.min_y, box.min_z
                if v == 'm':
                    sgs.append(SelectionBox((xm, ym, zm - 1), (xx, yy, zz - 1)))
                elif v == 1:
                    zz += v
                    sgs.append(SelectionBox((xm, ym, zm), (xx, yy, zz)))
                elif v == -1:
                    zz -= 1
                    sgs.append(SelectionBox((xm, ym, zm), (xx, yy, zz)))
            self.canvas.selection.set_selection_group(SelectionGroup(sgs))

        return OnClick

    def _boxSouth(self, v):
        def OnClick(event):
            sgs = []
            for box in self.canvas.selection.selection_group.selection_boxes:
                xx, yy, zz = box.max_x, box.max_y, box.max_z
                xm, ym, zm = box.min_x, box.min_y, box.min_z
                if v == 'm':
                    sgs.append(SelectionBox((xm, ym, zm + 1), (xx, yy, zz + 1)))
                elif v == 1:
                    zm -= v
                    sgs.append(SelectionBox((xm, ym, zm), (xx, yy, zz)))
                elif v == -1:
                    zm += 1
                    sgs.append(SelectionBox((xm, ym, zm), (xx, yy, zz)))
            self.canvas.selection.set_selection_group(SelectionGroup(sgs))

        return OnClick

    def _boxEast(self, v):

        def OnClick(event):
            sgs = []
            for box in self.canvas.selection.selection_group.selection_boxes:
                xx, yy, zz = box.max_x, box.max_y, box.max_z
                xm, ym, zm = box.min_x, box.min_y, box.min_z
                if v == 'm':
                    sgs.append(SelectionBox((xm + 1, ym, zm), (xx + 1, yy, zz)))
                elif v == 1:
                    xx += v
                    sgs.append(SelectionBox((xm, ym, zm), (xx, yy, zz)))
                elif v == -1:
                    xx -= 1
                    sgs.append(SelectionBox((xm, ym, zm), (xx, yy, zz)))
            self.canvas.selection.set_selection_group(SelectionGroup(sgs))
                # self.abc = [xx + 1, yy, zz]

        return OnClick

    def _boxWest(self, v):
        def OnClick(event):
            sgs = []
            for box in self.canvas.selection.selection_group.selection_boxes:
                xx, yy, zz = box.max_x, box.max_y, box.max_z
                xm, ym, zm = box.min_x, box.min_y, box.min_z
                if v == 'm':
                    sgs.append(SelectionBox((xm - 1, ym, zm), (xx - 1, yy, zz)))
                elif v == 1:
                    xm -= 1
                    sgs.append(SelectionBox((xm, ym, zm), (xx, yy, zz)))
                elif v == -1:
                    xm += 1
                    sgs.append(SelectionBox((xm, ym, zm), (xx, yy, zz)))
            self.canvas.selection.set_selection_group(SelectionGroup(sgs))

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
        this = self.textF.GetValue()
        that = self.textR.GetValue()
        newd = '_split_'.join(str(x) for x in data).replace(this,that).split("_split_")
        print(newd)
        self.checkForPages(newd)

    def findChanges(self):
        changedItems = []

        for x in range(0, len(self.Pages), 5):
            if self.Pages[x] != self.OrgCopy[x] or \
                    self.Pages[x + 1] != self.OrgCopy[x + 1] or \
                    self.Pages[x + 2] != self.OrgCopy[x + 2] or \
                    self.Pages[x + 3] != self.OrgCopy[x + 3] or \
                    self.Pages[x + 4] != self.OrgCopy[x + 4]:
                changedItems += self.Pages[x], self.Pages[x + 1], self.Pages[x + 2], self.Pages[x + 3], self.Pages[
                    x + 4]

        return changedItems

    def savejson(self, _):
        fdlg = wx.FileDialog(self, "Save  Block Data", "", "File_name", "json files(*.json)|*.*", wx.FD_SAVE)
        if fdlg.ShowModal() == wx.ID_OK:
            pathto = fdlg.GetPath()
            if ".json" not in pathto:
                pathto = pathto + ".json"
        data = self.Pages
        for i in range(0,len(data),5):
            x,y,z,blk,enty = data[0],data[1],data[2],data[3],data[4]
            # print(type(x),type(y),type(z),type(blk),type(enty))

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
        self.Pages = data
        self.OrgCopy = copy.copy(data)
        self.checkForPages(data)

    def _apply_changes(self, _):
        self.changedData = []
        try:
            self.changedData = self.findChanges()
        except:
            self.changedData = []
        try:
            if len(self.json) > 0:
                self.changedData = self.json
                self.json = []
        except:
            self.json = []
        if len(self.changedData) == 0:
            wx.MessageBox("No Changes were Made or Nothing to Apply",
                          "No Changes to save", wx.OK | wx.ICON_INFORMATION)
            return
        else:
            self.run_op()

    def finalize_op(self):
        cords = ()
        platform = self.world.level_wrapper.platform
        block = None
        entity = None
        the_nbt = None
        cx, cz = 0, 0
        total = len(self.changedData)
        count = 0
        for x in range(0, len(self.changedData), 5):
            yield x+5 / total
            cords = ((int(self.changedData[x]), int(self.changedData[x + 1]), int(self.changedData[x + 2])))
            cx, cz = cords[0], cords[2]
            if not self.world.has_chunk(block_coords_to_chunk_coords(cx,cz)[0],
                                        block_coords_to_chunk_coords(cx,cz)[1],self.canvas.dimension):
                self.world.create_chunk(block_coords_to_chunk_coords(cx,cz)[0],
                                        block_coords_to_chunk_coords(cx,cz)[1],self.canvas.dimension)
            block_full_name_space = self.changedData[x + 3].split("\n")[0]
            block_name_space = block_full_name_space.split(":")[0]
            block_name = block_full_name_space.split(":")[1]
            block_properties = dict(amulet_nbt.from_snbt(self.changedData[x + 3].split("\n",1)[1].split('<Extra_Block>')[0]))
            try:
                self.world.translation_manager.get_version(self.world.level_wrapper.platform,
                                                           self.world.level_wrapper.version).block.get_specification(
                    block_name_space, block_name)
            except KeyError:
                re = self.Onmsgbox(f"Block: {block_name_space ,block_name} \nCan't be found , If you sure this is correct click OK")
                if re == wx.OK:
                    pass
                else:
                    return
            enty = self.changedData[x + 4]
            if enty != 'null':
                snb = enty
                try:
                    nbtf = amulet_nbt.from_snbt(snb)
                    if nbtf.get("Items"):
                        for i, da in enumerate(nbtf["Items"]):
                            if hasattr(da, "get"):
                                if da.get('tag'):
                                    if da.get('tag').get("internalComponents"):
                                        data = nbtf["Items"][i]['tag']["internalComponents"].save_to(
                                            compressed=False, little_endian=True).replace(
                                            b'\x07\n\x00StorageKey\x08\x00\x00\x00',
                                            b'\x08\n\x00StorageKey\x08\x00')
                                        nbt = amulet_nbt.load(data, compressed=False, little_endian=True)
                                        nbtf["Items"][i]['tag'] \
                                            ["internalComponents"]["EntityStorageKeyComponent"] = nbt[
                                            "EntityStorageKeyComponent"]
                  #  print(nbtf)
                    the_nbt = BlockEntity(block_name_space ,block_name, 0, 0, 0,
                                          amulet_nbt.NBTFile(nbtf))
                except Exception as err:
                    wx.MessageBox(f"error: {err}  : maybe a Syntax Error in: {snb} \n"
                                  f"Make Sure you have not removed a comma or somthing important \n Use null for None.",
                                  "Error Applying snbt, please try agian", wx.OK | wx.ICON_INFORMATION)
                    return

            filter_extra_block = self.changedData[x + 3].split("<Extra_Block>")[1]

            if filter_extra_block.split("\n")[1] != 'None':
                org_blk_data = ""
                blk_name_space = self.changedData[x + 3].split("<Extra_Block>")[1].split(':')[0].strip()
                blkname = self.changedData[x + 3].split("<Extra_Block>")[1].split(':')[1].split("\n")[0].strip()
                blk_properties = dict(amulet_nbt.from_snbt(self.changedData[x + 3].split("<Extra_Block>")[1].split("\n",1)[1].split("\n",1)[1]))

                try:
                    self.world.translation_manager.get_version(self.world.level_wrapper.platform,
                                                               self.world.level_wrapper.version).block.get_specification(
                        blk_name_space, blkname, force_blockstate=True)
                except KeyError:
                    re = self.Onmsgbox(f"Block : {blk_name_space, blkname} Can't be found! , If you sure this is correct Click OK")
                    if re == wx.OK:
                        pass
                    else:
                        return
                # eblk = self.world.translation_manager.get_version(self.world.level_wrapper.platform,
                #                                            self.world.level_wrapper.version).block.get_specification(
                #     blk_name_space, blkname, force_blockstate=True)
                e_block = Block('minecraft', blkname, blk_properties)
                eblk = self.world.translation_manager.get_version(self.world.level_wrapper.platform,
                                                           self.world.level_wrapper.version).block.to_universal(e_block)
               # print(eblk, "EEEEE")

                block = Block(block_name_space, block_name, block_properties,e_block)
                platform = 'universal'
              #  print(eblk, "EEEEE", e_block)

            else:

                block = Block(block_name_space, block_name, block_properties)
            #platform = 'universal'

            self.world.set_version_block(cords[0], cords[1], cords[2], self.canvas.dimension,
                                         (platform, self.world.level_wrapper.version), block,
                                         the_nbt)
        self._refresh_chunk(self.canvas.dimension, self.world, cx, cz)
        self.OrgCopy = tuple(self.setOrg())
        try:
            self.window.Enable()
            # self.window.Show(True)
        except:
            pass

    def apply_raw(self,_):
        self.world.purge()
        self.visual_run()

    def run_op(self):
        self.canvas.run_operation(self.finalize_op)


    def _refresh_chunk(self, dimension, world, cx, cz):
        chunk = world.get_chunk(cx, cz, dimension)
        chunk.changed = True

    def finder(self, look, block=False):

        search_also_nbt = self.cb_entity_nbt.GetValue()
        found = set()
        foundcnt = 0
        prg = 0
        self.blocks_entity_dic = collections.defaultdict(dict)
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
            step_prog = cnt/100
            self.prog = wx.ProgressDialog("Searching for : " + str(self.textSearch.GetValue()),
                                          "Searched: " + str(cnt) + " Current Block: ", cnt,
                                          style=wx.PD_AUTO_HIDE | wx.PD_CAN_ABORT | wx.PD_ELAPSED_TIME | wx.PD_REMAINING_TIME)
            self.prog.Show(True)
            for x, y, z in look:
                if self.prog.WasCancelled():
                    self.prog.Hide()
                    self.prog.Destroy()
                    break
                prg += 1
                if prg >= step_prog:
                    self.prog.Update(prg, f"{prg} / {cnt} Current Blockzzz: {x} {y} {z} Found: {foundcnt}")
                    step_prog += step_prog
                if prg >= cnt:
                    self.prog.Hide()
                    self.prog.Destroy()
                block_data, block_enty = self.world.get_version_block(x, y, z, self.canvas.dimension,
                                (self.world.level_wrapper.platform, self.world.level_wrapper.version))
                extra_blk = self.world.get_block(x, y, z, self.canvas.dimension).extra_blocks
                c_extra_block = []
                if len(extra_blk) > 0:
                    for ex_blk in extra_blk:
                        pf, vb = self.world.level_wrapper.platform, self.world.level_wrapper.version
                        e_block = self.world.translation_manager.get_version(pf, vb).block.from_universal(ex_blk)[0]
                        c_extra_block.append(e_block)
                search_string = f"{block_data.base_name} {block_data.properties}"
                if search_also_nbt:
                    if block_enty != None:
                        search_string += block_enty.nbt.to_snbt(0)
                block_e = None
                if str(self.textSearch.GetValue()) in search_string:
                    if block_enty != None:
                        block_e = block_enty.nbt.to_snbt(0)
                    extra_blk = None
                    if len(c_extra_block) > 0:
                        extra_blk = c_extra_block[0]
                    get_block_object = {"Properties": block_data.properties, "Block_nbt": block_e,
                                        "Extra_block": extra_blk}
                    self.blocks_entity_dic[(x, y, z)] = {block_data.namespaced_name: get_block_object}
                    foundcnt += 1

        else:
            print("oks")
            total = 0
            for x, z in look:
                chunk = self.world.get_chunk(x, z, self.canvas.dimension)
                total += len(chunk.blocks.sub_chunks) * 16 * 16 * 16
            self.prog = wx.ProgressDialog(f"Finding: {self.textSearch.GetValue()}",f"Searching {total} Block's: ", total,
                                style=wx.PD_AUTO_HIDE | wx.PD_CAN_ABORT | wx.PD_ELAPSED_TIME | wx.PD_REMAINING_TIME)

            self.prog.Show(True)
            ent_found = ()

            for xx in self.world.block_palette.items():
                pf, vb = self.world.level_wrapper.platform,self.world.level_wrapper.version
                version_block = self.world.translation_manager.get_version(pf, vb).block.from_universal(xx[1])[0]
                s_string = str(version_block.base_name) + " " + str(version_block.properties)

                if str(self.textSearch.GetValue()) in s_string:
                    found.add(xx[0])
            prg_rate = total / 100
            prg_track = prg_rate
            for x, z in look:
                chunk = self.world.get_chunk(x, z, self.canvas.dimension)

                if search_also_nbt:
                    for ee in chunk.block_entities.items():  ########
                        if str(self.textSearch.GetValue()) in ee[1].nbt.to_snbt():
                            ent_found += ((ee[0][0], ee[0][1], ee[0][2]),)

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
                                            found.add(int(chunk.blocks.get_sub_chunk(cy)[dx, dy, dz]))
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
                                                c_extra_block.append(self.world.translation_manager.get_version(
                                                    self.world.level_wrapper.platform,
                                                    self.world.level_wrapper.version).block.from_universal(ex_blk)[
                                                    0])
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
                                            block_e = c_block_main_entitiy[1].nbt.to_snbt(0)
                                        else:
                                            block_e = None
                                        extra_b = None
                                        if len(c_extra_block) > 0:
                                            extra_b = c_extra_block[0]
                                        location = ((x * 16 + dx), (cy * 16 + dy), (z * 16 + dz))
                                        b_name = c_block_main_entitiy[0].namespaced_name
                                        b_prop = c_block_main_entitiy[0].properties
                                        get_blk_obj = {"Properties": b_prop,"Block_nbt": block_e,"Extra_block": extra_b}
                                        self.blocks_entity_dic[location] = { b_name : get_blk_obj }
                    #print(prg, prg_track)
                    if prg > prg_track:
                        prg_track += prg_rate
                        self.prog.Update(prg, f"Searching Blocks: {prg} / {total} Found : {foundcnt}")
                    if prg >= total:
                        self.prog.Hide()
                        self.prog.Destroy()

        self.setdata(None)
        self.OrgCopy = tuple(self.setOrg())

    def _start_the_search(self, _):

        chunks = []
        blocks = []
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
                                              " / Chunks Selected ",
                                              len(self.canvas.selection.selection_group.chunk_locations(16)),
                                              style=wx.PD_AUTO_HIDE | wx.PD_CAN_ABORT | wx.PD_ELAPSED_TIME | wx.PD_REMAINING_TIME)
                self.prog.Show(True)
                for c in self.canvas.selection.selection_group.chunk_locations(16):
                    if self.prog.WasCancelled():
                        self.prog.Hide()
                        self.prog.Destroy()
                        break
                    prg += 1
                    self.prog.Update(prg,
                                     "Searching: " + str(prg) + " / Chunks Selected" + str(
                                         len(self.canvas.selection.selection_group.chunk_locations(16))))
                    chunk = self.world.get_chunk(c[0], c[1], self.canvas.dimension)
                    for ee in chunk.block_entities.items():
                        tmp += (ee[0],)
                for eb in tmp:
                    try:
                        only_be += (blocks[blocks.index(eb)],)
                    except:
                        pass
                if len(only_be) == 0:
                    wx.MessageBox("Sorry No entities Found", "INFO", wx.OK | wx.ICON_INFORMATION)
                    return
                self.finder(only_be, True)
            else:
                # self.finder(blocks, True)
                self.search_raw_level_db(self.textSearch.GetValue())
        elif self.lst_mode.GetSelection() == 1:
            ent_Only = ()
            if search_only_for_e:
                self.prog = wx.ProgressDialog("Finding: Entitiy within selected chunks ", "Searching: " +
                                              str(len(self.canvas.selection.selection_group.chunk_locations(16))) +
                                              " / Chunks Selected: ",
                                              len(self.canvas.selection.selection_group.chunk_locations(16)),
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
        elif self.lst_mode.GetSelection() == 2:
            ent_Only = ()
            if search_only_for_e:
                tot = 0
                for c in self.world.level_wrapper.all_chunk_coords(self.canvas.dimension):
                    tot += 1  # Get Total Chunks in world
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
                # for c in self.world.level_wrapper.all_chunk_coords(self.canvas.dimension):
                #     chunks.append(c)
                # self.finder(chunks)
                self.search_raw_level_db(self.textSearch.GetValue())
                #print([ x for x in self.search_raw_level_db(self.textSearch.GetValue())])

    def pageContol(self, _):
        # print(self.pg)
        self.resetData(self.Pages[self.pg[str(self.lpage.GetSelection())][0]:
                                  self.pg[str(self.lpage.GetSelection())][1]])

    def resetData(self, data):
        try:
            self.Freeze()
            self._the_data.Hide()
            self._the_data.Destroy()
            self._the_data = wx.grid.Grid(self, size=(425, 500), style=5)
            self.Thaw()
        except:
            pass

        tableCount = int(len(data) / 5)
        self._the_data.CreateGrid(tableCount, 5)
        self._the_data.SetRowLabelSize(0)
        self._the_data.SetColLabelValue(0, "x")
        self._the_data.SetColLabelValue(1, "y")
        self._the_data.SetColLabelValue(2, "z")
        self._the_data.SetColLabelSize(20)
        self._the_data.SetColLabelValue(3, "Block")
        self._the_data.SetColLabelValue(4, "Entity Data")
        self._the_data.SetColLabelAlignment(0,0)

        for ind, dd in enumerate(range(0, len(data), 5)):
            self._the_data.SetCellValue(ind, 0, str(data[dd + 0]).replace("'", ""))
            self._the_data.SetCellValue(ind, 1, str(data[dd + 1]).replace("'", ""))
            self._the_data.SetCellValue(ind, 2, str(data[dd + 2]).replace("'", ""))
            self._the_data.SetCellBackgroundColour(ind, 0, "#ef476f")
            self._the_data.SetCellBackgroundColour(ind, 1, "#06d6a0")
            self._the_data.SetCellBackgroundColour(ind, 2, "#118ab2")
            self._the_data.SetCellValue(ind, 3, str(data[dd + 3]).replace("'", "").replace("\\n", "\n"))
            self._the_data.SetCellBackgroundColour(ind, 3, "#8ecae6")
            if "null" not in data[dd + 4]:
                self._the_data.SetCellBackgroundColour(ind, 4, "#95d5b2")
            self._the_data.SetCellValue(ind, 4, str(data[dd + 4]))

        self._the_data.Bind(wx.grid.EVT_GRID_CELL_RIGHT_CLICK, self.gridClick)
        self._the_data.Bind(wx.grid.EVT_GRID_CELL_LEFT_CLICK, self.gridClick)
        self.topTable.Add(self._the_data, 0, wx.TOP, 0)
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

        ox,oy,oz = self.canvas.camera.location

        x,y,z = (self._the_data.GetCellValue(event.Row,0),
                 self._the_data.GetCellValue(event.Row,1),
                 self._the_data.GetCellValue(event.Row,2))
        xx, yy, zz = float(x), float(y), float(z)

        def goto(_):
            self.canvas.camera.set_location((xx,yy + 4,zz))
            self.canvas.camera._notify_moved()
        def gobak(_):
            self.canvas.camera.set_location((ox,oy,oz))
            self.canvas.camera._notify_moved()

        self.frame = wx.Frame(self.parent, id=wx.ID_ANY, pos=wx.DefaultPosition, size=(400, 700),
                              style=(
                                      wx.MINIMIZE_BOX | wx.MAXIMIZE_BOX | wx.RESIZE_BORDER | wx.SYSTEM_MENU | wx.CAPTION | wx.CLOSE_BOX | wx.CLIP_CHILDREN | wx.FRAME_FLOAT_ON_PARENT),
                              name="Panel",
                              title="Cell (Row: " + str(event.GetRow()) + " Col: " + str(event.GetCol()) + ")")
        sizer_P = wx.BoxSizer(wx.VERTICAL)
        sizer_H = wx.BoxSizer(wx.HORIZONTAL)
        sizer_H2 = wx.BoxSizer(wx.HORIZONTAL)
        self.frame.SetSizer(sizer_P)
        save_close = wx.Button(self.frame, label="Save_Close")
        save_close.Bind(wx.EVT_BUTTON, self.ex_save_close(event.GetRow(), event.GetCol()))
        sizer_P.Add(sizer_H)
        sizer_P.Add(sizer_H2)

        self.textGrid = wx.TextCtrl(self.frame, style=wx.TE_MULTILINE | wx.TE_BESTWRAP, size=(400, 750))
        copy_to_find = wx.Button(self.frame, label="Copy To Find")
        copy_to_find.Bind(wx.EVT_BUTTON, self.copy_text_to_find)
        copy_to_replace = wx.Button(self.frame, label="Copy To Replace")
        goto_button = wx.Button(self.frame, label="Go to Location")
        goto_button.Bind(wx.EVT_BUTTON, goto)
        gobak_button = wx.Button(self.frame, label="Go Back to old Location")
        gobak_button.Bind(wx.EVT_BUTTON, gobak)
        copy_to_replace.Bind(wx.EVT_BUTTON, self.copy_text_to_replace)
        sizer_H.Add(save_close)
        sizer_H.Add(copy_to_find)
        sizer_H.Add(copy_to_replace)
        sizer_H.Add(goto_button)
        sizer_H2.Add(gobak_button, 0, wx.LEFT,240)
        sizer_P.Add(self.textGrid)

        if event.GetCol() < 3:
            self.textGrid.SetValue(f'Block location: {x,y,z}\nyour old location: {ox,oy,oz}')
            self.canvas.camera.set_location((xx, yy + 4, zz))
            self.canvas.camera._notify_moved()
            save_close.SetLabel("Close")
        else:
            self.textGrid.SetValue(self._the_data.GetCellValue(event.GetRow(), event.GetCol()))
        self.frame.Show(True)
        save_close.Show(True)


    def copy_text_to_find(self, _):
        self.textF.SetValue(self.textGrid.GetValue())

    def copy_text_to_replace(self, _):
        self.textR.SetValue(self.textGrid.GetValue())

    def ex_save_close(self, r, c):
        def OnClick(event):
            if c < 3:
                pass
            else:
                val = self.textGrid.GetValue()
                self._the_data.SetCellValue(r, c, val)
                try:
                    current_page = self.lpage.GetSelection()
                except:
                    current_page = 0
                self.Pages[(current_page * self.pageSize) + ((r * 5 + c))] = val

            self.frame.Close()

        return OnClick

    def checkForPages(self, data):
        try:
            self.Pages = data
            self.lpage.Hide()
            self.lpage.Destroy()

        except:
            pass
        self.pageSize = 1500
        # self.start = 0
        # self.end = 0

        if len(data) >= self.pageSize:
            ps = self.pageSize
            max_ = len(data)
            max_pages = max_//self.pageSize
            Pages = [(x - ps, x) for x in range(ps, max_, ps)]
            over_flow = 0
            if Pages[-1][1] < max_:
                Pages.append((Pages[-1][1], max_))
                # ps = Pages[-1][1]
                # print(Pages[-1][1])
            self.p_label = wx.StaticText(self, label="Pages:")
            self.progress_bar(max_pages, 1, start=True, title="Adding Pages ", text="...")
            # self.pg = {"Page: " + str(i): x for i, x in enumerate(Pages)}
            self.lpage = wx.Choice(self, choices=[])
            self.pg = {[self.progress_bar(max_pages, i,update=True, title="Adding Pages ", text=f"..."), str(i)][1]:x for i, x in enumerate(Pages)}
            self.progress_bar(100, 1, start=True, title="Almost Done", text="...")
            self.progress_bar(100, 80, update=True, title=f"Almost Done...Appending {len([*self.pg])} Items.  ", text=f"...")
            self.lpage.AppendItems([*self.pg])
            self.progress_bar(100, 100, update=True, title="Done ", text=f"...")
            self.lpage.Bind(wx.EVT_CHOICE, self.pageContol)
            self.lpage.SetSelection(0)
            self.grid_page = wx.GridSizer(1,2,0,0)
            self.grid_page.Add(self.p_label, 0, wx.LEFT, -160)
            self.grid_page.Add(self.lpage, 0, wx.LEFT, -120)

            self.saveload.Add(self.grid_page,0, wx.TOP, 30)
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
        for ind, (k, v) in enumerate(self.blocks_entity_dic.items()):
            x , y , z = f"{k[0]}",f"{k[1]}",f"{k[2]}"
            block_name = list(v.keys())[0]
            extra_block = None
            if v[block_name]['Extra_block']:
                extra_block = f"{v[block_name]['Extra_block'].namespaced_name }\n{amulet_nbt.TAG_Compound(v[block_name]['Extra_block'].properties).to_snbt(1)}"
            #print(amulet_nbt.TAG_Compound(v[block_name]['Properties']).to_snbt())
            Block = f"{block_name}\n{amulet_nbt.TAG_Compound(v[block_name]['Properties']).to_snbt(1)}\n<Extra_Block>\n{extra_block}\n "
            if v[block_name]['Block_nbt']:
                entitie = amulet_nbt.from_snbt(v[block_name]['Block_nbt'].replace(";B", ";"))
                if entitie.get("Items"):
                    for i, da in enumerate(entitie["Items"]):
                        if hasattr(da, "get"):
                            if da.get('tag'):
                                if da.get('tag').get("internalComponents"):
                                    data = amulet_nbt.NBTFile(
                                        entitie["Items"][i]['tag']["internalComponents"]).save_to(
                                        compressed=False, little_endian=True).replace(
                                        b'\x08\n\x00StorageKey\x08\x00',
                                        b'\x07\n\x00StorageKey\x08\x00\x00\x00', )
                                    nbt = amulet_nbt.load(data, compressed=False, little_endian=True)
                                    entitie["Items"][i]['tag'] \
                                        ["internalComponents"]["EntityStorageKeyComponent"] = nbt[
                                        "EntityStorageKeyComponent"]
                entitie = entitie.to_snbt(1)
            else:
                entitie = str("null")
            self.Pages += x, y, z, Block, entitie
        self.checkForPages(self.Pages)


    def select_the_blocks(self, _):
        blockPosdata = {}
        group = []
        for x in range(0,len(self.Pages)-1, 5):
            filter_text = f"{self.Pages[x]} {self.Pages[x+1]} {self.Pages[x+2]} {self.Pages[x+3]} {self.Pages[x+4]}"
            if self.textfilter.GetValue() in filter_text:
                blockPosdata[(self.Pages[x],self.Pages[x+1],self.Pages[x+2])] = (int(self.Pages[x]),int(self.Pages[x+1]),int(self.Pages[x+2]))
        total = len(blockPosdata)
        totalc = total / 100
        self.prog = wx.ProgressDialog("Setting Selection Boxes", "Selecting: " +
                                      str(len(blockPosdata )) +
                                      " / To Be Selected: ",
                                      100,
                                      style=wx.PD_AUTO_HIDE | wx.PD_CAN_ABORT | wx.PD_ELAPSED_TIME | wx.PD_REMAINING_TIME)
        self.prog.Show(True)

        total
        prg = 0
        p_cnt = 0
        for i,(k,v) in enumerate(blockPosdata.items()):
            p_cnt += 1
            va = (v[0], v[1], v[2])
            vv = (v[0]+1,v[1]+1,v[2]+1)
            group.append(SelectionBox(va,vv))
            if self.prog.WasCancelled():
                self.prog.Hide()
                self.prog.Destroy()
                break

            if p_cnt >= totalc:
                prg += 1
                p_cnt = 0
                self.prog.Update(prg,
                             "Selecting: " + str(i) + " / To Be Selected: " + str(
                                 len(blockPosdata)))
                sel = SelectionGroup(group).merge_boxes()
                self.canvas.selection.set_selection_group(sel)
                if i >= total-1:
                    self.prog.Update(100,
                                     "Selecting: " + str(i) + " / To Be Selected: " + str(
                                         len(blockPosdata)))
                    sel = SelectionGroup(group).merge_boxes()
                    self.canvas.selection.set_selection_group(sel)

    def byte_dim(self):
        dim = self.canvas.dimension
        byte_dim = b''
        if dim == "minecraft:the_end":
            byte_dim = b'\x02\x00\x00\x00'
        elif dim == "minecraft:the_nether":
            byte_dim = b'\x01\x00\x00\x00'
        return byte_dim

    def progress_bar(self, total, cnt, start=False, update=False,
                     title='Searching subchunks', text="True"):
        if text == "True":
           text = self.textSearch.GetValue()

        def start_progress(self):
            self.prog = wx.ProgressDialog(f"Searching for : {text}",
                                          f"Searched: {cnt} / {total}", total,
                                          style=wx.PD_AUTO_HIDE | wx.PD_CAN_ABORT
                                                | wx.PD_ELAPSED_TIME | wx.PD_REMAINING_TIME)
            self.prog.Show(True)

        def update_progress(self):
            self.prog.Update(cnt, f"{title} : {text}:  {cnt} / {total}")
        if start:
            start_progress(self)
        if update:
            if self.prog.WasCancelled():
                return self.prog.WasCancelled()
            else:
                update_progress(self)

    def search_raw_level_db(self, search):
        self.Pages.clear()
        from amulet_nbt import utf8_escape_decoder
        byte_dim = self.byte_dim()
        locations = []
        blk_entity_raw = {}
        total_len = 0
        count = 0
        if self.lst_mode.GetSelection() == 0:
            chunks = [struct.pack('<ii', xx, zz) for (xx, zz) in self.canvas.selection.selection_group.chunk_locations()]
        for k, v in self.level_db.iterate(start=b'\x00\x00\x00\x00\x00\x00\x00\x00/',
                              end=b'\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF/'):
            if k[-1] == 49:
                if byte_dim:
                    if len(k) > 12:
                        if self.lst_mode.GetSelection() == 0:
                            if k[:8] in chunks:
                                blk_entity_raw[k] = v
                                #total_len += 1
                        else:
                            blk_entity_raw[k] = v
                else:
                    if len(k) < 12:
                        if self.lst_mode.GetSelection() == 0:
                            if k[:8] in chunks:
                                blk_entity_raw[k] = v
                        else:
                            blk_entity_raw[k] = v
            if byte_dim:
                if len(k) > 12 and  k[-2] == 47:
                    if k[8:12] == byte_dim:
                        if self.lst_mode.GetSelection() == 0:
                            if k[:8] in chunks:
                                total_len +=1
                        else:
                            total_len +=1

            else:
                if len(k) == 10 and k[-2] == 47:
                    if self.lst_mode.GetSelection() == 0:
                        if k[:8] in chunks:
                            total_len += 1
                    else:
                        total_len += 1

        self.progress_bar(total_len, count, start=True)
        for k, v in self.level_db.iterate(start=b'\x00\x00\x00\x00\x00\x00\x00\x00/',
                              end=b'\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF'):
            chunk_v = False
            if byte_dim:
                if len(k) > 12 and  k[-2] == 47:
                    if k[8:12] == byte_dim:
                        if self.lst_mode.GetSelection() == 0:
                            if k[:8] in chunks:
                                chunk_v = True
                                if self.progress_bar(total_len, count, update=True):
                                    self.prog.Hide()
                                    self.prog.Destroy()
                                    break
                        else:
                            chunk_v = True
                            if self.progress_bar(total_len, count, update=True):
                                self.prog.Hide()
                                self.prog.Destroy()
                                break
                        count += 1
                        if chunk_v:
                            xc, ys_c, zc = (int.from_bytes(k[0:4], 'little', signed=True),
                                            k[-1],
                                            int.from_bytes(k[4:8], 'little', signed=True))
                            offs = self.get_v_off(v)
                            if search.encode() in v:
                                blocks, block_bits, extra_blk, extra_blk_bits = self.get_pallets_and_extra(v[offs:])
                                for blk in blocks:
                                    if search in f'{blk}':
                                        inx = blocks.index(blk)
                                        for idx, blkval in numpy.ndenumerate(block_bits):
                                            if blkval == inx:
                                                locations.append(idx)

            else:

                if len(k) == 10 and k[-2] == 47:
                    if self.lst_mode.GetSelection() == 0:
                        if k[:8] in chunks:
                            chunk_v = True
                            count += 1
                            if self.progress_bar(total_len, count, update=True):
                                self.prog.Hide()
                                self.prog.Destroy()
                                break
                    else:
                        chunk_v = True
                        count += 1
                        if self.progress_bar(total_len, count, update=True):
                            self.prog.Hide()
                            self.prog.Destroy()
                            break




                    b_y = k[-1]
                    if k[-1] > 127:
                        b_y = (256 - k[-1]) * (-1)
                    xc, ys_c, zc = (int.from_bytes(k[0:4], 'little', signed=True),
                                    b_y,
                                    int.from_bytes(k[4:8], 'little', signed=True))
                    offs = self.get_v_off(v)
            if chunk_v:
                if search.encode() in v:

                    blocks, block_bits, extra_blk, extra_blk_bits = self.get_pallets_and_extra(v[offs:])
                    blks = [x.get("name") for x in blocks]
                    if search in f'{blks}':
                        blks = [x for x in blocks if search in str(x)]
                        for blk in blks:
                            inx = blocks.index(blk)
                            locat = numpy.where(block_bits == inx)
                            nx, ny, nz = locat
                            # print(nx, ny, nz, "CHUNK", xc, ys_c, zc,"CORDS" ,(xc * 16), (ys_c * 16),(zc * 16))
                            l = [(nxx + (xc * 16), nyy + (ys_c * 16), nzz + (zc * 16),
                                  f"{blocks[inx]['name']}\n{blocks[inx]['states'].to_snbt(1)}", "null")
                                 for (nxx, nyy, nzz) in zip(nx.tolist(), ny.tolist(), nz.tolist())]
                            has_nbt = False
                            if blk_entity_raw.get(k[:-2] + b"\x31"):
                                if search.title().encode() in blk_entity_raw.get(k[:-2] + b"\x31"):
                                    has_nbt = True
                            for x, y, z, b, e in l:
                                if has_nbt:
                                    blk_entity_data = blk_entity_raw[k[:-2] + b"\x31"]
                                    nbt_block_ety_list = []
                                    while blk_entity_data:
                                        rc = amulet_nbt.ReadContext()
                                        nbt = amulet_nbt.load(
                                            blk_entity_data,
                                            little_endian=True,
                                            read_context=rc,
                                            string_decoder=utf8_escape_decoder,
                                        )
                                        blk_entity_data = blk_entity_data[rc.offset:]
                                        nbt_block_ety_list.append(nbt.compound)
                                    for n in nbt_block_ety_list:
                                        ex, ey, ez = (
                                            n.get("x").py_data,
                                            n.get("y").py_data,
                                            n.get("z").py_data,
                                        )
                                        # print(ex, ey, ex, x, y, z)
                                        if (ex, ey, ez) == (x, y, z):
                                            e = n.to_snbt(1)

                                if extra_blk:
                                    b += f"\n<Extra_Block>\n" \
                                         f"{extra_blk[extra_blk_bits[x % 16][y % 16][z % 16]]['name']}\n" \
                                         f"{extra_blk[extra_blk_bits[x % 16][y % 16][z % 16]]['states'].to_snbt(1)}"
                                else:
                                    b += f"\n<Extra_Block>\nNone"
                                if self.lst_mode.GetSelection() == 0:
                                    cords = [ (xx,yy,zz) for (xx,yy,zz) in self.canvas.selection.selection_group.blocks]
                                    if (x,y,z) in cords:
                                        self.Pages += x, y, z, b, e
                                else:

                                    self.Pages += x, y, z, b, e


                        # yield l, blocks[inx]
                        # for idx, blkval in numpy.ndenumerate(block_bits):
                        #     x, y, z = idx
                        #     xx,yy,zz = (xc*16) + x, (ys_c *16) + y,  (zc*16) + z
                        #     if blkval == inx:
                        #         locations.append((xx,yy,zz))

            # print([(x, "_")  for x in locations])
        self.OrgCopy = copy.copy(self.Pages)
        print(len(self.Pages),len(self.OrgCopy))
        self.checkForPages(self.Pages)

    def get_block_obj_data(self, chunk__key, old_blk, new_blk):
        chunk = self.level_db.get(chunk__key)
        offs = self.get_v_off(chunk)
        data_f = b'version'
        old_extra_block = None
        new_extra_block = None
        version_raw = chunk.find(data_f)
        print(chunk[version_raw + len(data_f):version_raw + len(data_f) + 4])
        byte_version = chunk[version_raw + len(data_f):version_raw + len(data_f) + 4]
        version = amulet_nbt.IntTag(int.from_bytes(byte_version, "little"))
        eb_str = "<Extra_Block>"
        pnt_n = old_blk.find('{')
        pnt_e = old_blk.find('}')
        pnt_eb = old_blk.find(eb_str)+len(eb_str)
        if ":" in old_blk[pnt_eb:]:
            pnt = old_blk.find("{",pnt_eb)
            old_extra_name = amulet_nbt.StringTag(old_blk[pnt_eb:pnt].strip())
            old_extra_prop = amulet_nbt.from_snbt(old_blk[pnt:].strip())
            old_extra_block = amulet_nbt.CompoundTag({'name': old_extra_name, 'states': old_extra_prop, 'version': version})

        pnt_neb = new_blk.find(eb_str) + len(eb_str)
        if ":" in new_blk[pnt_neb:]:
            pnt = new_blk.find("{", pnt_neb)
            new_extra_name = amulet_nbt.StringTag(new_blk[pnt_neb:pnt].strip())
            new_extra_prop = amulet_nbt.from_snbt(new_blk[pnt:].strip())
            new_extra_block = amulet_nbt.CompoundTag({'name': new_extra_name, 'states': new_extra_prop, 'version': version})

        pnt_nn = new_blk.find('{')
        pnt_ee = new_blk.find('}')
        old_blk_name = amulet_nbt.StringTag(old_blk[:pnt_n].strip())
        old_blk_prop = amulet_nbt.from_snbt(old_blk[pnt_n:pnt_e + 1].strip())
        new_blk_name = amulet_nbt.StringTag(new_blk[:pnt_nn].strip())
        new_blk_prop = amulet_nbt.from_snbt(new_blk[pnt_nn:pnt_ee + 1].strip())

        new_block = amulet_nbt.CompoundTag({'name': new_blk_name, 'states': new_blk_prop, 'version': version})
        old_block = amulet_nbt.CompoundTag({'name': old_blk_name, 'states': old_blk_prop, 'version': version})

        return new_block,new_extra_block,old_block,old_extra_block,chunk,offs,version

    # block_old = Block('minecraft', o_blk_name.replace("minecraft:",""), dict(amulet_nbt.from_snbt(o_blk_prop)))

    def raw_data_find(self):
        import math
        byte_dim = self.byte_dim()

        total = len(self.Pages)
        count = 0
        chunk_data_dic = collections.defaultdict(tuple)
        chunk_data_dic_strict = collections.defaultdict(tuple)
        chunk_enty_data_dic = collections.defaultdict(list)
        new_blocks_data_dic = collections.defaultdict(list)
        if self.world.level_wrapper.platform == "java":
            pass #TODO
        else:
            for i, p in enumerate(range(0,len(self.OrgCopy),5)):
                (x,y,z,ob,oe) = (self.OrgCopy[p],self.OrgCopy[p+1],
                                self.OrgCopy[p+2],self.OrgCopy[p+3],self.OrgCopy[p+4])
                nb,ne = self.Pages[p+3],self.Pages[p+4]
                cx,cz,yc = int(x)//16,int(z)//16,int(y) // 16 #block_coords_to_chunk_coords(x,z)
                chunkkey = struct.pack('<ii', cx,cz ) + byte_dim + b'\x2f'+ struct.pack('b', yc)
                if ob != nb:
                    if self.lst_mode.GetSelection() == 0:
                        chunk_data_dic_strict[(chunkkey, ob, x, y, z)] = (nb, x, y, z)
                    else:
                        chunk_data_dic[(chunkkey,ob)] = (nb, x,y,z) # this groups the changes together for each subchunk.
                if ne != oe: # add only if not the same
                    chunk_enty_data_dic[chunkkey].append((oe,ne,nb,x,y,z))
                    ################################## I LEFT OFF HERE NEED TO SET THE LOCATION TAGS IF THEY ARE THERE

        for k,v in chunk_enty_data_dic.items():
            chunk_key = k
            block_entitiy = []  # collections.defaultdict()
            raw_enty = self.level_db.get(chunk_key[:-2] + b'\x31')

            while raw_enty:
                nbt, p = amulet_nbt.load(raw_enty, little_endian=True, offset=True)
                raw_enty = raw_enty[p:]
                block_entitiy.append(nbt.value)

            for o_e,n_e,nb,xx, yy, zz in v:
                if "null" in n_e:
                    block_entitiy.remove(amulet_nbt.from_snbt(o_e))
                else:
                    new_data = amulet_nbt.from_snbt(n_e)
                    for i, d in enumerate(block_entitiy):
                        x, y, z = d['x'], d['y'], d['z']
                        if (x, y, z) == (xx, yy, zz):
                            basename, blkname = nb.split('\n', 1)[0].split(":")
                            blk_name = ''.join([i.title() for i in blkname.split('_')])
                            new_data['id'] = amulet_nbt.StringTag(blk_name)
                            new_data['x'], new_data['y'], new_data['z'] = \
                                amulet_nbt.IntTag(xx), amulet_nbt.IntTag(yy), amulet_nbt.IntTag(zz)
                            if new_data.get('pairx'):
                                new_data['pairx'] = amulet_nbt.IntTag(xx + new_data.get('pairx').value)
                                new_data['pairz'] = amulet_nbt.IntTag(zz + new_data.get('pairz').value)
                            block_entitiy[i] = new_data

            new_raw_eny = b"".join([x.save_to(compressed=False,little_endian=True) for x in block_entitiy])
            self.level_db.put(chunk_key[:-2] + b'\x31', new_raw_eny)
        if self.lst_mode.GetSelection() == 0:
            for key, val in chunk_data_dic_strict.items():
                print("OK strict")
                chunk__key, old_blk, new_blk = key[0], key[1], val[0]
                (
                    new_block,
                    new_extra_block,
                    old_block,
                    old_extra_block,
                    chunk,
                    offs,
                    version
                ) = self.get_block_obj_data(chunk__key, old_blk, new_blk)
                blocks, block_bits, extra_blk, extra_blk_bits = self.get_pallets_and_extra(chunk[offs:])
                # extra_version_holder = None
                version_holder = None
                if extra_blk:
                    for x in extra_blk:
                        x.pop('version')
                if blocks:
                    for b in blocks:
                        version_holder = b.pop('version')
                if new_block:
                    new_block.pop('version')
                if new_extra_block:
                    new_extra_block.pop('version')
                if old_block:
                    old_block.pop('version')
                if old_extra_block:
                    old_extra_block.pop('version')

                air_block = amulet_nbt.CompoundTag({
                    'name': amulet_nbt.StringTag("minecraft:air"),
                    'states': amulet_nbt.CompoundTag({}),
                    # 'version': version
                })

                the_o_inx = blocks.index(old_block)
                locate = numpy.where(block_bits == the_o_inx)
                nx, ny, nz = locate
                bit_locations = [(nxx, nyy, nzz) for (nxx, nyy, nzz) in zip(nx.tolist(), ny.tolist(), nz.tolist())]

                # if old_block in blocks:
                #     if ((old_block != new_block) and (old_block != air_block)):
                #         blocks.remove(old_block)
                if new_block in blocks:
                    the_n_inx = blocks.index(new_block)
                    block_bits[val[1] % 16][val[2] % 16][val[3] % 16] = the_n_inx
                else:
                    blocks.append(new_block)
                    the_n_inx = blocks.index(new_block)
                    block_bits[val[1] % 16][val[2] % 16][val[3] % 16] = the_n_inx

                if (new_extra_block == old_extra_block):
                    pass
                elif (not extra_blk and new_extra_block):
                    extra_blk_bits = numpy.zeros((16, 16, 16), dtype=numpy.int16)
                    extra_blk.append(air_block)
                    extra_blk.append(new_extra_block)
                    e_inx = extra_blk.index(new_extra_block)
                    extra_blk_bits[val[1] % 16][val[2] % 16][val[3] % 16] = e_inx

                elif (new_extra_block not in extra_blk and new_extra_block and old_extra_block):
                    the_o_eb_inx = extra_blk.index(old_extra_block)
                    # if old_extra_block in extra_blk:
                        # if "minecraft:air" not in old_extra_block.get("name").to_snbt():
                        #     extra_blk.remove(old_extra_block)
                        #     extra_blk_bits[extra_blk_bits > the_o_eb_inx] -= 1
                    extra_blk.append(new_extra_block)
                    e_inx = extra_blk.index(new_extra_block)
                    extra_blk_bits[val[1] % 16][val[2] % 16][val[3] % 16] = e_inx
                    for x, y, z in bit_locations:
                        extra_blk_bits[x][y][z] = e_inx
                elif (new_extra_block in extra_blk and old_extra_block):
                    if new_extra_block not in extra_blk:
                        extra_blk.append(new_extra_block)
                    e_inx = extra_blk.index(new_extra_block)
                    the_o_eb_inx = extra_blk.index(old_extra_block)
                    # if "minecraft:air" not in old_extra_block.get("name").to_snbt():
                    #     extra_blk.remove(old_extra_block)
                    #     extra_blk_bits[extra_blk_bits >= the_o_eb_inx] -= 1
                    extra_blk_bits[val[1] % 16][val[2] % 16][val[3] % 16] = e_inx
                elif new_extra_block:
                    if new_extra_block not in extra_blk:
                        extra_blk.append(new_extra_block)
                    e_inx = extra_blk.index(new_extra_block)
                    extra_blk_bits[val[1] % 16][val[2] % 16][val[3] % 16] = e_inx

                if extra_blk:
                    for i, x in enumerate(extra_blk):
                        x['version'] = version_holder
                if blocks:
                    for i, b in enumerate(blocks):
                        b['version'] = version_holder
                y_level = struct.unpack('b', chunk__key[-1:])[0]
                new_update_raw = b''.join(self.back_2_raw(block_bits, blocks, extra_blk_bits, extra_blk, y_level))
                self.level_db.put(chunk__key, new_update_raw)
                count += 1
                yield count / total




        for key,val in chunk_data_dic.items():
            print("OK")
            chunk__key, old_blk, new_blk = key[0],key[1],val[0]
            (
                new_block,
                new_extra_block,
                old_block,
                old_extra_block,
                chunk,
                offs,
                version
            ) = self.get_block_obj_data(chunk__key, old_blk, new_blk)
            blocks, block_bits, extra_blk, extra_blk_bits = self.get_pallets_and_extra(chunk[offs:])
            #extra_version_holder = None
            version_holder = None
            if extra_blk:
                for x in extra_blk:
                    x.pop('version')
            if blocks:
                for b in blocks:
                    version_holder = b.pop('version')
            if new_block:
                new_block.pop('version')
            if  new_extra_block:
                new_extra_block.pop('version')
            if old_block:
                old_block.pop('version')
            if old_extra_block:
                old_extra_block.pop('version')

            air_block = amulet_nbt.CompoundTag({
                'name': amulet_nbt.StringTag("minecraft:air"),
                'states': amulet_nbt.CompoundTag({}),
                #'version': version
            })

            the_o_inx = blocks.index(old_block)
            locate = numpy.where(block_bits == the_o_inx)
            nx, ny, nz = locate
            bit_locations = [(nxx, nyy, nzz) for (nxx, nyy, nzz) in zip(nx.tolist(), ny.tolist(), nz.tolist())]

            if old_block in blocks:
                if ((old_block != new_block) and (old_block != air_block)):
                    blocks.remove(old_block)
            if new_block in blocks:
                the_n_inx = blocks.index(new_block)
                block_bits[block_bits == the_o_inx] = the_n_inx
            elif (old_block != air_block):
                blocks.insert(the_o_inx, new_block)
            else:
                blocks.append(new_block)
                the_n_inx = blocks.index(new_block)
                block_bits[block_bits == the_o_inx] = the_n_inx

            if (new_extra_block == old_extra_block):
                pass
            elif (not extra_blk and new_extra_block):
                extra_blk_bits = numpy.zeros((16, 16, 16), dtype=numpy.int16)
                extra_blk.append(air_block)
                extra_blk.append(new_extra_block)
                e_inx = extra_blk.index(new_extra_block)
                for x, y, z in bit_locations:
                    extra_blk_bits[x][y][z] = e_inx

            elif (new_extra_block not in extra_blk and new_extra_block and old_extra_block):
                the_o_eb_inx = extra_blk.index(old_extra_block)
                if old_extra_block in extra_blk:
                    if "minecraft:air" not in old_extra_block.get("name").to_snbt():
                        extra_blk.remove(old_extra_block)
                        extra_blk_bits[extra_blk_bits > the_o_eb_inx] -= 1
                extra_blk.append(new_extra_block)
                e_inx = extra_blk.index(new_extra_block)

                for x, y, z in bit_locations:
                    extra_blk_bits[x][y][z] = e_inx
            elif (new_extra_block in extra_blk and old_extra_block):
                if new_extra_block not in extra_blk:
                    extra_blk.append(new_extra_block)
                e_inx = extra_blk.index(new_extra_block)
                the_o_eb_inx = extra_blk.index(old_extra_block)
                if "minecraft:air" not in old_extra_block.get("name").to_snbt():
                    extra_blk.remove(old_extra_block)
                    extra_blk_bits[extra_blk_bits >= the_o_eb_inx] -= 1
                for x, y, z in bit_locations:
                    extra_blk_bits[x][y][z] = e_inx
            elif new_extra_block:
                if new_extra_block not in extra_blk:
                    extra_blk.append(new_extra_block)
                e_inx = extra_blk.index(new_extra_block)
                for x, y, z in bit_locations:
                    extra_blk_bits[x][y][z] = e_inx

            if extra_blk:
                for i, x in enumerate(extra_blk):
                    x['version'] = version_holder
            if blocks:
                for i,  b in enumerate(blocks):
                    b['version'] = version_holder

            y_level = struct.unpack('b', chunk__key[-1:])[0]
            new_update_raw = b''.join(self.back_2_raw(block_bits,blocks , extra_blk_bits, extra_blk, y_level))
            self.level_db.put(chunk__key, new_update_raw)
            count += 1
            yield count / total
        self.OrgCopy = copy.copy(self.Pages)

    def visual_run(self):
        self.canvas.run_operation(self.raw_data_find)
        self.canvas.renderer.render_world.unload()
        self.canvas.renderer.render_world.enable()

    def get_v_off(self, data):
        version = data[0]
        offset = 3
        self.v_byte = 9
        if version == 8:
            self.v_byte = 8
            offset = 2
        return offset

    def get_pallets_and_extra(self, raw_sub_chunk):

        block_pal_dat, block_bits, bpv = self.get_blocks(raw_sub_chunk)
        if bpv < 1:
            pallet_size, pallet_data, off = 1, block_pal_dat, 0
        else:
            pallet_size, pallet_data, off = struct.unpack('<I', block_pal_dat[:4])[0], block_pal_dat[4:], 0
        blocks = []
        block_pnt_bits = block_bits
        extra_pnt_bits = []
        op = amulet_nbt.ReadContext()
        nbt_p = amulet_nbt.load_many(pallet_data,count=pallet_size, little_endian=True, read_context=op)
        pallet_data = pallet_data[op.offset:]
        for n in nbt_p:
            blocks.append(n.compound)
        extra_blocks = []
        if pallet_data:
            block_pal_dat, extra_block_bits, bpv = self.get_blocks(pallet_data)
            if bpv < 1:
                pallet_size, pallet_data, off = 1, block_pal_dat, 0
            else:
                pallet_size, pallet_data, off = struct.unpack('<I', block_pal_dat[:4])[0], block_pal_dat[4:], 0
            extra_pnt_bits = extra_block_bits
            op = amulet_nbt.ReadContext()
            nbt_p2 = amulet_nbt.load_many(pallet_data, count=pallet_size, little_endian=True, read_context=op)
            for n in nbt_p2:
                extra_blocks.append(n.compound)
        return blocks, block_pnt_bits, extra_blocks, extra_pnt_bits

    def back_2_raw(self, lay_one, pal_one, lay_two, pal_two, y_level):
        byte_blocks = []
        bytes_nbt = []
        header, lays = b'', 1
        if len(pal_two) > 0:
            lays = 2
        if self.v_byte > 8:
            header = struct.pack('bbb', self.v_byte, lays,  y_level)
        else:
            header = struct.pack('bb', self.v_byte, lays)

        if len(pal_two) > 0:
            block_list = [lay_one, lay_two]
            pal_len = [len(pal_one), len(pal_two)]
            raw = b''
            for rnbt in pal_one:
                raw += rnbt.save_to(compressed=False, little_endian=True)
            bytes_nbt.append(raw)
            raw = b''
            for rnbt in pal_two:
                raw += rnbt.save_to(compressed=False, little_endian=True)
            bytes_nbt.append(raw)
        else:
            block_list = [lay_one]
            pal_len = [len(pal_one)]
            raw = b''
            for rnbtx in pal_one:
                raw += rnbtx.save_to(compressed=False, little_endian=True)
            bytes_nbt.append(raw)
        for ii, b in enumerate(block_list):
            bpv = max(int(numpy.amax(b)).bit_length(), 1)
            if bpv == 7:
                bpv = 8
            elif 9 <= bpv <= 15:
                bpv = 16
            if ii > 0:
                header = b''
            compact_level = bytes([bpv << 1])
            bpw = (32 // bpv)
            wc = -(-4096 // bpw)
            compact = b.swapaxes(1, 2).ravel()
            compact = numpy.ascontiguousarray(compact[::-1], dtype=">i").view(dtype="uint8")
            compact = numpy.unpackbits(compact)
            compact = compact.reshape(4096, -1)[:, -bpv:]
            compact = numpy.pad(compact, [(wc * bpw - 4096, 0), (0, 0)], "constant", )
            compact = compact.reshape(-1, bpw * bpv)
            compact = numpy.pad(compact, [(0, 0), (32 - bpw * bpv, 0)], "constant", )
            compact = numpy.packbits(compact).view(dtype=">i4").tobytes()
            compact = bytes(reversed(compact))
            byte_blocks.append(header + compact_level + compact + struct.pack("<I", pal_len[ii]) + bytes_nbt[ii])
        return byte_blocks

    def get_blocks(self, raw_sub_chunk):
        bpv, rawdata = struct.unpack("b", raw_sub_chunk[0:1])[0] >> 1, raw_sub_chunk[1:]
        if bpv > 0:
            bpw = (32 // bpv)
            wc = -(-4096 // bpw)
            buffer = numpy.frombuffer(bytes(reversed(rawdata[: 4 * wc])), dtype="uint8")
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

    @property
    def level_db(self):
        level_wrapper = self.world.level_wrapper
        if hasattr(level_wrapper, "level_db"):
            return level_wrapper.level_db
        else:
            return level_wrapper._level_manager._db

export = dict(name="FinderReplacer v.3.01B", operation=FinderReplacer)  # By PremiereHell
