#By PremiereHell  ,
# Thanks To Ben #Podshot https://github.com/Podshot ,
# For the NBT Editor, without his code this would not exist.
#
# used some code from the WxPython wiki:
# Thanks To Rob and Titus for Drag And Drop Sample Code
# https://wiki.wxpython.org/DragAndDropWithFolderMovingAndRearranging
# Sample and NBT_Editor Updated and Edited By #PremiereHell

# Thanks To StealthyX https://github.com/StealthyExpertX/Amulet-Plugins
# For Getting me started on this, He provided some code that got me started on this.
from __future__ import annotations
import math
import time
import struct

import amulet_nbt
from amulet_map_editor.programs.edit.api.events import (
    EVT_SELECTION_CHANGE,
)
import copy
from functools import partial, reduce
import operator
from collections.abc import MutableMapping, MutableSequence
import wx
from amulet_map_editor.api.wx.ui import simple
from amulet_map_editor.api import image
nbt_resources = image.nbt
import re
import abc
import collections
import os
from os.path import exists
import numpy
import uuid
from amulet.api.block_entity import BlockEntity
from amulet.api.block import Block
from typing import TYPE_CHECKING, Type, Any, Callable, Tuple, BinaryIO, Optional, Union
from amulet.utils import world_utils
from amulet_map_editor.api.opengl.camera import Projection
from amulet_map_editor.programs.edit.api.behaviour import BlockSelectionBehaviour
from amulet.api.selection import SelectionGroup
from amulet.api.selection import SelectionBox
from amulet.utils import block_coords_to_chunk_coords
from amulet.level.formats.anvil_world.region import AnvilRegion
from amulet_map_editor.programs.edit.api.operations import DefaultOperationUI
from amulet_map_editor.api.wx.ui.base_select import BaseSelect
from amulet.api.errors import ChunkDoesNotExist
import amulet_nbt as nbt

if TYPE_CHECKING:
    from amulet.api.level import BaseLevel
    from amulet_map_editor.programs.edit.api.canvas import EditCanvas

class MyTreeCtrl(wx.TreeCtrl):
    def __init__(self, parent, id, pos, size, style, nbt_data):
        wx.TreeCtrl.__init__(self, parent, id, pos, size, style)
        self.nbt_data = nbt_data

    def Traverse(self, func, startNode):
        def TraverseAux(node, depth, func):
            nc = self.GetChildrenCount(node, 0)
            child, cookie = self.GetFirstChild(node)
            # In wxPython 2.5.4, GetFirstChild only takes 1 argument
            for i in range(nc):
                func(child, depth)
                TraverseAux(child, depth + 1, func)
                child, cookie = self.GetNextChild(node, cookie)


        func(startNode, 0)
        TraverseAux(startNode, 1, func)

    def ItemIsChildOf(self, item1, item2):
        self.result = False
        def test_func(node, depth):
            if node == item1:
                self.result = True
        self.Traverse(test_func, item2)
        return self.result

    def SaveItemsToList(self, startnode):
        global lista
        lista = []

        def save_func(node, depth):
            tmplist = lista
            for x in range(depth):
                if type(tmplist[-1]) is not dict:
                    tmplist.append({})
                tmplist = tmplist[-1].setdefault('children', [])

            item = {}
            item['label'] = self.GetItemText(node)
            item['data'] = self.GetItemData(node)
            item['icon-normal'] = self.GetItemImage(node, wx.TreeItemIcon_Normal)
            item['icon-selected'] = self.GetItemImage(node, wx.TreeItemIcon_Selected)
            item['icon-expanded'] = self.GetItemImage(node, wx.TreeItemIcon_Expanded)
            item['icon-selectedexpanded'] = self.GetItemImage(node, wx.TreeItemIcon_SelectedExpanded)

            tmplist.append(item)

        self.Traverse(save_func, startnode)
        return lista

    def OnCompareItems(self, item1, item2):
        t1 = self.GetItemText(item1)
        t2 = self.GetItemText(item2)

        if t1 < t2: return -1
        if t1 == t2: return 0
        return 1

    def InsertItemsFromList(self, itemlist, parent, insertafter=None, appendafter=False):
        newitems = []
        for item in itemlist:
            if insertafter:
                node = self.InsertItem(parent, insertafter, item['label'])
            elif appendafter:
                node = self.AppendItem(parent, item['label'])
            else:
                node = self.PrependItem(parent, item['label'])
            self.SetItemData(node, item['data'])
            self.SetItemImage(node, item['icon-normal'], wx.TreeItemIcon_Normal)
            self.SetItemImage(node, item['icon-selected'], wx.TreeItemIcon_Selected)
            self.SetItemImage(node, item['icon-expanded'], wx.TreeItemIcon_Expanded)
            self.SetItemImage(node, item['icon-selectedexpanded'], wx.TreeItemIcon_SelectedExpanded)

            newitems.append(node)
            if 'children' in item:
                self.InsertItemsFromList(item['children'], node, appendafter=True)
        return newitems

    def loop_all_tree_keys(self):
        root = self.GetRootItem()
        nc = self.GetChildrenCount(root, 0)
        child, cookie = self.GetFirstChild(root)
        orderit = []
        orderit.append(self.GetItemData(child)[0])
            # In wxPython 2.5.4, GetFirstChild only takes 1 argument
        for i in range(nc):
            child, cookie = self.GetNextChild(child, cookie)
            if child.IsOk():
                orderit.append(self.GetItemData(child)[0])
            else:
                break
        return orderit



class SmallEditDialog(wx.Frame):
    GRID_ROWS = 2
    GRID_COLUMNS = 2

    def __init__(
            self, parent, oper_name, tag_type_name, item, tree, bitmap_icon,image_map
    ):
        super(SmallEditDialog, self).__init__(
            parent, title=f"{oper_name} {tag_type_name}", size=(400, 200)
        )
        if bitmap_icon:
            if isinstance(bitmap_icon, wx.Icon):
                self.SetIcon(bitmap_icon)
            else:
                self.SetIcon(wx.Icon(bitmap_icon))
        self.Centre(50)

        if "SNBT" not in tag_type_name:
            self.image_map = image_map
            self.tree = tree

            self.text = self.tree.GetItemText(item)
            self.data = self.tree.GetItemData(item)
            main_panel = simple.SimplePanel(self)
            button_panel = simple.SimplePanel(main_panel, sizer_dir=wx.HORIZONTAL)
            name_panel = simple.SimplePanel(main_panel, sizer_dir=wx.HORIZONTAL)
            value_panel = simple.SimplePanel(main_panel, sizer_dir=wx.HORIZONTAL)
            name_label = wx.StaticText(name_panel, label="Name: ")
            value_label = wx.StaticText(value_panel, label="Value: ")

            self.name_field = wx.TextCtrl(name_panel)
            self.value_field = wx.TextCtrl(value_panel)
            name_panel.add_object(name_label, space=0, options=wx.ALL | wx.CENTER)
            name_panel.add_object(self.name_field, space=1, options=wx.ALL | wx.EXPAND)



            meta = False
            if isinstance(self.data, tuple):
                name, data = self.data
            else:
                name, data = None, self.data
            if isinstance(data, abc.ABCMeta):
                meta = True
            final_name, final_value = None, None
            self.name_field.Disable(), self.value_field.Disable()
            if oper_name == "Add":
                self.name_field.Enable(), self.value_field.Enable()
                f_child = self.tree.GetFirstChild(item)[0]
                if f_child.IsOk():
                    if isinstance(self.tree.GetItemData(f_child), tuple):
                        name, type_t = self.tree.GetItemData(f_child)
                        self.name_field.SetValue("")
                        self.value_field.SetValue("")
                    else:
                        type_t = self.tree.GetItemData(f_child)
                        self.name_field.Disable()
                        self.value_field.SetValue("")
            else:
                if name:
                    self.name_field.SetValue(name)
                    self.name_field.Enable()
                if not meta:
                    self.value_field.SetValue(str(data.value))
                    self.value_field.Enable()
                else:
                    if name:
                        self.name_field.SetValue(name)
                        self.value_field.SetValue(str(data))

            value_panel.add_object(value_label, space=0, options=wx.ALL | wx.CENTER)
            value_panel.add_object(self.value_field, space=1, options=wx.ALL | wx.EXPAND)
            self.save_button = wx.Button(button_panel, label=oper_name)
            self.cancel_button = wx.Button(button_panel, label="Cancel")
            button_panel.add_object(self.save_button, space=0)
            button_panel.add_object(self.cancel_button, space=0)
            main_panel.add_object(name_panel, space=0, options=wx.ALL | wx.EXPAND)
            main_panel.add_object(value_panel, space=0, options=wx.ALL | wx.EXPAND)
            main_panel.add_object(button_panel, space=0)
            self.save_button.Bind(wx.EVT_BUTTON, lambda evt:
            self.add_edit(evt, oper_name, self.data, item, tag_type_name))
            self.save_button.Bind(wx.EVT_KEY_UP, lambda evt:
            self.key_down_enter(evt, oper_name, self.data, item, tag_type_name))
            self.name_field.Bind(wx.EVT_KEY_UP, lambda evt:
            self.key_down_enter(evt, oper_name, self.data, item, tag_type_name))
            self.value_field.Bind(wx.EVT_KEY_UP, lambda evt:
            self.key_down_enter(evt, oper_name, self.data, item, tag_type_name))
            self.cancel_button.Bind(wx.EVT_BUTTON, lambda evt: self.Close())
            self.Layout()
        else:
            self.tree = tree
            self.SetSize(600,700)
            main_panel = simple.SimplePanel(self)
            button_panel = simple.SimplePanel(main_panel, sizer_dir=wx.HORIZONTAL)
            value_panel = simple.SimplePanel(main_panel, sizer_dir=wx.HORIZONTAL)
            self.value_field = wx.TextCtrl(value_panel, style=wx.TE_MULTILINE, size=(577,640))
            self.value_field.SetBackgroundColour((0,0,0))
            self.value_field.SetForegroundColour((0, 255, 255))
            font = wx.Font(14, wx.FONTFAMILY_ROMAN, wx.FONTSTYLE_MAX, wx.FONTWEIGHT_BOLD)
            self.value_field.SetFont(font)
            value_panel.add_object(self.value_field)
            self.save_button = wx.Button(button_panel, label="Save")
            self.save_button.Bind(wx.EVT_BUTTON, lambda evt:
            self.update_tree(evt))
            button_panel.add_object(self.save_button)
            self.f_path, self.raw_nbt, sel_snbt = NBTEditor.build_to(self.Parent, None, opt="snbt" )
            self.value_field.SetValue(sel_snbt)

            main_panel.add_object(value_panel, options=wx.EXPAND)
            main_panel.add_object(button_panel, space=0)


            self.Layout()


    def update_tree(self, evt):
        def get_real_nbt(map_list):
            return reduce(operator.getitem, map_list[:-1], self.raw_nbt)
        updated_nbt = get_real_nbt(self.f_path)
        if len(self.f_path) == 0:
            self.raw_nbt = nbt.from_snbt(self.value_field.GetValue())
        else:
            updated_nbt[self.f_path[-1]] = nbt.from_snbt(self.value_field.GetValue())

        EntitiePlugin.update_player_data(self, self.raw_nbt)
        # print("UPDATE",self.raw_nbt)


    def nbt_clean_array_string(self, strr, ntype):
        import re
        dtyped = {"L": "longs","B": "bytes","I": "ints"}
        dtype = dtyped[ntype]
        prog = re.compile(r'(\d*[.-]?\d*)', flags=0)
        result, new_string = (prog.findall(strr), '')
        for x in result:
            if x != '':
                new_string += f"{x}{ntype.replace('I', '')}, "
        new_string = f"[{ntype};{new_string[:-2]}]"
        return nbt.from_snbt(new_string), dtype

    def key_down_enter(self, evt, oper_name, data, item, tag_type_name):
        keycode = evt.GetKeyCode()
        if keycode == 13 or keycode == 370:
            self.add_edit(evt, oper_name, data, item, tag_type_name)

    def add_edit(self, evt, oper_name, data, item, tag_type_name):
        def set_data_tree(data):
            name, meta = None, False
            key, value = self.name_field.GetValue(), self.value_field.GetValue()
            set_string = f"{key}: {value}"
            if isinstance(data, tuple):
                name, data = data
            if isinstance(data, abc.ABCMeta):
                data, meta = data(), True
            tag_type = [tag_class for tag_class in self.image_map if tag_class.__name__ ==
                        tag_type_name.replace(" ", "")][0]
            set_data = tag_type(data)
            if isinstance(data, (nbt.IntArrayTag, nbt.LongArrayTag, nbt.ByteArrayTag)):
                value, tipe = self.nbt_clean_array_string(value, str(type(data)).split(".")[-1][0])
                t_value, entries = '' if meta else value, len(value)
                set_string = f"{key}:{t_value} [{entries} {tipe}]" if name else f"{t_value}:[{entries} {tipe}]"
                set_data = (key, value) if name else value
            elif isinstance(data, (nbt.ListTag, nbt.CompoundTag)):
                entries = self.tree.GetChildrenCount(item, 0)
                t_value = '' if meta else value
                set_string = f"{key}:{t_value} entries {entries}" if name else f"{t_value} entries {entries}"

                set_data = (key, tag_type) if name else tag_type
            else:
                t_value = '' if meta else value
                set_string = f"{key}:{t_value}" if name else f"{t_value}"
                set_data = (key, tag_type(value)) if name else tag_type(value)
            self.tree.SetItemText(item, set_string)

            self.tree.SetItemData(item, set_data)
            entries = self.tree.GetChildrenCount(item, 0)

        def add_data_tree(item, data):
            tag_type_data = [tag_class for tag_class in self.image_map if tag_class.__name__ ==
                             tag_type_name.replace(" ", "")][0]
            self.other = self.image_map[nbt.TAG_String]
            name, meta = None, False
            name, value = self.name_field.GetValue(), self.value_field.GetValue()
            if name == '':
                name = None

            tipe = data[1] if isinstance(data, tuple) else  data

            entries = 0
            set_string = f"{name}: {value}"

            if isinstance(tag_type_data(), (nbt.IntArrayTag, nbt.LongArrayTag, nbt.ByteArrayTag)):
                value, tipe = self.nbt_clean_array_string(value, str(type(tag_type_data())).split(".")[-1][0])
                t_value, entries = '' if meta else value, len(value)
                set_string = f"{name}:{t_value} [{entries} {tipe}]" if name else f"{t_value}:[{entries} {tipe}]"
                set_data = (name, value) if name else value
            elif isinstance(tag_type_data(), (nbt.ListTag, nbt.CompoundTag)):
                if isinstance(tipe, nbt.ListTag):
                    set_string = f"{name} entries {entries}" if name else f"entries {entries}"
                    set_data = (name, tag_type_data(value)) if name else tag_type_data(value)
                else:
                    set_string = f"{name} entries {entries}" if name else f"entries {entries}"
                    set_data = (name, tag_type_data(value)) if name else tag_type_data(value)
            else:
                if isinstance(tipe, nbt.ListTag):#????????????????????????????????????
                    set_string = f"{name}:{value}" if name else f"{value}"
                    set_data = (name, tag_type_data(value)) if name else tag_type_data(value)
                else:
                    set_string = f"{name}:{value}" if name else f"{value}"
                    set_data = (name, tag_type_data(value)) if name else tag_type_data(value)

            new_child = self.tree.AppendItem(item, set_string)
            self.tree.SetItemData(new_child, set_data)
            self.tree.SetItemImage(
                new_child,
                self.image_map.get(tag_type_data().__class__, self.other),
                wx.TreeItemIcon_Normal,
            )
            entries = self.tree.GetChildrenCount(item, 0)
            testdata = self.tree.GetItemText(item)
            self.tree.SetItemText(item, testdata.replace(f"{entries-1} entries",f"{entries} entries"))

        if oper_name == "Edit":
            set_data_tree(data)
        elif oper_name == "Add":
            add_data_tree(item, data)
        self.Close()

    def value_changed(self, evt):
        tag_value = evt.GetString()
        self.value_field.ChangeValue(str(self.data_type_func(tag_value)))


    def change_tag_type_func(self, tag_type, name_value=[False,False]):
        #self.data_type_func = lambda x: x
        if name_value[0]:
            self.name_field.Disable()
        if name_value[1]:
            self.value_field.Disable()
        if tag_type in ("IntTag", "LongTag", "ShortTag", "ByteTag"):
            self.data_type_func = lambda x: int(float(x))
            self.value_field.Enable()

        elif tag_type in ("FloatTag", "DoubleTag"):
            self.data_type_func = lambda x: str(float(x))
            self.value_field.Enable()

        if tag_type in ("ByteArrayTag", "IntArrayTag", "LongArrayTag"):
            self.value_field.ChangeValue(
                str("[0 0 0]")
            )
            self.value_field.Enable()
        if tag_type in ("NamedTag", "CompoundTag"):
            self.value_field.ChangeValue(
                str("")
            )

    def get_selected_tag_type(self):
        for rd_btn in self.radio_buttons:
            if rd_btn.GetValue():
                return rd_btn.nbt_tag_class
        return None

    def save(self, evt):
        self.save_callback(
            self.name_field.GetValue(),
            self.data_type_func(self.value_field.GetValue()),
            self.get_selected_tag_type(),
            self.old_name,
        )
        self.Close()

