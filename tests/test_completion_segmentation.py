import lloam
from lloam.completions import Completion
from lloam.segmentation import Segmentation
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


def test_nested_pairs(html_completion):
    tokens, compl = html_completion

    segmentation = Segmentation(compl)

    segmentation.add_pair("code_block", r"```[^\n]*(?=\n)", "```", regex=True)
    segmentation.add_pair("head", "<head>", "</head>", regex=False)
    segmentation.add_pair("body", "<body>", "</body>", regex=False)
    segmentation.add_pair("main", "<main>", "</main>", regex=False)

    segmentation.start()
    segments = segmentation.result()
    segment_types = segmentation.segment_types

    assert len(segments) == len(segment_types), f"{len(segments)} segments but {len(segment_types)} segment types"



if __name__ == "__main__":
    tokens, compl = html_completion()

    segmentation = Segmentation(compl, allow_nesting=True)

    segmentation.add_pair("code_block", r"```[^\n]*(?=\n)", "```", regex=True)
    segmentation.add_pair("head", "<head>", "</head>", regex=False)
    segmentation.add_pair("body", "<body>", "</body>", regex=False)
    segmentation.add_pair("main", "<main>", "</main>", regex=False)

    segmentation.start()
    segments = segmentation.result()
    segment_types = segmentation.segment_types

    for s in segments:
        print("----------------------------------------")
        print(s)

    print(len(segments))
    print(len(segmentation.segment_types))

    print("done")
