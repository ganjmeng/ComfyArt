"""#905: before-after follows the card orientation inside the reference, decided on the server."""
from __future__ import annotations

import base64
import io
from pathlib import Path

from PIL import Image, ImageDraw

from ComfyArt.bot.ref_orientation import content_box, first_image_bytes, reference_orientation, reference_ratio
from ComfyArt.bot.skill_output import apply_generate, run_hint

ROOT = Path(__file__).resolve().parent.parent
COVER = (ROOT / "docs/design/640/78/gold/before-after/cover.webp").read_bytes()


def _png(w, h, card=None, bg=(30, 32, 40), gradient=False):
    img = Image.new("RGB", (w, h), bg)
    d = ImageDraw.Draw(img)
    if gradient:
        for y in range(h):
            v = 90 - int(60 * y / h)
            d.line([(0, y), (w, y)], fill=(v, v, v + 10))
    if card:
        d.rectangle(card, fill=(240, 236, 228))
        d.rectangle((card[0] + 10, card[1] + 40, card[2] - 10, card[3] - 40), fill=(200, 150, 120))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _noise(w, h):
    img = Image.effect_noise((w, h), 90).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_cover_webp_landscape_file_with_portrait_card_gives_4_5():
    assert Image.open(io.BytesIO(COVER)).size == (1600, 1200)
    assert reference_orientation(COVER) == "portrait"
    assert reference_ratio(COVER) == "4:5"


def test_landscape_square_and_portrait_cards():
    assert reference_ratio(_png(1600, 1200, card=(200, 200, 1400, 900), gradient=True)) == "16:9"
    assert reference_ratio(_png(1600, 1200, card=(300, 100, 1300, 1100))) == "1:1"
    assert reference_ratio(_png(1200, 1200, card=(300, 50, 900, 1150))) == "4:5"


def test_gradient_backdrop_portrait_card_is_trimmed():
    # a portrait card on a vertical-gradient backdrop in a landscape file, like cover.webp
    assert content_box(Image.open(io.BytesIO(_png(1600, 1200, card=(500, 100, 1100, 1100), gradient=True)))) == (500, 100, 1101, 1101)
    assert reference_ratio(_png(1600, 1200, card=(500, 100, 1100, 1100), gradient=True)) == "4:5"


def test_full_bleed_image_without_border_falls_back_to_pixel_orientation():
    # a photo that fills the frame edge to edge (box over 95%): no border to trim, file orientation wins
    img = Image.new("RGB", (1600, 1000))
    d = ImageDraw.Draw(img)
    for x in range(1600):
        v = int(255 * x / 1599)
        d.line([(x, 0), (x, 999)], fill=(v, 255 - v, 128))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    full = buf.getvalue()
    assert content_box(Image.open(io.BytesIO(full))) is None
    assert reference_ratio(full) == "16:9"


def test_no_uniform_border_falls_back_to_pixel_orientation():
    assert content_box(Image.open(io.BytesIO(_noise(1200, 800)))) is None
    assert reference_ratio(_noise(1200, 800)) == "16:9"
    assert reference_ratio(_noise(800, 1200)) == "4:5"
    assert reference_ratio(_noise(1000, 1050)) == "1:1"


def test_small_content_box_falls_back_to_pixel_orientation():
    # a tiny portrait mark on a landscape backdrop is under 30% of the image: pixel orientation wins
    assert reference_ratio(_png(1600, 1000, card=(700, 300, 900, 700))) == "16:9"


def test_undecodable_bytes_give_none():
    assert reference_orientation(b"not an image") is None


def test_first_image_bytes_reads_base64_attachment():
    att = [{"media_type": "application/pdf", "data": "AAAA"}, {"media_type": "image/webp", "data": base64.b64encode(COVER).decode()}]
    assert first_image_bytes(att) == COVER
    assert first_image_bytes([]) is None


def _gen(user_text, ref, refs=("shape:r",), skill="before-after", **extra):
    args = {"skill": skill, "prompt": "p", "width": 1920, "height": 1080, "ratio": "16:9", **extra}
    if refs:
        args["refs"] = list(refs)
    return apply_generate(args, skill, user_text=user_text, ref_image=ref)


def test_priority_user_ratio_then_reference_then_default():
    out = _gen("make a before-after card", COVER)
    assert (out["width"], out["height"], out["ratio"]) == (1024, 1280, "4:5")
    out = _gen("make a before-after card, ratio 16:9", COVER)
    assert (out["width"], out["height"], out["ratio"]) == (1920, 1080, "16:9")
    out = _gen("比例 1:1", COVER)
    assert (out["width"], out["height"]) == (1024, 1024)
    out = _gen("make a before-after card", None, refs=())
    assert (out["width"], out["height"], out["ratio"]) == (1920, 1080, "16:9")


def test_model_invented_ratio_still_overridden_with_reference():
    out = _gen("make a before-after card", COVER, ratio="21:9", width=2100, height=900)
    assert (out["width"], out["height"], out["ratio"]) == (1024, 1280, "4:5")


def test_reference_bytes_without_refs_arg_do_not_change_size():
    out = _gen("make a before-after card", COVER, refs=())
    assert (out["width"], out["height"]) == (1920, 1080)


def test_other_fixed_size_skills_ignore_reference_orientation():
    out = _gen("make it", COVER, skill="game-art")
    assert (out["width"], out["height"]) == (1024, 1824)
    out = _gen("make it", COVER, skill="linkedin-banner")
    assert (out["width"], out["height"]) == (1584, 396)


