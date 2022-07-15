import collections
from amulet.utils import block_coords_to_chunk_coords
import amulet
import wx
import os
from amulet_map_editor.programs.edit.api.operations import DefaultOperationUI
import amulet_nbt
import struct
from amulet.libs.leveldb import LevelDB
from amulet.operations.delete_chunk import delete_chunk
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
        self.label = wx.StaticText(self, label="Set The Range of chunks to source Its *4: ")

        self.make_world_buffer = wx.Button(self, label="Build Buffer World")
        self.make_world_buffer.Bind(wx.EVT_BUTTON, self.make_world)
        self.world_load = wx.Button(self, label="Change/Add Source World Location")
        self.world_load.Bind(wx.EVT_BUTTON, self.operation_run)
        self.keep_chunks = wx.CheckBox(self, label="Keep Previously Sourced Chunks\n"
                                                   "( uncheck to overwrite local from source )")
        self.keep_chunks.SetValue(True)
        self.the_range = wx.SpinCtrl(self, min=1, max=25)
        self.source_new_data = wx.Button(self, label="Pull In Chunks")
        self.source_new_data.Bind(wx.EVT_BUTTON, self.operation_run_source)
        self.source_enty = wx.Button(self, label="Pull In All Entities")
        self.source_enty.Bind(wx.EVT_BUTTON, self.source_entities)
        self.send_enty = wx.Button(self, label="Send Entities Back")
        self.send_enty.Bind(wx.EVT_BUTTON, self.put_entities_back)

        self.source_players = wx.Button(self, label="Get All Player Data")
        self.source_players.Bind(wx.EVT_BUTTON, self.get_player_data())
        self.set_players = wx.Button(self, label="Send Back All Player Data")
        self.set_players.Bind(wx.EVT_BUTTON, self.set_player_data())

        self.save_new_data = wx.Button(self, label="Send Chunks Back")
        self.save_new_data.Bind(wx.EVT_BUTTON, self.put_data_back)

        self.del_chk = wx.Button(self, label="Delete Selected Chunks")
        self.del_chk.Bind(wx.EVT_BUTTON, self.del_selected_chunks)

        self._sizer.Add(self.label_main)
        self._sizer.Add(self.make_world_buffer)
        self._sizer.Add(self.world_load, 0 , wx.TOP, 10)

        self._sizer.Add(self.label, 0, wx.TOP, 15)
        self._sizer.Add(self.the_range, 0, wx.TOP, 5)
        self._sizer.Add(self.keep_chunks, 0, wx.TOP, 5)
        self._sizer.Add(self.source_new_data, 0 , wx.TOP, 5)
        self._sizer.Add(self.save_new_data, 0, wx.TOP, 5)



        self._sizer.Add(self.source_enty, 0 , wx.TOP, 15)
        self._sizer.Add(self.send_enty, 0 , wx.TOP, 5)
        self._sizer.Add(self.source_players, 0 , wx.TOP, 5)
        self._sizer.Add(self.set_players, 0 , wx.TOP, 5)
        self._sizer.Add(self.del_chk, 0 , wx.TOP, 5)

        self.Layout()
        self.Thaw()

    def make_world(self, _):
        pathlocal = os.getenv('LOCALAPPDATA')
        mc_path = ''.join([pathlocal,
                r'/Packages/Microsoft.MinecraftUWP_8wekyb3d8bbwe/LocalState/games/com.mojang/minecraftWorlds/'])
        with wx.DirDialog(None, "Select The World folder For the would you want to buffer",mc_path ,
                          wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST) as fileDialog:
            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return
            else:
                pathname = fileDialog.GetPath()
        import shutil
        the_dir = pathname.split("\\")
        pathhome = ''.join([x+'/' for x in the_dir[:-1]])
        world_buffer_f = pathhome + "buffer" + str(the_dir[-1])
        os.mkdir(world_buffer_f)
        os.mkdir(world_buffer_f + "/db")
        shutil.copy(pathname + "/level.dat", world_buffer_f + "/level.dat")
        # shutil.copy(pathname + "/levelname.txt", world_buffer_f + "/levelname.txt")
        shutil.copy(pathname + "/world_icon.jpeg", world_buffer_f + "/world_icon.jpeg")
        header, new_raw, end = b'', b'', 0

        with open(world_buffer_f + "/levelname.txt", "w") as data:
            data.write("BufferLevel")
            data.close()

        with open(world_buffer_f+'/main_dir.txt', "w") as data:
            data.write(pathname+"/db")
            data.close()

        with open(world_buffer_f + "/level.dat", "rb") as data:
            the_data = data.read()
            header = the_data[:4]
            nbt_leveldat = amulet_nbt.load(the_data[8:], compressed=False, little_endian=True)
            nbt_leveldat['LevelName'] = amulet_nbt.TAG_String("BufferLevel")
            new_raw = nbt_leveldat.save_to(compressed=False, little_endian=True)
            header += struct.pack("<I", len(new_raw))
            data.close()

        with open(world_buffer_f + "/level.dat", "wb") as data:
            data.write(header + new_raw)
            data.close()
        self.raw_level = LevelDB(pathname + "/db", create_if_missing=False)
        self.new_raw_level = LevelDB(world_buffer_f + "/db", create_if_missing=True)
        player_d = self.raw_level.get(b'~local_player')
        self.new_raw_level.put(b'~local_player', player_d)
        self.raw_level.close(compact=False)
        self.new_raw_level.close(compact=False)

    def close(self, _):
        self.raw_level.close(compact=False)

    def operation_run(self, _):

        self.world_load_data()

    def del_selected_chunks(self, _):
        self.world.save()
        with open(self.world.level_wrapper.path+'/main_dir.txt', "r") as d:
            self.world_location = d.read()
            d.close()
        self.raw_level = LevelDB(self.world_location, create_if_missing=False)
        the_chunks = self.canvas.selection.selection_group.chunk_locations()
        to_delete_list = []

        for xx, zz in the_chunks:
            chunkkey = struct.pack('<ii', xx, zz) + self.get_dim_value_bytes()
            key_len = len(chunkkey)

            for k, v in self.raw_level.iterate(start=chunkkey, end=chunkkey + b'\xff\xff'):
                if len(k) >= key_len:
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

    def operation_run_source(self, _):

        self.source_new()
        self.world.unload()
        self.world.purge()
        self.canvas.renderer.render_world._rebuild()


    def get_player_data(self):
        with open(self.world.level_wrapper.path+'/main_dir.txt', "r") as d:
            self.world_location = d.read()
            d.close()
        self.raw_level = LevelDB(self.world_location, create_if_missing=False)
        player_d = self.raw_level.get(b'~local_player')
        for k, v in self.raw_level.iterate(start=b'player_server_',
                                          end=b'player_server_\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF'):
            self.level_db.put(k,v)

        self.level_db.put(b'~local_player', player_d)
        self.raw_level.close(compact=False)

    def set_player_data(self):
        with open(self.world.level_wrapper.path+'/main_dir.txt', "r") as d:
            self.world_location = d.read()
            d.close()
        self.raw_level = LevelDB(self.world_location, create_if_missing=False)
        player_d = self.level_db.get(b'~local_player')
        for k, v in self.level_db.iterate(start=b'player_server_',
                                           end=b'player_server_\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF'):
            self.raw_level.put(k, v)

        self.raw_level.put(b'~local_player', player_d)
        self.raw_level.close(compact=False)



    def world_load_data(self):

        with wx.DirDialog(None, "THE the large world Folder To source data", "",
                          wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST) as fileDialog:
            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return
            else:
                pathname = fileDialog.GetPath()
        self.world_location = pathname + '/db'
        with open(self.world.level_wrapper.path+'/main_dir.txt', "w") as fdata:
            print(self.world_location)
            fdata.write(self.world_location)
            fdata.close()
        self.raw_level = LevelDB(pathname + '/db', create_if_missing=False)
        player_d = self.raw_level.get(b'~local_player')
        self.level_db.put(b'~local_player', player_d)
        self.raw_level.close(compact=False)

    def get_dim_value_bytes(self):
        if 'minecraft:the_end' in self.canvas.dimension:
            dim = int(2).to_bytes(4, 'little', signed=True)
        elif 'minecraft:the_nether' in self.canvas.dimension:
            dim = int(1).to_bytes(4, 'little', signed=True)
        elif 'minecraft:overworld' in self.canvas.dimension:
            dim = b''  # int(0).to_bytes(4, 'little', signed=True)
        return dim

    def put_data_back(self, _):
        self.world.save()
        with open(self.world.level_wrapper.path+'/main_dir.txt', "r") as d:
            self.world_location = d.read()
            d.close()
        self.raw_level = LevelDB(self.world_location, create_if_missing=False)
        the_chunks = [c for c in self.world.level_wrapper.all_chunk_coords(self.canvas.dimension)]
        for xx, zz in the_chunks:
            chunkkey = struct.pack('<ii', xx, zz) + self.get_dim_value_bytes()
            key_len = len(chunkkey)
            for k, v in self.level_db.iterate(start=chunkkey, end=chunkkey + b'\xff\xff'):
                if len(k) >= key_len:
                    self.raw_level.put(k, v)
        self.raw_level.close(compact=False)
        print("level closed")

    def source_new(self):
        with open(self.world.level_wrapper.path+'/main_dir.txt', "r") as d:
            self.world_location = d.read()
            d.close()
        self.raw_level = LevelDB(self.world_location, create_if_missing=False)
        loc = self.canvas.camera.location
        chunk_range = []
        the_chunks = []
        the_data = []
        cx, cz = block_coords_to_chunk_coords(loc[0], loc[2])
        prang = self.the_range.GetValue()
        for x in range(-prang, prang):
            for z in range(-prang, prang):
                chunk_range.append((cx + x, cz + z))

        for xx, zz in chunk_range:

            chunkkey = struct.pack('<ii', xx, zz) + self.get_dim_value_bytes()
            key_len = len(chunkkey)
            for k, v in self.raw_level.iterate(start=chunkkey, end=chunkkey + b'\xff\xff'):
                if len(k) >= key_len:

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
        self.world.purge()

        for k, v in the_data:
            self.level_db.put(k, v)
        self.raw_level.close(compact=False)
        print("level closed")
    def source_entities(self, _):
        with open(self.world.level_wrapper.path+'/main_dir.txt', "r") as d:
            self.world_location = d.read()
            d.close()
        self.raw_level = LevelDB(self.world_location, create_if_missing=False)
        actorprefixs = iter(self.raw_level.iterate(start=b'actorprefix',
                                                  end=b'actorprefix\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF'))
        digps = iter(self.raw_level.iterate(start=b'digp',
                                           end=b'digp\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF'))
        for k,v in actorprefixs:
            self.level_db.put(k,v)
        for k, v in digps:
            self.level_db.put(k, v)
        self.raw_level.close(compact=False)

    def put_entities_back(self, _):
        with open(self.world.level_wrapper.path+'/main_dir.txt', "r") as d:
            self.world_location = d.read()
            d.close()
        self.raw_level = LevelDB(self.world_location, create_if_missing=False)
        actorprefixs = iter(self.level_db.iterate(start=b'actorprefix',
                                                  end=b'actorprefix\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF'))
        digps = iter(self.level_db.iterate(start=b'digp',
                                           end=b'digp\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF'))
        for k,v in actorprefixs:
            self.raw_level.put(k,v)
        for k, v in digps:
            self.raw_level.put(k, v)

        self.raw_level.close(compact=False)

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


export = dict(name="A Buffer World Tool 0.90b", operation=Inventory)
