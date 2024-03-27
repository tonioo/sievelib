import unittest
import io

from sievelib.factory import FiltersSet
from .. import parser


class FactoryTestCase(unittest.TestCase):

    def setUp(self):
        self.fs = FiltersSet("test")

    def test_get_filter_conditions(self):
        """Test get_filter_conditions method."""
        orig_conditions = [("Sender", ":is", "toto@toto.com")]
        self.fs.addfilter(
            "ruleX",
            orig_conditions,
            [
                ("fileinto", ":copy", "Toto"),
            ],
        )
        conditions = self.fs.get_filter_conditions("ruleX")
        self.assertEqual(orig_conditions, conditions)

        orig_conditions = [
            ("exists", "list-help", "list-unsubscribe", "list-subscribe", "list-owner")
        ]
        self.fs.addfilter("ruleY", orig_conditions, [("fileinto", "List")])
        conditions = self.fs.get_filter_conditions("ruleY")
        self.assertEqual(orig_conditions, conditions)

        orig_conditions = [("Sender", ":notis", "toto@toto.com")]
        self.fs.addfilter(
            "ruleZ",
            orig_conditions,
            [
                ("fileinto", ":copy", "Toto"),
            ],
        )
        conditions = self.fs.get_filter_conditions("ruleZ")
        self.assertEqual(orig_conditions, conditions)

        orig_conditions = [
            (
                "notexists",
                "list-help",
                "list-unsubscribe",
                "list-subscribe",
                "list-owner",
            )
        ]
        self.fs.addfilter("ruleA", orig_conditions, [("fileinto", "List")])
        conditions = self.fs.get_filter_conditions("ruleA")
        self.assertEqual(orig_conditions, conditions)

        orig_conditions = [("envelope", ":is", ["From"], ["hello"])]
        self.fs.addfilter("ruleB", orig_conditions, [("fileinto", "INBOX")])
        conditions = self.fs.get_filter_conditions("ruleB")
        self.assertEqual(orig_conditions, conditions)

        orig_conditions = [("body", ":raw", ":notcontains", "matteo")]
        self.fs.addfilter("ruleC", orig_conditions, [("fileinto", "INBOX")])
        conditions = self.fs.get_filter_conditions("ruleC")
        self.assertEqual(orig_conditions, conditions)

        orig_conditions = [
            ("currentdate", ":zone", "+0100", ":notis", "date", "2019-02-26")
        ]
        self.fs.addfilter("ruleD", orig_conditions, [("fileinto", "INBOX")])
        conditions = self.fs.get_filter_conditions("ruleD")
        self.assertEqual(orig_conditions, conditions)

        orig_conditions = [
            ("currentdate", ":zone", "+0100", ":value", "gt", "date", "2019-02-26")
        ]
        self.fs.addfilter("ruleE", orig_conditions, [("fileinto", "INBOX")])
        conditions = self.fs.get_filter_conditions("ruleE")
        self.assertEqual(orig_conditions, conditions)

    def test_get_filter_conditions_from_parser_result(self):
        res = """require ["fileinto"];

# rule:[test]
if anyof (exists ["Subject"]) {
    fileinto "INBOX";
}
"""
        p = parser.Parser()
        p.parse(res)
        fs = FiltersSet("test", "# rule:")
        fs.from_parser_result(p)
        c = fs.get_filter_conditions("[test]")
        self.assertEqual(c, [("exists", "Subject")])

        res = """require ["date", "fileinto"];

# rule:aaa
if anyof (currentdate :zone "+0100" :is "date" ["2019-03-27"]) {
    fileinto "INBOX";
}
"""
        p = parser.Parser()
        p.parse(res)
        fs = FiltersSet("aaa", "# rule:")
        fs.from_parser_result(p)
        c = fs.get_filter_conditions("aaa")
        self.assertEqual(
            c, [("currentdate", ":zone", "+0100", ":is", "date", "2019-03-27")]
        )

        res = """require ["envelope", "fileinto"];

# rule:[aaa]
if anyof (envelope :contains ["To"] ["hello@world.it"]) {
    fileinto "INBOX";
}
"""
        p = parser.Parser()
        p.parse(res)
        fs = FiltersSet("aaa", "# rule:")
        fs.from_parser_result(p)
        c = fs.get_filter_conditions("[aaa]")
        self.assertEqual(c, [("envelope", ":contains", ["To"], ["hello@world.it"])])

    def test_get_filter_matchtype(self):
        """Test get_filter_matchtype method."""
        self.fs.addfilter(
            "ruleX",
            [
                ("Sender", ":is", "toto@toto.com"),
            ],
            [
                ("fileinto", ":copy", "Toto"),
            ],
        )
        match_type = self.fs.get_filter_matchtype("ruleX")
        self.assertEqual(match_type, "anyof")

    def test_get_filter_actions(self):
        """Test get_filter_actions method."""
        self.fs.addfilter(
            "ruleX",
            [
                ("Sender", ":is", "toto@toto.com"),
            ],
            [
                ("fileinto", ":copy", "Toto"),
            ],
        )
        actions = self.fs.get_filter_actions("ruleX")
        self.assertIn("fileinto", actions[0])
        self.assertIn(":copy", actions[0])
        self.assertIn("Toto", actions[0])

        self.fs.addfilter("ruleY", [("Subject", ":contains", "aaa")], [("stop",)])
        actions = self.fs.get_filter_actions("ruleY")
        self.assertIn("stop", actions[0])

    def test_add_header_filter(self):
        output = io.StringIO()
        self.fs.addfilter(
            "rule1",
            [
                ("Sender", ":is", "toto@toto.com"),
            ],
            [
                ("fileinto", ":copy", "Toto"),
            ],
        )
        self.assertIsNot(self.fs.getfilter("rule1"), None)
        self.fs.tosieve(output)
        self.assertEqual(
            output.getvalue(),
            """require ["fileinto", "copy"];

# Filter: rule1
if anyof (header :is "Sender" "toto@toto.com") {
    fileinto :copy "Toto";
}
""",
        )
        output.close()

    def test_use_action_with_tag(self):
        output = io.StringIO()
        self.fs.addfilter(
            "rule1",
            [
                ("Sender", ":is", "toto@toto.com"),
            ],
            [
                ("redirect", ":copy", "toto@titi.com"),
            ],
        )
        self.assertIsNot(self.fs.getfilter("rule1"), None)
        self.fs.tosieve(output)
        self.assertEqual(
            output.getvalue(),
            """require ["copy"];

# Filter: rule1
if anyof (header :is "Sender" "toto@toto.com") {
    redirect :copy "toto@titi.com";
}
""",
        )
        output.close()

    def test_add_header_filter_with_not(self):
        output = io.StringIO()
        self.fs.addfilter(
            "rule1",
            [("Sender", ":notcontains", "toto@toto.com")],
            [("fileinto", "Toto")],
        )
        self.assertIsNot(self.fs.getfilter("rule1"), None)
        self.fs.tosieve(output)
        self.assertEqual(
            output.getvalue(),
            """require ["fileinto"];

# Filter: rule1
if anyof (not header :contains "Sender" "toto@toto.com") {
    fileinto "Toto";
}
""",
        )

    def test_add_exists_filter(self):
        output = io.StringIO()
        self.fs.addfilter(
            "rule1",
            [
                (
                    "exists",
                    "list-help",
                    "list-unsubscribe",
                    "list-subscribe",
                    "list-owner",
                )
            ],
            [("fileinto", "Toto")],
        )
        self.assertIsNot(self.fs.getfilter("rule1"), None)
        self.fs.tosieve(output)
        self.assertEqual(
            output.getvalue(),
            """require ["fileinto"];

# Filter: rule1
if anyof (exists ["list-help","list-unsubscribe","list-subscribe","list-owner"]) {
    fileinto "Toto";
}
""",
        )

    def test_add_exists_filter_with_not(self):
        output = io.StringIO()
        self.fs.addfilter(
            "rule1",
            [
                (
                    "notexists",
                    "list-help",
                    "list-unsubscribe",
                    "list-subscribe",
                    "list-owner",
                )
            ],
            [("fileinto", "Toto")],
        )
        self.assertIsNot(self.fs.getfilter("rule1"), None)
        self.fs.tosieve(output)
        self.assertEqual(
            output.getvalue(),
            """require ["fileinto"];

# Filter: rule1
if anyof (not exists ["list-help","list-unsubscribe","list-subscribe","list-owner"]) {
    fileinto "Toto";
}
""",
        )

    def test_add_size_filter(self):
        output = io.StringIO()
        self.fs.addfilter(
            "rule1", [("size", ":over", "100k")], [("fileinto", "Totoéé")]
        )
        self.assertIsNot(self.fs.getfilter("rule1"), None)
        self.fs.tosieve(output)
        self.assertEqual(
            output.getvalue(),
            """require ["fileinto"];

# Filter: rule1
if anyof (size :over 100k) {
    fileinto "Totoéé";
}
""",
        )

    def test_remove_filter(self):
        self.fs.addfilter(
            "rule1", [("Sender", ":is", "toto@toto.com")], [("fileinto", "Toto")]
        )
        self.assertIsNot(self.fs.getfilter("rule1"), None)
        self.assertEqual(self.fs.removefilter("rule1"), True)
        self.assertIs(self.fs.getfilter("rule1"), None)

    def test_disablefilter(self):
        """
        FIXME: Extra spaces are written between if and anyof, why?!
        """
        self.fs.addfilter(
            "rule1", [("Sender", ":is", "toto@toto.com")], [("fileinto", "Toto")]
        )
        self.assertIsNot(self.fs.getfilter("rule1"), None)
        self.assertEqual(self.fs.disablefilter("rule1"), True)
        output = io.StringIO()
        self.fs.tosieve(output)
        self.assertEqual(
            output.getvalue(),
            """require ["fileinto"];

# Filter: rule1
if false {
    if     anyof (header :is "Sender" "toto@toto.com") {
        fileinto "Toto";
    }
}
""",
        )
        output.close()
        self.assertEqual(self.fs.is_filter_disabled("rule1"), True)

    def test_add_filter_unicode(self):
        """Add a filter containing unicode data."""
        name = "Test\xe9".encode("utf-8")
        self.fs.addfilter(
            name,
            [
                ("Sender", ":is", "toto@toto.com"),
            ],
            [
                ("fileinto", "Toto"),
            ],
        )
        self.assertIsNot(self.fs.getfilter("Testé"), None)
        self.assertEqual(
            "{}".format(self.fs),
            """require ["fileinto"];

# Filter: Testé
if anyof (header :is "Sender" "toto@toto.com") {
    fileinto "Toto";
}
""",
        )

    def test_add_body_filter(self):
        """Add a body filter."""
        self.fs.addfilter(
            "test", [("body", ":raw", ":contains", "matteo")], [("fileinto", "Toto")]
        )
        self.assertEqual(
            "{}".format(self.fs),
            """require ["body", "fileinto"];

# Filter: test
if anyof (body :contains :raw ["matteo"]) {
    fileinto "Toto";
}
""",
        )

    def test_add_notbody_filter(self):
        """Add a not body filter."""
        self.fs.addfilter(
            "test", [("body", ":raw", ":notcontains", "matteo")], [("fileinto", "Toto")]
        )
        self.assertEqual(
            "{}".format(self.fs),
            """require ["body", "fileinto"];

# Filter: test
if anyof (not body :contains :raw ["matteo"]) {
    fileinto "Toto";
}
""",
        )

    def test_add_envelope_filter(self):
        """Add a envelope filter."""
        self.fs.addfilter(
            "test", [("envelope", ":is", ["From"], ["hello"])], [("fileinto", "INBOX")]
        )
        self.assertEqual(
            "{}".format(self.fs),
            """require ["envelope", "fileinto"];

# Filter: test
if anyof (envelope :is ["From"] ["hello"]) {
    fileinto "INBOX";
}
""",
        )

    def test_add_notenvelope_filter(self):
        """Add a not envelope filter."""
        self.fs.addfilter(
            "test",
            [("envelope", ":notis", ["From"], ["hello"])],
            [("fileinto", "INBOX")],
        )
        self.assertEqual(
            "{}".format(self.fs),
            """require ["envelope", "fileinto"];

# Filter: test
if anyof (not envelope :is ["From"] ["hello"]) {
    fileinto "INBOX";
}
""",
        )

    def test_add_currentdate_filter(self):
        """Add a currentdate filter."""
        self.fs.addfilter(
            "test",
            [("currentdate", ":zone", "+0100", ":is", "date", "2019-02-26")],
            [("fileinto", "INBOX")],
        )
        self.assertEqual(
            "{}".format(self.fs),
            """require ["date", "fileinto"];

# Filter: test
if anyof (currentdate :zone "+0100" :is "date" ["2019-02-26"]) {
    fileinto "INBOX";
}
""",
        )

        self.fs.removefilter("test")
        self.fs.addfilter(
            "test",
            [("currentdate", ":zone", "+0100", ":value", "gt", "date", "2019-02-26")],
            [("fileinto", "INBOX")],
        )
        self.assertEqual(
            "{}".format(self.fs),
            """require ["date", "fileinto", "relational"];

# Filter: test
if anyof (currentdate :zone "+0100" :value "gt" "date" ["2019-02-26"]) {
    fileinto "INBOX";
}
""",
        )


if __name__ == "__main__":
    unittest.main()
