import asyncio
import threading
from queue import Queue
from enum import Enum
import re

from typing import List, Optional, Dict, Union

from .backends import get_backend

class CompletionStatus(Enum):
    PENDING = 0
    INITIALIZING = 1
    RUNNING = 2     # stream in progress
    STOP_CONDITION = 3  # stop condition met
    FINALIZING = 4
    FINISHED = 5
    ERROR = 6


def completion(
    prompt: Union[str, List[str], List[Dict[str, str]]],
    model: str = "openai/gpt-4o-mini",
    stops: Optional[List[str]] = [],
    regex_stops: Optional[List[str]] = [],
    include_stops: bool = False,
    backend_params: Optional[Dict] = None,
):
    """
    Generates a completion using a language model.

    :param prompt: A string, openai-style chat list, or list of strings
    :param model: Model slug in the format "<backend>/<model>", e.g. "openai/gpt-4o-mini"
    :param stops: A list of strings that will terminate the completion early
    :param regex_stops: A list of rexexp strings that will terminate the completion early
    :param include_stops: Whether characters that trigger a stopping condition should go in the final result

    :return: A Completion object
    """

    completion = Completion(
        prompt,
        include_stops=include_stops,
        model=model,
        backend_params=backend_params,
    )

    for stop in stops:
        completion.add_stop(stop)
    for stop in regex_stops:
        completion.add_stop(stop, regex=True)

    completion.start()
    return completion


