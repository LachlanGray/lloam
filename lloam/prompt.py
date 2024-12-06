import textwrap
import inspect
import re
from enum import Enum
from concurrent.futures import Future
import asyncio

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


def preprocess(f: callable):
    src = inspect.getsource(f)
    src = textwrap.dedent(src)

    lines = src.split("\n")
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

    # Pattern to match unescaped {.*?} and [.*?]
    pattern = re.compile(r'(\{.*?\}|\[.*?\])')

    # Split the text around the unescaped braces/brackets
    segments = pattern.split(text)

    # Function to restore placeholders to their original characters
    def restore_placeholders(segment):
        return segment.replace('__ESCAPED_OPEN_BRACE__', '{') \
                      .replace('__ESCAPED_CLOSE_BRACE__', '}') \
                      .replace('__ESCAPED_OPEN_BRACKET__', '[') \
                      .replace('__ESCAPED_CLOSE_BRACKET__', ']') \
                      .replace('__ESCAPED_BACKSLASH__', '\\')

    # Process segments to remove braces/brackets and restore placeholders
    result = []
    for segment in segments:
        segment = restore_placeholders(segment)
        if segment.startswith('{') and segment.endswith('}'):
            result.append((PromptSegment.VARIABLE, segment[1:-1]))
        elif segment.startswith('[') and segment.endswith(']'):
            result.append((PromptSegment.HOLE, segment[1:-1]))
        else:
            result.append((PromptSegment.BODY, segment))
    return result


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

            stop = None
            if ":" in symbol:
                symbol, regexp = symbol.split(":")
                symbol = symbol.strip()
                stop = regexp.strip()

            completion = Completion(
                cells, stop=stop, model=model, temperature=temperature
            )

            cells.append(completion)
            prompt_vars[symbol] = completion

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






