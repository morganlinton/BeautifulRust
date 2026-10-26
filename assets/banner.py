#!/usr/bin/env python3
"""Render the BeautifulRust README banner.

A procedurally painted pixel-art seascape at golden hour, with a crab on the
foreground rocks and the title set in a hand-built pixel font. Everything is
generated from the standard library: value noise, simple lighting, ordered
dithering onto a median-cut palette, then the text drawn on top.

The README banner (assets/banner.png) is a hand-made painting and is not generated.
Run `python3 assets/banner.py` to regenerate the plugin icon
(.claude-plugin/icon.png) and the earlier procedural banner (assets/banner-procedural.png).
"""
import math
import random
import struct
import zlib
from pathlib import Path

W, H = 418, 235          # native pixel-art resolution
SCALE = 4                # output is W*SCALE x H*SCALE
SEED = 11
HORIZON = 118
SUN = (386, 104)
PALETTE_SIZE = 64
DITHER = 0.06

# --------------------------------------------------------------------------
# noise and color helpers
# --------------------------------------------------------------------------
_rng = random.Random(SEED)
PERM = list(range(256))
_rng.shuffle(PERM)
PERM = PERM * 2


def _h(x, y, seed):
    return PERM[(PERM[(x + seed) & 255] + y) & 255] / 255.0


def _smooth(t):
    return t * t * (3 - 2 * t)


def noise(x, y, seed=0):
    xi = math.floor(x)
    yi = math.floor(y)
    xf = x - xi
    yf = y - yi
    a = _h(xi, yi, seed)
    b = _h(xi + 1, yi, seed)
    c = _h(xi, yi + 1, seed)
    d = _h(xi + 1, yi + 1, seed)
    u = _smooth(xf)
    v = _smooth(yf)
    return a + (b - a) * u + (c - a) * v + (a - b - c + d) * u * v


def fbm(x, y, octaves=4, seed=0, gain=0.5, lac=2.0):
    total = 0.0
    amp = 1.0
    freq = 1.0
    norm = 0.0
    for i in range(octaves):
        total += amp * noise(x * freq, y * freq, seed + i * 17)
        norm += amp
        amp *= gain
        freq *= lac
    return total / norm


def clamp(v, lo=0.0, hi=1.0):
    return lo if v < lo else hi if v > hi else v


def mix(c1, c2, t):
    return (c1[0] + (c2[0] - c1[0]) * t,
            c1[1] + (c2[1] - c1[1]) * t,
            c1[2] + (c2[2] - c1[2]) * t)


def mul(c, k):
    return (c[0] * k, c[1] * k, c[2] * k)


def add(c1, c2):
    return (c1[0] + c2[0], c1[1] + c2[1], c1[2] + c2[2])


def gradient(stops, t):
    if t <= stops[0][0]:
        return stops[0][1]
    for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
        if t <= t1:
            return mix(c0, c1, (t - t0) / (t1 - t0))
    return stops[-1][1]


# --------------------------------------------------------------------------
# scene layers
# --------------------------------------------------------------------------
SKY = [
    (0.00, (0.09, 0.10, 0.30)),
    (0.35, (0.32, 0.24, 0.48)),
    (0.65, (0.78, 0.42, 0.42)),
    (0.85, (0.98, 0.62, 0.38)),
    (1.00, (1.00, 0.86, 0.60)),
]


