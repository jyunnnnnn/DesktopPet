"""小圖示：全部自己畫（PIL），不用 emoji 或文字符號。

為什麼：emoji 是文字，有的電腦缺字會變成方框、每台電腦長得也不一樣。
用法：
- `draw_icon(name, size, color=None)`：回傳 size×size 的透明底圖。先放大 4 倍畫、再縮小，邊緣才平滑。
  單色的圖示（叉叉、勾、箭頭、音符……）用 color 上色；彩色的（食物、愛心、金幣……）自己有顏色。
- `ICON_CHARS`：文字裡的某個字元要換成哪個圖示。對話、標籤裡原本寫的 ♪ ✓ 🎧 ……會自動換成畫好的圖，
  另外有幾個私用區字元（COIN 等）是沒有對應文字的純圖示。
要新增圖示：在 `ART` 加一個畫圖函式，需要的話在 `ICON_CHARS` 加對應的字元。
"""
import math

from PIL import Image, ImageChops, ImageDraw, ImageFilter

# 沒有對應文字的純圖示（私用區字元，只當「圖示的位置」）
COIN, CAPSULE, TROPHY, LOCK, NOICON = "", "", "", "", ""

# 文字裡的字元 → 圖示名稱
ICON_CHARS = {
    COIN: "coin", CAPSULE: "capsule", TROPHY: "trophy", LOCK: "lock", NOICON: "blank",
    "♪": "note", "♫": "notes", "♩": "note", "🎵": "notes", "🎶": "notes", "✦": "sparkle", "✿": "flower", "♥": "heart",
    "✓": "check", "✕": "close", "×": "close", "－": "minus", "›": "chevron", "◀": "prev", "▶": "next", "≡": "menu",
    "⤢": "expand", "⇲": "shrink", "⇄": "swap", "◢": "grip", "✎": "pencil",
    "🎧": "headphones", "📁": "folder", "📂": "folder_open", "⏰": "clock", "🍬": "candy", "⚠": "warn", "💤": "zzz",
    "🔁": "repeat", "📸": "camera", "🎉": "party", "🎲": "dice", "🍱": "bento", "🎂": "birthday",
    "✌": "hand_scissors", "✊": "hand_rock", "✋": "hand_paper",
}
# 單色圖示：畫的時候用「文字的顏色」（跟字一樣深淺、一樣的 hover 色）
MONO = {"note", "notes", "sparkle", "flower", "check", "close", "minus", "chevron", "prev", "next", "menu", "expand",
        "shrink", "swap", "grip", "pencil", "repeat", "question", "zed", "exclaim"}
SKIP = "️‍"          # 變體選擇字元：沒有字，直接略過

INK = (74, 52, 42)               # 沒指定顏色時單色圖示用的深褐色


def _rgba(c, a=255):
    if c is None:
        return INK + (a,)
    if isinstance(c, str):
        h = c.lstrip("#")
        try:
            c = tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) if len(h) == 6 else INK       # 不是 #rrggbb（例如系統色名稱）就用預設色
        except ValueError:
            c = INK
    return tuple(c[:3]) + ((c[3] if len(c) > 3 else a),)


class _Pen:
    """用 0～100 的座標畫圖，自動放大到畫布。"""

    def __init__(self, size, scale=4):
        self.S = size * scale
        self.u = self.S / 100
        self.im = Image.new("RGBA", (self.S, self.S), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.im)

    def pt(self, p):
        return (p[0] * self.u, p[1] * self.u)

    def box(self, b):
        return tuple(v * self.u for v in b)

    def w(self, v):
        return max(1, int(round(v * self.u)))

    def poly(self, pts, fill=None, outline=None, width=0):
        self.d.polygon([self.pt(p) for p in pts], fill=fill, outline=outline, width=self.w(width) if width else 0)

    def ell(self, b, fill=None, outline=None, width=0):
        self.d.ellipse(self.box(b), fill=fill, outline=outline, width=self.w(width) if width else 0)

    def rect(self, b, r=0, fill=None, outline=None, width=0):
        self.d.rounded_rectangle(self.box(b), radius=r * self.u, fill=fill, outline=outline, width=self.w(width) if width else 0)

    def line(self, pts, fill, width, round_caps=True):
        pts = [self.pt(p) for p in pts]
        self.d.line(pts, fill=fill, width=self.w(width), joint="curve")
        if round_caps:
            r = self.w(width) / 2
            for x, y in (pts[0], pts[-1]):
                self.d.ellipse((x - r, y - r, x + r, y + r), fill=fill)

    def arc(self, b, a0, a1, fill, width):
        self.d.arc(self.box(b), a0, a1, fill=fill, width=self.w(width))

    def gfill(self, shape, top, bot, y0=0, y1=100):
        """漸層填色：shape(draw, pen) 用白色畫出形狀，裡面由上（top）到下（bot）漸層上色。"""
        m = Image.new("L", (self.S, self.S), 0)
        shape(ImageDraw.Draw(m), self)
        g = Image.new("RGBA", (self.S, self.S)); gd = ImageDraw.Draw(g)
        for y in range(self.S):
            t = min(1.0, max(0.0, (y / self.u - y0) / max(1e-6, y1 - y0)))
            gd.line((0, y, self.S, y), fill=tuple(round(top[k] + (bot[k] - top[k]) * t) for k in range(4)))
        self.im.paste(g, (0, 0), m)

    def stroke(self, shape, color, width):
        """沿著 shape 的邊緣描一圈外框（形狀不是簡單圖形時用）。"""
        m = Image.new("L", (self.S, self.S), 0)
        shape(ImageDraw.Draw(m), self)
        ring = ImageChops.subtract(m, m.filter(ImageFilter.MinFilter(self.w(width) * 2 + 1)))
        self.im.paste(Image.new("RGBA", (self.S, self.S), color), (0, 0), ring)

    def out(self, size):
        return self.im.resize((size, size), Image.LANCZOS)


