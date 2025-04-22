#!/usr/bin/env python

"""
This module provides a simple but functional parser for the SIEVE
language used to filter emails.

This implementation is based on RFC 5228 (http://tools.ietf.org/html/rfc5228)

"""
import re
import sys
from typing import Iterator, Tuple

from sievelib.commands import get_command_instance, CommandError, RequireCommand


class ParseError(Exception):
    """Generic parsing error"""

    def __init__(self, msg: str):
        self.msg = msg

    def __str__(self):
        return f"parsing error: {self.msg}"


class Lexer:
    r"""
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
            param = b"(?P<%s>%s)" % (name, part)
            parts.append(param)
        self.regexpString = b"|".join(parts)
        self.regexp = re.compile(self.regexpString, re.MULTILINE)
        self.wsregexp = re.compile(rb"\s+", re.M)

    def curlineno(self) -> int:
        """Return the current line number"""
        return self.text[: self.pos].count(b"\n") + 1

    def curcolno(self) -> int:
        """Return the current column number"""
        return self.pos - self.text.rfind(b"\n", 0, self.pos)

    def scan(self, text: bytes) -> Iterator[Tuple[str, bytes]]:
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
                token = text[self.pos :]
                m = self.wsregexp.search(token)
                if m is not None:
                    token = token[: m.start()]
                raise ParseError(f"unknown token {token}")

            yield (m.lastgroup, m.group(m.lastgroup))
            self.pos += len(m.group(0))


class Parser:
    """The grammatical analysis part.

    Here we define the SIEVE language tokens and grammar. This class
    works with a Lexer object in order to check for grammar validity.
    """

    lrules = [
        (b"left_bracket", rb"\["),
        (b"right_bracket", rb"\]"),
        (b"left_parenthesis", rb"\("),
        (b"right_parenthesis", rb"\)"),
        (b"left_cbracket", rb"{"),
        (b"right_cbracket", rb"}"),
        (b"semicolon", rb";"),
        (b"comma", rb","),
        (b"hash_comment", rb"#.*$"),
        (b"bracket_comment", rb"/\*[\s\S]*?\*/"),
        (b"multiline", rb"text:[^$]*?[\r\n]+\.$"),
        (b"string", rb'"([^"\\]|\\.)*"'),
        (b"identifier", rb"[a-zA-Z_][\w]*"),
        (b"tag", rb":[a-zA-Z_][\w]*"),
        (b"number", rb"[0-9]+[KMGkmg]?"),
    ]

    def __init__(self, debug: bool = False):
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
        self.__expected_brackets = []
        RequireCommand.loaded_extensions = []

    def __set_expected(self, *args, **kwargs):
        """Set the next expected token.

        One or more tokens can be provided. (they will represent the
        valid possibilities for the next token).
        """
        self.__expected = args

    def __push_expected_bracket(self, ttype: str, tvalue: bytes):
        """Append a new expected bracket.

        Next time a bracket is closed, it must match the one provided here.
        """
        self.__expected_brackets.append((ttype, tvalue))

    def __pop_expected_bracket(self, ttype: str, tvalue):
        """Drop the last expected bracket.

        If the given bracket doesn't match the dropped expected bracket,
        or if no bracket is expected at all, a ParseError will be raised.
        """
        try:
            etype, evalue = self.__expected_brackets.pop()
        except IndexError:
            raise ParseError("unexpected closing bracket %s (none opened)" % (tvalue,))
        if ttype != etype:
            raise ParseError(
                "unexpected closing bracket %s (expected %s)" % (tvalue, evalue)
            )

    def __up(self, onlyrecord: bool = False):
        """Return to the current command's parent

        This method should be called each time a command is
        complete. In case of a top level command (no parent), it is
        recorded into a specific list for further usage.

        :param onlyrecord: tell to only record the new command into its parent.
        """
        if self.__curcommand.must_follow is not None:
            if not self.__curcommand.parent:
                prevcmd = self.result[-1] if len(self.result) != 0 else None
            else:
                prevcmd = (
                    self.__curcommand.parent.children[-2]
                    if len(self.__curcommand.parent.children) >= 2
                    else None
                )
            if prevcmd is None or prevcmd.name not in self.__curcommand.must_follow:
                raise ParseError(
                    "the %s command must follow an %s command"
                    % (
                        self.__curcommand.name,
                        " or ".join(self.__curcommand.must_follow),
                    )
                )

        if not self.__curcommand.parent:
            # collect current amount of hash comments for later
            # parsing into names and desciptions
            self.__curcommand.hash_comments = self.hash_comments
            self.hash_comments = []
            self.result += [self.__curcommand]

        if onlyrecord:
            # We are done
            return

        while self.__curcommand:
            self.__curcommand = self.__curcommand.parent
            if not self.__curcommand:
                break
            # Make sure to detect all done tests (including 'not' ones).
            condition = (
                self.__curcommand.get_type() == "test"
                and self.__curcommand.iscomplete()
            )
            if condition:
                continue
            # If we are on a control accepting a test list, next token
            # must be a comma or a right parenthesis.
            condition = (
                self.__curcommand.get_type() == "test"
                and self.__curcommand.variable_args_nb
            )
            if condition:
                self.__set_expected("comma", "right_parenthesis")
            break

    def __check_command_completion(self, testsemicolon: bool = True) -> bool:
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
        condition = ctype == "action" or (
            ctype == "control" and not self.__curcommand.accept_children
        )
        if condition:
            if testsemicolon:
                self.__set_expected("semicolon")
            return True

        while self.__curcommand.parent:
            cmd = self.__curcommand
            self.__curcommand = self.__curcommand.parent
            if self.__curcommand.get_type() in ["control", "test"]:
                if self.__curcommand.iscomplete():
                    if self.__curcommand.get_type() == "control":
                        self.__set_expected("left_cbracket")
                        break
                    continue
                if not self.__curcommand.check_next_arg("test", cmd, add=False):
                    return False
                if not self.__curcommand.iscomplete():
                    if self.__curcommand.variable_args_nb:
                        self.__set_expected("comma", "right_parenthesis")
                    break
        return True

    def __stringlist(self, ttype: str, tvalue: bytes) -> bool:
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
            self.__pop_expected_bracket(ttype, tvalue)
            self.__curcommand.check_next_arg("stringlist", self.__curstringlist)
            self.__cstate = self.__arguments
            return self.__check_command_completion()
        return False

    def __argument(self, ttype: str, tvalue: bytes) -> bool:
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
            self.__push_expected_bracket("right_bracket", b"}")
            self.__cstate = self.__stringlist
            self.__curstringlist = []
            self.__set_expected("string")
            return True

        condition = (
            ttype in ["left_cbracket", "comma"]
            and self.__curcommand.non_deterministic_args
        )
        if condition:
            self.__curcommand.reassign_arguments()
            # rewind lexer
            self.lexer.pos -= 1
            return True

        return False

    def __arguments(self, ttype: str, tvalue: bytes) -> bool:
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
            if test.get_type() != "test":
                raise ParseError(
                    "Expected test command, '{}' found instead".format(test.name)
                )
            self.__curcommand.check_next_arg("test", test)
            self.__expected = test.get_expected_first()
            self.__curcommand = test
            return self.__check_command_completion(testsemicolon=False)

        if ttype == "left_parenthesis":
            self.__push_expected_bracket("right_parenthesis", b")")
            self.__set_expected("identifier")
            return True

        if ttype == "comma":
            self.__set_expected("identifier")
            return True

        if ttype == "right_parenthesis":
            self.__pop_expected_bracket(ttype, tvalue)
            self.__up()
            return True

        if self.__argument(ttype, tvalue):
            return self.__check_command_completion(testsemicolon=False)

        return False

    def __command(self, ttype: str, tvalue: bytes) -> bool:
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
                self.__pop_expected_bracket(ttype, tvalue)
                self.__up()
                self.__cstate = None
                return True

            if ttype != "identifier":
                return False
            command = get_command_instance(tvalue.decode("ascii"), self.__curcommand)
            if command.get_type() == "test":
                raise ParseError("%s may not appear as a first command" % command.name)
            if (
                command.get_type() == "control"
                and command.accept_children
                and command.has_arguments()
            ):
                self.__set_expected("identifier")
            if self.__curcommand is not None:
                if not self.__curcommand.addchild(command):
                    raise ParseError(
                        "%s unexpected after a %s" % (tvalue, self.__curcommand.name)
                    )
            self.__curcommand = command
            self.__cstate = self.__arguments

            return True

        if self.__cstate(ttype, tvalue):
            return True

        if ttype == "left_cbracket":
            self.__push_expected_bracket("right_cbracket", b"}")
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

    def parse(self, text: bytes) -> bool:
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
        if isinstance(text, str):
            text = text.encode("utf-8")

        self.__reset_parser()
        try:
            ttype: str
            tvalue: bytes = b""
            for ttype, tvalue in self.lexer.scan(text):
                if ttype == "hash_comment":
                    self.hash_comments += [tvalue.strip()]
                    continue
                if ttype == "bracket_comment":
                    continue
                if self.__expected is not None:
                    if ttype not in self.__expected:
                        if self.lexer.pos < len(text) + len(tvalue):
                            msg = "{} found while {} expected near '{}'".format(
                                ttype,
                                "|".join(self.__expected),
                                text.decode()[self.lexer.pos],
                            )
                        else:
                            msg = "%s found while %s expected at end of file" % (
                                ttype,
                                "|".join(self.__expected),
                            )
                        raise ParseError(msg)
                    self.__expected = None

                if not self.__command(ttype, tvalue):
                    msg = "unexpected token '%s' found near '%s'" % (
                        tvalue.decode(),
                        text.decode()[self.lexer.pos],
                    )
                    raise ParseError(msg)
            if self.__expected_brackets:
                self.__set_expected(self.__expected_brackets[-1][0])
            if self.__expected is not None:
                raise ParseError(
                    "end of script reached while %s expected"
                    % "|".join(self.__expected)
                )

        except (ParseError, CommandError) as e:
            self.error_pos = (
                self.lexer.curlineno(),
                self.lexer.curcolno(),
                len(tvalue),
            )
            self.error = "line %d: %s" % (self.error_pos[0], str(e))
            return False
        return True

    def parse_file(self, name: str) -> bool:
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
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        default=False,
        help="Activate verbose mode",
    )
    parser.add_argument(
        "-d",
        "--debug",
        action="store_true",
        default=False,
        help="Activate debug traces",
    )
    parser.add_argument(
        "--tosieve", action="store_true", help="Print parser results using sieve"
    )
    parser.add_argument("files", type=str, nargs="+", help="Files to parse")
    args = parser.parse_args()
    for fname in args.files:
        p = Parser(debug=args.debug)
        print(f"Parsing file {fname}... ", end=" ")
        if p.parse_file(fname):
            print("OK")
            if args.verbose:
                p.dump()
            if args.tosieve:
                for r in p.result:
                    r.tosieve()
            continue
        print("ERROR")
        print(p.error)