def render_sky(img):
    sx, sy = SUN
    for y in range(HORIZON + 1):
        t = y / HORIZON
        base = gradient(SKY, t)
        band = clamp(1 - abs(y - 48) / 58.0) ** 0.8
        for x in range(W):
            d = math.hypot(x - sx, y - sy)
            glow = math.exp(-d / 70.0) * 0.45 + math.exp(-d / 24.0) * 0.45
            c = add(base, mul((1.0, 0.72, 0.42), glow))
            if d < 12.5:
                c = mix(c, (1.0, 0.98, 0.86), clamp((12.5 - d) / 1.2))
            if band > 0.02:
                n = fbm(x / 48.0, y / 15.0, 5, seed=3)
                big = fbm(x / 150.0, y / 55.0, 2, seed=9)
                dens = clamp((n - 0.50 + (big - 0.5) * 0.4) * 5.0) * band
                if dens > 0:
                    n2 = fbm((x + 3) / 48.0, (y + 2) / 15.0, 5, seed=3)
                    light = clamp(0.4 + (n - n2) * 7.0)
                    sunfac = clamp(1 - d / 230.0)
                    shadow = (0.42, 0.30, 0.56)
                    lit = mix((0.96, 0.64, 0.62), (1.0, 0.84, 0.62), sunfac)
                    c = mix(c, mix(shadow, lit, light), clamp(dens * 1.4))
            img[y][x] = c


def render_headland(img):
    for x in range(210):
        fade = clamp((210 - x) / 70.0)
        h1 = (22 * fbm(x / 65.0, 0.37, 4, seed=21) + 3) * fade
        top = HORIZON - h1
        for y in range(int(top), HORIZON + 1):
            depth = clamp((y - top) / 9.0)
            c = mix((0.56, 0.40, 0.58), (0.40, 0.29, 0.47), depth)
            img[y][x] = mix(img[y][x], c, 0.9)


SEA = [
    (0.00, (0.92, 0.58, 0.42)),
    (0.08, (0.62, 0.48, 0.54)),
    (0.25, (0.30, 0.38, 0.58)),
    (0.60, (0.16, 0.26, 0.46)),
    (1.00, (0.10, 0.18, 0.36)),
]


def render_sea(img):
    sx, sy = SUN
    for y in range(HORIZON, H):
        u = y - HORIZON
        t = u / (H - HORIZON)
        base = gradient(SEA, t)
        v = 14.0 * math.log1p(u / 5.0)      # streaks compress toward the horizon
        w = 5.0 + u * 0.22
        for x in range(W):
            n = fbm(x / 18.0, v, 3, seed=31)
            fine = noise(x / 6.0, v * 2.0, seed=77)
            shade = (n - 0.5) * 0.18 + (fine - 0.5) * 0.05
            c = add(base, (shade, shade, shade * 0.8))
            crest = clamp((n - 0.62) * 4.0) * (0.2 + 0.5 * t)
            c = mix(c, (0.88, 0.84, 0.86), crest * 0.4)
            r = math.exp(-((x - sx) / w) ** 2) * (1.0 - 0.6 * t)
            if r > 0.02:
                sparkle = clamp((n - 0.45) * 2.5)
                c = mix(c, (1.0, 0.84, 0.55), r * (0.3 + 0.7 * sparkle))
            img[y][x] = c


def render_birds(img):
    for bx, by in ((252, 56), (266, 62), (240, 65)):
        for dx, dy in ((-2, -1), (-1, 0), (0, 0), (1, 0), (2, -1)):
            img[by + dy][bx + dx] = (0.16, 0.12, 0.26)


ROCKS = [  # (cx, cy, rx, ry): the ground is the upper envelope of these ellipses
    (90, 212, 95, 36),
    (40, 225, 60, 30),
    (190, 236, 70, 22),
    (300, 230, 90, 26),
    (390, 222, 70, 34),
    (150, 230, 40, 18),
    (209, 250, 260, 30),
]
GROUND = []


def compute_ground():
    GROUND.clear()
    for x in range(W):
        best = H + 10
        for cx, cy, rx, ry in ROCKS:
            dx = (x - cx) / rx
            if abs(dx) < 1:
                best = min(best, cy - ry * math.sqrt(1 - dx * dx))
        best += (fbm(x / 7.0, 0.5, 3, seed=41) - 0.5) * 6
        GROUND.append(best)