# ------------------------------------------------------------------ 介面小圖示（單色）
def _close(p, c):
    p.line([(22, 22), (78, 78)], c, 12); p.line([(78, 22), (22, 78)], c, 12)


def _minus(p, c):
    p.line([(20, 50), (80, 50)], c, 12)


def _check(p, c):
    p.line([(18, 54), (40, 76), (82, 26)], c, 13)


def _prev(p, c):
    p.poly([(74, 14), (74, 86), (24, 50)], fill=c)


def _next(p, c):
    p.poly([(26, 14), (26, 86), (76, 50)], fill=c)


def _menu(p, c):
    for y in (26, 50, 74):
        p.line([(18, y), (82, y)], c, 10)


def _expand(p, c):
    p.line([(28, 72), (72, 28)], c, 8)
    p.poly([(46, 20), (80, 20), (80, 54)], fill=c); p.poly([(54, 80), (20, 80), (20, 46)], fill=c)


def _shrink(p, c):
    p.line([(24, 24), (64, 64)], c, 8)
    p.poly([(80, 80), (80, 44), (44, 80)], fill=c)


def _swap(p, c):
    p.line([(14, 34), (72, 34)], c, 8); p.poly([(70, 20), (92, 34), (70, 48)], fill=c)
    p.line([(86, 66), (28, 66)], c, 8); p.poly([(30, 52), (8, 66), (30, 80)], fill=c)


def _grip(p, c):
    p.poly([(90, 90), (90, 34), (34, 90)], fill=c)


def _chevron(p, c):
    p.line([(36, 18), (66, 50), (36, 82)], c, 12)


def _pencil(p, c):
    p.line([(36, 64), (74, 26)], c, 18, round_caps=False)
    p.poly([(20, 82), (26, 60), (40, 74)], fill=c)
    p.line([(70, 22), (78, 30)], (255, 255, 255, 0), 1, round_caps=False)


def _note(p, c):
    p.ell((18, 62, 50, 88), fill=c)
    p.rect((44, 16, 52, 76), fill=c)
    p.poly([(52, 16), (80, 32), (76, 54), (52, 40)], fill=c)


def _notes(p, c):
    p.ell((10, 64, 40, 88), fill=c); p.ell((54, 56, 84, 80), fill=c)
    p.rect((34, 22, 42, 76), fill=c); p.rect((78, 14, 86, 68), fill=c)
    p.poly([(34, 22), (86, 12), (86, 30), (34, 40)], fill=c)


def _sparkle(p, c):
    pts = []
    for i in range(8):
        r = 46 if i % 2 == 0 else 12
        a = math.pi / 4 * i - math.pi / 2
        pts.append((50 + r * math.cos(a), 50 + r * math.sin(a)))
    p.poly(pts, fill=c)


def _flower(p, c):
    for i in range(6):
        a = math.pi / 3 * i
        x, y = 50 + 26 * math.cos(a), 50 + 26 * math.sin(a)
        p.ell((x - 17, y - 17, x + 17, y + 17), fill=c)
    p.ell((38, 38, 62, 62), fill=(255, 255, 255, 150))


def _repeat(p, c):
    p.arc((14, 22, 86, 78), 200, 340, c, 8)
    p.poly([(70, 12), (94, 30), (66, 40)], fill=c)
    p.arc((14, 22, 86, 78), 20, 160, c, 8)
    p.poly([(30, 88), (6, 70), (34, 60)], fill=c)


# ------------------------------------------------------------------ 彩色圖示
def _heart(p, c):
    col = _rgba(c) if c else (255, 105, 135, 255)
    p.ell((8, 14, 54, 60), fill=col); p.ell((46, 14, 92, 60), fill=col)
    p.poly([(11, 46), (89, 46), (50, 90)], fill=col)
    p.ell((18, 24, 32, 36), fill=(255, 255, 255, 130))


def _coin(p, c):
    p.ell((6, 6, 94, 94), fill=(255, 205, 60, 255), outline=(207, 140, 18, 255), width=6)
    p.ell((22, 22, 78, 78), outline=(235, 168, 28, 255), width=5)
    p.arc((14, 14, 86, 86), 200, 260, (255, 240, 170, 255), 6)
    p.poly([(50, 34), (55, 46), (67, 50), (55, 54), (50, 66), (45, 54), (33, 50), (45, 46)], fill=(255, 244, 200, 255))


def _capsule(p, c):
    box = (8, 8, 92, 92)
    p.d.pieslice(p.box(box), 180, 360, fill=(240, 120, 58, 255))
    p.d.pieslice(p.box(box), 0, 180, fill=(255, 246, 232, 255))
    p.ell(box, outline=(150, 82, 46, 255), width=5)
    p.line([(8, 50), (92, 50)], (150, 82, 46, 255), 5, round_caps=False)
    p.ell((24, 20, 40, 34), fill=(255, 255, 255, 190))


