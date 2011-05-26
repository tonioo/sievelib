sievelib
========

Client-side Sieve and Managesieve library written in Python.

* Sieve : An Email Filtering Language
  <http://tools.ietf.org/html/rfc5228>
* ManageSieve : A Protocol for Remotely Managing Sieve Scripts
  <http://tools.ietf.org/html/draft-martin-managesieve-12>

Sieve tools
-----------

What is supported
^^^^^^^^^^^^^^^^^

Currently, the provided parser only supports the functionalities
described in the RFC.(ie. there isn't any extensions supported). The
only exception concerns section *2.4.2.4. Encoding Characters Using
"encoded-character"* which is not supported.

Basic usage
^^^^^^^^^^^

The parser can either be used from the command-line::

  $ cd sievelib
  $ python parser.py test.sieve
  Syntax OK
  $

Or can be used from a python environment (or script/module)::

  >>> from sievelib.parser import Parser
  >>> p = Parser()
  >>> p.parse('require ["fileinto"];')
  True
  >>> p.dump()
  require (type: control)
      ["fileinto"]
  >>> 
  >>> p.parse('require ["fileinto"]')
  False
  >>> p.error
  'line 1: parsing error: end of script reached while semicolon expected'
  >>>

Additionnal documentation is available with source code.

ManageSieve tools
_________________

What is supported
^^^^^^^^^^^^^^^^^

All mandatory commands are supported. The ``RENAME`` extension is
supported, with a simulated behaviour for server that do not support
it.

For the ``AUTHENTICATE`` command, supported mechanisms are ``DIGEST-MD5``,
``PLAIN`` and ``LOGIN``.
    
Basic usage
^^^^^^^^^^^

The ManageSieve client is intended to be used from another python
application (there isn't any shell provided)::

  >>> from sievelib.managesieve import Client
  >>> c = Client("server.example.com")
  >>> c.connect("user", "password", starttls=False, authmech="DIGEST-MD5")
  True
  >>> c.listscripts()
  ("active_script", ["script1", "script2"])
  >>> c.setactive("script1")
  True
  >>> c.havespace("script3", 45)
  True
  >>>

Additionnal documentation is available with source code.
