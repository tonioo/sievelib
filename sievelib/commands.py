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
from collections.abc import Iterable
from . import tools


class CommandError(Exception):
    """Base command exception class."""

    pass


class UnknownCommand(CommandError):
    """Specific exception raised when an unknown command is encountered"""

    def __init__(self, name):
        self.name = name

    def __str__(self):
        return "unknown command %s" % self.name


class BadArgument(CommandError):
    """Specific exception raised when a bad argument is encountered"""

    def __init__(self, command, seen, expected):
        self.command = command
        self.seen = seen
        self.expected = expected

    def __str__(self):
        return "bad argument %s for command %s (%s expected)" % (
            self.seen,
            self.command,
            self.expected,
        )


class BadValue(CommandError):
    """Specific exception raised when a bad argument value is encountered"""

    def __init__(self, argument, value):
        self.argument = argument
        self.value = value

    def __str__(self):
        return "bad value %s for argument %s" % (self.value, self.argument)


class ExtensionNotLoaded(CommandError):
    """Raised when an extension is not loaded."""

    def __init__(self, name):
        self.name = name

    def __str__(self):
        return "extension '{}' not loaded".format(self.name)


# Statement elements (see RFC, section 8.3)
# They are used in different commands.
comparator = {
    "name": "comparator",
    "type": ["tag"],
    "values": [":comparator"],
    "extra_arg": {"type": "string", "values": ['"i;octet"', '"i;ascii-casemap"']},
    "required": False,
}
address_part = {
    "name": "address-part",
    "values": [":localpart", ":domain", ":all"],
    "type": ["tag"],
    "required": False,
}
match_type = {
    "name": "match-type",
    "values": [":is", ":contains", ":matches"],
    "extension_values": {
        ":count": "relational",
        ":value": "relational",
        ":regex": "regex",
    },
    "extra_arg": {
        "type": "string",
        "values": ['"gt"', '"ge"', '"lt"', '"le"', '"eq"', '"ne"'],
        "valid_for": [":count", ":value"],
    },
    "type": ["tag"],
    "required": False,
}