def _trophy(p, c):
    gold, edge = (255, 200, 50, 255), (196, 132, 16, 255)
    p.arc((4, 14, 36, 52), 90, 270, edge, 7); p.arc((64, 14, 96, 52), 270, 90, edge, 7)
    p.poly([(24, 10), (76, 10), (72, 44), (60, 62), (40, 62), (28, 44)], fill=gold, outline=edge, width=2)
    p.rect((44, 62, 56, 76), fill=gold, outline=edge, width=2)
    p.rect((28, 76, 72, 90), r=4, fill=gold, outline=edge, width=3)
    _star(p, 50, 34, 14, (255, 244, 200, 255))


def _star(p, cx, cy, r, col):
    pts = []
    for i in range(10):
        rr = r if i % 2 == 0 else r * .45
        a = math.pi / 5 * i - math.pi / 2
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    p.poly(pts, fill=col)


def _lock(p, c):
    p.arc((26, 8, 74, 60), 180, 360, (150, 132, 120, 255), 9)
    p.rect((18, 42, 82, 92), r=10, fill=(190, 172, 160, 255), outline=(140, 122, 110, 255), width=4)
    p.ell((44, 56, 56, 68), fill=(120, 104, 94, 255)); p.rect((48, 64, 52, 78), fill=(120, 104, 94, 255))


def _blank(p, c):
    pass


def _headphones(p, c):
    col = _rgba(c) if c else (112, 92, 176, 255)
    p.arc((16, 12, 84, 80), 180, 360, col, 9)
    p.rect((10, 48, 32, 82), r=8, fill=col); p.rect((68, 48, 90, 82), r=8, fill=col)
    p.rect((16, 54, 26, 76), r=4, fill=(255, 255, 255, 120)); p.rect((74, 54, 84, 76), r=4, fill=(255, 255, 255, 120))


def _folder(p, c):
    p.poly([(8, 26), (38, 26), (46, 36), (92, 36), (92, 84), (8, 84)], fill=(246, 188, 70, 255), outline=(196, 132, 30, 255), width=3)
    p.rect((8, 44, 92, 84), r=6, fill=(255, 208, 100, 255), outline=(196, 132, 30, 255), width=3)


def _folder_open(p, c):
    p.poly([(8, 22), (36, 22), (44, 32), (84, 32), (84, 80), (8, 80)], fill=(238, 172, 60, 255), outline=(196, 132, 30, 255), width=3)
    p.poly([(20, 46), (96, 46), (82, 86), (6, 86)], fill=(255, 208, 100, 255), outline=(196, 132, 30, 255), width=3)


def _clock(p, c):
    red, dark = (232, 90, 70, 255), (120, 60, 40, 255)
    p.ell((8, 6, 40, 38), fill=red, outline=dark, width=3); p.ell((60, 6, 92, 38), fill=red, outline=dark, width=3)
    p.ell((14, 16, 86, 88), fill=(255, 252, 244, 255), outline=red, width=7)
    p.line([(50, 52), (50, 32)], dark, 6); p.line([(50, 52), (66, 58)], dark, 6)
    p.line([(26, 90), (16, 98)], dark, 6); p.line([(74, 90), (84, 98)], dark, 6)


def _candy(p, c):
    p.poly([(4, 30), (30, 50), (4, 70)], fill=(255, 140, 170, 255)); p.poly([(96, 30), (70, 50), (96, 70)], fill=(255, 140, 170, 255))
    p.ell((22, 26, 78, 74), fill=(255, 112, 150, 255), outline=(200, 70, 110, 255), width=3)
    p.arc((28, 32, 72, 68), 200, 290, (255, 255, 255, 230), 6); p.arc((30, 34, 70, 66), 20, 110, (255, 214, 224, 255), 6)


def _warn(p, c):
    p.poly([(50, 8), (95, 88), (5, 88)], fill=(255, 196, 40, 255), outline=(176, 112, 10, 255), width=5)
    p.rect((45, 34, 55, 64), r=3, fill=(104, 64, 20, 255)); p.ell((44, 69, 56, 81), fill=(104, 64, 20, 255))


def _zzz(p, c):
    col = (120, 140, 205, 255)
    for x, y, s in ((10, 46, 36), (44, 22, 28), (70, 4, 22)):
        p.line([(x, y), (x + s, y), (x, y + s), (x + s, y + s)], col, 7 if s > 24 else 6, round_caps=True)


def _camera(p, c):
    p.rect((8, 28, 92, 82), r=10, fill=(120, 126, 140, 255), outline=(72, 76, 90, 255), width=3)
    p.rect((30, 18, 58, 32), r=4, fill=(120, 126, 140, 255), outline=(72, 76, 90, 255), width=3)
    p.ell((30, 36, 70, 76), fill=(240, 244, 250, 255), outline=(72, 76, 90, 255), width=4); p.ell((40, 46, 60, 66), fill=(86, 130, 190, 255))
    p.ell((76, 36, 86, 46), fill=(255, 220, 110, 255))


