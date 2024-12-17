import lloam
from lloam.completions import Completion
from lloam.segmentation import Spliterator
from lloam.segmentation import Segment, SegmentOpen, SegmentClose
import pytest

from tests.utils import tokens_and_generator


# @pytest.fixture
def html_completion():
    name = "html_completion"
    prompt = "Could you write me a hello world blog post for an html template?"

    tokens, generator = tokens_and_generator(name, prompt)

    compl = Completion(prompt)
    compl._async_gen_func = generator

    return tokens, compl


def test_nested_pairs(html_completion):
    tokens, compl = html_completion

    segmentation = Spliterator(compl)

    segmentation.add_pair("code_block", r"```[^\n]*(?=\n)", "```", regex=True)
    segmentation.add_pair("head", "<head>", "</head>", regex=False)
    segmentation.add_pair("body", "<body>", "</body>", regex=False)
    segmentation.add_pair("main", "<main>", "</main>", regex=False)

    segmentation.start()
    segments = segmentation.result()
    segment_types = segmentation.segment_types


    assert len(segments) == 17, f"Expected 17 segments but got {len(segments)}"
    assert len(segment_types) == 17, f"Expected 17 segment types but got {len(segment_types)}"

    segment_stack = []
    for seg in segment_types:
        if isinstance(seg, SegmentOpen):
            segment_stack.append(seg)
        elif isinstance(seg, SegmentClose):
            segment = segment_stack.pop()
            segment_open = segment_stack.pop()
            prev_segment = segment_stack.pop()

            assert seg.segment_open == segment_open
            assert segment_open.prev_segment == prev_segment

            if segment_stack == []:
                segment_stack.append(segment)

        else:
            assert isinstance(seg, Segment)
            segment_stack.append(seg)


def test_spliterator_stream(html_completion):
    tokens, compl = html_completion




if __name__ == "__main__":
    tokens, compl = html_completion()

    test_spliterator_stream((tokens, compl))
