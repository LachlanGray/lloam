import textwrap
import inspect
import re
from enum import Enum
from concurrent.futures import Future
import asyncio
from dataclasses import dataclass

from .completions import Completion, CompletionStatus

def prompt(f=None, *, model="gpt-4o-mini", temperature=0.7):
    """
    Decorator to define a prompt function using a lloam template string.


    Parameters
    ----------
    f : callable
        The function to decorate. The function should have a docstring that defines the prompt template.
    model : str, optional
        The model to use for completions. Default is "gpt-4o-mini".
    temperature : float, optional
        The temperature to use for completions. Default is 0.9.


    Returns
    -------
    callable
        A decorated function that returns a Prompt object.


    Syntax
    ------
    - Variables: {variable_name}
    - Holes: [hole_name]

    Variables
    - Variables are substituted into the prompt template like an f-string
    - Variables can be
        - positional or keyword arguments
        - attributes of positional or keyword arguments
        - the result of previously defined holes

    Holes
    - Holes are completed by the language model in order
    - Once completed, the result can be used as a variable
    - You can define the stopping conditions as a regex using "up until" syntax, e.g.

        [hole_name:regexp]

    """

    if f is None:
        def decorator(f):
            def wrapper(*args, **kwargs):
                fn_args, default_kwargs = get_signature(f)

                kwargs = {**default_kwargs, **kwargs}

                if len(args) < len(fn_args):
                    for arg in fn_args:
                        if arg not in kwargs:
                            raise ValueError(f"Missing postitional argument {arg}")

                    raise ValueError(f"Expected {len(fn_args)} arguments, got {len(args)}")

                args = {k: v for k, v in zip(fn_args, args)}
                args = {**args, **kwargs}

                return Prompt(
                    f,
                    args,
                    model=model,
                    temperature=temperature,
                    start=True
                )

            return wrapper

        return decorator

    def wrapper(*args, **kwargs):
        fn_args, default_kwargs = get_signature(f)

        kwargs = {**default_kwargs, **kwargs}

        if len(args) < len(fn_args):
            for arg in fn_args:
                if arg not in kwargs:
                    raise ValueError(f"Missing postitional argument {arg}")

            raise ValueError(f"Expected {len(fn_args)} arguments, got {len(args)}")

        args = {k: v for k, v in zip(fn_args, args)}
        args = {**args, **kwargs}


        return Prompt(f, args,model=model, temperature=temperature, start=True)

    return wrapper


def preprocess(f: callable, deco_fn=True):
    src = inspect.getsource(f)
    src = textwrap.dedent(src)

    lines = src.split("\n")
    if deco_fn:
        deco = lines.pop(0)
    fn_def = lines.pop(0)

    prompt_src = textwrap.dedent("\n".join(lines)).rstrip()
    lines = prompt_src.split("\n")
    open_quote = lines.pop(0)
    close_quote = lines.pop(-1)
    prompt_src = textwrap.dedent("\n".join(lines))

    return prompt_src

def get_signature(f: callable):
    args = []
    kwargs = {}
    for param_name, param in inspect.signature(f).parameters.items():
        if param.default == inspect.Parameter.empty:
            args.append(param_name)
        else:
            kwargs[param_name] = param.default

    return tuple(args), kwargs


class PromptSegment(Enum):
    VARIABLE = "variable"
    HOLE = "hole"
    BODY = "body"


class Hole:
    def __init__(self):
        self.start_pattern: str|None = None
        self.name: str               = None
        self.end_pattern: str|None   = None
        self.parents: list           = []
        self.children: list          = []



class Variable:
    def __init(self):
        self.name:str                = None

class Body:
    def __init(self):
        self.content:str             = None



def parse_prompt(text):
    # Define patterns for escaped characters
    escape_pattern = re.compile(r'\\.')

    # Function to replace escaped characters with placeholders
    def replace_escaped(match):
        return {'\\{': '__ESCAPED_OPEN_BRACE__',
                '\\}': '__ESCAPED_CLOSE_BRACE__',
                '\\[': '__ESCAPED_OPEN_BRACKET__',
                '\\]': '__ESCAPED_CLOSE_BRACKET__',
                '\\\\': '__ESCAPED_BACKSLASH__'}.get(match.group(), match.group())

    # Replace escaped braces and brackets with placeholders
    text = escape_pattern.sub(replace_escaped, text)

    stack = []
    prompt = []
    prompt_holes = {}
    prompt_vars = {}

    buffer = ""
    hole = Hole()
    variable = Variable()
    body = Body()

    for ch in text:

        if ch == "[":
            if len(stack) == 0:
                # opening new hole
                body.content = buffer
                prompt.append(body)
                body = Body()
            elif len(stack) == 1:
                # had outer condition
                hole.start_pattern = buffer
            else:
                assert False, f"hole syntax error:\n{buffer}"

            buffer = ""
            stack.append("]")
            continue

        elif ch == "{":
            if len(stack) == 0:
                body.content = buffer
                prompt.append(body)
                body = Body()
            else:
                assert False, f"variable syntax error:\n{buffer}"

            buffer = ""
            stack.append("}")
            continue

        else:
            pass


        if len(stack) > 0 and ch == stack[-1]:
            stack.pop()

            if ch == "]":
                if len(stack) == 0:
                    # finalize hole
                    if hole.name is None:
                        # no outer condition
                        hole.name = buffer
                    else:
                        # has outer conditions
                        hole.end_pattern = buffer

                    new_hole = Hole()
                    new_hole.parents.append(hole)
                    hole.children.append(new_hole)

                    assert hole.name not in prompt_holes, f"hole name {hole.name} already taken"

                    prompt_holes[hole.name] = hole
                    prompt.append(hole)

                    hole = new_hole

                elif len(stack) == 1:
                    # in inner portion; name hole
                    hole.name = buffer

            elif ch == "}":
                # define used variable
                variable.name = buffer
                prompt_vars[variable.name] = None
                prompt.append(variable)
                variable = Variable()

            buffer = ""

        else:
            buffer += ch


    assert len(stack) == 0, f"missing: {stack[-1]}"

    body.content = buffer
    prompt.append(body)


    # Function to restore placeholders to their original characters
    def restore_placeholders(segment):
        return segment.replace('__ESCAPED_OPEN_BRACE__', '{') \
                      .replace('__ESCAPED_CLOSE_BRACE__', '}') \
                      .replace('__ESCAPED_OPEN_BRACKET__', '[') \
                      .replace('__ESCAPED_CLOSE_BRACKET__', ']') \
                      .replace('__ESCAPED_BACKSLASH__', '\\')


    for i in range(len(prompt)):
        if isinstance(prompt[i], Body):
            prompt[i].content = restore_placeholders(prompt[i].content)

    return prompt, prompt_holes, prompt_vars


