import json
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

        if role in {"system", "developer"}:
            system_parts.append(str(content))
            continue

        if role == "tool":
            anthropic_messages.append({"role": "user", "content": content})
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
) -> AsyncGenerator[Dict[str, Any], None]:
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
    content_blocks: Dict[int, Dict[str, Any]] = {}
    finish_reason = None
    try:
        stream = await client.messages.create(**call_kwargs)
        async for event in stream:
            event_type = getattr(event, "type", None)
            if event_type is None and isinstance(event, dict):
                event_type = event.get("type")

            block_index = getattr(event, "index", None)
            if block_index is None and isinstance(event, dict):
                block_index = event.get("index")

            if event_type == "content_block_start":
                block = getattr(event, "content_block", None)
                if block is None and isinstance(event, dict):
                    block = event.get("content_block")

                block_type = getattr(block, "type", None)
                if block_type is None and isinstance(block, dict):
                    block_type = block.get("type")

                if block_type == "tool_use":
                    tool_id = getattr(block, "id", None)
                    if tool_id is None and isinstance(block, dict):
                        tool_id = block.get("id")
                    tool_name = getattr(block, "name", None)
                    if tool_name is None and isinstance(block, dict):
                        tool_name = block.get("name")
                    tool_input = getattr(block, "input", None)
                    if tool_input is None and isinstance(block, dict):
                        tool_input = block.get("input")

                    args_text = ""
                    if tool_input is not None:
                        args_text = json.dumps(tool_input)

                    content_blocks[int(block_index or 0)] = {
                        "type": "tool_use",
                        "id": tool_id or f"tool_call_{int(block_index or 0)}",
                        "name": tool_name,
                        "arguments_text": args_text,
                    }

                    yield {
                        "type": "tool_call_start",
                        "id": content_blocks[int(block_index or 0)]["id"],
                        "name": tool_name,
                    }
                    if args_text:
                        yield {
                            "type": "tool_call_delta",
                            "id": content_blocks[int(block_index or 0)]["id"],
                            "arguments_text": args_text,
                        }
                else:
                    content_blocks[int(block_index or 0)] = {"type": block_type or "text"}
                continue

            if event_type == "content_block_delta":
                delta = getattr(event, "delta", None)
                if delta is None and isinstance(event, dict):
                    delta = event.get("delta")

                delta_type = getattr(delta, "type", None)
                if delta_type is None and isinstance(delta, dict):
                    delta_type = delta.get("type")

                if delta_type == "text_delta":
                    text = getattr(delta, "text", None)
                    if text is None and isinstance(delta, dict):
                        text = delta.get("text")
                    if text:
                        yield {"type": "text_delta", "text": text}
                    continue

                if delta_type == "input_json_delta":
                    partial = getattr(delta, "partial_json", None)
                    if partial is None and isinstance(delta, dict):
                        partial = delta.get("partial_json")

                    state = content_blocks.get(int(block_index or 0))
                    if state and state.get("type") == "tool_use" and partial:
                        state["arguments_text"] = state.get("arguments_text", "") + partial
                        yield {
                            "type": "tool_call_delta",
                            "id": state["id"],
                            "arguments_text": partial,
                        }
                    continue

                text = _extract_text_from_event(event)
                if text:
                    yield {"type": "text_delta", "text": text}
                continue

            if event_type == "content_block_stop":
                state = content_blocks.get(int(block_index or 0))
                if state and state.get("type") == "tool_use":
                    arguments_text = state.get("arguments_text", "")
                    arguments = None
                    if arguments_text:
                        try:
                            arguments = json.loads(arguments_text)
                        except json.JSONDecodeError:
                            arguments = None
                    yield {
                        "type": "tool_call_end",
                        "id": state["id"],
                        "name": state.get("name"),
                        "arguments_text": arguments_text,
                        "arguments": arguments,
                    }
                continue

            if event_type == "message_delta":
                delta = getattr(event, "delta", None)
                if delta is None and isinstance(event, dict):
                    delta = event.get("delta")
                finish_reason = getattr(delta, "stop_reason", None)
                if finish_reason is None and isinstance(delta, dict):
                    finish_reason = delta.get("stop_reason")
                continue
        yield {"type": "message_end", "finish_reason": finish_reason}
    finally:
        if stream is not None:
            await _maybe_aclose(stream)
        await _maybe_aclose(client)
