"""Permissioned in-process tool sandbox over deterministic synthetic stores."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from voxwright.core import JSONValue
from voxwright.hashing import ChainLink, append_link, validate_chain
from voxwright.identifiers import Identifier


class PermissionDecision(str, Enum):
    ALLOW = "allow"
    CONFIRM = "confirm"
    DENY = "deny"


@dataclass(frozen=True, slots=True)
class PermissionPolicy:
    """Resolve exact tool rules with deny-by-default semantics."""

    rules: dict[Identifier, PermissionDecision]

    def __post_init__(self) -> None:
        object.__setattr__(self, "rules", dict(self.rules))

    def decide(self, tool_name: str | Identifier) -> PermissionDecision:
        name = tool_name if isinstance(tool_name, Identifier) else Identifier(tool_name)
        return self.rules.get(name, PermissionDecision.DENY)


@dataclass(slots=True)
class SideEffectLedger:
    """Tamper-evident ordered evidence for attempted and executed tools."""

    links: list[ChainLink]

    def __init__(self) -> None:
        self.links = []

    def record(
        self,
        tool_name: Identifier,
        arguments: dict[str, JSONValue],
        executed: bool,
        result: JSONValue,
    ) -> ChainLink:
        payload: dict[str, JSONValue] = {
            "tool_name": str(tool_name),
            "arguments": arguments,
            "executed": executed,
            "result": result,
        }
        link = append_link(self.links, payload)
        self.links.append(link)
        return link

    def validate(self) -> int | None:
        return validate_chain(self.links)


@dataclass(slots=True)
class SimulatedState:
    """Synthetic stores used by built-in tools; no external state is touched."""

    calendar: list[dict[str, JSONValue]]
    timers: list[dict[str, JSONValue]]
    messages: list[dict[str, JSONValue]]
    music: dict[str, JSONValue]
    home: dict[str, JSONValue]
    notes: list[dict[str, JSONValue]]

    @classmethod
    def empty(cls) -> SimulatedState:
        return cls([], [], [], {"playing": False}, {}, [])

    def calendar_create(self, title: str, hour: int) -> dict[str, JSONValue]:
        event = {"event_id": f"event-{len(self.calendar) + 1}", "title": title, "hour": hour}
        self.calendar.append(event)
        return dict(event)

    def timer_start(self, seconds: int) -> dict[str, JSONValue]:
        timer = {"timer_id": f"timer-{len(self.timers) + 1}", "seconds": seconds, "active": True}
        self.timers.append(timer)
        return dict(timer)

    def message_send(self, recipient: str, text: str) -> dict[str, JSONValue]:
        message = {
            "message_id": f"message-{len(self.messages) + 1}",
            "recipient": recipient,
            "text": text,
        }
        self.messages.append(message)
        return dict(message)

    def music_play(self, track: str) -> dict[str, JSONValue]:
        self.music.update({"playing": True, "track": track})
        return dict(self.music)

    def home_set(self, room: str, on: bool) -> dict[str, JSONValue]:
        self.home[room] = on
        return {"room": room, "on": on}

    def note_add(self, text: str) -> dict[str, JSONValue]:
        note = {"note_id": f"note-{len(self.notes) + 1}", "text": text}
        self.notes.append(note)
        return dict(note)


@dataclass(frozen=True, slots=True)
class ExecutionOutcome:
    executed: bool
    result: JSONValue
    permission: PermissionDecision
    prompt: str | None = None


@dataclass(slots=True)
class ToolSandbox:
    policy: PermissionPolicy
    state: SimulatedState
    ledger: SideEffectLedger
    grants: set[Identifier]

    def __init__(self, policy: PermissionPolicy, state: SimulatedState | None = None) -> None:
        self.policy = policy
        self.state = state if state is not None else SimulatedState.empty()
        self.ledger = SideEffectLedger()
        self.grants = set()

    def grant(self, tool_name: str | Identifier) -> None:
        name = tool_name if isinstance(tool_name, Identifier) else Identifier(tool_name)
        if self.policy.decide(name) is not PermissionDecision.CONFIRM:
            raise ValueError("session grant requires confirm permission")
        self.grants.add(name)

    def permission(self, tool_name: Identifier) -> ExecutionOutcome | None:
        decision = self.policy.decide(tool_name)
        if decision is PermissionDecision.DENY:
            self.ledger.record(tool_name, {}, False, "denied")
            return ExecutionOutcome(False, "denied", decision)
        if decision is PermissionDecision.CONFIRM and tool_name not in self.grants:
            return ExecutionOutcome(False, None, decision, f"Confirm tool {tool_name}")
        return None

    def execute(
        self, tool_name: str | Identifier, arguments: dict[str, JSONValue], *, dry_run: bool = False
    ) -> ExecutionOutcome:
        name = tool_name if isinstance(tool_name, Identifier) else Identifier(tool_name)
        blocked = self.permission(name)
        if blocked is not None:
            return blocked
        if dry_run:
            result: JSONValue = {"dry_run": True, "tool_name": str(name), "arguments": arguments}
            self.ledger.record(name, arguments, False, result)
            return ExecutionOutcome(False, result, self.policy.decide(name))
        handlers = {
            "calendar.create": lambda: self.state.calendar_create(
                str(arguments["title"]), int(arguments["hour"])
            ),
            "timer.start": lambda: self.state.timer_start(int(arguments["seconds"])),
            "messages.send": lambda: self.state.message_send(
                str(arguments["recipient"]), str(arguments["text"])
            ),
            "music.play": lambda: self.state.music_play(str(arguments["track"])),
            "home.set-light": lambda: self.state.home_set(
                str(arguments["room"]), bool(arguments["on"])
            ),
            "notes.add": lambda: self.state.note_add(str(arguments["text"])),
        }
        if str(name) not in handlers:
            raise ValueError(f"no simulated backend for tool: {name}")
        result = handlers[str(name)]()
        self.ledger.record(name, arguments, True, result)
        return ExecutionOutcome(True, result, self.policy.decide(name))
