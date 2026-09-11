## Connect to a Server Through an SSH Proxy

A server configured with `SSH Connection Route = SSH Proxy` is used in Cetmix Tower in the same way as a directly reachable server.

For example, assume the following network:

```text
Cetmix Tower
    |
    | SSH
    v
SSH Proxy
203.0.113.10
    |
    | SSH direct-tcpip
    v
Target Server
10.0.0.20
```

The Tower host can connect to `203.0.113.10`, but it cannot directly access `10.0.0.20`.

Configure the servers as follows.

### SSH Proxy

Create the proxy server with its regular SSH settings:

```text
Name: SSH Proxy
IP Address: 203.0.113.10
SSH Connection Route: Direct
```

Configure its SSH username, authentication mode, password or private key, and host key as for any regular Tower server.

### Target Server

Create the target server using its private address:

```text
Name: Private Server
IP Address: 10.0.0.20
SSH Connection Route: SSH Proxy
SSH Proxy Server: SSH Proxy
```

Configure the SSH credentials belonging to the target server itself.

When Tower opens the connection, it connects to the proxy first and asks the proxy SSH server to open a `direct-tcpip` channel to `10.0.0.20:22`. The target SSH session is then established through that channel.

## Running Commands

Commands are executed on the target server, not on the SSH proxy.

For the route:

```text
Cetmix Tower -> SSH Proxy -> Target Server
```

running a Tower SSH command on `Target Server` uses the proxy only as transport. The command itself is executed by the SSH session established with `Target Server`.

No special command configuration is required.

## SFTP and File Operations

SFTP operations use the same proxy connection automatically.

This includes operations such as:

* uploading files;
* downloading files;
* deleting files;
* file template operations that use SFTP.

No separate proxy configuration is required for SFTP.

## Multi-Hop Connection

Multiple SSH proxies can be chained.

For example:

```text
Cetmix Tower
    |
    v
Public Bastion
    |
    v
VPN Gateway
    |
    v
Private Server
```

Configure:

```text
Public Bastion
    SSH Connection Route: Direct

VPN Gateway
    SSH Connection Route: SSH Proxy
    SSH Proxy Server: Public Bastion

Private Server
    SSH Connection Route: SSH Proxy
    SSH Proxy Server: VPN Gateway
```

When connecting to `Private Server`, Tower resolves the complete route and establishes the connections in the following order:

```text
Cetmix Tower -> Public Bastion -> VPN Gateway -> Private Server
```

Commands and SFTP operations are executed against `Private Server`.

## Overlapping Private Networks

The complete proxy route is used to identify an SSH proxy connection.

This allows servers with identical private IP addresses to be accessed through different proxy servers.

For example:

```text
Customer A Proxy -> 10.0.0.20
Customer B Proxy -> 10.0.0.20
```

These are treated as separate SSH routes because they use different proxy servers.
