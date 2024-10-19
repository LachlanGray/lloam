import textwrap
import inspect
import re
from enum import Enum
from concurrent.futures import Future
import asyncio

from .completions import Completion, CompletionStatus

PROBABLE_STOPS = set([".", ",", "?", "!", ":", ";", "(", ")", "\"", "`", "__ESCAPED_OPEN_BRACE__", "__ESCAPED_CLOSE_BRACE__", "__ESCAPED_OPEN_BRACKET__", "__ESCAPED_CLOSE_BRACKET__"])

# def prompt(model="gpt-4o-mini", temperature=0.9):
def prompt(f=None, *, model="gpt-4o-mini", temperature=0.9):

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

                return Prompt(f, args, model=model, temperature=temperature)

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


def compile_prompt(prompt_src: str, args, model="gpt-4o-mini", temperature=0.9):
    prompt_vars = {**args}
    cells = []
    entrypoint = None

    prev_call = None
    after_hole = False
    for segment_type, content in parse_prompt(prompt_src):

        if segment_type == PromptSegment.BODY:
            cells.append(content)

            if after_hole:

                if content.strip() == "":
                    continue

                word_after = content.strip().split()[0]
                intersection = PROBABLE_STOPS.intersection(word_after)
                if intersection:
                    if word_after in PROBABLE_STOPS:
                        prompt_vars[prev_call].add_stop(word_after)
                    else:
                        for i in range(1, len(word_after)):
                            if word_after[:i] in PROBABLE_STOPS:
                                prompt_vars[prev_call].add_stop(word_after[:i])

        elif segment_type == PromptSegment.VARIABLE:
            if content in prompt_vars:
                if isinstance(prompt_vars[content], Prompt):
                    cells.append(prompt_vars[content].result())
                else:
                    cells.append(prompt_vars[content])

            elif "." in content:
                obj_name, *attributes = content.split(".")
                obj = prompt_vars[obj_name]

                nested_result = obj
                for attribute in attributes:
                    nested_result = getattr(nested_result, attribute)

                cells.append(nested_result)

            else:
                raise ValueError(f"Variable {content} used before definition")

        elif segment_type == PromptSegment.HOLE:
            if content in prompt_vars:
                raise ValueError(f"Variable {content} already defined")

            prompt_vars[content] = Completion(cells.copy(), model=model, temperature=temperature)

            if prev_call:
                prompt_vars[prev_call].add_done_callback(lambda fut, content=content: prompt_vars[content].start())
            else:
                entrypoint = content

            after_hole = True

            prev_call = content

            cells.append(prompt_vars[content])

        else:
            raise ValueError("Unknown segment type")


    return cells, prompt_vars, entrypoint


class Prompt:
    def __init__(self, f, args, model="gpt-4o-mini", temperature=0.9):
        self.prompt_src = preprocess(f)
        self.cells, self.prompt_vars, entrypoint = compile_prompt(self.prompt_src, args, model=model, temperature=temperature)

        self.prompt_vars[entrypoint].start()

    def __getattr__(self, name):
        if name in self.prompt_vars:
            return self.prompt_vars[name].result()
        else:
            raise AttributeError(f"Prompt has no attribute {name}")

    def __str__(self):
        return "".join(str(cell) for cell in self.cells)

    def __await__(self):
        return self._check_completion().__await__()

    async def _check_completion(self):
        completions = [var for var in self.prompt_vars.values() if isinstance(var, Completion)]
        while not all(var.status == CompletionStatus.FINISHED for var in completions):
            # Yield control back to the event loop for a while before rechecking
            await asyncio.sleep(0.1)
        return True


    def inspect(self):
        chunks = []
        for cell in self.cells:
            if isinstance(cell, Completion):
                chunks.append(cell.visual_status())
            else:
                chunks.append(str(cell))

        return "".join(chunks)



    def progress(self):
        n_completions = sum(1 for var in self.prompt_vars.values() if isinstance(var, Completion))
        n_completed = sum(1 for var in self.prompt_vars.values() if isinstance(var, Completion) and var.status == CompletionStatus.FINISHED)

        n_waiting = n_completions - n_completed

        return n_completed, n_waiting


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






