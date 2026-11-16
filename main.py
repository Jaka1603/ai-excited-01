#!/usr/bin/env python3
"""JOY OVERLOAD - procedural 1024x1024 PNG for ai-excited-01.

Pure standard library, no network, fully deterministic.
Renders at 2048x2048 (2x supersampling) then box-downscales to 1024x1024.
Every pixel is drawn by the rasterizer below; PNG encoding is hand-written
(zlib + struct).
"""
import os
import struct
import zlib
import math

SS = 2048          # supersampled canvas size
OUT = 1024         # final size
N = SS

# ---------------------------------------------------------------- LCG
class LCG:
    """Deterministic linear congruential generator (Numerical Recipes)."""
    def __init__(self, seed):
        self.state = seed & 0xFFFFFFFF

    def next(self):
        self.state = (1664525 * self.state + 1013904223) & 0xFFFFFFFF
        return self.state

    def rand(self):
        return self.next() / 4294967296.0

    def range(self, lo, hi):
        return lo + (hi - lo) * self.rand()

    def randint(self, lo, hi):
        return lo + int(self.rand() * (hi - lo + 1))


# ---------------------------------------------------------------- canvas
# RGB bytearray, row-major
pix = bytearray(N * N * 3)


def _idx(x, y):
    return (y * N + x) * 3


def set_px(x, y, r, g, b):
    if 0 <= x < N and 0 <= y < N:
        i = (y * N + x) * 3
        pix[i] = r
        pix[i + 1] = g
        pix[i + 2] = b


def blend_px(x, y, r, g, b, a):
    """Alpha blend colour over canvas, a in 0..255."""
    if 0 <= x < N and 0 <= y < N and a > 0:
        i = (y * N + x) * 3
        inv = 255 - a
        pix[i] = (r * a + pix[i] * inv) // 255
        pix[i + 1] = (g * a + pix[i + 1] * inv) // 255
        pix[i + 2] = (b * a + pix[i + 2] * inv) // 255


def fill_rect(x0, y0, x1, y1, col):
    r, g, b = col
    x0 = max(0, int(x0)); y0 = max(0, int(y0))
    x1 = min(N - 1, int(x1)); y1 = min(N - 1, int(y1))
    if x1 < x0 or y1 < y0:
        return
    row = bytes((r, g, b)) * (x1 - x0 + 1)
    w = (x1 - x0 + 1) * 3
    for y in range(y0, y1 + 1):
        i = (y * N + x0) * 3
        pix[i:i + w] = row


def hspan(y, x0, x1, col):
    if y < 0 or y >= N:
        return
    x0 = max(0, int(x0)); x1 = min(N - 1, int(x1))
    if x1 < x0:
        return
    r, g, b = col
    i = (y * N + x0) * 3
    pix[i:i + (x1 - x0 + 1) * 3] = bytes((r, g, b)) * (x1 - x0 + 1)


def fill_circle(cx, cy, rad, col):
    cx = int(cx); cy = int(cy); rad = int(rad)
    r2 = rad * rad
    for dy in range(-rad, rad + 1):
        w = int(math.sqrt(max(0, r2 - dy * dy)))
        hspan(cy + dy, cx - w, cx + w, col)


def fill_ellipse(cx, cy, rx, ry, col):
    cx = int(cx); cy = int(cy); rx = int(rx); ry = int(ry)
    if rx <= 0 or ry <= 0:
        return
    for dy in range(-ry, ry + 1):
        t = dy / ry
        w = int(rx * math.sqrt(max(0.0, 1.0 - t * t)))
        hspan(cy + dy, cx - w, cx + w, col)


def ring(cx, cy, rad, thick, col):
    """Draw a ring by scanline: outer span minus inner span."""
    cx = int(cx); cy = int(cy); rad = int(rad); thick = int(thick)
    inner = rad - thick
    r2 = rad * rad
    i2 = inner * inner
    for dy in range(-rad, rad + 1):
        w = int(math.sqrt(max(0, r2 - dy * dy)))
        if abs(dy) < inner:
            wi = int(math.sqrt(max(0, i2 - dy * dy)))
            hspan(cy + dy, cx - w, cx - wi, col)
            hspan(cy + dy, cx + wi, cx + w, col)
        else:
            hspan(cy + dy, cx - w, cx + w, col)


