from typing import Tuple, Dict, List, Union, Iterable, Optional, TYPE_CHECKING, Any
from amulet_map_editor.programs.edit.api.operations import DefaultOperationUI
from amulet_map_editor.programs.edit.api.behaviour.pointer_behaviour import PointerBehaviour
from amulet_map_editor.programs.edit.api.behaviour.pointer_behaviour import EVT_POINT_CHANGE
from amulet_map_editor.programs.edit.api.behaviour.pointer_behaviour import PointChangeEvent
from amulet.api.data_types import PointCoordinates
from amulet_map_editor.programs.edit.api.behaviour import StaticSelectionBehaviour
from amulet_map_editor.programs.edit.api.events import EVT_SELECTION_CHANGE
from amulet_map_editor.programs.edit.api.behaviour import BlockSelectionBehaviour
from amulet_map_editor.programs.edit.api.behaviour.block_selection_behaviour import RenderBoxChangeEvent
from amulet_nbt import *
import numpy
import struct
import wx
if TYPE_CHECKING:
    from amulet.api.level import BaseLevel
    from amulet_map_editor.programs.edit.api.canvas import EditCanvas


biome_id_to_name = {
    0: "Ocean",
    1: "Plains",
    2: "Desert",
    3: "Windswept Hills",
    4: "Forest",
    5: "Taiga",
    6: "Swamp",
    7: "River",
    8: "Nether Wastes",
    9: "The End",
    10: "Legacy Frozen Ocean",
    11: "Frozen River",
    12: "Snowy Plains",
    13: "Snowy Mountains",
    14: "Mushroom Fields",
    15: "Mushroom Field Shore",
    16: "Beach",
    17: "Desert Hills",
    18: "Wooded Hills",
    19: "Taiga Hills",
    20: "Mountain Edge",
    21: "Jungle",
    22: "Jungle Hills",
    23: "Sparse Jungle",
    24: "Deep Ocean",
    25: "Stony Shore",
    26: "Snowy Beach",
    27: "Birch Forest",
    28: "Birch Forest Hills",
    29: "Dark Forest",
    30: "Snowy Taiga",
    31: "Snowy Taiga Hills",
    32: "Old Growth Pine Taiga",
    33: "Giant Tree Taiga Hills",
    34: "Windswept Forest",
    35: "Savanna",
    36: "Savanna Plateau",
    37: "Badlands",
    38: "Wooded Badlands",
    39: "Badlands Plateau",
    40: "Warm Ocean",
    41: "Deep Warm Ocean",
    42: "Lukewarm Ocean",
    43: "Deep Lukewarm Ocean",
    44: "Cold Ocean",
    45: "Deep Cold Ocean",
    46: "Frozen Ocean",
    47: "Deep Frozen Ocean",
    48: "Bamboo Jungle",
    49: "Bamboo Jungle Hills",
    129: "Sunflower Plains",
    130: "Desert Lakes",
    131: "Windswept Gravelly Hills",
    132: "Flower Forest",
    133: "Taiga Mountains",
    134: "Swamp Hills",
    140: "Ice Spikes",
    149: "Modified Jungle",
    151: "Modified Jungle Edge",
    155: "Old Growth Birch Forest",
    156: "Tall Birch Hills",
    157: "Dark Forest Hills",
    158: "Snowy Taiga Mountains",
    160: "Old Growth Spruce Taiga",
    161: "Giant Spruce Taiga Hills",
    162: "Modified Gravelly Mountains",
    163: "Windswept Savanna",
    164: "Shattered Savanna Plateau",
    165: "Eroded Badlands",
    166: "Modified Wooded Badlands Plateau",
    167: "Modified Badlands Plateau",
    178: "Soul Sand Valley",
    179: "Crimson Forest",
    180: "Warped Forest",
    181: "Basalt Deltas",
    182: "Jagged Peaks",
    183: "Frozen Peaks",
    184: "Snowy Slopes",
    185: "Grove",
    186: "Meadow",
    187: "Lush Caves",
    188: "Dripstone Caves",
    189: "Stony Peaks",
    190: "Deep Dark",
    191: "Mangrove Swamp",
    192: "Cherry Grove",
    193: "Pale Garden",
}
def biomes_dict_to_numpy_arrays(biomes: dict[int, tuple[numpy.ndarray, numpy.ndarray]]
                                ) -> dict[int, numpy.ndarray]:
    """
    Convert your decode_full_3d_biomes() output (palette, indices) into a dict
    cy -> 16x16x16 numpy array of actual biome IDs in x,y,z order.
    """
    out = {}
    for cy, (palette, indices) in biomes.items():
        # missing palette/indices unlikely here because decode_full_3d_biomes sets them,
        # but just in case:
        if palette is None:
            continue

        if len(palette) == 1:
            # single palette: whole subchunk is the single biome id
            arr = numpy.full((16, 16, 16), int(palette[0]), dtype=numpy.uint32)
        else:
            # palette lookup: indices is shape (16,16,16) with integer indices into palette
            # advanced indexing will produce shape (16,16,16)
            arr = palette[indices.astype(int)]
        out[cy] = arr
    return out


