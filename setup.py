#!/usr/bin/env python

import re

from setuptools import setup


with open('README.rst') as readme:
    long_description = readme.read()
with open('shellquery.py') as py:
    version = re.search(r"__version__ = '(.+?)'", py.read()).group(1)
with open('dev_requirements.txt') as dev_requirements:
    tests_require = dev_requirements.read().splitlines()

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
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 3",
        "Programming Language :: SQL",
        "Topic :: Text Processing",
        "Topic :: Utilities",
    ],
    tests_require=tests_require,
    package_data={
        '': ['*.rst'],
    },
    entry_points={
        'console_scripts': [
            'shq = shellquery:main',
        ],
    }
)
