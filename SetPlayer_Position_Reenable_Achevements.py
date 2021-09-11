import wx
from typing import TYPE_CHECKING, Tuple
from amulet_map_editor.programs.edit.api.operations import DefaultOperationUI
import amulet_nbt
from amulet_nbt import *
from amulet import *

class SetPlayer(wx.Panel, DefaultOperationUI):

    def __init__(
            self,
            parent: wx.Window,
            canvas: "EditCanvas",
            world: "BaseLevel",
            options_path: str,

    ):

        platform = world.level_wrapper.platform
        world_version = world.level_wrapper.version

        wx.Panel.__init__(self, parent)
        DefaultOperationUI.__init__(self, parent, canvas, world, options_path)
        self.Freeze()

        self._sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self._sizer)
        self.info = wx.StaticText(self, wx.LEFT)
        self.info.SetLabel("Select player:")
        self.infoRe = wx.StaticText(self, wx.LEFT)
        self.infoRe.SetLabel("Remove any Behavior Packs!")
        self.infoRai = wx.StaticText(self, wx.LEFT)
        self.infoRai.SetLabel(".. Personal GameMode?")
        self.XL = wx.StaticText(self, wx.LEFT)
        self.XL.SetLabel("X:")
        self.YL = wx.StaticText(self, wx.LEFT)
        self.YL.SetLabel("Y:")
        self.ZL = wx.StaticText(self, wx.LEFT)
        self.ZL.SetLabel("Z:")
        self.dimL = wx.StaticText(self, wx.LEFT)
        self.dimL.SetLabel(" 0 = Overworld\n 1 = Nether\n 2 = End")
        self.X = wx.TextCtrl(
            self, style=wx.TE_LEFT | wx.TE_BESTWRAP, size=(90, 20),
        )
        self.Y = wx.TextCtrl(
            self, style=wx.TE_LEFT | wx.TE_BESTWRAP, size=(90, 20),
        )
        self.Z= wx.TextCtrl(
            self, style=wx.TE_LEFT | wx.TE_BESTWRAP, size=(90, 20),
        )
        self.dim = wx.TextCtrl(
            self, style=wx.TE_LEFT | wx.TE_BESTWRAP, size=(90, 20),
        )


        self.apply = wx.Button(self, size=(40, 20),label="Apply")
        self.apply.Bind(wx.EVT_BUTTON, self.savePosData)
        self.achieve = wx.Button(self, size=(160, 20), label="Re-enable achievements")
        self.achieve.Bind(wx.EVT_BUTTON, self.loadData)

        self.listRadio = {
            "Survival": 5,
            "Creative": 1
        }
        self.gm_mode = wx.RadioBox(self, label='Both Do NOT disable achievements', choices=list(self.listRadio.keys()))
        player = []

        for x in self.world.players.all_player_ids():
            player.append(x)

        self.playerlist = wx.ListBox(self, size=(160, 95), choices=player)
        self.playerlist.Bind(wx.EVT_LISTBOX, self.playerlistrun)

        self._sizer.Add(self.infoRe, 0, wx.LEFT, 10)
        self._sizer.Add(self.achieve, 0, wx.LEFT, 20)
        self._sizer.Add(self.info, 0, wx.LEFT, 10)
        self._sizer.Add(self.playerlist, 0, wx.LEFT, 10)

        self._sizer.Add(self.XL, 0, wx.LEFT, 20)
        self._sizer.Add(self.X,0,wx.LEFT,20)
        self._sizer.Add(self.YL, 0, wx.LEFT, 20)
        self._sizer.Add(self.Y, 0, wx.LEFT, 20)
        self._sizer.Add(self.ZL, 0, wx.LEFT, 20)
        self._sizer.Add(self.Z, 0, wx.LEFT, 20)
        self._sizer.Add(self.dimL, 0, wx.LEFT, 20)
        self._sizer.Add(self.dim, 0, wx.LEFT, 20)
        self._sizer.Add(self.infoRai, 0, wx.LEFT, 20)
        self._sizer.Add(self.gm_mode, 0, wx.LEFT, 20)
        self._sizer.Add(self.apply, 0, wx.LEFT, 10)
        self._sizer.Fit(self)

        self.Layout()
        self.Thaw()

    @property
    def wx_add_options(self) -> Tuple[int, ...]:
        return (0,)

    def getPlayerData(self, pl):
        enS = pl.encode("utf-8")
        player = self.world.level_wrapper._level_manager._db.get(enS)
        data = amulet_nbt.load(player, little_endian=True)
        data2 = []
        currentIMAPS = []
        dic = {}

        return data

    def playerlistrun(self, _):
        player = self.playerlist.GetString(self.playerlist.GetSelection())
        pdata = self.getPlayerData(player)
        X,Y,Z = pdata.get("Pos")
        self.X.SetValue(str(X))
        self.Y.SetValue(str(Y))
        self.Z.SetValue(str(Z))
        self.dim.SetValue(str(pdata.get("DimensionId")))

    def savePosData(self, _):
        player = self.playerlist.GetString(self.playerlist.GetSelection())
        pdata = self.getPlayerData(player)
        mode = self.gm_mode.GetString(self.gm_mode.GetSelection())


        pdata["PlayerGameMode"] = TAG_Int(int(self.listRadio.get(mode)))
        pdata["DimensionId"] = TAG_Int(int(self.dim.GetValue()))
        pdata['Pos'] = TAG_List()
        pdata['Pos'].append(TAG_Float(float(self.X.GetValue().replace("f",""))))
        pdata['Pos'].append(TAG_Float(float(self.Y.GetValue().replace("f",""))))
        pdata['Pos'].append(TAG_Float(float(self.Z.GetValue().replace("f",""))))
        save = pdata.save_to(compressed=False, little_endian=True)
        self.world.level_wrapper._level_manager._db.put(player.encode("utf-8"), save)

    def saveData(self, data):
        with open(self.world.level_path + "\\" + "level.dat", "wb") as f:
            f.write(data)

    def loadData(self, _):
        with open(self.world.level_path + "\\" + "level.dat", "rb") as f:
            s = f.read()
        data1 = s.replace(b'hasBeenLoadedInCreative\x01', b'hasBeenLoadedInCreative\x00')
        data2 = data1.replace(b'commandsEnabled\x01', b'commandsEnabled\x00')
        data3 = data2.replace(b'GameType\x01', b'GameType\x00')
        #print(data2)
        self.saveData(data3)
    pass


export = dict(name="SetPlayer Position/Re-enable achievements V1.0", operation=SetPlayer)  # by PreimereHell
