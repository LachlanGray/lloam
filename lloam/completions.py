import asyncio
import threading
from concurrent.futures import Future

from streaming import stream_chat_completion


class Completion(Future):
    def __init__(self, prompt):
        super().__init__()
        self.prompt = prompt
        self.finished = False

        self._async_gen_func = stream_chat_completion  # The async generator function
        self.chunks = []  # List to accumulate string chunks
        self._loop = asyncio.new_event_loop()  # Create a new event loop
        self._thread = threading.Thread(target=self._start_loop)
        self._thread.start()

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
            self.finished = True
        except Exception as e:
            self.set_exception(e)

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


