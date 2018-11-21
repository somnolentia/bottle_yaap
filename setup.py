#!/usr/bin/env python3
import os
from setuptools import setup

version = "1.0.0"
project = 'bottle_yaap'
author = "Pieter Vermeylen"
author_email = "pieter@somnolentia.net"
license = "MIT"


def _read(fname):
    try:
        return open(os.path.join(os.path.dirname(__file__), fname)).read()
    except IOError:
        return ''


def get_reqs():
    with open('reqs.txt') as fp:
        return fp.read().splitlines()


setup(
    name=project,
    version=version,
    license=license,
    description="luminix translation memory module",
    long_description=_read('README.rst'),
    platforms=('Any'),
    keywords="",
    author=author,
    author_email=author_email,
    url=f'https://www.luminix.fi/code/{project}',
    classifiers=[
        'Intended Audience :: Developers',
        'Programming Language :: Python :: 3',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: Utilities',
    ],

    py_modules=[project],
    install_requires=get_reqs(),
)