def render_rocks(img):
    for x in range(W):
        gy = GROUND[x]
        gl = GROUND[max(0, x - 2)]
        gr = GROUND[min(W - 1, x + 2)]
        slope = (gl - gr) / 4.0
        for y in range(max(0, int(math.ceil(gy))), H):
            d = y - gy
            n = fbm(x / 9.0, y / 9.0, 4, seed=51)
            n2 = fbm(x / 3.0, y / 3.0, 2, seed=53)
            facet = fbm(x / 22.0, y / 14.0, 2, seed=57)
            base = mix((0.12, 0.09, 0.14), (0.36, 0.26, 0.28), clamp(n * 0.7 + facet * 0.5 - 0.1))
            if n2 > 0.68:
                base = mul(base, 0.55)
            rim = clamp(1 - d / 2.5) * clamp(0.55 + slope * 1.2)
            c = mix(base, (0.98, 0.62, 0.38), rim * 0.9)
            face = clamp(1 - d / 22.0) * clamp(0.5 + slope)
            c = mix(c, (0.75, 0.45, 0.35), face * 0.35)
            img[y][x] = c


def render_pool(img):
    cx, cy, rx, ry = 244, 222, 54, 8
    for y in range(cy - ry, cy + ry + 1):
        for x in range(cx - rx, cx + rx + 1):
            dx = (x - cx) / rx
            dy = (y - cy) / ry
            e = dx * dx + dy * dy + (fbm(x / 9.0, y / 5.0, 2, seed=63) - 0.5) * 0.6
            if e > 1 or y < GROUND[x] + 1:
                continue
            t = clamp((y - (cy - ry)) / (2.0 * ry))
            c = gradient([(0, (0.96, 0.66, 0.46)), (0.5, (0.55, 0.42, 0.52)), (1, (0.28, 0.26, 0.42))], t)
            n = fbm(x / 6.0, y * 1.5, 3, seed=61)
            c = add(c, ((n - 0.5) * 0.18,) * 3)
            if e > 0.82:
                c = mix(c, (0.12, 0.09, 0.13), (e - 0.82) / 0.18)
            img[y][x] = c


def render_foam(img):
    for x in range(W):
        gy = GROUND[x]
        if gy <= HORIZON + 4:
            continue
        for y in range(int(gy) - 5, int(gy)):
            if not 0 <= y < H:
                continue
            f = noise(x / 5.0, y / 2.0, seed=91)
            k = clamp((f - 0.38) * 2.2) * clamp(1 - (gy - 1 - y) / 4.0)
            img[y][x] = mix(img[y][x], (0.93, 0.88, 0.90), k * 0.85)


def render_grass(img):
    rng = random.Random(5)
    for tx in (338, 352, 366, 383, 398, 408):
        ty = GROUND[tx]
        for i in range(rng.randint(5, 8)):
            lean = rng.uniform(-3, 4)
            length = rng.uniform(6, 13)
            x0 = tx + rng.uniform(-3, 3)
            steps = int(length * 2)
            for j in range(steps + 1):
                t = j / steps
                x = int(round(x0 + lean * t * t))
                y = int(round(ty - length * t))
                if 0 <= x < W and 0 <= y < H and y <= GROUND[x] + 1:
                    c = mix((0.20, 0.26, 0.14), (0.78, 0.62, 0.30), t * t * 0.7)
                    img[y][x] = c


