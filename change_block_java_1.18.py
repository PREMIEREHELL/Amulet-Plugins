import amulet_nbt
from amulet.level.formats.anvil_world.region import AnvilRegionInterface
from amulet.utils import world_utils
import wx
import os
import ctypes
import numpy as np
import sys

# Set numpy print options
np.set_printoptions(threshold=sys.maxsize)

# Constants
CSIDL_APPDATA = 0x001A  # Constant for the roaming app data folder
path_buffer = ctypes.create_unicode_buffer(1024)  # Buffer to store the path
ctypes.windll.shell32.SHGetFolderPathW(0, CSIDL_APPDATA, 0, 0, path_buffer)
roaming_path = path_buffer.value

# Create wx App
app = wx.App()
frame = wx.Frame(None, title="Change Block in java world")


# Open Folder
def on_open_folder(event):
    # Set default folder path
    default_folder = os.path.join(roaming_path, ".minecraft", "saves")

    # Create a dialog to choose a directory
    dialog = wx.DirDialog(frame, "Select a folder", defaultPath=default_folder,
        style=wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST)

    if dialog.ShowModal() == wx.ID_OK:
        selected_folder = dialog.GetPath()
        dialog.Destroy()
        return selected_folder


# Main Event Function
def everthing(event):
    # Parse input data from GUI: x, y, z, blockname
    x, y, z, block = map(str.strip, text_entry.GetValue().split(','))
    x, y, z = map(int, (x, y, z))

    # Convert the block coordinates to chunk and region coordinates
    xc, xz = world_utils.block_coords_to_chunk_coords(x, z)
    rx, rz = world_utils.chunk_coords_to_region_coords(xc, xz)

    # Set the path to the mca file for the corresponding region
    the_path = on_open_folder(event)
    full_file_path = os.path.join(the_path, f"region/r.{rx}.{rz}.mca")

    if os.path.exists(full_file_path):
        # Load the region file
        data = AnvilRegionInterface(full_file_path)

        # Proceed if the chunk exists
        if data.has_chunk(xc % 32, xz % 32):
            # Extract the chunk's NBT data
            chunk_nbt_data = data.get_data(xc % 32, xz % 32).tag

            # Calculate section index based on the y-coordinate
            section = (y - (-64)) // 16

            # Retrieve the palette and calculate the number of bits per entry
            palette = chunk_nbt_data['sections'][section]['block_states']['palette']
            palette_length = len(palette) - 1
            bits_per_entry = max(palette_length.bit_length(), 4)

            # Decode block states data, if available
            if chunk_nbt_data['sections'][section]['block_states'].get('data'):
                p_data = chunk_nbt_data['sections'][section]['block_states']['data'].py_data
                arr = world_utils.decode_long_array(p_data, 16 * 16 * 16, bits_per_entry=bits_per_entry, dense=False)
                arr = arr.reshape(16, 16, 16)
            else:
                arr = np.zeros((16, 16, 16), dtype=int)

            # Remove light data to force Minecraft to recalculate lighting
            for sections in chunk_nbt_data['sections']:
                sections.pop("BlockLight", None)
                sections.pop("SkyLight", None)

            # Find the block index value in the palette, add it if not found
            block_index_value = next(
                (i for i, val in enumerate(palette) if f'StringTag("minecraft:{block}")' in str(val)), None)
            if block_index_value is None:
                palette.append(amulet_nbt.CompoundTag({
                    "Name": amulet_nbt.StringTag(f"minecraft:{block}")}))
                block_index_value = len(palette) - 1

            # Calculate the coordinates within the chunk
            xx, yy, zz = x % 16, y % 16, z % 16

            # Change the block at the target location
            arr[yy][zz][xx] = block_index_value
            arr = arr.flatten()

            # Recalculate the number of bits per entry and re-encode the data
            bits_per_entry = len(palette).bit_length()
            n_data = world_utils.encode_long_array(arr, bits_per_entry=max(bits_per_entry, 4), dense=False)

            # Update the chunk's NBT data
            chunk_nbt_data['sections'][section]['block_states']['data'] = amulet_nbt.LongArrayTag(n_data)
            chunk_nbt_data['sections'][section]['block_states']['palette'] = palette
            data.write_data(xc % 32, xz % 32, chunk_nbt_data)

            print(chunk_nbt_data['sections'][section]['block_states']['palette'], arr, xc % 32, xz % 32, section,
                len(n_data), "DONE")
        else:
            print("Chunk does not exist")
    else:
        print("Chunk region file does not exist")


# Initialize GUI Elements
load_bl = wx.Button(frame, label="Change block")
load_bl.Bind(wx.EVT_BUTTON, everthing)
text_entry = wx.TextCtrl(frame, style=wx.TE_PROCESS_ENTER)
text_entry.SetInitialSize((300, -1))

# Set Sizer for Frame
sizer = wx.BoxSizer(wx.VERTICAL)
sizer.Add(text_entry)
sizer.Add(load_bl)
frame.SetSizerAndFit(sizer)
frame.Show()

# Start the main loop
app.MainLoop()