def fill_polygon(pts, col):
    """Scanline polygon fill."""
    ys = [p[1] for p in pts]
    y0 = max(0, int(math.floor(min(ys))))
    y1 = min(N - 1, int(math.ceil(max(ys))))
    n = len(pts)
    for y in range(y0, y1 + 1):
        yc = y + 0.5
        nodes = []
        for i in range(n):
            x1, yy1 = pts[i]
            x2, yy2 = pts[(i + 1) % n]
            if (yy1 <= yc < yy2) or (yy2 <= yc < yy1):
                if yy2 != yy1:
                    nodes.append(x1 + (yc - yy1) * (x2 - x1) / (yy2 - yy1))
        nodes.sort()
        for k in range(0, len(nodes) - 1, 2):
            hspan(y, nodes[k], nodes[k + 1], col)


def thick_line(x0, y0, x1, y1, thick, col):
    dist = math.hypot(x1 - x0, y1 - y0)
    steps = max(1, int(dist / max(2, thick // 3)))
    rad = thick // 2
    for s in range(steps + 1):
        t = s / steps
        fill_circle(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, rad, col)


def thick_polyline(pts, thick, col):
    for i in range(len(pts) - 1):
        thick_line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1],
                   thick, col)


def star_pts(cx, cy, r_out, r_in, rot=-math.pi / 2, points=5):
    pts = []
    for i in range(points * 2):
        ang = rot + i * math.pi / points
        rad = r_out if i % 2 == 0 else r_in
        pts.append((cx + rad * math.cos(ang), cy + rad * math.sin(ang)))
    return pts


def fill_star(cx, cy, r_out, col, rot=-math.pi / 2, points=5):
    fill_polygon(star_pts(cx, cy, r_out, r_out * 0.48, rot, points), col)


def diamond(cx, cy, s, col):
    fill_polygon([(cx, cy - s), (cx + s, cy), (cx, cy + s), (cx - s, cy)], col)


def rounded_rect(x0, y0, x1, y1, rad, col):
    fill_rect(x0 + rad, y0, x1 - rad, y1, col)
    fill_rect(x0, y0 + rad, x1, y1 - rad, col)
    fill_circle(x0 + rad, y0 + rad, rad, col)
    fill_circle(x1 - rad, y0 + rad, rad, col)
    fill_circle(x0 + rad, y1 - rad, rad, col)
    fill_circle(x1 - rad, y1 - rad, rad, col)


# ---------------------------------------------------------------- palette
BG_TOP = (38, 16, 84)
BG_BOT = (88, 28, 135)
MINT = (94, 240, 210)
MINT_LIGHT = (196, 255, 238)
MINT_DARK = (20, 140, 130)
TEAL_OUTLINE = (10, 74, 84)
CYAN = (64, 224, 255)
ORANGE = (255, 138, 42)
ORANGE_DARK = (214, 84, 20)
GOLD = (255, 205, 40)
YELLOW = (255, 232, 66)
MAGENTA = (240, 46, 170)
PINK = (255, 110, 180)
LIME = (150, 235, 60)
WHITE = (255, 255, 255)
DARK = (24, 22, 54)
CONFETTI = [MAGENTA, YELLOW, CYAN, LIME, ORANGE, (255, 90, 90),
             (160, 110, 255), WHITE]
RAINBOW = [(255, 62, 92), (255, 138, 42), (255, 220, 50),
           (90, 220, 90), (50, 190, 255), (150, 110, 255)]

# 5x7 bitmap font (rows top->bottom, 5 bits each) for J O Y ! and extras
FONT = {
    'J': [0x07, 0x02, 0x02, 0x02, 0x02, 0x12, 0x0C],
    'O': [0x0E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E],
    'Y': [0x11, 0x11, 0x0A, 0x04, 0x04, 0x04, 0x04],
    '!': [0x04, 0x04, 0x04, 0x04, 0x04, 0x00, 0x04],
}


def draw_text(cx, cy, text, cell, col):
    """Draw block text centred at (cx, cy); cell = pixel block size."""
    total_w = len(text) * 6 * cell - cell
    x_start = cx - total_w // 2
    y_start = cy - (7 * cell) // 2
    for ci, ch in enumerate(text):
        glyph = FONT.get(ch, [0] * 7)
        gx = x_start + ci * 6 * cell
        for row in range(7):
            bits = glyph[row]
            for c in range(5):
                if bits & (1 << (4 - c)):
                    fill_rect(gx + c * cell, y_start + row * cell,
                              gx + c * cell + cell - 1,
                              y_start + row * cell + cell - 1, col)


# ---------------------------------------------------------------- scene
CX = 1024          # explosion / head centre x
HEAD_CY = 900
BOX_CY = 1740      # gift box centre y


def draw_background(rng):
    # vertical gradient deep purple space
    for y in range(N):
        t = y / (N - 1)
        r = int(BG_TOP[0] + (BG_BOT[0] - BG_TOP[0]) * t)
        g = int(BG_TOP[1] + (BG_BOT[1] - BG_TOP[1]) * t)
        b = int(BG_TOP[2] + (BG_BOT[2] - BG_TOP[2]) * t)
        i = y * N * 3
        pix[i:i + N * 3] = bytes((r, g, b)) * N
    # distant nebula blobs (soft, low alpha)
    for _ in range(14):
        x = rng.range(0, N); y = rng.range(0, N)
        rad = rng.range(120, 340)
        col = CONFETTI[rng.randint(0, len(CONFETTI) - 1)]
        for dy in range(-int(rad), int(rad) + 1, 6):
            w = int(math.sqrt(max(0, rad * rad - dy * dy)))
            for x in range(int(x - w), int(x + w), 6):
                blend_px(x, int(y + dy), col[0], col[1], col[2], 10)
    # tiny stars
    for _ in range(520):
        x = int(rng.range(8, N - 8)); y = int(rng.range(8, N - 8))
        s = rng.randint(2, 6)
        bright = rng.randint(150, 255)
        col = (bright, bright, min(255, bright + 20))
        if rng.rand() < 0.22:
            # sparkle cross
            fill_rect(x - s * 2, y - 2, x + s * 2, y + 2, col)
            fill_rect(x - 2, y - s * 2, x + 2, y + s * 2, col)
        else:
            fill_circle(x, y, s, col)


def draw_glow():
    # warm radial glow behind head: concentric alpha circles, big -> small
    for rad, alpha in ((980, 26), (860, 34), (740, 44), (620, 54)):
        for dy in range(-rad, rad + 1, 4):
            w = int(math.sqrt(max(0, rad * rad - dy * dy)))
            y = HEAD_CY + dy
            if 0 <= y < N:
                for x in range(CX - w, CX + w, 4):
                    blend_px(x, y, 255, 196, 90, alpha)


def draw_rainbow():
    # concentric rainbow arcs centred low, head will cover the middle
    cy = 1560
    radii = [1010, 920, 830, 740, 650, 560]
    for rad, col in zip(radii, RAINBOW):
        # draw arc as thick ring segment: full ring then we rely on
        # background-coloured lower cover below horizon line
        ring(CX, cy, rad, 88, col)
    # hide ring parts below the horizon / behind the gift area
    fill_rect(0, cy + 330, N - 1, N - 1, (0, 0, 0))  # placeholder overwritten
    # repaint bottom background strip with gradient rows
    for y in range(cy + 330, N):
        t = y / (N - 1)
        r = int(BG_TOP[0] + (BG_BOT[0] - BG_TOP[0]) * t)
        g = int(BG_TOP[1] + (BG_BOT[1] - BG_TOP[1]) * t)
        b = int(BG_TOP[2] + (BG_BOT[2] - BG_TOP[2]) * t)
        i = y * N * 3
        pix[i:i + N * 3] = bytes((r, g, b)) * N


def draw_burst_rays(rng):
    # speed / burst rays radiating from explosion centre
    ex, ey = CX, 1560
    for i in range(28):
        ang = (i / 28.0) * math.pi * 2 + rng.range(-0.05, 0.05)
        if math.sin(ang) > 0.35:      # keep rays mostly upward/outward
            continue
        ln = rng.range(430, 720)
        x1 = ex + ln * math.cos(ang); y1 = ey + ln * math.sin(ang)
        col = CONFETTI[i % len(CONFETTI)]
        thick_polyline([(ex, ey), (x1, y1)], 8, col)


def draw_confetti(rng):
    ex, ey = CX, 1500
    # rotated rectangles flying on radial arcs
    for _ in range(300):
        ang = rng.range(-math.pi, math.pi)
        if math.sin(ang) > 0.45 and rng.rand() < 0.7:
            ang = -abs(ang)  # bias upward
        dist = rng.range(260, 1020)
        x = ex + dist * math.cos(ang)
        y = ey + dist * math.sin(ang) - rng.range(0, 160)
        if not (20 < x < N - 20 and 20 < y < N - 20):
            continue
        w = rng.range(26, 58); h = rng.range(12, 26)
        rot = rng.range(0, math.pi)
        ca, sa = math.cos(rot), math.sin(rot)
        pts = []
        for dx, dy in ((-w / 2, -h / 2), (w / 2, -h / 2),
                       (w / 2, h / 2), (-w / 2, h / 2)):
            pts.append((x + dx * ca - dy * sa, y + dx * sa + dy * ca))
        fill_polygon(pts, CONFETTI[rng.randint(0, len(CONFETTI) - 1)])
    # gold stars
    for _ in range(70):
        ang = rng.range(-math.pi, math.pi)
        dist = rng.range(300, 1000)
        x = ex + dist * math.cos(ang)
        y = ey + dist * math.sin(ang) - rng.range(0, 140)
        if 30 < x < N - 30 and 30 < y < N - 30:
            fill_star(x, y, rng.range(18, 44), GOLD,
                      rot=rng.range(0, math.pi))
            fill_star(x, y, rng.range(8, 18), YELLOW,
                      rot=rng.range(0, math.pi))
    # spiral ribbons: bright curling polylines
    for _ in range(16):
        ang0 = rng.range(-math.pi, 0)
        dist = rng.range(420, 820)
        bx = ex + dist * math.cos(ang0)
        by = ey + dist * math.sin(ang0)
        col = CONFETTI[rng.randint(0, len(CONFETTI) - 1)]
        pts = []
        for s in range(26):
            t = s / 25.0
            a = t * 5.2 + rng.range(0, 0.02)
            rr = 66 * (1 - t) + 6
            pts.append((bx + rr * math.cos(a), by + rr * math.sin(a)))
        thick_polyline(pts, 13, col)
    # dots
    for _ in range(180):
        x = rng.range(20, N - 20); y = rng.range(20, N - 20)
        fill_circle(int(x), int(y), rng.randint(5, 13),
                    CONFETTI[rng.randint(0, len(CONFETTI) - 1)])


def draw_gift_box():
    # tossed lids, tilted to both sides behind the box
    lid_l = [(300, 1560), (700, 1430), (760, 1530), (360, 1670)]
    fill_polygon(lid_l, MAGENTA)
    fill_polygon([(300, 1560), (700, 1430), (720, 1480), (330, 1610)],
                 PINK)
    lid_r = [(1348, 1430), (1748, 1560), (1688, 1670), (1288, 1530)]
    fill_polygon(lid_r, MAGENTA)
    fill_polygon([(1348, 1430), (1748, 1560), (1718, 1610), (1328, 1480)],
                 PINK)
    # gold ribbon stripes across each lid so they read as gift lids
    fill_polygon([(470, 1492), (530, 1478), (590, 1596), (530, 1612)],
                 GOLD)
    fill_polygon([(1518, 1478), (1578, 1492), (1518, 1612), (1458, 1596)],
                 GOLD)
    for pts in (lid_l, lid_r):
        cx = sum(p[0] for p in pts) / 4; cy = sum(p[1] for p in pts) / 4
        fill_circle(int(cx), int(cy), 26, GOLD)
    # box body
    rounded_rect(724, 1620, 1324, 1980, 36, MAGENTA)
    rounded_rect(724, 1620, 1324, 1700, 36, PINK)       # top rim light
    fill_rect(964, 1620, 1084, 1980, GOLD)              # vertical ribbon
    fill_rect(724, 1740, 1324, 1820, GOLD)              # horizontal ribbon
    fill_circle(CX, 1780, 62, YELLOW)                   # ribbon knot
    fill_circle(CX, 1780, 40, GOLD)
    # sparkles on box
    fill_star(830, 1900, 34, WHITE)
    fill_star(1220, 1680, 28, WHITE)


def draw_arms():
    # little arms raised in celebration, behind head sides
    # left arm
    thick_polyline([(430, 1080), (300, 900), (240, 700)], 92, MINT_DARK)
    thick_polyline([(430, 1080), (300, 900), (240, 700)], 64, MINT)
    fill_circle(240, 680, 74, ORANGE)
    for dx in (-52, 0, 52):  # fingers
        fill_circle(240 + dx, 600, 26, ORANGE)
    # right arm
    thick_polyline([(1618, 1080), (1748, 900), (1808, 700)], 92, MINT_DARK)
    thick_polyline([(1618, 1080), (1748, 900), (1808, 700)], 64, MINT)
    fill_circle(1808, 680, 74, ORANGE)
    for dx in (-52, 0, 52):
        fill_circle(1808 + dx, 600, 26, ORANGE)


def draw_head():
    cx, cy = CX, HEAD_CY
    # ears / side pods
    fill_circle(cx - 640, cy + 40, 130, TEAL_OUTLINE)
    fill_circle(cx + 640, cy + 40, 130, TEAL_OUTLINE)
    fill_circle(cx - 640, cy + 40, 104, ORANGE)
    fill_circle(cx + 640, cy + 40, 104, ORANGE)
    fill_circle(cx - 640, cy + 40, 52, GOLD)
    fill_circle(cx + 640, cy + 40, 52, GOLD)
    # antenna (behind top of head)
    thick_line(cx, cy - 560, cx, cy - 700, 34, TEAL_OUTLINE)
    thick_line(cx, cy - 560, cx, cy - 690, 20, MINT)
    fill_star(cx, cy - 782, 84, GOLD)
    fill_star(cx, cy - 782, 58, YELLOW)
    # head outline + body: big rounded shape
    fill_ellipse(cx, cy, 660, 600, TEAL_OUTLINE)
    fill_ellipse(cx, cy, 624, 564, MINT)
    # forehead shine band
    fill_ellipse(cx - 250, cy - 356, 225, 74, MINT_LIGHT)
    # face plate
    fill_ellipse(cx, cy + 60, 520, 440, (235, 255, 250))
    # rosy cheeks
    fill_ellipse(cx - 400, cy + 190, 104, 62, PINK)
    fill_ellipse(cx + 400, cy + 190, 104, 62, PINK)
    fill_ellipse(cx - 400, cy + 190, 64, 38, (255, 150, 200))
    fill_ellipse(cx + 400, cy + 190, 64, 38, (255, 150, 200))
    # ---- eyes: huge and sparkling
    for ex in (cx - 250, cx + 250):
        fill_ellipse(ex, cy - 60, 150, 190, TEAL_OUTLINE)
        fill_ellipse(ex, cy - 60, 132, 172, WHITE)
        fill_ellipse(ex, cy - 30, 92, 122, (28, 30, 90))
        fill_ellipse(ex, cy - 10, 62, 88, (12, 14, 44))
        # star highlight + dots
        fill_star(ex - 28, cy - 84, 52, WHITE)
        fill_circle(ex + 44, cy + 44, 26, WHITE)
        fill_circle(ex - 52, cy + 70, 15, CYAN)
    # happy closed brow arcs (thick short curves as lines)
    thick_polyline([(cx - 380, cy - 316), (cx - 250, cy - 352),
                    (cx - 120, cy - 316)], 18, TEAL_OUTLINE)
    thick_polyline([(cx + 120, cy - 316), (cx + 250, cy - 352),
                    (cx + 380, cy - 316)], 18, TEAL_OUTLINE)
    # nose: tiny orange triangle/dot
    diamond(cx, cy + 96, 30, ORANGE)
    # ---- mouth: wide open joyful smile (wider than tall)
    fill_ellipse(cx, cy + 268, 272, 142, TEAL_OUTLINE)
    fill_ellipse(cx, cy + 276, 240, 118, (120, 26, 48))
    fill_ellipse(cx, cy + 330, 150, 56, (255, 110, 150))   # tongue
    # teeth: rounded band with two divider grooves
    fill_rect(cx - 118, cy + 150, cx + 118, cy + 194, WHITE)
    fill_circle(cx - 118, cy + 172, 22, WHITE)
    fill_circle(cx + 118, cy + 172, 22, WHITE)
    fill_rect(cx - 44, cy + 152, cx - 38, cy + 192, (120, 26, 48))
    fill_rect(cx + 38, cy + 152, cx + 44, cy + 192, (120, 26, 48))


def draw_badge():
    # starburst badge, top-left corner
    bx, by = 300, 300
    pts = star_pts(bx, by, 238, 178, rot=-math.pi / 2, points=12)
    fill_polygon(pts, ORANGE_DARK)
    pts = star_pts(bx, by, 218, 160, rot=-math.pi / 2, points=12)
    fill_polygon(pts, GOLD)
    fill_circle(bx, by, 156, YELLOW)
    draw_text(bx, by, "JOY!", 12, (196, 44, 8))


def draw_foreground_confetti(rng):
    # a few big pieces in front for depth
    for _ in range(46):
        x = rng.range(40, N - 40); y = rng.range(40, N - 40)
        if abs(x - CX) < 560 and abs(y - HEAD_CY) < 520:
            continue
        if rng.rand() < 0.5:
            fill_star(x, y, rng.range(22, 40), GOLD)
        else:
            fill_circle(int(x), int(y), rng.randint(8, 15),
                        CONFETTI[rng.randint(0, len(CONFETTI) - 1)])


# ---------------------------------------------------------------- output
def downscale():
    """Average each 2x2 block of the SS canvas into the 1024 output."""
    out = bytearray(OUT * OUT * 3)
    stride = N * 3
    for y in range(OUT):
        row0 = (2 * y) * stride
        row1 = (2 * y + 1) * stride
        orow = y * OUT * 3
        for x in range(OUT):
            i0 = row0 + 6 * x
            i1 = row1 + 6 * x
            o = orow + 3 * x
            out[o] = (pix[i0] + pix[i0 + 3] + pix[i1] + pix[i1 + 3]) // 4
            out[o + 1] = (pix[i0 + 1] + pix[i0 + 3 + 1] +
                          pix[i1 + 1] + pix[i1 + 3 + 1]) // 4
            out[o + 2] = (pix[i0 + 2] + pix[i0 + 3 + 2] +
                          pix[i1 + 2] + pix[i1 + 3 + 2]) // 4
    return out


def encode_png(rgb, w, h):
    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        c += struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        return c

    raw = bytearray()
    stride = w * 3
    for y in range(h):
        raw.append(0)
        raw += rgb[y * stride:(y + 1) * stride]
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(bytes(raw), 6))
            + chunk(b"IEND", b""))


def main():
    rng = LCG(20261116)
    draw_background(rng)
    draw_glow()
    draw_rainbow()
    draw_burst_rays(rng)
    draw_confetti(rng)
    draw_arms()
    draw_head()
    draw_gift_box()
    draw_badge()
    draw_foreground_confetti(rng)
    rgb = downscale()
    data = encode_png(rgb, OUT, OUT)
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "entry.png")
    with open(path, "wb") as f:
        f.write(data)
    print(f"wrote {path} ({len(data)} bytes)")


if __name__ == "__main__":
    main()
