import wx
import wx.richtext as rt
import sys
import os
import json
import base64
import io
import collections
import re
import numpy
from PIL import Image
from amulet_nbt import *
# from mutf8 import encode_java_mutf8, decode_java_mutf8
def encode_java_mutf8(s: str) -> bytes:
    """
    Encode a Python string to Java-style MUTF-8 bytes.
    Handles surrogate pairs like Java does.
    """
    out = bytearray()
    for c in s:
        code = ord(c)
        if 0x0001 <= code <= 0x007F:
            out.append(code)
        elif code == 0x0000:
            # Java encodes null as two bytes: 0xC0 0x80
            out.extend(b'\xC0\x80')
        elif code <= 0x07FF:
            out.append(0xC0 | ((code >> 6) & 0x1F))
            out.append(0x80 | (code & 0x3F))
        else:
            # Encode surrogate pair style
            # split into high and low surrogate if >0xFFFF
            if code > 0xFFFF:
                code -= 0x10000
                high = 0xD800 + (code >> 10)
                low  = 0xDC00 + (code & 0x3FF)
                out.extend([0xE0 | (high >> 12), 0x80 | ((high >> 6) & 0x3F), 0x80 | (high & 0x3F)])
                out.extend([0xE0 | (low >> 12), 0x80 | ((low >> 6) & 0x3F), 0x80 | (low & 0x3F)])
            else:
                out.extend([0xE0 | (code >> 12), 0x80 | ((code >> 6) & 0x3F), 0x80 | (code & 0x3F)])
    return bytes(out)

def decode_java_mutf8(b: bytes) -> str:
    """
    Decode Java MUTF-8 bytes back to Python string.
    Handles surrogate pairs.
    """
    import io
    stream = io.BytesIO(b)
    out = []
    while True:
        c = stream.read(1)
        if not c:
            break
        c = c[0]
        if c >> 7 == 0:
            out.append(chr(c))
        elif c >> 5 == 0b110:
            c2 = stream.read(1)[0]
            code = ((c & 0x1F) << 6) | (c2 & 0x3F)
            out.append(chr(code))
        elif c >> 4 == 0b1110:
            c2 = stream.read(1)[0]
            c3 = stream.read(1)[0]
            code = ((c & 0x0F) << 12) | ((c2 & 0x3F) << 6) | (c3 & 0x3F)
            if 0xD800 <= code <= 0xDBFF:
                # High surrogate, read next for low surrogate
                c4 = stream.read(1)[0]
                c5 = stream.read(1)[0]
                c6 = stream.read(1)[0]
                low = ((c4 & 0x0F) << 12) | ((c5 & 0x3F) << 6) | (c6 & 0x3F)
                code = 0x10000 + (((code - 0xD800) << 10) | (low - 0xDC00))
            out.append(chr(code))
        else:
            raise ValueError(f"Invalid MUTF-8 byte: {c:02x}")
    return "".join(out)
APPDATA = os.getenv('APPDATA')  # Java Minecraft uses %APPDATA%\.minecraft
WORLDS_DIR = os.path.join(APPDATA, ".minecraft", "saves")

EMOJI_JAVA = ('😀😃😄😁😆😅🤣😂🙂🙃😉😊😇🥰😍🤩😘😗☺😚😙😋😛😜🤪😝🤑🤗🤭🤫🤔🤐🤨😐😑😶😏😒🙄😬🤥😌😔😪😮💨'
              '🤤😴😷🤒🤕🤢🤮🤧🥵🥶😶🌫🥴😵💫😵🤯🤠🥳😎🤓🧐😕😟🙁☹😮😯😲😳🥺😦😧😨😰😥😢😭😱😖😣😞😓😩😫🥱'
              '😤😡😠🤬😈👿💀☠💩🤡👹👺👻👽👾🤖😺😸😹😻😼😽🙀😿😾🙈🙉🙊👋🤚🖐✋🖖👌🤏✌🤞🤟🤘🤙👈👉👆🖕👇☝👍👎✊'
              '👊🤛🤜👏🙌👐🤲🤝🙏✍💅🤳💪🦾🦿🦵🦶👂🦻👃🧠🦷🦴👀👁👅👄🫦💋👶🧒👦👧🧑👨👩🧔🧔🧔🧑🦰👨🦰'
              '👩🦰🧑🦱👨🦱👩🦱🧑🦳👨🦳👩🦳🧑🦲👨🦲👩🦲👱👱👱🧓👴👵🙍🙍🙍🙎🙎🙎🙅🙅🙅🙆🙆🙆💁💁'
              '💁🙋🙋🙋🧏🧏🧏🙇🙇🙇🤦🤦🤦🤷🤷🤷🧑⚕👨⚕👩⚕🧑🎓👨🎓👩🎓🧑🏫👨🏫👩🏫🧑⚖👨⚖👩'
              '⚖🧑🌾👨🌾👩🌾🧑🍳👨🍳👩🍳🧑🔧👨🔧👩🔧🧑🏭👨🏭👩🏭🧑💼👨💼👩💼🧑🔬👨🔬👩🔬🧑💻👨💻👩💻🧑🎤👨🎤👩'
              '🎤🧑🎨👨🎨👩🎨🧑✈👨👩🧑🚀👨👩🧑🚒👨🚒👩🚒👮👮👮🕵🕵🕵💂💂💂👷👷👷🤴👸👳👳'
              '👳👲🧕🤵🤵🤵👰👰👰🤰🤱👩🍼👨🍼🧑🍼👼🎅🤶🧑🎄🦸🦸🦸🦹🦹🦹🧙🧚🧚🧚🧛🧛🧛🧜♀♂'
              '🧜🧜🧝🧝🧝🧞🧞🧞🧟🧟🧟🧌💆💇💇🚶🧍🧎🧑🦯👨🦯👩🦯🧑🦼👨🦼👩🦼'
              '🧑🦽👨🦽👩🦽🏃🏃🏃💃🕺🕴👯👯👯🧖🧖🧖🧗🧗🧗🤺🏇⛷🏂🏄🏄🏄🚣🏊🏌'
              '⛹⛹⛹🏋🏋🏋🚴🚴🚴🚵🚵🚵🤸🤸🤸🤼🤼🤼🤽🤽🤽🤾🤾🤾🤹🤹🤹🧘🧘🧘🛀🛌🧑'
              '🤝🧑👭👫👬💏👩❤💋👨👨❤💋👨👩❤💋👩💑👩❤👨👨❤👨👩❤👩👪👨👩👦👨👩👧👨👩👧👦👨👩👦👦👨👩👧👧👨'
              '👨👦👨👨👧👨👨👧👦👨👨👦👦👨👨👧👧👩👩👦👩👩👧👩👩👧👦👩👩👦👦👩👩👧👧👨👦👨👦👦👨👧👨👧👦👨👧👧'
              '👩👦👩👦👦👩👧👩👧👦👩👧👧🗣👤👥👣🐵🐒🦍🦧🐶🐕🦮🐕🦺🐩🐺🦊🦝🐱🐈🐈⬛🦁🐯🐅🐆🐴🐎🦄🦓🦌🐮🐂'
              '🐃🐄🐷🐖🐗🐽🐏🐑🐐🐪🐫🦙🦒🐘🦏🦛🐭🐁🐀🐹🐰🐇🐿🦔🦇🐻🐻❄🐨🐼🦥🦦🦨🦘🦡🐾🦃🐔🐓🐣🐤🐥🐦🐧🐦⬛🕊'
              '🦅🦆🦢🦉🦩🦚🦜🥚🐸🐊🐢🦎🐍🐲🐉🦕🦖🐳🐋🐬🐟🐠🐡🦈🐙🦑🦀🦞🦐🦪🐚🐌🦋🐛🐜🐝🐞🦗🕷🕸🦂🦟🦠'
              '🍄💐💮🏵🌼🌻🌹🥀🌺🌷🌸🌱🏕🌲🌳🌰🌴🌵🎋🎍🌾🌿☘🍀🍁🍂🍃🌍🌎🌏🌑🌒🌓🌔🌕🌖🌗🌘🌙🌚🌛🌜☀🌝🌞🪐💫⭐'
              '🌟✨🌠☄🌌☁⛅⛈🌤🌥🌦🌧🌨🌩🌪🌫🌬🌀🌈🌂☂☔⛱⚡❄☃⛄🏔⛰🗻🌋🔥💧🌊💥💦💨🍇🍈🍉🍊🍋🍌🍍🥭🍎🍏🍐🍑'
              '🍒🍓🫐🥝🍅🫒🥥🥑🍆🥔🥕🌽🌶🥒🥬🥦🧄🧅🍄🥜🌰🍞🥐🥖🫓🥨🥯🥞🧇🧀🍖🍗🥩🥓🍔🍟🍕🌭🥪🌮🌯🥙🧆🥚🍳🥘🍲'
              '🫕🥣🥗🍿🧈🧂🥫🍱🍘🍙🍚🍛🍜🍝🍠🍢🍣🍤🍥🥮🍡🥟🥠🥡🍦🍧🍨🍩🍪🎂🍰🧁🥧🍫🍬🍭🍮🍯🍼🥛☕🍵🍶🍾🍷🍸🍹🍺🍻🥂'
              '🥃🥤🧃🧉🧊🥢🍽🍴🥄🔪⚽⚾🥎🏀🏐🏈🏉🎾🥏🎳🏏🏑🏒🥍🏓🏸🥊🥋🥅⛳⛸🎣🤿🎽🎿🛷🥌🎯🪀🪁🎱🎖🏆🏅🥇🥈🥉🏔⛰'
              '🌋🗻🏕🏖🏜🏝🏟🏛🏗🧱🏘🏚🏠🏡🏢🏣🏤🏥🏦🏨🏩🏪🏫🏬🏭🏯🏰💒🗼🗽⛪🕌🛕🕍⛩🕋⛲⛺🌁🌃🏙🌄🌅🌆🌇🌉'
              '🗾🏞🎠🎡🎢💈🎪🚂🚃🚄🚅🚆🚇🚈🚉🚊🚝🚞🚋🚌🚍🚎🚐🚑🚒🚓🚔🚕🚖🚗🚘🚙🚚🚛🚜🏎🏍🛵🦽🦼🛺🚲🛴🛹🚏🛣'
              '🛤🛢⛽🚨🚥🚦🛑🚧⚓⛵🛶🚤🛳⛴🛥🚢✈🛩🛫🛬🪂💺🚁🚟🚠🚡🛰🚀🛸🎆🎇🎑🗿🛎🧳⌛⏳⌚⏰⏱⏲🕰🌡🗺🧭🎃🎄🧨🎈🎉'
              '🎊🎎🪭🎏🎐🎀🎁🎗🎟🎫🔮🧿🎮🕹🎰🎲♟🧩🧸🖼🎨🧵🧶👓🕶🥽🥼🦺👔👕👖🧣🧤🧥🧦👗👘🥻🩱🩲🩳👙👚👛👜👝🛍🎒'
              '👞👟🥾🥿👠👡🩰👢👑👒🎩🎓🧢⛑📿💄💍💎📢📣📯🎙🎚🎛🎤🎧📻🎷🎸🎹🎺🎻🪕🥁📱📲☎📞📟📠🔋🔌💻🖥🖨'
              '⌨🖱🖲💽💾💿📀🧮🎥🎞📽🎬📺📷📸📹📼🔍🔎🕯💡🔦🏮🪔📔📕📖📗📘📙📚📓📒📃📜📄📰🗞📑🔖🏷💰💴💵💶💷💸💳🪪🧾'
              '✉💌📧🧧📨📩📤📥📦📫📪📬📭📮🗳✏✒🖋🖊🖌🖍📝💼📁📂🗂📅📆🗒🗓📇📈📉📊📋📌📍📎🖇📏📐✂🗃🗄🗑🔒🔓🔏🔐🔑'
              '🗝🔨🪓⛏⚒🛠🗡⚔💣🔫🏹🛡🔧🔩⚙🗜⚖🦯🔗⛓🧰🧲⚗🧪🧫🧬🔬🔭📡💉🩸💊🩹🩺🚪🛏🛋🪑🚽🚿🛁🧼'
              '🪒🧴🧷🧹🧺🧻🧽🧯🛒🚬⚰⚱🏺🕳💘💝💖💗💓💞💕💟❣💔❤🧡💛💚💙💜🤎🖤🤍❤🔥❤🩹💯♨💢💬👁🗨🗨'
              '🗯💭💤🌐♠♥♦♣🃏🀄🎴🎭🔇🔈🔉🔊🔔🔕🎼🎵🎶💹🏧🚮🚰♿🚹🚺🚻🚼🚾🛂🛃🛄🛅⚠🚸⛔🚫🚳🚭🚯🚱🚷📵🔞☢☣'
              '⬆↗➡↘⬇↙⬅↖↕↔↩↪⤴⤵🔃🔄🔙🔚🔛🔜🔝🛐⚛🕉✡☸☯✝☦☪☮🕎🔯♈♉♊♋♌♍♎♏♐♑♒♓⛎'
              '🔀🔁🔂▶⏩⏭⏯◀⏪⏮🔼⏫🔽⏬⏸⏹⏺⏏🎦🔅🔆📶📳📴⚧✖➕➖➗♾‼⁉❓❔❕❗〰💱💲⚕♻⚜🔱📛🔰⭕✅☑✔'
              '❌❎➰➿〽✳✴❇©®™#*0123456789🔟🔠🔡🔢🔣🔤🅰🆎🅱🆑🆒🆓ℹ🆔Ⓜ🆕🆖🅾🆗🅿🆘🆙🆚🈁'
              '🈂🈷🈶🈯🉐🈹🈚🈲🉑🈸🈴🈳㊗㊙🈺🈵🔴🟠🟡🟢🔵🟣🟤⚫⚪🟥🟧🟨🟩🟦🟪🟫⬛⬜◼◻◾◽▪▫🔶🔷🔸🔹🔺🔻💠🔘🔳🔲'
              '🕛🕧🕐🕜🕑🕝🕒🕞🕓🕟🕔🕠🕕🕡🕖🕢🕗🕣🕘🕤🕙🕥🕚🕦☹☻☺ツ☚☛☜☝☞☟✍✎✌❤❥♥♡❣♨☠☮☯☪☀☣☢☭♏♒♈☂☃☁♔♕'
              '♚۩♛✿❀ ❃❂❁♠♤♣♧⚜™®©₪★☆✮✯✪✣✤✥✲❈☄✦❉✧♱♰๑☿⋄⋅⋆⋇☼*✖✗✘✕✓✔ღ✄✂☎☏✆✉♪♩♫♬♭❝❞‘ﾟ.･‖﹉﹊﹍﹎︱︳︴﹏﹋﹌▁┠┨┯'
              '┷┏┓﹃﹄┗┛┳⊥╝ ╚╔╗╬═╓╩▪▫□〓≡▬▂▃▄■▀▢▅▆▇▌▐█▓▒░┇┅✚▣▧▨▤▥▦▩回ஐ⋖⋗▲△▼♢♦▽Δ►◄⇨◈◆◇◊⋘⋙⋚⋛⋜⋝⋞⋟⋠⋡⋢⋣⋤⋥⋦⋧⋨ ⋩⋪⋫⋬⋭⋈⋉'
              '⋊⋋⋌⋍⋎⋏⋐⋑⋒⋓⋔⋕∵∴⋮⋯⋰⋱⋲⋳⋴⋵⋶⋷⋸⋹⋺⋻⋼≈⋽⋾⋿⌀⌁ϟ⌂⌃⌄⌅⌆⌇⌈⌉⌊⌋⊮⊯⊰⊱⊲⊳⊴⊵【】⊶⊷⊸⊹⊺⊻⊼⊽⊾⊿⋀⋁⋂⋃ ╯ぃ↔↕↑↓→←↘↙➹ψ♆◠◡┌┐└┘∟「'
              '」◯●◕◐◑○◔⊙◎㊚㊛¤㊣∞☾☽◘◙の➀➁➂➃➄➅➆➇➈➉'
              '∧∠∨∩⊂⊃∪∀ΞΓɐəɘεβɟɥɯɔи๏ɹʁяʌʍλчΣΠ℘ℑ￡あℜℵηαʊїз¢℃№¿¡ƸӜƷξЖЗж½⅓'
              '⅔¼¾⅛⅜⅝⅞℅')
WINDOW = {}
horn_actions = [
    "ponder", "sing", "seek", "feel",
    "admire", "call", "yearn", "dream"
]
bed_icons = {
    "minecraft:white_bed": "bed",
    "minecraft:light_gray_bed": "bed:8",
    "minecraft:gray_bed": "bed:7",
    "minecraft:black_bed": "bed:15",
    "minecraft:brown_bed": "bed:12",
    "minecraft:red_bed": "bed:14",
    "minecraft:orange_bed": "bed:1",
    "minecraft:yellow_bed": "bed:4",
    "minecraft:lime_bed": "bed:5",
    "minecraft:green_bed": "bed:13",
    "minecraft:cyan_bed": "bed:9",
    "minecraft:light_blue_bed": "bed:3",
    "minecraft:blue_bed": "bed:11",
    "minecraft:purple_bed": "bed:10",
    "minecraft:magenta_bed": "bed:2",
    "minecraft:pink_bed": "bed:6"
}
potion_to_java = {
    "potion": "minecraft:water",
    "potion:1": "minecraft:mundane",
    "potion:2": "minecraft:mundane",
    "potion:3": "minecraft:thick",
    "potion:4": "minecraft:awkward",
    "potion:5": "minecraft:night_vision",
    "potion:6": "minecraft:long_night_vision",
    "potion:7": "minecraft:invisibility",
    "potion:8": "minecraft:long_invisibility",
    "potion:9": "minecraft:leaping",
    "potion:10": "minecraft:long_leaping",
    "potion:11": "minecraft:strong_leaping",
    "potion:12": "minecraft:fire_resistance",
    "potion:13": "minecraft:long_fire_resistance",
    "potion:14": "minecraft:swiftness",
    "potion:15": "minecraft:long_swiftness",
    "potion:16": "minecraft:strong_swiftness",
    "potion:17": "minecraft:slowness",
    "potion:18": "minecraft:long_slowness",
    "potion:19": "minecraft:water_breathing",
    "potion:20": "minecraft:long_water_breathing",
    "potion:21": "minecraft:healing",
    "potion:22": "minecraft:strong_healing",
    "potion:23": "minecraft:harming",
    "potion:24": "minecraft:strong_harming",
    "potion:25": "minecraft:poison",
    "potion:26": "minecraft:long_poison",
    "potion:27": "minecraft:strong_poison",
    "potion:28": "minecraft:regeneration",
    "potion:29": "minecraft:long_regeneration",
    "potion:30": "minecraft:strong_regeneration",
    "potion:31": "minecraft:strength",
    "potion:32": "minecraft:long_strength",
    "potion:33": "minecraft:strong_strength",
    "potion:34": "minecraft:weakness",
    "potion:35": "minecraft:long_weakness",
    "potion:36": "minecraft:wither",
    "potion:37": "minecraft:turtle_master",
    "potion:38": "minecraft:long_turtle_master",
    "potion:39": "minecraft:strong_turtle_master",
    "potion:40": "minecraft:slow_falling",
    "potion:41": "minecraft:long_slow_falling",
    "potion:42": "minecraft:slowness",       # Slowness IV requires custom effect
    "potion:43": "minecraft:wind_charge",    # Custom potion
    "potion:44": "minecraft:weaving",       # Custom potion
    "potion:45": "minecraft:ozzing",        # Custom potion
    "potion:46": "minecraft:infesting",     # Custom potion
    "potion:99": "minecraft:luck",
}
arrow_potions = {
    "arrow:6":  "minecraft:night_vision",
    "arrow:7":  "minecraft:long_night_vision",
    "arrow:8":  "minecraft:invisibility",
    "arrow:9":  "minecraft:long_invisibility",
    "arrow:10": "minecraft:leaping",
    "arrow:11": "minecraft:long_leaping",
    "arrow:12": "minecraft:strong_leaping",
    "arrow:13": "minecraft:fire_resistance",
    "arrow:14": "minecraft:long_fire_resistance",
    "arrow:15": "minecraft:swiftness",
    "arrow:16": "minecraft:long_swiftness",
    "arrow:17": "minecraft:strong_swiftness",
    "arrow:18": "minecraft:slowness",
    "arrow:19": "minecraft:long_slowness",
    "arrow:20": "minecraft:water_breathing",
    "arrow:21": "minecraft:long_water_breathing",
    "arrow:22": "minecraft:healing",
    "arrow:23": "minecraft:strong_healing",
    "arrow:24": "minecraft:harming",
    "arrow:25": "minecraft:strong_harming",
    "arrow:26": "minecraft:poison",
    "arrow:27": "minecraft:long_poison",
    "arrow:28": "minecraft:strong_poison",
    "arrow:29": "minecraft:regeneration",
    "arrow:30": "minecraft:long_regeneration",
    "arrow:31": "minecraft:strong_regeneration",
    "arrow:32": "minecraft:strength",
    "arrow:33": "minecraft:long_strength",
    "arrow:34": "minecraft:strong_strength",
    "arrow:35": "minecraft:weakness",
    "arrow:36": "minecraft:long_weakness",
    "arrow:37": "minecraft:decay",               # wither/decay (Bedrock name)
    "arrow:38": "minecraft:turtle_master",
    "arrow:39": "minecraft:long_turtle_master",
    "arrow:40": "minecraft:strong_turtle_master",
    "arrow:41": "minecraft:slow_falling",
    "arrow:42": "minecraft:long_slow_falling",
    "arrow:43": "minecraft:strong_slowness",     # Slowness IV / amplified
    "arrow:44": "minecraft:wind_charge",         # custom/experimental
    "arrow:45": "minecraft:weaving",             # custom/experimental
    "arrow:46": "minecraft:oozing",              # custom/experimental
    "arrow:47": "minecraft:infesting",           # custom/experimental
    "arrow:99": "minecraft:luck",
    "arrow:98": "minecraft:mundane"
}
ominous_bottles = {
    'ominous_bottle:1': 1,
'ominous_bottle:2':2,
'ominous_bottle:3':3,
'ominous_bottle:4':4,
}
enchanted_books = {
    "enchanted_book:0": "minecraft:aqua_affinity_1",
    "enchanted_book:1": "minecraft:bane_of_arthropods_1",
    "enchanted_book:2": "minecraft:bane_of_arthropods_2",
    "enchanted_book:3": "minecraft:bane_of_arthropods_3",
    "enchanted_book:4": "minecraft:bane_of_arthropods_4",
    "enchanted_book:5": "minecraft:bane_of_arthropods_5",
    "enchanted_book:6": "minecraft:blast_protection_1",
    "enchanted_book:7": "minecraft:blast_protection_2",
    "enchanted_book:8": "minecraft:blast_protection_3",
    "enchanted_book:9": "minecraft:blast_protection_4",
    "enchanted_book:10": "minecraft:channeling_1",
    "enchanted_book:11": "minecraft:depth_strider_1",
    "enchanted_book:12": "minecraft:depth_strider_2",
    "enchanted_book:13": "minecraft:depth_strider_3",
    "enchanted_book:14": "minecraft:efficiency_1",
    "enchanted_book:15": "minecraft:efficiency_2",
    "enchanted_book:16": "minecraft:efficiency_3",
    "enchanted_book:17": "minecraft:efficiency_4",
    "enchanted_book:18": "minecraft:efficiency_5",
    "enchanted_book:19": "minecraft:feather_falling_1",
    "enchanted_book:20": "minecraft:feather_falling_2",
    "enchanted_book:21": "minecraft:feather_falling_3",
    "enchanted_book:22": "minecraft:feather_falling_4",
    "enchanted_book:23": "minecraft:fire_aspect_1",
    "enchanted_book:24": "minecraft:fire_aspect_2",
    "enchanted_book:25": "minecraft:fire_protection_1",
    "enchanted_book:26": "minecraft:fire_protection_2",
    "enchanted_book:27": "minecraft:fire_protection_3",
    "enchanted_book:28": "minecraft:fire_protection_4",
    "enchanted_book:29": "minecraft:flame_1",
    "enchanted_book:30": "minecraft:fortune_1",
    "enchanted_book:31": "minecraft:fortune_2",
    "enchanted_book:32": "minecraft:fortune_3",
    "enchanted_book:33": "minecraft:frost_walker_1",
    "enchanted_book:34": "minecraft:frost_walker_2",
    "enchanted_book:35": "minecraft:impaling_1",
    "enchanted_book:36": "minecraft:impaling_2",
    "enchanted_book:37": "minecraft:impaling_3",
    "enchanted_book:38": "minecraft:impaling_4",
    "enchanted_book:39": "minecraft:impaling_5",
    "enchanted_book:40": "minecraft:infinity",
    "enchanted_book:41": "minecraft:knockback_1",
    "enchanted_book:42": "minecraft:knockback_2",
    "enchanted_book:43": "minecraft:looting_1",
    "enchanted_book:44": "minecraft:looting_2",
    "enchanted_book:45": "minecraft:looting_3",
    "enchanted_book:46": "minecraft:loyalty_1",
    "enchanted_book:47": "minecraft:loyalty_2",
    "enchanted_book:48": "minecraft:loyalty_3",
    "enchanted_book:49": "minecraft:luck_of_the_sea_1",
    "enchanted_book:50": "minecraft:luck_of_the_sea_2",
    "enchanted_book:51": "minecraft:luck_of_the_sea_3",
    "enchanted_book:52": "minecraft:lure_1",
    "enchanted_book:53": "minecraft:lure_2",
    "enchanted_book:54": "minecraft:lure_3",
    "enchanted_book:55": "minecraft:mending_1",
    "enchanted_book:56": "minecraft:multishot_1",
    "enchanted_book:57": "minecraft:piercing_1",
    "enchanted_book:58": "minecraft:piercing_2",
    "enchanted_book:59": "minecraft:piercing_3",
    "enchanted_book:60": "minecraft:piercing_4",
    "enchanted_book:61": "minecraft:power_1",
    "enchanted_book:62": "minecraft:power_2",
    "enchanted_book:63": "minecraft:power_3",
    "enchanted_book:64": "minecraft:power_4",
    "enchanted_book:65": "minecraft:power_5",
    "enchanted_book:66": "minecraft:projectile_protection_1",
    "enchanted_book:67": "minecraft:projectile_protection_2",
    "enchanted_book:68": "minecraft:projectile_protection_3",
    "enchanted_book:69": "minecraft:projectile_protection_4",
    "enchanted_book:70": "minecraft:protection_1",
    "enchanted_book:71": "minecraft:protection_2",
    "enchanted_book:72": "minecraft:protection_3",
    "enchanted_book:73": "minecraft:protection_4",
    "enchanted_book:74": "minecraft:punch_1",
    "enchanted_book:75": "minecraft:punch_2",
    "enchanted_book:76": "minecraft:quick_charge_1",
    "enchanted_book:77": "minecraft:quick_charge_2",
    "enchanted_book:78": "minecraft:quick_charge_3",
    "enchanted_book:79": "minecraft:respiration_1",
    "enchanted_book:80": "minecraft:respiration_2",
    "enchanted_book:81": "minecraft:respiration_3",
    "enchanted_book:82": "minecraft:riptide_1",
    "enchanted_book:83": "minecraft:riptide_2",
    "enchanted_book:84": "minecraft:riptide_3",
    "enchanted_book:85": "minecraft:sharpness_1",
    "enchanted_book:86": "minecraft:sharpness_2",
    "enchanted_book:87": "minecraft:sharpness_3",
    "enchanted_book:88": "minecraft:sharpness_4",
    "enchanted_book:89": "minecraft:sharpness_5",
    "enchanted_book:90": "minecraft:silk_touch",
    "enchanted_book:91": "minecraft:smite_1",
    "enchanted_book:92": "minecraft:smite_2",
    "enchanted_book:93": "minecraft:smite_3",
    "enchanted_book:94": "minecraft:smite_4",
    "enchanted_book:95": "minecraft:smite_5",
    "enchanted_book:96": "minecraft:thorns_1",
    "enchanted_book:97": "minecraft:thorns_2",
    "enchanted_book:98": "minecraft:thorns_3",
    "enchanted_book:99": "minecraft:unbreaking_1",
    "enchanted_book:100": "minecraft:unbreaking_2",
    "enchanted_book:101": "minecraft:unbreaking_3",
    "enchanted_book:102": "minecraft:soul_speed_1",
    "enchanted_book:103": "minecraft:soul_speed_2",
    "enchanted_book:104": "minecraft:soul_speed_3",
    "enchanted_book:105": "minecraft:binding_curse_1",
    "enchanted_book:106": "minecraft:vanishing_curse_1",
    "enchanted_book:107": "minecraft:swift_sneak_1",
    "enchanted_book:108": "minecraft:swift_sneak_2",
    "enchanted_book:109": "minecraft:swift_sneak_3",
    "enchanted_book:110": "minecraft:density_1",
    "enchanted_book:111": "minecraft:density_2",
    "enchanted_book:112": "minecraft:density_3",
    "enchanted_book:113": "minecraft:density_4",
    "enchanted_book:114": "minecraft:density_5",
    "enchanted_book:115": "minecraft:wind_burst_1",
    "enchanted_book:116": "minecraft:wind_burst_2",
    "enchanted_book:117": "minecraft:wind_burst_3",
    "enchanted_book:118": "minecraft:breach_1",
    "enchanted_book:119": "minecraft:breach_2",
    "enchanted_book:120": "minecraft:breach_3",
    "enchanted_book:121": "minecraft:breach_4",
    "enchanted_book:122": "minecraft:sweeping_edge_1",
    "enchanted_book:123": "minecraft:sweeping_edge_2",
    "enchanted_book:124": "minecraft:sweeping_edge_3",
}
firework_colors = {
    "firework_rocket:0": 1973019,    # Black
    "firework_rocket:8": 11743532,   # Red
    "firework_rocket:7": 3887386,    # Green
    "firework_rocket:15": 5320730,   # Brown
    "firework_rocket:12": 2437522,   # Blue
    "firework_rocket:14": 8073150,   # Purple
    "firework_rocket:1": 2651799,    # Cyan
    "firework_rocket:4": 11250603,   # Light Gray
    "firework_rocket:5": 4408131,    # Gray
    "firework_rocket:13": 14188952,  # Pink
    "firework_rocket:9": 4312372,    # Lime
    "firework_rocket:3": 14602026,   # Yellow
    "firework_rocket:11": 6719955,   # Light Blue
    "firework_rocket:10": 12801229,  # Magenta
    "firework_rocket:2": 15435844,   # Orange
    "firework_rocket:6": 15790320    # White
}
firework_star_colors = {
    "firework_star:0": 1973019,    # Black
    "firework_star:8": 11743532,   # Gray
    "firework_star:7": 3887386,    # Light Gray
    "firework_star:15": 15790320,  # White
    "firework_star:12": 6719955,   # Light Blue
    "firework_star:14": 15435844,  # Orange
    "firework_star:1": 11743532,   # Red
    "firework_star:4": 2437522,    # Blue
    "firework_star:5": 8073150,    # Purple
    "firework_star:13": 12801229,  # Magenta
    "firework_star:9": 14188952,   # Pink
    "firework_star:3": 5320730,    # Brown
    "firework_star:11": 14602026,  # Yellow
    "firework_star:10": 4312372,   # Lime
    "firework_star:2": 3887386,    # Green
    "firework_star:6": 2651799     # Cyan
}
goat_horn_components = {
    i: CompoundTag({"minecraft:instrument": StringTag(f"minecraft:{action}_goat_horn")})
    for i, action in enumerate(horn_actions)
}