def _party(p, c):
    p.poly([(10, 90), (34, 30), (70, 66)], fill=(255, 176, 60, 255), outline=(200, 120, 20, 255), width=3)
    p.line([(26, 66), (44, 82)], (232, 90, 70, 255), 5, round_caps=False); p.line([(20, 80), (30, 88)], (232, 90, 70, 255), 5, round_caps=False)
    for (x, y), col in (((58, 22), (255, 100, 130, 255)), ((82, 40), (90, 170, 240, 255)), ((70, 12), (120, 200, 120, 255)), ((90, 66), (255, 210, 60, 255))):
        p.ell((x - 5, y - 5, x + 5, y + 5), fill=col)
    p.line([(46, 22), (54, 8)], (170, 110, 220, 255), 5); p.line([(80, 24), (92, 20)], (255, 120, 150, 255), 5)


def _dice(p, c):
    p.rect((10, 10, 90, 90), r=16, fill=(255, 252, 246, 255), outline=(150, 120, 100, 255), width=5)
    for x, y in ((30, 30), (70, 30), (50, 50), (30, 70), (70, 70)):
        p.ell((x - 8, y - 8, x + 8, y + 8), fill=(214, 70, 70, 255) if (x, y) == (50, 50) else (74, 52, 42, 255))


def _bento(p, c):
    p.rect((6, 22, 94, 84), r=10, fill=(150, 90, 56, 255), outline=(100, 56, 32, 255), width=3)
    p.rect((12, 28, 50, 78), r=6, fill=(255, 252, 244, 255)); p.ell((22, 38, 40, 56), fill=(214, 70, 70, 255))
    p.rect((54, 28, 88, 50), r=5, fill=(255, 196, 80, 255)); p.rect((54, 54, 88, 78), r=5, fill=(120, 190, 100, 255))


def _birthday(p, c):
    p.rect((8, 78, 92, 90), r=4, fill=(220, 200, 180, 255))
    p.rect((16, 52, 84, 80), r=6, fill=(255, 190, 200, 255), outline=(220, 130, 150, 255), width=3)
    p.rect((24, 34, 76, 54), r=6, fill=(255, 246, 232, 255), outline=(220, 130, 150, 255), width=3)
    p.rect((47, 14, 53, 34), fill=(120, 190, 240, 255)); p.poly([(50, 3), (57, 14), (43, 14)], fill=(255, 180, 50, 255))
    for x in (28, 44, 60, 74):
        p.ell((x - 5, 50, x + 5, 64), fill=(255, 246, 232, 255))


def _hand(p, kind):
    skin, edge = (255, 218, 170, 255), (196, 140, 90, 255)
    if kind == "paper":
        p.rect((26, 44, 74, 92), r=14, fill=skin, outline=edge, width=3)
        for i, x in enumerate((26, 40, 54, 66)):
            p.rect((x, 8 + (0 if i in (1, 2) else 8), x + 12, 56), r=6, fill=skin, outline=edge, width=3)
        p.rect((8, 48, 32, 62), r=7, fill=skin, outline=edge, width=3)
    elif kind == "rock":
        p.rect((18, 34, 82, 90), r=18, fill=skin, outline=edge, width=3)
        for x in (22, 38, 54, 68):
            p.rect((x, 26, x + 13, 52), r=6, fill=skin, outline=edge, width=3)
        p.rect((8, 54, 40, 70), r=8, fill=skin, outline=edge, width=3)
    else:  # scissors
        p.rect((26, 52, 82, 92), r=16, fill=skin, outline=edge, width=3)
        p.poly([(34, 56), (22, 8), (36, 6), (48, 52)], fill=skin, outline=edge, width=3)
        p.poly([(52, 52), (64, 6), (78, 10), (66, 56)], fill=skin, outline=edge, width=3)
        p.rect((8, 56, 36, 70), r=7, fill=skin, outline=edge, width=3)


# ------------------------------------------------------------------ 丟給她們的東西（食物、玩具）
OUT = (104, 66, 48, 255)           # 食物、玩具的外框：深褐色
HI = (255, 255, 255, 170)          # 高光


def _onigiri(p, c):
    def tri(d, pen):                                             # 圓角三角形（角上放小圓，再整個填滿）
        pts = ((50, 12), (90, 78), (10, 78))
        d.polygon([pen.pt(q) for q in pts], fill=255)
        for cx, cy in ((50, 16), (86, 75), (14, 75)):
            d.ellipse(pen.box((cx - 6, cy - 6, cx + 6, cy + 6)), fill=255)
        d.polygon([pen.pt(q) for q in ((50, 10), (92, 77), (8, 77))], fill=255)
    p.gfill(tri, (255, 255, 252, 255), (226, 230, 236, 255), 8, 88)
    p.stroke(tri, OUT, 2.5)
    for x, y in ((40, 40), (56, 34), (48, 52), (62, 52), (34, 58), (70, 62), (50, 66), (26, 68)):      # 飯粒
        p.ell((x - 3, y - 2, x + 3, y + 2), fill=(240, 240, 232, 255), outline=(206, 206, 198, 255), width=1)
    p.rect((24, 62, 76, 94), r=6, fill=(38, 54, 46, 255), outline=OUT, width=2)                    # 海苔
    p.rect((30, 66, 70, 71), r=2, fill=(86, 110, 96, 255))
    p.ell((43, 42, 57, 54), fill=(240, 110, 130, 255), outline=(190, 70, 90, 255), width=2)         # 梅子
    p.ell((40, 20, 50, 30), fill=HI)


