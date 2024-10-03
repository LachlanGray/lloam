import asyncio
from openai import AsyncOpenAI
from typing import List, Dict, AsyncGenerator, Optional
import re


async def stream_chat_completion(
    messages: List[Dict[str, str]],
    model: str = "gpt-3.5-turbo",
    temperature: float = 0.9,
    stop: Optional[List[str]] = None,
    api_key: Optional[str] = None
) -> AsyncGenerator[str, None]:
    client = AsyncOpenAI(api_key=api_key)

    if isinstance(messages, str):
        messages = [{"role": "user", "content": messages}]
    try:
        stream = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            stop=stop,
            stream=True
        )
        try:
            async for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    yield chunk.choices[0].delta.content
        finally:
            await stream.close()
    finally:
        await client.close()
        del client


async def parallel_stream_processing(questions: list[str]):
    
    responses = [[] for _ in questions]
    
    async def process_stream(question, index):
        async for chunk in stream_chat_completion([{"role": "user", "content": question}]):
            responses[index].append(chunk)
            # Clear the console and print the current state of all streams
            print("\033[H\033[J", end="")  # Clear console

            for i, r in enumerate(responses):
                print(f"{''.join(r)}")
                print(80*'-')
            
            # Add a small delay to make the output more readable
            await asyncio.sleep(0.1)

    # Create tasks for each question
    tasks = [process_stream(q, i) for i, q in enumerate(questions)]
    
    # Run all tasks concurrently
    await asyncio.gather(*tasks)

    return responses


async def process_stream(generator, tags):
    buffer = ''
    captured_content = ''
    current_tag = None  # Holds the current tag name when inside a tag
    opening_tags = {tag: f'<{tag}>' for tag in tags}
    closing_tags = {tag: f'</{tag}>' for tag in tags}

    max_open_tag_length = max(len(tag_str) for tag_str in opening_tags.values())
    max_close_tag_length = max(len(tag_str) for tag_str in closing_tags.values())

    # Compile regex patterns for opening and closing tags
    opening_pattern = '(' + '|'.join(re.escape(tag) for tag in opening_tags.values()) + ')'
    opening_regex = re.compile(opening_pattern)
    closing_regexes = {tag: re.compile(re.escape(closing_tags[tag])) for tag in tags}

    async for chunk in generator:
        buffer += chunk
        while True:
            if current_tag is None:
                # Search for any opening tag
                open_match = opening_regex.search(buffer)

                if open_match:
                    # If there is content before the opening tag, capture and yield it
                    leading_content = buffer[:open_match.start()]
                    if leading_content:
                        yield (None, leading_content)

                    tag_text = open_match.group(0)
                    # Identify which tag was found
                    for tag_name, tag_str in opening_tags.items():
                        if tag_str == tag_text:
                            current_tag = tag_name
                            break
                    buffer = buffer[open_match.end():]  # Remove processed part
                else:
                    # No opening tag found in buffer
                    # Need to check if we can safely yield part of the buffer
                    if len(buffer) > max_open_tag_length:
                        # Safe to yield buffer up to the point where an opening tag may start
                        safe_to_yield = buffer[:-max_open_tag_length]
                        buffer = buffer[-max_open_tag_length:]
                        if safe_to_yield:
                            yield (None, safe_to_yield)
                    else:
                        # Not enough data to decide, need to read more
                        break
            else:
                # Search for the corresponding closing tag
                close_match = closing_regexes[current_tag].search(buffer)
                if close_match:
                    # Capture content up to the closing tag
                    content = buffer[:close_match.start()]
                    captured_content += content
                    # Handle the captured content (e.g., print or store it)
                    yield (current_tag, captured_content)
                    captured_content = ''
                    current_tag = None
                    buffer = buffer[close_match.end():]
                else:
                    # No closing tag found in buffer
                    # Need to check if we can safely capture part of the buffer
                    if len(buffer) > max_close_tag_length:
                        # Safe to capture content up to the point where a closing tag may start
                        safe_to_capture = buffer[:-max_close_tag_length]
                        captured_content += safe_to_capture
                        buffer = buffer[-max_close_tag_length:]
                    else:
                        # Not enough data to decide, need to read more
                        break

    # After processing all chunks
    if current_tag is None:
        if buffer:
            yield (None, buffer)
    else:
        # Handle any remaining content if the closing tag was not found
        captured_content += buffer
        yield (current_tag, captured_content)


if __name__ == "__main__":
    async def test():
        test = "Who am I speaking to?"

        async for x in stream_chat_completion(test):
            print(x, end="")

    asyncio.run(test())

    # questions = [
    #     "What is the capital of France? make a short poem",
    #     "Who wrote 'Romeo and Juliet'? make a short poem",
    #     "What is the largest planet in our solar system? make a short poem"
    # ]
    # x = asyncio.run(parallel_stream_processing(questions))
    # print(x)
