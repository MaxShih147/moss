from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).parent
ACCENT = (44, 62, 80)
WHITE = (255, 255, 255)


def make_color(size=192):
    img = Image.new("RGBA", (size, size), ACCENT)
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", int(size * 0.55))
    except Exception:
        font = ImageFont.load_default()
    text = "D"
    bbox = d.textbbox((0, 0), text, font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    d.text(((size - w) / 2 - bbox[0], (size - h) / 2 - bbox[1]), text, fill=WHITE, font=font)
    img.save(OUT / "color.png")


def make_outline(size=32):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", int(size * 0.75))
    except Exception:
        font = ImageFont.load_default()
    text = "D"
    bbox = d.textbbox((0, 0), text, font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    d.text(((size - w) / 2 - bbox[0], (size - h) / 2 - bbox[1]), text, fill=WHITE, font=font)
    img.save(OUT / "outline.png")


if __name__ == "__main__":
    make_color()
    make_outline()
    print(f"icons written to {OUT}")
