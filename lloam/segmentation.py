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
        # asyncio.run_coroutine_threadsafe(self._filter(), self.completion.completions_loop)
        self.completion.start()
        asyncio.run(self._filter())

    def result(self):
        self.completion.result()
        return self.segments

    def _add_segment(self, segment_type):
        # self.segments.append([])
        self.segments.append("")
        self.segment_types.append(segment_type)


    async def _filter(self):
        open_q = [SegmentOpen(self.segment_types[0], None)]
        close_q = []

        async for tok in self.completion.astream():
            self.segments[-1] += tok

            matched = False

            # if a pattern is waiting to close
            if not close_q == []:
                matched = close_q[-1].search(self.segments[-1])

            if matched:
                _ = close_q.pop()
                segment_open = open_q.pop()

                start, end = matched.start(), matched.end()

                chars = self.segments.pop()

                self.segments[-1] += chars[:start]

                self._add_segment(SegmentClose(segment_open))
                self.segments[-1] += chars[start:end]

                self._add_segment(segment_open.prev_segment)

                # self.segments.append(chars[end:])
                self.segments[-1] += chars[end:]

                continue

            if not self.allow_nesting and len(open_q) > 1:
                continue

            for pair_type, pair in self.pairs.items():
                opening, ending = pair
                close_q.append(ending)

                matched = opening.search(self.segments[-1])
                if matched:
                    start, end = matched.start(), matched.end()

                    chars = self.segments.pop()

                    if len(self.segments) == 0:
                        self.segments.append(chars[:start])
                    else:
                        self.segments[-1] += chars[:start]

                    segment = Segment(pair_type)
                    segment_open = SegmentOpen(segment, open_q[-1].segment)

                    self._add_segment(segment_open)
                    self.segments[-1] += chars[start:end]
                    open_q.append(segment_open)

                    self._add_segment(segment)
                    self.segments.append(chars[end:])

                    break

            if matched:
                continue



    def add_pair(self, name, open_pattern, close_pattern, regex=False):

        if not regex:
            open_pattern = re.escape(open_pattern)
            close_pattern = re.escape(close_pattern)

        self.pairs[name] = (re.compile(open_pattern), re.compile(close_pattern))




