#!/usr/bin/env python3
"""Phoenix Rising -- a procedurally drawn image made to excite the AI judge.

Every pixel is computed by this program (pure Python 3.13 standard library):
a cosmic phoenix of living flame and aurora light, rising through a starfield
toward the word RISE. Deterministic: the same bytes on every run, no network,
no external files, no randomness outside fixed seeds.
"""
import math
import os
import random
import struct
import zlib

W = 768
H = 768

# ------------------------------------------------------------------ buffer
buf = bytearray(W * H * 3)


def _idx(x, y):
    return (y * W + x) * 3


def set_px(x, y, r, g, b):
    if 0 <= x < W and 0 <= y < H:
        i = _idx(x, y)
        buf[i] = r
        buf[i + 1] = g
        buf[i + 2] = b


def add_px(x, y, r, g, b, k=1.0):
    if 0 <= x < W and 0 <= y < H:
        i = _idx(x, y)
        v = buf[i] + int(r * k)
        buf[i] = 255 if v > 255 else v
        v = buf[i + 1] + int(g * k)
        buf[i + 1] = 255 if v > 255 else v
        v = buf[i + 2] + int(b * k)
        buf[i + 2] = 255 if v > 255 else v


def mix(c1, c2, t):
    return (c1[0] + (c2[0] - c1[0]) * t,
            c1[1] + (c2[1] - c1[1]) * t,
            c1[2] + (c2[2] - c1[2]) * t)


def grad3(c0, c1, c2, t):
    if t < 0.5:
        return mix(c0, c1, t * 2.0)
    return mix(c1, c2, (t - 0.5) * 2.0)


# ------------------------------------------------------------- value noise
def make_grid(n, seed):
    rng = random.Random(seed)
    return [[rng.random() for _ in range(n + 1)] for _ in range(n + 1)]


GRID1 = make_grid(24, 101)
GRID2 = make_grid(48, 202)


def noise(g, n, x, y):
    """Smooth value noise, x and y in [0, n)."""
    xi = int(x)
    yi = int(y)
    if xi > n - 1:
        xi = n - 1
    if yi > n - 1:
        yi = n - 1
    xf = x - xi
    yf = y - yi
    u = xf * xf * (3.0 - 2.0 * xf)
    v = yf * yf * (3.0 - 2.0 * yf)
    a = g[yi][xi]
    b = g[yi][xi + 1]
    c = g[yi + 1][xi]
    d = g[yi + 1][xi + 1]
    return a + (b - a) * u + (c - a) * v + (a - b - c + d) * u * v


# -------------------------------------------------------------- background
STOPS = [(0.0, (5, 2, 18)),
         (0.35, (12, 5, 32)),
         (0.65, (22, 9, 46)),
         (0.85, (30, 12, 52)),
         (1.0, (40, 14, 48))]


def bg_color(t):
    for i in range(len(STOPS) - 1):
        t0, c0 = STOPS[i]
        t1, c1 = STOPS[i + 1]
        if t <= t1:
            f = (t - t0) / (t1 - t0)
            return mix(c0, c1, f)
    return STOPS[-1][1]


def paint_background():
    for y in range(H):
        base = bg_color(y / (H - 1))
        row = y * W * 3
        ny1 = y / H * 24.0
        ny2 = y / H * 48.0
        for x in range(W):
            n1 = noise(GRID1, 24, x / W * 24.0, ny1)
            n2 = noise(GRID2, 48, x / W * 48.0, ny2)
            n = 0.65 * n1 + 0.35 * n2
            r, g, b = base
            glow = n - 0.57
            if glow > 0.0:
                if n1 > 0.72:
                    tc = (170, 40, 110)
                elif n2 > 0.5:
                    tc = (70, 40, 170)
                else:
                    tc = (15, 120, 140)
                k = glow * 1.1
                r += tc[0] * k
                g += tc[1] * k
                b += tc[2] * k
            # warm halo behind the phoenix, centred slightly above middle
            dx = (x - 384) / 520.0
            dy = (y - 360) / 520.0
            d2 = dx * dx + dy * dy
            if d2 < 1.0:
                k = (1.0 - d2) * (1.0 - d2) * 34.0
                r += 60.0 * k / 34.0 * 1.4
                g += 26.0 * k / 34.0 * 1.4
                b += 6.0 * k / 34.0
            # vignette: darken the corners
            vx = (x - 384) / 384.0
            vy = (y - 384) / 384.0
            vd = vx * vx + vy * vy
            if vd > 0.55:
                f = 1.0 - 0.30 * (vd - 0.55) / 1.45
                r *= f
                g *= f
                b *= f
            i = row + x * 3
            buf[i] = 255 if r > 255 else int(r)
            buf[i + 1] = 255 if g > 255 else int(g)
            buf[i + 2] = 255 if b > 255 else int(b)