class NBTEditor(wx.Panel):
    def __init__(self, parent,  nbt_data=nbt.CompoundTag(), root_tag_name="", callback=None,):
        # super(NBTEditor, self).__init__(parent)
        # Use the WANTS_CHARS style so the panel doesn't eat the Return key.
        wx.Panel.__init__(self, parent)
        self.sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.SetSizer(self.sizer)
      #  self.SetSize(600, 650)
        self.nbt_new = nbt.CompoundTag()
        self.nbt_data = nbt_data
        self.copy_data = None
        self.image_list = wx.ImageList(32, 32)
        self.image_map = {
            nbt.TAG_Byte: self.image_list.Add(self.resize_resorce(nbt_resources.nbt_tag_byte.bitmap())),
            nbt.TAG_Short: self.image_list.Add(self.resize_resorce(nbt_resources.nbt_tag_short.bitmap())),
            nbt.TAG_Int: self.image_list.Add(self.resize_resorce(nbt_resources.nbt_tag_int.bitmap())),
            nbt.TAG_Long: self.image_list.Add(self.resize_resorce(nbt_resources.nbt_tag_long.bitmap())),
            nbt.TAG_Float: self.image_list.Add(self.resize_resorce(nbt_resources.nbt_tag_float.bitmap())),
            nbt.TAG_Double: self.image_list.Add(self.resize_resorce(nbt_resources.nbt_tag_double.bitmap())),
            nbt.TAG_String: self.image_list.Add(self.resize_resorce(nbt_resources.nbt_tag_string.bitmap())),
            nbt.TAG_Compound: self.image_list.Add(
                self.resize_resorce(nbt_resources.nbt_tag_compound.bitmap())
            ),
            nbt.NamedTag: self.image_list.ImageCount - 1,
            nbt.TAG_List: self.image_list.Add(self.resize_resorce(nbt_resources.nbt_tag_list.bitmap())),
            nbt.TAG_Byte_Array: self.image_list.Add(
                self.resize_resorce(nbt_resources.nbt_tag_array.bitmap())
            ),
            nbt.TAG_Int_Array: self.image_list.ImageCount - 1,
            nbt.TAG_Long_Array: self.image_list.ImageCount - 1,
        }
        self.other = self.image_map[nbt.TAG_String]
        self.tree = self.build_tree(nbt_data)
        self.callback = callback

    def resize_resorce(self, img_path):
        image = img_path.ConvertToImage()
        image = image.Scale(32, 32, wx.IMAGE_QUALITY_HIGH)
        result = wx.Bitmap(image)
        return result

    def build_to(self, evt, opt='raw'):
        tree = self.tree

        # def get_full_path(child):
        #     index = 0
        #     p_type = None
        #     the_sib_items = []
        #     nbt_path_keys = []
        #     if isinstance(tree.GetItemData(child), tuple):
        #         name, data = tree.GetItemData(child)
        #         nbt_path_keys.append(name)
        #     sibl = tree.GetItemParent(child)
        #     while sibl.IsOk():
        #         # print("____",tree.GetItemData(sibl))
        #         the_sib_items.append(sibl)
        #         if isinstance(tree.GetItemData(sibl), tuple):
        #             p_type = tree.GetItemData(sibl)[1]
        #         else:
        #             p_type = tree.GetItemData(sibl)
        #         print(root_path(tree.GetFocusedItem()))
        #         if p_type == nbt.ListTag:
        #             item_num = tree.GetChildrenCount(sibl, recursively=True)
        #             f_child, f_c = tree.GetFirstChild(sibl)
        #             f_item = tree.GetFocusedItem()
        #             if f_child.IsOk():
        #                 for c in range(item_num):
        #                     if f_child.IsOk():
        #
        #                         if f_child == f_item:
        #                             index = c
        #                             break
        #                         f_child, f_c = tree.GetNextChild(f_child, f_c)
        #
        #             nbt_path_keys.append(index)
        #         if isinstance(tree.GetItemData(sibl), tuple):
        #             nname, ddata = tree.GetItemData(sibl)
        #             nbt_path_keys.append(nname)
        #         sibl = tree.GetItemParent(sibl)
        #     nbt_path_keys.reverse()
        #
        #     return nbt_path_keys[1:]

        def root_path(child):
            nbt_path_keys = []
            if isinstance(tree.GetItemData(child), tuple):
                name, data = tree.GetItemData(child)
                nbt_path_keys.append(name)
            sibl = tree.GetItemParent(child)
            while sibl.IsOk():

                if isinstance(tree.GetItemData(sibl), tuple):
                    nname, ddata = tree.GetItemData(sibl)
                    if ddata == nbt.ListTag:

                        index = 0
                        item_num = tree.GetChildrenCount(sibl, recursively=False)
                        f_child, f_c = tree.GetFirstChild(sibl)
                        f_item = tree.GetFocusedItem()
                        f_par = tree.GetItemParent(f_item)
                        if len(nbt_path_keys) > 0:
                            for xx in range(len(nbt_path_keys)-1):
                                f_par = tree.GetItemParent(f_par)
                        else:
                            f_par = tree.GetFocusedItem()
                        for c in range(item_num):
                            if f_child == f_par:
                                index = c
                                nbt_path_keys.append(index)
                            f_child, f_c = tree.GetNextChild(f_child, f_c)
                    nbt_path_keys.append(nname)
                # else:
                #     index = 0
                #     nname, ddata = "", tree.GetItemData(sibl)
                #     if ddata == nbt.ListTag:
                #         print("????", nname)
                #         index = 0
                #         item_num = tree.GetChildrenCount(sibl, recursively=False)
                #         f_child, f_c = tree.GetFirstChild(sibl)
                #         f_item = tree.GetFocusedItem()
                #         f_par = tree.GetItemParent(f_item)
                #         for xx in range(len(nbt_path_keys)):
                #             f_par = tree.GetItemParent(f_par)
                #         print(len(nbt_path_keys), "KKKKKKK")
                #         for c in range(item_num):
                #             if f_child == f_par:
                #                 index = c
                #                 nbt_path_keys.append(index)
                #
                #             f_child, f_c = tree.GetNextChild(f_child, f_c)
                #
                #         print(index, "DEX")
                    # print(type(ddata),"DtN", ddata)
                    # nbt_path_keys.append(index)

                sibl = tree.GetItemParent(sibl)
            nbt_path_keys.reverse()
            return nbt_path_keys[1:]

        def get_nbt(data_nbt, map_list):
            return reduce(operator.getitem, map_list[:-1], data_nbt)

        def get_real_nbt(data_nbt, map_list):
            return reduce(operator.getitem, map_list, data_nbt)

        def loop_tree_nodes(node, da_nbt):
            def is_comp(child, da_nbt):
                fcnt = tree.GetChildrenCount(child, 0)
                if isinstance(tree.GetItemData(child), tuple):
                    temp_comp = nbt.CompoundTag()
                    if tree.GetItemData(child)[1]() == nbt.CompoundTag():
                        for x in range(fcnt):
                            inner_child, cc = tree.GetFirstChild(child)
                            if inner_child.IsOk():
                                for xx in range(fcnt):
                                    if isinstance(tree.GetItemData(inner_child), tuple):
                                        k, v = tree.GetItemData(inner_child)
                                    else:
                                        v = tree.GetItemData(inner_child)
                                    if v == nbt.ListTag:
                                        temp_comp[k] = is_list(inner_child, da_nbt)
                                    elif v == nbt.CompoundTag:
                                        temp_comp[k] = is_comp(inner_child, da_nbt)
                                    else:
                                        temp_comp[k] = v
                                    inner_child, cc = tree.GetNextChild(inner_child, cc)
                        return temp_comp

            def is_list(child, da_nbt):
                first_child, c = tree.GetFirstChild(child)
                if first_child.IsOk():
                    temp_list = nbt.ListTag()
                    fcnt = tree.GetChildrenCount(child, 0)
                    if isinstance(tree.GetItemData(first_child), abc.ABCMeta):
                        for x in range(fcnt):
                            inner_child, cc = tree.GetFirstChild(first_child)  # a loop back
                            if inner_child.IsOk():
                                temp_comp = nbt.CompoundTag()
                                icnt = tree.GetChildrenCount(first_child, 0)
                                for xx in range(icnt):
                                    k, v = tree.GetItemData(inner_child)
                                    if isinstance(v, abc.ABCMeta):
                                        if v == nbt.CompoundTag:
                                            temp_comp[k] = is_comp(inner_child, da_nbt)
                                        elif v == nbt.ListTag:
                                            temp_comp[k] = is_list(inner_child, da_nbt)
                                    else:
                                        temp_comp[k] = v
                                    inner_child, cc = tree.GetNextChild(inner_child, cc)
                                temp_list.append(temp_comp)
                            first_child, c = tree.GetNextChild(first_child, c)
                        return temp_list
                    else:
                        inner_child, cc = tree.GetFirstChild(child)
                        if inner_child.IsOk():
                            for x in range(fcnt):
                                v = tree.GetItemData(inner_child)
                                temp_list.append(v)
                                inner_child, cc = tree.GetNextChild(inner_child, cc)
                        return temp_list
                else:
                    key, value = tree.GetItemData(child)
                    if value == nbt.CompoundTag or value == nbt.ListTag:
                        return value()
                    else:
                        return value

            nc = tree.GetChildrenCount(node, 0)
            child, cookie = tree.GetFirstChild(node)
            if child.IsOk():
                if isinstance(tree.GetItemData(child), tuple):
                    for i in range(nc):
                        key, value = tree.GetItemData(child)[0], tree.GetItemData(child)[1]
                        if type(value) == abc.ABCMeta:
                            the_path = root_path(child)
                            new = get_nbt(da_nbt, the_path[:-1])
                            if type(value()) == nbt.CompoundTag:
                                new[the_path[-1]] = is_comp(child, da_nbt)
                            else:
                                new[the_path[-1]] = is_list(child, da_nbt)
                        else:
                            the_path = root_path(child)
                            new = get_nbt(da_nbt, the_path)
                            new[the_path[-1]] = value
                        child, cookie = tree.GetNextChild(child, cookie)


        if opt == 'snbt':
            f_item = self.tree.GetFocusedItem()
            #
            # i_par = self.tree.GetItemParent(f_item)
            #

            root_tree = self.tree.GetRootItem()
            loop_tree_nodes(root_tree, self.nbt_new)
            t_path = root_path(f_item)

            selected_nbt = get_real_nbt(self.nbt_new, t_path)
            # self.nbt_new.save_to(r"C:\Users\drthe\AppData\Local\Packages\Microsoft.MinecraftUWP_8wekyb3d8bbwe\LocalState\games\com.mojang\minecraftWorlds\wNOGYzAFAQA=\Test.nbt", compressed=False , little_endian=True)
            if hasattr(selected_nbt, 'items'):
                tsnbt = []
                for k, v in selected_nbt.items():
                    tsnbt.append(nbt.CompoundTag({k: v}).to_snbt(5))
                snbt = '{' + ''.join([f" {x[1:-2]}," for x in tsnbt]) + "\n}" #replace("}{", ",").replace("\n,", ",")
                pat = re.compile(r'[A-Za-z0-9._+-:]+(?=":\s)')
                matchs = pat.finditer(snbt)
                for i,x in enumerate(matchs):
                    C1 = x.span()[0] - 1 -(i)#i*2 if no space
                    C2 = x.span()[1] - 1 -(i)#i*2 if no space
                    if ":" in x.group():
                        C1 -= 2
                        C2 += 2
                    snbt = snbt[0:C1:] + snbt[C1+1::]
                    snbt = snbt[0:C2:] + " " + snbt[C2+1::]
            else:
                snbt = selected_nbt.to_snbt(5)
                pat = re.compile(r'[A-Za-z0-9._+-:]+(?=":\s)')
                matchs = pat.finditer(snbt)
                for i, x in enumerate(matchs):
                    C1 = x.span()[0] - 1 - (i)  # i*2 if no space
                    C2 = x.span()[1] - 1 - (i)  # i*2 if no space
                    if ":" in x.group():
                        C1 -= 2
                        C2 += 2
                    snbt = snbt[0:C1:] + snbt[C1 + 1::]
                    snbt = snbt[0:C2:] + " " + snbt[C2 + 1::]

            return t_path, self.nbt_new, snbt

        else:
            root_tree = self.tree.GetRootItem()
            loop_tree_nodes(root_tree, self.nbt_new)
            return self.nbt_new

    def close(self, evt, parent):
        parent.Close(True)
        self.Close(True)

    def build_tree(self,  data, x=0,y=0, root_tag_name=""):
        try:
            self.sizer.Remove(self.tree)
            self.tree.DeleteAllItems()
        except:
            pass

        self.nbt_data = data
        def add_tree_node(_tree: wx.TreeCtrl, _parent, _items):
            for key, value in _items.items():
                new_child = None
                if isinstance(value, MutableMapping):
                    new_child = _tree.AppendItem(_parent, f"{key} {len(value)} entries")
                    add_tree_node(_tree, new_child, value)
                elif isinstance(value, MutableSequence):
                    new_child = _tree.AppendItem(_parent, f"{key} {len(value)} entries")
                    for i, item in enumerate(value):

                        if isinstance(item, MutableMapping):

                            child_child = _tree.AppendItem(new_child, f"{len(item)} entries")
                            add_tree_node(_tree, child_child, item)
                            tree.SetItemData(child_child, type(item))
                            tree.SetItemImage(
                                child_child,
                                self.image_map.get(item.__class__, self.other),
                                wx.TreeItemIcon_Normal,
                            )
                        else:
                            child_child = _tree.AppendItem(new_child, f"{item}")
                            tree.SetItemData(child_child, item)
                            tree.SetItemImage(
                                child_child,
                                self.image_map.get(item.__class__, self.other),
                                wx.TreeItemIcon_Normal,
                            )

                else:
                    new_child = _tree.AppendItem(_parent, f"{key}: {value}")

                if isinstance(value, (nbt.ListTag, nbt.CompoundTag)):

                    tree.SetItemData(new_child, (key, type(value)))
                    tree.SetItemImage(
                        new_child, self.image_map.get(value.__class__, self.other)
                    )

                else:
                    tree.SetItemData(new_child, (key, value))
                    tree.SetItemImage(
                        new_child, self.image_map.get(value.__class__, self.other)
                    )

        tree = MyTreeCtrl(self, wx.ID_ANY, wx.DefaultPosition,(10,10),
                               wx.TR_HAS_BUTTONS, self.nbt_data)
        tree.SetBackgroundColour((0, 0, 0))
        tree.SetForegroundColour((0, 255, 0))
        font = wx.Font(14, wx.FONTFAMILY_ROMAN, wx.FONTSTYLE_MAX, wx.FONTWEIGHT_BOLD)

        tree.SetFont(font)
        tree.AssignImageList(self.image_list)
        root_tag_name = f"{len(self.nbt_data)} entries"
        root = tree.AddRoot(root_tag_name)
        tree.SetItemData(root, ("", self.nbt_data))
        tree.SetItemImage(
            root,
            self.image_map.get(
                self.nbt_data.__class__, self.image_map[nbt.TAG_Compound]
            ),
            wx.TreeItemIcon_Normal,
        )

        add_tree_node(tree, root, self.nbt_data)
        tree.Expand(root)
        tree.Bind(wx.EVT_TREE_ITEM_RIGHT_CLICK, self.tree_right_click)
        # tree.Bind(wx.EVT_LEFT_DOWN, self.tree_leftDC_click)
        tree.Bind(wx.EVT_LEFT_UP, self.tree_leftDC_click)
        #self.tree = self.build_tree(data)
        self.sizer.Add(tree, 1, wx.ALL | wx.CENTER | wx.EXPAND)
        tree.Bind(wx.EVT_LEFT_DCLICK, self.OnLeftDClick)
        tree.Bind(wx.EVT_RIGHT_DOWN, self.OnRightDown)
        tree.Bind(wx.EVT_LEFT_DOWN, self.OnLeftDown)

        # These go at the end of __init__
        tree.Bind(wx.EVT_TREE_BEGIN_RDRAG, self.OnBeginRightDrag)
        tree.Bind(wx.EVT_TREE_BEGIN_DRAG, self.OnBeginLeftDrag)
        tree.Bind(wx.EVT_TREE_END_DRAG, self.OnEndDrag)
        return tree

    def tree_leftDC_click(self, evt):
        pt = (evt.x, evt.y)

        item, a = self.tree.HitTest(pt)

        if item == self.tree.GetFocusedItem() and evt.Button(wx.MOUSE_BTN_LEFT) and a == 64:
            try:
                self.edit_dialog.Destroy()
            except:
                pass
            if isinstance(self.tree.GetItemData(item), tuple):
                name , data = self.tree.GetItemData(item)

            else:
                data = self.tree.GetItemData(item)

            if isinstance(data, abc.ABCMeta):
                datat = type(data())
            else:
                datat = type(data)


            self.has_list_type = str(datat).split(".")[-1][:-2]
            icon = self.image_list.GetBitmap(self.image_map[datat])
            try:
                self.edit_dialog.Destroy()
            except:
                pass
            self.edit_dialog = SmallEditDialog(self, "Edit", self.has_list_type, item, self.tree, icon, self.image_map)
            style = self.edit_dialog.GetWindowStyle()
            self.edit_dialog.SetWindowStyle( style | wx.STAY_ON_TOP )
            self.edit_dialog.Show()

        evt.Skip()

    def tree_right_click(self, evt):


        if isinstance(self.tree.GetItemData(evt.GetItem()), tuple):
            tag_name, tag_obj = self.tree.GetItemData(evt.GetItem())
            if type(tag_obj) == abc.ABCMeta:
                tag_obj = tag_obj()
        else:
            tag_obj = self.tree.GetItemData(evt.GetItem())

        menu = self._generate_menu(
            isinstance(tag_obj, (MutableMapping, MutableSequence, nbt.NamedTag, nbt.CompoundTag, abc.ABCMeta))
        )
        self.PopupMenu(menu, evt.GetPoint())
        menu.Destroy()
        evt.Skip()



    def popup_menu_handler(self, op_map, op_sm_map,icon_sm_map, evt):
        op_id = evt.GetId()
        op_name = None
        continues = True

        if op_id in op_map:
            op_name = op_map[op_id]

        if op_id in op_sm_map:
            tag_type = [tag_class for tag_class in self.image_map if tag_class.__name__ ==
                        op_sm_map[op_id].replace(" ","")][0]

            item = self.tree.GetFocusedItem()

            root = self.tree.GetRootItem()
            n_child = self.tree.GetFirstChild(item)[0]
            if root == item:
                data = tag_type()
            elif n_child.IsOk():

                child_data = self.tree.GetItemData(n_child)

                if not isinstance(child_data, tuple):
                    data = child_data

                    if type(data) == abc.ABCMeta:
                        entries = self.tree.GetChildrenCount(item, 0)
                        testdata = self.tree.GetItemText(item)
                        self.tree.SetItemText(item, testdata.replace(f"{entries - 1} entries", f"{entries} entries"))
                        new_child = self.tree.AppendItem(item, f"0 entries")
                        self.tree.SetItemData(new_child, child_data())
                        self.tree.SetItemImage(
                            new_child,
                            self.image_map.get(data().__class__, self.other),
                            wx.TreeItemIcon_Normal,
                        )
                        self.tree.Expand(item)
                        continues = False
            else:
                 data = tag_type()
            if continues:
                data = tag_type()
                self.has_list_type = str(type(data)).split(".")[-1][:-2]
                try:
                    self.edit_dialog.Destroy()
                except:
                    pass
                icon = self.image_list.GetBitmap(self.image_map[type(data)])
                self.edit_dialog = SmallEditDialog(self, "Add", self.has_list_type, item, self.tree, icon,
                                                   self.image_map)
                style = self.edit_dialog.GetWindowStyle()
                self.edit_dialog.SetWindowStyle(style | wx.STAY_ON_TOP)
                self.edit_dialog.Show()

        elif op_name == "copy":
            self.copy_data = self.tree.SaveItemsToList(self.tree.GetFocusedItem())

        elif op_name == "[paste]":

            self.tree.InsertItemsFromList(self.copy_data,self.tree.GetFocusedItem())
            self.tree.UnselectAll()

        elif op_name == "edit_as":
            try:
                self.edit_dialog.Destroy()
            except:
                pass
            item = self.tree.GetFocusedItem()
            self.edit_dialog = SmallEditDialog(self, "Edit_As", "SNBT", item, self.tree, None,
                                               self.image_map)
            style = self.edit_dialog.GetWindowStyle()
            self.edit_dialog.SetWindowStyle(style | wx.STAY_ON_TOP)
            self.edit_dialog.Show()

        elif op_name == "edit":
            item = self.tree.GetFocusedItem()
            try:
                self.edit_dialog.Destroy()
            except:
                pass
            if isinstance(self.tree.GetItemData(item), tuple):
                name, data = self.tree.GetItemData(item)

            else:
                data = self.tree.GetItemData(item)

            if isinstance(data, abc.ABCMeta):
                datat = type(data())
            else:
                datat = type(data)


            self.has_list_type = str(datat).split(".")[-1][:-2]
            icon = self.image_list.GetBitmap(self.image_map[datat])
            try:
                self.edit_dialog.Destroy()
            except:
                pass
            self.edit_dialog = SmallEditDialog(self, "Edit", self.has_list_type, item, self.tree, icon,
                                               self.image_map)
            style = self.edit_dialog.GetWindowStyle()
            self.edit_dialog.SetWindowStyle(style | wx.STAY_ON_TOP)
            self.edit_dialog.Show()

        elif op_name == "delete":
            selected_tag = self.tree.GetFocusedItem()
            self.tree.Delete(selected_tag)
        else:
            if op_name == "bytetag":
                selected_tag = self.tree.GetFocusedItem()
                name , data = self.tree.GetItemData(selected_tag)
                edit_dialog = SmallEditDialog(self,op_name,data, selected_tag, self.tree, None)
                style = self.edit_dialog.GetWindowStyle()
                edit_dialog.SetWindowStyle(style | wx.STAY_ON_TOP) ###
                edit_dialog.Show()

    def _generate_menu(self, include_add_tag=False):
        menu = wx.Menu()
        s_menu = wx.Menu()

        path_list = [ nbt_resources.path +"\\" + x + ".png" for x in dir(nbt_resources) ]
        menu_items = [
            wx.MenuItem(menu, text="Edit", id=wx.ID_ANY),
            wx.MenuItem(menu, text="Copy", id=wx.ID_ANY),
            wx.MenuItem(menu, text="Edit_As SNBT", id=wx.ID_ANY),
            wx.MenuItem(menu, text="Delete", id=wx.ID_ANY),
        ]
        if self.copy_data:
            menu_items.insert(2, wx.MenuItem(menu, text="[Paste]", id=wx.ID_ANY))
        sub_menu = [
            wx.MenuItem(s_menu, text="Byte Tag", id=wx.ID_ANY),
            wx.MenuItem(s_menu, text="Short Tag", id=wx.ID_ANY),
            wx.MenuItem(s_menu, text="Int Tag", id=wx.ID_ANY),
            wx.MenuItem(s_menu, text="Long Tag", id=wx.ID_ANY),
            wx.MenuItem(s_menu, text="Float Tag", id=wx.ID_ANY),
            wx.MenuItem(s_menu, text="Double Tag", id=wx.ID_ANY),
            wx.MenuItem(s_menu, text="String Tag", id=wx.ID_ANY),
            wx.MenuItem(s_menu, text="Compound Tag", id=wx.ID_ANY),
            wx.MenuItem(s_menu, text="List Tag", id=wx.ID_ANY),
            wx.MenuItem(s_menu, text="Byte Array Tag", id=wx.ID_ANY),
            wx.MenuItem(s_menu, text="Long Array Tag", id=wx.ID_ANY),
            wx.MenuItem(s_menu, text="Int Array Tag", id=wx.ID_ANY),
        ]

        sub_menu[0].SetBitmap(wx.Bitmap(path_list[1]))
        sub_menu[1].SetBitmap(wx.Bitmap(path_list[8]))
        sub_menu[2].SetBitmap(wx.Bitmap(path_list[5]))
        sub_menu[3].SetBitmap(wx.Bitmap(path_list[7]))
        sub_menu[4].SetBitmap(wx.Bitmap(path_list[4]))
        sub_menu[5].SetBitmap(wx.Bitmap(path_list[3]))
        sub_menu[6].SetBitmap(wx.Bitmap(path_list[9]))
        sub_menu[7].SetBitmap(wx.Bitmap(path_list[2]))
        sub_menu[8].SetBitmap(wx.Bitmap(path_list[6]))
        sub_menu[9].SetBitmap(wx.Bitmap(path_list[0]))
        sub_menu[10].SetBitmap(wx.Bitmap(path_list[0]))
        sub_menu[11].SetBitmap(wx.Bitmap(path_list[0]))

        if include_add_tag:
            selected_tag = self.tree.GetFocusedItem()
            data_ = self.tree.GetItemData(selected_tag)
            if isinstance(data_, tuple):
                name, data = data_
            else:
                data = data_
            if type(data) == abc.ABCMeta:
                data = data()
            next_d, c = self.tree.GetFirstChild(selected_tag)
            if next_d.IsOk():
                tag_type = self.tree.GetItemData(next_d)
                if type(tag_type) == abc.ABCMeta:
                    tag_type = tag_type()
                cnt = self.tree.GetChildrenCount(selected_tag,0)
            else:
                tag_type = None
                cnt = 0

            if isinstance(data, nbt.ListTag) and cnt > 0:

                self.has_list_type = str(type(tag_type)).split(".")[-1][:-2]
                for s_menu_item in sub_menu:
                    has_tag = s_menu_item.GetItemLabel().replace(" ", "")
                    if has_tag == self.has_list_type:
                        s_menu.Append(s_menu_item)
            else:
                for s_menu_item in sub_menu:
                    s_menu.Append(s_menu_item)

            add_menu = wx.MenuItem(menu, text="Add Tag", id=wx.ID_ANY)
            add_menu.SetSubMenu(s_menu)
            menu_items.insert(0, add_menu)

        for menu_item in menu_items:

            menu.Append(menu_item)

        op_map = {
            item.GetId(): item.GetItemLabelText().split()[0].lower()
            for item in menu_items
        }
        op_sm_map = {
            item.GetId(): item.GetItemLabelText()
            for item in sub_menu
        }
        icon_sm_map = {
            item.GetId(): item.GetBitmap()
            for item in sub_menu
        }
        menu.Bind(wx.EVT_MENU, lambda evt: self.popup_menu_handler(op_map, op_sm_map,icon_sm_map, evt))

        return menu

    def OnBeginLeftDrag(self, event):
        '''Allow drag-and-drop for leaf nodes.'''
