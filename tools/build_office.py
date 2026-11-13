"""Draws the security spot-the-flaws office and writes office.tmj.

Everything is drawn here at full 32px resolution; nothing is downloaded. Called by
build_living_world.py, or on its own:

    python tools/build_office.py
"""
import json
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
T = 32
W, H = 20, 14
INK = (34, 30, 46, 255)

# Things to inspect. Each sits on a walkable tile in front of the object it is about.
# Finding ids must match FINDINGS in src/office.ts, decoy ids must match DECOYS.
FINDINGS = {"sticky": (3, 4), "unlocked": (7, 4), "phish": (11, 4), "usb": (9, 9), "trash": (6, 10)}
DECOYS = {"locked": (3, 9), "shredder": (4, 11), "whiteboard": (8, 2), "serverdoor": (15, 7)}
DOOR = (9, 13)  # two tiles wide


def rgba(c, a=255):
    return tuple(c) + (a,)


def shade(c, f):
    return tuple(max(0, min(255, int(v * f))) for v in c[:3]) + ((c[3],) if len(c) == 4 else (255,))


class Room:
    def __init__(self):
        self.floor = Image.new("RGBA", (W * T, H * T))
        self.items = Image.new("RGBA", (W * T, H * T))
        self.blocked = set()
        self.rng = random.Random(4)

    def block(self, x0, y0, x1, y1):
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                self.blocked.add((x, y))


