#!/usr/bin/env python3
"""Generate deterministic equirectangular and domemaster calibration charts."""

from functools import lru_cache
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


FULL_WIDTH = 4096
FULL_HEIGHT = 2048
DOME_SIZE = 2048
OUTPUT_DIR = Path(__file__).resolve().parent

BACKGROUND_A = (11, 20, 34)
BACKGROUND_B = (16, 28, 45)
MINOR_GRID = (62, 81, 103)
MAJOR_GRID = (104, 129, 154)
EQUATOR = (245, 245, 245)
PRIME_MERIDIAN = (255, 220, 50)
HEMISPHERE_EDGE = (30, 225, 235)
SEAM = (255, 65, 75)
RING = (255, 145, 35)
SPOKE = (90, 225, 115)
TEXT = (245, 248, 252)


@lru_cache(maxsize=None)
def get_font(size, bold=False):
    names = (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
    ) if bold else (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    )
    for name in names:
        try:
            return ImageFont.truetype(name, size=size)
        except OSError:
            pass
    return ImageFont.load_default()


def add_label(draw, xy, text, size=34, fill=TEXT, anchor="mm", bold=False,
              background=(3, 7, 12), padding=9):
    font = get_font(size, bold)
    bbox = draw.multiline_textbbox(
        xy, text, font=font, anchor=anchor, align="center", stroke_width=1,
    )
    box = (
        bbox[0] - padding,
        bbox[1] - padding,
        bbox[2] + padding,
        bbox[3] + padding,
    )
    draw.rounded_rectangle(box, radius=padding, fill=background)
    draw.multiline_text(
        xy,
        text,
        font=font,
        fill=fill,
        anchor=anchor,
        align="center",
        stroke_width=1,
        stroke_fill=(0, 0, 0),
    )


def lon_to_x(lon_deg, width=FULL_WIDTH):
    return min(width - 1, max(0, round((lon_deg / 360.0 + 0.5) * width)))


def lat_to_y(lat_deg, height=FULL_HEIGHT):
    return min(height - 1, max(0, round((0.5 - lat_deg / 180.0) * height)))


def direction_to_erp(x, y, z):
    lon = math.degrees(math.atan2(x, z))
    lat = math.degrees(math.asin(max(-1.0, min(1.0, y))))
    return lon_to_x(lon), lat_to_y(lat)


def angular_ring_points(theta_deg, samples=1440):
    theta = math.radians(theta_deg)
    sin_theta = math.sin(theta)
    cos_theta = math.cos(theta)
    points = []
    for index in range(samples + 1):
        bearing = 2.0 * math.pi * index / samples
        x = sin_theta * math.cos(bearing)
        y = -sin_theta * math.sin(bearing)
        z = cos_theta
        points.append(direction_to_erp(x, y, z))
    return points


def angular_spoke_points(bearing_deg, samples=360):
    bearing = math.radians(bearing_deg)
    points = []
    for index in range(samples + 1):
        theta = math.radians(90.0 * index / samples)
        x = math.sin(theta) * math.cos(bearing)
        y = -math.sin(theta) * math.sin(bearing)
        z = math.cos(theta)
        points.append(direction_to_erp(x, y, z))
    return points


