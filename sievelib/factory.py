"""
Tools for simpler sieve filters generation.

This module is intented to facilitate the creation of sieve filters
without having to write or to know the syntax.

Only commands (control/test/action) defined in the ``commands`` module
are supported.
"""

import io
import sys
from typing import List, Optional, TypedDict, Union
from typing_extensions import NotRequired

from sievelib import commands
from sievelib.parser import Parser


class FilterAlreadyExists(Exception):
    pass


class Filter(TypedDict):
    """Type definition for filter."""

    name: str
    content: commands.Command
    enabled: bool
    description: NotRequired[str]


class FiltersSet:
    """A set of filters."""

    def __init__(
        self,
        name: str,
        filter_name_pretext: str = "# Filter: ",
        filter_desc_pretext: str = "# Description: ",
    ):
        """
        Represents a set of one or more filters.

        :param name: the filterset's name
        :param filter_name_pretext: the text that is used to mark a filter name
                                    (as comment preceding the filter)
        :param filter_desc_pretext: the text that is used to mark a filter
                                     description
        """
        self.name = name
        self.filter_name_pretext = filter_name_pretext
        self.filter_desc_pretext = filter_desc_pretext
        self.requires: List[str] = []
        self.filters: List[Filter] = []

    def __str__(self):
        target = io.StringIO()
        self.tosieve(target)
        ret = target.getvalue()
        target.close()
        return ret

    def __isdisabled(self, fcontent: commands.Command) -> bool:
        """Tells if a filter is disabled or not

        Simply checks if the filter is surrounded by a "if false" test.

        :param fcontent: the filter's name
        """
        if not isinstance(fcontent, commands.IfCommand):
            return False
        if not isinstance(fcontent["test"], commands.FalseCommand):
            return False
        return True

    def from_parser_result(self, parser: Parser) -> None:
        cpt = 1
        for f in parser.result:
            if isinstance(f, commands.RequireCommand):
                if type(f.arguments["capabilities"]) == list:
                    [self.require(c) for c in f.arguments["capabilities"]]
                else:
                    self.require(f.arguments["capabilities"])
                continue

            name = "Unnamed rule %d" % cpt
            description = ""
            for comment in f.hash_comments:
                if isinstance(comment, bytes):
                    comment = comment.decode("utf-8")
                if comment.startswith(self.filter_name_pretext):
                    name = comment.replace(self.filter_name_pretext, "")
                if comment.startswith(self.filter_desc_pretext):
                    description = comment.replace(self.filter_desc_pretext, "")
            self.filters += [
                {
                    "name": name,
                    "description": description,
                    "content": f,
                    "enabled": not self.__isdisabled(f),
                }
            ]
            cpt += 1

    def require(self, name: str):
        """Add a new extension to the requirements list

        :param name: the extension's name
        """
        name = name.strip('"')
        if name not in self.requires:
            self.requires += [name]

    def check_if_arg_is_extension(self, arg: str):
        """Include extension if arg requires one."""
        args_using_extensions = {":copy": "copy", ":create": "mailbox"}
        if arg in args_using_extensions:
            self.require(args_using_extensions[arg])

    def __gen_require_command(self) -> Union[commands.Command, None]:
        """Internal method to create a RequireCommand based on requirements

        Called just before this object is going to be dumped.
        """
        if not len(self.requires):
            return None
        reqcmd = commands.get_command_instance("require")
        reqcmd.check_next_arg("stringlist", self.requires)
        return reqcmd

    def __quote_if_necessary(self, value: str) -> str:
        """Add double quotes to the given string if necessary

        :param value: the string to check
        :return: the string between quotes
        """
        if not value.startswith(('"', "'")):
            return '"%s"' % value
        return value

    def __build_condition(
        self, condition: List[str], parent: commands.Command, tag: Optional[str] = None
    ) -> commands.Command:
        """Translate a condition to a valid sievelib Command.

        :param list condition: condition's definition
        :param ``Command`` parent: the parent
        :param str tag: tag to use instead of the one included into :keyword:`condition`
        :rtype: Command
        :return: the generated command
        """
        if tag is None:
            tag = condition[1]
        cmd = commands.get_command_instance("header", parent)
        cmd.check_next_arg("tag", tag)
        if isinstance(condition[0], list):
            cmd.check_next_arg(
                "stringlist", [self.__quote_if_necessary(c) for c in condition[0]]
            )
        else:
            cmd.check_next_arg("string", self.__quote_if_necessary(condition[0]))
        if isinstance(condition[2], list):
            cmd.check_next_arg(
                "stringlist", [self.__quote_if_necessary(c) for c in condition[2]]
            )
        else:
            cmd.check_next_arg("string", self.__quote_if_necessary(condition[2]))
        return cmd

    def __create_filter(
        self,
        conditions: List[tuple],
        actions: List[tuple],
        matchtype: str = "anyof",
    ) -> commands.Command:
        """
        Create a new filter.

        A filter is composed of:
         * a name
         * one or more conditions (tests) combined together using ``matchtype``
         * one or more actions

        A condition must be given as a 3-uple of the form::

          (test's name, operator, value)

        An action must be given as a 2-uple of the form::

          (action's name, value)

        It uses the "header" test to generate the sieve syntax
        corresponding to the given conditions.

        :param conditions: the list of conditions
        :param actions: the list of actions
        :param matchtype: "anyof" or "allof"
        """
        ifcontrol = commands.get_command_instance("if")
        mtypeobj = commands.get_command_instance(matchtype, ifcontrol)
        for c in conditions:
            if not isinstance(c[0], list) and c[0].startswith("not"):
                negate = True
                cname = c[0].replace("not", "", 1)
            else:
                negate = False
                cname = c[0]
            if cname in ("true", "false"):
                cmd = commands.get_command_instance(c[0], ifcontrol)
            elif cname == "size":
                cmd = commands.get_command_instance("size", ifcontrol)
                cmd.check_next_arg("tag", c[1])
                cmd.check_next_arg("number", c[2])
            elif cname == "exists":
                cmd = commands.get_command_instance("exists", ifcontrol)
                cmd.check_next_arg(
                    "stringlist", "[%s]" % (",".join('"%s"' % val for val in c[1:]))
                )
            elif cname == "envelope":
                cmd = commands.get_command_instance("envelope", ifcontrol, False)
                self.require("envelope")
                if c[1].startswith(":not"):
                    comp_tag = c[1].replace("not", "")
                    negate = True
                else:
                    comp_tag = c[1]
                cmd.check_next_arg("tag", comp_tag)
                cmd.check_next_arg(
                    "stringlist",
                    "[{}]".format(",".join('"{}"'.format(val) for val in c[2])),
                )
                cmd.check_next_arg(
                    "stringlist",
                    "[{}]".format(",".join('"{}"'.format(val) for val in c[3])),
                )
            elif cname == "address":
                cmd = commands.get_command_instance("address", ifcontrol, False)
                if c[1].startswith(":not"):
                    comp_tag = c[1].replace("not", "")
                    negate = True
                else:
                    comp_tag = c[1]
                cmd.check_next_arg("tag", comp_tag)
                for arg in c[2:]:
                    if isinstance(arg, str):
                        finalarg = self.__quote_if_necessary(arg)
                    else:
                        finalarg = "[{}]".format(
                            ",".join('"{}"'.format(val) for val in arg)
                        )
                    cmd.check_next_arg("stringlist", finalarg)

            elif cname == "body":
                cmd = commands.get_command_instance("body", ifcontrol, False)
                self.require(cmd.extension)
                cmd.check_next_arg("tag", c[1])
                if c[2].startswith(":not"):
                    comp_tag = c[2].replace("not", "")
                    negate = True
                else:
                    comp_tag = c[2]
                cmd.check_next_arg("tag", comp_tag)
                cmd.check_next_arg(
                    "stringlist", "[%s]" % (",".join('"%s"' % val for val in c[3:]))
                )
            elif cname == "currentdate":
                cmd = commands.get_command_instance("currentdate", ifcontrol, False)
                self.require(cmd.extension)
                cmd.check_next_arg("tag", c[1])
                cmd.check_next_arg("string", self.__quote_if_necessary(c[2]))
                if c[3].startswith(":not"):
                    comp_tag = c[3].replace("not", "")
                    negate = True
                else:
                    comp_tag = c[3]
                cmd.check_next_arg("tag", comp_tag, check_extension=False)
                next_arg_pos = 4
                if comp_tag == ":value":
                    self.require("relational")
                    cmd.check_next_arg(
                        "string", self.__quote_if_necessary(c[next_arg_pos])
                    )
                    next_arg_pos += 1
                cmd.check_next_arg("string", self.__quote_if_necessary(c[next_arg_pos]))
                next_arg_pos += 1
                cmd.check_next_arg(
                    "stringlist",
                    "[%s]" % (",".join('"%s"' % val for val in c[next_arg_pos:])),
                )
            else:
                # header command fallback
                if c[1].startswith(":not"):
                    cmd = self.__build_condition(
                        c, ifcontrol, c[1].replace("not", "", 1)
                    )
                    negate = True
                else:
                    cmd = self.__build_condition(c, ifcontrol)
            if negate:
                not_cmd = commands.get_command_instance("not", ifcontrol)
                not_cmd.check_next_arg("test", cmd)
                cmd = not_cmd
            mtypeobj.check_next_arg("test", cmd)
        ifcontrol.check_next_arg("test", mtypeobj)

        for actdef in actions:
            action = commands.get_command_instance(actdef[0], ifcontrol, False)
            if action.extension is not None:
                self.require(action.extension)
            for arg in actdef[1:]:
                self.check_if_arg_is_extension(arg)
                if isinstance(arg, int):
                    atype = "number"
                elif isinstance(arg, list):
                    atype = "stringlist"
                elif arg.startswith(":"):
                    atype = "tag"
                else:
                    atype = "string"
                    arg = self.__quote_if_necessary(arg)
                action.check_next_arg(atype, arg, check_extension=False)
            ifcontrol.addchild(action)
        return ifcontrol

    def _unicode_filter_name(self, name) -> str:
        """Convert name to unicode if necessary."""
        return name.decode("utf-8") if isinstance(name, bytes) else name

    def filter_exists(self, name: str) -> bool:
        """Check if a filter with name already exists."""
        for existing_filter in self.filters:
            if existing_filter["name"] == name:
                return True
        return False

    def addfilter(
        self,
        name: str,
        conditions: List[tuple],
        actions: List[tuple],
        matchtype: str = "anyof",
    ) -> None:
        """Add a new filter to this filters set

        :param name: the filter's name
        :param conditions: the list of conditions
        :param actions: the list of actions
        :param matchtype: "anyof" or "allof"
        """
        name = self._unicode_filter_name(name)
        if self.filter_exists(name):
            raise FilterAlreadyExists
        ifcontrol = self.__create_filter(conditions, actions, matchtype)
        self.filters += [
            {
                "name": name,
                "content": ifcontrol,
                "enabled": True,
            }
        ]

    def updatefilter(
        self,
        oldname: str,
        newname: str,
        conditions: List[tuple],
        actions: List[tuple],
        matchtype: str = "anyof",
    ) -> bool:
        """Update a specific filter

        Instead of removing and re-creating the filter, we update the
        content in order to keep the original order between filters.

        :param oldname: the filter's current name
        :param newname: the filter's new name
        :param conditions: the list of conditions
        :param actions: the list of actions
        :param matchtype: "anyof" or "allof"
        """
        filter_def = None
        oldname = self._unicode_filter_name(oldname)
        for f in self.filters:
            if f["name"] == oldname:
                filter_def = f
                break
        if not filter_def:
            return False
        newname = self._unicode_filter_name(newname)
        if newname != oldname and self.filter_exists(newname):
            raise FilterAlreadyExists
        filter_def["name"] = newname
        filter_def["content"] = self.__create_filter(conditions, actions, matchtype)
        if not filter_def["enabled"]:
            return self.disablefilter(newname)
        return True

    def replacefilter(
        self,
        oldname: str,
        sieve_filter: commands.Command,
        newname: Optional[str] = None,
        description: Optional[str] = None,
    ) -> bool:
        """replace a specific sieve_filter

        Instead of removing and re-creating the sieve_filter, we update the
        content in order to keep the original order between filters.

        :param oldname: the sieve_filter's current name
        :param newname: the sieve_filter's new name
        :param sieve_filter: the sieve_filter object as get from
                             FiltersSet.getfilter()
        """
        filter_def = None
        oldname = self._unicode_filter_name(oldname)
        for f in self.filters:
            if f["name"] == oldname:
                filter_def = f
                break
        if not filter_def:
            return False
        if newname is None:
            newname = oldname
        newname = self._unicode_filter_name(newname)
        if newname != oldname and self.filter_exists(newname):
            raise FilterAlreadyExists
        filter_def["name"] = newname
        filter_def["content"] = sieve_filter
        if description is not None:
            filter_def["description"] = description
        if not filter_def["enabled"]:
            return self.disablefilter(newname)
        return True

    def getfilter(self, name: str) -> Union[commands.Command, None]:
        """Search for a specific filter

        :param name: the filter's name
        :return: the Command object if found, None otherwise
        """
        name = self._unicode_filter_name(name)
        for f in self.filters:
            if f["name"] == name:
                if not f["enabled"]:
                    return f["content"].children[0]
                return f["content"]
        return None

    def get_filter_matchtype(self, name: str) -> Union[str, None]:
        """Retrieve matchtype of the given filter."""
        flt = self.getfilter(name)
        if not flt:
            return None
        for node in flt.walk():
            if isinstance(node, (commands.AllofCommand, commands.AnyofCommand)):
                return node.__class__.__name__.lower().replace("command", "")
        return None

    def get_filter_conditions(self, name: str) -> Union[List[str], None]:
        """Retrieve conditions of the given filter."""
        flt = self.getfilter(name)
        if not flt:
            return None
        conditions = []
        negate = False
        for node in flt.walk():
            if isinstance(node, commands.NotCommand):
                negate = True
            elif isinstance(
                node,
                (
                    commands.HeaderCommand,
                    commands.SizeCommand,
                    commands.ExistsCommand,
                    commands.BodyCommand,
                    commands.EnvelopeCommand,
                    commands.CurrentdateCommand,
                ),
            ):
                args = node.args_as_tuple()
                if negate:
                    if node.name in ["header", "envelope"]:
                        nargs = (args[0], ":not{}".format(args[1][1:]))
                        if len(args) > 3:
                            nargs += args[2:]
                        else:
                            nargs += (args[2],)
                        args = nargs
                    elif node.name == "body":
                        args = args[:2] + (":not{}".format(args[2][1:]),) + args[3:]
                    elif node.name == "currentdate":
                        args = args[:3] + (":not{}".format(args[3][1:]),) + args[4:]
                    elif node.name == "exists":
                        args = ("not{}".format(args[0]),) + args[1:]
                    negate = False
                conditions.append(args)
        return conditions

    def get_filter_actions(self, name: str) -> Union[List[str], None]:
        """Retrieve actions of the given filter."""
        flt = self.getfilter(name)
        if not flt:
            return None
        actions: list = []
        for node in flt.walk():
            if isinstance(node, commands.ActionCommand):
                actions.append(node.args_as_tuple())
        return actions

    def removefilter(self, name: str) -> bool:
        """Remove a specific filter

        :param name: the filter's name
        """
        name = self._unicode_filter_name(name)
        for f in self.filters:
            if f["name"] == name:
                self.filters.remove(f)
                return True
        return False

    def enablefilter(self, name: str) -> bool:
        """Enable a filter

        Just removes the "if false" test surrouding this filter.

        :param name: the filter's name
        """
        name = self._unicode_filter_name(name)
        for f in self.filters:
            if f["name"] != name:
                continue
            if not self.__isdisabled(f["content"]):
                return False
            f["content"] = f["content"].children[0]
            f["enabled"] = True
            return True
        return False  # raise NotFound

    def is_filter_disabled(self, name: str) -> bool:
        """Tells if the filter is currently disabled or not

        :param name: the filter's name
        """
        name = self._unicode_filter_name(name)
        for f in self.filters:
            if f["name"] == name:
                return self.__isdisabled(f["content"])
        return True

    def disablefilter(self, name: str) -> bool:
        """Disable a filter

        Instead of commenting the filter, we just surround it with a
        "if false { }" test.

        :param name: the filter's name
        :return: True if filter was disabled, False otherwise
        """
        name = self._unicode_filter_name(name)
        ifcontrol = commands.get_command_instance("if")
        falsecmd = commands.get_command_instance("false", ifcontrol)
        ifcontrol.check_next_arg("test", falsecmd)
        for f in self.filters:
            if f["name"] != name:
                continue
            ifcontrol.addchild(f["content"])
            f["content"] = ifcontrol
            f["enabled"] = False
            return True
        return False

    def movefilter(self, name: str, direction: str) -> bool:
        """Moves the filter up or down

        :param name: the filter's name
        :param direction: string "up" or "down"
        """
        name = self._unicode_filter_name(name)
        cpt = 0
        for f in self.filters:
            if f["name"] == name:
                if direction == "up":
                    if cpt == 0:
                        return False
                    self.filters.remove(f)
                    self.filters.insert(cpt - 1, f)
                    return True
                if cpt == len(self.filters) - 1:
                    return False
                self.filters.remove(f)
                self.filters.insert(cpt + 1, f)
                return True
            cpt += 1
        return False  # raise not found

    def dump(self, target=sys.stdout):
        """Dump this object

        Available for debugging purposes
        """
        print("Dumping filters set %s\n" % self.name)
        cmd = self.__gen_require_command()
        if cmd:
            print("Dumping requirements")
            cmd.dump(target=target)
            target.write("\n")

        for f in self.filters:
            target.write("Filter Name: %s\n" % f["name"])
            if "description" in f:
                target.write("Filter Description: %s\n" % f["description"])
            f["content"].dump(target=target)

    def tosieve(self, target=sys.stdout):
        """Generate the sieve syntax corresponding to this filters set

        This method will usually be called when this filters set is
        done. The default is to print the sieve syntax on the standard
        output. You can pass an opened file pointer object if you want
        to write the content elsewhere.

        :param target: file pointer where the sieve syntax will be printed
        """
        cmd = self.__gen_require_command()
        if cmd:
            cmd.tosieve(target=target)
            target.write("\n")
        for f in self.filters:
            target.write("{}{}\n".format(self.filter_name_pretext, f["name"]))
            if "description" in f and f["description"]:
                target.write(
                    "{}{}\n".format(self.filter_desc_pretext, f["description"])
                )
            f["content"].tosieve(target=target)


if __name__ == "__main__":
    fs = FiltersSet("test")

    fs.addfilter(
        "rule1",
        [
            ("Sender", ":is", "toto@toto.com"),
        ],
        [
            ("fileinto", "Toto"),
        ],
    )
    fs.tosieve()
