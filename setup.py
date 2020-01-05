#!/usr/bin/env python3

import re

from setuptools import setup


with open('README.rst') as readme:
    long_description = readme.read()
with open('shellquery.py') as py:
    version_match = re.search(r"__version__ = '(.+?)'", py.read())
    assert version_match is not None
    version = version_match.group(1)

setup(
    name="ShellQuery",
    version=version,
    description="Command line plain text SQL",
    long_description=long_description,
    url='https://github.com/jingw/shellquery',
    author="Jing Wang",
    author_email="99jingw@gmail.com",
    license="MIT License",
    py_modules=['shellquery'],
    classifiers=[
        "Environment :: Console",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: SQL",
        "Topic :: Text Processing",
        "Topic :: Utilities",
    ],
    entry_points={
        'console_scripts': [
            'shq = shellquery:main',
        ],
    },
    python_requires='>=3.6',
)
