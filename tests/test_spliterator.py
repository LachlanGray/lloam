import lloam
from lloam.completions import Completion
from lloam.spliterator import Spliterator
from lloam.spliterator import Segment, SegmentOpen, SegmentClose
import pytest

from tests.utils import tokens_and_generator


@pytest.fixture
def html_completion():
    name = "html_completion"
    prompt = "Could you write me a hello world blog post for an html template?"

    tokens, generator = tokens_and_generator(name, prompt)

    compl = Completion(prompt)
    compl._async_gen_func = generator

    return tokens, compl


# def test_nested_pairs(html_completion):
#     tokens, compl = html_completion

#     spliterator = Spliterator(compl)

#     spliterator.add_pair("code_block", r"```[^\n]*(?=\n)", "```", regex=True)
#     spliterator.add_pair("head", "<head>", "</head>", regex=False)
#     spliterator.add_pair("body", "<body>", "</body>", regex=False)
#     spliterator.add_pair("main", "<main>", "</main>", regex=False)

#     spliterator.completion.start()
#     spliterator.completion.result()
#     segments = spliterator.result()
#     segment_types = spliterator.segment_types


#     assert len(segments) == 17, f"Expected 17 segments but got {len(segments)}"
#     assert len(segment_types) == 17, f"Expected 17 segment types but got {len(segment_types)}"

#     segment_stack = []
#     for seg in segment_types:
#         if isinstance(seg, SegmentOpen):
#             segment_stack.append(seg)
#         elif isinstance(seg, SegmentClose):
#             segment = segment_stack.pop()
#             segment_open = segment_stack.pop()
#             prev_segment = segment_stack.pop()

#             assert seg.segment_open == segment_open
#             assert segment_open.prev_segment == prev_segment

#             if segment_stack == []:
#                 segment_stack.append(segment)

#         else:
#             assert isinstance(seg, Segment)
#             segment_stack.append(seg)


def test_nested_pairs(html_completion):
    tokens, compl = html_completion

    spliterator = Spliterator(compl)

    spliterator.add_pair("paragraph", "<p>", "</p>", regex=False)

    spliterator.completion.start()


    expected = [
        'Welcome to my first blog post. This is a simple HTML template to help you get started with blogging. In this post, I wanted to take a moment to say hello to the world and share my excitement about writing.',
        'Whether you are a seasoned blogger or just starting out, I hope you find joy in expressing your thoughts and sharing your ideas with others. Happy blogging!',
        '&copy; 2023 My Blog. All rights reserved.'
    ]
    for s, x in zip(spliterator.stream(), expected):
        assert s == x







if __name__ == "__main__":
    tokens, compl = html_completion()

    test_nested_pairs((tokens, compl))
