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

        self._sizer.Add(self.playerlist, 0, wx.LEFT, 10)
        self._sizer.Add(self.slotList, 0, wx.LEFT, 10)

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
        #self.playerGetSlot(None)

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

                    img = r"C:\Users\DJ\Desktop\tttt\IMAGE TEST\block Imgs\items" + "\\" + \
                      n2 + ".png"
                    print(img)
                    print(path.isfile(img))

                if path.isfile(img):
                    self.label = wx.StaticText(self, size=(71, 20))
                    self.label.SetLabel(L + ": ")
                    self.gridd.Add(self.label, pos=(0, 1), span=(0, 0), flag=wx.EXPAND | wx.ALL, border=1)
                    self.img = wx.Image(img, wx.BITMAP_TYPE_PNG)
                    self.gridd.Add(wx.StaticBitmap(self, bitmap=self.img.ConvertToBitmap()),pos = (0,2), span = (0,0), flag = wx.EXPAND|wx.ALL, border = 1)

                    self.gridd.Fit(self)
                else:
                    self.label = wx.StaticText(self, size=(80, 20))
                    self.label.SetLabel(L + ": ")
                    self.gridd.Add(self.label, pos=(0, 1), span=(0, 0), flag=wx.EXPAND | wx.ALL, border=1)
                    self.gridd.Fit(self)
                    print("not file")
            except:
                self.label = wx.StaticText(self, size=(80, 20))
                self.label.SetLabel(L + ": ")
                self.gridd.Add(self.label, pos=(0, 1), span=(0, 0), flag=wx.EXPAND | wx.ALL, border=1)
                self.gridd.Fit(self)
                print("Not Found", n[0] , ".png")
        else:
            self.label = wx.StaticText(self, size=(80, 20))
            self.label.SetLabel(L + ": ")
            self.gridd.Add(self.label, pos=(0, 1), span=(0, 0), flag=wx.EXPAND | wx.ALL, border=1)
            self.gridd.Fit(self)
        self.gridd.Add(self.text, pos=(0, 3), span=(0, 0), flag=wx.EXPAND | wx.ALL, border=1)

        self.gridd.Fit(self)
        self.Holder.Add(self.gridd)
        self._sizer.Add(self.Holder)
        self._sizer.Fit(self)
        self._sizer.Layout()
        print(L, "LLL---")
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
        print("saaa")
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









    pass


export = dict(name="!#111#A#a!!INVENTORY-EDIT", operation=SetPlayer)  # by PremiereHell
