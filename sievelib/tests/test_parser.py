# coding: utf-8

"""
Unit tests for the SIEVE language parser.
"""
import unittest
import os.path
import codecs
import six

from sievelib.parser import Parser
from sievelib.factory import FiltersSet
import sievelib.commands


class MytestCommand(sievelib.commands.ActionCommand):
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


class Quota_notificationCommand(sievelib.commands.ActionCommand):
    args_definition = [
        {"name": "subject",
         "type": ["tag"],
         "write_tag": True,
         "values": [":subject"],
         "extra_arg": {"type": "string"},
         "required": False},
        {"name": "recipient",
         "type": ["tag"],
         "write_tag": True,
         "values": [":recipient"],
         "extra_arg": {"type": "stringlist"},
         "required": True}
    ]


class SieveTest(unittest.TestCase):
    def setUp(self):
        self.parser = Parser()

    def __checkCompilation(self, script, result):
        self.assertEqual(self.parser.parse(script), result)

    def compilation_ok(self, script):
        self.__checkCompilation(script, True)

    def compilation_ko(self, script):
        self.__checkCompilation(script, False)

    def representation_is(self, content):
        target = six.StringIO()
        self.parser.dump(target)
        repr_ = target.getvalue()
        target.close()
        self.assertEqual(repr_, content.lstrip())

    def sieve_is(self, content):
        filtersset = FiltersSet("Testfilterset")
        filtersset.from_parser_result(self.parser)
        target = six.StringIO()
        filtersset.tosieve(target)
        repr_ = target.getvalue()
        target.close()
        self.assertEqual(repr_, content)


class AdditionalCommands(SieveTest):
    def test_add_command(self):
        self.assertRaises(
            sievelib.commands.UnknownCommand,
            sievelib.commands.get_command_instance, 'mytest'
        )
        sievelib.commands.add_commands(MytestCommand)
        sievelib.commands.get_command_instance('mytest')
        self.compilation_ok(b"""
        mytest :testtag 10 ["testrecp1@example.com"];
        """)

    def test_quota_notification(self):
        sievelib.commands.add_commands(Quota_notificationCommand)
        quota_notification_sieve = """# Filter: Testrule\nquota_notification :subject "subject here" :recipient ["somerecipient@example.com"];\n"""
        self.compilation_ok(quota_notification_sieve)
        self.sieve_is(quota_notification_sieve)


class ValidEncodings(SieveTest):
    def test_utf8_file(self):
        utf8_sieve = os.path.join(
            os.path.dirname(__file__), 'files', 'utf8_sieve.txt'
        )
        with codecs.open(utf8_sieve, encoding='utf8') as fobj:
            source_sieve = fobj.read()
        self.parser.parse_file(utf8_sieve)
        self.sieve_is(source_sieve)


