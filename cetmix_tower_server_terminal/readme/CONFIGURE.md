To configure this module:

1. Configure the target server in Cetmix Tower.
2. Set SSH credentials in the server form:
	- SSH private key (recommended), or password according to the selected auth mode.
3. Configure host verification:
	- Set the server host key for strict verification, or
	- enable Skip Host Key Check when host key verification is not required.

The terminal session reuses these server SSH settings to open the interactive PTY shell.