def numpy_arrays_to_biomes_bytes(arrays: dict[int, numpy.ndarray]) -> bytes:
    """
    Convert a dict cy -> 16x16x16 numpy array of biome IDs back into the raw bytes
    sequence for the 3D-biome region (subchunks -4..19).
    Depends on the existing _encode_packed_array(indices_array, biome=True).
    """
    parts = []
    for cy in range(-4, 20):
        arr = arrays.get(cy)
        if arr is None:
            # missing subchunk marker
            parts.append(b'\xff')
            continue

        # ensure correct shape & dtype
        arr = numpy.asarray(arr, dtype=numpy.uint32)
        if arr.shape != (16, 16, 16):
            raise ValueError(f"subchunk {cy} array must be shape (16,16,16), got {arr.shape}")

        flat = arr.ravel()
        # preserve first-occurrence order for palette
        unique_vals, first_idx = numpy.unique(flat, return_index=True)
        order = numpy.argsort(first_idx)
        palette_vals = unique_vals[order].astype(numpy.uint32)

        if palette_vals.size == 1:
            # single-palette shortcut: header 0 (bits_per_value) with biome-flag set -> 0x01
            parts.append(b'\x01')
            parts.append(struct.pack('<I', int(palette_vals[0])))
        else:
            # build index array: map each cell value -> index in palette_vals
            mapping = {int(v): i for i, v in enumerate(palette_vals)}
            # vectorized mapping of flat -> indices
            indices_flat = numpy.fromiter((mapping[int(v)] for v in flat), dtype=numpy.uint32)
            indices = indices_flat.reshape((16, 16, 16))
            # use existing encoder (keeps your bit-packing logic)
            packed = _encode_packed_array(indices, min_bit_size=1, biome=True)
            parts.append(packed)
            parts.append(struct.pack('<I', len(palette_vals)))
            parts.append(palette_vals.astype('<i4').tobytes())

    return b"".join(parts)

@staticmethod #max(int(numpy.amax(b)).bit_length(), 1)
def _encode_packed_array(arr: numpy.ndarray, min_bit_size=1, biome=False) -> bytes:
    bits_per_value = max(int(numpy.amax(arr)).bit_length(), min_bit_size)
    if bits_per_value == 7:
        bits_per_value = 8
    elif 9 <= bits_per_value <= 15:
        bits_per_value = 16
    if biome:
        header = bytes([bits_per_value << 1 | 1])
    else:
        header = bytes([bits_per_value << 1])
    values_per_word = 32 // bits_per_value  # Word = 4 bytes, basis of compacting.
    word_count = -(
            -4096 // values_per_word
    )  # Ceiling divide is inverted floor divide

    arr = arr.swapaxes(1, 2).ravel()
    packed_arr = bytes(
        reversed(
            numpy.packbits(
                numpy.pad(
                    numpy.pad(
                        numpy.unpackbits(
                            numpy.ascontiguousarray(arr[::-1], dtype=">i").view(
                                dtype="uint8"
                            )
                        ).reshape(4096, -1)[:, -bits_per_value:],
                        [(word_count * values_per_word - 4096, 0), (0, 0)],
                        "constant",
                    ).reshape(-1, values_per_word * bits_per_value),
                    [(0, 0), (32 - values_per_word * bits_per_value, 0)],
                    "constant",
                )
            )
            .view(dtype=">i4")
            .tobytes()
        )
    )
    return header + packed_arr


