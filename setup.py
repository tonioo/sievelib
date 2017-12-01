# coding=utf-8
import os
import re
from setuptools import setup, find_packages

ROOT = os.path.dirname(__file__)
PIP_REQUIRES = os.path.join(ROOT, "requirements.txt")


def parse_requirements(*filenames):
    """
    We generate our install_requires from the pip-requires and test-requires
    files so that we don't have to maintain the dependency definitions in
    two places.
    """
    requirements = []
    for f in filenames:
        for line in open(f, 'r').read().split('\n'):
            # Comment lines. Skip.
            if re.match(r'(\s*#)|(\s*$)', line):
                continue
            # Editable matches. Put the egg name into our reqs list.
            if re.match(r'\s*-e\s+', line):
                pkg = re.sub(r'\s*-e\s+.*#egg=(.*)$', r'\1', line)
                requirements.append("%s" % pkg)
            # File-based installs not supported/needed. Skip.
            elif re.match(r'\s*-f\s+', line):
                pass
            else:
                requirements.append(line)
    return requirements


def parse_dependency_links(*filenames):
    """
    We generate our dependency_links from the pip-requires and test-requires
    files for the dependencies pulled from github (prepended with -e).
    """
    dependency_links = []
    for f in filenames:
        for line in open(f, 'r').read().split('\n'):
            if re.match(r'\s*-[ef]\s+', line):
                line = re.sub(r'\s*-[ef]\s+', '', line)
                line = re.sub(r'\s*git\+https', 'http', line)
                line = re.sub(r'\.git#', '/tarball/master#', line)
                dependency_links.append(line)
    return dependency_links


def read(fname):
    return open(os.path.join(ROOT, fname)).read()


setup(
    name="sievelib",
    packages=find_packages(),
    include_package_data=True,
    version="1.1.0",
    description="Client-side SIEVE library",
    author="Antoine Nguyen",
    author_email="tonio@ngyn.org",
    url="https://github.com/tonioo/sievelib",
    license="MIT",
    keywords=["sieve", "managesieve", "parser", "client"],
    install_requires=parse_requirements(PIP_REQUIRES),
    dependency_links=parse_dependency_links(PIP_REQUIRES),
    classifiers=[
        "Programming Language :: Python",
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Communications :: Email :: Filters"
    ],
    long_description=read("README.rst")
)
