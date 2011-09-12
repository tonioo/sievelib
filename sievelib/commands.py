# coding: utf-8

"""
SIEVE commands representation

This module contains classes that represent known commands. They all
inherit from the Command class which provides generic method for
command manipulation or parsing.

There are three command types (each one represented by a class):
 * control (ControlCommand) : Control structures are needed to allow
   for multiple and conditional actions
 * action (ActionCommand) : Actions that can be applied on emails
 * test (TestCommand) : Tests are used in conditionals to decide which
   part(s) of the conditional to execute

Finally, each known command is represented by its own class which
provides extra information such as:
 * expected arguments,
 * completion callback,
 * etc.

"""
import sys

class UnknownCommand(Exception):
    """Specific exception raised when an unknown command is encountered"""
    def __init__(self, name):
        self.name = name

    def __str__(self):
        return "unknown command %s" % self.name

class BadArgument(Exception):
    """Specific exception raised when a bad argument is encountered"""
    def __init__(self, command, seen, expected):
        self.command = command
        self.seen = seen
        self.expected = expected

    def __str__(self):
        return "bad argument %s for command %s (%s expected)" \
            % (self.seen, self.command, self.expected)

class BadValue(Exception):
    """Specific exception raised when a bad argument value is encountered"""
    def __init__(self, argument, value):
        self.argument = argument
        self.value = value

    def __str__(self):
        return "bad value %s for argument %s" \
            % (self.value, self.argument)


# Statement elements (see RFC, section 8.3)
# They are used in different commands.
comparator = {"name" : "comparator",
              "type" : ["tag"],
              "values" : [":comparator"],
              "extra_arg" : {"type" : "string",
                             "values" : ['"i;octet"', '"i;ascii-casemap"']},
              "required" : False}
address_part = {"name" : "address-part",
                "values" : [":localpart", ":domain", ":all"],
                "type" : ["tag"],
                "required" : False}
match_type = {"name" : "match-type",
              "values" : [":is", ":contains", ":matches"],
              "type" : ["tag"],
              "required" : False}