@staticmethod
def _decode_packed_array(data: bytes) -> Tuple[bytes, int, Optional[numpy.ndarray]]:
    """
    Parse a packed array as documented here
    https://gist.github.com/Tomcc/a96af509e275b1af483b25c543cfbf37

    :param data: The data to parse
    :return:
    """
    bits_per_value, data = struct.unpack("b", data[0:1])[0] >> 1, data[1:]

    if bits_per_value > 0:
        values_per_word = (
                32 // bits_per_value
        )  # Word = 4 bytes, basis of compacting.
        word_count = -(
                -4096 // values_per_word
        )  # Ceiling divide is inverted floor divide

        arr = numpy.packbits(
            numpy.pad(
                numpy.unpackbits(
                    numpy.frombuffer(
                        bytes(reversed(data[: 4 * word_count])), dtype="uint8"
                    )
                )
                .reshape(-1, 32)[:, -values_per_word * bits_per_value:]
                .reshape(-1, bits_per_value)[-4096:, :],
                [(0, 0), (16 - bits_per_value, 0)],
                "constant",
            )
        ).view(dtype=">i2")[::-1]
        arr = arr.reshape((16, 16, 16)).swapaxes(1, 2)
        data = data[4 * word_count:]
    else:
        arr = None

    return data, bits_per_value, arr

