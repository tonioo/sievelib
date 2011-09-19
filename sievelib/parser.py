#!/usr/bin/env python
# coding: utf-8

"""
This module provides a simple but functional parser for the SIEVE
language used to filter emails.

This implementation is based on RFC 5228 (http://tools.ietf.org/html/rfc5228)

"""
import re
import sys

from commands import get_command_instance, UnknownCommand, BadArgument, BadValue

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
    
      [("left_bracket", r'\['),]
    """
    def __init__(self, definitions):
        self.definitions = definitions
        parts = []
        for name, part in definitions:
            parts.append("(?P<%s>%s)" % (name, part))
        self.regexpString = "|".join(parts)
        self.regexp = re.compile(self.regexpString, re.MULTILINE)
        self.wsregexp = re.compile(r'\s+', re.M)

    def curlineno(self):
        """Return the current line number"""
        return self.text[:self.pos].count('\n') + 1

    def scan(self, text):
        """Analyse some data

        Analyse the passed content. Each time a token is recognized, a
        2-uple containing its name and parsed value is raised (via
        yield).

        On error, a ParseError exception is raised.

        :param text: a string containing the data to parse
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
                lineno = self.curlineno()
                raise ParseError("unknown token %s" % text[self.pos:])

            self.pos = m.end()
            yield (m.lastgroup, m.group(m.lastgroup))

class Parser(object):
    """The grammatical analysis part.

    Here we define the SIEVE language tokens and grammar. This class
    works with a Lexer object in order to check for grammar validity.
    """
    lrules = [
        ("left_bracket", r'\['),
        ("right_bracket", r'\]'),
        ("left_parenthesis", r'\('),
        ("right_parenthesis", r'\)'),
        ("left_cbracket", r'{'),
        ("right_cbracket", r'}'),
        ("semicolon", r';'),
        ("comma", r','),
        ("hash_comment", r'#.*$'),
        ("bracket_comment", r'/\*[\s\S]*?\*/'),
        ("multiline", r'text:[^$]*[\r\n]+\.$'),
        ("string", r'"([^"\\]|\\.)*"'),
        ("identifier", r'[a-zA-Z_][\w]*'),
        ("tag", r':[a-zA-Z_][\w]*'),
        ("number", r'[0-9]+[KMGkmg]?'),
        ]

    def __init__(self, debug=False):
        self.debug = debug
        self.lexer = Lexer(Parser.lrules)

    def __dprint(self, *msgs):
        if not self.debug:
            return
        for m in msgs:
            print m

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
                raise ParseError("the %s command must follow an %s command" % \
                                     (self.__curcommand.name,
                                      " or ".join(self.__curcommand.must_follow)))

        if not self.__curcommand.parent:
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
                (ctype == "control" and \
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
            self.__curstringlist += [tvalue]
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
        if ttype == "multiline":
            return self.__curcommand.check_next_arg("string", tvalue)

        if ttype in ["number", "tag", "string"]:
            return self.__curcommand.check_next_arg(ttype, tvalue)

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
            test = get_command_instance(tvalue, self.__curcommand)
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
            return self.__check_command_completion()

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
            command = get_command_instance(tvalue, self.__curcommand)
            if command.get_type() == "test":
                raise ParseError("%s may not appear as a first command" % command.name)
            if command.get_type() == "control" and command.accept_children \
                    and command.has_arguments():
                self.__set_expected("identifier")
            if self.__curcommand is not None:
                if not self.__curcommand.addchild(command):
                    raise ParseError("%s unexpected after a %s" % \
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
        self.__reset_parser()
        try:
            for ttype, tvalue in self.lexer.scan(text):
                if ttype == "hash_comment":
                    self.hash_comments += [tvalue]
                    continue
                if ttype == "bracket_comment":
                    continue
                if self.__expected is not None:
                    if not ttype in self.__expected:
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
                raise ParseError("end of script reached while %s expected" % \
                                     "|".join(self.__expected))

        except (ParseError, UnknownCommand, BadArgument, BadValue), e:
            self.error = "line %d: %s" % (self.lexer.curlineno(), str(e))
            return False
        return True

    def parse_file(self, name):
        """Parse the content of a file.

        See 'parse' method for information.

        :param name: the pathname of the file to parse
        :return: True on success (no error detected), False otherwise
        """
        fp = open(name)
        content = fp.read()
        fp.close()
        return self.parse(content)

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
    options, args = op.parse_args()

    if not len(args):
        print "Nothing to parse, exiting."
        sys.exit(0)

    for a in args:
        p = Parser(debug=options.debug)
        print "Parsing file %s... " % a,
        if p.parse_file(a):
            print "OK"
            if options.verbose:
                p.dump()
            continue
        print "ERROR"
        print p.error

    
