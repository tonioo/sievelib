"""Managesieve test cases."""

import socket
import unittest
try:
    from unittest import mock
except ImportError:
    import mock

from sievelib import managesieve

AUTHENTICATION = (
    b'"IMPLEMENTATION" "Example1 ManageSieved v001"\r\n'
    b'"VERSION" "1.0"\r\n'
    b'"SASL" "PLAIN SCRAM-SHA-1 GSSAPI"\r\n'
    b'"SIEVE" "fileinto vacation"\r\n'
    b'"STARTTLS"\r\n'
    b'OK\r\n'
    b'OK test\r\n'
)


class ManageSieveTestCase(unittest.TestCase):
    """Managesieve test cases."""

    def setUp(self):
        """Create client."""
        self.client = managesieve.Client("127.0.0.1")

    @mock.patch("socket.socket")
    def test_connect(self, mock_socket):
        """Test connection."""
        mock_socket.return_value.recv.side_effect = (AUTHENTICATION, )
        self.client.connect(b"user", b"password")
        self.assertEqual(
            self.client.get_sieve_capabilities(), ["fileinto", "vacation"])


if __name__ == "__main__":
    unittest.main()
