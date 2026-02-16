from typing import Any, Dict, List


ALLOWED_ROLES = {"system", "developer", "user", "assistant", "tool"}


def normalize_messages(messages: str | List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if isinstance(messages, str):
        return [{"role": "user", "content": messages}]

    if not isinstance(messages, list):
        raise TypeError("messages must be a string or a list of message dicts")

    normalized: List[Dict[str, Any]] = []
    for i, message in enumerate(messages):
        if not isinstance(message, dict):
            raise ValueError(f"Message at index {i} must be a dict")
        if "role" not in message:
            raise ValueError(f"Message at index {i} is missing 'role'")
        if "content" not in message:
            raise ValueError(f"Message at index {i} is missing 'content'")

        role = message["role"]
        if not isinstance(role, str):
            raise ValueError(f"Message at index {i} has a non-string role")
        role = role.strip().lower()

        if role not in ALLOWED_ROLES:
            allowed = ", ".join(sorted(ALLOWED_ROLES))
            raise ValueError(
                f"Message at index {i} has unsupported role '{role}'. Allowed roles: {allowed}"
            )

        content = message["content"]
        if not isinstance(content, (str, list)):
            raise ValueError(
                f"Message at index {i} has invalid content type {type(content).__name__}; "
                "expected str or list"
            )

        msg = dict(message)
        msg["role"] = role
        msg["content"] = content
        normalized.append(msg)

    return normalized
