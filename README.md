A fertile collection of primitives for building things with LLMs.

## Prompt Template
Let's start with an example `lloam` prompt:
```python
@lloam.prompt
def define(x):
    """
    What is {x}? {x} is [definition]
    """

completion = test("loam")
print(completion["answer"])
# a fertile soil of clay and sand containing humus.
```

The `lloam.prompt` decorator marks this function as a `lloam` prompt. The body is the propmt template. *Variables* like `{x}` are denoted with curly brances, and work like f-strings.


*Holes* like `[definition]` are denoted with square braces. They are filled in by the language model and stored. After completion the name in the hole can be used as a variable.

A `lloam` prompt returns a dictionary of variables.
