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
