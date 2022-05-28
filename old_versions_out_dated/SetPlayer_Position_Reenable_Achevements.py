import amulet.utils.format_utils
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

        self.platform = world.level_wrapper.platform
        world_version = world.level_wrapper.version


        wx.Panel.__init__(self, parent)
        DefaultOperationUI.__init__(self, parent, canvas, world, options_path)
        self.Freeze()
        self.data = None
        self._sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self._sizer)
        self.info = wx.StaticText(self, wx.LEFT)
        self.info.SetLabel("Select player:")
        if self.platform == "bedrock":
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
        self.facingL = wx.StaticText(self, wx.LEFT)
        self.facingL.SetLabel("Facing:")
        self.lookingL = wx.StaticText(self, wx.LEFT)
        self.lookingL.SetLabel("Looking:")
        self.X = wx.TextCtrl(
            self, style=wx.TE_LEFT | wx.TE_BESTWRAP, size=(150, 20),
        )
        self.Y = wx.TextCtrl(
            self, style=wx.TE_LEFT | wx.TE_BESTWRAP, size=(150, 20),
        )
        self.Z= wx.TextCtrl(
            self, style=wx.TE_LEFT | wx.TE_BESTWRAP, size=(150, 20),
        )
        self.facing = wx.TextCtrl(
            self, style=wx.TE_LEFT | wx.TE_BESTWRAP, size=(150, 20),
        )
        self.looking = wx.TextCtrl(
            self, style=wx.TE_LEFT | wx.TE_BESTWRAP, size=(150, 20),
        )
        self.dimDict = {
            "Overworld": 0,
            "Nether": 1,
            "End":2
        }
        self.dim = wx.RadioBox(self, size=(200,50),label='Select Dimension', choices=list(self.dimDict.keys()))
        self.apply = wx.Button(self, size=(50, 30), label="Apply")
        if self.platform == "bedrock":
            self.apply.Bind(wx.EVT_BUTTON, self.savePosData)
        else:
            self.apply.Bind(wx.EVT_BUTTON, self.savePosDataJava)
        self.getSet = wx.Button(self, size=(120, 20), label="Get Current Position")
        self.getSet.Bind(wx.EVT_BUTTON, self.getsetCurrentPos)
        self.tpUser = wx.CheckBox(self, size=(150, 20), label="Enable TP for select")
        self.fcords = wx.CheckBox(self, size=(150, 20), label="lock Cord Values")

        if self.platform == "bedrock":
            self.achieve = wx.Button(self, size=(160, 20), label="Re-enable achievements")
            self.achieve.Bind(wx.EVT_BUTTON, self.loadData)

        self.listRadio = {
            "Survival": 0,
            "Creative": 1
        }
        if self.platform == "bedrock":
            self.gm_mode = wx.RadioBox(self, label='Both Do NOT disable achievements', choices=list(self.listRadio.keys()))
        player = []
        if self.platform == "bedrock":
            for x in self.world.players.all_player_ids():
                if "server_" in x or "~" in x:
                    if "server_" in x:
                        player.append("player_"+x)
                    else:
                        player.append(x)
        else:
            for x in self.world.players.all_player_ids():
                player.append(x)


        self.playerlist = wx.ListBox(self, size=(160, 95), choices=player)
        self.playerlist.SetSelection(0)
        self.playerlistrun(None)
        self.playerlist.Bind(wx.EVT_LISTBOX, self.playerlistrun)

        if self.platform == "bedrock":
            self._sizer.Add(self.infoRe, 0, wx.LEFT, 10)
            self._sizer.Add(self.achieve, 0, wx.LEFT, 20)
        self._sizer.Add(self.info, 0, wx.LEFT, 10)
        self._sizer.Add(self.playerlist, 0, wx.LEFT, 10)


        self._sizer.Add(self.tpUser, 0, wx.LEFT, 20)

        self._sizer.Add(self.fcords, 0, wx.LEFT, 20)
        self._sizer.Add(self.getSet, 0, wx.LEFT, 40)
        self.Grid = wx.GridSizer(5,2,0,0)
        self.Grid.Add(self.XL, 0, wx.LEFT, 5)
        self.Grid.Add(self.X,0,wx.LEFT,-60)
        self.Grid.Add(self.YL, 0, wx.LEFT, 5)
        self.Grid.Add(self.Y, 0, wx.LEFT, -60)
        self.Grid.Add(self.ZL, 0, wx.LEFT, 5)
        self.Grid.Add(self.Z, 0, wx.LEFT, -60)

        self.Grid.Add(self.facingL, 0, wx.LEFT, 5)
        self.Grid.Add(self.facing, 0, wx.LEFT, -50)
        self.Grid.Add(self.lookingL, 0, wx.LEFT, 5)
        self.Grid.Add(self.looking, 0, wx.LEFT, -50)

        self._sizer.Add(self.Grid)
        self.Grid.Fit(self)

        self._sizer.Add(self.dim, 0, wx.LEFT, 0)

        if self.platform == "bedrock":
            self._sizer.Add(self.infoRai, 0, wx.LEFT, 0)
            self._sizer.Add(self.gm_mode, 0, wx.LEFT, 0)

        self._sizer.Add(self.apply, 0, wx.LEFT, 160)
        self._sizer.Fit(self)

        self.Layout()
        self.Thaw()

    @property
    def wx_add_options(self) -> Tuple[int, ...]:
        return (0,)

    def getPlayerData(self, pl):
        data = "None"
        if self.platform == "bedrock":

            try:
                enS = pl.encode("utf-8")

                player = self.world.level_wrapper._level_manager._db.get(enS)
                data = amulet_nbt.load(player, little_endian=True)
            except:
                data = "None"
        else:

            try:
                path = self.world.level_path + "\\level.dat"
                if pl != "~local_player":
                     path = self.world.level_path + "\\playerdata\\" + pl + ".dat"
                with open(path, "rb") as f:
                    r = f.read()
                if pl != "~local_player":
                    data = amulet_nbt.load(r, compressed=True, little_endian=False)
                else:
                    self.data = amulet_nbt.load(r, compressed=True, little_endian=False)
                    data = self.data["Data"]["Player"]

            except:
                data = "None"

        return data

    def playerlistrun(self, _):

        if self.platform == "bedrock":
            player = self.playerlist.GetString(self.playerlist.GetSelection())
            pdata = self.getPlayerData(player)
            if pdata != "None":
                X,Y,Z = pdata.get("Pos")
                facing,looking = pdata.get("Rotation")

                if self.tpUser.GetValue() == True:
                    self.canvas.camera.location = [float(str(X).replace('f','')),float(str(Y).replace('f','')),float(str(Z).replace('f',''))]
                    self.canvas.camera.rotation = [float(str(facing).replace('f','')),float(str(looking).replace('f',''))]
                if self.fcords.GetValue() == True:
                    return
                self.X.SetValue(str(X))
                self.Y.SetValue(str(Y))
                self.Z.SetValue(str(Z))
                self.facing.SetValue(str(facing))
                self.looking.SetValue(str(looking))
                self.dim.SetSelection(pdata.get("DimensionId"))
        else:
            player = self.playerlist.GetString(self.playerlist.GetSelection())
            pdata = self.getPlayerData(player)
            if pdata != "None":
                X, Y, Z = pdata.get("Pos")
                facing, looking = pdata.get("Rotation")

                if self.tpUser.GetValue() == True:
                    self.canvas.camera.location = [float(str(X).replace('d', '')), float(str(Y).replace('d', '')),
                                               float(str(Z).replace('d', ''))]
                    self.canvas.camera.rotation = [float(str(facing).replace('f', '')),
                                               float(str(looking).replace('f', ''))]
                if self.fcords.GetValue() == True:
                    return
                self.X.SetValue(str(X))
                self.Y.SetValue(str(Y))
                self.Z.SetValue(str(Z))
                self.facing.SetValue(str(facing))
                self.looking.SetValue(str(looking))
                dim = {
                    'minecraft:overworld': 0,
                    'minecraft:the_nether': 1,
                    'minecraft:the_end': 2
                }
                self.canvas.dimension = str(pdata.get("Dimension"))
                self.dim.SetSelection(dim[str(pdata.get("Dimension"))])

    def getsetCurrentPos(self, _):

        X, Y, Z = self.canvas.camera.location
        facing,looking = self.canvas.camera.rotation
        self.X.SetValue(str(X))
        self.Y.SetValue(str(Y))
        self.Z.SetValue(str(Z))
        self.facing.SetValue(str(facing))
        self.looking.SetValue(str(looking))
        dim = {
            'minecraft:overworld':0,
            'minecraft:the_nether':1,
            'minecraft:the_end':2
        }
        self.dim.SetSelection(dim[self.canvas.dimension])

    def savePosData(self, _):
        player = self.playerlist.GetString(self.playerlist.GetSelection())
        pdata = self.getPlayerData(player)
        mode = self.gm_mode.GetString(self.gm_mode.GetSelection())
        dim = {
            0:"Over World",
            1:"Nether",
            2: "The End"
        }
        facing, looking = pdata.get("Rotation")
        if self.platform == "bedrock":
            pdata["PlayerGameMode"] = TAG_Int(int(self.listRadio.get(mode)))

        pdata["DimensionId"] = TAG_Int(int(self.dim.GetSelection()))
        pdata["Rotation"] = TAG_List()
        pdata['Rotation'].append(TAG_Float(float(self.facing.GetValue().replace("f", ""))))
        pdata['Rotation'].append(TAG_Float(float(self.looking.GetValue().replace("f", ""))))
        pdata['Pos'] = TAG_List()
        pdata['Pos'].append(TAG_Float(float(self.X.GetValue().replace("f",""))))
        pdata['Pos'].append(TAG_Float(float(self.Y.GetValue().replace("f",""))))
        pdata['Pos'].append(TAG_Float(float(self.Z.GetValue().replace("f",""))))
        save = pdata.save_to(compressed=False, little_endian=True)
        self.world.level_wrapper._level_manager._db.put(player.encode("utf-8"), save)
        wx.MessageBox(player +"\nPersonal Mode: "+ mode +"\nLocation is set to\n"+dim.get(int(self.dim.GetSelection()))+" \nX: "
                      +self.X.GetValue().replace("f","")+"\nY: "+ self.Y.GetValue().replace("f","") +"\nZ: "+self.Z.GetValue().replace("f","") +
                      "\nFacing: " + self.facing.GetValue().replace("f", "") +
                      "\nLooking: " + self.looking.GetValue().replace("f", "") +
                      "\nNOTE: You MUST CLOSE This world Before Opening in MineCraft",
                      "INFO", wx.OK | wx.ICON_INFORMATION)

    def savePosDataJava(self, _):
        player = self.playerlist.GetString(self.playerlist.GetSelection())
        pdata = self.getPlayerData(player)
        dim = {
            0:'minecraft:overworld',
            1:'minecraft:the_nether',
            2:'minecraft:the_end'
        }
        facing, looking = pdata.get("Rotation")


        pdata["Dimension"] = TAG_String(dim[int(self.dim.GetSelection())])
        pdata["Rotation"] = TAG_List()
        pdata['Rotation'].append(TAG_Float(float(self.facing.GetValue().replace("f", ""))))
        pdata['Rotation'].append(TAG_Float(float(self.looking.GetValue().replace("f", ""))))
        pdata['Pos'] = TAG_List()
        pdata['Pos'].append(TAG_Double(float(self.X.GetValue().replace("d", ""))))
        pdata['Pos'].append(TAG_Double(float(self.Y.GetValue().replace("d", ""))))
        pdata['Pos'].append(TAG_Double(float(self.Z.GetValue().replace("d", ""))))
        if player != "~local_player":
            print("ok")
            save = pdata.save_to(compressed=True, little_endian=False)
            with open(self.world.level_path + "\\playerdata\\" + player + ".dat", "wb") as f:
                f.write(save)
        else:
            print("ok")
            self.data["Data"]["Player"] = pdata

            print(self.data)
            save = self.data.save_to(compressed=True, little_endian=False)

            with open(self.world.level_path + "\\level.dat", "wb") as f:
                 f.write(save)


        wx.MessageBox(player + "\nLocation is set to\n" + dim.get(
            int(self.dim.GetSelection())) + " \nX: "
                      + self.X.GetValue().replace("f", "") + "\nY: " + self.Y.GetValue().replace("f","") + "\nZ: " + self.Z.GetValue().replace(
            "f", "") +
                      "\nFacing: " + self.facing.GetValue().replace("f", "") +
                      "\nLooking: " + self.looking.GetValue().replace("f", "") +
                      "\nNOTE: You MUST CLOSE This world Before Opening in MineCraft",
                      "INFO", wx.OK | wx.ICON_INFORMATION)

    def saveData(self, head, data):
        with open(self.world.level_path + "\\" + "level.dat", "wb") as f:
            f.write(head + data)
            wx.MessageBox("Achievements are Re-enable",
                          "INFO", wx.OK | wx.ICON_INFORMATION)

    def loadData(self, _):
        if self.platform != "bedrock":
            wx.MessageBox("Java is not  suported",
                          "INFO", wx.OK | wx.ICON_INFORMATION)
            return
        with open(self.world.level_path + "\\" + "level.dat", "rb") as f:
            s = f.read()
        print(s)
        nbt = amulet_nbt.load(s[8:], compressed=False,little_endian=True)
        head = s[0:8]

        #print(head + saveit)

        # data1 = s.replace(b'hasBeenLoadedInCreative\x01', b'hasBeenLoadedInCreative\x00')
        # data2 = data1.replace(b'commandsEnabled\x01', b'commandsEnabled\x00')
        # data3 = data2.replace(b'GameType\x01', b'GameType\x00')
        nbt['hasBeenLoadedInCreative'] = TAG_Byte(0)
        nbt['commandsEnabled'] = TAG_Byte(0)
        nbt['GameType'] = TAG_Int(0)

        saveit = nbt.save_to(compressed=False, little_endian=True)
        self.saveData(head, saveit)
    pass


export = dict(name="SetPlayer Position/Re-enable achievements V1.601", operation=SetPlayer)  # by PremiereHell
