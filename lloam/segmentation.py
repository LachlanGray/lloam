from .completions import Completion, CompletionStatus
from enum import Enum
from dataclasses import dataclass
import re
import asyncio
from queue import Queue


@dataclass
class Segment:
    segment_type: str | None

@dataclass
class SegmentOpen:
    segment: Segment
    prev_segment: Segment | None

@dataclass
class SegmentClose:
    segment_open: SegmentOpen


class Spliterator:
    def __init__(self, completion:Completion, allow_nesting=True):
        self.completion = completion
        self.allow_nesting = allow_nesting

        self.pairs = {}

        self.segments = [""]
        self.segment_types = [Segment(None)]

        self.stream_q = Queue()
        self.astream_q = asyncio.Queue()


    def result(self):
        self._ensure_completion_stream()

        self.completion.result()
        return self.segments

    def _ensure_completion_stream(self):
        if self.completion.status == CompletionStatus.PENDING:
            assert False, f"Spliterator.completion.start() must be called before Spliterator.start()"

    def _add_segment(self, segment_type):
        self.segments.append("")
        self.segment_types.append(segment_type)

    def stream(self, capture:list[str]|str=None):
        """
        capture: type or list of pair types to include in stream. If None, will use all defined pairs.
        """
        self._ensure_completion_stream()

        if capture is None:
            # capture all pairs
            capture = [p for p in self.pairs.keys()]

        asyncio.run(self._filter())

        while True:
            if self.stream_q.empty():
                continue

            segment_type, segment = self.stream_q.get()

            if segment_type is None:
                break

            if segment_type in capture:
                yield segment


    async def astream(self, capture:list[str]|str=None):
        """
        capture: type or list of pair types to include in stream. If None, will use all defined pairs.
        """
        self._ensure_completion_stream()

        if capture is None:
            # capture all pairs
            capture = [p for p in self.pairs.keys()]

        asyncio.create_task(self._filter())

        while True:

            segment_type, segment = await self.astream_q.get()

            if segment_type is None:
                break

            if segment_type in capture:
                yield segment


    async def _filter(self):
    # def _filter(self):
        open_q = [SegmentOpen(self.segment_types[0], None)]
        close_q = []

        async for tok in self.completion.astream():
        # for tok in self.completion.stream():
            self.segments[-1] += tok

            if len(close_q) > 0:
                close_match = close_q[-1].search(self.segments[-1])
            else:
                close_match = False

            if close_match:
                segment_open = open_q.pop()
                _ = close_q.pop()
                start, end = close_match.start(), close_match.end()
                chars = self.segments.pop()

                self.segments.append(chars[:start])

                self.stream_q.put((segment_open.segment.segment_type, chars[:start]))
                await self.astream_q.put((segment_open.segment.segment_type, chars[:start]))

                self._add_segment(SegmentClose(segment_open))
                self.segments[-1] += chars[start:end]
                self._add_segment(segment_open.prev_segment)
                self.segments[-1] += chars[end:]



            for segment_type, pair in self.pairs.items():
                opening, ending = pair

                open_match = opening.search(self.segments[-1])
                if open_match:
                    start, end = open_match.start(), open_match.end()
                    chars = self.segments.pop()

                    self.segments.append(chars[:start])

                    segment = Segment(segment_type)
                    open_segment = SegmentOpen(segment, open_q[-1].segment)
                    self._add_segment(open_segment)
                    self.segments[-1] += (chars[start:end])
                    self._add_segment(segment)
                    self.segments[-1] += (chars[end:])

                    open_q.append(open_segment)
                    close_q.append(ending)

                    break


        self.stream_q.put((None, None))
        await self.astream_q.put((None, None))

    def add_pair(self, name, open_pattern, close_pattern, regex=False):

        if not regex:
            open_pattern = re.escape(open_pattern)
            close_pattern = re.escape(close_pattern)

        self.pairs[name] = (re.compile(open_pattern), re.compile(close_pattern))


