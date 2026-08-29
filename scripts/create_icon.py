from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "assets" / "lumaguard.ico"
EXTENSION_OUTPUT = ROOT / "browser-extension" / "icons"
ACCENT_COLORS = {
    "violet": (139, 124, 255, 255),
    "rose": (255, 122, 144, 255),
    "mint": (83, 214, 181, 255),
    "blue": (101, 184, 255, 255),
    "amber": (244, 190, 97, 255),
}


def make_icon(size: int = 1024, shield_color: tuple[int, int, int, int] = ACCENT_COLORS["violet"]) -> Image.Image:
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    margin = int(size * 0.07)
    draw.rounded_rectangle(
        (margin, margin, size - margin, size - margin),
        radius=int(size * 0.25),
        fill=(14, 15, 24, 255),
        outline=(49, 47, 72, 255),
        width=max(2, size // 80),
    )
    shield = [
        (size * 0.50, size * 0.17),
        (size * 0.72, size * 0.25),
        (size * 0.72, size * 0.49),
        (size * 0.69, size * 0.65),
        (size * 0.59, size * 0.76),
        (size * 0.50, size * 0.82),
        (size * 0.41, size * 0.76),
        (size * 0.31, size * 0.65),
        (size * 0.28, size * 0.49),
        (size * 0.28, size * 0.25),
    ]
    draw.polygon(shield, fill=shield_color)
    line_width = max(5, int(size * 0.055))
    draw.line(
        [(size * 0.37, size * 0.49), (size * 0.47, size * 0.59), (size * 0.65, size * 0.38)],
        fill=(10, 11, 18, 255),
        width=line_width,
        joint="curve",
    )
    return image


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    source = make_icon()
    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    source.save(OUTPUT, format="ICO", sizes=sizes)
    EXTENSION_OUTPUT.mkdir(parents=True, exist_ok=True)
    for name, color in ACCENT_COLORS.items():
        accent_source = make_icon(shield_color=color)
        for icon_size in (16, 32, 48, 128):
            icon = accent_source.resize((icon_size, icon_size), Image.Resampling.LANCZOS)
            icon.save(EXTENSION_OUTPUT / f"{name}-{icon_size}.png", format="PNG")
    print(OUTPUT)


if __name__ == "__main__":
    main()