# ------------------------------------------------------------------- stars
def disc(cx, cy, r, col, add=False, alpha=1.0):
    """Filled disc, flat colour or additive."""
    x0 = int(cx - r)
    x1 = int(cx + r)
    y0 = int(cy - r)
    y1 = int(cy + r)
    for y in range(y0, y1 + 1):
        dy = (y - cy) / r
        if dy < -1.0 or dy > 1.0:
            continue
        hw = r * math.sqrt(1.0 - dy * dy)
        for x in range(int(cx - hw), int(cx + hw) + 1):
            if add:
                add_px(x, y, col[0], col[1], col[2], alpha)
            else:
                set_px(x, y, int(col[0]), int(col[1]), int(col[2]))


def paint_stars():
    rng = random.Random(7)
    for _ in range(340):
        x = rng.randrange(W)
        y = rng.randrange(H)
        m = rng.random()
        br = 90.0 + 165.0 * m * m
        tint = (br, br, min(255.0, br * 1.15)) if m < 0.7 else (br, br * 0.85, br * 0.7)
        r = 1 if m < 0.8 else 2
        disc(x, y, r, tint, add=True, alpha=0.9)
    # a few bright stars with a cross sparkle
    for _ in range(26):
        x = rng.randrange(20, W - 20)
        y = rng.randrange(20, H - 20)
        ln = rng.randint(5, 11)
        for d in range(-ln, ln + 1):
            add_px(x + d, y, 220, 230, 255, 0.55 * (1.0 - abs(d) / ln))
            add_px(x, y + d, 220, 230, 255, 0.55 * (1.0 - abs(d) / ln))
        disc(x, y, 2, (255, 255, 255), add=True, alpha=0.9)


# ------------------------------------------------------------------ aurora
def paint_aurora():
    ribbons = [
        (150, 40, 0.0022, 0.7, 110, (20, 220, 190), 0.45),
        (230, 52, 0.0018, 2.1, 130, (120, 80, 255), 0.40),
        (620, 36, 0.0026, 4.0, 100, (40, 200, 160), 0.38),
    ]
    for (y0, amp, f1, ph, wdt, col, strength) in ribbons:
        for x in range(W):
            yc = (y0 + amp * math.sin(x * f1 * 6.283 + ph)
                  + amp * 0.5 * math.sin(x * f1 * 2.7 * 6.283 + ph * 2.0))
            y_start = max(0, int(yc - wdt))
            y_end = min(H - 1, int(yc + wdt))
            for y in range(y_start, y_end + 1):
                d = (y - yc) / wdt
                k = math.exp(-d * d * 2.2) * strength
                add_px(x, y, col[0], col[1], col[2], k)


# ------------------------------------------------------- polygons and glow
def fill_poly(pts, col, add=False, alpha=1.0):
    ys = [p[1] for p in pts]
    y0 = max(0, int(math.ceil(min(ys))))
    y1 = min(H - 1, int(math.floor(max(ys))))
    n = len(pts)
    for y in range(y0, y1 + 1):
        xs = []
        for i in range(n):
            x1, y1p = pts[i]
            x2, y2p = pts[(i + 1) % n]
            if (y1p <= y < y2p) or (y2p <= y < y1p):
                t = (y - y1p) / (y2p - y1p)
                xs.append(x1 + t * (x2 - x1))
        if len(xs) < 2:
            continue
        xs.sort()
        xa = max(0, int(math.ceil(xs[0])))
        xb = min(W - 1, int(math.floor(xs[-1])))
        for x in range(xa, xb + 1):
            if add:
                add_px(x, y, col[0], col[1], col[2], alpha)
            else:
                set_px(x, y, int(col[0]), int(col[1]), int(col[2]))


def radial_glow(cx, cy, rad, col, strength):
    x0 = max(0, int(cx - rad))
    x1 = min(W - 1, int(cx + rad))
    y0 = max(0, int(cy - rad))
    y1 = min(H - 1, int(cy + rad))
    for y in range(y0, y1 + 1):
        dy = (y - cy) / rad
        for x in range(x0, x1 + 1):
            dx = (x - cx) / rad
            d2 = dx * dx + dy * dy
            if d2 < 1.0:
                k = (1.0 - d2) * (1.0 - d2) * strength
                add_px(x, y, col[0], col[1], col[2], k)