class Command(object):
    """Generic command representation.

    A command is described as follow:
     * A name
     * A type
     * A description of supported arguments
     * Does it accept an unknown quantity of arguments? (ex: anyof, allof)
     * Does it accept children? (ie. subcommands)
     * Is it an extension?
     * Must follow only certain commands

    """

    _type = None
    variable_args_nb = False
    non_deterministic_args = False
    accept_children = False
    must_follow = None
    extension = None

    def __init__(self, parent=None):
        self.parent = parent
        self.arguments = {}
        self.extra_arguments = {}  # to store tag arguments
        self.children = []

        self.nextargpos = 0
        self.required_args = -1
        self.rargs_cnt = 0
        self.curarg = None  # for arguments that expect an argument :p (ex: :comparator)

        self.name = self.__class__.__name__.replace("Command", "")
        self.name = self.name.lower()

        self.hash_comments = []

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
                if not arg["name"] in self.arguments:
                    continue
                target.write(" ")
                value = self.arguments[arg["name"]]
                atype = arg["type"]
                if "tag" in atype:
                    target.write(value)
                    if arg["name"] in self.extra_arguments:
                        value = self.extra_arguments[arg["name"]]
                        atype = arg["extra_arg"]["type"]
                        target.write(" ")
                    else:
                        continue

                if type(value) == list:
                    if self.__get_arg_type(arg["name"]) == ["testlist"]:
                        target.write("(")
                        for t in value:
                            t.tosieve(target=target)
                            if value.index(t) != len(value) - 1:
                                target.write(", ")
                        target.write(")")
                    else:
                        target.write(
                            "[{}]".format(
                                ", ".join(['"%s"' % v.strip('"') for v in value])
                            )
                        )
                    continue
                if isinstance(value, Command):
                    value.tosieve(indentlevel, target=target)
                    continue

                if "string" in atype:
                    target.write(value)
                    if not value.startswith('"') and not value.startswith("["):
                        target.write("\n")
                else:
                    target.write(value)

        if not self.accept_children:
            if self.get_type() != "test":
                target.write(";\n")
            return
        if self.get_type() != "control":
            return
        target.write(" {\n")
        for ch in self.children:
            ch.tosieve(indentlevel + 4, target=target)
        self.__print("}", indentlevel, target=target)

    def __print(self, data, indentlevel, nocr=False, target=sys.stdout):
        text = "%s%s" % (" " * indentlevel, data)
        if nocr:
            target.write(text)
        else:
            target.write(text + "\n")

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

    def reassign_arguments(self):
        """Reassign arguments to proper slots.

        Should be called when parsing of commands with non
        deterministic arguments is considered done.
        """
        raise NotImplementedError

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
                if not arg["name"] in self.arguments:
                    continue
                value = self.arguments[arg["name"]]
                atype = arg["type"]
                if "tag" in atype:
                    self.__print(str(value), indentlevel, target=target)
                    if arg["name"] in self.extra_arguments:
                        value = self.extra_arguments[arg["name"]]
                        atype = arg["extra_arg"]["type"]
                    else:
                        continue
                if type(value) == list:
                    if self.__get_arg_type(arg["name"]) == ["testlist"]:
                        for t in value:
                            t.dump(indentlevel, target)
                    else:
                        self.__print(
                            "[" + (",".join(value)) + "]", indentlevel, target=target
                        )
                    continue
                if isinstance(value, Command):
                    value.dump(indentlevel, target)
                    continue
                self.__print(str(value), indentlevel, target=target)
        for ch in self.children:
            ch.dump(indentlevel, target)

    def walk(self):
        """Walk through commands."""
        yield self
        if self.has_arguments():
            for arg in self.args_definition:
                if not arg["name"] in self.arguments:
                    continue
                value = self.arguments[arg["name"]]
                if type(value) == list:
                    if self.__get_arg_type(arg["name"]) == ["testlist"]:
                        for t in value:
                            for node in t.walk():
                                yield node
                if isinstance(value, Command):
                    for node in value.walk():
                        yield node
        for ch in self.children:
            for node in ch.walk():
                yield node

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

    def iscomplete(self, atype=None, avalue=None):
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
                if arg.get("required", False):
                    self.required_args += 1
        return (
            not self.curarg
            or "extra_arg" not in self.curarg
            or (
                "valid_for" in self.curarg["extra_arg"]
                and atype
                and atype in self.curarg["extra_arg"]["type"]
                and avalue not in self.curarg["extra_arg"]["valid_for"]
            )
        ) and (self.rargs_cnt == self.required_args)

    def get_type(self):
        """Return the command's type"""
        if self._type is None:
            raise NotImplementedError
        return self._type

    def __is_valid_value_for_arg(self, arg, value, check_extension=True):
        """Check if value is allowed for arg

        Some commands only allow a limited set of values. The method
        always returns True for methods that do not provide such a
        set.

        :param arg: the argument's name
        :param value: the value to check
        :param check_extension: check if value requires an extension
        :return: True on succes, False otherwise
        """
        if "values" not in arg and "extension_values" not in arg:
            return True
        if "values" in arg and value.lower() in arg["values"]:
            return True
        if "extension_values" in arg:
            extension = arg["extension_values"].get(value.lower())
            if extension:
                condition = (
                    check_extension
                    and extension not in RequireCommand.loaded_extensions
                )
                if condition:
                    raise ExtensionNotLoaded(extension)
                return True
        return False

    def __is_valid_type(self, typ, typlist):
        """Check if type is valid based on input type list
            "string" is special because it can be used for stringlist

        :param typ: the type to check
        :param typlist: the list of type to check
        :return: True on success, False otherwise
        """
        typ_is_str = typ == "string"
        str_list_in_typlist = "stringlist" in typlist

        return typ in typlist or (typ_is_str and str_list_in_typlist)

    def check_next_arg(self, atype, avalue, add=True, check_extension=True):
        """Argument validity checking

        This method is usually used by the parser to check if detected
        argument is allowed for this command.

        We make a distinction between required and optional
        arguments. Optional (or tagged) arguments can be provided
        unordered but not the required ones.

        A special handling is also done for arguments that require an
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
        :param check_extension: raise ExtensionNotLoaded if extension not
                                loaded
        :return: True on success, False otherwise
        """
        if not self.has_arguments():
            return False
        if self.iscomplete(atype, avalue):
            return False

        if self.curarg is not None and "extra_arg" in self.curarg:
            condition = atype in self.curarg["extra_arg"]["type"] and (
                "values" not in self.curarg["extra_arg"]
                or avalue in self.curarg["extra_arg"]["values"]
            )
            if condition:
                if add:
                    self.extra_arguments[self.curarg["name"]] = avalue
                self.curarg = None
                return True
            raise BadValue(self.curarg["name"], avalue)

        failed = False
        pos = self.nextargpos
        while pos < len(self.args_definition):
            curarg = self.args_definition[pos]
            if curarg.get("required", False):
                if curarg["type"] == ["testlist"]:
                    if atype != "test":
                        failed = True
                    elif add:
                        if not curarg["name"] in self.arguments:
                            self.arguments[curarg["name"]] = []
                        self.arguments[curarg["name"]] += [avalue]
                elif not self.__is_valid_type(
                    atype, curarg["type"]
                ) or not self.__is_valid_value_for_arg(curarg, avalue, check_extension):
                    failed = True
                else:
                    self.curarg = curarg
                    self.rargs_cnt += 1
                    self.nextargpos = pos + 1
                    if add:
                        self.arguments[curarg["name"]] = avalue
                break

            condition = atype in curarg["type"] and self.__is_valid_value_for_arg(
                curarg, avalue, check_extension
            )
            if condition:
                ext = curarg.get("extension")
                condition = (
                    check_extension
                    and ext
                    and ext not in RequireCommand.loaded_extensions
                )
                if condition:
                    raise ExtensionNotLoaded(ext)
                condition = "extra_arg" in curarg and (
                    "valid_for" not in curarg["extra_arg"]
                    or avalue in curarg["extra_arg"]["valid_for"]
                )
                if condition:
                    self.curarg = curarg
                if add:
                    self.arguments[curarg["name"]] = avalue
                break

            pos += 1

        if failed:
            raise BadArgument(self.name, avalue, self.args_definition[pos]["type"])
        return True

    def __contains__(self, name):
        """Check if argument is provided with command."""
        return name in self.arguments

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
        if name not in self.arguments:
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
        {"name": "capabilities", "type": ["string", "stringlist"], "required": True}
    ]

    loaded_extensions = []

    def complete_cb(self):
        if type(self.arguments["capabilities"]) != list:
            exts = [self.arguments["capabilities"]]
        else:
            exts = self.arguments["capabilities"]
        for ext in exts:
            ext = ext.strip('"')
            if ext not in RequireCommand.loaded_extensions:
                RequireCommand.loaded_extensions += [ext]


