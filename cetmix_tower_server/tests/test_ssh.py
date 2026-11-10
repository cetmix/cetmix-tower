import io
import socket
import threading
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from paramiko import (
    AUTH_SUCCESSFUL,
    ECDSAKey,
    RSAKey,
    ServerInterface,
    SSHClient,
    SSHException,
    Transport,
)

from odoo.tests.common import BaseCase

from ..ssh.ssh import SSHConnection


class TestSSHHostKeys(BaseCase):
    """Exercise real Paramiko host verification before authentication."""

    connection_class = SSHConnection
    client_module = "odoo.addons.cetmix_tower_server.ssh.ssh"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.remote_key = RSAKey.generate(1024)
        cls.other_key = RSAKey.generate(1024)

    def _connection(self, host_key=None, port=22):
        """Return a password connection using the selected connection class."""
        return self.connection_class(
            host="tower.example",
            port=port,
            username="tower",
            password="password",
            host_key=host_key,
        )

    @contextmanager
    def _client(self, known_key=None, port=22):
        """Use real SSHClient verification with a controlled remote transport."""
        client = SSHClient()
        transport = MagicMock()
        transport.gss_kex_used = False
        transport.get_remote_server_key.return_value = self.remote_key
        transport.get_security_options.return_value.key_types = (
            Transport._preferred_keys
        )

        def load_keys():
            if known_key:
                hostname = "tower.example" if port == 22 else f"[tower.example]:{port}"
                client._system_host_keys.add(hostname, known_key.get_name(), known_key)

        with (
            patch(f"{self.client_module}.SSHClient", return_value=client),
            patch.object(client, "load_system_host_keys", side_effect=load_keys),
            patch.object(
                client,
                "_families_and_addresses",
                return_value=[(2, ("127.0.0.1", port))],
            ),
            patch("paramiko.client.socket.socket"),
            patch("paramiko.client.Transport", return_value=transport),
            patch.object(client, "_auth") as authenticate,
        ):
            try:
                yield client, authenticate
            finally:
                client.close()

    def test_unknown_host_rejected_before_authentication(self):
        """Missing pins must never imply trust, including repeated attempts."""
        connection = self._connection()
        with self._client() as (_, authenticate):
            for _attempt in range(2):
                with self.assertRaises(SSHException):
                    connection.connect()
            authenticate.assert_not_called()
            self.assertIsNone(connection._ssh_client)

    def test_unknown_host_rejected_with_private_key_auth(self):
        """Private-key authentication also requires a verified server identity."""
        connection = self._connection()
        private_key = io.StringIO()
        self.remote_key.write_private_key(private_key)
        connection.mode = "k"
        connection.ssh_key = private_key.getvalue()
        with self._client() as (_, authenticate):
            with self.assertRaises(SSHException):
                connection.connect()
            authenticate.assert_not_called()

    def test_malformed_pin_never_falls_back_to_system_keys(self):
        """Invalid or unsupported pins cannot be reinterpreted as missing pins."""
        for pin in ("not-base64!", "AAAA"):
            with (
                self.subTest(pin=pin),
                self._client(self.remote_key) as (_, authenticate),
            ):
                with self.assertRaises(SSHException):
                    self._connection(pin).connect()
                authenticate.assert_not_called()

    def test_known_host_accepted(self):
        """System known_hosts remains usable without a Tower pin."""
        for port in (22, 2222):
            with (
                self.subTest(port=port),
                self._client(self.remote_key, port) as (client, authenticate),
            ):
                self.assertIs(self._connection(port=port).connect(), client)
                authenticate.assert_called_once()

    def test_changed_known_host_rejected(self):
        """A changed known host key must fail before authentication."""
        with self._client(self.other_key) as (_, authenticate):
            with self.assertRaises(SSHException):
                self._connection().connect()
            authenticate.assert_not_called()

    def test_matching_pin_accepted(self):
        """The configured Tower pin permits authentication."""
        with self._client() as (client, authenticate):
            self.assertIs(
                self._connection(self.remote_key.get_base64()).connect(), client
            )
            authenticate.assert_called_once()

    def test_mismatched_pin_rejected_even_if_known_host_matches(self):
        """System known_hosts must not override an explicit Tower pin."""
        with self._client(self.remote_key) as (_, authenticate):
            with self.assertRaises(SSHException):
                self._connection(self.other_key.get_base64()).connect()
            authenticate.assert_not_called()

    def test_matching_pin_overrides_stale_known_host(self):
        """A stale system entry must not override the configured Tower pin."""
        with self._client(self.other_key) as (_, authenticate):
            self._connection(self.remote_key.get_base64()).connect()
            authenticate.assert_called_once()

    def test_pin_selects_matching_algorithm_on_multi_key_server(self):
        """An RSA pin must work when the same host also offers an ECDSA key."""
        client_socket, server_socket = socket.socketpair()
        server = Transport(server_socket)
        server.add_server_key(self.remote_key)
        server.add_server_key(ECDSAKey.generate())
        stop = threading.Event()
        authenticated = threading.Event()

        class AuthServer(ServerInterface):
            def check_auth_password(self, username, password):
                authenticated.set()
                return AUTH_SUCCESSFUL

        def serve():
            server.start_server(server=AuthServer())
            stop.wait(5)

        worker = threading.Thread(target=serve, daemon=True)
        client = SSHClient()
        connect = client.connect
        worker.start()
        try:
            with (
                patch(f"{self.client_module}.SSHClient", return_value=client),
                patch.object(
                    client,
                    "connect",
                    side_effect=lambda **kwargs: connect(
                        **dict(kwargs, sock=client_socket, look_for_keys=False)
                    ),
                ),
            ):
                self._connection(self.remote_key.get_base64(), port=2222).connect()
                self.assertTrue(authenticated.is_set())
                self.assertEqual(
                    client.get_transport().get_remote_server_key(), self.remote_key
                )
        finally:
            stop.set()
            client.close()
            server.close()
            client_socket.close()
            server_socket.close()
            worker.join(timeout=5)


