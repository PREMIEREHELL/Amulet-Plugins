import functools
import collections
import copy
import uuid
import struct
import math
import PyMCTranslate
from amulet_map_editor.api.wx.ui.block_select import BlockDefine
from amulet_map_editor.api.wx.ui.version_select import VersionSelect
from collections import namedtuple
from typing import TYPE_CHECKING, Tuple, List
from math import ceil
import io
from PIL import Image
import wx
import os
from os import path
from amulet_nbt import *
from amulet.api.selection import SelectionBox
import numpy
from amulet.api.block_entity import BlockEntity
from amulet.api.selection import SelectionGroup
from amulet_map_editor.programs.edit.api.operations import DefaultOperationUI
from amulet_map_editor.programs.edit.api.behaviour import PointerBehaviour
from amulet_map_editor.programs.edit.api.behaviour import StaticSelectionBehaviour
from amulet_map_editor.programs.edit.api.key_config import ACT_BOX_CLICK
from amulet.utils import block_coords_to_chunk_coords
from amulet.utils import chunk_coords_to_region_coords
from amulet.api.block import Block
from amulet.level.formats.anvil_world.region import AnvilRegion
from pathlib import Path
from amulet_map_editor.programs.edit.api.events import (
    InputPressEvent,
    EVT_INPUT_PRESS,
)
from amulet_map_editor.programs.edit.api.behaviour.pointer_behaviour import (
    PointerBehaviour,
    EVT_POINT_CHANGE,
    PointChangeEvent,
)
from amulet_map_editor.api.wx.ui.block_select.properties import (
    PropertySelect,
    WildcardSNBTType,
    EVT_PROPERTIES_CHANGE,
)
from amulet_map_editor.programs.edit.api.events import (
    EVT_SELECTION_CHANGE,
)

