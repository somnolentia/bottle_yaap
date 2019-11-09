#!/usr/bin/env python3
import os
from setuptools import setup

project = 'bottle_yaap'


def _read(fname):
    try:
        return open(os.path.join(os.path.dirname(__file__), fname)).read()
    except IOError:
        return ''


setup(
    name=project,
    version='1.0',
    author='Pieter Vermeylen',
    author_email='pieter@somnolenta.net',
    description="Yet Another Authorization Plugin (for Bottle)",
    long_description=_read('README.rst'),
    url=f'https://www.somnolentia.net/code/{project}',
    keywords="",
    license='MIT',
    platforms=('Any'),
    classifiers=[
        'Intended Audience :: Developers',
        'Programming Language :: Python :: 3',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: Utilities',
    ],
    py_modules=[project],
    install_requires=[
        'bottle',
        'passlib',
        'argon2-cffi',
    ],
    extras_require={
        'dev': ['pytest'],
        'cli': ['Click']
    },
    entry_points={
        'console_scripts': ['yaap=bottle_yaap:cli'],
    },
)
