from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional


@dataclass
class ProviderStatus:
    available: bool
    version: str = ""
    logged_in: Optional[bool] = None
    detail: str = ""


@dataclass
class ProviderCaps:
    stateful: bool = True
    tools: str = "mcp"
    attachments: bool = True


@dataclass
class TurnRequest:
    chat_id: str
    user_text: str
    resume_token: Optional[str] = None
    history: Optional[list[dict]] = None
    mcp_endpoint: str = ""
    allowed_tools: list[str] = field(default_factory=list)
    attachments: list[dict] = field(default_factory=list)
    model: str = ""
    comfy_mcp_argv: list[str] = field(default_factory=list)
    lang: str = ""  # UI language of the sender ("zh" / "en"), "" if unknown
    # #391: run identity / mode. Ownership defaults to the local single user.
    goal_text: str = ""                # #383: the user's own words (user_text may carry memory/context)
    run_mode: str = "interactive"      # interactive | unattended (schedules, patrols: #388)
    resume_run_id: str = ""            # continue a paused run from its server-side checkpoint
    lease_owner: str = ""              # DB lease already taken by the API for this resume
    owner_id: str = "local"
    workspace_id: str = "local"
    project_id: str = "local"   # #391: on agent_runs + run logs (locked naming)


@dataclass
class BotEvent:
    t: str
    text: str = ""
    name: str = ""
    input: Optional[dict] = None
    detail: str = ""
    id: str = ""
    is_error: bool = False


@dataclass
class TurnResult:
    resume_token: Optional[str] = None
    error: str = ""
    aborted: bool = False
    usage: Optional[dict] = None
    run: Optional[dict] = None  # #391: {"run_id", "status", "stop": {...}, "self_check": {...}}


class TurnHandle:
    def __init__(self) -> None:
        self.process: Any = None
        self.stop_requested = False


EmitFn = Callable[[BotEvent], Awaitable[None]]


class AgentProvider(ABC):
    id: str = ""
    label: str = ""
    supports_branch: bool = True

    @abstractmethod
    async def probe(self) -> ProviderStatus: ...

    @abstractmethod
    def capabilities(self) -> ProviderCaps: ...

    def clear_probe_cache(self) -> None:
        # #247: 「重新检测」asks /bot/status?refresh=1 so the next probe is not a stale 60s hit
        if hasattr(self, "_probe_cache"):
            self._probe_cache = None

    async def list_models(self) -> list[str]:
        return []

    def model_options(self) -> list[dict]:
        return []

    @abstractmethod
    async def send(self, turn: TurnRequest, emit: EmitFn,
                   handle: TurnHandle) -> TurnResult: ...

    @abstractmethod
    async def stop(self, handle: TurnHandle) -> None: ...


_REGISTRY: dict[str, AgentProvider] = {}


def register_provider(provider: AgentProvider) -> None:
    _REGISTRY[provider.id] = provider


def get_provider(provider_id: str) -> Optional[AgentProvider]:
    return _REGISTRY.get(provider_id)


def list_providers() -> list[AgentProvider]:
    return list(_REGISTRY.values())
