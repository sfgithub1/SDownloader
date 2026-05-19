from setuptools import setup, find_packages

setup(
    name="sdownloader",
    version="1.0.0",
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