class IfCommand(ControlCommand):
    accept_children = True

    args_definition = [{"name": "test", "type": ["test"], "required": True}]

    def get_expected_first(self):
        return ["identifier"]


class ElsifCommand(ControlCommand):
    accept_children = True
    must_follow = ["if", "elsif"]
    args_definition = [{"name": "test", "type": ["test"], "required": True}]

    def get_expected_first(self):
        return ["identifier"]


class ElseCommand(ControlCommand):
    accept_children = True
    must_follow = ["if", "elsif"]
    args_definition = []


class ActionCommand(Command):
    """Indermediate class to represent "action" commands"""

    _type = "action"

    def args_as_tuple(self):
        args = []
        for name, value in list(self.arguments.items()):
            unquote = False
            for argdef in self.args_definition:
                if name == argdef["name"]:
                    condition = (
                        "string" in argdef["type"] or "stringlist" in argdef["type"]
                    )
                    if condition:
                        unquote = True
                        break
            if unquote:
                if "," in value:
                    args += tools.to_list(value)
                else:
                    args.append(value.strip('"'))
                continue
            args.append(value)
        return (self.name,) + tuple(args)


class StopCommand(ActionCommand):
    args_definition = []


class FileintoCommand(ActionCommand):
    extension = "fileinto"
    args_definition = [
        {
            "name": "copy",
            "type": ["tag"],
            "values": [":copy"],
            "required": False,
            "extension": "copy",
        },
        {
            "name": "create",
            "type": ["tag"],
            "values": [":create"],
            "required": False,
            "extension": "mailbox",
        },
        {
            "name": "flags",
            "type": ["tag"],
            "values": [":flags"],
            "extra_arg": {"type": ["string", "stringlist"]},
            "extension": "imap4flags",
        },
        {"name": "mailbox", "type": ["string"], "required": True},
    ]