def test_output_lock_line_follows_reference_card():
    assert "width=1024 height=1280 ratio=4:5" in run_hint("before-after", "make a card", COVER)
    assert "width=1920 height=1080 ratio=16:9" in run_hint("before-after", "ratio 16:9", COVER)
    assert "4:5" not in run_hint("game-art", "make it", COVER)


def _put_input(name: str, data: bytes) -> str:
    import folder_paths

    root = Path(folder_paths.get_input_directory())
    root.mkdir(parents=True, exist_ok=True)
    (root / name).write_bytes(data)
    return f"/api/view?filename={name}&type=input"


def test_canvas_shape_ref_made_from_cover_webp_gives_4_5():
    # #905 tech: a reference picked on the canvas reaches generate_image as a shape id in refs, with no
    # chat attachment. Its bytes are resolved through the turn's Attached-line, so the rule still runs.
    from ComfyArt.bot.ref_orientation import ref_image_bytes

    src = _put_input("cover-905.webp", COVER)
    text = f'Make it.\n[Attached image 1 "cover-905.webp": shape id shape:ba-ref \u2014 {src}. Use the shape id with edit tools or as a generation ref.]'
    data = ref_image_bytes(["shape:ba-ref"], text, attachments=[])
    assert data == COVER
    out = apply_generate({"skill": "before-after", "refs": ["shape:ba-ref"], "width": 1920, "height": 1080, "ratio": "16:9"},
                         "before-after", user_text=text, ref_image=data)
    assert (out["width"], out["height"], out["ratio"]) == (1024, 1280, "4:5")


def test_ref_url_is_read_directly_and_refs_beat_attachments():
    from ComfyArt.bot.ref_orientation import ref_image_bytes

    src = _put_input("cover-905b.webp", COVER)
    other = base64.b64encode(_png(1600, 900)).decode()
    assert ref_image_bytes([src], "", attachments=[{"media_type": "image/png", "data": other}]) == COVER
    # an unresolvable shape id falls back to the chat attachment
    assert ref_image_bytes(["shape:unknown"], "", attachments=[{"media_type": "image/png", "data": other}]) == _png(1600, 900)


def test_chat_loop_resolves_reference_from_refs():
    src = (ROOT / "bot/local_llm.py").read_text(encoding="utf-8")
    assert 'ref_image_bytes(args.get("refs"), _ut, getattr(turn, "attachments", None))' in src


def _landscape_att():
    data = _png(1600, 900)
    return data, [{"media_type": "image/png", "data": base64.b64encode(data).decode()}]


def test_landscape_attachment_loses_to_cover_webp_shape_ref():
    # (a) chat attachment is landscape, refs shape resolves to cover.webp → 4:5 (refs win)
    from ComfyArt.bot.ref_orientation import ref_image_bytes

    src = _put_input("cover-905-lock-a.webp", COVER)
    landscape, attachments = _landscape_att()
    assert reference_ratio(landscape) == "16:9"
    text = (
        f'Make it.\n[Attached image 1 "cover-905-lock-a.webp": shape id shape:ba-ref '
        f'— {src}. Use the shape id with edit tools or as a generation ref.]'
    )
    data = ref_image_bytes(["shape:ba-ref"], text, attachments=attachments)
    assert data == COVER
    out = apply_generate(
        {"skill": "before-after", "refs": ["shape:ba-ref"], "width": 1920, "height": 1080, "ratio": "16:9"},
        "before-after", user_text=text, ref_image=data,
    )
    assert (out["width"], out["height"], out["ratio"]) == (1024, 1280, "4:5")


def test_unreadable_shape_falls_back_to_attachment_orientation():
    # (b) shape id missing from user_text, or src unreadable → attachment orientation (not another image)
    from ComfyArt.bot.ref_orientation import ref_image_bytes

    landscape, attachments = _landscape_att()
    other_src = _put_input("cover-905-lock-b-other.webp", COVER)

    # shape id not present in user_text
    text_missing = "Make it. No attached shape line."
    data = ref_image_bytes(["shape:missing"], text_missing, attachments=attachments)
    assert data == landscape
    out = apply_generate(
        {"skill": "before-after", "refs": ["shape:missing"], "width": 1920, "height": 1080, "ratio": "16:9"},
        "before-after", user_text=text_missing, ref_image=data,
    )
    assert (out["width"], out["height"], out["ratio"]) == (1920, 1080, "16:9")

    # Attached-line points at a file that cannot be read; a later refs entry must not be used
    text_bad = (
        'Make it.\n[Attached image 1 "gone.webp": shape id shape:gone '
        '— /api/view?filename=does-not-exist-905.webp&type=input. Use the shape id.]'
    )
    data = ref_image_bytes(["shape:gone", other_src], text_bad, attachments=attachments)
    assert data == landscape
    assert data != COVER
    out = apply_generate(
        {"skill": "before-after", "refs": ["shape:gone", other_src], "width": 1920, "height": 1080, "ratio": "16:9"},
        "before-after", user_text=text_bad, ref_image=data,
    )
    assert (out["width"], out["height"], out["ratio"]) == (1920, 1080, "16:9")


def test_unreadable_shape_and_no_attachment_defaults_to_16_9():
    # (c) shape unreadable and no attachment → 16:9 default, no exception
    from ComfyArt.bot.ref_orientation import ref_image_bytes

    text = "Make it."
    data = ref_image_bytes(["shape:gone"], text, attachments=[])
    assert data is None
    out = apply_generate(
        {"skill": "before-after", "refs": ["shape:gone"], "width": 1920, "height": 1080, "ratio": "16:9"},
        "before-after", user_text=text, ref_image=data,
    )
    assert (out["width"], out["height"], out["ratio"]) == (1920, 1080, "16:9")
    data_none = ref_image_bytes(["shape:gone"], text, attachments=None)
    assert data_none is None