max_levels_java = {
    "minecraft:aqua_affinity": 1,
    "minecraft:bane_of_arthropods": 5,
    "minecraft:blast_protection": 4,
    "minecraft:channeling": 1,
    "minecraft:binding_curse": 1,
    "minecraft:vanishing_curse": 1,
    "minecraft:depth_strider": 3,
    "minecraft:efficiency": 5,
    "minecraft:feather_falling": 4,
    "minecraft:fire_aspect": 2,
    "minecraft:fire_protection": 4,
    "minecraft:flame": 1,
    "minecraft:fortune": 3,
    "minecraft:frost_walker": 2,
    "minecraft:impaling": 5,
    "minecraft:infinity": 1,
    "minecraft:knockback": 2,
    "minecraft:looting": 3,
    "minecraft:loyalty": 3,
    "minecraft:luck_of_the_sea": 1,
    "minecraft:lure": 1,
    "minecraft:mending": 1,
    "minecraft:multishot": 1,
    "minecraft:piercing": 1,
    "minecraft:power": 5,
    "minecraft:projectile_protection": 4,
    "minecraft:protection": 4,
    "minecraft:punch": 2,
    "minecraft:quick_charge": 3,
    "minecraft:respiration": 3,
    "minecraft:riptide": 3,
    "minecraft:sharpness": 5,
    "minecraft:silk_touch": 1,
    "minecraft:smite": 5,
    "minecraft:soul_speed": 3,
    "minecraft:thorns": 3,
    "minecraft:unbreaking": 3,
    "minecraft:swift_sneak": 3,
    "minecraft:breach": 4,
    "minecraft:density": 5,
    "minecraft:wind_burst": 3
}
java_enchant_map = {
    "minecraft:protection": "Protection",
    "minecraft:fire_protection": "Fire Protection",
    "minecraft:feather_falling": "Feather Falling",
    "minecraft:blast_protection": "Blast Protection",
    "minecraft:projectile_protection": "Projectile Protection",
    "minecraft:thorns": "Thorns",
    "minecraft:respiration": "Respiration",
    "minecraft:depth_strider": "Depth Strider",
    "minecraft:aqua_affinity": "Aqua Affinity",
    "minecraft:sharpness": "Sharpness",
    "minecraft:smite": "Smite",
    "minecraft:bane_of_arthropods": "Bane of Arthropods",
    "minecraft:knockback": "Knockback",
    "minecraft:fire_aspect": "Fire Aspect",
    "minecraft:looting": "Looting",
    "minecraft:efficiency": "Efficiency",
    "minecraft:silk_touch": "Silk Touch",
    "minecraft:unbreaking": "Unbreaking",
    "minecraft:fortune": "Fortune",
    "minecraft:power": "Power",
    "minecraft:punch": "Punch",
    "minecraft:flame": "Flame",
    "minecraft:infinity": "Infinity",
    "minecraft:luck_of_the_sea": "Luck of the Sea",
    "minecraft:lure": "Lure",
    "minecraft:frost_walker": "Frost Walker",
    "minecraft:mending": "Mending",
    "minecraft:binding_curse": "Curse of Binding",
    "minecraft:vanishing_curse": "Curse of Vanishing",
    "minecraft:impaling": "Impaling",
    "minecraft:riptide": "Riptide",
    "minecraft:loyalty": "Loyalty",
    "minecraft:channeling": "Channeling",
    "minecraft:multishot": "Multishot",
    "minecraft:piercing": "Piercing",
    "minecraft:quick_charge": "Quick Charge",
    "minecraft:soul_speed": "Soul Speed",
    "minecraft:swift_sneak": "Swift Sneak",
    "minecraft:wind_burst": "Wind Burst",
    "minecraft:density": "Density",
    "minecraft:breach": "Breach",
}
valid_enchants_java = {
    "helmet": [
        "minecraft:protection",
        "minecraft:fire_protection",
        "minecraft:blast_protection",
        "minecraft:projectile_protection",
        "minecraft:thorns",
        "minecraft:respiration",
        "minecraft:aqua_affinity",
        "minecraft:unbreaking",
        "minecraft:mending",
        "minecraft:binding_curse",
        "minecraft:vanishing_curse"
    ],
    "chestplate": [
        "minecraft:protection",
        "minecraft:fire_protection",
        "minecraft:blast_protection",
        "minecraft:projectile_protection",
        "minecraft:thorns",
        "minecraft:unbreaking",
        "minecraft:mending",
        "minecraft:binding_curse",
        "minecraft:vanishing_curse"
    ],
    "elytra": [
        "minecraft:unbreaking",
        "minecraft:mending",
        "minecraft:binding_curse",
        "minecraft:vanishing_curse"
    ],
    "leggings": [
        "minecraft:protection",
        "minecraft:fire_protection",
        "minecraft:blast_protection",
        "minecraft:projectile_protection",
        "minecraft:thorns",
        "minecraft:swift_sneak",
        "minecraft:unbreaking",
        "minecraft:mending",
        "minecraft:binding_curse",
        "minecraft:vanishing_curse"
    ],
    "boots": [
        "minecraft:protection",
        "minecraft:fire_protection",
        "minecraft:feather_falling",
        "minecraft:blast_protection",
        "minecraft:projectile_protection",
        "minecraft:thorns",
        "minecraft:depth_strider",
        "minecraft:frost_walker",
        "minecraft:soul_speed",
        "minecraft:unbreaking",
        "minecraft:mending",
        "minecraft:binding_curse",
        "minecraft:vanishing_curse"
    ],
    "sword": [
        "minecraft:sharpness",
        "minecraft:smite",
        "minecraft:bane_of_arthropods",
        "minecraft:knockback",
        "minecraft:fire_aspect",
        "minecraft:looting",
        "minecraft:unbreaking",
        "minecraft:mending",
        "minecraft:binding_curse",
        "minecraft:vanishing_curse"
    ],
    "axe": [
        "minecraft:sharpness",
        "minecraft:smite",
        "minecraft:bane_of_arthropods",
        "minecraft:fire_aspect",
        "minecraft:looting",
        "minecraft:efficiency",
        "minecraft:silk_touch",
        "minecraft:unbreaking",
        "minecraft:fortune",
        "minecraft:mending",
        "minecraft:binding_curse",
        "minecraft:vanishing_curse"
    ],
    "pickaxe": [
        "minecraft:efficiency",
        "minecraft:silk_touch",
        "minecraft:unbreaking",
        "minecraft:fortune",
        "minecraft:mending",
        "minecraft:binding_curse",
        "minecraft:vanishing_curse"
    ],
    "shovel": [
        "minecraft:efficiency",
        "minecraft:silk_touch",
        "minecraft:unbreaking",
        "minecraft:fortune",
        "minecraft:mending",
        "minecraft:binding_curse",
        "minecraft:vanishing_curse"
    ],
    "hoe": [
        "minecraft:efficiency",
        "minecraft:silk_touch",
        "minecraft:unbreaking",
        "minecraft:mending",
        "minecraft:binding_curse",
        "minecraft:vanishing_curse"
    ],
    "bow": [
        "minecraft:power",
        "minecraft:punch",
        "minecraft:flame",
        "minecraft:infinity",
        "minecraft:unbreaking",
        "minecraft:mending",
        "minecraft:binding_curse",
        "minecraft:vanishing_curse"
    ],
    "crossbow": [
        "minecraft:power",
        "minecraft:multishot",
        "minecraft:piercing",
        "minecraft:quick_charge",
        "minecraft:unbreaking",
        "minecraft:mending",
        "minecraft:binding_curse",
        "minecraft:vanishing_curse"
    ],
    "trident": [
        "minecraft:fire_aspect",
        "minecraft:silk_touch",
        "minecraft:unbreaking",
        "minecraft:mending",
        "minecraft:impaling",
        "minecraft:riptide",
        "minecraft:loyalty",
        "minecraft:channeling",
        "minecraft:binding_curse",
        "minecraft:vanishing_curse"
    ],
    "fishing_rod": [
        "minecraft:silk_touch",
        "minecraft:unbreaking",
        "minecraft:luck_of_the_sea",
        "minecraft:lure",
        "minecraft:mending",
        "minecraft:binding_curse",
        "minecraft:vanishing_curse"
    ],
    "shears": [
        "minecraft:silk_touch",
        "minecraft:unbreaking",
        "minecraft:mending",
        "minecraft:binding_curse",
        "minecraft:vanishing_curse"
    ],
    "mace": [
        "minecraft:unbreaking",
        "minecraft:mending",
        "minecraft:wind_burst",
        "minecraft:density",
        "minecraft:breach",
        "minecraft:binding_curse",
        "minecraft:vanishing_curse"
    ],
    "enchanted_book": list(java_enchant_map.keys()),
    "shield": [
        "minecraft:unbreaking",
        "minecraft:mending",
        "minecraft:binding_curse",
        "minecraft:vanishing_curse"
    ]
}

def get_item_type(item_id):
    """Returns the type of item in the slot based on its ID or tag."""
    types = [
        "sword", "pickaxe", "axe", "shovel", "hoe",
        "helmet", "chestplate", "leggings", "boots",
        "bow", "crossbow", "trident", "elytra",
        "fishing_rod", "mace", "enchanted_book", "shield"
    ]
    return next((t for t in types if t in item_id), "Not in list")

CONTAINERS_TYPE_2_PATH = {
    "bundle": "minecraft:bundle_contents",
    "shulker": "minecraft:container",
    "dispenser": "minecraft:container",
    "chest": "minecraft:container",
    "barrel": "minecraft:container",
}

class IconResources:
    _instance = None  # Class-level instance reference

    def __new__(cls, *args, **kwargs):
        """
        The `__new__` method is responsible for creating and returning the instance.
        It ensures that only one instance of IconResources is ever created.
        """
        if not cls._instance:
            cls._instance = super(IconResources, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self):
        if not hasattr(self, '_initialized'):
            def get_resource_path(filename):
                if hasattr(sys, "_MEIPASS"):
                    # Running in PyInstaller bundle
                    return os.path.join(sys._MEIPASS, filename)
                else:
                    current_dir = os.path.dirname(os.path.abspath(__file__))
                    file_path = os.path.join(current_dir, 'item_atlas.json')
                    return file_path

            # Check to avoid reinitialization
            self._initialized = True
            self.catalog_window = None
            # Initialize the current directory and file path
            # current_dir = os.path.dirname(os.path.abspath(__file__))
            # file_path = os.path.join(current_dir, 'item_atlas.json')
            #
            # # Load the icon data from the file
            # with open(file_path, 'r') as file:
            #     self.data = json.load(file)
            json_path = get_resource_path("data/item_atlas.json")

            with open(json_path, "r") as f:
                self.data = json.load(f)
            self.items_id = []  # List to store item ids
            self.icon_cache = {}  # Cache for item icons
            self.scaled_cache = {}  # Cache for scaled item icons
            self.scaled_cache32 = {}
            self.icon_list_window = None  # Placeholder for the icon list window (not currently used)

            # Load the icon cache from the data
            self.load_icon_cache(self.data)

            # Remove the 'atlas' key from the data (unnecessary)
            self.data.pop('atlas', None)


    @property
    def get_items_id(self):
        """Returns the list of item IDs."""
        return self.items_id

    @property
    def get_json_data(self):
        """Returns the JSON data for the items."""
        return self.data

    @property
    def get_icon_cache(self):
        """Returns the icon cache dictionary."""
        return self.icon_cache

    @property
    def get_scaled_cache(self):
        """Returns the icon cache dictionary."""
        return self.scaled_cache

    @property
    def get_scaled_cache32(self):
        """Returns the icon cache dictionary."""
        return self.scaled_cache32

    def load_icon_cache(self, atlas):
        """Loads icons from the item atlas."""

        def load_base64_imagefile(data):
            """Decodes and loads the base64-encoded image from the atlas data."""
            atlas_data = base64.b64decode(data['atlas'])
            buffer = io.BytesIO(atlas_data)
            atlas_image = wx.Image()
            atlas_image.LoadFile(buffer, wx.BITMAP_TYPE_PNG)
            return atlas_image

        # Load the atlas image (either from base64 or direct file path)
        if isinstance(atlas, dict):
            atlas_image = load_base64_imagefile(atlas)
        else:
            atlas_image = wx.Image(atlas, wx.BITMAP_TYPE_PNG)

        # Extract icons from the atlas and add to the cache
        for item_id, data in self.data.items():
            if "icon_position" in data:
                x, y = data["icon_position"]["x"], data["icon_position"]["y"]
                icon_image = atlas_image.GetSubImage(wx.Rect(x, y, 32, 32))
                self.icon_cache[item_id] = icon_image
                self.items_id.append(item_id)

        target_width = 64
        target_height = 64

        for item_id, img in self.icon_cache.items():
            scaled_img = img.Scale(target_width, target_height, wx.IMAGE_QUALITY_HIGH)
            bmp = scaled_img.ConvertToBitmap()
            self.scaled_cache[item_id] = bmp

    def get_bitmap(self, bedrock_id):
        return self.scaled_cache.get(bedrock_id)

    def get(self, item_id, default=None):
        """Returns the data for a given item ID, or a default value if not found."""
        return self.data.get(item_id, default)

    def open_catalog(self, parent, data):
        """Open the catalog window, ensuring only one instance exists."""
        if WINDOW.get('catalog', None) is None:  # If window is not created yet
            WINDOW['catalog'] = IconListCtrl(parent, "Catalog", data, slot)
        else:
            self.catalog_window.update_data(data)
            self.catalog_window.update_slot(slot)
            # Calculate position to place the catalog window next to the parent window
        mouse_x, mouse_y = wx.GetMousePosition()

        # Optionally, add some offset to the mouse position so that the window doesn't overlap the mouse
        offset_x = 10  # Horizontal offset from the mouse position
        offset_y = 10  # Vertical offset from the mouse position

        # Set the position of the catalog window to be near the mouse position
        WINDOW['catalog'].Move(mouse_x + offset_x, mouse_y + offset_y)

        # Ensure the window stays within the screen bounds (on the same monitor)
        screen_width, screen_height = wx.GetDisplaySize()  # Get screen size (monitor resolution)

        # Check if the catalog window would go off the screen on the right or bottom
        catalog_x, catalog_y = WINDOW['catalog'].GetPosition()
        catalog_width, catalog_height = WINDOW['catalog'].GetSize()
        if catalog_x + catalog_width > screen_width:
            # If it's too far to the right, position it to the left of the mouse
            WINDOW['catalog'].Move(mouse_x - catalog_width - offset_x, mouse_y + offset_y)
        if catalog_y + catalog_height > screen_height:
            # If it's too far down, position it above the mouse
            WINDOW['catalog'].Move(mouse_x + offset_x, mouse_y - catalog_height - offset_y)
        WINDOW['catalog'].Show()  # Show the window
        WINDOW['catalog'].Raise()  # Bring it to the front

    def close_catalog(self):
        """Close (hide) the catalog window."""
        if WINDOW.get('catalog', None):
            WINDOW['catalog'].Hide()  # Hide the window, but don't destroy it

    def toggle_catalog_h(self, parent, data):
        if WINDOW.get('catalog', None) is None:
            WINDOW['catalog'](parent, data, slot)

            WINDOW['catalog'].Hide()

    def toggle_catalog(self, parent, data):
        """Show the catalog window if hidden, hide if shown, create if missing."""

        # Create the window if it doesn't exist
        if WINDOW.get('catalog') is None:
            WINDOW['catalog'] = IconListCtrl(parent, "Catalog", data)
        # else:
        #     # Update data/slot if needed
        #     WINDOW['catalog'].update_data(data)


        # Position the catalog near the mouse
        mouse_x, mouse_y = wx.GetMousePosition()
        offset_x, offset_y = 10, 10
        WINDOW['catalog'].Move(mouse_x + offset_x, mouse_y + offset_y)

        # Keep window within screen bounds
        screen_width, screen_height = wx.GetDisplaySize()
        x, y = WINDOW['catalog'].GetPosition()
        w, h = WINDOW['catalog'].GetSize()
        if x + w > screen_width:
            x = screen_width - w
        if y + h > screen_height:
            y = screen_height - h
        WINDOW['catalog'].Move(max(x, 0), max(y, 0))

        # Toggle visibility
        if WINDOW['catalog'].IsShown():
            WINDOW['catalog'].Hide()
        else:
            WINDOW['catalog'].Show()
            WINDOW['catalog'].Raise()

