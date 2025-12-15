# cogs/gradient_image.py

import os
from PIL import Image, ImageDraw, ImageFont


def create_gradient_text_image(
    sender: str,
    receiver: str,
    amount: int,
    unit: str,
    color1: str,
    color2: str,
    output_path: str,
):
    width, height = 900, 360
    image = Image.new("RGB", (width, height), "#0f0f12")
    draw = ImageDraw.Draw(image)

    base_dir = os.path.dirname(os.path.dirname(__file__))
    font_path = os.path.join(
        base_dir,
        "utils",
        "fonts",
        "NotoSansJP-VariableFont_wght.ttf",
    )

    font_label = _load_font(font_path, 32)
    font_main = _load_font(font_path, 48)

    # ラベル（白）
    draw.text((60, 50), "送信者", fill="#cccccc", font=font_label)
    draw.text((60, 140), "受取", fill="#cccccc", font=font_label)
    draw.text((60, 230), "送金額", fill="#cccccc", font=font_label)

    # グラデーション文字
    draw_gradient_text(
        draw,
        (200, 40),
        sender,
        font_main,
        color1,
        color2,
    )

    draw_gradient_text(
        draw,
        (200, 130),
        receiver,
        font_main,
        color1,
        color2,
    )

    draw_gradient_text(
        draw,
        (200, 220),
        f"{amount:,} {unit}",
        font_main,
        color1,
        color2,
    )

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    image.save(output_path)


    image.save(output_path)
def _hex_to_rgb(hex_color: str):
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def _lerp(a: int, b: int, t: float) -> int:
    return int(a + (b - a) * t)


def draw_gradient_text(
    draw: ImageDraw.Draw,
    position: tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont,
    color_start: str,
    color_end: str,
):
    x, y = position
    c1 = _hex_to_rgb(color_start)
    c2 = _hex_to_rgb(color_end)

    total_width = sum(font.getlength(c) for c in text)
    current_x = x

    for char in text:
        w = font.getlength(char)
        t = (current_x - x) / max(total_width, 1)

        r = _lerp(c1[0], c2[0], t)
        g = _lerp(c1[1], c2[1], t)
        b = _lerp(c1[2], c2[2], t)

        draw.text(
            (current_x, y),
            char,
            fill=(r, g, b),
            font=font,
        )
        current_x += w

