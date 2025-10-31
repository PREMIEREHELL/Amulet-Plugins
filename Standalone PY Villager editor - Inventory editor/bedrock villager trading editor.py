import amulet
from amulet_nbt import *
import struct
import wx
import collections
import os
import sys
import json
from pathlib import Path
def get_all_bedrock_worlds_paths():
    world_paths = []

    local_appdata = os.getenv('LOCALAPPDATA')
    if local_appdata:
        uwp_base = Path(local_appdata) / "Packages" / "Microsoft.MinecraftUWP_8wekyb3d8bbwe" / \
                   "LocalState" / "games" / "com.mojang" / "minecraftWorlds"
        if uwp_base.exists():
            world_paths.append(uwp_base)

    roaming_appdata = os.getenv('APPDATA')
    if roaming_appdata:
        users_base = Path(roaming_appdata) / "Minecraft Bedrock" / "Users"
        if users_base.exists():
            for user_dir in users_base.iterdir():
                if user_dir.is_dir() and user_dir.name.lower() != "shared":
                    user_worlds = user_dir / "games" / "com.mojang" / "minecraftWorlds"
                    if user_worlds.exists():
                        world_paths.append(user_worlds)

    world_paths = list(dict.fromkeys(world_paths))
    return world_paths
def select_world_path(paths):
    """Show a small wxPython window to select one world path."""
    app = wx.App(False)

    # Extract user or folder ID to show in the list
    labels = [path.parent.parent.parent.name for path in paths]

    dialog = wx.SingleChoiceDialog(
        None,
        message="Select a Minecraft user/worlds folder:",
        caption="Select World Path",
        choices=labels,
        style=wx.CHOICEDLG_STYLE
    )

    selected_path = None
    if dialog.ShowModal() == wx.ID_OK:
        idx = dialog.GetSelection()
        selected_path = paths[idx]

    dialog.Destroy()
    app.MainLoop()
    return selected_path
def get_bedrock_world_path():
    paths = get_all_bedrock_worlds_paths()

    if not paths:
        raise FileNotFoundError("No Minecraft Bedrock world directories found.")
    elif len(paths) > 1:
        # Let user select one if there are more than 3
        selected = select_world_path(paths)
        if selected:
            return selected
        else:
            raise RuntimeError("No selection made.")
    else:
        # If 3 or fewer, just pick the first automatically
        return paths[0]