#
        event.Allow()
        self.dragType = "left button"
        self.dragItem = event.GetItem()

    def OnBeginRightDrag(self, event):
        '''Allow drag-and-drop for leaf nodes.'''

        event.Allow()
        self.dragType = "right button"
        self.dragItem = event.GetItem()

    def OnEndDrag(self, event):
        # If we dropped somewhere that isn't on top of an item, ignore the event
        if event.GetItem().IsOk():
            target = event.GetItem()
        else:
            return
        # Make sure this member exists.
        try:
            source = self.dragItem
        except:
            return
        # Prevent the user from dropping an item inside of itself
        if self.tree.ItemIsChildOf(target, source):
            print
            "the tree item can not be moved in to itself! "
            self.tree.Unselect()
            return

        # Get the target's parent's ID
        targetparent = self.tree.GetItemParent(target)
        if not targetparent.IsOk():
            targetparent = self.tree.GetRootItem()

        # One of the following methods of inserting will be called...
        def MoveHere(event):

            # Save + delete the source
            save = self.tree.SaveItemsToList(source)

            self.tree.Delete(source)
            newitems = self.tree.InsertItemsFromList(save, targetparent, target)
            self.tree.UnselectAll()
            for item in newitems:
                self.tree.SelectItem(item)
        def CopyHere(event):

            # Save + delete the source
            save = self.tree.SaveItemsToList(source)
            newitems = self.tree.InsertItemsFromList(save, target)
            self.tree.UnselectAll()
            for item in newitems:
                self.tree.SelectItem(item)

        def InsertInToThisGroup(event):
            # Save + delete the source
            save = self.tree.SaveItemsToList(source)
            self.tree.Delete(source)
            newitems = self.tree.InsertItemsFromList(save, target)
            # self.tree.UnselectAll()
            for item in newitems:
                self.tree.SelectItem(item)


        # ---------------------------------------

        if self.tree.GetItemData(target) and self.dragType == "right button":
            menu = wx.Menu()
            menu.Append(101, "Move to after this group", "")
            menu.Append(102, "Insert into this group", "")
            menu.Append(103, "Copy into this group", "")
            menu.UpdateUI()
            menu.Bind(wx.EVT_MENU, MoveHere, id=101)
            menu.Bind(wx.EVT_MENU, InsertInToThisGroup, id=102)
            menu.Bind(wx.EVT_MENU, CopyHere, id=103)
            self.PopupMenu(menu)
        else:
            if self.tree.IsExpanded(target):
                InsertInToThisGroup(None)
            else:
                MoveHere(None)

    # def OnRightUp(self, event):
    #     pt = event.GetPosition();
    #     item, flags = self.tree.HitTest(pt)
    #
    #     #self.tree.EditLabel(item)
    #     print(item)

    def OnLeftDown(self, event):
        print
        "control key is", event.controlDown

        pt = event.GetPosition();
        item, flags = self.tree.HitTest(pt)
        self.tree.SelectItem(item)
        event.Skip()

    def OnRightDown(self, event):
        print
        "control key is", event.controlDown

        pt = event.GetPosition();
        item, flags = self.tree.HitTest(pt)
        self.tree.SelectItem(item)
        event.Skip()

    def OnLeftDClick(self, event):
        pt = event.GetPosition();
        item, flags = self.tree.HitTest(pt)


        # expand/collapse toggle
        self.tree.Toggle(item)
        print
        "toggled ", item
        # event.Skip()

    def OnSize(self, event):
        w, h = self.GetClientSize()
        self.tree.SetSize(0, 0, w, h)