class ValidSyntaxes(SieveTest):
    def test_hash_comment(self):
        self.compilation_ok(b"""
if size :over 100k { # this is a comment
    discard;
}
""")
        self.representation_is("""
if (type: control)
    size (type: test)
        :over
        100k
    discard (type: action)
""")

    def test_bracket_comment(self):
        self.compilation_ok(b"""
if size :over 100K { /* this is a comment
    this is still a comment */ discard /* this is a comment
    */ ;
}
""")
        self.representation_is("""
if (type: control)
    size (type: test)
        :over
        100K
    discard (type: action)
""")

    def test_string_with_bracket_comment(self):
        self.compilation_ok(b"""
if header :contains "Cc" "/* comment */" {
    discard;
}
""")
        self.representation_is("""
if (type: control)
    header (type: test)
        :contains
        "Cc"
        "/* comment */"
    discard (type: action)
""")

    def test_multiline_string(self):
        self.compilation_ok(b"""
require "reject";

if allof (false, address :is ["From", "Sender"] ["blka@bla.com"]) {
    reject text:
noreply
============================
Your email has been canceled
============================
.
;
    stop;
} else {
    reject text:
================================
Your email has been canceled too
================================
.
;
}
""")
        self.representation_is("""
require (type: control)
    "reject"
if (type: control)
    allof (type: test)
        false (type: test)
        address (type: test)
            :is
            ["From","Sender"]
            ["blka@bla.com"]
    reject (type: action)
        text:
noreply
============================
Your email has been canceled
============================
.
    stop (type: control)
else (type: control)
    reject (type: action)
        text:
================================
Your email has been canceled too
================================
.
""")

    def test_nested_blocks(self):
        self.compilation_ok(b"""
if header :contains "Sender" "example.com" {
  if header :contains "Sender" "me@" {
    discard;
  } elsif header :contains "Sender" "you@" {
    keep;
  }
}
""")
        self.representation_is("""
if (type: control)
    header (type: test)
        :contains
        "Sender"
        "example.com"
    if (type: control)
        header (type: test)
            :contains
            "Sender"
            "me@"
        discard (type: action)
    elsif (type: control)
        header (type: test)
            :contains
            "Sender"
            "you@"
        keep (type: action)
""")

    def test_true_test(self):
        self.compilation_ok(b"""
if true {

}
""")
        self.representation_is("""
if (type: control)
    true (type: test)
""")

    def test_rfc5228_extended(self):
        self.compilation_ok(b"""
#
# Example Sieve Filter
# Declare any optional features or extension used by the script
#
require ["fileinto"];

#
# Handle messages from known mailing lists
# Move messages from IETF filter discussion list to filter mailbox
#
if header :is "Sender" "owner-ietf-mta-filters@imc.org"
        {
        fileinto "filter";  # move to "filter" mailbox
        }
#
# Keep all messages to or from people in my company
#
elsif address :DOMAIN :is ["From", "To"] "example.com"
        {
        keep;               # keep in "In" mailbox
        }

#
# Try and catch unsolicited email.  If a message is not to me,
# or it contains a subject known to be spam, file it away.
#
elsif anyof (NOT address :all :contains
               ["To", "Cc", "Bcc"] "me@example.com",
             header :matches "subject"
               ["*make*money*fast*", "*university*dipl*mas*"])
        {
        fileinto "spam";   # move to "spam" mailbox
        }
else
        {
        # Move all other (non-company) mail to "personal"
        # mailbox.
        fileinto "personal";
        }
""")
        self.representation_is("""
require (type: control)
    ["fileinto"]
if (type: control)
    header (type: test)
        :is
        "Sender"
        "owner-ietf-mta-filters@imc.org"
    fileinto (type: action)
        "filter"
elsif (type: control)
    address (type: test)
        :DOMAIN
        :is
        ["From","To"]
        "example.com"
    keep (type: action)
elsif (type: control)
    anyof (type: test)
        not (type: test)
            address (type: test)
                :all
                :contains
                ["To","Cc","Bcc"]
                "me@example.com"
        header (type: test)
            :matches
            "subject"
            ["*make*money*fast*","*university*dipl*mas*"]
    fileinto (type: action)
        "spam"
else (type: control)
    fileinto (type: action)
        "personal"
""")

    def test_explicit_comparator(self):
        self.compilation_ok(b"""
if header :contains :comparator "i;octet" "Subject" "MAKE MONEY FAST" {
  discard;
}
""")
        self.representation_is("""
if (type: control)
    header (type: test)
        "i;octet"
        :contains
        "Subject"
        "MAKE MONEY FAST"
    discard (type: action)
""")

    def test_non_ordered_args(self):
        self.compilation_ok(b"""
if address :all :is "from" "tim@example.com" {
    discard;
}
""")
        self.representation_is("""
if (type: control)
    address (type: test)
        :all
        :is
        "from"
        "tim@example.com"
    discard (type: action)
""")

    def test_multiple_not(self):
        self.compilation_ok(b"""
if not not not not true {
    stop;
}
""")
        self.representation_is("""
if (type: control)
    not (type: test)
        not (type: test)
            not (type: test)
                not (type: test)
                    true (type: test)
    stop (type: control)
""")

    def test_just_one_command(self):
        self.compilation_ok(b"keep;")
        self.representation_is("""
keep (type: action)
""")

    def test_singletest_testlist(self):
        self.compilation_ok(b"""
if anyof (true) {
    discard;
}
""")
        self.representation_is("""
if (type: control)
    anyof (type: test)
        true (type: test)
    discard (type: action)
""")

    def test_truefalse_testlist(self):
        self.compilation_ok(b"""
if anyof(true, false) {
    discard;
}
""")
        self.representation_is("""
if (type: control)
    anyof (type: test)
        true (type: test)
        false (type: test)
    discard (type: action)
""")

    def test_vacationext_basic(self):
        self.compilation_ok(b"""
require "vacation";
if header :contains "subject" "cyrus" {
    vacation "I'm out -- send mail to cyrus-bugs";
} else {
    vacation "I'm out -- call me at +1 304 555 0123";
}
""")

    def test_vacationext_medium(self):
        self.compilation_ok(b"""
require "vacation";
if header :contains "subject" "lunch" {
    vacation :handle "ran-away" "I'm out and can't meet for lunch";
} else {
    vacation :handle "ran-away" "I'm out";
}
""")

    def test_vacationext_with_limit(self):
        self.compilation_ok(b"""
require "vacation";
vacation :days 23 :addresses ["tjs@example.edu",
                              "ts4z@landru.example.edu"]
   "I'm away until October 19.
   If it's an emergency, call 911, I guess." ;
""")

    def test_vacationext_with_single_mail_address(self):
        self.compilation_ok("""
require "vacation";
vacation :days 23 :addresses "tjs@example.edu"
   "I'm away until October 19.
   If it's an emergency, call 911, I guess." ;
""")

    def test_vacationext_with_multiline(self):
        self.compilation_ok(b"""
require "vacation";
vacation :mime text:
Content-Type: multipart/alternative; boundary=foo

--foo

I'm at the beach relaxing.  Mmmm, surf...

--foo
Content-Type: text/html; charset=us-ascii

<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.0//EN"
 "http://www.w3.org/TR/REC-html40/strict.dtd">
<HTML><HEAD><TITLE>How to relax</TITLE>
<BASE HREF="http://home.example.com/pictures/"></HEAD>
<BODY><P>I'm at the <A HREF="beach.gif">beach</A> relaxing.
Mmmm, <A HREF="ocean.gif">surf</A>...
</BODY></HTML>

--foo--
.
;
""")

    def test_reject_extension(self):
        self.compilation_ok(b"""
require "reject";

if header :contains "subject" "viagra" {
    reject;
}
""")


