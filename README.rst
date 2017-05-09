sievelib
========

|travis| |codecov| |latest-version|

Client-side Sieve and Managesieve library written in Python.

* Sieve : An Email Filtering Language
  (`RFC 5228 <http://tools.ietf.org/html/rfc5228>`_)
* ManageSieve : A Protocol for Remotely Managing Sieve Scripts
  (`RFC 5804 <http://tools.ietf.org/html/rfc5804>`_)

Installation
------------

To install ``sievelib`` from PyPI::

  pip install sievelib

To install sievelib from git::

  git clone git@github.com:tonioo/sievelib.git
  cd sievelib
  python ./setup.py install

Sieve tools
-----------

What is supported
^^^^^^^^^^^^^^^^^

Currently, the provided parser supports most of the functionalities
described in the RFC. The only exception concerns section
*2.4.2.4. Encoding Characters Using "encoded-character"* which is not
supported.

The following extensions are also supported:

* Date and Index (`RFC 5260 <https://tools.ietf.org/html/rfc5260>`_)
* Vacation (`RFC 5230 <http://tools.ietf.org/html/rfc5230>`_)

Extending the parser
^^^^^^^^^^^^^^^^^^^^

It is possible to extend the parser by adding new supported
commands. For example::

  import sievelib

  class MyCommand(sievelib.commands.ActionCommand):
      args_definition = [
          {"name": "testtag",
              "type": ["tag"],
              "write_tag": True,
              "values": [":testtag"],
              "extra_arg": {"type": "number",
                            "required": False},
              "required": False},
          {"name": "recipients",
              "type": ["string", "stringlist"],
              "required": True}
      ]

  sievelib.commands.add_commands(MyCommand)

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

  >>> from sievelib.factory import FiltersSet
  >>> fs = FiltersSet("test")
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

Additional documentation is available within source code.

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

Additional documentation is available with source code.

.. |latest-version| image:: https://badge.fury.io/py/sievelib.svg
   :target: https://badge.fury.io/py/sievelib
.. |travis| image:: https://travis-ci.org/tonioo/sievelib.png?branch=master
   :target: https://travis-ci.org/tonioo/sievelib
.. |codecov| image:: http://codecov.io/github/tonioo/sievelib/coverage.svg?branch=master
   :target: http://codecov.io/github/tonioo/sievelib?branch=master