class CustomRadioBox(wx.Panel):
    def __init__(self, parent, label, choices, foreground_color, sty=None, md=1):
        super().__init__(parent)

        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.label = wx.StaticText(self, label=label)
        self.label.SetForegroundColour(foreground_color)
        self.sizer.Add(self.label, 0, wx.ALL, 5)

        self.radio_buttons = []
        self.radio_buttons_map = {}

        if sty == wx.RA_SPECIFY_ROWS:
            self.radio_sizer = wx.FlexGridSizer(rows=md, cols=(len(choices) + md - 1) // md, vgap=5, hgap=5)
        elif sty == wx.RA_SPECIFY_COLS:
            self.radio_sizer = wx.FlexGridSizer(rows=(len(choices) + md - 1) // md, cols=md, vgap=5, hgap=5)
        else:
            self.radio_sizer = wx.BoxSizer(wx.VERTICAL if md == 1 else wx.HORIZONTAL)

        for i, choice in enumerate(choices):
            style = wx.RB_GROUP if i == 0 else 0
            radio_btn = wx.RadioButton(self, label=choice, style=style)
            radio_btn.SetForegroundColour(foreground_color)
            self.radio_sizer.Add(radio_btn, 0, wx.ALL, 5)
            self.radio_buttons.append(radio_btn)
            self.radio_buttons_map[radio_btn] = i

        self.sizer.Add(self.radio_sizer, 0, wx.ALL, 5)
        self.SetSizer(self.sizer)

    def GetString(self, index):
        if 0 <= index < len(self.radio_buttons):
            return self.radio_buttons[int(index)].GetLabel()

    def SetSelection(self, index):
        if 0 <= index < len(self.radio_buttons):
            self.radio_buttons[int(index)].SetValue(True)

    def GetSelection(self):
        for index, radio_btn in enumerate(self.radio_buttons):
            if radio_btn.GetValue():
                return index
        return None

class ProgressBar:
    def __init__(self):
        self.parent = None
        self.prog = None
        self.pos_start = False

    def progress_bar(self, total, cnt, title=None, text=None, update_interval=50):
        """Manage progress bar updates."""
        if self.prog and self.prog.WasCancelled():
            self.stop()
            return True
        update, start = False, False

        if cnt > 0:
            cnt -= 1
            self.pos_start = True

        if cnt == 0:
            start = True
            update = False
        elif cnt > 0:
            start = False
            update = True
        if self.pos_start:
            cnt += 1

        if start:
            self.start_progress(total, cnt, title, text, update_interval)
            return None

        if update:
            if self.prog and self.prog.WasCancelled():
                self.stop()
                return True
            else:
                return self.update_progress(cnt, total, title, text, update_interval)

        return False

    def stop(self):
        if self.prog:
            self.prog.Hide()
            self.prog.Destroy()
        return True

    def start_progress(self, total, cnt, title, text, update_interval):
        """Start the progress dialog."""
        if total > update_interval:
            self.prog = wx.ProgressDialog(
                f"{title}",
                f"{text}: {cnt} / {total}\n  ", total,
                style=wx.PD_AUTO_HIDE | wx.PD_CAN_ABORT | wx.PD_ELAPSED_TIME | wx.PD_REMAINING_TIME,
                parent=self.parent
            )
            self.prog.Show(True)

    def update_progress(self, cnt, total, title, text, update_interval):
        """Update the progress dialog."""
        if cnt % update_interval == 0 or cnt == total:
            if self.prog:
                if self.prog.WasCancelled():
                    self.prog.Destroy()
                    return True
                else:
                    self.prog.Update(cnt, f"{text}: {cnt} / {total}\n  ")

        return False

def scale_bitmap(bitmap, width, height):
    image = bitmap.ConvertToImage()
    image = image.Scale(width, height, wx.IMAGE_QUALITY_HIGH)
    return wx.Bitmap(image)

class ImportImageSettings(wx.Frame):
    def __init__(self, parent, world=None):
        super(ImportImageSettings, self).__init__(parent, title="Import Settings", size=(300,600), style=wx.DEFAULT_FRAME_STYLE | wx.STAY_ON_TOP)
        parent_position = parent.GetScreenPosition()
        self.world = world
        self.SetPosition(parent_position + (50, 50))
        self.parent = parent
        self.font = wx.Font(14, wx.FONTFAMILY_ROMAN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        self.SetFont(self.font)
        self.SetForegroundColour((0, 255, 0))
        self.SetBackgroundColour((0, 0, 0))

        # Color picker control

        self.transparent_border = wx.CheckBox(self, label="Transparent Border?")
        self.transparent_border.Bind(wx.EVT_CHECKBOX, self.is_color_picker_visable)
        self.transparent_border.SetValue(True)
        self.color_picker_label = wx.StaticText(self, label="Select A Color For Border:")
        self.color_picker = wx.ColourPickerCtrl(self, size=(150, 40))

        self.selected_file = wx.StaticText(self, label=" ( Dont Select File if Reusing Custom Maps )\n"
                                                       "No File Selected")
        self.selected_block = wx.StaticText(self, label=str(self.parent.selected_block))
        self.ok_btn = wx.Button(self, label="OK")
        self.ok_btn.Bind(wx.EVT_BUTTON, self.done)

        # Custom radio box for frame type
        self.rb_frame_type = CustomRadioBox(self, 'Frame type?', self.parent.frame_types, (0, 255, 0), md=2)

        # Image file selection button
        self._set_images_on_frames = wx.Button(self, size=(160, 40), label="Select Image File")
        self._set_images_on_frames.Bind(wx.EVT_BUTTON, self.open_file_dialof)

        # Block type selection button
        self.apply_back_block = wx.Button(self, size=(160, 40), label="Select Backing Block")
        self.apply_back_block.Bind(wx.EVT_BUTTON, self.parent.apply_backblock)

        # Bind close event
        self.Bind(wx.EVT_CLOSE, self.on_close)

        # Layout
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.color_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.SetSizer(self.sizer)
        self.mode_sizer = wx.BoxSizer(wx.VERTICAL)
        self.sizer.Add(self._set_images_on_frames, 0, wx.LEFT, 10)
        self.sizer.Add(self.selected_file, 0, wx.LEFT, 10)
        self.sizer.Add(self.apply_back_block, 0, wx.LEFT, 10)
        self.sizer.Add(self.selected_block, 0, wx.LEFT, 10)
        if self.world.level_wrapper.platform == 'java':
            modes = ["Fast","Better","Lab(slow closer)"]
            self.color_find_modes = CustomRadioBox(self, 'How to Match Colors?', modes, (0, 255, 0), md=2)
            self.fixed_frame = wx.CheckBox(self, label="Fixed Frames No Backing Block Required")
            self.invisible_frames = wx.CheckBox(self, label="Make Item Frames Invisible")
            self.fixed_frame.SetValue(True)
            self.invisible_frames.SetValue(True)
            self.sizer.Add(self.fixed_frame, 0, wx.LEFT, 10)
            self.sizer.Add(self.invisible_frames, 0, wx.LEFT, 10)
            self.mode_sizer.Add(self.color_find_modes, 0, wx.LEFT, 10)

        self.sizer.Add(self.rb_frame_type, 0, wx.LEFT, 50)
        self.mode_sizer.Add(self.transparent_border, 0, wx.LEFT, 10)
        self.color_sizer.Add(self.color_picker_label, 0, wx.LEFT, 0)
        self.color_sizer.Add(self.color_picker, 0, wx.LEFT, 0)

        self.sizer.Add(self.mode_sizer)
        self.sizer.Add(self.color_sizer, 0, wx.LEFT, 10)

        self.sizer.Add(self.ok_btn, 0, wx.LEFT, 150)
        self.sizer.Hide(self.color_sizer)
        self.sizer.Hide(self.mode_sizer)
        self.Layout()

        self.Fit()

    def on_close(self, _):

        if self.world.level_wrapper.platform == 'java':
            self.java_options()
        color = self.color_picker.GetColour()
        # Update parent frame type and color properties
        self.parent.rb_frame_type = self.rb_frame_type.GetString(self.rb_frame_type.GetSelection())
        if self.transparent_border.IsChecked():
            self.parent.color = (0, 0, 0, 0)
        else:
            self.parent.color = (color.Red(), color.Green(), color.Blue(), 255)
        self.Destroy()
        if self.parent.selected_file:
            self.parent.set_images_on_frames(None)

    def done(self, _):
        # Similar to on_close, handles OK button press
        self.on_close(None)

    def is_color_picker_visable(self,_):
        if self.transparent_border.IsChecked():

            self.sizer.Hide(self.color_sizer)
        else:
            self.sizer.Show(self.color_sizer)
        self.Fit()  # Adjust the frame size to fit the new layout

    def java_options(self):
        self.parent.fixed_frame = self.fixed_frame.GetValue()
        self.parent.invisible_frames = self.invisible_frames.GetValue()
        selection = self.color_find_modes.GetSelection()
        if selection == 1:
            self.parent.map_data_manager.color_match_mode = 'closer'
        elif selection == 2:
            self.parent.map_data_manager.color_match_mode = 'lab'
        else:
            self.parent.map_data_manager.color_match_mode = None # fast default

    def open_file_dialof(self, _):

        with wx.FileDialog(self, "Open Image file", wildcard="*", style=wx.FD_OPEN) as file_dialog:
            if file_dialog.ShowModal() == wx.ID_CANCEL:
                return
            else:
                self.selected_file.SetLabel(file_dialog.GetPath())
                self.parent.selected_file = file_dialog.GetPath()
                self.sizer.Show(self.mode_sizer)
                self.Fit()
                self.Layout()

    def GetSelectedFrame(self):
        return self.rb_frame_type

    def GetSelectedBlock(self):
        pass

    def SetBlock(self, text):
        self.selected_block.SetLabel(text)

class BuildWallSettings(wx.Frame):
    def __init__(self, parent, maps_img_data, world=None):
        super(BuildWallSettings, self).__init__(parent, title="Map Wall Settings", size=(300,300),
                                                style=wx.DEFAULT_FRAME_STYLE | wx.STAY_ON_TOP)
        parent_position = parent.GetScreenPosition()
        self.world = world
        self.maps_img_data = maps_img_data
        self.SetPosition(parent_position + (50, 50))
        self.parent = parent
        self.font = wx.Font(16, wx.FONTFAMILY_ROMAN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        self.SetFont(self.font)
        self.SetForegroundColour((0, 255, 0))
        self.SetBackgroundColour((0, 0, 0))
        self.vsizer = wx.BoxSizer(wx.VERTICAL)
        self.label_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.input_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.vsizer.Add(self.label_sizer)
        self.vsizer.Add(self.input_sizer)
        self.vsizer.Add(self.button_sizer)

        self.label_col = wx.StaticText(self, label="Height: ")
        self.label_row = wx.StaticText(self, label="Width:  ")
        self.label_sizer.Add(self.label_col,0,wx.LEFT,5)
        self.label_sizer.Add(self.label_row,0,wx.LEFT,35)
        self.text_cols = wx.TextCtrl(self, size=(120, 30))
        self.text_rows = wx.TextCtrl(self, size=(120, 30))
        self.input_sizer.Add(self.text_cols,0,wx.LEFT,5)
        self.input_sizer.Add(self.text_rows,0,wx.LEFT,15)
        self.text_cols.SetValue('4')
        self.text_rows.SetValue('4')
        self.ok_btn = wx.Button(self, label="OK")
        self.ok_btn.Bind(wx.EVT_BUTTON, self.done)
        self.button_sizer.Add(self.ok_btn)
        self.SetSizer(self.vsizer)
        self.Layout()
        self.Fit()
        self.Show()

    def done(self, _):
        cols, rows = int(self.text_cols.GetValue()),int(self.text_rows.GetValue())
        BuildMapWall(cols, rows, self.maps_img_data, parent=self.parent)
        self.Close()

class JavaMapColorsResolver:

    def __init__(self):
        self.MAP_SHADE_MODIFIERS = [180, 220, 255, 135]
        self.map_colors = [
            (0, 0, 0, 0), (127, 178, 56, 255), (247, 233, 163, 255),
            (199, 199, 199, 255), (255, 0, 0, 255), (160, 160, 255, 255),
            (167, 167, 167, 255), (0, 124, 0, 255), (255, 255, 255, 255),
            (164, 168, 184, 255), (151, 109, 77, 255), (112, 112, 112, 255),
            (64, 64, 255, 255), (143, 119, 72, 255), (255, 252, 245, 255),
            (216, 127, 51, 255), (178, 76, 216, 255), (102, 153, 216, 255),
            (229, 229, 51, 255), (127, 204, 25, 255), (242, 127, 165, 255),
            (76, 76, 76, 255), (153, 153, 153, 255), (76, 127, 153, 255),
            (127, 63, 178, 255), (51, 76, 178, 255), (102, 76, 51, 255),
            (102, 127, 51, 255), (153, 51, 51, 255), (25, 25, 25, 255),
            (250, 238, 77, 255), (92, 219, 213, 255), (74, 128, 255, 255),
            (0, 217, 58, 255), (129, 86, 49, 255),
            # Colors added in version 1.12
            (112, 2, 0, 255), (209, 177, 161, 255), (159, 82, 36, 255),
            (149, 87, 108, 255), (112, 108, 138, 255), (186, 133, 36, 255),
            (103, 117, 53, 255), (160, 77, 78, 255), (57, 41, 35, 255),
            (135, 107, 98, 255), (87, 92, 92, 255), (122, 73, 88, 255),
            (76, 62, 92, 255), (76, 50, 35, 255), (76, 82, 42, 255),
            (142, 60, 46, 255), (37, 22, 16, 255),
            # Colors added in version 1.16
            (189, 48, 49, 255), (148, 63, 97, 255), (92, 25, 29, 255),
            (22, 126, 134, 255), (58, 142, 140, 255), (86, 44, 62, 255),
            (20, 180, 133, 255), (100, 100, 100, 255), (216, 175, 147, 255),
            (127, 167, 150, 255)
        ]
        self.map_colors_shaded = self.generate_shaded_colors()

    def generate_shaded_colors(self) -> numpy.ndarray:
        return numpy.array([
            [
                (r * shade) // 255,
                (g * shade) // 255,
                (b * shade) // 255,
                a
            ]
            for r, g, b, a in self.map_colors
            for shade in self.MAP_SHADE_MODIFIERS
        ])

    # Helper function to convert RGB to XYZ color space using numpy
    def rgb_to_xyz_np(self, rgb):
        # Normalize the RGB values to [0, 1]
        rgb = rgb / 255.0

        # Apply sRGB companding (inverse gamma correction)
        mask = rgb > 0.04045
        rgb[mask] = ((rgb[mask] + 0.055) / 1.055) ** 2.4
        rgb[~mask] = rgb[~mask] / 12.92

        # Convert to XYZ using the sRGB matrix
        matrix = numpy.array([[0.4124, 0.3576, 0.1805],
                           [0.2126, 0.7152, 0.0722],
                           [0.0193, 0.1192, 0.9505]])
        xyz = numpy.dot(rgb, matrix.T)

        return xyz

    # Helper function to convert XYZ to Lab color space using numpy
    def xyz_to_lab_np(self,xyz):
        # Reference white point (D65)
        ref_white = numpy.array([0.95047, 1.00000, 1.08883])
        xyz = xyz / ref_white

        # Convert to Lab
        epsilon = 0.008856
        kappa = 903.3

        mask = xyz > epsilon
        xyz[mask] = numpy.cbrt(xyz[mask])
        xyz[~mask] = (kappa * xyz[~mask] + 16) / 116

        L = 116 * xyz[:, 1] - 16
        a = 500 * (xyz[:, 0] - xyz[:, 1])
        b = 200 * (xyz[:, 1] - xyz[:, 2])

        return numpy.stack([L, a, b], axis=1)

    # Function to compute CIE76 color difference using numpy
    def cie76_np(self, lab1, lab2):
        return numpy.sqrt(numpy.sum((lab1 - lab2) ** 2, axis=1))

    def find_closest_java_color_fast(self, rr: int, gg: int, bb: int, aa: int) -> int:

        cr = self.map_colors_shaded[:, 0]
        cg = self.map_colors_shaded[:, 1]
        cb = self.map_colors_shaded[:, 2]
        ca = self.map_colors_shaded[:, 3]

        # Calculate the weighted differences
        r_diff = (cr * 0.71 - rr * 0.71) ** 2
        g_diff = (cg * 0.86 - gg * 0.986) ** 2
        b_diff = (cb * 0.654 - bb * 0.754) ** 2
        a_diff = (ca * 0.53 - aa * 0.53) ** 2

        # Calculate the score
        score = r_diff + g_diff + b_diff + a_diff

        # Find the index with the minimum score
        min_index = numpy.argmin(score)

        return int(min_index)

    def find_closest_java_color_closer(self, rr: int, gg: int, bb: int, aa: int) -> int:

        cr = self.map_colors_shaded[:, 0]
        cg = self.map_colors_shaded[:, 1]
        cb = self.map_colors_shaded[:, 2]
        ca = self.map_colors_shaded[:, 3]

        rmean = (cr + rr) // 2
        r = cr - rr
        g = cg - gg
        b = cb - bb
        a = ca - aa
        score = numpy.sqrt((((512 + rmean) * r * r) >> 8) + (4 * g * g ) + (((747 - rmean) * b * b) >> 8) + a)

        min_index = numpy.argmin(score)
        return int(min_index)

    def find_closest_java_color_lab(self, rr: int, gg: int, bb: int, aa: int) -> int:
        # Convert the target color to Lab
        target_rgb = numpy.array([rr, gg, bb])
        target_xyz = self.rgb_to_xyz_np(target_rgb)
        target_lab = self.xyz_to_lab_np(numpy.array([target_xyz]))

        # Convert all candidate colors to Lab
        candidate_rgb = self.map_colors_shaded[:, :3]  # Ignore alpha for color comparison
        candidate_xyz = self.rgb_to_xyz_np(candidate_rgb)
        candidate_lab = self.xyz_to_lab_np(candidate_xyz)

        # Calculate CIE76 color differences
        distances = self.cie76_np(candidate_lab, target_lab)

        # Find the index of the minimum distance
        min_index = numpy.argmin(distances)

        return int(min_index)

    def from_chunker_colors(self, chunker_map_colors: bytes, mode=None) -> bytes:
        output_bytes = bytearray(len(chunker_map_colors) // 4)
        for i in range(0, len(chunker_map_colors), 4):
            r = chunker_map_colors[i] & 0xFF
            g = chunker_map_colors[i + 1] & 0xFF
            b = chunker_map_colors[i + 2] & 0xFF
            a = chunker_map_colors[i + 3] & 0xFF
            if mode == 'lab':
                output_bytes[i // 4] = self.find_closest_java_color_lab(r, g, b, a)
            elif mode == 'closer':
                output_bytes[i // 4] = self.find_closest_java_color_closer(r, g, b, a)
            else:
                output_bytes[i // 4] = self.find_closest_java_color_fast(r, g, b, a)

        return bytes(output_bytes)

    def to_java_colors(self, java_map_colors: bytes) -> bytes:
        output_bytes = bytearray(len(java_map_colors) * 4)
        for i, value in enumerate(java_map_colors):
            if 0 <= value < len(self.map_colors_shaded):
                rgba = self.map_colors_shaded[value]
                new_index = i * 4
                output_bytes[new_index] = rgba[0]
                output_bytes[new_index + 1] = rgba[1]
                output_bytes[new_index + 2] = rgba[2]
                output_bytes[new_index + 3] = rgba[3]
        return bytes(output_bytes)

class ImageGridManager(wx.StaticBitmap):
    def __init__(self, parent, bitmap, img_id, grid):
        super().__init__(parent, bitmap=bitmap)
        self.parent = parent
        self.img_id = img_id
        self.grid = grid
        self.pos_in_grid = None
        self.Bind(wx.EVT_LEFT_DOWN, self.OnLeftClick)

    def OnLeftClick(self, event):
        if self.pos_in_grid is None:
            self.grid.PlaceImageInFirstAvailableSlot(self)
        else:
            self.grid.RemoveImageFromGrid(self)

    def Copy(self):
        # Create a copy of the image
        return ImageGridManager(self.parent, self.GetBitmap(), self.img_id, self.grid)

class ImageGrid(wx.Panel):
    def __init__(self, parent, rows, cols):
        super().__init__(parent)
        self.rows = rows
        self.cols = cols
        self.sizer = wx.GridSizer(rows, cols, 0, 0)
        self.SetSizer(self.sizer)
        self.image_positions = {}

        for i in range(rows * cols):
            placeholder = wx.Panel(self, size=(120, 120))
            placeholder.SetBackgroundColour(wx.Colour(200, 200, 200))
            self.sizer.Add(placeholder, 0, wx.ALL | wx.EXPAND, 1)
            self.image_positions[i] = placeholder

    def PlaceImageInFirstAvailableSlot(self, image):
        # Check if image is already placed in the grid
        if image.pos_in_grid is not None:
            return
        available_slot_found = False
        for i in range(self.rows * self.cols):
            if isinstance(self.image_positions[i], wx.Panel):  # Placeholder check
                available_slot_found = True
                break

        if not available_slot_found:
            # Handle case where the grid is full
            wx.MessageBox("The grid is full. Cannot place more images.", "Error", wx.ICON_ERROR)
            return
        # Create a copy of the image and add it to the grid
        copied_image = image.Copy()
        copied_image.Hide()
        self.AddImageToGrid(copied_image)

    def AddImageToGrid(self, image, from_last=False):
        # Get grid cell size dynamically
        grid_width, grid_height = self.get_grid_cell_size()

        # Resize the image before adding it to the grid, keeping the img_id intact
        resized_image = self.resize_image_to_fit_grid(image.GetBitmap(), grid_width, grid_height, image.img_id)

        # Remove image from any existing sizer (including the ImageSourcePanel)
        if image.GetContainingSizer() is not None:
             image.GetContainingSizer().Detach(image)

        # Reparent the resized image to the grid's panel
        resized_image.Reparent(self)

        if from_last:
            for i in range(self.rows * self.cols - 1, -1, -1):
                if isinstance(self.image_positions[i], wx.Panel):  # Placeholder check
                    self.sizer.Hide(self.image_positions[i])  # Hide the placeholder
                    self.image_positions[i] = resized_image

                    # Add the resized image to the grid's sizer
                    self.sizer.Replace(self.sizer.GetChildren()[i].GetWindow(), resized_image)

                    resized_image.pos_in_grid = i
                    self.sizer.Layout()
                    break
        else:
            for i in range(self.rows * self.cols):
                if isinstance(self.image_positions[i], wx.Panel):  # Placeholder check
                    self.sizer.Hide(self.image_positions[i])  # Hide the placeholder
                    self.image_positions[i] = resized_image

                    # Add the resized image to the grid's sizer
                    self.sizer.Replace(self.sizer.GetChildren()[i].GetWindow(), resized_image)

                    resized_image.pos_in_grid = i
                    self.sizer.Layout()
                    break
    def get_grid_cell_size(self):
        # Dynamically retrieve the size of a single grid cell
        grid_size = self.GetSize()
        rows, cols = self.rows, self.cols
        grid_width = grid_size.GetWidth() // cols
        grid_height = grid_size.GetHeight() // rows

        return grid_width, grid_height

    def resize_image_to_fit_grid(self, bitmap, grid_width, grid_height, img_id):
        # Convert the bitmap to wx.Image, resize it, and convert it back to wx.Bitmap
        img = bitmap.ConvertToImage()
        img = img.Rescale(grid_width, grid_height, wx.IMAGE_QUALITY_HIGH)
        resized_bitmap = wx.Bitmap(img)

        # Return a new ImageGridManager with the resized bitmap, preserving the img_id
        return ImageGridManager(self.GetParent(), resized_bitmap, img_id=img_id, grid=self)

    def RemoveImageFromGrid(self, image):
        if image.pos_in_grid is not None:
            pos = image.pos_in_grid
            self.sizer.Hide(image)
            placeholder = wx.Panel(self, size=(120, 120))
            placeholder.SetBackgroundColour(wx.Colour(200, 200, 200))
            self.image_positions[pos] = placeholder
            self.sizer.Replace(image, placeholder)
            image.pos_in_grid = None
            self.sizer.Layout()

class ImageSourcePanel(wx.ScrolledWindow):
    def __init__(self, parent, grid):
        super().__init__(parent)
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self.sizer)
        self.SetScrollRate(5, 5)
        self.grid = grid

    def AddImage(self, bitmap, img_id):
        img = ImageGridManager(self, bitmap, img_id, self.grid)
        self.sizer.Add(img, 0, wx.ALL, 5)
        self.Layout()
        self.FitInside()

class BuildMapWall(wx.Frame):
    def __init__(self, col, rows, map_img_list, parent=None):
        super().__init__(parent=None, title="Build Map Wall", size=(800, 800),
                         style=wx.DEFAULT_FRAME_STYLE | wx.STAY_ON_TOP)
        self.parent = parent
        panel = wx.Panel(self)
        parent_position = parent.GetScreenPosition()

        self.SetPosition(parent_position + (50, 50))
        self.font = wx.Font(16, wx.FONTFAMILY_ROMAN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        self.SetFont(self.font)
        self.SetForegroundColour((0, 255, 0))
        self.SetBackgroundColour((0, 0, 0))
        self.grid_rows = col
        self.grid_cols = rows

        self.grid = ImageGrid(panel, self.grid_rows, self.grid_cols)

        self.image_source = ImageSourcePanel(panel, self.grid)
        for map_image, map_id in map_img_list:
            self.image_source.AddImage(map_image, map_id)

        self.image_source.SetMinSize((160, 168))
        get_image_order = wx.Button(panel, size=(80, 50), label="Apply")
        get_image_order.Bind(wx.EVT_BUTTON, self.GetImageOrder)
        _close = wx.Button(panel, size=(80, 50), label="Close")
        _close.Bind(wx.EVT_BUTTON, self.close)
        vbox = wx.BoxSizer(wx.VERTICAL)
        hbox = wx.BoxSizer(wx.HORIZONTAL)
        hbox.Add(self.image_source, 0, wx.EXPAND | wx.ALL, 5)
        hbox.Add(self.grid, 5, wx.EXPAND | wx.ALL, 0)
        vbox.Add(hbox, 10, wx.EXPAND | wx.ALL, 0)
        vbox.Add(get_image_order, 0, wx.CENTER, 0)
        panel.SetSizer(vbox)
        self.Show()
    def close(self, ):
        self.Close()

    def GetImageOrder(self, _):
        map_order_list = []
        for i in range(self.grid_rows * self.grid_cols):

            if self.grid.image_positions.get(i, None):
                if hasattr(self.grid.image_positions.get(i), 'img_id'):
                    map_order_list.append(self.grid.image_positions.get(i).img_id)
                else:
                    map_order_list.append(None)
        self.parent.custom_map_wall = (map_order_list,self.grid_rows , self.grid_cols)

        if None in map_order_list:
            wx.MessageBox(f"The Grid need to be full",
                          "Can Not Apply",
                          wx.OK | wx.ICON_ERROR)
            return
        self.parent.custom_map_wall_add()
        self.Close()

class JavaMapData:
    facing = {
        "Facing Down": 0,
        "Facing Up": 1,
        "Facing North": 2,
        "Facing South": 3,
        "Facing West": 4,
        "Facing East": 5,
    }
    pointing = {
        "Flip Right": 0,
        "Flip Left": 1,
        "Up (Like Preview)": 2,
        "Upside Down": 3
    }

    def __init__(self, parent=None, canvas=None, world=None):

        self.parent = parent
        self.world = world
        self.canvas = canvas
        self.map_data_converter = JavaMapColorsResolver()
        self.color_match_mode = None
        self.maps_path = os.path.join(self.world.level_wrapper.path, 'data')
        self.cols_rows = (0, 0)
        self.progress = ProgressBar()
        self.maps_tobe = {}
        self.c_map_counts = -1
        self.maps_tobe_color_ready = []

        self.custom_map_tobe = {}

        self.all_map = {}
        self.custom_map = {}

        self.temp_new_custom_keys = []
        self.temp_new_map_keys = []
        self.load_all_maps()

    def convert_images(self):
        maps_tobe_new = []
        total = len(self.maps_tobe)
        cnt = 0
        for v in self.maps_tobe:
            cnt += 1
            stop = self.progress.progress_bar(total, cnt, update_interval=1, title="Converting Image to Java Image Preview",
                                              text=f"Processing...")
            if stop:
                return
            java_colors = self.map_data_converter.from_chunker_colors(v[0], mode=self.color_match_mode)
            java_rgba = self.map_data_converter.to_java_colors(java_colors)
            maps_tobe_new.append((java_rgba,v[1], v[2]))
            self.maps_tobe_color_ready.append((java_colors,v[1], v[2]))
        self.maps_tobe = maps_tobe_new

    def get_map_img(self, img_bytes):

        colors = self.map_data_converter.to_java_colors(bytes(img_bytes))
        bb = wx.Bitmap.FromBufferRGBA(128, 128, colors)
        img = scale_bitmap(bb, 128,128)
        return img

    def apply(self, map_key_list=None):

        if not map_key_list:
            map_key_list = self.apply_compund_maps()
        self.java_region_data_apply()
        self.custom_map_location_entry(map_key_list)
        wx.MessageBox(
            f'Amulet does not render Item Frames.\n'
            f'They will be where you placed them.\n'
            f'Also note: You can reuse this by selecting\n'
            f'{self.custom_key_str} from the custom maps list.\n'
            f'After clicking ok this will auto select your custom map'
            f'Click once somewhere in the world\n'
            f'to trigger mouse move selection.',
            "Operation Completed",
            wx.OK | wx.ICON_INFORMATION
        )
        self.refresh_all()

        self.parent._custom_map_list.Clear()

        self.parent._custom_map_list.AppendItems([x for x in self.custom_map.keys()])

        self.parent._custom_map_list.SetStringSelection(self.custom_key_str)
        self.parent._custom_event = wx.CommandEvent(wx.EVT_LISTBOX.evtType[0], self.parent._custom_map_list.GetId())
        self.parent._custom_event.SetEventObject(self.parent._custom_map_list)
        self.parent._custom_map_list.GetEventHandler().ProcessEvent(self.parent._custom_event)

    def get_block_placement_offset(self, xx, yy, zz):
        facing = self.parent.facing.GetSelection()
        block_offset = {
            0: (0, -1, 0),
            # Facing Up
            1: (0, 1, 0),
            # Facing North
            2: (0, 0, -1),
            # Facing South
            3: (0, 0, 1),
            # Facing West
            4: (-1, 0, 0),
            # Facing East
            5: (1, 0, 0)
        }
        x, y, z = block_offset[facing]
        return xx - x, yy - y, zz - z

    def get_item_rotation(self):
        pointing, facing = self.parent.pointing.GetSelection(), self.parent.facing.GetSelection()

        rotation_data = {
            # Facing Down
            (0, 0): (0, 6, [0, 90]),  # North or Right
            (0, 1): (0, 5, [0, 90]),  # East or Left
            (0, 2): (0, 4, [0, 90]),  # South or Up
            (0, 3): (0, 7, [0, 90]),  # West or Down

            # Facing Up
            (1, 0): (1, 0, [0, -90]),  # North or Right
            (1, 1): (1, 5, [0, -90]),  # East or Left
            (1, 2): (1, 2, [0, -90]),  # South or Up
            (1, 3): (1, 7, [0, -90]),  # West or Down

            # Facing North
            (2, 0): (2, 5, [180, 0]),  # North or Right
            (2, 1): (2, 7, [180, 0]),  # East or Left
            (2, 2): (2, 4, [180, 0]),  # South or Up
            (2, 3): (2, 6, [180, 0]),  # West or Down

            # Facing South
            (3, 0): (3, 5, [180, 0]),  # North or Right
            (3, 1): (3, 7, [180, 0]),  # East or Left
            (3, 2): (3, 4, [180, 0]),  # South or Up
            (3, 3): (3, 6, [180, 0]),  # West or Down

            # Facing West
            (4, 0): (4, 5, [0, 0]),  # North or Right
            (4, 1): (4, 7, [90, 0]),  # East or Left
            (4, 2): (4, 4, [90, 0]),  # South or Up
            (4, 3): (4, 6, [90, 0]),  # West or Down

            # Facing East
            (5, 0): (5, 1, [270, 0]),  # North or Right
            (5, 1): (5, 7, [270, 0]),  # East or Left
            (5, 2): (5, 4, [270, 0]),  # South or Up
            (5, 3): (5, 6, [270, 0]),  # West or Down
        }

        _facing, _item_rotation, (rx, ry) = rotation_data[(facing, pointing)]
        return ByteTag(_facing), ByteTag(_item_rotation),  ListTag([FloatTag(rx),FloatTag(ry)])

    def get_dim_vpath_java_dir(self, regonx, regonz, folder='region'):  # entities
        file = "r." + str(regonx) + "." + str(regonz) + ".mca"
        path = self.world.level_wrapper.path
        full_path = ''
        dim = ''
        if 'minecraft:the_end' in self.canvas.dimension:
            dim = 'DIM1'
        elif 'minecraft:the_nether' in self.canvas.dimension:
            dim = 'DIM-1'
        elif 'minecraft:overworld' in self.canvas.dimension:
            dim = ''

        full_path = os.path.join(path, dim, folder, file)
        return full_path

    def custom_map_location_entry(self, maps_keys: list[str]):

        idcounts_dat = os.path.join(self.maps_path,'idcounts.dat')
        count_data = None
        if os.path.exists(idcounts_dat):
            count_data = load(idcounts_dat)
            count = count_data['data'].get('map').py_int
            count += len(maps_keys)
            count_data['data']['map'] = IntTag(count)
        else:
            count_data = CompoundTag({
                'data': CompoundTag({
                    'map': IntTag(len(maps_keys))}),
                'DataVersion': IntTag(self.world.level_wrapper.version)
            })
        count_data.save_to(idcounts_dat, compressed=True, little_endian=False,
                           string_encoder=utf8_encoder)

        custom_pre_fix = self.get_available_custom_key

        self.custom_key_str = custom_pre_fix + ":" + self.parent.custom_map_name.GetValue()
        custom_path_file = os.path.join(self.maps_path, f'{custom_pre_fix}.dat')


        pointing = self.parent.pointing.GetSelection()
        facing = self.parent.facing.GetSelection()
        cols, rows = self.cols_rows

        nbt_maps = [StringTag(m) for m in maps_keys]
        x, y, z = self.canvas.camera.location
        xz, yy = self.canvas.camera.rotation
        sg = self.canvas.selection.selection_group
        (sx, sy, sg), (xs, xy, xg) = sg.min, sg.max
        c_data = CompoundTag({
            "name": StringTag(self.custom_key_str),
            "pointing": IntTag(pointing),
            "facing": IntTag(facing),
            "cols": IntTag(cols),
            "rows": IntTag(rows),
            "map_list": ListTag(nbt_maps),
            "dimension": StringTag(self.canvas.dimension),
            "rotation": IntArrayTag([xz, yy]),
            "location": IntArrayTag([x, y, z]),
            "selectionGp": IntArrayTag([sx, sy, sg, xs, xy, xg])
        })

        c_data.save_to(custom_path_file, compressed=True, little_endian=False,
                           string_encoder=utf8_encoder)
        return self.custom_key_str

    def get_map_colors(self, map_name):
        nbt = load(self.all_map[map_name])

        colors = nbt['data'].get('colors', None)
        name = map_name
        map_id = int(name[4:])

        self.maps_tobe_color_ready.append((name, map_id, name))
        rgba_colors = self.map_data_converter.to_java_colors(bytes(colors.py_data))
        return rgba_colors

    def get_custom_map_nbt(self, selection):
        custom_data = load(self.custom_map[selection])

        return custom_data

    def item_frame_entitle(self, item_map_id, position):
        fixed_frame, invisible_frame = 0,0
        if self.parent.fixed_frame:
            fixed_frame = 1
        if self.parent.invisible_frames:
            invisible_frame = 1
        cord_pos = {
            0: (0.5, 0.03125, 0.5),
            1: (0.5, 0.96875, 0.5),
            2: (0.5, 0.5, 0.03125),
            3: (0.5, 0.5, 0.96875), #96875
            4: (0.03125, 0.5, 0.5),
            5: (0.96875, 0.5, 0.5)
        }
        facing, item_rotation, rotation = self.get_item_rotation()

        item_name = None
        if self.parent.rb_frame_type  == "Regular Frame":
            item_name = 'minecraft:item_frame'
        elif self.parent.rb_frame_type == "Glow Frame":
            item_name = 'minecraft:glow_item_frame'
        x,y,z = position
        if x >= 0:
            x = x + cord_pos[facing.py_int][0]
        else:
            x = -(abs(x) + cord_pos[facing.py_int][0])

        # Handle y-coordinate
        if y >= 0:
            y = y + cord_pos[facing.py_int][1]
        else:
            y = -(abs(y) + cord_pos[facing.py_int][1])

        # Handle z-coordinate
        if z >= 0:
            z = z + cord_pos[facing.py_int][2]
        else:
            z = -(abs(z) + cord_pos[facing.py_int][2])

        print(x,y,z, position)
        entitle_compound = CompoundTag({
            'Motion': ListTag([DoubleTag(0), DoubleTag(0), DoubleTag(0)]),
            'Facing': facing,
            'ItemRotation': item_rotation,
            'Invulnerable': ByteTag(0),
            'Air': ShortTag(300),
            'OnGround': ByteTag(0),
            'PortalCooldown': IntTag(0),
            'Rotation': rotation,
            'FallDistance': FloatTag(0),
            'Item': CompoundTag({
                'components': CompoundTag({
                    "minecraft:map_id": IntTag(item_map_id)
                }),
                'count': ByteTag(1),
                'id': StringTag("minecraft:filled_map")
            }),
            'ItemDropChance': FloatTag(1),
            'Pos': ListTag([DoubleTag(x), DoubleTag(y), DoubleTag(z)]),
            'Fire': ShortTag(-1),
            'TileY': IntTag(y),
            'id': StringTag(item_name),
            'TileX': IntTag(x),
            'Invisible': ByteTag(invisible_frame),
            'UUID': IntArrayTag([x for x in struct.unpack('>iiii', uuid.uuid4().bytes)]),
            'TileZ': IntTag(z),
            'Fixed': ByteTag(fixed_frame)
        })
        return entitle_compound

    def java_region_data_apply(self):
        self.raw_data_chunks = None
        self.raw_data_entities = None
        sorted_blocks, rotation = self.parent.reorder_coordinates()
        #blk_location_dict = collections.defaultdict(lambda: collections.defaultdict(list))
        location_dict = collections.defaultdict(lambda: collections.defaultdict(list))
        platform = self.world.level_wrapper.platform
        version = self.world.level_wrapper.version
        chunk_list = []
        blk_location = []
        for map_inx, (x, y, z) in enumerate(sorted_blocks):
            xx, yy, zz = block_coords_to_chunk_coords(x, y, z)
            rx, rz = chunk_coords_to_region_coords(xx, zz)
            if (xx, yy, zz) in location_dict[(rx, rz)]:
                location_dict[(rx, rz)][(xx, yy, zz)].append(((x, y, z),map_inx))
            else:
                location_dict[(rx, rz)][(xx, yy, zz)] = [((x, y, z),map_inx)]
        for x, y, z in sorted_blocks:
            bx, by, bz = self.get_block_placement_offset(x, y, z)
            blk_location.append((bx, by, bz))


        item_map_id = [x[1] for x in self.maps_tobe_color_ready]

        for (rx, rz), chunk_data in location_dict.items():
            self.raw_data_entities = AnvilRegion(self.get_dim_vpath_java_dir(rx, rz, folder='entities'))
            for (cx, cy, cz), block_locations in chunk_data.items():#
                chunk_list.append((cx, cz))

                if self.raw_data_entities.has_chunk(cx % 32, cz % 32):
                    entities_data = self.raw_data_entities.get_chunk_data(cx % 32, cz % 32)
                    for block_loc, map_inx in  block_locations:
                        print(item_map_id[map_inx], block_loc, cx % 32, cz % 32)
                        entities_data['Entities'].append(self.item_frame_entitle(item_map_id[map_inx], block_loc))
                    self.raw_data_entities.put_chunk_data(cx % 32, cz % 32, entities_data)
                else:
                    entities_data = CompoundTag({
                        'Position': IntArrayTag([cx,cz]),
                        'DataVersion': IntTag(self.world.level_wrapper.version),
                        'Entities': ListTag([])
                    })
                    for block_loc, map_inx in  block_locations:
                        entities_data['Entities'].append(self.item_frame_entitle(item_map_id[map_inx],block_loc))
                    self.raw_data_entities.put_chunk_data(cx % 32, cz % 32, entities_data)


            self.raw_data_entities.save()
            self.raw_data_entities.unload()

        if self.parent.selected_block:

            for x, y, z in blk_location:

                self.world.set_version_block(x, y, z, self.canvas.dimension,
                                             (platform, version), self.parent.selected_block, None)
            self.canvas.run_operation(
                lambda: self.parent._refresh_chunk(self.canvas.dimension, self.world,
                                                   self.canvas.selection.selection_group.min_x,
                                                   self.canvas.selection.selection_group.min_z))
            self.world.save()
        for cx,cz in chunk_list:
            chunk_data = self.world.level_wrapper.get_raw_chunk_data(cx, cz, self.canvas.dimension)
            if chunk_data.get('isLightOn', None):
                chunk_data['isLightOn'] = ByteTag(0)
            self.world.level_wrapper.put_raw_chunk_data(cx, cz, chunk_data, self.canvas.dimension)

    def apply_compund_maps(self): # .dat files
        version = self.world.level_wrapper.version
        map_data = CompoundTag({'DataVersion': IntTag(version)})
        map_data['data'] = CompoundTag({
            'zCenter': IntTag(2147483647),
            'xCenter': IntTag(2147483647),
            "trackingPosition": ByteTag(1),
            "unlimitedTracking": ByteTag(0),
            "dimension": StringTag(self.canvas.dimension),
            "colors": ByteArrayTag(0)
        })
        map_key_list = []
        cols, rows = self.cols_rows
        total = cols * rows
        cnt = 0
        for raw_color_data, map_id, name in self.maps_tobe_color_ready:
            cnt += 1
            stop = self.progress.progress_bar(total, cnt, update_interval=1, title="Adding Images To World",
                                              text=f"Processing...{name}")
            if stop:
                break
            map_key_list.append(name)
            map_data['data']['colors'] = ByteArrayTag(bytearray(raw_color_data))
            file_path = os.path.join(self.maps_path, name+'.dat')
            map_data.save_to(file_path, compressed=True, little_endian=False,
                                      string_encoder=utf8_encoder)

        return map_key_list

    def get_colors_from_map(self, _file_path):
        nbt = load(_file_path)
        colors = nbt['data'].get('colors', None)
        rgba_colors = self.map_data_converter.to_java_colors(bytes(colors.py_data))
        return rgba_colors

    def load_all_maps(self):
        idcounts_dat = os.path.join(self.maps_path, 'idcounts.dat')
        if os.path.exists(idcounts_dat):
            pass
        all_maps = [f"{f}" for f in os.listdir(self.maps_path)
                    if os.path.isfile(os.path.join(self.maps_path, f)) and "map_" in f[0:4]]
        self.c_map_counts = -len([x for x in all_maps if 'map_-' in x[0:5]]) - 1

        custom_map = [f"{f}" for f in os.listdir(self.maps_path)
                    if os.path.isfile(os.path.join(self.maps_path, f)) and "cmap_" in f[0:5]]

        for map_ in all_maps: # 2147483647
            if 'map_' in map_:
                nbt = load(os.path.join(self.maps_path, map_))
                if max(nbt['data'].get('colors').py_data) > 0:
                    self.all_map[map_[:-4]] = f"{self.maps_path}\\{map_}"
                # if nbt['data'].get('xCenter').py_int != 2147483647 and nbt['data'].get('zCenter').py_int != 2147483647:

        for cmap_ in custom_map:
            if 'cmap_' in cmap_:
                nbt = load(os.path.join(self.maps_path ,cmap_))
                name_str = nbt.get('name').py_str
                self.custom_map[name_str] = f"{self.maps_path}\\{cmap_}"

    @property
    def get_available_custom_key(self):
        if len(self.custom_map) == 0 and len(self.temp_new_custom_keys) == 0:
            self.temp_new_custom_keys.append(f'cmap_{0}')
            return f'cmap_{0}'
        else:
            for i in range(len(self.custom_map) + len(self.temp_new_custom_keys)):
                next_map_key = f'cmap_{i + 1}'
                if next_map_key not in str(self.custom_map.keys()):
                    if next_map_key not in str(self.temp_new_custom_keys):
                        self.temp_new_custom_keys.append(next_map_key)
                        return next_map_key

    @property
    def get_available_map_key(self):
        if self.c_map_counts == -1 and len(self.temp_new_map_keys) == 0:
            self.temp_new_map_keys.append(f'map_{self.c_map_counts}')
            self.c_map_counts -= 1
            return f'map_{-1}'
        else:
            next_map_key = f'map_{self.c_map_counts}'
            self.temp_new_map_keys.append(next_map_key)
            self.c_map_counts -= 1
            return next_map_key

    def del_selected_map(self, file_):

        def check_for_matching_cmap(name, current_map_list):

            for n,f in self.custom_map.items():
                if n != name:
                    nbt = load(f)
                    map_list = nbt.get('map_list').py_data
                    for m in map_list:
                        if m in current_map_list:
                            current_map_list.remove(m)

            for rm in current_map_list: #safe to delete no other cmaps contain map
                f = self.all_map[rm.py_str]
                os.remove(f)

        def check_for_matching_map(name):
            map_in_cmap = []
            for f in self.custom_map.values():

                nbt = load(f)
                map_list = nbt.get('map_list').py_data
                cmap_name = nbt.get('name').py_str
                if name in str(map_list):
                    map_in_cmap.append(cmap_name)
            if len(map_in_cmap) > 0:
                wx.MessageBox(f"This {name} is part of custom map/'s\n"
                              f"Remove theses custom maps and try again: \n{map_in_cmap} ",
                              "Can Not Remove",
                              wx.OK | wx.ICON_ERROR)
            else:
                f = self.all_map[name]
                os.remove(f)

        if 'cmap_' in file_:
            f = self.custom_map[file_]
            nbt = load(f)
            map_list = nbt.get('map_list').py_data
            if 'map_-' in map_list[0].py_str:
                check_for_matching_cmap(file_, map_list)
                os.remove(f)
            else:
                os.remove(f)
        else:
            check_for_matching_map(file_)

    def delete_all_maps(self):
        for f in self.all_map.values():
            os.remove(f)
        for f in self.custom_map.values():
            os.remove(f)
        idcounts_dat = os.path.join(self.maps_path, 'idcounts.dat')
        count_data = CompoundTag({
            'data': CompoundTag({
                'map': IntTag(0),
            'DataVersion': IntTag(self.world.level_wrapper.version)
            })
        })
        count_data.save_to(idcounts_dat, compressed=True, little_endian=False,
                           string_encoder=utf8_encoder)
        self.refresh_all()

    def refresh_all(self):
        self.maps_tobe = []
        self.custom_map_tobe = {}
        self.all_map = {}
        self.custom_map = {}
        self.maps_tobe_color_ready = []
        self.temp_new_custom_keys = []
        self.temp_new_map_keys = []
        self.load_all_maps()

    def get_cmap_list_of_map_images(self, cmap):
        f = self.custom_map[cmap]
        nbt = load(f)
        list_or_maps = nbt['map_list'].py_data
        imgs = []
        for i in list_or_maps:
            rgba = self.get_map_colors(i.py_str)
            img = Image.frombytes('RGBA', (128, 128), rgba)
            imgs.append(img)
        return imgs

class BedrockMapData:
    facing = {
        "Facing Down": 0,
        "Facing Up": 1,
        "Facing North": 2,
        "Facing South": 3,
        "Facing West": 4,
        "Facing East": 5,
    }
    pointing = {
        "Flip Right": 0,
        "Flip Left": 1,
        "Up (Like Preview)": 2,
        "Upside Down": 3
    }

    def __init__(self, parent=None, canvas=None, world=None):
        self.parent = parent
        self.world = world
        self.canvas = canvas

        self.cols_rows = (0, 0)
        self.progress = ProgressBar()
        self.maps_tobe = []
        self.custom_map_tobe = {}

        self.all_map = {}
        self.custom_map = {}

        self.temp_new_custom_keys = []
        self.temp_new_map_keys = []
        self.load_all_maps()

    def get_map_img(self, name):

        colors = self.all_map[name]
        bb = wx.Bitmap.FromBufferRGBA(128, 128, colors.get('colors').py_data)
        img = scale_bitmap(bb, 128, 128)
        return img
    def get_block_placement_offset(self, xx,yy,zz):
        facing = self.parent.facing.GetSelection()
        block_offset = {
            0: (0, -1, 0),
            # Facing Up
            1: (0, 1, 0),
            # Facing North
            2: (0, 0, -1),
            # Facing South
            3: (0, 0, 1),
            # Facing West
            4: (-1, 0, 0),
            # Facing East
            5: (1, 0, 0)
        }
        x,y,z = block_offset[facing]

        return (xx-x,yy-y,zz-z)

    def apply(self,  map_key_list=None):
        platform = self.world.level_wrapper.platform
        version = self.world.level_wrapper.version
        block_name, block_entiy_name = None, None
        if self.parent.rb_frame_type == "Regular Frame":
            block_name, block_entiy_name = ("frame", "ItemFrame")
        elif self.parent.rb_frame_type == "Glow Frame":
            block_name, block_entiy_name = ("glow_frame", "GlowItemFrame")
        c_map_key = None
        if not map_key_list:
            map_key_list = self.put_map_data()
            c_map_key = [x[1] for x in self.maps_tobe]
        self.parent.custom_key_str = self.custom_map_location_entry(map_key_list)

        facing_direction, pointed = self.parent.facing.GetSelection(), self.parent.pointing.GetSelection()
        block_coordinates, rotation_angle = self.parent.reorder_coordinates()
        sorted_blocks, rotation = self.parent.reorder_coordinates()
        blk_location = []
        for x, y, z in sorted_blocks:
            bx, by, bz = self.get_block_placement_offset(x, y, z)
            blk_location.append((bx, by, bz))
        map_keys_tobe = [k[1] for k in self.maps_tobe]
        for idx in range(len(block_coordinates)):
            if self.parent.custom_map_loaded:
                uuid = LongTag(int(self.parent.selected_maps[idx].replace('map_', '')))
            else:
                uuid = LongTag(map_keys_tobe[idx])

            x, y, z = block_coordinates[idx][0], block_coordinates[idx][1], block_coordinates[idx][2]
            block_nbt = CompoundTag({
                "facing_direction": IntTag(facing_direction),
                "item_frame_map_bit": ByteTag(1)
            })
            block = Block("minecraft", block_name, dict(block_nbt))
            entity_nbt = CompoundTag({
                "isMovable": ShortTag(1),
                "Item": CompoundTag({
                    "Count": ByteTag(1),
                    "Damage": ByteTag(6),
                    "Name": StringTag("minecraft:filled_map"),
                    "WasPickedUp": ByteTag(0),
                    "tag": CompoundTag({
                        "map_name_index": IntTag(-1),
                        "map_uuid": uuid,
                    })
                }),
                "ItemDropChance": FloatTag(1.0),
                "ItemRotation": FloatTag(rotation_angle),
            })
            block_entity = BlockEntity("minecraft", block_entiy_name, 0, 0, 0, NamedTag(entity_nbt))
            self.world.set_version_block(x, y, z, self.canvas.dimension,
                                         (platform, version), block, block_entity)

        if self.parent.selected_block:
            for x,y,z in blk_location:
                self.world.set_version_block(x, y, z, self.canvas.dimension,
                                             (platform, version), self.parent.selected_block, None)

        self.canvas.run_operation(
            lambda: self.parent._refresh_chunk(self.canvas.dimension, self.world,
                                               self.canvas.selection.selection_group.min_x,
                                               self.canvas.selection.selection_group.min_z))
        self.world.save()
        wx.MessageBox(
            f'Amulet does not render Item Frames.\n'
            f'They will be where you placed them.\n'
            f'Also note: You can reuse this by selecting\n'
            f'{c_map_key} from the custom maps list.\n'
            f'After clicking ok this will auto select your custom map'
            f'Click once somewhere in the world\n'
            f'to trigger mouse move selection.',
            "Operation Completed",
            wx.OK | wx.ICON_INFORMATION
        )
        self.refresh_all()

        self.parent._custom_map_list.Clear()

        self.parent._custom_map_list.AppendItems([x for x in self.custom_map.keys()])

        self.parent._custom_map_list.SetStringSelection(self.parent.custom_key_str)
        self.parent._custom_event = wx.CommandEvent(wx.EVT_LISTBOX.evtType[0], self.parent._custom_map_list.GetId())
        self.parent._custom_event.SetEventObject(self.parent._custom_map_list)
        self.parent._custom_map_list.GetEventHandler().ProcessEvent(self.parent._custom_event)

    def get_map_colors(self, key):
        return self.all_map[key]['colors'].py_data

    def get_colors_from_map(self, _file_path):
        color_data = _file_path.get('colors', None)
        return bytes(color_data.py_data)

    def custom_map_location_entry(self, maps_keys: list[str]):
        pointing = self.parent.pointing.GetSelection()
        facing = self.parent.facing.GetSelection()
        cols, rows = self.cols_rows
        # if self.parent.custom_map_loaded:
        #
        # else:
        #     custom_pre_fix = [x for x in self.maps_tobe.keys()][0]
        custom_pre_fix = self.get_available_custom_key
        self.custom_key_str = custom_pre_fix + ":" + self.parent.custom_map_name.GetValue()
        custom_key = self.custom_key_str.encode()
        nbt_maps = [StringTag(m) for m in maps_keys]
        x, y, z = self.canvas.camera.location
        xz, yy = self.canvas.camera.rotation
        sg = self.canvas.selection.selection_group
        (sx, sy, sg), (xs, xy, xg) = sg.min, sg.max
        c_data = CompoundTag({
            "pointing": IntTag(pointing),
            "facing": IntTag(facing),
            "cols": IntTag(cols),
            "rows": IntTag(rows),
            "map_list": ListTag(nbt_maps),
            "dimension": StringTag(self.canvas.dimension),
            "rotation": IntArrayTag([xz, yy]),
            "location": IntArrayTag([x, y, z]),
            "selectionGp": IntArrayTag([sx, sy, sg, xs, xy, xg])
        })
        raw_nbt = c_data.to_nbt(compressed=False, little_endian=True, string_encoder=utf8_escape_encoder)
        self.level_db.put(custom_key, raw_nbt)
        return self.custom_key_str

    def get_custom_map_nbt(self, selection):

        return self.custom_map[selection]

    def put_map_data(self):
        map_key_list = self.apply_compund_maps()
        return map_key_list

    def apply_compund_maps(self):
        map_data = CompoundTag({
            "name": StringTag(''),
            "dimension": ByteTag(0),
            "fullyExplored": ByteTag(1),
            "scale": ByteTag(4),
            "mapId": LongTag(0),
            "parentMapId": LongTag(-1),
            "mapLocked": ByteTag(1),
            "unlimitedTracking": ByteTag(0),
            "xCenter": IntTag(2147483647),
            "zCenter": IntTag(2147483647),
            "height": ShortTag(128),
            "width": ShortTag(128),
            "colors": ByteArrayTag(0)
        })
        map_key_list = []
        cols, rows = self.cols_rows
        total = cols * rows
        cnt = 0
        for raw_color_data, map_id, name in self.maps_tobe:
            cnt += 1
            stop = self.progress.progress_bar(total, cnt, update_interval=1, title="Adding Images To World",
                                              text=f"Processing...{name}")
            if stop:
                break
            map_key_list.append(name)
            map_key = name.encode()
            map_data['name'] = StringTag(name)
            map_data['mapId'] = LongTag(map_id)
            map_data['colors'] = ByteArrayTag(bytearray(raw_color_data))
            raw_map = map_data.to_nbt(compressed=False, little_endian=True,
                                      string_encoder=utf8_escape_encoder)
            self.level_db.put(map_key, raw_map)

        return map_key_list

    def load_all_maps(self):
        self.custom_map = self.get_nbt_data(b'cmap')
        self.all_map = self.get_nbt_data(b'map_')

    def get_nbt_data(self, byte_key: bytes):
        _map = {}
        for k, v in self.level_db.iterate(start=byte_key,
                                          end=byte_key + b'\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF'):
            nbt = load(v, compressed=False, little_endian=True, string_decoder=utf8_escape_decoder).tag
            if nbt.get('colors', None):
                if max(nbt['colors'].py_data) > 0:
                    _map[k.decode()] = nbt
            else:
                _map[k.decode()] = nbt
        return _map

    def del_selected_map(self, key):

        def check_for_matching_cmap(name, current_map_list):

            for n, f in self.custom_map.items():
                if n != name:
                    nbt = f
                    map_list = nbt.get('map_list').py_data
                    for m in map_list:
                        if m in current_map_list:
                            current_map_list.remove(m)
            for rm in current_map_list:  # safe to delete no other cmaps contain map
                self.level_db.delete(rm.encode())

        def check_for_matching_map(name):
            map_in_cmap = []
            for k,f in self.custom_map.items():

                nbt = f
                map_list = nbt.get('map_list').py_data
                cmap_name = k
                if name in str(map_list):
                    map_in_cmap.append(cmap_name)
            if len(map_in_cmap) > 0:
                wx.MessageBox(f"This {name} is part of custom map/'s\n"
                              f"Remove theses custom maps and try again: \n{map_in_cmap} ",
                              "Can Not Remove",
                              wx.OK | wx.ICON_ERROR)
            else:
                self.level_db.delete(name.encode())

        if 'cmap_' in key:
            nbt = self.custom_map[key]
            map_list = nbt.get('map_list').py_data
            if 'map_-' not in map_list[0].py_str:
                check_for_matching_cmap(key, map_list)
                self.level_db.delete(key.encode())
            else:
                self.level_db.delete(key.encode())
        else:
            check_for_matching_map(key)
        # self.all_map
        # self.custom_map
        # self.level_db.delete(k)

    def delete_all_maps(self):

        for k, v in self.level_db.iterate(start=b'cmap',
                                          end=b'cmap' + b'\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF'):
            self.level_db.delete(k)
        for k, v in self.level_db.iterate(start=b'map_',
                                          end=b'map_' + b'\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF'):
            self.level_db.delete(k)

    def refresh_all(self):
        self.maps_tobe = []
        self.custom_map_tobe = {}
        self.all_map = {}
        self.custom_map = {}
        self.temp_new_custom_keys = []
        self.temp_new_map_keys = []
        self.load_all_maps()

    def convert_images(self):
        pass # holder for java

    def get_cmap_list_of_map_images(self, cmap):
        nbt = self.custom_map[cmap]
        list_or_maps = nbt['map_list'].py_data
        imgs = []
        for i in list_or_maps:
            rgba = self.get_map_colors(i.py_str)
            img = Image.frombytes('RGBA', (128, 128), bytes(rgba))
            imgs.append(img)
        return imgs

    @property
    def get_available_custom_key(self):
        if len(self.custom_map) == 0 and len(self.temp_new_custom_keys) == 0:
            self.temp_new_custom_keys.append(f'cmap_{0}')
            return f'cmap_{0}'
        else:
            for i in range(len(self.custom_map) + len(self.temp_new_custom_keys)):
                next_map_key = f'cmap_{i + 1}'
                if next_map_key not in str(self.custom_map.keys()):
                    if next_map_key not in str(self.temp_new_custom_keys):
                        self.temp_new_custom_keys.append(next_map_key)
                        return next_map_key
    @property
    def get_available_map_key(self):
        if len(self.all_map) == 0 and len(self.temp_new_map_keys) == 0:
            self.temp_new_map_keys.append(f'map_{0}')
            return f'map_{0}'
        else:
            for i in range(len(self.all_map) + len(self.temp_new_map_keys)):
                next_map_key = f'map_{i + 1}'
                if not self.all_map.get(next_map_key, None):
                    if next_map_key not in self.temp_new_map_keys:
                        self.temp_new_map_keys.append(next_map_key)
                        return next_map_key
    @property
    def level_db(self):
        level_wrapper = self.world.level_wrapper
        if hasattr(level_wrapper, "level_db"):
            return level_wrapper.level_db
        else:
            return level_wrapper._level_manager._db

class SetFrames(wx.Panel, DefaultOperationUI):

    def __init__(
            self,
            parent: wx.Window,
            canvas: "EditCanvas",
            world: "BaseLevel",
            options_path: str,

    ):


        wx.Panel.__init__(self, parent)
        DefaultOperationUI.__init__(self, parent, canvas, world, options_path)
        self.platform = world.level_wrapper.platform
        self.world_version = world.level_wrapper.version

        if self.platform == 'bedrock':
            self.map_data_manager = BedrockMapData(parent=self, canvas=self.canvas, world=self.world)
        else:
            self.map_data_manager = JavaMapData(parent=self, canvas=self.canvas, world=self.world)
        self.fixed_frame = True
        self.invisible_frames = True
        self.back_block = None
        self.custom_map_loaded = False
        self.custom_map_wall = 'The Wall Data'
        self.color = (0, 0, 0, 0)
        self.pointer_shape = []
        self.progress = ProgressBar()
        self.Freeze()
        self.selected_block = None
        self.old_ponter_shape = None
        self._is_enabled = True
        self._moving = True

        self._sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self._sizer)

        self.button_menu_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.top_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.middle_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.bottom_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self._sizer.Add(self.button_menu_sizer)
        self._sizer.Add(self.top_sizer)
        self._sizer.Add(self.middle_sizer)
        self._sizer.Add(self.bottom_sizer)
        self.font = wx.Font(11, wx.FONTFAMILY_ROMAN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        self.SetFont(self.font)
        self.SetForegroundColour((0, 255, 0))
        self.SetBackgroundColour((0, 0, 0))
        self.selected_file = None
        self.frame_types = ["Glow Frame", "Regular Frame"]
        self.rb_frame_type = "Glow Frame"
        self._save_map_image = wx.Button(self, size=(70, 50), label="Save Map\n Image")
        self._save_map_image.Bind(wx.EVT_BUTTON, self.save_image_grid)
        self._save_map_image.Hide()
        self._go_to_maps = wx.Button(self, size=(70, 50), label="Go To\n Location")
        self._go_to_maps.Bind(wx.EVT_BUTTON, self.go_to_maps)
        self._go_to_maps.Hide()


        #self.top_sizer.Add(self.rb_frame_type, 0, wx.LEFT, 2)

        self.top_sizer.Add(self._go_to_maps, 0, wx.LEFT, 170)
        self.top_sizer.Add(self._save_map_image, 0, wx.LEFT, 5)
        real_maps = []
        if self.platform == 'java':
            real_maps = [x for x in self.map_data_manager.all_map.keys() if "map_-" not in x[0:5]]
        else:
            real_maps = [x for x in self.map_data_manager.all_map.keys() if "map_-" in x[0:5]]
        self._map_list = wx.ListBox(self, style=wx.LB_SINGLE, size=(175, 165),
                                    choices=real_maps)
        self._map_list.Bind(wx.EVT_LISTBOX, self.on_focus_map_list)

        self._custom_map_list = wx.ListBox(self, style=wx.LB_SINGLE, size=(175, 165),
                                           choices=[x for x in self.map_data_manager.custom_map.keys()])
        self._custom_map_list.Bind(wx.EVT_LISTBOX, self.on_focus_custom_map_list)

        self._import_image = wx.Button(self, size=(80, 50), label="Import \n and \n Settings")
        self._import_image.Bind(wx.EVT_BUTTON, self.import_image)

        self._del_sel_map = wx.Button(self, size=(80, 50), label="Delete \n Selected")
        self._del_sel_map.Bind(wx.EVT_BUTTON, self.del_sel_map)

        self._build_map_wall = wx.Button(self, size=(80, 50), label="Build \n Map Wall")
        self._build_map_wall.Bind(wx.EVT_BUTTON, self.build_map_wall)

        self._delete_all_maps = wx.Button(self, size=(80, 50), label="Delete All \n Maps")
        self._delete_all_maps.Bind(wx.EVT_BUTTON, self._run_del_maps)

        self.button_menu_sizer.Add(self._delete_all_maps, 0, wx.LEFT, 5)

        self.button_menu_sizer.Add(self._del_sel_map, 0, wx.LEFT, 5)
        self.button_menu_sizer.Add(self._build_map_wall, 0, wx.LEFT, 5)
        self.button_menu_sizer.Add(self._import_image, 0, wx.LEFT, 5)
       # self.button_menu_sizer.Add(self.apply_back_block, 0, wx.LEFT, 11)
        #self.button_menu_sizer.Add(self._set_images_on_frames, 0, wx.LEFT, 11)

        self.middle_sizer.Add(self._map_list)
        self.middle_sizer.Add(self._custom_map_list)

        self._up = wx.Button(self, label="up", size=(40, 20))
        self._up.Bind(wx.EVT_BUTTON, self._boxUp)
        self._down = wx.Button(self, label="down", size=(40, 20))
        self._down.Bind(wx.EVT_BUTTON, self._boxDown)
        self._east = wx.Button(self, label="east", size=(40, 20))
        self._east.Bind(wx.EVT_BUTTON, self._boxEast)
        self._west = wx.Button(self, label="west", size=(40, 20))
        self._west.Bind(wx.EVT_BUTTON, self._boxWest)
        self._north = wx.Button(self, label="north", size=(40, 20))
        self._north.Bind(wx.EVT_BUTTON, self._boxNorth)
        self._south = wx.Button(self, label="south", size=(40, 20))
        self._south.Bind(wx.EVT_BUTTON, self._boxSouth)

        self.move_grid = wx.GridSizer(3, 2, 1, 1)
        self.move_grid.Add(self._up)
        self.move_grid.Add(self._down)
        self.move_grid.Add(self._east)
        self.move_grid.Add(self._west)
        self.move_grid.Add(self._north)
        self.move_grid.Add(self._south)

        # Preview UI
        self.box = wx.BoxSizer(wx.VERTICAL)
        self.custom_name_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.label_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.grid_preview = wx.GridSizer(0, 0, 1, 1)

        self.box.Add(self.grid_preview, 0, wx.LEFT, 0)

        self.grid_options = wx.GridSizer(0, 3, 1, 1)
        self.button_grid_sizer = wx.BoxSizer(wx.VERTICAL)
        self.custom_map_name_label = wx.StaticText(self, label="Name Custom Map Entry:", size=(160, 25))
        self.custom_map_name = wx.TextCtrl(self, style=wx.TEXT_ALIGNMENT_LEFT)
        self.direction_label = wx.StaticText(self, label="Set The Orientation:↓", size=(125, 22))
        self.position_label = wx.StaticText(self, label="Fine Tune Box Area:↓", size=(129, 22))

        self.pointing = wx.ListBox(self, style=wx.LB_SINGLE, size=(115, 110),
                                   choices=[x for x in self.map_data_manager.pointing.keys()])

        self.facing = wx.ListBox(self, style=wx.LB_SINGLE, size=(115, 110),
                                 choices=[x for x in self.map_data_manager.facing.keys()])

        self.apply_preview = wx.Button(self, size=(80, 40), label="Place Image\n  On Frames")

        self.pointing.Bind(wx.EVT_LISTBOX, self.pointing_onclick)
        self.facing.Bind(wx.EVT_LISTBOX, self.facing_onclick)
        self.apply_preview.Bind(wx.EVT_BUTTON, self.apply_placement)
        self.custom_name_sizer.Add(self.custom_map_name_label)
        self.custom_name_sizer.Add(self.custom_map_name)
        self.label_sizer.Add(self.direction_label)
        self.label_sizer.Add(self.position_label, 0, wx.LEFT, 40)

        self.button_grid_sizer.Add(self.move_grid, 0, wx.TOP, 2)
        self.button_grid_sizer.Add(self.apply_preview, 0, wx.TOP, 6)

        self.grid_options.Add(self.pointing)
        self.grid_options.Add(self.facing)
        self.grid_options.Add(self.button_grid_sizer)

        self._sizer.Add(self.custom_name_sizer)
        self._sizer.Add(self.label_sizer)

        self._sizer.Add(self.grid_options, 0, wx.TOP, -3)
        self._sizer.Hide(self.custom_name_sizer)
        self._sizer.Hide(self.label_sizer)
        self._sizer.Hide(self.grid_options)

        self._sizer.Add(self.box)
        self._sizer.Fit(self)

        self.Layout()
        self.Thaw()

    def build_map_wall(self, _):
        map_data = []
        for name,file in self.map_data_manager.all_map.items() :
            if self.platform == 'java':
                if 'map_-' not in name:
                    nbt = load(file)
                    img = self.map_data_manager.get_map_img(nbt['data'].get('colors').py_data)
                    map_data.append((img, name))
            else:
                if 'map_-' in name:
                    nbt = self.map_data_manager.all_map[name]

                    img = self.map_data_manager.get_map_img(name)
                    map_data.append((img, name))



        BuildWallSettings(self, map_data ,world=self.world)

    def custom_map_wall_add(self):
        self.map_data_manager.refresh_all()
        self._map_list.SetSelection(-1)
        self._map_list.Hide()

        self._go_to_maps.Hide()

        self.clear_grid_preview()

        self.custom_map_loaded = True
        map_list, rows,cols = self.custom_map_wall
        print(self.custom_map_wall, 'yea', map_list, rows,cols)
        self.pointing.SetSelection(2)
        self.facing.SetSelection(2)
        self.map_data_manager.cols_rows = (cols, rows)
        self.selected_maps = map_list
        self.map_data_manager.maps_tobe = map_list
        self.map_data = []
        total = len(self.selected_maps)

        for m in self.selected_maps:
            # print(m,self.map_data_manager.all_map)
            self.map_data.append(self.map_data_manager.get_map_colors(m))

        def add_images(grid):
            cnt = 0
            for m in self.map_data:
                cnt += 1
                self.progress.progress_bar(total, cnt, text="Loading Map Images", title='Loading', update_interval=1)
                bb = wx.Bitmap.FromBufferRGBA(128, 128, m)
                grid.Add(wx.StaticBitmap(self, bitmap=scale_bitmap(bb, size, size)))
            return grid

        max_cell_width = 350 // cols
        max_cell_height = 350 // rows
        size = min(max_cell_width, max_cell_height)

        self.grid_preview.SetRows(rows)
        self.grid_preview.SetCols(cols)

        self.grid_preview = add_images(self.grid_preview)
        self.grid_preview.Fit(self)

        self._sizer.Show(self.custom_name_sizer)
        self._sizer.Show(self.label_sizer)
        self._sizer.Show(self.grid_options)
        self.shape_of_image()
        self._selection = StaticSelectionBehaviour(self.canvas)
        self._cursor = PointerBehaviour(self.canvas)
        self._selection.bind_events()
        self._cursor.bind_events()
        self.canvas.Bind(EVT_POINT_CHANGE, self._on_pointer_change)
        self.canvas.Bind(EVT_INPUT_PRESS, self._on_input_press)

        self._is_enabled = False
        self._moving = False
        self._map_list.Show()
        self.Fit()
        self.Update()
        self.Layout()

    def del_sel_map(self, _):
        if len(self._map_list.GetStringSelection()) > 0:
            map_ = self._map_list.GetStringSelection()
            self.map_data_manager.del_selected_map(map_)
        if len(self._custom_map_list.GetStringSelection()) > 0:
            cmap_ = self._custom_map_list.GetStringSelection()
            self.map_data_manager.del_selected_map(cmap_)
        self.map_data_manager.refresh_all()
        self._map_list.Update()
        self._custom_map_list.Update()
        self._map_list.Clear()
        self._custom_map_list.Clear()
        real_maps = None
        if self.platform == 'java':
            real_maps = [x for x in self.map_data_manager.all_map.keys() if "map_-" not in x[0:5]]
        else:
            real_maps = [x for x in self.map_data_manager.all_map.keys() if "map_-" in x[0:5]]
        self._custom_map_list.AppendItems([x for x in self.map_data_manager.custom_map.keys() ])

        self._map_list.AppendItems(real_maps)

    def apply_backblock(self, _):
        if self.pointer_shape and self.pointer_shape != (1, 1, 1):
            self.old_pointer_shape = copy.copy(self.pointer_shape)

        if not hasattr(self, 'window'):
            self._initialize_window()
            self._input_press_handler = functools.partial(self._on_input_press_block_define,
                                                          block_define=self._block_define)
            self.canvas.Bind(EVT_POINT_CHANGE, self._on_pointer_change_blk)
            self.canvas.Bind(EVT_INPUT_PRESS, self._input_press_handler)
            self._block_define.Bind(EVT_PROPERTIES_CHANGE, self._on_properties_change)
        else:

            self._input_press_handler = functools.partial(self._on_input_press_block_define, block_define=self._block_define)
            self.canvas.Bind(EVT_POINT_CHANGE, self._on_pointer_change_blk)
            self.canvas.Bind(EVT_INPUT_PRESS, self._input_press_handler)
            self._block_define.Bind(EVT_PROPERTIES_CHANGE, self._on_properties_change)
        # Show the window again if it was hidden
        self.pointer_shape = (1, 1, 1)
        self.window.Show()

    def _initialize_window(self):
        """Initialize the window and its components."""
        translation_manager = PyMCTranslate.new_translation_manager()
        self.window = wx.Frame(self, title="Choose back block", size=(500, 400),
                               style=wx.DEFAULT_FRAME_STYLE | wx.STAY_ON_TOP)
        self.window.Centre(direction=wx.VERTICAL)

        self._block_define = BlockDefine(self.window, translation_manager, wx.VERTICAL,
                                         platform=self.world.level_wrapper.platform)

        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.ok_sizer = wx.BoxSizer(wx.VERTICAL)
        self.window.SetSizer(self.sizer)
        self.ok_btn = wx.Button(self.window, label="OK", size=(100, 25))
        self.ok_btn.Bind(wx.EVT_BUTTON, self.done)

        # Set proportion to 0 to avoid stretching and align center
        self.ok_sizer.Add(self._block_define, 0, wx.LEFT, 0)
        self.ok_sizer.Add(self.ok_btn, 0, wx.ALIGN_CENTER)

        self.sizer.Add(self.ok_sizer, 1, wx.LEFT, 0)

        self.sizer.Fit(self.window)
        self.window.Layout()
        self._hide_version_select()
        self.window.Bind(wx.EVT_CLOSE, self._unbind_events)

    def done(self, _):
        self._unbind_events(None)

    def bind_events(self):
        super().bind_events()

        self.pointer_shape = (1, 1, 1)
        self._selection = StaticSelectionBehaviour(self.canvas)
        self._cursor = PointerBehaviour(self.canvas)
        self._selection.bind_events()
        self._cursor.bind_events()

        self.canvas.Bind(EVT_POINT_CHANGE, self._on_pointer_change)
        self.canvas.Bind(EVT_INPUT_PRESS, self._on_input_press)

        self._is_enabled = True
        self._moving = False

    def _unbind_events(self, event):

        self.canvas.Unbind(EVT_POINT_CHANGE, handler=self._on_pointer_change_blk)
        self.canvas.Unbind(EVT_INPUT_PRESS, handler=self._input_press_handler)
        self.canvas.Unbind(EVT_SELECTION_CHANGE)
        self._selection = StaticSelectionBehaviour(self.canvas)
        self._cursor = PointerBehaviour(self.canvas)
        self._selection.bind_events()
        self._cursor.bind_events()
        self.canvas.Bind(EVT_POINT_CHANGE, self._on_pointer_change)
        self.canvas.Bind(EVT_INPUT_PRESS, self._on_input_press)

        if hasattr(self, 'old_pointer_shape'):
            self.pointer_shape = self.old_pointer_shape

        self.window.Hide()  # Instead of destroying, just hide the window

    def _on_properties_change(self, event):
        """Handle the block properties change event."""
        self.get_block(event, self._block_define)

    def _on_selection_change(self, event):
        """Handle the selection change event."""
        self.set_block(event, self._block_define)

    def _hide_version_select(self):
        """Hide the VersionSelect component if it is shown."""
        for child in self._block_define.GetChildren():
            if isinstance(child, VersionSelect) and child.IsShown():
                child.Hide()

    def get_block(self, event, data):
        # print(data.block_name, data.properties)
        self.selected_block = data.block

        if self.world.level_wrapper.platform == 'bedrock':
            self.back_block = data.block
        else:
            block_data = CompoundTag({'Name': StringTag("minecraft:" + data.block_name)})
            if data.properties:
                block_data['Properties'] = CompoundTag(data.properties)
            self.back_block = block_data
        self.dlg.SetBlock(data.block_name)

    def set_block(self, event):
        x, y, z = self.canvas.selection.selection_group.min
        cx, cz = block_coords_to_chunk_coords(x, z)
        if self.world.has_chunk(cx, cz, self.canvas.dimension):
            block, enty = self.world.get_version_block(x, y, z, self.canvas.dimension,
                                                       (self.world.level_wrapper.platform,
                                                        self.world.level_wrapper.version))
            self.selected_block = block

            # if self.world.level_wrapper.platform == 'bedrock':
            #     self.back_block = block
            # else:
            #     block_data = CompoundTag({'Name': StringTag("minecraft:" + block.base_name)})
            #     if block.properties:
            #         block_data['Properties'] = CompoundTag(block.properties)
            #     self.back_block = block_data
            #     print(data.block_name, data.properties)

        event.Skip()

    def _on_pointer_change(self, evt: PointChangeEvent):

        if self._is_enabled:

            x, y, z = evt.point
            a, b, c = self.pointer_shape
            sg = SelectionGroup(SelectionBox((x, y, z), (x + a, y + b, z + c)))
            self.canvas.selection.set_selection_group(sg)

        evt.Skip()

    def _on_input_press_block_define(self, evt: InputPressEvent, block_define=None):

        if evt.action_id == ACT_BOX_CLICK:
            if block_define and self.selected_block:
                block_define.block = self.selected_block
                print(block_define.block)
            if self._is_enabled:

                self._moving = not self._moving
                self._is_enabled = False
                return

            if not self._is_enabled:
                self._is_enabled = True
                return
        evt.Skip()

    def import_image(self, evt):
        evt.Skip()
        self.dlg = ImportImageSettings(self, world=self.world)
        self.dlg.Show()
        # if dlg.ShowModal() == wx.ID_OK:
        #     r, g, b, a = dlg.GetSelectedColor()
        #     self.color = (r, g, b, a)
        
    def _on_pointer_change_blk(self, evt: PointChangeEvent):

        if self._is_enabled:
            self.set_block(evt)
            self.canvas.renderer.fake_levels.active_transform = evt.point
            x, y, z = evt.point
            a, b, c = self.pointer_shape
            sg = SelectionGroup(SelectionBox((x, y, z), (x + a, y + b, z + c)))

            self.canvas.selection.set_selection_group(sg)

        evt.Skip()
        
    def _on_input_press(self, evt: InputPressEvent):

        if evt.action_id == ACT_BOX_CLICK:

            if self._is_enabled:
                self._moving = not self._moving
                self._is_enabled = False
                return

            if not self._is_enabled:
                self._is_enabled = True
                return
        evt.Skip()

    def go_to_maps(self, _):
        lx, ly, lz, rx, ry, rz, cx, cy, cz, r1, r2 = self.selected_data
        self.canvas.selection.set_selection_group(SelectionGroup(SelectionBox((lx, ly, lz), (rx, ry, rz))))
        self.canvas.camera.location = (cx, cy, cz)
        self.canvas.camera.rotation = (r1, r2)

    def clear_grid_preview(self):
        sizer = self.grid_preview
        while sizer.GetItemCount() > 0:
            item = sizer.GetItem(0).GetWindow()
            sizer.Detach(0)
            if item:
                item.Destroy()

    def save_image_grid(self, _):
        grid_rows, grid_cols = self.grid_preview.GetRows(), self.grid_preview.GetCols()
        cmap = self._custom_map_list.GetStringSelection()
        imgs =self.map_data_manager.get_cmap_list_of_map_images(cmap)
        combined_img = Image.new('RGBA', (grid_cols * 128, grid_rows * 128))
        for index, img in enumerate(imgs):
            row = index // grid_cols
            col = index % grid_cols
            position = (col * 128, row * 128)
            combined_img.paste(img, position)

        with wx.FileDialog(self, "Save file", wildcard="PNG files (*.png)|*.png|All files (*.*)|*.*",
                           style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as save_dialog:

            # Show the dialog and check if the user clicked "Save"
            if save_dialog.ShowModal() == wx.ID_CANCEL:
                return  # User canceled, exit the function

            # Get the path selected by the user
            save_path = save_dialog.GetPath()
            combined_img.save(save_path, format='PNG')



    def on_focus_custom_map_list(self, evt):
        self.map_data_manager.refresh_all()
        self._map_list.SetSelection(-1)
        self._map_list.Hide()

        self._go_to_maps.Hide()

        self.clear_grid_preview()
        self._go_to_maps.Show()
        self._save_map_image.Show()
        self.custom_map_loaded = True

        custom_map_nbt = self.map_data_manager.get_custom_map_nbt(self._custom_map_list.GetStringSelection())
        lx, ly, lz, rx, ry, rz = custom_map_nbt.get('selectionGp').py_data
        cx, cy, cz = custom_map_nbt.get('location').py_data
        r1, r2 = custom_map_nbt.get('rotation').py_data
        self.selected_data = (lx, ly, lz, rx, ry, rz, cx, cy, cz, r1, r2)

        cols, rows = custom_map_nbt.get('cols').py_int, custom_map_nbt.get('rows').py_int
        pointing, facing = custom_map_nbt.get('pointing').py_int, custom_map_nbt.get('facing').py_int
        self.pointing.SetSelection(pointing)
        self.facing.SetSelection(facing)
        self.map_data_manager.cols_rows = (cols, rows)
        self.selected_maps = [s.py_str for s in custom_map_nbt.get('map_list').py_data]
        self.map_data = []
        total = len(self.selected_maps)

        for m in self.selected_maps:
            # print(m,self.map_data_manager.all_map)
            self.map_data.append(self.map_data_manager.get_map_colors(m))

        def add_images(grid):
            cnt = 0
            for m in self.map_data:
                cnt += 1
                self.progress.progress_bar(total, cnt, text="Loading Map Images", title='Loading', update_interval=1)
                bb = wx.Bitmap.FromBufferRGBA(128, 128, m)
                grid.Add(wx.StaticBitmap(self, bitmap=scale_bitmap(bb, size, size)))
            return grid

        max_cell_width = 350 // cols
        max_cell_height = 350 // rows
        size = min(max_cell_width, max_cell_height)

        self.grid_preview.SetRows(rows)
        self.grid_preview.SetCols(cols)

        self.grid_preview = add_images(self.grid_preview)
        self.grid_preview.Fit(self)

        self._sizer.Show(self.custom_name_sizer)
        self._sizer.Show(self.label_sizer)
        self._sizer.Show(self.grid_options)
        self.shape_of_image()
        self._selection = StaticSelectionBehaviour(self.canvas)
        self._cursor = PointerBehaviour(self.canvas)
        self._selection.bind_events()
        self._cursor.bind_events()
        self.canvas.Bind(EVT_POINT_CHANGE, self._on_pointer_change)
        self.canvas.Bind(EVT_INPUT_PRESS, self._on_input_press)

        self._is_enabled = False
        self._moving = False
        self._map_list.Show()
        self.Fit()
        self.Update()
        self.Layout()

        self.canvas.selection.set_selection_group(SelectionGroup(SelectionBox((lx, ly, lz), (rx, ry, rz))))

    def on_focus_map_list(self, evt):
        self.map_data_manager.refresh_all()
        self.Freeze()
        self._map_list.Hide()
        self._map_list.Show()
        self._go_to_maps.Show()
        self._go_to_maps.Hide()
        self._save_map_image.Hide()
        self._custom_map_list.SetSelection(-1)
        self.clear_grid_preview()
        self.grid_preview.Clear()
        selected_map = self._map_list.GetStringSelection()
        data_path = self.map_data_manager.all_map[selected_map]
        colors = self.map_data_manager.get_colors_from_map(data_path)
        bb = wx.Bitmap.FromBufferRGBA(128, 128, colors)
        img = wx.StaticBitmap(self, bitmap=scale_bitmap(bb, 256, 256))
        self.grid_preview.SetRows(1)
        self.grid_preview.SetCols(1)
        self.grid_preview.Add(img)

        self.grid_preview.Fit(self)
        self._sizer.Layout()  # Update layout of the parent sizer
        self.Fit()  # Adjust the size of the window to fit its content
        self.Layout()
        self.Thaw()

    def _refresh_chunk(self, dimension, world, x, z):
        cx, cz = block_coords_to_chunk_coords(x, z)
        chunk = world.get_chunk(cx, cz, dimension)
        chunk.changed = True

    def set_images_on_frames(self, event):
        self.box.Hide(self.grid_preview)
        self.custom_map_loaded = False
        self.map_data_manager.refresh_all()


        image = Image.open(self.selected_file).convert("RGBA")

        cols, rows = ceil(image.size[0] / 128), ceil(image.size[1] / 128)
        self.map_data_manager.cols_rows = (cols, rows)
        self.process_image(image)
        self.preview_ui()

    def preview_ui(self):

        self.map_data_manager.convert_images()
        def add_images(grid):
            for v in self.map_data_manager.maps_tobe:
                bb = wx.Bitmap.FromBufferRGBA(128, 128, v[0])
                grid.Add(wx.StaticBitmap(self, bitmap=scale_bitmap(bb, size, size)))
            return grid

        cols, rows = self.map_data_manager.cols_rows
        max_cell_width = 350 // cols
        max_cell_height = 350 // rows
        size = min(max_cell_width, max_cell_height)
        self.grid_preview.Hide(self, recursive=True)
        self.grid_preview.Clear()
        self.grid_preview.SetRows(rows)
        self.grid_preview.SetCols(cols)
        self.grid_preview = add_images(self.grid_preview)

        self.grid_preview.Fit(self)

        self._sizer.Show(self.custom_name_sizer)
        self._sizer.Show(self.label_sizer)
        self._sizer.Show(self.grid_options)

        self.pointing.SetSelection(2)
        self.facing.SetSelection(2)
        self._sizer.Layout()  # Update layout of the parent sizer
        self.Fit()  # Adjust the size of the window to fit its content
        self.Layout()  # Adjust the layout of the window
        self.shape_of_image()
        self._selection = StaticSelectionBehaviour(self.canvas)
        self._cursor = PointerBehaviour(self.canvas)
        self._selection.bind_events()
        self._cursor.bind_events()
        self.canvas.Bind(EVT_POINT_CHANGE, self._on_pointer_change)
        self.canvas.Bind(EVT_INPUT_PRESS, self._on_input_press)

        self._is_enabled = True
        self._moving = True

    def shape_of_image(self):
        dimensions = self.map_data_manager.cols_rows
        current_facing_direction, pointed_direction = self.facing.GetSelection(), self.pointing.GetSelection()
        if (pointed_direction in [1, 3]) and (current_facing_direction <= 1):
            self.pointer_shape = ((dimensions[1]), 1, (dimensions[0]))
        elif (pointed_direction in [0, 2]) and (current_facing_direction <= 1):
            self.pointer_shape = ((dimensions[0]), 1, (dimensions[1]))
        elif (pointed_direction in [0, 1]) and (2 <= current_facing_direction < 4):
            self.pointer_shape = ((dimensions[1]), (dimensions[0]), 1)
        elif (pointed_direction in [2, 3]) and (2 <= current_facing_direction < 4):
            self.pointer_shape = ((dimensions[0]), (dimensions[1]), 1)
        elif (pointed_direction in [0, 1]) and (current_facing_direction >= 4):
            self.pointer_shape = (1, (dimensions[0]), (dimensions[1]))
        elif (pointed_direction in [2, 3]) and (current_facing_direction >= 4):
            self.pointer_shape = (1, (dimensions[1]), (dimensions[0]))

    def pointing_onclick(self, _):

        self.shape_of_image()
        self._is_enabled = True
        self._moving = True

    def facing_onclick(self, _):
        facing_selected = self.facing.GetSelection()
        pointing_selected = self.pointing.GetSelection()
        if facing_selected <= 1:
            self.pointing.Clear()
            self.pointing.AppendItems(["Top Image North", "Top Image East", "Top Image South", "Top Image West"])
            self.pointing.SetSelection(pointing_selected)
        elif facing_selected >= 2:
            self.pointing.Clear()
            self.pointing.AppendItems(["Flip Right", "Flip Left", "Up (Like Preview)", "Upside Down"])
            self.pointing.SetSelection(pointing_selected)

        self.shape_of_image()
        self._is_enabled = True
        self._moving = True

    def apply_placement(self, _):
        if self.custom_map_loaded:
            self.boxSetter(map_key_list=self.selected_maps)
        else:
            self.boxSetter()

    def process_image(self, image, tile_size=128):
        color = self.color
        image_array = numpy.array(image)
        height, width = image_array.shape[:2]
        new_height = (height + tile_size - 1) // tile_size * tile_size
        new_width = (width + tile_size - 1) // tile_size * tile_size
        new_image_array = numpy.full((new_height, new_width, 4), color, dtype=numpy.uint8)
        pad_top = (new_height - height) // 2
        pad_left = (new_width - width) // 2
        new_image_array[pad_top:pad_top + height, pad_left:pad_left + width] = image_array

        for y in range(0, new_height, tile_size):
            for x in range(0, new_width, tile_size):
                tile = new_image_array[y:y + tile_size, x:x + tile_size]
                flattened_pixels = tile.reshape(-1).tobytes()
                self.map_key = self.map_data_manager.get_available_map_key
                print(self.map_key)
                map_id = int(self.map_key.replace('map_', ''))
                self.map_data_manager.maps_tobe.append((flattened_pixels, map_id, self.map_key))

    def boxSetter(self, map_key_list=None):
        self.map_data_manager.apply(map_key_list=map_key_list)

    def reorder_coordinates(self ):
        pointing_value, facing_value = self.pointing.GetSelection(), self.facing.GetSelection()
        cords = []
        for x, y, z in self.canvas.selection.selection_group.blocks:
            cords.append((x, y, z))
        transformation_data = {
            # Facing Down
            (0, 0): (2, 0, 270, False, [0]),  # North or Right
            (0, 1): (0, 2, 225, False, [0, 2]),  # East or Left
            (0, 2): (2, 0, 180, True, [0]),  # South or Up
            (0, 3): (0, 2, 315, True, [0, 2]),  # West or Down
            # Facing Up
            (1, 0): (2, 0, 0, False, None),  # North or Right
            (1, 1): (0, 2, 225, False, [0]),  # East or Left
            (1, 2): (2, 0, 270, True, None),  # South or Up
            (1, 3): (0, 2, 315, True, [0]),  # West or Down
            # Facing North
            (2, 0): (0, 1, 225, False, [1]),  # North or Right
            (2, 1): (0, 1, 315, True, [1]),  # East or Left
            (2, 2): (1, 0, 180, True, None),  # South or Up
            (2, 3): (1, 0, 270, False, None),  # West or Down
            # Facing South
            (3, 0): (0, 1, 45, False, [1, 0]),  # North or Right
            (3, 1): (0, 1, 315, True, [1, 0]),  # East or Left
            (3, 2): (1, 0, 0, True, [0]),  # South or Up
            (3, 3): (1, 0, 270, False, [0]),  # West or Down
            # Facing West
            (4, 0): (2, 1, 225, False, [1, 2]),  # North or Right
            (4, 1): (2, 1, 315, True, [1, 2]),  # East or Left
            (4, 2): (1, 2, 180, True, [2]),  # South or Up
            (4, 3): (1, 2, 270, False, [2]),  # West or Down
            # Facing East
            (5, 0): (2, 1, 45, False, [1]),  # North or Right
            (5, 1): (2, 1, 315, True, [1]),  # East or Left
            (5, 2): (1, 2, 180, True, None),  # South or Up
            (5, 3): (1, 2, 270, False, None),  # West or Down
        }

        primary_sort_axis, secondary_sort_axis, rotation, reverse, axis_reverse = (
            transformation_data)[(facing_value, pointing_value)]

        coords_array = numpy.array(cords)
        coords_array = coords_array[
            numpy.lexsort((coords_array[:, secondary_sort_axis], coords_array[:, primary_sort_axis]))]

        if axis_reverse:
            for x in axis_reverse:
                coords_array[:, x] = coords_array[:, x][::-1]
        if reverse:
            coords_array = coords_array[::-1]

        cords_sorted = [tuple(coord) for coord in coords_array]
        return cords_sorted, rotation

    def _run_del_maps(self, _):

        wxx = wx.MessageBox("You are going to deleted EVERY MAP \n Every entry in the list",
                            "This can't be undone Are you Sure?", wx.OK | wx.CANCEL | wx.ICON_INFORMATION)
        if wxx == int(16):
            return
        self.Freeze()
        self.map_data_manager.delete_all_maps()
        self.map_data_manager.refresh_all()
        self._map_list.Update()
        self._custom_map_list.Update()
        self._map_list.Clear()
        self._custom_map_list.Clear()
        self._custom_map_list.AppendItems([x for x in self.map_data_manager.custom_map.keys()])
        self._map_list.AppendItems([x for x in self.map_data_manager.all_map.keys()])
        self.clear_grid_preview()
        self.grid_preview.Hide(self, recursive=True)
        self.grid_preview.Clear()
        self._sizer.Hide(self.custom_name_sizer)
        self._sizer.Hide(self.label_sizer)
        self._sizer.Hide(self.grid_options)
        self._sizer.Fit(self)
        self.Fit()
        self.Layout()
        self.Thaw()

    def _move_box(self, dx=0, dy=0, dz=0):
        for box in self.canvas.selection.selection_group.selection_boxes:
            xx, yy, zz = box.max_x, box.max_y, box.max_z
            xm, ym, zm = box.min_x, box.min_y, box.min_z
            sg = SelectionGroup(SelectionBox((xm + dx, ym + dy, zm + dz), (xx + dx, yy + dy, zz + dz)))
            self.canvas.selection.set_selection_group(sg)

    def _boxUp(self, _):
        self._move_box(dy=1)

    def _boxDown(self, _):
        self._move_box(dy=-1)

    def _boxNorth(self, _):
        self._move_box(dz=-1)

    def _boxSouth(self, _):
        self._move_box(dz=1)

    def _boxEast(self, _):
        self._move_box(dx=1)
        for box in self.canvas.selection.selection_group.selection_boxes:
            xx, yy, zz = box.max_x + 1, box.max_y, box.max_z  # Reflect the updated position
            self.pointer_shape = [xx, yy, zz]

    def _boxWest(self, _):
        self._move_box(dx=-1)

export = dict(name="Image or Maps to Frames Plugin V2.0b", operation=SetFrames)  # by PreimereHell