class InvalidSyntaxes(SieveTest):
    def test_nested_comments(self):
        self.compilation_ko(b"""
/* this is a comment /* with a nested comment inside */
it is allowed by the RFC :p */
""")

    def test_nonopened_block(self):
        self.compilation_ko(b"""
if header :is "Sender" "me@example.com" 
    discard;
}
""")

    def test_nonclosed_block(self):
        self.compilation_ko(b"""
if header :is "Sender" "me@example.com" {
    discard;

""")

    def test_unknown_token(self):
        self.compilation_ko(b"""
if header :is "Sender" "Toto" & header :contains "Cc" "Tata" {
    
}
""")

    def test_empty_string_list(self):
        self.compilation_ko(b"require [];")

    def test_unclosed_string_list(self):
        self.compilation_ko(b'require ["toto", "tata";')

    def test_misplaced_comma_in_string_list(self):
        self.compilation_ko(b'require ["toto",];')

    def test_nonopened_tests_list(self):
        self.compilation_ko(b"""
if anyof header :is "Sender" "me@example.com",
          header :is "Sender" "myself@example.com") {
    fileinto "trash";
}
""")

    def test_nonclosed_tests_list(self):
        self.compilation_ko(b"""
if anyof (header :is "Sender" "me@example.com",
          header :is "Sender" "myself@example.com" {
    fileinto "trash";
}
""")

    def test_nonclosed_tests_list2(self):
        self.compilation_ko(b"""
if anyof (header :is "Sender" {
    fileinto "trash";
}
""")

    def test_misplaced_comma_in_tests_list(self):
        self.compilation_ko(b"""
if anyof (header :is "Sender" "me@example.com",) {

}
""")

    def test_comma_inside_arguments(self):
        self.compilation_ko(b"""
require "fileinto", "enveloppe";
""")

    def test_non_ordered_args(self):
        self.compilation_ko(b"""
if address "From" :is "tim@example.com" {
    discard;
}
""")

    def test_extra_arg(self):
        self.compilation_ko(b"""
if address :is "From" "tim@example.com" "tutu" {
    discard;
}
""")

    def test_empty_not(self):
        self.compilation_ko(b"""
if not {
    discard;
}
""")

    def test_missing_semicolon(self):
        self.compilation_ko(b"""
require ["fileinto"]
""")

    def test_missing_semicolon_in_block(self):
        self.compilation_ko(b"""
if true {
    stop
}
""")

    def test_misplaced_parenthesis(self):
        self.compilation_ko(b"""
if (true) {

}
""")


