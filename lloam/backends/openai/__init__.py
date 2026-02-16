import json
from typing import Any, AsyncGenerator, Dict, List, Optional

from openai import AsyncOpenAI


async def stream_chat_completion(
    messages: List[Dict[str, str]],
    model: str = "gpt-4o-mini",
    temperature: float = 0.9,
    stop: Optional[List[str]] = None,
    api_key: Optional[str] = None,
    backend_params: Optional[Dict] = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    params = backend_params or {}

    client_kwargs = dict(params.get("client", {}))
    request_kwargs = dict(params.get("request", {}))

    if api_key is not None and "api_key" not in client_kwargs:
        client_kwargs["api_key"] = api_key

    for key in (
        "api_key",
        "base_url",
        "organization",
        "project",
        "timeout",
        "max_retries",
        "default_headers",
        "default_query",
    ):
        if key in params and key not in client_kwargs:
            client_kwargs[key] = params[key]

    client = AsyncOpenAI(**client_kwargs)

    if isinstance(messages, str):
        messages = [{"role": "user", "content": messages}]

    call_kwargs = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "stop": stop,
        "stream": True,
    }
    call_kwargs.update(request_kwargs)
    call_kwargs["stream"] = True

    try:
        stream = await client.chat.completions.create(**call_kwargs)
        tool_states: Dict[int, Dict[str, Any]] = {}
        finish_reason = None
        try:
            async for chunk in stream:
                if not chunk.choices:
                    continue

                choice = chunk.choices[0]
                delta = choice.delta

                if getattr(delta, "content", None) is not None:
                    yield {"type": "text_delta", "text": delta.content}

                tool_calls = getattr(delta, "tool_calls", None) or []
                for tc in tool_calls:
                    idx = tc.index if tc.index is not None else 0
                    state = tool_states.get(idx)
                    if state is None:
                        state = {
                            "id": tc.id or f"tool_call_{idx}",
                            "name": None,
                            "arguments": "",
                            "started": False,
                        }
                        tool_states[idx] = state

                    if tc.id:
                        state["id"] = tc.id

                    fn = getattr(tc, "function", None)
                    fn_name = getattr(fn, "name", None) if fn is not None else None
                    fn_args = getattr(fn, "arguments", None) if fn is not None else None

                    if fn_name:
                        state["name"] = fn_name
                    if not state["started"]:
                        yield {
                            "type": "tool_call_start",
                            "id": state["id"],
                            "name": state["name"],
                        }
                        state["started"] = True

                    if fn_args:
                        state["arguments"] += fn_args
                        yield {
                            "type": "tool_call_delta",
                            "id": state["id"],
                            "arguments_text": fn_args,
                        }

                choice_finish_reason = getattr(choice, "finish_reason", None)
                if choice_finish_reason is not None:
                    finish_reason = choice_finish_reason
        finally:
            await stream.close()

        for idx in sorted(tool_states.keys()):
            state = tool_states[idx]
            arguments_text = state["arguments"]
            arguments = None
            if arguments_text:
                try:
                    arguments = json.loads(arguments_text)
                except json.JSONDecodeError:
                    arguments = None
            yield {
                "type": "tool_call_end",
                "id": state["id"],
                "name": state["name"],
                "arguments_text": arguments_text,
                "arguments": arguments,
            }

        yield {"type": "message_end", "finish_reason": finish_reason}
    finally:
        await client.close()
        del client
