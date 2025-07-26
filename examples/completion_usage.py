from lloam.completions import Completion

prompt = "If you were a fruit what would you be?"



print("# normal usage ##########")
response = Completion(prompt)
response.start()

print(response.result())



print("# stream ##########")
response = Completion(prompt)
response.start()

for c in response.stream():
    print(c, end="")
print("\n\n")



print("# run completions in parallel ##########")
responses = [Completion(prompt) for _ in range(3)]

for r in responses:
    r.start()

# ... code here would run immediately ...
# ... completions continue in background ...

for r in responses:
    print(r, end="\n\n")


