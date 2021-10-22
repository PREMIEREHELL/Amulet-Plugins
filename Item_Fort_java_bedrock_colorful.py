
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
import random
def RandomShulkerBoxColorJava():
    rand = random.randint(0, 15)
    colorBoxs = [
"shulker_box",
"white_shulker_box",
"orange_shulker_box",
"magenta_shulker_box",
"light_blue_shulker_box",
"yellow_shulker_box",
"lime_shulker_box",
"pink_shulker_box",
"gray_shulker_box",
"light_gray_shulker_box",
"cyan_shulker_box",
"purple_shulker_box",
"blue_shulker_box",
"brown_shulker_box",
"green_shulker_box",
"red_shulker_box",
"black_shulker_box",
]
    return colorBoxs[rand]
def RandomShulkerBoxColorBedrock():
    rand = random.randint(0,15)
    colorBoxs = [
        " ",
"white",
"orange",
"magenta",
"light_blue",
"yellow",
"lime",
"pink",
"gray",
"light_gray",
"cyan",
"purple",
"blue",
"brown",
"green",
"red",
"black",

    ]

    return colorBoxs[rand]

def create_all_items_in_boxes(
    world: BaseLevel, dimension: Dimension, selection: SelectionGroup, options: dict
):

    # lPathN = -(len(str(os.path.realpath(__file__).split("\\")[-1:])) - 3)
    # fileP = os.path.realpath(__file__)[:lPathN] + "\\itemdef.json"
    fileP =  os.path.join(os.path.dirname(os.path.abspath(__file__))) + os.path.join("/itemdef.json")

    with open(fileP, "r") as fj:
        jdata = json.load(fj)

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

                if v.get('jsnbt') != None:
                    data = v.get('jsnbt').replace("'", "\"")
                    nbt = amulet_nbt.from_snbt("{" + data + "}")

                    try:
                        Slots['tag'] = nbt['tag']
                    except:
                        Slots['Block'] = nbt['Block']

                cntslot += 1
                theNBT["Items"].append(Slots)
            if cntslot > 26 or int(k) == len(jdata['Items']) - 1:
                blockEntity = BlockEntity("", "ShulkerBox", 0, 0, 0, NBTFile(theNBT))
                cnt_boxs += 1
                if 16 <= cnt_boxs <= 20:
                    block = Block("minecraft", RandomShulkerBoxColorJava(), {"facing": TAG_String("east"),})
                if 11 <= cnt_boxs <= 15:
                    block = Block("minecraft", RandomShulkerBoxColorJava(), {"facing": TAG_String("north")})
                if  6 <= cnt_boxs <= 10:
                    block = Block("minecraft", RandomShulkerBoxColorJava(), {"facing": TAG_String("west")})
                if cnt_boxs <= 5:
                    block = Block("minecraft", RandomShulkerBoxColorJava(), {"facing": TAG_String("south")})

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
                if 5 <= cnt_boxs < 11:
                    pzz += 1
                if  10 <= cnt_boxs < 16:
                    pxx -= 1
                if  15 <= cnt_boxs <= 20:
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
                 
                if v.get('bsnbt') != None:
                    data = v.get('bsnbt').replace("'", "\"")
                    nbt = amulet_nbt.from_snbt("{" + data + "}")

                    try:
                        Slots['tag'] = nbt['tag']
                    except:
                        Slots['Block'] = nbt['Block']

                cntslot += 1

                theNBT["Items"].append(Slots)


            if cntslot > 26 or int(k) == len(jdata['Items']) - 1:

                block = Block("minecraft", "shulker_box", {"color": TAG_String(RandomShulkerBoxColorBedrock())})
                blockEntity = BlockEntity("", "ShulkerBox", 0, 0, 0, NBTFile(theNBT))
                cnt_boxs += 1

                if  16 <= cnt_boxs <= 20:
                    theNBT['facing'] = TAG_Byte(5)
                if  11 <= cnt_boxs <= 15:
                    theNBT['facing'] = TAG_Byte(2)
                if  6 <= cnt_boxs <= 10:
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
                if 5 <= cnt_boxs < 11:
                    pzz += 1
                if 10 <= cnt_boxs < 16:
                    pxx -= 1
                if 15 <= cnt_boxs <= 20:
                    pzz -= 1
                if cnt_boxs >= 20:
                    pzz = 0
                    pxx = 0
                    pyy += 1
                    cnt_boxs = 0

export = {
    "name": "#A colorful Fort of all Items",  #by PremiereHell
    "operation": create_all_items_in_boxes,
}