class IconListCtrl(wx.Frame):
    def __init__(self, parent, title, data):
        super().__init__(parent, title=title, size=(1110, 800), style=wx.DEFAULT_FRAME_STYLE | wx.STAY_ON_TOP)
        self.parent = parent
        self.bedrock_id = None

        self.resources = data
        self.font = wx.Font(11, wx.FONTFAMILY_ROMAN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        self.SetFont(self.font)
        self.bmp = 0
        self.icon_size = 64
        self.panel = wx.Panel(self)
        self.list_ctrl = wx.ListCtrl(self.panel, style=wx.LC_ICON)
        self.image_list = wx.ImageList(self.icon_size, self.icon_size)
        self.list_ctrl.AssignImageList(self.image_list, wx.IMAGE_LIST_NORMAL)

        self.list_ctrl.SetForegroundColour((0, 255, 0))
        self.list_ctrl.SetBackgroundColour((88, 88, 88))

        self.drag_image =None
        self.dragging = False
        self.index_to_bedrock = {}
        self.all_items = []

        panel_sizer = wx.BoxSizer(wx.VERTICAL)
        panel_horz = wx.BoxSizer(wx.HORIZONTAL)
        self.button = wx.Button(self.panel, size=(100, 30), label="Filter")
        self.filterstring = wx.TextCtrl(self.panel, size=(100, 30), style=wx.TE_PROCESS_ENTER)

        self.list_ctrl.Bind(wx.EVT_LEFT_DOWN, self.OnMouseDown)
        self.list_ctrl.Bind(wx.EVT_MOTION, self.OnMouseMove)
        self.list_ctrl.Bind(wx.EVT_LEFT_UP, self.OnMouseUp)


        self.button.Bind(wx.EVT_BUTTON, self.filter_string)
        self.filterstring.Bind(wx.EVT_TEXT_ENTER, self.filter_string)

        panel_horz.Add(self.button)
        panel_horz.Add(self.filterstring)
        panel_sizer.Add(panel_horz)
        panel_sizer.Add(self.list_ctrl, 3, flag=wx.EXPAND)
        self.panel.SetSizerAndFit(panel_sizer)

        self.Bind(wx.EVT_CLOSE, self.on_close)
        self.item_index = -1
        self.load_all_items()
        self.Layout()

    def OnMouseMove(self, event):
        if hasattr(self, "drag_image") and event.Dragging() and event.LeftIsDown():
            self.drag_image.Move(event.GetPosition())

    def OnMouseDown(self, event):
        pos = event.GetPosition()
        index = self.list_ctrl.HitTest(pos)[0]


        # Convert to screen coordinates
        screen_pos = event.GetEventObject().ClientToScreen(pos)
        if index == wx.NOT_FOUND:
            return

        bedrock_id = self.index_to_bedrock.get(index)
        self.item_id = bedrock_id
        if not bedrock_id:
            return

        image_index = self.index_to_icon_index.get(index)
        if image_index is None:
            return

        bmp = self.image_list.GetBitmap(image_index)

        self.dragged_index = index
        self.drag_image = wx.DragImage(bmp)
        self.drag_image.BeginDrag((30, 30), self.list_ctrl, fullScreen=True)
        self.drag_image.Move(screen_pos)
        self.drag_image.Show()

    def OnMouseUp(self, evt):

        if hasattr(self, "drag_image"):
            self.drag_image.Hide()

        if self.list_ctrl.HasCapture():
            try:
                self.list_ctrl.ReleaseMouse()
            except Exception:
                pass  # swallow any error

        if hasattr(self, "drag_image"):
            try:
                self.drag_image.EndDrag()
            except Exception:
                pass
            finally:
                del self.drag_image
        button = evt.GetEventObject()
        pos = evt.GetPosition()

        screen_pos = button.ClientToScreen(pos)

        # --- NEW: find widget under mouse ---
        hovered_window = wx.FindWindowAtPoint(screen_pos)
        if isinstance(hovered_window, wx.Button):
            screen_pt = self.list_ctrl.ClientToScreen(evt.GetPosition())
            if hovered_window.GetScreenRect().Contains(screen_pt):
                icon_index = self.index_to_icon_index.get(self.dragged_index)
                if icon_index is not None:
                    bmp = self.image_list.GetBitmap(icon_index)

                if hovered_window:
                    hovered_window.SetBitmap(bmp)
                    display_name = self.resources.data[self.item_id].get('display_name', self.item_id)
                    hovered_window.SetToolTip(wx.ToolTip(display_name))
                    if evt.ShiftDown():
                        hovered_window.GetParent().set_count(64)
                    else:
                        hovered_window.GetParent().set_count(1)
                    hovered_window.GetParent().set_item_id(self.item_id.split(':')[0])
                    hovered_window.GetParent().set_components(None)
                    if 'goat_horn' in self.item_id:
                        if ':' not in self.item_id:
                            hovered_window.GetParent().set_components(goat_horn_components[0])
                        else:
                            hovered_window.GetParent().set_components(goat_horn_components[int(self.item_id.split(":")[1])])
                    elif 'enchanted_book' in self.item_id:
                        enchant = enchanted_books[self.item_id][:-2]
                        lvl = enchanted_books[self.item_id][-1:]
                        print(enchant, lvl)
                        hovered_window.GetParent().set_components(
                                CompoundTag({"minecraft:stored_enchantments": CompoundTag({enchant: IntTag(int(lvl))})}))
                    elif 'firework_rocket' in self.item_id:
                        color = firework_colors[self.item_id]
                        hovered_window.GetParent().set_components(
                            CompoundTag( {"minecraft:fireworks":
                                CompoundTag({'explosions': ListTag([CompoundTag(
                                    {'colors': IntArrayTag([color]),
                                     'fade_colors': IntArrayTag([]),
                                     'shape': StringTag("small_ball"),
                                     'has_trail': ByteTag(0), 'has_twinkle':
                                         ByteTag(0)})], 10), 'flight_duration': ByteTag(1)})}))
                    elif 'firework_star' in self.item_id:
                        color = firework_star_colors[self.item_id] # replace for lookup
                        hovered_window.GetParent().set_components(
                            CompoundTag({'minecraft:firework_explosion':
                                CompoundTag({'has_trail': ByteTag(0), 'shape': StringTag("small_ball"),
                                             'colors': ListTag([IntTag(color)]), 'has_twinkle': ByteTag(0)})}))
                    elif 'potion' in self.item_id:
                        effect = potion_to_java[
                            self.item_id.replace("lingering_", "").replace("splash_", "")]  # replace for lookup
                        hovered_window.GetParent().set_components(
                            CompoundTag({'minecraft:potion_contents': CompoundTag({'potion': StringTag(effect)})}))
                    elif 'arrow' in self.item_id:
                        print(self.item_id)
                        effect = arrow_potions.get(self.item_id, None)  # replace for lookup
                        if effect:
                            hovered_window.GetParent().set_components(
                                CompoundTag({'minecraft:potion_contents': CompoundTag({'potion': StringTag(effect)})}))
                            hovered_window.GetParent().set_item_id('tipped_arrow')

        if hasattr(self, "dragged_index"):
            del self.dragged_index
        if hasattr(self, "dragged_id"):
            del self.dragged_id

        # Here, simulate a successful drop by directly handling the position

    def on_close(self, event):
        self.HideWithEffect(effect=wx.SHOW_EFFECT_BLEND)

    # def update_data(self, data):
    #     self.data = data
    #
    # def update_slot(self, slot):
    #     self.inv_slot = slot[1]
    #     self.key_slot = slot

    def load_all_items(self):
        self.all_items.clear()
        self.image_list.RemoveAll()
        self.list_ctrl.DeleteAllItems()

        scaled_cache = self.resources.get_scaled_cache  # Cache shortcut
        json_data = self.resources.get_json_data

        for bedrock_id, info in json_data.items():
            if bedrock_id == 'banner':
                continue

            display_name = info.get('display_name', '')
            bmp = scaled_cache.get(bedrock_id)
            if bmp:
                icon_index = self.image_list.Add(bmp)
                self.all_items.append((bedrock_id, display_name, icon_index))

        self.show_filtered_items()

    def show_filtered_items(self, filter_text=''):
        self.list_ctrl.DeleteAllItems()
        self.index_to_bedrock.clear()
        self.index_to_icon_index = {}  # new dict for image indexes
        filter_text = filter_text.lower()

        for bedrock_id, display_name, icon_index in self.all_items:
            if not filter_text or filter_text in display_name.lower():
                list_index = self.list_ctrl.InsertItem(self.list_ctrl.GetItemCount(), display_name, icon_index)
                self.index_to_bedrock[list_index] = bedrock_id
                self.index_to_icon_index[list_index] = icon_index

    def filter_string(self, _):
        filter_val = self.filterstring.GetValue()
        self.show_filtered_items(filter_val)

    def create_catalog_menu(self):
        for category, item_range in categories.items():
            menu_item = wx.MenuItem(self.catalog_menu, wx.ID_ANY, category)
            self.catalog_menu.Append(menu_item)
            self.Bind(wx.EVT_MENU, self.create_filter_callback(category, item_range), menu_item)

    def create_filter_callback(self, category, item_range):
        def filter_items(event):
            if category == "All":
                self.show_filtered_items('')
            else:
                valid_keys = [key for i, key in enumerate(self.data.resources.get_json_data.keys()) if i in item_range]
                self.show_filtered_items_for_keys(valid_keys)
        return filter_items

    def show_filtered_items_for_keys(self, allowed_keys):
        self.list_ctrl.DeleteAllItems()
        self.index_to_bedrock.clear()
        for bedrock_id, display_name, icon_index in self.all_items:
            if bedrock_id in allowed_keys:
                index = self.list_ctrl.InsertItem(self.list_ctrl.GetItemCount(), display_name, icon_index)
                self.index_to_bedrock[index] = bedrock_id

    def handel_components_name_value(self, value):
        print(goat_horn_components[value])


categories = {
    "Weapons & Combat": {
        "Weapons": [919, 920, 921, 922, 923, 924, 925],
        "Arrows": [958, 959, 960, 961, 962, 963, 964, 965, 966, 967, 968, 969, 970, 971, 972, 973, 974, 975, 976, 977, 978, 979, 980, 981, 982, 983, 984, 985, 986, 987, 988, 989, 990, 991, 992, 993, 994, 995, 996, 997, 998, 999, 1000, 1001, 1002, 1003],
        "Tools": [926, 927, 928, 929, 930, 931, 932, 933, 934, 935, 936, 937, 938, 939, 940, 941, 942, 943, 944, 945, 946, 947, 948, 949, 950, 951, 952, 953],
        "Armor": [891, 892, 893, 894, 895, 896, 897, 898, 899, 900, 901, 902, 903, 904, 905, 906, 907, 908, 909, 910, 911, 912, 913, 914, 915, 916, 917, 918, 1082],
        "Horse_Armor": [1076, 1077, 1078, 1079, 1080],
    },
    "Building Blocks": {
        "Planks": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 12],
        "Walls": [13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38],
        "Fences": [39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51],
        "Fence_Gates": [53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63],
        "Stairs": [64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121],
        "Doors": [122, 123, 124, 125, 126, 127, 128, 129, 130, 131, 132, 133, 134, 135, 136, 137, 138, 139, 140, 141, 142],
        "Trapdoors": [143, 144, 145, 146, 147, 148, 149, 150, 151, 152, 153, 154, 155, 156, 157, 158, 159, 160, 161, 162, 163],
        "Glass": [173, 190, 1085, 1236, 1838],
        "Stained_Glass": [174, 175, 176, 177, 178, 179, 180, 181, 182, 183, 184, 185, 186, 187, 188, 189, 1836],
        "Glass_Panes": [192, 193, 194, 195, 196, 197, 198, 199, 200, 201, 202, 203, 204, 205, 206, 207, 1837, 1839],
        "Wool": [373, 374, 375, 376, 377, 378, 379, 380, 381, 382, 383, 384, 385, 386, 387, 388],
        "Carpets": [389, 390, 391, 392, 393, 394, 395, 396, 397, 398, 399, 400, 401, 402, 403, 404, 713, 715],
        "Concrete": [421, 422, 423, 424, 425, 426, 427, 428, 429, 430, 431, 432, 433, 434, 435, 436],
        "Concrete_Powder": [405, 406, 407, 408, 409, 410, 411, 412, 413, 414, 415, 416, 417, 418, 419, 420],
        "Terracotta": [438, 439, 440, 441, 442, 443, 444, 445, 446, 447, 448, 449, 450, 451, 452, 453, 454, 455, 456, 457, 458, 459, 460, 461, 462, 463, 464, 465, 466, 467, 468, 469],
        "Bricks": [272, 273, 274, 275, 277, 278, 279, 284, 285, 286, 289, 352, 357, 365, 366, 367, 369, 370, 473, 767, 768, 769, 770, 1467],
        "Blackstone": [280, 281, 514, 521, 1673, 1690],
        "Basalt": [517, 524, 525],
        "Tuff": [288, 516, 523],
        "Copper_Blocks": [303, 304, 305, 306, 348],
        "Amethyst_Blocks": [728, 1469],
        "Prismarine": [356, 358, 1470],
        "Nether_Bricks": [368],
        "Nylium": [477, 478],
    },
    "Natural Blocks": {
        "Logs": [530, 531, 532, 533, 534, 535, 536, 537, 538, 539, 540, 541, 542, 543, 544, 545, 546, 547, 548, 549, 550, 551, 570, 571, 572, 573, 750, 1859, 1874],
        "Wood": [552, 554, 556, 558, 560, 562, 564, 566, 568],
        "Stripped_Wood": [553, 555, 557, 559, 561, 563, 565, 567, 569],
        "Leaves": [576, 577, 578, 579, 580, 581, 582, 583, 584, 585, 586],
        "Saplings": [587, 588, 589, 590, 591, 592, 594, 595],
        "Mushroom_Blocks": [748, 749],
        "Ores": [491, 492, 493, 494, 495, 496, 497, 498, 499, 500, 502, 503, 504, 505, 506, 507, 508, 509, 1856],
        "Raw_Blocks": [210, 301, 302, 343, 344, 345, 346, 347, 349, 350, 351, 354, 360, 361, 362, 363, 364, 371, 470, 474, 475, 481, 574, 575, 612, 711, 714, 716, 722, 865, 874, 875, 876, 877, 878, 879, 880, 881, 882, 883, 1447, 1657, 1820, 1824, 1825, 1880],
    },
    "Redstone": {
        "Redstone_Components": [1650, 1651, 1654, 1658, 1659, 1660, 1661, 1662, 1663, 1664, 1665, 1666, 1667, 1668, 1669, 1670, 1671, 1672, 1675, 1676, 1677, 1678, 1679, 1680, 1681, 1682, 1683, 1684, 1685, 1686, 1687, 1688, 1689, 1691, 1693, 1694, 1695, 1696, 1697, 1699, 1700, 1815, 1871, 1872, 1873, 1883],
        "Lamps": [1386, 1855],
    },
    "Farming": {
        "Crops": [597, 598, 599, 600, 601, 603, 604, 605, 606, 607, 608, 613, 614, 617, 618, 619, 694, 1014, 1016, 1018, 1022, 1864, 1865, 1866],
        "Food": [610, 611, 1012, 1013, 1015, 1019],
        "Animal_Products": [752, 753, 772, 773, 774, 780, 781, 782, 783, 784, 785, 786, 787, 788, 789, 790, 791, 792, 793, 794, 795, 796, 797, 798, 799, 800, 801, 802, 803, 804, 805, 806, 807, 808, 809, 810, 811, 812, 813, 814, 815, 816, 817, 818, 819, 820, 821, 822, 823, 824, 825, 826, 827, 828, 829, 830, 831, 832, 833, 834, 835, 836, 837, 838, 839, 840, 841, 842, 843, 844, 845, 846, 847, 848, 849, 850, 851, 852, 853, 854, 855, 856, 857, 858, 859, 860, 1005, 1006, 1007, 1008, 1382, 1862],
    },
    "Mob Drops": {
        "Monster_Drops": [639, 649, 1021, 1032, 1033, 1034, 1035, 1036, 1037, 1038, 1039, 1381, 1436, 1437, 1438, 1439, 1440, 1441, 1442, 1443, 1471, 1473, 1474, 1475, 1484, 1485, 1492, 1493, 1495, 1498],
        "Heads": [1429, 1430, 1431, 1432, 1433, 1434, 1435],
    },
    "Fireworks": {
        "Fireworks": [1773, 1774, 1775, 1776, 1777, 1778, 1779, 1780, 1781, 1782, 1783, 1784, 1785, 1786, 1787, 1788, 1789],
        "Firework_Stars": [1790, 1791, 1792, 1793, 1794, 1795, 1796, 1797, 1798, 1799, 1800, 1801, 1802, 1803, 1804, 1805],
    },
    "Containers": {
        "Shulker_Boxes": [1334, 1335, 1336, 1337, 1338, 1339, 1340, 1341, 1342, 1343, 1344, 1345, 1346, 1347, 1348, 1349, 1350],
        "Bundles": [1059, 1060, 1061, 1062, 1063, 1064, 1065, 1066, 1067, 1068, 1069, 1070, 1071, 1072, 1073, 1074, 1075],
        "Chests": [1322, 1323, 1324, 1325, 1326, 1327, 1328, 1329, 1330, 1331, 1332, 1653],
        "Barrel": [1333],
    },
    "Potions": {
        "Potions_Regular": [1087, 1088, 1089, 1090, 1091, 1092, 1093, 1094, 1095, 1096, 1097, 1098, 1099, 1100, 1101, 1102, 1103, 1104, 1105, 1106, 1107, 1108, 1109, 1110, 1111, 1112, 1113, 1114, 1115, 1116, 1117, 1118, 1119, 1120, 1121, 1122, 1123, 1124, 1125, 1126, 1127, 1128, 1129, 1130, 1131, 1132, 1133, 1134],
        "Potions_Splash": [1135, 1136, 1137, 1138, 1139, 1140, 1141, 1142, 1143, 1144, 1145, 1146, 1147, 1148, 1149, 1150, 1151, 1152, 1153, 1154, 1155, 1156, 1157, 1158, 1159, 1160, 1161, 1162, 1163, 1164, 1165, 1166, 1167, 1168, 1169, 1170, 1171, 1172, 1173, 1174, 1175, 1176, 1177, 1178, 1179, 1180, 1181, 1182],
        "Potions_Lingering": [1183, 1184, 1185, 1186, 1187, 1188, 1189, 1190, 1191, 1192, 1193, 1194, 1195, 1196, 1197, 1198, 1199, 1200, 1201, 1202, 1203, 1204, 1205, 1206, 1207, 1208, 1209, 1210, 1211, 1212, 1213, 1214, 1215, 1216, 1217, 1218, 1219, 1220, 1221, 1222, 1223, 1224, 1225, 1226, 1227, 1228, 1229, 1230],
    },
    "Miscellaneous": {
        "Dyes": [676, 677, 678, 679, 680, 681, 682, 683, 684, 685, 686, 687, 688, 689, 690, 691],
        "Buckets": [1419, 1420, 1421, 1422, 1423, 1424, 1425, 1426, 1427, 1428],
        "Music_Discs": [1362, 1363, 1364, 1365, 1366, 1367, 1368, 1369, 1370, 1371, 1372, 1373, 1374, 1375, 1376, 1377, 1378, 1379, 1380],
        "Boats": [1628, 1629, 1630, 1631, 1632, 1633, 1634, 1635, 1636, 1637, 1638, 1639, 1640, 1641, 1642, 1643, 1644, 1645, 1646, 1647],
        "Beds": [863, 1239, 1240, 1241, 1242, 1243, 1244, 1245, 1246, 1247, 1248, 1249, 1250, 1251, 1252, 1253, 1254, 1829, 1842],
        "Signs": [1388, 1389, 1390, 1391, 1392, 1393, 1394, 1395, 1396, 1397, 1398, 1399, 1885],
        "Hanging_Signs": [1400, 1401, 1402, 1403, 1404, 1405, 1406, 1407, 1408, 1409, 1410, 1411],
        "Banners": [1704, 1705, 1706, 1707, 1708, 1709, 1710, 1711, 1712, 1713, 1714, 1715, 1716, 1717, 1718, 1719, 1720, 1721, 1722, 1723, 1724, 1725, 1726, 1727, 1728, 1729, 1730],
        "Spawners": [760, 761],
        "Coral": [630, 631, 632, 633, 634, 640, 641, 642, 643, 644],
        "Dead_Coral": [635, 636, 637, 638, 645, 646, 647, 648],
        "Enchanted_Books": [1503, 1504, 1505, 1506, 1507, 1508, 1509, 1510, 1511, 1512, 1513, 1514, 1515, 1516, 1517, 1518, 1519, 1520, 1521, 1522, 1523, 1524, 1525, 1526, 1527, 1528, 1529, 1530, 1531, 1532, 1533, 1534, 1535, 1536, 1537, 1538, 1539, 1540, 1541, 1542, 1543, 1544, 1545, 1546, 1547, 1548, 1549, 1550, 1551, 1552, 1553, 1554, 1555, 1556, 1557, 1558, 1559, 1560, 1561, 1562, 1563, 1564, 1565, 1566, 1567, 1568, 1569, 1570, 1571, 1572, 1573, 1574, 1575, 1576, 1577, 1578, 1579, 1580, 1581, 1582, 1583, 1584, 1585, 1586, 1587, 1588, 1589, 1590, 1591, 1592, 1593, 1594, 1595, 1596, 1597, 1598, 1599, 1600, 1601, 1602, 1603, 1604, 1605, 1606, 1607, 1608, 1609, 1610, 1611, 1612, 1613, 1614, 1615, 1616, 1617, 1618, 1619, 1620, 1621, 1622, 1623, 1624, 1625, 1626, 1627],
    },
}
MC_COLORS = [
    (249, 255, 254),  # White
    (249, 128, 29),  # Orange
    (199, 78, 189),  # Magenta
    (58, 179, 218),  # Light Blue
    (254, 216, 61),  # Yellow
    (128, 199, 31),  # Lime
    (243, 139, 170),  # Pink
    (71, 79, 82),  # Gray
    (157, 157, 151),  # Light Gray
    (22, 156, 156),  # Cyan
    (137, 50, 184),  # Purple
    (60, 68, 170),  # Blue
    (131, 84, 50),  # Brown
    (94, 124, 22),  # Green
    (176, 46, 38),  # Red
    (29, 29, 33)  # Black
]
COLOR_NAMES = [
    "White", "Orange", "Magenta", "Light Blue",
    "Yellow", "Lime", "Pink", "Gray",
    "Light Gray", "Cyan", "Purple", "Blue",
    "Brown", "Green", "Red", "Black"
]
BEDROCK_PATTERN_TO_JAVA = {
    "bs": "stripe_bottom",  # Base
    "ts": "stripe_top",  # Chief
    "ls": "stripe_left",  # Pale Dexter
    "rs": "stripe_right",  # Pale Sinister
    "cs": "stripe_center",  # Pale
    "ms": "stripe_middle",  # Fess
    "ss": "small_stripes",  # Paly
    "sc": "straight_cross",  # Cross
    "drs": "diagonal_right",  # Per Bend
    "ld": "diagonal_up_left",  # Per Bend Inverted
    "dls": "diagonal_left",  # Per Bend Sinister
    "rud": "diagonal_up_right",  # Per Bend Sinister Inverted
    "bt": "triangle_bottom",  # Chevron
    "tt": "triangle_top",  # Inverted Chevron
    "bts": "triangles_bottom",  # Base Indented
    "tts": "triangles_top",  # Chief Indented
    "bo": "border",  # Bordure
    "cbo": "curly_border",  # Bordure Indented
    "bl": "square_bottom_left",  # Base Dexter Canton
    "br": "square_bottom_right",  # Base Sinister Canton
    "tl": "square_top_left",  # Chief Dexter Canton
    "tr": "square_top_right",  # Chief Sinister Canton
    "hh": "half_horizontal",  # Per Fess
    "hhb": "half_horizontal_bottom",  # Per Fess Inverted
    "vh": "half_vertical",  # Per Pale
    "vhr": "half_vertical_right",  # Per Pale Inverted
    "gra": "gradient",  # Gradient
    "gru": "gradient_up",  # Base Gradient
    "bri": "bricks",  # Field Masoned
    "mc": "circle",  # Roundel
    "mr": "rhombus",  # Lozenge
    "cr": "cross",  # Saltire
    "flo": "flower",  # Flower Charge
    "cre": "creeper",  # Creeper Charge
    "sku": "skull",  # Skull Charge
    "glb": "globe",  # Globe
    "moj": "mojang",  # Thing
    "pig": "piglin",  # Snout
    "flw": "flow",  # Flow
    "gus": "guster",  # Guster
}
IMAGE_COUNT = 44
ORIGINAL_WIDTH = 880 // IMAGE_COUNT
ORIGINAL_HEIGHT = 40
PATTERN_WIDTH = 30
PATTERN_HEIGHT = 50
PREVIEW_WIDTH = 100
PREVIEW_HEIGHT = 200
BANNER = {}
# MC_COLORS = list(reversed(MC_COLORS))
# COLOR_NAMES = list(reversed(COLOR_NAMES))
PATTERN_KEY_TO_NAME = {
    0: ("base", "Base 1"),
    1: ("base", "Base 2"),
    2: ("bo", "border"),  # Bordure
    3: ("bri", "bricks"),  # Field Masoned
    4: ("mc", "circle"),  # Roundel
    5: ("cre", "creeper"),  # Creeper Charge
    6: ("cr", "cross"),  # Saltire
    7: ("cbo", "curly_border"),  # Bordure Indented
    8: ("ld", "diagonal_up_left"),  # Per Bend Inverted
    9: ("rud", "diagonal_up_right"),  # Per Bend Sinister Inverted
    10: ("flo", "flower"),  # Flower Charge
    11: ("gra", "gradient"),  # Gradient
    12: ("hh", "half_horizontal"),  # Per Fess
    13: ("vh", "half_vertical"),  # Per Pale
    14: ("moj", "mojang"),  # Thing / White Thing
    15: ("mr", "rhombus"),  # Lozenge
    16: ("sku", "skull"),  # Skull Charge
    17: ("ss", "small_stripes"),  # Paly
    18: ("bl", "square_bottom_left"),  # Base Dexter Canton
    19: ("br", "square_bottom_right"),  # Base Sinister Canton
    20: ("tl", "square_top_left"),  # Chief Dexter Canton
    21: ("tr", "square_top_right"),  # Chief Sinister Canton
    22: ("sc", "straight_cross"),  # Cross
    23: ("bs", "stripe_bottom"),  # Bass Fess / Base
    24: ("cs", "stripe_center"),  # Pale
    25: ("dls", "diagonal_left"),  # Bend Sinister
    26: ("drs", "diagonal_right"),  # Bend
    27: ("ls", "stripe_left"),  # Pale Dexter
    28: ("ms", "stripe_middle"),  # Fess
    29: ("rs", "stripe_right"),  # Pale Sinister
    30: ("ts", "stripe_top"),  # Chief Fess
    31: ("bts", "triangles_bottom"),  # Base Indented
    32: ("tts", "triangles_top"),  # Chief Indented
    33: ("bt", "triangle_bottom"),  # Chevron
    34: ("tt", "triangle_top"),  # Inverted Chevron
    35: ("lud", "per_bend_sinister"),  # Per Bend Sinister
    36: ("rd", "per_bend"),  # Per Bend
    37: ("gru", "gradient_up"),  # Base Gradient
    38: ("hhb", "half_horizontal_bottom"),  # Per Fess Inverted
    39: ("vhr", "half_vertical_right"),  # Per Pale Inverted
    40: ("glb", "globe"),  # Globe
    41: ("pig", "piglin"),  # Snout
    42: ("flw", "flow"),  # Flow
    43: ("gus", "guster"),  # Guster
}
class BannerSelector(wx.Frame):
    def __init__(self, parent, components):
        super().__init__(None, title="Banner Selector", size=(545, 560),style=wx.DEFAULT_FRAME_STYLE | wx.STAY_ON_TOP)

        self.parent = parent
        self.panel = wx.Panel(self)
        self.nbt_data = None
        self.damage_color = None
        self.selected_pattern_button = None
        # Main sizer
        self.layered_selection = []
        # IS NOT LOADING PREVIEW
        self.components = components

        self.main_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # Left panel for patterns and colors
        self.left_panel = wx.Panel(self.panel)
        self.left_sizer = wx.BoxSizer(wx.VERTICAL)

        # Pattern selection
        self.pattern_panel = wx.ScrolledWindow(self.left_panel, size=(550, 250))
        self.pattern_panel.SetScrollRate(10, 10)
        self.pattern_sizer = wx.GridSizer(rows=0, cols=7, vgap=5, hgap=5)
        self.pattern_panel.SetSizer(self.pattern_sizer)
        # self.pattern_panel.SetForegroundColour((100,255,100))
        # # self.pattern_panel.SetForegroundColour((0, 0, 0))
        self.left_sizer.Add(self.pattern_panel, 1, wx.EXPAND | wx.ALL, 5)

        # Color selection
        self.color_panel = wx.Panel(self.left_panel)
        self.color_sizer = wx.GridSizer(rows=2, cols=8, vgap=2, hgap=2)
        self.color_buttons = []
        for i in range(16):
            btn = wx.Button(self.color_panel, size=(40, 40))
            btn.SetBackgroundColour(wx.Colour(*MC_COLORS[i]))
            btn.SetToolTip(COLOR_NAMES[i])
            btn.Bind(wx.EVT_BUTTON, lambda evt, idx=i: self.on_color_select(idx))
            self.color_sizer.Add(btn, 0, wx.EXPAND)
            self.color_buttons.append(btn)
        self.color_panel.SetSizer(self.color_sizer)
        self.left_sizer.Add(self.color_panel, 0, wx.ALIGN_CENTER | wx.ALL, 5)

        self.left_panel.SetSizer(self.left_sizer)
        self.main_sizer.Add(self.left_panel, 1, wx.EXPAND)

        # Right panel for preview and NBT
        self.right_panel = wx.Panel(self.panel)
        self.right_sizer = wx.BoxSizer(wx.VERTICAL)

        # Preview
        self.preview_bitmap = wx.StaticBitmap(self.right_panel, size=(PREVIEW_WIDTH, PREVIEW_HEIGHT))
        self.right_sizer.Add(self.preview_bitmap, 0, wx.ALIGN_CENTER | wx.ALL, 10)

        # Base color selection label
        self.base_color_label = wx.StaticText(self.right_panel, label="Base Color:")
        self.right_sizer.Add(self.base_color_label, 0, wx.ALL, 5)

        # Base color preview
        self.base_color_preview = wx.Panel(self.right_panel, size=(50, 50))
        self.base_color_preview.SetBackgroundColour(wx.Colour(*MC_COLORS[0]))
        self.right_sizer.Add(self.base_color_preview, 0, wx.ALL, 5)

        # NBT output
        self.nbt_output = wx.TextCtrl(self.right_panel, style=wx.TE_MULTILINE | wx.TE_READONLY, size=(200, 150))
        self.right_sizer.Add(self.nbt_output, 0, wx.EXPAND | wx.ALL, 5)

        # Buttons
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.build_button = wx.Button(self.right_panel, label="Save")
        self.clear_button = wx.Button(self.right_panel, label="Clear Layers")
        self.undo_button = wx.Button(self.right_panel, label="Undo Last")

        self.build_button.Bind(wx.EVT_BUTTON, self.on_save)
        self.clear_button.Bind(wx.EVT_BUTTON, self.on_clear_layers)
        self.undo_button.Bind(wx.EVT_BUTTON, self.on_undo_pattern)

        button_sizer.Add(self.build_button, 0, wx.ALL, 5)
        button_sizer.Add(self.clear_button, 0, wx.ALL, 5)
        button_sizer.Add(self.undo_button, 0, wx.ALL, 5)

        self.right_sizer.Add(button_sizer, 0, wx.ALIGN_CENTER)

        self.right_panel.SetSizer(self.right_sizer)
        self.main_sizer.Add(self.right_panel, 0, wx.EXPAND)

        self.panel.SetSizer(self.main_sizer)

        # Initialize
        self.selected_pattern_index = None
        self.layered_selection = []
        self.base_color_index = 0

        print(self.parent.get_item_id())
        if self.parent.get_item_id().startswith("minecraft:") and self.parent.get_item_id().endswith("_banner"):
            color_name_str = self.parent.get_item_id()[len("minecraft:"): -len("_banner")]
            print('color_name_str', color_name_str)
            try:
                self.base_color_index = COLOR_NAMES.index(color_name_str.replace("_", " ").title())
            except ValueError:
                self.base_color_index = 0  # Default to White
        elif self.parent.get_item_id().startswith("minecraft:") and self.parent.get_item_id().endswith("shield"):

            try:
                self.base_color_index =  COLOR_NAMES.index(components['minecraft:base_color'].py_str.replace("_", " ").title())

            except ValueError:
                self.base_color_index = 0  # Default to White
        self.load_images()
        self.display_patterns()
        self.status_bar = self.CreateStatusBar(2)
        self.status_bar.SetStatusWidths([-3, -1])
        self.update_status_bar()
        if components and 'minecraft:banner_patterns' in components:
            self.layered_selection = []
            for pat in components['minecraft:banner_patterns']:
                color_str = pat['color'].py_str
                pattern_str = pat['pattern'].py_str

                # Find color index
                try:
                    color_index = COLOR_NAMES.index(color_str.title().replace("_", " "))
                except ValueError:
                    color_index = 0  # default to white

                # Find pattern index
                pattern_idx = None
                for k, v in PATTERN_KEY_TO_NAME.items():
                    java_name = f"minecraft:{BEDROCK_PATTERN_TO_JAVA.get(v[0], "")}"
                    print(java_name,pattern_str)
                    if java_name == pattern_str:
                        pattern_idx = k
                        break
                if pattern_idx is not None:
                    self.layered_selection.append((pattern_idx, color_index))

            self.update_preview()

    def on_undo_pattern(self, event):
        if self.layered_selection:
            # Remove the last added pattern
            self.layered_selection.pop()
            self.update_preview()
            self.SetStatusText("Last pattern removed", 0)
        else:
            self.SetStatusText("No patterns to undo", 0)

    def load_images(self):
        banner = base64.b64decode(BANNER['ICONS'])
        buffer = io.BytesIO(banner)
        base = wx.Image()
        # base.LoadFile(buffer, wx.BITMAP_TYPE_PNG)
        base = Image.open(buffer)
        self.base_images = []
        self.pattern_images = []

        for i in range(IMAGE_COUNT):
            # Load and resize the image
            img = base.crop((i * ORIGINAL_WIDTH, 0, (i + 1) * ORIGINAL_WIDTH, ORIGINAL_HEIGHT))
            img = img.resize((PATTERN_WIDTH, PATTERN_HEIGHT), Image.NEAREST)

            # Convert to black while maintaining transparency
            img = img.convert("RGBA")
            data = numpy.array(img)

            # Set all non-transparent pixels to black (29, 29, 33)
            mask = data[:, :, 3] > 0
            data[mask, 0] = 255  # R
            data[mask, 1] = 255  # G
            data[mask, 2] = 255  # B

            # Alpha channel remains unchanged

            black_img = Image.fromarray(data)
            self.base_images.append(black_img)
            self.pattern_images.append(black_img)

    def display_patterns(self):
        """Display patterns with proper ordering and black background"""
        self.pattern_panel.SetBackgroundColour(wx.RED)

        # Create buttons in the correct order (0-42)
        for pattern_idx in (PATTERN_KEY_TO_NAME.keys()):
            if pattern_idx < 2:
                continue

            img = self.pattern_images[pattern_idx]
            rgba_img = img.convert('RGBA')
            data = numpy.array(rgba_img)

            # Create black background for transparent areas
            background = Image.new('RGBA', img.size, (0, 0, 0, 255))
            composite = Image.alpha_composite(background, rgba_img)

            # Create bitmap with black background
            bmp = wx.Bitmap.FromBufferRGBA(*composite.size, numpy.array(composite))

            # Create button with tooltip showing pattern name
            btn = wx.BitmapButton(
                self.pattern_panel,
                id=pattern_idx,
                bitmap=bmp,
                size=(PATTERN_WIDTH, PATTERN_HEIGHT)
            )
            btn.SetBackgroundColour(wx.BLACK)
            btn.SetToolTip(PATTERN_KEY_TO_NAME[pattern_idx][1])
            btn.Bind(wx.EVT_BUTTON, self.on_select_pattern)
            self.pattern_sizer.Add(btn, 0, wx.ALL, 1)

        self.pattern_panel.Layout()
        self.pattern_panel.Refresh()

    def on_select_pattern(self, event):
        # Reset previous selection if exists
        if self.selected_pattern_button:
            self.selected_pattern_button.SetBackgroundColour(wx.Colour(0, 0, 0))  # Black
            self.selected_pattern_button.Refresh()

        # Set new selection
        self.selected_pattern_index = event.GetId()
        self.selected_pattern_button = event.GetEventObject()
        self.selected_pattern_button.SetBackgroundColour(wx.Colour(255, 255, 0))  # Yellow highlight
        self.selected_pattern_button.Refresh()

    def on_color_select(self, color_index):
        if self.selected_pattern_index is None:
            # Set base color
            self.base_color_index = color_index
            self.base_color_preview.SetBackgroundColour(wx.Colour(*MC_COLORS[color_index]))
            self.base_color_preview.Refresh()
        else:
            # Add pattern layer
            self.layered_selection.append((self.selected_pattern_index, color_index))

            # Reset selection after color is chosen
            if self.selected_pattern_button:
                self.selected_pattern_button.SetBackgroundColour(wx.Colour(0, 0, 0))
                self.selected_pattern_button.Refresh()
            self.selected_pattern_index = None
            self.selected_pattern_button = None

        self.update_preview()

    def apply_color_filter(self, img, color):
        """Apply color while preserving transparency"""
        img = img.convert('RGBA')
        data = numpy.array(img)

        # Only modify non-transparent pixels
        mask = data[:, :, 3] > 0
        data[mask, :3] = color  # Set RGB for non-transparent pixels
        # Leave alpha channel as is

        return Image.fromarray(data)

    def update_preview(self):
        # Create blank canvas
        preview = Image.new("RGBA", (PREVIEW_WIDTH, PREVIEW_HEIGHT), (0, 0, 0, 0))

        # Apply base color to a solid rectangle (no pattern)
        base_color = MC_COLORS[self.base_color_index]
        base_layer = Image.new("RGBA", (PREVIEW_WIDTH, PREVIEW_HEIGHT), (*base_color, 255))
        preview = Image.alpha_composite(preview, base_layer)

        # Apply each pattern layer
        for pattern_idx, color_idx in self.layered_selection:
            pattern_img = self.pattern_images[pattern_idx].resize((PREVIEW_WIDTH, PREVIEW_HEIGHT))
            colored_pattern = self.apply_color_filter(pattern_img, MC_COLORS[color_idx])
            preview = Image.alpha_composite(preview, colored_pattern)

        # Convert to wx bitmap and display
        wx_img = wx.Bitmap.FromBufferRGBA(PREVIEW_WIDTH, PREVIEW_HEIGHT, preview.tobytes())
        self.preview_bitmap.SetBitmap(wx_img)
        self.nbt_output.SetValue(self.generate_java_nbt())
        self.panel.Layout()
        self.update_status_bar()

    def update_status_bar(self):
        if not self.layered_selection:
            self.SetStatusText("No patterns added", 0)
        else:
            last_pattern_idx, last_color_idx = self.layered_selection[-1]
            pattern_name = PATTERN_KEY_TO_NAME[last_pattern_idx][1]
            color_name = COLOR_NAMES[last_color_idx]
            self.SetStatusText(f"Last: {pattern_name} ({color_name})", 0)
        self.SetStatusText(f"Total: {len(self.layered_selection)} layers", 1)

    def generate_java_nbt(self):
        """Generate proper Bedrock NBT data with correct pattern names"""
        base_color = COLOR_NAMES[self.base_color_index].lower().replace(" ", "_")

        patterns = ListTag([])
        for pattern_idx, color_idx in self.layered_selection:
            if pattern_idx in PATTERN_KEY_TO_NAME:
                pattern_code = PATTERN_KEY_TO_NAME[pattern_idx][0]
                color_name = COLOR_NAMES[color_idx].lower().replace(" ", "_")
                patterns.append( CompoundTag({
                    "color": StringTag(color_name),
                    "pattern": StringTag(f"minecraft:{BEDROCK_PATTERN_TO_JAVA[pattern_code]}")
                }))
        if 'shield' in self.parent.get_item_id():
            self.nbt_data = CompoundTag({
                "minecraft:banner_patterns": patterns,
                "minecraft:base_color" : StringTag(base_color),
            })
        else:

            self.parent.set_item_id(f"minecraft:{base_color}_banner")
            self.nbt_data = CompoundTag({
                "minecraft:banner_patterns": patterns,
            })


        return self.nbt_data.to_snbt(2)

    def on_save(self, event):
        self.parent.set_components(self.nbt_data)
        self.Hide()
        self.Destroy()



        print('ok')

    def on_clear_layers(self, event):
        self.layered_selection = []
        # Clear any pattern selection
        if self.selected_pattern_button:
            self.selected_pattern_button.SetBackgroundColour(wx.Colour(0, 0, 0))
            self.selected_pattern_button.Refresh()
            self.selected_pattern_index = None
            self.selected_pattern_button = None
        self.update_preview()
