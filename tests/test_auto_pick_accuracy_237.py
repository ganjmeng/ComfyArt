"""#237: zh + en cases for every row of the #133 Auto table (issue comment, product table v1).

Accuracy is the share of cases whose model AND category match the table (the reply's
"why"). Model accuracy ignores the category, so a poster that still uses the default
model counts as a model hit. Measured on the matcher before the #237 change, same 115
cases (mocks only, no WaveSpeed and no LLM):

    all  row 64/115 = 55.7%    model 71/115 = 61.7%
    zh   row 33/55 = 60.0%     model 36/55 = 65.5%
    en   row 31/60 = 51.7%     model 35/60 = 58.3%

The tests require the table outcome, including a note that names the model and the
reason in both zh and en.

Product choices this set locks in, where the table is silent (see the PR):
- 2+ reference images stay on image edit `google/nano-banana-2.1/edit` (#153). The
  table names the text-to-image id; refs cannot run on that path.
- 1 reference or a base image stays on the image-edit default (#153), even if the
  prompt also matches another row.
- When several rows match, the first row in api/auto_models.json wins. Character /
  product consistency is last, so an explicit logo / poster / anime / photoreal cue
  keeps that row.
"""
from __future__ import annotations

from ComfyArt.api import auto_models
from ComfyArt.api.mcp_tools import canvas

FLARE_T2I = "openai/gpt-image-2.5-flare/text-to-image"
FLARE_EDIT = "openai/gpt-image-2.5-flare/edit"
SEEDREAM = "bytedance/seedream-v5.0-pro"
SEEDREAM_EDIT = "bytedance/seedream-v5.0-pro/edit"
NANO_T2I = "google/nano-banana-2.1/text-to-image"
NANO_EDIT = "google/nano-banana-2.1/edit"
MJ = "midjourney/text-to-image"
RECRAFT = "recraft-ai/recraft-v3"
NAMED = "alibaba/qwen-image-3.0/text-to-image"

# Rows that must have at least one zh case and one en case.
TABLE_ROWS = (
    "t2i_general", "t2i_poster", "t2i_photoreal", "t2i_consistency",
    "t2i_multi_ref", "t2i_one_ref", "t2i_anime", "t2i_logo",
    "edit_general", "edit_identity", "edit_retouch", "user_named",
)


def case(lang, row, tool, prompt, expect, category, **args):
    return {"lang": lang, "row": row, "tool": tool, "prompt": prompt,
            "model": expect, "category": category, "args": args}


