import asyncio
import threading
from concurrent.futures import Future
from enum import Enum

from streaming import stream_chat_completion

class CompletionStatus(Enum):
    PENDING = 0
    RUNNING = 1
    FINISHED = 2
    ERROR = 3


class Completion(Future):
    def __init__(self, prompt):
        super().__init__()
        self.prompt = prompt
        self.status = CompletionStatus.PENDING

        self._async_gen_func = stream_chat_completion  # The async generator function
        self.chunks = []  # List to accumulate string chunks
        self._loop = asyncio.new_event_loop()  # Create a new event loop
        self._thread = threading.Thread(target=self._start_loop)

    def start(self):
        if self.prompt is None:
            raise ValueError("Prompt not set")
        if isinstance(self.prompt, list) and isinstance(self.prompt[0], str):
            self.prompt = "".join([str(x) for x in self.prompt])

        self._thread.start()
        self.status = CompletionStatus.RUNNING

    def __str__(self):
        return "".join(self.chunks)

    def _start_loop(self):
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._run_generator())
        finally:
            self._loop.close()

    async def _run_generator(self):
        try:
            async for chunk in self._async_gen_func(self.prompt):
                self.chunks.append(chunk)
            self.set_result(self.chunks)  # Set the final result
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

    test = "who am I speaking to"
    completion = Completion(test)
    
    while not completion.finished:
        print(completion.chunks)

    result = completion.result()
    print(result)


