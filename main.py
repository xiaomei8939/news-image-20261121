#!/usr/bin/env python3
"""THE WORLD TODAY - front page for Saturday 21 November 2026.

A pure-standard-library renderer. It draws a newspaper front page
(masthead, date banner, one hero story, five more stories, an "also
today" box and per-story source tags) into an RGB buffer and writes
a deterministic PNG to $MAKEFUN_OUTPUT_DIR/entry.png (or
./output/entry.png when the variable is unset).

No network, no randomness, no clock: the same input always produces
the same bytes. Every word in the image is program-rendered from a
hand-drawn 5x7 pixel font defined below (each glyph written out in
this session); bold text is drawn with a one-unit horizontal
thicken. Illustrations are flat pictograms drawn from primitives.

Stories: Iran's strike on US bases in Bahrain, Mexico's capture of
cartel boss "El Chapo Isidro", the Russian missile strike on
Zelenskyy's hometown Kryvyi Rih, COP31 running into overtime in
Antalya, Wall Street sliding into correction on the AI sell-off,
and the Wolbachia mosquito trial that cut dengue infections 69% in
Brazil - all reported 21 November 2026.
"""

import binascii
import os
import struct
import zlib

W, H = 1024, 1024

PAPER = (250, 248, 242)
INK = (22, 22, 22)
RED = (178, 34, 34)
DARKRED = (140, 20, 20)
BLUE = (30, 64, 120)
NAVY = (16, 32, 64)
GREY = (110, 106, 96)
LIGHT = (233, 229, 219)
SKY = (216, 230, 240)
GOLD = (198, 148, 52)
GREEN = (46, 110, 62)
ORANGE = (226, 112, 28)
TEAL = (52, 110, 150)
BODY = (52, 50, 46)
CAPTION = (82, 80, 74)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
YELLOW = (240, 200, 60)

# ---------------------------------------------------------------------------
# Hand-drawn 5x7 pixel font.
#
# Each glyph is a 7-character string, one character per row, top to
# bottom. The character is an index into ALPHA (0-9 then A-V), giving
# a 5-bit row value: bit 4 is the leftmost pixel, bit 0 the rightmost.
# So "EHHVHHH" for A means rows 01110, 10001, 10001, 11111, 10001,
# 10001, 10001. Advance is 6 units (5 pixels + 1 of spacing).
# ---------------------------------------------------------------------------
ALPHA = "0123456789ABCDEFGHIJKLMNOPQRSTUV"


def _g(rows):
    return tuple(ALPHA.index(c) for c in rows)


FONT = {
    "A": _g("EHHVHHH"), "B": _g("UHHUHHU"), "C": _g("EHGGGHE"),
    "D": _g("UHHHHHU"), "E": _g("VGGUGGV"), "F": _g("VGGUGGG"),
    "G": _g("EHGNHHF"), "H": _g("HHHVHHH"), "I": _g("E44444E"),
    "J": _g("72222IC"), "K": _g("HIKOKIH"), "L": _g("GGGGGGV"),
    "M": _g("HRLLHHH"), "N": _g("HPLJHHH"), "O": _g("EHHHHHE"),
    "P": _g("UHHUGGG"), "Q": _g("EHHHLID"), "R": _g("UHHUKIH"),
    "S": _g("FGGE11U"), "T": _g("V444444"), "U": _g("HHHHHHE"),
    "V": _g("HHHHHA4"), "W": _g("HHHLLRH"), "X": _g("HHA4AHH"),
    "Y": _g("HHA4444"), "Z": _g("V1248GV"),
    "a": _g("00E1FHF"), "b": _g("GGMPHHU"), "c": _g("00EHGHE"),
    "d": _g("11DJHHF"), "e": _g("00EHVGE"), "f": _g("688U888"),
    "g": _g("0FHHF1E"), "h": _g("GGMPHHH"), "i": _g("40C444E"),
    "j": _g("20622IC"), "k": _g("GGIKOKI"), "l": _g("C44444E"),
    "m": _g("00QLLLL"), "n": _g("00MPHHH"), "o": _g("00EHHHE"),
    "p": _g("00UHUGG"), "q": _g("00DJF11"), "r": _g("00MPGGG"),
    "s": _g("00FGE1U"), "t": _g("88U8886"), "u": _g("00HHHJD"),
    "v": _g("00HHHA4"), "w": _g("00HHLLA"), "x": _g("00HA4AH"),
    "y": _g("00HHF1E"), "z": _g("00V248V"),
    "0": _g("EHJLPHE"), "1": _g("4C4444E"), "2": _g("EH168GV"),
    "3": _g("V2421HE"), "4": _g("26AIV22"), "5": _g("VGU11HE"),
    "6": _g("68GUHHE"), "7": _g("V124888"), "8": _g("EHHEHHE"),
    "9": _g("EHHF12C"),
    " ": _g("0000000"), ".": _g("00000CC"), ",": _g("0000C48"),
    ":": _g("0CC0CC0"), ";": _g("0CC0C48"), "'": _g("4480000"),
    '"': _g("AAA0000"), "!": _g("4444404"), "?": _g("EH12404"),
    "-": _g("000E000"), "(": _g("2488842"), ")": _g("8422248"),
    "/": _g("11248GG"), "%": _g("PP248JJ"), "&": _g("CIK8LID"),
    "+": _g("044V440"), "=": _g("00V0V00"), "*": _g("04LEL40"),
    "[": _g("E88888E"), "]": _g("E22222E"), "$": _g("4FKE5U4"),
    "#": _g("AAVAVAA"), "@": _g("EHNLMGE"), "_": _g("000000V"),
    "|": _g("4444444"), "<": _g("248G842"), ">": _g("8421248"),
}