class Command(object):
    """Generic command representation.

    A command is described as follow:
     * A name
     * A type
     * A description of supported arguments
     * Does it accept an unkwown quantity of arguments? (ex: anyof, allof)
     * Does it accept children? (ie. subcommands)
     * Is it an extension?
     * Must follow only certain commands
    
    """
    _type = None
    variable_args_nb = False
    accept_children = False
    must_follow = None
    is_extension = False

    def __init__(self, parent=None):
        self.parent = parent
        self.arguments = {}
        self.children = []

        self.nextargpos = 0
        self.required_args = -1
        self.rargs_cnt = 0
        self.curarg = None # for arguments that expect an argument :p (ex: :comparator)

        self.name = self.__class__.__name__.replace("Command", "")
        self.name = self.name.lower()

    def __repr__(self):
        return "%s (type: %s)" % (self.name, self._type)

    def tosieve(self, indentlevel=0, target=sys.stdout):
        """Generate the sieve syntax corresponding to this command

        Recursive method.

        :param indentlevel: current indentation level
        :param target: opened file pointer where the content will be printed
        """
        self.__print(self.name, indentlevel, nocr=True, target=target)
        if self.has_arguments():
            for arg in self.args_definition:
                if not self.arguments.has_key(arg["name"]):
                    continue
                target.write(" ")
                value = self.arguments[arg["name"]]
                if type(value) == list:
                    if self.__get_arg_type(arg["name"]) == ["testlist"]:
                        target.write("(")
                        for t in value:
                            t.tosieve(target=target)
                            if value.index(t) != len(value) - 1:
                                target.write(", ")
                        target.write(")")
                    else:
                        target.write("[" + (", ".join(map(lambda v: '"%s"' % v.strip('"'), value))) + "]")
                    continue
                if isinstance(value, Command):
                    value.tosieve(indentlevel, target=target)
                    continue

                if "tag" in arg["type"] and arg.get("write_tag", False):
                    target.write("%s " % arg["values"][0])

                if "string" in arg["type"]:
                    target.write('"%s"' % value.strip('"'))
                else:
                    target.write(value)

        if not self.accept_children:
            if self.get_type() != "test":
                print >>target, ";"
            return
        if self.get_type() != "control":
            return
        print >>target, " {"
        for ch in self.children:
            ch.tosieve(indentlevel + 4, target=target)
        self.__print("}", indentlevel, target=target)

    def __print(self, data, indentlevel, nocr=False, target=sys.stdout):
        text = "%s%s" % (" " * indentlevel, data)
        if nocr:
            target.write(text)
        else:
            print >>target, text

    def __get_arg_type(self, arg):
        """Return the type corresponding to the given name.

        :param arg: a defined argument name
        """
        for a in self.args_definition:
            if a["name"] == arg:
                return a["type"]
        return None

    def complete_cb(self):
        """Completion callback
        
        Called when a command is considered as complete by the parser.
        """
        pass

    def get_expected_first(self):
        """Return the first expected token for this command"""
        return None

    def has_arguments(self):
        return len(self.args_definition) != 0

    def dump(self, indentlevel=0, target=sys.stdout):
        """Display the command

        Pretty printing of this command and its eventual arguments and
        children. (recursively)

        :param indentlevel: integer that indicates indentation level to apply
        """
        self.__print(self, indentlevel, target=target)
        indentlevel += 4
        if self.has_arguments():
            for arg in self.args_definition:
                if not self.arguments.has_key(arg["name"]):
                    continue
                value = self.arguments[arg["name"]]
                if type(value) == list:
                    if self.__get_arg_type(arg["name"]) == ["testlist"]:
                        for t in value:
                            t.dump(indentlevel, target)
                    else:
                        self.__print("[" + (",".join(value)) + "]", indentlevel, target=target)
                    continue
                if isinstance(value, Command):
                    value.dump(indentlevel, target)
                    continue
                self.__print(str(value), indentlevel, target=target)
        for ch in self.children:
            ch.dump(indentlevel, target)

    def addchild(self, child):
        """Add a new child to the command

        A child corresponds to a command located into a block (this
        command's block). It can be either an action or a control.

        :param child: the new child
        :return: True on succes, False otherwise
        """
        if not self.accept_children:
            return False
        self.children += [child]
        return True

    def iscomplete(self):
        """Check if the command is complete

        Check if all required arguments have been encountered. For
        commands that allow an undefined number of arguments, this
        method always returns False.

        :return: True if command is complete, False otherwise
        """
        if self.variable_args_nb:
            return False
        if self.required_args == -1:
            self.required_args = 0
            for arg in self.args_definition:
                if arg["required"]:
                    self.required_args += 1
        return self.rargs_cnt == self.required_args

    def get_type(self):
        """Return the command's type"""
        if self._type is None:
            raise NotImplemented
        return self._type

    def __is_valid_value_for_arg(self, arg, value):
        """Check if value is allowed for arg

        Some commands only allow a limited set of values. The method
        always returns True for methods that do not provide such a
        set.

        :param arg: the argument's name
        :param value: the value to check
        :return: True on succes, False otherwise
        """
        if not arg.has_key("values"):
            return True
        return value.lower() in arg["values"]

    def check_next_arg(self, atype, avalue, add=True):
        """Argument validity checking

        This method is usually used by the parser to check if detected
        argument is allowed for this command.

        We make a distinction between required and optional
        arguments. Optional (or tagged) arguments can be provided
        unordered but the required ones.

        A special handling is also for arguments that require an
        argument (example: the :comparator argument expects a string
        argument).

        The "testlist" type is checked separately as we can't know in
        advance how many arguments will be provided.

        If the argument is incorrect, the method raises the
        appropriate exception, or return False to let the parser
        handle the exception.

        :param atype: the argument's type
        :param avalue: the argument's value
        :param add: indicates if this argument should be recorded on success
        :return: True on success, False otherwise
        """
        if not self.has_arguments():
            return False
        if self.iscomplete():
            return False

        if self.curarg is not None:
            if atype == self.curarg["extra_arg"]["type"]:
                if not self.curarg["extra_arg"].has_key("values") or \
                        avalue in self.curarg["extra_arg"]["values"]:
                    if add:
                        self.arguments[self.curarg["name"]] = avalue
                    self.curarg = None
                    return True
            raise BadValue(self.curarg["name"], avalue)

        failed = False
        pos = self.nextargpos
        while pos < len(self.args_definition):
            curarg = self.args_definition[pos]
            if curarg["required"]:
                if curarg["type"] == ["testlist"]:
                    if atype != "test":
                        failed = True
                    elif add:
                        if not self.arguments.has_key(curarg["name"]):
                            self.arguments[curarg["name"]] = []
                        self.arguments[curarg["name"]] += [avalue]
                elif atype not in curarg["type"] or \
                        not self.__is_valid_value_for_arg(curarg, avalue):
                    failed = True
                else:
                    self.rargs_cnt += 1
                    self.nextargpos = pos + 1
                    if add:
                        self.arguments[curarg["name"]] = avalue
                break

            if atype in curarg["type"]:
                if self.__is_valid_value_for_arg(curarg, avalue):
                    if curarg.has_key("extra_arg"):
                        self.curarg = curarg
                        break
                    if add:
                        self.arguments[curarg["name"]] = avalue
                    break

            pos += 1

        if failed:
            raise BadArgument(self.name, avalue, 
                              self.args_definition[pos]["type"])
        return True

    def __getitem__(self, name):
        """Shorcut to access a command argument

        :param name: the argument's name
        """
        found = False
        for ad in self.args_definition:
            if ad["name"] == name:
                found = True
                break
        if not found:
            raise KeyError(name)
        if not self.arguments.has_key(name):
            raise KeyError(name)
        return self.arguments[name]

