# coding: utf-8

"""Managesieve test cases."""

import unittest
try:
    from unittest import mock
except ImportError:
    import mock

from sievelib import managesieve

CAPABILITIES = (
    b'"IMPLEMENTATION" "Example1 ManageSieved v001"\r\n'
    b'"VERSION" "1.0"\r\n'
    b'"SASL" "PLAIN SCRAM-SHA-1 GSSAPI"\r\n'
    b'"SIEVE" "fileinto vacation"\r\n'
    b'"STARTTLS"\r\n'
)

CAPABILITIES_WITHOUT_VERSION = (
    b'"IMPLEMENTATION" "Example1 ManageSieved v001"\r\n'
    b'"SASL" "PLAIN SCRAM-SHA-1 GSSAPI"\r\n'
    b'"SIEVE" "fileinto vacation"\r\n'
    b'"STARTTLS"\r\n'
)

AUTHENTICATION = (
    CAPABILITIES +
    b'OK "Dovecot ready."\r\n'
    b'OK "Logged in."\r\n'
)

LISTSCRIPTS = (
    b'"summer_script"\r\n'
    b'"vac\xc3\xa0tion_script"\r\n'
    b'{13}\r\n'
    b'clever"script\r\n'
    b'"main_script" ACTIVE\r\n'
    b'OK "Listscripts completed."\r\n'
)

GETSCRIPT = (
    b'{54}\r\n'
    b'#this is my wonderful script\r\n'
    b'reject "I reject all";\r\n'
    b'OK "Getscript completed."\r\n'
)


@mock.patch("socket.socket")
class ManageSieveTestCase(unittest.TestCase):
    """Managesieve test cases."""

    def setUp(self):
        """Create client."""
        self.client = managesieve.Client("127.0.0.1")

    def authenticate(self, mock_socket):
        """Authenticate client."""
        mock_socket.return_value.recv.side_effect = (AUTHENTICATION, )
        self.client.connect(b"user", b"password")

    def test_connection(self, mock_socket):
        """Test connection."""
        self.authenticate(mock_socket)
        self.assertEqual(
            self.client.get_sieve_capabilities(), ["fileinto", "vacation"])
        mock_socket.return_value.recv.side_effect = (b"OK test\r\n", )
        self.client.logout()

    def test_capabilities(self, mock_socket):
        """Test capabilities command."""
        self.authenticate(mock_socket)
        mock_socket.return_value.recv.side_effect = (
            CAPABILITIES + b'OK "Capability completed."\r\n', )
        capabilities = self.client.capability()
        self.assertEqual(capabilities, CAPABILITIES)

    def test_listscripts(self, mock_socket):
        """Test listscripts command."""
        self.authenticate(mock_socket)
        mock_socket.return_value.recv.side_effect = (LISTSCRIPTS, )
        active_script, others = self.client.listscripts()
        self.assertEqual(active_script, "main_script")
        self.assertEqual(
            others, [u'summer_script', u'vacàtion_script', u'clever"script'])

    def test_getscript(self, mock_socket):
        """Test getscript command."""
        self.authenticate(mock_socket)
        mock_socket.return_value.recv.side_effect = (GETSCRIPT, )
        content = self.client.getscript("main_script")
        self.assertEqual(
            content, u'#this is my wonderful script\nreject "I reject all";')

    def test_putscript(self, mock_socket):
        """Test putscript command."""
        self.authenticate(mock_socket)
        script = """require ["fileinto"];

if envelope :contains "to" "tmartin+sent" {
  fileinto "INBOX.sent";
}
"""
        mock_socket.return_value.recv.side_effect = (
            b'OK "putscript completed."\r\n', )
        self.assertTrue(self.client.putscript(u"test_script", script))

    def test_deletescript(self, mock_socket):
        """Test deletescript command."""
        self.authenticate(mock_socket)
        mock_socket.return_value.recv.side_effect = (
            b'OK "deletescript completed."\r\n', )
        self.assertTrue(self.client.deletescript(u"test_script"))

    def test_checkscript(self, mock_socket):
        """Test checkscript command."""
        self.authenticate(mock_socket)
        mock_socket.return_value.recv.side_effect = (
            b'OK "checkscript completed."\r\n', )
        script = "#comment\r\nInvalidSieveCommand\r\n"
        self.assertTrue(self.client.checkscript(script))

    def test_setactive(self, mock_socket):
        """Test setactive command."""
        self.authenticate(mock_socket)
        mock_socket.return_value.recv.side_effect = (
            b'OK "setactive completed."\r\n', )
        self.assertTrue(self.client.setactive(u"test_script"))

    def test_havespace(self, mock_socket):
        """Test havespace command."""
        self.authenticate(mock_socket)
        mock_socket.return_value.recv.side_effect = (
            b'OK "havespace completed."\r\n', )
        self.assertTrue(self.client.havespace(u"test_script", 1000))

    def test_renamescript(self, mock_socket):
        """Test renamescript command."""
        self.authenticate(mock_socket)
        mock_socket.return_value.recv.side_effect = (
            b'OK "renamescript completed."\r\n', )
        self.assertTrue(self.client.renamescript(u"old_script", u"new_script"))

    def test_renamescript_simulated(self, mock_socket):
        """Test renamescript command simulation."""
        mock_socket.return_value.recv.side_effect = (
            CAPABILITIES_WITHOUT_VERSION +
            b'OK "Dovecot ready."\r\n'
            b'OK "Logged in."\r\n',
        )
        self.client.connect(b"user", b"password")
        mock_socket.return_value.recv.side_effect = (
            LISTSCRIPTS,
            GETSCRIPT,
            b'OK "putscript completed."\r\n',
            b'OK "setactive completed."\r\n',
            b'OK "deletescript completed."\r\n'
        )
        self.assertTrue(
            self.client.renamescript(u"main_script", u"new_script"))


if __name__ == "__main__":
    unittest.main()
