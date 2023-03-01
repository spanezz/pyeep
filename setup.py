#!/usr/bin/env python3

from setuptools import setup

setup(
    name="pyeep",
    python_requires=">= 3.11",
    install_requires=[
        'pyaudio', 'numpy',
    ],
    version="0.1",
    description="Simple Python synth and audio pattern generator",
    author="Enrico Zini",
    author_email="enrico@enricozini.org",
    url="https://github.com/spanezz/pyeep",
    license="http://www.gnu.org/licenses/gpl-3.0.html",
    packages=[
        "pyeep",
    ],
)
