import textwrap
import inspect
import re
from enum import Enum
import asyncio

from .completions import Completion, CompletionStatus
from .segmentation import Spliterator

def prompt(f=None, *, model="gpt-4o-mini", temperature=0.7, start=True):

    if f is None:
        # kwargs were given; decorator evaluates to decorator with no args
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
                    start=start
                )

            return wrapper

        return decorator

    # no kwargs given, return wrapper directly
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
            start=start
        )

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

        self.has_spliterator             = False
        self.split_start_pattern     = ""
        self.split_end_pattern       = ""

        self.completion              = None
        self.spliterator             = None



class Variable:
    def __init(self):
        self.content:str                = None

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
                '\\]': '__ESCAPED_CLOSE_BRACKET__'}.get(match.group(), match.group())


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
            elif len(stack) == 2:
                hole.has_spliterator = True
                hole.split_start_pattern = buffer
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
                    hole.end_pattern = buffer

                    new_hole = Hole()
                    new_hole.parents.append(hole)
                    hole.children.append(new_hole)

                    if hole.name:
                        assert hole.name not in prompt_holes, f"hole name {hole.name} already taken"

                    prompt_holes[hole.name] = hole
                    prompt.append(hole)

                    hole = new_hole

                elif len(stack) == 1:
                    # has outer conditions
                    if hole.name is None:
                        hole.name = buffer
                    else:
                        hole.split_end_pattern = buffer

                elif len(stack) == 2:
                    hole.name = buffer

            elif ch == "}":
                # define used variable
                variable.content = buffer
                prompt_vars[variable.content] = None
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


    for i in range(len(prompt)):
        if isinstance(prompt[i], Body):
            prompt[i].content = restore_placeholders(prompt[i].content)

    return prompt, prompt_holes, prompt_vars


def compile_prompt(
        prompt_segments, prompt_holes, prompt_vars,
        args, 
        model="gpt-4o-mini",
        temperature=0.7
):


    # get entrypoint
    for segment in prompt_segments:
        if isinstance(segment, Hole):
            entrypoint = segment.name
            break

    # make prompt
    cells = []
    for segment in prompt_segments:
        if isinstance(segment, Body):
            cells.append(segment.content)

        elif isinstance(segment, Variable):
            if segment.content in prompt_holes:
                cells.append(prompt_holes[segment.content].completion)
            elif segment.content in args:
                arg = args[segment.content]

                if isinstance(arg, Completion):
                    arg = arg.result()

                cells.append(str(arg))
                prompt_vars[segment.content] = str(arg)

            else:

                output = {}
                exec("x = " + segment.content, args, output)

                cells.append(output["x"])
                prompt_vars[segment.content] = output["x"]


        elif isinstance(segment, Hole):

            segment.completion = Completion(cells[:], temperature=temperature)

            if segment.start_pattern:
                print("WARNING: start patterns not implemented yet! Completion will include preamble")

            if segment.end_pattern:
                if segment.end_pattern[0] == "r":
                    segment.end_pattern = segment.end_pattern[1:]
                    regex = True
                else:
                    regex = False

                segment.completion.add_stop(segment.end_pattern, regex=regex)

            # create spliterator
            if segment.has_spliterator:
                segment.spliterator = Spliterator(segment.completion, allow_nesting=False)

                if segment.split_start_pattern and segment.split_end_pattern:
                    split_start = segment.split_start_pattern
                    split_end = segment.split_end_pattern
                    regex = False
                    if split_start[0] == "r":
                        regex = True
                        split_start = split_start[1:]

                    if split_end[0] == "r":
                        regex = True
                        split_end = split_end[1:]

                    segment.spliterator.add_pair("capture", split_start, split_end, regex=regex)

                else:
                    assert False, f"spliterator requires start and end pattern for now"


            # add callback to parents (parent for now)
            for parent in segment.parents:
                parent.completion.add_done_callback(segment.completion.start)

            cells.append(segment.completion)

        else:
            assert False

    return entrypoint


class Prompt:
    def __init__(self, f, args, model="gpt-4o-mini", temperature=0.7, start=False):
        self.prompt_src = preprocess(f)
        self.args = args
        self.prompt, self.prompt_holes, self.prompt_vars = parse_prompt(self.prompt_src)

        self.entrypoint = compile_prompt(
            self.prompt,
            self.prompt_holes,
            self.prompt_vars,
            args, 
            model=model,
            temperature=temperature
        )

        if start:
            self.start()

    def start(self):
        self.prompt_holes[self.entrypoint].completion.start()

    def __getattr__(self, name):
        if name in self.prompt_holes:

            hole = self.prompt_holes[name]
            if hole.has_spliterator:
                return hole.spliterator
            else:
                return hole.completion

        elif name in self.prompt_vars:
            var = self.prompt_vars[name]
            return var

        else:
            raise AttributeError(f"Prompt has no attribute {name}")


    def __await__(self):
        return self._check_completion().__await__()

    async def _check_completion(self):
        # completions = [var for var in self.prompt_vars.values() if isinstance(var, Completion)]
        completions = [hole.completion for hole in self.prompt_holes.values()]
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






