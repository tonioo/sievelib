#!/usr/bin/env python
# coding: utf-8

"""
This module provides a simple but functional parser for the SIEVE
language used to filter emails.

This implementation is based on RFC 5228 (http://tools.ietf.org/html/rfc5228)

"""
from __future__ import print_function

import re
import sys

from future.utils import python_2_unicode_compatible, text_type
import six

from sievelib.commands import (
    get_command_instance, CommandError, RequireCommand)


@python_2_unicode_compatible
class ParseError(Exception):
    """Generic parsing error"""

    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return "parsing error: %s" % self.msg


class Lexer(object):
    """
    The lexical analysis part.

    This class provides a simple way to define tokens (with patterns)
    to be detected.

    Patterns are provided into a list of 2-uple. Each 2-uple consists
    of a token name and an associated pattern, example:

      [(b"left_bracket", br'\['),]
    """

    def __init__(self, definitions):
        self.definitions = definitions
        parts = []
        for name, part in definitions:
            param = "(?P<%s>%s)" % (name.decode(), part.decode())
            if six.PY3:
                param = bytes(param, "utf-8")
            parts.append(param)
        self.regexpString = b"|".join(parts)
        self.regexp = re.compile(self.regexpString, re.MULTILINE)
        self.wsregexp = re.compile(br'\s+', re.M)

    def curlineno(self):
        """Return the current line number"""
        return self.text[:self.pos].count(b'\n') + 1

    def scan(self, text):
        """Analyse some data

        Analyse the passed content. Each time a token is recognized, a
        2-uple containing its name and parsed value is raised (via
        yield).

        On error, a ParseError exception is raised.

        :param text: a binary string containing the data to parse
        """
        self.pos = 0
        self.text = text
        while self.pos < len(text):
            m = self.wsregexp.match(text, self.pos)
            if m is not None:
                self.pos = m.end()
                continue

            m = self.regexp.match(text, self.pos)
            if m is None:
                raise ParseError("unknown token %s" % text[self.pos:])

            self.pos = m.end()
            yield (m.lastgroup, m.group(m.lastgroup))


