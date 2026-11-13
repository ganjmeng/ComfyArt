from server import PromptServer

from .. import chat_store
from . import banner, bot_tools, canvas, media
from ._context import BOT_CHAT_ID, PROJECT


async def _server_info(_args: dict) -> dict:
    chat = chat_store.get_chat(BOT_CHAT_ID.get()) if BOT_CHAT_ID.get() else None
    return {
        "app": "ComfyArt",
        "project": PROJECT.get() or None,
        "chat": {"id": chat["id"], "provider": chat["provider"], "run_mode": chat["run_mode"]} if chat else None,
        "comfyui_queue_remaining": PromptServer.instance.prompt_queue.get_tasks_remaining(),
    }


TOOLS: dict[str, dict] = {
    "server_info": {
        "description": "ComfyArt status: the open project, this chat and how many ComfyUI jobs are queued.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        "handler": _server_info,
    },
}
TOOLS.update(canvas.TOOLS)
TOOLS.update(media.TOOLS)
TOOLS.update(banner.TOOLS)
TOOLS.update(bot_tools.TOOLS)
