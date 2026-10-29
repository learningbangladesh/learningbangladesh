"""Rebuild the Global Change Award 2027 banner as pure vector art.
All text is converted to outlines (glyph paths) - no live fonts in the output.
Design units: px of the 600x1600 reference; output scaled to 36in x 96in (3ft x 8ft).
"""
import math, sys, os
from fontTools.ttLib import TTFont
from fontTools.pens.recordingPen import RecordingPen
from reportlab.pdfgen import canvas
from reportlab.lib.colors import CMYKColor

HERE = os.path.dirname(os.path.abspath(__file__))
FD = os.path.join(HERE, 'fonts')
W, H = 600, 1600
SCALE = 36 * 72 / W            # 4.32 pt per design px -> 36in x 96in
BLEED = 0.25 * 72 / SCALE      # 0.25in bleed in design units

# colour: (rgb hex for SVG, cmyk 0-1 for print PDF)
COL = {
    'cream':  ('#fff8ee', (0, .03, .07, 0)),
    'navy':   ('#241e4e', (.95, .95, .30, .30)),
    'orange': ('#f37b0d', (0, .62, 1, 0)),
    'purple': ('#5c2163', (.68, 1, .25, .18)),
    'white':  ('#ffffff', (0, 0, 0, 0)),
}

# ---------------------------------------------------------------- geometry
# A path is a list of ('M',x,y) ('L',x,y) ('C',x1,y1,x2,y2,x,y) ('Z',)
def rect(x, y, w, h, r=0):
    if not r:
        return [('M', x, y), ('L', x + w, y), ('L', x + w, y + h), ('L', x, y + h), ('Z',)]
    k = 0.5523 * r
    return [('M', x + r, y), ('L', x + w - r, y), ('C', x + w - r + k, y, x + w, y + r - k, x + w, y + r),
            ('L', x + w, y + h - r), ('C', x + w, y + h - r + k, x + w - r + k, y + h, x + w - r, y + h),
            ('L', x + r, y + h), ('C', x + r - k, y + h, x, y + h - r + k, x, y + h - r),
            ('L', x, y + r), ('C', x, y + r - k, x + r - k, y, x + r, y), ('Z',)]

def circle(cx, cy, r):
    k = 0.5523 * r
    return [('M', cx + r, cy), ('C', cx + r, cy + k, cx + k, cy + r, cx, cy + r),
            ('C', cx - k, cy + r, cx - r, cy + k, cx - r, cy),
            ('C', cx - r, cy - k, cx - k, cy - r, cx, cy - r),
            ('C', cx + k, cy - r, cx + r, cy - k, cx + r, cy), ('Z',)]

def transform(path, fn):
    out = []
    for c in path:
        if c[0] == 'Z':
            out.append(c); continue
        pts = [fn(c[i], c[i + 1]) for i in range(1, len(c), 2)]
        out.append((c[0],) + tuple(v for p in pts for v in p))
    return out

def rotate(path, deg, cx, cy):
    a = math.radians(deg); ca, sa = math.cos(a), math.sin(a)
    return transform(path, lambda x, y: (cx + (x - cx) * ca - (y - cy) * sa, cy + (x - cx) * sa + (y - cy) * ca))

# ---------------------------------------------------------------- fonts -> outlines
_fonts = {}
def font(name):
    if name not in _fonts:
        _fonts[name] = TTFont(os.path.join(FD, name))
    return _fonts[name]

def text_width(s, fname, size, track=0):
    f = font(fname); upm = f['head'].unitsPerEm; cmap = f.getBestCmap(); hm = f['hmtx']
    return sum(hm[cmap[ord(ch)]][0] for ch in s) * size / upm + track * (len(s) - 1)

