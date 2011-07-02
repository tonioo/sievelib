# coding: utf-8

"""
Tools for simpler sieve filters generation.

This module is intented to facilitate the creation of sieve filters
without having to write or to know the syntax.

Only commands (control/test/action) defined in the ``commands`` module
are supported.
"""
import sys
import cStringIO
from commands import *

class FiltersSet(object):
    def __init__(self, name):
        self.name = name
        self.requires = []
        self.filters = []

    def __str__(self):
        target = cStringIO.StringIO()
        self.tosieve(target)
        ret = target.getvalue()
        target.close()
        return ret

    def __isdisabled(self, fcontent):
        """Tells if a filter is disabled or not
        
        Simply checks if the filter is surrounded by a "if false" test.

        :param name: the filter's name
        """
        if not isinstance(fcontent, IfCommand):
            return False
        if not isinstance(fcontent["test"], FalseCommand):
            return False
        return True

    def from_parser_result(self, parser):
        cpt = 1
        for f in parser.result:
            if isinstance(f, RequireCommand):
                if type(f.arguments["capabilities"]) == list:
                    map(self.require, f.arguments["capabilities"])
                else:
                    self.require(f.arguments["capabilities"])
                continue
            if cpt - 1 >= len(parser.hash_comments):
                name =  "Unnamed rule %d" % cpt
            else:
                name = parser.hash_comments[cpt - 1].replace("# Filter: ", "")
            self.filters += [{"name" : name,
                              "content" : f,
                              "enabled" : not self.__isdisabled(f)}]
            cpt += 1

    def require(self, name):
        """Add a new extension to the requirements list

        :param name: the extension's name
        """
        name = name.strip('"')
        if not name in self.requires:
            self.requires += [name]

    def __gen_require_command(self):
        """Internal method to create a RequireCommand based on requirements

        Called just before this object is going to be dumped.
        """
        reqcmd = get_command_instance("require")
        reqcmd.check_next_arg("stringlist", self.requires)
        return reqcmd

    def __create_filter(self, conditions, actions, matchtype="anyof"):
        """Create a new filter

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
        ifcontrol = get_command_instance("if")
        mtypeobj = get_command_instance(matchtype, ifcontrol)
        for c in conditions:
            if c[0] in ("true", "false"):
                cmd = get_command_instance(c[0], ifcontrol)
            elif c[0] == "size":
                cmd = get_command_instance("size", ifcontrol)
                cmd.check_next_arg("tag", c[1])
                cmd.check_next_arg("number", c[2])
            else:
                cmd = get_command_instance("header", ifcontrol)
                cmd.check_next_arg("tag", c[1])
                cmd.check_next_arg("string", c[0])
                cmd.check_next_arg("string", c[2])
            mtypeobj.check_next_arg("test", cmd)
        ifcontrol.check_next_arg("test", mtypeobj)

        for actdef in actions:
            self.require(actdef[0])
            action = get_command_instance(actdef[0], ifcontrol, False)
            for arg in actdef[1:]:
                action.check_next_arg("string", arg)
            ifcontrol.addchild(action)
        return ifcontrol

    def addfilter(self, name, conditions, actions, matchtype="anyof"):
        """Add a new filter to this filters set

        :param name: the filter's name
        :param conditions: the list of conditions
        :param actions: the list of actions
        :param matchtype: "anyof" or "allof"
        """
        ifcontrol = self.__create_filter(conditions, actions, matchtype)
        self.filters += [{"name" : name, "content" : ifcontrol, "enabled" : True}]

    def updatefilter(self, oldname, newname, conditions, actions, matchtype="anyof"):
        """Update a specific filter

        Instead of removing and re-creating the filter, we update the
        content in order to keep the original ordre between filters.

        :param name: the filter's name
        :param conditions: the list of conditions
        :param actions: the list of actions
        :param matchtype: "anyof" or "allof"
        """
        for f in self.filters:
            if f["name"] == oldname:
                f["name"] = newname
                f["content"] = \
                    self.__create_filter(conditions, actions, matchtype)
                if not f["enabled"]:
                    return self.disablefilter(newname)
                return True
        return False

    def getfilter(self, name):
        """Search for a specific filter

        :param name: the filter's name
        :return: the Command object if found, None otherwise
        """
        for f in self.filters:
            if f["name"] == name:
                if not f["enabled"]:
                    return f["content"].children[0]
                return f["content"]
        return None

    def removefilter(self, name):
        """Remove a specific filter

        :param name: the filter's name
        """
        for f in self.filters:
            if f["name"] == name:
                self.filters.remove(f)
                return True
        return False

    def enablefilter(self, name):
        """Enable a filter

        Just removes the "if false" test surrouding this filter.

        :param name: the filter's name
        """
        for f in self.filters:
            if f["name"] != name:
                continue
            if not self.__isdisabled(f["content"]):
                return False
            f["content"] = f["content"].children[0]
            f["enabled"] = True
            return True
        return False # raise NotFound

    def is_filter_disabled(self, name):
        """Tells if the filter is currently disabled or not

        :param name: the filter's name
        """
        for f in self.filters:
            if f["name"] == name:
                return self.__isdisabled(f["content"])
        return True

    def disablefilter(self, name):
        """Disable a filter

        Instead of commenting the filter, we just surround it with a
        "if false { }" test.

        :param name: the filter's name
        """
        ifcontrol = get_command_instance("if")
        falsecmd = get_command_instance("false", ifcontrol)
        ifcontrol.check_next_arg("test", falsecmd)
        for f in self.filters:
            if f["name"] != name:
                continue
            ifcontrol.addchild(f["content"])
            f["content"] = ifcontrol
            f["enabled"] = False
            return True
        return False

    def movefilter(self, name, direction):
        """Moves the filter up or down

        :param name: the filter's name
        :param direction: string "up" or "down"
        """
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
        return False # raise not found

    def dump(self):
        """Dump this object

        Available for debugging purposes
        """
        print "Dumping filters set %s\n" % self.name
        
        print "Dumping requirements"
        self.__gen_require_command().dump()
        print 

        for f in self.filters:
            print "Filter %s" % f["name"]
            f["content"].dump()

    def tosieve(self, target=sys.stdout):
        """Generate the sieve syntax corresponding to this filters set

        This method will usually be called when this filters set is
        done. The default is to print the sieve syntax on the standard
        output. You can pass an opened file pointer object if you want
        to write the content elsewhere.

        :param target: file pointer where the sieve syntax will be printed
        """
        self.__gen_require_command().tosieve(target=target)
        target.write("\n")
        for f in self.filters:
            print >>target, "# Filter: %s" % f["name"]
            f["content"].tosieve(target=target)
        
    
if __name__ == "__main__":
    fs = FiltersSet("test")
    
    fs.addfilter("rule1", 
                 [("Sender", ":is", "toto@toto.com"),],
                 [("fileinto", "Toto"),])
    fs.tosieve()
    
