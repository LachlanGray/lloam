from typing import Any, AsyncGenerator, Dict, List, Optional


def _coerce_to_anthropic_messages(
    messages: List[Dict[str, Any]] | str,
) -> tuple[List[Dict[str, Any]], Optional[str]]:
    if isinstance(messages, str):
        return [{"role": "user", "content": messages}], None

    anthropic_messages: List[Dict[str, Any]] = []
    system_parts: List[str] = []

    for msg in messages:
        if not isinstance(msg, dict):
            anthropic_messages.append({"role": "user", "content": str(msg)})
            continue

        role = str(msg.get("role", "user")).lower()
        content = msg.get("content", "")

        if role == "system":
            system_parts.append(str(content))
            continue

        if role not in {"user", "assistant"}:
            role = "user"

        anthropic_messages.append({"role": role, "content": content})

    system = "\n\n".join([part for part in system_parts if part != ""]) or None
    return anthropic_messages, system


def _extract_text_from_event(event: Any) -> Optional[str]:
    event_type = getattr(event, "type", None)
    if event_type is None and isinstance(event, dict):
        event_type = event.get("type")

    if event_type == "content_block_delta":
        delta = getattr(event, "delta", None)
        if delta is None and isinstance(event, dict):
            delta = event.get("delta")

        if delta is None:
            return None

        delta_type = getattr(delta, "type", None)
        if delta_type is None and isinstance(delta, dict):
            delta_type = delta.get("type")

        if delta_type == "text_delta":
            text = getattr(delta, "text", None)
            if text is None and isinstance(delta, dict):
                text = delta.get("text")
            return text

    if event_type == "text":
        text = getattr(event, "text", None)
        if text is None and isinstance(event, dict):
            text = event.get("text")
        return text

    return None


async def _maybe_aclose(obj: Any) -> None:
    aclose = getattr(obj, "aclose", None)
    if callable(aclose):
        await aclose()
        return

    close = getattr(obj, "close", None)
    if callable(close):
        result = close()
        if hasattr(result, "__await__"):
            await result


async def stream_chat_completion(
    messages: List[Dict[str, Any]],
    model: str = "claude-3-5-sonnet-latest",
    temperature: float = 0.9,
    stop: Optional[List[str]] = None,
    api_key: Optional[str] = None,
    backend_params: Optional[Dict] = None,
) -> AsyncGenerator[str, None]:
    from anthropic import AsyncAnthropic

    params = backend_params or {}

    client_kwargs = dict(params.get("client", {}))
    request_kwargs = dict(params.get("request", {}))

    if api_key is not None and "api_key" not in client_kwargs:
        client_kwargs["api_key"] = api_key

    for key in (
        "api_key",
        "base_url",
        "timeout",
        "max_retries",
        "default_headers",
        "default_query",
        "http_client",
    ):
        if key in params and key not in client_kwargs:
            client_kwargs[key] = params[key]

    client = AsyncAnthropic(**client_kwargs)

    anthropic_messages, system = _coerce_to_anthropic_messages(messages)

    max_tokens = request_kwargs.pop("max_tokens", params.get("max_tokens", 1024))
    stop_sequences = request_kwargs.pop("stop_sequences", stop)

    call_kwargs: Dict[str, Any] = {
        "model": model,
        "messages": anthropic_messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stop_sequences": stop_sequences,
        "stream": True,
    }
    if system is not None and "system" not in request_kwargs:
        call_kwargs["system"] = system

    call_kwargs.update(request_kwargs)
    call_kwargs["stream"] = True

    stream = None
    try:
        stream = await client.messages.create(**call_kwargs)
        async for event in stream:
            text = _extract_text_from_event(event)
            if text:
                yield text
    finally:
        if stream is not None:
            await _maybe_aclose(stream)
        await _maybe_aclose(client)