class LanguageRestrictions(SieveTest):
    def test_unknown_control(self):
        self.compilation_ko(b"""
macommande "Toto";
""")

    def test_misplaced_elsif(self):
        self.compilation_ko(b"""
elsif true {

}
""")

    def test_misplaced_elsif2(self):
        self.compilation_ko(b"""
elsif header :is "From" "toto" {

}
""")

    def test_misplaced_nested_elsif(self):
        self.compilation_ko(b"""
if true {
  elsif false {

  }
}
""")

    def test_unexpected_argument(self):
        self.compilation_ko(b'stop "toto";')

    def test_bad_arg_value(self):
        self.compilation_ko(b"""
if header :isnot "Sent" "me@example.com" {
  stop;
}
""")

    def test_bad_arg_value2(self):
        self.compilation_ko(b"""
if header :isnot "Sent" 10000 {
  stop;
}
""")

    def test_bad_comparator_value(self):
        self.compilation_ko(b"""
if header :contains :comparator "i;prout" "Subject" "MAKE MONEY FAST" {
  discard;
}
""")

    def test_not_included_extension(self):
        self.compilation_ko(b"""
if header :contains "Subject" "MAKE MONEY FAST" {
  fileinto "spam";
}
""")

    def test_test_outside_control(self):
        self.compilation_ko(b"true;")


class DateCommands(SieveTest):
    def test_currentdate_command(self):
        self.compilation_ok(b"""require ["date", "relational"];

if allof ( currentdate :value "ge" "date" "2013-10-23" , currentdate :value "le" "date" "2014-10-12" ) 
{
    discard;
}
""")

    def test_currentdate_command_timezone(self):
        self.compilation_ok(b"""require ["date", "relational"];

if allof ( currentdate :zone "+0100" :value "ge" "date" "2013-10-23" , currentdate :value "le" "date" "2014-10-12" ) 
{
    discard;
}
""")

    def test_currentdate_norel(self):
        self.compilation_ok(b"""require ["date"];

if allof ( 
  currentdate :zone "+0100" :is "date" "2013-10-23"  
) 
{
    discard;
}""")


class VariablesCommands(SieveTest):
    def test_set_command(self):
        self.compilation_ok(b"""require ["variables"];

set "matchsub" "testsubject";
        
if allof (
  header :contains ["Subject"] "${header}"
)
{
  discard;
}
""")


class CopyWithoutSideEffectsTestCase(SieveTest):
    """RFC3894 test cases."""

    def test_redirect_with_copy(self):
        self.compilation_ko(b"""
if header :contains "subject" "test" {
    redirect :copy "dev@null.com";
}
""")

        self.compilation_ok(b"""require "copy";
if header :contains "subject" "test" {
    redirect :copy "dev@null.com";
}
""")

    def test_fileinto_with_copy(self):
        self.compilation_ko(b"""require "fileinto";
if header :contains "subject" "test" {
    fileinto :copy "Spam";
}
""")
        self.assertEqual(
            self.parser.error, "line 3: extension 'copy' not loaded")

        self.compilation_ok(b"""require ["fileinto", "copy"];
if header :contains "subject" "test" {
    fileinto :copy "Spam";
}
""")


if __name__ == "__main__":
    unittest.main()
