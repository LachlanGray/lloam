from typing import AsyncGenerator, Dict, List, Optional

from openai import AsyncOpenAI


async def stream_chat_completion(
    messages: List[Dict[str, str]],
    model: str = "gpt-4o-mini",
    temperature: float = 0.9,
    stop: Optional[List[str]] = None,
    api_key: Optional[str] = None,
    backend_params: Optional[Dict] = None,
) -> AsyncGenerator[str, None]:
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
        messages = [{"role": "assistant", "content": messages}]

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
        try:
            async for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    yield chunk.choices[0].delta.content
        finally:
            await stream.close()
    finally:
        await client.close()
        del client
