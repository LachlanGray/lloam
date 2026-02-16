from lloam.prompt import parse_prompt, compile_prompt
import re



def test_parser():
    test_body = """This is a [[hole]]

    This has start condition [start[start_hole]]

    This is a [[end_hole]end]

    This is a variable referencing a {hole}

    This was \\[escaped\\]

    """


    prompt, prompt_holes, prompt_vars = parse_prompt(test_body)

    assert prompt[0].content == "This is a "

    assert prompt[1].name == "hole"
    assert prompt[3].start_pattern == "start"
    assert prompt[5].end_pattern == "end"

    assert prompt[7].name == "hole"

    assert prompt[3] == prompt_holes["start_hole"]

    assert prompt_vars['hole'] == None

    assert "escaped" not in prompt_holes


def test_compile():
    test_body = """

    This is {arg1}

    This is a {thing.thingy}

    This has stop condition [[hole1]end]

    This has regex stop [[hole2]r\\s*END]

    These were passed: {"|".join(listed)} then [[last_hole]].


    """


    prompt, prompt_holes, prompt_vars = parse_prompt(test_body)

    class Thing:
        thingy = "thang"

    args = {"arg1": "hello", "thing": Thing(), "listed": ["a", "b", "c"]}

    entrypoint = compile_prompt(
        prompt,
        prompt_holes,
        prompt_vars,
        args
    )

    # normal stop
    assert prompt[5].completion.stops[0] == re.compile("end")
    # regex stop
    assert prompt[7].completion.stops[0] == re.compile("\\s*END")

    # member
    assert prompt_vars["thing.thingy"] == "thang"

    # ensure completions receive appropriate slice
    assert len(prompt[5].completion.prompt) == 5
    assert len(prompt[7].completion.prompt) == 7

    # inline var logic
    assert prompt[11].completion.prompt[-2] == "a|b|c"




if __name__ == "__main__":
    test_compile()
