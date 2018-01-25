#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
A setuptools based setup module.

See:
https://packaging.python.org/en/latest/distributing.html
"""

from __future__ import unicode_literals

import io
from os import path
from pip.req import parse_requirements
from setuptools import setup, find_packages


def get_requirements(requirements_file):
    """Use pip to parse requirements file."""
    requirements = []
    if path.isfile(requirements_file):
        for req in parse_requirements(requirements_file, session="hack"):
            # check markers, such as
            #
            #     rope_py3k    ; python_version >= '3.0'
            #
            if req.match_markers():
                requirements.append(str(req.req))
    return requirements


if __name__ == "__main__":
    HERE = path.abspath(path.dirname(__file__))
    INSTALL_REQUIRES = get_requirements(path.join(HERE, "requirements.txt"))
    with io.open(path.join(HERE, "README.rst"), encoding="utf-8") as readme:
        LONG_DESCRIPTION = readme.read()
    setup(
        name="sievelib",
        packages=find_packages(),
        include_package_data=True,
        description="Client-side SIEVE library",
        author="Antoine Nguyen",
        author_email="tonio@ngyn.org",
        url="https://github.com/tonioo/sievelib",
        license="MIT",
        keywords=["sieve", "managesieve", "parser", "client"],
        install_requires=INSTALL_REQUIRES,
        setup_requires=["setuptools_scm"],
        use_scm_version=True,
        classifiers=[
            "Programming Language :: Python",
            "Development Status :: 4 - Beta",
            "Intended Audience :: Developers",
            "License :: OSI Approved :: MIT License",
            "Operating System :: OS Independent",
            "Topic :: Software Development :: Libraries :: Python Modules",
            "Topic :: Communications :: Email :: Filters"
        ],
        long_description=LONG_DESCRIPTION
    )
