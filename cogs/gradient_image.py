# cogs/gradient_image.py

import os
from PIL import Image, ImageDraw, ImageFont


def create_gradient_text_image(
    username: str,
    amount: int,
    unit: str,
    color1: str,
    color2: str,
    output_path: str,
):
    # 画像サイズ
    width, height = 600, 200
    image = Image.new("RGB", (width, height), "#111111")
    draw = ImageDraw.Draw(image)

    # フォントパス
    base_dir = os.path.dirname(os.path.dirname(__file__))
    font_path = os.path.join(
        base_dir,
        "utils",
        "fonts",
        "NotoSansJP-VariableFont_wght.ttf",
    )

    # フォント読み込み
    font_large = ImageFont.truetype(font_path, 40)
    font_small = ImageFont.truetype(font_path, 28)

    # テキスト描画（※ここは後でグラデーション化する）
    draw.text(
        (30, 40),
        username,
        fill=color1,
        font=font_large,
    )

    draw.text(
        (30, 100),
        f"{amount:,} {unit}",
        fill=color2,
        font=font_small,
    )

    image.save(output_path)