# import amulet_nbt
# from amulet.level.formats.anvil_world.region import AnvilRegionInterface
# from amulet.utils import world_utils
# import wx
# import  os
# import ctypes
# from os.path import exists
# import numpy as np
# import sys
# np.set_printoptions(threshold=sys.maxsize)
# CSIDL_APPDATA = 0x001A  # Constant for the roaming app data folder
# path_buffer = ctypes.create_unicode_buffer(1024)  # Buffer to store the path
# ctypes.windll.shell32.SHGetFolderPathW(0, CSIDL_APPDATA, 0, 0, path_buffer)
# roaming_path = path_buffer.value
#
# app = wx.App()
# frame = wx.Frame(None, title="Change Block in java world")
# selected_folder = ''
# def on_open_folder(event):
#     default_folder = roaming_path + "\.minecraft\saves" # Set your default folder path here
#     dialog = wx.DirDialog(frame, "Select a folder", defaultPath=default_folder, style=wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST)
#
#     if dialog.ShowModal() == wx.ID_OK:
#         selected_folder = dialog.GetPath()
#
#
#     dialog.Destroy()
#
#     return selected_folder
#
# def everthing(event):
#     # lazy need input data x,y,z,blockname
#     x, y,z, block = text_entry.GetValue().split(',')
#     x, y, z , block = int(x), int(y),int(z), block
#     xc,xz = world_utils.block_coords_to_chunk_coords(x,z)
#     rx,rz = world_utils.chunk_coords_to_region_coords(xc,xz)
#     the_path = on_open_folder(event)
#     full_file_path = f'{the_path}/region/r.{rx}.{rz}.mca'
#
#
#     if exists(full_file_path):
#         data = AnvilRegionInterface(full_file_path)
#         if data.has_chunk(xc % 32,xz %32):
#             chunk_nbt_data = data.get_data(xc % 32,xz %32).tag # NBT DATA 100,170,200,water
#             section = (y - (-64)) // 16
#             pallet = chunk_nbt_data['sections'][section]['block_states']['palette']
#             palette_length = len(pallet) - 1
#             bits_per_entry = palette_length.bit_length()
#             if bits_per_entry < 4:
#                 bits_per_entry = 4
#             if chunk_nbt_data['sections'][section]['block_states'].get('data'):
#                 p_data = chunk_nbt_data['sections'][section]['block_states']['data'].py_data
#                 arr = world_utils.decode_long_array(p_data, 16 * 16 * 16,
#                     bits_per_entry=bits_per_entry, dense=False) #dence false for 1.16 +
#                 arr = arr.reshape(16, 16, 16)
#                 print(arr)
#             else:
#                 arr = np.zeros((16, 16, 16), dtype=int)
#
#             for i, ss in enumerate(chunk_nbt_data['sections']): # force fix lighting
#                 if ss.get("BlockLight"):
#                     ss.pop("BlockLight")
#                 if ss.get("SkyLight"):
#                     ss.pop("SkyLight")
#
#             block_index_value = 0
#             has_block = False
#             for i, ss in enumerate(pallet):
#                 if f'StringTag("minecraft:{block}")' in str(ss): # check if block exsits and grab the index value
#                     block_index_value = i
#                     has_block = True
#             if not has_block:
#
#                 pallet.append(amulet_nbt.CompoundTag({"Name":amulet_nbt.StringTag(f"minecraft:{block}")}))
#                 block_index_value = palette_length+1 # need to have the new index value for the new block
#
#             xx, yy, zz = x % 16, y % 16, z % 16 # get the 16,16,16 location of the subchunk from the cords
#
#             arr[yy][zz][xx] = block_index_value
#             arr = arr.flatten()
#             bits_per_entry = len(pallet).bit_length() - 1
#             if bits_per_entry < 4:
#                 bits_per_entry = 4
#             n_data = world_utils.encode_long_array(arr, bits_per_entry=bits_per_entry, dense=False)
#             chunk_nbt_data['sections'][section]['block_states']['data'] = amulet_nbt.LongArrayTag(n_data)# Update data
#             chunk_nbt_data['sections'][section]['block_states']['palette'] = pallet # Update the pallet
#
#             data.write_data(xc % 32, xz% 32, chunk_nbt_data) # Put data back into the chunk
#             print(chunk_nbt_data['sections'][section]['block_states']['palette'], arr, xc % 32, xz % 32, section,
#                 len(n_data), "DONE")
#
#     else:
#         print("chunk does not exist")
#
#
# load_bl = wx.Button(frame, label="change block")
# load_bl.Bind(wx.EVT_BUTTON, everthing)
# text_entry = wx.TextCtrl(frame, style=wx.TE_PROCESS_ENTER)
# text_entry.SetInitialSize((300, -1))
# sizer = wx.BoxSizer(wx.VERTICAL)
#
# sizer.Add(text_entry)
# sizer.Add(load_bl)
# frame.SetSizerAndFit(sizer)
# frame.Show()
# app.MainLoop()
# # pathlocal = os.getenv('LOCALAPPDATA')
# # mc_path = ''.join([pathlocal,
# #                    r'/Packages/Microsoft.MinecraftUWP_8wekyb3d8bbwe/LocalState/games/com.mojang/minecraftWorlds/'])
# #
# # dialog = wx.DirDialog(None, "Select a directory", defaultPath=mc_path, style=wx.DD_DEFAULT_STYLE)
# #
# # if dialog.ShowModal() == wx.ID_OK:
# #     selected_directory = dialog.GetPath()
#
# # world = leveldb.LevelDB(f'{selected_directory}/db')