from ..mcp_commands import submit_command
from ..wavespeed import grouped_models, load_config
from ._context import BOT_CHAT_ID, PROJECT
from .bot_tools import maybe_ask_run_approval

WAIT_MAX_S = 170
SLOW_S = 90.0

_ID = {"type": "string", "description": "shape id exactly as get_canvas returns it, e.g. shape:abc"}
_IDS = {"type": "array", "items": {"type": "string"}}
_POINT = {"type": "number"}
_REGION = {"x": _POINT, "y": _POINT, "width": _POINT, "height": _POINT}
_PLACE = {
    "frame": {"type": "string", "description": "frame id to place the result inside"},
    "near": {"type": "string", "description": "shape id to place the result next to"},
}


def _schema(properties: dict, required: list[str] = ()) -> dict:
    return {"type": "object", "properties": properties, "required": list(required), "additionalProperties": False}


def _relay(action: str, *, timeout: float = 20.0, approval: str = ""):
    async def handler(args: dict) -> dict:
        if approval:
            label = str(args.get("prompt") or args.get("to") or "")[:80]
            blocked = await maybe_ask_run_approval(f"{approval}{'：' + label if label else ''}")
            if blocked is not None:
                return blocked
        result = await submit_command(action, args, PROJECT.get(), timeout, chat=BOT_CHAT_ID.get())
        image = result.pop("png", None)
        if image:
            result["_images"] = [{"data": image, "mime": "image/png"}]
        return result
    return handler


async def _wait_generation(args: dict) -> dict:
    timeout = max(1, min(int(args.get("timeout_s") or WAIT_MAX_S), WAIT_MAX_S))
    return await submit_command("wait_generation", {**args, "timeout_s": timeout}, PROJECT.get(), timeout + 15)


def _tool(description: str, properties: dict, required: list[str] = (), **relay) -> dict:
    return {"description": description, "inputSchema": _schema(properties, required), "relay": relay}


