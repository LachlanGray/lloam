import textwrap
import inspect
import re
from enum import Enum

from completions import Completion


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

        prompt_src = preprocess(f)

        prompt_graph = parse_prompt(prompt_src, args)
        return prompt_graph

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
    prompt_holes = {}
    cells = {}

    i = 0
    for segment_type, content in split_prompt(prompt_src):
        if segment_type == PromptSegment.BODY:
            cells[i] = content

        elif segment_type == PromptSegment.VARIABLE:
            if content in prompt_vars:
                cells[i] = prompt_vars[content]
            elif content in prompt_holes:
                cells[i] = prompt_holes[content]
            else:
                raise ValueError(f"Variable {content} used before definition")


        elif segment_type == PromptSegment.HOLE:
            if content in prompt_vars:
                raise ValueError(f"Variable {content} already defined; choose different name for hole")
            elif content in prompt_holes:
                raise ValueError(f"Hole {content} already defined")
            else:
                prompt_holes[content] = i


            cells[i] = prompt_holes[content],

        else:
            raise ValueError("Unknown segment type")

        i += 1

    return cells, prompt_vars, prompt_holes


class Prompt:
    def __init__(self, f, args):
        self.prompt_src = preprocess(f)

        self.cells,
        self.prompt_vars,
        self.prompt_holes = parse_prompt(self.prompt_src, args)


        self.completions = {}
        self.active_hole = list(self.prompt_holes.keys())
        prev_hole = list(self.prompt_holes.keys())[0]

        for hole_name, loc in list(self.prompt_holes.items())[1:]:
            self.completions[hole_name] = {
                "completion": Completion()
            }

            self.completions[prev_hole]["next"] = hole_name
            prev_hole = hole_name

        self.prompt_state = ""
        self.pc = 0

        def completion_callback(completion):
            while self.pc < self.prompt_holes[self.active_hole]:
                self.prompt_state += self.cells[self.pc]
                self.pc += 1

            result = completion.result()

            self.prompt_state += result
            self.active_hole = self.completions[self.active_hole]["next"]
            self.pc += 1





    def __getattr__(self, name):
        if name in self.prompt_vars:
            return self.prompt_vars[name]
        elif name in self.prompt_holes:
            return self.completions[name]
        elif name == "prompt":
            return self.prompt_src
        else:
            raise AttributeError(f"Prompt has no attribute {name}")



if __name__ == "__main__":

    @prompt
    def test(x, y=5):
        """
        What is an {x}? An {x} is [answer].

        {x} is not {y}.

        These square braces are escaped \[something\]
        As are these curlies \{something\}

        Whats this \\? and this \\[ ?
        """

    out = test(1)
    for k, v in out.items():
        print(k, v)

    # preprocess(prompt)