class Completion:
    """
    Accumulates/manages streamed tokens for one completion.
    Manages stopping conditions.
    """
    completions_loop = None
    completions_thread = None


    def __init__(
            self,
            prompt,
            include_stops=False,
            model="openai/gpt-4o-mini",
            temperature=0.7,
            backend_params: Optional[Dict] = None,
    ):
        super().__init__()
        self.prompt = prompt
        self.status = CompletionStatus.PENDING
        self.model = model
        self.temperature = temperature
        self.backend_params = backend_params or {}

        self._done_callbacks = []
        self._exception = None
        self._result = None
        self._done_event = threading.Event()
        self._callback_lock = threading.Lock()

        self.stops = []
        self.include_stops = include_stops

        self._async_gen_func, self._provider_model = get_backend(self.model)

        self.chunks = []
        self._chunks_lock = threading.Lock()
        self._chunks_cv = threading.Condition(self._chunks_lock)
        self._paused = False
        self._pause_event = threading.Event()
        self._pause_event.set()  # start in resumed state

        self.stream_q = Queue()

        self._initialize_event_loop_in_thread()


    @classmethod
    def _initialize_event_loop_in_thread(cls):
        if cls.completions_loop is not None:
            return

        def run_loop():
            cls.completions_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(cls.completions_loop)
            cls.completions_loop.run_forever()

        cls.completions_thread = threading.Thread(target=run_loop, daemon=True)
        cls.completions_thread.start()

        # Wait for the loop to be created
        while cls.completions_loop is None:
            pass


    def start(self):

        self.status = CompletionStatus.INITIALIZING
        if self.prompt is None:
            raise ValueError("Prompt not set")

        # A completion can exist in its own prompt (there's a reason). 
        # In that case, use proceeding prompts to generate the completion
        if isinstance(self.prompt, list):
            if self in self.prompt:
                self.prompt = self.prompt[:self.prompt.index(self)].copy()

            any_dicts = any(isinstance(p, dict) for p in self.prompt)
            any_lists = any(isinstance(p, list) for p in self.prompt)
            # all_dicts = all(isinstance(p, dict) for p in self.prompt)
            # are_messages = all("role" in p for p in self.prompt if isinstance(p, dict))


            if any_lists:
                # unpack any list in prompt
                new_prompt = []
                for p in self.prompt:
                    if isinstance(p, list):
                        new_prompt.extend(p)
                    else:
                        new_prompt.append(p)

                self.prompt = new_prompt


            # if prompt is mixture of oai messages and strings, strings are cast to user messages
            if any_dicts:
                new_prompt = []
                for p in self.prompt:
                    if isinstance(p, dict):
                        if "role" in p:
                            new_prompt.append(p)
                        else:
                            new_prompt.append("\n".join([f"{k}: {v}" for k, v in p.items()]))
                    else:
                        new_prompt.append({
                            "role": "user",
                            "content": str(p)
                        })

                self.prompt = new_prompt

            else:
                self.prompt = "".join([str(x) for x in self.prompt])

        self.status = CompletionStatus.RUNNING
        asyncio.run_coroutine_threadsafe(self._run_generator(), self.completions_loop)


    def stream(self, from_index: int = 0):
        """
        :param from_index: Start yielding from this chunk index (replays prior chunks).
        :return: A generator that yields completion chunks as they are generated
        """

        if self.status == CompletionStatus.PENDING:
            raise Exception(f"Completion.start() must be called before streaming")

        idx = max(0, int(from_index))
        while True:
            with self._chunks_lock:
                # Yield any chunks we haven't returned yet
                if idx < len(self.chunks):
                    chunk = self.chunks[idx]
                    idx += 1
                else:
                    # If finished and no new data, exit
                    if self.done():
                        break
                    # Wait for more chunks
                    self._chunks_cv.wait(timeout=0.5)
                    continue

            # Respect pause (read-side only)
            self._pause_event.wait()
            yield chunk

    async def astream(self, period=0.1, from_index: int = 0):
        idx = max(0, int(from_index))
        while True:
            # Drain any available chunks
            with self._chunks_lock:
                if idx < len(self.chunks):
                    chunk = self.chunks[idx]
                    idx += 1
                else:
                    # If no new chunks, decide whether to stop or poll again
                    if self.done():
                        break
                    chunk = None

            if chunk is None:
                await asyncio.sleep(period)
                continue

            # Respect pause (read-side only)
            while not self._pause_event.is_set():
                await asyncio.sleep(period)

            yield chunk

    # Iterator protocol helpers
    def __iter__(self):
        """Enable: for chunk in completion: ... (replay from start)."""
        return self.stream()

    def iter_from(self, index: int = 0):
        """Create a sync iterator starting from a given chunk index."""
        return self.stream(from_index=index)

    def __aiter__(self):
        """Enable: async for chunk in completion: ... (replay from start)."""
        return self.astream()

    def aiter_from(self, index: int = 0, period: float = 0.1):
        """Create an async iterator starting from a given chunk index."""
        return self.astream(period=period, from_index=index)


    def add_stop(self, stop, regex=False):
        """
        :param stop: A string or list of strings to stop completion
        :param regex: If True, stop is treated as a regex
        """
        if isinstance(stop, list):
            for stop in stop:
                self.add_stop(stop)

        elif isinstance(stop, str):
            if not regex:
                stop = re.escape(stop)

            self.stops.append(re.compile(stop))

        else:
            raise ValueError("Stop must be a strings or list of strings")

    def __str__(self):
        return self.result()


    async def _run_generator(self):
        gen = self._async_gen_func(
            self.prompt,
            model=self._provider_model,
            temperature=self.temperature,
            backend_params=self.backend_params,
        )
        try:
            async for chunk in gen:

                self._refresh_status(chunk)

                # close generator ASAP to save tokens
                if self.status == CompletionStatus.STOP_CONDITION:
                    await gen.aclose()
                    break


            self.status = CompletionStatus.FINALIZING
            with self._chunks_lock:
                result = "".join(self.chunks)

            self.stream_q.put(None)

            self.set_result(result)
            self.status = CompletionStatus.FINISHED


        except Exception as e:
            self.set_exception(e)
            self.status = CompletionStatus.ERROR


    def _refresh_status(self, chunk):
        # checks if stopping conditions have been met if so,
        # trim completion to that point and update the status
        new_chunk = chunk

        with self._chunks_lock:
            prompt = "".join(self.chunks + [chunk])
            stop_triggered = False
            for stop in self.stops:
                matched = stop.search(prompt)

                if matched:
                    self.status = CompletionStatus.STOP_CONDITION

                    start, end = matched.start(), matched.end()

                    if self.include_stops:
                        to_remove = len(prompt[end:])
                    else:
                        to_remove = len(prompt[start:])

                    while to_remove > 0:
                        if new_chunk == "":
                            if self.chunks and self.chunks[-1] == "":
                                self.chunks.pop()
                            if self.chunks:
                                self.chunks[-1] = self.chunks[-1][:-1]
                        else:
                            new_chunk = new_chunk[:-1]

                        to_remove -= 1

                    stop_triggered = True
                    break

            # Append the (possibly trimmed) chunk
            self.chunks.append(new_chunk)

            # Notify any waiting replay streams
            self._chunks_cv.notify_all()

        # Maintain existing queue behavior for any legacy consumers
        self.stream_q.put(new_chunk)
        if stop_triggered:
            self.stream_q.put(None)         # sentinel for queue consumers

    def add_done_callback(self, fn):
        with self._callback_lock:
            done = self._done_event.is_set()
            if not done:
                self._done_callbacks.append(fn)

        if done:
            fn()

    def set_result(self, result):
        self._result = result
        self._done_event.set()
        with self._chunks_lock:
            self._chunks_cv.notify_all()
        self._invoke_callbacks()

    def set_exception(self, exception):
        self._exception = exception
        self._done_event.set()
        with self._chunks_lock:
            self._chunks_cv.notify_all()
        self._invoke_callbacks()

    def pause(self):
        """Pause replaying to stream()/astream() consumers (does not pause generation)."""
        self._paused = True
        self._pause_event.clear()

    def resume(self):
        """Resume replaying to stream()/astream() consumers."""
        self._paused = False
        self._pause_event.set()

    def result(self, timeout=None):

        if self.status == CompletionStatus.PENDING:
            raise Exception(f"Completion.start() must be called before result is obtainable")

        if not self._done_event.wait(timeout):
            raise TimeoutError()
        if self._exception:
            raise self._exception
        with self._chunks_lock:
            return "".join(self.chunks)

    def _invoke_callbacks(self):
        with self._callback_lock:
            callbacks = self._done_callbacks
            self._done_callbacks = []

        for fn in callbacks:
            try:
                fn()
            except Exception as e:
                print(f"Exception in callback: {e}")
                raise e

    def done(self):
        return self._done_event.is_set()

    def findall(self, pattern):
        self.result()
        return re.findall(pattern, "".join(self.chunks))

    def current_index(self) -> int:
        """Return the current number of chunks accumulated (for resume points)."""
        with self._chunks_lock:
            return len(self.chunks)

    def __await__(self):
        async def wait_for_result():
            while not self.done():
                await asyncio.sleep(0.1)
            return self.result()
        return wait_for_result().__await__()