def text(s, fname, x, baseline, cap=None, size=None, track=0, anchor='start', width=None):
    """Outline a string. Size given directly or derived from the desired cap height (px)."""
    f = font(fname); upm = f['head'].unitsPerEm
    if width is not None:
        size = (width - track * (len(s) - 1)) / text_width(s, fname, 1)
    elif size is None:
        size = cap * upm / f['OS/2'].sCapHeight
    if anchor == 'middle':
        x -= text_width(s, fname, size, track) / 2
    elif anchor == 'end':
        x -= text_width(s, fname, size, track)
    gs = f.getGlyphSet(); cmap = f.getBestCmap(); sc = size / upm
    path = []
    for ch in s:
        gn = cmap[ord(ch)]
        pen = RecordingPen(); gs[gn].draw(pen)
        ox = x
        P = lambda px, py: (ox + px * sc, baseline - py * sc)
        cur = None
        for op, args in pen.value:
            if op == 'moveTo':
                cur = args[0]; path.append(('M',) + P(*cur))
            elif op == 'lineTo':
                cur = args[0]; path.append(('L',) + P(*cur))
            elif op == 'curveTo':
                for i in range(0, len(args), 3):
                    a, b, c = args[i:i + 3]
                    path.append(('C',) + P(*a) + P(*b) + P(*c)); cur = c
            elif op == 'qCurveTo':
                pts = list(args)
                if pts[-1] is None:  # closed contour of off-curve points only
                    pts = pts[:-1]
                    start = ((pts[-1][0] + pts[0][0]) / 2, (pts[-1][1] + pts[0][1]) / 2)
                    path.append(('M',) + P(*start)); cur = start; pts = pts + [start]
                for i in range(len(pts) - 1):
                    q = pts[i]
                    end = pts[i + 1] if i == len(pts) - 2 else ((q[0] + pts[i + 1][0]) / 2, (q[1] + pts[i + 1][1]) / 2)
                    c1 = (cur[0] + 2 / 3 * (q[0] - cur[0]), cur[1] + 2 / 3 * (q[1] - cur[1]))
                    c2 = (end[0] + 2 / 3 * (q[0] - end[0]), end[1] + 2 / 3 * (q[1] - end[1]))
                    path.append(('C',) + P(*c1) + P(*c2) + P(*end)); cur = end
            elif op in ('closePath', 'endPath'):
                path.append(('Z',))
        x += f['hmtx'][gn][0] * sc + track
    return path

# ---------------------------------------------------------------- scene
scene = []   # (layer_name, path, fill or None, stroke or None, stroke_width)
def add(name, path, fill=None, stroke=None, sw=0):
    scene.append((name, path, fill, stroke, sw))

def line(x1, y1, x2, y2):
    return [('M', x1, y1), ('L', x2, y2)]

b = BLEED
# background
add('Background', rect(-b, -b, W + 2 * b, H + 2 * b), 'cream')

# header logos (redrawn approximations - replace with official vector logos)
add('Logo H&M Foundation', text('H&M FOUNDATION', 'Kalam-Regular.ttf', 50, 126, width=250, track=-1), 'navy')
add('Logo divider', line(320, 72, 320, 150), None, 'navy', 2.5)
star = []
for i in range(12):
    star += rotate(rect(362.5, 85, 6, 16, 3), i * 30, 365.5, 108)
add('Logo CARE mark', star + circle(365.5, 108, 8), 'orange')
add('Logo CARE wordmark', text('care', 'Poppins-ExtraBold.ttf', 396, 128, width=120, track=-1), 'orange')

# decorative dashes
for x1, y1, x2, y2 in [(413, 196, 429, 180), (387, 233, 414, 225), (349, 748, 364, 728), (359, 778, 386, 768)]:
    add('Accent dash', line(x1, y1, x2, y2), None, 'orange', 4)

# bulb badge
add('Bulb circle', circle(492, 262, 62), 'navy')
bulb = [('M', 482, 275), ('C', 482, 266, 472, 262, 472, 250), ('C', 472, 238, 481, 230, 492, 230),
        ('C', 503, 230, 512, 238, 512, 250), ('C', 512, 262, 502, 266, 502, 275), ('Z',)]
