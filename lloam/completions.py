import asyncio
import threading
from concurrent.futures import Future
from enum import Enum
import re

from typing import List, Optional, Dict, Union

from .streaming import stream_chat_completion

class CompletionStatus(Enum):
    PENDING = 0
    RUNNING = 1     # stream in progress
    FINALIZING = 2  # strop condition met
    FINISHED = 3
    ERROR = 4


def completion(
    prompt: Union[str, List[str], List[Dict[str, str]]],
    stop: Optional[str|List[str]] = None,
    model: str = "gpt-4o-mini"
):
    """
    :param prompt: A string, openai-style chat list, or list of strings
    :param stop: A stopping string, or list of stopping strings

    :return: A Completion object
    """

    completion = Completion(prompt, stop)
    completion.start()
    return completion

# TODO: Rename to RunningCompletion, have it return Completion which inherits from str

class Completion:
    """
    Accumulates/manages streamed tokens for one completion.
    Manages stopping conditions.
    """
    completions_loop = None
    completions_thread = None


    def __init__(self, prompt, stop=None, model="gpt-4o-mini", temperature=0.7):
        super().__init__()
        self.prompt = prompt
        self.status = CompletionStatus.PENDING
        self.model = model
        self.temperature = temperature

        self._done_callbacks = []
        self._exception = None
        self._result = None
        self._done_event = threading.Event()
        self._callback_lock = threading.Lock()

        self.stops = []
        if stop:
            self.add_stop(stop)

        self._async_gen_func = stream_chat_completion
        self.chunks = []
        self._chunks_lock = threading.Lock()

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
        if self.prompt is None:
            raise ValueError("Prompt not set")

        # A completion can exist in its own prompt (there's a reason). 
        # In that case, use proceeding prompts to generate the completion
        if isinstance(self.prompt, list):
            if self in self.prompt:
                self.prompt = self.prompt[:self.prompt.index(self)].copy()

            any_dicts = any(isinstance(p, dict) for p in self.prompt)
            all_dicts = all(isinstance(p, dict) for p in self.prompt)
            are_messages = all("role" in p for p in self.prompt if isinstance(p, dict))

            if any_dicts and are_messages:
                self.prompt = [
                    {"role":"user", "content":p} if not isinstance(p, dict) 
                    else p
                    for p in self.prompt 
                ]

            elif any_dicts and not are_messages:
                self.prompt = [
                    p["content"] if isinstance(p, dict) 
                    else p
                    for p in self.prompt 
                ]

            else:
                self.prompt = "".join([str(x) for x in self.prompt])

        self.status = CompletionStatus.RUNNING
        asyncio.run_coroutine_threadsafe(self._run_generator(), self.completions_loop)


    def stream(self):
        stream_index = 0

        while self.status != CompletionStatus.FINISHED:
            if stream_index < len(self.chunks):
                yield self.chunks[stream_index]
                stream_index += 1


    def add_stop(self, stop):
        if isinstance(stop, str):
            if len(stop) == 1:
                stop = re.escape(stop)

            self.stops.append(re.compile(stop))
        elif isinstance(stop, list):
            for stop in stop:
                self.add_stop(stop)
        else:
            raise ValueError("Stop must be a strings or list of strings")

    def __str__(self):
        return self.result()


    def visual_status(self):
        if self.status == CompletionStatus.PENDING:
            return "[     ]"
        elif self.status == CompletionStatus.RUNNING or self.status == CompletionStatus.FINALIZING:
            return "[ ... ]"
        elif self.status == CompletionStatus.FINISHED:
            with self._chunks_lock:
                return "".join(self.chunks)


    async def _run_generator(self):
        gen = self._async_gen_func(
            self.prompt, model=self.model, temperature=self.temperature
        )
        try:
            async for chunk in gen:

                self._refresh_status(chunk)

                # close generator ASAP to save tokens
                if self.status == CompletionStatus.FINALIZING:
                    await gen.aclose()
                    break

                with self._chunks_lock:
                    self.chunks.append(chunk)

            self.status = CompletionStatus.FINALIZING
            with self._chunks_lock:
                result = "".join(self.chunks)

            self.set_result(result)
            self.status = CompletionStatus.FINISHED


        except Exception as e:
            self.set_exception(e)
            self.status = CompletionStatus.ERROR


    def _refresh_status(self, chunk):
        # checks if stopping conditions have been met if so,
        # trim completion to that point and update the status

        prompt = "".join(self.chunks)
        for stop in self.stops:

            if stop.match(chunk):
                match_idx = stop.match(chunk).start()
                leading = len(chunk[:match_idx])

                if leading > 0:
                    chunk = chunk[:leading]
                    with self._chunks_lock:
                        self.chunks.append(chunk)

                self.status = CompletionStatus.FINALIZING
                break

            # terrible
            if stop.match(prompt):
                trailing = len(prompt) - stop.match(prompt).end()

                for _ in range(trailing):
                    self.chunks[-1] = self.chunks[-1][:-1]
                    if self.chunks[-1] == "":
                        self.chunks.pop(-1)

                self.status = CompletionStatus.FINALIZING
                break

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
        self._invoke_callbacks()

    def set_exception(self, exception):
        self._exception = exception
        self._done_event.set()
        self._invoke_callbacks()

    def result(self, timeout=None):
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


