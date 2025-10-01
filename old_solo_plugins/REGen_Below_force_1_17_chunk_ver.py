import wx
from amulet.api.block_entity import BlockEntity
from amulet.api.block import Block
from typing import TYPE_CHECKING, Type, Any, Callable, Tuple, BinaryIO, Optional, Union
from amulet.utils import world_utils
from amulet.api.selection import SelectionGroup
from amulet.api.selection import SelectionBox
from amulet.utils import block_coords_to_chunk_coords
from amulet_map_editor.programs.edit.api.operations import DefaultOperationUI
from amulet_map_editor.api.wx.ui.base_select import BaseSelect
from amulet.api.errors import ChunkDoesNotExist
import amulet_nbt

if TYPE_CHECKING:
    from amulet.api.level import BaseLevel
    from amulet_map_editor.programs.edit.api.canvas import EditCanvas
class ForceHeightUpdate(wx.Panel, DefaultOperationUI):

    def __init__(
            self,
            parent: wx.Window,
            canvas: "EditCanvas",
            world: "BaseLevel",
            options_path: str,
    ):

        wx.Panel.__init__(self, parent)
        DefaultOperationUI.__init__(self, parent, canvas, world, options_path)
        self.Freeze()
        self._sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self._sizer)
        side_sizer = wx.BoxSizer(wx.VERTICAL)
        self._sizer.Add(side_sizer)
        self._run_button = wx.Button(self, label="Convert Chunks to 1.17")
        self.setup = wx.Button(self, label="(Save new seed)")
        self.seed_input = wx.TextCtrl(self, style=wx.TE_LEFT, size=(120, 25))
        if self.seed_input.GetValue() == "":
            self.seed_input.SetValue("1147413641")
        self.label = wx.StaticText(self, label="SEED [-2147483648 to 2147483647]")
        self._run_button.Bind(wx.EVT_BUTTON, self._run_operation)
        self.setup.Bind(wx.EVT_BUTTON,self.set_world_version)
        side_sizer.Add(self._run_button, 10, wx.TOP | wx.LEFT, 5)
        side_sizer.Add(self.seed_input, 10, wx.TOP | wx.LEFT, 5)
        side_sizer.Add(self.label, 10, wx.TOP | wx.LEFT, 5)

        if self.world.level_wrapper.version != (1,17,11,1,0):
            side_sizer.Add(self.setup, 10, wx.TOP | wx.LEFT, 5)
            self.setup.SetLabel("Setup needed 1.17 (Save Seed)")
        else:
            side_sizer.Add(self.setup, 10, wx.TOP | wx.LEFT, 5)
        self.Layout()
        self.Thaw()

    @property
    def wx_add_options(self) -> Tuple[int, ...]:
        return (0,)

    def _cls(self):
        print("\033c\033[3J", end='')
    def set_world_version(self, _):
        self.world.level_wrapper.root_tag['FlatWorldLayers'] = amulet_nbt.TAG_String("null")
        self.world.level_wrapper.root_tag['InventoryVersion'] = amulet_nbt.TAG_String("1.17.11")
        i1 = amulet_nbt.TAG_Int(1)
        i2 = amulet_nbt.TAG_Int(17)
        i3 = amulet_nbt.TAG_Int(11)
        i4 = amulet_nbt.TAG_Int(1)
        i5 = amulet_nbt.TAG_Int(0)
        self.world.level_wrapper.root_tag['lastOpenedWithVersion'] = amulet_nbt.TAG_List([i1, i2, i3, i4, i5])
        self.world.level_wrapper.root_tag['RandomSeed'] = amulet_nbt.TAG_Long((int(self.seed_input.GetValue())))
        self.world.level_wrapper.root_tag.save()
        self.world.save()
        self.world.purge()
        if self.world.level_wrapper.version != (1, 17, 11, 1, 0):
            wx.MessageBox( "Close and reload within amulet you should see (1,17,11,1,0) at the top."
                                   "\n  If you see this message you need close and reload the world agian in Amulet\n"
                                   "you should not see this twice","IMPORTANT", wx.OK | wx.ICON_INFORMATION)

    def _run_operation(self, _):
        block_platform = self.world.level_wrapper.platform
        block_version = (1,17,11,1,0)
        xx, zz = 0,0
        get_total = [x for x in self.world.level_wrapper.all_chunk_coords(self.canvas.dimension)]
        total = len(get_total)
        count = 0
        prg_max = total
        prg_pre = 0
        prg_pre_th = total / 100
        self.prog = wx.ProgressDialog("Y_Zero Filling bedrock", str(0) + " of " + str(prg_max),
                style=wx.PD_AUTO_HIDE | wx.PD_CAN_ABORT | wx.PD_ELAPSED_TIME | wx.PD_REMAINING_TIME)
        self.prog.Show(True)

        for xc, xz in  self.world.level_wrapper.all_chunk_coords(self.canvas.dimension):
            if self.prog.WasCancelled():
                self.prog.Hide()
                self.prog.Destroy()
                break
            y = 0
            xx, zz = world_utils.chunk_coords_to_block_coords(xc,xz)
            for xcc in range(16):
                for zcc in range(16):
                    x = xcc + xx
                    z = zcc + zz
                    block = Block("minecraft", "bedrock")

                    self.world.set_version_block(x,y,z,self.canvas.dimension,
                                                 (block_platform,block_version),block,None)
            if count >= prg_pre_th:
                prg_pre_th += total / 100
                prg_pre += 0.99
                self.prog.Update(prg_pre, f"Chunk: {xc,xz} Done.... {count} of {total}")
            count += 1
        self.prog.Update(100, f"Chunk: {xc, xz} Done \n {count} of {total}")

        self.canvas.run_operation(lambda: self._refresh_chunk(self.canvas.dimension, self.world, xx, zz))

        wx.MessageBox( "Make Sure to save and close Amulet and "
                           "\nYou Must reload minecraft so the changes are detected.","IMPORTANT", wx.OK | wx.ICON_INFORMATION)

    def _refresh_chunk(self, dimension, world, x, z):
        cx, cz = block_coords_to_chunk_coords(x, z)
        chunk = world.get_chunk(cx, cz, dimension)
        chunk.changed = True

    pass

export = dict(name="Regenorate(Force New Height Update) -Y v1.00", operation=ForceHeightUpdate) #By PremiereHell