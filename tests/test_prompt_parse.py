from lloam.prompt import parse_prompt



def test_parser():
    test_body = """This is a [hole]

    This is a [[nested_hole]]

    This is a [start[start_hole]]

    This is a [[end_hole]end]

    This is a {variable}

    This is more body
    """

    prompt, prompt_holes, prompt_vars = parse_prompt(test_body)

    assert prompt[0].content == "This is a "

    assert prompt[1].name == "hole"
    assert prompt[3].name == "nested_hole"
    assert prompt[5].start_pattern == "start"
    assert prompt[7].end_pattern == "end"

    assert prompt[9].name == "variable"

    assert prompt[3] == prompt_holes["nested_hole"]

    assert prompt_vars['variable'] == None



if __name__ == "__main__":
    test_parser()

