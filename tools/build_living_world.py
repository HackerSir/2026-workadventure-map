#!/usr/bin/env python3
"""Generates every "living world" asset procedurally and builds map.tmj.

Nothing here is downloaded: tiles are drawn or derived from the sprites already
in tilesets/, and audio is synthesised. map.tmj is always rebuilt from
tools/map.source.json, so make layout edits to that file in Tiled, then run:

    python tools/build_living_world.py

Outputs: map.tmj, map.png, tilesets/HS_Living32x.png, public/audio/*.wav and
public/portraits/*.png. See textures.py and characters.py for the artwork.
"""
import json
import math
import random
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

import characters
import textures

ROOT = Path(__file__).resolve().parent.parent
T = 32
MAP_W, MAP_H = 100, 50
INK = (20, 33, 63, 255)
GOLD = (255, 209, 102, 255)
GREEN = (92, 214, 130, 255)
WHITE = (255, 255, 255, 255)

# Where things stand on the map, in tiles (see map.tmj).
KEEPERS = {"stand1": (31, 28), "stand2": (39, 22), "stand3": (49, 22), "stand4": (57, 28)}
QUEST_MARKS = {"stand1": (31, 26), "stand2": (39, 20), "stand3": (49, 20), "stand4": (57, 26), "kahoot": (6, 20)}
# The guide cat is the club's mascot, so it keeps its original Meow32x sprite and is not redrawn.
CAT_FEET = (23, 29)
REDRAWN_NPCS = {**KEEPERS, "merchant": (91, 41)}
NPC_FEET = {**REDRAWN_NPCS, "cat": CAT_FEET}
# Everything that was a round tree in the source map; the forest is replanted over these.
OLD_TREE_GIDS = {3026, 3027, 3028, 3029, 3030, 3031, 3058, 3059, 3060, 3061, 3062, 3063, 3092, 3093, 3094, 3095, 3123, 3125, 3126}
ROAD_GID, DRIFT_GID = 2957, 3085
SMOOTHED_TILESETS = {"FD_Winter_Village", "Stand2Color32x", "Tent32x"}
STALLS = {"stand1": (28, 26), "stand2": (36, 20), "stand3": (46, 20), "stand4": (54, 26)}
NEAR_MARKS = {"cat": (23, 27), "merchant": (91, 39), **{k: QUEST_MARKS[k] for k in KEEPERS}}
XMAS_TREE = (40, 27)
PORTAL = (95, 43)
TALK_HOLES = [(35, 24, 50, 40), (90, 41, 99, 49)]  # x0, y0, x1, y1 where voice chat is allowed


