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
        self.fs.tosieve(output)
        self.assertEqual(output.getvalue(), """require ["fileinto"];

# Filter: rule1
if anyof (header :is "Sender" "toto@toto.com") {
    fileinto "Toto";
}
""")
        output.close()


if __name__ == "__main__":
    unittest.main()
