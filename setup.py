from setuptools import setup

setup(
    name = "sievelib",
    packages = ["sievelib"],
    version = "0.1",
    description = "Client-side SIEVE library",
    author = "Antoine Nguyen",
    author_email = "tonio@ngyn.org",
    url = "http://bitbucket.org/tonioo/sievelib",
    license = "MIT",
    keywords = ["sieve", "managesieve", "parser", "client"],
    classifiers = [
        "Programming Language :: Python",
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Communications :: Email :: Filters"
        ],
    
    long_description = """\
Client-side SIEVE library
-------------------------

This library offers tools to work with the SIEVE (An email filtering
language) and MANAGESIEVE (A Protocol for Remotely Managing Sieve
Scripts) protocols.

It includes a SIEVE language parser and MANAGESIEVE client.

"""
)