class Parser(object):
    """The grammatical analysis part.

    Here we define the SIEVE language tokens and grammar. This class
    works with a Lexer object in order to check for grammar validity.
    """
    lrules = [
        (b"left_bracket", br'\['),
        (b"right_bracket", br'\]'),
        (b"left_parenthesis", br'\('),
        (b"right_parenthesis", br'\)'),
        (b"left_cbracket", br'{'),
        (b"right_cbracket", br'}'),
        (b"semicolon", br';'),
        (b"comma", br','),
        (b"hash_comment", br'#.*$'),
        (b"bracket_comment", br'/\*[\s\S]*?\*/'),
        (b"multiline", br'text:[^$]*?[\r\n]+\.$'),
        (b"string", br'"([^"\\]|\\.)*"'),
        (b"identifier", br'[a-zA-Z_][\w]*'),
        (b"tag", br':[a-zA-Z_][\w]*'),
        (b"number", br'[0-9]+[KMGkmg]?'),
    ]

    def __init__(self, debug=False):
        self.debug = debug
        self.lexer = Lexer(Parser.lrules)

    def __dprint(self, *msgs):
        if not self.debug:
            return
        for m in msgs:
            print(m)

    def __reset_parser(self):
        """Reset parser's internal variables

        Restore the parser to an initial state. Useful when creating a
        new parser or reusing an existing one.
        """
        self.result = []
        self.hash_comments = []

        self.__cstate = None
        self.__curcommand = None
        self.__curstringlist = None
        self.__expected = None
        self.__opened_blocks = 0
        RequireCommand.loaded_extensions = []

    def __set_expected(self, *args, **kwargs):
        """Set the next expected token.

        One or more tokens can be provided. (they will represent the
        valid possibilities for the next token).
        """
        self.__expected = args

    def __up(self, onlyrecord=False):
        """Return to the current command's parent

        This method should be called each time a command is
        complete. In case of a top level command (no parent), it is
        recorded into a specific list for further usage.

        :param onlyrecord: tell to only record the new command into its parent.
        """
        if self.__curcommand.must_follow is not None:
            if not self.__curcommand.parent:
                prevcmd = self.result[-1] if len(self.result) else None
            else:
                prevcmd = self.__curcommand.parent.children[-2] \
                    if len(self.__curcommand.parent.children) >= 2 else None
            if prevcmd is None or prevcmd.name not in self.__curcommand.must_follow:
                raise ParseError("the %s command must follow an %s command" %
                                 (self.__curcommand.name,
                                  " or ".join(self.__curcommand.must_follow)))

        if not self.__curcommand.parent:
            # collect current amount of hash comments for later
            # parsing into names and desciptions
            self.__curcommand.hash_comments = self.hash_comments
            self.hash_comments = []
            self.result += [self.__curcommand]

        if not onlyrecord:
            self.__curcommand = self.__curcommand.parent

    def __check_command_completion(self, testsemicolon=True):
        """Check for command(s) completion

        This function should be called each time a new argument is
        seen by the parser in order to check a command is complete. As
        not only one command can be ended when receiving a new
        argument (nested commands case), we apply the same work to
        parent commands.

        :param testsemicolon: if True, indicates that the next
        expected token must be a semicolon (for commands that need one)
        :return: True if command is
        considered as complete, False otherwise.
        """
        if not self.__curcommand.iscomplete():
            return True

        ctype = self.__curcommand.get_type()
        if ctype == "action" or \
                (ctype == "control" and
                 not self.__curcommand.accept_children):
            if testsemicolon:
                self.__set_expected("semicolon")
            return True

        while self.__curcommand.parent:
            cmd = self.__curcommand
            self.__curcommand = self.__curcommand.parent
            if self.__curcommand.get_type() in ["control", "test"]:
                if self.__curcommand.iscomplete():
                    if self.__curcommand.get_type() == "control":
                        break
                    continue
                if not self.__curcommand.check_next_arg("test", cmd, add=False):
                    return False
                if not self.__curcommand.iscomplete():
                    if self.__curcommand.variable_args_nb:
                        self.__set_expected("comma", "right_parenthesis")
                    break

        return True

    def __stringlist(self, ttype, tvalue):
        """Specific method to parse the 'string-list' type

        Syntax:
            string-list = "[" string *("," string) "]" / string
                            ; if there is only a single string, the brackets
                            ; are optional
        """
        if ttype == "string":
            self.__curstringlist += [tvalue.decode("utf-8")]
            self.__set_expected("comma", "right_bracket")
            return True
        if ttype == "comma":
            self.__set_expected("string")
            return True
        if ttype == "right_bracket":
            self.__curcommand.check_next_arg("stringlist", self.__curstringlist)
            self.__cstate = self.__arguments
            return self.__check_command_completion()
        return False

    def __argument(self, ttype, tvalue):
        """Argument parsing method

        This method acts as an entry point for 'argument' parsing.

        Syntax:
            string-list / number / tag

        :param ttype: current token type
        :param tvalue: current token value
        :return: False if an error is encountered, True otherwise
        """
        if ttype in ["multiline", "string"]:
            return self.__curcommand.check_next_arg("string", tvalue.decode("utf-8"))

        if ttype in ["number", "tag"]:
            return self.__curcommand.check_next_arg(ttype, tvalue.decode("ascii"))

        if ttype == "left_bracket":
            self.__cstate = self.__stringlist
            self.__curstringlist = []
            self.__set_expected("string")
            return True
        return False

    def __arguments(self, ttype, tvalue):
        """Arguments parsing method

        Entry point for command arguments parsing. The parser must
        call this method for each parsed command (either a control,
        action or test).

        Syntax:
            *argument [ test / test-list ]

        :param ttype: current token type
        :param tvalue: current token value
        :return: False if an error is encountered, True otherwise
        """
        if ttype == "identifier":
            test = get_command_instance(tvalue.decode("ascii"), self.__curcommand)
            self.__curcommand.check_next_arg("test", test)
            self.__expected = test.get_expected_first()
            self.__curcommand = test
            return self.__check_command_completion(testsemicolon=False)

        if ttype == "left_parenthesis":
            self.__set_expected("identifier")
            return True

        if ttype == "comma":
            self.__set_expected("identifier")
            return True

        if ttype == "right_parenthesis":
            self.__up()
            return True

        if self.__argument(ttype, tvalue):
            return self.__check_command_completion(testsemicolon=False)

        return False

    def __command(self, ttype, tvalue):
        """Command parsing method

        Entry point for command parsing. Here is expected behaviour:
         * Handle command beginning if detected,
         * Call the appropriate sub-method (specified by __cstate) to
           handle the body,
         * Handle command ending or block opening if detected.

        Syntax:
            identifier arguments (";" / block)

        :param ttype: current token type
        :param tvalue: current token value
        :return: False if an error is encountered, True otherwise
        """
        if self.__cstate is None:
            if ttype == "right_cbracket":
                self.__up()
                self.__opened_blocks -= 1
                self.__cstate = None
                return True

            if ttype != "identifier":
                return False
            command = get_command_instance(
                tvalue.decode("ascii"), self.__curcommand)
            if command.get_type() == "test":
                raise ParseError(
                    "%s may not appear as a first command" % command.name)
            if command.get_type() == "control" and command.accept_children \
               and command.has_arguments():
                self.__set_expected("identifier")
            if self.__curcommand is not None:
                if not self.__curcommand.addchild(command):
                    raise ParseError("%s unexpected after a %s" %
                                     (tvalue, self.__curcommand.name))
            self.__curcommand = command
            self.__cstate = self.__arguments

            return True

        if self.__cstate(ttype, tvalue):
            return True

        if ttype == "left_cbracket":
            self.__opened_blocks += 1
            self.__cstate = None
            return True

        if ttype == "semicolon":
            self.__cstate = None
            if not self.__check_command_completion(testsemicolon=False):
                return False
            self.__curcommand.complete_cb()
            self.__up()
            return True
        return False

    def parse(self, text):
        """The parser entry point.

        Parse the provided text to check for its validity.

        On success, the parsing tree is available into the result
        attribute. It is a list of sievecommands.Command objects (see
        the module documentation for specific information).

        On error, an string containing the explicit reason is
        available into the error attribute.

        :param text: a string containing the data to parse
        :return: True on success (no error detected), False otherwise
        """
        if isinstance(text, text_type):
            text = text.encode("utf-8")

        self.__reset_parser()
        try:
            for ttype, tvalue in self.lexer.scan(text):
                if ttype == "hash_comment":
                    self.hash_comments += [tvalue.strip()]
                    continue
                if ttype == "bracket_comment":
                    continue
                if self.__expected is not None:
                    if ttype not in self.__expected:
                        if self.lexer.pos < len(text):
                            msg = "%s found while %s expected near '%s'" \
                                  % (ttype, "|".join(self.__expected), text[self.lexer.pos])
                        else:
                            msg = "%s found while %s expected at end of file" \
                                  % (ttype, "|".join(self.__expected))
                        raise ParseError(msg)
                    self.__expected = None

                if not self.__command(ttype, tvalue):
                    msg = "unexpected token '%s' found near '%s'" \
                          % (tvalue, text[self.lexer.pos])
                    raise ParseError(msg)
            if self.__opened_blocks:
                self.__set_expected("right_cbracket")
            if self.__expected is not None:
                raise ParseError("end of script reached while %s expected" %
                                 "|".join(self.__expected))

        except (ParseError, CommandError) as e:
            self.error = "line %d: %s" % (self.lexer.curlineno(), str(e))
            return False
        return True

    def parse_file(self, name):
        """Parse the content of a file.

        See 'parse' method for information.

        :param name: the pathname of the file to parse
        :return: True on success (no error detected), False otherwise
        """
        with open(name, "rb") as fp:
            return self.parse(fp.read())

    def dump(self, target=sys.stdout):
        """Dump the parsing tree.

        This method displays the parsing tree on the standard output.
        """
        for r in self.result:
            r.dump(target=target)


if __name__ == "__main__":
    from optparse import OptionParser

    op = OptionParser()
    op.usage = "%prog: [options] files"
    op.add_option("-v", "--verbose", action="store_true", default=False,
                  help="Activate verbose mode")
    op.add_option("-d", "--debug", action="store_true", default=False,
                  help="Activate debug traces")
    op.add_option("--tosieve", action="store_true",
                  help="Print parser results using sieve")
    options, args = op.parse_args()

    if not len(args):
        print("Nothing to parse, exiting.")
        sys.exit(0)

    for a in args:
        p = Parser(debug=options.debug)
        print("Parsing file %s... " % a, end=' ')
        if p.parse_file(a):
            print("OK")
            if options.verbose:
                p.dump()
            if options.tosieve:
                for r in p.result:
                    r.tosieve()
            continue
        print("ERROR")
        print(p.error)