class Atlas:
    """Collects 32x32 tiles for the tileset.

    wa-map-optimizer rebuilds tilesets, and it assumes every animation frame is a tile no other
    animation uses, so frames are never shared. To stay small, an unchanged run of frames in one
    animation becomes a single frame with a longer duration.
    """

    def __init__(self):
        self.images, self.tiles, self.static_index = [], [], {}

    def add(self, image):
        self.images.append(image)
        return len(self.images) - 1

    def static(self, image):
        """For tiles that are never animation frames, identical images can share one tile."""
        key = image.tobytes()
        if key not in self.static_index:
            self.static_index[key] = self.add(image)
        return self.static_index[key]

    def animated(self, frames, duration):
        durations = duration if isinstance(duration, list) else [duration] * len(frames)
        runs = []
        for frame, ms in zip(frames, durations):
            data = frame.tobytes()
            if runs and runs[-1][1] == data:
                runs[-1][2] += ms
            else:
                runs.append([frame, data, ms])
        animation = [{"tileid": self.add(frame), "duration": ms} for frame, _, ms in runs]
        base = animation[0]["tileid"]
        if len(animation) > 1:
            self.tiles.append({"id": base, "animation": animation})
        return base

    def named(self, image, name):
        base = self.add(image)
        self.tiles.append({"id": base, "properties": [{"name": "name", "type": "string", "value": name}]})
        return base

    def save(self, path):
        columns = 32
        rows = math.ceil(len(self.images) / columns)
        sheet = Image.new("RGBA", (columns * T, rows * T))
        for i, image in enumerate(self.images):
            sheet.paste(image, ((i % columns) * T, (i // columns) * T))
        sheet.save(path, optimize=True)
        return sheet.size, columns


def tile_from(name, index, columns):
    sheet = Image.open(ROOT / "tilesets" / f"{name}.png").convert("RGBA")
    return sheet.crop(((index % columns) * T, (index // columns) * T, (index % columns + 1) * T, (index // columns + 1) * T))


def shifted(image, dx=0, dy=0):
    out = Image.new("RGBA", image.size)
    out.alpha_composite(image, (max(dx, 0), max(dy, 0)), (max(-dx, 0), max(-dy, 0)))
    return out


def flip(image):
    return image.transpose(Image.FLIP_LEFT_RIGHT)


def from_pattern(pattern, palette, scale=2):
    """Pixel art from strings. Each character is one art pixel, drawn at 2x like the map."""
    h, w = len(pattern), max(map(len, pattern))
    image = Image.new("RGBA", (w * scale, h * scale))
    draw = ImageDraw.Draw(image)
    for y, row in enumerate(pattern):
        for x, c in enumerate(row):
            if c in palette:
                draw.rectangle([x * scale, y * scale, (x + 1) * scale - 1, (y + 1) * scale - 1], palette[c])
    return image


def on_tile(sprite, x, y):
    tile = Image.new("RGBA", (T, T))
    tile.alpha_composite(sprite, (x, y))
    return tile


def split_grid(canvas, cols, rows):
    return [[canvas.crop((c * T, r * T, (c + 1) * T, (r + 1) * T)) for c in range(cols)] for r in range(rows)]


# ---------------------------------------------------------------- map art

BANG = ["..kkk..", "..kyk..", "..kyk..", "..kyk..", "..kkk..", "..kyk..", "..kkk.."]
CHECK = [".......kk", "......kgk", ".....kggk", "kk..kggk.", "kgkkggk..", "kggggk...", ".kggk....", "..kk....."]
QUESTION = [".kkkkk.", "kyyyyyk", "kkkkyyk", "..kyyk.", "..kyk..", "..kkk..", "..kyk..", "..kkk.."]
ICON_COLORS = {"k": INK, "y": GOLD, "g": GREEN}

BUBBLE = [
    ".kkkkkkkkkkkk.",
    "kwwwwwwwwwwwwk",
    "kwwwwwwwwwwwwk",
    "kwwwwwwwwwwwwk",
    "kwwwwwwwwwwwwk",
    ".kkkkwkkkkkkk.",
    "....kwk.......",
    ".....k........",
]

RABBIT = [
    "..k.k.....",
    ".kwkwk....",
    ".kwkwk....",
    ".kwwwk....",
    "kwwkwwkkk.",
    "kwwwwwwwwk",
    ".kwwwwwwwk",
    "..kk.kkkk.",
]


def bobbing_icon(pattern):
    icon = from_pattern(pattern, ICON_COLORS, scale=3)
    x, y = (T - icon.width) // 2, (T - icon.height) // 2 + 2
    return [on_tile(icon, x, y + dy) for dy in (0, -2, -4, -2)]


def speech_frames():
    frames = []
    for lit in range(3):
        bubble = from_pattern(BUBBLE, {"k": INK, "w": WHITE})
        draw = ImageDraw.Draw(bubble)
        for i in range(3):
            x = 6 + i * 6
            draw.rectangle([x, 4, x + 3, 7], INK if i <= lit else (170, 190, 215, 255))
        frames.append(on_tile(bubble, 2, 8))
    return frames


def snow_frames(seed, count=4):
    rng = random.Random(seed)
    flakes = [(rng.randrange(0, 30), rng.randrange(0, T), rng.choice((2, 2, 4)), rng.random() * 6.3) for _ in range(count)]
    frames = []
    for f in range(8):
        image = Image.new("RGBA", (T, T))
        draw = ImageDraw.Draw(image)
        for x, y, size, phase in flakes:
            sway = round(math.sin(f / 8 * 2 * math.pi + phase) * 2) * 2
            px, py = (x + sway) % (T - size), (y + f * 4) % (T - size)
            draw.rectangle([px, py, px + size - 1, py + size - 1], (255, 255, 255, 215))
        frames.append(image)
    return frames


def smoke_frames(seed):
    rng = random.Random(seed)
    puffs = [(rng.randrange(10, 20), i * (64 / 5), rng.random() * 6.3) for i in range(5)]
    tops, bottoms = [], []
    for f in range(10):
        canvas = Image.new("RGBA", (T, T * 2))
        draw = ImageDraw.Draw(canvas)
        for x, offset, phase in puffs:
            y = 62 - (offset + f * 6.4) % 64  # 0 at the top of the column, 62 at the chimney
            life = y / 64  # 1 at the chimney, fading towards the top
            size = 8 - 2 * round(life * 2)
            size = max(2, size)
            px = round((x + math.sin(y / 11 + phase) * 4) / 2) * 2
            py = round(y / 2) * 2
            alpha = int(60 + 130 * life)
            draw.rectangle([px, py, px + size - 1, py + size - 1], (225, 232, 240, alpha))
        tops.append(canvas.crop((0, 0, T, T)))
        bottoms.append(canvas.crop((0, T, T, T * 2)))
    return tops, bottoms


def lamp_glow_grid():
    """A 3x3 warm halo that flickers. Stepped alpha keeps it looking like pixel art."""
    grids = []
    for level in (1.0, 0.86, 0.96, 0.78):
        canvas = Image.new("RGBA", (T * 3, T * 3))
        pixels = canvas.load()
        for y in range(0, T * 3, 2):
            for x in range(0, T * 3, 2):
                d = math.hypot(x + 1 - T * 1.5, y + 1 - T * 1.5) / (T * 1.5)
                if d >= 1:
                    continue
                alpha = round((1 - d) ** 1.6 * 150 * level / 18) * 18
                for oy in (0, 1):
                    for ox in (0, 1):
                        pixels[x + ox, y + oy] = (255, 214, 130, alpha)
        grids.append(split_grid(canvas, 3, 3))
    return grids


def tree_light_frames(bulbs, star):
    """Bulbs only land on opaque parts of the existing Christmas tree."""
    sheet = Image.open(ROOT / "tilesets" / "ChristmasTree32x.png").convert("RGBA")
    alpha = sheet.getchannel("A")
    rng = random.Random(bulbs)
    colors = [(255, 90, 90), (255, 214, 90), (110, 220, 255), (255, 130, 220), (160, 255, 150)]
    spots = []
    while len(spots) < bulbs:
        x, y = rng.randrange(8, 150) // 4 * 4, rng.randrange(20, 140) // 4 * 4
        if alpha.getpixel((x + 2, y + 2)) > 200 and alpha.getpixel((x + 8, y)) > 0 and alpha.getpixel((x - 8, y)) > 0:
            spots.append((x, y, rng.choice(colors), rng.randrange(3)))
    frames = []
    for f in range(3):
        canvas = Image.new("RGBA", (T * 5, T * 5))
        draw = ImageDraw.Draw(canvas)
        for x, y, color, phase in spots:
            on = (f + phase) % 3
            if on == 0:
                draw.rectangle([x - 2, y - 2, x + 5, y + 5], color + (80,))
            draw.rectangle([x, y, x + 3, y + 3], color + (255 if on < 2 else 110,))
        if star:
            top = next(y for y in range(160) if any(alpha.getpixel((x, y)) > 200 for x in range(70, 90)))
            cy, grow = max(top, 12), (6, 8, 7)[f]
            draw.rectangle([80 - grow, cy - 2, 80 + grow - 1, cy + 1], GOLD)
            draw.rectangle([78, cy - grow, 81, cy + grow - 1], GOLD)
        frames.append(split_grid(canvas, 5, 5))
    return frames


def firework_frames(cols, rows, count=14):
    rng = random.Random(7)
    colors = [(255, 110, 90), (255, 214, 90), (120, 230, 255), (255, 140, 225), (170, 255, 150)]
    bursts = []
    for i in range(6):
        cx, cy = rng.randrange(40, cols * T - 40), rng.randrange(40, rows * T - 70)
        rays = [(a / 14 * 2 * math.pi, rng.uniform(0.75, 1)) for a in range(14)]
        bursts.append((i * 2, cx, cy, rng.choice(colors), rays))
    frames = []
    for f in range(count):
        canvas = Image.new("RGBA", (cols * T, rows * T))
        draw = ImageDraw.Draw(canvas)
        for start, cx, cy, color, rays in bursts:
            age = (f - start) % count
            if age >= 7:
                continue
            for angle, power in rays:
                r = (age + 1) * 8 * power
                x = round((cx + math.cos(angle) * r) / 4) * 4
                y = round((cy + math.sin(angle) * r + age * age * 0.6) / 4) * 4
                size = 6 if age < 3 else 4
                draw.rectangle([x, y, x + size - 1, y + size - 1], color + (255 - age * 28,))
        frames.append(split_grid(canvas, cols, rows))
    return frames


def portal_seal_frames():
    """Ice that freezes the existing portal shut until a player has all four cards."""
    rng = random.Random(3)
    base = Image.new("RGBA", (T * 3, T * 3))
    pixels = base.load()
    for y in range(0, T * 3, 4):
        for x in range(0, T * 3, 4):
            shade = rng.choice(((190, 235, 248), (168, 222, 242), (214, 244, 252), (150, 208, 235)))
            for oy in range(4):
                for ox in range(4):
                    pixels[x + ox, y + oy] = shade + (238,)
    draw = ImageDraw.Draw(base)
    for points in (((10, 0), (28, 22), (16, 46), (36, 70), (24, 96)), ((60, 0), (48, 26), (70, 52), (60, 96)), ((28, 22), (60, 34)), ((16, 46), (0, 58)), ((70, 52), (96, 62))):
        draw.line(points, (250, 255, 255, 255), width=2)
    frames = []
    for f in range(6):
        image = base.copy()
        d = ImageDraw.Draw(image)
        x = 8 + f * 16
        d.line((x, 95, x + 34, 0), (255, 255, 255, 170), width=4)
        frames.append(split_grid(image, 3, 3))
    return frames


def sparkle_frames(cols, rows, seed, count=30, color=WHITE):
    rng = random.Random(seed)
    stars = [(rng.randrange(4, cols * T - 8), rng.randrange(4, rows * T - 8), rng.randrange(6)) for _ in range(count)]
    frames = []
    for f in range(6):
        canvas = Image.new("RGBA", (cols * T, rows * T))
        draw = ImageDraw.Draw(canvas)
        for x, y, phase in stars:
            age = (f + phase) % 6
            if age == 0:
                draw.rectangle([x, y, x + 1, y + 1], color)
            elif age == 1:
                draw.rectangle([x - 2, y, x + 3, y + 1], color)
                draw.rectangle([x, y - 2, x + 1, y + 3], color)
            elif age == 2:
                draw.rectangle([x, y, x + 1, y + 1], color[:3] + (150,))
        frames.append(split_grid(canvas, cols, rows))
    return frames


def walker_strip(sprites, length, step=8, hold=6):
    """Slides a sprite along a band of tiles. Each tile loops the part of the walk that crosses it."""
    rows = math.ceil(sprites[0].height / T)
    travel = (length - 1) * T // step
    path = [(i * step, False, i) for i in range(travel)]
    path += [(travel * step, True, 0) for _ in range(hold)]
    path += [((travel - i) * step, True, i) for i in range(travel)]
    path += [(0, False, 0) for _ in range(hold)]
    cells = [[[] for _ in range(length)] for _ in range(rows)]
    for x, backwards, i in path:
        canvas = Image.new("RGBA", (T * length, T * rows))
        sprite = sprites[i % len(sprites)]
        canvas.alpha_composite(flip(sprite) if backwards else sprite, (x, canvas.height - sprite.height))
        for r in range(rows):
            for c in range(length):
                cells[r][c].append(canvas.crop((c * T, r * T, (c + 1) * T, (r + 1) * T)))
    return cells


def stand_tiles(frames):
    """Splits 32x48 sprites into their top and bottom tiles, feet on the bottom one."""
    tops, bottoms = [], []
    for frame in frames:
        canvas = Image.new("RGBA", (T, T * 2))
        canvas.alpha_composite(frame, (0, T * 2 - frame.height))
        tops.append(canvas.crop((0, 0, T, T)))
        bottoms.append(canvas.crop((0, T, T, T * 2)))
    return tops, bottoms


# ---------------------------------------------------------------- audio

RATE = 22050


def write_wav(name, samples):
    data = np.clip(samples, -1, 1)
    with wave.open(str(ROOT / "public" / "audio" / f"{name}.wav"), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(RATE)
        out.writeframes((data * 32000).astype(np.int16).tobytes())


def env(n, attack=0.005, decay=None):
    t = np.arange(n) / RATE
    decay = decay or n / RATE / 4
    return np.minimum(t / attack, 1) * np.exp(-t / decay)


def tone(freq, seconds, kind="sine", attack=0.005, decay=None, vibrato=0):
    n = int(seconds * RATE)
    t = np.arange(n) / RATE
    phase = 2 * np.pi * freq * t + vibrato * np.sin(2 * np.pi * 5.5 * t)
    if kind == "sine":
        wave_data = np.sin(phase)
    elif kind == "bell":
        wave_data = np.sin(phase) + 0.45 * np.sin(2.01 * phase) + 0.2 * np.sin(4.1 * phase)
    else:  # square
        wave_data = np.sign(np.sin(phase)) * 0.5
    return wave_data * env(n, attack, decay)


def place(buffer, sound, at, gain=1.0, wrap=False):
    start = int(at * RATE)
    if wrap:
        index = (start + np.arange(len(sound))) % len(buffer)
        np.add.at(buffer, index, sound * gain)
    else:
        end = min(len(buffer), start + len(sound))
        buffer[start:end] += sound[: end - start] * gain


def looped_noise(seconds, low, high, seed, tilt=0.0):
    """Noise shaped in the frequency domain, so it loops with no seam."""
    rng = np.random.default_rng(seed)
    n = int(seconds * RATE)
    freqs = np.fft.rfftfreq(n, 1 / RATE)
    gain = ((freqs > low) & (freqs < high)) / np.maximum(freqs, 1) ** tilt
    spectrum = gain * np.exp(2j * np.pi * rng.random(len(freqs)))
    out = np.fft.irfft(spectrum, n)
    return out / np.abs(out).max()


def note(semitones):
    return 293.66 * 2 ** (semitones / 12)  # 0 is D4


def town_theme():
    beat = 0.5
    bars = 16
    length = bars * 4 * beat
    music = np.zeros(int(length * RATE))
    chords = [[-12, -5, 0], [-15, -8, -3], [-17, -10, -5], [-19, -12, -7]]  # D Bm G A in low voicing
    rng = random.Random(11)
    scale = [0, 2, 4, 7, 9, 12, 14, 16]
    position = 3
    for bar in range(bars):
        chord = chords[bar % 4]
        for semi in chord:
            place(music, tone(note(semi), 4 * beat + 0.8, attack=0.4, decay=1.6), bar * 4 * beat, 0.07, wrap=True)
        for b, (offset, gain) in enumerate(((0, 0.2), (1, 0.13), (2, 0.16), (3, 0.13))):
            place(music, tone(note(chord[b % 3] + 12), 1.1, "bell", decay=0.45), (bar * 4 + offset) * beat, gain * 0.55, wrap=True)
        rhythm = rng.choice(([0, 1.5, 2, 3], [0, 1, 2.5], [0.5, 1, 2, 3.5], [0, 2]))
        if bar % 8 == 7:
            rhythm = [0]
        for hit in rhythm:
            position = min(len(scale) - 1, max(0, position + rng.choice((-2, -1, 1, 1, 2))))
            place(music, tone(note(scale[position] + 12), 1.6, "bell", decay=0.55), (bar * 4 + hit) * beat, 0.2, wrap=True)
    return music / np.abs(music).max() * 0.85


def kahoot_theme():
    beat = 0.4
    length = beat * 40
    music = np.zeros(int(length * RATE))
    roots = [-12, -12, -9, -7, -12, -12, -14, -7]
    for bar in range(10):
        root = roots[bar % 8]
        for b in range(4):
            place(music, tone(note(root), 0.26, "square", decay=0.09), (bar * 4 + b) * beat, 0.22)
            place(music, tone(1800, 0.03, decay=0.01), (bar * 4 + b + 0.5) * beat, 0.12)
        if bar % 2:
            for i, semi in enumerate((12, 15, 19)):
                place(music, tone(note(root + semi + 12), 0.5, "bell", decay=0.16), (bar * 4 + 1 + i) * beat, 0.16)
    return music / np.abs(music).max() * 0.8


def wind():
    gust = looped_noise(16, 180, 900, 1, 0.6)
    t = np.arange(len(gust)) / RATE
    swell = 0.55 + 0.25 * np.sin(2 * np.pi * t / 16) + 0.2 * np.sin(2 * np.pi * 3 * t / 16 + 1)
    return gust * swell * 0.8


def campfire():
    bed = looped_noise(8, 60, 500, 2, 0.8) * 0.3
    rng = np.random.default_rng(3)
    for _ in range(70):
        pop = rng.normal(size=int(rng.uniform(0.003, 0.012) * RATE))
        place(bed, pop * env(len(pop), 0.0005, 0.003), rng.uniform(0, 7.9), rng.uniform(0.15, 0.6), wrap=True)
    return bed * 0.9


def crunch(seed):
    rng = np.random.default_rng(seed)
    n = int(0.13 * RATE)
    noise = rng.normal(size=n)
    noise = np.convolve(noise, np.ones(3) / 3, "same") - np.convolve(noise, np.ones(30) / 30, "same")
    grains = (rng.random(n) > 0.55) * 0.7 + 0.3
    return noise * grains * env(n, 0.006, 0.035) * 0.9


def voice(pitches, kind="square", length=0.075, gap=0.09):
    out = np.zeros(int((len(pitches) * gap + 0.2) * RATE))
    for i, freq in enumerate(pitches):
        place(out, tone(freq, length, kind, decay=0.04), i * gap, 0.6)
    return out


def meow():
    n = int(0.55 * RATE)
    t = np.arange(n) / RATE
    pitch = 620 + 330 * np.sin(np.pi * np.minimum(t / 0.5, 1)) ** 1.5 - 180 * t
    phase = 2 * np.pi * np.cumsum(pitch) / RATE
    body = sum(np.sin(phase * h) / h for h in range(1, 7))
    formant = 0.6 + 0.4 * np.sin(np.pi * np.minimum(t / 0.5, 1))
    return body * formant * np.minimum(t / 0.05, 1) * np.minimum((0.55 - t) / 0.12, 1) * 0.42


def arpeggio(semitones, gap=0.11, ring=0.8, gain=0.5):
    out = np.zeros(int((len(semitones) * gap + ring) * RATE))
    for i, semi in enumerate(semitones):
        place(out, tone(note(semi), ring, "bell", decay=ring / 3), i * gap, gain)
    return out


def portal_sound():
    n = int(1.6 * RATE)
    t = np.arange(n) / RATE
    sweep = np.sin(2 * np.pi * np.cumsum(120 + 900 * (t / 1.6) ** 2) / RATE)
    air = np.random.default_rng(5).normal(size=n) * 0.2
    return (sweep * 0.5 + air) * np.sin(np.pi * t / 1.6) ** 2


def generate_audio():
    (ROOT / "public" / "audio").mkdir(parents=True, exist_ok=True)
    wrong = np.concatenate([tone(196, 0.18, "square", decay=0.1), tone(147, 0.4, "square", decay=0.2)]) * 0.6
    tracks = {
        "bgm_town": town_theme(),
        "bgm_kahoot": kahoot_theme(),
        "wind": wind(),
        "campfire": campfire(),
        "step1": crunch(1),
        "step2": crunch(2),
        "talk_cat": meow(),
        "talk_keeper": voice([520, 620, 470, 580, 660]),
        "talk_merchant": voice([190, 170, 210, 150], length=0.11, gap=0.13),
        "card": arpeggio([12, 16, 19, 24, 28]),
        "all_clear": arpeggio([0, 4, 7, 12, 16, 19, 24, 19, 24, 28, 31, 36], gap=0.1, ring=1.1),
        "correct": arpeggio([12, 19], gap=0.09),
        "wrong": wrong,
        "someone": arpeggio([19, 24], gap=0.12, ring=0.6, gain=0.35),
        "wave": voice([700, 880, 1040], "sine", 0.1, 0.1),
        "portal": portal_sound(),
    }
    for name, samples in tracks.items():
        write_wav(name, samples)


# ---------------------------------------------------------------- map patching

next_layer_id = 1000


def new_layer_id():
    global next_layer_id
    next_layer_id += 1
    return next_layer_id


def tile_layer(name, cells, visible=True):
    data = [0] * (MAP_W * MAP_H)
    for (x, y), gid in cells.items():
        if 0 <= x < MAP_W and 0 <= y < MAP_H:
            data[y * MAP_W + x] = gid
    return {
        "data": data, "height": MAP_H, "id": new_layer_id(), "name": name, "opacity": 1, "type": "tilelayer",
        "visible": visible, "width": MAP_W, "x": 0, "y": 0,
    }


def find_layer(layers, path):
    head, *rest = path.split("/")
    for layer in layers:
        if layer["name"] == head:
            return find_layer(layer["layers"], "/".join(rest)) if rest else layer
    raise KeyError(path)


def silent_rects():
    """Splits the whole map into rectangles that leave TALK_HOLES uncovered."""
    rows = sorted({0, MAP_H, *(v for h in TALK_HOLES for v in (h[1], h[3] + 1))})
    rects = []
    for top, bottom in zip(rows, rows[1:]):
        holes = sorted(h for h in TALK_HOLES if h[1] <= top and bottom <= h[3] + 1)
        x = 0
        for hole in holes:
            if hole[0] > x:
                rects.append((x, top, hole[0] - x, bottom - top))
            x = hole[2] + 1
        if x < MAP_W:
            rects.append((x, top, MAP_W - x, bottom - top))
    return rects


def layer_map(layers, prefix=""):
    out = {}
    for layer in layers:
        if layer["type"] == "group":
            out.update(layer_map(layer["layers"], prefix + layer["name"] + "/"))
        else:
            out[prefix + layer["name"]] = layer
    return out


def reachable_tiles(layers):
    """Every tile a player can actually walk to from the spawn point."""
    blocked = layers["collisions"]["data"]
    stack = [(i % MAP_W, i // MAP_W) for i, value in enumerate(layers["start"]["data"]) if value]
    seen = set(stack)
    while stack:
        x, y = stack.pop()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < MAP_W and 0 <= ny < MAP_H and (nx, ny) not in seen and not blocked[ny * MAP_W + nx]:
                seen.add((nx, ny))
                stack.append((nx, ny))
    return seen


class TileLookup:
    """Reads a gid's first-frame picture from whichever tileset owns it."""

    def __init__(self, tilesets):
        self.sets = sorted(tilesets, key=lambda t: t["firstgid"])
        self.sheets = {}

    def __call__(self, gid):
        gid &= 0x1FFFFFFF
        owner = next(s for s in reversed(self.sets) if gid >= s["firstgid"])
        index = gid - owner["firstgid"]
        if owner["image"] not in self.sheets:
            self.sheets[owner["image"]] = Image.open(ROOT / owner["image"]).convert("RGBA")
        c = owner["columns"]
        return self.sheets[owner["image"]].crop((index % c * T, index // c * T, (index % c + 1) * T, (index // c + 1) * T))


def build_map():
    path = ROOT / "map.tmj"
    source = json.loads((ROOT / "tools" / "map.source.json").read_text(encoding="utf-8"))
    layers = layer_map(source["layers"])
    lookup = TileLookup(source["tilesets"])

    furniture = find_layer(source["layers"], "furniture")
    floor = find_layer(source["layers"], "floor")
    objects = find_layer(source["layers"], "floorLayer")["objects"]
    kept = [o for o in objects if not o["name"].startswith("silentZone")]

    firstgid = max(t["firstgid"] + t["tilecount"] for t in source["tilesets"])
    atlas = Atlas()
    gid = lambda tile: firstgid + tile
    above_group = []

    # ---- Buildings and props: same drawings, with their chunky steps smoothed.
    for tileset in source["tilesets"]:
        if tileset["name"] in SMOOTHED_TILESETS:
            image = Image.open(ROOT / tileset["image"]).convert("RGBA")
            tileset["image"] = f"tilesets/HS_{tileset['name']}.png"
            textures.upscale_detail(image).save(ROOT / tileset["image"], optimize=True)
    lookup = TileLookup(source["tilesets"])

    # ---- Ground: a seamless 16x16-tile texture for roads and drifts, instead of one flat colour.
    road_tiles = [[gid(atlas.static(t)) for t in row] for row in textures.tile_grid(textures.road_texture())]
    drift_grid = textures.tile_grid(textures.drift_texture())
    drift_tiles = [[gid(atlas.static(t)) for t in row] for row in drift_grid]
    road, drift = layers["floor/floor1"]["data"], layers["floor/floor2"]["data"]
    for i in range(MAP_W * MAP_H):
        x, y = i % MAP_W, i // MAP_W
        if road[i] == ROAD_GID:
            road[i] = road_tiles[y % 16][x % 16]
        if drift[i] == DRIFT_GID:
            drift[i] = drift_tiles[y % 16][x % 16]
        elif drift[i]:
            edge = textures.retexture_edge(lookup(drift[i]), drift_grid[y % 16][x % 16])
            drift[i] = gid(atlas.static(edge))

    # ---- Forest: replace the round trees with a replanted, baked pine forest.
    tree_data, above1 = layers["furniture/tree"]["data"], layers["above/above1"]["data"]
    mask = [[False] * MAP_W for _ in range(MAP_H)]
    for i in range(MAP_W * MAP_H):
        if tree_data[i] in OLD_TREE_GIDS:
            mask[i // MAP_W][i % MAP_W] = True
            tree_data[i] = 0
        if above1[i] in OLD_TREE_GIDS:
            above1[i] = 0
    keep_clear = {(x, y - r) for (x, y) in NPC_FEET.values() for r in (0, 1)}
    for name in ("furniture/furniture1", "furniture/market", "above/above1", "above/market"):
        keep_clear |= {(i % MAP_W, i // MAP_W) for i, value in enumerate(layers[name]["data"]) if value}
    forest = textures.bake_forest(mask, MAP_W, MAP_H, keep_clear, reachable_tiles(layers))
    forest_low, forest_high = {}, {}
    for y in range(MAP_H):
        for x in range(MAP_W):
            cell = forest.crop((x * T, y * T, (x + 1) * T, (y + 1) * T))
            if cell.getbbox():
                (forest_low if mask[y][x] else forest_high)[(x, y)] = gid(atlas.static(cell))
    furniture["layers"].insert(0, tile_layer("hs_forest", forest_low))
    above_group.append(tile_layer("forest_tops", forest_high))

    # ---- Shadows cast by buildings, stalls and lamps give the flat map some depth.
    silhouette = Image.new("RGBA", (MAP_W * T, MAP_H * T))
    for name in ("furniture/furniture1", "furniture/market", "above/above1", "above/market"):
        for i, value in enumerate(layers[name]["data"]):
            if value:
                silhouette.alpha_composite(lookup(value), (i % MAP_W * T, i // MAP_W * T))
    cast = textures.object_shadow(silhouette)
    shadow_cells = {}
    for y in range(MAP_H):
        for x in range(MAP_W):
            cell = cast.crop((x * T, y * T, (x + 1) * T, (y + 1) * T))
            if cell.getbbox():
                shadow_cells[(x, y)] = gid(atlas.static(cell))
    floor["layers"].append(tile_layer("hs_shadow", shadow_cells))

    # ---- NPCs: redrawn at full resolution, a tile and a half tall, with idle animations.
    npc = layers["furniture/npc"]
    for name, (x, y) in REDRAWN_NPCS.items():
        frames, durations = characters.idle_frames(name)
        top, bottom = stand_tiles(frames)
        npc["data"][y * MAP_W + x] = gid(atlas.animated(bottom, durations))
        npc["data"][(y - 1) * MAP_W + x] = gid(atlas.animated(top, durations))

    # ---- Things wandering the streets.
    walker_cells = {}
    rabbit = on_tile(from_pattern(RABBIT, {"k": INK, "w": (244, 248, 252, 255)}), 6, 14)
    hops = [shifted(rabbit, dy=d) for d in (0, -4, -6, -4)]
    for sprite_set, x0, y0, length, duration in (
        (characters.walk_frames("villager_a"), 60, 29, 12, 170),
        (characters.walk_frames("villager_b"), 8, 31, 12, 190),
        (hops, 34, 37, 6, 130),
        (characters.walk_frames("villager_a"), 48, 7, 7, 200),
    ):
        for r, row in enumerate(walker_strip(sprite_set, length)):
            for i, frames in enumerate(row):
                walker_cells[(x0 + i, y0 + r)] = gid(atlas.animated(frames, duration))
    furniture["layers"].append(tile_layer("hs_walkers", walker_cells))
    floor["layers"].append(tile_layer("hs_trail", {}))

    # Footprint tile: named, so the optimizer keeps it and scripts can place it by name.
    print_tile = Image.new("RGBA", (T, T))
    draw = ImageDraw.Draw(print_tile)
    for x, y in ((8, 6), (18, 17)):
        draw.rounded_rectangle([x, y, x + 6, y + 9], 2, (120, 160, 200, 190))
        draw.rectangle([x + 1, y + 1, x + 5, y + 3], (96, 134, 180, 210))
        draw.line([x, y + 10, x + 6, y + 10], (244, 250, 254, 220))
    atlas.named(print_tile, "hs_footprint")

    # Weather and chimneys.
    rng = random.Random(42)
    snow_tiles = [gid(atlas.animated(snow_frames(s), 170)) for s in range(4)]
    snow_cells = {(x, y): rng.choice(snow_tiles) for y in range(MAP_H) for x in range(MAP_W) if rng.random() < 0.14}
    above_group.append(tile_layer("snow", snow_cells))

    above = above1
    roof_gids = {3164: 1, 3200: 0, 3368: 0, 3360: 0, 3324: 0, 3600: 0, 3796: 0, 3196: 1, 3604: 0, 3332: 0}
    smoke_cells = {}
    for i, value in enumerate(above):
        if value in roof_gids:
            x, y = i % MAP_W, i // MAP_W
            top, bottom = smoke_frames(i)
            smoke_cells[(x + roof_gids[value], y - 1)] = gid(atlas.animated(top, 130))
            smoke_cells[(x + roof_gids[value], y)] = gid(atlas.animated(bottom, 130))
    above_group.append(tile_layer("smoke", smoke_cells))

    # Lamps: the same lamp-head tile (3160) appears at each of the 21 street lamps.
    glow = lamp_glow_grid()
    glow_tiles = [[gid(atlas.animated([g[r][c] for g in glow], 260)) for c in range(3)] for r in range(3)]
    glow_cells = {}
    for i, value in enumerate(above):
        if value == 3160:
            x, y = i % MAP_W, i // MAP_W
            for r in range(3):
                for c in range(3):
                    glow_cells[(x + c - 1, y + r - 1)] = glow_tiles[r][c]
    above_group.append(tile_layer("lamps", glow_cells))

    # Reactive markers, shown and hidden by src/main.ts.
    bang = gid(atlas.animated(bobbing_icon(BANG), 170))
    check = gid(atlas.animated(bobbing_icon(CHECK), 220))
    question = gid(atlas.animated(bobbing_icon(QUESTION), 220))
    speech = gid(atlas.animated(speech_frames(), 300))
    for name, cell in QUEST_MARKS.items():
        above_group.append(tile_layer(f"{name}_todo", {cell: bang}, False))
        above_group.append(tile_layer(f"{name}_done", {cell: check}, False))
    above_group.append(tile_layer("merchant_locked", {NEAR_MARKS["merchant"]: question}, False))
    above_group.append(tile_layer("merchant_ready", {NEAR_MARKS["merchant"]: bang}, False))
    for name, cell in NEAR_MARKS.items():
        above_group.append(tile_layer(f"{name}_near", {(cell[0] + 1, cell[1]): speech}, False))

    # A finished stall keeps sparkling.
    sparkles = sparkle_frames(3, 2, 21, 16, GOLD)
    sparkle_tiles = [[gid(atlas.animated([f[r][c] for f in sparkles], 160)) for c in range(3)] for r in range(2)]
    for name, (x, y) in STALLS.items():
        above_group.append(tile_layer(f"{name}_lit", {(x + c, y + r): sparkle_tiles[r][c] for r in range(2) for c in range(3)}, False))

    # Town-wide tree: the more quests everyone clears, the more it lights up.
    for tier, (bulbs, star) in enumerate(((14, False), (34, False), (70, True)), 1):
        frames = tree_light_frames(bulbs, star)
        cells = {}
        for r in range(5):
            for c in range(5):
                cells[(XMAS_TREE[0] + c, XMAS_TREE[1] + r)] = gid(atlas.animated([f[r][c] for f in frames], 340))
        above_group.append(tile_layer(f"tree{tier}", cells, False))

    # The portal stays frozen until a player holds all four cards.
    seal = portal_seal_frames()
    above_group.append(tile_layer("portal_sealed", {
        (PORTAL[0] + c, PORTAL[1] + r): gid(atlas.animated([f[r][c] for f in seal], 240)) for r in range(3) for c in range(3)
    }))
    opened = sparkle_frames(5, 5, 33, 34, (214, 190, 255, 255))
    above_group.append(tile_layer("portal_open", {
        (PORTAL[0] - 1 + c, PORTAL[1] - 1 + r): gid(atlas.animated([f[r][c] for f in opened], 140)) for r in range(5) for c in range(5)
    }, False))

    # Fireworks over the plaza whenever anyone in town finishes everything.
    fireworks = firework_frames(9, 7)
    above_group.append(tile_layer("fireworks", {
        (38 + c, 21 + r): gid(atlas.animated([f[r][c] for f in fireworks], 120)) for r in range(7) for c in range(9)
    }, False))

    # Write the tileset and register it.
    (width, height), columns = atlas.save(ROOT / "tilesets" / "HS_Living32x.png")
    source["tilesets"].append({
        "columns": columns, "firstgid": firstgid, "image": "tilesets/HS_Living32x.png",
        "imageheight": height, "imagewidth": width, "margin": 0, "name": "HS_Living32x",
        "spacing": 0, "tilecount": len(atlas.images), "tileheight": T, "tilewidth": T, "tiles": atlas.tiles,
    })

    source["layers"].append({"id": new_layer_id(), "layers": above_group, "name": "hs", "opacity": 1, "type": "group", "visible": True, "x": 0, "y": 0})

    # Objects: silence everywhere but the talk spots, plus new triggers.
    next_id = max(o["id"] for o in kept) + 1

    def add(name, x, y, w, h, kind="area", props=None):
        nonlocal next_id
        kept.append({"id": next_id, "name": name, "type": kind, "rotation": 0, "visible": True, "x": x * T, "y": y * T, "width": w * T, "height": h * T, **({"properties": props} if props else {})})
        next_id += 1

    for n, (x, y, w, h) in enumerate(silent_rects()):
        add(f"silentZone{n}", x, y, w, h, props=[{"name": "silent", "type": "bool", "value": True}])
    add("hsPlaza", TALK_HOLES[0][0], TALK_HOLES[0][1], TALK_HOLES[0][2] - TALK_HOLES[0][0] + 1, TALK_HOLES[0][3] - TALK_HOLES[0][1] + 1)
    add("hsCampfire", TALK_HOLES[1][0], TALK_HOLES[1][1], TALK_HOLES[1][2] - TALK_HOLES[1][0] + 1, TALK_HOLES[1][3] - TALK_HOLES[1][1] + 1)
    add("hsPortalGate", PORTAL[0], PORTAL[1] + 2, 3, 1)
    add("hsFromPortal", 42, 38, 1, 1, props=[{"name": "start", "type": "bool", "value": True}])
    add("hsFromOffice", 55, 30, 1, 1, props=[{"name": "start", "type": "bool", "value": True}])
    add("townClears", 1, 1, 0, 0, "variable", [{"name": "default", "type": "int", "value": 0}, {"name": "persist", "type": "bool", "value": True}])
    find_layer(source["layers"], "floorLayer")["objects"] = kept
    source["nextobjectid"] = next_id
    source["nextlayerid"] = next_layer_id + 1

    path.write_text(json.dumps(source, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    render_preview(source, atlas.images, firstgid)
    print(f"tileset: {len(atlas.images)} tiles, {width}x{height}; smoke cells {len(smoke_cells)}, lamp cells {len(glow_cells)}, snow cells {len(snow_cells)}")


def render_preview(source, images, firstgid):
    """Writes map.png, which the landing page and WorkAdventure's map info both show."""
    lookup = TileLookup(source["tilesets"])
    canvas = Image.new("RGBA", (MAP_W * T, MAP_H * T), (255, 255, 255, 255))

    def draw(layers):
        for layer in layers:
            if not layer.get("visible", True) or layer["name"] in ("collisions", "start", "snow"):
                continue
            if layer["type"] == "group":
                draw(layer["layers"])
            elif layer["type"] == "tilelayer":
                for i, value in enumerate(layer["data"]):
                    if value:
                        tile = images[value - firstgid] if value >= firstgid else lookup(value)
                        canvas.alpha_composite(tile, (i % MAP_W * T, i // MAP_W * T))

    draw(source["layers"])
    canvas.convert("RGB").save(ROOT / "map.png", optimize=True)


def generate_portraits():
    out = ROOT / "public" / "portraits"
    out.mkdir(parents=True, exist_ok=True)
    for name in REDRAWN_NPCS:
        sprite = characters.sprite(characters.LOOKS[name])
        box = sprite.getbbox()
        sprite.crop((box[0], box[1], box[2], box[3] - 6)).save(out / f"{name}.png", optimize=True)
    # The cat's sheet holds its animation frames; frame 0 is in column 0, top and bottom rows.
    cat = Image.open(ROOT / "tilesets" / "Meow32x.png").convert("RGBA").crop((0, 0, T, T * 2))
    cat.crop(cat.getbbox()).save(out / "cat.png", optimize=True)


if __name__ == "__main__":
    import build_office

    build_office.build()
    generate_audio()
    generate_portraits()
    build_map()
