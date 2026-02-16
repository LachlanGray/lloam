import lloam
import pytest
import re

from tests.utils import tokens_and_generator

from lloam.completions import Completion
import asyncio
import threading
import time
from types import SimpleNamespace
from lloam.completions import CompletionStatus
from lloam.backends import openai as openai_backend

failure_msg = lambda original, expected, actual: f"Original ----------\n{original}\n\nExpected ----------\n{expected}\n\nGot ----------\n{actual}"


@pytest.fixture
def code_sample():
    name = "code_sample"
    prompt = "Could you write me a fibonacci function in python? Please annotate the code blocks with ```python."

    return prompt, *tokens_and_generator(name, prompt)



def test_stop_literal(code_sample):
    prompt, tokens, generator = code_sample

    compl = Completion(prompt, include_stops=False)
    compl._async_gen_func = generator

    stop = "```"
    compl.add_stop(stop, regex=False)

    compl.start()

    expected = "".join(tokens).split(stop)[0]

    assert expected == compl.result(), failure_msg("".join(tokens), expected, compl.result())


def test_stop_literal_include_stop(code_sample):
    prompt, tokens, generator = code_sample

    compl = Completion(prompt, include_stops=True)
    compl._async_gen_func = generator

    stop = "```"
    compl.add_stop(stop, regex=False)

    compl.start()

    expected = "".join(tokens).split(stop)[0] + "```"

    assert expected == compl.result(), failure_msg("".join(tokens), expected, compl.result())



def test_stop_regex(code_sample):
    prompt, tokens, generator = code_sample

    compl = Completion(prompt, include_stops=False)
    compl._async_gen_func = generator

    stop = r"```\s+"
    compl.add_stop(stop, regex=True)

    compl.start()

    parts = "".join(tokens).split("```")
    expected = parts[0] + "```" + parts[1]

    assert expected == compl.result(), failure_msg("".join(tokens), expected, compl.result())


def test_stop_regex_include_stop(code_sample):
    prompt, tokens, generator = code_sample

    compl = Completion(prompt, include_stops=True)
    compl._async_gen_func = generator

    stop = r"```\s+"
    compl.add_stop(stop, regex=True)

    compl.start()

    parts = "".join(tokens).split("```")
    expected = parts[0] + "```" + parts[1] + "```\n\n"

    assert expected == compl.result(), failure_msg("".join(tokens), expected, compl.result())


def test_stop_trim_across_chunk_boundaries():
    # Stop pattern spans chunks: 'cd' across 'c' and 'd'
    tokens = ["ab", "c", "d", "ef"]

    async def generator(*args, **kwargs):
        for t in tokens:
            yield t

    # exclude stop
    compl = Completion("irrelevant", include_stops=False)
    compl._async_gen_func = generator
    compl.add_stop("cd", regex=False)
    compl.start()
    assert compl.result() == "ab", failure_msg("".join(tokens), "ab", compl.result())

    # include stop
    compl2 = Completion("irrelevant", include_stops=True)
    compl2._async_gen_func = generator
    compl2.add_stop("cd", regex=False)
    compl2.start()
    assert compl2.result() == "abcd", failure_msg("".join(tokens), "abcd", compl2.result())


def test_pause_resume_stream_blocks_and_resumes():
    # Slow generator to allow coordination
    tokens = ["1", "2", "3", "4", "5"]

    async def generator(*args, **kwargs):
        for t in tokens:
            await asyncio.sleep(0.05)
            yield t

    compl = Completion("irrelevant")
    compl._async_gen_func = generator

    compl.start()

    consumed = []

    def consume():
        for c in compl.stream():
            consumed.append(c)

    # Pause before starting consumer to ensure it blocks
    compl.pause()

    t = threading.Thread(target=consume)
    t.start()

    # Allow producer to run while consumer is paused
    time.sleep(0.25)
    assert consumed == [], f"Consumer should be paused; got {consumed}"

    # Resume and ensure all tokens are delivered
    compl.resume()
    t.join(timeout=2)
    assert consumed == tokens, f"Expected {tokens}, got {consumed}"