selected_world_dir = get_bedrock_world_path()
WORLDS_DIR =  selected_world_dir
categories = { # This will sort both menu options

    "Construction": range(0, 466),
    "Equipment": range(880, 937), #Sheild 980
    "Items": range(1196, 1718),
    "Nature": range(466, 880),
    "Tools": range(910, 935),
    "Weapons": list(range(904, 915)),
    "Special Weapons": range(934, 937),
    "Arrows": range(937, 979),
    "Unlisted Bedrock": range(1718, 1766),
    "Fast Ready Special": range(1041, 1045),
    #"Ready": range(0, 0), #some how this happen bottom is visable no submenu I like it
}
class MinecraftWorldSelector(wx.Frame):
    def __init__(self):
        super().__init__(None, title="Minecraft World Selector", size=(1100, 900))
        self.font = wx.Font(18, wx.FONTFAMILY_ROMAN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        self.SetFont(self.font)
        self.SetForegroundColour((0, 255, 0))
        self.SetBackgroundColour(wx.Colour(0, 0, 0, 0))
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        panel = wx.ScrolledWindow(self)

        panel.SetScrollRate(10, 10)
        grid_sizer = wx.GridSizer(0, 4, 5, -80)  # 0 rows, 4 columns, 10px gap

        if os.path.exists(WORLDS_DIR):
            worlds = []
            for world_folder in os.listdir(WORLDS_DIR):
                world_path = os.path.join(WORLDS_DIR, world_folder)
                if os.path.isdir(world_path):
                    mod_time = os.path.getmtime(world_path)  # Get modification time
                    worlds.append((mod_time, world_path))

            # Sort worlds by most recent modification time (descending)
            worlds.sort(reverse=True, key=lambda x: x[0])

            for _, world_path in worlds:
                world_name = "Unknown World"
                icon_path = os.path.join(world_path, "world_icon.jpeg")
                name_path = os.path.join(world_path, "levelname.txt")

                if os.path.exists(name_path):
                    with open(name_path, "r", encoding="utf-8") as f:
                        world_name = f.read().strip()

                world_panel = wx.Panel(panel)
                world_sizer = wx.BoxSizer(wx.VERTICAL)

                if os.path.exists(icon_path):
                    image = wx.Image(icon_path, wx.BITMAP_TYPE_JPEG).Scale(128, 128)
                    bitmap = wx.StaticBitmap(world_panel, bitmap=wx.Bitmap(image))

                    # Bind hover events correctly
                    bitmap.Bind(wx.EVT_ENTER_WINDOW, self.on_hover)
                    bitmap.Bind(wx.EVT_LEAVE_WINDOW, self.on_leave)
                    bitmap.Bind(wx.EVT_LEFT_DOWN, lambda evt, path=world_path: self.on_world_selected(evt, path))

                    world_sizer.Add(bitmap, 0, wx.ALIGN_CENTER | wx.ALL, 5)
                else:
                    button = wx.Button(world_panel, label="Select")
                    button.Bind(wx.EVT_BUTTON, lambda evt, path=world_path: self.on_world_selected(evt, path))
                    world_sizer.Add(button, 0, wx.ALIGN_CENTER | wx.ALL, 5)

                label = wx.StaticText(world_panel, label=world_name)
                label.Bind(wx.EVT_ENTER_WINDOW, self.on_hover)
                label.Bind(wx.EVT_LEAVE_WINDOW, self.on_leave)

                label.SetFont(self.font)
                label.SetForegroundColour((0, 255, 0))
                label.SetBackgroundColour(wx.Colour(0, 0, 0, 0))
                label.SetMinSize((150, 150))
                world_sizer.Add(label, 0, wx.ALIGN_CENTER | wx.ALL, 5)
                # label.SetTransparent(0)

                world_panel.SetSizer(world_sizer)
                grid_sizer.Add(world_panel, 0, wx.EXPAND | wx.ALL, 5)

        panel.SetSizer(grid_sizer)
        self.Centre()
        self.Show()

    def on_hover(self, event):
        obj = event.GetEventObject()
        parent = obj.GetParent()

        if isinstance(obj, wx.StaticText):
            obj.Hide()
            parent.Layout()  # Layout the parent, not the text itself
            parent.Refresh()

        elif isinstance(obj, wx.StaticBitmap):
            bmp = obj.GetBitmap()
            img = bmp.ConvertToImage().Scale(354, 354)
            obj.SetBitmap(wx.Bitmap(img))
            parent.Layout()
            parent.Refresh()

    def on_leave(self, event):
        obj = event.GetEventObject()
        parent = obj.GetParent()

        if isinstance(obj, wx.StaticText):
            obj.Show()
            parent.Layout()
            parent.Refresh()

        elif isinstance(obj, wx.StaticBitmap):
            bmp = obj.GetBitmap()
            img = bmp.ConvertToImage().Scale(128, 128)
            obj.SetBitmap(wx.Bitmap(img))
            parent.Layout()
            parent.Refresh()

    def on_world_selected(self, event, path):
        ListWindow(path)
class GetVillagerData():
    def __init__(self, path):
        self.world = amulet.level.load_level( path)
        self.list_of = []
        self.list_of_villager_data = collections.defaultdict(list)
        self.current_actor = None
    def load_villager(self):
        dig_chunks = {}
        def get_dim(digp):
            dim = None
            if len(digp) == 12:
                dim = 'overworld'
            elif len(digp) == 16:
                if digp[12] == 0x01:
                    dim =  'nether'
                elif digp[12] == 0x02:
                    dim =  'end'
            return dim

        def find_key_by_value(dig_chunks, value):
            for key, chunk in dig_chunks.items():
                for c in chunk:
                    if c == value:
                        return key
            return None

        for k, v in self.world.level_wrapper.level_db.iterate(start=b'digp', end=b'digp' + b'\xFF' * 40):
            dig_chunks[k] = [v[i:i+8] for i in range(0, len(v), 8)]

        for k, v in self.world.level_wrapper.level_db.iterate(start=b'actorprefix', end=b'actorprefix\xFF' * 40):
            data = v
            act_nbt = load(data, compressed=False, little_endian=True,
                           string_decoder=utf8_escape_decoder).compound
            key = find_key_by_value(dig_chunks, k[11:])

            if act_nbt.get('identifier').py_str == 'minecraft:villager_v2':
                preferred_profession = str(act_nbt.get('PreferredProfession'))
                x, y, z = act_nbt['Pos'].py_data
                # print(act_nbt.to_snbt(1))

                if preferred_profession != 'None':
                    self.list_of_villager_data[k].append({
                    'pos': f'{int(x.py_float), int(y.py_float), int(z.py_float)}',
                    'pp': preferred_profession,
                    'dim' : get_dim(key),
                    'Name': act_nbt.get('CustomName', ''),
                    'data': act_nbt})


        return self.list_of_villager_data
class ListWindow(wx.Frame):
    def __init__(self, path):
        super().__init__(None, title="wxPython List Example", size=(660, 800))
        panel = wx.Panel(self)
        vil = GetVillagerData(path)
        self.world = vil.world
        self.loaded_villager = vil.load_villager()
        self.vil_list = []
        self.display_map = {}
        for key, villagers in self.loaded_villager.items():
            for villager in villagers:
                display_text = f"{villager['dim']} - {villager['pos']} - {villager['pp']} - {villager['Name']}"
                self.vil_list.append(display_text)
                self.display_map[display_text] = key

        self.font = wx.Font(20, wx.FONTFAMILY_ROMAN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        self.SetFont(self.font)
        self.SetForegroundColour((0, 255, 0))
        self.SetBackgroundColour((0, 0, 0))
        vbox = wx.BoxSizer(wx.VERTICAL)

        self.list_ctrl = wx.ListBox(panel, choices=self.vil_list)
        self.list_ctrl.SetFont(self.font)
        self.list_ctrl.SetForegroundColour((0, 255, 0))
        self.list_ctrl.SetBackgroundColour((0, 0, 0))
        vbox.Add(self.list_ctrl, 1, wx.EXPAND | wx.ALL, 10)
        self.list_ctrl.Bind(wx.EVT_LISTBOX_DCLICK, self.on_item_click)

        panel.SetSizer(vbox)
        self.Show()

    def on_item_click(self, event):
        selection = self.list_ctrl.GetSelection()
        if selection != wx.NOT_FOUND:
            item_text = self.list_ctrl.GetString(selection)
            recipes = self.loaded_villager[self.display_map[item_text]][0]['data']['Offers']['Recipes']
            DetailWindow(self, item_text, recipes, self.display_map[item_text],
            self.loaded_villager[self.display_map[item_text]], self.world)

class IconListCtrl(wx.Frame):
    def __init__(self, parent, title, data, icon_cache, on_select):
        """
        :param parent: wx parent
        :param title: frame title
        :param data: dict bedrock_id → {"display_name": ...}
        :param icon_cache: dict bedrock_id → wx.Image
        :param on_select: callback(bedrock_id, icon_bitmap, display_name)
        """
        super().__init__(parent, title=title, size=(900, 900))
        self.data = data
        self.icon_cache = icon_cache
        self.icon_size = 50
        self.index_to_bedrock = {}
        self.on_select = on_select

        panel = wx.Panel(self)

        # Filter bar
        filter_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.filter_ctrl = wx.TextCtrl(panel)
        filter_sizer.Add(wx.StaticText(panel, label="Filter: "), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        filter_sizer.Add(self.filter_ctrl, 1, wx.EXPAND)
        self.filter_ctrl.Bind(wx.EVT_TEXT, self._on_filter_change)

        # ListCtrl
        self.list_ctrl = wx.ListCtrl(panel, style=wx.LC_ICON)
        self.image_list = wx.ImageList(self.icon_size, self.icon_size)
        self.list_ctrl.AssignImageList(self.image_list, wx.IMAGE_LIST_NORMAL)
        self.list_ctrl.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self._on_item_click)

        # Layout
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(filter_sizer, 0, wx.EXPAND | wx.ALL, 5)
        sizer.Add(self.list_ctrl, 1, wx.EXPAND | wx.ALL, 5)
        panel.SetSizer(sizer)

        # Initial populate
        self._populate_list(self.data.keys())

        self.Show()

    def _on_filter_change(self, event):
        search = self.filter_ctrl.GetValue().lower()
        if not search:
            filtered_keys = self.data.keys()
        else:
            filtered_keys = []
            for k, v in self.data.items():
                # If v is a dict, get "display_name"; otherwise, treat v as the display name
                name = v.get("display_name", k) if isinstance(v, dict) else str(v)
                if search in name.lower():
                    filtered_keys.append(k)

        self._populate_list(filtered_keys)

    def _on_item_click(self, event):
        idx = event.GetIndex()
        bedrock_id = self.index_to_bedrock.get(idx)
        if not bedrock_id:
            return

        info = self.data.get(bedrock_id, {})
        display_name = info.get("display_name", bedrock_id)
        icon = self.icon_cache.get(bedrock_id)
        bmp = icon.Rescale(32, 32).ConvertToBitmap() if icon else None

        if self.on_select:
            self.on_select(bedrock_id, bmp, display_name)
        self.Close()

    def _populate_list(self, item_keys):
        self.list_ctrl.DeleteAllItems()
        self.image_list.RemoveAll()
        self.index_to_bedrock.clear()

        for bedrock_id in item_keys:
            info = self.data[bedrock_id]
            display_name = info.get("display_name", bedrock_id) if isinstance(info, dict) else str(info)
            icon = self.icon_cache.get(bedrock_id)
            if not icon:
                continue
            icon = icon.Rescale(self.icon_size, self.icon_size)
            icon_index = self.image_list.Add(icon.ConvertToBitmap())
            index = self.list_ctrl.InsertItem(self.list_ctrl.GetItemCount(), display_name, icon_index)
            self.index_to_bedrock[index] = bedrock_id

enchantments = {
    8: "Aqua Affinity",
    11: "Bane of Arthropods",
    3: "Blast Protection",
    32: "Channeling",
    27: "Curse of Binding",
    28: "Curse of Vanishing",
    7: "Depth Strider",
    15: "Efficiency",
    2: "Feather Falling",
    13: "Fire Aspect",
    1: "Fire Protection",
    21: "Flame",
    18: "Fortune",
    25: "Frost Walker",
    29: "Impaling",
    22: "Infinity",
    12: "Knockback",
    14: "Looting",
    31: "Loyalty",
    23: "Luck of the Sea",
    24: "Lure",
    26: "Mending",
    33: "Multishot",
    34: "Piercing",
    19: "Power",
    4: "Projectile Protection",
    0: "Protection",
    20: "Punch",
    35: "Quick Charge",
    6: "Respiration",
    30: "Riptide",
    9: "Sharpness",
    16: "Silk Touch",
    10: "Smite",
    36: "Soul Speed",
    5: "Thorns",
    17: "Unbreaking",
    37: "Swift Sneak",
    40: "Breach",
    39: "Density",
    38: "Wind Burst"
}
class DetailWindow(wx.Frame):
    def __init__(self, parent, title, recipes, key, villager_data, world):
        super().__init__(parent, title=f"Details - {title}", size=(1400, 900))
        self.world = world
        self.current_key = key
        self.villager_data = villager_data
        self.recipes = recipes
        self.input_fields = {}
        self.linked_fields = {}  # Tracks linked fields
        self.icon_cache = {}
        self.items_id = []
        self.input_buttons = {}
        self.recipe_sizers = {}
        self.sell_sizers = {}
        self.sell_sizers_parent = {}
        script_dir = os.path.dirname(os.path.abspath(__file__))  # this if for py to exe

        # Load tem_atlas.json using importlib.resources
        json_path = os.path.join(script_dir, 'item_atlas.json')

        # Check if it's running as a bundled executable
        if getattr(sys, 'frozen', False):
            # Running as a bundled exe (PyInstaller)
            json_path = os.path.join(sys._MEIPASS, 'data/item_atlas.json')  # to here

        with open(json_path, 'r') as file:
            self.data = json.load(file)
        self.icon_cache = self.load_icon_cache(self.data)
        self.data.pop('atlas')
        # --- Main layout ---
        main_vbox = wx.BoxSizer(wx.VERTICAL)

        # --- Top panel with Save button ---
        top_panel = wx.Panel(self)
        top_sizer = wx.BoxSizer(wx.HORIZONTAL)

        save_button = wx.Button(top_panel, label="Save Changes")
        save_button.Bind(wx.EVT_BUTTON, self.on_save)

        label = wx.StaticText(top_panel, label="CustomName:")
        self.custom_name = wx.TextCtrl(top_panel, size=(150, -1))
        self.custom_name.SetValue(self.villager_data[0]['data'].get('CustomName', StringTag('')).py_str)

        self.make_invulnerable = wx.CheckBox(top_panel, label="Invulnerable")
        if self.villager_data[0]['data'].get('Invulnerable', None) == ByteTag(1):
            self.make_invulnerable.SetValue(True)


        top_sizer.Add(self.make_invulnerable, 0, wx.LEFT | wx.ALL, 10)
        top_sizer.Add(label, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 5)
        top_sizer.Add(self.custom_name, 0, wx.LEFT | wx.ALL, 10)
        top_sizer.AddStretchSpacer()
        top_sizer.Add(save_button, 0, wx.RIGHT | wx.ALL, 10)


        top_panel.SetSizer(top_sizer)
        main_vbox.Add(top_panel, 0, wx.EXPAND)

        # --- Scrollable panel for recipes ---
        self.scroll_panel = wx.ScrolledWindow(self, style=wx.VSCROLL)
        self.scroll_panel.SetScrollRate(5, 5)

        recipes_grid = wx.FlexGridSizer(cols=3, hgap=1, vgap=1)
        recipes_grid.AddGrowableCol(0, 1)
        recipes_grid.AddGrowableCol(1, 1)
        recipes_grid.AddGrowableCol(2, 1)
        print(self.villager_data[0]['data'].to_snbt(2))
        for i, recipe in enumerate(self.recipes):
            box = wx.StaticBox(self.scroll_panel, label=f"Recipe {i + 1}")
            recipe_sizer = wx.StaticBoxSizer(box, wx.VERTICAL)

            grid = wx.FlexGridSizer(cols=2, hgap=10, vgap=5)
            grid.AddGrowableCol(1, 1)

            # Create a dedicated row_sizer for the sell item
            sell_row_sizer = wx.BoxSizer(wx.HORIZONTAL)
            self.sell_sizers[i] = sell_row_sizer  # now guaranteed to exist

            for key, value in recipe.items():
                self._add_key_value(self.scroll_panel, grid, key, value, path=[i])

            recipe_sizer.Add(grid, 1, wx.EXPAND | wx.ALL, 5)
            recipe_sizer.Add(sell_row_sizer, 0, wx.EXPAND | wx.ALL, 2)  # add sell row to recipe UI
            recipes_grid.Add(recipe_sizer, 1, wx.EXPAND)

        self.scroll_panel.SetSizer(recipes_grid)
        main_vbox.Add(self.scroll_panel, 1, wx.EXPAND | wx.ALL, 5)
        self.SetSizer(main_vbox)
        self.Centre()
        self.Show()

        # --- Setup linked fields (sync buyA['Count'] <-> buyCountA) ---
        self._setup_linked_fields()
    def load_icon_cache(self, atlas):
        """Loads icons from the item atlas."""
        icon_cache = {}

        def load_base64_imagefile(data):
            import base64
            import io
            atlas = base64.b64decode(data['atlas'])
            buffer = io.BytesIO(atlas)
            atlas_image = wx.Image()
            atlas_image.LoadFile(buffer, wx.BITMAP_TYPE_PNG)
            return atlas_image

        if isinstance(atlas, dict):
            atlas_image = load_base64_imagefile(atlas)
        else:
            atlas_image = wx.Image(atlas, wx.BITMAP_TYPE_PNG)

        for item_id, data in self.data.items():  #Icons Size
            if "icon_position" in data:
                x, y = data["icon_position"]["x"], data["icon_position"]["y"]
                icon_image = atlas_image.GetSubImage(wx.Rect(x, y, 32, 32))
                icon_cache[item_id] = icon_image
                self.items_id.append(item_id)
        return icon_cache
    # -------------------- KEY/VALUE GUI --------------------
    def _add_key_value(self, parent, sizer, key, value, path):
        """Adds a label + value, recursive for CompoundTag/ListTag, with optional icon button or enchantment drop-down."""
        if key == "WasPickedUp":
            return
        label = wx.StaticText(parent, label=f"{'' * (len(path) - 1)}{key}:")
        sizer.Add(label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)

        if isinstance(value, CompoundTag):
            sub_grid = wx.FlexGridSizer(cols=2, hgap=2, vgap=1)
            sub_grid.AddGrowableCol(1, 1)
            for n_key, n_value in value.items():
                self._add_key_value(parent, sub_grid, n_key, n_value, path + [key])
            sizer.Add(sub_grid, 1, wx.EXPAND)

        elif isinstance(value, ListTag):
            sub_grid = wx.FlexGridSizer(cols=2, hgap=2, vgap=1)
            sub_grid.AddGrowableCol(1, 1)
            for idx, n_value in enumerate(value):
                # Pass integer index directly for ListTag
                self._add_key_value(parent, sub_grid, idx, n_value, path + [key])
            sizer.Add(sub_grid, 1, wx.EXPAND)

        else:
            row_sizer = wx.BoxSizer(wx.HORIZONTAL)
            path_tuple = tuple(path + [key])

            # --- Special handling for enchantments ---
            if key == "id" and "ench" in path:
                try:
                    ench_id = int(str(value))
                except (ValueError, TypeError):
                    ench_id = None
                ench_choices = [f"{k}: {v}" for k, v in enchantments.items()]
                default_val = f"{ench_id}: {enchantments.get(ench_id, 'Unknown')}" if ench_id in enchantments else ""
                ctrl = wx.ComboBox(
                    parent,
                    value=default_val,
                    choices=ench_choices,
                    style=wx.CB_DROPDOWN,
                    size=(200, -1)
                )
            else:
                # Regular TextCtrl for all other fields
                if isinstance(value, (ByteTag, ShortTag, IntTag, FloatTag, StringTag)):
                    display_value = str(value)
                else:
                    display_value = str(value)
                char_width = 8
                min_width = 70
                max_width = 250
                width = min(max_width, max(min_width, len(display_value) * char_width))
                ctrl = wx.TextCtrl(parent, value=display_value, size=(width, -1))

            row_sizer.Add(ctrl, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 1)
            self.input_fields[path_tuple] = ctrl

            # --- Icon button for items ---
            btn = None
            val_str = str(value)
            if "minecraft:" in val_str:
                item_id = val_str.replace("minecraft:", "")
                icon_image = self.icon_cache.get(item_id)
                if icon_image:
                    bmp = wx.Bitmap(icon_image)
                    btn = wx.BitmapButton(parent, bitmap=bmp, size=(32, 32))
                else:
                    btn = wx.Button(parent, label="?", size=(32, 32))

                btn.Bind(wx.EVT_BUTTON, lambda e, slot_path=path_tuple: self._open_icon_window(slot_path))
                row_sizer.Add(btn, 0, wx.ALIGN_CENTER_VERTICAL)

            if btn:
                self.input_buttons[path_tuple] = btn
            if "sell" in path and key.lower() == "name":
                # Row sizer for this sell item
                self.sell_sizers[path[0]] = row_sizer
                self.sell_sizers_parent[path[0]] = sizer  # <-- save parent sizer

                # Add Enchant button next to item name
                add_ench_btn = wx.Button(parent, label="Add Enchant")
                add_ench_btn.Bind(wx.EVT_BUTTON, lambda e, ri=path[0]: self._add_enchant_for_item(ri))
                row_sizer.Add(add_ench_btn, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 5)

            sizer.Add(row_sizer, 1, wx.EXPAND | wx.ALL, 2)

    # -------------------- OPEN ICON WINDOW --------------------
    def _add_enchant_for_item(self, recipe_index):
        scroll_panel = self.scroll_panel
        item_row_sizer = self.sell_sizers.get(recipe_index)
        parent_sizer = self.sell_sizers_parent.get(recipe_index)

        if not item_row_sizer or not parent_sizer:
            print("Missing row or parent sizer for recipe", recipe_index)
            return

        recipe = self.recipes[recipe_index].get("sell", {})
        tag = recipe.setdefault("tag", CompoundTag({}))
        ench_list = tag.setdefault("ench", ListTag([]))

        new_ench = CompoundTag({"id": ShortTag(34), "lvl": ShortTag(1)})
        ench_list.append(new_ench)
        new_index = len(ench_list) - 1

        # Check if enchant sizer exists
        ench_sizer_attr = f"sell_ench_sizer_{recipe_index}"
        ench_sizer_obj = getattr(self, ench_sizer_attr, None)
        if ench_sizer_obj is None:
            # Create sizer below the item row
            ench_sizer_obj = wx.FlexGridSizer(cols=2, hgap=2, vgap=1)
            ench_sizer_obj.AddGrowableCol(1, 1)
            parent_sizer.Add(wx.StaticText(scroll_panel, label="ench:"), 0, wx.ALL, 2)
            parent_sizer.Add(ench_sizer_obj, 0, wx.EXPAND | wx.ALL, 2)
            setattr(self, ench_sizer_attr, ench_sizer_obj)

        # Add the new enchant row like loaded ones
        self._add_key_value(scroll_panel, ench_sizer_obj, new_index, new_ench,
                            [recipe_index, "sell", "tag", "ench"])

        # Refresh layouts
        ench_sizer_obj.Layout()
        parent_sizer.Layout()
        scroll_panel.FitInside()
        scroll_panel.Layout()
        scroll_panel.Refresh()

    def _open_icon_window(self, path):
        """Open IconListCtrl and update callback for the selected slot."""
        IconListCtrl(
            parent=self,
            title="Select Item",
            data=self.data,
            icon_cache=self.icon_cache,
            on_select=lambda bedrock_id, bmp, display_name: self.on_item_selected(path, bedrock_id, bmp, display_name)
        )

    def on_item_selected(self, path, bedrock_id, bmp, display_name):
        """Update the TextCtrl and button at a given path when an item is chosen."""
        # Update TextCtrl
        ctrl = self.input_fields.get(path)
        if ctrl:
            ctrl.SetValue(f"minecraft:{bedrock_id}")

        # Update BitmapButton
        btn = self.input_buttons.get(path)
        if btn and bmp:
            btn.SetBitmap(bmp)
            btn.SetBitmapCurrent(bmp)
            btn.Refresh()
            btn.Update()
    # -------------------- LINKED FIELDS --------------------
    def _setup_linked_fields(self):
        """Setup syncing for buyA['Count'] ↔ buyCountA."""
        for i, recipe in enumerate(self.recipes):
            buyA_path = (i, "buyA", "Count")
            buyCountA_path = (i, "buyCountA")
            buyB_path = (i, "buyB", "Count")
            buyCountB_path = (i, "buyCountB")
            if buyA_path in self.input_fields and buyCountA_path in self.input_fields:
                # Link both ways
                self.linked_fields[buyA_path] = [buyCountA_path]
                self.linked_fields[buyCountA_path] = [buyA_path]
            if buyB_path in self.input_fields and buyCountB_path in self.input_fields:
                # Link both ways
                self.linked_fields[buyB_path] = [buyCountB_path]
                self.linked_fields[buyCountB_path] = [buyB_path]

        # Bind events
        for path, linked_paths in self.linked_fields.items():
            ctrl = self.input_fields.get(path)
            if ctrl:
                ctrl.Bind(wx.EVT_TEXT, lambda e, p=path: self._on_linked_text(e, p))

    def _on_linked_text(self, event, path):
        """Sync linked text entries."""
        new_value = self.input_fields[path].GetValue()
        for linked_path in self.linked_fields.get(path, []):
            linked_ctrl = self.input_fields.get(linked_path)
            if linked_ctrl:
                linked_ctrl.ChangeValue(new_value)

    # -------------------- SAVE --------------------
    def on_save(self, event):
        TAG_CLASSES = {
            "ByteTag": (ByteTag, int),
            "ShortTag": (ShortTag, int),
            "IntTag": (IntTag, int),
            "FloatTag": (FloatTag, float),
            "StringTag": (StringTag, str),
            "CompoundTag": (CompoundTag, dict),
            "ListTag": (ListTag, list),
        }
        if self.custom_name.GetValue() != '':
            self.villager_data[0]['data']['CustomName'] = StringTag(self.custom_name.GetValue())
        if self.make_invulnerable.IsChecked():
            self.villager_data[0]['data']['Invulnerable'] = ByteTag(1)
        else:
            self.villager_data[0]['data']['Invulnerable'] = ByteTag(0)

        for path, text_ctrl in self.input_fields.items():
            value = text_ctrl.GetValue()
            if len(path) >= 2 and path[-1] == "id" and "ench" in path:
                clean_val = value.split()[0].strip("(): ")
                try:
                    value = int(clean_val)
                except ValueError:
                    value = clean_val
            i, *keys = path
            current_level = self.recipes[i]

            for key in keys[:-1]:
                if isinstance(current_level, ListTag):
                    key = int(key)  # convert key to integer
                    current_level = current_level[key]
                else:
                    print(keys)
                    if key not in current_level or not isinstance(current_level[key], (CompoundTag, ListTag)):
                        # if the next level should be CompoundTag for dict-like entries
                        current_level[key] = CompoundTag({})
                    current_level = current_level[key]

            last_key = keys[-1]

            if isinstance(current_level, ListTag):
                idx = int(last_key)
                old_val = current_level[idx]
            else:
                old_val = current_level.get(last_key, StringTag(""))

            tag_class, caster = TAG_CLASSES.get(type(old_val).__name__, (StringTag, str))
            try:
                cast_value = caster(value)
            except Exception:
                cast_value = value

            new_tag = tag_class(cast_value)

            if isinstance(current_level, ListTag):
                current_level[idx] = new_tag
            else:
                current_level[last_key] = new_tag

        raw_data = self.villager_data[0]['data'].save_to(
            compressed=False, little_endian=True, string_encoder=utf8_escape_encoder
        )
        self.world.level_wrapper.level_db.put(self.current_key, raw_data)
        wx.MessageBox("Data Updated!", "Success", wx.OK | wx.ICON_INFORMATION)


if __name__ == "__main__":
    app = wx.App(False)
    MinecraftWorldSelector()
    app.MainLoop()
#by PremiereHell


