"""Procedural ground and forest textures, drawn at the map's full 32px resolution."""
import random

import numpy as np
from PIL import Image, ImageDraw

T = 32
BAYER = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) / 16 - 0.5


def tileable_noise(size, cells, seed):
    """Value noise that wraps, so textures repeat without a seam."""
    rng = np.random.default_rng(seed)
    grid = rng.random((cells, cells))
    coords = np.arange(size) / size * cells
    i0 = coords.astype(int) % cells
    i1 = (i0 + 1) % cells
    f = coords - np.floor(coords)
    f = f * f * (3 - 2 * f)
    top = grid[i0[:, None], i0[None, :]] * (1 - f[None, :]) + grid[i0[:, None], i1[None, :]] * f[None, :]
    bottom = grid[i1[:, None], i0[None, :]] * (1 - f[None, :]) + grid[i1[:, None], i1[None, :]] * f[None, :]
    return top * (1 - f[:, None]) + bottom * f[:, None]


def fbm(size, seed, base=4, octaves=4):
    out = sum(tileable_noise(size, base * 2 ** o, seed + o) * 0.5 ** o for o in range(octaves))
    return (out - out.min()) / (out.max() - out.min())


def ramp_image(value, ramp):
    """Maps 0-1 values onto a colour ramp with ordered dithering, the pixel-art way to blend."""
    h, w = value.shape
    dither = np.tile(BAYER, (h // 4 + 1, w // 4 + 1))[:h, :w] * 0.9
    index = np.clip((value * (len(ramp) - 1) + dither).round().astype(int), 0, len(ramp) - 1)
    rgb = np.array(ramp, dtype=np.uint8)[index]
    alpha = np.full((h, w, 1), 255, dtype=np.uint8)
    return Image.fromarray(np.concatenate([rgb, alpha], axis=2), "RGBA").copy()


def scatter(rng, image, count, painter):
    size = image.width
    for _ in range(count):
        painter(image, rng.randrange(size), rng.randrange(size), rng)


def wrap_rect(image, x, y, w, h, color):
    pixels = image.load()
    for oy in range(h):
        for ox in range(w):
            pixels[(x + ox) % image.width, (y + oy) % image.height] = color


def road_texture(size=512):
    """Packed snow: wheel-worn streaks, faint tracks, ice glints and bits of grit."""
    drifts = fbm(size, 11, base=3)
    streaks = fbm(size, 29, base=2, octaves=2)
    # Stretching one axis of the noise reads as snow compressed along the road.
    stretched = np.roll(np.repeat(tileable_noise(size, 32, 5), 1, axis=0), 0, axis=0)
    stretched = (stretched + np.roll(stretched, 11, axis=1) + np.roll(stretched, 23, axis=1)) / 3
    value = 0.56 * drifts + 0.26 * streaks + 0.18 * stretched
    value = (value - value.min()) / (value.max() - value.min())
    ramp = [(198, 214, 232), (212, 226, 240), (224, 235, 246), (234, 242, 250), (243, 248, 253), (250, 252, 255)]
    image = ramp_image(value ** 0.8, ramp)

    rng = random.Random(7)

    def glint(img, x, y, r):
        wrap_rect(img, x, y, 1, 1, (255, 255, 255, 255))
        if r.random() < 0.3:
            wrap_rect(img, x - 1, y, 3, 1, (255, 255, 255, 255))
            wrap_rect(img, x, y - 1, 1, 3, (255, 255, 255, 255))

    def grit(img, x, y, r):
        wrap_rect(img, x, y, r.choice((1, 1, 2)), 1, r.choice(((148, 160, 182, 255), (168, 158, 158, 255), (128, 142, 170, 255))))

    def dent(img, x, y, r):
        w = r.randrange(5, 12)
        wrap_rect(img, x, y, w, 1, (186, 204, 226, 255))
        wrap_rect(img, x + 1, y + 1, w - 2, 1, (250, 252, 255, 255))

    scatter(rng, image, 240, glint)
    scatter(rng, image, 150, grit)
    scatter(rng, image, 60, dent)
    return image


def drift_texture(size=512):
    """Soft blue drifts, with tufts of frozen grass, twigs, stones and crystals poking through."""
    value = 0.7 * fbm(size, 41, base=3) + 0.3 * fbm(size, 57, base=9, octaves=2)
    value = (value - value.min()) / (value.max() - value.min())
    ramp = [(146, 205, 226), (160, 216, 233), (174, 226, 238), (188, 235, 243), (203, 242, 248), (219, 248, 251)]
    image = ramp_image(value, ramp)

    rng = random.Random(13)
    sparkle = (255, 255, 255, 255)

    def crystal(img, x, y, r):
        wrap_rect(img, x, y, 1, 1, sparkle)
        if r.random() < 0.25:
            wrap_rect(img, x + 1, y + 1, 1, 1, (232, 250, 255, 255))

    def tuft(img, x, y, r):
        colors = ((62, 112, 112, 255), (84, 134, 122, 255), (150, 142, 104, 255))
        for i in range(r.randrange(3, 6)):
            h = r.randrange(2, 6)
            wrap_rect(img, x + i * 2, y - h, 1, h, r.choice(colors))
        wrap_rect(img, x - 1, y, r.randrange(7, 12), 1, (228, 248, 252, 255))

    def stone(img, x, y, r):
        wrap_rect(img, x, y, 6, 3, (110, 128, 156, 255))
        wrap_rect(img, x + 1, y + 3, 4, 1, (82, 100, 130, 255))
        wrap_rect(img, x + 1, y - 1, 4, 2, (246, 252, 255, 255))
        wrap_rect(img, x + 6, y + 2, 3, 1, (136, 190, 216, 255))

    def twig(img, x, y, r):
        length = r.randrange(6, 12)
        for i in range(length):
            wrap_rect(img, x + i, y + (i // 3), 1, 1, (106, 82, 76, 255))
        wrap_rect(img, x + length // 2, y - 2, 1, 2, (106, 82, 76, 255))

    def mound(img, x, y, r):
        w = r.randrange(10, 20)
        wrap_rect(img, x + 2, y, w - 4, 1, (240, 252, 254, 255))
        wrap_rect(img, x, y + 1, w, 1, (226, 248, 252, 255))
        wrap_rect(img, x + 1, y + 2, w - 2, 1, (130, 194, 220, 255))

    scatter(rng, image, 170, crystal)
    scatter(rng, image, 70, mound)
    scatter(rng, image, 44, tuft)
    scatter(rng, image, 16, stone)
    scatter(rng, image, 14, twig)
    return image


def tile_grid(image):
    n = image.width // T
    return [[image.crop((x * T, y * T, (x + 1) * T, (y + 1) * T)) for x in range(n)] for y in range(n)]


def retexture_edge(edge, texture_tile):
    """Puts the drift texture on an autotile edge, keeping its scalloped outline and transparency."""
    src = np.array(edge)
    tex = np.array(texture_tile)
    out = src.copy()
    flat = (src[..., :3] == (189, 239, 244)).all(axis=2) & (src[..., 3] > 0)
    out[flat] = tex[flat]
    # A softer two-step rim sits better on textured snow than the original saturated blue.
    out[(src[..., :3] == (122, 203, 227)).all(axis=2) & (src[..., 3] > 0)] = (150, 208, 228, 255)
    out[(src[..., :3] == (86, 172, 217)).all(axis=2) & (src[..., 3] > 0)] = (118, 170, 208, 255)
    return Image.fromarray(out, "RGBA")


# ---------------------------------------------------------------- forest

NEEDLES = [(12, 40, 50), (17, 56, 62), (24, 74, 72), (34, 94, 82), (52, 118, 94)]
SNOW = [(120, 152, 196), (156, 190, 222), (196, 222, 240), (232, 244, 252), (255, 255, 255)]
BARK = [(52, 34, 38), (84, 56, 50), (118, 82, 66)]
# A tree may overlap the back of a path tile a little, which reads as depth, but no more.
MAX_PATH_COVER = T * T // 4
OUTLINE = (10, 28, 42, 255)


def pine(seed, width=92, height=124, snow_amount=0.62, tiers=None):
    """One snow-laden conifer. Light comes from the upper left."""
    rng = np.random.default_rng(seed)
    pad = 8
    canvas_w, canvas_h = width + pad * 2, height + pad + 14
    cx = canvas_w // 2
    ground = canvas_h - 10
    rgba = np.zeros((canvas_h, canvas_w, 4), dtype=np.uint8)
    yy, xx = np.mgrid[0:canvas_h, 0:canvas_w]
    grain = rng.random((canvas_h, canvas_w))
    needle_noise = fbm(max(canvas_w, canvas_h), seed + 3, base=16, octaves=2)[:canvas_h, :canvas_w]

    # Trunk.
    trunk_top, trunk_half = ground - 26, 5 + width // 40
    trunk = (np.abs(xx - cx) <= trunk_half) & (yy >= trunk_top) & (yy <= ground)
    shade = np.clip(((cx - xx) / (trunk_half * 2) + 0.5) * 2 + (grain - 0.5) * 0.7 + np.sin(yy * 1.7 + xx) * 0.35, 0, 2).round().astype(int)
    rgba[trunk, :3] = np.array(BARK)[shade[trunk]]
    rgba[trunk, 3] = 255

    tier_count = tiers or int(rng.integers(5, 7))
    foliage_bottom = ground - 14
    span = foliage_bottom - pad
    for tier in range(tier_count):  # bottom to top, so each tier overlaps the one below
        t = tier / max(1, tier_count - 1)
        bottom = foliage_bottom - span * (t ** 0.92) * 0.82
        tier_height = span * (0.34 - 0.13 * t)
        top = bottom - tier_height
        half = (width / 2) * (1 - t * 0.82) * float(rng.uniform(0.94, 1.04))
        offset = float(rng.uniform(-2.5, 2.5)) * (1 - t)
        dx = xx - cx - offset

        lumps = np.sin(dx / max(2.5, half / 3.2) + float(rng.uniform(0, 6.3))) * (2.2 + 2.5 * (1 - t))
        tips = np.sin(dx * 1.6 + float(rng.uniform(0, 6.3))) * 1.3
        edge = bottom + lumps + tips - (np.abs(dx) / max(half, 1)) ** 2 * tier_height * 0.05
        profile = np.abs(dx) / np.maximum(1, half)
        roof = top + (bottom - top) * profile ** 1.15
        body = (yy >= roof) & (yy <= edge) & (profile <= 1)

        depth = np.clip((yy - roof) / np.maximum(1, edge - roof), 0, 1)
        light = 0.75 - depth * 0.55 - dx / max(half, 1) * 0.28
        streak = np.sin((dx * np.sign(dx + 0.01) + (yy - top)) * 1.25) * 0.14
        value = light + streak + (needle_noise - 0.5) * 0.5 + (grain - 0.5) * 0.16
        index = np.clip((value * (len(NEEDLES) - 1)).round().astype(int), 0, len(NEEDLES) - 1)
        rgba[body, :3] = np.array(NEEDLES)[index[body]]
        rgba[body, 3] = 255

        # The boughs above throw a dark band onto this tier.
        if tier < tier_count - 1:
            band = body & (depth < 0.2)
            rgba[band, :3] = (rgba[band, :3] * 0.62).astype(np.uint8)

        # Snow rests along the top of each tier and is thicker on the lit side.
        line = roof + (edge - roof) * (snow_amount * (1.0 - 0.22 * dx / max(half, 1))) + np.sin(dx * 0.9 + float(rng.uniform(0, 6.3))) * 2.2 + (needle_noise - 0.5) * 6
        snow = body & (yy <= line)
        snow_light = 0.9 - dx / max(half, 1) * 0.42 - np.clip((yy - roof) / np.maximum(1, line - roof), 0, 1) * 0.42 + (grain - 0.5) * 0.1
        snow_index = np.clip((snow_light * (len(SNOW) - 1)).round().astype(int), 0, len(SNOW) - 1)
        rgba[snow, :3] = np.array(SNOW)[snow_index[snow]]
        rgba[snow, 3] = 255

    # Dark selective outline gives the silhouette weight against the snow.
    solid = rgba[..., 3] > 0
    grown = solid.copy()
    grown[1:, :] |= solid[:-1, :]
    grown[:-1, :] |= solid[1:, :]
    grown[:, 1:] |= solid[:, :-1]
    grown[:, :-1] |= solid[:, 1:]
    rim = grown & ~solid
    rgba[rim] = OUTLINE

    image = Image.fromarray(rgba, "RGBA")
    return image, (cx, ground)


def contact_shadow(width):
    """Blue pooled shadow at a tree's foot, stepped so it stays crisp."""
    w, h = width, 26
    image = Image.new("RGBA", (w, h))
    draw = ImageDraw.Draw(image)
    for step, alpha in enumerate((36, 56, 84)):
        inset = step * 7
        draw.ellipse([inset, step * 3, w - 1 - inset, h - 1 - step * 3], (42, 74, 122, alpha))
    return image


def canopy_fits(image, left, top, keep_clear, walkable):
    """False if a tree at this spot would hide an object, or bury a tile players can walk on."""
    alpha = np.array(image.getchannel("A")) > 0
    x0, y0 = left // T, top // T
    for y in range(y0, (top + image.height - 1) // T + 1):
        for x in range(x0, (left + image.width - 1) // T + 1):
            cell = alpha[max(0, y * T - top) : max(0, (y + 1) * T - top), max(0, x * T - left) : max(0, (x + 1) * T - left)]
            covered = int(cell.sum())
            if not covered:
                continue
            if (x, y) in keep_clear and covered > 40:
                return False
            if (x, y) in walkable and covered > MAX_PATH_COVER:
                return False
    return True


def bake_forest(mask, map_w, map_h, keep_clear=frozenset(), walkable=frozenset()):
    """Plants trees on a repeating jittered grid, so most forest tiles repeat and de-duplicate.

    Where the chosen tree would hide an object or a path, a smaller one is tried, then none.
    """
    variants = [
        pine(101, 92, 124, 0.60), pine(102, 84, 112, 0.68), pine(103, 100, 134, 0.55),
        pine(104, 76, 100, 0.72), pine(105, 94, 120, 0.50), pine(106, 88, 128, 0.78),
    ]
    shadows = {id(v): contact_shadow(v[0].width - 18) for v in variants}
    canvas = Image.new("RGBA", (map_w * T, map_h * T))

    # Deep shade under the canopy, kept well inside so its square tiles never show at the edge.
    shade = Image.new("RGBA", (T, T), (34, 62, 104, 200))
    reach = 6
    for y in range(reach, map_h - reach):
        for x in range(reach, map_w - reach):
            if all(mask[y + dy][x + dx] for dy in range(-reach, reach + 1) for dx in range(-reach, reach + 1)):
                canvas.paste(shade, (x * T, y * T))

    step_x, step_y, period = 48, 40, 8
    jitter = random.Random(9)
    table = {
        (i, j): (jitter.randint(-9, 9), jitter.randint(-7, 7), jitter.randrange(len(variants)))
        for i in range(period) for j in range(period)
    }
    plants = []
    for gy in range(-1, map_h * T // step_y + 2):
        for gx in range(-1, map_w * T // step_x + 2):
            jx, jy, variant = table[gx % period, gy % period]
            px, py = gx * step_x + (gy % 2) * step_x // 2 + jx, gy * step_y + jy
            cx, cy = px // T, py // T
            if 0 <= cx < map_w and 0 <= cy < map_h and mask[cy][cx]:
                plants.append((py, px, variant))
    by_height = sorted(variants, key=lambda v: v[0].height)
    for py, px, variant in sorted(plants):
        chosen = variants[variant]
        candidates = [chosen] + [v for v in by_height if v[0].height < chosen[0].height]
        for image, (ax, ay) in candidates:
            if canopy_fits(image, px - ax, py - ay, keep_clear, walkable):
                shadow = shadows[id(next(v for v in variants if v[0] is image))]
                canvas.alpha_composite(shadow, clamp_origin(px - shadow.width // 2 + 6, py - 12))
                paste_clipped(canvas, image, px - ax, py - ay)
                break
    return canvas


def clamp_origin(x, y):
    return max(x, 0), max(y, 0)


def paste_clipped(canvas, image, x, y):
    left, top = max(0, -x), max(0, -y)
    if left >= image.width or top >= image.height or x >= canvas.width or y >= canvas.height:
        return
    canvas.alpha_composite(image, (max(x, 0), max(y, 0)), (left, top))


def object_shadow(silhouette):
    """A soft blue shadow cast down and to the right from everything standing on the ground."""
    alpha = np.array(silhouette.getchannel("A")) > 40
    out = np.zeros(alpha.shape, dtype=np.uint8)
    for dx, dy, value in ((10, 8, 40), (6, 5, 62), (3, 2, 80)):
        moved = np.zeros_like(alpha)
        moved[dy:, dx:] = alpha[:-dy, :-dx]
        out = np.maximum(out, moved * value)
    out[alpha] = 0
    rgba = np.zeros(alpha.shape + (4,), dtype=np.uint8)
    rgba[..., :3] = (44, 78, 128)
    rgba[..., 3] = out
    return Image.fromarray(rgba, "RGBA")


def upscale_detail(sheet):
    """Redraws art made of 2x2 blocks at true 32px resolution using Scale2x, which rounds off
    staircases along diagonals instead of leaving chunky steps next to the finer new art."""
    src = np.array(sheet.convert("RGBA"))
    small = src[::2, ::2].astype(np.int64)
    packed = (small[..., 0] << 24) | (small[..., 1] << 16) | (small[..., 2] << 8) | small[..., 3]
    p = np.pad(packed, 1, mode="edge")
    b, h, d, f, e = p[:-2, 1:-1], p[2:, 1:-1], p[1:-1, :-2], p[1:-1, 2:], p[1:-1, 1:-1]
    active = (b != h) & (d != f)
    corners = (
        np.where(active & (d == b), d, e),
        np.where(active & (b == f), f, e),
        np.where(active & (d == h), d, e),
        np.where(active & (h == f), f, e),
    )
    height, width = packed.shape
    out = np.zeros((height * 2, width * 2), dtype=np.int64)
    out[0::2, 0::2], out[0::2, 1::2], out[1::2, 0::2], out[1::2, 1::2] = corners
    rgba = np.stack([(out >> 24) & 255, (out >> 16) & 255, (out >> 8) & 255, out & 255], axis=2).astype(np.uint8)
    # Tile grids must not change, or neighbouring tiles would stop lining up.
    return Image.fromarray(rgba[: src.shape[0], : src.shape[1]], "RGBA")