class BedRock(wx.Panel):
    def __int__(self, world, canvas):
        wx.Panel.__init__(self, parent)
        self.world = world
        self.canvas = canvas
        self.actors = collections.defaultdict(list)
        self.digp = collections.defaultdict(list)

    def get_raw_data_new_version(self, is_export=False, all_enty=False):
        self.get_all_flag = all_enty
        self.EntyData = []
        self.Key_tracker = []
        self.lstOfE = []
        select_chunks = self.canvas.selection.selection_group.chunk_locations()  # selection_group.chunk_locations()
        all_chunks = [x for x in self.world.level_wrapper.all_chunk_coords(self.canvas.dimension)]
        dim = struct.unpack("<i", self.get_dim_value())[0]
        exclude_filter = self.exclude_filter.GetValue().split(",")
        include_filter = self.include_filter.GetValue().split(",")
        if all_enty:
            self.canvas.selection.set_selection_group(SelectionGroup([]))
        if self.canvas.selection.selection_group:
            search_chunks = select_chunks
        else:
            search_chunks = all_chunks
        for xc, zc in search_chunks:
            key = (xc, zc, dim)
            if self.digp.get(key) != None:
                for x in self.digp.get(key):
                    if self.actors.get(x) != None:

                        for raw in self.actors.get(x):
                            try:
                                nbt_ = self.nbt_loder(raw)
                            except:
                                nbt_ = nbt.from_snbt(raw)
                            # print(nbt_)
                            try:
                                name = str(nbt_['identifier']).replace("minecraft:", "")
                            except:
                                name="unknown"
                            custom_name= ''
                            if nbt_.get("CustomName"):
                                custom_name = str(nbt_['CustomName'])
                            print(custom_name)


                            if exclude_filter != [''] or include_filter != ['']:
                                if name not in exclude_filter and exclude_filter != ['']:
                                    self.lstOfE.append(name +":"+custom_name)
                                    self.EntyData.append(nbt_.to_snbt(1))
                                    self.Key_tracker.append(x)
                                for f in include_filter:
                                    if f in name:
                                        self.lstOfE.append(name +":"+custom_name)
                                        self.EntyData.append(nbt_.to_snbt(1))
                                        self.Key_tracker.append(x)
                            else:
                                self.lstOfE.append(name +":"+custom_name)
                                self.EntyData.append(nbt_.to_snbt(1))
                                self.Key_tracker.append(x)
        if is_export:
            print("Exporting")
            return self.EntyData
        if len(self.EntyData) > 0:
            zipped_lists = zip(self.lstOfE, self.EntyData, self.Key_tracker)
            sorted_pairs = sorted(zipped_lists)
            tuples = zip(*sorted_pairs)
            self.lstOfE, self.EntyData, self.Key_tracker = [list(tuple) for tuple in tuples]

        if len(self.lstOfE) == 0:
            EntitiePlugin.Onmsgbox(self, "No Entities", "No Entities were found within the selecton")
        else:
            return self.EntyData, self.lstOfE

    def delete_un_or_selected_entities(self, event, unseleted):
        res = EntitiePlugin.important_question(self)
        if res == False:
            return
        selection = self.canvas.selection.selection_group
        try:
            chunks = selection.chunk_locations()
            for c in chunks:
                self.world.get_chunk(c[0], c[1], self.canvas.dimension)
        except ChunkDoesNotExist:
            responce = EntitiePlugin.con_boc(self,"Chuck Error", "Empty chunk selected, \n Continue any Ways?")
            if responce:
                print("Exiting")
                return
            else:
                pass
        if "[((0, 0, 0), (0, 0, 0))]" == str(selection):
            responce = EntitiePlugin.con_boc(self,"No selection",
                                    "All Entities will be deleted in " + str(self.canvas.dimension) + " \n Continue?")
            if responce:
                print("Exiting")
                return
        sel_res_text = ''
        if unseleted:
            all_chunks = [x for x in self.world.level_wrapper.all_chunk_coords(self.canvas.dimension)]
            selected = self.canvas.selection.selection_group.chunk_locations()
            sel_res_text = "Unselected"
        else:  # Combine Two functions into one
            all_chunks = self.canvas.selection.selection_group.chunk_locations()
            selected = []
            sel_res_text = "Selected"
        if self.world.level_wrapper.version >= (1, 18, 30, 4, 0):
            self._load_entitie_data(event,False,True)
            prefixList = []
            tempPreKe = []
            d = b''
            pdig_to_delete = []
            for ch in all_chunks:
                if ch not in selected:
                    cx, cz = ch[0].to_bytes(4, 'little', signed=True), ch[1].to_bytes(4, 'little', signed=True)
                    if 'minecraft:the_end' in self.canvas.dimension:
                        d = int(2).to_bytes(4, 'little', signed=True)
                    elif 'minecraft:the_nether' in self.canvas.dimension:
                        d = int(1).to_bytes(4, 'little', signed=True)
                    key = b'digp' + cx + cz + d  # build the digp key for the chunk
                    try:
                        if self.level_db.get(key):
                            data = self.level_db.get(key)
                            for CntB in range(0, len(data), 8):  # the actorprefix keys are every 8 bytes , build a list
                                prefixList.append(b'actorprefix' + data[CntB:CntB + 8])
                            pdig_to_delete.append(key)
                    except KeyError as e:
                        print("keyerror")

            for pkey in prefixList:
                self.level_db.delete(pkey)
            for pdig_d in pdig_to_delete:
                self.level_db.delete(pdig_d)
        else:
            for x, z in all_chunks:
                if (x,z) not in selected:
                    raw = self.world.level_wrapper.get_raw_chunk_data(x, z, self.canvas.dimension)
                    raw[b'2'] = b''
                    self.world.level_wrapper.put_raw_chunk_data(x, z, raw, self.canvas.dimension)

        self.world.save()
        self._set_list_of_actors_digp
        self._load_entitie_data(event, False, False)
        EntitiePlugin.Onmsgbox(self, "Deleted ", f"Entities from {sel_res_text}")
    def _exp_entitie_data(self, _):
        dlg = ExportImportCostomDialog(None)
        dlg.InitUI(1)
        res = dlg.ShowModal()
        if dlg.selected_chunks.GetValue():
            select_chunks = self.canvas.selection.selection_group.chunk_locations()
        elif dlg.all_chunks.GetValue():
            select_chunks = [x for x in self.world.level_wrapper.all_chunk_coords(self.canvas.dimension)]
        elif dlg.nbt_file_option.GetValue():
            self._export_nbt(_)
            return
        else:
            return

        snbt_list = b''
        world = self.world
        dimension = self.canvas.dimension
        selection = self.canvas.selection.selection_group
        snbt_line_list = ""
        dim = struct.unpack("<i", self.get_dim_value())[0]
        if self.world.level_wrapper.version >= (1, 18, 30, 4, 0):
            if self.canvas.selection.selection_group.selection_boxes == ():
                responce = EntitiePlugin.con_boc(self, "Backup: ",
                                                 "No selection, This will back up all Entities within this Dim:\n"
                                                 + self.canvas.dimension)
                if responce == True:
                    return

            else:
                responce = EntitiePlugin.con_boc(self, "Backup",
                                                 ",This will back up all Entities within this selection/s >" + str(
                                                     self.canvas.selection.selection_group))
                if responce == True:
                    return
            listOfent = self.get_raw_data_new_version(True)
            if len(listOfent) > 0:
                for data in listOfent:
                    format = nbt.from_snbt(data)
                    snbt_line_list += format.to_snbt() + "\n"
                responce = EntitiePlugin.save_entities_export(self, snbt_line_list)
                if responce == True:
                    EntitiePlugin.Onmsgbox(self, "Export Complete", "No Erros were detected")
                else:
                    EntitiePlugin.Onmsgbox(self, "Cancel", "Canceled or something went wrong")
                return
        else:
            ent = {}
            chunks = select_chunks
            byteCount = 0
            snbb = []
            self.EntyData.clear()
            for count, (cx, cz) in enumerate(chunks):
                chunk = self.world.level_wrapper.get_raw_chunk_data(cx, cz, self.canvas.dimension)
                if chunk.get(b'2'):
                    max = len(chunk[b'2'])
                    pointer = 0
                    while pointer < max:
                        EntyD, p = nbt.load(chunk[b'2'][pointer:], little_endian=True, offset=True)
                        pointer += p
                        self.EntyData.append(EntyD)

            if len(self.EntyData) > 0:
                for elist in self.EntyData:
                    snbt_line_list += elist.to_snbt() + "\n"

        res = EntitiePlugin.save_entities_export(self,snbt_line_list)
        if res == False:
            return
        EntitiePlugin.Onmsgbox(self,"Export", "Saved")

    def _export_nbt(self, _):
        entities = amulet_nbt.TAG_List()
        blocks = amulet_nbt.TAG_List()
        palette = amulet_nbt.TAG_List()
        DataVersion = amulet_nbt.TAG_Int(2975)
        selection = self.canvas.selection.selection_group.to_box()
        pallet_key_map = collections.defaultdict(list)
        nbt_state_map = collections.defaultdict(list)
        indx = 0
        sx, sy, sz = 0, 0, 0

        mx, my, mz = self.canvas.selection.selection_group.to_box().shape
        block_pos = []
        reps = EntitiePlugin.con_boc(self, "Air Blocks", 'Do you want to encude air block?')
        # bl = np.zeros(shape, dtype=numpy.uint32)
        for x in range(0, (mx)):
            for y in range(0, (my)):
                for z in range(0, (mz)):
                    block_pos.append((x, y, z))
        entities = self.get_entities_nbt(block_pos)
        prg_max = len(block_pos)
        prg_pre = 0
        prg_pre_th = len(block_pos) / 100
        self.prog = wx.ProgressDialog("Saving blocks", str(0) + " of " + str(prg_max),
                                      style=wx.PD_AUTO_HIDE | wx.PD_CAN_ABORT | wx.PD_ELAPSED_TIME | wx.PD_REMAINING_TIME)
        self.prog.Show(True)
        for i, (s, b) in enumerate(zip(selection, block_pos)):
            if self.prog.WasCancelled():
                self.prog.Hide()
                self.prog.Destroy()
                break
            if i >= prg_pre_th:
                prg_pre_th += len(block_pos) / 100
                prg_pre += 1
                self.prog.Update(prg_pre, "Saving blocks " + str(i) + " of " + str(prg_max))
            block, blockEntity = self.world.get_version_block(s[0], s[1], s[2], self.canvas.dimension,
                                                              ("java", (1, 18, 0)))

            if not reps:
                check_string = ""
            else:
                check_string = 'minecraft:air'
            if str(block) != check_string:
                if pallet_key_map.get((block.namespaced_name, str(block.properties))) == None:
                    pallet_key_map[(block.namespaced_name, str(block.properties))] = indx
                    indx += 1
                    palette_Properties = nbt.CompoundTag(
                        {'Properties': nbt.CompoundTag(block.properties),
                         'Name': nbt.StringTag(block.namespaced_name)})
                    palette.append(palette_Properties)
                state = pallet_key_map[(block.namespaced_name, str(block.properties))]

                if blockEntity == None:
                    blocks_pos = amulet_nbt.TAG_Compound({'pos': amulet_nbt.TAG_List(
                        [nbt.IntTag(b[0]), nbt.IntTag(b[1]),
                         nbt.IntTag(b[2])]), 'state': nbt.IntTag(state)})
                    blocks.append(blocks_pos)
                else:
                    blocks_pos = nbt.CompoundTag({'nbt': nbt.from_snbt(blockEntity.nbt.to_snbt()),
                                                          'pos': nbt.ListTag(
                                                              [nbt.IntTag(b[0]),
                                                               nbt.IntTag(b[1]),
                                                               nbt.IntTag(b[2])]),
                                                          'state': amulet_nbt.TAG_Int(state)})
                    blocks.append(blocks_pos)
        prg_pre = 99
        self.prog.Update(prg_pre, "Finishing Up " + str(i) + " of " + str(prg_max))
        size = nbt.ListTag([nbt.IntTag(mx), nbt.IntTag(my), nbt.IntTag(mz)])

        save_it = nbt.CompoundTag({})
        save_it['size'] = size
        save_it['entities'] = entities
        save_it['blocks'] = blocks
        save_it['palette'] = palette
        save_it['DataVersion'] = DataVersion
        raw_data = save_it.save_to(compressed=True, little_endian=False)
        prg_pre = 100
        self.prog.Update(prg_pre, "Done")
        pathto = ""
        fdlg = wx.FileDialog(self, "Save As .nbt", "", "", "nbt files(*.nbt)|*.*", wx.FD_SAVE)
        if fdlg.ShowModal() == wx.ID_OK:
            pathto = fdlg.GetPath()
        else:
            return False
        if ".nbt" not in pathto:
            pathto = pathto + ".nbt"
        with open(pathto, "wb") as tfile:
            tfile.write(raw_data)
            tfile.close()
        wx.MessageBox("Save Complete", "No Issues", wx.OK | wx.ICON_INFORMATION)

    def _import_nbt(self, _):

        fdlg = wx.FileDialog(self, "Load .nbt File", "", "", "nbt files(*.nbt)|*.*", wx.FD_OPEN)
        the_id = fdlg.ShowModal()
        if int(the_id) == 5101:
            return False
        if the_id == wx.ID_OK:
            pathto = fdlg.GetPath()
            nbt_ = amulet_nbt.load(pathto, compressed=True, little_endian=False, )
            block_platform = "java"
            block_version = (1, 18, 0)
            b_pos = []
            palette = []
            Name = []
            enbt_ = []
            xx = self.canvas.selection.selection_group.min_x
            yy = self.canvas.selection.selection_group.min_y
            zz = self.canvas.selection.selection_group.min_z
            if True:
                reps = EntitiePlugin.con_boc(self, "Air Blocks", 'Do you want to encude air block?')
                for x in nbt_.get('blocks'):
                    if x['palette'][int(x.get('state'))].get('Properties') != None:
                        palette.append(
                            dict(amulet_nbt.from_snbt(nbt['palette'][int(x.get('state'))]['Properties'].to_snbt())))
                    else:
                        palette.append(None)
                    b_pos.append(x.get('pos'))
                    Name.append(nbt['palette'][int(x.get('state'))]['Name'])
                    if x.get('nbt') != None:
                        name = str(nbt['palette'][int(x.get('state'))]['Name']).split(':')

                        blockEntity = BlockEntity(name[0], name[1].replace('_', '').capitalize(), 0, 0, 0,
                                                  amulet_nbt.NBTFile(x.get('nbt')))
                        enbt.append(blockEntity)
                    else:
                        enbt.append(None)
                if not reps:
                    check_string = ""
                else:
                    check_string = 'minecraft:air'
                for x in zip(b_pos, palette, Name, enbt):
                    if x[1] != check_string:
                        block = Block(str(x[2]).split(':')[0], str(x[2]).split(':')[1], x[1])
                        self.world.set_version_block(xx + x[0][0], yy + x[0][1], zz + x[0][2], self.canvas.dimension,
                                                     (block_platform, block_version), block, x[3])
                self.canvas.run_operation(lambda: self._refresh_chunk_now(self.canvas.dimension, self.world, xx, zz))
                dialog = wx.MessageDialog(self, "Including entities directly edits the world and there is no Undo."
                                                "\n Would you like to save changes or discard them,"
                                                "\n Both option will remove all current undo points\n"
                                                "What do you wish to do?", "NOTICE",
                                          wx.ICON_EXCLAMATION | wx.YES_NO | wx.CANCEL | wx.CANCEL_DEFAULT)
                dialog.SetYesNoLabels('Save changes', 'Discard changes')
                responce = dialog.ShowModal()
                dialog.Destroy()
                if responce == wx.ID_YES:
                    self.world.save()
                    self.world.purge()
                    pass
                elif responce == wx.ID_NO:
                    self.world.purge()
                    pass
                else:
                    return
                e_nbt_list = []
                for x in nbt.get('entities'):
                    if str(x) != '':
                        e_nbt_ = x.get('nbt')
                        nxx, nyy, nzz = x.get('pos').value
                        if 'Float' in str(type(nxx)):
                            x['nbt']['Pos'] = amulet_nbt.TAG_List([amulet_nbt.TAG_Float(float(nxx + xx)),
                                                                   amulet_nbt.TAG_Float(float(nyy + yy)),
                                                                   amulet_nbt.TAG_Float(float(nzz + zz))])
                        if 'Double' in str(type(nxx)):
                            x['nbt']['Pos'] = amulet_nbt.TAG_List([amulet_nbt.TAG_Double(float(nxx + xx)),
                                                                   amulet_nbt.TAG_Double(float(nyy + yy)),
                                                                   amulet_nbt.TAG_Double(float(nzz + zz))])
                        e_nbt_list.append(x['nbt'])
                self.set_entities_nbt(e_nbt_list)

    def _refresh_chunk_now(self, dimension, world, x, z):
        cx, cz = block_coords_to_chunk_coords(x, z)
        chunk = world.get_chunk(cx, cz, dimension)
        chunk.changed = True

    def get_dim_value_bytes(self):
        if 'minecraft:the_end' in self.canvas.dimension:
            dim = int(2).to_bytes(4, 'little', signed=True)
        elif 'minecraft:the_nether' in self.canvas.dimension:
            dim = int(1).to_bytes(4, 'little', signed=True)
        elif 'minecraft:overworld' in self.canvas.dimension:
            dim = b''  # int(0).to_bytes(4, 'little', signed=True)
        return dim

    def get_entities_nbt(self, rpos):
        mapdic = collections.defaultdict()

        entities = amulet_nbt.TAG_List()
        selection = self.canvas.selection.selection_group.to_box()
        for o, n in zip(selection, rpos):
            mapdic[o] = n
        chunk_min, chunk_max = self.canvas.selection.selection_group.min, \
                               self.canvas.selection.selection_group.max
        min_chunk_cords, max_chunk_cords = block_coords_to_chunk_coords(chunk_min[0], chunk_min[2]), \
                                           block_coords_to_chunk_coords(chunk_max[0], chunk_max[2])
        if self.world.level_wrapper.platform == "bedrock":
            print("ok")
            if self.world.level_wrapper.version >= (1, 18, 30, 4, 0):

                actorprefixs = iter(self.level_db.iterate(start=b'actorprefix',
                                                          end=b'actorprefix\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF'))
                t_start = struct.pack('<ii', min_chunk_cords[0], min_chunk_cords[1])
                t_end = struct.pack('<ii', max_chunk_cords[0], max_chunk_cords[1])
                start = b''.join([b'digp', t_start, self.get_dim_value_bytes()])
                end = b''.join([b'digp', t_end, self.get_dim_value_bytes()])
                for digps_key, digps_val in self.level_db.iterate(start=start, end=end):
                    for x in range(0, len(digps_val), 8):
                        key = b''.join([b'actorprefix', digps_val[x:x + 8]])
                        actor = self.level_db.get(key).\
                            replace(b'\x08\n\x00StorageKey\x08\x00',b'\x07\n\x00StorageKey\x08\x00\x00\x00')
                        nbt_data = amulet_nbt.load(actor, compressed=False, little_endian=True)

                        print(nbt_data)
                        pos = nbt_data.get("Pos")
                        x, y, z = math.floor(pos[0]), math.floor(pos[1]), math.floor(pos[2])

                        if (x, y, z) in selection:
                            nbt_entitie = amulet_nbt.TAG_List()
                            new_pos = mapdic[(x, y, z)]
                            nbt_pos = amulet_nbt.TAG_List(
                                [amulet_nbt.TAG_Float(sum([new_pos[0],
                                                           math.modf(abs(nbt_data.get("Pos")[0].value))[0]])),
                                 amulet_nbt.TAG_Float(sum([new_pos[1],
                                                           math.modf(abs(nbt_data.get("Pos")[1].value))[0]])),
                                 amulet_nbt.TAG_Float(sum([new_pos[2],
                                                           math.modf(abs(nbt_data.get("Pos")[2].value))[0]]))])

                            nbt_block_pos = amulet_nbt.TAG_List([amulet_nbt.TAG_Int(new_pos[0]),
                                                                 amulet_nbt.TAG_Int(new_pos[1]),
                                                                 amulet_nbt.TAG_Int(new_pos[2])])
                            # nbt_data.pop('internalComponents')
                            # nbt_data.pop('UniqueID')
                            nbt_nbt = amulet_nbt.from_snbt(nbt_data.to_snbt())
                            main_entry = amulet_nbt.TAG_Compound()
                            main_entry['nbt'] = nbt_nbt
                            main_entry['blockPos'] = nbt_block_pos
                            main_entry['pos'] = nbt_pos
                            entities.append(main_entry)
                return entities

            elif self.world.level_wrapper.version < (1, 18, 30, 4, 0):

                entitie = amulet_nbt.TAG_List()
                for cx, cz in self.canvas.selection.selection_group.chunk_locations():
                    chunk = self.world.level_wrapper.get_raw_chunk_data(cx, cz, self.canvas.dimension)
                    if chunk.get(b'2') != None:
                        max = len(chunk[b'2'])
                        cp = 0

                        while cp < max:
                            nbt_data, p = amulet_nbt.load(chunk[b'2'][cp:], little_endian=True, offset=True)
                            cp += p
                            pos = nbt_data.get("Pos")
                            print(nbt_data.get('identifier'), selection.blocks)
                            x, y, z = math.floor(pos[0]), math.floor(pos[1]), math.floor(pos[2])
                            print((x, y, z) in selection)
                            if (x, y, z) in selection:
                                new_pos = mapdic[(x, y, z)]
                                nbt_pos = amulet_nbt.TAG_List(
                                    [amulet_nbt.TAG_Float(sum([new_pos[0],
                                                               math.modf(abs(nbt_data.get("Pos")[0].value))[0]])),
                                     amulet_nbt.TAG_Float(sum([new_pos[1],
                                                               math.modf(abs(nbt_data.get("Pos")[1].value))[0]])),
                                     amulet_nbt.TAG_Float(sum([new_pos[2],
                                                               math.modf(abs(nbt_data.get("Pos")[2].value))[0]]))])
                                nbt_block_pos = amulet_nbt.TAG_List([amulet_nbt.TAG_Int(new_pos[0]),
                                                                     amulet_nbt.TAG_Int(new_pos[1]),
                                                                     amulet_nbt.TAG_Int(new_pos[2])])
                                # nbt_data.pop('internalComponents')
                                # nbt_data.pop('UniqueID')
                                nbt_nbt_ = amulet_nbt.from_snbt(nbt_data.to_snbt())
                                main_entry = amulet_nbt.TAG_Compound()
                                main_entry['nbt'] = nbt_nbt
                                main_entry['blockPos'] = nbt_block_pos
                                main_entry['pos'] = nbt_pos
                                entities.append(main_entry)
                return entities
            else:
                print("no data")

    def set_entities_nbt(self, entities_list):
        entcnt = 0
        if self.world.level_wrapper.platform == "bedrock":
            if self.world.level_wrapper.version >= (1, 18, 30, 4, 0):
                for x in entities_list:
                    xc, zc = block_coords_to_chunk_coords(x.get('Pos')[0], x.get('Pos')[2])

                    world_count = int(str(self.world.level_wrapper.root_tag.get('worldStartCount')).replace('L', ''))
                    start_count = 4294967295 - world_count
                    entcnt += 1
                    actorKey = struct.pack('>LL', start_count, entcnt)
                    put_key = b''.join([b'actorprefix', actorKey])

                    digp = b''.join([b'digp', struct.pack('<ii', xc, zc), self.get_dim_value_bytes()])
                    # try:
                    #     # print(self.level_db.get(digp))
                    #     new_digp = self.level_db.get(digp)
                    #     # print(self.level_db.get(digp))
                    # except:
                    #     new_digp = b''
                    # try:
                    #     new_actor = self.level_db.get(put_key)
                    # except:
                    #     new_actor = b''
                    # new_digp += actorKey
                    new_actor += x.save_to(compressed=False, little_endian=True)

                    self.level_db.put(put_key, new_actor)
                    self.level_db.put(digp, new_digp)

            elif self.world.level_wrapper.version < (1, 18, 30, 4, 0):
                for x in entities_list:
                    xc, zc = block_coords_to_chunk_coords(x.get('Pos')[0], x.get('Pos')[2])
                    chunk = self.world.level_wrapper.get_raw_chunk_data(xc, zc, self.canvas.dimension)
                    try:
                        chunk[b'2'] += amulet_nbt.NBTFile(x).save_to(little_endian=True, compressed=False)
                    except:
                        chunk[b'2'] = amulet_nbt.NBTFile(x).save_to(little_endian=True, compressed=False)
                    self.world.level_wrapper.put_raw_chunk_data(xc, zc, chunk, self.canvas.dimension)
                    self.world.level_wrapper.save()

        self.world.save()

    def _imp_entitie_data(self, _):
        dlg = ExportImportCostomDialog(None)
        dlg.InitUI(2)
        res = dlg.ShowModal()
        #self._set_list_of_actors_digp
        if dlg.ms_file.GetValue():
            fdlg = wx.FileDialog(self, "export Entities", "", "",
                                 f"SNBT (*.snbt_{self.world.level_wrapper.platform})|*.*", wx.FD_OPEN)
            if fdlg.ShowModal() == wx.ID_OK:
                pathto = fdlg.GetPath()
            else:
                return
            anbt = amulet_nbt.load(pathto, compressed=False, little_endian=True)
            sx, sy, sz = anbt.get("structure_world_origin")
            egx, egy, egz = anbt.get("size")
            ex, ey, ez = sx + egx, sy + egy, sz + egz
            group = []
            self.canvas.camera.set_location((sx, 70, sz))
            self.canvas.camera._notify_moved()
            s, e = (int(sx), int(sy), int(sz)), (int(ex), int(ey), int(ez))
            group.append(SelectionBox(s, e))
            sel_grp = SelectionGroup(group)
            self.canvas.selection.set_selection_group(sel_grp)
            actors = self.actors
            for xx in self.canvas.selection.selection_group.blocks:
                for nbtlist in actors.values():
                    for anbt in nbtlist:
                        nbtd = amulet_nbt.load(anbt, compressed=False, little_endian=True)
                        x,y,z = nbtd.get('Pos').value
                        ex,ey,ez = math.floor(x),math.floor(y),math.floor(z)
                        if (ex,ey,ez) == xx:
                            #print(ex,ey,ez, nbtd.value)
                            anbt['structure']['entities'].append(nbtd.value)
            #nbt_file = amulet_nbt.NBTFile(anbt)
            anbt.save_to(pathto, compressed=False, little_endian=True)
            EntitiePlugin.Onmsgbox(self, "Entities Added To Structure File", "Complete")
            return
        elif dlg.nbt_file.GetValue():
            try:
                re = self._import_nbt(_)
                if re == False:
                    return
            except ValueError as e:
                EntitiePlugin.Onmsgbox(self, "No Selection", "You Need to make a selection to set starting point. ")
                return
            EntitiePlugin.Onmsgbox(self, "NBT Import", "Complete")

        elif dlg.list.GetValue():
            res = EntitiePlugin.important_question(self)
            if res == False:
                return
            snbt_loaded_list = EntitiePlugin.load_entities_export(self)
            chunk_dict = collections.defaultdict(list)
            NewRawB = b''

            if self.world.level_wrapper.version >= (1, 18, 30, 4, 0):
                ent_cnt = 2
                print("Importing...")
                self._set_list_of_actors_digp
                xxxx = 0
                for snbt_line in snbt_loaded_list:
                    print(xxxx)
                    xxxx+=1
                    nbt_from_snbt = nbt.from_snbt(snbt_line)
                    cx, cz = block_coords_to_chunk_coords(nbt_from_snbt.get('Pos')[0], nbt_from_snbt.get('Pos')[2])
                    chunk_dict[(cx, cz)].append(nbt_from_snbt)

                d = 0
                for lk_data in chunk_dict.keys():

                    key = self.build_digp_chunk_key(lk_data[0], lk_data[1])  # build the digp key for the chunk
                    dig_p_dic = {}
                    dig_byte_list = b''

                    for ent_data in chunk_dict[lk_data]:
                        new_prefix = self.build_actor_key(1, ent_cnt)
                        ent_cnt += 1
                        ent_data["UniqueID"] = self._genorate_uid(ent_cnt)
                        try:
                            print( nbt.ByteArrayTag(bytearray(new_prefix[len(b'actorprefix'):])),"___________________________________")
                            ent_data['internalComponents']['EntityStorageKeyComponent']['StorageKey'] = \
                                nbt.ByteArrayTag(bytearray(new_prefix[len(b'actorprefix'):]))
                        except:
                            pass
                        dig_byte_list += new_prefix[len(b'actorprefix'):]
                        final_data = ent_data.save_to(compressed=False, little_endian=True).replace(b'\x07\n\x00StorageKey\x08\x00\x00\x00', b'\x08\n\x00StorageKey\x08\x00')
                       # print(new_prefix, final_data)
                        self.level_db.put(new_prefix, final_data)
                        print(new_prefix, "New")
                    self.level_db.put(key, dig_byte_list)


            else:
                cnt = 0
                for snbt in snbt_loaded_list:
                    nbt_from_snbt_ = nbt.from_snbt(snbt)
                    cx, cz = block_coords_to_chunk_coords(nbt_from_snbt.get('Pos')[0], nbt_from_snbt.get('Pos')[2])
                    chunk_dict[(cx, cz)].append(nbt_from_snbt)
                for k in chunk_dict.keys():

                    chunk = b''
                    chunk = self.world.level_wrapper.get_raw_chunk_data(k[0], k[1], self.canvas.dimension)
                    NewRawB = []
                    for ent in chunk_dict[k]:
                        cnt += 1
                        ent["UniqueID"] = self._genorate_uid(cnt)
                        NewRawB.append(ent.save_to(compressed=False, little_endian=True))

                    if chunk.get(b'2'):
                        chunk[b'2'] += b''.join(NewRawB)
                    else:
                        chunk[b'2'] = b''.join(NewRawB)

                    self.world.level_wrapper.put_raw_chunk_data(k[0], k[1], chunk, self.canvas.dimension)

            old_start = self.world.level_wrapper.root_tag.get('worldStartCount')
            self.world.level_wrapper.root_tag['worldStartCount'] = nbt.TAG_Long((int(old_start) - 1))
            self.world.level_wrapper.root_tag.save()
            self.world.save()
            self._set_list_of_actors_digp
            self._load_entitie_data(_, False,False)
            EntitiePlugin.Onmsgbox(self,"Entitie Import", "Complete")
    def _genorate_uid(self, cnt):
        start_c = self.world.level_wrapper.root_tag.get('worldStartCount')
        new_gen = struct.pack('<LL', int(cnt), int(start_c))
        new_tag = nbt.TAG_Long(struct.unpack('<q', new_gen)[0])
        return new_tag

    def _storage_key_(self, val):
        if isinstance(val, bytes):
            return struct.unpack('>II', val)
        if isinstance(val, nbt.TAG_String):
            return nbt.TAG_Byte_Array([x for x in val.py_data])
        if isinstance(val, nbt.TAG_Byte_Array):
            data = b''
            for b in val: data += b
            return data

    def _move_copy_entitie_data(self, event, copy=False):
        res = EntitiePlugin.important_question(self)
        if res == False:
            return
        try:
            data = nbt.from_snbt(self.EntyData[self.ui_entitie_choice_list.GetSelection()])
        except:
            data = self.EntyData[self.ui_entitie_choice_list.GetSelection()]
        if data == '':
            EntitiePlugin.Onmsgbox(self,"No Data", "Did you make a selection?")
            return
        x = self._X.GetValue().replace(" X", "")
        y = self._Y.GetValue().replace(" Y", "")
        z = self._Z.GetValue().replace(" Z", "")
        xx,yy, zz = 0, 0,0

        if float(x) >= 0.0:
            xx = 1
        if float(y) >= 0.0:
            yy = 1
        if float(z) >= 0.0:
            zz = 1

        dim = struct.unpack("<i", self.get_dim_value())[0]
        location = nbt.ListTag([nbt.FloatTag(float(x)-xx ), nbt.FloatTag(float(y)-yy), nbt.FloatTag(float(z)-zz)])

        if data != '':
            if copy:
                cx, cz = block_coords_to_chunk_coords(data.get('Pos')[0], data.get('Pos')[2])
                actor_key = self.uuid_to_storage_key(data)
                acnt = []
                for x in self.actors.keys():
                    if x[0] == actor_key[0]:
                        acnt.append(x[1])
                acnt.sort()
                max_count_uuid = acnt[-1:][0]
                wc = 4294967296 - actor_key[0]
                new_actor_key = (actor_key[0],max_count_uuid+1)
                new_actor_key_raw = struct.pack('>LL', new_actor_key[0], new_actor_key[1] )
                new_uuid = struct.pack('<LL', max_count_uuid+1, wc )
                data["UniqueID"] = nbt.TAG_Long(struct.unpack('<q', new_uuid)[0])
                data["Pos"] = location
                key_actor = b''.join([b'actorprefix',new_actor_key_raw])
                key_digp = self.build_digp_chunk_key(cx, cz)
                nx,nz = block_coords_to_chunk_coords(location[0],location[2])
                new_digp_key = self.build_digp_chunk_key(nx, nz)

                if data.get("internalComponents") != None:
                    b_a = []
                    for b in struct.pack('>LL', actor_key[0], max_count_uuid+1 ):
                        b_a.append(nbt.TAG_Byte(b))
                    tb_arry = nbt.TAG_Byte_Array([b_a[0],b_a[1],b_a[2],b_a[3],b_a[4],b_a[5],b_a[6],b_a[7]])
                    data["internalComponents"]["EntityStorageKeyComponent"]["StorageKey"] = tb_arry
                if self.world.level_wrapper.version >= (1, 18, 30, 4, 0):
                    try:
                        append_data_key_digp = self.level_db.get(new_digp_key)
                    except:
                        append_data_key_digp = b''
                    append_data_key_digp += new_actor_key_raw
                    self.level_db.put(new_digp_key, append_data_key_digp)
                    self.level_db.put(key_actor, data.save_to(compressed=False, little_endian=True)
                            .replace(b'\x07\n\x00StorageKey\x08\x00\x00\x00', b'\x08\n\x00StorageKey\x08\x00'))
                    EntitiePlugin.Onmsgbox(self, "Copy", "Completed")
                    self._finishup(event)
                else:
                    raw_chunk_entitie = nbt.NBTFile(data).save_to(compressed=False, little_endian=True)
                    raw = self.world.level_wrapper.get_raw_chunk_data(nx, nz, self.canvas.dimension)
                    if raw.get(b'2'):
                        raw[b'2'] += raw_chunk_entitie
                    else:
                        raw[b'2'] = raw_chunk_entitie
                    self.world.level_wrapper.put_raw_chunk_data(nx,nz, raw, self.canvas.dimension)

                    EntitiePlugin.Onmsgbox(self, "Copy", "Completed")
                    self._finishup(event)
            else:
                cx, cz = block_coords_to_chunk_coords(data.get('Pos')[0], data.get('Pos')[2])
                nx, nz = block_coords_to_chunk_coords(location[0], location[2])
                actor_key = self.uuid_to_storage_key(data)
                actor_key_raw = struct.pack('>LL', actor_key[0], actor_key[1])
                uid = data.get("UniqueID").value
                data["Pos"] = location
                key_digp = self.build_digp_chunk_key(cx, cz)
                new_digp_key = self.build_digp_chunk_key(nx, nz)
                if self.world.level_wrapper.version >= (1, 18, 30, 4, 0):
                    if key_digp != new_digp_key:
                        dpkeys = self.level_db.get(key_digp)
                        try:
                            new_dpkeys = self.level_db.get(new_digp_key)
                        except:
                            new_dpkeys = b''
                        keep = []
                        new_dpkeys =  b''.join([new_dpkeys, actor_key_raw])
                        for db in range(0, len(dpkeys), 8):
                            akey = dpkeys[db:db + 8]
                            if akey != actor_key_raw:
                                keep.append(akey)
                        dpkeys =  b''.join(keep)
                        self.level_db.put(key_digp, dpkeys)
                        self.level_db.put(new_digp_key, new_dpkeys)
                    actor_key = b''.join([b'actorprefix', actor_key_raw])
                    self.level_db.put(actor_key, data.save_to(compressed=False, little_endian=True)
                                          .replace(b'\x07\n\x00StorageKey\x08\x00\x00\x00',
                                                   b'\x08\n\x00StorageKey\x08\x00'))
                    EntitiePlugin.Onmsgbox(self, "Move Position", "Completed")
                    self._finishup(event)
                else:

                    if (cx,cz) != (nx,nz):
                        old_raw = self.world.level_wrapper.get_raw_chunk_data(cx,cz, self.canvas.dimension)
                        new_raw = self.world.level_wrapper.get_raw_chunk_data(nx,nz, self.canvas.dimension)
                        point = 0
                        max = len(old_raw[b'2'])
                        old_raw_keep = []
                        while point < max:
                            data_old, p = nbt.load(old_raw[b'2'][point:],compressed=False, little_endian=True, offset=True)
                            point += p
                            if data.get('UniqueID') != data_old.get('UniqueID'):
                                old_raw_keep.append(data_old.save_to(compressed=False, little_endian=True))
                        old_raw[b'2'] = b''.join(old_raw_keep)
                        self.world.level_wrapper.put_raw_chunk_data(cx, cz, old_raw, self.canvas.dimension)
                        raw_chunk_entitie = nbt.NBTFile(data).save_to(compressed=False, little_endian=True)

                        if new_raw.get(b'2'):
                            new_raw[b'2'] += raw_chunk_entitie
                        else:
                            new_raw[b'2'] = raw_chunk_entitie
                        self.world.level_wrapper.put_raw_chunk_data(nx, nz, new_raw, self.canvas.dimension)
                        EntitiePlugin.Onmsgbox(self, "Move Position", "Completed")
                        self._finishup(event)
                    else:
                        update_raw = self.world.level_wrapper.get_raw_chunk_data(nx, nz, self.canvas.dimension)
                        point = 0
                        max = len(update_raw[b'2'])
                        update_keep = []
                        while point < max:
                            data_old, p = nbt.load(update_raw[b'2'][point:], compressed=False, little_endian=True,
                                                   offset=True)
                            point += p
                            if data.get('UniqueID') != data_old.get('UniqueID'):
                                update_keep.append(data_old.save_to(compressed=False, little_endian=True))
                            else:
                                update_keep.append(nbt.NBTFile(data).save_to(compressed=False, little_endian=True))
                        update_raw[b'2'] = b''.join(update_keep)
                        self.world.level_wrapper.put_raw_chunk_data(nx, nz, update_raw, self.canvas.dimension)
                        EntitiePlugin.Onmsgbox(self, "Move Position", "Completed")
                        self._finishup(event)

    def _finishup(self, event):
        self.world.save()
        self._set_list_of_actors_digp
        self._load_entitie_data(event, False, False)


    def _save_data_to_world(self, _):

        NewRawB = b''
        selection = self.ui_entitie_choice_list.GetSelection()
        # newData = self.nbt_editor_instance.GetValue()
        res = EntitiePlugin.important_question(self)
        if res == False:
            return
        new_data = NBTEditor.build_to(self.nbt_editor_instance, _)
        self.EntyData[selection] = new_data.to_snbt(1)
        if self.world.level_wrapper.version >= (1, 18, 30, 4, 0):
            for snbt, key in zip(self.EntyData, self.Key_tracker):
                nbt_data = nbt.from_snbt(snbt)
                dim = struct.unpack("<i", self.get_dim_value())[0]
                cx, cz = block_coords_to_chunk_coords(nbt_data.get('Pos')[0], nbt_data.get('Pos')[2])
                try:
                    store_key = struct.unpack(">LL", (self._storage_key_(
                        nbt_data.get('internalComponents').get('EntityStorageKeyComponent').get('StorageKey'))))

                except:
                    store_key = key
                for key in self.digp.keys():
                    for i, p in enumerate(self.digp[key]):
                        if store_key == p:
                            self.digp[key].remove(p)
                self.digp[(cx, cz, dim)].append(store_key)
                raw_actor_key = b''.join([b'actorprefix', struct.pack('>II', store_key[0], store_key[1])])
                raw_nbt_data = nbt_data.save_to(compressed=False, little_endian=True) \
                    .replace(b'\x07\n\x00StorageKey\x08\x00\x00\x00', b'\x08\n\x00StorageKey\x08\x00')
                self.level_db.put(raw_actor_key, raw_nbt_data)

            for data in self.digp.keys():
                cx, cz, dim = data
                new_concatination_data = b''
                if dim == 0:
                    raw_digp_key = b''.join([b'digp', struct.pack('<ii', cx, cz)])
                else:
                    raw_digp_key = b''.join([b'digp', struct.pack('<iii', cx, cz, dim)])
                for a, b in self.digp[data]:
                    new_concatination_data += struct.pack('>II', a, b)
                self.level_db.put(raw_digp_key, new_concatination_data)

            EntitiePlugin.Onmsgbox(self, "Entities Saved", "Complete")
        else:
            for snbt, key in zip(self.EntyData, self.Key_tracker):
                nbt_data = nbt.from_snbt(snbt)
                dim = struct.unpack("<i", self.get_dim_value())[0]
                cx, cz = block_coords_to_chunk_coords(nbt_data.get('Pos')[0], nbt_data.get('Pos')[2])
                actor_key = self.uuid_to_storage_key(nbt)
                self.actors[actor_key].clear()
                self.actors[actor_key].append(nbt.to_snbt(1))
                for k in self.digp.keys():
                    if actor_key in self.digp[k]:
                        self.digp[k].remove(actor_key)

                self.digp[(cx, cz, dim)].append(actor_key)

            for k, v in self.digp.items():
                chunk = self.world.level_wrapper.get_raw_chunk_data(k[0], k[1], self.canvas.dimension)
                chunk[b'2'] = b''
                for ak in v:
                    nbt_data = nbt.from_snbt(self.actors.get(ak)[0])
                    chunk[b'2'] += nbt_data.save_to(compressed=False, little_endian=True)

                self.world.level_wrapper.put_raw_chunk_data(k[0], k[1], chunk, self.canvas.dimension)

            EntitiePlugin.Onmsgbox(self, "Entities Saved", "Complete")

    def check_if_key_used(self, l, h):
        pass

    def build_actor_key(self, l, h):
        return b''.join([b'actorprefix', struct.pack('>ii', l, h)])

    def build_digp_chunk_key(self, xc, xz):
        if 'minecraft:the_end' in self.canvas.dimension:
            dim = int(2).to_bytes(4, 'little', signed=True)
        elif 'minecraft:the_nether' in self.canvas.dimension:
            dim = int(1).to_bytes(4, 'little', signed=True)
        elif 'minecraft:overworld' in self.canvas.dimension:
            dim = b''

        return b''.join([b'digp', struct.pack('<ii', xc, xz), dim])


    def digp_chunk_key_to_cords(self, data_key: bytes):
        xc, zc = struct.unpack_from("<ii", data_key, 4)
        if len(data_key) > 12:
            dim = struct.unpack_from("<i", data_key, 12)[0]
            return xc, zc, dim
        else:
            return xc, zc, 0

    def check_if_duplicate(self, nbt_enty):
        unique_id = nbt_enty.get('UniqueID')
        if unique_id in self.all_uniqueids:
            pass

    def convert_uniqueids(self, uid_or_enty_cnt, world_counter=0):
        l, h = 0, 0
        world_cnt, cnt_enty = b'', b''
        if isinstance(uid_or_enty_cnt, bytes):
            l, h = struct.unpack('<II', uid_or_enty_cnt)
            return l, h
        elif isinstance(uid_or_enty_cnt, int):
            cnt_enty = struct.pack('<I', uid_or_enty_cnt)
            world_cnt = struct.pack('<I', world_counter)
            return cnt_enty + world_cnt

    def save_chunk_backup(self, cx, cz, dimension, chunk):
        pathto = ""
        fname = "chk_" + str(cx) + "_" + str(cz) + "_" + str(
            dimension.replace(":", "_")) + "_Dont Remove first part.bak"
        fdlg = wx.FileDialog(self, "Save  Block Data", "", fname, "bakup files(*.bak)|*.*", wx.FD_SAVE)
        fdlg.ShowModal()
        pathto = fdlg.GetPath()
        if ".bak" not in pathto:
            pathto = pathto + ".bak"
        with open(pathto, "wb") as tfile:
            tfile.write(pickle.dumps(chunk))
            tfile.close()

    def load_chunk_backup(self):
        chunk_raw = b''
        fdlg = wx.FileDialog(self, "Load Block Data", "", "cx_cz_dimension_anyName.bak", "json files(*.bak)|*.*",
                             wx.FD_OPEN)
        if fdlg.ShowModal() == wx.ID_OK:
            pathto = fdlg.GetPath()
        with open(pathto, "rb") as tfile:
            chunk_raw = tfile.read()
            tfile.close()
        return chunk_raw

    @property
    def reuse_var(self):
        self.lstOfE = []
        # make sure to start fresh
        self.selection = self.canvas.selection.selection_group

    def get_dim_value(self):
        if 'minecraft:the_end' in self.canvas.dimension:
            dim = int(2).to_bytes(4, 'little', signed=True)
        elif 'minecraft:the_nether' in self.canvas.dimension:
            dim = int(1).to_bytes(4, 'little', signed=True)
        elif 'minecraft:overworld' in self.canvas.dimension:
            dim = int(0).to_bytes(4, 'little', signed=True)
        return dim

    def _load_entitie_data(self, event, bool1, bool2 ):
        self.reuse_var
        self._set_list_of_actors_digp
        self.get_raw_data_new_version(bool1,bool2)

        self.ui_entitie_choice_list.Set(self.lstOfE)

    @property
    def level_db(self):
        level_wrapper = self.world.level_wrapper
        if hasattr(level_wrapper, "level_db"):
            return level_wrapper.level_db
        else:
            return level_wrapper._level_manager._db

    def uuid_to_storage_key(self, nbt):
        uid = nbt.get("UniqueID").value
        uuid = struct.pack('<q', uid)
        # "converted to Long to see real data"
        acnt, wrldcnt = struct.unpack('<LL', uuid)
        wc = 4294967296 - wrldcnt
        actor_key = (wc, acnt)
        return actor_key

    def nbt_loder(self, raw):
        try:
            new_raw = nbt.load(raw.replace(b'\x08\n\x00StorageKey\x08\x00',
                       b'\x07\n\x00StorageKey\x08\x00\x00\x00'),compressed=False,little_endian=True)
        except:
            new_raw = nbt.load(raw,compressed=False, little_endian=True)
        return new_raw
    @property
    def _set_list_of_actors_digp(self):
        self.actors = collections.defaultdict(list)
        self.digp = collections.defaultdict(list)
        items = ""
        st = time.time_ns()

        if self.world.level_wrapper.version >= (1, 18, 30, 4, 0):
            self.not_to_remove = []
            actorprefixs = iter(self.level_db.iterate(start=b'actorprefix',
                                                      end=b'actorprefix\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF'))
            digps = iter(self.level_db.iterate(start=b'digp',
                                               end=b'digp\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF'))
            done_actors = False
            done_digps = False
            while not done_actors:
                try:
                    k,v = next(actorprefixs)
                except StopIteration:
                    done_actors = True
                else:
                    if  b"actorprefixb'\\" not in k:
                        # print(k, v)
                        # self.level_db.delete(k)
                        self.actors[struct.unpack('>II', k[11:])].append(v)

            while not done_digps:
                try:
                    k, v = next(digps)

                except StopIteration:
                    done_digps = True
                else:
                    if v != b'':
                        if len(k) == 12:
                            k += b'\x00\x00\x00\x00'
                        for p in range(0, len(v), 8):
                          #  print(v)
                            self.digp[struct.unpack('<iii', k[4:])].append(
                                struct.unpack('>II', v[p:p + 8]))
                            self.not_to_remove.append(struct.unpack('>II', v[p:p + 8]))
        else:

            self.EntyData.clear()  # make sure to start fresh
            nbt_ = amulet_nbt.NBTFile()
            dim = dim = struct.unpack("<i", self.get_dim_value())[0]
            world_start_count = self.world.level_wrapper.root_tag["worldStartCount"]
            all_chunks = [x for x in self.world.level_wrapper.all_chunk_coords(self.canvas.dimension)]
            for cx, cz in all_chunks:
                chunk = self.world.level_wrapper.get_raw_chunk_data(cx, cz, self.canvas.dimension)
                if chunk.get(b'2') != None:
                    max = len(chunk[b'2'])
                    cp = 0
                    while cp < max:
                        nbt, p = nbt.load(chunk[b'2'][cp:], little_endian=True, offset=True)
                        cp += p
                        actor_key = self.uuid_to_storage_key(nbt)
                        self.actors[actor_key].append(nbt.to_snbt(1))
                        self.digp[(cx, cz, dim)].append(actor_key)

    def _delete_all_the_dead(self, _):
        self._set_list_of_actors_digp
        self.the_dead = collections.defaultdict(list)
        count_deleted = 0
        for dv in self.actors.keys():
            if dv not in self.not_to_remove:
                key = b''.join([b'actorprefix', struct.pack('>II', dv[0], dv[1])])
                self.level_db.delete(key)
                count_deleted +=1
        self.ui_entitie_choice_list.Set([])
        EntitiePlugin.Onmsgbox(self,"DELETED",f"Deleted {count_deleted} ghosted entities . ")

    def _list_the_dead(self, _):
        self._set_list_of_actors_digp
        self.the_dead = collections.defaultdict(list)
        for dv in self.actors.keys():
            if dv not in self.not_to_remove:
                key = b''.join([b'actorprefix', struct.pack('>II', dv[0], dv[1])])
                data = self.level_db.get(key)
                nbt_ = nbt.load(data.replace(b'\x08\n\x00StorageKey\x08\x00',
                                            b'\x07\n\x00StorageKey\x08\x00\x00\x00'), little_endian=True)
                self.the_dead[key].append(nbt)

        self.EntyData.clear()
        self.lstOfE = []
        self.current_selection = []


        filter = self.exclude_filter.GetValue().split(",")
        custom_filter =  self.include_filter.GetValue().split(",")
        for k, v in self.the_dead.items():
            px, py, pz = '', '', ''
            name = str(v[0]['identifier']).replace("minecraft:", "")
            try:
                px, py, pz = v[0].get('Pos').value
            except:
                print("ERROR WHY")
                pass
              #  print(k, v, name, "wtf went wrong")
            if name not in filter and custom_filter == ['']:
                self.EntyData.append(v[0].to_snbt(1))
                self.lstOfE.append(
                    name + " , " + str(px).split(".")[0] + ", " + str(py).split(".")[0] + ", " + str(pz).split(".")[0])
                self.current_selection.append(k)
            if name in custom_filter:
                self.current_selection.append(k)
                self.EntyData.append(v[0].to_snbt(1))
                self.lstOfE.append(
                    name + " , " + str(px).split(".")[0] + ", " + str(py).split(".")[0] + ", " + str(pz).split(".")[0])
        #print(len(self.lstOfE), len(self.EntyData), len(self.current_selection), len(self.the_dead.items()))
        zipped_lists = zip(self.lstOfE, self.EntyData, self.current_selection)
        sorted_pairs = sorted(zipped_lists)
        tuples = zip(*sorted_pairs)
        self.lstOfE, self.EntyData, self.current_selection = [list(tuple) for tuple in tuples]
        self.ui_entitie_choice_list.Set(self.lstOfE)

    def _make_undead(self, _):
        res = EntitiePlugin.important_question(self)
        if res == False:
            return
        bring_back = nbt.from_snbt(self.EntyData[self.ui_entitie_choice_list.GetSelection()])
        raw_dead_actor_key = self.current_selection.pop(self.ui_entitie_choice_list.GetSelection())
        self.the_dead.pop(raw_dead_actor_key)
        try:
            recovory_key = self._storage_key_(
                bring_back["internalComponents"]["EntityStorageKeyComponent"]['StorageKey'])
        except:
            recovory_key = raw_dead_actor_key[11:]
          #  print(recovory_key)

        x, y, z = bring_back.get('Pos').value
       # print(x, y, z)
        try:
            bring_back["Attributes"][1]['Current'] = nbt.TAG_Float(20.)
            bring_back["Dead"] = nbt.TAG_Byte(0)
        except:
            pass
        raw_nbt_ = nbt.NBTFile(bring_back).save_to(compressed=False, little_endian=True) \
            .replace(b'\x07\n\x00StorageKey\x08\x00\x00\x00', b'\x08\n\x00StorageKey\x08\x00')
        self.level_db.put(raw_dead_actor_key, raw_nbt)
        for popoff in self.digp.keys():
            for d in self.digp[popoff]:
             #   print(self._storage_key_(recovory_key), d)
                if self._storage_key_(recovory_key) in d:
                    dd = self.digp[popoff].pop(d)

        xc, zc = block_coords_to_chunk_coords(x, z)
        digp_key = (xc, zc, struct.unpack('i', self.get_dim_value())[0])
        self.digp[digp_key].append(self._storage_key_(recovory_key))
        self.EntyData.pop(self.ui_entitie_choice_list.GetSelection())
        self.lstOfE.pop(self.ui_entitie_choice_list.GetSelection())
        self.ui_entitie_choice_list.Set(self.lstOfE)

        for dig in self.digp.keys():
            new_digp_data = b''
            for dig_data in self.digp[dig]:
                if dig[2] > 0:
                    chunk_loc = b'digp' + struct.pack('<i', dig[0]) + struct.pack('<i', dig[1]) + struct.pack('<i',
                                                                                                              dig[2])
                else:
                    chunk_loc = b'digp' + struct.pack('<i', dig[0]) + struct.pack('<i', dig[1])
                new_digp_data += struct.pack(">II", dig_data[0], dig_data[1])
            self.level_db.put(chunk_loc, new_digp_data)
    def _delete_from_list(self, e):
        res = EntitiePlugin.important_question(self)
        if res == False:
            return
        setdata = nbt.from_snbt(self.EntyData[self.ui_entitie_choice_list.GetSelection()])
        xc, xz = block_coords_to_chunk_coords(setdata.get("Pos")[0], setdata.get("Pos")[2])
        if self.world.level_wrapper.version >= (1, 18, 30, 4, 0):
            p_dig_key = self.build_digp_chunk_key(xc, xz)
            s_key = self._storage_key_(
                setdata.get('internalComponents').get("EntityStorageKeyComponent").get("StorageKey"))
            save_keys = []
            the_dig_keys = self.level_db.get(p_dig_key)
            for key_r in range(0, len(the_dig_keys), 8):
                current_key = the_dig_keys[key_r:key_r + 8]
                if s_key != current_key:
                    save_keys.append(current_key)
            if len(save_keys) > 0:
                self.level_db.put(p_dig_key, b''.join(save_keys))
            else:
                self.level_db.delete(p_dig_key)
            self.level_db.delete(b''.join([b'actorprefix', s_key]))
        else:
            raw_chunk = self.world.level_wrapper.get_raw_chunk_data(xc, xz, self.canvas.dimension)
            if raw_chunk[b'2']:
                point = len(raw_chunk[b'2'])
                pos = 0
                find_uuid = setdata.get('UniqueID')
                keep_data = []
                while pos < point:
                    data, p = amulet_nbt.load(raw_chunk[b'2'][pos:], compressed=False, little_endian=True, offset=True)
                    uuid = data.get('UniqueID')
                    if find_uuid != uuid:
                        keep_data.append(data)
                    pos += p
                new_data = b''
                for d in keep_data:
                    new_data += d.save_to(compressed=False, little_endian=True)
                raw_chunk[b'2'] = b''
                raw_chunk[b'2'] = new_data
                self.world.level_wrapper.put_raw_chunk_data(xc, xz, raw_chunk, self.canvas.dimension)
        self.world.save()
        self._load_entitie_data(e, False, self.get_all_flag)