add('Bulb icon', bulb, None, 'white', 3.2)
add('Bulb icon', line(483, 282, 501, 282) + line(486, 289, 498, 289), None, 'white', 3.2)

# right-side shapes
add('Purple circle', circle(622, 712, 96), 'purple')
add('Orange ring', circle(597, 620, 39), None, 'orange', 3)

# headline
add('Headline The', text('The', 'Anton-Regular.ttf', 49, 358, cap=53), 'navy')
for word, top, bot in [('GLOBAL', 370, 472), ('CHANGE', 485, 588), ('AWARD', 600, 700)]:
    add('Headline ' + word, text(word, 'Anton-Regular.ttf', 47, bot, cap=bot - top, track=1), 'navy')
add('Headline 2027', text('2027', 'Anton-Regular.ttf', 47, 835, cap=120, track=1), 'orange')

# rotated orange tag with navy shadow
TAG_ROT, TCX, TCY = -1.6, 287, 935
add('Tag shadow', rotate(rect(57, 873, 472, 128, 6), TAG_ROT, TCX + 7, TCY + 7), 'navy')
add('Tag', rotate(rect(50, 866, 472, 128, 6), TAG_ROT, TCX, TCY), 'orange')
add('Tag text', rotate(text('Bangladesh', 'Poppins-Bold.ttf', 78, 925, width=257), TAG_ROT, TCX, TCY)
    + rotate(text('Nominee Selection', 'Poppins-Bold.ttf', 78, 975, width=417), TAG_ROT, TCX, TCY), 'white')

# subtitle
add('Subtitle', text('Final Presentation &', 'Poppins-SemiBold.ttf', 50, 1058, width=326), 'navy')
add('Subtitle', text('Jury Evaluation', 'Poppins-SemiBold.ttf', 50, 1098, width=250), 'orange')

# date block
add('Date box', rect(50, 1124, 500, 116, 8), 'navy')
add('Date 31', text('31', 'Anton-Regular.ttf', 79, 1224, cap=84), 'white')
add('Date month', text('OCTOBER', 'Anton-Regular.ttf', 183, 1185, cap=45, track=1), 'white')
add('Date year', text('2026', 'Poppins-Bold.ttf', 183, 1222, width=81, track=1), 'orange')

# venue pill
add('Venue pill', rect(51, 1258, 498, 55, 27.5), 'cream', 'navy', 2)
pin = [('M', 85, 1297), ('C', 85, 1297, 76, 1287, 76, 1280), ('C', 76, 1275, 80, 1271, 85, 1271),
       ('C', 90, 1271, 94, 1275, 94, 1280), ('C', 94, 1287, 85, 1297, 85, 1297), ('Z',)]
add('Venue pin', pin, 'orange')
add('Venue pin dot', circle(85, 1280, 3.2), 'cream')
add('Venue text', text('CARE Bangladesh Country Office, Dhaka', 'Poppins-SemiBold.ttf', 112, 1291, width=380), 'navy')

# footer waves
wave = [('M', -b, 1335), ('C', 120, 1318, 260, 1350, 400, 1336), ('C', 480, 1328, 540, 1322, W + b, 1326),
        ('L', W + b, H + b), ('L', -b, H + b), ('Z',)]
add('Footer navy', wave, 'navy')
add('Footer purple', rect(528, 1310, 100, 90, 22), 'purple')
add('Footer orange circle', circle(606, 1362, 34), 'orange')
add('Footer line', [('M', -b, 1532), ('C', 150, 1505, 300, 1540, 450, 1515), ('C', 520, 1503, 570, 1508, W + b, 1505)], None, 'orange', 1.5)
add('Footer line', [('M', -b, 1556), ('C', 180, 1535, 330, 1565, 470, 1545), ('C', 540, 1535, 580, 1540, W + b, 1537)], None, 'purple', 1.5)