class RedirectCommand(ActionCommand):
    args_definition = [
        {
            "name": "copy",
            "type": ["tag"],
            "values": [":copy"],
            "required": False,
            "extension": "copy",
        },
        {"name": "address", "type": ["string"], "required": True},
    ]


class RejectCommand(ActionCommand):
    extension = "reject"
    args_definition = [{"name": "text", "type": ["string"], "required": True}]


class KeepCommand(ActionCommand):
    args_definition = [
        {
            "name": "flags",
            "type": ["tag"],
            "values": [":flags"],
            "extra_arg": {"type": ["string", "stringlist"]},
            "extension": "imap4flags",
        },
    ]


class DiscardCommand(ActionCommand):
    args_definition = []


class SetflagCommand(ActionCommand):
    """imap4flags extension: setflag."""

    args_definition = [
        {"name": "variable-name", "type": ["string"], "required": False},
        {"name": "list-of-flags", "type": ["string", "stringlist"], "required": True},
    ]
    extension = "imap4flags"


class AddflagCommand(ActionCommand):
    """imap4flags extension: addflag."""

    args_definition = [
        {"name": "variable-name", "type": ["string"], "required": False},
        {"name": "list-of-flags", "type": ["string", "stringlist"], "required": True},
    ]
    extension = "imap4flags"


class RemoveflagCommand(ActionCommand):
    """imap4flags extension: removeflag."""

    args_definition = [
        {"name": "variable-name", "type": ["string"]},
        {"name": "list-of-flags", "type": ["string", "stringlist"], "required": True},
    ]
    extension = "imap4flags"


class TestCommand(Command):
    """Indermediate class to represent "test" commands"""

    _type = "test"


class AddressCommand(TestCommand):
    args_definition = [
        comparator,
        address_part,
        match_type,
        {"name": "header-list", "type": ["string", "stringlist"], "required": True},
        {"name": "key-list", "type": ["string", "stringlist"], "required": True},
    ]


class AllofCommand(TestCommand):
    accept_children = True
    variable_args_nb = True

    args_definition = [{"name": "tests", "type": ["testlist"], "required": True}]

    def get_expected_first(self):
        return ["left_parenthesis"]


class AnyofCommand(TestCommand):
    accept_children = True
    variable_args_nb = True

    args_definition = [{"name": "tests", "type": ["testlist"], "required": True}]

    def get_expected_first(self):
        return ["left_parenthesis"]


class EnvelopeCommand(TestCommand):
    args_definition = [
        comparator,
        address_part,
        match_type,
        {"name": "header-list", "type": ["string", "stringlist"], "required": True},
        {"name": "key-list", "type": ["string", "stringlist"], "required": True},
    ]
    extension = "envelope"

    def args_as_tuple(self):
        """Return arguments as a list."""
        result = ("envelope", self.arguments["match-type"])
        value = self.arguments["header-list"]
        if isinstance(value, list):
            # FIXME
            value = "[{}]".format(",".join('"{}"'.format(item) for item in value))
        if value.startswith("["):
            result += (tools.to_list(value),)
        else:
            result += ([value.strip('"')],)
        value = self.arguments["key-list"]
        if isinstance(value, list):
            # FIXME
            value = "[{}]".format(",".join('"{}"'.format(item) for item in value))
        if value.startswith("["):
            result += (tools.to_list(value),)
        else:
            result = result + ([value.strip('"')],)
        return result