class Java(wx.Panel):

    def __int__(self, world, canvas):
        wx.Panel.__init__(self, parent)
        self.world = world
        self.canvas = canvas
        select_chunks = self.canvas.selection.selection_group.chunk_locations()  # selection_group.chunk_locations()
        all_chunks = [x for x in self.world.level_wrapper.all_chunk_coords(self.canvas.dimension)]
        dim = struct.unpack("<i", self.get_dim_value())[0]
        custom_filter = self.filter.GetValue().split(",")

    def _delete_from_list(self, e):
        res = EntitiePlugin.important_question(self)
        if res == False:
            return
        setdata = nbt.from_snbt(self.EntyData[self.ui_entitie_choice_list.GetSelection()])
        xc, xz = block_coords_to_chunk_coords(setdata.get("Pos")[0], setdata.get("Pos")[2])
        find_uuid = setdata.get("UUID")
        rx, rz = world_utils.chunk_coords_to_region_coords(xc, xz)
        entitiesPath = self.get_dim_vpath_java_dir(rx, rz)  # full path for file
        self.Entities_region = AnvilRegion(entitiesPath)
        chunk = self.Entities_region.get_chunk_data(xc % 32, xz % 32)
        if self.world.level_wrapper.version >= 2730:
            for i, enty in enumerate(chunk['Entities']):
                if enty.get('UUID') == find_uuid:
                    chunk['Entities'].pop(i)
        else:
            for i, enty in enumerate(chunk['Level']['Entities']):
                if enty.get('UUID') == find_uuid:
                    chunk['Level']['Entities'].pop(i)
        self.Entities_region.put_chunk_data(xc % 32, xz % 32, chunk)
        self.Entities_region.save()

        self.world.save()
        self._load_entitie_data(e, False, self.get_all_flag)

    def _load_entitie_data(self, event, bool1, bool2 ):
        self.get_all_flag = bool2
        sel = SelectionGroup([])
        if bool2:
            self.canvas.selection.set_selection_group(sel)
        self._set_list_of_actors_digp
        self.ui_entitie_choice_list.Set([])
        self.ui_entitie_choice_list.Set(self.lstOfE)

    @property
    def _set_list_of_actors_digp(self):
        self.found_entities = []
        self.lstOfE = []
        self.EntyData = []
        if self.canvas.selection.selection_group:
            chunks = self.canvas.selection.selection_group.chunk_locations()
        else:
            chunks = [x for x in self.world.level_wrapper.all_chunk_coords(self.canvas.dimension)]
        rcords = collections.defaultdict(list)
        self.found_entities = nbt.ListTag()
        for xc , xz in chunks:
            rx, rz = world_utils.chunk_coords_to_region_coords(xc , xz)
            rcords[(rx, rz)].append((xc , xz))

        for rx, rz in rcords.keys():
            path = self.world.level_wrapper.path  # need path for file
            entitiesPath = self.get_dim_vpath_java_dir(rx,rz)  # full path for file
            file_exists = exists(entitiesPath)
            if file_exists:
                self.Entities_region = AnvilRegion(entitiesPath)  # create instance for region data
                for cx, cz in rcords[(rx, rz)]:

                    self.nbt_data = []
                    if self.Entities_region.has_chunk(cx % 32, cz % 32):
                        self.nbt_data_full = self.Entities_region.get_chunk_data(cx % 32, cz % 32)
                        if self.world.level_wrapper.version >= 2730:
                            self.nbt_data = self.nbt_data_full['Entities']
                        else:
                            self.nbt_data = self.nbt_data_full["Level"]['Entities']
                        for x in self.nbt_data:
                            self.found_entities.append(x)

        for nbt_ in self.found_entities:
            exclude_filter = self.exclude_filter.GetValue().split(",")
            include_filter = self.include_filter.GetValue().split(",")
            name = str(nbt_['id']).replace("minecraft:", "")
            if exclude_filter != ['']:
                if name not in exclude_filter:
                    self.lstOfE.append(name)
                    self.EntyData.append(nbt_.to_snbt(1))
            if include_filter != ['']:
                if name in include_filter:
                    self.lstOfE.append(name)
                    self.EntyData.append(nbt_.to_snbt(1))
            else:
                self.lstOfE.append(name)
                self.EntyData.append(nbt_.to_snbt(1))

        if len(self.EntyData) > 0:
            zipped_lists = zip(self.lstOfE, self.EntyData)
            sorted_pairs = sorted(zipped_lists)
            tuples = zip(*sorted_pairs)
            self.lstOfE, self.EntyData = [list(tuple) for tuple in tuples]

        if len(self.lstOfE) == 0:
            EntitiePlugin.Onmsgbox(self, "No Entities", "No Entities were found within the selecton")
            return

    def _move_copy_entitie_data(self, event, copy=False):
        res = EntitiePlugin.important_question(self)
        if res == False:
            return
        try:
            setdata = nbt.from_snbt(self.EntyData[self.ui_entitie_choice_list.GetSelection()])
        except:
            setdata = self.EntyData[self.ui_entitie_choice_list.GetSelection()]
        ox, oy, oz = setdata.get('Pos')
        nx = self._X.GetValue().replace(" X", "")
        ny = self._Y.GetValue().replace(" Y", "")
        nz = self._Z.GetValue().replace(" Z", "")
        location = nbt.TAG_List([nbt.TAG_Double(float(nx)), nbt.TAG_Double(float(ny)), nbt.TAG_Double(float(nz))])

        setdata["Pos"] = location
        data_nbt_ = setdata

        cx, cz = block_coords_to_chunk_coords(float(ox), float(oz))
        rx, rz = world_utils.chunk_coords_to_region_coords(cx, cz)

        self.Entities_region = AnvilRegion(self.get_dim_vpath_java_dir(rx, rz))
        nbt_reg = self.Entities_region.get_chunk_data(cx % 32, cz % 32)
        main_uuid = data_nbt.get('UUID')
        if copy:
            pass
        else:
            if self.world.level_wrapper.version >= 2730:
                for i, x in enumerate(nbt_reg['Entities']):
                    if main_uuid == x.get('UUID'):
                        nbt_reg['Entities'].pop(i)
            else:
                for i, x in enumerate(nbt_reg['Level']['Entities']):
                    if main_uuid == x.get('UUID'):
                        nbt_reg['Level']['Entities'].pop(i)

        self.Entities_region.put_chunk_data(cx % 32, cz % 32, nbt_reg)
        self.Entities_region.save()
        cx, cz = block_coords_to_chunk_coords(float(nx), float(nz))
        rx, rz = world_utils.chunk_coords_to_region_coords(cx, cz)
        file_exists = exists(self.get_dim_vpath_java_dir(rx, rz))
        if file_exists:
            self.Entities_region = AnvilRegion(self.get_dim_vpath_java_dir(rx, rz))
            if self.Entities_region.has_chunk(cx % 32, cz % 32):
                nbt_reg = self.Entities_region.get_chunk_data(cx % 32, cz % 32)
                if copy:
                    uu_id = uuid.uuid4()
                    q, w, e, r = struct.unpack('>iiii', uu_id.bytes)
                    setdata['UUID'] = amulet_nbt.TAG_Int_Array(
                        [amulet_nbt.TAG_Int(q), amulet_nbt.TAG_Int(w), amulet_nbt.TAG_Int(e),
                         amulet_nbt.TAG_Int(r)])
                if self.world.level_wrapper.version >= 2730:
                    nbt_reg['Entities'].append(setdata)
                else:
                    nbt_reg['Level']['Entities'].append(setdata)
                self.Entities_region.put_chunk_data(cx % 32, cz % 32, nbt_reg)
                self.Entities_region.save()
            else:
                if self.world.level_wrapper.version >= 2730:
                    new_data = amulet_nbt.NBTFile()
                    new_data['Position'] = amulet_nbt.from_snbt(f'[I; {cx}, {cz}]')
                    new_data['DataVersion'] = amulet_nbt.TAG_Int(self.world.level_wrapper.version)
                    new_data['Entities'] = amulet_nbt.TAG_List()
                    new_data['Entities'].append(setdata)
                    self.Entities_region.put_chunk_data(cx % 32, cz % 32, new_data)
                    self.Entities_region.save()
                else:
                    print("java version would leave hole in world , file")
        else:
            if self.world.level_wrapper.version >= 2730:
                self.Entities_region = AnvilRegion(self.get_dim_vpath_java_dir(rx, rz), create=True)
                new_data = amulet_nbt.NBTFile()
                new_data['Position'] = amulet_nbt.from_snbt(f'[I; {cx}, {cz}]')
                new_data['DataVersion'] = amulet_nbt.TAG_Int(self.world.level_wrapper.version)
                new_data['Entities'] = amulet_nbt.TAG_List()
                new_data['Entities'].append(setdata)
                self.Entities_region.put_chunk_data(cx % 32, cz % 32, new_data)
                self.Entities_region.save()
                print(f'SAVED CHUNK NEW FILE file r.{rx}, {rz} Chunk: {cx}, {cz}')
            else:
                print("java version would leave hole in world, No file")

        self.world.save()
        self._load_entitie_data(event, False, self.get_all_flag)

    def get_dim_vpath_java_dir(self, regonx,regonz):
        file =  "r." + str(regonx) + "." + str(regonz) + ".mca"
        path = self.world.level_wrapper.path
        full_path = ''
        if 'minecraft:the_end' in self.canvas.dimension:
            dim = 'DIM1'
        elif 'minecraft:the_nether' in self.canvas.dimension:
            dim = 'DIM-1'
        elif 'minecraft:overworld' in self.canvas.dimension:
            dim = ''
        if self.world.level_wrapper.version >= 2730:
            version = "entities"
        else:
            version = "region"
        full_path =  os.path.join(path,dim,version,file)
        return full_path

    def java_get_ver_path_data(self, nbt):

        if self.world.level_wrapper.version >= 2730:
            return nbt.get('Entities')
        else:
            return nbt.get("Level").get('Entities')

    def java_set_ver_path_data(self, add, this ):

        if self.world.level_wrapper.version >= 2730:
             if this == None:
                 add = amulet_nbt.TAG_List()
             add.append(this)
        else:
            if this == None:
                return
            add.append(this)
        return add

    def delete_un_or_selected_entities(self, event, unseleted):
        res = EntitiePlugin.important_question(self)
        if res == False:
            return
        chunk_regon_dict = collections.defaultdict(list)
        if unseleted:
            chunks = [x for x in self.world.level_wrapper.all_chunk_coords(self.canvas.dimension)]
            selected = self.canvas.selection.selection_group.chunk_locations()
        else:
            chunks = self.canvas.selection.selection_group.chunk_locations()
            selected = []
        for xc, xz in chunks:
            rx,rz = world_utils.chunk_coords_to_region_coords(xc,xz)
            the_file = self.get_dim_vpath_java_dir(rx,rz)
            file_exists = exists(the_file)
            if file_exists:
                chunk_regon_dict[(rx,rz, the_file)].append((xc, xz))
        for rx, rz, f in chunk_regon_dict.keys():
            self.Entities_region = AnvilRegion(f)
            for cx,cz in chunk_regon_dict[(rx, rz, f)]:
                if self.Entities_region.has_chunk(cx % 32, cz % 32):
                    self.chunk_data = self.Entities_region.get_chunk_data(cx % 32, cz % 32)
                    if self.world.level_wrapper.version >= 2730:
                        if (cx, cz) not in selected:
                            self.chunk_data['Entities'].clear()
                    else:
                        if (cx,cz) not in selected:
                            self.chunk_data['Level']['Entities'].clear()
                    self.Entities_region.put_chunk_data(cx % 32, cz % 32, self.chunk_data)
            self.Entities_region.save()
        self.world.save()
        self._load_entitie_data(event, False, self.get_all_flag)

    def _imp_entitie_data(self, _):

        dlg = ExportImportCostomDialog(None)
        dlg.InitUI(2)
        res = dlg.ShowModal()
        snbt_list = b''
        if dlg.nbt_file.GetValue():
            res = EntitiePlugin.important_question(self)
            if res == False:
                return
            try:
                self._import_nbt(_)
            except ValueError as e:
                EntitiePlugin.Onmsgbox(self, "No Selection", "You must select a area in the world to start from, \n Note: Just one block will work. It builds from the South/West")
            return

        if dlg.list.GetValue():
            res = EntitiePlugin.important_question(self)
            if res == False:
                return
            fdlg = wx.FileDialog(self, "Import Entities from a line list of snbt", "", "",
                                 f"SNBT (*.snbt_{self.world.level_wrapper.platform})|*.*", wx.FD_OPEN)
            if fdlg.ShowModal() == wx.ID_OK:
                pathto = fdlg.GetPath()
            else:
                return
            with open(pathto, "r") as tfile:
                snbt_list = tfile.readlines()
            loaction_dict = collections.defaultdict(list)
            for line in snbt_list:
                nbt_ = amulet_nbt.from_snbt(line)
                x,y,z = nbt_.get('Pos').value
                uu_id = uuid.uuid4()
                q, w, e, r = struct.unpack('>iiii', uu_id.bytes)
                nbt_['UUID'] = amulet_nbt.TAG_Int_Array(
                    [amulet_nbt.TAG_Int(q), amulet_nbt.TAG_Int(w), amulet_nbt.TAG_Int(e), amulet_nbt.TAG_Int(r)])
                bc,bz = block_coords_to_chunk_coords(x,z)
                rx,rz = world_utils.chunk_coords_to_region_coords(bc,bz)
                l_nbt_ = {}
                l_nbt_[(bc,bz)] = nbt_
                loaction_dict[(rx,rz)].append(l_nbt_)

            for rx,rz in loaction_dict.keys():
                file_exists = exists(self.get_dim_vpath_java_dir(rx,rz))
                if file_exists:
                    for di in loaction_dict[(rx,rz)]:
                        for k,v in di.items():
                            cx, cz = k
                            nbt_data = v
                            self.Entities_region = AnvilRegion(self.get_dim_vpath_java_dir(rx,rz))
                            if self.Entities_region.has_chunk(cx % 32, cz % 32):
                                nbtdata = self.Entities_region.get_chunk_data(cx % 32, cz % 32)
                                entitiedata = self.java_get_ver_path_data(nbtdata)
                                newData = self.java_set_ver_path_data(entitiedata, nbt_data)
                                self.Entities_region.put_chunk_data(cx % 32, cz % 32, nbtdata)
                                self.Entities_region.save()
                else:
                    if self.world.level_wrapper.version >= 2730:
                        new_data = amulet_nbt.NBTFile()
                        new_data['Position'] = amulet_nbt.from_snbt(f'[I; {cx}, {cz}]')
                        new_data['DataVersion'] = amulet_nbt.TAG_Int(self.world.level_wrapper.version)
                        new_data['Entities'] = amulet_nbt.TAG_List()
                        new_data['Entities'].append(nbt_data)
                        self.Entities_region.put_chunk_data(cx % 32, cz % 32, new_data)
                        self.Entities_region.save()
                        print(f'SAVED CHUNK file r.{rx}, {rz} Chunk: {cx}, {cz}, world genoration my kill entitiy')
                    else:
                        mc_id = new_data.get('id')
                        print(f'NO CHUNK DATA file r.{rx}, {rz} Chunk: {cx} , {cz} , pos: {(x,y,z)} , id: {mc_id}')
                        #  less than java version 2730
                            # can not store entities without leaving a chunk hole.

            self.canvas.run_operation(lambda: self._refresh_chunk_now(self.canvas.dimension, self.world, cx, cz))
            self.world.save()
            EntitiePlugin.Onmsgbox(self,"SNBT LIST", "Import Complete.")

        if dlg.ms_file.GetValue():
            snbt_list = []
            fdlg = wx.FileDialog(self, "Add Entities into a MCStructure File", "", "",
                                 "MCstructure files(*.mcstructure)|*.*", wx.FD_OPEN)
            if fdlg.ShowModal() == wx.ID_OK:
                pathto = fdlg.GetPath()
            else:
                return
            with open(pathto, "rb") as tfile:
                snbt_list = tfile.read()
                tfile.close()
            anbt_ = amulet_nbt.load(snbt_list, compressed=False, little_endian=True)
            sx,sy,sz = anbt.get("structure_world_origin")
            egx,egy,egz = anbt.get("size")
            ex, ey, ez = sx-egx,sy-egy,sz-egz
            group = []
            self.canvas.camera.set_location((sx, 70, sz))
            self.canvas.camera._notify_moved()
            s, e = (int(sx),int(sy),int(sz)), (int(ex), int(ey), int(ez))
            group.append(SelectionBox(s, e))
            sel_grp = SelectionGroup(group)
            self.canvas.selection.set_selection_group(sel_grp)

    def _exp_entitie_data(self, _):

        dlg = ExportImportCostomDialog(None)
        dlg.InitUI(1)
        res = dlg.ShowModal()
        chunks_to_backup = []
        if dlg.all_chunks.GetValue():
            chunks_to_backup = [x for x in self.world.level_wrapper.all_chunk_coords(self.canvas.dimension)]
        elif dlg.selected_chunks.GetValue():
            chunks_to_backup = self.canvas.selection.selection_group.chunk_locations()
        elif dlg.nbt_file_option.GetValue():
            self._export_nbt(_)
            return
        else:
            return
        snbt_lines = ""
        self.nbt_data = []
        regon_dict = collections.defaultdict(list)
        for cx, cz in chunks_to_backup:
            rx, rz = world_utils.chunk_coords_to_region_coords(cx, cz)
            regon_dict[(rx,rz)].append((cx,cz))
        for rx,rz in regon_dict.keys():
            entitiesPath = self.get_dim_vpath_java_dir(rx, rz)  # full path for file
            file_exists = exists(entitiesPath)

            if file_exists:
                self.Entities_region = AnvilRegion(entitiesPath)
                for cx,cz in regon_dict[rx,rz]:
                    if self.Entities_region.has_chunk(cx % 32, cz % 32):
                        self.nbt_data_full = self.Entities_region.get_chunk_data(cx % 32, cz % 32)

                        if self.world.level_wrapper.version >= 2730:
                            self.nbt_data = self.nbt_data_full['Entities']
                        else:
                            self.nbt_data = self.nbt_data_full["Level"]['Entities']
                        if len(self.nbt_data) > 0:
                            for x in self.nbt_data:
                                snbt_lines += x.to_snbt() + "\n"
        EntitiePlugin.save_entities_export(self, snbt_lines)
        EntitiePlugin.Onmsgbox(self, "SNBT LIST", "Export Complete.")

    def _save_data_to_world(self, _):
        res = EntitiePlugin.important_question(self)
        if res == False:
            return
        # newData = self.nbt_editor_instance.GetValue()  # get new data
        newData = NBTEditor.build_to(self.nbt_editor_instance, _)
        data = newData
        # data = nbt.from_snbt(newData)  # convert to nbt
        cx , cz = block_coords_to_chunk_coords(data.get("Pos")[0].value,data.get("Pos")[2].value)
        loc = data.get("Pos")
        uuid = data.get("UUID")
        rx, rz = world_utils.chunk_coords_to_region_coords(cx,cz)
        self.Entities_region = AnvilRegion(self.get_dim_vpath_java_dir(rx, rz))
        self.old_to_new_data = self.Entities_region.get_chunk_data(cx % 32, cz % 32)
        if self.world.level_wrapper.version >= 2730:
            for i, o in enumerate(self.old_to_new_data['Entities']):
                if o.get("UUID") == uuid:
                    self.old_to_new_data['Entities'][i] = data
        else:
            for i, o in enumerate(self.old_to_new_data["Level"]['Entities']):
                if o.get("UUID") == uuid:
                    self.old_to_new_data["Level"]['Entities'][i] = data
        self.EntyData[self.ui_entitie_choice_list.GetSelection()] = newData
        self.Entities_region.put_chunk_data(cx % 32, cz % 32, self.old_to_new_data)  # put data back where it goes
        self.Entities_region.save()  # save file operation
        self.world.save()
        EntitiePlugin.Onmsgbox(self,"Operation complete",
                      "The operation has completed without error:\n Save world to see the changes")

    def _export_nbt(self, _):
        entities = amulet_nbt.TAG_List()
        blocks = amulet_nbt.TAG_List()
        palette = amulet_nbt.TAG_List()
        DataVersion = amulet_nbt.TAG_Int(2975)
        selection = self.canvas.selection.selection_group.to_box()
        pallet_key_map = collections.defaultdict(list)
        nbt_state_map = collections.defaultdict(list)
        indx = 0
        sx, sy, sz = 0, 0, 0
        reps = EntitiePlugin.con_boc(self, "Air Blocks", 'Do you want to encude air block?')
        mx, my, mz = self.canvas.selection.selection_group.to_box().shape
        block_pos = []
        # bl = np.zeros(shape, dtype=numpy.uint32)
        for x in range(0, (mx)):
            for y in range(0, (my)):
                for z in range(0, (mz)):
                    block_pos.append((x, y, z))
        entities = self.get_entities_nbt(block_pos)
        prg_max = len(block_pos)
        prg_pre = 0
        prg_pre_th = len(block_pos) / 100
        self.prog = wx.ProgressDialog("Saving blocks", str(0) + " of " + str(prg_max),
                        style=wx.PD_AUTO_HIDE | wx.PD_CAN_ABORT | wx.PD_ELAPSED_TIME | wx.PD_REMAINING_TIME)
        self.prog.Show(True)
        for i, (s, b) in enumerate(zip(selection, block_pos)):
            if self.prog.WasCancelled():
                self.prog.Hide()
                self.prog.Destroy()
                break
            if i >= prg_pre_th:
                prg_pre_th += len(block_pos) / 100
                prg_pre += 1
                self.prog.Update(prg_pre, "Saving blocks " + str(i) + " of " + str(prg_max))
            block, blockEntity = self.world.get_version_block(s[0], s[1], s[2], self.canvas.dimension,
                                                              ("java", (1, 18, 0)))
            if not reps:
                check_string = ""
            else:
                check_string = 'minecraft:air'
            if str(block) != check_string:
                if pallet_key_map.get((block.namespaced_name, str(block.properties))) == None:
                    pallet_key_map[(block.namespaced_name, str(block.properties))] = indx
                    indx += 1
                    palette_Properties = amulet_nbt.TAG_Compound(
                        {'Properties': amulet_nbt.from_snbt(str(block.properties)),
                         'Name': amulet_nbt.TAG_String(block.namespaced_name)})
                    palette.append(palette_Properties)
                state = pallet_key_map[(block.namespaced_name, str(block.properties))]

                if blockEntity == None:
                    blocks_pos = amulet_nbt.TAG_Compound({'pos': amulet_nbt.TAG_List(
                        [amulet_nbt.TAG_Int(b[0]), amulet_nbt.TAG_Int(b[1]),
                         amulet_nbt.TAG_Int(b[2])]), 'state': amulet_nbt.TAG_Int(state)})
                    blocks.append(blocks_pos)
                else:
                    blocks_pos = amulet_nbt.TAG_Compound({'nbt': amulet_nbt.from_snbt(blockEntity.nbt.to_snbt()),
                                                          'pos': amulet_nbt.TAG_List(
                                                              [amulet_nbt.TAG_Int(b[0]),
                                                               amulet_nbt.TAG_Int(b[1]),
                                                               amulet_nbt.TAG_Int(b[2])]),
                                                          'state': amulet_nbt.TAG_Int(state)})
                    blocks.append(blocks_pos)
        prg_pre = 99
        self.prog.Update(prg_pre, "Finishing Up " + str(i) + " of " + str(prg_max))
        size = amulet_nbt.TAG_List([amulet_nbt.TAG_Int(mx), amulet_nbt.TAG_Int(my), amulet_nbt.TAG_Int(mz)])

        save_it = amulet_nbt.NBTFile()
        save_it['size'] = size
        save_it['entities'] = entities
        save_it['blocks'] = blocks
        save_it['palette'] = palette
        save_it['DataVersion'] = DataVersion
        raw_data = save_it.save_to(compressed=True, little_endian=False)
        prg_pre = 100
        self.prog.Update(prg_pre, "Done")
        pathto = ""
        fdlg = wx.FileDialog(self, "Save As .nbt", "", "", "nbt files(*.nbt)|*.*", wx.FD_SAVE)
        if fdlg.ShowModal() == wx.ID_OK:
            pathto = fdlg.GetPath()
        else:
            return False
        if ".nbt" not in pathto:
            pathto = pathto + ".nbt"
        with open(pathto, "wb") as tfile:
            tfile.write(raw_data)
            tfile.close()

        wx.MessageBox("Save Complete", "No Issues", wx.OK | wx.ICON_INFORMATION)

    def _import_nbt(self, _):

        fdlg = wx.FileDialog(self, "Load .nbt", "", "", "nbt files(*.nbt)|*.*", wx.FD_OPEN)
        if fdlg.ShowModal() == wx.ID_OK:
            pathto = fdlg.GetPath()
            nbt_ = amulet_nbt.load(pathto, compressed=True, little_endian=False, )
            block_platform = "java"
            block_version = (1, 18, 0)
            b_pos = []
            palette = []
            Name = []
            enbt_ = []
            xx = self.canvas.selection.selection_group.min_x
            yy = self.canvas.selection.selection_group.min_y
            zz = self.canvas.selection.selection_group.min_z
            reps = EntitiePlugin.con_boc(self, "Air Blocks", 'Do you want to encude air block?')
            for x in nbt.get('blocks'):
                if nbt['palette'][int(x.get('state'))].get('Properties') != None:
                    palette.append(
                        dict(amulet_nbt.from_snbt(nbt['palette'][int(x.get('state'))]['Properties'].to_snbt())))
                else:
                    palette.append(None)
                b_pos.append(x.get('pos'))
                Name.append(nbt['palette'][int(x.get('state'))]['Name'])
                if x.get('nbt') != None:
                    name = str(nbt['palette'][int(x.get('state'))]['Name']).split(':')

                    blockEntity = BlockEntity(name[0], name[1].replace('_', '').capitalize(), 0, 0, 0,
                                              amulet_nbt.NBTFile(x.get('nbt')))
                    enbt.append(blockEntity)
                else:
                    enbt.append(None)

            if not reps:
                check_string = ""
            else:
                check_string = 'minecraft:air'
            for x in zip(b_pos, palette, Name, enbt):
                if x[1] != check_string:
                    block = Block(str(x[2]).split(':')[0], str(x[2]).split(':')[1], x[1])
                    self.world.set_version_block(xx + x[0][0], yy + x[0][1], zz + x[0][2], self.canvas.dimension,
                                                 (block_platform, block_version), block, x[3])

            self.canvas.run_operation(lambda: self._refresh_chunk_now(self.canvas.dimension, self.world, xx, zz))
            self.world.save() # MUST SAVE NOW OR THIS WILL REMOVE ENTITIES
            e_nbt_list = []
            for x in nbt.get('entities'):
                if str(x) != '':
                    e_nbt_ = x.get('nbt')
                    nxx, nyy, nzz = x.get('pos').value

                    x['nbt']['Pos'] = amulet_nbt.TAG_List([amulet_nbt.TAG_Double(float(nxx + xx)),
                                                           amulet_nbt.TAG_Double(float(nyy + yy)),
                                                           amulet_nbt.TAG_Double(float(nzz + zz))])
                    e_nbt_list.append(x['nbt'])
            self.set_entities_nbt(e_nbt_list)


    def _refresh_chunk_now(self, dimension, world, x, z):
        cx, cz = block_coords_to_chunk_coords(x, z)
        chunk = world.get_chunk(cx, cz, dimension)
        chunk.changed = True

    def get_dim_value_bytes(self):
        if 'minecraft:the_end' in self.canvas.dimension:
            dim = int(2).to_bytes(4, 'little', signed=True)
        elif 'minecraft:the_nether' in self.canvas.dimension:
            dim = int(1).to_bytes(4, 'little', signed=True)
        elif 'minecraft:overworld' in self.canvas.dimension:
            dim = b''
        return dim

    def get_entities_nbt(self, rpos):
        mapdic = collections.defaultdict()

        entities = amulet_nbt.TAG_List()
        selection = self.canvas.selection.selection_group.to_box()
        for o, n in zip(selection, rpos):
            mapdic[o] = n
        chunk_min, chunk_max = self.canvas.selection.selection_group.min, \
                               self.canvas.selection.selection_group.max
        min_chunk_cords, max_chunk_cords = block_coords_to_chunk_coords(chunk_min[0], chunk_min[2]), \
                                           block_coords_to_chunk_coords(chunk_max[0], chunk_max[2])
        cl = self.canvas.selection.selection_group.chunk_locations()
        self.found_entities = amulet_nbt.TAG_List()
        self.nbt_data = []
        for cx, cz in cl:
            rx, rz = world_utils.chunk_coords_to_region_coords(cx, cz)  # need region cords for file
            self.Entities_region = AnvilRegion(self.get_dim_vpath_java_dir(rx, rz))
            self.nbt_data_full = self.Entities_region.get_chunk_data(cx % 32, cz % 32)

            if self.Entities_region.has_chunk(cx % 32, cz % 32):
                if self.world.level_wrapper.version >= 2730:
                    self.nbt_data = self.nbt_data_full['Entities']
                else:
                    self.nbt_data = self.nbt_data_full["Level"]['Entities']
                if len(self.nbt_data) > 0:
                    for x in self.nbt_data:
                        self.found_entities.append(x)

        if len(self.found_entities) == 0:
            return amulet_nbt.TAG_List()
        entities = amulet_nbt.TAG_List()
        for nbt_data in self.found_entities:
            x, y, z = math.floor(nbt_data.get('Pos')[0].value), math.floor(
                nbt_data.get('Pos')[1].value), math.floor(nbt_data.get('Pos')[2].value)
            if (x, y, z) in selection:
                new_pos = mapdic[(x, y, z)]
                nbt_pos = amulet_nbt.TAG_List([amulet_nbt.TAG_Double(sum([new_pos[0],
                                               math.modf(abs(nbt_data.get("Pos")[0].value))[0]])),
                                               amulet_nbt.TAG_Double(sum([new_pos[1],
                                               math.modf(abs(nbt_data.get("Pos")[1].value))[0]])),
                                               amulet_nbt.TAG_Double(sum([new_pos[2],
                                               math.modf(abs(nbt_data.get("Pos")[2].value))[0]]))])
                nbt_block_pos = amulet_nbt.TAG_List([amulet_nbt.TAG_Int(new_pos[0]),
                                                     amulet_nbt.TAG_Int(new_pos[1]),
                                                     amulet_nbt.TAG_Int(new_pos[2])])
                nbt_nbt_ = amulet_nbt.from_snbt(nbt_data.to_snbt())
                main_entry = amulet_nbt.TAG_Compound()
                main_entry['nbt'] = nbt_nbt
                main_entry['blockPos'] = nbt_block_pos
                main_entry['pos'] = nbt_pos
                entities.append(main_entry)

        return entities

    def set_entities_nbt(self, entities_list):
        entcnt = 0
        if self.world.level_wrapper.platform == "java":
            path = self.world.level_wrapper.path  # need path for file
            self.version_path = ""
            if self.world.level_wrapper.version >= 2730:
                self.version_path = "entities"
            else:
                self.version_path = "region"
            for nbt_data in entities_list:
                import uuid
                uu_id = uuid.uuid4()
                q, w, e, r = struct.unpack('>iiii', uu_id.bytes)
                nbt_data['UUID'] = amulet_nbt.TAG_Int_Array(
                    [amulet_nbt.TAG_Int(q), amulet_nbt.TAG_Int(w), amulet_nbt.TAG_Int(e), amulet_nbt.TAG_Int(r)])
                x, y, z = math.floor(nbt_data.get('Pos')[0].value), math.floor(
                    nbt_data.get('Pos')[1].value), math.floor(nbt_data.get('Pos')[2].value)
                cx, cz = block_coords_to_chunk_coords(x, z)
                rx, rz = world_utils.chunk_coords_to_region_coords(cx, cz)
                entitiesPath = self.get_dim_vpath_java_dir(rx,rz)  # full path for file
                file_exists = exists(entitiesPath)
                if file_exists:
                    self.Entities_region = AnvilRegion(entitiesPath)
                    if self.Entities_region.has_chunk(cx % 32, cz % 32):
                        self.chunk_raw = self.Entities_region.get_chunk_data(cx % 32, cz % 32)
                        if self.world.level_wrapper.version >= 2730:
                            if not self.chunk_raw.get('Entities'):
                                self.chunk_raw['Entities'] = amulet_nbt.TAG_List()

                            self.chunk_raw['Entities'].append(nbt_data)

                            self.Entities_region.put_chunk_data(cx % 32, cz % 32, self.chunk_raw)
                            self.Entities_region.save()
                            print(f' 1 SAVED CHUNK NEW FILE file r.{rx}, {rz} Chunk: {cx}, {cz}')
                        else:
                            if not self.chunk_raw.get('Level').get('Entities'):
                                self.chunk_raw["Level"]['Entities'] = amulet_nbt.TAG_List()
                            self.chunk_raw["Level"]['Entities'].append(nbt_data)
                            self.Entities_region.put_chunk_data(cx % 32, cz % 32, self.chunk_raw)
                            self.Entities_region.save()
                            print(self.chunk_raw["Level"])
                            print(f' 2 SAVED CHUNK NEW FILE file r.{rx}, {rz} Chunk: {cx}, {cz}')
                    else:
                        if self.world.level_wrapper.version >= 2730:
                            self.Entities_region = AnvilRegion(entitiesPath, create=True)
                            new_data = amulet_nbt.NBTFile()
                            new_data['Position'] = amulet_nbt.from_snbt(f'[I; {cx}, {cz}]')
                            new_data['DataVersion'] = amulet_nbt.TAG_Int(self.world.level_wrapper.version)
                            new_data['Entities'] = amulet_nbt.TAG_List()
                            new_data['Entities'].append(nbt_data)
                            self.Entities_region.put_chunk_data(cx % 32, cz % 32, new_data)
                            self.Entities_region.save()
                            print(f' 3 SAVED CHUNK NEW FILE file r.{rx}, {rz} Chunk: {cx}, {cz}')
                        else:
                            print(
                                f'4 NO CHUNK DATA file r.{rx}, {rz} Chunk: {cx} , {cz} ')
                            # java less than version 2730
                        # can not store entities without leaving hole
                else:
                    if self.world.level_wrapper.version >= 2730:
                        new_data = amulet_nbt.NBTFile()
                        new_data['Position'] = amulet_nbt.from_snbt(f'[I; {cx}, {cz}]')
                        new_data['DataVersion'] = amulet_nbt.TAG_Int(self.world.level_wrapper.version)
                        new_data['Entities'] = amulet_nbt.TAG_List()
                        new_data['Entities'].append(nbt_data)

                        self.Entities_region.put_chunk_data(cx % 32, cz % 32, new_data)
                        self.Entities_region.save()
                        print(f' 5 SAVED CHUNK NEW FILE file r.{rx}, {rz} Chunk: {cx}, {cz}')
                    else:
                        print(f' 6 NO CHUNK DATA file r.{rx}, {rz} Chunk: {cx} , {cz} ')  # #java less than version 2730
                        # can not store entities without leaving hole
            self.world.save()
            self._load_entitie_data('0',False,self.get_all_flag)

