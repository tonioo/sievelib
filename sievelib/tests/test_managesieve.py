"""Managesieve test cases."""

import unittest
from unittest import mock
import warnings

from sievelib import managesieve

CAPABILITIES = (
    b'"IMPLEMENTATION" "Example1 ManageSieved v001"\r\n'
    b'"VERSION" "1.0"\r\n'
    b'"SASL" "PLAIN SCRAM-SHA-1 GSSAPI OAUTHBEARER XOAUTH2"\r\n'
    b'"SIEVE" "fileinto vacation"\r\n'
    b'"STARTTLS"\r\n'
)

CAPABILITIES_WITHOUT_VERSION = (
    b'"IMPLEMENTATION" "Example1 ManageSieved v001"\r\n'
    b'"SASL" "PLAIN SCRAM-SHA-1 GSSAPI OAUTHBEARER XOAUTH2"\r\n'
    b'"SIEVE" "fileinto vacation"\r\n'
    b'"STARTTLS"\r\n'
)

AUTHENTICATION = CAPABILITIES + b'OK "Dovecot ready."\r\n' b'OK "Logged in."\r\n'

LISTSCRIPTS = (
    b'"summer_script"\r\n'
    b'"vac\xc3\xa0tion_script"\r\n'
    b"{13}\r\n"
    b'clever"script\r\n'
    b'"main_script" ACTIVE\r\n'
    b'OK "Listscripts completed."\r\n'
)

GETSCRIPT = (
    b"{54}\r\n"
    b"#this is my wonderful script\r\n"
    b'reject "I reject all";\r\n'
    b'OK "Getscript completed."\r\n'
)


def recv_then_eof(*chunks):
    """Simulate a server sending chunks then closing the connection.

    Each recv() call returns at most one chunk (split to respect the
    requested size), then b"" (EOF). A client that keeps reading after
    EOF would spin forever, so we fail loudly instead.
    """
    pending = list(chunks)
    eof_reads = 0

    def recv(size):
        nonlocal eof_reads
        if pending:
            chunk = pending.pop(0)
            if len(chunk) > size:
                pending.insert(0, chunk[size:])
                chunk = chunk[:size]
            return chunk
        eof_reads += 1
        if eof_reads > 10:
            raise AssertionError("recv() called again after EOF")
        return b""

    return recv