def paint_rays(cx, cy, count, length, col):
    rng = random.Random(99)
    for i in range(count):
        ang = (i / count) * 2.0 * math.pi + rng.uniform(-0.06, 0.06)
        ln = length * rng.uniform(0.55, 1.0)
        tipx = cx + math.cos(ang) * ln
        tipy = cy + math.sin(ang) * ln
        px = -math.sin(ang) * 2.5
        py = math.cos(ang) * 2.5
        fill_poly([(cx + px, cy + py), (cx - px, cy - py), (tipx, tipy)],
                  col, add=True, alpha=0.16)


# ----------------------------------------------------------------- phoenix
FEATHER_BASE = (150, 20, 40)
FEATHER_MID = (255, 120, 20)
FEATHER_TIP = (255, 210, 80)


def feather(bx, by, tx, ty, bend, maxw, segments=8):
    """One long tapered feather, base (bx,by) to tip (tx,ty)."""
    dx = tx - bx
    dy = ty - by
    ln = math.hypot(dx, dy)
    ux, uy = dx / ln, dy / ln
    px, py = -uy, ux
    prev_l = (bx, by)
    prev_r = (bx, by)
    for s in range(1, segments + 1):
        t = s / segments
        cxp = bx + dx * t + px * bend * math.sin(math.pi * t)
        cyp = by + dy * t + py * bend * math.sin(math.pi * t)
        wdt = maxw * math.sin(math.pi * (t ** 0.75))
        cur_l = (cxp - px * wdt, cyp - py * wdt)
        cur_r = (cxp + px * wdt, cyp + py * wdt)
        col = grad3(FEATHER_BASE, FEATHER_MID, FEATHER_TIP, (s - 0.5) / segments)
        fill_poly([prev_l, prev_r, cur_r, cur_l], col)
        prev_l, prev_r = cur_l, cur_r


def paint_wings():
    for side in (-1, 1):
        sx = 384 + side * 30
        sy = 400
        for k in range(9):
            frac = k / 8.0
            ang = math.radians(-175.0 + frac * 80.0)
            ln = 300.0 + 90.0 * math.sin(math.pi * frac)
            # mirror: left wing tips point left, right wing tips point right
            tx = sx + side * abs(math.cos(ang)) * ln
            ty = sy + math.sin(ang) * ln
            bend = 26.0 if side < 0 else -26.0
            feather(sx, sy, tx, ty, bend, 18.0 + 11.0 * math.sin(math.pi * frac))


def paint_tail():
    palette = [(0, 220, 255), (150, 80, 255), (255, 60, 180),
               (255, 180, 60), (80, 255, 170)]
    for k in range(5):
        col = palette[k]
        x0 = 384 + (k - 2) * 14
        y0 = 520
        x1 = 384 + (k - 2) * 78
        y1 = 690 + abs(k - 2) * 12
        phase = k * 1.3
        segs = 12
        prev_l = (x0, y0)
        prev_r = (x0, y0)
        for s in range(1, segs + 1):
            t = s / segs
            cxp = x0 + (x1 - x0) * t + 26.0 * math.sin(t * 2.2 + phase)
            cyp = y0 + (y1 - y0) * t
            wdt = 15.0 * math.sin(math.pi * (t ** 0.8)) + 1.5
            # plume runs mostly downward: perpendicular is horizontal
            cur_l = (cxp - wdt, cyp)
            cur_r = (cxp + wdt, cyp)
            c = grad3(col, mix(col, (255, 180, 60), 0.5), (255, 160, 40),
                      (s - 0.5) / segs)
            fill_poly([prev_l, prev_r, cur_r, cur_l], c)
            prev_l, prev_r = cur_l, cur_r


def paint_body():
    y0, y1 = 300, 545
    for y in range(y0, y1 + 1):
        t = (y - y0) / (y1 - y0)
        wdt = 58.0 * (math.sin(math.pi * (0.12 + 0.88 * t)) ** 0.8)
        col = grad3((255, 230, 150), (255, 140, 30), (190, 30, 20), t)
        xa = int(384 - wdt)
        xb = int(384 + wdt)
        for x in range(max(0, xa), min(W - 1, xb) + 1):
            # bright core column down the middle of the flame body
            core = max(0.0, 1.0 - abs(x - 384) / max(1.0, wdt))
            set_px(x, y,
                   min(255, int(col[0] + 60.0 * core)),
                   min(255, int(col[1] + 45.0 * core)),
                   min(255, int(col[2] + 20.0 * core)))


