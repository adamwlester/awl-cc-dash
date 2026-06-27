"""Serialization helpers shared by the sidecar and its drivers.

Converts Claude Agent SDK message objects into JSON-serializable dicts whose
shape the frontend understands (a top-level `type` plus, for assistant/user
messages, a `content` list of blocks that each carry their own `type`).
"""

from datetime import datetime
from typing import Any
import json

# SDK message class name -> the top-level event `type` the frontend switches on.
_MESSAGE_TYPE_MAP = {
    "AssistantMessage": "assistant",
    "UserMessage": "user",
    "SystemMessage": "system",
    "ResultMessage": "result",
    "StreamEvent": "stream_event",
    "RateLimitEvent": "rate_limit",
}

# SDK content-block dataclasses don't carry a `type` field in their __dict__, but the
# frontend switches each block on block.type. Map the class name to the type the
# renderer expects so text / tool-use / tool-result / thinking blocks actually render.
_BLOCK_TYPE_MAP = {
    "TextBlock": "text",
    "ThinkingBlock": "thinking",
    "ToolUseBlock": "tool_use",
    "ToolResultBlock": "tool_result",
    # Server-side tool blocks (e.g. web search) — same shapes the renderer expects.
    "ServerToolUseBlock": "tool_use",
    "ServerToolResultBlock": "tool_result",
}


def serialize_message(message: Any) -> dict[str, Any]:
    """Convert an SDK message to a JSON-serializable dict with a stable `type`."""
    result: dict[str, Any] = {"timestamp": datetime.now().isoformat()}
    msg_type = type(message).__name__
    result["sdk_type"] = msg_type
    result["type"] = _MESSAGE_TYPE_MAP.get(msg_type, msg_type.lower())

    for key, value in getattr(message, "__dict__", {}).items():
        if key.startswith("_"):
            continue
        result[key] = safe_serialize(value)

    return result


def safe_serialize(value: Any, depth: int = 0) -> Any:
    if depth > 5:
        return str(value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {k: safe_serialize(v, depth + 1) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe_serialize(v, depth + 1) for v in value]
    if hasattr(value, "__dict__"):
        data = {k: safe_serialize(v, depth + 1) for k, v in value.__dict__.items()
                if not k.startswith("_")}
        # Ensure SDK content blocks expose the `type` the frontend keys off.
        block_type = _BLOCK_TYPE_MAP.get(type(value).__name__)
        if block_type and "type" not in data:
            data["type"] = block_type
        return data
    try:
        json.dumps(value)
        return value
    except (TypeError, ValueError):
        return str(value)
