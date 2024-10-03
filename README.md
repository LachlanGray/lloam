![](assets/lloam.png)
*Rich primitives for building with LLMs*
# Lloam 🌱
Lloam is a minimal prompting library offering a clean way to write prompt templates and manage their execution. Key features:
- Manage parallel completions without touching `asyncio`
- Light: only dependency is `openai`
- Call prompt templates as functions
- Doesn't stream unwanted tokens


## Lloam Prompts
Lloam prompts make a prompt template callable as a function. The prompt template goes in the docstring of the lloam function, and returns a `Prompt` object that runs the completions in the background.
- *Variables* (`{x}`) are substituded into the prompt with curly braces like f-strings.
- *Holes* (`[name]`) are filled by the language model, and can be used as variables afterward.
- Completions run in the background and only block when you access variables


```python
import lloam

@lloam.prompt
def test(x, y=5):
    """
    One kind of {x} is a [name].

    {y} {name}s makes a [group_name].
    """

template = test("domestic animal") # fills template in the background

# ... code here runs immediately ...

# access completions later
print(template.name)           # dog
print(template.group_name)     # pack
```

**Inspect running templates:**
You can print a template while it's running to investigate its state.
```python
template = test("domestic animal")

import time

for _ in range(3):
    print(template)
    print("---")
    time.sleep(0.5)

# One kind of domestic animal is a [ ... ].
#
# 5 [ ... ]s makes a [     ].
# ---
# One kind of domestic animal is a dog.
#
# 5 dogs makes a [ ... ].
# ---
# One kind of domestic animal is a dog.
#
# 5 dogs makes a pack.
# ---



```
**Infer stopping conditions:** Uses the context of a prompt to infer stopping conditions, like quotes, commas, and periods

```python
@lloam.prompt
def jsonify(entity):
    """
    \{"name": "{entity}", "color": "[color]", "taste": "[taste]" \}
    """

template = jsonify("mango")

mango_json = json.loads(str(template).strip())
print(mango_json)
# {'name': 'mango', 'color': 'yellow', 'taste': 'sweet and tangy'}
```

## Lloam Completions
For a traditional completion, use the `completion` function. A completion runs in the background until you call `.result()`, making it simple to run several completions in parallel without blocking your program.

```python
from lloam import completion

# messages
messages = [
    {"role": "system", "content": "You are a helpful assistant"},
    {"role": "user", "content": "What is loam?"}
]
loam_definition = completion(messages)

# strings
prompt = "Billy Joel said: Sing us a song you're "
lyric = completion(prompt, stop=[".", "!", "\n"])

# chunks
chunks = ["The capi", "tal of", " France ", "is", " "]
capitol = completion(chunks, stop=".")


print(loam.result())
# Loam is fertile soil,
# A mix of sand, silt, and clay,
# Perfect for planting.

print(lyric.result())
# the piano man 

print(capitol.result())
# Paris

```

