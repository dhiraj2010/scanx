# Draws the ScanX launcher icon and splash straight into the Android project (run by the GitHub build after `cap add android`).
import glob, os
from PIL import Image, ImageDraw
RES = 'android/app/src/main/res'

def mark(size, pad_ratio):
    im = Image.new('RGBA', (size, size), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    p = int(size * pad_ratio); w = size - 2 * p
    bars = [0.35, 0.55, 0.45, 0.75, 1.0]; gap = w / len(bars); bw = gap * 0.55; base = p + w * 0.86
    for i, b in enumerate(bars):
        x = p + i * gap + (gap - bw) / 2; h = w * 0.62 * b
        d.rounded_rectangle([x, base - h, x + bw, base], radius=bw * 0.25, fill=(255, 210, 63, 255) if i == 4 else (255, 255, 255, 255))
    pts = [(p + w * 0.04, p + w * 0.62), (p + w * 0.3, p + w * 0.42), (p + w * 0.5, p + w * 0.5), (p + w * 0.72, p + w * 0.26), (p + w * 0.96, p + w * 0.1)]
    d.line(pts, fill=(255, 210, 63, 255), width=max(2, int(size * 0.035)), joint='curve')
    return im

def grad(size):
    g = Image.new('RGBA', (size, size)); gd = ImageDraw.Draw(g)
    for y in range(size):
        gd.line([(0, y), (size, y)], fill=(int(20 + 11 * y / size), int(40 + 39 * y / size), int(150 + 59 * y / size), 255))
    return g

S = 1024
legacy = Image.new('RGBA', (S, S), (0, 0, 0, 0)); m = Image.new('L', (S, S), 0); ImageDraw.Draw(m).rounded_rectangle([0, 0, S, S], radius=220, fill=255)
legacy.paste(grad(S), (0, 0), m); legacy.alpha_composite(mark(S, 0.2))
roundi = Image.new('RGBA', (S, S), (0, 0, 0, 0)); m2 = Image.new('L', (S, S), 0); ImageDraw.Draw(m2).ellipse([0, 0, S, S], fill=255)
roundi.paste(grad(S), (0, 0), m2); roundi.alpha_composite(mark(S, 0.24))
fg = mark(S, 0.12)  # the adaptive icon already insets it by 16.7%
for f in glob.glob(f'{RES}/mipmap-*/ic_launcher.png'):
    n = Image.open(f).size[0]; legacy.resize((n, n), Image.LANCZOS).save(f)
for f in glob.glob(f'{RES}/mipmap-*/ic_launcher_round.png'):
    n = Image.open(f).size[0]; roundi.resize((n, n), Image.LANCZOS).save(f)
for f in glob.glob(f'{RES}/mipmap-*/ic_launcher_foreground.png'):
    n = Image.open(f).size[0]; fg.resize((n, n), Image.LANCZOS).save(f)
for f in glob.glob(f'{RES}/mipmap-*/ic_launcher_background.png'):
    n = Image.open(f).size[0]; grad(S).resize((n, n), Image.LANCZOS).save(f)
bgxml = f'{RES}/values/ic_launcher_background.xml'
if os.path.exists(bgxml):
    open(bgxml, 'w').write('<?xml version="1.0" encoding="utf-8"?>\n<resources>\n    <color name="ic_launcher_background">#1F4FD1</color>\n</resources>\n')
for f in glob.glob(f'{RES}/drawable*/splash.png'):
    w, h = Image.open(f).size; night = 'night' in f
    sp = Image.new('RGB', (w, h), (12, 18, 25) if night else (242, 244, 247)); k = int(min(w, h) * 0.28)
    ic = legacy.resize((k, k), Image.LANCZOS); sp.paste(ic, ((w - k) // 2, (h - k) // 2), ic); sp.save(f)
print('icons and splash written')
