#!/usr/bin/env python

"""
A setuptools based setup module.

See:
https://packaging.python.org/en/latest/distributing.html
"""

import io
from os import path
from setuptools import setup, find_packages


def local_scheme(version):
    """
    Skip the local version (eg. +xyz of 0.6.1.dev4+gdf99fe2)
    to be able to upload to Test PyPI
    """
    return ""


if __name__ == "__main__":
    HERE = path.abspath(path.dirname(__file__))
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
        install_requires=[],
        setup_requires=["setuptools_scm"],
        use_scm_version={"local_scheme": local_scheme},
        classifiers=[
            "Programming Language :: Python",
            "Development Status :: 5 - Production/Stable",
            "Intended Audience :: Developers",
            "License :: OSI Approved :: MIT License",
            "Operating System :: OS Independent",
            "Topic :: Software Development :: Libraries :: Python Modules",
            "Topic :: Communications :: Email :: Filters",
        ],
        python_requires=">=3.7",
        long_description=LONG_DESCRIPTION,
    )
