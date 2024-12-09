import lloam
import json
import os

examples_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "samples"))

def create_sample(fp, prompt):
    completion = lloam.completion(prompt)
    completion.result()

    tokens = completion.chunks

    with open(fp, "w") as f:
        json.dump(tokens, f)

    return tokens


def sample(name, prompt):
    fp = os.path.join(examples_dir, f"{name}.txt")

    if os.path.exists(fp):
        with open(fp, "r") as f:
            tokens = json.load(f)

        return tokens

    return create_sample(fp, prompt)


def tokens_and_generator(name, prompt):
    tokens = sample(name, prompt)

    async def generator(*args, **kwargs):
        for t in tokens:
            yield t

    return tokens, generator


