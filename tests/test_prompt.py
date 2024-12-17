import lloam
import pytest
from utils import tokens_and_generator
import re


# @pytest.fixture
def say_hello():
    name = "say_hello"
    prompt = "hello there!"

    _, f = tokens_and_generator(name, prompt)
    return f

# @pytest.fixture
def blog_html():
    name = "html_completion"

    _, f = tokens_and_generator(name, None)

    return f



def test_prompt_decorator(say_hello, blog_html):
    gen1 = say_hello
    gen2 = blog_html

    @lloam.prompt(start=False)
    def my_test(arg1, kwarg1=10):
        """
        The arg is {arg1}. The kwarg is {kwarg1}.

        This is a [[hole]].

        This is a [[<p>[spliterator_hole]</p>]].

        This is a [[r<.*>[regex_spliterator_hole]r</.*>]].

        This is a [[r<.*>[regex_split_stop]r</.*>]</header>].

        """


    result = my_test("bees")

    # make sure args were subbed/stringed
    assert result.prompt_vars == {'arg1': 'bees', 'kwarg1': '10'}
    assert result.args == {'arg1': 'bees', 'kwarg1': 10}

    assert result.prompt_holes["hole"].completion == result.hole
    assert result.prompt_holes["spliterator_hole"].spliterator == result.spliterator_hole


    result.prompt_holes["hole"].completion._async_gen_func = gen1
    result.prompt_holes["spliterator_hole"].completion._async_gen_func = gen2
    result.prompt_holes["regex_spliterator_hole"].completion._async_gen_func = gen2
    result.prompt_holes["regex_split_stop"].completion._async_gen_func = gen2

    result.start()

    assert result.hole.result() == "Hello! How can I assist you today?"


    # spliterator
    assert result.spliterator_hole.pairs == {'capture': (re.compile('<p>'), re.compile('</p>'))}

    expected = [
        "Welcome to my first blog post. This is a simple HTML template to help you get started with blogging. In this post, I wanted to take a moment to say hello to the world and share my excitement about writing.",
        "Whether you are a seasoned blogger or just starting out, I hope you find joy in expressing your thoughts and sharing your ideas with others. Happy blogging!",
        "&copy; 2023 My Blog. All rights reserved."
    ]

    for i, x in enumerate(result.spliterator_hole.stream()):
        assert x == expected[i], f"should split between p tags. expected:\n\n{expected[i]}\n\ngot:\n\n{x}"


    # regex spliterator
    regex_splits = [x for x in result.regex_spliterator_hole.stream()]
    assert len(regex_splits) == 14


    # regex spliterator with stop (all ptags until <header> tag)
    stopped_regex_splits = [x for x in result.regex_split_stop.stream()]
    assert len(stopped_regex_splits) == 4



def test_member_prompt():
    pass


if __name__ == "__main__":

    f1 = say_hello()
    f2 = blog_html()
    test_prompt_decorator(f1, f2)