class ExistsCommand(TestCommand):
    args_definition = [
        {"name": "header-names", "type": ["string", "stringlist"], "required": True}
    ]

    def args_as_tuple(self):
        """FIXME: en fonction de la manière dont la commande a été générée
        (factory ou parser), le type des arguments est différent :
        string quand ça vient de la factory ou type normal depuis le
        parser. Il faut uniformiser tout ça !!

        """
        value = self.arguments["header-names"]
        if isinstance(value, list):
            value = "[{}]".format(",".join('"{}"'.format(item) for item in value))
        if not value.startswith("["):
            return ("exists", value.strip('"'))
        return ("exists",) + tuple(tools.to_list(value))


class TrueCommand(TestCommand):
    args_definition = []


class FalseCommand(TestCommand):
    args_definition = []


class HeaderCommand(TestCommand):
    args_definition = [
        comparator,
        match_type,
        {"name": "header-names", "type": ["string", "stringlist"], "required": True},
        {"name": "key-list", "type": ["string", "stringlist"], "required": True},
    ]

    def args_as_tuple(self):
        """Return arguments as a list."""
        if "," in self.arguments["header-names"]:
            result = tuple(tools.to_list(self.arguments["header-names"]))
        else:
            result = (self.arguments["header-names"].strip('"'),)
        result = result + (self.arguments["match-type"],)
        if "," in self.arguments["key-list"]:
            result = result + tuple(
                tools.to_list(self.arguments["key-list"], unquote=False)
            )
        else:
            result = result + (self.arguments["key-list"].strip('"'),)
        return result


class BodyCommand(TestCommand):
    """Body extension.

    See https://tools.ietf.org/html/rfc5173.
    """

    args_definition = [
        comparator,
        match_type,
        {
            "name": "body-transform",
            "values": [":raw", ":content", ":text"],
            "extra_arg": {"type": "stringlist", "valid_for": [":content"]},
            "type": ["tag"],
            "required": False,
        },
        {"name": "key-list", "type": ["string", "stringlist"], "required": True},
    ]
    extension = "body"

    def args_as_tuple(self):
        """Return arguments as a list."""
        result = ("body",)
        result = result + (
            self.arguments["body-transform"],
            self.arguments["match-type"],
        )
        value = self.arguments["key-list"]
        if isinstance(value, list):
            # FIXME
            value = "[{}]".format(",".join('"{}"'.format(item) for item in value))
        if value.startswith("["):
            result += tuple(tools.to_list(value))
        else:
            result += (value.strip('"'),)
        return result


class NotCommand(TestCommand):
    accept_children = True

    args_definition = [{"name": "test", "type": ["test"], "required": True}]

    def get_expected_first(self):
        return ["identifier"]


class SizeCommand(TestCommand):
    args_definition = [
        {
            "name": "comparator",
            "type": ["tag"],
            "values": [":over", ":under"],
            "required": True,
        },
        {"name": "limit", "type": ["number"], "required": True},
    ]

    def args_as_tuple(self):
        return ("size", self.arguments["comparator"], self.arguments["limit"])


class HasflagCommand(TestCommand):
    """imap4flags extension: hasflag."""

    args_definition = [
        comparator,
        match_type,
        {"name": "variable-list", "type": ["string", "stringlist"], "required": False},
        {"name": "list-of-flags", "type": ["string", "stringlist"], "required": True},
    ]
    extension = "imap4flags"
    non_deterministic_args = True

    def reassign_arguments(self):
        """Deal with optional stringlist before a required one."""
        condition = (
            "variable-list" in self.arguments and "list-of-flags" not in self.arguments
        )
        if condition:
            self.arguments["list-of-flags"] = self.arguments.pop("variable-list")
            self.rargs_cnt = 1