class ControlCommand(Command):
    """Indermediate class to represent "control" commands"""
    _type = "control"
    
class RequireCommand(ControlCommand):
    """The 'require' command

    This class has one big difference with others as it is used to
    store loaded extension names. (The result is we can check for
    unloaded extensions during the parsing)
    """
    args_definition = [
        {"name" : "capabilities",
         "type" : ["string", "stringlist"],
         "required" : True}
        ]

    loaded_extensions = []

    def complete_cb(self):
        if type(self.arguments["capabilities"]) == str:
            exts = [self.arguments["capabilities"]]
        else:
            exts = self.arguments["capabilities"]
        for ext in exts:
            ext = ext.strip('"')
            if not ext in RequireCommand.loaded_extensions:
                RequireCommand.loaded_extensions += [ext]

class StopCommand(ControlCommand):
    args_definition = []

class IfCommand(ControlCommand):
    accept_children = True

    args_definition = [
        {"name" : "test",
         "type" : ["test"],
         "required" : True}
        ]

    def get_expected_first(self):
        return ["identifier"]

class ElsifCommand(ControlCommand):
    accept_children = True
    must_follow = ["if", "elsif"]
    args_definition = [
        {"name" : "test",
         "type" : ["test"],
         "required" : True}
        ]

    def get_expected_first(self):
        return ["identifier"]

class ElseCommand(ControlCommand):
    accept_children = True
    must_follow = ["if", "elsif"]
    args_definition = []

class ActionCommand(Command):
    """Indermediate class to represent "action" commands"""
    _type = "action"

class FileintoCommand(ActionCommand):
    is_extension = True
    args_definition = [
        {"name" : "mailbox",
         "type" : ["string"],
         "required" : True}
        ]

class RedirectCommand(ActionCommand):
    args_definition = [
        {"name" : "address",
         "type" : ["string"],
         "required" : True}
        ]

class KeepCommand(ActionCommand):
    args_definition = []

class DiscardCommand(ActionCommand):
    args_definition = []

class TestCommand(Command):
    """Indermediate class to represent "test" commands"""
    _type = "test"

