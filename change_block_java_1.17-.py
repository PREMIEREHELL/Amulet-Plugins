import amulet_nbt
from amulet.level.formats.anvil_world.region import AnvilRegionInterface
from amulet.utils import world_utils
import wx
import  os
import ctypes
from os.path import exists
import numpy as np
import sys
np.set_printoptions(threshold=sys.maxsize)
CSIDL_APPDATA = 0x001A  # Constant for the roaming app data folder
path_buffer = ctypes.create_unicode_buffer(1024)  # Buffer to store the path
ctypes.windll.shell32.SHGetFolderPathW(0, CSIDL_APPDATA, 0, 0, path_buffer)
roaming_path = path_buffer.value

app = wx.App()
frame = wx.Frame(None, title="Change Block in java world")
selected_folder = ''
def on_open_folder(event):
    default_folder = roaming_path + "\.minecraft\saves" # Set your default folder path here
    dialog = wx.DirDialog(frame, "Select a folder", defaultPath=default_folder, style=wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST)

    if dialog.ShowModal() == wx.ID_OK:
        selected_folder = dialog.GetPath()
    dialog.Destroy()

    return selected_folder

def everthing(event):# lazy need input data x,y,z,blockname

    x, y,z, block = text_entry.GetValue().split(',')
    x, y, z , block = int(x), int(y),int(z), block
    xc,xz = world_utils.block_coords_to_chunk_coords(x,z)
    rx,rz = world_utils.chunk_coords_to_region_coords(xc,xz)
    the_path = on_open_folder(event)
    full_file_path = f'{the_path}/region/r.{rx}.{rz}.mca'


    if exists(full_file_path):
        data = AnvilRegionInterface(full_file_path)
        if data.has_chunk(xc % 32,xz %32):
            chunk_nbt_data = data.get_data(xc % 32,xz %32).tag # NBT DATA 100,170,200,water
            print(chunk_nbt_data)
            section = (y - (0)) // 16
            section += 1 # java 1.15
            if chunk_nbt_data['Level']['Sections'][section].get('Palette'):
                pallet = chunk_nbt_data['Level']['Sections'][section]['Palette']
            else:
                chunk_nbt_data['Level']['Sections'][section]['Palette'] = amulet_nbt.ListTag([])
                chunk_nbt_data['Level']['Sections'][section]['Palette']\
                    .append(amulet_nbt.CompoundTag(
                    {"Name":amulet_nbt.StringTag(f"minecraft:air")})) #need to make the pallet
                pallet = chunk_nbt_data['Level']['Sections'][section]['Palette']

            palette_length = len(pallet) - 1
            bits_per_entry = palette_length.bit_length()
            if bits_per_entry < 4:
                bits_per_entry = 4
            if chunk_nbt_data['Level']['Sections'][section].get('BlockStates'):
                p_data = chunk_nbt_data['Level']['Sections'][section]['BlockStates'].py_data
                arr = world_utils.decode_long_array(p_data, 16 * 16 * 16,
                    bits_per_entry=bits_per_entry, dense=True) # i think this changes for 1.16 dence=False
                arr = arr.reshape(16, 16, 16)
                print(arr)
            else:
                arr = np.zeros((16, 16, 16), dtype=int) # if only one block there is no pallet air is the only block
                # need to make a new data section

            # for i, ss in enumerate(chunk_nbt_data['Level']['Sections']): # force fix lighting, this may work for
            # old version
            #     if ss.get("BlockLight"):
            #         ss.pop("BlockLight")
            #     if ss.get("SkyLight"):
            #         ss.pop("SkyLight")

            block_index_value = 0
            has_block = False
            for i, ss in enumerate(pallet):
                if f'StringTag("minecraft:{block}")' in str(ss): # check if block exsits and grab the index value
                    block_index_value = i
                    has_block = True
            if not has_block:

                pallet.append(amulet_nbt.CompoundTag({"Name":amulet_nbt.StringTag(f"minecraft:{block}")})) #add block
                block_index_value = palette_length+1 # need to have the new index value for the new block

            xx, yy, zz = x % 16, y % 16, z % 16 # get the 16,16,16 location of the subchunk from the cords

            arr[yy][zz][xx] = block_index_value
            arr = arr.flatten()
            bits_per_entry = len(pallet).bit_length() - 1 # get new bits per entry
            if bits_per_entry < 4:
                bits_per_entry = 4
            n_data = world_utils.encode_long_array(arr, bits_per_entry=bits_per_entry, dense=True)
            chunk_nbt_data['Level']['Sections'][section]['BlockStates'] = amulet_nbt.LongArrayTag(n_data) #updata longs
            chunk_nbt_data['Level']['Sections'][section]['Palette'] = pallet # Update the pallet

            data.write_data(xc % 32, xz% 32, chunk_nbt_data) #put the data in the chunk

            print(chunk_nbt_data['Level']['Sections'][section]['Palette'], arr, xc % 32, xz % 32, section,
                len(n_data), "DONE")

        else:
            print("no chunk")
    else:
        print("chunk does not exist")


load_bl = wx.Button(frame, label="change block")
load_bl.Bind(wx.EVT_BUTTON, everthing)
text_entry = wx.TextCtrl(frame, style=wx.TE_PROCESS_ENTER)
text_entry.SetInitialSize((300, -1))
sizer = wx.BoxSizer(wx.VERTICAL)

sizer.Add(text_entry)
sizer.Add(load_bl)
frame.SetSizerAndFit(sizer)
frame.Show()
print("Selected folder:", selected_folder)
app.MainLoop()
# pathlocal = os.getenv('LOCALAPPDATA')
# mc_path = ''.join([pathlocal,
#                    r'/Packages/Microsoft.MinecraftUWP_8wekyb3d8bbwe/LocalState/games/com.mojang/minecraftWorlds/'])
#
# dialog = wx.DirDialog(None, "Select a directory", defaultPath=mc_path, style=wx.DD_DEFAULT_STYLE)
#
# if dialog.ShowModal() == wx.ID_OK:
#     selected_directory = dialog.GetPath()

# world = leveldb.LevelDB(f'{selected_directory}/db')