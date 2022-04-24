
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
from amulet.libs.leveldb.leveldb import LevelDB
import amulet_nbt
from amulet.level.formats import mcstructure
import datetime
from pathlib import Path
#from amulet.level.formats.leveldb_world import  format

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
        self.storage_key = amulet_nbt.TAG_Compound()

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
        self._structlist = wx.Choice(self, choices=self._run_get_slist())
        self._structlist.SetSelection(0)
        self._structlist.Bind(wx.EVT_CHOICE,self.onFocus)
        side_sizer.Add(self._mode, 0,  wx.TOP | wx.LEFT , 5)
        side_sizer.Add(self._structlist, 0,  wx.TOP | wx.LEFT, 9)


        self._run_getSData_button = wx.Button(self, label="Get Player DATA")
        self._run_getSData_button.Bind(wx.EVT_BUTTON, self._run_get_sdata)
        side_sizer.Add(self._run_getSData_button, 25, wx.BOTTOM | wx.LEFT, 20)
        self._run_text = wx.TextCtrl(
            self, style=wx.TE_LEFT  |  wx.TE_BESTWRAP, size=(290,20)
        )
        bottom_sizer.Add(self._run_text,0 , wx.LEFT, 0)
        self._run_text.SetValue("PLAYER UUID")
        self._run_setSData_button = wx.Button(self, label="Save Player  \n Data to world ")
        self._run_setSData_button.Bind(wx.EVT_BUTTON, self._run_set_sdata)
        bottom_sizer.Add(self._run_setSData_button, 0,   wx.TOP | wx.LEFT, 0)
        self._run_setSData_button.Fit()


        self._run_setEData_button = wx.Button(self, label="Export Player NBT")
        self._run_setEData_button.Bind(wx.EVT_BUTTON, self._run_export)
        bottom_sizer.Add(self._run_setEData_button, 0, wx.LEFT, 0)

        self._run_setImData_button = wx.Button(self, label="Import Player NBT")
        self._run_setImData_button.Bind(wx.EVT_BUTTON, self._run_import)
        bottom_sizer.Add(self._run_setImData_button, 0, wx.LEFT, 0)


        self._run_Del_button = wx.Button(self, label="DELETE Player \n from World")
        self._run_Del_button.Bind(wx.EVT_BUTTON, self._run_Del)
        bottom_sizer.Add(self._run_Del_button, 0, wx.LEFT, 0)



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
        setdata = self._run_text.GetValue()#self._structlist.GetString(self._structlist.GetSelection())
        enS = setdata.encode("utf-8")

        player = self.world.level_wrapper._level_manager._db.get(enS)
        print(player)

        data = amulet_nbt.load(player, little_endian=True)
        self.storage_key = data.pop('internalComponents')
        data2 = []
        self._mode_description.SetValue(data.to_snbt(2))
        # back to bytes
        data2 = data.save_to(compressed=False, little_endian=True)


        # for p in player:
        #     print(p)

    def Onmsgbox(self, caption, message):  # message
        wx.MessageBox(message, caption, wx.OK | wx.ICON_INFORMATION)

    def _run_set_sdata(self, _):

        theKey = self._run_text.GetValue().encode("utf-8")
        print(theKey)
        data = self._mode_description.GetValue()
        test_b_arr = amulet_nbt.TAG_Byte_Array()
        print(test_b_arr.to_snbt())
        try:
            nbt = from_snbt(data.replace("[B;B]", "[B;]"))
            nbtf = NBTFile(nbt)
        except Exception as e:
            self.Onmsgbox("Snbt Error", f"Check the syntax? error was : {e}")
        try:
            if self.storage_key.get('EntityStorageKeyComponent'):
                nbtf['internalComponents'] = self.storage_key
        except:
            pass
        # back to bytes

            print(data2)
        try:
            data2 = nbtf.save_to(compressed=False, little_endian=True)
            self.world.level_wrapper._level_manager._db.put(theKey, data2)
            self.Onmsgbox("Saved", f"All went well")
        except Exception as e:
            self.Onmsgbox("Error", f"Something went wrong: {e}")
        self._structlist.Clear()
        self._structlist.Append(self._run_get_slist())
        self._structlist.SetSelection(0)
        # for p in player:
        # print(p)
    def _run_export(self, _):  # b'structuretemplate_mystructure:test'

        theKey = self._run_text.GetValue().encode("utf-8")
        print(theKey)
        data = self._mode_description.GetValue()
        nbt = from_snbt(data.replace('NBTFile("":', ''))
        nbtf = NBTFile(nbt)
        # back to bytes
        data2 = nbtf.save_to(compressed=False, little_endian=True)
        with wx.FileDialog(self, "Open NBT file", wildcard="NBT files (*.NBT)|*.NBT",
                           style=wx.FD_SAVE) as fileDialog:

            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return
            else:
                pathname = fileDialog.GetPath()
                print(pathname)

        f = open(pathname, "wb")
        f.write(data2)
        print(data2)
       # self.world.level_wrapper._level_manager._db.put(theKey, data2)
        # for p in player:
        # print(p)
    def _run_import(self, _):
        data2 = []

        # back to bytes
       # data2 = nbtf.save_to(compressed=False, little_endian=True)
        with wx.FileDialog(self, "Open NBT file", wildcard="NBT files (*.NBT)|*.NBT",
                           style=wx.FD_OPEN) as fileDialog:

            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return
            else:
                pathname = fileDialog.GetPath()
                print(pathname)

        with open(pathname, "rb") as f:
            bytes_read = f.read()
        for b in bytes_read:
            data2.append(b)

        thebytes = bytes(data2)
        print(thebytes)


        #nbt = from_snbt(data.replace('NBTFile("":', ''))
       # nbtf = NBTFile(nbt)
        data = amulet_nbt.load(thebytes, little_endian=True)
        self._mode_description.SetValue(str(data))

        # back to bytes
        #data2 = data.save_to(compressed=False, little_endian=True)


    # def _run_load(self, _):
    #
    #     with wx.FileDialog(self, "Open McStructure file", wildcard="mcstructure files (*.mcstructure)|*.mcstructure",
    #                        style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as fileDialog:
    #         if fileDialog.ShowModal() == wx.ID_CANCEL:
    #             return
    #         pathname = fileDialog.GetPath()
    #     data = amulet_nbt.load(pathname,compressed=False,little_endian=True)
    #     self._mode_description.SetValue(str(data))

    def _run_Del(self, _):

        theKey = self._run_text.GetValue().encode("utf-8")

        wxx = wx.MessageBox("You are going to deleted \n " + str(theKey),
                      "This can't be undone Are you Sure?", wx.OK | wx.CANCEL | wx.ICON_INFORMATION)
        if wxx == int(16):
            return
        self.world.level_wrapper._level_manager._db.delete(theKey)
        wxx = wx.MessageBox("PLAYER "+ str(theKey) +" DELETED",
                            "THis "+ str(theKey) +"has been deleted \n ", wx.OK | wx.ICON_INFORMATION)
        self._structlist.Clear()
        self._structlist.Append(self._run_get_slist())
        self._structlist.SetSelection(0)

    def _run_get_slist(self):
        world = self.world.level_wrapper._level_manager._db.keys()
        currentStructure = []
        currentStructure.append("Players In this World")
        for w in world:
            if b'\xff' not in w:
                if b'\x00' not in w:
                    if b'player' in w:
                        currentStructure.append(w)
        return currentStructure
    pass


#simple export options.
export = dict(name="Edit / Export/Import Player Inventory", operation=SetBlock)