class AddressCommand(TestCommand):
    args_definition = [
        comparator,
        address_part,
        match_type,
        {"name" : "header-list",
         "type" : ["string", "stringlist"],
         "required" : True},
        {"name" : "key-list",
         "type" : ["string", "stringlist"],
         "required" : True}
        ]

class AllofCommand(TestCommand):
    accept_children = True
    variable_args_nb = True

    args_definition = [
        {"name" : "tests",
         "type" : ["testlist"],
         "required" : True}
        ]

    def get_expected_first(self):
        return ["left_parenthesis"]

class AnyofCommand(TestCommand):
    accept_children = True
    variable_args_nb = True

    args_definition = [
        {"name" : "tests",
         "type" : ["testlist"],
         "required" : True}
        ]

    def get_expected_first(self):
        return ["left_parenthesis"]

class EnvelopeCommand(TestCommand):
    args_definition = [
        comparator,
        address_part,
        match_type,
        {"name" : "header-list",
         "type" : ["string", "stringlist"],
         "required" : True},
        {"name" : "key-list",
         "type" : ["string", "stringlist"],
         "required" : True}
        ]

class ExistsCommand(TestCommand):
    args_definition = [
        {"name" : "header-names",
         "type" : ["stringlist"],
         "required" : True}
        ]

class TrueCommand(TestCommand):
    args_definition = []

class FalseCommand(TestCommand):
    args_definition = []

class HeaderCommand(TestCommand):
    args_definition = [
        comparator,
        match_type,
        {"name" : "header-names",
         "type" : ["string", "stringlist"],
         "required" : True},
        {"name" : "key-list",
         "type" : ["string", "stringlist"],
         "required" : True}
        ]

class NotCommand(TestCommand):
    accept_children = True

    args_definition = [
        {"name" : "test",
         "type" : ["test"],
         "required" : True}
        ]

    def get_expected_first(self):
        return ["identifier"]

class SizeCommand(TestCommand):
    args_definition = [
        {"name" : "comparator",
         "type" : ["tag"],
         "values" : [":over", ":under"],
         "required" : True},
        {"name" : "limit",
         "type" : ["number"],
         "required" : True},
        ]

class VacationCommand(ActionCommand):
    args_definition = [
        {"name" : "subject",
          "type" : ["tag"],
          "write_tag": True,
          "values" : [":subject"],
          "extra_arg" : {"type" : "string"},
          "required" : False},
        {"name" : "days",
          "type" : ["tag"],
          "write_tag": True,
          "values" : [":days"],
          "extra_arg" : {"type" : "number"},
          "required" : False},
        {"name" : "from",
          "type" : ["tag"],
          "write_tag": True,
          "values" : [":from"],
          "extra_arg" : {"type" : "string"},
          "required" : False},
        {"name" : "addresses",
          "type" : ["tag"],
          "write_tag": True,
          "values" : [":addresses"],
          "extra_arg" : {"type" : "stringlist"},
          "required" : False},
        {"name" : "handle",
          "type" : ["tag"],
          "write_tag": True,
          "values" : [":handle"],
          "extra_arg" : {"type" : "string"},
          "required" : False},
        {"name" : "mime",
          "type" : ["tag"],
          "write_tag": True,
          "values" : [":mime"],
          "required" : False},
        {"name" : "reason",
         "type" : ["string"],
         "required" : True},
        ]


def get_command_instance(name, parent=None, checkexists=True):
    """Try to guess and create the appropriate command instance

    Given a command name (encountered by the parser), construct the
    associated class name and, if known, return a new instance.

    If the command is not known or has not been loaded using require,
    an UnknownCommand exception is raised.

    :param name: the command's name
    :param parent: the eventual parent command
    :return: a new class instance
    """
    cname = "%sCommand" % name.lower().capitalize()
    if not globals().has_key(cname) or \
            (checkexists and globals()[cname].is_extension and \
                 not name in RequireCommand.loaded_extensions):
        raise UnknownCommand(name)
    return globals()[cname](parent)
