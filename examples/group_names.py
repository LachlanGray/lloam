import lloam

@lloam.prompt(model="gpt-3.5-turbo")
def group_name(x, n=5):
    """
    One kind of {x} is a [name:(\.|,)].

    {n} {name}s makes a [group_name:(\.|,)].
    """


animal = group_name("domestic animal")
print("This prints immediately!")

# access variables later
print(animal.name)           # dog
print(animal.group_name)     # pack

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