def _rice(p, c):
    p.gfill(lambda d, pen: d.pieslice(pen.box((10, 14, 90, 70)), 180, 360, fill=255), (255, 255, 252, 255), (228, 232, 238, 255), 14, 44)
    for x, y in ((30, 34), (44, 26), (58, 30), (70, 38), (38, 40), (52, 40), (64, 46), (24, 42), (78, 46), (48, 33)):
        p.ell((x - 4, y - 2.5, x + 4, y + 2.5), fill=(247, 247, 240, 255), outline=(206, 206, 198, 255), width=1)
    p.d.arc(p.box((10, 14, 90, 70)), 180, 360, fill=OUT, width=p.w(2.5))
    p.gfill(lambda d, pen: d.pieslice(pen.box((6, 36, 94, 96)), 0, 180, fill=255), (96, 150, 214, 255), (52, 92, 160, 255), 40, 94)       # 藍白瓷碗
    p.d.pieslice(p.box((6, 36, 94, 96)), 0, 180, outline=OUT, width=p.w(3))
    p.rect((4, 34, 96, 46), r=5, fill=(250, 250, 246, 255), outline=OUT, width=2.5)                  # 碗口
    for x in (24, 40, 56, 72):
        p.ell((x - 5, 58, x + 5, 70), fill=(250, 250, 246, 255))
        p.ell((x - 2, 61, x + 2, 67), fill=(96, 150, 214, 255))
    p.rect((14, 38, 30, 42), r=2, fill=HI)


def _cake_slice(p, c):
    p.poly([(8, 82), (8, 40), (92, 26), (92, 82)], fill=(255, 232, 196, 255), outline=OUT, width=3)         # 海綿蛋糕
    p.poly([(8, 56), (92, 42), (92, 50), (8, 64)], fill=(255, 250, 244, 255))                                   # 鮮奶油夾層
    p.poly([(8, 70), (92, 58), (92, 64), (8, 76)], fill=(255, 250, 244, 255))
    p.poly([(8, 40), (92, 26), (92, 44), (8, 58)], fill=(255, 168, 190, 255), outline=OUT, width=3)             # 粉紅糖霜
    for x in (18, 34, 50, 66, 82):
        p.ell((x - 5, 42 - (82 - x) * .16, x + 5, 54 - (82 - x) * .16), fill=(255, 168, 190, 255))
    p.rect((8, 80, 92, 90), r=3, fill=(232, 208, 180, 255), outline=OUT, width=2)                              # 底盤
    p.gfill(lambda d, pen: d.ellipse(pen.box((34, 12, 64, 40)), fill=255), (255, 90, 100, 255), (214, 40, 60, 255), 12, 40)
    p.d.ellipse(p.box((34, 12, 64, 40)), outline=OUT, width=p.w(2.5))
    for x, y in ((44, 22), (54, 24), (48, 31), (58, 31)):
        p.ell((x - 1.5, y - 2, x + 1.5, y + 2), fill=(255, 230, 150, 255))
    p.poly([(44, 14), (50, 6), (56, 14), (50, 12)], fill=(96, 170, 84, 255), outline=OUT, width=1.5)
    p.ell((38, 16, 46, 24), fill=HI)


def _dango(p, c):
    p.line([(50, 2), (50, 98)], (200, 160, 100, 255), 5)
    for y, top, bot in ((22, (255, 196, 214, 255), (240, 140, 170, 255)), (50, (255, 255, 252, 255), (230, 232, 238, 255)), (78, (178, 226, 150, 255), (110, 186, 100, 255))):
        p.gfill(lambda d, pen, y=y: d.ellipse(pen.box((24, y - 16, 76, y + 16)), fill=255), top, bot, y - 16, y + 16)
        p.d.ellipse(p.box((24, y - 16, 76, y + 16)), outline=OUT, width=p.w(2.5))
        p.ell((34, y - 12, 46, y - 4), fill=HI)


def _donut(p, c):
    p.gfill(lambda d, pen: d.ellipse(pen.box((6, 12, 94, 92)), fill=255), (238, 190, 112, 255), (200, 140, 72, 255), 12, 92)
    p.d.ellipse(p.box((6, 12, 94, 92)), outline=OUT, width=p.w(3))
    p.gfill(lambda d, pen: d.ellipse(pen.box((10, 12, 90, 76)), fill=255), (255, 176, 204, 255), (240, 120, 168, 255), 12, 76)    # 糖霜
    for x in (14, 28, 48, 66, 82):                                                                               # 糖霜滴下來
        p.ell((x - 7, 64, x + 7, 80), fill=(244, 132, 176, 255))
    p.d.ellipse(p.box((10, 12, 90, 76)), outline=(196, 84, 132, 255), width=p.w(2.5))
    for x, y, a, col in ((22, 30, 30, (96, 170, 240)), (66, 22, -20, (255, 224, 90)), (78, 46, 60, (140, 220, 140)), (24, 56, -40, (255, 255, 255)),
                         (50, 20, 10, (255, 255, 255)), (40, 66, 20, (96, 170, 240)), (62, 64, -30, (255, 224, 90))):
        dx, dy = 5 * math.cos(math.radians(a)), 5 * math.sin(math.radians(a))
        p.line([(x - dx, y - dy), (x + dx, y + dy)], col + (255,), 3.4)
    p.ell((18, 22, 30, 32), fill=HI)
    hole = Image.new("L", (p.S, p.S), 255)                                                                       # 中間挖一個洞（透明）
    ImageDraw.Draw(hole).ellipse(p.box((34, 32, 66, 58)), fill=0)
    p.im.putalpha(ImageChops.multiply(p.im.getchannel("A"), hole))
    p.d.ellipse(p.box((34, 32, 66, 58)), outline=OUT, width=p.w(2.5))


