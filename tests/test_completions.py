import lloam
import pytest
import re

from tests.utils import tokens_and_generator

from lloam.completions import Completion

failure_msg = lambda original, expected, actual: f"Original ----------\n{original}\n\nExpected ----------\n{expected}\n\nGot ----------\n{actual}"


@pytest.fixture
def code_sample():
    name = "code_sample"
    prompt = "Could you write me a fibonacci function in python? Please annotate the code blocks with ```python."

    return prompt, *tokens_and_generator(name, prompt)



def test_stop_literal(code_sample):
    prompt, tokens, generator = code_sample

    compl = Completion(prompt, include_stops=False)
    compl._async_gen_func = generator

    stop = "```"
    compl.add_stop(stop, regex=False)

    compl.start()

    expected = "".join(tokens).split(stop)[0]

    assert expected == compl.result(), failure_msg("".join(tokens), expected, compl.result())


def test_stop_literal_include_stop(code_sample):
    prompt, tokens, generator = code_sample

    compl = Completion(prompt, include_stops=True)
    compl._async_gen_func = generator

    stop = "```"
    compl.add_stop(stop, regex=False)

    compl.start()

    expected = "".join(tokens).split(stop)[0] + "```"

    assert expected == compl.result(), failure_msg("".join(tokens), expected, compl.result())



def test_stop_regex(code_sample):
    prompt, tokens, generator = code_sample

    compl = Completion(prompt, include_stops=False)
    compl._async_gen_func = generator

    stop = r"```\s+"
    compl.add_stop(stop, regex=True)

    compl.start()

    parts = "".join(tokens).split("```")
    expected = parts[0] + "```" + parts[1]

    assert expected == compl.result(), failure_msg("".join(tokens), expected, compl.result())


def test_stop_regex_include_stop(code_sample):
    prompt, tokens, generator = code_sample

    compl = Completion(prompt, include_stops=True)
    compl._async_gen_func = generator

    stop = r"```\s+"
    compl.add_stop(stop, regex=True)

    compl.start()

    parts = "".join(tokens).split("```")
    expected = parts[0] + "```" + parts[1] + "```\n\n"

    assert expected == compl.result(), failure_msg("".join(tokens), expected, compl.result())


