import asyncio
import threading
from concurrent.futures import Future
from enum import Enum

from typing import List, Optional, Dict, Union

from .streaming import stream_chat_completion

class CompletionStatus(Enum):
    PENDING = 0
    RUNNING = 1
    FINISHED = 2
    ERROR = 3


def completion(
    prompt: Union[str, List[str], List[Dict[str, str]]],
    stop: Optional[str|List[str]] = None
):
    """
    :param prompt: A string, openai-style chat list, or list of strings
    :param stop: A stopping string, or list of stopping strings

    :return: A Completion object
    """

    completion = Completion(prompt, stop)
    completion.start()
    return completion


class Completion(Future):
    def __init__(self, prompt, stop=None):
        super().__init__()
        self.prompt = prompt
        self.status = CompletionStatus.PENDING

        self.stops = set()
        if stop:
            self.add_stop(stop)

        self._async_gen_func = stream_chat_completion  # The async generator function
        self.chunks = []  # List to accumulate string chunks
        self._thread = threading.Thread(target=self._start_loop)

    def start(self):
        if self.prompt is None:
            raise ValueError("Prompt not set")
        if isinstance(self.prompt, list) and isinstance(self.prompt[0], str):
            self.prompt = "".join([str(x) for x in self.prompt])

        self._thread.start()
        self.status = CompletionStatus.RUNNING

    def add_stop(self, stop):
        if isinstance(stop, str):
            self.stops.add(stop)
        else:
            self.stops.update(set(stop))

    def __str__(self):
        if self.status == CompletionStatus.PENDING:
            return "[     ]"
        elif self.status == CompletionStatus.RUNNING:
            return "[ ... ]"
        elif self.status == CompletionStatus.FINISHED:
            return "".join(self.chunks)

    def _start_loop(self):
        self._loop = asyncio.new_event_loop()  # Create a new event loop
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._run_generator())
        finally:
            self._loop.close()

    async def _run_generator(self):
        gen = self._async_gen_func(self.prompt)
        try:
            async for chunk in gen:
                self.chunks.append(chunk)

                prompt = "".join(self.chunks)
                for stop in self.stops:
                    if stop in prompt:

                        trailing = len(prompt) - prompt.rfind(stop)

                        for _ in range(trailing):
                            self.chunks[-1] = self.chunks[-1][:-1]
                            if self.chunks[-1] == "":
                                self.chunks.pop(-1)

                        self.status = CompletionStatus.FINISHED
                        break

                if self.status == CompletionStatus.FINISHED:
                    await gen.aclose()
                    break

            self.set_result(self.chunks)
            self.status = CompletionStatus.FINISHED

        except Exception as e:
            self.set_exception(e)
            self.status = CompletionStatus.ERROR


    def result(self, timeout=None):
        # Wait for the future to complete
        res = super().result(timeout=timeout)
        # Clean up the thread and event loop
        self._cleanup()
        return "".join(res)

    def _cleanup(self):
        self._thread.join()
        if not self._loop.is_closed():
            self._loop.close()



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