def compile_prompt(parsed_prompt: list[tuple[PromptSegment, str]], args, model="gpt-4o-mini", temperature=0.7):
    prompt_vars = {**args}
    cells = []
    entrypoint = None

    prev_call = None

    for segment_type, symbol in parsed_prompt:

        if segment_type == PromptSegment.BODY:
            cells.append(symbol)

        elif segment_type == PromptSegment.VARIABLE:
            if symbol in prompt_vars:
                if isinstance(prompt_vars[symbol], Prompt):
                    cells.append(prompt_vars[symbol].result())
                elif isinstance(prompt_vars[symbol], Completion):
                    cells.append(prompt_vars[symbol].result())
                else:
                    cells.append(prompt_vars[symbol])

            elif "." in symbol:
                obj_name, *attributes = symbol.split(".")
                assert obj_name in prompt_vars, f"No symbol {obj_name} in prompt_vars"

                obj = prompt_vars[obj_name]

                nested_result = obj
                for attribute in attributes:
                    nested_result = getattr(nested_result, attribute)

                if isinstance(nested_result, Completion):
                    cells.append(nested_result.result())
                else:
                    cells.append(str(nested_result))

            else:
                raise ValueError(f"Variable {symbol} used before definition")

        elif segment_type == PromptSegment.HOLE:
            if symbol in prompt_vars:
                raise ValueError(f"Variable name {symbol} already defined as variable, can't redefine as hole.")

            compl = Completion(
                cells, model=model, temperature=temperature
            )

            stop = None
            if ":" in symbol:
                symbol, regexp = symbol.split(":")
                symbol = symbol.strip()
                stop = regexp.strip()

                compl.add_stop(stop)

            cells.append(compl)
            prompt_vars[symbol] = compl

            if prev_call:
                prompt_vars[prev_call].add_done_callback(prompt_vars[symbol].start)
            else:
                entrypoint = symbol

            prev_call = symbol

        else:
            raise ValueError("Unknown segment type")

    exitpoint = prev_call

    return cells, prompt_vars, entrypoint, exitpoint


class Prompt:
    def __init__(self, f, args, model="gpt-4o-mini", temperature=0.7, start=False):
        self.prompt_src = preprocess(f)
        self.parsed_prompt = parse_prompt(self.prompt_src)
        self.cells, self.prompt_vars, entrypoint, exitpoint = compile_prompt(self.parsed_prompt, args, model=model, temperature=temperature)
        self.entrypoint = entrypoint
        self.exitpoint = exitpoint

        if start:
            self.start()

    def start(self):
        self.prompt_vars[self.entrypoint].start()

    def __getattr__(self, name):
        if name in self.prompt_vars:
            var = self.prompt_vars[name]
            return var
        else:
            raise AttributeError(f"Prompt has no attribute {name}")

    def __str__(self):
        return "".join(str(cell) for cell in self.cells)

    def __await__(self):
        return self._check_completion().__await__()

    async def _check_completion(self):
        completions = [var for var in self.prompt_vars.values() if isinstance(var, Completion)]
        while not all(var.status == CompletionStatus.FINISHED for var in completions):
            await asyncio.sleep(0.1)
        return True


if __name__ == "__main__":

    @prompt
    def test(x, y=5):
        """
        One kind of {x} is a [name].

        {y} {name}s makes a [group_name].
        """

    template = test("domestic animal")

    import time

    for _ in range(3):
        print(template)
        print("---")
        time.sleep(0.5)

    print(template.name)         # a dog
    print(template.group_name)   # a pack


    # @prompt
    # def jsonify(entity):
    #     """
    #     \{"name": "{entity}", "color": "[color]", "taste": "[taste]" \}
    #     """

    # template = jsonify("mango")
    # import time
    # import json

    # for _ in range(3):
    #     print(template)
    #     print("---")
    #     time.sleep(1)

    # mango_json = json.loads(str(template).strip())
    # print(mango_json)