def render_crab(img, bx, k=1.15):
    by = int(min(GROUND[int(bx - 26 * k)], GROUND[bx], GROUND[int(bx + 26 * k)]) - 18 * k)
    pix = {}
    base = (0.93, 0.42, 0.14)
    hi = (1.0, 0.74, 0.38)
    lo = (0.50, 0.16, 0.06)

    def shade(nx, ny):
        l = clamp(0.5 + 0.3 * nx - 0.4 * ny)
        if l < 0.55:
            return mix(lo, base, l / 0.55)
        return mix(base, hi, (l - 0.55) / 0.45)

    def ellipse(cx, cy, rx, ry, power=2.0, flat=None):
        rx *= k
        ry *= k
        cx = bx + cx * k
        cy = by + cy * k
        for y in range(int(cy - ry) - 1, int(cy + ry) + 2):
            for x in range(int(cx - rx) - 1, int(cx + rx) + 2):
                dx = (x - cx) / rx
                dy = (y - cy) / ry
                if abs(dx) ** power + abs(dy) ** power <= 1:
                    pix[(x, y)] = flat if flat else shade(dx, dy)

    def segment(x0, y0, x1, y1, w):
        x0, x1 = bx + x0 * k, bx + x1 * k
        y0, y1 = by + y0 * k, by + y1 * k
        w *= k
        steps = int(max(abs(x1 - x0), abs(y1 - y0)) * 2) + 1
        r = int(math.ceil(w))
        for i in range(steps + 1):
            t = i / steps
            x = x0 + (x1 - x0) * t
            y = y0 + (y1 - y0) * t
            for oy in range(-r, r + 1):
                for ox in range(-r, r + 1):
                    if ox * ox + oy * oy <= w * w:
                        pix[(int(round(x + ox)), int(round(y + oy)))] = shade(ox / w * 0.5, oy / w + 0.3)

    for s in (-1, 1):
        for ax, ay, jx, jy, fx, fy, w in [(12, 3, 21, 6, 26, 15, 1.7),
                                          (10, 6, 18, 10, 21, 17, 1.6),
                                          (7, 8, 12, 12, 13, 18, 1.4)]:
            segment(s * ax, ay, s * jx, jy, w)
            segment(s * jx, jy, s * fx, fy, w - 0.3)
    for s in (-1, 1):
        segment(s * 14, -1, s * 22, -7, 2.7)
        segment(s * 22, -7, s * 27, -10, 2.4)
        ellipse(s * 29, -13, 6.5, 5.5, power=2.2)
        segment(s * 32, -17.5, s * 39, -21, 1.9)
        segment(s * 33, -11, s * 40, -14.5, 2.0)
    ellipse(0, 0, 17, 9.5, power=2.5)
    for i in range(-3, 4):
        ellipse(i * 5, -9.5, 2.0, 1.6)
    for y in range(int(by + 4 * k), int(by + 10 * k)):
        for x in range(int(bx - 9 * k), int(bx + 10 * k)):
            if (x, y) in pix:
                pix[(x, y)] = mix(pix[(x, y)], lo, 0.5 * clamp((y - by - 4 * k) / (5.0 * k)))
    for s in (-1, 1):
        segment(s * 5, -8, s * 6, -12.5, 1.1)
        ellipse(s * 6, -14.5, 2.6, 2.6, flat=(0.08, 0.04, 0.05))
        ex, ey = int(bx + s * 6 * k), int(by - 14.5 * k)
        pix[(ex - 1, ey - 1)] = (0.95, 0.95, 0.95)
        pix[(ex, ey - 2)] = (0.95, 0.95, 0.95)
    edge = {}
    for (x, y), c in pix.items():
        if any((x + dx, y + dy) not in pix for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
            edge[(x, y)] = mul(c, 0.55)
    pix.update(edge)
    for y in range(int(by + 9 * k), int(by + 20 * k)):
        for x in range(int(bx - 28 * k), int(bx + 29 * k)):
            dx = (x - bx) / (27.0 * k)
            dy = (y - (by + 15 * k)) / (5.0 * k)
            e = dx * dx + dy * dy
            if e < 1 and 0 <= x < W and y >= GROUND[x]:
                img[y][x] = mul(img[y][x], 1 - 0.45 * (1 - e))
    for (x, y), c in pix.items():
        if 0 <= x < W and 0 <= y < H:
            img[y][x] = c


# --------------------------------------------------------------------------
# dithering, palette, upscale
# --------------------------------------------------------------------------
BAYER = [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]


def quantize(img):
    sample = [tuple(int(clamp(v) * 255) for v in img[y][x])
              for y in range(0, H, 2) for x in range(0, W, 2)]
    boxes = [sample]

    def spread(b):
        return max(max(p[i] for p in b) - min(p[i] for p in b) for i in range(3))

    while len(boxes) < PALETTE_SIZE:
        boxes.sort(key=lambda b: -spread(b) if len(b) > 1 else 0)
        b = boxes.pop(0)
        if len(b) < 2:
            boxes.append(b)
            break
        axis = max(range(3), key=lambda i: max(p[i] for p in b) - min(p[i] for p in b))
        b.sort(key=lambda p: p[axis])
        m = len(b) // 2
        boxes += [b[:m], b[m:]]
    palette = [tuple(int(round(sum(p[i] for p in b) / len(b))) for i in range(3)) for b in boxes if b]

    cache = {}
    out = []
    for y in range(H):
        row = []
        for x in range(W):
            o = (BAYER[y & 3][x & 3] / 16.0 - 0.5) * DITHER
            key = tuple(int(clamp(v + o) * 31.999) for v in img[y][x])
            c = cache.get(key)
            if c is None:
                r, g, b = (k * 255 / 31 for k in key)
                c = min(palette, key=lambda p: (p[0] - r) ** 2 + (p[1] - g) ** 2 + (p[2] - b) ** 2)
                cache[key] = c
            row.append(c)
        out.append(row)
    return out


def upscale(q):
    big = []
    for y in range(H):
        srow = []
        for c in q[y]:
            srow += [c] * SCALE
        for _ in range(SCALE):
            big.append(list(srow))
    return big


# --------------------------------------------------------------------------
# pixel font and title
# --------------------------------------------------------------------------
GLYPHS = {
    'B': ["######.", "#.....#", "#.....#", "#.....#", "######.", "#.....#", "#.....#", "#.....#", "######."],
    'R': ["######.", "#.....#", "#.....#", "#.....#", "######.", "#...#..", "#....#.", "#.....#", "#.....#"],
    'I': ["#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#..", "..#..", "#####"],
    'C': [".#####.", "#.....#", "#......", "#......", "#......", "#......", "#......", "#.....#", ".#####."],
    'e': [".......", ".......", ".......", ".#####.", "#.....#", "#######", "#......", "#.....#", ".#####."],
    'a': [".......", ".......", ".......", ".#####.", "......#", ".######", "#.....#", "#.....#", ".######"],
    'u': [".......", ".......", ".......", "#.....#", "#.....#", "#.....#", "#.....#", "#....##", ".####.#"],
    't': ["..#..", "..#..", "#####", "..#..", "..#..", "..#..", "..#..", "..#.#", "...#."],
    'i': [".#.", ".#.", "...", ".#.", ".#.", ".#.", ".#.", ".#.", ".#."],
    'f': ["..###", ".#...", ".#...", "#####", ".#...", ".#...", ".#...", ".#...", ".#..."],
    'l': [".#.", ".#.", ".#.", ".#.", ".#.", ".#.", ".#.", ".#.", ".##"],
    's': ["......", "......", "......", ".####.", "#.....", ".####.", ".....#", "#....#", ".####."],
    'd': [".....#", ".....#", ".....#", ".#####", "#....#", "#....#", "#....#", "#....#", ".#####"],
    'o': ["......", "......", "......", ".####.", "#....#", "#....#", "#....#", "#....#", ".####."],
    'm': [".......", ".......", ".......", ".##.##.", "#..#..#", "#..#..#", "#..#..#", "#..#..#", "#..#..#"],
    'c': ["......", "......", "......", ".####.", "#....#", "#.....", "#.....", "#....#", ".####."],
    'r': [".....", ".....", ".....", "#.###", "##...", "#....", "#....", "#....", "#...."],
    ',': ["..", "..", "..", "..", "..", "..", "..", ".#", "#."],
    ' ': ["...", "...", "...", "...", "...", "...", "...", "...", "..."],
}


def text_cells(s):
    cells = set()
    x = 0
    for ch in s:
        g = GLYPHS[ch]
        for gy, row in enumerate(g):
            for gx, c in enumerate(row):
                if c == '#':
                    cells.add((x + gx, gy))
        x += len(g[0]) + 1
    return cells, x - 1


def draw_text(big, s, cy, cell, fill, outline, shadow, outline_px, shadow_off):
    cells, wcells = text_cells(s)
    fw, fh = len(big[0]), len(big)
    x0 = (fw - wcells * cell) // 2
    y0 = cy - (9 * cell) // 2

    def paint(dx, dy, color, grow):
        for cx, cyy in cells:
            px = x0 + cx * cell + dx
            py = y0 + cyy * cell + dy
            for yy in range(py - grow, py + cell + grow):
                if 0 <= yy < fh:
                    row = big[yy]
                    for xx in range(px - grow, px + cell + grow):
                        if 0 <= xx < fw:
                            row[xx] = color

    paint(shadow_off, shadow_off, shadow, outline_px)
    paint(0, 0, outline, outline_px)
    paint(0, 0, fill, 0)


# --------------------------------------------------------------------------
# output
# --------------------------------------------------------------------------
def write_png(path, big):
    fh, fw = len(big), len(big[0])
    cache = {}
    raw = bytearray()
    for row in big:
        raw += b"\x00"
        for c in row:
            b = cache.get(c)
            if b is None:
                b = bytes(int(clamp(v / 255.0 if max(c) > 1 else v) * 255) for v in c)
                cache[c] = b
            raw += b

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", fw, fh, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    png += chunk(b"IEND", b"")
    Path(path).write_bytes(png)
    return fw, fh


# --------------------------------------------------------------------------
# icon: the crab alone, square, for the plugin listing
# --------------------------------------------------------------------------
def render_icon(path, size=128):
    """Render a square icon by re-pointing the scene globals at a small canvas."""
    global W, H, HORIZON, SUN, ROCKS
    saved = (W, H, HORIZON, SUN, ROCKS)
    W = H = size
    HORIZON = int(size * 0.44)
    SUN = (int(size * 0.77), int(size * 0.34))
    ROCKS = [(size // 2, int(size * 1.17), int(size * 0.70), int(size * 0.46)),
             (size // 2, int(size * 1.30), size, int(size * 0.40))]
    try:
        img = [[(0.0, 0.0, 0.0)] * W for _ in range(H)]
        render_sky(img)
        render_sea(img)
        compute_ground()
        render_foam(img)
        render_rocks(img)
        render_crab(img, size // 2, k=size / 96.0)
        big = upscale(quantize(img))
        return write_png(path, big)
    finally:
        W, H, HORIZON, SUN, ROCKS = saved
        compute_ground()


def main():
    img = [[(0.0, 0.0, 0.0)] * W for _ in range(H)]
    render_sky(img)
    render_headland(img)
    render_birds(img)
    render_sea(img)
    compute_ground()
    render_foam(img)
    render_rocks(img)
    render_pool(img)
    render_grass(img)
    render_crab(img, 100)
    big = upscale(quantize(img))
    fh = len(big)
    draw_text(big, "Beautiful Rust", int(fh * 0.40), 12,
              fill=(245, 233, 185), outline=(28, 22, 40), shadow=(18, 14, 30),
              outline_px=4, shadow_off=8)
    draw_text(big, "Idiomatic Rust, distilled", int(fh * 0.53), 6,
              fill=(184, 220, 250), outline=(24, 20, 36), shadow=(16, 12, 28),
              outline_px=3, shadow_off=4)
    out = Path(__file__).with_name("banner-procedural.png")
    fw, fh = write_png(out, big)
    print(f"wrote {out} ({fw}x{fh})")
    icon = Path(__file__).resolve().parent.parent / ".claude-plugin" / "icon.png"
    iw, ih = render_icon(icon)
    print(f"wrote {icon} ({iw}x{ih})")


if __name__ == "__main__":
    main()
