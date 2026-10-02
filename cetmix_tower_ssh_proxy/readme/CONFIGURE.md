**Prerequisites**

The SSH proxy server must be reachable from the Cetmix Tower host using its regular SSH connection settings.

The proxy server must also be able to reach the target server on its SSH host and port.

SSH TCP forwarding must be enabled on every server used as an SSH proxy. The SSH server configuration should allow TCP forwarding, for example:

```text
AllowTcpForwarding yes
```

If `PermitOpen` restrictions are configured on the SSH server, access to the required target SSH host and port must also be allowed.

For multi-hop routes, every proxy server must be able to reach the next server in the route.

**Configure an SSH Proxy Server**

1. Navigate to `Cetmix Tower > Servers > Servers`.
2. Create a new server or open an existing server that will be used as the SSH proxy.
3. Configure its regular SSH connection settings:

   * IP Address
   * SSH Port
   * SSH Username
   * SSH Authentication Mode
   * SSH Password or SSH Private Key
   * Host Key settings
4. Keep `SSH Connection Route` set to `Direct`.

The proxy server must have a working direct SSH connection from the Tower host unless it is itself configured to use another SSH proxy.

**Configure a Target Server**

1. Navigate to `Cetmix Tower > Servers > Servers`.
2. Create a new server or open the target server.
3. Configure the SSH credentials of the target server.
4. Set `SSH Connection Route` to `SSH Proxy`.
5. Select the proxy server in `SSH Proxy Server`.
6. Save the server.
7. Use the standard Tower SSH connection test to verify the configuration.

The SSH credentials configured on the target server are always used to authenticate on the target server. The credentials configured on the proxy server are used only for the connection to that proxy server.

**Host Key Verification**

Host key verification is performed independently for every server in the route.

When host key verification is enabled, each proxy server must have its own valid host key configured.

If host key verification is temporarily skipped for the requested target connection, for example while obtaining its host key, the setting applies only to the target server. Proxy servers continue to use their own host key verification settings.

**Multi-Hop SSH Proxy**

A proxy server can itself use another SSH proxy.

For example:

```text
Cetmix Tower
    |
    v
Proxy A
    |
    v
Proxy B
    |
    v
Target Server
```

Configure the route as follows:

* `Proxy A`: `SSH Connection Route = Direct`
* `Proxy B`: `SSH Connection Route = SSH Proxy`, `SSH Proxy Server = Proxy A`
* `Target Server`: `SSH Connection Route = SSH Proxy`, `SSH Proxy Server = Proxy B`

Cetmix Tower automatically builds the complete route from the outermost proxy to the target server.

Circular proxy routes are not allowed. The maximum supported proxy chain is 8 hops.

**Server Templates**

SSH proxy settings are also available on Server Templates.

Set `SSH Connection Route` and `SSH Proxy Server` on a Server Template to use the same connection route as the default when creating servers from that template.