class EntitiePlugin(wx.Panel, DefaultOperationUI):

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
        main = wx.Panel.__init__(self, parent)
        DefaultOperationUI.__init__(self, parent, canvas, world, options_path)
        self.lstOfE = ['This List will Contain', 'Entities', "NOTE: the TAB key",
                       " to toggle Perspective", "Canvas must be active","Mouse over the canvas", "To activate canvas"]
        self.nbt_data = nbt.NBTFile()
        self.Freeze()
        self.EntyData = []
        self._highlight_edges = numpy.zeros((2, 3), dtype=bool)

        if platform == 'bedrock':
            self.operation = BedRock()
            self.operation.world = self.world
            self.operation.canvas = self.canvas
            self.operation.EntyData = self.EntyData

        else:
            self.operation = Java()
            self.operation.world = self.world
            self.operation.canvas = self.canvas
            self.operation.EntyData = self.EntyData
            self.operation.lstOfE =self.lstOfE

        self.operation.select_tracer = collections.defaultdict(list)
        self.get_all_flag = False
        self.operation.get_all_flag = self.get_all_flag

        self._sizer_v_main = wx.BoxSizer(wx.VERTICAL)
        self.left_sizer = wx.BoxSizer(wx.VERTICAL)
        self.right_sizer = wx.BoxSizer(wx.VERTICAL)

        self.bottom_h = wx.BoxSizer(wx.HORIZONTAL)
        self.top_sizer = wx.GridSizer(4, 3, 0, -1)
        self.button_group_one = wx.GridSizer(2, 2, 0, -20)
        self.button_group_two = wx.GridSizer(0, 3, 0,  1)
        self.button_group_three = wx.GridSizer(0, 2, 0, -1)
        self.button_group_four = wx.GridSizer(0, 4, 1, 1)

        self.SetSizer(self._sizer_v_main)
        self.operation.filter_include_label = wx.StaticText(self, label=" Include Filter:", size=(76,25))
        self.operation.filter_exclude_label = wx.StaticText(self, label=" Exclude Filter:", size=(76,25))
        self.operation.exclude_filter = wx.TextCtrl(self, style=wx.TE_LEFT, size=(120, 25))
        self.operation.include_filter = wx.TextCtrl(self, style=wx.TE_LEFT, size=(120, 25))

        self.button_group_four.Add(self.operation.filter_include_label)
        self.button_group_four.Add(self.operation.include_filter, 3, wx.LEFT, -20)
        self.button_group_four.Add(self.operation.filter_exclude_label)
        self.button_group_four.Add(self.operation.exclude_filter,3, wx.LEFT, -20)
        self.font_ex_in = wx.Font(12, wx.FONTFAMILY_ROMAN, wx.FONTSTYLE_MAX, wx.FONTWEIGHT_BOLD)
        self.operation.exclude_filter.SetForegroundColour((0,  0, 0))
        self.operation.exclude_filter.SetBackgroundColour((255, 0, 0))
        self.operation.include_filter.SetForegroundColour((0, 0, 0))
        self.operation.include_filter.SetBackgroundColour((0, 255, 0))
        self.operation.include_filter.SetFont(self.font_ex_in)
        self.operation.exclude_filter.SetFont(self.font_ex_in)
        self.operation.exclude_filter.SetToolTip(".Seporate with a comma , "
                                                 "to exclude more that one, Dont use Filters together")

        self.operation.include_filter.SetToolTip("Seporate with a comma , "
                                                 "to enclude more that one, Dont use Filters together")

        self._sizer_v_main.Add(self.top_sizer)
        self._sizer_v_main.Add(self.button_group_four)
        self._sizer_v_main.Add(self.bottom_h)
        self.font = wx.Font(11, wx.FONTFAMILY_ROMAN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)

        self.delete_selected = wx.Button(self, label="Delete All Selected")
        self.list_dead = wx.Button(self, label="List Dead", size=(60, 20))
        self.make_undead = wx.Button(self, label="Make UnDead", size=(80, 20))
        self.delete_unselected = wx.Button(self, label="Delete All Un_Selected")
        self._move = wx.Button(self, label="Move", size=(40, 24))
        self._copy = wx.Button(self, label="Copy", size=(40, 24))
        self._delete = wx.Button(self, label="Delete", size=(40, 24))
        self._get_button = wx.Button(self, label="Get Entities", size=(70, 20))
        self._get_all_button = wx.Button(self, label="Get All",size=(60, 20))
        self._get_all_button.SetToolTip("Get All Entities in the dimension and unselects any selections")
        self._get_button.SetToolTip("Get All Entities within the selected chunk area. "
                                    "Note: selection shows the hole chunk")
        self._set_button = wx.Button(self, label="Apply Changes")
        self.operation._imp_button = wx.Button(self, label="Import Entities")
        self.operation._exp_button = wx.Button(self, label="Export Entities")
        self._teleport_check = wx.CheckBox(self, label="Auto teleportation")
        self._teleport_check.SetValue(True)
        self._move.SetToolTip("Prepares the new position (from cords above) for the selected entitiy ")
        self._copy.SetToolTip("Prepares a copy of the entities and sets its location (from cords above)")
        self._delete.SetToolTip("Delete the selected entitie")
        self.delete_selected.SetToolTip(
            "Immediately Deletes All Selected areas with Entities From World, "
            "\n NOTE: There is No Undo, Also Entities may be stored in a different chunk , Be sure to have a Backup! ")
        self.delete_unselected.SetToolTip(
            "Immediately Deletes All Un_Selected Entities From World,  "
            "\n NOTE: There is No Undo, Also Entities may be stored in a different chunk , Be sure to have a Backup! ")

        self.delete_unselected.Bind(wx.EVT_BUTTON,
                                    lambda event: self.operation.delete_un_or_selected_entities(event, True))
        self.delete_selected.Bind(wx.EVT_BUTTON,
                                  lambda event: self.operation.delete_un_or_selected_entities(event, False))
        self._move.Bind(wx.EVT_BUTTON, lambda event: self.operation._move_copy_entitie_data(event, False))
        self._copy.Bind(wx.EVT_BUTTON, lambda event: self.operation._move_copy_entitie_data(event, True))
        self._delete.Bind(wx.EVT_BUTTON, lambda event: self.operation._delete_from_list(event))
        self._get_button.Bind(wx.EVT_BUTTON, lambda event: self.operation._load_entitie_data(event,False , False))
        self._get_all_button.Bind(wx.EVT_BUTTON, lambda event: self.operation._load_entitie_data(event, False, True))
        self.list_dead.Bind(wx.EVT_BUTTON, lambda event: self.operation._list_the_dead(event))
        self.make_undead.Bind(wx.EVT_BUTTON, lambda event: self.operation._make_undead(event))
        self._set_button.Bind(wx.EVT_BUTTON, lambda event: self.operation._save_data_to_world(event))
        self.operation._imp_button.Bind(wx.EVT_BUTTON, self.operation._imp_entitie_data)
        self.operation._exp_button.Bind(wx.EVT_BUTTON, self.operation._exp_entitie_data)

        self.operation._X = wx.TextCtrl(self, style=wx.TE_LEFT)  # "X of Selected")
        self.operation._Y = wx.TextCtrl(self, style=wx.TE_LEFT)  # "Y of Selected")
        self.operation._Z = wx.TextCtrl(self, style=wx.TE_LEFT)  # "Z of Selected")
        self.operation._X.SetForegroundColour((0, 255, 255))
        self.operation._Y.SetForegroundColour((255, 0, 0))
        self.operation._Z.SetForegroundColour((255, 255, 0))
        self.operation._X.SetBackgroundColour((255, 0, 0))
        self.operation._Y.SetBackgroundColour((0,255, 0))
        self.operation._Z.SetBackgroundColour((0, 0, 255))
        self.operation._X.SetLabel("X of Selected")
        self.operation._Y.SetLabel("Y of Selected")
        self.operation._Z.SetLabel("Z of Selected")
        self.operation._X.SetFont(self.font_ex_in)
        self.operation._Y.SetFont(self.font_ex_in)
        self.operation._Z.SetFont(self.font_ex_in)

        self.top_sizer.Add(self.delete_unselected,0 ,wx.TOP, 5)
        self.top_sizer.Add(self.operation._imp_button,0 ,wx.TOP, 5)
        self.button_group_three.Add(self._get_button,0 ,wx.TOP, 5)
        self.button_group_three.Add(self._get_all_button ,0 ,wx.TOP, 5)
        self.top_sizer.Add(self.button_group_three,0 ,wx.TOP, 1)

        self.top_sizer.Add(self.delete_selected)

        self.top_sizer.Add(self.operation._exp_button)
        self.top_sizer.Add(self._set_button )

        self.top_sizer.Add(self.operation._X ,0 ,wx.TOP, -5)
        self.top_sizer.Add(self.operation._Y,0 ,wx.TOP, -5)
        self.top_sizer.Add(self.operation._Z,0 ,wx.TOP, -5)
        self.del_ghosts = wx.Button(self, label="Delete All", size=(60, 20))
        self.del_ghosts.SetToolTip("Delete all dead unlinked entities.")
        self.del_ghosts.Bind(wx.EVT_BUTTON, lambda event: self.operation._delete_all_the_dead(event))
        self.button_group_one.Add(self.list_dead)
        self.button_group_one.Add(self.make_undead)
        self.button_group_one.Add(self.del_ghosts)
        if self.world.level_wrapper.platform == "bedrock":
            if self.world.level_wrapper.version < (1, 18, 30, 4, 0):
                self.list_dead.Hide()
                self.make_undead.Hide()
                self.del_ghosts.Hide()
        elif self.world.level_wrapper.platform == "java":
            self.list_dead.Hide()
            self.make_undead.Hide()
            self.del_ghosts.Hide()
        self.top_sizer.Add(self.button_group_one,0 ,wx.TOP, -10)
        self.top_sizer.Add(self._teleport_check, 0 ,wx.LEFT, 7)

        self.button_group_two.Add(self._move)
        self.button_group_two.Add(self._copy)
        self.button_group_two.Add(self._delete)
        self.top_sizer.Add(self.button_group_two )

        self.operation.ui_entitie_choice_list = wx.ListBox(self, style=wx.LB_HSCROLL, choices=self.lstOfE, pos=(0, 20),
                                                 size=(140, 800))
        self.operation.nbt_editor_instance = NBTEditor(self)
        self.bottom_h.Add(self.operation.nbt_editor_instance, 130, wx.EXPAND,21)
        self.operation.ui_entitie_choice_list.SetFont(self.font)
        self.operation.ui_entitie_choice_list.Bind(wx.EVT_LISTBOX, lambda event: self.on_focus(event))

        self.bottom_h.Add(self.operation.ui_entitie_choice_list, 50, wx.RIGHT , 0 )
        self.operation.ui_entitie_choice_list.SetBackgroundColour((0, 0, 0))
        self.operation.ui_entitie_choice_list.SetForegroundColour((255, 255, 0))

        self.bottom_h.Fit(self)
        self._sizer_v_main.Fit(self)
        self.Layout()
        self.Thaw()

    # self.nbt_editor_instance.Bind(wx.EVT_KEY_UP, self.autoSaveOnKeyPress)
    def bind_events(self):
        super().bind_events()
        self.canvas.Bind(EVT_SELECTION_CHANGE, self._set_new_block)
        self._selection.bind_events()
        self._selection.enable()

    def enable(self):
        #self.canvas.camera.projection_mode = Projection.TOP_DOWN
        self._selection = BlockSelectionBehaviour(self.canvas)
        self._selection.enable()

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

    def update_player_data(self, new_data):
        self_ = self.Parent.Parent
        # nbt.from_snbt(self.operation.EntyData[self.operation.ui_entitie_choice_list.GetSelection()])
        save_expanded = []
        f_root = self_.operation.nbt_editor_instance.tree.GetRootItem()
        r_c = self_.operation.nbt_editor_instance.tree.GetChildrenCount(f_root, 0)

        def get_full_path(child):
            tree = self_.operation.nbt_editor_instance.tree
            index = 0
            p_type = None
            the_sib_items = None
            nbt_path_keys = []
            if isinstance(tree.GetItemData(child), tuple):
                name, data = tree.GetItemData(child)
                nbt_path_keys.append(name)
            sibl = tree.GetItemParent(child)
            while sibl.IsOk():
                the_sib_items = sibl
                if isinstance(tree.GetItemData(sibl), tuple):
                    p_type = type(tree.GetItemData(sibl)[1])
                else:
                    p_type = tree.GetItemData(sibl)


                if p_type == nbt.ListTag or p_type == nbt.CompoundTag:

                    item_num = tree.GetChildrenCount(sibl, recursively=False)
                    f_child, f_c = tree.GetFirstChild(sibl)
                    f_item = child
                    for c in range(item_num):
                        if f_child == f_item:
                            index = c
                            break
                        f_child, f_c = tree.GetNextChild(f_child, f_c)
                    nbt_path_keys.append(index)
                if isinstance(tree.GetItemData(sibl), tuple):
                    nname, ddata = tree.GetItemData(sibl)
                    nbt_path_keys.append(nname)
                sibl = tree.GetItemParent(sibl)
            nbt_path_keys.reverse()
            return nbt_path_keys[1:]

        def root_path(child):
            tree = self_.operation.nbt_editor_instance.tree
            nbt_path_keys = []
            if isinstance(tree.GetItemData(child), tuple):
                name, data = tree.GetItemData(child)
                nbt_path_keys.append(name)
            sibl = tree.GetItemParent(child)
            while sibl.IsOk():
                if isinstance(tree.GetItemData(sibl), tuple):
                    nname, ddata = tree.GetItemData(sibl)
                    if ddata == nbt.ListTag:
                        index = 0
                        item_num = tree.GetChildrenCount(sibl, recursively=False)
                        f_child, f_c = tree.GetFirstChild(sibl)
                        f_item = child
                        f_par = tree.GetItemParent(f_item)
                        if len(nbt_path_keys) > 0:
                            for xx in range(len(nbt_path_keys)-1):
                                f_par = tree.GetItemParent(f_par)
                        else:
                            f_par = child
                        for c in range(item_num):
                            if f_child == f_par:
                                index = c
                                nbt_path_keys.append(index)
                            f_child, f_c = tree.GetNextChild(f_child, f_c)
                    nbt_path_keys.append(nname)
                sibl = tree.GetItemParent(sibl)
            nbt_path_keys.reverse()
            return nbt_path_keys[1:]

        def recurtree(item):
            # for c in range(r_c):
            if item.IsOk():
                i_c = self_.operation.nbt_editor_instance.tree.GetChildrenCount(item, recursively=True)
                f_ic, cc_i = self_.operation.nbt_editor_instance.tree.GetFirstChild(item)
                for ci in range(i_c):
                    if f_ic.IsOk():

                        if self_.operation.nbt_editor_instance.tree.IsExpanded(f_ic):
                            save_expanded.append(copy.copy(root_path(f_ic)))
                        if self_.operation.nbt_editor_instance.tree.GetChildrenCount(f_ic) > 0:
                            recurtree(f_ic)
                    f_ic, cc_i = self_.operation.nbt_editor_instance.tree.GetNextChild(f_ic, cc_i)



        recurtree(f_root)
        current_scr_h = self_.operation.nbt_editor_instance.tree.GetScrollPos(orientation=wx.VERTICAL)

        self_.bottom_h.Detach(self_.operation.nbt_editor_instance)
        self_.bottom_h.Detach(self_.operation.ui_entitie_choice_list)
        self_.operation.nbt_editor_instance.Hide()
        NBTEditor.close(self_.operation.nbt_editor_instance, None, self_.GetParent())
        self_.operation.nbt_editor_instance = NBTEditor(self_, new_data)
        self_.bottom_h.Add(self_.operation.nbt_editor_instance, 130, wx.EXPAND, 21)
        self_.bottom_h.Add(self_.operation.ui_entitie_choice_list, 50, wx.RIGHT, 0)

        self_.nbt_editor_instance = NBTEditor(self_, new_data)
        root = self_.operation.nbt_editor_instance.tree.GetRootItem()
        first_c ,c = self_.operation.nbt_editor_instance.tree.GetFirstChild(root)
        def re_expand(item):
            if item.IsOk():
                i_c = self_.operation.nbt_editor_instance.tree.GetChildrenCount(item)
                f_ic, cc_i = self_.operation.nbt_editor_instance.tree.GetFirstChild(item)
                for ci in range(i_c):
                    if f_ic.IsOk():
                        if root_path(f_ic) in save_expanded:
                            self_.operation.nbt_editor_instance.tree.Expand(f_ic)
                        if self_.operation.nbt_editor_instance.tree.GetChildrenCount(f_ic) > 0:
                            re_expand(f_ic)
                    f_ic, cc_i = self_.operation.nbt_editor_instance.tree.GetNextChild(f_ic, cc_i)
        self_.operation.nbt_editor_instance.tree.Expand(first_c)
        re_expand(root)
        self_.operation.nbt_editor_instance.tree.SetScrollPos(wx.VERTICAL, current_scr_h)
        self_.bottom_h.Layout()
        self_.bottom_h.Fit(self_)
        self_._sizer_v_main.Fit(self_)
        self_._sizer_v_main.Layout()
        self_.Fit()
        self_.Layout()

        self.Close()


    def get_dir_path(self, foldername, cx, cz):
        return os.path.join(os.getcwd(), "plugins", "operations", foldername,
                            "chunk_bk_up" + str(cx) + "." + str(cz) + ".txt")

    def create_saved_entities_dir(self, foldername):
        if not os.path.exists(os.path.join(os.getcwd(), "plugins", "operations", foldername)):
            os.makedirs(os.path.join(os.getcwd(), "plugins", "operations", foldername))
            print("Created Save Dir")

    def Onmsgbox(self, caption, message):  # message
        wx.MessageBox(message, caption, wx.OK | wx.ICON_INFORMATION)

    def autoSaveOnKeyPress(self, _):

        selection = self.operation.ui_entitie_choice_list.GetSelection()
        # newData = self.operation.nbt_editor_instance.GetValue()
        try:
            self.operation.EntyData[selection] = nbt.NBTFile(nbt.from_snbt(newData))
        except:
            self.Onmsgbox("syntax error", "Try agian")
            setdata = self.operation.EntyData[selection]
            # try:
            #     self.operation.nbt_editor_instance.SetValue(nbt.from_snbt(setdata).to_snbt(1))
            # except:
            #     self.operation.nbt_editor_instance.SetValue(setdata.to_snbt(1))


    def on_focus(self, evt):

        setdata = nbt.from_snbt(self.operation.EntyData[self.operation.ui_entitie_choice_list.GetSelection()])
        self.bottom_h.Detach(self.operation.nbt_editor_instance)
        self.bottom_h.Detach(self.operation.ui_entitie_choice_list)
        self.operation.nbt_editor_instance.Hide()
        NBTEditor.close(self.operation.nbt_editor_instance, evt, self.GetParent())
        self.operation.nbt_editor_instance = NBTEditor(self, setdata)
        self.bottom_h.Add(self.operation.nbt_editor_instance, 130, wx.EXPAND, 21)
        self.bottom_h.Add(self.operation.ui_entitie_choice_list, 50, wx.RIGHT, 0)
        self.bottom_h.Layout()
        self.bottom_h.Fit(self)
        self._sizer_v_main.Fit(self)
        self._sizer_v_main.Layout()
        self.Fit()
        self.Layout()

        # self.operation.nbt_editor_instance.SetValue(setdata.to_snbt(1))
        # self.operation.nbt_editor_instance.
        (x, y, z) = setdata.get('Pos')[0], setdata.get('Pos')[1], setdata.get('Pos')[2]
        self.operation._X.SetLabel(str(x).replace("f", " X").replace("d", " X"))
        self.operation._Y.SetLabel(str(y).replace("f", " Y").replace("d", " Y"))
        self.operation._Z.SetLabel(str(z).replace("f", " Z").replace("d", " Z"))
        X = int(str(self.operation._X.GetValue()).replace(" X", "").split(".")[0])
        Y = int(str(self.operation._Y.GetValue()).replace(" Y", "").split(".")[0])
        Z = int(str(self.operation._Z.GetValue()).replace(" Z", "").split(".")[0])
        blockPosdata = {}
        group = []
        xx,zz = 1,1
        v = (
            (X),
            (Y),
            (Z))
        if X < 0:
            xx = -1
        if Z < 0:
            zz = -1
        vv = ((X+xx),
              (Y+1),
               (Z+zz))
        group.append(SelectionBox(v, vv))
        sel = SelectionGroup(group)
        self.canvas.selection.set_selection_group(sel)
        if self._teleport_check.GetValue():
            x, y, z = (x, y, z)
            self.canvas.camera.set_location((x, Y+10, z))
            self.canvas.camera.set_rotation((34.720000000000006, 90))
            self.canvas.camera._notify_moved()

    def _refresh_chunk(self, dimension, world, x, z):
        self.world.level_wrapper.load_chunk(x, z, dimension).changed = True
        self.world.create_undo_point()

    def _undo_it(self, _):
        cx, cz = block_coords_to_chunk_coords(self.canvas.selection.selection_group.selection_boxes[0].min_x,
                                              self.canvas.selection.selection_group.selection_boxes[0].min_z)
        enty = self.canvas.world.get_native_entities(cx, cz, self.canvas.dimension)
    def _set_new_block(self, _):
        if self.canvas.selection.selection_group:
            if 'Y of Selected' not in self.operation._Y.GetValue():
                fx = float(self.operation._X.GetValue().replace(" X", ""))
                fy = float(self.operation._Y.GetValue().replace(" Y", ""))
                fz = float(self.operation._Z.GetValue().replace(" Z", ""))
                s_x_, s_y_, s_z_ = self.canvas.selection.selection_group.max
                self.operation._X.SetLabel(str(s_x_) + "." + str(fx).split('.')[1] + " X")
                self.operation._Y.SetLabel(str(s_y_) + "." + str(fy).split('.')[1] + " Y")
                self.operation._Z.SetLabel(str(s_z_) + "." + str(fz).split('.')[1] + " Z")

    def save_entities_export(self, snbt_list):

        pathto = ""
        fname = "one entity per line.snbt"
        fdlg = wx.FileDialog(self, "Export Entities", "", "",
                             f"SNBT (*.snbt_{self.world.level_wrapper.platform})|*.*", wx.FD_SAVE)
        if fdlg.ShowModal() == wx.ID_OK:
            pathto = fdlg.GetPath()
        else:
            return False
        if ".snbt" not in pathto:
            pathto = pathto + ".snbt"
        with open(pathto, "w") as tfile:
            tfile.write(snbt_list)
            tfile.close()
        return True

    def load_entities_export(self):
        snbt_list = []
        fdlg = wx.FileDialog(self, "Import Entities", "", "",
                             f"SNBT (*.snbt_{self.world.level_wrapper.platform})|*.*", wx.FD_OPEN)
        if fdlg.ShowModal() == wx.ID_OK:
            pathto = fdlg.GetPath()
        else:
            return
        with open(pathto, "r") as tfile:
            snbt_list = tfile.readlines()
            tfile.close()
        return snbt_list

    def important_question(self):
        dialog = wx.MessageDialog(self, "   Including entities directly edits the world and there is no (Ctrl-Z ) Undo."
                                        "\n Would you like to save any current pending changes or discard them?"
                                        "\n     This needs to remove all current undo points"
                                        "\n To prevent conflicts that could occur"
                                        "\n    I suggest making a .snbt list all chunk entities export, "
                                        "\nso you can start over easy."
                                        "\nWhat do you wish to do?", "NOTICE",
                                  wx.ICON_EXCLAMATION | wx.YES_NO | wx.CANCEL | wx.CANCEL_DEFAULT)
        dialog.SetYesNoLabels('Save changes', 'Discard changes')
        responce = dialog.ShowModal()
        dialog.Destroy()
        if responce == wx.ID_YES:
            self.world.save()
            self.world.purge()
            pass
        elif responce == wx.ID_NO:
            self.world.purge()
            pass
        else:
            return False
        pass