def _strawberry(p, c):
    def shape(d, pen):
        d.polygon([pen.pt(q) for q in ((12, 38), (88, 38), (60, 94), (40, 94))], fill=255)
        d.ellipse(pen.box((10, 18, 90, 66)), fill=255)
    p.gfill(shape, (248, 84, 96, 255), (206, 34, 58, 255), 18, 94)
    p.stroke(shape, OUT, 2.5)
    for x, y in ((28, 42), (44, 38), (60, 40), (74, 44), (36, 56), (52, 52), (66, 58), (44, 70), (58, 72), (50, 84)):
        p.ell((x - 2.5, y - 3.5, x + 2.5, y + 3.5), fill=(255, 232, 150, 255), outline=(190, 130, 40, 255), width=1)
    leaf = (104, 182, 92, 255)
    for a in (-60, -30, 0, 30, 60):
        ex, ey = 50 + 26 * math.sin(math.radians(a)), 22 - 12 * math.cos(math.radians(a)) + 8
        p.poly([(50, 24), (50 + (ex - 50) * .5 - 5, 24 + (ey - 24) * .5), (ex, ey), (50 + (ex - 50) * .5 + 5, 24 + (ey - 24) * .5)], fill=leaf, outline=OUT, width=1.5)
    p.line([(50, 22), (52, 6)], (84, 140, 66, 255), 6)
    p.ell((24, 28, 40, 40), fill=HI)


def _banana(p, c):
    body, edge = (255, 226, 84, 255), (190, 140, 20, 255)
    box = (2, -18, 94, 74)
    p.arc(box, 22, 158, edge, 30)
    p.arc(box, 25, 155, body, 22)
    p.arc(box, 30, 150, (255, 240, 140, 255), 6)                                                       # 高光帶
    p.arc(box, 70, 118, (226, 176, 40, 255), 4.5)                                                      # 稜線
    p.rect((2, 34, 16, 48), r=4, fill=(120, 84, 40, 255), outline=OUT, width=2)                          # 蒂頭
    p.ell((82, 40, 94, 52), fill=(96, 66, 40, 255), outline=OUT, width=1.5)                              # 尾巴


def _drink(p, c):
    p.line([(62, 2), (58, 28)], (244, 92, 112, 255), 6)
    p.line([(62, 2), (70, 2)], (244, 92, 112, 255), 6)
    cup = ((20, 30), (80, 30), (72, 94), (28, 94))
    p.gfill(lambda d, pen: d.polygon([pen.pt(q) for q in cup], fill=255), (250, 214, 190, 255), (214, 150, 110, 255), 30, 94)   # 奶茶
    p.d.line([p.pt(q) for q in ((20, 30), (28, 94), (72, 94), (80, 30))], fill=OUT, width=p.w(2.5), joint="curve")
    p.poly([(23, 50), (77, 50), (72, 94), (28, 94)], fill=(232, 176, 128, 255))
    for x, y in ((38, 84), (50, 86), (62, 84), (44, 76), (56, 77)):                                      # 珍珠
        p.ell((x - 5, y - 5, x + 5, y + 5), fill=(70, 44, 34, 255), outline=(40, 24, 20, 255), width=1)
        p.ell((x - 3, y - 3.5, x, y - 1), fill=(150, 120, 100, 255))
    p.rect((14, 20, 86, 34), r=5, fill=(250, 250, 246, 255), outline=OUT, width=2.5)                      # 杯蓋
    p.rect((26, 34, 36, 70), r=3, fill=HI)


def _tea(p, c):
    for x in (34, 50, 66):                                                                                # 熱氣
        p.arc((x - 9, 2, x + 9, 24), 90, 270, (186, 198, 210, 255), 4)
        p.arc((x - 9, 18, x + 9, 38), 270, 90, (186, 198, 210, 255), 4)
    p.ell((6, 78, 94, 96), fill=(244, 244, 240, 255), outline=OUT, width=2.5)                             # 茶碟
    p.ell((22, 82, 78, 92), fill=(220, 224, 228, 255))
    p.arc((70, 44, 100, 74), 270, 90, OUT, 8)
    p.arc((70, 44, 100, 74), 270, 90, (250, 250, 246, 255), 4)                                            # 把手
    p.gfill(lambda d, pen: (d.pieslice(pen.box((14, 22, 86, 90)), 0, 180, fill=255), d.rectangle(pen.box((14, 40, 86, 56)), fill=255)),
            (255, 255, 252, 255), (226, 230, 236, 255), 40, 88)
    p.d.arc(p.box((14, 22, 86, 90)), 0, 180, fill=OUT, width=p.w(2.5))
    p.ell((14, 36, 86, 60), fill=(250, 250, 246, 255), outline=OUT, width=2.5)                             # 杯口
    p.gfill(lambda d, pen: d.ellipse(pen.box((19, 40, 81, 56)), fill=255), (196, 130, 60, 255), (150, 86, 36, 255), 40, 56)   # 茶
    p.ell((28, 43, 46, 49), fill=(240, 190, 120, 160))
    for x, y in ((26, 70), (50, 74), (74, 70)):                                                           # 花紋
        p.ell((x - 3, y - 3, x + 3, y + 3), fill=(238, 150, 180, 255))
    p.ell((20, 62, 28, 70), fill=HI)


