![](assets/lloam.png)
*Rich primitives for building with LLMs*
# Lloam 🌱
Lloam is a minimal prompting library offering a clean way to write prompts and manage their execution. Key features:

- **Parallel:** completions run concurrently
- **Lightweight:** only dependency is `openai`
- **Lloam prompts:** clean function syntax for inline prompts


## Usage

```
pip install lloam
```

Overview: [completions](#lloam-completions), [prompts](#lloam-prompts), [agents](#lloam-agents)

### Lloam Completions

`lloam.completion` is a simple and familiar way to generate completions. It returns a `Completion` object, which manages the token stream.  Tokens are accumulated concurrently, meaning completions won't block your program until you acess their results (e.g. with `str()` or `print()`).

```python
from lloam import completion


# strings
prompt = "Snap, crackle, and"
who = completion(prompt, stop="!", model="gpt-3.5-turbo")

# lists
chunks = ["The capi", "tal of", " France ", "is", "?"]
capitol = completion(chunks, stop=[".", "!"])

messages = [
    {"role": "system", "content": "You answer questions in haikus"},
    {"role": "user", "content": "What's loam"}
]
poem = completion(messages)

# ...completions are running concurrently...

print(who)     # pop
print(capitol) # The capital of France is Paris
print(poem)    # Soil rich and robust,
               # A blend of clay, sand, and silt,
               # Perfect for planting.
```

### Lloam Prompts
Lloam prompts offer a clean templating syntax you can use to write more complex prompts inline. The language model fills the `[holes]`, while `{variables}` are substituted into the prompt. Lloam prompts run concurrently just like completions, under the hood they are managing a sequence of Completions.

```python
import lloam

@lloam.prompt(model="gpt-3.5-turbo")
def group_name(x, n=5):
    """
    One kind of {x} is a [name].

    {n} {name}s makes a [group_name].
    """


animal = group_name("domestic animal")
print("This prints immediately!")

# access variables later
print(animal.name)           # dog
print(animal.group_name)     # pack
```

You can also inspect the live state of a prompt with `.inspect()`:

```python
musician_type = group_name("musician", n=3)

import time
for _ in range(3):
    print(musician_type.inspect())
    print("---")
    time.sleep(0.5)

print(musician_type.name)
print(musician_type.group_name)

# output:

# One kind of musician is a [ ... ].

# 3 [ ... ]s makes a [     ].
# ---
# One kind of musician is a singer-songwriter.

# 3 singer-songwriters makes a [ ... ].
# ---
# One kind of musician is a singer-songwriter.

# 3 singer-songwriters makes a trio.
# ---
# singer-songwriter
# trio
```

### Lloam Agents
Lloam encourages you to think of an agent as a datastructure around language. Here's how you could make a RAG Agent that has 
- a chat history

- a database

- a context for retrieved artifacts

You can see another example in `examples/shell_agent.py`. More stuff on agents coming soon!

```python
import lloam

class RagAgent:
    def __init__(self, db):
        self.db = db
        self.history = []
        self.artifacts = {}

    def ask(self, question):
        self.history.append({"role": "user", "content": question})

        results = self.db.query(question)
        self.artifacts.update(results)

        answer = self.answer(question)

        self.history.append({"role": "assistant", "content": answer.answer})

        return {
            "answer": answer.answer
            "followup": answer.followup
        }


    @lloam.prompt
    def answer(self, question):
        """
        {self.artifacts}
        ---
        {self.history}

        user: {question}

        [answer]

        What would be a good followup question?
        [followup]
        """
```