@mock.patch("socket.socket")
class ManageSieveTestCase(unittest.TestCase):
    """Managesieve test cases."""

    def setUp(self):
        """Create client."""
        self.client = managesieve.Client("127.0.0.1")
        # tests connect without TLS on purpose, see test_unencrypted_warning
        catcher = warnings.catch_warnings()
        catcher.__enter__()
        self.addCleanup(catcher.__exit__, None, None, None)
        warnings.filterwarnings("ignore", "Credentials are sent", UserWarning)

    def authenticate(self, mock_socket):
        """Authenticate client."""
        mock_socket.return_value.recv.side_effect = (AUTHENTICATION,)
        self.client.connect("user", "password")

    def test_connection(self, mock_socket):
        """Test connection."""
        self.authenticate(mock_socket)
        self.assertEqual(self.client.get_sieve_capabilities(), ["fileinto", "vacation"])
        mock_socket.return_value.recv.side_effect = (b"OK test\r\n",)
        self.client.logout()

    def test_auth_oauthbearer(self, mock_socket):
        """Test OAUTHBEARER mechanism."""
        mock_socket.return_value.recv.side_effect = (AUTHENTICATION,)
        self.assertTrue(self.client.connect("user", "token", authmech="OAUTHBEARER"))

    def test_auth_xoauth2(self, mock_socket):
        """Test XOAUTH2 mechanism."""
        mock_socket.return_value.recv.side_effect = (AUTHENTICATION,)
        self.assertTrue(self.client.connect("user", "token", authmech="XOAUTH2"))

    def test_auth_unsupported_mechanism(self, mock_socket):
        """Test that an unsupported mechanism is rejected."""
        with self.assertRaises(managesieve.Error):
            self.client.connect("user", "password", authmech="DIGEST-MD5")
        mock_socket.return_value.connect.assert_not_called()

    def test_unencrypted_warning(self, mock_socket):
        """Test a warning is emitted when authenticating without TLS."""
        mock_socket.return_value.recv.side_effect = (AUTHENTICATION,)
        with self.assertWarnsRegex(UserWarning, "unencrypted"):
            self.client.connect("user", "password")

    def test_greeting_no(self, mock_socket):
        """Test a NO greeting is reported as an error."""
        mock_socket.return_value.recv.side_effect = (b'NO "Service unavailable"\r\n',)
        with self.assertRaisesRegex(managesieve.Error, "capabilities"):
            self.client.connect("user", "password")

    def test_no_without_message(self, mock_socket):
        """Test NO responses without a quoted message."""
        self.authenticate(mock_socket)
        mock_socket.return_value.recv.side_effect = (b"NO\r\n",)
        self.assertFalse(self.client.deletescript("test_script"))
        self.assertEqual((self.client.errcode, self.client.errmsg), (b"", b""))
        mock_socket.return_value.recv.side_effect = (b"NO (QUOTA/MAXSIZE)\r\n",)
        self.assertFalse(self.client.putscript("test_script", "keep;"))
        self.assertEqual(
            (self.client.errcode, self.client.errmsg), (b"QUOTA/MAXSIZE", b"")
        )
        mock_socket.return_value.recv.side_effect = (b'NO (NONEXISTENT) "No"\r\n',)
        self.assertFalse(self.client.deletescript("test_script"))
        self.assertEqual(
            (self.client.errcode, self.client.errmsg), (b"NONEXISTENT", b"No")
        )

    def test_no_with_literal_or_code_parameters(self, mock_socket):
        """Test NO responses with code parameters or a literal message."""
        self.authenticate(mock_socket)
        mock_socket.return_value.recv.side_effect = (
            b'NO (TAG "a)b") "Not \\"here\\""\r\n',
        )
        self.assertFalse(self.client.deletescript("test_script"))
        self.assertEqual(
            (self.client.errcode, self.client.errmsg), (b'TAG "a)b"', b'Not "here"')
        )
        mock_socket.return_value.recv.side_effect = (
            b"NO (QUOTA/MAXSIZE) {15}\r\nToo\r\nbig, sorry\r\n",
            b'OK "Deletescript completed."\r\n',
        )
        self.assertFalse(self.client.putscript("test_script", "keep;"))
        self.assertEqual(
            (self.client.errcode, self.client.errmsg),
            (b"QUOTA/MAXSIZE", b"Too\r\nbig, sorry"),
        )
        # the whole literal was read: the next response is not shifted
        self.assertTrue(self.client.deletescript("test_script"))
        mock_socket.return_value.recv.side_effect = (b"NO garbage\r\n",)
        with self.assertRaisesRegex(managesieve.Error, "Bad error message"):
            self.client.deletescript("test_script")

    def test_capabilities(self, mock_socket):
        """Test capabilities command."""
        self.authenticate(mock_socket)
        mock_socket.return_value.recv.side_effect = (
            CAPABILITIES + b'OK "Capability completed."\r\n',
        )
        capabilities = self.client.capability()
        self.assertEqual(capabilities, CAPABILITIES)

    def test_listscripts(self, mock_socket):
        """Test listscripts command."""
        self.authenticate(mock_socket)
        mock_socket.return_value.recv.side_effect = (LISTSCRIPTS,)
        active_script, others = self.client.listscripts()
        self.assertEqual(active_script, "main_script")
        self.assertEqual(others, ["summer_script", "vacàtion_script", 'clever"script'])

    def test_getscript(self, mock_socket):
        """Test getscript command."""
        self.authenticate(mock_socket)
        mock_socket.return_value.recv.side_effect = (GETSCRIPT,)
        content = self.client.getscript("main_script")
        self.assertEqual(
            content, '#this is my wonderful script\nreject "I reject all";'
        )

    def test_putscript(self, mock_socket):
        """Test putscript command."""
        self.authenticate(mock_socket)
        script = """require ["fileinto"];

if envelope :contains "to" "tmartin+sent" {
  fileinto "INBOX.sent";
}
"""
        mock_socket.return_value.recv.side_effect = (b'OK "putscript completed."\r\n',)
        self.assertTrue(self.client.putscript("test_script", script))

    def test_putscript_normalizes_line_breaks(self, mock_socket):
        """Test LF and CRLF line breaks are both sent as CRLF."""
        self.authenticate(mock_socket)
        mock_socket.return_value.recv.side_effect = (b'OK "putscript completed."\r\n',)
        script = 'require "vacation";\nvacation text:\r\nété\n.\n;'
        self.assertTrue(self.client.putscript("test_script", script))
        mock_socket.return_value.sendall.assert_called_with(
            b'PUTSCRIPT "test_script" {48+}\r\n'
            b'require "vacation";\r\nvacation text:\r\n\xc3\xa9t\xc3\xa9\r\n.\r\n;\r\n'
        )

    def test_deletescript(self, mock_socket):
        """Test deletescript command."""
        self.authenticate(mock_socket)
        mock_socket.return_value.recv.side_effect = (
            b'OK "deletescript completed."\r\n',
        )
        self.assertTrue(self.client.deletescript("test_script"))

    def test_script_name_is_escaped(self, mock_socket):
        """Test quotes and backslashes in a script name are escaped."""
        self.authenticate(mock_socket)
        mock_socket.return_value.recv.side_effect = (
            b'OK "deletescript completed."\r\n',
        )
        self.assertTrue(self.client.deletescript('clever"scr\\ipt'))
        mock_socket.return_value.sendall.assert_called_with(
            b'DELETESCRIPT "clever\\"scr\\\\ipt"\r\n'
        )

    def test_script_name_with_line_break_is_rejected(self, mock_socket):
        """Test a script name cannot inject another command."""
        self.authenticate(mock_socket)
        mock_socket.return_value.sendall.reset_mock()
        with self.assertRaises(managesieve.Error):
            self.client.deletescript('x"\r\nDELETESCRIPT "important')
        mock_socket.return_value.sendall.assert_not_called()

    def test_checkscript(self, mock_socket):
        """Test checkscript command."""
        self.authenticate(mock_socket)
        mock_socket.return_value.recv.side_effect = (
            b'OK "checkscript completed."\r\n',
        )
        script = "#comment\r\nInvalidSieveCommand\r\n"
        self.assertTrue(self.client.checkscript(script))

    def test_setactive(self, mock_socket):
        """Test setactive command."""
        self.authenticate(mock_socket)
        mock_socket.return_value.recv.side_effect = (b'OK "setactive completed."\r\n',)
        self.assertTrue(self.client.setactive("test_script"))

    def test_havespace(self, mock_socket):
        """Test havespace command."""
        self.authenticate(mock_socket)
        mock_socket.return_value.recv.side_effect = (b'OK "havespace completed."\r\n',)
        self.assertTrue(self.client.havespace("test_script", 1000))

    def test_renamescript(self, mock_socket):
        """Test renamescript command."""
        self.authenticate(mock_socket)
        mock_socket.return_value.recv.side_effect = (
            b'OK "renamescript completed."\r\n',
        )
        self.assertTrue(self.client.renamescript("old_script", "new_script"))

    def test_renamescript_simulated(self, mock_socket):
        """Test renamescript command simulation."""
        mock_socket.return_value.recv.side_effect = (
            CAPABILITIES_WITHOUT_VERSION + b'OK "Dovecot ready."\r\n'
            b'OK "Logged in."\r\n',
        )
        self.client.connect("user", "password")
        mock_socket.return_value.recv.side_effect = (
            LISTSCRIPTS,
            GETSCRIPT,
            b'OK "putscript completed."\r\n',
            b'OK "setactive completed."\r\n',
            b'OK "deletescript completed."\r\n',
        )
        self.assertTrue(self.client.renamescript("main_script", "new_script"))

    def test_renamescript_simulated_listing_fails(self, mock_socket):
        """Test renamescript simulation when LISTSCRIPTS fails."""
        mock_socket.return_value.recv.side_effect = (
            CAPABILITIES_WITHOUT_VERSION + b'OK "Dovecot ready."\r\n'
            b'OK "Logged in."\r\n',
        )
        self.client.connect("user", "password")
        mock_socket.return_value.recv.side_effect = (b'NO "Try later"\r\n',)
        self.assertFalse(self.client.renamescript("main_script", "new_script"))

    def test_connection_closed_during_greeting(self, mock_socket):
        """Test server closing the connection while sending capabilities."""
        mock_socket.return_value.recv.side_effect = recv_then_eof(
            b'"IMPLEMENTATION" "Dovecot Pigeonhole"\r\n"SIEVE" "fileinto'
        )
        with self.assertRaisesRegex(managesieve.Error, "Connection closed"):
            self.client.connect("user", "password")

    def test_connection_closed_during_literal(self, mock_socket):
        """Test server closing the connection in the middle of a literal."""
        self.authenticate(mock_socket)
        mock_socket.return_value.recv.side_effect = recv_then_eof(
            b"{54}\r\n#this is my wonder"
        )
        with self.assertRaisesRegex(managesieve.Error, "Connection closed"):
            self.client.getscript("main_script")

    def test_getscript_literal_split(self, mock_socket):
        """Test literal received through several recv() calls."""
        self.authenticate(mock_socket)
        script = b'require "fileinto";\r\n\r\nkeep;\r\n'
        mock_socket.return_value.recv.side_effect = recv_then_eof(
            b"{%d}\r\n" % len(script) + script[:5],
            script[5:12],
            script[12:] + b'OK "Getscript completed."\r\n',
        )
        content = self.client.getscript("main_script")
        self.assertEqual(content, 'require "fileinto";\n\nkeep;')


if __name__ == "__main__":
    unittest.main()
