from lloam.completions import Completion


prompt = "If you were a fruit what would you be?"


# string stopping conditions
print("# string stopping condition ##########")
response = Completion(prompt)
response.add_stop(".")
response.add_stop("!") # stop at end of first sentence

response.start()

print(response.result())


print("# regex stopping condition ##########")
response = Completion(prompt, include_stops=False)
response.add_stop(r"[.!]", regex=True)

response.start()

print(response.result())

