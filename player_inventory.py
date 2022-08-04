import collections

import wx
import os
from amulet_map_editor.programs.edit.api.operations import DefaultOperationUI
import amulet_nbt
class Inventory(wx.Panel, DefaultOperationUI):

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
        self.font = wx.Font(11, wx.FONTFAMILY_ROMAN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        top_sizer = wx.BoxSizer(wx.VERTICAL)
        side_sizer = wx.BoxSizer(wx.HORIZONTAL)
        bottom_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self._sizer.Add(side_sizer, 1, wx.TOP | wx.LEFT, 0)
        self._sizer.Add(top_sizer)
        self._sizer.Add(bottom_sizer, 1, wx.BOTTOM | wx.LEFT,2)
        self.items = wx.Choice(self, choices=[])
        self.items.Bind(wx.EVT_CHOICE, self.on_item_focus)



        self.info_list = wx.StaticText(self, label="Select A Player")
        top_sizer.Add(self.info_list, 0, wx.LEFT, 140)



        self.blank = wx.StaticText(self, label="")
        self.save_player_data_button = wx.Button(self, label="Save Player")
        self.save_player_snbt_button = wx.Button(self, label="Save File")
        self.remove_player_btn = wx.Button(self, label="Remove Player")
        self.load_player_snbt = wx.Button(self, label="Load File")


        self.save_player_data_button.Bind(wx.EVT_BUTTON, self.save_player_data)
        self.save_player_snbt_button.Bind(wx.EVT_BUTTON, self.export_snbt)
        self.load_player_snbt.Bind(wx.EVT_BUTTON, self.import_snbt)
        self.remove_player_btn.Bind(wx.EVT_BUTTON, self.remove_player)

        self.the_grid = wx.GridSizer(3,3,5,-10)


        self.the_grid.Add(self.save_player_snbt_button)
        self.the_grid.Add(self.items, 0, wx.LEFT, -10)
        self.the_grid.Add(self.remove_player_btn, 0, wx.LEFT, 10)
        self.the_grid.Add(self.load_player_snbt)
        self.the_grid.Add(self.blank)
        self.the_grid.Add(self.save_player_data_button, 0, wx.LEFT, 10)
        bottom_sizer.Add(self.the_grid)
        self.snbt_text_data = wx.TextCtrl(
            self, style=wx.TE_MULTILINE | wx.TE_BESTWRAP
        )
        self._sizer.Add(self.snbt_text_data, 25, wx.EXPAND | wx.TOP | wx.RIGHT, 0)
        if self.world.level_wrapper.platform == "bedrock":
            self._structlist = wx.Choice(self, choices=self._run_get_slist())
            self._structlist.Bind(wx.EVT_CHOICE, self.onFocus)
            self._structlist.SetSelection(0)
        else:
            self._structlist = wx.Choice(self, choices=[])#self._run_get_slist())
            self._structlist.Bind(wx.EVT_CHOICE, self.onFocus)
            self.java_setup()
            self._structlist.SetSelection(0)
        self.snbt_text_data.SetBackgroundColour((0, 0, 0))
        self.snbt_text_data.SetForegroundColour((0, 255, 0))
        self.snbt_text_data.SetFont(self.font)
        self.snbt_text_data.Fit()

        top_sizer.Add(self._structlist, 0, wx.LEFT, 11)
        if self.world.level_wrapper.platform == "bedrock":
            self.get_player_data()
        self.Layout()
        self.Thaw()




    def on_item_focus(self, _):
        selcted = self.items.GetStringSelection()
        if self.world.level_wrapper.platform == "bedrock":
            self.snbt_text_data.SetValue(self.nbt_dic_list[selcted].to_snbt(1))
        else:
            self.snbt_text_data.SetValue(self.nbt_dic_list[selcted])

    def onFocus(self,evt):
        if self.world.level_wrapper.platform == "bedrock":
            setdata = self._structlist.GetString(self._structlist.GetSelection())
            self.get_player_data()
        else:
            s_player = self._structlist.GetStringSelection()
            if s_player == '~local_player':
                path_to = self.world.level_wrapper.path + "/" + "level.dat"
            else:
                path_to = self.world.level_wrapper.path + "/playerdata/" + s_player + ".dat"
            with open(path_to, "rb") as dat:
                self.data_nbt = amulet_nbt.load(dat, compressed=True, little_endian=False)
                if s_player == '~local_player':
                    for k,v in self.data_nbt['Data']['Player'].items():
                        self.nbt_dic_list[k] = v.to_snbt(1)
                else:
                    for k,v in self.data_nbt.items():
                        self.nbt_dic_list[k] = v.to_snbt(1)

                self.snbt_text_data.SetValue(self.nbt_dic_list.get('Inventory'))


    def _run_set_data(self, _):
        player = self.level_db.get(b'~local_player')
        data = self.snbt_text_data.GetValue()
        nbt = from_snbt(data.replace('NBTFile("":',''))
        nbtf = NBTFile(nbt)
        data2 = nbtf.save_to(compressed=False,little_endian=True)
        self.level_db.put(b'~local_player', data2)

    def get_player_data(self):

        setdata = self._structlist.GetStringSelection()#self._structlist.GetString(self._structlist.GetSelection())
        enS = setdata.encode("utf-8")
        try:
            player = self.level_db.get(enS).replace(b'\x08\n\x00StorageKey\x08\x00',
                                                    b'\x07\n\x00StorageKey\x08\x00\x00\x00')
            self.nbt_dic_list = amulet_nbt.load(player, little_endian=True)
            self.items.SetItems(["EnderChestInventory", "Inventory"])
            self.items.SetSelection(1)
            self.snbt_text_data.SetValue(self.nbt_dic_list["Inventory"].to_snbt(1))
        except:
            self.Onmsgbox("Local Player Does exits", "Open locally In Minecraft to regenerate the player.")





    def Onmsgbox(self, caption, message):  # message
        wx.MessageBox(message, caption, wx.OK | wx.ICON_INFORMATION)

    def save_player_data(self, _):
        if self.world.level_wrapper.platform == "bedrock":
            theKey = self._structlist.GetStringSelection().encode("utf-8")
            data = self.snbt_text_data.GetValue()

            try:
                selcted = self.items.GetStringSelection()
                nbt = amulet_nbt.from_snbt(data.replace("[B;B]", "[B;]"))
                self.nbt_dic_list[selcted] = nbt
                rawdata = self.nbt_dic_list.save_to(compressed=False, little_endian=True)
                self.level_db.put(theKey, rawdata)
                self.Onmsgbox("Saved", f"All went well")
            except Exception as e:
                self.Onmsgbox("Error", f"Something went wrong: {e}")


        else:
            data = self.snbt_text_data.GetValue()
            selection = self.items.GetStringSelection()
            s_player = self._structlist.GetStringSelection()
            if s_player == '~local_player':
                self.data_nbt['Data']['Player'][selection] = amulet_nbt.from_snbt(data)
            else:
                 self.data_nbt[selection] = amulet_nbt.from_snbt(data)


            nbt_file = self.data_nbt.save_to(compressed=True, little_endian=False)

            if s_player == '~local_player':
                path_to = self.world.level_wrapper.path + "/" + "level.dat"
            else:
                path_to = self.world.level_wrapper.path + "/playerdata/" + s_player + ".dat"
            with open(path_to, "wb") as dat:
                dat.write(nbt_file)



            self.Onmsgbox("Saved", f"All went well")

    def export_snbt(self, _):
        data = self.snbt_text_data.GetValue()
        with wx.FileDialog(self, "Save SNBT file", wildcard="SNBT files (*.SNBT)|*.SNBT",
                           style=wx.FD_SAVE) as fileDialog:
            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return
            else:
                pathname = fileDialog.GetPath()
                print(pathname)
        f = open(pathname, "w")
        f.write(data)
        f.close()

    def import_snbt(self, _):
        with wx.FileDialog(self, "Open SNBT file", wildcard="SNBT files (*.SNBT)|*.SNBT",
                           style=wx.FD_OPEN) as fileDialog:
            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return
            else:
                pathname = fileDialog.GetPath()
        with open(pathname, "r") as f:
            data = f.read()
        self.snbt_text_data.SetValue(data)
        f.close()

    def remove_player(self, _):
        if self.world.level_wrapper.platform == "bedrock":
            theKey = self._structlist.GetStringSelection().encode("utf-8")
            wxx = wx.MessageBox("You are going to deleted \n " + str(theKey),
                                "This can't be undone Are you Sure?", wx.OK | wx.CANCEL | wx.ICON_INFORMATION)
            if wxx == int(16):
                return
            print(theKey,type(theKey))
            self.level_db.delete(theKey)
            wxx = wx.MessageBox("THis " + str(theKey) + "has been deleted \n  Reload plugin to see changes \n"
                                                        "Reloading in minecraft will regenerate the player",
                                "PLAYER " + str(theKey) + " DELETED", wx.OK | wx.ICON_INFORMATION)
        else:
            s_player = self._structlist.GetStringSelection()
            if s_player == '~local_player':
                print("You dont want to delete this")
                pass#path_to = self.world.level_wrapper.path + "/" + "level.dat"
            else:
                path_to = self.world.level_wrapper.path + "/playerdata/" + s_player + ".dat"
            os.remove(path_to)
        self._structlist.Clear()
        self._structlist.Append(self._run_get_slist())
        self._structlist.SetSelection(0)

    def _run_get_slist(self):
        l = []
        l.append(b'~local_player')
        for k, v in self.level_db.iterate(start=b'player_server_',
                            end=b'player_server_\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF'):
            print(k)
            l.append(k)
        return l

    def setup_data(self):
        self.nbt_dic_list = collections.defaultdict()
        self.data_nbt = amulet_nbt.NBTFile()
        if self.world.level_wrapper.platform == "bedrock":
            self.get_player_data()
            self._structlist.SetForegroundColour((0, 255, 0))
            self._structlist.SetBackgroundColour((0, 0, 0))
        else:
            s_player = self._structlist.GetStringSelection()
            if s_player == '~local_player':
                path_to = self.world.level_wrapper.path + "/" + "level.dat"
            else:
                path_to = self.world.level_wrapper.path + "/playerdata/" + s_player + ".dat"
            with open(path_to, "rb") as dat:
                self.data_nbt = amulet_nbt.load(dat, compressed=True, little_endian=False)
                if s_player == '~local_player':
                    for k,v in self.data_nbt['Data']['Player'].items():
                        self.nbt_dic_list[k] = v.to_snbt(1)
                else:
                    for k,v in self.data_nbt.items():
                        self.nbt_dic_list[k] = v.to_snbt(1)

                self.snbt_text_data.SetValue(self.nbt_dic_list.get('Inventory'))
                self.items.SetItems(["EnderItems", "Inventory"])
                self.items.SetSelection(1)

    def java_setup(self):
        players = []
        for p in self.world.players.all_player_ids():
            players.append(p)
        players.reverse()
        self._structlist.SetItems(players)
        self._structlist.SetSelection(0)
        self.setup_data()
    @property
    def level_db(self):
        level_wrapper = self.world.level_wrapper
        if hasattr(level_wrapper, "level_db"):
            return level_wrapper.level_db
        else:
            return level_wrapper._level_manager._db

export = dict(name="Players Inventory 2.01", operation=Inventory)