def test_stop_condition_status_transition_observable_with_patch():
    # Create a stop and patch _refresh_status to hold STOP_CONDITION long enough to observe
    tokens = ["one two ", "STOP", " end"]

    async def generator(*args, **kwargs):
        for t in tokens:
            yield t

    compl = Completion("irrelevant", include_stops=False)
    compl._async_gen_func = generator
    compl.add_stop("STOP", regex=False)

    stop_seen = threading.Event()

    orig = compl._refresh_status

    def patched_refresh(chunk):
        orig(chunk)
        if compl.status == CompletionStatus.STOP_CONDITION:
            stop_seen.set()
            time.sleep(0.1)  # widen the observation window

    compl._refresh_status = patched_refresh

    compl.start()

    # We should observe STOP_CONDITION before FINISHED
    assert stop_seen.wait(timeout=2), "STOP_CONDITION was not observed in time"

    # Final state should be FINISHED with trimmed result (exclude stop)
    assert compl.result() == "one two ", failure_msg("".join(tokens), "one two ", compl.result())

def test_stream_replay_multiple_calls(code_sample):
    prompt, tokens, generator = code_sample

    compl = Completion(prompt)
    compl._async_gen_func = generator
    compl.start()
    compl.result()  # ensure generation completed

    expected = "".join(tokens)

    s1 = "".join([c for c in compl.stream()])
    s2 = "".join([c for c in compl.stream()])
    s3 = "".join([c for c in compl])  # iterator protocol

    assert s1 == expected, failure_msg(expected, expected, s1)
    assert s2 == expected, failure_msg(expected, expected, s2)
    assert s3 == expected, failure_msg(expected, expected, s3)


def test_stream_from_index(code_sample):
    prompt, tokens, generator = code_sample

    compl = Completion(prompt)
    compl._async_gen_func = generator
    compl.start()
    compl.result()

    # pick a safe index within range
    idx = 3 if len(compl.chunks) > 3 else 0
    expected_rest = "".join(compl.chunks[idx:])

    got_rest = "".join([c for c in compl.stream(from_index=idx)])
    got_rest_iter = "".join([c for c in compl.iter_from(idx)])

    assert got_rest == expected_rest, failure_msg(expected_rest, expected_rest, got_rest)
    assert got_rest_iter == expected_rest, failure_msg(expected_rest, expected_rest, got_rest_iter)


def test_astream_replay_and_from_index(code_sample):
    prompt, tokens, generator = code_sample

    compl = Completion(prompt)
    compl._async_gen_func = generator
    compl.start()

    async def run():
        # wait until completed
        await compl

        expected = "".join(tokens)

        out = []
        async for c in compl:
            out.append(c)
        assert "".join(out) == expected, failure_msg(expected, expected, "".join(out))

        idx = 5 if len(compl.chunks) > 5 else 0
        expected_rest = "".join(compl.chunks[idx:])
        out2 = []
        async for c in compl.aiter_from(idx):
            out2.append(c)
        assert "".join(out2) == expected_rest, failure_msg(expected_rest, expected_rest, "".join(out2))

    asyncio.run(run())


def test_completion_normalizes_mixed_message_prompts():
    captured = {}

    async def generator(messages, *args, **kwargs):
        captured["messages"] = messages
        yield "ok"

    prompt = [
        {"role": "system", "content": "rules"},
        "Hello there",
        {"foo": "bar"},
    ]
    compl = Completion(prompt)
    compl._async_gen_func = generator
    compl.start()

    assert compl.result() == "ok"
    assert captured["messages"] == [
        {"role": "system", "content": "rules"},
        {"role": "user", "content": "Hello there"},
        "foo: bar",
    ]


def test_openai_backend_treats_string_prompt_as_user(monkeypatch):
    recorded = {}

    class FakeStream:
        def __init__(self):
            self._done = False
            self.closed = False

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self._done:
                raise StopAsyncIteration
            self._done = True
            return SimpleNamespace(
                choices=[SimpleNamespace(delta=SimpleNamespace(content="token"))]
            )

        async def close(self):
            self.closed = True

    class FakeCompletions:
        def __init__(self):
            self.stream = FakeStream()

        async def create(self, **kwargs):
            recorded["create_kwargs"] = kwargs
            return self.stream

    class FakeClient:
        def __init__(self, **kwargs):
            recorded["client_kwargs"] = kwargs
            self.chat = SimpleNamespace(completions=FakeCompletions())
            self.closed = False

        async def close(self):
            self.closed = True

    monkeypatch.setattr(openai_backend, "AsyncOpenAI", FakeClient)

    async def run():
        chunks = []
        async for chunk in openai_backend.stream_chat_completion("hello"):
            chunks.append(chunk)
        return chunks

    chunks = asyncio.run(run())

    assert chunks == ["token"]
    assert recorded["create_kwargs"]["messages"] == [
        {"role": "user", "content": "hello"}
    ]
