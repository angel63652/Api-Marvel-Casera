"""Barcode label generation using python-barcode + Pillow."""
import io

from barcode import Code128
from barcode.writer import ImageWriter
from PIL import Image, ImageDraw, ImageFont

# Label dimensions: 400×200 px (≈ 2.67"×1.33" at 150 DPI)
_W, _H = 400, 200
_BG = (255, 255, 255)
_FG = (0, 0, 0)
_BARCODE_H = 110  # height reserved for barcode strip
_MARGIN = 10


def _default_font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size)
    except OSError:
        try:
            return ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", size)
        except OSError:
            return ImageFont.load_default()


def generate_label(barcode_value: str, name: str, niu: str) -> bytes:
    """Return PNG bytes for a printable barcode label."""
    # Generate barcode strip as PNG into a buffer
    writer = ImageWriter()
    # Disable human-readable text in barcode strip (we place it manually)
    writer.set_options({
        "write_text": False,
        "quiet_zone": 2,
        "module_height": 10.0,
        "module_width": 0.5,
        "font_size": 0,
        "text_distance": 1,
    })
    buf = io.BytesIO()
    bc = Code128(barcode_value, writer=writer)
    bc.write(buf, options={"write_text": False})
    buf.seek(0)
    barcode_img = Image.open(buf).convert("RGB")

    # Create label canvas
    label = Image.new("RGB", (_W, _H), _BG)
    draw = ImageDraw.Draw(label)

    # Scale and center barcode strip to fit width
    bw, bh = barcode_img.size
    scale = min((_W - 2 * _MARGIN) / bw, _BARCODE_H / bh)
    new_bw = int(bw * scale)
    new_bh = int(bh * scale)
    barcode_img = barcode_img.resize((new_bw, new_bh), Image.LANCZOS)
    bx = (_W - new_bw) // 2
    label.paste(barcode_img, (bx, _MARGIN))

    # Barcode value text
    font_bc = _default_font(13)
    bc_text = barcode_value
    draw.text((_W // 2, _MARGIN + new_bh + 4), bc_text, font=font_bc, fill=_FG, anchor="mt")

    # Product name (truncated if needed)
    font_name = _default_font(14)
    max_chars = 45
    display_name = name if len(name) <= max_chars else name[: max_chars - 1] + "…"
    draw.text((_W // 2, _MARGIN + new_bh + 22), display_name, font=font_name, fill=_FG, anchor="mt")

    # NIU
    font_niu = _default_font(12)
    draw.text((_W // 2, _H - _MARGIN - 2), f"NIU: {niu}", font=font_niu, fill=(100, 100, 100), anchor="mb")

    out = io.BytesIO()
    label.save(out, format="PNG")
    return out.getvalue()
