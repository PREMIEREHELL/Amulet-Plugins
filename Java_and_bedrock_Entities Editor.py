import math
from typing import TYPE_CHECKING, Tuple

import amulet.level
import amulet_nbt
from amulet.api.wrapper import Interface, EntityIDType, EntityCoordType

import numpy
import wx
import ast
import os
import string
import os.path
import re
import zlib
import gzip
from os import path
from ctypes import windll
from distutils.version import LooseVersion, StrictVersion
from amulet.api.data_types import Dimension
from amulet.api.selection import SelectionGroup
from amulet.api.selection import SelectionBox
from amulet_nbt import *
from amulet.utils import world_utils
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
from amulet.level.formats.anvil_world.region import AnvilRegion
from amulet_map_editor.api.wx.ui.base_select import BaseSelect
import datetime
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

class EditEntities(wx.Panel, DefaultOperationUI):

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
        self.EntyData = []
        self._sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self._sizer)
        self.nbt_data = NBTFile()
        options = self._load_options({})
        top_sizer = wx.BoxSizer(wx.VERTICAL)
        side_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self._sizer.Add(side_sizer, 1, wx.TOP | wx.LEFT, 0)
        self._sizer.Add(top_sizer, 0, wx.TOP | wx.LEFT, 290)

        self.ui_entitie_choice_list = wx.Choice(self, choices=['This Will List all The Entities within the chunk'])
        self.ui_entitie_choice_list.SetSelection(0)
        self.ui_entitie_choice_list.Bind(wx.EVT_CHOICE, self.onFocus)
       
        side_sizer.Add(self.ui_entitie_choice_list, 0, wx.TOP | wx.LEFT, 5)
        self._get_button = wx.Button(self, label="Get Entities")
        self._get_button.Bind(wx.EVT_BUTTON, self._load_entitie_data)
        side_sizer.Add(self._get_button, 0, wx.TOP | wx.LEFT, 5)

        self._set_button = wx.Button(self, label="Set Entities")
        self._set_button.Bind(wx.EVT_BUTTON, self._save_data_to_world)
        side_sizer.Add(self._set_button, 10, wx.TOP | wx.LEFT, 5)
        self.sel = wx.Button(self, label="Select")
        self.sel.Bind(wx.EVT_BUTTON, self._sel)
        side_sizer.Add(self.sel, 10, wx.TOP | wx.LEFT, 5)
        self._snbt_edit_data = wx.TextCtrl(
            self, style=wx.TE_MULTILINE | wx.TE_BESTWRAP
        )
        self._sizer.Add(self._snbt_edit_data, 25, wx.EXPAND | wx.LEFT | wx.RIGHT, 0)

        self._snbt_edit_data.Fit()

        self.Layout()
        self.Thaw()

    @property
    def wx_add_options(self) -> Tuple[int, ...]:
        return (0,)

    def _cls(self):
        print("\033c\033[3J", end='')

    def ConFbox(self, caption, message): # message, yes Know
        r = wx.MessageDialog(
            self, message,
            caption,
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION
        ).ShowModal()
        if r != wx.ID_YES:
            return True
        else:
            return False

    def Onmsgbox(self, caption, message): # message
        wx.MessageBox(message, caption , wx.OK | wx.ICON_INFORMATION)

    def onFocus(self, evt): #ui_entitie_choice_list event control
        setdata = self.EntyData[self.ui_entitie_choice_list.GetSelection()]
        self._snbt_edit_data.SetValue(setdata.to_snbt(3))

    def _sel(self, _):  # pointer event control
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

    def _on_pointer_change(self, evt: PointChangeEvent):  # pointer event
        if self._is_enabled:
            self.canvas.renderer.fake_levels.active_transform = (
                evt.point
            )
            x, y, z = evt.point
            a, b, c = 1, 1, 1  # self.abc
            sg = SelectionGroup(SelectionBox((x, y, z), (x + a, y + b, z + c)))
            self.canvas.selection.set_selection_group(sg)

        evt.Skip()

    def _on_input_press(self, evt: InputPressEvent): # pointer event
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

    def _save_data_to_world(self, _):
        responce = self.ConFbox("!! IMPORTANT !!",  "This Pluging: May cause a conflict with other chunk operation."
                                                   "\n  DID YOU BACKUP YOUR WORLD ? "
                                                    "\n Continue?")
        # maybe should change this or check if the same as loaded entities
        cx, cz = block_coords_to_chunk_coords(self.canvas.selection.selection_group.min_x,
                                              self.canvas.selection.selection_group.min_z)
        if responce == True:
            return
        try:
            if "bedrock" in self.world.level_wrapper.platform:  # Check if bedrock

                newBytes = b''
                selection = self.ui_entitie_choice_list.GetSelection()
                newData = self._snbt_edit_data.GetValue()
                self.EntyData[selection] = from_snbt(newData)
                for TNewData in self.EntyData:
                    NewRawB = b''
                    NewRawB = NBTFile(from_snbt(TNewData.to_snbt())).save_to(compressed=False, little_endian=True)
                    newBytes += NewRawB
                chunk = self.world.level_wrapper.get_raw_chunk_data(cx, cz, self.canvas.dimension)
                chunk[b'2'] = newBytes
                self.world.level_wrapper.put_raw_chunk_data(cx, cz, chunk, self.canvas.dimension)
                #self.world.save()
                self.Onmsgbox("Operation complete", "The operation has completed without error:\n Save world to see the changes")
            else:  # else its java
                newData = self._snbt_edit_data.GetValue()  # get new data
                data = from_snbt(newData)  # convert to nbt
                if self.version_path == "region":
                    self.nbt_data_full["Level"]['Entities'][self.ui_entitie_choice_list.GetSelection()] = data  # overwrite current data
                else:
                    self.nbt_data_full['Entities'][self.ui_entitie_choice_list.GetSelection()] = data
                self.Entities_region.put_chunk_data(cx % 32, cz % 32, self.nbt_data_full)  # put data back where it goes
                self.Entities_region.save()  # save file operation
                #self.world.save()  # save world
                self.Onmsgbox("Operation complete", "The operation has completed without error:\n Save world to see the changes")
        except amulet_nbt.amulet_cy_nbt.SNBTParseError as e:
            self.Onmsgbox("SNBT Syntax Error: ", str(e))


    def _refresh_chunk(self, dimension, world, x, z):
        cx, cz = block_coords_to_chunk_coords(x, z)
        chunk = world.get_chunk(cx, cz, dimension)
        chunk.changed = True

    def _load_entitie_data(self, _):
        if self.canvas.selection.selection_group.selection_boxes == ():
            self.Onmsgbox("No Selection","Need to select one chunk or one block to convert to chunk cords")
            return 
        self.EntyData.clear() # make sure to start fresh
        self.ui_entitie_choice_list.Clear()
        self.ui_entitie_choice_list.Hide()
        lstOfE = [] # holds the list of of choices
        #need the chunk from the selection 
        cx, cz = block_coords_to_chunk_coords(self.canvas.selection.selection_group.min_x, self.canvas.selection.selection_group.min_z)
        # raw chunk
        if "bedrock" in self.world.level_wrapper.platform:  # bedrock
            try:
                chunk = self.world.level_wrapper.get_raw_chunk_data(cx, cz, self.canvas.dimension)
            except amulet.api.errors.ChunkDoesNotExist:
                self.Onmsgbox("Chuck Error", "Empty chunk selected")
                return
                # find the start position of Entitiy data
            posStart = [air.start() for air in re.finditer(b'\n\x00\x00', chunk[b'2'])]

            for s in posStart:  # grab the data from the chunks from the found offsets
                snb = amulet_nbt.load(chunk[b'2'][s:], little_endian=True) # let amulet find the end offset
                print(snb)
                if snb.get('identifier') != None: #make sure it not empty
                    self.EntyData.append(snb)
            for enty in self.EntyData:  # add data to ui entity list
                lstOfE.append(str(enty['identifier']) + " x(" + str(enty['Pos'][0]).split('.')[0] + ") y(" +
                              str(enty['Pos'][1]).split('.')[0] + ") z(" +
                              str(enty['Pos'][2]).split('.')[0] + ")")
                
        else:  # java

            rx, rz = world_utils.chunk_coords_to_region_coords(cx, cz)  # need region cords for file
            path = self.world.level_wrapper.path  # need path for file
            self.version_path = ""
            if self.world.level_wrapper.version >= 2730 :
                self.version_path = "entities"
            else:
                self.version_path = "region"
            print(self.version_path)
            entitiesPath = os.path.join(path, self.version_path ,
                                        "r." + str(rx) + "." + str(rz) + ".mca")  # full path for file
            self.Entities_region = AnvilRegion(entitiesPath)  # create instance for region data
            # the " % 32 " calulates the location of the chunk in the header,
            try:
                self.nbt_data_full = self.Entities_region.get_chunk_data(cx % 32, cz % 32)
                if self.version_path == "region":
                    self.nbt_data = self.nbt_data_full["Level"]['Entities']
                else:
                    self.nbt_data = self.nbt_data_full['Entities']
                if len(self.nbt_data) == 0:
                    self.Onmsgbox("No Entities", "No Entities were found in this chunk or the chunk does not exist")
                    return
            except amulet.api.errors.ChunkDoesNotExist:
                self.Onmsgbox("No Entities", "No Entities were found in this chunk or the chunk does not exist")
                return
           
            for nbt in self.nbt_data:  # loop over entities
                self.EntyData.append(nbt)
                lstOfE.append(str(nbt['id'] + " x(" + str(nbt['Pos'][0]).split(".")[
                    0] + ") y("  # add ids and position data to list
                                  + str(nbt['Pos'][1]).split(".")[0] + ") z(" + str(nbt['Pos'][2]).split(".")[
                                      0]) + ")")

        # fix up the UI needs work, adds data to ui


        self.ui_entitie_choice_list = wx.Choice(self, choices=lstOfE)
        self.ui_entitie_choice_list.Bind(wx.EVT_CHOICE, self.onFocus)
        self.ui_entitie_choice_list.SetSelection(0)
        self.ui_entitie_choice_list.Fit()
        
    pass


# simple export options.
export = dict(name="A Chunk Entities Editor v1.03 ", operation=EditEntities) #By PremiereHell
