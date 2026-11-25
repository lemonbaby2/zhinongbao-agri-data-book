"""生成 exe 图标（绿色的“田”字方块，与站点 favicon 一致）。

用法：python tools/make_icon.py
输出：desktop/assets/zhinongbao.ico（含 16/32/48/64/128/256 多尺寸）
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "desktop" / "assets" / "zhinongbao.ico"
SIZES = [16, 24, 32, 48, 64, 128, 256]

BG = (20, 81, 47, 255)
LINE = (215, 234, 217, 255)
RULE = (143, 191, 155, 255)


def draw(size: int) -> Image.Image:
    scale = 8  # 先画大图再缩，边缘更顺
    canvas = size * scale
    image = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    pen = ImageDraw.Draw(image)

    radius = int(canvas * 0.22)
    pen.rounded_rectangle([0, 0, canvas - 1, canvas - 1], radius=radius, fill=BG)

    # 田字格
    margin = int(canvas * 0.235)
    left, top, right, bottom = margin, margin, canvas - margin, canvas - margin
    stroke = max(2, int(canvas * 0.055))
    pen.rectangle([left, top, right, bottom], outline=LINE, width=stroke)
    middle_x = (left + right) // 2
    middle_y = (top + bottom) // 2
    pen.line([middle_x, top, middle_x, bottom], fill=LINE, width=stroke)
    pen.line([left, middle_y, right, middle_y], fill=LINE, width=stroke)

    return image.resize((size, size), Image.LANCZOS)


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    frames = [draw(size) for size in SIZES]
    frames[-1].save(OUT, format="ICO", sizes=[(s, s) for s in SIZES])
    # 同时留一张 PNG 给文档用
    png = OUT.with_name("zhinongbao-256.png")
    frames[-1].save(png, format="PNG")
    print(f"已生成 {OUT} ({OUT.stat().st_size / 1024:.1f} KB)")
    print(f"已生成 {png}")


if __name__ == "__main__":
    main()
