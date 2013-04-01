# coding: utf-8
import unittest
import cStringIO
from sievelib.factory import FiltersSet


class FactoryTestCase(unittest.TestCase):
    
    def setUp(self):
        self.fs = FiltersSet("test")

    def test_add_filter(self):
        output = cStringIO.StringIO()
        self.fs.addfilter("rule1",
                          [('Sender', ":is", 'toto@toto.com'),],
                          [("fileinto", 'Toto'),])
        self.assertIsNot(self.fs.getfilter("rule1"), None)
        self.fs.tosieve(output)
        self.assertEqual(output.getvalue(), """require ["fileinto"];

# Filter: rule1
if anyof (header :is "Sender" "toto@toto.com") {
    fileinto "Toto";
}
""")
        output.close()

    def test_remove_filter(self):
        self.fs.addfilter("rule1",
                          [('Sender', ":is", 'toto@toto.com'),],
                          [("fileinto", 'Toto'),])
        self.assertIsNot(self.fs.getfilter("rule1"), None)
        self.assertEqual(self.fs.removefilter("rule1"), True)
        self.assertIs(self.fs.getfilter("rule1"), None)


    def test_disablefilter(self):
        """
        FIXME: Extra spaces are written between if and anyof, why?!
        """
        self.fs.addfilter("rule1",
                          [('Sender', ":is", 'toto@toto.com'),],
                          [("fileinto", 'Toto'),])
        self.assertIsNot(self.fs.getfilter("rule1"), None)
        self.assertEqual(self.fs.disablefilter("rule1"), True)
        output = cStringIO.StringIO()
        self.fs.tosieve(output)
        self.assertEqual(output.getvalue(), """require ["fileinto"];

# Filter: rule1
if false {
    if     anyof (header :is "Sender" "toto@toto.com") {
        fileinto "Toto";
    }
}
""")
        output.close()
        self.assertEqual(self.fs.is_filter_disabled("rule1"), True)

if __name__ == "__main__":
    unittest.main()