# organizer card
add('Card shadow', rect(58, 1353, 500, 155, 12), 'orange')
add('Card', rect(50, 1345, 500, 155, 12), 'white')
add('Card label', text('ORGANIZED BY', 'Poppins-SemiBold.ttf', 300, 1379, width=152, track=3.2, anchor='middle'), 'purple')
add('Card title', text('CARE Bangladesh', 'Anton-Regular.ttf', 300, 1437, cap=46, track=0.5, anchor='middle'), 'orange')
add('Card pill', rect(115, 1450, 370, 29, 14.5), 'orange')
add('Card pill text', text('Official Nominator', 'Poppins-SemiBold.ttf', 131, 1469.5, width=131)
    + text('Global Change Award 2027', 'Poppins-SemiBold.ttf', 275, 1469.5, width=194)
    + circle(268.5, 1465.5, 1.25), 'white')

# ---------------------------------------------------------------- writers
def svg_d(path):
    out = []
    for c in path:
        out.append(c[0] + ' '.join('%.2f' % v for v in c[1:]))
    return ''.join(out)

def write_svg(fn):
    vb = '%.2f %.2f %.2f %.2f' % (-b, -b, W + 2 * b, H + 2 * b)
    o = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="%s" width="%.0fpt" height="%.0fpt">' % (vb, (W + 2 * b) * SCALE, (H + 2 * b) * SCALE)]
    for name, p, fill, stroke, sw in scene:
        a = 'fill="%s"' % (COL[fill][0] if fill else 'none')
        if stroke:
            a += ' stroke="%s" stroke-width="%s" stroke-linecap="round" stroke-linejoin="round"' % (COL[stroke][0], sw)
        o.append('<path id="%s" fill-rule="nonzero" %s d="%s"/>' % (name.replace(' ', '_'), a, svg_d(p)))
    o.append('</svg>')
    open(fn, 'w').write('\n'.join(o))

def write_pdf(fn, title):
    pw, ph = (W + 2 * b) * SCALE, (H + 2 * b) * SCALE
    c = canvas.Canvas(fn, pagesize=(pw, ph))
    c.setTitle(title); c.setAuthor('CARE Bangladesh'); c.setSubject('Print-ready, all text outlined')
    bl = b * SCALE
    c.setTrimBox((bl, bl, pw - bl, ph - bl))
    c.setBleedBox((0, 0, pw, ph))
    tx = lambda x, y: ((x + b) * SCALE, ph - (y + b) * SCALE)
    for name, p, fill, stroke, sw in scene:
        pa = c.beginPath()
        for cmd in p:
            if cmd[0] == 'M': pa.moveTo(*tx(*cmd[1:3]))
            elif cmd[0] == 'L': pa.lineTo(*tx(*cmd[1:3]))
            elif cmd[0] == 'C': pa.curveTo(*tx(*cmd[1:3]), *tx(*cmd[3:5]), *tx(*cmd[5:7]))
            else: pa.close()
        if fill: c.setFillColor(CMYKColor(*COL[fill][1]))
        if stroke:
            c.setStrokeColor(CMYKColor(*COL[stroke][1])); c.setLineWidth(sw * SCALE)
            c.setLineCap(1); c.setLineJoin(1)
        c.drawPath(pa, fill=1 if fill else 0, stroke=1 if stroke else 0, fillMode=1)  # nonzero winding
    c.showPage(); c.save()

if __name__ == '__main__':
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    base = os.path.join(out, 'Global_Change_Award_2027_Banner_3x8ft_Outlined')
    write_svg(base + '.svg')
    write_pdf(base + '.pdf', 'Global Change Award 2027 - Bangladesh Nominee Selection')
    write_pdf(base + '.ai', 'Global Change Award 2027 - Bangladesh Nominee Selection')
    print('ok', base)
