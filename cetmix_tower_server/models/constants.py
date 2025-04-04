from odoo import _

# ***
# This file is used to define commonly used constants
# ***

# Returned when a general error occurs
GENERAL_ERROR = -100

# Returned when a resource is not found
NOT_FOUND = -101

# -- SSH

# Returned when an SSH connection error occurs
SSH_CONNECTION_ERROR = 503

# -- Command: -200 > -299

# Returned when trying to execute another instance of a command on the same server
# and this command doesn't allow parallel run
ANOTHER_COMMAND_RUNNING = -201

# Returned when no runner is found for command action
NO_COMMAND_RUNNER_FOUND = -202

# Returned when the command failed to execute due to a python code execution error
PYTHON_COMMAND_ERROR = -203

# Returned when the command failed to execute because the condition was not met
PLAN_LINE_CONDITION_CHECK_FAILED = -205

# Returned when the command timed out
COMMAND_TIMED_OUT = -206
COMMAND_TIMED_OUT_MESSAGE = _("Command timed out and was terminated")

# -- Plan: -300 > -399

# Returned when trying to execute another instance of a flightplan on the same server
# and this flightplan doesn't allow parallel run
ANOTHER_PLAN_RUNNING = -301

# Returned when trying to start plan without lines
PLAN_IS_EMPTY = -302

# Returned when a plan tries to parse a command log record which doesn't have
# a valid plan reference in it
PLAN_NOT_ASSIGNED = -303

# Returned when a plan tries to parse a command log record which doesn't have
# a valid plan line reference in it
PLAN_LINE_NOT_ASSIGNED = -304


# -- File: -400 > -499

# Returned when the file could not be created on the server
FILE_CREATION_FAILED = -400

# -- Default values

# Default SSH code used in SSH command
DEFAULT_SSH_CODE = _(
    """# Run any SSH command on the target system
# Examples: ls, cd, pwd, mkdir, rm
# Adapt commands to your specific OS.
"""
)

# Default Python code used in Python code command
DEFAULT_PYTHON_CODE = _(
    """# Please refer to the 'Help' tab and documentation for more information.
#
# You can return command result in the 'result' variable which is a dictionary:
#   result = {"exit_code": 0, "message": "Some message"}
#   default value is {"exit_code": 0, "message": None}
#
# Available variables:
#  - user: Current Odoo User
#  - env: Odoo Environment on which the action is triggered
#  - server: server on which the command is run
#  - tower: 'cetmix.tower' helper class
#  - time, datetime, dateutil, timezone: useful Python libraries
#  - requests: Python 'requests' library. Available methods: 'post', 'get', 'delete', 'request'
#  - json: Python 'json' library. Available methods: 'dumps'
#  - hashlib: Python 'hashlib' library. Available methods: 'sha1', 'sha224', 'sha256',
#    'sha384', 'sha512', 'sha3_224', 'sha3_256', 'sha3_384', 'sha3_512', 'shake_128',
#    'shake_256', 'blake2b', 'blake2s', 'md5', 'new'
#  - hmac: Python 'hmac' library. Use 'new' to create HMAC objects.
#    Available methods on the HMAC *object*: 'update', 'copy', 'digest', 'hexdigest'.
#    Module-level function: 'compare_digest'.
#  - float_compare: Odoo function to compare floats based on specific precisions
#  - UserError: Warning Exception to use with raise
"""  # noqa: E501
)

# Default Python code help displayed in the "Help" tab
DEFAULT_PYTHON_CODE_HELP = _(
    """
<h3>Help with Python expressions</h3>
<div style="margin-bottom: 10px;">
    <p>
        Each Python code command returns the <code>result</code> value which is a dictionary.
        <br>There are two keys in the dictionary:
        <ul>
    <li><code>exit_code</code>: Integer. Exit code of the command. "0" means success, any other value means failure. Default value is "0".</li>
    <li><code>message</code>: String. Message to be logged. Default value is "None".</li>
</ul>
Here is an example of a python code command:
<code style='white-space: pre-wrap'>
    server_name = server.name
    result = {"exit_code": 0, "message": "Server name is " + server_name}
</code>
</p>
<br>
Please refer to the <a href="https://cetmix.com/tower/documentation/command/#python-code-commands" target="_blank">official documentation</a> for more information and examples.
</div>
<p
>Various fields may use Python code or Python expressions. The
    following variables can be used:</p>
<ul>
    <li><code>user</code>: Current Odoo user</li>
    <li><code
        >env</code>: Odoo Environment on which the action is
        triggered</li>
    <li><code
        >server</code>: Server on which the command is run</li>
    <li><code
        >tower</code>: 'cetmix.tower' helper class shortcut</li>
    <li><code>time</code>, <code>datetime</code>, <code
        >dateutil</code>
        , <code
        >timezone</code>: useful Python libraries</li>
    <li><code
        >requests</code>: Python 'requests' library. Available methods: 'post', 'get', 'delete', 'request'</li>
    <li><code
        >json</code>: Python 'json' library. Available methods: 'dumps'</li>
    <li><code>hashlib</code>: Python 'hashlib' library.
            Available methods: 'sha1', 'sha224', 'sha256', 'sha384', 'sha512', 'sha3_224', 'sha3_256',<br
        />
            'sha3_384', 'sha3_512', 'shake_128', 'shake_256', 'blake2b', 'blake2s', 'md5', 'new'</li>
    <li><code
        >hmac</code>: Python 'hmac' library. Use 'new' to create HMAC objects.<br
        />
        Available methods on the HMAC *object*: 'update', 'copy', 'digest', 'hexdigest'.<br
        />
        Module-level function: 'compare_digest'.</li>
    <li><code
        >UserError</code>: Warning Exception to use with <code
        >
        raise</code></li>
</ul>
"""  # noqa: E501
)
