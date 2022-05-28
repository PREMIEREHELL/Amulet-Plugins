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
import datetime
from pathlib import Path

# from amulet.level.formats.leveldb_world import  format

if TYPE_CHECKING:
    from amulet.api.level import BaseLevel
    from amulet_map_editor.programs.edit.api.canvas import EditCanvas


def saveHistoy(data):
    f = open(os.path.join(os.path.dirname(__file__), "history.txt"), "a", encoding="utf-8")
    f.write(data)
    f.close()


historyFile = Path(os.path.join(os.path.dirname(__file__), "history.txt"))
if historyFile.is_file():
    print("Making Histoy.txt fileReady")
else:
    d = "History of Get and Set~~Your History Will Be here\n"
    saveHistoy(d)


def LoadHistory():
    with open(os.path.join(os.path.dirname(__file__), "history.txt"), "r", encoding="utf-8") as f:
        list2 = []
        historyTime = []
        historyDatas = []
        for item in f:
            list2.append(item.replace('\n', ''))
        for lz in list2:
            lb = lz.split("~~")
            historyTime.append(lb[0])
            historyDatas.append(lb[1])
    return historyTime, historyDatas


TT, DD = LoadHistory()
res = {TT[i]: DD[i] for i in range(len(TT))}
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

        self._sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self._sizer)

        options = self._load_options({})
        top_sizer = wx.BoxSizer(wx.VERTICAL)
        side_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self._sizer.Add(side_sizer, 1, wx.TOP | wx.LEFT, 0)
        self._sizer.Add(top_sizer, 0, wx.TOP | wx.LEFT, 290)
        # choicebox for operation mode selection.
        self._mode = wx.Choice(self, choices=list(operation_modes.keys()))
        self._mode.SetSelection(1)
        self._history = wx.Choice(self, choices=list(res.keys()))
        self._history.SetSelection(0)
        self._history.Bind(wx.EVT_CHOICE, self.onFocus)
        side_sizer.Add(self._mode, 0, wx.TOP | wx.LEFT, 5)
        side_sizer.Add(self._history, 0, wx.TOP | wx.LEFT, 5)
        self._run_button = wx.Button(self, label="Get Selected\n Block SNBT")
        self._run_button.Bind(wx.EVT_BUTTON, self._run2_operation)
        side_sizer.Add(self._run_button, 0, wx.TOP | wx.LEFT, 5)

        self._run_button = wx.Button(self, label="Set Selected\n Block SNBT")
        self._run_button.Bind(wx.EVT_BUTTON, self._run_operation)
        side_sizer.Add(self._run_button, 10, wx.TOP | wx.LEFT, 5)

        self._mode_description = wx.TextCtrl(
            self, style=wx.TE_MULTILINE | wx.TE_BESTWRAP
        )
        self._sizer.Add(self._mode_description, 25, wx.EXPAND | wx.LEFT | wx.RIGHT, 0)

        self._mode_description.Fit()

        self.Layout()
        self.Thaw()

    @property
    def wx_add_options(self) -> Tuple[int, ...]:
        return (0,)

    def _cls(self):
        print("\033c\033[3J", end='')

    def Onmsgbox(self):
        wx.MessageBox("You need to have valid snbt data in the Text field.\n This field cant be Empty.",
                      "Something Went Wrong", wx.OK | wx.ICON_INFORMATION)

    def onFocus(self, evt):
        setdata = res[self._history.GetString(self._history.GetSelection())]
        self._mode_description.SetValue(setdata)

    def _run_operation(self, _):

        block_platform = "bedrock"
        block_version = (1, 17, 0)
        data = self._mode_description.GetValue()
        if data == "":
            self.Onmsgbox()
            return
        data = str(data).replace('NBTFile({','NBTFile("":{')
        print(data)
        dataSplit = data.split("|")
        dataPartBlock = dataSplit[0]
        print(dataSplit[0])
        dataPartEntity = dataSplit[1]
        NBT = None
        direction = 2
        Snbt = from_snbt("[]")
        posBlocknameStart = dataPartBlock.find(":") + 1
        if "[" in dataPartBlock:
            posBlocknameEnd = dataPartBlock.find("[")
        else:
            posBlocknameEnd = None
        posBlockDataStart = dataPartBlock.find("[") + 1
        posBlockDataEnd = dataPartBlock.find("]")
        blockName = dataPartBlock[posBlocknameStart:posBlocknameEnd]
        fixedBlockFormat = dataPartBlock[posBlockDataStart:posBlockDataEnd]
        if "=" in dataPartBlock:
            fixedBlockFormat = dataPartBlock[posBlockDataStart:posBlockDataEnd].replace("=", ":")  # .replace(",","],[")
        if "[" in data:
            Snbt = from_snbt("{" + fixedBlockFormat + "}")

            block = Block("minecraft", blockName, dict(Snbt))

        else:
            Snbt = from_snbt("{" + fixedBlockFormat + "}")
            block = Block("minecraft", blockName, dict(Snbt))
        if "BlockEntity" in data:
            entity = data.find('NBTFile') + 11
            NBT = from_snbt(data[entity:])

            blockEntity = BlockEntity("minecraft", blockName.replace('_', '').capitalize(), 0, 0, 0, NBTFile(NBT))

        else:
            blockEntity = None
        historyData = '{:%Y-%b-%d %H:%M:%S}'.format(datetime.datetime.now()) + "~~" + str(block) + "|" + str(
            blockEntity).replace('\n\n\n', '') + "\n"
        saveHistoy(historyData)
        hs = historyData.split("~~")
        res.update({hs[0]: hs[1]})
        self._history.Clear()
        self._history.Append(list(res.keys()))
        self._history.SetSelection(0)
        for (box) in (self.canvas.selection.selection_group):
            pos = px, py, pz = box.min_x, box.min_y, box.min_z
            self.world.set_version_block(px, py, pz, self.canvas.dimension, (block_platform, block_version), block,
                                         blockEntity)
            self.canvas.run_operation(lambda: self._refresh_chunk(self.canvas.dimension, self.world, px, pz))

    def _refresh_chunk(self, dimension, world, x, z):
        cx, cz = block_coords_to_chunk_coords(x, z)
        chunk = world.get_chunk(cx, cz, dimension)
        chunk.changed = True

    def _run2_operation(self, _):

        block_platform = operation_modes[self._mode.GetString(self._mode.GetSelection())]

        block_version = (1, 17, 0)
        for (box) in (self.canvas.selection.selection_group):

            pos = x, y, z = box.min_x, box.min_y, box.min_z
            #pmax = x, y, z = box.min_x, box.min_y, box.min_z

            # for rx in range (box.min_x, box.max_x):
            # for ry in range(box.min_y, box.max_y):
            # for rz in range(box.min_z, box.max_z):

            block, blockEntity = self.world.get_version_block(x, y, z, self.canvas.dimension,
                                                              (block_platform, block_version))
            bbb = self.world.get_block(x, y, z, self.canvas.dimension)
            #print(blockEntity)
            #print(blockEntity)
            SpData = str(blockEntity).split("\"\":")


            #self._mode_description.SetValue(str(block) + "|" + str(blockEntity).replace('\n\n\n', ''))
            try:
                headerData = amulet_nbt.from_snbt(SpData[0])
                blockEData = amulet_nbt.from_snbt(SpData[1])
                self._mode_description.SetValue( str(block) + "|\n" + SpData[0] + blockEData.to_snbt(2))
            except:
                self._mode_description.SetValue(str(block) + "|" + str(blockEntity) )
            historyData = '{:%Y-%b-%d %H:%M:%S}'.format(datetime.datetime.now()) + "~~" + str(block) + "|" + str(
                blockEntity).replace('\n\n\n', '') + "\n"
            saveHistoy(historyData)
            hs = historyData.split("~~")
            res.update({hs[0]: hs[1]})
            self._history.Clear()
            self._history.Append(list(res.keys()))
            self._history.SetSelection(0)

    pass


# simple export options.
export = dict(name="A Block editor, v1.1", operation=SetBlock) #By PremiereHell