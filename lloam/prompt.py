import textwrap
import inspect
import re
from enum import Enum

from completions import Completion, CompletionStatus


def prompt(f):
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

        return Prompt(f, args)

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


def split_prompt(text):
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


def parse_prompt(prompt_src: str, args):
    prompt_vars = {**args}
    cells = []
    entrypoint = None

    prev_call = None
    for segment_type, content in split_prompt(prompt_src):
        if segment_type == PromptSegment.BODY:
            cells.append(content)

        elif segment_type == PromptSegment.VARIABLE:
            if content in prompt_vars:
                cells.append(prompt_vars[content])
            else:
                raise ValueError(f"Variable {content} used before definition")

        elif segment_type == PromptSegment.HOLE:
            if content in prompt_vars:
                raise ValueError(f"Variable {content} already defined")
            else:
                prompt_vars[content] = Completion(cells.copy())
                if prev_call:
                    prompt_vars[prev_call].add_done_callback(lambda fut, content=content: prompt_vars[content].start())
                else:
                    entrypoint = content

                prev_call = content

            cells.append(prompt_vars[content])

        else:
            raise ValueError("Unknown segment type")


    return cells, prompt_vars, entrypoint


class Prompt:
    def __init__(self, f, args):
        self.prompt_src = preprocess(f)
        self.cells, self.prompt_vars, entrypoint = parse_prompt(self.prompt_src, args)

        self.prompt_vars[entrypoint].start()

    def __getattr__(self, name):
        if name in self.prompt_vars:
            return str(self.prompt_vars[name])

    def __str__(self):
        return "".join(str(cell) for cell in self.cells)


if __name__ == "__main__":

    @prompt
    def test(x, y=5):
        """
        One kind of {x} is [answer].

        {y} of them makes [another].
        """

    out = test("domestic animal")

    breakpoint()
    # preprocess(prompt)

