from odoo.addons.cetmix_tower_server.tests.test_ssh import TestSSHHostKeys

from ..ssh.proxy import ProxySSHConnection


class TestProxySSHHostKeys(TestSSHHostKeys):
    """Apply the host-verification contract to proxy target connections."""

    allow_inherited_tests_method = True
    connection_class = ProxySSHConnection
    client_module = "odoo.addons.cetmix_tower_ssh_proxy.ssh.proxy"