def _soccer(p, c):
    p.gfill(lambda d, pen: d.ellipse(pen.box((6, 6, 94, 94)), fill=255), (255, 255, 255, 255), (214, 218, 226, 255), 6, 94)
    dark = (44, 46, 54, 255)
    p.poly([(50, 28), (68, 42), (61, 64), (39, 64), (32, 42)], fill=dark)
    for a in range(5):
        ang = math.pi * 2 / 5 * a - math.pi / 2
        x, y = 50 + 36 * math.cos(ang), 50 + 36 * math.sin(ang)
        p.line([(50 + 22 * math.cos(ang), 50 + 22 * math.sin(ang)), (50 + 34 * math.cos(ang), 50 + 34 * math.sin(ang))], (96, 100, 110, 255), 2.5)
        p.ell((x - 8, y - 6, x + 8, y + 6), fill=dark)
    p.d.ellipse(p.box((6, 6, 94, 94)), outline=OUT, width=p.w(3.5))
    p.ell((20, 16, 40, 32), fill=(255, 255, 255, 180))


def _basketball(p, c):
    p.gfill(lambda d, pen: d.ellipse(pen.box((6, 6, 94, 94)), fill=255), (255, 160, 70, 255), (222, 100, 36, 255), 6, 94)
    dark = (80, 44, 24, 255)
    p.line([(50, 6), (50, 94)], dark, 3.5, round_caps=False)
    p.line([(6, 50), (94, 50)], dark, 3.5, round_caps=False)
    p.arc((-26, 8, 40, 92), -62, 62, dark, 3.5)
    p.arc((60, 8, 126, 92), 118, 242, dark, 3.5)
    for x, y in ((24, 30), (30, 70), (70, 24), (74, 66)):                                                 # 皮的小顆粒
        p.ell((x - 1.5, y - 1.5, x + 1.5, y + 1.5), fill=(190, 90, 40, 255))
    p.d.ellipse(p.box((6, 6, 94, 94)), outline=dark, width=p.w(3.5))
    p.ell((18, 14, 38, 30), fill=(255, 255, 255, 120))


def _yarn(p, c):
    p.gfill(lambda d, pen: d.ellipse(pen.box((8, 8, 88, 88)), fill=255), (214, 156, 236, 255), (162, 100, 200, 255), 8, 88)
    dark, light = (124, 72, 168, 255), (232, 190, 250, 255)
    for box, a0, a1 in (((4, 24, 98, 76), 192, 338), ((12, 40, 102, 102), 205, 330), ((-6, 6, 72, 88), 330, 78), ((18, -6, 102, 84), 98, 200),
                        ((20, 16, 80, 90), 20, 120), ((2, 14, 80, 94), 240, 300)):
        p.arc(box, a0, a1, dark, 4.5)
        p.arc(box, a0 + 3, a1 - 3, light, 1.8)
    p.d.ellipse(p.box((8, 8, 88, 88)), outline=(110, 62, 150, 255), width=p.w(3.5))
    p.ell((22, 18, 40, 32), fill=(255, 255, 255, 150))
    p.line([(78, 76), (92, 84), (88, 96)], (190, 130, 224, 255), 5)
    p.line([(78, 76), (92, 84), (88, 96)], light, 1.8)


def _question(p, c):
    p.arc((26, 8, 74, 52), 180, 450, c, 11)
    p.line([(50, 50), (50, 64)], c, 11); p.ell((43, 76, 57, 90), fill=c)


def _zed(p, c):
    p.line([(22, 24), (78, 24), (22, 76), (78, 76)], c, 13)


def _sunflower(p, c):
    for i in range(12):
        a = math.pi / 6 * i
        x, y = 50 + 31 * math.cos(a), 50 + 31 * math.sin(a)
        p.ell((x - 11, y - 11, x + 11, y + 11), fill=(255, 205, 50, 255), outline=(224, 160, 20, 255), width=2)
    p.ell((28, 28, 72, 72), fill=(130, 84, 40, 255), outline=(96, 60, 28, 255), width=3)
    for x, y in ((42, 42), (58, 42), (50, 50), (42, 58), (58, 58)):
        p.ell((x - 3, y - 3, x + 3, y + 3), fill=(180, 126, 70, 255))


def _pin(p, c):
    p.line([(36, 62), (18, 90)], (150, 150, 160, 255), 6)
    p.poly([(36, 26), (64, 54), (54, 64), (26, 36)], fill=(230, 70, 70, 255), outline=(170, 40, 40, 255), width=3)
    p.ell((50, 10, 88, 48), fill=(240, 90, 90, 255), outline=(170, 40, 40, 255), width=3)
    p.ell((60, 18, 70, 28), fill=(255, 255, 255, 150))


