import asyncio
import threading
from concurrent.futures import Future
from enum import Enum
import re

from typing import List, Optional, Dict, Union

from .streaming import stream_chat_completion

class CompletionStatus(Enum):
    PENDING = 0
    RUNNING = 1
    FINISHED = 2
    ERROR = 3


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

class Completion(Future):
    """
    Accumulates/manages streamed tokens for one completion.
    Manages stopping conditions.
    """
    completions_loop = None
    completions_thread = None


    def __init__(self, prompt, stop=None, model="gpt-4o-mini", temperature=0.9):
        super().__init__()
        self.prompt = prompt
        self.status = CompletionStatus.PENDING
        self.model = model
        self.temperature = temperature

        self.stops = set()
        if stop:
            self.add_stop(stop)

        self._async_gen_func = stream_chat_completion
        self.chunks = []

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
        if isinstance(self.prompt, list) and isinstance(self.prompt[0], str):
            self.prompt = "".join([str(x) for x in self.prompt])


        self.status = CompletionStatus.RUNNING
        asyncio.run_coroutine_threadsafe(self._run_generator(), self.completions_loop)


    def add_stop(self, stop):
        if isinstance(stop, str):
            self.stops.add(stop)
        else:
            self.stops.update(set(stop))

    def __str__(self):
        return self.result()


    def visual_status(self):
        if self.status == CompletionStatus.PENDING:
            return "[     ]"
        elif self.status == CompletionStatus.RUNNING:
            return "[ ... ]"
        elif self.status == CompletionStatus.FINISHED:
            return "".join(self.chunks)


    async def _run_generator(self):
        gen = self._async_gen_func(self.prompt, model=self.model, temperature=self.temperature)
        try:
            async for chunk in gen:

                self._refresh_status(chunk)

                if self.status == CompletionStatus.FINISHED:
                    await gen.aclose()
                    break

                self.chunks.append(chunk)

            self.status = CompletionStatus.FINISHED
            self.set_result("".join(self.chunks))

        except Exception as e:
            self.set_exception(e)
            self.status = CompletionStatus.ERROR


    def _refresh_status(self, chunk):
        prompt = "".join(self.chunks)
        for stop in self.stops:

            if stop in chunk:
                leading = chunk.find(stop)

                if leading > 0:
                    chunk = chunk[:leading]
                    self.chunks.append(chunk)

                self.status = CompletionStatus.FINISHED
                break

            if stop in prompt:
                trailing = len(prompt) - prompt.rfind(stop)

                for _ in range(trailing):
                    self.chunks[-1] = self.chunks[-1][:-1]
                    if self.chunks[-1] == "":
                        self.chunks.pop(-1)

                self.status = CompletionStatus.FINISHED
                break

    def findall(self, pattern):
        self.result()
        return re.findall(pattern, "".join(self.chunks))

    @property
    def text(self):
        text = super().result()
        return text


    @property
    def backticks(self):
        pattern = r'`(.*?)`'
        return self.findall(pattern)



if __name__ == "__main__":


    # messages
    messages = [
        {"role": "system", "content": "You speak in haikus"},
        {"role": "user", "content": "What is loam?"}
    ]
    loam = completion(messages)


    # strings
    prompt = "Billy Joel said: Sing us a song you're "
    lyric = completion(prompt, stop=[".", "!", "\n"])


    # chunks
    chunks = ["The capi", "tal of", " France ", "is", " "]
    capitol = completion(chunks, stop=".")


    print(loam.result())
    print(lyric.result())
    print(capitol.result())
