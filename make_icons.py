# Generates the ScanX app icon and splash images into assets/ (run by the GitHub build).
import os
from PIL import Image, ImageDraw
os.makedirs('assets', exist_ok=True)
S = 1024
def fg(size, pad_ratio):
    im = Image.new('RGBA', (size, size), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    p = int(size * pad_ratio); w = size - 2 * p
    bars = [0.35, 0.55, 0.45, 0.75, 1.0]; gap = w / len(bars); bw = gap * 0.55; base = p + w * 0.86
    for i, b in enumerate(bars):
        x = p + i * gap + (gap - bw) / 2; h = w * 0.62 * b
        d.rounded_rectangle([x, base - h, x + bw, base], radius=bw * 0.25, fill=(255, 210, 63, 255) if i == 4 else (255, 255, 255, 255))
    pts = [(p + w * 0.04, p + w * 0.62), (p + w * 0.3, p + w * 0.42), (p + w * 0.5, p + w * 0.5), (p + w * 0.72, p + w * 0.26), (p + w * 0.96, p + w * 0.1)]
    d.line(pts, fill=(255, 210, 63, 255), width=int(size * 0.035), joint='curve')
    return im
grad = Image.new('RGBA', (S, S)); gd = ImageDraw.Draw(grad)
for y in range(S):
    gd.line([(0, y), (S, y)], fill=(int(20 + 11 * y / S), int(40 + 39 * y / S), int(150 + 59 * y / S), 255))
mask = Image.new('L', (S, S), 0); ImageDraw.Draw(mask).rounded_rectangle([0, 0, S, S], radius=220, fill=255)
icon = Image.new('RGBA', (S, S), (0, 0, 0, 0)); icon.paste(grad, (0, 0), mask); icon.alpha_composite(fg(S, 0.2))
icon.save('assets/icon-only.png'); fg(S, 0.3).save('assets/icon-foreground.png'); grad.save('assets/icon-background.png')
for name, bg in (('splash.png', (242, 244, 247, 255)), ('splash-dark.png', (12, 18, 25, 255))):
    sp = Image.new('RGBA', (2732, 2732), bg); sp.alpha_composite(icon.resize((600, 600)), (1066, 1066)); sp.convert('RGB').save('assets/' + name)
print('icons ready')
