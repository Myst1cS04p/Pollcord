# setup.py
from setuptools import setup, find_packages

setup(
    name="pollcord",  # Name of the package
    version="0.0.1",  # Version number
    packages=find_packages(),  # Automatically find all packages in the project
    install_requires=[  # List of external dependencies
        "discord.py"  # Discord library
    ],
    author="Myst1cS04p",
    author_email="myst1cs04p@gmail.com",
    description="A simple library for interacting with Discord polls.",
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    url="https://github.com/Myst1cS04p/Pollcord",  # URL of the project
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: CC-BY License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.12',  # Minimum Python version
)
