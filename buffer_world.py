import collections
from amulet.utils import block_coords_to_chunk_coords
from os.path import exists
import amulet
import wx
import os
from amulet_map_editor.programs.edit.api.operations import DefaultOperationUI
from amulet_map_editor.programs.edit.api.behaviour import BlockSelectionBehaviour
import amulet_nbt
import struct
import shutil
from amulet.libs.leveldb import LevelDB
from amulet.operations.delete_chunk import delete_chunk

from amulet.utils import world_utils
from amulet.level.formats.anvil_world.region import AnvilRegion

import numpy

class Inventory(wx.Panel, DefaultOperationUI):

    def __init__(
            self,
            parent: wx.Window,
            canvas: "EditCanvas",
            world: "BaseLevel",
            options_path: str,

    ):

        self.storage_key = amulet_nbt.TAG_Compound()

        wx.Panel.__init__(self, parent)
        DefaultOperationUI.__init__(self, parent, canvas, world, options_path)
        self.Freeze()
        self.world_location = ''
        self._sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self._sizer)
        self.font = wx.Font(11, wx.FONTFAMILY_ROMAN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        top_sizer = wx.BoxSizer(wx.VERTICAL)
        self._sizer.Add(top_sizer)
        self.label_main = wx.StaticText(self, label="Setup a blank world to work with")
        self.label = wx.StaticText(self, label="Set The Range of chunks from Source Its Times 4: ")

        self.make_world_buffer = wx.Button(self, label="Build Buffer World")
        self.make_world_buffer.Bind(wx.EVT_BUTTON, self.make_world)
        self.world_load = wx.Button(self, label="Change/Add Source World Location\n"
                                                "(Make open world a buffer or changes the source world)\n"
                                                "Note: Simply adds a main_dir.txt with the source location.")
        self.world_load.Bind(wx.EVT_BUTTON, self.operation_run)
        self.keep_chunks = wx.CheckBox(self, label="Keep Previously Sourced Chunks\n"
                                                   "( uncheck to overwrite local from source )")
        self.keep_chunks.SetValue(True)
        self.the_range = wx.SpinCtrl(self, min=1, max=25)
        self.the_range.SetValue(6)
        self.source_new_data = wx.Button(self, label="Pull In Chunks")
        self.source_new_data.Bind(wx.EVT_BUTTON, self.operation_run_source)
        self.source_enty = wx.Button(self, label="Pull In All Entities")
        self.source_enty.Bind(wx.EVT_BUTTON, self.source_entities)
        self.send_enty = wx.Button(self, label="Send Entities Back")
        self.send_enty.Bind(wx.EVT_BUTTON, self.put_entities_back)

        self.source_players = wx.Button(self, label="Get All Player Data")
        self.source_players.Bind(wx.EVT_BUTTON, self.get_player_data)
        self.set_players = wx.Button(self, label="Send Back All Player Data")
        self.set_players.Bind(wx.EVT_BUTTON, self.set_player_data)

        self.save_new_data = wx.Button(self, label="Send Chunks Back")
        self.save_new_data.Bind(wx.EVT_BUTTON, self.put_data_back)

        self.del_chk = wx.Button(self, label="Delete Selected Chunks \n( Both Locations )")
        self.del_chk.Bind(wx.EVT_BUTTON, self.del_selected_chunks)

        # self.test = wx.Button(self, label="TEST")
        # self.test.Bind(wx.EVT_BUTTON, self.testselected)
        # self._sizer.Add(self.test)

        self._sizer.Add(self.label_main)
        self._sizer.Add(self.make_world_buffer)
        self._sizer.Add(self.world_load, 0 , wx.TOP, 10)

        self._sizer.Add(self.label, 0, wx.TOP, 15)
        self._sizer.Add(self.the_range, 0, wx.TOP, 5)
        self._sizer.Add(self.keep_chunks, 0, wx.TOP, 5)
        self._sizer.Add(self.source_new_data, 0 , wx.TOP, 5)
        self._sizer.Add(self.save_new_data, 0, wx.TOP, 5)




        if self.world.level_wrapper.platform == 'bedrock':
            self._sizer.Add(self.source_enty, 0, wx.TOP, 15)
            self._sizer.Add(self.send_enty, 0 , wx.TOP, 5)
        else:
            if self.world.level_wrapper.version >= 2730:
                self._sizer.Add(self.source_enty, 0, wx.TOP, 15)
                self._sizer.Add(self.send_enty, 0 , wx.TOP, 5)

            else:
                self.source_enty.Hide()
                self.send_enty.Hide()

        self._sizer.Add(self.source_players, 0 , wx.TOP, 5)
        self._sizer.Add(self.set_players, 0 , wx.TOP, 5)
        self._sizer.Add(self.del_chk, 0 , wx.TOP, 5)

        self.Layout()
        self.Thaw()
    # def testselected(self,_):
    #     chunks = [c for c in self.world.level_wrapper.all_chunk_coords(self.canvas.dimension)]#self.canvas.selection.selection_group.chunk_locations()
    #     for xx,zz in chunks:
    #         chunkkey = struct.pack('<ii', xx, zz) + self.get_dim_value_bytes()
    #         key_len = len(chunkkey)
    #         contin = False
    #         for k, v in self.level_db.iterate(start=chunkkey, end=chunkkey + b'\xff\xff'):
    #             # if len(k) > key_len + 1:
    #             #     contin = True
    #             #     break
    #             print(k, ":", k[-1])
    #             if k[-1] == 54:
    #                 print(f"Key: {k} Value: {v}")
    #
    #             # for k, v in self.level_db.iterate(start=chunkkey, end=chunkkey + b'\x39'):
    #             #     print(f"Key: {k} Value: {v}")




    def bind_events(self):
        super().bind_events()
        self._selection.bind_events()
        self._selection.enable()

    def enable(self):
        self._selection = BlockSelectionBehaviour(self.canvas)
        self._selection.enable()

    def Onmsgbox(self, caption, message):  # message
        wx.MessageBox(message, caption, wx.OK | wx.ICON_INFORMATION)

    def con_boc(self, caption="", message=""):  # message, yes Know
        r = wx.MessageDialog(
            self, message,
            caption,
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION
        ).ShowModal()
        if r != wx.ID_YES:
            return True
        else:
            return False

    def make_world(self, _):
        if self.world.level_wrapper.platform == "bedrock":
            pathlocal = os.getenv('LOCALAPPDATA')
            mc_path = ''.join([pathlocal,
                               r'/Packages/Microsoft.MinecraftUWP_8wekyb3d8bbwe/LocalState/games/com.mojang/minecraftWorlds/'])
            with wx.DirDialog(None, "Select The World folder For the would you want to buffer", mc_path,
                              wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST) as fileDialog:
                if fileDialog.ShowModal() == wx.ID_CANCEL:
                    return
                else:
                    pathname = fileDialog.GetPath()
            if self.world.level_wrapper.path == pathname:
                self.Onmsgbox("Can Not Use Buffer as Source!", "This Would break!")
                return
            the_dir = pathname.split("\\")
            pathhome = ''.join([x + '/' for x in the_dir[:-1]])
            world_buffer_f = pathhome + "buffer" + str(the_dir[-1])
            os.mkdir(world_buffer_f)
            os.mkdir(world_buffer_f + "/db")
            shutil.copy(pathname + "/level.dat", world_buffer_f + "/level.dat")
            shutil.copy(pathname + "/world_icon.jpeg", world_buffer_f + "/world_icon.jpeg")
            header, new_raw = b'', b''

            with open(world_buffer_f + "/levelname.txt", "w") as data:
                data.write("BufferLevel")

            with open(world_buffer_f + '/main_dir.txt', "w") as data:
                data.write(pathname + "/db")

            with open(world_buffer_f + "/level.dat", "rb") as data:
                the_data = data.read()
                header = the_data[:4]
                nbt_leveldat = amulet_nbt.load(the_data[8:], compressed=False, little_endian=True)
                nbt_leveldat['LevelName'] = amulet_nbt.TAG_String("BufferLevel")
                new_raw = nbt_leveldat.save_to(compressed=False, little_endian=True)
                header += struct.pack("<I", len(new_raw))

            with open(world_buffer_f + "/level.dat", "wb") as data:
                data.write(header + new_raw)

            self.raw_level = LevelDB(pathname + "/db", create_if_missing=False)
            self.new_raw_level = LevelDB(world_buffer_f + "/db", create_if_missing=True)

            player_d = self.raw_level.get(b'~local_player')
            self.new_raw_level.put(b'~local_player', player_d)
            self.raw_level.close(compact=False)
            self.new_raw_level.close(compact=False)
            folder = world_buffer_f.split("/")[-1]
            self.Onmsgbox("World is Ready to open and to pull chunks", f"Created {folder}")
        else: #java
            pathlocal = os.getenv('APPDATA')
            pathname = ''
            mc_path = ''.join([pathlocal,
                               r'/.minecraft/saves'])
            with wx.DirDialog(None, "Select The World folder For the would you want to buffer", mc_path,
                              wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST) as fileDialog:
                if fileDialog.ShowModal() == wx.ID_CANCEL:
                    return
                else:
                    pathname = fileDialog.GetPath()
            if self.world.level_wrapper.path == pathname:
                self.Onmsgbox("Can Not Use Buffer as Source!", "This Would break!")
                return

            the_dir = pathname.split("\\")
            pathhome = ''.join([x + '/' for x in the_dir[:-1]])
            world_buffer_f = pathhome + "buffer" + str(the_dir[-1])
            os.mkdir(world_buffer_f)
            os.mkdir(world_buffer_f + "/region")
            os.mkdir(world_buffer_f + "/DIM-1")
            os.mkdir(world_buffer_f + "/DIM1")
            # if self.world.level_wrapper.version >= 2730:
            #     os.mkdir(world_buffer_f + "/entities")

            shutil.copy(pathname + "/level.dat", world_buffer_f + "/level.dat")


            try:
                shutil.copy(pathname + "/icon.png", world_buffer_f + "/icon.png")
            except:
                pass
            with open(world_buffer_f + '/main_dir.txt', "w") as data:
                data.write(pathname)
            # with open(f"{world_buffer_f}/level.dat", "bw+", ) as dat:
            data = amulet_nbt.load(f"{world_buffer_f}/level.dat", compressed=True, little_endian=False)
            data["Data"]["LevelName"] = amulet_nbt.TAG_String("buffer" + str(the_dir[-1]))
            save = data.save_to(compressed=True, little_endian=False)
            with open(f"{world_buffer_f}/level.dat", "wb") as f:
                f.write(save)


    def close(self, _):
        self.raw_level.close(compact=False)

    def operation_run(self, _):

        self.world_load_data()

    def del_selected_chunks(self, _):
        if exists(self.world.level_wrapper.path + '/main_dir.txt'):
            self.world.save()
            with open(self.world.level_wrapper.path + '/main_dir.txt', "r") as d:
                self.world_location = d.read()
                d.close()
            self.raw_level = LevelDB(self.world_location, create_if_missing=False)
            the_chunks = self.canvas.selection.selection_group.chunk_locations()
            to_delete_list = []

            for xx, zz in the_chunks:
                chunkkey = struct.pack('<ii', xx, zz) + self.get_dim_value_bytes()
                key_len = len(chunkkey)
                contin = False
                for k, v in self.raw_level.iterate(start=chunkkey, end=chunkkey + b'\xff\xff'):
                    if len(k) > key_len + 1:
                        contin = True
                        break
                if contin:
                    for k, v in self.raw_level.iterate(start=chunkkey, end=chunkkey + b'\xff\xff'):
                        if key_len <= len(k) <= key_len + 3:
                            to_delete_list.append(k)

            for d in to_delete_list:
                self.raw_level.delete(d)
            self.raw_level.close(compact=False)
            self.canvas.run_operation(
                lambda: delete_chunk(
                    self.canvas.world,
                    self.canvas.dimension,
                    self.canvas.selection.selection_group,
                    False,

                ))

            self.world.unload()
            self.canvas.renderer.render_world._rebuild()

            self.Onmsgbox("Chunks Deleted", f"Deleted chunks {the_chunks}")

    def operation_run_source(self, _):

        self.source_new()
        self.world.unload()
        self.canvas.renderer.render_world._rebuild()


    def get_player_data(self, _):
        if self.world.level_wrapper.platform == 'bedrock':
            if exists(self.world.level_wrapper.path + '/main_dir.txt'):
                with open(self.world.level_wrapper.path + '/main_dir.txt', "r") as d:
                    self.world_location = d.read()

                self.raw_level = LevelDB(self.world_location, create_if_missing=False)
                player_d = self.raw_level.get(b'~local_player')
                for k, v in self.raw_level.iterate(start=b'player_server_',
                                                   end=b'player_server_\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF'):
                    self.level_db.put(k, v)

                self.level_db.put(b'~local_player', player_d)
                self.raw_level.close(compact=False)
        else: #java
            if exists(self.world.level_wrapper.path + '/main_dir.txt'):
                with open(self.world.level_wrapper.path + '/main_dir.txt', "r") as d:
                    self.world_location = d.read()
                #buffer_world = os.path.join(self.world_location, 'playerdata' )
                buffer_world = ''.join(self.world_location + "/playerdata")
                os.system(f"cp -rf \"{buffer_world}\" \"{self.world.level_wrapper.path}\"")


    def set_player_data(self, _):
        if self.world.level_wrapper.platform == 'bedrock':
            if exists(self.world.level_wrapper.path + '/main_dir.txt'):
                with open(self.world.level_wrapper.path + '/main_dir.txt', "r") as d:
                    self.world_location = d.read()
                self.raw_level = LevelDB(self.world_location, create_if_missing=False)
                player_d = self.level_db.get(b'~local_player')
                for k, v in self.level_db.iterate(start=b'player_server_',
                                                  end=b'player_server_\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF'):
                    self.raw_level.put(k, v)

                self.raw_level.put(b'~local_player', player_d)
                self.raw_level.close(compact=False)
        else:
            if exists(self.world.level_wrapper.path + '/main_dir.txt'):
                with open(self.world.level_wrapper.path + '/main_dir.txt', "r") as d:
                    self.world_location = d.read()

                buffer_world = ''.join(self.world_location)
                os.system(f"cp -rf \"{self.world.level_wrapper.path}/playerdata\" \"{buffer_world}\"")


    def world_load_data(self):


        if self.world.level_wrapper.platform == 'bedrock':
            pathname = ''
            pathlocal = os.getenv('LOCALAPPDATA')
            mc_path = ''.join([pathlocal,
                               r'/Packages/Microsoft.MinecraftUWP_8wekyb3d8bbwe/LocalState/games/com.mojang/minecraftWorlds/'])
            with wx.DirDialog(None, "Pick A SOURCE World Directory", "",
                              wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST) as fileDialog:
                if fileDialog.ShowModal() == wx.ID_CANCEL:
                    return
                else:
                    pathname = fileDialog.GetPath()

            if self.world.level_wrapper.path == pathname:
                self.Onmsgbox("Can Not Use Buffer as Source!", "This Would not work")
                return
            self.world_location = pathname + '/db'
            with open(self.world.level_wrapper.path + '/main_dir.txt', "w") as fdata:
                print(self.world_location)
                fdata.write(self.world_location)

            set_player = self.con_boc("Source World Location added ",
                                      f"Do You want Replace local player data from this world? "
                                      "\n After reloading world you will spawn in that location same"
                                      "Click No To Keep this Local players data\n"
                                      f" and to manually set location")
            if set_player:
                self.raw_level = LevelDB(pathname + '/db', create_if_missing=False)
                player_d = self.raw_level.get(b'~local_player')
                self.level_db.put(b'~local_player', player_d)
                self.raw_level.close(compact=False)
            self.Onmsgbox( f"This World can now pull data from {pathname}", "Updated")
        else:
            pathlocal = os.getenv('APPDATA')
            pathname = ''
            mc_path = ''.join([pathlocal,
                               r'/.minecraft/saves'])
            with wx.DirDialog(None, "Select The World folder For the would you want to buffer", mc_path,
                              wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST) as fileDialog:
                if fileDialog.ShowModal() == wx.ID_CANCEL:
                    return
                else:
                    pathname = fileDialog.GetPath()
            if self.world.level_wrapper.path == pathname:
                self.Onmsgbox("Can Not Use Buffer as Source!", "This Would break!")
                return

            the_dir = pathname.split("\\")
            pathhome = ''.join([x + '/' for x in the_dir[:-1]])


            with open(self.world.level_wrapper.path + '/main_dir.txt', "w") as data:
                data.write(pathname)
            self.Onmsgbox( "Updated", f"This World can now pull data from {pathname}")



    def get_dim_value_bytes(self):
        if 'minecraft:the_end' in self.canvas.dimension:
            dim = int(2).to_bytes(4, 'little', signed=True)
        elif 'minecraft:the_nether' in self.canvas.dimension:
            dim = int(1).to_bytes(4, 'little', signed=True)
        elif 'minecraft:overworld' in self.canvas.dimension:
            dim = b''  # int(0).to_bytes(4, 'little', signed=True)
        return dim

    def put_data_back(self, _):
        if exists(self.world.level_wrapper.path + '/main_dir.txt'):
            self.world.save()
            with open(self.world.level_wrapper.path + '/main_dir.txt', "r") as d:
                self.world_location = d.read()

            ###############################################################
            if self.world.level_wrapper.platform == "bedrock":
                self.raw_level = LevelDB(self.world_location, create_if_missing=False)
                the_chunks = [c for c in self.world.level_wrapper.all_chunk_coords(self.canvas.dimension)]
                for xx, zz in the_chunks:
                    chunkkey = struct.pack('<ii', xx, zz) + self.get_dim_value_bytes()
                    key_len = len(chunkkey)
                    contin = False
                    for k, v in self.raw_level.iterate(start=chunkkey, end=chunkkey + b'\xff\xff'):
                        if len(k) > key_len + 1:
                            contin = True
                            break
                    if contin:
                        for k, v in self.level_db.iterate(start=chunkkey, end=chunkkey + b'\xff\xff'):
                            if key_len <= len(k) <= key_len + 3:
                                self.raw_level.put(k, v)
                self.raw_level.close(compact=False)
                self.Onmsgbox("Chunks Saved to Source", f"Chunks Saved {the_chunks}")
            else: #java
                buffer_world = ''.join(self.world.level_wrapper.path + "/" + self.get_dim_path_name())
                os.system(f"cp -rf \"{buffer_world}\" \"{self.world_location}\"")
                #shutil.copytree(buffer_world, source_world)
                self.Onmsgbox("Chunks Saved to Source", f"Copied {buffer_world} to {source_world}")


    def source_new(self):

        if exists(self.world.level_wrapper.path + '/main_dir.txt'):
            chunk_range, the_chunks, the_data = [], [], []
            with open(self.world.level_wrapper.path + '/main_dir.txt', "r") as d:
                self.world_location = d.read()
            if self.world.level_wrapper.platform == "java":
                loc = self.canvas.camera.location
                cx, cz = block_coords_to_chunk_coords(loc[0], loc[2])
                prang = self.the_range.GetValue()
                loaction_dict = collections.defaultdict(list)
                for x in range(-prang, prang):
                    for z in range(-prang, prang):
                        chunk_range.append((cx + x, cz + z))
                total = len(chunk_range)
                copy_set = set()
                chunk_set = set()
                for xx, zz in chunk_range:
                    rx, rz = world_utils.chunk_coords_to_region_coords(xx, zz)
                    loaction_dict[(rx, rz)].append((xx, zz))
                for rx, rz in loaction_dict.keys():
                    source_world = self.get_nbt_reg_file(rx, rz, self.world_location)
                    if exists(source_world):
                        buffer_world = self.get_nbt_reg_file(rx, rz,self.world.level_wrapper.path)
                        source_chunks = AnvilRegion(source_world)
                        for xx, zz in source_chunks.all_chunk_coords():
                            chunk_set.add((xx, zz))
                            copy_set.add((source_world,buffer_world))
                for xx,zz in chunk_set:
                    self.world.create_chunk(xx, zz, self.canvas.dimension).changed = True
                self.world.purge()
                for s,d in copy_set:
                    shutil.copy(s,d)

            else: #bedrock
                self.raw_level = LevelDB(self.world_location, create_if_missing=False)
                chunk_range, the_chunks, the_data = [], [], []
                loc = self.canvas.camera.location
                cx, cz = block_coords_to_chunk_coords(loc[0], loc[2])
                prang = self.the_range.GetValue()
                for x in range(-prang, prang):
                    for z in range(-prang, prang):
                        chunk_range.append((cx + x, cz + z))
                for xx, zz in chunk_range:
                    chunkkey = struct.pack('<ii', xx, zz) + self.get_dim_value_bytes()
                    key_len = len(chunkkey)
                    contin = False
                    for k, v in self.raw_level.iterate(start=chunkkey, end=chunkkey + b'\xff\xff'):
                        if len(k) > key_len + 1:
                            contin = True
                            break
                    if contin:
                        for k, v in self.raw_level.iterate(start=chunkkey, end=chunkkey + b'\xff\xff'):
                            if key_len <= len(k) <= key_len + 3:
                                if self.keep_chunks.GetValue():
                                    if not self.world.has_chunk(xx, zz, self.canvas.dimension):
                                        the_chunks.append((xx, zz))
                                        the_data.append((k, v))
                                else:
                                    the_chunks.append((xx, zz))
                                    the_data.append((k, v))
                for xx, zz in the_chunks:
                    self.world.create_chunk(xx, zz, self.canvas.dimension).changed = True
                self.world.save()
                for k, v in the_data:
                    self.level_db.put(k, v)
                self.raw_level.close(compact=False)


    def source_entities(self, _):
        if self.world.level_wrapper.platform == 'bedrock':
            if exists(self.world.level_wrapper.path + '/main_dir.txt'):
                with open(self.world.level_wrapper.path + '/main_dir.txt', "r") as d:
                    self.world_location = d.read()
                    d.close()
                self.raw_level = LevelDB(self.world_location, create_if_missing=False)
                actorprefixs = iter(self.raw_level.iterate(start=b'actorprefix',
                                                           end=b'actorprefix\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF'))
                digps = iter(self.raw_level.iterate(start=b'digp',
                                                    end=b'digp\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF'))
                for k, v in actorprefixs:
                    self.level_db.put(k, v)
                for k, v in digps:
                    self.level_db.put(k, v)
                self.raw_level.close(compact=False)
                self.Onmsgbox("Entities Added", f"All Entities from source world are now in this world.")
        else: #java
            if exists(self.world.level_wrapper.path + '/main_dir.txt'):
                with open(self.world.level_wrapper.path + '/main_dir.txt', "r") as d:
                    self.world_location = d.read()

                buffer_world = ''.join(self.world_location + "/entities")
                os.system(f"cp -rf \"{buffer_world}\" \"{self.world.level_wrapper.path}\" ")
                self.Onmsgbox("Entities Added", f"All Entities from source world are now in this world.")




    def put_entities_back(self, _):
        if self.world.level_wrapper.platform == 'bedrock':
            if exists(self.world.level_wrapper.path + '/main_dir.txt'):
                confirm = self.con_boc("PLEASE NOTE:",
                                       "This Removes all entities and then copies them Back from this copy\n"
                                       "If you have Not pulled in entities all entities will be removed\n"
                                       "are you sure you want to continue?")
                if confirm:
                    with open(self.world.level_wrapper.path + '/main_dir.txt', "r") as d:
                        self.world_location = d.read()
                    to_remove = []
                    self.raw_level = LevelDB(self.raw_level, create_if_missing=False)
                    actorprefixs_b = iter(self.raw_level.iterate(start=b'actorprefix',
                                                                 end=b'actorprefix\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF'))
                    digps_b = iter(self.raw_level.iterate(start=b'digp',
                                                          end=b'digp\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF'))
                    for k, v in actorprefixs_b:
                        to_remove.append(k)
                    for k, v in digps_b:
                        to_remove.append(k)
                    for dk in to_remove:
                        self.raw_level.delete(dk)  # TODO Find a better way to accomplish this

                    actorprefixs = iter(self.level_db.iterate(start=b'actorprefix',
                                                              end=b'actorprefix\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF'))
                    digps = iter(self.level_db.iterate(start=b'digp',
                                                       end=b'digp\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF'))
                    for k, v in actorprefixs:
                        self.raw_level.put(k, v)
                    for k, v in digps:
                        self.raw_level.put(k, v)

                    self.raw_level.close(compact=False)
                    self.Onmsgbox("Done", "Entities Have been copied back to source world")
            else: #java
                if exists(self.world.level_wrapper.path + '/main_dir.txt'):
                    with open(self.world.level_wrapper.path + '/main_dir.txt', "r") as d:
                        self.world_location = d.read()
                buffer_world = ''.join(self.world_location)
                os.system(f"cp -rf {self.world.level_wrapper.path}/entities {buffer_world}")
                self.Onmsgbox("Done", "Entities Have been copied back to source world")


    @property
    def level_db(self):
        level_wrapper = self.world.level_wrapper
        if hasattr(level_wrapper, "level_db"):
            return level_wrapper.level_db
        else:
            return level_wrapper._level_manager._db

    @property
    def big_level_db(self):
        level_wrapper = self.big_world.level_wrapper
        if hasattr(level_wrapper, "level_db"):
            return level_wrapper.level_db
        else:
            return level_wrapper._level_manager._db

    def get_root(self):
        return self.world.level_wrapper.path

    def get_dim_path_name(self):
        if 'minecraft:the_end' in self.canvas.dimension:
            dim = 'DIM1'
        elif 'minecraft:the_nether' in self.canvas.dimension:
            dim = 'DIM-1'
        elif 'minecraft:overworld' in self.canvas.dimension:
            dim = ''

        full_path = os.path.join(dim, "region")
        return full_path

    def get_nbt_reg_file(self, regonx, regonz, path):
        file = "r." + str(regonx) + "." + str(regonz) + ".mca"
        if 'minecraft:the_end' in self.canvas.dimension:
            dim = 'DIM1'
        elif 'minecraft:the_nether' in self.canvas.dimension:
            dim = 'DIM-1'
        elif 'minecraft:overworld' in self.canvas.dimension:
            dim = ''
        version = "region"
        full_path = os.path.join(path, dim, version, file)
        return full_path

export = dict(name="A Buffer World Tool 1.00b", operation=Inventory)
