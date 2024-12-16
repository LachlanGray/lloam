from lloam.prompt import parse_prompt



def test_parser():
    test_body = """This is a [[hole]]

    This has start condition [start[start_hole]]

    This is a [[end_hole]end]

    This is a {variable}

    This was \[escaped\]

    This is a pair spliterator [[inner[split_iterator]conditions]]

    This is a pair spliterator [outer_and[inner[split_and_stop]conditions]end]

    """


    prompt, prompt_holes, prompt_vars = parse_prompt(test_body)

    assert prompt[0].content == "This is a "

    assert prompt[1].name == "hole"
    assert prompt[3].start_pattern == "start"
    assert prompt[5].end_pattern == "end"

    assert prompt[7].name == "variable"

    assert prompt[3] == prompt_holes["start_hole"]

    assert prompt_vars['variable'] == None

    assert "escaped" not in prompt_holes

    assert prompt[9].name == "split_iterator"
    assert prompt[9].split_start_pattern == "inner"
    assert prompt[9].split_end_pattern == "conditions"

    assert prompt[11].name == "split_and_stop"
    assert prompt[11].start_pattern == "outer_and"
    assert prompt[11].split_start_pattern == "inner"
    assert prompt[11].split_end_pattern == "conditions"
    assert prompt[11].end_pattern == "end"





if __name__ == "__main__":
    test_parser()

