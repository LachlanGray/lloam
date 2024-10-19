import lloam

@lloam.prompt(model="gpt-3.5-turbo")
def test(x, y=5):
    """
    One kind of {x} is a [name].

    {y} {name}s makes a [group_name].
    """

if __name__ == "__main__":
    prompt = test("domestic animal") # fills propmt template in the background

    import time
    for _ in range(3):
        print(prompt.inspect())
        print("---")
        time.sleep(0.5)

    print(prompt.name)
    print(prompt.group_name)

    # output:

    # One kind of domestic animal is a [ ... ].

    # 5 [ ... ]s makes a [     ].
    # ---
    # One kind of domestic animal is a dog.

    # 5 dogs makes a [ ... ].
    # ---
    # One kind of domestic animal is a dog.

    # 5 dogs makes a pack.
    # ---
    # dog
    # pack
