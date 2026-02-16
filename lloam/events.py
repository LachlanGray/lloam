from typing import Any, Dict


def text_delta_event(text: str) -> Dict[str, Any]:
    return {"type": "text_delta", "text": text}


def normalize_backend_event(item: Any) -> Dict[str, Any]:
    if isinstance(item, str):
        return text_delta_event(item)

    if isinstance(item, dict):
        event_type = item.get("type")
        if not isinstance(event_type, str) or event_type == "":
            raise ValueError("Backend event dict must contain non-empty string 'type'")
        return item

    raise TypeError(
        f"Backend stream yielded unsupported type {type(item).__name__}; "
        "expected str or event dict"
    )
