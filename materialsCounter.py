import struct
import collections
from typing import TYPE_CHECKING, Type, Any, Callable, Tuple,  BinaryIO, Optional
from amulet_map_editor.programs.edit.api.operations import DefaultOperationUI
from amulet_map_editor.programs.edit.api.behaviour import BlockSelectionBehaviour
import wx
import re
from amulet_map_editor.api.wx.ui.base_select import BaseSelect
if TYPE_CHECKING:
    from amulet.api.level import BaseLevel
    from amulet_map_editor.programs.edit.api.canvas import EditCanvas
class PluginClassName(wx.Panel, DefaultOperationUI):
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

        wx.Panel.__init__(self, parent)
        DefaultOperationUI.__init__(self, parent, canvas, world, options_path)
        self._sizer = wx.BoxSizer(wx.VERTICAL)
        self.text = wx.TextCtrl(self, style=wx.TE_MULTILINE, size=(280, 650), pos=(30,30))
        self.test = wx.Button(self, label="Get Materials count", pos=(0,0))
        self.test.Bind(wx.EVT_BUTTON, self._run_count)
        self._sizer.Add(self.test)
        self._sizer.Add(self.text)

    def _run_count(self, _):

        block_version = self.world.level_wrapper.version

        block_platform = "universal"

        matrials = collections.defaultdict(list)
        selection = self.canvas.selection.selection_group.selection_boxes
        text = ''
        print('ok')
        for g in selection:
            for b in g:
                name, ent = self.world.get_version_block(b[0],b[1],b[2],self.canvas.dimension, (block_platform, block_version))
                clean_name = str(name.properties.get('material')).replace('None', '')
                clean_name += str(name.properties.get('plant_type')).replace('None', '')
                if clean_name != '':
                    clean_name += ' '
                clean_name +=  name.base_name
                print(name.properties)
                # clean_name_t = name.replace("[material=\""," ").replace('",type="bottom"]','').replace('",type="top"]','')\
                #     .replace('[color="',' ').replace('"]', '').replace("[",' ').replace('"','').replace('east','')\
                #                  .replace('north','').replace('south','').replace('west','').replace('=','')\
                #                  .replace('true','').replace('false','').replace(',','').replace('universal_minecraft','')\
                #                    .replace('{','').replace('age','').replace('halflower','').replace('halfupper','').replace(' ','')\
                #                .replace('fallingflowinglevel','')+": "
                # clean_name = re.sub(r'[0-9]+', '', clean_name_t)
                #print(name)
                matrials[clean_name].append(clean_name)
        for x in matrials.keys():
            text += str(x)  +" " + str(len(matrials[x])) + "\n"

        self.text.SetValue(text)

    def bind_events(self):
        super().bind_events()
        self._selection.bind_events()
        self._selection.enable()

    def enable(self):
        self._selection = BlockSelectionBehaviour(self.canvas)
        self._selection.enable()
    pass


# simple export options.
export = dict(name="A Materials Counter", operation=PluginClassName) # by PremiereHell