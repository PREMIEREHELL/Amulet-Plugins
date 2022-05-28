from typing import TYPE_CHECKING

import amulet
import wx
import math
import numpy as np
from amulet.utils import block_coords_to_chunk_coords
from amulet.api.chunk.biomes import BiomesShape
from amulet_map_editor.api.wx.ui.base_select import EVT_PICK
from amulet_map_editor.api.wx.ui.biome_select import BiomeDefine
from amulet_map_editor.programs.edit.api.operations import SimpleOperationPanel
from amulet_map_editor.api.wx.ui.simple import SimpleChoiceAny
from amulet.api.selection import SelectionGroup
from amulet.api.selection import SelectionBox
if TYPE_CHECKING:
    from amulet.api.level import BaseLevel
    from amulet_map_editor.programs.edit.api.canvas import EditCanvas
    from amulet.api.selection import SelectionGroup
    from amulet.api.selection import SelectionBox
    from amulet.api.data_types import Dimension, OperationReturnType


options = {}
MODE = {
    'RepMode': "This Replace's The Bottom selected biome With the Top selected biome within the selection box (ColumnMode for (java))",
}

Border = wx.TOP | wx.LEFT | wx.RIGHT | wx.EXPAND


class SetBiome(SimpleOperationPanel):
    def __init__(
        self,
        parent: wx.Window,
        canvas: "EditCanvas",
        world: "BaseLevel",
        options_path: str,
    ):
        SimpleOperationPanel.__init__(self, parent, canvas, world, options_path)
        self.Freeze()

        self._mode_description = wx.TextCtrl(
            self, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_BESTWRAP
        )
        self._sizer.Add(self._mode_description, 0, Border, 5)

        self._mode_description.SetLabel(MODE.get("RepMode"))
        self._mode_description.Fit()

        self._biome_choice = BiomeDefine(
            self,
            world.level_wrapper.translation_manager,
            wx.VERTICAL,
            *(
                options.get("original_block_options", [])
                or [world.level_wrapper.platform]
            ),
            show_pick_biome=True,
        )
        self._biome_rep_choice = BiomeDefine(
            self,
            world.level_wrapper.translation_manager,
            wx.VERTICAL,
            *(
                options.get("original_block_options", [])
                or [world.level_wrapper.platform]
            ),
            show_pick_biome=True,
        )
        self._show_rep_pointer = False
        self._biome_choice.Bind(EVT_PICK, self._on_pick_biome_button)
        self._sizer.Add(self._biome_choice, 1, Border, 5)
        self._biome_rep_choice.Bind(EVT_PICK, self._on_pick_rep_biome_button)
        self._sizer.Add(self._biome_rep_choice, 1, Border, 5)

        self._add_run_button()

        self.Thaw()


    def _on_mode_change(self, evt):
        self._mode_description.SetLabel(MODES[self._mode.GetCurrentObject()])
        self._mode_description.Fit()
        self.Layout()
        evt.Skip()

    def _on_pick_biome_button(self, evt):
        """Set up listening for the biome click"""
        self._show_pointer = True
    def _on_pick_rep_biome_button(self, evt):
        """Set up listening for the biome click"""
        self._show_rep_pointer = True
        self._show_pointer = True

    def _on_box_click(self):
        rep = False
        if self._show_pointer or self._show_rep_pointer:
            if self._show_rep_pointer:
                rep = True
            self._show_pointer = False
            self._show_rep_pointer = False

            x, y, z = self._pointer.pointer_base

            # TODO: replace with "get_biome(x, y, z)" if it'll be created
            cx, cz = block_coords_to_chunk_coords(
                x, z, sub_chunk_size=self.world.sub_chunk_size
            )
            offset_x, offset_z = x - 16 * cx, z - 16 * cz
            try:
                chunk = self.world.get_chunk(cx, cz, self.canvas.dimension)
                if chunk.biomes.dimension == BiomesShape.Shape3D:
                    biome = chunk.biomes[offset_x // 4, y // 4, offset_z // 4]
                elif chunk.biomes.dimension == BiomesShape.Shape2D:
                    biome = chunk.biomes[offset_x, offset_z]
                else:
                    return
                if not rep:
                    self._biome_choice.universal_biome = chunk.biome_palette[biome]
                elif rep:
                    self._biome_rep_choice.universal_biome = chunk.biome_palette[biome]
                    rep = False
                else:
                    return

            except:
                print("no biome chunk data found")

    def _operation(
        self, world: "BaseLevel", dimension: "Dimension", selection: "SelectionGroup"
    ) -> "OperationReturnType":
        iter_count = len(list(world.get_coord_box(dimension, selection, False)))
        for count, (chunk, slices, _) in enumerate(
                world.get_chunk_slice_box(dimension, selection, False)
        ):
            new_biome = chunk.biome_palette.get_add_biome(
                self._biome_choice.universal_biome
            )
            old_biome = chunk.biome_palette.get_add_biome(
                self._biome_rep_choice.universal_biome)

            if chunk.biomes.dimension == BiomesShape.Shape3D:
                    slices = (
                        slice(slices[0].start // 4, math.ceil(slices[0].stop / 4)),
                        slice(None, None, None),
                        slice(slices[2].start // 4, math.ceil(slices[2].stop / 4)),
                    )
            elif chunk.biomes.dimension == BiomesShape.Shape2D:
                    slices = (slices[0], slices[2])
            else:
                continue

            newnp = np.array(chunk.biomes[slices])
            mask = (newnp == old_biome)
            newnp[mask] = new_biome
            chunk.biomes[slices] = newnp
            chunk.changed = True


            yield (count + 1) / iter_count

export = {
    "name": "Replace Biome",  #Simple conversion of original Amulet set biomes to Replace biome,  by PremiereHell
    "operation": SetBiome,
}