SPECS: dict[str, dict] = {
    "get_canvas": _tool(
        "List the open project: pages, the current page's frames and shapes (id, type, name or text, "
        "x/y/width/height, parent, image or video URL and its pixel size, generation prompt, the text of "
        "imported PDF pages), the selection, the linked "
        "brand kit and running generations. page selects another page by id or name.",
        {"page": {"type": "string"}}),
    "view_canvas": _tool(
        "Render real pixels of the current page (default), of some shapes or frames (ids), so you can "
        "see layout and results. max_px caps the long side (default 1024).",
        {"ids": _IDS, "max_px": {"type": "integer"}}, timeout=SLOW_S),
    "list_models": _tool(
        "WaveSpeed cloud models grouped by feature (text_to_image, image_edit, upscale_image, ...): ids, "
        "price in USD per run, description, accepted inputs and the default per feature. Pass an id as "
        "model to the matching tool, or omit model to use the default.", {}),
    "brand_kits": _tool(
        "The user's brand kits and saved assets (characters, products): names, descriptions, colors "
        "with roles, fonts, logo and reference image URLs, and which kit this project is linked to.", {}),
    "generate_image": _tool(
        "Start generating images on the canvas. Returns ids at once; call wait_generation with them. "
        "prompt: detailed English description (put exact text to render in quotes). ratio like 1:1, "
        "3:4, 16:9. count 1-4. refs: image shape ids or image URLs the result must follow (subject, "
        "product, style). base: an image shape id to transform (image-to-image) with base_strength "
        "0-100 (higher changes more).",
        {"prompt": {"type": "string"}, "model": {"type": "string"}, "ratio": {"type": "string"},
         "count": {"type": "integer"}, "refs": _IDS, "base": {"type": "string"},
         "base_strength": {"type": "integer"}, **_PLACE},
        ["prompt"], approval="生成图像"),
    "generate_video": _tool(
        "Start generating a video. Returns ids at once; call wait_generation with them. first_frame / "
        "last_frame are image shape ids. References make a video that follows characters, products, scenes, "
        "motion or sound instead of starting from a frame: reference_images (up to 9 image shape ids, "
        "<Picture 1>…), reference_videos (up to 3 video shape ids, <Video 1>…), reference_audios (up to 3 "
        "audio shape ids, <Audio 1>…). With references, first say what each one is and what it does "
        "(\"Use <Picture 1> as the product, <Video 1> for the camera move, <Audio 1> as the voice\"), then "
        "describe the shot; a tag only mentioned in passing is ignored. motion_video (a video shape id) "
        "makes the person in first_frame copy that video's body motion. speech_audio (an audio shape id) "
        "makes the person in first_frame say that audio with matching lip movement; the video lasts as long "
        "as the audio. duration in seconds (5, 10 or 15).",
        {"prompt": {"type": "string"}, "model": {"type": "string"}, "ratio": {"type": "string"},
         "duration": {"type": "integer"}, "first_frame": {"type": "string"}, "last_frame": {"type": "string"},
         "reference_images": _IDS, "reference_videos": _IDS, "reference_audios": _IDS,
         "motion_video": {"type": "string"}, "speech_audio": {"type": "string"}, **_PLACE},
        ["prompt"], approval="生成视频"),
    "edit_image": _tool(
        "Edit an image shape with an instruction (change, add or remove things, restyle). The result is "
        "placed next to it. Returns ids for wait_generation.",
        {"id": _ID, "prompt": {"type": "string"}}, ["id", "prompt"], approval="编辑图片"),
    "animate_image": _tool(
        "Turn an image shape into an animated image (a looping WebP of a few seconds, motion described by "
        "prompt), placed as an image. loop makes the last frame match the first. For a real video use "
        "generate_video with first_frame. Returns ids for wait_generation.",
        {"id": _ID, "prompt": {"type": "string"}, "loop": {"type": "boolean"}}, ["id", "prompt"],
        approval="动态图片"),
    "upscale_image": _tool(
        "Upscale an image shape by factor 2 or 4. creative=true re-renders details (style optional).",
        {"id": _ID, "factor": {"type": "integer", "enum": [2, 4]}, "creative": {"type": "boolean"},
         "style": {"type": "string"}}, ["id"], approval="放大"),
    "remove_background": _tool(
        "Cut the main subject out of an image shape onto a transparent background.",
        {"id": _ID}, ["id"], approval="去背景"),
    "expand_image": _tool(
        "Outpaint an image shape: extend it by left/top/right/bottom pixels, filling the new area "
        "(prompt optional).",
        {"id": _ID, "left": _POINT, "top": _POINT, "right": _POINT, "bottom": _POINT, "prompt": {"type": "string"}},
        ["id"], approval="扩图"),
    "split_layers": _tool(
        "Split an image shape into separate transparent layers (layers: how many, default 4).",
        {"id": _ID, "layers": {"type": "integer"}, "prompt": {"type": "string"}}, ["id"], approval="图层拆分"),
    "change_angle": _tool(
        "Re-render an image shape from another camera angle: horizontal -180..180 degrees, vertical "
        "-90..90 degrees, zoom 0.5..2.",
        {"id": _ID, "horizontal": _POINT, "vertical": _POINT, "zoom": _POINT}, ["id"], approval="多角度"),
    "replace_text": _tool(
        "Replace text rendered inside an image shape: from is the current text, to the new text.",
        {"id": _ID, "from": {"type": "string"}, "to": {"type": "string"}}, ["id", "from", "to"],
        approval="编辑文字"),
    "edit_region": _tool(
        "Repaint only a region of an image shape following prompt; the rest stays untouched. x/y/width/"
        "height are in the image's own pixels (get_canvas pixels gives its size; comments sent by the "
        "user carry a ready region).",
        {"id": _ID, **_REGION, "prompt": {"type": "string"}}, ["id", "x", "y", "width", "height", "prompt"],
        approval="局部重绘"),
    "erase_region": _tool(
        "Remove whatever is inside a region of an image shape and fill it with the surrounding "
        "background. Region in the image's own pixels.",
        {"id": _ID, **_REGION}, ["id", "x", "y", "width", "height"], approval="擦除"),
    "move_object": _tool(
        "Move one object inside an image shape by dx/dy image pixels; the old spot is filled with "
        "background. Pick the object by object (a short English name like 'apple') or by x/y (a point "
        "on it, in the image's own pixels).",
        {"id": _ID, "object": {"type": "string"}, "x": _POINT, "y": _POINT, "dx": _POINT, "dy": _POINT},
        ["id", "dx", "dy"],
        approval="移动对象"),
    "style_transfer": _tool(
        "Redraw an image shape in another style: style describes it in words, ref is an optional image "
        "shape id or URL whose style to copy.",
        {"id": _ID, "style": {"type": "string"}, "ref": {"type": "string"}}, ["id"], approval="风格迁移"),
    "vectorize_image": _tool(
        "Trace an image shape into an SVG vector image placed next to it (best for logos, icons, flat "
        "art). Returns the new shape id at once.",
        {"id": _ID}, ["id"], timeout=SLOW_S),
    "upscale_video": _tool(
        "Upscale a video shape to target 1080p, 2K or 4K (long side).",
        {"id": _ID, "target": {"type": "string", "enum": ["1080p", "2K", "4K"]}}, ["id"], approval="视频放大"),
    "remove_video_background": _tool(
        "Cut the main subject out of a video shape onto a black background.",
        {"id": _ID}, ["id"], approval="视频去背景"),
    "extend_video": _tool(
        "Continue a video shape by duration seconds following prompt.",
        {"id": _ID, "prompt": {"type": "string"}, "duration": {"type": "integer"}}, ["id", "prompt"],
        approval="视频延长"),
    "generate_music": _tool(
        "Generate a piece of music as an audio element on the canvas. prompt: English style tags (genre, "
        "mood, instruments, tempo, vocal type). lyrics optional (use [verse]/[chorus] lines; omit for an "
        "instrumental). duration in seconds (default 30). Returns ids for wait_generation.",
        {"prompt": {"type": "string"}, "lyrics": {"type": "string"}, "duration": {"type": "integer"}},
        ["prompt"], approval="生成配乐"),
    "generate_sound_effect": _tool(
        "Generate a short sound effect (an audio element) from an English description. duration in "
        "seconds (default 8; Stable Audio is trained on clips up to 47 s). Returns ids for wait_generation.",
        {"prompt": {"type": "string"}, "duration": {"type": "integer"}}, ["prompt"], approval="生成音效"),
    "text_to_speech": _tool(
        "Read text aloud as an audio element. voice is a built-in voice id (zf_/zm_ Chinese female/male, "
        "af_/am_ American, bf_/bm_ British, jf_/jm_ Japanese; default zf_xiaoxiao; or the Qwen3-TTS speakers "
        "Serena, Vivian, Uncle_fu, Dylan, Eric, Ryan, Aiden, Ono_anna, Sohee; default Serena), or pass reference "
        "(an audio shape id) to clone that recording's voice. Returns ids for wait_generation.",
        {"text": {"type": "string"}, "voice": {"type": "string"}, "reference": _ID}, ["text"], approval="生成配音"),
    "edit_elements": _tool(
        "Turn the text inside an image shape into editable text: OCR finds each line, the text is erased "
        "from the picture, and a new artboard holds the clean background plus one editable text shape "
        "per line (same position, size, color). Then change the texts with update_shapes. Returns ids "
        "for wait_generation; the returned shape is the background image inside the new artboard.",
        {"id": _ID}, ["id"], approval="编辑元素"),
    "create_mockup": _tool(
        "Turn a product photo (image shape) into a mockup: its surface (depth, outline, shading) is "
        "analysed so a design can be printed onto it. Returns ids for wait_generation; the placed shape "
        "is the mockup. Then call place_design.",
        {"id": _ID}, ["id"], approval="制作样机"),
    "place_design": _tool(
        "Print a design onto a mockup shape. design: an image shape id or URL. x/y: design center as "
        "0-1 of the mockup width/height; scale: design width as a fraction of the mockup width; "
        "rotation in degrees; warp 0-1 (how much the design follows the surface). bake=true also "
        "places the result as a normal image and returns its id.",
        {"id": _ID, "design": {"type": "string"}, "x": _POINT, "y": _POINT, "scale": _POINT,
         "rotation": _POINT, "warp": _POINT, "bake": {"type": "boolean"}},
        ["id"], timeout=SLOW_S),
    "image_to_3d": _tool(
        "Turn an image shape (best: one object on a plain background) into a textured 3D model placed next "
        "to it. Takes a few minutes. Returns ids for wait_generation. Runs on WaveSpeed "
        "(default wavespeed-ai/trellis-2/image-to-3d). views: 1-4 image shape ids of the same object as front, "
        "left, back and right, in that order; when given, tripo3d/h3.1/multiview-to-3d builds one model from "
        "all of them and id is ignored.",
        {"id": _ID, "model": {"type": "string", "description": "WaveSpeed 3D model id from list_models (image_to_3d); omit for the default. Multiple views use tripo3d/h3.1/multiview-to-3d"}, "views": _IDS}, approval="转 3D"),
    "place_html": _tool(
        "Place a web page on the canvas: html is one complete self-contained HTML document you wrote "
        "(inline CSS/JS, images by absolute URL). width/height in canvas units.",
        {"html": {"type": "string"}, "name": {"type": "string"}, "x": _POINT, "y": _POINT,
         "width": _POINT, "height": _POINT},
        ["html"]),
    "create_slides": _tool(
        "Build a slide deck as 1280x720 frames with editable title and bullet text; slides with image "
        "get a generated picture (image is an English image prompt). Returns frame ids and generation ids.",
        {"title": {"type": "string"},
         "slides": {"type": "array", "items": _schema({"title": {"type": "string"},
                                                       "bullets": {"type": "array", "items": {"type": "string"}},
                                                       "image": {"type": "string"}}, ["title"])}},
        ["slides"], approval="制作 PPT"),
    "add_text": _tool(
        "Add an editable text shape. font_size in px, color as hex, font family name (brand fonts work), "
        "width wraps the text. x/y are page coordinates, or relative to frame when frame is given.",
        {"text": {"type": "string"}, "x": _POINT, "y": _POINT, "width": _POINT, "font_size": _POINT,
         "color": {"type": "string"}, "font": {"type": "string"},
         "align": {"type": "string", "enum": ["left", "center", "right"]}, "frame": _PLACE["frame"]},
        ["text"]),
    "add_shape": _tool(
        "Add a vector shape: kind rect, ellipse, polygon (sides) or star (sides = points). fill and "
        "stroke as hex. x/y are page coordinates, or relative to frame when frame is given.",
        {"kind": {"type": "string", "enum": ["rect", "ellipse", "polygon", "star"]}, "x": _POINT, "y": _POINT,
         "width": _POINT, "height": _POINT, "sides": {"type": "integer"}, "fill": {"type": "string"},
         "stroke": {"type": "string"}, "frame": _PLACE["frame"]},
        ["kind"]),
    "create_frame": _tool(
        "Create an artboard frame (name, width, height). children: shape ids to move inside it.",
        {"name": {"type": "string"}, "width": _POINT, "height": _POINT, "x": _POINT, "y": _POINT,
         "children": _IDS},
        ["width", "height"]),
    "update_shapes": _tool(
        "Change shapes: each update has id plus any of x, y (page coordinates), width, height, rotation "
        "(degrees), name (frames), text (text shapes), color (hex; text color or shape fill), opacity "
        "(0-1), frame (move into a frame id, or '' for the page).",
        {"updates": {"type": "array", "items": _schema({
            "id": _ID, "x": _POINT, "y": _POINT, "width": _POINT, "height": _POINT, "rotation": _POINT,
            "name": {"type": "string"}, "text": {"type": "string"}, "color": {"type": "string"},
            "opacity": _POINT, "frame": {"type": "string"}}, ["id"])}},
        ["updates"]),
    "delete_shapes": _tool("Delete shapes by id.", {"ids": _IDS}, ["ids"]),
    "focus": _tool(
        "Show shapes to the user: switch page if needed, select them and zoom to them.",
        {"ids": _IDS}, ["ids"]),
    "memory": _tool(
        "The user's long-term memory across projects. action list; add with text and category (about, "
        "taste, work, assets); correct with old (copied exactly) and new; forget with text (copied "
        "exactly). Save only lasting preferences the user states, not one-off requests.",
        {"action": {"type": "string", "enum": ["list", "add", "correct", "forget"]},
         "text": {"type": "string"}, "category": {"type": "string"},
         "old": {"type": "string"}, "new": {"type": "string"}},
        ["action"]),
    "skill": _tool(
        "Installed skills (instruction packs). action list; read with name (and optional path for a "
        "bundled file); save with name and instructions to store a reusable workflow the user wants "
        "to keep. When a task matches a skill, read it first and follow it.",
        {"action": {"type": "string", "enum": ["list", "read", "save"]}, "name": {"type": "string"},
         "path": {"type": "string"}, "instructions": {"type": "string"}},
        ["action"]),
    "custom_workflow": _tool(
        "Connect the user's own WaveSpeed model to a ComfyArt feature (image generation, edit, inpaint, "
        "upscale, video...). action rules: how to describe the model, read it first. list: each feature's "
        "markers, its saved files and the one in use. check: validate workflow ({model, fields, params} "
        "object) or file for a feature and report what to fix. install: save workflow as name for "
        "feature and use it (refused while check has errors). assign: give feature one of its files, or "
        "file \"\" to switch back to built in. There is no delete; the user removes files on disk.",
        {"action": {"type": "string", "enum": ["rules", "list", "check", "install", "assign"]},
         "feature": {"type": "string"}, "workflow": {"type": "object"}, "file": {"type": "string"},
         "name": {"type": "string"}},
        ["action"]),
}

_MODEL = {"type": "string", "description": "WaveSpeed model id from list_models for this tool's feature; omit for the default"}
for _name in load_config()["tool_features"]:
    if _name in SPECS:
        SPECS[_name]["inputSchema"]["properties"].setdefault("model", _MODEL)


async def _list_models(args: dict) -> dict:
    return {"features": await grouped_models(), "tool_features": load_config()["tool_features"]}


TOOLS: dict[str, dict] = {
    name: {"description": spec["description"], "inputSchema": spec["inputSchema"],
           "handler": _relay(name, **spec["relay"])}
    for name, spec in SPECS.items()
}
TOOLS["list_models"]["handler"] = _list_models
TOOLS["wait_generation"] = {
    "description": (
        "Wait for generations started by generate_image, generate_video and the edit tools. ids are the "
        "ids those tools returned. Returns status done with the placed shape ids and URLs of each "
        "result (or its error), or status running when timeout_s (max 170) passed first — then call "
        "it again."),
    "inputSchema": _schema({"ids": _IDS, "timeout_s": {"type": "integer"}}, ["ids"]),
    "handler": _wait_generation,
}
