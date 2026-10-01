"""Sample swatches for the photo/illustration formats: one synthetic scene, five treatments.
Run by `make previews`. Writes static/previews/photo-<style>.png."""
import math, random
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageOps, ImageEnhance

OUT = Path(__file__).resolve().parent.parent / "static" / "previews"
W, H = 480, 360
random.seed(7)


def scene():
    im = Image.new("RGB", (W, H), (178, 196, 210))
    d = ImageDraw.Draw(im)
    for y in range(H // 2):                                  # sky gradient
        t = y / (H / 2)
        d.line([(0, y), (W, y)], fill=(int(150 + 60 * t), int(180 + 40 * t), int(210 + 20 * t)))
    d.polygon([(0, 200), (120, 120), (230, 190), (330, 110), (480, 190), (480, 360), (0, 360)], fill=(92, 112, 96))
    d.rectangle([0, 250, W, H], fill=(70, 96, 120))         # lake
    for i in range(0, W, 9):
        d.line([(i, 262 + 4 * math.sin(i / 17)), (i + 5, 262 + 4 * math.sin(i / 17))], fill=(140, 170, 190))
    d.rectangle([300, 200, 380, 255], fill=(120, 72, 48))   # cabin
    d.polygon([(292, 202), (340, 165), (388, 202)], fill=(80, 50, 36))
    d.rectangle([330, 225, 348, 255], fill=(50, 34, 26))
    for x in (60, 95, 130, 420):                              # pines
        d.polygon([(x, 250), (x - 18, 250), (x - 9, 175)], fill=(38, 64, 44))
    d.ellipse([180, 205, 205, 230], fill=(60, 40, 34))       # a figure
    d.rectangle([186, 228, 200, 262], fill=(60, 40, 34))
    return im


def grain(im, amount):
    noise = Image.effect_noise(im.size, amount).convert("L")
    return Image.blend(im.convert("L"), noise, 0.12).convert("RGB")


def tintype(im):
    g = ImageOps.colorize(ImageOps.grayscale(im).filter(ImageFilter.GaussianBlur(1.2)), (24, 20, 16), (205, 196, 170))
    g = ImageEnhance.Contrast(g).enhance(1.25)
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([18, 18, W - 18, H - 18], 40, fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(14))
    return Image.composite(g, Image.new("RGB", im.size, (30, 26, 22)), mask)


def silver(im):
    return ImageEnhance.Contrast(grain(ImageOps.grayscale(im).convert("RGB"), 40)).enhance(1.15)


def kodachrome(im):
    k = ImageEnhance.Color(im).enhance(1.5)
    r, g, b = k.split()
    return Image.merge("RGB", (r.point(lambda v: min(255, v + 18)), g.point(lambda v: min(255, v + 6)), b.point(lambda v: max(0, v - 12))))


def polaroid(im):
    sq = ImageOps.fit(im, (300, 300))
    r, g, b = ImageEnhance.Contrast(sq).enhance(0.85).split()
    sq = Image.merge("RGB", (r.point(lambda v: max(0, v - 10)), g, b.point(lambda v: min(255, v + 14))))
    frame = Image.new("RGB", (W, H), (236, 232, 222))
    card = Image.new("RGB", (330, 356 - 10), (250, 248, 242))
    card.paste(sq, (15, 15))
    frame.paste(card, ((W - 330) // 2, 6))
    return frame


def line(im):
    edges = ImageOps.grayscale(im).filter(ImageFilter.FIND_EDGES)
    edges = ImageOps.invert(ImageEnhance.Contrast(edges).enhance(4))
    return ImageOps.colorize(edges, (30, 28, 25), (248, 244, 234))


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    base = scene()
    for name, fn in (("tintype", tintype), ("silver", silver), ("kodachrome", kodachrome), ("polaroid", polaroid), ("line", line)):
        fn(base).save(OUT / f"photo-{name}.png", optimize=True)
        print("photo-" + name)
