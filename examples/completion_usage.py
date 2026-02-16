import asyncio
import os
import subprocess
import json

from lloam.completions import Completion


OPENAI_MODEL = "openai/gpt-4o-mini"
ANTHROPIC_MODEL = "anthropic/claude-haiku-4-5-20251001"


def api_key_for_model(model_slug):
    if model_slug.startswith("openai/"):
        return os.getenv("OPENAI_API_KEY")
    if model_slug.startswith("anthropic/"):
        return os.getenv("ANTHROPIC_API_KEY")
    return None


def backend_params_for_model(model_slug):
    key = api_key_for_model(model_slug)
    if model_slug.startswith("openai/"):
        return {
            "api_key": key,
            "request": {
                "max_tokens": 120,
            },
        }
    if model_slug.startswith("anthropic/"):
        return {
            "request": {
                "max_tokens": 120,
            },
        }
    return {"api_key": key}


def anthropic_preflight():
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return False, "ANTHROPIC_API_KEY is not set"

    model_id = ANTHROPIC_MODEL.split("/", 1)[1]
    cmd = [
        "curl",
        "--max-time",
        "20",
        "https://api.anthropic.com/v1/messages",
        "-H",
        f"x-api-key: {api_key}",
        "-H",
        "anthropic-version: 2023-06-01",
        "-H",
        "content-type: application/json",
        "-d",
        json.dumps(
            {
                "model": model_id,
                "max_tokens": 1,
                "messages": [{"role": "user", "content": "ping"}],
            }
        ),
    ]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
    except Exception as e:
        return False, f"Could not run Anthropic preflight: {type(e).__name__}: {e}"

    body = (out.stdout or "").strip()
    if out.returncode != 0:
        return False, f"Anthropic preflight failed to connect ({body or out.stderr.strip()})"

    try:
        payload = json.loads(body)
    except Exception:
        return False, f"Unexpected Anthropic preflight response: {body[:240]}"

    error = payload.get("error")
    if isinstance(error, dict):
        msg = error.get("message", "")
        typ = error.get("type", "error")
        if "credit balance is too low" in msg.lower():
            return False, "Anthropic billing issue: credit balance is too low."
        return False, f"Anthropic preflight {typ}: {msg}"

    return True, "ok"


def run_result_example(model_slug, messages):
    print(f"# result() -> {model_slug} ##########")
    params = backend_params_for_model(model_slug)
    if model_slug.startswith("anthropic/"):
        # Diagnostic: run non-stream mode for result() to isolate stream-path failures.
        params = {**params, "stream": False}
    completion = Completion(
        messages,
        model=model_slug,
        temperature=0.2,
        backend_params=params,
    )
    completion.start()
    print(completion.result())
    print()


def run_stream_example(model_slug, messages):
    print(f"# stream() -> {model_slug} ##########")
    completion = Completion(
        messages,
        model=model_slug,
        temperature=0.2,
        backend_params=backend_params_for_model(model_slug),
    )
    completion.start()
    for token in completion:
        print(token, end="", flush=True)
    # Surface background generation errors (stream() alone won't raise them).
    completion.result()
    print("\n")


async def run_astream_example(model_slug, messages):
    print(f"# astream() + await -> {model_slug} ##########")
    completion = Completion(
        messages,
        model=model_slug,
        temperature=0.2,
        backend_params=backend_params_for_model(model_slug),
    )
    completion.start()

    async for token in completion.astream(period=0.02):
        print(token, end="", flush=True)
    await completion
    print("\n")


def run_parallel_example(models, messages):
    print("# parallel completions ##########")
    completions = [
        Completion(
            messages,
            model=model,
            temperature=0.2,
            backend_params=backend_params_for_model(model),
        )
        for model in models
    ]
    for completion in completions:
        completion.start()

    for completion in completions:
        print(f"[{completion.model}]")
        try:
            print(completion.result())
        except Exception as e:
            print(f"ERROR parallel result() for {completion.model}: {type(e).__name__}: {e}")
        print()


def main():
    chat_messages = [
        {"role": "system", "content": "Answer in 1 short paragraph."},
        {"role": "user", "content": "What makes good soil for vegetables?"},
    ]

    configured_models = []
    if os.getenv("OPENAI_API_KEY"):
        configured_models.append(OPENAI_MODEL)
    if os.getenv("ANTHROPIC_API_KEY"):
        ok, reason = anthropic_preflight()
        if ok:
            configured_models.append(ANTHROPIC_MODEL)
        else:
            print(f"Skipping {ANTHROPIC_MODEL}: {reason}\n")

    if not configured_models:
        print("Set OPENAI_API_KEY and/or ANTHROPIC_API_KEY to run this example.")
        return

    successful_models = []
    for model in configured_models:
        model_had_success = False

        try:
            run_result_example(model, chat_messages)
        except Exception as e:
            print(f"ERROR result() for {model}: {type(e).__name__}: {e}\n")
        else:
            model_had_success = True

        try:
            run_stream_example(model, chat_messages)
        except Exception as e:
            print(f"ERROR stream() for {model}: {type(e).__name__}: {e}\n")
        else:
            model_had_success = True

        try:
            asyncio.run(run_astream_example(model, chat_messages))
        except Exception as e:
            print(f"ERROR astream() for {model}: {type(e).__name__}: {e}\n")
        else:
            model_had_success = True

        if model_had_success:
            successful_models.append(model)

    if len(successful_models) > 1:
        run_parallel_example(successful_models, chat_messages)


if __name__ == "__main__":
    main()
