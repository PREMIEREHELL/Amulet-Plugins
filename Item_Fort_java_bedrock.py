
from amulet.api.selection import SelectionGroup
from amulet.api.level import BaseLevel
from amulet.api.data_types import Dimension
from amulet_map_editor.programs.edit.api.operations.errors import OperationError
from amulet.api.block import Block
from amulet.api.block_entity import BlockEntity
from amulet_nbt import *
import amulet_nbt
import json
import random
import os
from os import path
import sys

def create_all_items_in_boxes(
    world: BaseLevel, dimension: Dimension, selection: SelectionGroup, options: dict
):

    lPathN = -(len(str(os.path.realpath(__file__).split("\\")[-1:])) - 3)
    fileP = os.path.realpath(__file__)[:lPathN] + "\\itemdef.json"
    with open(fileP, "r") as fj:
        jdata = json.load(fj)
    print(jdata)
    pos = px, py, pz = selection.min_x, selection.min_y, selection.min_z
    cntslot = 0
    pxx = 0
    cnt_boxs = 0
    pyy = 0
    pzz = 0

    if world.level_wrapper.platform == "java":
        bp = "java"
        bv = (1, 17, 0)
        for k, v in jdata['Items'].items():
            if v.get('java') != "None":
                if cntslot == 0:
                    theNBT = TAG_Compound({
                        "isMovable": TAG_Byte(1),
                        "Findable": TAG_Byte(0),
                        # "CustomName": TAG_String("§l§bEverything"), #TODO ADD NAME FOR JAVA
                        "Items": TAG_List(),
                    })
                Slots = TAG_Compound({
                    "id": TAG_String("minecraft:" + v.get('java')),
                    "Count": TAG_Byte(64),
                    "Slot": TAG_Byte(cntslot)
                })
                print(v.get('jsnbt'))
                if v.get('jsnbt') != None:
                    data = v.get('jsnbt').replace("'", "\"")
                    nbt = amulet_nbt.from_snbt("{" + data + "}")
                    print(nbt, "nbt")
                    try:
                        Slots['tag'] = nbt['tag']
                    except:
                        Slots['Block'] = nbt['Block']
                    print(Slots)
                cntslot += 1
                theNBT["Items"].append(Slots)
            if cntslot > 26 or int(k) == len(jdata['Items']) - 1:
                blockEntity = BlockEntity("", "ShulkerBox", 0, 0, 0, NBTFile(theNBT))
                cnt_boxs += 1
                if cnt_boxs >= 16 and cnt_boxs <= 20:
                    block = Block("minecraft", "shulker_box", {"facing": TAG_String("east")})
                if cnt_boxs >= 11 and cnt_boxs <= 15:
                    block = Block("minecraft", "shulker_box", {"facing": TAG_String("north")})
                if cnt_boxs >= 6 and cnt_boxs <= 10:
                    block = Block("minecraft", "shulker_box", {"facing": TAG_String("west")})
                if cnt_boxs <= 5:
                    block = Block("minecraft", "shulker_box", {"facing": TAG_String("south")})

                world.set_version_block(
                    px + pxx, py + pyy, pz + pzz, dimension, (bp, bv), block, blockEntity
                )
                block, blockEntity = world.get_version_block(
                    px + pxx, py + pyy, pz + pzz, dimension, (bp, bv)
                )

                cntslot = 0
                if cnt_boxs <= 5:
                    pxx += 1
                # if cnt_boxs == 5:
                #     pzz += 1
                if cnt_boxs == 10:  # LEAVE A GAP
                    pzz += 1
                # if cnt_boxs == 15:
                #     pxx -= 1
                if cnt_boxs >= 5 and cnt_boxs < 11:
                    pzz += 1
                if cnt_boxs >= 10 and cnt_boxs < 16:
                    pxx -= 1
                if cnt_boxs >= 15 and cnt_boxs <= 20:
                    pzz -= 1
                if cnt_boxs >= 20:
                    pzz = 0
                    pxx = 0
                    pyy += 1
                    cnt_boxs = 0

    if world.level_wrapper.platform == "bedrock":
        bp = "bedrock"
        bv = (1, 17, 0)
        for k, v in jdata['Items'].items():
            if v.get('bedrock') != "None":
                if cntslot == 0:

                    theNBT = TAG_Compound({
                        "isMovable": TAG_Byte(1),
                        "Findable": TAG_Byte(0),
                        "CustomName": TAG_String("§l§bEverything"),
                        "Items": TAG_List(),
                    })
                Slots = TAG_Compound({
                    "Name": TAG_String("minecraft:" + v.get('bedrock')),
                    "Damage": TAG_Short(v.get('DV')),
                    "Count": TAG_Byte(64),
                    "Slot": TAG_Byte(cntslot)

                })
                print(v.get('bsnbt'))
                if v.get('bsnbt') != None:
                    data = v.get('bsnbt').replace("'", "\"")
                    nbt = amulet_nbt.from_snbt("{" + data + "}")
                    print(nbt, "nbt")
                    try:
                        Slots['tag'] = nbt['tag']
                    except:
                        Slots['Block'] = nbt['Block']
                    print(Slots)
                cntslot += 1

                theNBT["Items"].append(Slots)


            if cntslot > 26 or int(k) == len(jdata['Items']) - 1:
                block = Block("minecraft", "shulker_box")
                blockEntity = BlockEntity("", "ShulkerBox", 0, 0, 0, NBTFile(theNBT))
                cnt_boxs += 1

                if cnt_boxs >= 16 and cnt_boxs <= 20:
                    theNBT['facing'] = TAG_Byte(5)
                if cnt_boxs >= 11 and cnt_boxs <= 15:
                    theNBT['facing'] = TAG_Byte(2)
                if cnt_boxs >= 6 and cnt_boxs <= 10:
                    theNBT['facing'] = TAG_Byte(4)
                if cnt_boxs <= 5:
                    theNBT['facing'] = TAG_Byte(3)

                world.set_version_block(
                    px + pxx, py + pyy, pz + pzz, dimension, (bp, bv), block, blockEntity
                )
                block, blockEntity = world.get_version_block(
                    px + pxx, py + pyy, pz + pzz, dimension, (bp, bv)
                )

                cntslot = 0
                if cnt_boxs <= 5:
                    pxx += 1
                # if cnt_boxs == 5:
                #     pzz += 1
                if cnt_boxs == 10:  # LEAVE A GAP
                    pzz += 1
                # if cnt_boxs == 15:
                #     pxx -= 1
                if cnt_boxs >= 5 and cnt_boxs < 11:
                    pzz += 1
                if cnt_boxs >= 10 and cnt_boxs < 16:
                    pxx -= 1
                if cnt_boxs >= 15 and cnt_boxs <= 20:
                    pzz -= 1
                if cnt_boxs >= 20:
                    pzz = 0
                    pxx = 0
                    pyy += 1
                    cnt_boxs = 0

export = {
    "name": "#A Fort of all Items",  #by PremiereHell
    "operation": create_all_items_in_boxes,
}