def paint_head():
    # head: golden disc, per-row gradient
    cx, cy, r = 384, 260, 42
    for y in range(int(cy - r), int(cy + r) + 1):
        dy = (y - cy) / r
        if dy < -1.0 or dy > 1.0:
            continue
        hw = r * math.sqrt(1.0 - dy * dy)
        col = mix((255, 205, 95), (235, 95, 25), (y - (cy - r)) / (2.0 * r))
        for x in range(int(cx - hw), int(cx + hw) + 1):
            set_px(x, y, int(col[0]), int(col[1]), int(col[2]))
    # crest: three thin flame plumes sweeping up and back
    crest = [((398, 232), (428, 178), (412, 236)),
             ((404, 228), (448, 196), (420, 240)),
             ((392, 234), (404, 168), (386, 238))]
    for (a, tip, b) in crest:
        fill_poly([a, tip, b], (255, 170, 40))
    # beak, pointing left
    fill_poly([(352, 256), (352, 272), (326, 264)], (255, 180, 60))
    # eye: white with a dark pupil and a gold ring
    disc(364, 250, 8, (255, 215, 130), add=False)
    disc(364, 250, 5, (255, 255, 255), add=False)
    disc(363, 250, 3, (20, 8, 8), add=False)


# ------------------------------------------------------------ embers + text
def paint_embers():
    rng = random.Random(1234)
    warm = [(255, 160, 60), (255, 200, 90), (255, 110, 40)]
    cool = [(120, 220, 255), (180, 140, 255)]
    for _ in range(130):
        x = rng.randrange(80, 688)
        y = rng.randrange(120, 700)
        col = rng.choice(warm) if rng.random() < 0.8 else rng.choice(cool)
        disc(x, y, rng.choice([1, 1, 2]), col, add=True, alpha=0.85)


FONT = {
    "R": ["01110", "10001", "10001", "11110", "10100", "10010", "10001"],
    "I": ["01110", "00100", "00100", "00100", "00100", "00100", "01110"],
    "S": ["01111", "10000", "10000", "01110", "00001", "00001", "11110"],
    "E": ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
    "!": ["00100", "00100", "00100", "00100", "00100", "00000", "00100"],
}


def paint_text():
    word = "RISE!"
    scale = 6
    adv = 7 * scale
    total = len(word) * 5 * scale + (len(word) - 1) * 2 * scale
    x0 = 384 - total // 2
    y0 = 34
    # soft glow pass, slightly larger and dimmer
    for gi, ch in enumerate(word):
        gx = x0 + gi * adv
        for row in range(7):
            for c in range(5):
                if FONT[ch][row][c] == "1":
                    for dy in range(scale + 2):
                        for dx in range(scale + 2):
                            add_px(gx + c * scale + dx - 1, y0 + row * scale + dy - 1,
                                   255, 170, 60, 0.10)
    # crisp letters
    for gi, ch in enumerate(word):
        gx = x0 + gi * adv
        for row in range(7):
            for c in range(5):
                if FONT[ch][row][c] == "1":
                    for dy in range(scale):
                        for dx in range(scale):
                            add_px(gx + c * scale + dx, y0 + row * scale + dy,
                                   255, 215, 120, 1.0)


# ------------------------------------------------------------- PNG encoding
def encode_png():
    raw = bytearray()
    stride = W * 3
    for y in range(H):
        raw.append(0)
        raw += buf[y * stride:(y + 1) * stride]
    comp = zlib.compress(bytes(raw), 6)

    def chunk(tag, data):
        out = struct.pack(">I", len(data)) + tag + data
        out += struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        return out

    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", comp) + chunk(b"IEND", b""))


def main():
    paint_background()
    paint_stars()
    paint_aurora()
    paint_rays(384, 400, 22, 430, (255, 190, 90))
    paint_tail()
    paint_wings()
    paint_body()
    paint_head()
    radial_glow(384, 400, 200, (255, 170, 60), 0.35)
    radial_glow(384, 400, 80, (255, 230, 160), 0.5)
    paint_embers()
    paint_text()
    data = encode_png()
    outdir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, "entry.png"), "wb") as f:
        f.write(data)


if __name__ == "__main__":
    main()