class BIOME(wx.Panel, DefaultOperationUI):

    def __init__(
            self,
            parent: wx.Window,
            canvas: "EditCanvas",
            world: "BaseLevel",
            options_path: str,
    ):

        wx.Panel.__init__(self, parent)
        DefaultOperationUI.__init__(self, parent, canvas, world, options_path)
        self._sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self._sizer)
        self.v_byte = 9

        # biome listbox
        self.text = wx.ListBox(self, size=(300,300), choices=[x for x in biome_id_to_name.values()])

        # buttons
        self.butt = wx.Button(self, label="Get Biome", size=(75,25))
        self.butt.Bind(wx.EVT_BUTTON, self.get_biome)

        self.butt2 = wx.Button(self, label="Set Biome", size=(75,25))
        self.butt2.Bind(wx.EVT_BUTTON, self.set_biome)

        self.butt3 = wx.Button(self, label="Add Custom Biome", size=(130,25))
        self.butt3.Bind(wx.EVT_BUTTON, self.add_custom_biome)

        # layout
        self._sizer.Add(self.text, 0, wx.ALL, 5)
        self._sizer.Add(self.butt, 0, wx.ALL, 5)
        self._sizer.Add(self.butt2, 0, wx.ALL, 5)
        self._sizer.Add(self.butt3, 0, wx.ALL, 5)

        self._sizer.Fit(self)
        self.Fit()
        self.Layout()

    def add_custom_biome(self, event):
        """Prompt user to add a custom biome ID + name."""
        dlg = wx.TextEntryDialog(self, "Enter new biome ID (integer):", "Custom Biome")
        if dlg.ShowModal() == wx.ID_OK:
            try:
                biome_id = int(dlg.GetValue())
            except ValueError:
                wx.MessageBox("Biome ID must be an integer.", "Error", wx.ICON_ERROR)
                dlg.Destroy()
                return
        else:
            dlg.Destroy()
            return
        dlg.Destroy()

        dlg = wx.TextEntryDialog(self, "Enter biome name:", "Custom Biome")
        if dlg.ShowModal() == wx.ID_OK:
            biome_name = dlg.GetValue().strip()
            if not biome_name:
                wx.MessageBox("Biome name cannot be empty.", "Error", wx.ICON_ERROR)
                dlg.Destroy()
                return
        else:
            dlg.Destroy()
            return
        dlg.Destroy()

        # add to dictionary
        if biome_id in biome_id_to_name:
            wx.MessageBox(f"Biome ID {biome_id} already exists ({biome_id_to_name[biome_id]}).", "Error", wx.ICON_ERROR)
            return

        biome_id_to_name[biome_id] = biome_name

        # refresh listbox
        self.text.Set([x for x in biome_id_to_name.values()])

        wx.MessageBox(f"Custom biome added: {biome_id} -> {biome_name}", "Success", wx.ICON_INFORMATION)
    def bind_events(self):
        super().bind_events()
        self._selection = BlockSelectionBehaviour(self.canvas)
        self._selection.bind_events()
        self._selection.enable()

    def get_biome(self, _):
        selection = [x for x in self.canvas.selection.selection_group.blocks]

        if not selection:
            wx.MessageBox("Need to have a selection")
            return

        lines = []

        for xx, yy, zz in selection:
            cx, cy, cz = xx // 16, yy // 16, zz // 16
            raw = self.level_db.get(self.chunk_biome_key(cx, cz))
            if raw is None or len(raw) <= 512:
                lines.append(f"({xx}, {yy}, {zz}): <no biome data>")
                continue

            biomes = self.decode_full_3d_biomes(raw[512:])
            entry = biomes.get(cy)
            if entry is None:
                lines.append(f"({xx}, {yy}, {zz}): <missing subchunk>")
                continue

            palette, indices = entry
            if len(palette) == 1:
                biome_id = int(palette[0])
            else:
                biome_id = int(palette[indices[xx % 16, yy % 16, zz % 16]])

            biome_name = biome_id_to_name.get(biome_id, f"<unknown:{biome_id}>")
            lines.append(f"({xx}, {yy}, {zz}): {biome_name}")

        # join into one block of text
        text_output = "\n".join(lines)

        # popup dialog with selectable/copyable text
        dlg = wx.Dialog(self, title="Biome Viewer", size=(400, 300))
        sizer = wx.BoxSizer(wx.VERTICAL)
        txt_ctrl = wx.TextCtrl(
            dlg, value=text_output, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL
        )
        sizer.Add(txt_ctrl, 1, wx.EXPAND | wx.ALL, 5)
        btn = wx.Button(dlg, wx.ID_OK, "Close")
        sizer.Add(btn, 0, wx.ALIGN_CENTER | wx.ALL, 5)
        dlg.SetSizer(sizer)
        dlg.Layout()
        dlg.ShowModal()
        dlg.Destroy()

    def set_biome(self, _):
        # read raw chunk
        # gather selections and subchunk locations (same as your original approach)
        sub_chunk_locations = [x for x in self.canvas.selection.selection_group.sub_chunk_locations()]
        selections = [x for x in self.canvas.selection.selection_group.blocks]
        name_to_biome_id = {v: k for k, v in biome_id_to_name.items()}

        if len(selections) == 0:
            wx.MessageBox("Need to have a selection")
            return

        # Organize selected block coordinates by chunk (sx, sy, sz)
        sub_organized_locations = {}
        for sx, sy, sz in sub_chunk_locations:
            for bx, by, bz in selections:
                if (bx // 16, by // 16, bz // 16) == (sx, sy, sz):
                    sub_organized_locations.setdefault((sx, sy, sz), []).append((bx, by, bz))

        if not sub_organized_locations:
            wx.MessageBox("No selected blocks inside the current subchunk locations")
            return

        selected_name = self.text.GetStringSelection()
        if not selected_name:
            wx.MessageBox("No biome selected in the listbox")
            return
        selected_biome_id = name_to_biome_id.get(selected_name)
        if selected_biome_id is None:
            wx.MessageBox(f"Unknown biome selected: {selected_name}")
            return

        # Process each affected chunk
        for (sx, sy, sz), block_list in sub_organized_locations.items():
            key = self.chunk_biome_key(sx, sz)  # note: chunk_biome_key(xc, xz)
            raw = self.level_db.get(key)
            if raw is None or len(raw) < 512:
                raw_height = bytes(512)
                raw_biome = b""
            else:
                raw_height = raw[:512]
                raw_biome = raw[512:]

            # decode to your (palette, indices) dict
            biomes = self.decode_full_3d_biomes(raw_biome)

            # convert decoded palettes+indices -> dict cy -> 16x16x16 numpy array of biome IDs (x,y,z)
            id_arrays = {}
            for cy, (palette, indices) in biomes.items():
                if palette is None:
                    continue
                if len(palette) == 1:
                    id_arrays[cy] = numpy.full((16, 16, 16), int(palette[0]), dtype=numpy.uint32)
                else:
                    # indices are indices into palette; produce actual biome IDs
                    id_arrays[cy] = palette[indices.astype(int)]

            # apply edits: ensure arrays exist for each cy we modify and set the selected biome id
            for bx, by, bz in block_list:
                cy = by // 16
                lx, ly, lz = bx % 16, by % 16, bz % 16
                if cy not in id_arrays:
                    # create a new subchunk array pre-filled with the selected biome
                    id_arrays[cy] = numpy.full((16, 16, 16), int(selected_biome_id), dtype=numpy.uint32)
                else:
                    id_arrays[cy][lx, ly, lz] = int(selected_biome_id)

            # Rebuild raw biome bytes for full cy range (-4..19)
            parts = []
            for cy in range(-4, 20):
                arr = id_arrays.get(cy)
                if arr is None:
                    parts.append(b'\xff')  # missing subchunk marker
                    continue

                # normalize shape & dtype
                arr = numpy.asarray(arr, dtype=numpy.uint32)
                if arr.shape != (16, 16, 16):
                    raise ValueError(f"subchunk {cy} must be shape (16,16,16), got {arr.shape}")

                flat = arr.ravel()

                # build palette preserving first-seen order
                uniq_vals, first_idx = numpy.unique(flat, return_index=True)
                order = numpy.argsort(first_idx)
                palette_vals = uniq_vals[order].astype(numpy.uint32)

                if palette_vals.size == 1:
                    # single-palette shortcut: header 0 (bits_per_value) with biome flag => 0x01
                    parts.append(b'\x01')
                    parts.append(struct.pack('<I', int(palette_vals[0])))
                else:
                    # map each cell value to palette index
                    mapping = {int(v): i for i, v in enumerate(palette_vals)}
                    indices_flat = numpy.fromiter((mapping[int(v)] for v in flat), dtype=numpy.uint32)
                    indices = indices_flat.reshape((16, 16, 16))
                    # use your encoder (keeps your packed format)
                    packed = _encode_packed_array(indices, min_bit_size=1, biome=True)
                    parts.append(packed)
                    parts.append(struct.pack('<I', len(palette_vals)))
                    parts.append(palette_vals.astype('<i4').tobytes())

            new_biome_bytes = b"".join(parts)
            new_chunk_raw = raw_height + new_biome_bytes
            self.level_db.put(key, new_chunk_raw)

        wx.MessageBox("Biome(s) updated")


    def chunk_biome_key(self, xc, xz):
        if 'minecraft:the_end' in self.canvas.dimension:
            dim = int(2).to_bytes(4, 'little', signed=True)
        elif 'minecraft:the_nether' in self.canvas.dimension:
            dim = int(1).to_bytes(4, 'little', signed=True)
        elif 'minecraft:overworld' in self.canvas.dimension:
            dim = b''

        return b''.join([b'', struct.pack('<ii', xc, xz), dim, b'+']) #43 or /x2b biome 3d

    def edit_biome_full_3d(self, biome):
        sub_layer = 3
        # x,y,z = x % 16, y % 16, z % 16
        palette, indices = biome.get(sub_layer)
        # numpy.set_printoptions(threshold=numpy.inf, linewidth=200)
        for x in palette:
            print(biome_id_to_name[x])



    def decode_full_3d_biomes(self, data: bytes) -> dict[int, tuple[numpy.ndarray, numpy.ndarray]]:
        """
        Decode Bedrock 3D biome data into a dict of (palette, indices).
        Each value is a tuple: (palette array, indices array).
        Keys are subchunk y-coordinates starting at -4.
        """
        biomes = {}
        cy = -4

        while data:
            data, bits_per_value, arr = _decode_packed_array(data)

            if bits_per_value == 0:
                value, data = struct.unpack("<I", data[:4])[0], data[4:]
                palette = numpy.array([value], dtype="<i4")
                indices = numpy.zeros((16, 16, 16), dtype="<i4")
                biomes[cy] = [palette, indices]

            elif bits_per_value > 0:

                palette_len, data = struct.unpack("<I", data[:4])[0], data[4:]
                palette = numpy.frombuffer(data[: 4 * palette_len], dtype="<i4").astype(numpy.uint32)
                data = data[4 * palette_len:]
                biomes[cy] = [palette, arr]

            cy += 1

        return biomes

    @staticmethod
    def encode_full_3d_biomes(biomes: dict[int, tuple[numpy.ndarray, numpy.ndarray]]) -> bytes:
        """
        Encode 3D biome data back into Bedrock raw format.
        Input must be (palette, indices) tuples as produced by full_3d_biomes.
        """
        out = []

        for cy in range(-4, 20):
            entry = biomes.get(cy)
            if entry is None:
                out.append(b'\xff')
                continue

            palette, indices = entry

            if len(palette) == 1:
                out.append(b"\x01")
                out.append(palette.astype("<i4").tobytes())
            else:
                packed = _encode_packed_array(indices, biome=True)
                out.append(packed)
                out.append(struct.pack("<I", len(palette)))
                out.append(palette.astype("<i4").tobytes())

        return b''.join(out)

    @property
    def level_db(self):
        level_wrapper = self.world.level_wrapper
        if hasattr(level_wrapper, "level_db"):
            return level_wrapper.level_db
        else:
            return level_wrapper._level_manager._db

export = dict(name="Full 3d BIOME", operation=BIOME) #By PremiereHell
