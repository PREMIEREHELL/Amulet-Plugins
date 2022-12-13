import collections
import wx
from typing import TYPE_CHECKING, Tuple
from amulet_map_editor.programs.edit.api.behaviour import BlockSelectionBehaviour
from amulet.api.selection import SelectionGroup
from amulet.api.selection import SelectionBox
from amulet_map_editor.programs.edit.api.operations import DefaultOperationUI
from amulet.api.errors import ChunkDoesNotExist
from amulet_map_editor.programs.edit.api.key_config import ACT_BOX_CLICK
from amulet_map_editor.programs.edit.api.key_config import ACT_CHANGE_MOUSE_MODE
from amulet_map_editor.programs.edit.api.events import (
    InputPressEvent,
    EVT_INPUT_PRESS,
    SelectionChangeEvent,
    EVT_SELECTION_CHANGE,
)
from amulet_map_editor.programs.edit.api.behaviour.pointer_behaviour import (
    PointerBehaviour,
    EVT_POINT_CHANGE,
    PointChangeEvent,
)
if TYPE_CHECKING:
    from amulet.api.level import BaseLevel
    from amulet_map_editor.programs.edit.api.canvas import EditCanvas

class HardCodedSpawnArea(wx.Panel, DefaultOperationUI):

    def __init__(
            self,
            parent: wx.Window,
            canvas: "EditCanvas",
            world: "BaseLevel",
            options_path: str,
    ):

        wx.Panel.__init__(self, parent, size=(350,480))
        DefaultOperationUI.__init__(self, parent, canvas, world, options_path)
        self.type_dic = {1: "Fortress", 3: "Monument", 5: "Villager Outpost", 2: "Witch Hut"}
        self.abc = []
        self.cord_dic = collections.defaultdict(list)
        self.Freeze()
        self.sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.side = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self.sizer)
        if self.world.level_wrapper.platform == "java":
            wx.MessageBox("Java Not Supported", "Not Supported", wx.OK | wx.ICON_INFORMATION)
        else:
            self._up = wx.Button(self, label="Up", size=(36, 35))
            self._up.Bind(wx.EVT_BUTTON, self._boxUp('m'))
            self._down = wx.Button(self, label="Down", size=(36, 35))
            self._down.Bind(wx.EVT_BUTTON, self._boxDown('m'))
            self._east = wx.Button(self, label="East", size=(36, 35))
            self._east.Bind(wx.EVT_BUTTON, self._boxEast('m'))
            self._west = wx.Button(self, label="West", size=(36, 35))
            self._west.Bind(wx.EVT_BUTTON, self._boxWest('m'))
            self._north = wx.Button(self, label="North", size=(36, 35))
            self._north.Bind(wx.EVT_BUTTON, self._boxNorth('m'))
            self._south = wx.Button(self, label="South", size=(36, 35))
            self._south.Bind(wx.EVT_BUTTON, self._boxSouth('m'))

            self.lbct = wx.StaticText(self, label="Step:")

            self.control = wx.SpinCtrl(self, value="1", min=1, max=1000)

            self.get_button = wx.Button(self, label="Get All")
            self.get_button.Bind(wx.EVT_BUTTON, self.get_all_)

            self.search_button = wx.Button(self, label="Within Selection")
            self.search_button.Bind(wx.EVT_BUTTON, self.search_button_)

            self.gsel = wx.Button(self, label="Set Boxs")
            self.gsel.Bind(wx.EVT_BUTTON, self._gsel)
            self.copy_boxs = wx.Button(self, label="Copy Boxs")
            self.copy_boxs.Bind(wx.EVT_BUTTON, self._copy_boxs)
            self.paste_boxs = wx.Button(self, label="Paste Boxs")
            self.paste_boxs.Bind(wx.EVT_BUTTON, self._paste_boxs)
            self.locationlist = wx.ListBox(self, size=(260, 480))
            self.locationlist.Bind(wx.EVT_LISTBOX, self.go_to_and_sel)
            self.locationlist.SetBackgroundColour((0, 0, 0))
            self.locationlist.SetForegroundColour((0, 255, 0))
            self.lb_info_move = wx.StaticText(self, label="Move All Box/s\n Step == Faster")
            self.lb_info_delete = wx.StaticText(self, label="Delete Spawns\n From Selected")
            self.lb_info = wx.StaticText(self, label="Set Bounding Boxes:\n")

            self.drop = wx.Choice(self, choices=[x for x in self.type_dic.values()],size=(150, 30))
            if "overworld" in self.canvas.dimension:
                self.drop.Clear()
                self.drop.Append([x for x in self.type_dic.values()][1:4])

            elif 'nether' in self.canvas.dimension:
                self.drop.Clear()
                self.drop.Append([x for x in self.type_dic.values()][0])
            else:
                self.drop.Clear()
                self.drop.Append("None")

            self.drop.SetSelection(0)

            self.delete_spawns = wx.Button(self, label="Delete Spawns")
            self.delete_spawns.Bind(wx.EVT_BUTTON, self._delete_spawns)

            self.sizer.Add(self.locationlist)
            self.side.Add(self.get_button, 0, wx.TOP, 5)
            self.side.Add(self.search_button, 0, wx.TOP, 5)

            self.side.Add(self.copy_boxs, 0, wx.TOP, 5)
            self.side.Add(self.paste_boxs, 0, wx.TOP, 5)

            self.grid = wx.GridSizer(4, 2, 0, -6)
            self.grid.Add(self.lbct)
            self.grid.Add(self.control, 0, wx.LEFT, -10)
            self.grid.Add(self._up)
            self.grid.Add(self._down)
            self.grid.Add(self._north)
            self.grid.Add(self._south)
            self.grid.Add(self._west)
            self.grid.Add(self._east)

            self._is_enabled = True
            self._moving = True
            self.Bind(wx.EVT_MOUSE_EVENTS, self._on_canvas_change)
            self.dim_c = ""

            self.side.Add(self.lb_info_move, 0, wx.TOP, 5)
            self.side.Add(self.grid, 0, wx.TOP, 5)
            self.side.Add(self.lb_info, 0, wx.TOP, 5)
            self.side.Add(self.drop, 0, wx.TOP, 5)
            self.side.Add(self.gsel, 0, wx.TOP, 5)
            self.side.Add(self.lb_info_delete, 0, wx.TOP, 5)
            self.side.Add(self.delete_spawns, 0, wx.TOP, 5)
            self.sizer.Add(self.side)
            self.Layout()
            self.Thaw()



    def _on_input_press(self, evt: InputPressEvent):

        if evt.action_id == ACT_BOX_CLICK:
            if self._is_enabled == True:
                self._moving = not self._moving
                self.canvas.Unbind(EVT_POINT_CHANGE)
                self._selection = BlockSelectionBehaviour(self.canvas)
                self._selection.enable()
                self._selection.bind_events()
                self._is_enabled = False
                self._moving = False
                return
            if self._is_enabled == False:
                self._is_enabled = True
                self._on_pointer_change
                return
            if self._moving:
                self.canvas.renderer.fake_levels.active_transform = ()
        evt.Skip()

    def bind_events(self):
        super().bind_events()
        self._selection.bind_events()
        self._selection.enable()

    def enable(self):

        self._selection = BlockSelectionBehaviour(self.canvas)
        self._selection.enable()

    def _on_canvas_change(self, evt):
        dim = self.canvas.dimension

        if dim != self.dim_c:
            if "overworld" in self.canvas.dimension:
                self.drop.Clear()
                self.drop.Append([x for x in self.type_dic.values()][1:4])
                self.drop.SetSelection(0)
                self.dim_c = self.canvas.dimension
            elif 'nether' in self.canvas.dimension:
                self.drop.Clear()
                self.drop.Append([x for x in self.type_dic.values()][0])
                self.drop.SetSelection(0)
                self.dim_c = self.canvas.dimension
            else:
                self.drop.Clear()
                self.drop.Append("None")
                self.drop.SetSelection(0)
                self.dim_c = self.canvas.dimension
        evt.Skip()

    def _on_pointer_change(self, evt: PointChangeEvent):
        if self._is_enabled:
            self.canvas.renderer.fake_levels.active_transform = (
                evt.point
            )
            x, y, z = evt.point
            groups = []
            for (a,b,c,aa,bb,cc) in self.abc:
                groups.append(SelectionBox((x + a, y + b, z + c), (x + aa, y + bb, z + cc)))
            sg = SelectionGroup(groups )
            self.canvas.selection.set_selection_group(sg)
        evt.Skip()

    def search_button_(self, _):
        self.cord_dic.clear()
        self.locationlist.Clear()
        sel_chunks = self.canvas.selection.selection_group.chunk_locations()
        def get_dim_value_bytes():
            if 'minecraft:the_end' in self.canvas.dimension:
                dim = int(2).to_bytes(4, 'little', signed=True)
            elif 'minecraft:the_nether' in self.canvas.dimension:
                dim = int(1).to_bytes(4, 'little', signed=True)
            elif 'minecraft:overworld' in self.canvas.dimension:
                dim = b''  # int(0).to_bytes(4, 'little', signed=True)
            return dim

        found = []
        for x, z in sel_chunks:
            xx, zz = int(x).to_bytes(4, 'little', signed=True), int(z).to_bytes(4, 'little', signed=True)
            dim = get_dim_value_bytes()
            k = xx + zz + dim + b'\x39'

            try:
                v = self.level_db.get(k)
                num_of = int.from_bytes(v[:4], 'little', signed=True)
                if len(k) > 9:  # Only Nether and Overworld Contain Hard Spawns
                    for gc, c in enumerate(range(4, 1 + (num_of * 6) * 4, 4)):
                        g = int(gc / 6)
                        self.cord_dic[f"{self.type_dic[v[-1]]} Nether:{x, z}"].append(
                            int.from_bytes(v[c + g:g + c + 4], 'little', signed=True))
                else:
                    for gc, c in enumerate(range(4, 1 + (num_of * 6) * 4, 4)):
                        g = int(gc / 6)
                        self.cord_dic[f"{self.type_dic[v[-1]]} Overworld:{x, z}"].append(
                            int.from_bytes(v[c + g:g + c + 4], 'little', signed=True))
                found.append((x, z))
            except:
                pass

        try:
            self.locationlist.InsertItems([x for x in self.cord_dic.keys()], 0)
            group = []
            for k in self.cord_dic.keys():
                cords = self.cord_dic[k]
                cx, cy, cz = self.cord_dic[k][:3]
                cx1, cy1, cz1 = self.cord_dic[k][3:6]
                lenth = int(len(cords) / 6)
                for d in range(0, (lenth * 6), 6):
                    x, y, z, xx, yy, zz = cords[d:d + 6]
                    group.append(SelectionBox((int(x), int(y), int(z)), (int(xx + 1), int(yy), int(zz + 1))))
            sel = SelectionGroup(group)
            self.canvas.selection.set_selection_group(sel)
            wx.MessageBox(f"Found and selected Spawns From Chunk\s: {found}", "Completed", wx.OK | wx.ICON_INFORMATION)
        except:
            wx.MessageBox(f"No Spawns Found", "Completed", wx.OK | wx.ICON_INFORMATION)

    def _delete_spawns(self, _):
        sel_chunks = self.canvas.selection.selection_group.chunk_locations()

        def get_dim_value_bytes():
            if 'minecraft:the_end' in self.canvas.dimension:
                dim = int(2).to_bytes(4, 'little', signed=True)
            elif 'minecraft:the_nether' in self.canvas.dimension:
                dim = int(1).to_bytes(4, 'little', signed=True)
            elif 'minecraft:overworld' in self.canvas.dimension:
                dim = b''  # int(0).to_bytes(4, 'little', signed=True)
            return dim

        for x, z in sel_chunks:
            xx, zz = int(x).to_bytes(4, 'little', signed=True), int(z).to_bytes(4, 'little', signed=True)
            dim = get_dim_value_bytes()
            chunk_key = xx + zz + dim + b'\x39'
            removed = []
            try:
                self.level_db.delete(chunk_key)
                removed.append((x,z))
            except:
                pass

        wx.MessageBox(f"Removed Spawns From Chunk\s: {removed}", "Completed", wx.OK | wx.ICON_INFORMATION)


    def _copy_boxs(self, _):
        sizes = []
        points = []
        self.abc.clear()
        for box in self.canvas.selection.selection_group.selection_boxes:

            px,py,pz = box.min
            px2, py2, pz2 = box.max
            sx, sy, sz = px2-px,py2-py,pz2-pz
            sizes.append((box.size_x,box.size_y,box.size_z))
            points.append((px,py,pz))
        box_cords = []
        fpx, fpy, fpz = 0,0,0
        for i ,((px, py, pz),(sx,sy,sz)) in enumerate(zip(points,sizes)):

            if i > 0:
                ax,ay,az = box_cords[i-1][:3]
                fpx, fpy, fpz = ((px)-(fpx))+(ax), ((py)-(fpy))+(ay), ((pz)-(fpz))+(az)
                box_cords.append(((fpx), (fpy), (fpz),sx,sy,sz))
            else:
                box_cords.append(((fpx), (fpy), (fpz), sx,sy,sz))
            fpx , fpy , fpz = px, py, pz

        for (a,b,c,aa,bb,cc) in box_cords:
            tx, ty, tz = 0, 0, 0
            tx1, ty1, tz1 = 0, 0, 0
            self.abc.append(( tx+a, ty+b, tz+c,(tx1+aa)+a, (ty1+bb)+b, (tz1+cc)+c))

    def _paste_boxs(self, evt):
        self.canvas.Bind(EVT_POINT_CHANGE, self._on_pointer_change)#, id=300, id2=400)
        self.canvas.Bind(EVT_INPUT_PRESS, self._on_input_press)#, id=301, id2=401)
        self._is_enabled = True
        self._moving = True
        self._on_pointer_change

    def _gsel(self, _):
        added = []
        set_it = collections.defaultdict(list)
        for box in self.canvas.selection.selection_group.selection_boxes:
            for chunk, box in box.chunk_boxes():
                x, y, z, xx, yy, zz = box.min_x.to_bytes(4, 'little', signed=True), \
                                      box.min_y.to_bytes(4, 'little', signed=True), \
                                      box.min_z.to_bytes(4, 'little', signed=True), \
                                      (box.max_x - 1).to_bytes(4, 'little', signed=True), \
                                      box.max_y.to_bytes(4, 'little', signed=True), \
                                      (box.max_z - 1).to_bytes(4, 'little', signed=True)  # convert to the raw format.
                xc, zc = chunk #[xcc for xcc in box.chunk_locations()][0]
                xcb, zcb = xc.to_bytes(4, 'little', signed=True), zc.to_bytes(4, 'little', signed=True)
                added.append((self.drop.GetStringSelection(),xc, zc))
                if xcb + zcb + self.get_dim_value_bytes() in set_it.keys():
                    set_it[xcb + zcb + self.get_dim_value_bytes()].append((b'\x01' + x + y + z + xx + yy + zz))
                else:
                    set_it[xcb + zcb + self.get_dim_value_bytes()].append((x + y + z + xx + yy + zz))

        t = list(self.type_dic.keys())[list(self.type_dic.values()).index(self.drop.GetStringSelection())]
        for x in set_it.values(): # set the selected type
            x.append(t.to_bytes(1, 'little', signed=True))

        for kb, vb in set_it.items(): # join and append
            lenth = (len(vb)-1).to_bytes(4, 'little', signed=True)
            data = lenth + b''.join(vb)
            key = kb + b'\x39'
            self.level_db.put(key,data)

        f_added = set(added)
        wx.MessageBox(f"Added Spawn Type to Chunk\s: {f_added}", "Completed", wx.OK | wx.ICON_INFORMATION)


    def get_dim_value_bytes(self):
        if 'minecraft:the_end' in self.canvas.dimension:
            dim = int(2).to_bytes(4, 'little', signed=True)
        elif 'minecraft:the_nether' in self.canvas.dimension:
            dim = int(1).to_bytes(4, 'little', signed=True)
        elif 'minecraft:overworld' in self.canvas.dimension:
            dim = b''
        return dim

    def go_to_and_sel(self, _):
        group = []
        cords = self.cord_dic[self.locationlist.GetStringSelection()]
        cx,cy,cz = self.cord_dic[self.locationlist.GetStringSelection()][:3]
        cx1, cy1, cz1 = self.cord_dic[self.locationlist.GetStringSelection()][3:6]
        self.canvas.camera.set_location((float(((cx+cx1)/2)+10),float(((cy+cy1)/2)+40 ),float(((cz+cz1)/2))-10))
        self.canvas.camera.set_rotation((float(0),float(90)))
        lenth = int(len(cords)/6)
        for d in range(0, (lenth*6), 6):
            x, y, z, xx, yy, zz = cords[d:d+6]
            group.append(SelectionBox((int(x), int(y), int(z)), (int(xx+1), int(yy), int(zz+1))))
        sel = SelectionGroup(group)
        if "Overworld" in self.locationlist.GetStringSelection():
            self.canvas.dimension = 'minecraft:overworld'
        else:
            self.canvas.dimension = 'minecraft:the_nether'
        self.canvas.selection.set_selection_group(sel)
        self.canvas.camera._notify_moved()

    def get_all_(self, _):
        self.cord_dic.clear()
        self.locationlist.Clear()
        for k,v in self.level_db.iterate():
            if k[-1] == 57 and (len(k) == 9 or len(k) == 13):
                num_of = int.from_bytes(v[:4], 'little', signed=True)
                xc,zc = int.from_bytes(k[:4], 'little', signed=True),int.from_bytes(k[4:8], 'little', signed=True)
                if len(k) > 9: # Only Nether and Overworld Contain Hard Spawns
                    for gc, c in enumerate(range(4, 1 + (num_of * 6) * 4, 4)):
                        g = int(gc/6)
                        self.cord_dic[f"{self.type_dic[v[-1]]} Nether:{xc,zc}"].append(int.from_bytes(v[c+g:g+c+4], 'little', signed=True))
                        # if gc%6 == 5 and g > 0: # located the ... I guess spacer bytes
                        #     print(xc,zc, int.from_bytes(v[c+g+4:g+4+c+1], 'little', signed=True),''.join('{:02x}'.format(x) for x in v) )
                else:
                    for gc, c in enumerate(range(4, 1 + (num_of * 6) * 4, 4)):
                        g = int(gc / 6)
                        self.cord_dic[f"{self.type_dic[v[-1]]} Overworld:{xc,zc}"].append(int.from_bytes(v[c+g:g+c+4], 'little', signed=True))
        self.locationlist.InsertItems([ x for x in self.cord_dic.keys()], 0)

    @property
    def level_db(self):
        level_wrapper = self.world.level_wrapper
        if hasattr(level_wrapper, "level_db"):
            return level_wrapper.level_db
        else:
            return level_wrapper._level_manager._db

    def _boxUp(self, v):
        def OnClick(event):
            sgs = []
            print(self.control.GetValue())
            for box in self.canvas.selection.selection_group.selection_boxes:
                xx, yy, zz = box.max_x, box.max_y, box.max_z
                xm, ym, zm = box.min_x, box.min_y, box.min_z
                sgs.append(SelectionBox((xm, ym + self.control.GetValue(), zm), (xx, yy + self.control.GetValue(), zz)))
            self.canvas.selection.set_selection_group(SelectionGroup(sgs))
        return OnClick

    def _boxDown(self, v):
        def OnClick(event):
            sgs = []
            for box in self.canvas.selection.selection_group.selection_boxes:
                xx, yy, zz = box.max_x, box.max_y, box.max_z
                xm, ym, zm = box.min_x, box.min_y, box.min_z
                sgs.append(SelectionBox((xm, ym - self.control.GetValue(), zm), (xx, yy - self.control.GetValue(), zz)))
            self.canvas.selection.set_selection_group(SelectionGroup(sgs))
        return OnClick

    def _boxNorth(self, v):

        def OnClick(event):
            sgs = []
            for box in self.canvas.selection.selection_group.selection_boxes:
                xx, yy, zz = box.max_x, box.max_y, box.max_z
                xm, ym, zm = box.min_x, box.min_y, box.min_z
                sgs.append(SelectionBox((xm, ym, zm - self.control.GetValue()), (xx, yy, zz - self.control.GetValue())))
            self.canvas.selection.set_selection_group(SelectionGroup(sgs))
        return OnClick

    def _boxSouth(self, v):
        def OnClick(event):
            sgs = []
            for box in self.canvas.selection.selection_group.selection_boxes:
                xx, yy, zz = box.max_x, box.max_y, box.max_z
                xm, ym, zm = box.min_x, box.min_y, box.min_z
                sgs.append(SelectionBox((xm, ym, zm + self.control.GetValue()), (xx, yy, zz + self.control.GetValue())))
            if len(sgs) > 0:
                self.canvas.selection.set_selection_group(SelectionGroup(sgs))
        return OnClick

    def _boxEast(self, v):
        def OnClick(event):
            sgs = []
            for box in self.canvas.selection.selection_group.selection_boxes:
                xx, yy, zz = box.max_x, box.max_y, box.max_z
                xm, ym, zm = box.min_x, box.min_y, box.min_z
                sgs.append(SelectionBox((xm + self.control.GetValue(), ym, zm), (xx + self.control.GetValue(), yy, zz)))
            self.canvas.selection.set_selection_group(SelectionGroup(sgs))
        return OnClick

    def _boxWest(self, v):
        def OnClick(event):
            sgs = []
            for box in self.canvas.selection.selection_group.selection_boxes:
                xx, yy, zz = box.max_x, box.max_y, box.max_z
                xm, ym, zm = box.min_x, box.min_y, box.min_z
                sgs.append(SelectionBox((xm - self.control.GetValue(), ym, zm), (xx - self.control.GetValue(), yy, zz)))
            self.canvas.selection.set_selection_group(SelectionGroup(sgs))
        return OnClick

export = dict(name="Hard Coded Spawn Area Editor v1.11", operation=HardCodedSpawnArea) #By PremiereHell
