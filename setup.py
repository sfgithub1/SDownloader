from pathlib import Path
from setuptools import setup, find_packages

version = (Path(__file__).parent / "VERSION").read_text().strip()

setup(
    name="sdownloader",
    version=version,
    packages=find_packages(),
    install_requires=[
        "tqdm",
    ],
    entry_points={
        "console_scripts": [
            "sdownloader=sdownloader.cli:main",
        ],
    },
    python_requires=">=3.7",
)