def draw_carpet(room):
    pixels = room.floor.load()
    rng = np.random.default_rng(2)
    noise = rng.random((H * T, W * T))
    for y in range(H * T):
        for x in range(W * T):
            tile = ((x // 64) + (y // 64)) % 2
            base = (82, 98, 128) if tile else (90, 107, 138)
            n = noise[y, x]
            f = 0.93 if n < 0.18 else 1.06 if n > 0.9 else 1.0
            # A fine woven grid every 4px.
            if x % 4 == 0 and y % 4 == 0:
                f *= 0.9
            pixels[x, y] = shade(base, f)


def draw_walls(room):
    d = ImageDraw.Draw(room.floor)
    # Back wall: trim, plaster, wainscot.
    d.rectangle([0, 0, W * T, 2 * T - 1], (228, 220, 202, 255))
    d.rectangle([0, 0, W * T, 5], (66, 58, 74, 255))
    d.rectangle([0, 2 * T - 16, W * T, 2 * T - 1], (150, 112, 82, 255))
    d.line([0, 2 * T - 16, W * T, 2 * T - 16], (186, 146, 108, 255))
    d.line([0, 2 * T - 1, W * T, 2 * T - 1], (98, 70, 56, 255))
    for x in range(0, W * T, 16):
        d.line([x, 2 * T - 15, x, 2 * T - 2], (136, 100, 74, 255))
    # Windows onto the snowy town.
    for wx in (1, 11):
        x0, x1 = wx * T + 6, (wx + 2) * T - 6
        d.rectangle([x0 - 3, 9, x1 + 3, 2 * T - 19], (92, 72, 60, 255))
        for y in range(12, 2 * T - 21):
            t = (y - 12) / 30
            d.line([x0, y, x1, y], (int(150 + 60 * t), int(190 + 40 * t), int(230 + 15 * t), 255))
        for px in range(x0 + 4, x1 - 4, 11):
            h = 6 + (px * 7) % 6
            d.polygon([(px, 2 * T - 22 - h), (px - 4, 2 * T - 22), (px + 4, 2 * T - 22)], (40, 84, 84, 255))
        d.rectangle([x0, 2 * T - 23, x1, 2 * T - 22], (246, 250, 255, 255))
        rng = random.Random(wx)
        for _ in range(10):
            d.point([rng.randrange(x0, x1), rng.randrange(12, 2 * T - 24)], (255, 255, 255, 255))
        d.line([(x0 + x1) // 2, 12, (x0 + x1) // 2, 2 * T - 22], (92, 72, 60, 255))
        d.rectangle([x0 - 5, 2 * T - 21, x1 + 5, 2 * T - 18], (204, 196, 180, 255))
    # Side and front walls, seen from above.
    wall_top, wall_edge = (72, 64, 84, 255), (112, 102, 124, 255)
    d.rectangle([0, 0, 11, H * T], wall_top)
    d.line([11, 2 * T, 11, H * T], wall_edge)
    d.rectangle([W * T - 12, 0, W * T, H * T], wall_top)
    d.line([W * T - 12, 2 * T, W * T - 12, H * T], wall_edge)
    d.rectangle([0, (H - 1) * T + 14, W * T, H * T], wall_top)
    d.line([0, (H - 1) * T + 14, W * T, (H - 1) * T + 14], wall_edge)
    # Doorway and mat.
    dx = DOOR[0] * T
    d.rectangle([dx, (H - 1) * T + 14, dx + 2 * T - 1, H * T], (60, 54, 70, 255))
    d.rectangle([dx + 4, (H - 1) * T - 4, dx + 2 * T - 5, (H - 1) * T + 12], (150, 60, 58, 255))
    d.rectangle([dx + 8, (H - 1) * T, dx + 2 * T - 9, (H - 1) * T + 8], (176, 82, 72, 255))
    room.block(0, 0, W - 1, 1)
    room.block(0, 0, 0, H - 1)
    room.block(W - 1, 0, W - 1, H - 1)
    room.block(0, H - 1, W - 1, H - 1)
    room.blocked -= {(DOOR[0], H - 1), (DOOR[0] + 1, H - 1)}


def draw_partition(room):
    """The server room, top right, with its door propped open."""
    d = ImageDraw.Draw(room.items)
    x0, y0, x1, y1 = 13 * T, 2 * T, (W - 1) * T, 6 * T
    wall = (196, 190, 204, 255)
    d.rectangle([x0, y0, x0 + 9, y1 + 9], wall)
    d.rectangle([x0, y1, x1, y1 + 9], wall)
    d.line([x0 + 9, y0, x0 + 9, y1], (150, 144, 162, 255))
    d.line([x0, y1 + 9, x1, y1 + 9], (150, 144, 162, 255))
    # A closed door at column 15 with a badge reader beside it (doing it right).
    gx = 15 * T
    d.rectangle([gx + 2, y1 - 2, gx + T - 3, y1 + 9], (126, 90, 64, 255))
    d.line([gx + 2, y1 - 2, gx + T - 3, y1 - 2], (164, 122, 88, 255))
    d.rectangle([gx + T - 9, y1 + 2, gx + T - 7, y1 + 5], (230, 200, 90, 255))
    d.rectangle([gx - 7, y1 + 11, gx - 1, y1 + 20], (40, 44, 56, 255))
    d.rectangle([gx - 6, y1 + 12, gx - 2, y1 + 15], (80, 200, 120, 255))
    # Racks.
    for i, rx in enumerate((14, 16, 17)):
        px = rx * T + 3
        d.rectangle([px, y0 + 4, px + 25, y0 + 58], (34, 38, 50, 255))
        d.rectangle([px + 2, y0 + 6, px + 23, y0 + 56], (48, 54, 70, 255))
        for slot in range(7):
            sy = y0 + 9 + slot * 7
            d.rectangle([px + 4, sy, px + 21, sy + 4], (62, 70, 90, 255))
    for y in range(2, 6):
        room.block(13, y, 13, y)
    room.block(13, 6, W - 1, 6)
    room.block(14, 2, 17, 3)


def rack_lights(frame):
    """LED overlay for the racks, two frames."""
    image = Image.new("RGBA", (W * T, H * T))
    d = ImageDraw.Draw(image)
    rng = random.Random(10 + frame)
    for rx in (14, 16, 17):
        px = rx * T + 3
        for slot in range(7):
            sy = 2 * T + 10 + slot * 7
            for led in range(3):
                color = rng.choice(((90, 230, 120), (90, 230, 120), (250, 190, 60), (40, 60, 50)))
                d.point([px + 6 + led * 3, sy + 1], color + (255,))
    return image


def desk(room, x, y, screen, extras=()):
    """A 2x2 desk with a monitor. screen: 'sticky', 'unlocked', 'phish', 'locked' or None."""
    d = ImageDraw.Draw(room.items)
    px, py = x * T, y * T
    top, front, edge = (176, 130, 90, 255), (136, 96, 66, 255), (204, 160, 116, 255)
    d.rectangle([px + 2, py + 20, px + 61, py + 44], top)
    d.line([px + 2, py + 20, px + 61, py + 20], edge)
    d.rectangle([px + 2, py + 45, px + 61, py + 58], front)
    d.rectangle([px + 4, py + 58, px + 8, py + 62], (96, 66, 48, 255))
    d.rectangle([px + 55, py + 58, px + 59, py + 62], (96, 66, 48, 255))
    if screen:
        # Monitor: stand, bezel, screen.
        d.rectangle([px + 28, py + 22, px + 35, py + 28], (60, 62, 74, 255))
        d.rectangle([px + 23, py + 27, px + 40, py + 29], (52, 54, 66, 255))
        d.rectangle([px + 14, py + 2, px + 49, py + 23], (36, 38, 50, 255))
        sx0, sy0, sx1, sy1 = px + 16, py + 4, px + 47, py + 20
        if screen == "locked":
            d.rectangle([sx0, sy0, sx1, sy1], (30, 60, 110, 255))
            d.rectangle([px + 28, py + 11, px + 35, py + 17], (230, 230, 240, 255))
            d.arc([px + 28, py + 6, px + 35, py + 14], 180, 360, (230, 230, 240, 255), width=2)
        elif screen in ("unlocked", "sticky"):
            d.rectangle([sx0, sy0, sx1, sy1], (90, 150, 210, 255))
            d.rectangle([sx0 + 3, sy0 + 3, sx0 + 18, sy0 + 12], (240, 244, 250, 255))
            d.rectangle([sx0 + 3, sy0 + 3, sx0 + 18, sy0 + 4], (70, 100, 180, 255))
            for i in range(3):
                d.line([sx0 + 5, sy0 + 7 + i * 2, sx0 + 15, sy0 + 7 + i * 2], (150, 160, 180, 255))
            d.rectangle([sx0, sy1 - 2, sx1, sy1], (40, 50, 80, 255))
            if screen == "sticky":
                d.rectangle([px + 41, py + 1, px + 50, py + 10], (250, 222, 90, 255))
                d.line([px + 43, py + 4, px + 48, py + 4], (120, 90, 40, 255))
                d.line([px + 43, py + 7, px + 47, py + 7], (120, 90, 40, 255))
        elif screen == "phish":
            d.rectangle([sx0, sy0, sx1, sy1], (236, 240, 246, 255))
            d.rectangle([sx0, sy0, sx0 + 7, sy1], (60, 90, 160, 255))
            for i in range(4):
                d.line([sx0 + 10, sy0 + 3 + i * 4, sx1 - 3, sy0 + 3 + i * 4], (170, 176, 190, 255))
        # Keyboard and mouse.
        d.rectangle([px + 20, py + 33, px + 43, py + 38], (206, 208, 216, 255))
        for k in range(22, 42, 3):
            d.point([k, py + 35], (150, 152, 164, 255))
        d.rectangle([px + 48, py + 34, px + 51, py + 38], (206, 208, 216, 255))
    if "mug" in extras:
        d.rectangle([px + 6, py + 27, px + 11, py + 34], (226, 90, 80, 255))
        d.point([px + 12, py + 30], (226, 90, 80, 255))
    if "plant" in extras:
        d.rectangle([px + 6, py + 28, px + 12, py + 36], (190, 110, 80, 255))
        for dx, dy in ((-3, -6), (0, -9), (3, -6), (-1, -4), (2, -3)):
            d.ellipse([px + 8 + dx, py + 26 + dy, px + 12 + dx, py + 30 + dy], (74, 150, 90, 255))
    if "papers" in extras:
        d.rectangle([px + 46, py + 30, px + 57, py + 40], (246, 246, 240, 255))
        d.rectangle([px + 48, py + 28, px + 59, py + 38], (236, 236, 228, 255))
    # An empty chair, pushed back: the owner just walked away.
    if screen == "unlocked":
        d.ellipse([px + 22, py + 52, px + 41, py + 63], (60, 64, 84, 255))
    room.block(x, y, x + 1, y + 1)


def phish_blink(frame):
    """A pulsing 'new mail' badge on the phishing computer."""
    image = Image.new("RGBA", (W * T, H * T))
    if frame == 0:
        d = ImageDraw.Draw(image)
        px, py = 10 * T, 2 * T
        d.ellipse([px + 41, py + 1, px + 49, py + 9], (230, 60, 60, 255))
        d.point([px + 45, py + 5], (255, 255, 255, 255))
    return image


def small_props(room):
    d = ImageDraw.Draw(room.items)
    # USB stick on the floor.
    ux, uy = FINDINGS["usb"][0] * T + 12, FINDINGS["usb"][1] * T + 14
    d.rectangle([ux, uy, ux + 8, uy + 4], (40, 90, 200, 255))
    d.rectangle([ux + 9, uy + 1, ux + 12, uy + 3], (200, 204, 214, 255))
    d.point([ux + 2, uy + 2], (255, 255, 255, 255))

    # Bin with an unshredded confidential document.
    bx, by = 6 * T, 11 * T
    d.rectangle([bx + 8, by + 6, bx + 23, by + 26], (140, 146, 160, 255))
    d.rectangle([bx + 6, by + 4, bx + 25, by + 7], (170, 176, 190, 255))
    d.line([bx + 20, by + 8, bx + 20, by + 25], (116, 122, 136, 255))
    d.polygon([(bx + 10, by + 6), (bx + 14, by - 6), (bx + 24, by - 3), (bx + 21, by + 6)], (250, 250, 244, 255))
    d.rectangle([bx + 15, by - 3, bx + 21, by + 1], (210, 40, 50, 255))
    room.block(6, 11, 6, 11)

    # Shredder (doing it right).
    sx, sy = 4 * T, 12 * T
    d.rectangle([sx + 4, sy + 2, sx + 27, sy + 26], (52, 54, 64, 255))
    d.rectangle([sx + 4, sy + 2, sx + 27, sy + 7], (80, 82, 94, 255))
    d.line([sx + 8, sy + 4, sx + 23, sy + 4], (20, 20, 26, 255))
    for i in range(6):
        d.line([sx + 8 + i * 3, sy + 10, sx + 8 + i * 3, sy + 18], (236, 236, 230, 255))
    room.block(4, 12, 4, 12)

    # Whiteboard with meeting notes (nothing sensitive).
    wx = 6 * T + 4
    d.rectangle([wx, 10, wx + 3 * T - 8, 2 * T - 20], (240, 244, 248, 255))
    d.rectangle([wx, 10, wx + 3 * T - 8, 2 * T - 20], outline=(150, 156, 170, 255))
    for i, (c, w) in enumerate((((60, 110, 200), 40), ((210, 70, 70), 26), ((60, 160, 90), 52))):
        d.line([wx + 6, 16 + i * 8, wx + 6 + w, 16 + i * 8], c + (255,), width=2)

    # Decoration: plants, water cooler, bookshelf.
    for qx, qy in ((1, 2), (12, 12), (18, 12)):
        px, py = qx * T, qy * T
        d.rectangle([px + 9, py + 18, px + 22, py + 30], (176, 98, 70, 255))
        for dx, dy, r in ((0, 0, 9), (-6, 4, 7), (6, 4, 7), (0, -6, 7)):
            d.ellipse([px + 15 + dx - r, py + 12 + dy - r, px + 15 + dx + r, py + 12 + dy + r], (62, 140, 84, 255))
            d.ellipse([px + 13 + dx - r // 2, py + 9 + dy - r // 2, px + 13 + dx + r // 2, py + 9 + dy + r // 2], (96, 176, 104, 255))
        room.block(qx, qy, qx, qy)
    cx, cy = 18 * T, 8 * T
    d.rectangle([cx + 8, cy + 10, cx + 24, cy + 30], (210, 214, 224, 255))
    d.ellipse([cx + 6, cy - 6, cx + 26, cy + 14], (150, 200, 240, 220))
    room.block(18, 8, 18, 8)


def tile_layer(name, cells, layer_id, visible=True):
    data = [0] * (W * H)
    for (x, y), gid in cells.items():
        data[y * W + x] = gid
    return {"data": data, "height": H, "id": layer_id, "name": name, "opacity": 1, "type": "tilelayer", "visible": visible, "width": W, "x": 0, "y": 0}


def build():
    room = Room()
    draw_carpet(room)
    draw_walls(room)
    draw_partition(room)
    desk(room, 2, 2, "sticky", ("mug",))
    desk(room, 6, 2, "unlocked", ("papers",))
    desk(room, 10, 2, "phish", ("plant",))
    desk(room, 2, 7, "locked", ("mug",))
    desk(room, 6, 7, None, ("papers", "plant"))
    small_props(room)

    # Found markers: a green check floating over each problem once it has been found.
    check = Image.new("RGBA", (T, T))
    cd = ImageDraw.Draw(check)
    cd.ellipse([4, 2, 27, 25], (40, 160, 90, 235))
    cd.line([(9, 13), (14, 19), (23, 8)], (255, 255, 255, 255), width=3)

    tiles, index, animations = [], {}, []

    def static(image):
        key = image.tobytes()
        if key not in index:
            index[key] = len(tiles)
            tiles.append(image)
        return index[key] + 1

    def animated(frames, duration):
        ids = []
        for frame in frames:
            tiles.append(frame)
            ids.append(len(tiles) - 1)
        animations.append({"id": ids[0], "animation": [{"tileid": i, "duration": duration} for i in ids]})
        return ids[0] + 1

    def slice_cells(image):
        out = {}
        for y in range(H):
            for x in range(W):
                cell = image.crop((x * T, y * T, (x + 1) * T, (y + 1) * T))
                if cell.getbbox():
                    out[(x, y)] = cell
        return out

    floor_cells = {k: static(v) for k, v in slice_cells(room.floor).items()}
    item_cells = {k: static(v) for k, v in slice_cells(room.items).items()}

    lights = [slice_cells(rack_lights(f)) for f in range(2)]
    light_cells = {k: animated([lights[0][k], lights[1].get(k, Image.new("RGBA", (T, T)))], 600) for k in lights[0]}
    blink = [slice_cells(phish_blink(f)) for f in range(2)]
    blink_cells = {k: animated([blink[0][k], Image.new("RGBA", (T, T))], 500) for k in blink[0]}

    check_gid = static(check)
    # WorkAdventure only blocks movement on tiles whose "collides" property is true.
    tiles.append(Image.new("RGBA", (T, T)))  # invisible: the layer must stay visible to collide
    collide_gid = len(tiles)
    animations.append({"id": collide_gid - 1, "properties": [{"name": "collides", "type": "bool", "value": True}]})

    columns = 16
    rows = (len(tiles) + columns - 1) // columns
    sheet = Image.new("RGBA", (columns * T, rows * T))
    for i, tile in enumerate(tiles):
        sheet.paste(tile, ((i % columns) * T, (i // columns) * T))
    sheet.save(ROOT / "tilesets" / "HS_Office32x.png", optimize=True)

    layer_id = iter(range(1, 1000))
    objects, object_id = [], iter(range(1, 1000))

    def area(name, x, y, w=1, h=1, props=None):
        objects.append({"id": next(object_id), "name": name, "type": "area", "rotation": 0, "visible": True, "x": x * T, "y": y * T, "width": w * T, "height": h * T, **({"properties": props} if props else {})})

    for name, (x, y) in FINDINGS.items():
        area(f"find_{name}", x, y)
    for name, (x, y) in DECOYS.items():
        area(f"decoy_{name}", x, y)
    area("to-overworld", DOOR[0], H - 1, 2, 1, [{"name": "exitUrl", "type": "string", "value": "map.tmj#hsFromOffice"}])
    area("silentZone", 0, 0, W, H, [{"name": "silent", "type": "bool", "value": True}])

    found_layers = [tile_layer(name, {(x, y - 1): check_gid}, next(layer_id), False) for name, (x, y) in FINDINGS.items()]
    spawn = {(DOOR[0], H - 3): 1, (DOOR[0] + 1, H - 3): 1}  # two tiles from the exit, or the player leaves on arrival

    office = {
        "compressionlevel": -1, "height": H, "infinite": False, "orientation": "orthogonal",
        "renderorder": "right-down", "tiledversion": "1.10.2", "tileheight": T, "tilewidth": T,
        "type": "map", "version": "1.10", "width": W,
        "layers": [
            tile_layer("start", spawn, next(layer_id)),
            tile_layer("collisions", {cell: collide_gid for cell in room.blocked}, next(layer_id)),
            {"id": next(layer_id), "layers": [tile_layer("floor", floor_cells, next(layer_id))], "name": "floor", "opacity": 1, "type": "group", "visible": True, "x": 0, "y": 0},
            {"id": next(layer_id), "layers": [
                tile_layer("furniture", item_cells, next(layer_id)),
                tile_layer("lights", light_cells, next(layer_id)),
                tile_layer("mail", blink_cells, next(layer_id)),
            ], "name": "furniture", "opacity": 1, "type": "group", "visible": True, "x": 0, "y": 0},
            {"draworder": "topdown", "id": next(layer_id), "name": "floorLayer", "objects": objects, "opacity": 1, "type": "objectgroup", "visible": True, "x": 0, "y": 0},
            {"id": next(layer_id), "layers": found_layers, "name": "found", "opacity": 1, "type": "group", "visible": True, "x": 0, "y": 0},
        ],
        "nextlayerid": next(layer_id), "nextobjectid": next(object_id),
        "properties": [
            {"name": "mapName", "type": "string", "value": "Hackersir Information Security Week - Office"},
            {"name": "mapDescription", "type": "string", "value": "Find the security mistakes in the office."},
            {"name": "mapCopyright", "type": "string", "value": "Generated by tools/build_office.py. License: CC-BY-SA 3.0, like the rest of the map."},
            {"name": "script", "type": "string", "value": "src/office.ts"},
        ],
        "tilesets": [{
            "columns": columns, "firstgid": 1, "image": "tilesets/HS_Office32x.png", "imageheight": rows * T,
            "imagewidth": columns * T, "margin": 0, "name": "HS_Office32x", "spacing": 0, "tilecount": len(tiles),
            "tileheight": T, "tilewidth": T, "tiles": animations,
        }],
    }
    (ROOT / "office.tmj").write_text(json.dumps(office, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"office: {len(tiles)} tiles, {len(room.blocked)} blocked cells")


if __name__ == "__main__":
    build()