def make_erp_chart():
    image = Image.new("RGB", (FULL_WIDTH, FULL_HEIGHT), BACKGROUND_A)
    draw = ImageDraw.Draw(image)

    # Alternating angular bands make mirroring and large-scale warping obvious.
    for index, lon in enumerate(range(-180, 180, 15)):
        if index % 2:
            draw.rectangle(
                (lon_to_x(lon), 0, lon_to_x(lon + 15), FULL_HEIGHT - 1),
                fill=BACKGROUND_B,
            )
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    for index, lat in enumerate(range(-90, 90, 15)):
        if index % 2:
            overlay_draw.rectangle(
                (0, lat_to_y(lat + 15), FULL_WIDTH - 1, lat_to_y(lat)),
                fill=(35, 62, 78, 35),
            )
    image = Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(image)

    for lon in range(-180, 181, 15):
        x = lon_to_x(lon)
        major = lon % 30 == 0
        draw.line(
            (x, 0, x, FULL_HEIGHT - 1),
            fill=MAJOR_GRID if major else MINOR_GRID,
            width=3 if major else 1,
        )
    for lat in range(-90, 91, 15):
        y = lat_to_y(lat)
        major = lat % 30 == 0
        draw.line(
            (0, y, FULL_WIDTH - 1, y),
            fill=MAJOR_GRID if major else MINOR_GRID,
            width=3 if major else 1,
        )

    # Orange constant-angle rings become equally spaced circles in an
    # equidistant domemaster. Green curves become straight radial spokes.
    for theta in range(15, 90, 15):
        draw.line(angular_ring_points(theta), fill=RING, width=5, joint="curve")
    for bearing in range(0, 360, 30):
        draw.line(angular_spoke_points(bearing), fill=SPOKE, width=4, joint="curve")

    left = lon_to_x(-90)
    right = lon_to_x(90)
    draw.rectangle(
        (left, 0, right, FULL_HEIGHT - 1),
        outline=HEMISPHERE_EDGE,
        width=9,
    )
    draw.line(
        (lon_to_x(0), 0, lon_to_x(0), FULL_HEIGHT - 1),
        fill=PRIME_MERIDIAN,
        width=8,
    )
    draw.line(
        (0, lat_to_y(0), FULL_WIDTH - 1, lat_to_y(0)),
        fill=EQUATOR,
        width=7,
    )
    draw.line((0, 0, 0, FULL_HEIGHT - 1), fill=SEAM, width=12)
    draw.line(
        (FULL_WIDTH - 1, 0, FULL_WIDTH - 1, FULL_HEIGHT - 1),
        fill=SEAM,
        width=12,
    )

    # Numeric coordinates are placed just below/right of the main axes.
    for lon in range(-150, 151, 30):
        add_label(
            draw,
            (lon_to_x(lon), lat_to_y(0) + 52),
            f"{lon:+d}°",
            size=24,
            fill=PRIME_MERIDIAN if lon == 0 else TEXT,
            padding=5,
        )
    for lat in range(-60, 61, 30):
        if lat == 0:
            continue
        add_label(
            draw,
            (lon_to_x(0) + 62, lat_to_y(lat)),
            f"{lat:+d}°",
            size=24,
            padding=5,
        )

    add_label(
        draw,
        (FULL_WIDTH // 8, 65),
        "FULL ERP  360° × 180°\n4096 × 2048",
        size=34,
        bold=True,
    )
    add_label(
        draw,
        (FULL_WIDTH // 2, 65),
        "CENTER HEMISPHERE  180° × 180°\nCYAN BOUNDARY",
        size=34,
        fill=HEMISPHERE_EDGE,
        bold=True,
    )
    add_label(
        draw,
        (FULL_WIDTH // 2, FULL_HEIGHT // 2 - 70),
        "FORWARD\n0° LON / 0° LAT",
        size=31,
        fill=PRIME_MERIDIAN,
        bold=True,
    )
    add_label(
        draw,
        (left + 135, FULL_HEIGHT // 2 - 70),
        "LEFT RIM\n−90° LON",
        size=28,
        fill=HEMISPHERE_EDGE,
        bold=True,
    )
    add_label(
        draw,
        (right - 135, FULL_HEIGHT // 2 - 70),
        "RIGHT RIM\n+90° LON",
        size=28,
        fill=HEMISPHERE_EDGE,
        bold=True,
    )
    add_label(
        draw,
        (FULL_WIDTH // 2 + 185, 145),
        "ZENITH  +90° LAT",
        size=27,
        fill=HEMISPHERE_EDGE,
        bold=True,
    )
    add_label(
        draw,
        (FULL_WIDTH // 2 + 185, FULL_HEIGHT - 145),
        "NADIR  −90° LAT",
        size=27,
        fill=HEMISPHERE_EDGE,
        bold=True,
    )
    add_label(
        draw,
        (145, FULL_HEIGHT // 2 - 70),
        "BACK / SEAM\n−180°",
        size=27,
        fill=SEAM,
        bold=True,
    )
    add_label(
        draw,
        (FULL_WIDTH - 145, FULL_HEIGHT // 2 - 70),
        "BACK / SEAM\n+180°",
        size=27,
        fill=SEAM,
        bold=True,
    )
    add_label(
        draw,
        (FULL_WIDTH // 2, FULL_HEIGHT - 65),
        "ORANGE = 15° ANGULAR RINGS     GREEN = 30° BEARING SPOKES",
        size=26,
        fill=TEXT,
        bold=True,
    )
    return image


def make_domemaster_reference():
    size = DOME_SIZE
    center = (size - 1) / 2.0
    radius = (size - 8) / 2.0
    bounds = (
        round(center - radius),
        round(center - radius),
        round(center + radius),
        round(center + radius),
    )
    image = Image.new("RGB", (size, size), (0, 0, 0))
    draw = ImageDraw.Draw(image)

    sector_colors = (
        (15, 31, 44),
        (18, 36, 48),
        (12, 27, 42),
        (19, 33, 50),
    )
    for index, start in enumerate((0, 90, 180, 270)):
        draw.pieslice(bounds, start=start, end=start + 90, fill=sector_colors[index])

    for theta in range(15, 91, 15):
        ring_radius = radius * theta / 90.0
        ring_box = (
            round(center - ring_radius),
            round(center - ring_radius),
            round(center + ring_radius),
            round(center + ring_radius),
        )
        color = HEMISPHERE_EDGE if theta == 90 else RING
        draw.ellipse(ring_box, outline=color, width=8 if theta == 90 else 5)

    for bearing in range(0, 360, 30):
        angle = math.radians(bearing)
        end_x = center + radius * math.cos(angle)
        end_y = center + radius * math.sin(angle)
        draw.line(
            (round(center), round(center), round(end_x), round(end_y)),
            fill=SPOKE,
            width=4,
        )

    draw.line(
        (center - 28, center, center + 28, center),
        fill=PRIME_MERIDIAN,
        width=7,
    )
    draw.line(
        (center, center - 28, center, center + 28),
        fill=PRIME_MERIDIAN,
        width=7,
    )

    for theta in range(15, 90, 15):
        ring_radius = radius * theta / 90.0
        angle = math.radians(42)
        add_label(
            draw,
            (
                center + ring_radius * math.cos(angle),
                center + ring_radius * math.sin(angle),
            ),
            f"{theta}°",
            size=22,
            fill=RING,
            padding=4,
        )

    add_label(
        draw,
        (center, center),
        "FORWARD\n0°",
        size=29,
        fill=PRIME_MERIDIAN,
        bold=True,
    )
    add_label(
        draw,
        (center + radius - 160, center),
        "RIGHT RIM\n+90° LON",
        size=26,
        fill=HEMISPHERE_EDGE,
        bold=True,
    )
    add_label(
        draw,
        (center - radius + 160, center),
        "LEFT RIM\n−90° LON",
        size=26,
        fill=HEMISPHERE_EDGE,
        bold=True,
    )
    add_label(
        draw,
        (center, center - radius + 145),
        "ZENITH\n+90° LAT",
        size=26,
        fill=HEMISPHERE_EDGE,
        bold=True,
    )
    add_label(
        draw,
        (center, center + radius - 145),
        "NADIR\n−90° LAT",
        size=26,
        fill=HEMISPHERE_EDGE,
        bold=True,
    )
    add_label(
        draw,
        (245, 70),
        "IDEAL EQUIDISTANT\nDOMEMASTER",
        size=29,
        bold=True,
    )
    add_label(
        draw,
        (size - 235, size - 65),
        "equal 15° radial steps",
        size=23,
        fill=RING,
        bold=True,
    )
    return image


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    full_path = OUTPUT_DIR / "erp_360x180_angular_grid_4096x2048.png"
    crop_path = OUTPUT_DIR / "hemisphere_180x180_center_crop_2048x2048.png"
    dome_path = OUTPUT_DIR / "domemaster_equidistant_reference_2048.png"

    erp = make_erp_chart()
    erp.save(full_path, format="PNG", optimize=True)

    crop_left = (FULL_WIDTH - FULL_HEIGHT) // 2
    hemisphere = erp.crop(
        (crop_left, 0, crop_left + FULL_HEIGHT, FULL_HEIGHT)
    )
    hemisphere.save(crop_path, format="PNG", optimize=True)

    domemaster = make_domemaster_reference()
    domemaster.save(dome_path, format="PNG", optimize=True)

    for path in (full_path, crop_path, dome_path):
        with Image.open(path) as image:
            print(f"{path.name}: {image.width}x{image.height} {image.mode}")


if __name__ == "__main__":
    main()
