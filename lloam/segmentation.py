from .completions import Completion
from enum import Enum
from dataclasses import dataclass
import re
import asyncio


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


class Segmentation:
    def __init__(self, completion:Completion, allow_nesting=True):
        self.completion = completion
        self.allow_nesting = allow_nesting

        self.pairs = {}

        self.segments = [""]
        self.segment_types = [Segment(None)]


    def start(self):
        self.completion.start()
        asyncio.run_coroutine_threadsafe(self._filter(), self.completion.completions_loop)

    def result(self):
        self.completion.result()
        return self.segments

    def _add_segment(self, segment_type):
        self.segments.append("")
        self.segment_types.append(segment_type)


    async def _filter(self):
        open_q = [SegmentOpen(self.segment_types[0], None)]
        close_q = []

        async for tok in self.completion.astream():
            self.segments[-1] += tok

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


            if len(close_q) > 1:
                close_match = close_q[-1].search(self.segments[-1])
            else:
                close_match = False

            if close_match:
                segment_open = open_q.pop()
                _ = close_q.pop()
                start, end = close_match.start(), close_match.end()
                chars = self.segments.pop()

                self.segments.append(chars[:start])

                self._add_segment(SegmentClose(segment_open))
                self.segments[-1] += chars[start:end]
                self._add_segment(segment_open.prev_segment)
                self.segments[-1] += chars[end:]


    def add_pair(self, name, open_pattern, close_pattern, regex=False):

        if not regex:
            open_pattern = re.escape(open_pattern)
            close_pattern = re.escape(close_pattern)

        self.pairs[name] = (re.compile(open_pattern), re.compile(close_pattern))