CASES = [
    # --- text-to-image: general / cannot tell → flare ---
    case("en", "t2i_general", "generate_image", "a cup of coffee on a wooden table", FLARE_T2I, "default"),
    case("en", "t2i_general", "generate_image", "sunset over snowy mountains, no people", FLARE_T2I, "default"),
    case("en", "t2i_general", "generate_image", "a red bicycle leaning against a brick wall", FLARE_T2I, "default"),
    case("en", "t2i_general", "generate_image", "an iconic city skyline at dusk", FLARE_T2I, "default"),
    case("en", "t2i_general", "generate_image", "a cartoonish dog running through a park", FLARE_T2I, "default"),
    case("en", "t2i_general", "generate_image", "portrait orientation, 3:4, a coffee cup", FLARE_T2I, "default"),
    case("en", "t2i_general", "generate_image", "show the app context menu in a dark theme", FLARE_T2I, "default"),
    case("en", "t2i_general", "generate_image", "a name badge with the job title Designer", FLARE_T2I, "default"),
    case("en", "t2i_general", "generate_image", "photorealistic landscape of mountains, no people", FLARE_T2I, "default"),
    case("zh", "t2i_general", "generate_image", "画一只坐在窗边的橘猫", FLARE_T2I, "default"),
    case("zh", "t2i_general", "generate_image", "雨后的街道，路灯刚亮", FLARE_T2I, "default"),
    case("zh", "t2i_general", "generate_image", "一碗热气腾腾的拉面", FLARE_T2I, "default"),
    case("zh", "t2i_general", "generate_image", "竖构图，一张桌子上的咖啡杯", FLARE_T2I, "default"),
    case("zh", "t2i_general", "generate_image", "不要任何文字的海边风景", FLARE_T2I, "default"),
    case("zh", "t2i_general", "generate_image", "写实风格的山川风景", FLARE_T2I, "default"),

    # --- poster / infographic / title or a lot of text → flare (reason differs from general) ---
    case("en", "t2i_poster", "generate_image", 'Movie poster with the headline "SUMMER"', FLARE_T2I, "poster_text"),
    case("en", "t2i_poster", "generate_image", "an infographic explaining how coffee is roasted", FLARE_T2I, "poster_text"),
    case("en", "t2i_poster", "generate_image", "a conference brochure with a big slogan", FLARE_T2I, "poster_text"),
    case("en", "t2i_poster", "generate_image", "restaurant menu board, dish names in large type", FLARE_T2I, "poster_text"),
    case("en", "t2i_poster", "generate_image", "a billboard with the words GRAND OPENING", FLARE_T2I, "poster_text"),
    case("zh", "t2i_poster", "generate_image", "一张电影海报，大标题是「夏日」", FLARE_T2I, "poster_text"),
    case("zh", "t2i_poster", "generate_image", "咖啡烘焙流程信息图", FLARE_T2I, "poster_text"),
    case("zh", "t2i_poster", "generate_image", "促销宣传单，标语要醒目", FLARE_T2I, "poster_text"),
    case("zh", "t2i_poster", "generate_image", "餐厅菜单设计，菜名用大字", FLARE_T2I, "poster_text"),
    case("zh", "t2i_poster", "generate_image", "易拉宝，上面写着开业大吉", FLARE_T2I, "poster_text"),
    case("zh", "t2i_poster", "generate_image", "海报，不要太小的文字，标题要大", FLARE_T2I, "poster_text"),

    # --- photoreal portrait / product photo / e-commerce hero → seedream ---
    case("en", "t2i_photoreal", "generate_image", "Photorealistic portrait of an old fisherman", SEEDREAM, "photoreal"),
    case("en", "t2i_photoreal", "generate_image", "professional head shot of a CEO, soft studio light", SEEDREAM, "photoreal"),
    case("en", "t2i_photoreal", "generate_image", "packshot of a perfume bottle on white", SEEDREAM, "photoreal"),
    case("en", "t2i_photoreal", "generate_image", "studio product photography of white sneakers", SEEDREAM, "photoreal"),
    case("en", "t2i_photoreal", "generate_image", "e-commerce hero image of a skincare bottle", SEEDREAM, "photoreal"),
    case("en", "t2i_photoreal", "generate_image", "a realistic portrait of a smiling woman", SEEDREAM, "photoreal"),
    case("en", "t2i_photoreal", "generate_image", "no headline, just a product photo of a shoe", SEEDREAM, "photoreal"),
    case("zh", "t2i_photoreal", "generate_image", "一张写实人像，自然光", SEEDREAM, "photoreal"),
    case("zh", "t2i_photoreal", "generate_image", "电商主图，白底，香水瓶", SEEDREAM, "photoreal"),
    case("zh", "t2i_photoreal", "generate_image", "产品摄影，运动鞋，棚拍", SEEDREAM, "photoreal"),
    case("zh", "t2i_photoreal", "generate_image", "证件照风格的半身照", SEEDREAM, "photoreal"),
    case("zh", "t2i_photoreal", "generate_image", "真人照片，女士，微笑", SEEDREAM, "photoreal"),
    case("zh", "t2i_photoreal", "generate_image", "商品白底图，用于上架", SEEDREAM, "photoreal"),

    # --- character / product consistency, no extra images → nano text-to-image ---
    case("en", "t2i_consistency", "generate_image", "the same girl in three outfits, keep her face identical", NANO_T2I, "consistency"),
    case("en", "t2i_consistency", "generate_image", "character consistency across the set, one boy", NANO_T2I, "consistency"),
    case("en", "t2i_consistency", "generate_image", "product consistency: the bottle must look the same in every shot", NANO_T2I, "consistency"),
    case("en", "t2i_consistency", "generate_image", "same character, three views, identical face", NANO_T2I, "consistency"),
    case("zh", "t2i_consistency", "generate_image", "同一个角色的三视图，五官要一致", NANO_T2I, "consistency"),
    case("zh", "t2i_consistency", "generate_image", "角色一致性，还是那个女孩", NANO_T2I, "consistency"),
    case("zh", "t2i_consistency", "generate_image", "产品一致性：瓶子每张都要一样", NANO_T2I, "consistency"),
    case("zh", "t2i_consistency", "generate_image", "同一张脸，换三套衣服", NANO_T2I, "consistency"),
    # a clearer style row wins over consistency
    case("en", "t2i_anime", "generate_image", "anime girl, same character, three views", MJ, "anime_art"),
    case("en", "t2i_photoreal", "generate_image", "photorealistic portrait of the same girl", SEEDREAM, "photoreal"),

    # --- 2+ refs → nano edit (#153); 1 ref / base → edit default. Prompt category does not override. ---
    case("en", "t2i_multi_ref", "generate_image", "the mug from picture 1 on the desk from picture 2", NANO_EDIT, "multi_reference", refs=["shape:a", "shape:b"]),
    case("zh", "t2i_multi_ref", "generate_image", "把图1的人放到图2的房间里", NANO_EDIT, "multi_reference", refs=["shape:a", "shape:b"]),
    case("en", "t2i_multi_ref", "generate_image", "anime style, use both references", NANO_EDIT, "multi_reference", refs=["shape:a", "shape:b"]),
    case("zh", "t2i_multi_ref", "generate_image", "同一个角色，参考这两张图", NANO_EDIT, "multi_reference", refs=["shape:a", "shape:b"]),
    case("en", "t2i_one_ref", "generate_image", "a movie poster using this photo", FLARE_EDIT, "references", refs=["shape:r"]),
    case("zh", "t2i_one_ref", "generate_image", "参考这张图做一张海报", FLARE_EDIT, "references", refs=["shape:r"]),
    case("en", "t2i_one_ref", "generate_image", "make the character consistent with this photo", FLARE_EDIT, "references", base="shape:b"),
    case("zh", "t2i_one_ref", "generate_image", "让角色和这张底图一致", FLARE_EDIT, "references", base="shape:b"),

    # --- anime / illustration / art style → midjourney ---
    case("en", "t2i_anime", "generate_image", "Anime girl under cherry blossoms", MJ, "anime_art"),
    case("en", "t2i_anime", "generate_image", "a comic-style drawing of a knight", MJ, "anime_art"),
    case("en", "t2i_anime", "generate_image", "a digital painting of a dragon", MJ, "anime_art"),
    case("en", "t2i_anime", "generate_image", "an illustrated children's book page with a fox", MJ, "anime_art"),
    case("en", "t2i_anime", "generate_image", "ghibli style countryside path", MJ, "anime_art"),
    case("en", "t2i_anime", "generate_image", "manga panel, black and white line art", MJ, "anime_art"),
    case("zh", "t2i_anime", "generate_image", "二次元少女，樱花树下", MJ, "anime_art"),
    case("zh", "t2i_anime", "generate_image", "吉卜力风格的乡间小路", MJ, "anime_art"),
    case("zh", "t2i_anime", "generate_image", "水墨画，留白很多", MJ, "anime_art"),
    case("zh", "t2i_anime", "generate_image", "手绘绘本风格的小狐狸", MJ, "anime_art"),
    case("zh", "t2i_anime", "generate_image", "漫画分镜，线稿", MJ, "anime_art"),
    case("zh", "t2i_anime", "generate_image", "一幅油画，星空", MJ, "anime_art"),

    # --- logo / icon / vector → recraft ---
    case("en", "t2i_logo", "generate_image", "Minimal logo for a tea brand", RECRAFT, "logo"),
    case("en", "t2i_logo", "generate_image", "a wordmark for a cafe, flat", RECRAFT, "logo"),
    case("en", "t2i_logo", "generate_image", "flat brand mark of a fox", RECRAFT, "logo"),
    case("en", "t2i_logo", "generate_image", "app icon of a fox", RECRAFT, "logo"),
    case("en", "t2i_logo", "generate_image", "a monogram emblem, vector", RECRAFT, "logo"),
    case("zh", "t2i_logo", "generate_image", "一个茶饮品牌的图标设计", RECRAFT, "logo"),
    case("zh", "t2i_logo", "generate_image", "品牌商标，扁平，单色", RECRAFT, "logo"),
    case("zh", "t2i_logo", "generate_image", "字标设计，咖啡店", RECRAFT, "logo"),
    case("zh", "t2i_logo", "generate_image", "一套线性应用图标", RECRAFT, "logo"),
    case("zh", "t2i_logo", "generate_image", "矢量徽标，圆形", RECRAFT, "logo"),

    # --- image edit: general / change text / cannot tell → flare edit ---
    case("en", "edit_general", "edit_image", "change the sign text to OPEN", FLARE_EDIT, "default"),
    case("en", "edit_general", "edit_image", "replace the background with a beach", FLARE_EDIT, "default"),
    case("en", "edit_general", "edit_image", "make it brighter", FLARE_EDIT, "default"),
    case("en", "edit_general", "edit_image", "change the snakeskin bag to leather", FLARE_EDIT, "default"),
    case("en", "edit_general", "edit_image", "make the lighting consistent across the frame", FLARE_EDIT, "default"),
    case("en", "edit_general", "edit_image", "change the poster headline to SALE", FLARE_EDIT, "default"),
    case("zh", "edit_general", "edit_image", "把牌子上的字改成「营业中」", FLARE_EDIT, "default"),
    case("zh", "edit_general", "edit_image", "把背景换成海边", FLARE_EDIT, "default"),
    case("zh", "edit_general", "edit_image", "再亮一点", FLARE_EDIT, "default"),
    case("zh", "edit_general", "edit_image", "把这条蛇皮纹改成皮革", FLARE_EDIT, "default"),
    case("zh", "edit_general", "edit_image", "让光线统一一点，不要改别的", FLARE_EDIT, "default"),
    case("zh", "edit_general", "edit_image", "把标题文字改成「特价」", FLARE_EDIT, "default"),

    # --- local edit that must keep the person or product → nano edit ---
    case("en", "edit_identity", "edit_image", "new background, keep the same person", NANO_EDIT, "keep_identity"),
    case("en", "edit_identity", "edit_image", "change the shirt to red but don't change her face", NANO_EDIT, "keep_identity"),
    case("en", "edit_identity", "edit_image", "the person should look identical, only the background changes", NANO_EDIT, "keep_identity"),
    case("en", "edit_identity", "edit_image", "preserve the product, recolor the backdrop", NANO_EDIT, "keep_identity"),
    case("en", "edit_identity", "edit_image", "keep her face, new hairstyle", NANO_EDIT, "keep_identity"),
    case("zh", "edit_identity", "edit_image", "换背景，保持同一个人", NANO_EDIT, "keep_identity"),
    case("zh", "edit_identity", "edit_image", "只换背景，人脸不要动", NANO_EDIT, "keep_identity"),
    case("zh", "edit_identity", "edit_image", "衣服改成红色，五官不变", NANO_EDIT, "keep_identity"),
    case("zh", "edit_identity", "edit_image", "保留产品外观，只改背景颜色", NANO_EDIT, "keep_identity"),
    case("zh", "edit_identity", "edit_image", "人物不要变，把季节换成冬天", NANO_EDIT, "keep_identity"),

    # --- photoreal photo retouch → seedream edit ---
    case("en", "edit_retouch", "edit_image", "retouch the portrait, natural skin", SEEDREAM_EDIT, "photo_retouch"),
    case("en", "edit_retouch", "edit_image", "smooth wrinkles and remove blemishes", SEEDREAM_EDIT, "photo_retouch"),
    case("en", "edit_retouch", "edit_image", "this photo needs retouching, even out the complexion", SEEDREAM_EDIT, "photo_retouch"),
    case("en", "edit_retouch", "edit_image", "professionally retouched headshot, remove blemishes", SEEDREAM_EDIT, "photo_retouch"),
    case("en", "edit_retouch", "edit_image", "fix the lighting on this portrait photo", SEEDREAM_EDIT, "photo_retouch"),
    case("zh", "edit_retouch", "edit_image", "精修这张人像，自然一点", SEEDREAM_EDIT, "photo_retouch"),
    case("zh", "edit_retouch", "edit_image", "磨皮，保留质感", SEEDREAM_EDIT, "photo_retouch"),
    case("zh", "edit_retouch", "edit_image", "祛痘去皱，修一下脸", SEEDREAM_EDIT, "photo_retouch"),
    case("zh", "edit_retouch", "edit_image", "美颜，不要过度", SEEDREAM_EDIT, "photo_retouch"),
    case("zh", "edit_retouch", "edit_image", "这张照片太暗，补光修一下", SEEDREAM_EDIT, "photo_retouch"),

    # --- the user named a model → that model, and the note says so ---
    case("en", "user_named", "generate_image", "Anime poster", NAMED, "user", model=NAMED),
    case("zh", "user_named", "generate_image", "一张写实人像", NAMED, "user", model=NAMED),
    case("en", "user_named", "edit_image", "retouch the portrait", MJ, "user", model=MJ),
    case("zh", "user_named", "edit_image", "只换背景，人脸不要动", RECRAFT, "user", model=RECRAFT),
]