class ExportImportCostomDialog(wx.Dialog):

    def __init__(self, *args, **kw):
        super(ExportImportCostomDialog, self).__init__(*args, **kw)
        self.InitUI()
        self.SetSize(500, 160)

    def InitUI(self, *ar):
        if len(ar) > 0:
            print(ar)
            if ar[0] == 1:
                self.Export()
            if ar[0] == 2:
                self.Import()

    def Export(self):
        self.SetTitle("Export")
        panel = wx.Panel(self)
        vert_box = wx.BoxSizer(wx.VERTICAL)
        static_box = wx.StaticBox(panel)
        static_box_sizer = wx.StaticBoxSizer(static_box, orient=wx.VERTICAL)
        static_box.SetLabel('Select Export Type:')
        image = wx.ArtProvider.GetBitmap(wx.ART_QUESTION)
        image_placer = wx.BoxSizer(wx.HORIZONTAL)
        self.bitmap = wx.StaticBitmap(self, -1, image, pos=(200, 20))
        image_placer.Add(self.bitmap)
        self.selected_chunks = wx.RadioButton(panel, label='Selected Chunks .snbt list')
        self.all_chunks = wx.RadioButton(panel, label='All Chunks .snbt list')
        self.nbt_file_option = wx.RadioButton(panel, label='NBT Structure File')
        static_box_sizer.Add(self.selected_chunks)
        static_box_sizer.Add(self.all_chunks)
        static_box_sizer.Add(self.nbt_file_option)
        panel.SetSizer(static_box_sizer)
        hor_box = wx.BoxSizer(wx.HORIZONTAL)
        self.okButton = wx.Button(self)
        self.selected_chunks.Bind(wx.EVT_RADIOBUTTON, self.setbuttonEL)
        self.all_chunks.Bind(wx.EVT_RADIOBUTTON, self.setbuttonEL)
        self.nbt_file_option.Bind(wx.EVT_RADIOBUTTON, self.setbuttonEL)
        closeButton = wx.Button(self, label='Cancel')
        hor_box.Add(self.okButton)
        hor_box.Add(closeButton, flag=wx.LEFT, border=5)
        vert_box.Add(panel, proportion=1, flag=wx.ALL | wx.EXPAND, border=5)
        vert_box.Add(hor_box, flag=wx.ALIGN_CENTER | wx.TOP | wx.BOTTOM, border=10)
        self.SetSizer(vert_box)
        self.okButton.Bind(wx.EVT_BUTTON, self.OnClose)
        closeButton.Bind(wx.EVT_BUTTON, self.OnCancelEX)
        self.Bind(wx.EVT_CLOSE, self.OnCancelEX)

    def setbuttonEL(self, e):
        if self.selected_chunks.GetValue():
            self.okButton.SetLabel(self.selected_chunks.GetLabel())
        if self.all_chunks.GetValue():
            self.okButton.SetLabel(self.all_chunks.GetLabel())
        if self.nbt_file_option.GetValue():
            self.okButton.SetLabel(self.nbt_file_option.GetLabel())
            
    def Import(self):
        self.SetTitle("Import")

        panel = wx.Panel(self)
        vert_box = wx.BoxSizer(wx.VERTICAL)
        static_box = wx.StaticBox(panel)
        static_box.SetLabel('Select Import Type:')
        static_box_sizer = wx.StaticBoxSizer(static_box, orient=wx.VERTICAL)
        image = wx.ArtProvider.GetBitmap(wx.ART_QUESTION)
        image_placer = wx.BoxSizer(wx.HORIZONTAL)
        self.bitmap = wx.StaticBitmap(self, -1, image, pos=(200, 20))
        image_placer.Add(self.bitmap)
        self.list = wx.RadioButton(panel, label='A Entitie .snbt list to world')
        self.nbt_file = wx.RadioButton(panel, label='NBT Structure File')
        self.ms_file = wx.RadioButton(panel, label='Open and Add Entities to MCStructure File')
        self.ms_file.SetToolTip("This Will go the the location where created and pull the Entities from where they are,"
                                "NOTE:  They wont get added if they are not there")
        static_box_sizer.Add(self.list)
        static_box_sizer.Add(self.nbt_file)
        static_box_sizer.Add(self.ms_file)
        panel.SetSizer(static_box_sizer)
        hor_box = wx.BoxSizer(wx.HORIZONTAL)
        self.okButton = wx.Button(self)
        self.list.Bind(wx.EVT_RADIOBUTTON, self.setbuttonIM)
        self.nbt_file.Bind(wx.EVT_RADIOBUTTON, self.setbuttonIM)
        self.ms_file.Bind(wx.EVT_RADIOBUTTON, self.setbuttonIM)
        closeButton = wx.Button(self, label='Cancel')
        hor_box.Add(self.okButton, flag=wx.TOP)
        hor_box.Add(closeButton, flag=wx.LEFT, border=5)
        vert_box.Add(panel, proportion=1, flag=wx.ALL | wx.EXPAND, border=5)
        vert_box.Add(hor_box, flag=wx.ALIGN_CENTER | wx.TOP | wx.BOTTOM, border=10)
        self.SetSizer(vert_box)
        self.okButton.Bind(wx.EVT_BUTTON, self.OnClose)
        closeButton.Bind(wx.EVT_BUTTON, self.OnCancelIM)
        self.Bind(wx.EVT_CLOSE, self.OnCancelIM)

    def setbuttonIM(self, e):
        if self.list.GetValue():
            self.okButton.SetLabel(self.list.GetLabel())
            self.okButton.SetSize(200, 23)
            self.okButton.SetPosition(pt=(15, 87))
        if self.nbt_file.GetValue():
            self.okButton.SetSize(200, 23)
            self.okButton.SetPosition(pt=(15, 87))
            self.okButton.SetLabel(self.nbt_file.GetLabel())
        if self.ms_file.GetValue():
            self.okButton.SetSize(250,23)
            self.okButton.SetPosition(pt=(15,87))
            self.okButton.SetLabel(self.ms_file.GetLabel())

    def OnClose(self, e):
        self.Destroy()

    def OnCancelIM(self, e):
        self.ms_file.SetValue(False)
        self.nbt_file.SetValue(False)
        self.list.SetValue(False)
        self.Destroy()

    def OnCancelEX(self, e):
        self.selected_chunks.SetValue(False)
        self.all_chunks.SetValue(False)
        self.nbt_file_option.SetValue(False)
        self.Destroy()



export = dict(name="# The Entitie's Plugin nbt v2.11b", operation=EntitiePlugin) #PremiereHell