def _exclaim(p, c):
    p.rect((42, 10, 58, 62), r=7, fill=c)
    p.ell((40, 72, 60, 92), fill=c)


def _globe(p, c):
    blue, edge = (96, 170, 236, 255), (50, 110, 186, 255)
    p.ell((8, 8, 92, 92), fill=blue, outline=edge, width=4)
    for pts in (((30, 24), (44, 20), (52, 30), (42, 40), (30, 36)), ((50, 56), (66, 50), (76, 62), (64, 78), (52, 72))):
        p.poly(list(pts), fill=(122, 200, 120, 255))
    p.arc((26, 8, 74, 92), 90, 270, (255, 255, 255, 150), 3)
    p.line([(8, 50), (92, 50)], (255, 255, 255, 120), 3, round_caps=False)


def _moon(p, c):
    p.ell((14, 10, 86, 82), fill=(255, 236, 160, 255), outline=(224, 190, 90, 255), width=3)
    p.ell((36, 2, 100, 68), fill=(0, 0, 0, 0))
    p.d.ellipse(p.box((36, 2, 100, 68)), fill=(0, 0, 0, 0))


def _lock_open(p, c):
    """打開的鎖（灰色）：沒有釘選。"""
    steel = (150, 156, 168, 255)
    p.arc((30, 4, 76, 58), 180, 340, steel, 9)
    p.line([(34, 31), (34, 46)], steel, 9, round_caps=False)
    p.gfill(lambda d, pen: d.rounded_rectangle(pen.box((18, 44, 82, 94)), radius=pen.u * 10, fill=255), (196, 200, 210, 255), (150, 156, 170, 255), 44, 94)
    p.rect((18, 44, 82, 94), r=10, outline=(112, 118, 132, 255), width=3)
    p.ell((44, 60, 56, 72), fill=(96, 102, 116, 255)); p.rect((48, 68, 52, 82), fill=(96, 102, 116, 255))


def _lock_closed(p, c):
    """鎖上的鎖（橘色）：釘選中。"""
    p.arc((26, 6, 74, 62), 180, 360, (214, 120, 40, 255), 9)
    p.line([(30, 34), (30, 48)], (214, 120, 40, 255), 9, round_caps=False)
    p.line([(70, 34), (70, 48)], (214, 120, 40, 255), 9, round_caps=False)
    p.gfill(lambda d, pen: d.rounded_rectangle(pen.box((16, 44, 84, 94)), radius=pen.u * 10, fill=255), (255, 188, 92, 255), (236, 128, 40, 255), 44, 94)
    p.rect((16, 44, 84, 94), r=10, outline=(158, 82, 28, 255), width=3)
    p.ell((44, 60, 56, 72), fill=(118, 58, 22, 255)); p.rect((48, 68, 52, 82), fill=(118, 58, 22, 255))
    p.rect((24, 50, 32, 84), r=3, fill=(255, 255, 255, 80))


ART = {
    "lock_open": _lock_open, "lock_closed": _lock_closed,
    "exclaim": _exclaim, "globe": _globe, "moon": _moon,
    "question": _question, "zed": _zed, "sunflower": _sunflower, "pin": _pin,
    "close": _close, "minus": _minus, "check": _check, "prev": _prev, "next": _next, "menu": _menu, "expand": _expand,
    "shrink": _shrink, "swap": _swap, "grip": _grip, "chevron": _chevron, "pencil": _pencil, "note": _note, "notes": _notes,
    "sparkle": _sparkle, "flower": _flower, "repeat": _repeat,
    "heart": _heart, "coin": _coin, "capsule": _capsule, "trophy": _trophy, "lock": _lock, "blank": _blank,
    "headphones": _headphones, "folder": _folder, "folder_open": _folder_open, "clock": _clock, "candy": _candy, "warn": _warn,
    "zzz": _zzz, "camera": _camera, "party": _party, "dice": _dice, "bento": _bento, "birthday": _birthday,
    "hand_paper": lambda p, c: _hand(p, "paper"), "hand_rock": lambda p, c: _hand(p, "rock"), "hand_scissors": lambda p, c: _hand(p, "scissors"),
    # 食物、玩具
    "飯糰": _onigiri, "白飯": _rice, "蛋糕": _cake_slice, "糰子": _dango, "甜甜圈": _donut, "草莓": _strawberry, "香蕉": _banana,
    "飲料": _drink, "熱茶": _tea, "足球": _soccer, "籃球": _basketball, "毛線球": _yarn,
}


def draw_icon(name, size, color=None):
    """畫一個 size×size 的小圖。單色圖示用 color（顏色字串 "#rrggbb" 或 (r, g, b)），沒給就是深褐色。"""
    p = _Pen(size)
    col = _rgba(color) if (name in MONO or color is not None) else None
    ART[name](p, _rgba(color) if name in MONO else (_rgba(color) if color is not None else None))
    return p.out(size)


_CACHE = {}


def icon_pil(name, size, color=None):
    key = (name, size, _rgba(color) if color is not None else None)
    if key not in _CACHE:
        _CACHE[key] = draw_icon(name, size, color)
    return _CACHE[key]