def predict(item: dict) -> dict:
    args = {"prompt": item["prompt"], **item["args"]}
    choice = canvas._auto_choice(item["tool"], args)
    assert choice, item["prompt"]
    return {**choice, "note": auto_models.note(choice)}


def score(items=None) -> dict:
    items = CASES if items is None else items
    misses = []
    for item in items:
        got = predict(item)
        model_ok = got["model"] == item["model"]
        row_ok = model_ok and got["category"] == item["category"]
        if not row_ok:
            misses.append({**item, "got_model": got["model"], "got_category": got["category"]})
        item["_model_ok"] = model_ok
        item["_row_ok"] = row_ok
    def pack(group):
        n = len(group)
        return {"n": n,
                "row": sum(1 for i in group if i["_row_ok"]),
                "model": sum(1 for i in group if i["_model_ok"])}
    return {"all": pack(items),
            "zh": pack([i for i in items if i["lang"] == "zh"]),
            "en": pack([i for i in items if i["lang"] == "en"]),
            "misses": misses}


def _fmt(part: dict) -> str:
    def pct(k):
        return f"{part[k]}/{part['n']} = {part[k] / part['n']:.1%}"
    return f"row {pct('row')}    model {pct('model')}"


def test_table_rows_have_zh_and_en():
    for row in TABLE_ROWS:
        langs = {c["lang"] for c in CASES if c["row"] == row}
        assert langs == {"zh", "en"}, row


