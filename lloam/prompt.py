from completions import Completion
import textwrap
import inspect
import re
from enum import Enum


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
    graph = {}

    i = 0
    for segment_type, content in split_prompt(prompt_src):
        if segment_type == PromptSegment.BODY:
            graph[i] = {
                "value": content,
                "depends_on": i - 1
            }

        elif segment_type == PromptSegment.VARIABLE:
            prompt_vars[content] = {
                "value": args[content],
                "depends_on": i - 1
            }

            graph[i] = {
                "value": prompt_vars[content],
                "depends_on": i - 1
            }

        elif segment_type == PromptSegment.HOLE:
            if content in prompt_vars:
                raise ValueError(f"Variable {content} already defined; choose different name for hole")
            elif content in prompt_holes:
                raise ValueError(f"Hole {content} already defined")
            else:
                prompt_holes[content] = None

            graph[i] = {
                "value": prompt_holes[content],
                "depends_on": i - 1
            }

        else:
            raise ValueError("Unknown segment type")

        i += 1

    return graph


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

