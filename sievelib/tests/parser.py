# coding: utf-8

"""
Unit tests for the SIEVE language parser.
"""
from sievelib.parser import Parser
import unittest

class SieveTest(unittest.TestCase):
    def setUp(self):
        self.parser = Parser()

    def __checkCompilation(self, script, result):
        self.assertEqual(self.parser.parse(script), result)

    def compilation_ok(self, script):
        self.__checkCompilation(script, True)

    def compilation_ko(self, script):
        self.__checkCompilation(script, False)

class ValidSyntaxes(SieveTest):

    def test_hash_comment(self):
        self.compilation_ok("""
if size :over 100k { # this is a comment
    discard;
}
""")

    def test_bracket_comment(self):
        self.compilation_ok("""
if size :over 100K { /* this is a comment
    this is still a comment */ discard /* this is a comment
    */ ;
}
""")
        
    def test_string_with_bracket_comment(self):
        self.compilation_ok("""
if header :contains "Cc" "/* comment */" {
    discard;
}
""")

    def test_nested_blocks(self):
        self.compilation_ok("""
if header :contains "Sender" "example.com" {
  if header :contains "Sender" "me@" {
    discard;
  } elsif header :contains "Sender" "you@" {
    keep;
  }
}
""")

    def test_true_test(self):
        self.compilation_ok("""
if true {

}
""")

    def test_rfc5228_extended(self):
        self.compilation_ok("""
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

    def test_explicit_comparator(self):
        self.compilation_ok("""
if header :contains :comparator "i;octet" "Subject" "MAKE MONEY FAST" {
  discard;
}
""")

    def test_non_ordered_args(self):
        self.compilation_ok("""
if address :all :is "from" "tim@example.com" {
    discard;
}
""")

    def test_multiple_not(self):
        self.compilation_ok("""
if not not not not true {
    stop;
}
""")

    def test_just_one_command(self):
        self.compilation_ok("keep;")

class InvalidSyntaxes(SieveTest):

    def test_nested_comments(self):
        self.compilation_ko("""
/* this is a comment /* with a nested comment inside */
it is allowed by the RFC :p */
""")

    def test_nonopened_block(self):
        self.compilation_ko("""
if header :is "Sender" "me@example.com" 
    discard;
}
""")

    def test_nonclosed_block(self):
        self.compilation_ko("""
if header :is "Sender" "me@example.com" {
    discard;

""")

    def test_unknown_token(self):
        self.compilation_ko("""
if header :is "Sender" "Toto" & header :contains "Cc" "Tata" {
    
}
""")

    def test_empty_string_list(self):
        self.compilation_ko("require [];")

    def test_unclosed_string_list(self):
        self.compilation_ko('require ["toto", "tata";')

    def test_misplaced_comma_in_string_list(self):
        self.compilation_ko('require ["toto",];')

    def test_nonopened_tests_list(self):
        self.compilation_ko("""
if anyof header :is "Sender" "me@example.com",
          header :is "Sender" "myself@example.com") {
    fileinto "trash";
}
""")

    def test_nonclosed_tests_list(self):
        self.compilation_ko("""
if anyof (header :is "Sender" "me@example.com",
          header :is "Sender" "myself@example.com" {
    fileinto "trash";
}
""")

    def test_nonclosed_tests_list2(self):
        self.compilation_ko("""
if anyof (header :is "Sender" {
    fileinto "trash";
}
""")

    def test_misplaced_comma_in_tests_list(self):
        self.compilation_ko("""
if anyof (header :is "Sender" "me@example.com",) {

}
""")

    def test_comma_inside_arguments(self):
        self.compilation_ko("""
require "fileinto", "enveloppe";
""")

    def test_non_ordered_args(self):
        self.compilation_ko("""
if address "From" :is "tim@example.com" {
    discard;
}
""")

    def test_extra_arg(self):
        self.compilation_ko("""
if address :is "From" "tim@example.com" "tutu" {
    discard;
}
""")

    def test_empty_not(self):
        self.compilation_ko("""
if not {
    discard;
}
""")

    def test_missing_semicolon(self):
        self.compilation_ko("""
require ["fileinto"]
""")

class LanguageRestrictions(SieveTest):

    def test_unknown_control(self):
        self.compilation_ko("""
macommande "Toto";
""")

    def test_misplaced_elsif(self):
        self.compilation_ko("""
elsif true {

}
""")

    def test_unexpected_argument(self):
        self.compilation_ko('stop "toto";')

    def test_bad_arg_value(self):
        self.compilation_ko("""
if header :isnot "Sent" "me@example.com" {
  stop;
}
""")

    def test_bad_arg_value2(self):
        self.compilation_ko("""
if header :isnot "Sent" 10000 {
  stop;
}
""")

    def test_bad_comparator_value(self):
        self.compilation_ko("""
if header :contains :comparator "i;prout" "Subject" "MAKE MONEY FAST" {
  discard;
}
""")

    def test_not_included_extension(self):
        self.compilation_ko("""
if header :contains "Subject" "MAKE MONEY FAST" {
  fileinto "spam";
}
""")

    def test_test_outside_control(self):
        self.compilation_ko("true;")
                            
if __name__ == "__main__":
    unittest.main()

