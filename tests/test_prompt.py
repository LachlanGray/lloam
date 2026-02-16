import lloam
import pytest

from tests.utils import tokens_and_generator

@pytest.fixture
def say_hello():
    name = "say_hello"
    prompt = "hello there!"

    _, f = tokens_and_generator(name, prompt)
    return f

def test_prompt_decorator(say_hello):
    gen1 = say_hello

    @lloam.prompt(start=False)
    def my_test(arg1, kwarg1=10):
        """
        The arg is {arg1}. The kwarg is {kwarg1}.

        This is a [[hole]].

        """


    result = my_test("bees")

    # make sure args were subbed/stringed
    assert result.prompt_vars == {'arg1': 'bees', 'kwarg1': '10'}
    assert result.args == {'arg1': 'bees', 'kwarg1': 10}

    assert result.prompt_holes["hole"].completion == result.hole

    result.prompt_holes["hole"].completion._async_gen_func = gen1

    result.start()

    assert result.hole.result() == "Hello! How can I assist you today?"



def test_member_prompt():
    pass


if __name__ == "__main__":

    f1 = say_hello()
    test_prompt_decorator(f1)