class EmojiPanel(wx.ScrolledWindow):
    def __init__(self, parent, emojis, on_click):
        super().__init__(parent, style=wx.VSCROLL | wx.HSCROLL)
        self.emojis = emojis
        self.on_click = on_click

        self.cell_size = 30     # space for each emoji cell
        self.columns = 22       # emojis per row

        self.Bind(wx.EVT_PAINT, self.on_paint)
        self.Bind(wx.EVT_LEFT_DOWN, self.on_click_event)

        self.SetScrollRate(20, 20)
        self.update_virtual_size()

    def update_virtual_size(self):
        rows = (len(self.emojis) + self.columns - 1) // self.columns
        width = self.columns * self.cell_size
        height = rows * self.cell_size
        self.SetVirtualSize((width, height))

    def on_paint(self, event):
        dc = wx.BufferedPaintDC(self)
        self.PrepareDC(dc)
        dc.Clear()

        font = wx.Font(18, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        dc.SetFont(font)

        for i, emoji in enumerate(self.emojis):
            col = i % self.columns
            row = i // self.columns
            x = col * self.cell_size + 4
            y = row * self.cell_size + 4
            dc.DrawText(emoji, x, y)

    def on_click_event(self, event):
        x, y = self.CalcUnscrolledPosition(event.GetPosition())
        col = x // self.cell_size
        row = y // self.cell_size
        index = row * self.columns + col
        if 0 <= index < len(self.emojis):
            emoji = self.emojis[index]
            self.on_click(emoji)
class JavaNameTagAndLoreEditor(wx.Frame):
    def __init__(self, parent, components):
        super().__init__(None, title="Java Name and Lore Editor", size=(800, 720),
                         style=wx.DEFAULT_FRAME_STYLE | wx.STAY_ON_TOP)

        self.parent = parent
        # Always use CompoundTag for components
        self.components = components or CompoundTag({})

        # Normalize existing name/lore data from NBT
        self.custom_name = self._nbt_to_list(self.components.get("minecraft:custom_name")) or [{"text": ""}]
        self.lore = self._nbt_to_lore_list(self.components.get("minecraft:lore"))

        # UI
        panel = wx.Panel(self)
        v = wx.BoxSizer(wx.VERTICAL)

        # --- Name input ---
        v.Add(wx.StaticText(panel, label="Item Name:"), 0, wx.ALL, 6)
        self.name_input = rt.RichTextCtrl(panel,
                                          style=wx.VSCROLL | wx.HSCROLL | wx.NO_BORDER,
                                          size=(-1, 50))
        self.name_input.SetFont(wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        v.Add(self.name_input, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)

        # Controls row: color, bold, italic
        controls = wx.BoxSizer(wx.HORIZONTAL)
        controls.Add(wx.StaticText(panel, label="Text Color:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self.color_picker = wx.ColourPickerCtrl(panel, colour=wx.Colour(self._get_first_color(self.custom_name)))
        controls.Add(self.color_picker, 0, wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, 20)

        self.bold_cb = wx.CheckBox(panel, label="Bold")
        self.italic_cb = wx.CheckBox(panel, label="Italic")
        controls.Add(self.bold_cb, 0, wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, 10)
        controls.Add(self.italic_cb, 0, wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, 10)
        v.Add(controls, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)

        # --- Lore input ---
        v.Add(wx.StaticText(panel, label="Lore Editor (each styled line preserved):"), 0, wx.ALL, 6)
        self.lore_input = rt.RichTextCtrl(panel,
                                          style=wx.VSCROLL | wx.HSCROLL | wx.NO_BORDER,
                                          size=(-1, 140))
        self.lore_input.SetFont(wx.Font(11, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        v.Add(self.lore_input, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)

        # --- Preview ---
        v.Add(wx.StaticText(panel, label="Preview:"), 0, wx.LEFT | wx.TOP, 6)
        self.preview = rt.RichTextCtrl(panel, style=rt.RE_READONLY | wx.NO_BORDER | wx.VSCROLL | wx.HSCROLL,
                                       size=(-1, 90))
        self.preview.SetEditable(False)
        v.Add(self.preview, 0, wx.EXPAND | wx.ALL, 6)

        # --- Save button ---
        save_btn = wx.Button(panel, label="Save Name and Lore")
        v.Add(save_btn, 0, wx.CENTER | wx.ALL, 8)
        panel.SetSizer(v)

        # Populate initial content
        self.load_formatted_text(self.name_input, self.custom_name)
        for idx, line in enumerate(self.lore):
            self.load_formatted_text(self.lore_input, line)
            if idx < len(self.lore) - 1:
                self.lore_input.WriteText("\n")

        self._rebuild_preview()

        # --- Bind events ---
        self.color_picker.Bind(wx.EVT_COLOURPICKER_CHANGED, self.on_color_change)
        self.bold_cb.Bind(wx.EVT_CHECKBOX, self.on_toggle_bold)
        self.italic_cb.Bind(wx.EVT_CHECKBOX, self.on_toggle_italic)
        save_btn.Bind(wx.EVT_BUTTON, self.on_generate)

        # Selection/caret change events
        self.name_input.Bind(rt.EVT_RICHTEXT_SELECTION_CHANGED, self.on_selection_changed)
        self.name_input.Bind(wx.EVT_TEXT, self.on_name_text_changed)
        self.lore_input.Bind(wx.EVT_TEXT, self.on_lore_text_changed)
        self.lore_input.Bind(rt.EVT_RICHTEXT_SELECTION_CHANGED, self.on_lore_selection_changed)
        self.name_input.Bind(wx.EVT_SET_FOCUS, self.on_ctrl_focus)
        self.lore_input.Bind(wx.EVT_SET_FOCUS, self.on_ctrl_focus)
        emojis = list(EMOJI_JAVA)

        emoji_panel = EmojiPanel(panel, emojis, self.on_emoji_click)

        v.Add(wx.StaticText(panel, label="Emoji Picker:"), 0, wx.LEFT | wx.TOP, 6)
        v.Add(emoji_panel, 1, wx.EXPAND | wx.ALL, 6)
        self.Centre()
        self.Show()

    # ------------------------------
    # Utility functions
    # ------------------------------
    def on_emoji_click(self, emoji):
        """Insert clicked emoji into the last active RichTextCtrl at the caret"""
        ctrl = getattr(self, "_last_active_ctrl", self.name_input)


        # Insert emoji at current caret position
        pos = ctrl.GetInsertionPoint()
        ctrl.WriteText(emoji)
        ctrl.SetInsertionPoint(len(emoji) + pos + 1)

        # Rebuild preview
        self._rebuild_preview()
    def on_ctrl_focus(self, evt):
        self._last_active_ctrl = evt.GetEventObject()
        evt.Skip()
    def _get_first_color(self, formatted_list):
        if not formatted_list:
            return "#FFFFFF"
        for e in formatted_list:
            if isinstance(e, dict) and e.get("color"):
                return e.get("color")
        return "#FFFFFF"

    def _to_wxcolour(self, hexstr):
        try:
            if hexstr and hexstr.startswith("#") and len(hexstr) >= 7:
                r = int(hexstr[1:3], 16)
                g = int(hexstr[3:5], 16)
                b = int(hexstr[5:7], 16)
                return wx.Colour(r, g, b)
        except Exception:
            pass
        return wx.Colour(255, 255, 255)

    def _nbt_to_list(self, nbt):
        """Convert NBT name (ListTag or CompoundTag) into list of dicts"""
        out = []
        if nbt is None:
            return out

        # Wrap single CompoundTag in a list
        if not isinstance(nbt, (list, ListTag)):
            nbt = [nbt]

        try:
            for entry in nbt:
                d = {"text": str(entry.get("text", ""))}
                color = entry.get("color")
                if color:
                    d["color"] = str(color)
                bold = entry.get("bold")
                if bold:
                    d["bold"] = bool(bold.value) if hasattr(bold, "value") else bool(bold)
                italic = entry.get("italic")
                if italic:
                    d["italic"] = bool(italic.value) if hasattr(italic, "value") else bool(italic)
                out.append(d)
        except Exception:
            pass
        return out

    def _nbt_to_lore_list(self, nbt):
        """Convert NBT lore (ListTag of CompoundTag with optional 'extra') into list of lists of dicts"""
        out = []
        if nbt is None:
            return out
        try:
            for line_tag in nbt:
                line_list = []
                # first text
                first_entry = {
                    "text": str(line_tag.get("text", "")),
                }
                if "color" in line_tag:
                    first_entry["color"] = str(line_tag["color"])
                if "bold" in line_tag:
                    first_entry["bold"] = bool(line_tag["bold"].value) if hasattr(line_tag["bold"], "value") else bool(
                        line_tag["bold"])
                if "italic" in line_tag:
                    first_entry["italic"] = bool(line_tag["italic"].value) if hasattr(line_tag["italic"],
                                                                                      "value") else bool(
                        line_tag["italic"])
                line_list.append(first_entry)

                # extra
                extra = line_tag.get("extra")
                if extra:
                    for e in extra:
                        entry = {
                            "text": str(e.get("text", "")),
                        }
                        if "color" in e:
                            entry["color"] = str(e["color"])
                        if "bold" in e:
                            entry["bold"] = bool(e["bold"].value) if hasattr(e["bold"], "value") else bool(e["bold"])
                        if "italic" in e:
                            entry["italic"] = bool(e["italic"].value) if hasattr(e["italic"], "value") else bool(
                                e["italic"])
                        line_list.append(entry)

                out.append(line_list)
        except Exception:
            pass
        return out

    def _dict_to_nbt(self, entry):
        """Convert dict to CompoundTag with StringTag/ByteTag"""
        nbt_entry = CompoundTag()
        # Fix surrogate pairs for 'text'
        text = entry.get("text", "")
        text = self.fix_surrogates(text)
        nbt_entry["text"] = StringTag(text)

        if "color" in entry:
            nbt_entry["color"] = StringTag(entry["color"])
        if "bold" in entry:
            nbt_entry["bold"] = ByteTag(1 if entry["bold"] else 0)
        if "italic" in entry:
            nbt_entry["italic"] = ByteTag(1 if entry["italic"] else 0)
        return nbt_entry

    # ------------------------------
    # Load formatted text into RichTextCtrl
    # ------------------------------
    def load_formatted_text(self, ctrl, formatted_text):
        if formatted_text is None:
            return
        if isinstance(formatted_text, dict):
            formatted_text = [formatted_text]
        for entry in formatted_text:
            attr = rt.RichTextAttr()
            if entry.get("color"):
                attr.SetTextColour(self._to_wxcolour(entry["color"]))
            if entry.get("bold"):
                attr.SetFontWeight(wx.FONTWEIGHT_BOLD)
            if entry.get("italic"):
                attr.SetFontStyle(wx.FONTSTYLE_ITALIC)
            ctrl.BeginStyle(attr)
            ctrl.WriteText(entry.get("text", ""))
            ctrl.EndStyle()

    # ------------------------------
    # Process RichTextCtrl → list of dicts (single_line or multi-line)
    # ------------------------------
    def process_richtext(self, ctrl, single_line=False):
        pos = 0
        end = ctrl.GetLastPosition()
        lines = []
        current_line = []

        while pos < end:
            attr = rt.RichTextAttr()
            try:
                ctrl.GetStyle(pos, attr)
            except Exception:
                pass
            ch = ctrl.GetRange(pos, pos + 1)
            if ch == "\n" and not single_line:
                if current_line:
                    lines.append(current_line)
                current_line = []
                pos += 1
                continue

            entry = {"text": ch}
            if attr.HasTextColour():
                try:
                    entry["color"] = attr.GetTextColour().GetAsString(wx.C2S_HTML_SYNTAX)
                except Exception:
                    pass
            if attr.GetFontWeight() == wx.FONTWEIGHT_BOLD:
                entry["bold"] = True
            if attr.GetFontStyle() == wx.FONTSTYLE_ITALIC:
                entry["italic"] = True
            current_line.append(entry)
            pos += 1

        if current_line:
            lines.append(current_line)

        # Merge runs with identical formatting
        def merge(line):
            merged = []
            for e in line:
                if merged and all(merged[-1].get(k) == e.get(k) for k in ("color", "bold", "italic")):
                    merged[-1]["text"] += e["text"]
                else:
                    merged.append(e.copy())
            return merged

        if single_line:
            return merge(lines[0]) if lines else []
        return [merge(l) for l in lines]

    # ------------------------------
    # Apply style to selection or insertion
    # ------------------------------
    def _get_selection_range(self, ctrl):
        try:
            sel = ctrl.GetSelectionRange()
            if hasattr(sel, "GetStart"):
                return sel.GetStart(), sel.GetEnd()
        except Exception:
            pass
        return ctrl.GetInsertionPoint(), ctrl.GetInsertionPoint()

    def _style_at_pos(self, ctrl, pos):
        attr = rt.RichTextAttr()
        try:
            ctrl.GetStyle(pos, attr)
        except Exception:
            pass
        out = {}
        if attr.HasTextColour():
            try:
                out["color"] = attr.GetTextColour().GetAsString(wx.C2S_HTML_SYNTAX)
            except Exception:
                pass
        if attr.GetFontWeight() == wx.FONTWEIGHT_BOLD:
            out["bold"] = True
        if attr.GetFontStyle() == wx.FONTSTYLE_ITALIC:
            out["italic"] = True
        return out

    def on_name_text_changed(self, evt):
        self._rebuild_preview()
        evt.Skip()
    def apply_style_to_ctrl(self, ctrl, color=None, bold=None, italic=None):
        start, end = self._get_selection_range(ctrl)
        sel_len = end - start

        attr = rt.RichTextAttr()
        if sel_len > 0:
            if color:
                attr.SetTextColour(color)
            if bold is not None:
                attr.SetFontWeight(wx.FONTWEIGHT_BOLD if bold else wx.FONTWEIGHT_NORMAL)
            if italic is not None:
                attr.SetFontStyle(wx.FONTSTYLE_ITALIC if italic else wx.FONTSTYLE_NORMAL)
            ctrl.SetStyle(rt.RichTextRange(start, end), attr)
        else:
            current = ctrl.GetDefaultStyleEx()
            if color:
                current.SetTextColour(color)
            if bold is not None:
                current.SetFontWeight(wx.FONTWEIGHT_BOLD if bold else wx.FONTWEIGHT_NORMAL)
            if italic is not None:
                current.SetFontStyle(wx.FONTSTYLE_ITALIC if italic else wx.FONTSTYLE_NORMAL)
            ctrl.SetDefaultStyle(current)

    # ------------------------------
    # Sync selection to controls
    # ------------------------------
    def on_lore_text_changed(self, evt):
        self._rebuild_preview()
        evt.Skip()

    # ------------------------------
    # Track the last active RichTextCtrl
    # ------------------------------
    def on_selection_changed(self, evt):
        ctrl = evt.GetEventObject()
        self._last_active_ctrl = ctrl  # Remember this control for styling
        start, end = self._get_selection_range(ctrl)
        pos = start if start < ctrl.GetLastPosition() else max(0, ctrl.GetLastPosition() - 1)
        style = self._style_at_pos(ctrl, pos)

        # Update controls
        if "color" in style:
            try:
                wx.CallAfter(self.color_picker.SetColour, self._to_wxcolour(style["color"]))
            except Exception:
                pass
        self.bold_cb.SetValue(style.get("bold", False))
        self.italic_cb.SetValue(style.get("italic", False))

        self._rebuild_preview()
        evt.Skip()

    def on_lore_selection_changed(self, evt):
        # Mirror the same logic for lore
        self.on_selection_changed(evt)
        evt.Skip()

    # ------------------------------
    # Apply style to the last active control
    # ------------------------------
    def on_color_change(self, evt):
        ctrl = getattr(self, "_last_active_ctrl", self.name_input)
        self.apply_style_to_ctrl(ctrl, color=evt.GetColour())
        self._rebuild_preview()

    def on_toggle_bold(self, evt):
        ctrl = getattr(self, "_last_active_ctrl", self.name_input)
        self.apply_style_to_ctrl(ctrl, bold=self.bold_cb.GetValue())
        self._rebuild_preview()

    def on_toggle_italic(self, evt):
        ctrl = getattr(self, "_last_active_ctrl", self.name_input)
        self.apply_style_to_ctrl(ctrl, italic=self.italic_cb.GetValue())
        self._rebuild_preview()

    # ------------------------------
    # Preview builder
    # ------------------------------
    def _rebuild_preview(self):
        self.preview.Freeze()
        try:
            self.preview.Clear()
            # Name
            name_runs = self.process_richtext(self.name_input, single_line=True)
            for entry in name_runs:
                attr = rt.RichTextAttr()
                if entry.get("color"):
                    attr.SetTextColour(self._to_wxcolour(entry["color"]))
                if entry.get("bold"):
                    attr.SetFontWeight(wx.FONTWEIGHT_BOLD)
                if entry.get("italic"):
                    attr.SetFontStyle(wx.FONTSTYLE_ITALIC)
                self.preview.BeginStyle(attr)
                self.preview.WriteText(entry.get("text", ""))
                self.preview.EndStyle()
            self.preview.WriteText("\n")

            # Lore
            lore_runs = self.process_richtext(self.lore_input, single_line=False)
            for li, line in enumerate(lore_runs):
                for entry in line:
                    attr = rt.RichTextAttr()
                    if entry.get("color"):
                        attr.SetTextColour(self._to_wxcolour(entry["color"]))
                    if entry.get("bold"):
                        attr.SetFontWeight(wx.FONTWEIGHT_BOLD)
                    if entry.get("italic"):
                        attr.SetFontStyle(wx.FONTSTYLE_ITALIC)
                    self.preview.BeginStyle(attr)
                    self.preview.WriteText(entry.get("text", ""))
                    self.preview.EndStyle()
                if li < len(lore_runs) - 1:
                    self.preview.WriteText("\n")
        finally:
            self.preview.Thaw()

    def fix_surrogates(self, text: str) -> str:
        # Encode to utf-16-le bytes, preserving surrogates
        utf16_bytes = text.encode("utf-16-le", "surrogatepass")
        # Decode back to string, preserving surrogates
        return utf16_bytes.decode("utf-16-le", "surrogatepass")
    # ------------------------------
    # Save to NBT
    # ------------------------------
    def lore_line_to_nbt(self, line):
        if not line:
            return CompoundTag({'text': StringTag('')})
        # Fix surrogates for all text
        first = line[0].copy()
        first['text'] = self.fix_surrogates(first.get('text', ''))
        rest = []
        for e in line[1:]:
            e_copy = e.copy()
            e_copy['text'] = self.fix_surrogates(e_copy.get('text', ''))
            rest.append(e_copy)

        tag = self._dict_to_nbt(first)
        if rest:
            tag['extra'] = ListTag([self._dict_to_nbt(e) for e in rest])
        return tag

    # Updated on_generate
    def on_generate(self, evt):
        # Process name and lore from RichTextCtrl
        name_data = self.process_richtext(self.name_input, single_line=True)
        lore_data = self.process_richtext(self.lore_input, single_line=False)

        # Convert name → ListTag of CompoundTag
        self.components["minecraft:custom_name"] = self._dict_to_nbt({
            **name_data[0],  # use the first element of name_data or merge if needed
            "text": self.fix_surrogates(name_data[0].get("text", "")),
        })

        # Convert lore → ListTag of CompoundTag with 'extra'
        lore_nbt_list = ListTag()
        for line in lore_data:
            lore_nbt_list.append(self.lore_line_to_nbt(line))
        self.components["minecraft:lore"] = lore_nbt_list

        self._rebuild_preview()
        print("[Saved NBT components]")
        print(self.components)
        self.parent.set_components(self.components)
        wx.MessageBox("Name and Lore saved as NBT components.", "Saved", wx.OK | wx.ICON_INFORMATION)

class ItemTools:
    def __init__(self, parent):
        self.parent = parent
        self.icon_resources = IconResources()

        BANNER['ICONS'] = self.icon_resources.get_json_data['banner']
    def banner_editor(self, parent, components):
        banner_select = BannerSelector(parent, components)
        banner_select.Show(True)
    def edit_name_lore(self, parent, components):

        name_lore = JavaNameTagAndLoreEditor(parent, components)
        name_lore.Show(True)

    def edit_tag(self, parent, components):
        """
        Opens a small window to display and edit SNBT text.
        Displays components.to_snbt(1) in a multiline text box
        and returns the modified text when saved.
        """
        snbt_text = components.to_snbt(1)

        dialog = wx.Dialog(parent, title="Edit SNBT", size=(500, 400))
        dialog.SetBackgroundColour(wx.Colour(40, 40, 40))

        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # --- Multiline text box ---
        text_ctrl = wx.TextCtrl(
            dialog,
            value=snbt_text,
            style=wx.TE_MULTILINE | wx.TE_RICH2 | wx.HSCROLL
        )
        text_ctrl.SetBackgroundColour(wx.Colour(30, 30, 30))
        text_ctrl.SetForegroundColour(wx.Colour(0, 230, 0))
        main_sizer.Add(text_ctrl, 1, wx.EXPAND | wx.ALL, 10)

        # --- Buttons ---
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        save_btn = wx.Button(dialog, label="Save")
        cancel_btn = wx.Button(dialog, label="Cancel")
        btn_sizer.Add(save_btn, 1, wx.RIGHT, 5)
        btn_sizer.Add(cancel_btn, 1, wx.LEFT, 5)
        main_sizer.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 10)

        dialog.SetSizer(main_sizer)

        # --- Bindings ---
        result = {"text": None}

        def on_save(event):
            result["text"] = text_ctrl.GetValue()
            dialog.EndModal(wx.ID_OK)

        def on_cancel(event):
            dialog.EndModal(wx.ID_CANCEL)

        save_btn.Bind(wx.EVT_BUTTON, on_save)
        cancel_btn.Bind(wx.EVT_BUTTON, on_cancel)

        if dialog.ShowModal() == wx.ID_OK:
            new_text = result["text"]
            print("Updated SNBT:")
            print(new_text)
            dialog.Destroy()
            return new_text
        else:
            dialog.Destroy()
            return None

    def edit_enchants(self, parent, components):
        import wx
        from wx import (
            CheckBox, TextCtrl, Button, StaticText, BoxSizer, Frame, FlexGridSizer,
            EVT_CHECKBOX, EVT_BUTTON, ALL, VERTICAL, HORIZONTAL
        )
        from amulet_nbt import CompoundTag, IntTag

        font = wx.Font(11, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        BLACK = wx.Colour(0, 0, 0)
        GREEN = wx.Colour(0, 255, 0)

        enchant_checkboxes = {}
        enchant_level_inputs = {}

        # Create main frame
        panel = Frame(parent, title="Edit Enchantments", style=wx.DEFAULT_FRAME_STYLE | wx.STAY_ON_TOP)
        panel.SetBackgroundColour(BLACK)
        main_sizer = BoxSizer(VERTICAL)

        # ----------------------- Helpers -----------------------
        def on_check(evt):
            cb = evt.GetEventObject()
            lvl_ctrl = enchant_level_inputs.get(cb.GetId())
            if lvl_ctrl:
                lvl_ctrl.Enable(cb.IsChecked())

        def unselect(evt):
            for cb in enchant_checkboxes.values():
                cb.SetValue(False)
                lvl_ctrl = enchant_level_inputs.get(cb.GetId())
                if lvl_ctrl:
                    lvl_ctrl.SetValue("0")
                    lvl_ctrl.Enable(False)

        def select_best(evt):
            if ':' not in parent.get_item_id():
                item_type = get_item_type(parent.get_item_id())
            else:
                item_type = get_item_type(parent.get_item_id().split(':')[1])
            allowed_ids = valid_enchants_java.get(item_type, [])
            for ench_id in allowed_ids:
                name = java_enchant_map[ench_id]
                cb = enchant_checkboxes.get(name)
                if cb:
                    cb.SetValue(True)
                    lvl_ctrl = enchant_level_inputs[cb.GetId()]
                    lvl_ctrl.SetValue(str(max_levels_java.get(ench_id, 1)))
                    lvl_ctrl.Enable(True)

        def save_data(evt):
            # Ensure stored_enchantments path exists
            if "minecraft:enchantments" not in components or not isinstance(
                    components["minecraft:enchantments"], CompoundTag):
                components["minecraft:enchantments"] = CompoundTag()

            stored_enchants = CompoundTag()
            name_to_java = {v: k for k, v in java_enchant_map.items()}

            for name, cb in enchant_checkboxes.items():
                if cb.IsChecked():
                    java_id = name_to_java[name]
                    lvl = int(enchant_level_inputs[cb.GetId()].GetValue())
                    stored_enchants[java_id] = IntTag(lvl)

            # Save back
            components["minecraft:enchantments"] = stored_enchants
            print("Saved enchantments:", components)
            parent.set_components(components)

        # ----------------------- UI -----------------------
        top_bar = BoxSizer(HORIZONTAL)
        unselect_button = Button(panel, label="Unselect All")
        select_button = Button(panel, label="Select All")
        save_button = Button(panel, label="Save Enchants")
        for btn in (unselect_button, select_button, save_button):
            btn.SetFont(font)
            btn.SetForegroundColour(GREEN)
            btn.SetBackgroundColour(BLACK)
        unselect_button.Bind(EVT_BUTTON, unselect)
        select_button.Bind(EVT_BUTTON, select_best)
        save_button.Bind(EVT_BUTTON, save_data)
        top_bar.Add(unselect_button, 0, ALL, 5)
        top_bar.Add(select_button, 0, ALL, 5)
        top_bar.Add(save_button, 0, ALL, 5)
        main_sizer.Add(top_bar)

        main_sizer.Add(StaticText(panel, label="Enchant (Check to apply, set level):"), 0, ALL, 5)

        # Determine allowed enchantments for the item
        if ':' not in parent.get_item_id():
            item_type = get_item_type(parent.get_item_id())
        else:
            item_type = get_item_type(parent.get_item_id().split(':')[1])
        allowed_ids = valid_enchants_java.get(item_type, [])

        # Load existing enchantments, default to empty CompoundTag
        if not components:
            components = CompoundTag({})
        existing_enchants = components.get("minecraft:enchantments", None)


        if not isinstance(existing_enchants, CompoundTag):
            existing_enchants = CompoundTag()
            components["minecraft:enchantments"] = existing_enchants

        # Grid layout
        grid_sizer = FlexGridSizer(rows=0, cols=6, hgap=10, vgap=5)
        grid_sizer.AddGrowableCol(1)
        grid_sizer.AddGrowableCol(3)
        grid_sizer.AddGrowableCol(5)

        for ench_id in allowed_ids:
            name = java_enchant_map[ench_id]
            level = existing_enchants.get(ench_id, IntTag(max_levels_java.get(ench_id, 1))).py_int

            cb_id = wx.NewIdRef()
            cb = CheckBox(panel, id=cb_id.GetId(), label=name)
            cb.SetFont(font)
            cb.SetForegroundColour(GREEN)
            cb.SetBackgroundColour(BLACK)
            cb.Bind(EVT_CHECKBOX, on_check)
            cb.SetValue(ench_id in existing_enchants)

            lvl = TextCtrl(panel, size=(50, -1), style=wx.TE_CENTER)
            lvl.SetFont(font)
            lvl.SetValue(str(level))
            lvl.Enable(ench_id in existing_enchants)
            lvl.SetForegroundColour(GREEN)
            lvl.SetBackgroundColour(BLACK)

            enchant_checkboxes[name] = cb
            enchant_level_inputs[cb_id.GetId()] = lvl

            grid_sizer.Add(cb, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 3)
            grid_sizer.Add(lvl, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 3)

        main_sizer.Add(grid_sizer, 0, wx.ALL, 5)

        panel.SetSizer(main_sizer)
        panel.Centre()
        panel.Fit()
        panel.Show()

    def edit_fireworks_data(self, parent, components):
        def java_color_to_rgb(color_int):
            """Convert Java/Minecraft color int (0xRRGGBB) to (R, G, B)."""
            r = (color_int >> 16) & 0xFF
            g = (color_int >> 8) & 0xFF
            b = color_int & 0xFF
            return r, g, b

        def rgb_to_java_color(r, g, b):
            """Convert (R, G, B) to Java/Minecraft color int (0xRRGGBB)."""
            return (r << 16) | (g << 8) | b
        """Edit fireworks stored in components using NBT format."""
        frame = wx.Frame(parent, title="Edit Fireworks Explosions", size=(700, 500),
                         style=wx.DEFAULT_FRAME_STYLE | wx.STAY_ON_TOP)

        scroll_panel = wx.ScrolledWindow(frame, style=wx.VSCROLL)
        scroll_panel.SetScrollRate(5, 5)
        scroll_panel.SetBackgroundColour(wx.Colour(255, 255, 255))

        main_sizer = wx.BoxSizer(wx.VERTICAL)
        scroll_panel.SetSizer(main_sizer)
        frame_sizer = wx.BoxSizer(wx.VERTICAL)
        frame_sizer.Add(scroll_panel, 1, wx.EXPAND)
        frame.SetSizer(frame_sizer)

        explosion_rows = []

        # Flight
        flight_sizer = wx.BoxSizer(wx.HORIZONTAL)
        flight_sizer.Add(wx.StaticText(scroll_panel, label="Flight:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)

        # Get existing flight from NBT
        if not components:
            components = CompoundTag()
        fw_tag = components.get("minecraft:fireworks", CompoundTag())
        flight_val = fw_tag.get("flight_duration", ByteTag(1)).py_data
        flight_input = wx.SpinCtrl(scroll_panel, min=1, max=127, initial=flight_val)
        flight_sizer.Add(flight_input, 0, wx.RIGHT, 10)
        main_sizer.Add(flight_sizer, 0, wx.ALL | wx.EXPAND, 5)

        def create_color_picker(label, initial_colors=None):
            """Creates a color picker row for NBT colors with both manual and standard color options."""
            colors_list = initial_colors or []
            sizer = wx.BoxSizer(wx.HORIZONTAL)
            sizer.Add(wx.StaticText(scroll_panel, label=label + ":"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)

            btns = []

            # --- Standard dye colors (RGB from integer) ---
            standard_colors = [
                ("Black", 1973019),
                ("Red", 11743532),
                ("Green", 3887386),
                ("Brown", 5320730),
                ("Blue", 2437522),
                ("Purple", 8073150),
                ("Cyan", 2651799),
                ("Light Gray", 11250603),
                ("Gray", 4408131),
                ("Pink", 14188952),
                ("Lime", 4312372),
                ("Yellow", 14602026),
                ("Light Blue", 6719955),
                ("Magenta", 12801229),
                ("Orange", 15435844),
                ("White", 15790320)
            ]

            # --- Add + button first ---
            add_btn = wx.Button(scroll_panel, label="+", size=(20,20))
            sizer.Add(add_btn, 0, wx.RIGHT, 5)

            # --- Add dropdown for standard colors ---
            color_choice = wx.Choice(scroll_panel, choices=[c[0] for c in standard_colors])
            sizer.Add(color_choice, 0, wx.RIGHT, 5)

            add_std_btn = wx.Button(scroll_panel, label="Add Std", size=(60,20))
            sizer.Add(add_std_btn, 0, wx.RIGHT, 5)

            def refresh_ui():
                scroll_panel.Layout()
                scroll_panel.FitInside()
                frame.Layout()
                frame.Refresh()
                frame.Update()

            def open_color_dialog(existing_btn=None):
                """Opens color picker dialog; updates existing button if given."""
                dlg = wx.ColourDialog(frame)
                dlg.GetColourData().SetChooseFull(True)
                if dlg.ShowModal() == wx.ID_OK:
                    col = dlg.GetColourData().GetColour()
                    r, g, b = col.Red(), col.Green(), col.Blue()
                    if existing_btn:
                        existing_btn.SetBackgroundColour(wx.Colour(r, g, b))
                    else:
                        btn = wx.Button(scroll_panel, label="Pick Color")
                        btn.SetBackgroundColour(wx.Colour(r, g, b))
                        sizer.Add(btn, 0, wx.RIGHT, 5)
                        btns.append(btn)
                        bind_color_button(btn)
                    refresh_ui()
                dlg.Destroy()

            def remove_color(btn):
                """Removes color button."""
                sizer.Hide(btn)
                sizer.Remove(btn)
                btn.Destroy()
                if btn in btns:
                    btns.remove(btn)
                refresh_ui()

            def bind_color_button(btn):
                """Bind color editing/removal to button."""
                btn.Bind(wx.EVT_BUTTON, lambda evt, b=btn: open_color_dialog(existing_btn=b))
                btn.Bind(wx.EVT_RIGHT_DOWN, lambda evt, b=btn: remove_color(b))

            def add_color(evt=None):
                """Manual color picker via + button."""
                open_color_dialog()

            def add_standard_color(evt=None):
                """Add selected standard color."""
                idx = color_choice.GetSelection()
                if idx == wx.NOT_FOUND:
                    return
                name, value = standard_colors[idx]
                r, g, b = java_color_to_rgb(value)
                btn = wx.Button(scroll_panel, label=name)
                btn.SetBackgroundColour(wx.Colour(r, g, b))
                sizer.Add(btn, 0, wx.RIGHT, 5)
                btns.append(btn)
                bind_color_button(btn)
                refresh_ui()

            # --- Bind buttons ---
            add_btn.Bind(wx.EVT_BUTTON, add_color)
            add_std_btn.Bind(wx.EVT_BUTTON, add_standard_color)

            # --- Initialize with provided colors ---
            for c in colors_list:
                r, g, b = java_color_to_rgb(c)
                btn = wx.Button(scroll_panel, label="Pick Color")
                btn.SetBackgroundColour(wx.Colour(r, g, b))
                sizer.Add(btn, 0, wx.RIGHT, 5)
                btns.append(btn)
                bind_color_button(btn)

            refresh_ui()
            return sizer, btns

        def add_explosion(explosion_tag=None):
            container_box = wx.StaticBox(scroll_panel, label="Explosion")
            container = wx.StaticBoxSizer(container_box, wx.VERTICAL)

            explosion_tag = explosion_tag or CompoundTag()
            colors = [c.py_int if hasattr(c, "py_int") else c for c in
                      explosion_tag.get("colors", IntArrayTag([])).py_data]
            fade_colors = [c.py_int if hasattr(c, "py_int") else c for c in
                           explosion_tag.get("fade_colors", IntArrayTag([])).py_data]
            shape = explosion_tag.get("shape", StringTag("small_ball")).py_str
            has_trail = bool(explosion_tag.get("has_trail", ByteTag(0)).py_int)
            has_twinkle = bool(explosion_tag.get("has_twinkle", ByteTag(0)).py_int)

            color_sizer, color_btns = create_color_picker("Colors", colors)
            fade_sizer, fade_btns = create_color_picker("Fade", fade_colors)
            container.Add(color_sizer, 0, wx.EXPAND | wx.ALL, 5)
            container.Add(fade_sizer, 0, wx.EXPAND | wx.ALL, 5)

            # Options row
            options = wx.FlexGridSizer(1, 6, 5, 5)
            type_choice = wx.Choice(scroll_panel, choices=["small_ball", "large_ball", "star", "creeper", "burst"])
            type_choice.SetSelection(["small_ball", "large_ball", "star", "creeper", "burst"].index(shape))
            options.Add(wx.StaticText(scroll_panel, label="Shape:"), 0, wx.ALIGN_CENTER_VERTICAL)
            options.Add(type_choice, 0)

            flicker_cb = wx.CheckBox(scroll_panel, label="Twinkle")
            flicker_cb.SetValue(has_twinkle)
            trail_cb = wx.CheckBox(scroll_panel, label="Trail")
            trail_cb.SetValue(has_trail)

            # Remove + Copy buttons
            remove_btn = wx.Button(scroll_panel, label="Remove")
            copy_btn = wx.Button(scroll_panel, label="Copy")

            def remove(evt):
                main_sizer.Hide(container)
                main_sizer.Remove(container)
                explosion_rows.remove(explosion_row)
                scroll_panel.Layout()
                scroll_panel.FitInside()

            def copy(evt):
                """Duplicate this explosion with the same settings."""
                duplicate_tag = CompoundTag({
                    "colors": IntArrayTag([(btn.GetBackgroundColour().Red() << 16) |
                                           (btn.GetBackgroundColour().Green() << 8) |
                                           btn.GetBackgroundColour().Blue()
                                           for btn in color_btns]),
                    "fade_colors": IntArrayTag([(btn.GetBackgroundColour().Red() << 16) |
                                                (btn.GetBackgroundColour().Green() << 8) |
                                                btn.GetBackgroundColour().Blue()
                                                for btn in fade_btns]),
                    "shape": StringTag(type_choice.GetString(type_choice.GetSelection())),
                    "has_trail": ByteTag(1 if trail_cb.GetValue() else 0),
                    "has_twinkle": ByteTag(1 if flicker_cb.GetValue() else 0)
                })
                add_explosion(duplicate_tag)
                scroll_panel.Layout()
                scroll_panel.FitInside()
                frame.Refresh()

            remove_btn.Bind(wx.EVT_BUTTON, remove)
            copy_btn.Bind(wx.EVT_BUTTON, copy)

            # Add to layout
            options.Add(flicker_cb, 0)
            options.Add(trail_cb, 0)
            options.Add(copy_btn, 0)
            options.Add(remove_btn, 0)

            container.Add(options, 0, wx.EXPAND | wx.ALL, 5)
            main_sizer.Add(container, 0, wx.EXPAND | wx.ALL, 5)

            # Store explosion as dict for safe access later
            explosion_row = {
                "sizer": container,
                "color_btns": color_btns,
                "fade_btns": fade_btns,
                "type_choice": type_choice,
                "flicker_cb": flicker_cb,
                "trail_cb": trail_cb
            }
            explosion_rows.append(explosion_row)

            scroll_panel.Layout()
            scroll_panel.FitInside()

        # Buttons
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        add_btn = wx.Button(scroll_panel, label="Add Explosion")
        save_btn = wx.Button(scroll_panel, label="Save")

        add_btn.Bind(wx.EVT_BUTTON, lambda e: add_explosion())

        def save_fireworks(evt):
            explosions_list = ListTag()

            for row in explosion_rows:  # row is now a dict
                colors = []
                for btn in row["color_btns"]:
                    col = btn.GetBackgroundColour()
                    color_int = (col.Red() << 16) | (col.Green() << 8) | col.Blue()
                    colors.append(color_int)

                fade_colors = []
                for btn in row["fade_btns"]:
                    col = btn.GetBackgroundColour()
                    color_int = (col.Red() << 16) | (col.Green() << 8) | col.Blue()
                    fade_colors.append(color_int)

                shape = row["type_choice"].GetString(row["type_choice"].GetSelection())
                has_trail = row["trail_cb"].GetValue()
                has_twinkle = row["flicker_cb"].GetValue()

                explosions_list.append(
                    CompoundTag({
                        "colors": IntArrayTag(colors),
                        "fade_colors": IntArrayTag(fade_colors),
                        "shape": StringTag(shape),
                        "has_trail": ByteTag(1 if has_trail else 0),
                        "has_twinkle": ByteTag(1 if has_twinkle else 0)
                    })
                )

            # Save back to components NBT
            components["minecraft:fireworks"] = CompoundTag({
                "explosions": explosions_list,
                "flight_duration": ByteTag(flight_input.GetValue())
            })

            print(components)
            self.parent.set_components(components)
            # frame.Close()

        save_btn.Bind(wx.EVT_BUTTON, save_fireworks)
        btn_sizer.Add(add_btn, 0, wx.ALL, 5)
        btn_sizer.Add(save_btn, 0, wx.ALL, 5)
        main_sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER)

        # Prefill from existing NBT explosions
        for explosion_tag in fw_tag.get("explosions", ListTag()):
            add_explosion(explosion_tag)

        if not explosion_rows:
            add_explosion()

        scroll_panel.FitInside()
        frame.Layout()
        frame.Centre()
        frame.Show()

    def edit_add_armor_trims(self, parent, components):
        # --- Ensure components is always safe to use ---
        self.components = components
        if not self.components or not hasattr(self.components, "get"):
            self.components = CompoundTag({})

        patterns = {
            "Sentry": "minecraft:sentry",
            "Vex": "minecraft:vex",
            "Wild": "minecraft:wild",
            "Coast": "minecraft:coast",
            "Dune": "minecraft:dune",
            "Wayfinder": "minecraft:wayfinder",
            "Raiser": "minecraft:raiser",
            "Shaper": "minecraft:shaper",
            "Host": "minecraft:host",
            "Ward": "minecraft:ward",
            "Silence": "minecraft:silence",
            "Tide": "minecraft:tide",
            "Snout": "minecraft:snout",
            "Rib": "minecraft:rib",
            "Eye": "minecraft:eye",
            "Spire": "minecraft:spire",
            "Bolt": "minecraft:bolt",
            "Flow": "minecraft:flow"
        }

        materials = {
            "Amethyst": "minecraft:amethyst",
            "Copper": "minecraft:copper",
            "Diamond": "minecraft:diamond",
            "Emerald": "minecraft:emerald",
            "Gold": "minecraft:gold",
            "Iron": "minecraft:iron",
            "Lapis": "minecraft:lapis_lazuli",
            "Netherite": "minecraft:netherite",
            "Redstone": "minecraft:redstone",
            "Quartz": "minecraft:quartz",
            "Resin": "minecraft:resin"
        }

        standard_colors = [
            ("Black", 1973019), ("Red", 11743532), ("Green", 3887386),
            ("Brown", 5320730), ("Blue", 2437522), ("Purple", 8073150),
            ("Cyan", 2651799), ("Light Gray", 11250603), ("Gray", 4408131),
            ("Pink", 14188952), ("Lime", 4312372), ("Yellow", 14602026),
            ("Light Blue", 6719955), ("Magenta", 12801229), ("Orange", 15435844),
            ("White", 15790320)
        ]

        def java_color_to_rgb(color_int):
            r = (color_int >> 16) & 0xFF
            g = (color_int >> 8) & 0xFF
            b = color_int & 0xFF
            return r, g, b

        def rgb_to_java_color(r, g, b):
            return (r << 16) | (g << 8) | b

        # --- Setup GUI ---
        panel = wx.Frame(parent, title="Edit Armor Trim", size=(420, 360),
                         style=wx.DEFAULT_FRAME_STYLE | wx.STAY_ON_TOP)
        sizer = wx.BoxSizer(wx.VERTICAL)

        # === CLEAR BUTTON ===
        remove_all_btn = wx.Button(panel, label="Clear Trim and Color")

        def on_remove_all(evt):
            self.components.pop('minecraft:trim', None)
            self.components.pop('minecraft:dyed_color', None)
            self.parent.set_components(self.components)
            panel.Close()

        remove_all_btn.Bind(wx.EVT_BUTTON, on_remove_all)
        sizer.Add(remove_all_btn, 0, wx.ALL | wx.EXPAND, 8)

        # === PATTERN SELECTION ===
        sizer.Add(wx.StaticText(panel, label="Select Trim Pattern:"), 0, wx.ALL, 5)
        trim_choice = wx.Choice(panel, choices=list(patterns.keys()))

        current_pattern = self.components.get('minecraft:trim', {}).get('pattern', StringTag('')).py_str
        if current_pattern in patterns.values():
            name = next((k for k, v in patterns.items() if v == current_pattern), None)
            if name:
                trim_choice.SetStringSelection(name)
        sizer.Add(trim_choice, 0, wx.ALL | wx.EXPAND, 5)

        # === MATERIAL SELECTION ===
        sizer.Add(wx.StaticText(panel, label="Select Trim Material:"), 0, wx.ALL, 5)
        material_choice = wx.Choice(panel, choices=list(materials.keys()))

        current_material = self.components.get('minecraft:trim', {}).get('material', StringTag('')).py_str
        if current_material in materials.values():
            name = next((k for k, v in materials.items() if v == current_material), None)
            if name:
                material_choice.SetStringSelection(name)
        sizer.Add(material_choice, 0, wx.ALL | wx.EXPAND, 5)

        # === LEATHER COLOR SECTION ===
        current_item = self.parent.get_item_id()
        current_color = self.components.get("minecraft:dyed_color", IntTag(0)).py_int

        if "leather" in current_item:
            sizer.Add(wx.StaticText(panel, label="Leather Color:"), 0, wx.ALL, 5)
            color_row = wx.BoxSizer(wx.HORIZONTAL)

            color_choice = wx.Choice(panel, choices=[c[0] for c in standard_colors])
            color_row.Add(color_choice, 1, wx.RIGHT, 5)

            color_preview = wx.Button(panel, label="", size=(30, 25))
            color_row.Add(color_preview, 0, wx.RIGHT, 5)

            color_picker_btn = wx.Button(panel, label="Custom...")
            color_row.Add(color_picker_btn, 0, wx.RIGHT, 5)
            sizer.Add(color_row, 0, wx.ALL | wx.EXPAND, 5)

            def set_preview_from_int(color_int):
                r, g, b = java_color_to_rgb(color_int)
                color_preview.SetBackgroundColour(wx.Colour(r, g, b))
                color_preview.Refresh()

            def open_color_picker(evt):
                dlg = wx.ColourDialog(panel)
                dlg.GetColourData().SetChooseFull(True)
                if dlg.ShowModal() == wx.ID_OK:
                    col = dlg.GetColourData().GetColour()
                    rgb_int = rgb_to_java_color(col.Red(), col.Green(), col.Blue())
                    self.components['minecraft:dyed_color'] = IntTag(rgb_int)
                    set_preview_from_int(rgb_int)
                    color_choice.SetSelection(-1)
                dlg.Destroy()

            def on_select_standard(evt):
                idx = color_choice.GetSelection()
                if idx != wx.NOT_FOUND:
                    _, value = standard_colors[idx]
                    self.components['minecraft:dyed_color'] = IntTag(value)
                    set_preview_from_int(value)

            color_picker_btn.Bind(wx.EVT_BUTTON, open_color_picker)
            color_choice.Bind(wx.EVT_CHOICE, on_select_standard)

            # Preload color
            if current_color:
                match = next((name for name, val in standard_colors if val == current_color), None)
                if match:
                    color_choice.SetStringSelection(match)
                set_preview_from_int(current_color)
            else:
                set_preview_from_int(15790320)  # default white

        # === SAVE BUTTON ===
        def save_data(evt):
            selected_pattern = trim_choice.GetStringSelection()
            selected_material = material_choice.GetStringSelection()
            pattern_key = patterns.get(selected_pattern)
            material_key = materials.get(selected_material)



            # Ensure we are updating existing tag, not replacing
            if not isinstance(self.components, CompoundTag):
                self.components = CompoundTag({})
            if (selected_pattern and not selected_material) or (selected_material and not selected_pattern):
                print("Error: Both trim pattern and material must be selected together.")
                return
            else:# Always set trim
                self.components['minecraft:trim'] = CompoundTag({
                    'material': StringTag(material_key),
                    'pattern': StringTag(pattern_key)
                })

            # Handle color if applicable
            if "leather" in current_item:
                idx = color_choice.GetSelection()
                if idx != wx.NOT_FOUND:
                    _, value = standard_colors[idx]
                    self.components['minecraft:dyed_color'] = IntTag(value)
                elif 'minecraft:dyed_color' not in self.components:
                    # keep custom if chosen manually
                    pass
            else:
                # Clean up color if switching from leather to non-leather
                self.components.pop('minecraft:dyed_color', None)

            print("Saved Trim and Color:", self.components)
            self.parent.set_components(self.components)
            panel.Close()

        save_button = wx.Button(panel, label="Save Changes")
        save_button.Bind(wx.EVT_BUTTON, save_data)
        sizer.Add(save_button, 0, wx.ALL | wx.ALIGN_CENTER, 10)

        panel.SetSizer(sizer)
        panel.Centre()
        panel.Fit()
        panel.Show()

COPY_DATA = None
class DropMenu:
    """Handles creation of item and category menus for inventory buttons."""

    def __init__(self, parent, resources, on_item_selected, categories=None, components=None):
        """
        :param parent: wx.Window or panel that owns the menu (for event binding)
        :param resources: Object with get_items_id, get_icon_cache, data, etc.
        :param on_item_selected: Callback when a menu item is chosen (fn(event, id))
        :param categories: Optional categories dictionary for menu structure
        """
        self.parent = parent
        self.resources = resources
        self.on_item_selected = on_item_selected
        self.categories = categories or {}
        self.tools = ItemTools(parent)
        self.components = components

    # ──────────────────────────────────────────────
    # Menu Creation Helpers
    # ──────────────────────────────────────────────

    def build_menu_items(self, menu, item_ids):
        """Create and append menu items (with icons) to the given menu."""
        for item_id in item_ids:
            if not (0 <= item_id < len(self.resources.get_items_id)):
                continue

            item_name = self.resources.get_items_id[item_id]
            display_name = self.resources.data.get(item_name, {}).get('display_name', item_name)
            icon_bitmap = self.resources.get_icon_cache.get(item_name, wx.NullBitmap)

            menu_item = wx.MenuItem(menu, wx.ID_ANY, display_name)
            if icon_bitmap and icon_bitmap.IsOk():
                menu_item.SetBitmap(icon_bitmap)
            menu.Append(menu_item)

            self.parent.Bind(
                wx.EVT_MENU,
                lambda e, bid=item_name: self.on_item_selected(e, bid),
                menu_item
            )

    def build_menu_items_from_id(self, menu, item_ids):
        for item_name in item_ids:
            # Safety check in case the ID isn't in resources
            if item_name not in self.resources.data:
                continue

            display_name = self.resources.data[item_name].get('display_name', item_name)
            icon_bitmap = self.resources.get_icon_cache.get(item_name, wx.NullBitmap)

            menu_item = wx.MenuItem(menu, wx.ID_ANY, display_name)
            if icon_bitmap and icon_bitmap.IsOk():
                menu_item.SetBitmap(icon_bitmap)
            menu.Append(menu_item)

            self.parent.Bind(
                wx.EVT_MENU,
                lambda e, bid=item_name: self.on_item_selected(e, bid),
                menu_item
            )

    def expand_ids(self, id_ranges):
        """Expand a list of IDs or (start, end) tuples into a flat list of IDs."""
        expanded = []
        for item in id_ranges:
            if isinstance(item, tuple):
                expanded.extend(range(item[0], item[1] + 1))
            elif isinstance(item, range):
                expanded.extend(item)
            else:
                expanded.append(item)
        return expanded
    # ──────────────────────────────────────────────
    # Main Menu Building
    # ──────────────────────────────────────────────
    def add_category_menus(self, parent_menu):
        """Create hierarchical menus from the provided 'categories' dictionary."""
        for group_name, group_data in self.categories.items():
            group_menu = wx.Menu()
            parent_menu.AppendSubMenu(group_menu, group_name)

            if isinstance(group_data, dict):
                if len(group_data) == 1:
                    _, id_ranges = next(iter(group_data.items()))
                    self.build_menu_items(group_menu, self.expand_ids(id_ranges))
                else:
                    for cat_name, id_ranges in group_data.items():
                        sub_menu = wx.Menu()
                        group_menu.AppendSubMenu(sub_menu, cat_name)
                        self.build_menu_items(sub_menu, self.expand_ids(id_ranges))
            else:
                self.build_menu_items(group_menu, self.expand_ids(group_data))

    def handle_offhand(self, parent_menu):
        """Create a predefined 'offhand' submenu with categorized items."""
        offhand_categories = {
            "Arrows": [
                "arrow",
                "tipped_arrow",
                "spectral_arrow",
            ],
            "More Arrows": [
                "firework_rocket",
                "torch",
                "trident",
            ],
            "Most Used (may not work)": [
                "shield",
                "crossbow",
                "totem_of_undying",
            ],
        }

        for name, item_ids in offhand_categories.items():
            submenu = wx.Menu()
            self.build_menu_items_from_id(submenu, item_ids)
            parent_menu.AppendSubMenu(submenu, name)
    def handle_head(self, parent_menu):
        """Create a predefined 'head' menu with helmets and wearable blocks."""
        head = [
            # Helmets
            "leather_helmet",
            "chainmail_helmet",
            "copper_helmet",
            "iron_helmet",
            "golden_helmet",
            "diamond_helmet",
            "netherite_helmet",
            "turtle_helmet",

            # Wearable Blocks
            "carved_pumpkin",
            "player_head",
            "skeleton_skull",
            "wither_skeleton_skull",
            "zombie_head",
            "creeper_head",
            "dragon_head",
            "piglin_head",
        ]
        self.build_menu_items_from_id(parent_menu, head)

    def handle_chest(self, parent_menu):
        """Create a predefined 'chest' menu with chestplates and elytra."""
        chest = [
            "leather_chestplate",
            "chainmail_chestplate",
            "copper_chestplate",
            "iron_chestplate",
            "golden_chestplate",
            "diamond_chestplate",
            "netherite_chestplate",
            "elytra",
        ]

        self.build_menu_items_from_id(parent_menu, chest)
    def handle_legs(self, parent_menu):
        """Create a predefined 'legs' menu with leggings."""
        legs = [
            "leather_leggings",
            "chainmail_leggings",
            "copper_leggings",
            "iron_leggings",
            "golden_leggings",
            "diamond_leggings",
            "netherite_leggings",
        ]

        self.build_menu_items_from_id(parent_menu, legs)
    def handle_feet(self, parent_menu):
        """Create a predefined 'feet' menu with boots."""
        feet = [
            "leather_boots",
            "chainmail_boots",
            "copper_boots",
            "iron_boots",
            "golden_boots",
            "diamond_boots",
            "netherite_boots",
        ]

        self.build_menu_items_from_id(parent_menu, feet)

    def update_main_menu(self, parent_menu, total_items):
        """Add flat list of item IDs directly to menu."""
        if not total_items:
            return
        self.build_menu_items(parent_menu, total_items)

    # ──────────────────────────────────────────────
    # Menu Display
    # ──────────────────────────────────────────────
    def open_left_click(self, event, button_slot=None, total_items=None):
        menu = wx.Menu()
        button = event.GetEventObject().GetParent()
        container_types = CONTAINERS_TYPE_2_PATH.keys()
        item_id = button.get_item_id()

        def add_menu_item(label, callback):
            """Helper to append a menu item and bind it."""
            mi = wx.MenuItem(menu, wx.ID_ANY, label)
            menu.Append(mi)
            self.parent.Bind(wx.EVT_MENU, callback, mi)

        if item_id:
            add_menu_item("Edit Name and Lore",
                          lambda e: self.tools.edit_name_lore(self.parent, self.components))
            if self.components:
                add_menu_item("Edit Components",
                          lambda e: self.tools.edit_tag(self.parent, self.components))

            if 'firework' in item_id:
                add_menu_item("Edit Fireworks",
                              lambda e: self.tools.edit_fireworks_data(self.parent, self.components))

            if any(t in item_id for t in [
                "pickaxe", "axe", "shovel", "hoe", "trident",
                "helmet", "leggings", "chestplate", "boots",
                "chainmail", "sword", "elytra", "mace", "brush", 'shield', 'bow']):
                add_menu_item("Edit Enchants",
                              lambda e: self.tools.edit_enchants(self.parent, self.components))

            if 'banner' in item_id or 'shield' in item_id:
                add_menu_item("Edit Banner",
                              lambda e: self.tools.banner_editor(self.parent, self.components))

            if any(x in item_id for x in container_types) and 'chestplate' not in item_id:
                add_menu_item("Open Container",
                              lambda e: self.parent.load_container(button))

            if any(x in item_id for x in ["leggings", "helmet", "chestplate", "boots"]):
                add_menu_item("Edit Trims",
                              lambda e: self.tools.edit_add_armor_trims(self.parent, self.components))

            # Copy
            add_menu_item("Copy", self.copy_)

            # Delete
            menu.AppendSeparator()
            add_menu_item("Delete", self.delete)

        # Paste (global)
        if COPY_DATA:
            add_menu_item("Paste", self.paste_)

        self.update_main_menu(menu, total_items)
        self.parent.PopupMenu(menu)
        menu.Destroy()

    def open(self, event, button_slot=None, total_items=None):
        """Open a context menu depending on button slot or category data."""
        menu = wx.Menu()
        large_menu_item = wx.MenuItem(menu, wx.ID_ANY, "🟦🟦 LARGE MENU 🟦🟦")
        menu.Append(large_menu_item)
        button = event.GetEventObject().GetParent()
        # Bind the top item to open catalog if needed

        self.parent.Bind(wx.EVT_MENU, lambda e: self.resources.toggle_catalog(self.parent, self.resources),
                  id=large_menu_item.GetId())

        if button_slot == 'offhand':
            self.handle_offhand(menu)
        elif button_slot == 'head':
            self.handle_head(menu)
        elif button_slot == 'chest':
            self.handle_chest(menu)
        elif button_slot == 'legs':
            self.handle_legs(menu)
        elif button_slot == 'feet':
            self.handle_feet(menu)
        elif self.categories:
            self.add_category_menus(menu)

        self.update_main_menu(menu, total_items)
        self.parent.PopupMenu(menu)
        menu.Destroy()

    def copy_(self, event):
        """Copy the data from this button."""
        global COPY_DATA
        button = self.parent  # the button being copied
        tooltip = button.GetToolTip()
        COPY_DATA = {
            "tool_tip": tooltip.GetTip() if tooltip else "",  # safe even if no tooltip
            "bitmap": button.GetBitmap(),
            "item_id": button.get_item_id(),
            "count": button.get_count(),
            "components": button.get_components()
        }
        # print("Copied:", COPY_DATA)

    def paste_(self, event):
        """Paste the previously copied data onto this button."""
        global COPY_DATA
        if not COPY_DATA:
            print("Nothing to paste.")
            return

        button = self.parent  # the button to paste onto
        data = COPY_DATA

        # Set bitmap (label can stay blank)
        button.SetBitmap(data.get("bitmap", wx.NullBitmap), data.get("tool_tip", ""))

        # Set tooltip
        button.set_item_id(data.get("item_id"))
        button.set_count(data.get("count", 0))
        button.set_components(data.get("components"))

        button.Refresh()
        button.Update()
        print("Pasted:", data)

    def delete(self, event):
        button = self.parent  # now it's the actual button
        button.SetBitmap(wx.NullBitmap, " ")
        button.set_item_id(None)
        button.set_count(0)
        button.set_components(None)

        button.Refresh()
        button.Update()

class IconButton(wx.Panel):
    def __init__(self, parent, slot="", label="", include_text=True):
        super().__init__(parent)
        self.resources = IconResources()
        self.total_items = 0
        self.container_window = None
        self.icon_window_open = False
        self.the_over_button = None
        self.components = None
        self.left_down = False
        self.is_mouse_down = False
        self.motion_fired = False
        self.dragged_index = None
        self.dragged_id = None
        self.drag_image = None
        self.dragging = False
        vbox = wx.BoxSizer(wx.VERTICAL)

        # Main button
        self.button = wx.Button(self, label=label, size=(80, 80))
        self.button.slot = slot
        self.item_id = None

        vbox.Add(self.button, 0, wx.ALIGN_CENTER | wx.ALL, 2)


        if 'save' in slot:

            self.button.Bind(wx.EVT_BUTTON, self.save_data)
            save_bmp = wx.ArtProvider.GetBitmap(wx.ART_FILE_SAVE, wx.ART_TOOLBAR, (80, 80))
            self.button.SetBitmap(save_bmp)
            self.button.SetToolTip(wx.ToolTip("Save"))
        elif 'ender' in slot:
            self.button.Bind(wx.EVT_BUTTON, self.open_ender)
            icon = self.resources.get_scaled_cache['ender_chest']
            self.button.SetBitmap(icon)
            self.button.SetToolTip(wx.ToolTip("Ender Chest"))
        else:
            self.button.Bind(wx.EVT_MOUSE_EVENTS, self.mouse_events)

        # Small text field at bottom
        if include_text:
            self.text_ctrl = wx.TextCtrl(
                self, value="0", size=(40, 30), style=wx.TE_CENTER
            )
            vbox.Add(self.text_ctrl, 0, wx.ALIGN_CENTER | wx.TOP, 2)
            self.font = wx.Font(14, wx.FONTFAMILY_ROMAN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
            self.text_ctrl.SetFont(self.font)
        else:
            self.text_ctrl = None

        self.SetSizer(vbox)
    def hide_text_box(self):
        self.text_ctrl.Hide()

    def set_count(self, cnt):
        self.text_ctrl.SetValue(str(cnt))

    def get_count(self):
        if hasattr(self, 'text_ctrl') and self.text_ctrl is not None:
            try:
                return int(self.text_ctrl.GetValue())
            except ValueError:
                return 0
        # Fallback if no text_ctrl exists
        return 0

    def save_data(self, event):
        frame = self.GetTopLevelParent()
        parent_button = getattr(frame, 'parent_icon_button', None)

        # Use existing components if available, otherwise create fresh
        if parent_button and parent_button.get_components():
            components = parent_button.get_components()
        else:
            components = CompoundTag()

        # Prepare clean container list (don’t pre-create it)
        container_list = ListTag([])
        data_nbt = ListTag([])
        equipment = CompoundTag({})
        ender_data = ListTag([])  # For Ender Chest items
        bundle_data = ListTag([])
        # Helper for consistent ID handling
        def safe_item_id(raw_id):
            if not raw_id:
                return None
            return raw_id if ':' in raw_id else 'minecraft:' + raw_id

        for child in self.GetParent().GetChildren():
            if not isinstance(child, IconButton):
                continue

            title = child.GetParent().GetParent().GetTitle()
            slot_name = getattr(child.button, 'slot', None)
            if not slot_name:
                continue

            try:
                count = int(child.get_count()) if child.get_count() else 0
            except Exception:
                count = 0

            # Skip reserved slots
            if slot_name == "save":
                continue

            try:
                raw_id = child.get_item_id()
            except Exception:
                raw_id = None
            item_id_str = safe_item_id(raw_id)

            # --- INVENTORY SECTION ---
            if title == 'Inventory':
                if count > 0 and item_id_str:
                    if 'Slot' in slot_name:
                        item = CompoundTag({
                            'count': IntTag(count),
                            'id': StringTag(item_id_str),
                            'Slot': ByteTag(slot_name.split('_')[1])
                        })
                        if getattr(child, 'components', None):
                            item['components'] = child.components
                        data_nbt.append(item)
                    else:
                        eq = CompoundTag({
                            'count': IntTag(count),
                            'id': StringTag(item_id_str)
                        })
                        if getattr(child, 'components', None):
                            eq['components'] = child.components
                        equipment[slot_name] = eq

            # --- CONTAINER SECTION ---
            elif title == 'container':
                if count > 0 and item_id_str:
                    container_item = CompoundTag({
                        'item': CompoundTag({
                            'count': IntTag(count),
                            'id': StringTag(item_id_str)
                        }),
                        'slot': ByteTag(slot_name.split('_')[1])
                    })
                    if getattr(child, 'components', None):
                        container_item['item']['components'] = child.components
                    container_list.append(container_item)
            elif title == 'dispenser':
                if count > 0 and item_id_str:
                    container_item = CompoundTag({
                        'item': CompoundTag({
                            'count': IntTag(count),
                            'id': StringTag(item_id_str)
                        }),
                        'slot': ByteTag(slot_name.split('_')[1])
                    })
                    if getattr(child, 'components', None):
                        container_item['item']['components'] = child.components
                    container_list.append(container_item)
            # --- ENDER CHEST SECTION ---
            elif title.lower() == 'ender':
                if count > 0 and item_id_str:
                    ender_item = CompoundTag({
                        'count': IntTag(count),
                        'id': StringTag(item_id_str),
                        'Slot': ByteTag(slot_name.split('_')[1])
                    })
                    if getattr(child, 'components', None):
                        ender_item['components'] = child.components
                    ender_data.append(ender_item)
            elif title.lower() == 'bundle':
                if count > 0 and item_id_str:
                    bundle_item = CompoundTag({
                        'count': IntTag(count),
                        'id': StringTag(item_id_str),

                    })
                    if getattr(child, 'components', None):
                        bundle_item['components'] = child.components
                    bundle_data.append(bundle_item)
        # ✅ Only set minecraft:container if there’s at least one item
        if len(container_list) > 0:
            components['minecraft:container'] = container_list
        elif 'minecraft:container' in components:
            del components['minecraft:container']
        if len(bundle_data) > 0:
            components['minecraft:bundle_contents'] = bundle_data
        elif 'minecraft:bundle_contents' in components:
            del components['minecraft:bundle_contents']
        # Update the parent icon button if this is a nested container
        if parent_button:
            parent_button.set_components(components)

        if title.lower() == 'inventory':
            frame.player_data['Inventory'].clear()
            frame.player_data['Inventory'].extend(data_nbt)
            frame.player_data['equipment'] = CompoundTag()
            frame.player_data['equipment'].update(equipment)
            frame.player_data.save()
        if title.lower() == 'ender':

            if not isinstance(frame.player_data['EnderItems'], ListTag):
                frame.player_data['EnderItems'] = ListTag([], 10)  # 10 = Compound

            # Replace or update its contents
            frame.player_data['EnderItems'].clear()
            frame.player_data['EnderItems'].extend(ender_data)

        # Finally save the player
            frame.player_data.save()
        # Debug
        # print("SAVED INVENTORY:", data_nbt)
        # print("SAVED EQUIPMENT:", equipment)
        # print("SAVED ENDER:", ender_data)
        # if parent_button:
        #     print("SAVED CONTAINER:", components)
    def open_ender(self, _):
        frame = self.GetTopLevelParent()
        ender = InventoryFrame(self,  title="ender", size=(880, 600), ender=frame.ender, player_data=frame.player_data)
        ender.Show()
        print('OPened Ender')

    def SetBitmap(self, icon, display_name):
        self.display_name = display_name

        if icon and icon.IsOk() or icon == wx.NullBitmap:
            self.button.SetBitmap(icon)

        self.button.SetToolTip(wx.ToolTip(self.display_name))

    def GetBitmap(self):
        icon = self.button.GetBitmap()
        return icon

    def on_menu_item_selected(self, event, item_id):
        """Handle item selection from any menu."""
        self.namespace = 'minecraft:'
        self.item_id = item_id
        self.set_components(None)
        icon = self.resources.get_scaled_cache[self.item_id]
        display_name = self.resources.data[self.item_id].get('display_name', self.item_id)
        # Detect if Shift is down using wx.GetKeyState
        if wx.GetKeyState(wx.WXK_SHIFT):
            self.set_count(64)
        else:
            self.set_count(1)

        if 'goat_horn' in self.item_id:
            if ':' not in self.item_id:
                self.set_components(goat_horn_components[0])
            else:
                self.set_components(goat_horn_components[int(self.item_id.split(":")[1])])
        elif 'enchanted_book' in self.item_id:
            enchant = enchanted_books[self.item_id][:-2]
            lvl = enchanted_books[self.item_id][-1:]
            self.set_components(
                CompoundTag({"minecraft:stored_enchantments": CompoundTag({enchant: IntTag(int(lvl))})})
            )
        elif 'firework_rocket' in self.item_id:
            color = firework_colors[self.item_id]
            self.set_components(
                CompoundTag({"minecraft:fireworks":
                    CompoundTag({'explosions': ListTag([CompoundTag(
                        {'colors': IntArrayTag([color]),
                         'fade_colors': IntArrayTag([]),
                         'shape': StringTag("small_ball"),
                         'has_trail': ByteTag(0), 'has_twinkle':
                             ByteTag(0)})], 10), 'flight_duration': ByteTag(1)})}))
        elif 'firework_star' in self.item_id:
            color = firework_star_colors[self.item_id]  # replace for lookup
            self.set_components(
                CompoundTag({'minecraft:firework_explosion':
                                 CompoundTag({'has_trail': ByteTag(0), 'shape': StringTag("small_ball"),
                                              'colors': ListTag([IntTag(color)]), 'has_twinkle': ByteTag(0)})}))
        elif 'potion' in self.item_id:
            effect = potion_to_java[self.item_id.replace("lingering_", "").replace("splash_", "")]  # replace for lookup
            self.set_components(
                CompoundTag({'minecraft:potion_contents': CompoundTag({'potion': StringTag(effect)})}))
        elif 'arrow' in self.item_id:
            print(self.item_id)
            effect = arrow_potions.get(self.item_id, None)  # replace for lookup
            if effect:
                self.set_components(
                    CompoundTag({'minecraft:potion_contents': CompoundTag({'potion': StringTag(effect)})}))
                self.set_item_id('tipped_arrow')
        self.SetName(self.item_id.split(':')[0])
        self.set_item_id(self.item_id.split(':')[0])# TEST
        self.SetBitmap(icon, display_name)
        self.Refresh()
    def load_container(self, icon_button):
        container_id = icon_button.get_item_id()
        slot_count = 27
        bundle = False
        if 'dispenser' in  container_id:

            if icon_button.get_components():
                components = icon_button.get_components()

                self.container_window = InventoryFrame(self, title="dispenser", size=(400, 550),
                                                       container=components['minecraft:container'],
                                                       icon_button=icon_button)
            else:
                self.container_window = InventoryFrame(self, title="dispenser", size=(400, 550), container=ListTag([]),
                                                       icon_button=icon_button)

            self.container_window.Show()

        elif 'bundle' in  container_id:
            if icon_button.get_components():
                components = icon_button.get_components()

                self.container_window = InventoryFrame(self, title="bundle", size=(800, 550),
                                                       container=components['minecraft:bundle_contents'],
                                                       icon_button=icon_button)
            else:
                self.container_window = InventoryFrame(self, title="bundle", size=(800, 550), container=ListTag([]),
                                                       icon_button=icon_button)

            self.container_window.Show()
        else:
            if icon_button.get_components():
                components = icon_button.get_components()

                self.container_window = InventoryFrame(self, title="container", size=(880, 600),container=components['minecraft:container'], icon_button=icon_button)
            else:
                self.container_window = InventoryFrame(self, title="container", size=(880, 600), container=ListTag([]), icon_button=icon_button)

            self.container_window.Show()

    def mouse_events(self, event):
        """Unified mouse event handler for right-click menu and drag-drop."""

        button = event.GetEventObject()
        # ---------------- Right-click menu ----------------
        if event.RightDown():
            drop_menu = DropMenu(
                parent=self,
                resources=self.resources,
                on_item_selected=self.on_menu_item_selected,
                categories=categories,
                components = self.get_components()
            )
            drop_menu.open(event, button_slot=getattr(self.button, 'slot', None), total_items=self.total_items)
            event.Skip()
            return

        # ---------------- Left down ----------------
        if event.LeftDown():
            self.left_down = True
            self.dragging = False
            self.drag_image = None
            self.drag_start_pos = event.GetPosition()
            self.button = button
            self.the_over_button = None
            event.Skip()
            return

        # ---------------- Dragging ----------------
        if event.Dragging() and self.left_down:
            pos = event.GetPosition()

            if not self.dragging:
                dx = abs(pos.x - self.drag_start_pos.x)
                dy = abs(pos.y - self.drag_start_pos.y)
                if dx < 3 and dy < 3:
                    # Too small movement — still a click
                    event.Skip()
                    return

                image = getattr(self.button, "GetBitmap", lambda: None)()
                if not image or not image.IsOk():
                    event.Skip()
                    return

                try:
                    self.drag_image = wx.DragImage(image)
                    screen_pos = self.button.ClientToScreen(self.drag_start_pos)


                    # Correct BeginDrag signature:
                    # BeginDrag(hotSpot, window, fullScreen=False, useHardware=False)
                    if not self.drag_image.BeginDrag(screen_pos, self.button, fullScreen=True):
                        raise RuntimeError("BeginDrag failed")

                    self.drag_image.Move(screen_pos)
                    self.drag_image.Show()
                    self.dragging = True

                except Exception as e:
                    print("Drag image error:", e)
                    if getattr(self, "drag_image", None):
                        try:
                            self.drag_image.EndDrag()
                        except Exception:
                            pass
                    self.drag_image = None
                    self.dragging = False
                    event.Skip()
                    return

            # Move drag image while dragging
            if self.dragging and self.drag_image:
                try:
                    screen_pos = self.button.ClientToScreen(pos)
                    self.drag_image.Move(screen_pos)

                    hovered = wx.FindWindowAtPoint(wx.GetMousePosition())
                    if hovered:
                        self.the_over_button = hovered
                except Exception as e:
                    print("Dragging error:", e)

            event.Skip()
            return

        # ---------------- Left Up ----------------
        if event.LeftUp():

            if self.dragging:
                # Finish drag

                if getattr(self, "drag_image", None):
                    try:
                        self.drag_image.Hide()
                        self.drag_image.EndDrag()
                    except Exception:
                        pass
                    self.drag_image = None
                parent_title = getattr(self.the_over_button.Parent, "GetTitle", lambda: None)()
                if parent_title == 'bundle':
                    self.handle_bundle()

                if isinstance(getattr(self, "the_over_button", None),
                              wx.Button) and self.the_over_button != self.button:
                    self.swap_button_contents(self.button, self.the_over_button)

                self.the_over_button = None
                self.dragging = False
                self.left_down = False
                event.Skip()
                return

            # Only open DropMenu if not dragging
            if self.left_down and not self.dragging:
                drop_menu = DropMenu(
                    parent=self,
                    resources=self.resources,
                    on_item_selected=self.on_menu_item_selected,
                    categories=categories,
                    components=self.get_components()
                )
                drop_menu.open_left_click(
                    event,
                    button_slot=getattr(self.button, 'slot', None),
                    total_items=self.total_items
                )

            self.left_down = False
            self.dragging = False
            event.Skip()
            return

    def swap_button_contents(self, source_btn, target_btn):
        """Swap or move icons, tooltips, parent data, and components between two inventory buttons.
        - In bundle windows: remove source button if target has no data.
        - In non-bundle windows: clear source button if target has no data.
        """

        source_ib = source_btn.GetParent()
        target_ib = target_btn.GetParent()

        # --- Fetch all relevant data safely ---
        icon1 = source_btn.GetBitmap()
        tip1 = source_btn.GetToolTip()
        count1 = source_ib.get_count()
        item1 = source_ib.get_item_id()
        components1 = getattr(source_ib, "get_components", lambda: None)()

        icon2 = target_btn.GetBitmap()
        tip2 = target_btn.GetToolTip()
        count2 = target_ib.get_count()
        item2 = target_ib.get_item_id()
        components2 = getattr(target_ib, "get_components", lambda: None)()

        def safe_text(tip):
            return tip.GetTip() if tip else "empty"

        # --- Perform swap / move ---
        wx.CallAfter(target_btn.SetBitmap, icon1 if icon1 and icon1.IsOk() else wx.NullBitmap)
        wx.CallAfter(target_btn.SetToolTip, wx.ToolTip(safe_text(tip1)))
        wx.CallAfter(target_ib.set_count, count1)
        wx.CallAfter(target_ib.set_item_id, item1)
        if hasattr(target_ib, "set_components"):
            wx.CallAfter(target_ib.set_components, components1)

        wx.CallAfter(source_btn.SetBitmap, icon2 if icon2 and icon2.IsOk() else wx.NullBitmap)
        wx.CallAfter(source_btn.SetToolTip, wx.ToolTip(safe_text(tip2)))
        wx.CallAfter(source_ib.set_count, count2)
        wx.CallAfter(source_ib.set_item_id, item2)
        if hasattr(source_ib, "set_components"):
            wx.CallAfter(source_ib.set_components, components2)

        # --- Determine window type ---
        parent_frame = self.GetTopLevelParent()
        is_bundle_window = "bundle" in parent_frame.GetTitle().lower()

        # --- Handle bundle or non-bundle behavior ---
        if is_bundle_window:
            # Moving TO a bundle window
            print(f"[ BUNDLE] item2={item2}")
            if not item2:
                def remove_source_icon_button():
                    print("[BUNDLE] Removing source IconButton")
                    source_icon_button = source_btn.GetParent()
                    parent_sizer = source_icon_button.GetContainingSizer()
                    parent_panel = source_icon_button.GetParent()

                    if parent_sizer:
                        parent_sizer.Detach(source_icon_button)

                    source_icon_button.Destroy()

                    if parent_panel:
                        parent_panel.Layout()
                        top = parent_panel.GetTopLevelParent()
                        if top:
                            top.Layout()

                wx.CallAfter(remove_source_icon_button)

    def GetToolTip(self):
        return self.button.GetToolTip()

    def handle_bundle(self):
        """
        Create a new IconButton based on this button's data.
        Adds it to the bundle grid on the parent's scroll_panel.
        """

        parent_panel = self.the_over_button.Parent.scroll_panel  # The scroll panel where the bundle lives

        # --- Fetch all relevant data safely from this button ---
        icon = self.GetBitmap()
        tip = self.GetToolTip()
        count = getattr(self, "get_count", lambda: 0)()
        item_id = getattr(self, "get_item_id", lambda: None)()
        components = getattr(self, "get_components", lambda: None)()
        display_name = tip.GetTip() if tip else item_id or "empty"
        tooltip_text = tip.GetTip() if tip else display_name

        # --- Determine next slot index dynamically ---
        existing_indices = [
            int(k.split("_", 1)[1])
            for k in parent_panel.Parent.slot_map.keys()
            if k.startswith("Slot_") and k.split("_", 1)[1].isdigit()
        ]
        next_index = (max(existing_indices) + 1) if existing_indices else 0
        slot_name = f"Slot_{next_index}"

        # --- Ensure bundle grid exists ---
        if not hasattr(parent_panel.Parent, "bundle_grid") or parent_panel.Parent.bundle_grid is None:
            parent_panel.Parent.bundle_grid = wx.FlexGridSizer(rows=0, cols=3, hgap=5, vgap=5)
            parent_panel.Parent.bundle_grid.SetFlexibleDirection(wx.BOTH)
            parent_panel.Parent.bundle_grid.SetNonFlexibleGrowMode(wx.FLEX_GROWMODE_SPECIFIED)
            if parent_panel.GetSizer():
                parent_panel.GetSizer().Add(parent_panel.Parent.bundle_grid, 0, wx.ALIGN_CENTER | wx.TOP, 5)

        # --- Create the new button on the scroll_panel ---
        new_btn = IconButton(parent_panel, slot=slot_name)
        new_ib = new_btn

        # --- Copy visual and logical data safely ---
        wx.CallAfter(new_btn.SetBitmap, icon if icon and icon.IsOk() else wx.NullBitmap, display_name)
        wx.CallAfter(new_btn.SetToolTip, wx.ToolTip(tooltip_text))
        if hasattr(new_ib, "set_count"):
            wx.CallAfter(new_ib.set_count, count)
        if hasattr(new_ib, "set_item_id"):
            wx.CallAfter(new_ib.set_item_id, item_id)
        if components and hasattr(new_ib, "set_components"):
            wx.CallAfter(new_ib.set_components, components)
        if hasattr(new_ib, "set_display_name"):
            wx.CallAfter(new_ib.set_display_name, display_name)

        # --- Add the new button to the bundle grid ---
        parent_panel.Parent.bundle_grid.Add(new_btn, 0, wx.ALL, 5)

        # Track the new button in the correct slot_map
        parent_panel.Parent.slot_map[slot_name] = new_btn

        # Refresh layout
        parent_panel.Parent.bundle_grid.Layout()
        parent_panel.Layout()
        parent_panel.Parent.Layout()

        # --- 🔥 NEW: Remove or clear source button after move ---
        def remove_source_after_move():
            """Clear the source button after moving to a bundle."""
            print("[HANDLE_BUNDLE] Clearing source button (non-bundle → bundle move)")

            if hasattr(self, "set_count"):
                self.set_count(0)
            if hasattr(self, "set_item_id"):
                self.set_item_id(None)
            if hasattr(self, "set_components"):
                self.set_components(None)

            # Clear icon and tooltip
            self.SetBitmap(wx.NullBitmap, "")
            self.SetToolTip(wx.ToolTip("empty"))

            # Refresh layout
            parent = self.GetParent()
            if parent:
                parent.Layout()
            top = parent.GetTopLevelParent() if parent else None
            if top:
                top.Layout()

        wx.CallAfter(remove_source_after_move)

    def on_click(self, event):

        event.Skip()

    def set_components(self, nbt):
        self.components = nbt
    def get_components(self):
        return self.components
    def set_item_id(self, item_id):
        self.item_id = item_id
    def get_item_id(self):
        return self.item_id
class InventoryFrame(wx.Frame):
    def __init__(self, parent=None, title="Inventory", size=(880, 740), player_data=None,
                 inventory=ListTag([]), equipment=CompoundTag({}), ender=ListTag([]), container=ListTag([]), icon_button=None ):
        super().__init__(parent, title=title, size=size, style=wx.DEFAULT_FRAME_STYLE | wx.STAY_ON_TOP)
        self.parent = parent
        self.player_data = player_data
        self.parent_button = icon_button
        self.title = self.GetTitle()
        self.resources = IconResources()
        self.parent_icon_button = icon_button
        self.inventory = inventory
        self.equipment = equipment
        self.ender = ender
        self.container = container
        # Scrolled panel inside frame
        self.scroll_panel = wx.ScrolledWindow(self, style=wx.VSCROLL)
        self.scroll_panel.SetScrollRate(5, 5)

        bg_color = wx.Colour(88, 88, 88)
        self.SetBackgroundColour(bg_color)
        self.SetForegroundColour(bg_color)  # text matches background
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)

        menubar = wx.MenuBar()
        file_menu = wx.Menu()

        # 1. Predefined ID: wx.ID_OPEN
        file_menu.Append(wx.ID_OPEN, "Import Inventory\tCtrl+O", "Open a file")
        self.Bind(wx.EVT_MENU, self.on_open, id=wx.ID_OPEN)

        file_menu.Append(wx.ID_SAVE, "Export Inventory\tCtrl+S", "Save")
        self.Bind(wx.EVT_MENU, self.on_save, id=wx.ID_SAVE)

        # 2. Custom ID using NewIdRef
        self.items_id = wx.NewIdRef()
        file_menu.Append(self.items_id, "Show Large Items Menu\tCtrl+I", "Show Large items Menu")
        self.Bind(wx.EVT_MENU, self.on_items_menu, id=self.items_id)

        # 3. Set Game mode
        self.game_mode = wx.NewIdRef()
        file_menu.Append(self.game_mode, "Set Game Mode\tCtrl+Shift+G", "Set Game mode")
        self.Bind(wx.EVT_MENU, self._game_mode, id=self.game_mode)

        # 4. Custom ID using NewIdRef (Clear All)
        self.clear_id = wx.NewIdRef()
        file_menu.Append(self.clear_id, "Clear All\tCtrl+Shift+C", "Clear everything")
        self.Bind(wx.EVT_MENU, self.on_clear_all, id=self.clear_id)

        menubar.Append(file_menu, "&Menu")
        self.SetMenuBar(menubar)

        # Accelerator table
        accel_tbl = wx.AcceleratorTable([
            (wx.ACCEL_CTRL, ord('O'), wx.ID_OPEN),  # Open
            (wx.ACCEL_CTRL, ord('I'), self.items_id),  # Items Menu
            (wx.ACCEL_CTRL | wx.ACCEL_SHIFT, ord('C'), self.clear_id),  # Clear All
            (wx.ACCEL_CTRL | wx.ACCEL_SHIFT, ord('G'), self.game_mode),  # Game mode
        ])
        self.SetAcceleratorTable(accel_tbl)

        self.slot_map = {}
        self.grid_sizer = wx.BoxSizer(wx.VERTICAL)
        self.create_inventory_grid()

        main_sizer = wx.BoxSizer(wx.VERTICAL)
        main_sizer.Add(self.scroll_panel, 1, wx.EXPAND)
        self.SetSizer(main_sizer)

        self.Layout()
        self.Centre()
        self.Show()

    def _game_mode(self, event):
        player_modes = {
            0: 'Survival',
            1: 'Creative',
            2: 'Adventure',
            3: 'Spectator'
        }

        # Get current mode
        current_mode = int(self.player_data.get('playerGameType', IntTag(0)).py_int)

        # Create popup dialog
        dialog = wx.SingleChoiceDialog(
            self,
            message="Select the player's game mode:",
            caption="Player Game Mode",
            choices=[f"{v} ({k})" for k, v in player_modes.items()]
        )

        # Preselect current mode
        if current_mode in player_modes:
            dialog.SetSelection(current_mode)

        # Show the dialog
        if dialog.ShowModal() == wx.ID_OK:
            selection_index = dialog.GetSelection()
            selected_mode = list(player_modes.keys())[selection_index]

            # Save the selected mode
            self.player_data['playerGameType'] = IntTag(selected_mode)
            self.player_data.save()

            wx.MessageBox(
                f"Player mode set to {player_modes[selected_mode]} ({selected_mode}).",
                "Saved",
                wx.ICON_INFORMATION
            )

        dialog.Destroy()

    def on_open(self, event):
        with wx.FileDialog(self, "Open NBT file", wildcard="NBT files (*.nbt)|*.nbt",
                           style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as file_dialog:
            if file_dialog.ShowModal() == wx.ID_CANCEL:
                return

            pathname = file_dialog.GetPath()
            print(f"Opening file: {pathname}")
            custom_file = load(pathname, compressed=False, little_endian=True,
                 string_decoder=decode_java_mutf8).compound


            self.player_data['Inventory'] = custom_file['Inventory']
            self.player_data['EnderItems'] = custom_file['EnderItems']
            if custom_file.get('equipment'):
                 self.player_data['equipment'] = custom_file['equipment']


            self.player_data.save()
            self.Close()
            wx.MessageBox(
                f"Import Complete, Reopen player to see changes",
                "Import Complete ",
                wx.ICON_INFORMATION
            )

    def on_save(self, event):

        with wx.FileDialog(self, "Save NBT file", wildcard="NBT files (*.nbt)|*.nbt",
                           style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as file_dialog:
            if file_dialog.ShowModal() == wx.ID_CANCEL:
                return  # user cancelled

            pathname = file_dialog.GetPath()
            if not pathname.lower().endswith('.nbt'):
                pathname += '.nbt'


            custom_file = CompoundTag()
            custom_file['Inventory'] = self.player_data['Inventory']
            custom_file['EnderItems'] = self.player_data['EnderItems']
            if self.player_data.get('equipment'):
                custom_file['equipment'] = self.player_data['equipment']


            custom_file.save_to(pathname,compressed=False, little_endian=True,
                                  string_encoder=encode_java_mutf8)

            print(f"Saving file to: {pathname}")
            # TODO: Save your NBT file here
    def on_items_menu(self, event):
        self.icon_resources = IconResources()
        self.icon_resources.toggle_catalog(self.parent, self.icon_resources)

    def on_clear_all(self, event):
        """Clears all buttons except 'Save' and 'Ender' buttons."""
        # Iterate over all children (e.g., buttons) in the parent container
        for window in self.GetChildren():
            for child in window.GetChildren():
                # Only process wx.Button controls
                if isinstance(child, IconButton):
                    slot = child.button.slot
                    # Skip 'save' and 'ender' buttons
                    if slot in ("save", "ender"):
                        continue
                    child.SetBitmap(wx.NullBitmap, '')
                    if hasattr(child, "set_item_id"):
                        child.set_item_id(None)
                    if hasattr(child, "set_count"):
                        child.set_count(0)
                    if hasattr(child, "set_components"):
                        child.set_components(None)

                    # Refresh to update the UI immediately
                    child.Refresh()
                    child.Update()

    def create_inventory_grid(self):
        self.grid_sizer.Clear(True)  # clean rebuild
        row_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # ----- TOP ROW -----
        if 'Inventory' in self.title:
            for x in ['head', 'chest', 'legs', 'feet']:
                btn = IconButton(self.scroll_panel, slot=x)
                btn.hide_text_box()
                row_sizer.Add(btn, 0, wx.ALL, 5)
                self.slot_map[x] = btn

            row_sizer.AddSpacer(25)
            for x in ['save', 'ender']:
                btn = IconButton(self.scroll_panel, slot=x, include_text=False)
                row_sizer.Add(btn, 0, wx.ALL, 5)
                self.slot_map[x] = btn

            row_sizer.AddSpacer(25)
            btn = IconButton(self.scroll_panel, slot='offhand')
            row_sizer.Add(btn, 0, wx.ALL, 5)
            self.slot_map['offhand'] = btn

        self.grid_sizer.Add(row_sizer, 0, wx.ALIGN_CENTER | wx.TOP, 5)

        # ----- MAIN INVENTORY -----
        if 'Inventory' in self.title:
            for row_start in (9, 18, 27):
                row_sizer = wx.BoxSizer(wx.HORIZONTAL)
                for x in range(row_start, row_start + 9):
                    btn = IconButton(self.scroll_panel, slot=f"Slot_{x}")
                    row_sizer.Add(btn, 0, wx.ALL, 5)
                    self.slot_map[f"Slot_{x}"] = btn
                self.grid_sizer.Add(row_sizer, 0, wx.ALIGN_CENTER | wx.TOP, 5)

            # Divider + Hotbar
            self.grid_sizer.Add(wx.StaticLine(self.scroll_panel, style=wx.LI_HORIZONTAL),
                                0, wx.EXPAND | wx.TOP | wx.BOTTOM, 10)

            row_sizer = wx.BoxSizer(wx.HORIZONTAL)
            for x in range(0, 9):
                btn = IconButton(self.scroll_panel, slot=f"Slot_{x}")
                row_sizer.Add(btn, 0, wx.ALL, 5)
                self.slot_map[f"Slot_{x}"] = btn
            self.grid_sizer.Add(row_sizer, 0, wx.ALIGN_CENTER | wx.TOP, 5)

            self.load_player_inventory()

        elif 'ender' in self.title:
            row_sizer = wx.BoxSizer(wx.HORIZONTAL)
            for x in ['save']:
                btn = IconButton(self.scroll_panel, slot=x, include_text=False)
                row_sizer.Add(btn, 0, wx.ALL, 5)
                self.slot_map[x] = btn
            self.grid_sizer.Add(row_sizer, 0, wx.ALIGN_CENTER | wx.TOP, 5)

            for row_start in (0, 9, 18):
                row_sizer = wx.BoxSizer(wx.HORIZONTAL)
                for x in range(row_start, row_start + 9):
                    btn = IconButton(self.scroll_panel, slot=f"Slot_{x}")
                    row_sizer.Add(btn, 0, wx.ALL, 5)
                    self.slot_map[f"Slot_{x}"] = btn
                self.grid_sizer.Add(row_sizer, 0, wx.ALIGN_CENTER | wx.TOP, 5)

            self.load_ender_inventory()

        elif 'container' in self.title:
            row_sizer = wx.BoxSizer(wx.HORIZONTAL)
            for x in ['save']:
                btn = IconButton(self.scroll_panel, slot=x, include_text=False)
                row_sizer.Add(btn, 0, wx.ALL, 5)
                self.slot_map[x] = btn
            self.grid_sizer.Add(row_sizer, 0, wx.ALIGN_CENTER | wx.TOP, 5)

            for row_start in (0, 9, 18):
                row_sizer = wx.BoxSizer(wx.HORIZONTAL)
                for x in range(row_start, row_start + 9):
                    btn = IconButton(self.scroll_panel, slot=f"Slot_{x}")
                    row_sizer.Add(btn, 0, wx.ALL, 5)
                    self.slot_map[f"Slot_{x}"] = btn
                self.grid_sizer.Add(row_sizer, 0, wx.ALIGN_CENTER | wx.TOP, 5)

            self.load_container()
        elif 'dispenser' in self.title:
            # Optional top row / save button
            row_sizer = wx.BoxSizer(wx.HORIZONTAL)
            for x in ['save']:
                btn = IconButton(self.scroll_panel, slot=x, include_text=False)
                row_sizer.Add(btn, 0, wx.ALL, 5)
                self.slot_map[x] = btn
            self.grid_sizer.Add(row_sizer, 0, wx.ALIGN_CENTER | wx.TOP, 5)

            # 3x3 grid for dispenser (9 slots)
            for row_start in (0, 3, 6):
                row_sizer = wx.BoxSizer(wx.HORIZONTAL)
                for x in range(row_start, row_start + 3):
                    btn = IconButton(self.scroll_panel, slot=f"Slot_{x}")
                    row_sizer.Add(btn, 0, wx.ALL, 5)
                    self.slot_map[f"Slot_{x}"] = btn
                self.grid_sizer.Add(row_sizer, 0, wx.ALIGN_CENTER | wx.TOP, 5)

            # Load the dispenser container items into the buttons
            self.load_container()
        elif 'bundle' in self.title:
            # Optional top row / save button
            row_sizer = wx.BoxSizer(wx.HORIZONTAL)
            save_btn = IconButton(self.scroll_panel, slot='save', include_text=False)
            row_sizer.Add(save_btn, 0, wx.ALL, 5)
            self.slot_map['save'] = save_btn
            self.grid_sizer.Add(row_sizer, 0, wx.ALIGN_CENTER | wx.TOP, 5)

            # Create a flexible grid for bundle items (3 columns)
            self.bundle_grid = wx.FlexGridSizer(rows=0, cols=8, hgap=5, vgap=5)
            self.bundle_grid.SetFlexibleDirection(wx.BOTH)
            self.bundle_grid.SetNonFlexibleGrowMode(wx.FLEX_GROWMODE_SPECIFIED)

            # Load bundle contents (already a list or ListTag)
            bundle_items = list(self.container)

            for index, item in enumerate(bundle_items):
                item_id = item.get("id", "minecraft:air")
                count = item.get("count", 1)

                # Create button for this slot
                slot_name = f"Slot_{index}"
                btn = IconButton(self.scroll_panel, slot=slot_name)

                # Tooltip text
                tooltip_text = item_id.py_str.replace("minecraft:", "") + f" x{count}"

                btn.SetToolTip(tooltip_text)
                self.slot_map[slot_name] = btn
                self.bundle_grid.Add(btn, 0, wx.ALL, 5)

            # Add the bundle grid to the layout
            self.grid_sizer.Add(self.bundle_grid, 0, wx.ALIGN_CENTER | wx.TOP, 5)

            # Update layout and load item icons
            self.Layout()
            self.load_bundle()

        # Apply layout
        self.scroll_panel.SetSizer(self.grid_sizer)
        self.scroll_panel.Layout()
        self.scroll_panel.FitInside()
    def load_player_inventory(self):
        # Equipment first — uses named slots
        for slot_name, item in self.equipment.items():
            btn = self.slot_map.get(slot_name)

            if btn:
                self._update_button(btn, item)

        # Main inventory — numeric slots
        self._load_generic(self.inventory, key_field='Slot')
    def load_ender_inventory(self):
        self._load_generic(self.ender, key_field='Slot')
    def load_container(self):
        for container in self.container:
            slot_index = int(container['slot'].py_int)
            slot_key = f"Slot_{slot_index}" if f"Slot_{slot_index}" in self.slot_map else slot_index
            btn = self.slot_map.get(slot_key)
            if not btn:
                print(f"Warning: No button found for slot {slot_index}")
                continue
            # Pass the actual item, not the container wrapper
            self._update_button(btn, container['item'])

    def load_bundle(self):
        """Dynamically load bundle items into the button grid."""
        bundle_data = list(self.container)

        # --- Create grid if it doesn't exist ---
        if not hasattr(self, "bundle_grid") or self.bundle_grid is None:
            self.bundle_grid = wx.FlexGridSizer(rows=0, cols=3, hgap=5, vgap=5)
            self.bundle_grid.SetFlexibleDirection(wx.BOTH)
            self.bundle_grid.SetNonFlexibleGrowMode(wx.FLEX_GROWMODE_SPECIFIED)
            self.grid_sizer.Add(self.bundle_grid, 0, wx.ALIGN_CENTER | wx.TOP, 5)

        # --- Ensure each item has a button ---
        for index, item_entry in enumerate(bundle_data):
            slot_key = f"Slot_{index}"
            btn = self.slot_map.get(slot_key)

            if not btn:
                # Create a new IconButton dynamically
                btn = IconButton(self.scroll_panel, slot=slot_key)
                self.slot_map[slot_key] = btn
                self.bundle_grid.Add(btn, 0, wx.ALL, 5)

            # Update the button contents
            self._update_button(btn, item_entry)

        # --- Handle extra buttons (clear if fewer items) ---
        existing_slots = list(self.slot_map.keys())
        for key in existing_slots:
            if key.startswith("Slot_"):
                index = int(key.split("_")[1])
                if index >= len(bundle_data):
                    btn = self.slot_map.pop(key)
                    btn.Destroy()

        # --- Refresh layout ---
        self.bundle_grid.Layout()
        self.grid_sizer.Layout()
        self.Layout()

    def _load_generic(self, items, key_field='Slot'):
        """Generic loader for numeric-slot inventories"""
        for item in items:
            slot_index = int(item[key_field].py_int)
            slot_key = f"Slot_{slot_index}" if f"Slot_{slot_index}" in self.slot_map else slot_index
            btn = self.slot_map.get(slot_key)
            if not btn:
                print(f"Warning: No button found for slot {slot_index}")
                continue
            self._update_button(btn, item)
    def _update_button(self, button, item):
        """Update IconButton with item data"""
        item_id = str(item['id'].py_str)
        count = int(item['count'].py_int)
        lookup_id = item_id  # Default lookup key

        # --- Handle component-based variations (e.g., Goat Horns) ---
        if item.get('components'):
            button.set_components(item['components'])

            if 'goat_horn' in item_id:
                comp = item['components']
                index = next(
                    (k for k, v in goat_horn_components.items()
                     if v["minecraft:instrument"].py_str == comp["minecraft:instrument"].py_str),
                    None
                )
                if index is not None and index != 0: # minecraft:potion_contents
                    lookup_id = f"{item_id}:{index}"
            if 'firework_rocket' in item_id:
                comp = item['components']
                firework_colors_rev = {v: k for k, v in firework_colors.items()}
                value = comp["minecraft:fireworks"]['explosions'][0]['colors'][0]
                if firework_colors_rev.get(value, None):
                    lookup_id = '_:' + firework_colors_rev.get(value, None)
                else:
                    lookup_id = '_:firework_rocket'
            if 'firework_star' in item_id:
                comp = item['components']
                firework_colors_rev = {v: k for k, v in firework_star_colors.items()}
                value = comp["minecraft:firework_explosion"]['colors'][0].py_int
                if firework_colors_rev.get(value, None):
                    lookup_id = '_:' + firework_colors_rev.get(value)
                else:
                    lookup_id = '_:firework_star'

            if 'enchanted_book' in item_id:
                comp = item["components"]
                # Reverse the dictionary so you can look up by the Minecraft enchantment name
                enchanted_books_rev = {v: k for k, v in enchanted_books.items()}
                # Assuming stored_enchantments looks like {"minecraft:sharpness": 3}
                stored_enchants = comp.get("minecraft:stored_enchantments", {})
                for key, value in stored_enchants.items():
                    lookup_key = f"{key}_{value}"
                    lookup_id = '_:'+enchanted_books_rev.get(lookup_key, None)

            elif 'ominous_bottle' in item_id:
                comp = item['components']
                ominous_bottles_rev = {v: k for k, v in ominous_bottles.items()}
                value = comp["minecraft:ominous_bottle_amplifier"].py_int
                # print(value,ominous_bottles_rev[value])

                lookup_id = '_:'+ ominous_bottles_rev[value]
            elif 'splash_potion' in item_id:
                java_to_potion = {v: k for k, v in potion_to_java.items()}
                comp = item['components']
                potion_value = comp["minecraft:potion_contents"]['potion'].py_str  # e.g., 'minecraft:night_vision'
                # print(potion_value, '<<<<<<<', java_to_potion.get(potion_value, "None"))
                lookup_id = '_:splash_'+java_to_potion.get(potion_value, "None")  # e.g., 'potion:5'
            elif 'lingering_potion' in item_id:
                java_to_potion = {v: k for k, v in potion_to_java.items()}
                comp = item['components']
                potion_value = comp["minecraft:potion_contents"]['potion'].py_str  # e.g., 'minecraft:night_vision'
                # print(potion_value, '<<<<<<<', java_to_potion.get(potion_value, "None"))
                lookup_id = '_:lingering_'+java_to_potion.get(potion_value, "None")  # e.g., 'potion:5'
            elif 'potion' in item_id:
                java_to_potion = {v: k for k, v in potion_to_java.items()}
                comp = item['components']
                potion_value = comp["minecraft:potion_contents"]['potion'].py_str  # e.g., 'minecraft:night_vision'
                # print(potion_value, '<<<<<<<', java_to_potion.get(potion_value, "None"))
                lookup_id = '_:'+java_to_potion.get(potion_value, "None")  # e.g., 'potion:5'
            elif 'tipped_arrow' in item_id:
                java_to_potion = {v: k for k, v in arrow_potions.items()}
                comp = item['components']
                potion_value = comp["minecraft:potion_contents"]['potion'].py_str  # e.g., 'minecraft:night_vision'
                # print(potion_value, '<<<<<<<', java_to_potion.get(potion_value, "None"))
                lookup_id = '_:'+java_to_potion.get(potion_value, "None")  # e.g., 'potion:5'

                # --- Handle bed variants using your mapping dict ---
        elif item_id in bed_icons:

            lookup_id = '_:'+bed_icons[item_id]

        # --- Retrieve icon from cache ---
        icon_key = lookup_id.split(":", 1)[1] if ":" in lookup_id else lookup_id
        icon_bitmap = self.resources.get_scaled_cache.get(icon_key)

        if not icon_bitmap:
            print(f"Missing icon for {item_id} (lookup key: {icon_key})")
            return

        # --- Retrieve display name and set button ---
        display_name = self.resources.data.get(icon_key, {}).get('display_name', icon_key)
        if item.get('components'):
            comp = item.get('components')
            if 'minecraft:custom_name' in comp:

                text_list = item['components']['minecraft:custom_name']

                display_name += f"\n {text_list['text']}"
            if 'minecraft:enchantments' in comp:
                comp = item['components']['minecraft:enchantments'].py_data
                # display_name += f"\n Enchantments:"
                for k,v in comp.items():
                    enchant_lvl = f'{k.replace('minecraft:', '').replace('_', ' ').title()}   {v}'
                    display_name += f"\n {enchant_lvl}"
            if 'minecraft:lore' in comp:
                text_list = item['components']['minecraft:lore']
                for text in text_list:
                    display_name += f"\n {text['text']}"

        button.SetBitmap(icon_bitmap, display_name)
        button.set_item_id(item_id)
        button.set_count(count)

class PlayersData:
    def __init__(self, world):
        self.dict_of_player_data = collections.defaultdict(dict)
        self.world = world
        self.load_players_data()
        self._player = {}

    def get_player_data(self):
        return self._player

    @property
    def get_loaded_players_list(self):
        return list(self.dict_of_player_data.keys())

    def load_players_data(self):
        """
        Loads Java Edition 'level.dat' and all player data files from 'playerdata'.
        Handles local_player (Data->Player) and online UUID players.
        """
        path = self.world
        self.dict_of_player_data = {}

        # --- Load the main world data (level.dat) ---
        local_path = os.path.join(path, "level.dat")
        if os.path.exists(local_path):
            nbt_data = load(local_path, string_decoder=decode_java_mutf8).compound
            try:
                player_nbt = nbt_data["Data"]["Player"]

                self.dict_of_player_data["local_player"] = player_nbt
            except KeyError:
                print("Warning: No Player data found inside level.dat")

        # --- Load all player data files from playerdata directory ---
        playerdata_dir = os.path.join(path, "playerdata")
        if os.path.exists(playerdata_dir):
            for filename in os.listdir(playerdata_dir):
                if filename.endswith(".dat"):
                    player_path = os.path.join(playerdata_dir, filename)
                    try:
                        player_uuid = os.path.splitext(filename)[0]
                        self.dict_of_player_data[player_uuid] = load(player_path, string_decoder=decode_java_mutf8)
                    except Exception as e:
                        print(f"Failed to load player data {filename}: {e}")

    def get_player(self, player_id):
        """
        Returns a Player wrapper instance for the given player ID.
        """
        if player_id not in self._player:
            if player_id not in self.dict_of_player_data:
                raise KeyError(f"Player {player_id} not found in loaded data.")
            self._player[player_id] = self.Player(
                self.dict_of_player_data[player_id], player_id, self.world
            )
        return self._player[player_id]

    class Player:
        def __init__(self, player_data, player_id, world):
            self.player_data = player_data
            self.player_id = player_id
            self.world = world

        def update(self, nbt):
            self.player_data = nbt

        def clear(self):
            self.player_data = CompoundTag({})

        def _traverse(self, keys):
            if isinstance(keys, str):
                keys = [keys]  # make it a list containing one key

            current = self.player_data
            for key in keys[:-1]:
                if isinstance(current, (collections.defaultdict, dict, CompoundTag)):
                    current = current[key]
                elif isinstance(current, (list, ListTag)):
                    for i, x in enumerate(current):
                        if x.get("Slot", IntTag(-9999)).py_int == key:
                            key = i
                            break
                    current = current[key]
                else:
                    raise KeyError(f"Invalid key/index during traversal: {key}")
            return current, keys[-1]

        def __getitem__(self, keys):
            # Direct string key access
            if isinstance(keys, str):
                if isinstance(self.player_data, NamedTag):
                    return self.player_data.compound[keys]
                return self.player_data[keys]
            # Nested key traversal (list form)
            elif isinstance(keys, list):
                current = self.player_data.compound
                for key in keys:
                    if isinstance(current, (collections.defaultdict, dict, CompoundTag)):
                        current = current[key]
                    elif isinstance(current, (list, ListTag)):
                        for i, x in enumerate(current):
                            if x.get("Slot", IntTag(-9999)).py_int == key:
                                key = i
                                break
                        current = current[key]
                    else:
                        raise KeyError(f"Invalid key/index: {key}")
                return current

            else:
                raise TypeError(f"Unsupported key type: {type(keys).__name__}")

        def __setitem__(self, keys, value):
            current, last_key = self._traverse(keys)
            current[last_key] = value

        def __delitem__(self, keys):
            current, last_key = self._traverse(keys)
            del current[last_key]

        def pop(self, keys, default=None):
            current, last_key = self._traverse(keys)
            return current.pop(last_key, default)

        def keys(self, keys=None):
            if keys is None:
                return self.player_data.keys()
            nested = self[keys]
            if hasattr(nested, "keys"):
                return nested.keys()
            raise TypeError("Target object does not support .keys()")

        def items(self, keys=None):
            if keys is None:
                return self.player_data.items()
            nested = self[keys]
            if hasattr(nested, "items"):
                return nested.items()
            raise TypeError("Target object does not support .items()")

        def get(self, keys, default=None):
            """
            Dictionary-like safe getter.
            Example:
                player.get('equipment')
                player.get(['Inventory', 0, 'tag'])
            """
            try:
                return self[keys]
            except (KeyError, IndexError, TypeError):
                return default

        def save(self):
            """
            Saves this player's data back to disk.
            For local_player → updates level.dat
            For UUID players → updates playerdata/<uuid>.dat
            """
            path = self.world
            if self.player_id == "local_player":
                # Update the player data within level.dat -> Data -> Player
                level_path = os.path.join(path, "level.dat")
                nbt_data = load(level_path, string_decoder=decode_java_mutf8).compound

                # Access .tag explicitly to modify the compound content
                nbt_data["Data"]["Player"] = self.player_data

                nbt_data.save_to(level_path, compressed=True, string_encoder=encode_java_mutf8)
                print("Saved local player data to level.dat")
            else:
                player_path = os.path.join(path, "playerdata", f"{self.player_id}.dat")
                nbt_data.save_to(level_path, compressed=True, string_encoder=encode_java_mutf8)
                print(f"Saved player data: {self.player_id}")

        def get_or_create_slot_item(self, keys, slot_value):
            """
            Finds or creates a CompoundTag with Slot = slot_value inside a ListTag.
            """
            current = self[keys]
            if not isinstance(current, ListTag):
                raise TypeError("Target is not a list")

            for item in current:
                if isinstance(item, CompoundTag) and item.get("Slot") == slot_value:
                    return item

            new_item = CompoundTag({"Slot": slot_value})
            current.append(new_item)
            return new_item

class InventoryEditorList(wx.Frame):

    def __init__(self, parent, canvas, path):
        super().__init__(parent, title="Player List Double Click to Load", size=(400, 800),
                         style=wx.DEFAULT_FRAME_STYLE | wx.STAY_ON_TOP)
        self.parent = parent
        self.canvas = canvas
        self.path = path

        self.open_editors = []  # Store references to open InventoryEditor instances

        self.player_data = PlayersData(path)
        self.player_list = self.player_data.get_loaded_players_list

        self.font = wx.Font(20, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        self.SetFont(self.font)
        self.SetForegroundColour((0, 255, 0))
        self.SetBackgroundColour((0, 0, 0))

        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        self.list_ctrl = wx.ListBox(panel, choices=self.player_list)
        self.list_ctrl.SetFont(self.font)
        self.list_ctrl.SetForegroundColour((0, 255, 0))
        self.list_ctrl.SetBackgroundColour((0, 0, 0))

        vbox.Add(self.list_ctrl, 1, wx.EXPAND | wx.ALL, 10)
        self.list_ctrl.Bind(wx.EVT_LISTBOX_DCLICK, self.on_item_click)
        self.Bind(wx.EVT_CLOSE, self.on_close)
        self.Centre()
        panel.SetSizer(vbox)
        self.Show()

    def on_close(self, event):
        self.Hide()
        # if __name__ == "__main__":
        #     self.world.close()

    def on_item_click(self, event):
        selection = self.list_ctrl.GetStringSelection()
        if selection != wx.NOT_FOUND:
            selected_player = self.player_data.get_player(selection)
            # print(selected_player['Inventory'])
            inventory = selected_player['Inventory']
            equipment = selected_player.get('equipment', CompoundTag({}))
            ender = selected_player['EnderItems']
            inventory_editor = InventoryFrame(player_data=selected_player, inventory=inventory, equipment=equipment, ender=ender)
            # inventory_editor.Bind(wx.EVT_CLOSE, lambda evt, ed=inventory_editor: self._on_editor_close(evt, ed))
            inventory_editor.Show(True)
            self.open_editors.append(inventory_editor)

    def _on_editor_close(self, event, editor):
        if editor in self.open_editors:
            self.open_editors.remove(editor)
        event.Skip()

class MinecraftWorldSelector(wx.Frame):
    def __init__(self):
        super().__init__(None, title="Minecraft World Selector", size=(1100, 900))
        self.font = wx.Font(18, wx.FONTFAMILY_ROMAN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        self.SetFont(self.font)

        bg_color = wx.Colour(88, 88, 88)
        self.SetBackgroundColour(bg_color)
        self.SetForegroundColour(bg_color)  # text matches background
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        panel = wx.ScrolledWindow(self)

        panel.SetScrollRate(10, 10)
        grid_sizer = wx.GridSizer(0, 4, 5, -80)  # 0 rows, 4 columns, 10px gap

        if os.path.exists(WORLDS_DIR):
            worlds = []
            for world_folder in os.listdir(WORLDS_DIR):
                world_path = os.path.join(WORLDS_DIR, world_folder)
                if os.path.isdir(world_path):
                    mod_time = os.path.getmtime(world_path)
                    worlds.append((mod_time, world_path))

            # Sort worlds by last modified time (most recent first)
            worlds.sort(reverse=True, key=lambda x: x[0])

            for _, world_path in worlds:
                world_name = os.path.basename(world_path)  # Default to folder name
                icon_path = os.path.join(world_path, "icon.png")
                level_dat_path = os.path.join(world_path, "level.dat")

                # Try to read a custom name from levelname.txt (some worlds have it)
                name_path = os.path.join(world_path, "levelname.txt")
                if os.path.exists(name_path):
                    with open(name_path, "r", encoding="utf-8") as f:
                        world_name = f.read().strip()

                world_panel = wx.Panel(panel)
                world_sizer = wx.BoxSizer(wx.VERTICAL)

                if os.path.exists(icon_path):
                    image = wx.Image(icon_path, wx.BITMAP_TYPE_PNG).Scale(128, 128)
                    bitmap = wx.StaticBitmap(world_panel, bitmap=wx.Bitmap(image))

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
                label.SetBackgroundColour(wx.Colour(88, 88, 88, 0))
                label.SetMinSize((180, 80))
                world_sizer.Add(label, 0, wx.ALIGN_CENTER | wx.ALL, 3)
                # label.SetTransparent(0)

                world_panel.SetSizer(world_sizer)
                grid_sizer.Add(world_panel, 0, wx.EXPAND | wx.ALL, 3)

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

        new_window = InventoryEditorList(None, None, path)
        new_window.Move(self.GetScreenPosition())  # Open next to the parent
        new_window.Show()

if __name__ == "__main__":
    app = wx.App(False)
    MinecraftWorldSelector()
    app.MainLoop()
