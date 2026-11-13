"""Hand-specified NPC sprites, drawn at full 32px resolution on a 32x48 canvas."""
from dataclasses import dataclass, field

import numpy as np
from PIL import Image, ImageDraw

W, H = 32, 48
OUTLINE = (24, 22, 44, 255)
SKIN = [(236, 186, 150), (250, 212, 178), (255, 230, 204)]
SKIN_DARK = [(170, 112, 84), (196, 136, 104), (220, 162, 128)]
BOOT = [(46, 36, 44), (72, 56, 60), (98, 78, 78)]
PANTS = [(44, 54, 82), (62, 74, 106), (84, 98, 132)]


def shaded(draw, box, ramp, shape="rect"):
    """Fills a box with a 3-step ramp, lit from the upper left."""
    x0, y0, x1, y1 = box
    painter = draw.rectangle if shape == "rect" else draw.ellipse
    painter(box, ramp[1] + (255,))
    if shape == "rect":
        draw.rectangle([x1 - max(1, (x1 - x0) // 3), y0, x1, y1], ramp[0] + (255,))
        draw.line([x0, y0, x0, y1], ramp[2] + (255,))
    else:
        draw.arc([x0, y0, x1, y1], 20, 150, ramp[0] + (255,), width=2)
        draw.arc([x0 + 1, y0 + 1, x1 - 1, y1 - 1], 190, 290, ramp[2] + (255,), width=1)


@dataclass
class Look:
    coat: list
    trim: tuple = (240, 244, 250)
    skin: list = field(default_factory=lambda: SKIN)
    hair: list | None = None
    hair_style: str = "short"
    hat: str | None = None
    hat_color: list | None = None
    scarf: list | None = None
    beard: bool = False
    glasses: bool = False
    apron: tuple | None = None
    ears: bool = False
    pants: list = field(default_factory=lambda: PANTS)
    boots: list = field(default_factory=lambda: BOOT)


def _legs(draw, look, step, y):
    left, right = y, y
    if step == 1:
        left -= 2
    elif step == 3:
        right -= 2
    for x, top in ((11, left), (17, right)):
        shaded(draw, [x, top, x + 4, top + 5], look.pants)
        shaded(draw, [x - 1, top + 5, x + 4, top + 8], look.boots)
        draw.line([x, top + 6, x + 1, top + 6], look.boots[2] + (255,))


def _torso(draw, look, y, arm):
    shaded(draw, [9, y, 22, y + 12], look.coat)
    # Coat hem flares slightly, and a placket and buttons give it some construction.
    draw.rectangle([8, y + 9, 23, y + 12], look.coat[1] + (255,))
    draw.rectangle([20, y + 9, 23, y + 12], look.coat[0] + (255,))
    draw.line([8, y + 12, 23, y + 12], look.trim + (255,))
    draw.line([15, y + 1, 15, y + 11], look.coat[0] + (255,))
    for by in (y + 4, y + 7):
        draw.point([16, by], look.trim + (255,))
    if look.apron:
        draw.rectangle([11, y + 4, 20, y + 12], look.apron + (255,))
        draw.line([11, y + 4, 11, y + 12], tuple(min(255, c + 22) for c in look.apron) + (255,))
        draw.line([20, y + 4, 20, y + 12], tuple(int(c * 0.78) for c in look.apron) + (255,))
    # Arms and mittens. A raised arm is the wave pose.
    if arm == "wave":
        shaded(draw, [23, y - 6, 26, y + 3], look.coat)
        draw.rectangle([23, y - 9, 26, y - 6], look.trim + (255,))
    else:
        shaded(draw, [23, y + 1, 26, y + 9], look.coat)
        draw.rectangle([23, y + 9, 26, y + 11], look.trim + (255,))
    shaded(draw, [5, y + 1, 8, y + 9], look.coat)
    draw.rectangle([5, y + 9, 8, y + 11], look.trim + (255,))
    if look.scarf:
        draw.rectangle([9, y - 1, 22, y + 2], look.scarf[1] + (255,))
        draw.rectangle([18, y - 1, 22, y + 2], look.scarf[0] + (255,))
        draw.rectangle([17, y + 2, 20, y + 8], look.scarf[1] + (255,))
        draw.line([17, y + 8, 20, y + 8], look.scarf[2] + (255,))
        draw.line([9, y, 16, y], look.scarf[2] + (255,))


def _head(draw, look, y, blink):
    x0, x1 = 7, 24
    y0, y1 = y, y + 15
    draw.rounded_rectangle([x0, y0, x1, y1], 5, fill=look.skin[1] + (255,))
    draw.rectangle([x1 - 2, y0 + 4, x1, y1 - 3], look.skin[0] + (255,))
    draw.point([x0 + 3, y0 + 10], (244, 160, 150, 255))
    draw.point([x0 + 4, y0 + 10], (244, 160, 150, 255))
    draw.point([x1 - 4, y0 + 10], (236, 150, 142, 255))
    draw.point([x1 - 3, y0 + 10], (236, 150, 142, 255))

    # Eyes.
    eye_y = y0 + 7
    for ex in (x0 + 4, x1 - 6):
        if blink:
            draw.line([ex, eye_y + 2, ex + 2, eye_y + 2], (40, 30, 50, 255))
        else:
            draw.rectangle([ex, eye_y, ex + 2, eye_y + 3], (34, 30, 58, 255))
            draw.point([ex, eye_y], (255, 255, 255, 255))
            draw.line([ex + 2, eye_y + 3, ex + 2, eye_y + 2], (86, 110, 170, 255))
    draw.line([x0 + 8, y0 + 12, x0 + 10, y0 + 12], (176, 96, 88, 255))
    if look.glasses:
        for ex in (x0 + 3, x1 - 7):
            draw.rectangle([ex, eye_y - 1, ex + 4, eye_y + 4], outline=(70, 60, 80, 255))
        draw.line([x0 + 8, eye_y, x1 - 8, eye_y], (70, 60, 80, 255))

    hair = look.hair
    if hair:
        if look.hair_style == "short":
            draw.rounded_rectangle([x0 - 1, y0 - 1, x1 + 1, y0 + 6], 4, fill=hair[1] + (255,))
            draw.rectangle([x0 - 1, y0 + 4, x0 + 1, y0 + 9], hair[1] + (255,))
            draw.rectangle([x1 - 1, y0 + 4, x1 + 1, y0 + 9], hair[0] + (255,))
            for fx in range(x0 + 2, x1 - 1, 3):
                draw.line([fx, y0 + 6, fx + 1, y0 + 7], hair[1] + (255,))
            draw.line([x0 + 3, y0 + 1, x0 + 9, y0 + 1], hair[2] + (255,))
        elif look.hair_style == "long":
            draw.rounded_rectangle([x0 - 2, y0 - 1, x1 + 2, y0 + 7], 5, fill=hair[1] + (255,))
            draw.rectangle([x0 - 2, y0 + 5, x0 + 1, y0 + 21], hair[1] + (255,))
            draw.rectangle([x1 - 1, y0 + 5, x1 + 2, y0 + 21], hair[0] + (255,))
            draw.line([x0 - 1, y0 + 7, x0 - 1, y0 + 19], hair[2] + (255,))
            draw.line([x0 + 3, y0 + 1, x0 + 10, y0 + 1], hair[2] + (255,))
            for fx in range(x0 + 2, x1 - 1, 3):
                draw.line([fx, y0 + 7, fx + 1, y0 + 8], hair[1] + (255,))
    if look.beard:
        white = (236, 240, 246, 255)
        draw.rectangle([x0 + 1, y0 + 11, x1 - 1, y0 + 18], white)
        draw.rectangle([x0 + 4, y0 + 18, x1 - 4, y0 + 21], white)
        draw.line([x1 - 3, y0 + 12, x1 - 3, y0 + 18], (196, 206, 222, 255))
        draw.line([x0 + 7, y0 + 12, x1 - 7, y0 + 12], (176, 96, 88, 255))
    if look.hat == "beanie":
        c = look.hat_color
        draw.rounded_rectangle([x0 - 1, y0 - 4, x1 + 1, y0 + 4], 5, fill=c[1] + (255,))
        draw.rectangle([x1 - 3, y0 - 2, x1 + 1, y0 + 4], c[0] + (255,))
        draw.line([x0 + 2, y0 - 3, x0 + 9, y0 - 3], c[2] + (255,))
        draw.rectangle([x0 - 1, y0 + 3, x1 + 1, y0 + 6], c[2] + (255,))
        for fx in range(x0, x1 + 1, 2):
            draw.line([fx, y0 + 4, fx, y0 + 6], c[0] + (255,))
        draw.ellipse([x0 + 6, y0 - 8, x0 + 11, y0 - 3], (246, 246, 250, 255))
    elif look.hat == "fur":
        c = look.hat_color
        draw.rounded_rectangle([x0 - 2, y0 - 3, x1 + 2, y0 + 5], 3, fill=c[1] + (255,))
        draw.rectangle([x1 - 3, y0 - 2, x1 + 2, y0 + 5], c[0] + (255,))
        draw.rectangle([x0 - 2, y0 + 3, x1 + 2, y0 + 6], (238, 232, 222, 255))
        draw.rectangle([x0 - 2, y0 + 5, x0 + 1, y0 + 12], (238, 232, 222, 255))
        draw.rectangle([x1 - 1, y0 + 5, x1 + 2, y0 + 12], (214, 206, 198, 255))
    if look.ears:
        black, pink = (32, 30, 40, 255), (240, 150, 170, 255)
        draw.polygon([(x0 - 1, y0 + 3), (x0, y0 - 5), (x0 + 6, y0)], fill=black)
        draw.polygon([(x1 + 1, y0 + 3), (x1, y0 - 5), (x1 - 6, y0)], fill=black)
        draw.polygon([(x0 + 1, y0 + 1), (x0 + 1, y0 - 2), (x0 + 4, y0)], fill=pink)
        draw.polygon([(x1 - 1, y0 + 1), (x1 - 1, y0 - 2), (x1 - 4, y0)], fill=pink)
        # Whiskers.
        for wy in (y0 + 9, y0 + 11):
            draw.line([x0 - 3, wy, x0 + 1, wy], (70, 66, 86, 255))
            draw.line([x1 - 1, wy, x1 + 3, wy], (70, 66, 86, 255))


def _outlined(image):
    rgba = np.array(image)
    solid = rgba[..., 3] > 0
    grown = solid.copy()
    grown[1:, :] |= solid[:-1, :]
    grown[:-1, :] |= solid[1:, :]
    grown[:, 1:] |= solid[:, :-1]
    grown[:, :-1] |= solid[:, 1:]
    rgba[grown & ~solid] = OUTLINE
    return Image.fromarray(rgba, "RGBA")


def sprite(look, bob=0, blink=False, step=0, arm=None, flip=False):
    """bob raises the body a pixel for breathing; step 0-3 is the walk cycle."""
    image = Image.new("RGBA", (W, H))
    draw = ImageDraw.Draw(image)

    # Shadow on the snow, under everything.
    shadow = Image.new("RGBA", (W, H))
    ImageDraw.Draw(shadow).ellipse([5, H - 7, 27, H - 1], (44, 78, 128, 110))

    base = H - 9
    _legs(draw, look, step, base - 7)
    lift = bob + (1 if step in (1, 3) else 0)
    _torso(draw, look, base - 19 - lift, arm)
    _head(draw, look, base - 33 - lift, blink)

    image = _outlined(image)
    shadow.alpha_composite(image)
    if flip:
        shadow = shadow.transpose(Image.FLIP_LEFT_RIGHT)
    return shadow


NAVY = [(30, 44, 88), (48, 68, 124), (74, 100, 164)]
BLACK = [(22, 22, 32), (40, 40, 54), (66, 66, 84)]
PURPLE = [(92, 44, 130), (130, 66, 174), (172, 110, 214)]
RED = [(142, 34, 46), (190, 54, 62), (234, 96, 92)]
GREEN = [(34, 84, 74), (50, 116, 96), (84, 154, 124)]
BROWN = [(84, 54, 44), (118, 80, 60), (156, 112, 84)]
GOLD_HAIR = [(204, 142, 52), (240, 186, 82), (255, 226, 136)]
DARK_HAIR = [(30, 28, 44), (50, 46, 70), (82, 76, 106)]
RUST_HAIR = [(122, 58, 38), (166, 84, 50), (206, 122, 76)]
GREY_BLUE = [(70, 84, 112), (98, 116, 146), (136, 154, 184)]

LOOKS = {
    "stand1": Look(coat=BROWN, trim=(234, 222, 200), hat="fur", hat_color=BROWN, beard=True, skin=SKIN_DARK, apron=(204, 188, 158)),
    "stand2": Look(coat=GREEN, hair=GOLD_HAIR, hair_style="long", scarf=RED, pants=[(92, 56, 56), (120, 76, 72), (150, 100, 92)]),
    "stand3": Look(coat=GREY_BLUE, hair=RUST_HAIR, glasses=True, apron=(226, 222, 212), scarf=None),
    "stand4": Look(coat=[(36, 40, 52), (58, 64, 82), (90, 98, 120)], hair=DARK_HAIR, glasses=True, scarf=[(40, 120, 200), (60, 150, 230), (130, 196, 250)]),
    "merchant": Look(coat=BLACK, trim=(150, 110, 200), hat="beanie", hat_color=PURPLE, hair=DARK_HAIR, scarf=PURPLE, pants=BLACK),
    "villager_a": Look(coat=RED, hat="beanie", hat_color=NAVY, hair=DARK_HAIR, scarf=[(214, 170, 60), (240, 204, 92), (255, 232, 150)]),
    "villager_b": Look(coat=NAVY, hair=RUST_HAIR, hair_style="long", hat="fur", hat_color=GREY_BLUE, scarf=None),
}


def idle_frames(name):
    """Breathes, blinks, glances the other way and occasionally waves."""
    look = LOOKS[name]
    return (
        [sprite(look), sprite(look, bob=1), sprite(look), sprite(look, blink=True), sprite(look), sprite(look, bob=1),
         sprite(look, flip=True), sprite(look, bob=1, flip=True), sprite(look, blink=True, flip=True), sprite(look),
         sprite(look, arm="wave"), sprite(look, bob=1, arm="wave"), sprite(look, arm="wave"), sprite(look)],
        [800, 700, 800, 140, 900, 700, 1000, 700, 140, 800, 260, 260, 260, 900],
    )


def walk_frames(name):
    look = LOOKS[name]
    return [sprite(look, step=s) for s in range(4)]
