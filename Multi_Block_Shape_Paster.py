
from typing import TYPE_CHECKING, Tuple

import amulet
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
from amulet.api.registry.biome_manager import BiomeManager
from amulet.api.chunk.biomes import Biomes
from amulet.api.chunk.biomes import Biomes3D
from amulet.api.chunk.biomes import BiomesShape
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
import datetime
from pathlib import Path
from ctypes import windll
from amulet.api.data_types import PointCoordinates
from amulet_map_editor.programs.edit.api.behaviour import StaticSelectionBehaviour
from amulet_map_editor.programs.edit.api.events import EVT_SELECTION_CHANGE
from amulet_map_editor.programs.edit.api.behaviour import BlockSelectionBehaviour
from amulet_map_editor.programs.edit.api.behaviour.block_selection_behaviour import RenderBoxChangeEvent
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

class SetBlocks(wx.Panel, DefaultOperationUI):

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


        self.options = self._load_options({})
        self._block_define = BlockDefine(
            self,
            self.world.translation_manager,
            wx.VERTICAL,
            force_blockstate=False,
            # platform="universal",
            namespace='minecraft',
            *(self.options.get("fill_block_options", []) or [self.world.level_wrapper.platform]),
            show_pick_block=False
        )
        self.options_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.bot_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self._sizer.Add(self.options_sizer, 1, wx.TOP | wx.LEFT, 0)
        self._sizer.Add(self.bot_sizer, 0, wx.BOTTOM | wx.LEFT, 0)
        self._sizer.Add(self._block_define, 25, wx.EXPAND | wx.LEFT | wx.RIGHT, 0)

        brush_option = ["Circle", "90° Square", "Square"]

        self.options = wx.RadioBox(self, label='Brush Type', choices=brush_option)

        self.options_sizer.Add(self.options)
        self.l_int_size = wx.StaticText(self, label=" Size: ")
        self.l_int_y = wx.StaticText(self, label=" Y: ")
        self.l_int_x = wx.StaticText(self, label=" X: ")
        self.l_int_z = wx.StaticText(self, label=" Z: ")
        self.int_size = wx.SpinCtrl(self, initial=4)
        self.int_y = wx.SpinCtrl(self, initial=4)
        self.int_x = wx.SpinCtrl(self, initial=4)
        self.int_z = wx.SpinCtrl(self, initial=4)



        self.bot_sizer.Add(self.l_int_size)
        self.bot_sizer.Add(self.int_size)
        self.bot_sizer.Add(self.l_int_y)
        self.bot_sizer.Add(self.int_y)
        self.bot_sizer.Add(self.l_int_x)
        self.bot_sizer.Add(self.int_x)
        self.bot_sizer.Add(self.l_int_z)
        self.bot_sizer.Add(self.int_z)
        self.bot_sizer.Fit(self)
        self.location_current = []
        self.location_last = [0]
        self._block_define.Fit()
        self.click = False
        self.toggle = False
        self.point_evt = []
        self.location_last = self.point_evt
        self.no_need_to_wait = True
        self.event_cnt = 0



        self.Layout()
        self.Thaw()


    @property
    def wx_add_options(self) -> Tuple[int, ...]:

        return (0,)

    def _cls(self):
        print("\033c\033[3J", end='')

    def sphere_gen(self, xx,yy,zz):

        circle_size = self.int_size.GetValue()
        diff = circle_size - 1
        area = {}
        outer = circle_size ** 2
        inner_diff = diff ** 2
        xx = (xx + xx+1) >> 1
        yy = (yy+1 + yy+2) >> 1
        zz = (zz + zz+1) >> 1

        for y in range(self.int_y.GetValue() + 1):
            yyy = y ** 2 -1
            for z in range(self.int_z.GetValue() + 1):
                zzz = z ** 2 -1
                for x in range(self.int_x.GetValue() + 1):
                    xxx = x ** 2 -1
                    overall = yyy + zzz + xxxx
                    sel_box = None
                    if overall <= outer:
                        if overall > inner_diff:
                            sel_box = "Yes"
                    if sel_box is not None:
                        area[(xx - x, yy + y, zz - z)] = sel_box
                        area[(xx - x, yy - y, zz + z)] = sel_box
                        area[(xx - x, yy - y, zz - z)] = sel_box
                        area[(xx + x, yy + y, zz + z)] = sel_box
                        area[(xx + x, yy + y, zz - z)] = sel_box
                        area[(xx + x, yy - y, zz + z)] = sel_box
                        area[(xx + x, yy - y, zz - z)] = sel_box
                        area[(xx - x, yy + y, zz + z)] = sel_box

        for (x, y, z), sel_box in points.items():
                yield SelectionBox((x-1, y-1, z-1),(x, y, z))

    def cusotome_brush(self, xx,yy,zz):
        xx = (xx + xx + 1) >> 1
        yy = (yy + 1 + yy + 2) >> 1
        zz = (zz + zz + 1) >> 1

        if self.options.GetSelection() == 0:
            size = self.int_size.GetValue()
            diff = size - 1
            area = {}
            o_size = size ** 2
            inner_size = diff ** 2
        elif self.options.GetSelection() == 1:
            size = self.int_size.GetValue()
            diff = size - 1
            area = {}
            o_size = size
            inner_size = diff



        if self.options.GetSelection() < 2:
            for y in range(self.int_y.GetValue() + 1):
                if self.options.GetSelection() == 0:
                    yyy = y ** 2 - 1
                elif self.options.GetSelection() == 1:
                    yyy = y
                for z in range(self.int_z.GetValue() + 1):
                    if self.options.GetSelection() == 0:
                        zzz = z ** 2 - 1
                    elif self.options.GetSelection() == 1:
                        zzz = z
                    for x in range(self.int_x.GetValue() + 1):
                        if self.options.GetSelection() == 0:
                            xxx = x ** 2 - 1
                        elif self.options.GetSelection() == 1:
                            xxx = x
                        sel_box = None
                        overall = yyy + xxx + zzz
                        # if self.options.GetSelection() == 2:
                        #     if overall < o_size:
                        #         sel_box = "Yes"
                        # else:

                        if overall >= inner_size:
                            if overall <= o_size:
                                sel_box = "Yes"

                        if sel_box is not None:
                            area[(xx - x, yy + y, zz - z)] = sel_box
                            area[(xx - x, yy - y, zz + z)] = sel_box
                            area[(xx - x, yy - y, zz - z)] = sel_box
                            area[(xx + x, yy + y, zz + z)] = sel_box
                            area[(xx + x, yy + y, zz - z)] = sel_box
                            area[(xx + x, yy - y, zz + z)] = sel_box
                            area[(xx + x, yy - y, zz - z)] = sel_box
                            area[(xx - x, yy + y, zz + z)] = sel_box
        else:
            xx = (xx + xx + 1) >> 1
            yy = (yy + 1 + yy + 2) >> 1
            zz = (zz + zz + 1) >> 1
            size = self.int_size.GetValue()
            diff = size - 1
            area = {}
            o_size = size
            inner_size = diff
            for y in range(self.int_y.GetValue() + 1):
                yyy = y
                for z in range(self.int_z.GetValue() + 1):
                    zzz = z
                    for x in range(self.int_x.GetValue() + 1):
                        xxx = x
                        sel_box = None
                        overall = yyy + xxx + zzz
                        if yyy > inner_size:
                            sel_box = "Yes"
                        if zzz > inner_size:
                            sel_box = "Yes"
                        if xxx > inner_size:
                            sel_box = "Yes"

                        if sel_box is not None:
                            area[(xx - x, yy + y, zz - z)] = sel_box
                            area[(xx - x, yy - y, zz + z)] = sel_box
                            area[(xx - x, yy - y, zz - z)] = sel_box
                            area[(xx + x, yy + y, zz + z)] = sel_box
                            area[(xx + x, yy + y, zz - z)] = sel_box
                            area[(xx + x, yy - y, zz + z)] = sel_box
                            area[(xx + x, yy - y, zz - z)] = sel_box
                            area[(xx - x, yy + y, zz + z)] = sel_box
        for (x, y, z), sel_box in area.items():
            if sel_box:
                yield SelectionBox((x - 1, y - 1, z - 1), (x, y, z))


    def _on_pointer_change(self, evt: PointChangeEvent):
        if self._is_enabled or self.click:
            x, y, z = evt.point
            sg = SelectionGroup
            if self.point_evt != (x, y, z):
                self.location_last = (x, y, z)
                selboxs = self.cusotome_brush(x, y, z)
                sg = SelectionGroup(selboxs)
                merge = sg.merge_boxes()
                self.canvas.selection.set_selection_group(merge)
            evt.Skip()
        evt.Skip()
    def _refresh_chunk(self, dimension, world, x, z):
        cx, cz = block_coords_to_chunk_coords(x, z)
        if self.world.has_chunk(cx, cz, dimension):
            chunk = self.world.get_chunk(cx, cz, dimension)
            chunk.changed = True

    def mouse_click(self, event):
        blocks = self.canvas.selection.selection_group.merge_boxes().blocks
        if self.location_current != self.location_last:
            self.location_current = self.location_last
            newblock = self._block_define.block
            newEntity = self._block_define.block_entity
            platform = self.world.level_wrapper.platform
            world_version = self.world.level_wrapper.version
            for xx,yy,zz in blocks:
                self.world.set_version_block(int(xx), int(yy), int(zz), self.canvas.dimension,
                                             (platform, world_version),
                                             newblock, newEntity)
                self.canvas.renderer.render_world.rebuild_changed()
                self._refresh_chunk(self.canvas.dimension, self.world, yy, zz)
        event.Skip()
    def mouse_tog_on(self, event):
        self.mouse_click(event)
        self.timer.Start(5)
        event.Skip()

    def mouse_tog_off(self, event):
        if self.timer.IsRunning():
            self.timer.Stop()
            self.canvas.run_operation(lambda: self._refresh_chunk(self.canvas.dimension,
                                                              self.world, self.location_last[0],
                                                              self.location_last[2]))
        event.Skip()

    def bind_events(self):
        super().bind_events()
        self.timer = wx.Timer(self.canvas)
        self.canvas.Bind(wx.EVT_LEFT_DOWN, self.mouse_tog_on)
        self.canvas.Bind(wx.EVT_LEFT_UP, self.mouse_tog_off)
        self.canvas.Bind(wx.EVT_TIMER, self.mouse_click, self.timer)
        self._curs = PointerBehaviour(self.canvas)
        self._selection.bind_events()
        self._curs.bind_events()
        self.canvas.Bind(EVT_POINT_CHANGE, self._on_pointer_change)

    def location(self) -> PointCoordinates:
        return self._location.value

    def _gsel(self, _):
        for box in self.canvas.selection.selection_group.selection_boxes:
            newl = ""

            # if self._mode_description.GetValue() != "":
            #     newl = "\n"
            # print(str(box.min_z) +","+ str(box.min_y) +","+str(box.min_z)+","+str(box.max_x)+","+str(box.max_y)+","+str(box.max_z))
            # self._mode_description.SetValue(self._mode_description.GetValue()+newl+str(box.min_x) +","+ str(box.min_y) +","+str(box.min_z)+","+str(box.max_x)+","+str(box.max_y)+","+str(box.max_z))

    # def _getc(self):
    #
    #     # print(str(self.canvas.selection.selection_group.selection_boxes).replace("(SelectionBox((","").replace(")),)","")
    #     #       .replace("(","").replace(")","").replace(" ",""))
    #     newl = ""
    #     # if self._mode_description.GetValue() != "":
    #     #     newl = "\n"
    #     # self._mode_description.SetValue(self._mode_description.GetValue()+ newl + str(self.canvas.selection.selection_group.selection_boxes).replace("(SelectionBox((","").replace(")),)","")
    #     #       .replace("(","").replace(")","").replace(" ","") )
    #
    # def _sel(self, _):
    #     pass
    #     # self._selection = StaticSelectionBehaviour(self.canvas)
    #     # self._curs = PointerBehaviour(self.canvas)
    #     # self._selection.bind_events()
    #     # self._curs.bind_events()
    #     # self.canvas.Bind(EVT_POINT_CHANGE, self._on_pointer_change)
    #     # self.canvas.Bind(EVT_INPUT_PRESS, self._on_input_press)
    #     # self.click = True
    #     # self._is_enabled = True
    #     # self._moving = True
    #     # self._on_pointer_change


    def test(self):
        for x,z in world.level_wrapper.all_chunk_coords(dimension):
            chunk = world.get_chunk(x, z, dimension)
            sourceChunk = sourceWorld.get_chunk(x, z, dimension)
            chunk.biomes = sourceChunk.biomes.convert_to_3d()
            chunk.changed = True
        world.save()



    def _on_input_press(self, evt: InputPressEvent):
        if self.click == True:
            self._getc()
        # if evt.action_id == ACT_BOX_CLICK:
        #
        #     if self._is_enabled == True:
        #         self._moving = not self._moving
        #         self._is_enabled = False
        #         return
        #     if self._is_enabled == False:
        #         self._is_enabled = True
        #         return
        #     if self._moving:
        #         self.canvas.renderer.fake_levels.active_transform = ()
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

export = dict(name="Multi Block Shape Paster v1.00", operation=SetBlocks) #By PremiereHell