def test_video_is_outside_the_table():
    assert auto_models.tool_feature("generate_video") is None
    assert canvas._auto_choice("generate_video", {"prompt": "anime poster"}) is None


def test_accuracy_matches_the_133_table():
    result = score()
    if result["misses"]:
        lines = [f"{m['lang']} {m['row']}: {m['prompt']!r} -> {m['got_category']}/{m['got_model']} "
                 f"(want {m['category']}/{m['model']})" for m in result["misses"]]
        raise AssertionError(
            "all " + _fmt(result["all"]) + "\nzh  " + _fmt(result["zh"]) + "\nen  " + _fmt(result["en"])
            + "\n" + "\n".join(lines))
    assert result["all"]["row"] == result["all"]["n"]


def test_every_choice_names_the_model_and_why():
    for item in CASES:
        got = predict(item)
        note = got["note"]
        assert note.startswith(f"用了 {got['model']}"), note
        assert f"Used {got['model']}" in note
        assert got["reason"]["zh"] in note and got["reason"]["en"] in note
        again = predict(item)
        assert again["model"] == got["model"] and again["category"] == got["category"]


def test_zh_and_en_accuracy_are_both_full():
    result = score()
    assert result["zh"]["n"] and result["en"]["n"]
    assert result["zh"]["row"] == result["zh"]["n"]
    assert result["en"]["row"] == result["en"]["n"]


if __name__ == "__main__":
    result = score()
    print("all ", _fmt(result["all"]))
    print("zh  ", _fmt(result["zh"]))
    print("en  ", _fmt(result["en"]))
    print(f"misses {len(result['misses'])}")
    for m in result["misses"]:
        print(f"  {m['lang']:2} {m['row']:16} {m['got_category']:16} {m['got_model']}")
        print(f"     want {m['category']:16} {m['model']}")
        print(f"     {m['prompt']}")