class TestSSHHostKeyDiscovery(BaseCase):
    """Discovery is a key exchange only, with no reusable authenticated client."""

    def test_discovery_never_authenticates_or_creates_client(self):
        """Reading an untrusted key must not send credentials or cache a client."""
        with (
            patch(
                "odoo.addons.cetmix_tower_server.ssh.ssh.socket.create_connection"
            ) as open_socket,
            patch(
                "odoo.addons.cetmix_tower_server.ssh.ssh.Transport"
            ) as transport_class,
            patch("odoo.addons.cetmix_tower_server.ssh.ssh.SSHClient") as client_class,
        ):
            transport = transport_class.return_value
            transport.get_remote_server_key.return_value.get_base64.return_value = (
                "unverified-key"
            )
            self.assertEqual(
                SSHConnection.fetch_host_key("target", 2222, 30), "unverified-key"
            )
            open_socket.assert_called_once_with(("target", 2222), timeout=30)
            transport.start_client.assert_called_once_with(timeout=30)
            transport.auth_password.assert_not_called()
            transport.auth_publickey.assert_not_called()
            transport.auth_none.assert_not_called()
            client_class.assert_not_called()
            transport.close.assert_called_once_with()
            open_socket.return_value.close.assert_called_once_with()

    def test_proxy_channel_closed_after_failed_discovery(self):
        """A failed key exchange closes both the transport and proxy channel."""
        channel = MagicMock()
        with (
            patch(
                "odoo.addons.cetmix_tower_server.ssh.ssh.socket.create_connection"
            ) as open_socket,
            patch(
                "odoo.addons.cetmix_tower_server.ssh.ssh.Transport"
            ) as transport_class,
        ):
            transport = transport_class.return_value
            transport.start_client.side_effect = SSHException("Handshake failed")
            with self.assertRaises(SSHException):
                SSHConnection.fetch_host_key("target", 22, 30, sock=channel)
            open_socket.assert_not_called()
            transport.close.assert_called_once_with()
            channel.close.assert_called_once_with()
