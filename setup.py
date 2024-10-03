from setuptools import setup, find_packages

setup(
    name="lloam",
    version="0.1.1",
    packages=find_packages(),
    install_requires=[
        "openai>=1.51.0"
    ],
    author="Lachlan Gray",
    description="A fertile collection of primitives for building things with LLMs",
    long_description=open('README.md').read(),
    long_description_content_type="text/markdown",
    url="https://github.com/LachlanGray/lloam",
)
