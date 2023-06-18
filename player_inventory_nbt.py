#By PremiereHell  ,
# Thanks To Ben #Podshot https://github.com/Podshot ,
# For the NBT Editor, without his code this would not exist.
#
# used some code from the WxPython wiki:
# Thanks To Rob and Titus for Drag And Drop Sample Code
# https://wiki.wxpython.org/DragAndDropWithFolderMovingAndRearranging
# Sample and NBT_Editor Updated and Edited By #PremiereHell
from __future__ import annotations

import collections
import re

import amulet_nbt
import wx
import os
from amulet_map_editor.programs.edit.api.operations import DefaultOperationUI

import copy
from functools import partial, reduce
import operator
from collections.abc import MutableMapping, MutableSequence
import wx
from amulet_map_editor.api.wx.ui import simple
import amulet_nbt as nbt
from amulet_map_editor.api import image
nbt_resources = image.nbt
import abc

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

        Inventory.update_player_data(self, self.raw_nbt)
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

    def len(self, data):
        return len(data)

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
            # item_num = self.tree.GetChildrenCount(i_par, recursively=False)
            # f_child, f_c = self.tree.GetFirstChild(i_par)
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
        #print(type(data), len(data))
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
        root_tag_name = f"{len(data)} entries"
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
    # def len(self, data):
    #     return len(data)

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
        self.storage_key = nbt.TAG_Compound()

        wx.Panel.__init__(self, parent)
        DefaultOperationUI.__init__(self, parent, canvas, world, options_path)
        self.Freeze()

        self._sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self._sizer)

        self.font = wx.Font(11, wx.FONTFAMILY_ROMAN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        self.top_sizer = wx.BoxSizer(wx.VERTICAL)
        self.side_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.bottom_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self._sizer.Add(self.side_sizer, 1, wx.TOP | wx.LEFT, 0)
        self._sizer.Add(self.top_sizer)
        self._sizer.Add(self.bottom_sizer, 1, wx.BOTTOM | wx.LEFT,2)
        self.items = wx.Choice(self, choices=[])
        self.items.Bind(wx.EVT_CHOICE, self.on_item_focus)

        self.info_list = wx.StaticText(self, label=" ")#just a hack to force width
        self.top_sizer.Add(self.info_list, 0, wx.LEFT, 450)

        self.blank = wx.StaticText(self, label="")
        self.save_player_data_button = wx.Button(self, label="Save Player")
        self.save_player_snbt_button = wx.Button(self, label="Save File")
        self.remove_player_btn = wx.Button(self, label="Remove Player")
        self.load_file_grid = wx.GridSizer(2,1,0,-0)
        self.load_player_snbt = wx.Button(self, label="Load File")
        self.load_player_snbt_info = wx.StaticText(self, label="NOTE : \nWhen loading file make sure to select what \n was select from the dropdown when you saved.")
        self.load_file_grid.Add(self.load_player_snbt)
        self.load_file_grid.Add(self.load_player_snbt_info)

        self.save_player_data_button.Bind(wx.EVT_BUTTON, self.save_player_data)
        self.save_player_snbt_button.Bind(wx.EVT_BUTTON, self.export_snbt)
        self.load_player_snbt.Bind(wx.EVT_BUTTON, self.import_snbt)
        self.remove_player_btn.Bind(wx.EVT_BUTTON, self.remove_player)

        self.the_grid = wx.GridSizer(3,3,-60,-130)


        self.the_grid.Add(self.save_player_snbt_button)
        self.the_grid.Add(self.items, 0, wx.LEFT, -10)
        self.the_grid.Add(self.remove_player_btn, 0, wx.LEFT, 30)
        self.the_grid.Add(self.load_file_grid)
        self.the_grid.Add(self.blank)
        self.the_grid.Add(self.save_player_data_button, 0, wx.LEFT, 30)
        self.bottom_sizer.Add(self.the_grid)
        self.nbt_editor_instance = NBTEditor(self)

        self._sizer.Add(self.nbt_editor_instance,130, wx.EXPAND,51)
        if self.world.level_wrapper.platform == "bedrock":
            self._structlist = wx.Choice(self, choices=self._run_get_slist())
            self._structlist.Bind(wx.EVT_CHOICE, self.onFocus)
            self._structlist.SetSelection(0)
        else:
            self._structlist = wx.Choice(self, choices=[])#self._run_get_slist())
            self._structlist.Bind(wx.EVT_CHOICE, self.onFocus)
            self.java_setup()
            self._structlist.SetSelection(0)
        self.nbt_editor_instance.SetBackgroundColour((0, 0, 0))
        self.nbt_editor_instance.SetForegroundColour((0, 255, 0))
        self.nbt_editor_instance.SetFont(self.font)

        self.nbt_editor_instance.Fit()

        self.top_sizer.Add(self._structlist, 0, wx.LEFT, 11)
        if self.world.level_wrapper.platform == "bedrock":
            self.get_player_data()
        self.Layout()
        self.Thaw()

    def on_item_focus(self, _):
        selcted = self.items.GetStringSelection()
        if self.world.level_wrapper.platform == "bedrock":
            self.Freeze()
            self._sizer.Detach(self.nbt_editor_instance)
            self.nbt_editor_instance.Hide()
            NBTEditor.close(self.nbt_editor_instance, None, self.GetParent())
            if selcted == "Root":

                self.nbt_editor_instance = NBTEditor(self, self.nbt_dic_list)
            else:
                self.nbt_editor_instance = NBTEditor(self, nbt.CompoundTag({selcted: self.nbt_dic_list[selcted]}) )
            self._sizer.Add(self.nbt_editor_instance, 130, wx.EXPAND,21)
            self.Layout()
            self.Thaw()
        else:
            self.Freeze()
            self._sizer.Detach(self.nbt_editor_instance)
            self.nbt_editor_instance.Hide()
            NBTEditor.close(self.nbt_editor_instance, None, self.GetParent())
            self.nbt_editor_instance = NBTEditor(self, nbt.CompoundTag({selcted: self.nbt_dic_list[selcted]}))
            self._sizer.Add(self.nbt_editor_instance,130, wx.EXPAND,21)
            self.Layout()
            self.Thaw()

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
                self.data_nbt = nbt.load(dat, compressed=True, little_endian=False)
                if s_player == '~local_player':
                    for k,v in self.data_nbt['Data']['Player'].items():
                        self.nbt_dic_list[k] = v
                else:
                    for k,v in self.data_nbt.items():
                        self.nbt_dic_list[k] = v

                self._sizer.Detach(self.nbt_editor_instance)
                self.nbt_editor_instance.Hide()
                NBTEditor.close(self.nbt_editor_instance, None, self.GetParent())
                self.nbt_editor_instance = NBTEditor(self, nbt.CompoundTag({"Inventory": self.nbt_dic_list["Inventory"]}))
                root = self.nbt_editor_instance.tree.GetRootItem()
                first_c, c = self.nbt_editor_instance.tree.GetFirstChild(root)

                self.nbt_editor_instance.tree.Expand(first_c)
                self._sizer.Add(self.nbt_editor_instance, 130, wx.EXPAND, 21)
                self.Layout()

                # self.nbt_editor_instance.SetValue(self.nbt_dic_list.get('Inventory'))


    def _run_set_data(self, _):
        player = self.level_db.get(b'~local_player')
        data = self.nbt_editor_instance.GetValue()
        nnbt = nbt.from_snbt(data)

        data2 = nnbt.save_to(compressed=False,little_endian=True)
        self.level_db.put(b'~local_player', data2)

    def update_player_data(self, new_data):
        self_ = self.Parent.Parent
        seleted_ = self_.items.GetStringSelection()

        save_expanded = []
        # self.Freeze()
        f_root = self_.nbt_editor_instance.tree.GetRootItem()

        r_c = self_.nbt_editor_instance.tree.GetChildrenCount(f_root, 0)

        def get_full_path(child):
            tree = self_.nbt_editor_instance.tree
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
            tree = self_.nbt_editor_instance.tree
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
                i_c = self_.nbt_editor_instance.tree.GetChildrenCount(item, recursively=True)
                f_ic, cc_i = self_.nbt_editor_instance.tree.GetFirstChild(item)
                for ci in range(i_c):
                    if f_ic.IsOk():

                        if self_.nbt_editor_instance.tree.IsExpanded(f_ic):
                            save_expanded.append(copy.copy(root_path(f_ic)))
                        if self_.nbt_editor_instance.tree.GetChildrenCount(f_ic) > 0:
                            recurtree(f_ic)
                    f_ic, cc_i = self_.nbt_editor_instance.tree.GetNextChild(f_ic, cc_i)



        recurtree(f_root)
        current_scr_h = self_.nbt_editor_instance.tree.GetScrollPos(orientation=wx.VERTICAL)

        self_.Freeze()
        self_._sizer.Detach(self_.nbt_editor_instance)

        self_.nbt_editor_instance.Hide()
        self_.nbt_dic_list[seleted_] = new_data
        NBTEditor.close(self_.nbt_editor_instance, None, self_.GetParent())
        self_.nbt_editor_instance = NBTEditor(self_, self_.nbt_dic_list[seleted_])
        root = self_.nbt_editor_instance.tree.GetRootItem()
        first_c ,c = self_.nbt_editor_instance.tree.GetFirstChild(root)

        def re_expand(item):

            if item.IsOk():
                i_c = self_.nbt_editor_instance.tree.GetChildrenCount(item)
                f_ic, cc_i = self_.nbt_editor_instance.tree.GetFirstChild(item)

                for ci in range(i_c):
                    if f_ic.IsOk():

                        if root_path(f_ic) in save_expanded:
                            self_.nbt_editor_instance.tree.Expand(f_ic)
                        if self_.nbt_editor_instance.tree.GetChildrenCount(f_ic) > 0:
                            re_expand(f_ic)
                    f_ic, cc_i = self_.nbt_editor_instance.tree.GetNextChild(f_ic, cc_i)

        self_.nbt_editor_instance.tree.Expand(first_c)
        re_expand(root)
        self_._sizer.Add(self_.nbt_editor_instance, 130, wx.EXPAND, 21)
        self_.nbt_editor_instance.tree.SetScrollPos(wx.VERTICAL, current_scr_h)
        self_.Layout()
        self_.Thaw()
        self.Close()


            # self.nbt_editor_instance.SetValue(self.nbt_dic_list["Inventory"].to_snbt(1))



    def get_player_data(self):

        setdata = self._structlist.GetStringSelection()#self._structlist.GetString(self._structlist.GetSelection())
        enS = setdata.encode("utf-8")
        try:
            player = self.level_db.get(enS).replace(b'\x08\n\x00StorageKey\x08\x00',
                                                    b'\x07\n\x00StorageKey\x08\x00\x00\x00')
            self.nbt_dic_list = nbt.load(player, little_endian=True)
            self.items.SetItems(["Root","EnderChestInventory", "Inventory","PlayerLevel", "Armor", "Offhand", "Mainhand", "abilities", "ActiveEffects", "PlayerGameMode","Attributes", "Pos", "Invulnerable", "Tags"])
            self.items.SetSelection(2)

            self.Freeze()
            self._sizer.Detach(self.nbt_editor_instance)
            self.nbt_editor_instance.Hide()
            NBTEditor.close(self.nbt_editor_instance, None, self.GetParent())
            self.nbt_editor_instance = NBTEditor(self, nbt.CompoundTag({"Inventory": self.nbt_dic_list["Inventory"]}))
            root = self.nbt_editor_instance.tree.GetRootItem()
            first_c, c = self.nbt_editor_instance.tree.GetFirstChild(root)

            self.nbt_editor_instance.tree.Expand(first_c)
            self._sizer.Add(self.nbt_editor_instance,130, wx.EXPAND,21)
            self.Layout()
            self.Thaw()
            # self.nbt_editor_instance.SetValue(self.nbt_dic_list["Inventory"].to_snbt(1))
        except:
            self.Onmsgbox("Cant Find Local Player", "Open locally In Minecraft to regenerate the player.")


    def Onmsgbox(self, caption, message):  # message
        wx.MessageBox(message, caption, wx.OK | wx.ICON_INFORMATION)

    def save_player_data(self, _):
        new_data = NBTEditor.build_to(self.nbt_editor_instance, _)
        if self.world.level_wrapper.platform == "bedrock":
            theKey = self._structlist.GetStringSelection().encode("utf-8")
            if self.items.GetStringSelection() == "Root":
                self.nbt_dic_list = new_data
            else:
                selcted = self.items.GetStringSelection()
                self.nbt_dic_list[selcted] = new_data[self.items.GetStringSelection()]
            try:
                rawdata = self.nbt_dic_list.save_to(compressed=False, little_endian=True)\
                    .replace(b'\x07\n\x00StorageKey\x08\x00\x00\x00',b'\x08\n\x00StorageKey\x08\x00')
                self.level_db.put(theKey, rawdata)
                self.Onmsgbox("Saved", f"All went well")
            except Exception as e:
                self.Onmsgbox("Error", f"Something went wrong: {e}")


        else:
            data = new_data[self.items.GetStringSelection()].to_snbt()
            selection = self.items.GetStringSelection()
            s_player = self._structlist.GetStringSelection()
            if s_player == '~local_player':
                self.data_nbt['Data']['Player'][selection] = nbt.from_snbt(data)
            else:
                 self.data_nbt[selection] = nbt.from_snbt(data)


            nbt_file = self.data_nbt.save_to(compressed=True, little_endian=False)

            if s_player == '~local_player':
                path_to = self.world.level_wrapper.path + "/" + "level.dat"
            else:
                path_to = self.world.level_wrapper.path + "/playerdata/" + s_player + ".dat"
            with open(path_to, "wb") as dat:
                dat.write(nbt_file)
            self.Onmsgbox("Saved", f"All went well")

    def export_snbt(self, _):
        data = self.nbt_editor_instance.build_to(_,"raw")
        with wx.FileDialog(self, "Save NBT file", wildcard="NBT files (*.NBT)|*.NBT",
                           style=wx.FD_SAVE) as fileDialog:
            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return
            else:
                pathname = fileDialog.GetPath()
        data.save_to(pathname,little_endian= True, compressed=False)

    def import_snbt(self, _):
        with wx.FileDialog(self, "Open NBT file", wildcard="SNBT files (*.NBT)|*.NBT",
                           style=wx.FD_OPEN) as fileDialog:
            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return
            else:
                pathname = fileDialog.GetPath()
        data = nbt.load(pathname,little_endian= True, compressed=False).compound
        # print(type(data.compound),len(data.compound))
        # self.nbt_editor_instance.sizer.Hide(self.nbt_editor_instance.tree)
        # self.nbt_editor_instance.tree.DeleteAllItems()
        self.Freeze()
        self._sizer.Detach(self.nbt_editor_instance)
        self.nbt_editor_instance.Hide()
        NBTEditor.close(self.nbt_editor_instance, None, self.GetParent())
        self.nbt_editor_instance = NBTEditor(self, data)
        self._sizer.Add(self.nbt_editor_instance, 130, wx.EXPAND, 21)
        self.Layout()
        self.Thaw()

        # self.nbt_editor_instance.build_tree(self, data)


    def remove_player(self, _):
        if self.world.level_wrapper.platform == "bedrock":
            theKey = self._structlist.GetStringSelection().encode("utf-8")
            wxx = wx.MessageBox("You are going to deleted \n " + str(theKey),
                                "This can't be undone Are you Sure?", wx.OK | wx.CANCEL | wx.ICON_INFORMATION)
            if wxx == int(16):
                return
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
            l.append(k)
        return l

    def setup_data(self):
        self.nbt_dic_list = collections.defaultdict()
        self.data_nbt = nbt.CompoundTag()
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
                self.data_nbt = nbt.load(dat, compressed=True, little_endian=False)
                if s_player == '~local_player':
                    for k,v in self.data_nbt['Data']['Player'].items():
                        self.nbt_dic_list[k] = v
                else:
                    for k,v in self.data_nbt.items():
                        self.nbt_dic_list[k] = v
                self.items.SetItems(["EnderItems", "Inventory"])
                self.items.SetSelection(1)
                self.Freeze()
                self._sizer.Detach(self.nbt_editor_instance)
                self.nbt_editor_instance.Hide()
                NBTEditor.close(self.nbt_editor_instance, None, self.GetParent())
                self.nbt_editor_instance = NBTEditor(self,
                                                     nbt.CompoundTag({"Inventory": self.nbt_dic_list["Inventory"]}))
                root = self.nbt_editor_instance.tree.GetRootItem()
                first_c, c = self.nbt_editor_instance.tree.GetFirstChild(root)

                self.nbt_editor_instance.tree.Expand(first_c)
                self._sizer.Add(self.nbt_editor_instance, 130, wx.EXPAND, 21)
                self.Layout()
                self.Thaw()
                 ##################################################################################################

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

export = dict(name="Players Inventory NBT 4.00", operation=Inventory)
