This module adds SSH proxy support to Cetmix Tower.

It allows a Tower server to be used as an SSH proxy (jump/bastion host) for connecting to another server that is not directly reachable from the Tower host.

Proxy connections use SSH `direct-tcpip` forwarding and support multi-hop routes, allowing proxy servers to use other proxy servers.

Standard Cetmix Tower SSH operations continue to work transparently through the configured proxy route, including command execution and SFTP operations.

Each hop uses the standard Cetmix Tower SSH configuration. Host-key verification is performed independently for each hop.

Queue execution is supported transparently through the Tower SSH transport layer.
