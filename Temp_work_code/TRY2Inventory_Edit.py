import wx
from typing import TYPE_CHECKING, Tuple
from amulet_map_editor.programs.edit.api.operations import DefaultOperationUI
import amulet_nbt
from amulet_nbt import *
from amulet import *
import minecraft_model_reader
import os
import os.path
from os import path
model_path = os.path.abspath(minecraft_model_reader.__file__)

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
        self.Holder = wx.BoxSizer(wx.VERTICAL)
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



        self.apply = wx.Button(self, size=(50, 30),label="Apply")
        self.apply.Bind(wx.EVT_BUTTON, self.savePosData)
        self.getSet = wx.Button(self, size=(120, 20), label="Get Current Position")
        self.getSet.Bind(wx.EVT_BUTTON, self.getsetCurrentPos)

        self.achieve = wx.Button(self, size=(160, 20), label="Re-enable achievements")
        self.achieve.Bind(wx.EVT_BUTTON, self.loadData)

        self.listRadio = {
            "Survival": 5,
            "Creative": 1
        }
        self.gm_mode = wx.RadioBox(self, label='Both Do NOT disable achievements', choices=list(self.listRadio.keys()))
        player = []
        self.slots = []

        for x in self.world.players.all_player_ids():
            if "server_" in x:
                player.append("player_"+x)
            if "~" in x:
                player.append(x)


        self.slotList = wx.ListBox(self, size=(65, 95), choices=self.slots)
        self.slotList.Bind(wx.EVT_LISTBOX, self.playerGetSlot)

        self.playerlist = wx.ListBox(self, size=(340, 95), choices=player)
        self.playerlist.SetSelection(0)
        self.playerlistrun(None)
        self.playerlist.Bind(wx.EVT_LISTBOX, self.playerlistrun)

        self._sizer.Add(self.infoRe, 0, wx.LEFT, 10)
        self._sizer.Add(self.achieve, 0, wx.LEFT, 20)
        self._sizer.Add(self.info, 0, wx.LEFT, 10)
        self._sizer.Add(self.playerlist, 0, wx.LEFT, 10)
        self._sizer.Add(self.slotList, 0, wx.LEFT, 10)
        self._sizer.Add(self.Holder)
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
        enS = pl.encode("utf-8")
        player = self.world.level_wrapper._level_manager._db.get(enS)
        data = amulet_nbt.load(player, little_endian=True)
        return data

    def playerlistrun(self, _):
        player = self.playerlist.GetString(self.playerlist.GetSelection())
        pdata = self.getPlayerData(player)
        slots = []
        for x in pdata.get("Inventory"):
            slots.append("Slot: "+str(x.get('Slot')).replace('b',''))
        self.slotList.SetItems(slots)
        X,Y,Z = pdata.get("Pos")
        facing,looking = pdata.get("Rotation")
        self.X.SetValue(str(X))
        self.Y.SetValue(str(Y))
        self.Z.SetValue(str(Z))
        self.facing.SetValue(str(facing))
        self.looking.SetValue(str(looking))
        self.dim.SetSelection(pdata.get("DimensionId"))
    def SetSlotDisPlayBigText(self, L,T,t):
        self.label = wx.StaticText(self, size=(80, 20))
        self.label.SetLabel(L + ": ")
        self.text = wx.TextCtrl(
            self, id=888,style=wx.TE_MULTILINE | wx.TE_BESTWRAP, size=(200, 60),name=L+t,
        )
        self.text.SetValue(T)

        self.gridd = wx.GridBagSizer(0, 0)
        self.gridd.Add(self.label, pos=(0, 1), span=(0, 0), flag=wx.EXPAND | wx.ALL, border=0)
        self.gridd.Add(self.text, pos=(0, 2), span=(0, 0), flag=wx.EXPAND | wx.ALL, border=0)
        self.Holder.Add(self.gridd)

    def SetSlotDisPlayTXL(self, L,T,t):

        self.text = wx.TextCtrl(
            self, id=888,style=wx.TE_LEFT | wx.TE_BESTWRAP, size=(200, 20),name=L+t,
        )
        self.text.SetValue(T)

        self.gridd = wx.GridBagSizer( 0,0)


        if 'Name' in L:
            try:

                n = T.split(":")
                if 'spawn_egg' in n[1]:
                    splitegg = n[1].replace(" ","").split("_spawn_")
                    n2 = splitegg[1] +"_"+ splitegg[0]
                #     n[1] = 'spawn_egg'
                #     n2 = 'spawn_egg_overlay'
                #     img2 = str(model_path)[
                #            :-11] + r"api\resource_pack\java\resource_packs\java_vanilla\assets\minecraft\textures\item" + "\\" + \
                #            n2 + ".png"
                # print(str(model_path)[
                #       :-11] + r"api\resource_pack\java\resource_packs\java_vanilla\assets\minecraft\textures\item" + "\\" +
                #       n[1] + ".png")
                # img = str(model_path)[
                #       :-11] + r"api\resource_pack\java\resource_packs\java_vanilla\assets\minecraft\textures\item" + "\\" + \
                #       n[1] + ".png"
                    img = r"C:\Users\DJ\Desktop\tttt\IMAGE TEST\block Imgs\items" + "\\" + \
                      n2 + ".png"
                    print(img)
                    print(path.isfile(img))

                if path.isfile(img):
                    self.label = wx.StaticText(self, size=(71, 20))
                    self.label.SetLabel(L + ": ")
                    self.gridd.Add(self.label, pos=(0, 1), span=(0, 0), flag=wx.EXPAND | wx.ALL, border=1)
                    self.img = wx.Image(img, wx.BITMAP_TYPE_PNG)


                # # wx.StaticBitmap(self.img,)
                #     buffer = self.img.GetData()
                #     # buffer2 = self.img2.GetData()
                #     alf = self.img.GetAlphaBuffer()
                #     for x in range(0,len(buffer),3):
                #         if buffer[x] > 0:
                #             buffer[x] = 0
                #         if buffer[x+1] > 0:
                #             buffer[x+1] = 0
                #         if buffer[x + 2] > 0:
                #             buffer[x+2] = 255
                #
                #         print(buffer[x+2])
                #     for x in range(0, len(buffer2), 3):
                #         if buffer2[x] > 0:
                #             buffer[x] = 0
                #         if buffer2[x + 1] > 0:
                #             buffer[x + 1] = 255
                #         if buffer2[x + 2] > 0:
                #             buffer[x + 2] = 255
                #
                #     self.img.SetDataBuffer(buffer)
                #     print(alf)
                #    self.img.SetAlphaBuffer(alf)

                    self.gridd.Add(wx.StaticBitmap(self, bitmap=self.img.ConvertToBitmap()),pos = (0,2), span = (0,0), flag = wx.EXPAND|wx.ALL, border = 1)

                    self.gridd.Fit(self)
                else:
                    self.label = wx.StaticText(self, size=(80, 20))
                    self.label.SetLabel(L + ": ")
                    self.gridd.Add(self.label, pos=(0, 1), span=(0, 0), flag=wx.EXPAND | wx.ALL, border=1)

                    print("not file")
            except:

                print("Not Found", n[1] , ".png")
        else:
            self.label = wx.StaticText(self, size=(80, 20))
            self.label.SetLabel(L + ": ")
            self.gridd.Add(self.label, pos=(0, 1), span=(0, 0), flag=wx.EXPAND | wx.ALL, border=1)
        self.gridd.Add(self.text, pos=(0, 3), span=(0, 0), flag=wx.EXPAND | wx.ALL, border=1)
        self.Holder.Add(self.gridd)
    def SetSlotDisPlayLabel(self, L):
        self.label = wx.StaticText(self, id=888, name=L)
        self.label.SetLabel(L + ": ")
        self.gridd = wx.GridBagSizer(0, 0)
        self.gridd.Add(self.label, pos=(0, 1), span=(0, 0), flag=wx.EXPAND | wx.ALL, border=0)
        self.Holder.Add(self.gridd)

    def playerGetSlot(self, _):
        player = self.playerlist.GetString(self.playerlist.GetSelection())
        pdata = self.getPlayerData(player)
        slot = self.slotList.GetSelection()
        inv = pdata.get("Inventory")
        dicInv = dict(inv[slot])
        cnt = self.Holder.GetChildren()
        for x in range(0, len(cnt)):
                self.Holder.Hide(x)
        self.Holder.Clear()

        for d in dicInv.keys():
            if d == "Block":
                self.SetSlotDisPlayBigText(d,str(dicInv.get(d)),"ttttt")
            if d != "Block":
                if d != "tag":
                    print("2")
                    self.SetSlotDisPlayTXL(d,str(dicInv.get(d)),"tttt")
            if d == "tag":
                print("3")
                self.SetSlotDisPlayLabel("tag: ")
                tags = dicInv.get(d)
                print(tags)
                for tag in dict(tags):
                    print(tag)
                    print(tags)
                    print(len(tags))
                    print("44444")
                    if type(tags.get(tag)) is TAG_List:
                        tc = tags.get(tag)
                        for tagC in tc:
                            print(tagC,"CCCCCCC")
                            for tagD in tagC:
                                self.SetSlotDisPlayTXL(tagC + ": ", tagD,"ttt")

                    if type(tags.get(tag)) is TAG_Compound:
                        tc = tags.get(tag)
                        for tagC in tc:
                            if type(tagC) is TAG_List:
                                self.SetSlotDisPlayLabel(tag)
                                for X in tagC:
                                        for tagD in X:
                                            self.SetSlotDisPlayTXL(X +":_",tadD,"tt")
                            else:
                                self.SetSlotDisPlayTXL(tagC, str(tc.get(tagC)),"t")

                    else:
                        self.SetSlotDisPlayTXL(tag,str(tags.get(tag)),"-t")

        self.SaveIT = wx.Button(self, size=(60, 35), label="SaveIT")
        self.SaveIT.Bind(wx.EVT_BUTTON, self.getSaveSLOTData)
        self.Holder.Add(self.SaveIT)
        self.Holder.Fit(self)
        self._sizer.Fit(self)
        self.Layout()


    def getSaveSLOTData(self, _):
        txtCtrls = [widget for widget in self.GetChildren() if isinstance(widget, wx.TextCtrl)]
        LabCtrls = [widget for widget in self.GetChildren() if isinstance(widget, wx.StaticText)]
        print(str(model_path)[:-11]+r"api\resource_pack\java\resource_packs\java_vanilla\assets\minecraft\textures\item")
        tagConvert = {}
        tagConvert["tag"] = {}
        for x,l in zip(txtCtrls, LabCtrls):
         #   print(x.GetId())
            if str(x.GetId()) == str(888):
                print(x.GetName(),": ", x.GetValue()[-1])

                if l.GetLabel() != 'tag:':
                    tagConvert[x.GetName()] = x.GetValue()
                # else:
                #     tagConvert["tag"][x.GetName()] =

        # for x,l in zip(txtCtrls, LabCtrls):
        #     if x.GetId == 888:
        #         print(x.GetName(),x.GetValue())
        #     if l.GetLabel() != 'tag:':
        #         if x.GetId == 888:
        #             print(l.GetLabel(),x.GetValue())
        print(tagConvert)


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
        print(dim[self.canvas.dimension])
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

    def saveData(self, data):
        with open(self.world.level_path + "\\" + "level.dat", "wb") as f:
            f.write(data)
            wx.MessageBox("Achievements are Re-enable",
                          "INFO", wx.OK | wx.ICON_INFORMATION)

    def loadData(self, _):
        with open(self.world.level_path + "\\" + "level.dat", "rb") as f:
            s = f.read()
        data1 = s.replace(b'hasBeenLoadedInCreative\x01', b'hasBeenLoadedInCreative\x00')
        data2 = data1.replace(b'commandsEnabled\x01', b'commandsEnabled\x00')
        data3 = data2.replace(b'GameType\x01', b'GameType\x00')
        self.saveData(data3)
    pass


export = dict(name="#a!!Inventory Edit V1.2", operation=SetPlayer)  # by PremiereHell