ADV = 6  # glyph advance in font units (5 pixels + 1 spacing)


# ---------------------------------------------------------------------------
# Canvas: an RGB buffer with flat drawing primitives.
# ---------------------------------------------------------------------------
class Canvas:
    def __init__(self, w, h, bg):
        self.w = w
        self.h = h
        self.px = bytearray(bg) * (w * h)

    def set(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.px[i], self.px[i + 1], self.px[i + 2] = c

    def rect(self, x, y, w, h, c):
        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(self.w, x + w)
        y1 = min(self.h, y + h)
        for yy in range(y0, y1):
            i = (yy * self.w + x0) * 3
            for xx in range(x0, x1):
                self.px[i], self.px[i + 1], self.px[i + 2] = c
                i += 3

    def hline(self, x, y, w, c, t=1):
        self.rect(x, y, w, t, c)

    def vline(self, x, y, h, c, t=1):
        self.rect(x, y, t, h, c)

    def line(self, x0, y0, x1, y1, c, t=1):
        """Bresenham line, t pixels thick (square brush)."""
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        while True:
            self.rect(x0 - t // 2, y0 - t // 2, t, t, c)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def circle(self, cx, cy, r, c):
        """Filled circle by scanlines."""
        for yy in range(cy - r, cy + r + 1):
            d = r * r - (yy - cy) * (yy - cy)
            if d < 0:
                continue
            half = int(d ** 0.5)
            self.rect(cx - half, yy, 2 * half + 1, 1, c)

    def ellipse(self, cx, cy, rx, ry, c):
        for yy in range(cy - ry, cy + ry + 1):
            d = 1.0 - ((yy - cy) / ry) ** 2
            if d < 0:
                continue
            half = int(rx * d ** 0.5)
            self.rect(cx - half, yy, 2 * half + 1, 1, c)

    def poly(self, pts, c):
        """Filled polygon by scanline fill (convex or concave)."""
        if len(pts) < 3:
            return
        ys = [p[1] for p in pts]
        for yy in range(min(ys), max(ys) + 1):
            xs = []
            n = len(pts)
            for i in range(n):
                x0, y0 = pts[i]
                x1, y1 = pts[(i + 1) % n]
                if y0 == y1:
                    continue
                if (y0 <= yy < y1) or (y1 <= yy < y0):
                    t = (yy - y0) / (y1 - y0)
                    xs.append(x0 + t * (x1 - x0))
            xs.sort()
            for k in range(0, len(xs) - 1, 2):
                self.rect(int(xs[k]), yy, max(1, int(xs[k + 1]) - int(xs[k])), 1, c)

    def starburst(self, cx, cy, r0, r1, points, c):
        """Explosion star: alternating outer/inner radius polygon."""
        import math
        pts = []
        for i in range(points * 2):
            ang = 3.141592653589793 * i / points
            r = r1 if i % 2 == 0 else r0
            pts.append((int(cx + r * math.cos(ang - 1.5708)),
                        int(cy + r * math.sin(ang - 1.5708))))
        self.poly(pts, c)


# ---------------------------------------------------------------------------
# PNG writer: deterministic, no ancillary chunks.
# ---------------------------------------------------------------------------
def _chunk(tag, data):
    out = struct.pack(">I", len(data)) + tag + data
    out += struct.pack(">I", binascii.crc32(tag + data) & 0xFFFFFFFF)
    return out


def write_png(cv, path):
    raw = bytearray()
    stride = cv.w * 3
    for y in range(cv.h):
        raw.append(0)
        raw += cv.px[y * stride:(y + 1) * stride]
    ihdr = struct.pack(">IIBBBBB", cv.w, cv.h, 8, 2, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n"
    png += _chunk(b"IHDR", ihdr)
    png += _chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    png += _chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)


# ---------------------------------------------------------------------------
# Text: the font is 5 wide, 7 tall; scale multiplies every pixel.
# Bold draws each pixel one unit wider.
# ---------------------------------------------------------------------------
def draw_char(cv, x, y, ch, scale, color, bold=False):
    rows = FONT.get(ch)
    if rows is None:
        rows = FONT[" "]
    thick = 1 if (bold and scale >= 2) else 0
    for r in range(7):
        bits = rows[r]
        for col in range(5):
            if bits & (1 << (4 - col)):
                px = x + col * scale
                py = y + r * scale
                cv.rect(px, py, scale + thick, scale, color)


def text_width(s, scale, bold=False):
    n = len(s)
    if n == 0:
        return 0
    w = n * ADV * scale + (1 if bold and scale >= 2 else 0) * scale
    return w - scale  # no trailing spacing after the last glyph


def draw_text(cv, x, y, s, scale, color, bold=False):
    cx = x
    for ch in s:
        draw_char(cv, cx, y, ch, scale, color, bold)
        cx += ADV * scale
    return cx


def wrap_text(s, scale, max_w, bold=False):
    """Greedy word wrap; returns a list of lines that fit max_w."""
    words = s.split(" ")
    lines = []
    cur = ""
    for word in words:
        trial = word if not cur else cur + " " + word
        if text_width(trial, scale, bold) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def draw_para(cv, x, y, lines, scale, color, leading, bold=False):
    yy = y
    for line in lines:
        draw_text(cv, x, yy, line, scale, color, bold)
        yy += 7 * scale + leading
    return yy


def draw_centered(cv, y, s, scale, color, bold=False, cx=512):
    w = text_width(s, scale, bold)
    draw_text(cv, cx - w // 2, y, s, scale, color, bold)


# ---------------------------------------------------------------------------
# Pictograms: flat scenes drawn from primitives.
# ---------------------------------------------------------------------------
def pic_hero(cv, x, y, w, h):
    """Bahrain strike: night sky, explosion over a naval base, the sea."""
    cv.rect(x, y, w, h, NAVY)
    # stars
    for sx, sy in [(18, 14), (52, 30), (96, 10), (150, 22), (210, 12),
                   (240, 34), (120, 40), (30, 52), (190, 46)]:
        cv.rect(x + sx, y + sy, 3, 3, WHITE)
    # missile streak
    cv.line(x + 40, y + 120, x + 150, y + 46, WHITE, 3)
    cv.circle(x + 150, y + 46, 6, YELLOW)
    # explosion burst
    cv.starburst(x + 175, y + 78, 26, 52, 9, ORANGE)
    cv.starburst(x + 175, y + 78, 14, 30, 9, YELLOW)
    cv.circle(x + 175, y + 78, 12, WHITE)
    # base towers (silhouettes)
    cv.rect(x + 18, y + 128, 34, 62, (38, 52, 86))
    cv.rect(x + 60, y + 108, 26, 82, (30, 44, 74))
    cv.rect(x + 94, y + 140, 44, 50, (38, 52, 86))
    cv.rect(x + 210, y + 118, 30, 72, (30, 44, 74))
    for bx in (24, 40, 66, 76, 104, 122, 216, 228):
        cv.rect(x + bx, y + 138, 6, 8, YELLOW)
    # sea
    cv.rect(x, y + h - 34, w, 34, (24, 80, 130))
    for wy in (y + h - 26, y + h - 16, y + h - 7):
        for wx in range(8, w - 20, 34):
            cv.line(x + wx, wy, x + wx + 18, wy, SKY, 2)
    # ship
    cv.rect(x + 150, y + h - 52, 86, 12, (20, 20, 20))
    cv.rect(x + 168, y + h - 64, 30, 12, (20, 20, 20))
    cv.rect(x + 176, y + h - 76, 4, 12, (20, 20, 20))


def pic_badge(cv, x, y, w, h):
    """Mexico capture: prison bars and a gold badge."""
    cv.rect(x, y, w, h, (232, 222, 200))
    for bx in range(x + 14, x + w - 10, 26):
        cv.vline(bx, y + 4, h - 8, (120, 110, 92), 5)
    cx, cy = x + w // 2, y + h // 2
    cv.circle(cx, cy, 24, GOLD)
    cv.circle(cx, cy, 19, (240, 210, 110))
    # star
    pts = []
    import math
    for i in range(10):
        ang = 3.141592653589793 * i / 5 - 1.5708
        r = 15 if i % 2 == 0 else 6
        pts.append((int(cx + r * math.cos(ang)), int(cy + r * math.sin(ang))))
    cv.poly(pts, RED)


def pic_city(cv, x, y, w, h):
    """Kryvyi Rih: skyline under a double-tap strike."""
    cv.rect(x, y, w, h, (226, 214, 196))
    cv.rect(x, y, w, h // 2 + 6, (238, 226, 208))
    # skyline
    base = y + h - 4
    for bx, bw, bh in [(6, 34, 26), (48, 26, 36), (82, 40, 22),
                       (130, 30, 40), (168, 36, 28), (212, 30, 34),
                       (250, 38, 24), (296, 28, 38), (332, 34, 26),
                       (374, 30, 32), (412, 34, 22)]:
        cv.rect(x + bx, base - bh, bw, bh, (70, 66, 60))
        for wy in range(base - bh + 5, base - 4, 9):
            cv.rect(x + bx + 5, wy, 5, 5, YELLOW)
    # falling missiles and bursts
    cv.line(x + 120, y + 2, x + 96, y + 30, INK, 3)
    cv.starburst(x + 96, y + 34, 8, 16, 7, ORANGE)
    cv.line(x + 300, y + 6, x + 322, y + 28, INK, 3)
    cv.starburst(x + 322, y + 32, 9, 18, 7, RED)
    cv.circle(x + 322, y + 32, 5, YELLOW)
    # smoke
    for sx, sy, sr in [(86, 22, 7), (110, 18, 9), (312, 20, 8), (336, 24, 6)]:
        cv.circle(x + sx, y + sy, sr, (150, 146, 138))


def pic_globe(cv, x, y, w, h):
    """COP31: a warming globe with a rising arrow."""
    cv.rect(x, y, w, h, SKY)
    cx, cy = x + w // 2 - 30, y + h // 2
    cv.circle(cx, cy, 26, (52, 130, 190))
    cv.ellipse(cx - 12, cy - 8, 10, 7, GREEN)
    cv.ellipse(cx + 10, cy + 8, 9, 6, GREEN)
    cv.ellipse(cx + 2, cy - 14, 6, 5, GREEN)
    cv.line(cx - 26, cy - 6, cx + 26, cy + 6, (30, 90, 160), 2)
    cv.line(cx - 18, cy + 18, cx + 18, cy - 18, (30, 90, 160), 2)
    # rising temperature arrow
    ax = x + w - 58
    cv.line(ax, y + h - 8, ax, y + 8, RED, 4)
    cv.poly([(ax - 9, y + 16), (ax + 9, y + 16), (ax, y + 2)], RED)
    cv.circle(ax, y + h - 10, 7, RED)
    # sun
    cv.circle(x + 26, y + 12, 7, YELLOW)


def pic_chart(cv, x, y, w, h):
    """Wall Street: a falling market line over candlesticks."""
    cv.rect(x, y, w, h, (238, 236, 228))
    # candlesticks
    for bx, top, bot in [(30, 18, 30), (70, 12, 26), (110, 22, 34),
                         (150, 8, 24), (190, 26, 36), (230, 14, 28)]:
        cv.vline(x + bx + 5, y + top, bot - top + 8, INK, 2)
        cv.rect(x + bx, y + top + 3, 11, bot - top + 2, RED)
    # falling line with arrowhead
    pts = [(x + 8, y + 6), (x + 90, y + 12), (x + 170, y + 22),
           (x + 250, y + 26), (x + 330, y + 34), (x + 410, y + 40)]
    for a, b in zip(pts, pts[1:]):
        cv.line(a[0], a[1], b[0], b[1], DARKRED, 4)
    ex, ey = pts[-1]
    cv.poly([(ex, ey + 2), (ex - 14, ey - 4), (ex - 6, ey + 10)], DARKRED)


def pic_mosquito(cv, x, y, w, h):
    """Dengue trial: a mosquito inside a green shield of protection."""
    cv.rect(x, y, w, h, (226, 240, 226))
    cx, cy = x + w // 2, y + h // 2
    # shield
    cv.poly([(cx, y + 6), (cx + 34, y + 16), (cx + 34, y + 34),
             (cx, cy + h // 2 - 6), (cx - 34, y + 34), (cx - 34, y + 16)],
            GREEN)
    cv.poly([(cx, y + 11), (cx + 28, y + 19), (cx + 28, y + 33),
             (cx, cy + h // 2 - 11), (cx - 28, y + 33), (cx - 28, y + 19)],
            (226, 240, 226))
    # mosquito body
    cv.ellipse(cx, cy + 4, 7, 17, INK)
    cv.circle(cx, cy - 16, 7, INK)
    # wings
    cv.ellipse(cx - 13, cy - 8, 12, 5, (180, 190, 200))
    cv.ellipse(cx + 13, cy - 8, 12, 5, (180, 190, 200))
    # legs
    for dx in (-1, 0, 1):
        cv.line(cx + dx * 4, cy + 4, cx + dx * 18, cy + 16, INK, 2)
        cv.line(cx + dx * 4, cy + 10, cx + dx * 18, cy + 20, INK, 2)
    # antennae
    cv.line(cx - 3, cy - 21, cx - 11, cy - 31, INK, 2)
    cv.line(cx + 3, cy - 21, cx + 11, cy - 31, INK, 2)


# ---------------------------------------------------------------------------
# Layout: masthead, date banner, hero, story panels, also-today box.
# ---------------------------------------------------------------------------
M = 28  # page margin


def frame(cv, x, y, w, h, c=INK, t=2):
    cv.rect(x, y, w, t, c)
    cv.rect(x, y + h - t, w, t, c)
    cv.rect(x, y, t, h, c)
    cv.rect(x + w - t, y, t, h, c)


def story_panel(cv, x, y, w, h, pic, headline, summary, source):
    frame(cv, x, y, w, h)
    pic(cv, x + 12, y + 12, w - 24, 44)
    hx = x + 12
    hy = y + 62
    lines = wrap_text(headline, 3, w - 24, bold=True)
    draw_para(cv, hx, hy, lines[:2], 3, INK, 6, bold=True)
    sy = y + 116
    slines = wrap_text(summary, 2, w - 24)
    draw_para(cv, hx, sy, slines[:3], 2, BODY, 5)
    draw_text(cv, hx, y + 180, source, 2, CAPTION)


def draw_page():
    cv = Canvas(W, H, PAPER)

    # Masthead.
    draw_centered(cv, 16, "THE WORLD TODAY", 7, INK, bold=True)
    cv.hline(M, 74, W - 2 * M, INK, 2)
    cv.hline(M, 79, W - 2 * M, INK, 1)

    # Date banner.
    cv.rect(M, 86, W - 2 * M, 34, BLACK)
    draw_centered(cv, 95, "SATURDAY 21 NOVEMBER 2026", 3, WHITE, bold=True)

    # Hero: Iran strikes US bases in Bahrain.
    hy, hh = 132, 236
    frame(cv, M, hy, W - 2 * M, hh)
    pic_hero(cv, M + 2, hy + 2, 268, hh - 4)
    tx = M + 286
    draw_text(cv, tx, hy + 12, "GULF CRISIS - LEAD STORY", 3, RED, bold=True)
    hlines = ["IRAN STRIKES U.S.", "BASES IN BAHRAIN"]
    draw_para(cv, tx, hy + 40, hlines, 5, INK, 7, bold=True)
    cv.hline(tx, hy + 126, W - M - tx - 14, INK, 1)
    slines = wrap_text(
        "Tehran says its Guards hit two U.S. positions. Bahrain "
        "reports a fire at a civilian plant; no injuries.",
        3, W - M - tx - 14)
    draw_para(cv, tx, hy + 136, slines[:3], 3, BODY, 5)
    draw_text(cv, tx, hy + 214, "SOURCES: AL JAZEERA, CHANNEL NEWS ASIA",
              2, CAPTION)

    # Row A: Mexico | Kryvyi Rih.
    ay, ah = 380, 202
    pw = (W - 2 * M - 14) // 2
    story_panel(cv, M, ay, pw, ah, pic_badge,
                "MEXICO CAPTURES 'EL CHAPO ISIDRO'",
                "FBI most-wanted boss seized in Guasave; 11 die "
                "as gunmen fight back.",
                "SOURCES: REUTERS, AP")
    story_panel(cv, M + pw + 14, ay, pw, ah, pic_city,
                "MISSILE HITS ZELENSKYY'S HOMETOWN",
                "Double-tap strike kills a boy of 7 and a medic; "
                "60 hurt. Missiles land in Poland.",
                "SOURCES: AL JAZEERA, AP")

    # Row B: COP31 | Wall Street.
    by, bh = 594, 202
    story_panel(cv, M, by, pw, bh, pic_globe,
                "CLIMATE TALKS RUN INTO OVERTIME",
                "Talks in Antalya pass the deadline with no deal; "
                "the draft omits fossil fuels.",
                "SOURCE: REUTERS")
    story_panel(cv, M + pw + 14, by, pw, bh, pic_chart,
                "WALL STREET SLIDES INTO CORRECTION",
                "S&P 500 and Dow fall 10% from peaks as the AI "
                "sell-off deepens; Nasdaq erases 2026 gains.",
                "SOURCES: MORNINGSTAR, AP")

    # Row C: dengue panel + Also today.
    cy, ch = 808, 192
    dw = 612
    frame(cv, M, cy, dw, ch)
    pic_mosquito(cv, M + 12, cy + 12, 120, ch - 24)
    dx = M + 144
    dlines = ["MOSQUITOES THAT", "BEAT DENGUE"]
    draw_para(cv, dx, cy + 16, dlines, 4, INK, 8, bold=True)
    dsum = wrap_text(
        "Wolbachia mosquitoes cut dengue and chikungunya 69% "
        "in 5,700 children.",
        3, dw - 144 - 12)
    draw_para(cv, dx, cy + 92, dsum[:3], 3, BODY, 5)
    draw_text(cv, dx, cy + 174, "SOURCE: ASSOCIATED PRESS", 2, CAPTION)

    ax = M + dw + 12
    aw = W - M - ax
    frame(cv, ax, cy, aw, ch)
    draw_text(cv, ax + 12, cy + 12, "ALSO TODAY", 3, RED, bold=True)
    items = [
        "Anthropic claims AI-assisted Riemann proof.",
        "UK and EU sign three post-Brexit deals.",
        "EU-Indonesia trade deal covers 730m people.",
    ]
    iy = cy + 44
    for item in items:
        cv.rect(ax + 12, iy + 3, 8, 8, RED)
        ilines = wrap_text(item, 2, aw - 28)
        iy = draw_para(cv, ax + 28, iy, ilines[:2], 2, BODY, 4)
        iy += 8

    return cv


def main():
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "output")
    os.makedirs(out_dir, exist_ok=True)
    cv = draw_page()
    write_png(cv, os.path.join(out_dir, "entry.png"))


if __name__ == "__main__":
    main()
