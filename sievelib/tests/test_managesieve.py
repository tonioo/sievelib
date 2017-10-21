# coding: utf-8

"""Managesieve test cases."""

import socket
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
    b'OK "Listscripts completed.\r\n'
)

class ManageSieveTestCase(unittest.TestCase):
    """Managesieve test cases."""

    def setUp(self):
        """Create client."""
        self.client = managesieve.Client("127.0.0.1")

    @mock.patch("socket.socket")
    def test_connection(self, mock_socket):
        """Test connection."""
        mock_socket.return_value.recv.side_effect = (AUTHENTICATION, )
        self.client.connect(b"user", b"password")
        self.assertEqual(
            self.client.get_sieve_capabilities(), ["fileinto", "vacation"])
        mock_socket.return_value.recv.side_effect = (b"OK test\r\n", )
        self.client.logout()

    @mock.patch("socket.socket")
    def test_capabilities(self, mock_socket):
        """Test capabilities command."""
        mock_socket.return_value.recv.side_effect = (AUTHENTICATION, )
        self.client.connect(b"user", b"password")
        mock_socket.return_value.recv.side_effect = (
            CAPABILITIES + b'OK "Capability completed."\r\n', )
        capabilities = self.client.capability()
        self.assertEqual(capabilities, CAPABILITIES)

    @mock.patch("socket.socket")
    def test_listscripts(self, mock_socket):
        """Test listscripts command."""
        mock_socket.return_value.recv.side_effect = (AUTHENTICATION, )
        self.client.connect(b"user", b"password")
        mock_socket.return_value.recv.side_effect = (LISTSCRIPTS, )
        active_script, others = self.client.listscripts()
        self.assertEqual(active_script, "main_script")
        self.assertEqual(
            others, ['summer_script', 'vacàtion_script', 'clever"script'])


if __name__ == "__main__":
    unittest.main()
