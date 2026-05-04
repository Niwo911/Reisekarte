"""
Erzeugt 7 Demo-JPGs mit eingebetteten GPS-EXIF-Daten in ../fotos/.

Wird einmalig ausgeführt; die fertigen .jpg-Dateien werden im Repo committed.
End-User benötigen dieses Skript nicht zur Laufzeit.

Aufruf (aus dem Repo-Root):
    pip install Pillow piexif
    python tools/generate_demo_fotos.py
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import piexif
from PIL import Image, ImageDraw, ImageFont


# (Datei-Stem, Anzeigename, Land, Lat, Lon, Tag-Offset (0..2), Stunden-Offset, (Top, Bottom)-Farbe)
LOCATIONS = [
    ("01_brandenburger_tor", "Brandenburger Tor", "Berlin · Deutschland",   52.5163, 13.3777, 0,  9, ((25, 35, 60),  (90, 70, 110))),
    ("02_markusplatz",       "Markusplatz",       "Venedig · Italien",      45.4341, 12.3388, 0, 12, ((30, 70, 110), (200, 150, 90))),
    ("03_kolosseum",         "Kolosseum",         "Rom · Italien",          41.8902, 12.4922, 0, 16, ((90, 50, 30),  (180, 130, 70))),
    ("04_akropolis",         "Akropolis",         "Athen · Griechenland",   37.9715, 23.7267, 1, 10, ((40, 90, 130), (220, 200, 160))),
    ("05_sagrada_familia",   "Sagrada Família",   "Barcelona · Spanien",    41.4036,  2.1744, 1, 15, ((60, 40, 90),  (220, 130, 80))),
    ("06_eiffelturm",        "Eiffelturm",        "Paris · Frankreich",     48.8584,  2.2945, 2, 11, ((20, 30, 60),  (160, 120, 200))),
    ("07_big_ben",           "Big Ben",           "London · Großbritannien", 51.5007, -0.1246, 2, 17, ((30, 40, 70),  (90, 110, 140))),
]

BASE_DATE = datetime(2025, 6, 12)


def _to_dms_rational(value: float) -> tuple:
    """Dezimalgrad → EXIF-DMS-Rational ((d,1),(m,1),(s,100))."""
    abs_val = abs(value)
    deg = int(abs_val)
    min_full = (abs_val - deg) * 60
    minutes = int(min_full)
    seconds = round((min_full - minutes) * 60 * 100)
    return ((deg, 1), (minutes, 1), (seconds, 100))


def build_gps_ifd(lat: float, lon: float, ts: datetime, alt: float = 50.0) -> dict:
    return {
        piexif.GPSIFD.GPSVersionID: (2, 0, 0, 0),
        piexif.GPSIFD.GPSLatitudeRef: b"N" if lat >= 0 else b"S",
        piexif.GPSIFD.GPSLatitude: _to_dms_rational(lat),
        piexif.GPSIFD.GPSLongitudeRef: b"E" if lon >= 0 else b"W",
        piexif.GPSIFD.GPSLongitude: _to_dms_rational(lon),
        piexif.GPSIFD.GPSAltitudeRef: 0,
        piexif.GPSIFD.GPSAltitude: (int(alt * 100), 100),
        piexif.GPSIFD.GPSDateStamp: ts.strftime("%Y:%m:%d").encode("ascii"),
        piexif.GPSIFD.GPSTimeStamp: ((ts.hour, 1), (ts.minute, 1), (ts.second, 1)),
    }


def vertical_gradient(size: tuple[int, int], top, bottom) -> Image.Image:
    w, h = size
    img = Image.new("RGB", size, top)
    draw = ImageDraw.Draw(img)
    for y in range(h):
        t = y / max(1, h - 1)
        r = int(top[0] * (1 - t) + bottom[0] * t)
        g = int(top[1] * (1 - t) + bottom[1] * t)
        b = int(top[2] * (1 - t) + bottom[2] * t)
        draw.line([(0, y), (w, y)], fill=(r, g, b))
    return img


def _try_font(candidates: list[str], size: int):
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


SERIF_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Times New Roman Bold Italic.ttf",
    "/System/Library/Fonts/Supplemental/Georgia Bold.ttf",
    "/System/Library/Fonts/NewYork.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif-BoldItalic.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSerif-BoldItalic.ttf",
    "C:/Windows/Fonts/timesbi.ttf",
]
SANS_CANDIDATES = [
    "/System/Library/Fonts/HelveticaNeue.ttc",
    "/System/Library/Fonts/Supplemental/Futura.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "C:/Windows/Fonts/arial.ttf",
]


def render_demo_image(name: str, country: str, top, bottom, size=(1200, 800)) -> Image.Image:
    img = vertical_gradient(size, top, bottom)
    w, h = size

    # Diagonale Texturlinien
    overlay = Image.new("RGBA", size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    for i in range(0, w + h, 22):
        od.line([(i, 0), (i - h, h)], fill=(255, 255, 255, 9), width=1)
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    # Vignette
    vignette = Image.new("RGBA", size, (0, 0, 0, 0))
    vd = ImageDraw.Draw(vignette)
    for layer in range(22):
        alpha = layer * 4
        inset = layer * 14
        vd.rectangle((inset, inset, w - inset, h - inset), outline=(0, 0, 0, alpha))
    img = Image.alpha_composite(img.convert("RGBA"), vignette).convert("RGB")

    draw = ImageDraw.Draw(img)
    big = _try_font(SERIF_CANDIDATES, 92)
    small = _try_font(SANS_CANDIDATES, 26)
    tiny = _try_font(SANS_CANDIDATES, 16)

    bbox = draw.textbbox((0, 0), name, font=big)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    cx, cy = w / 2, h / 2 - 30
    draw.text((cx - tw / 2 + 3, cy - th / 2 + 3), name, font=big, fill=(0, 0, 0))
    draw.text((cx - tw / 2,     cy - th / 2),     name, font=big, fill=(255, 235, 200))

    draw.line([(cx - 60, cy + th / 2 + 16), (cx + 60, cy + th / 2 + 16)], fill=(245, 196, 105), width=2)

    bbox2 = draw.textbbox((0, 0), country, font=small)
    sw = bbox2[2] - bbox2[0]
    draw.text((cx - sw / 2, cy + th / 2 + 32), country, font=small, fill=(255, 255, 255))

    demo_txt = "DEMO · Reisekarte"
    bbox3 = draw.textbbox((0, 0), demo_txt, font=tiny)
    dw = bbox3[2] - bbox3[0]
    draw.text((w - dw - 30, h - 35), demo_txt, font=tiny, fill=(220, 220, 220))

    return img


def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    out_dir = repo_root / "fotos"
    out_dir.mkdir(parents=True, exist_ok=True)

    for stem, name, country, lat, lon, day_offset, hour, (top, bottom) in LOCATIONS:
        ts = BASE_DATE + timedelta(days=day_offset, hours=hour)

        img = render_demo_image(name, country, top, bottom)

        zeroth_ifd = {
            piexif.ImageIFD.Make: b"Reisekarte Demo",
            piexif.ImageIFD.Model: b"Synthetic",
            piexif.ImageIFD.Software: b"Reisekarte demo generator",
            piexif.ImageIFD.DateTime: ts.strftime("%Y:%m:%d %H:%M:%S").encode("ascii"),
        }
        exif_ifd = {
            piexif.ExifIFD.DateTimeOriginal:  ts.strftime("%Y:%m:%d %H:%M:%S").encode("ascii"),
            piexif.ExifIFD.DateTimeDigitized: ts.strftime("%Y:%m:%d %H:%M:%S").encode("ascii"),
        }
        gps_ifd = build_gps_ifd(lat, lon, ts)

        exif_bytes = piexif.dump({
            "0th": zeroth_ifd, "Exif": exif_ifd, "GPS": gps_ifd, "1st": {}, "thumbnail": None,
        })

        out_path = out_dir / f"{stem}.jpg"
        img.save(out_path, "JPEG", quality=85, optimize=True, exif=exif_bytes)
        print(f"  ✓ {out_path.name}  ({lat:+.4f}, {lon:+.4f})  @ {ts:%Y-%m-%d %H:%M}")

    print(f"\n{len(LOCATIONS)} Demo-Bilder erzeugt in {out_dir}")


if __name__ == "__main__":
    main()