class DateCommand(TestCommand):
    """date command, part of the date extension.

    https://tools.ietf.org/html/rfc5260#section-4
    """

    extension = "date"
    args_definition = [
        {
            "name": "zone",
            "type": ["tag"],
            "values": [":zone", ":originalzone"],
            "extra_arg": {"type": "string", "valid_for": [":zone"]},
            "required": False,
        },
        comparator,
        match_type,
        {"name": "header-name", "type": ["string"], "required": True},
        {"name": "date-part", "type": ["string"], "required": True},
        {"name": "key-list", "type": ["string", "stringlist"], "required": True},
    ]


class CurrentdateCommand(TestCommand):
    """currentdate command, part of the date extension.

    http://tools.ietf.org/html/rfc5260#section-5
    """

    extension = "date"
    args_definition = [
        {
            "name": "zone",
            "type": ["tag"],
            "values": [":zone"],
            "extra_arg": {"type": "string"},
            "required": False,
        },
        comparator,
        match_type,
        {"name": "date-part", "type": ["string"], "required": True},
        {"name": "key-list", "type": ["string", "stringlist"], "required": True},
    ]

    def args_as_tuple(self):
        """Return arguments as a list."""
        result = ("currentdate",)
        result += (
            ":zone",
            self.extra_arguments["zone"].strip('"'),
            self.arguments["match-type"],
        )
        if self.arguments["match-type"] in [":count", ":value"]:
            result += (self.extra_arguments["match-type"].strip('"'),)
        result += (self.arguments["date-part"].strip('"'),)
        value = self.arguments["key-list"]
        if isinstance(value, list):
            # FIXME
            value = "[{}]".format(",".join('"{}"'.format(item) for item in value))
        if value.startswith("["):
            result = result + tuple(tools.to_list(value))
        else:
            result = result + (value.strip('"'),)
        return result


class VacationCommand(ActionCommand):
    args_definition = [
        {
            "name": "subject",
            "type": ["tag"],
            "values": [":subject"],
            "extra_arg": {"type": "string"},
            "required": False,
        },
        {
            "name": "days",
            "type": ["tag"],
            "values": [":days"],
            "extra_arg": {"type": "number"},
            "required": False,
        },
        {
            "name": "seconds",
            "type": ["tag"],
            "extension_values": {":seconds": "vacation-seconds"},
            "extra_arg": {"type": "number"},
            "required": False,
        },
        {
            "name": "from",
            "type": ["tag"],
            "values": [":from"],
            "extra_arg": {"type": "string"},
            "required": False,
        },
        {
            "name": "addresses",
            "type": ["tag"],
            "values": [":addresses"],
            "extra_arg": {"type": ["string", "stringlist"]},
            "required": False,
        },
        {
            "name": "handle",
            "type": ["tag"],
            "values": [":handle"],
            "extra_arg": {"type": "string"},
            "required": False,
        },
        {"name": "mime", "type": ["tag"], "values": [":mime"], "required": False},
        {"name": "reason", "type": ["string"], "required": True},
    ]


class SetCommand(ControlCommand):
    """set command, part of the variables extension

    http://tools.ietf.org/html/rfc5229
    """

    extension = "variables"
    args_definition = [
        {"name": "startend", "type": ["string"], "required": True},
        {"name": "date", "type": ["string"], "required": True},
    ]


def add_commands(cmds):
    """
    Adds one or more commands to the module namespace.
    Commands must end in "Command" to be added.
    Example (see tests/parser.py):
    sievelib.commands.add_commands(MytestCommand)

    :param cmds: a single Command Object or list of Command Objects
    """
    if not isinstance(cmds, Iterable):
        cmds = [cmds]

    for command in cmds:
        if command.__name__.endswith("Command"):
            globals()[command.__name__] = command


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
    gl = globals()
    condition = cname not in gl or (
        checkexists
        and gl[cname].extension
        and gl[cname].extension not in RequireCommand.loaded_extensions
    )
    if condition:
        raise UnknownCommand(name)
    return gl[cname](parent)
