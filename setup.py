from setuptools import setup, find_packages

setup(
    name="lloam",
    version="0.1.4",
    packages=find_packages(),
    install_requires=[
        "openai>=1.51.0"
    ],
    extras_require={
        "anthropic": ["anthropic>=0.40.0"],
    },
    author="Lachlan Gray",
    description="A rich collection of primitives for building things with LLMs",
    long_description=open('README.md').read(),
    long_description_content_type="text/markdown",
    url="https://github.com/LachlanGray/lloam",
)
