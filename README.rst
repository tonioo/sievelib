sievelib
========

Client-side Sieve and Managesieve library written in Python.

* Sieve : An Email Filtering Language
  (`RFC 5228 <http://tools.ietf.org/html/rfc5228>`_)
* ManageSieve : A Protocol for Remotely Managing Sieve Scripts
  (`Draft <http://tools.ietf.org/html/draft-martin-managesieve-12>`_)

Sieve tools
-----------

What is supported
^^^^^^^^^^^^^^^^^

Currently, the provided parser supports most of the functionalities
described in the RFC. The only exception concerns section
*2.4.2.4. Encoding Characters Using "encoded-character"* which is not
supported.

The following extensions are also supported:

* Vacation (`RFC 5230 <http://tools.ietf.org/html/rfc5230>`_)

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

Simple filters creation
^^^^^^^^^^^^^^^^^^^^^^^

Some high-level classes are provided with the ``factory`` module, they
make the generation of Sieve rules easier::

  >>> from sievelib.factory import FilterSet
  >>> fs.addfilter("rule1",
  ...              [("Sender", ":is", "toto@toto.com"),],
  ...              [("fileinto", "Toto"),])
  >>> fs.tosieve()
  require ["fileinto"];
  
  # Filter: rule1
  if anyof (header :is "Sender" "toto@toto.com") {
      fileinto "Toto";
  }
  >>> 

Additionnal documentation is available with source code.

ManageSieve tools
-----------------

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
