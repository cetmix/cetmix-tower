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
COMMAND_TIMED_OUT_MESSAGE = "Command timed out and was terminated"

# Returned when the command is not compatible with the server
COMMAND_NOT_COMPATIBLE_WITH_SERVER = -207

# Returned when the command was stopped by user
COMMAND_STOPPED = -208

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

# Returned when any of the commands in the plan is not compatible with the server
PLAN_NOT_COMPATIBLE_WITH_SERVER = -306

# Returned when the flight plan was stopped by user
PLAN_STOPPED = -308

# -- File: -400 > -499

# Returned when the file could not be created on the server
FILE_CREATION_FAILED = -400

# Returned when the file could not be uploaded to the server
FILE_UPLOAD_FAILED = -401

# Returned when the file could not be downloaded from the server
FILE_DOWNLOAD_FAILED = -402

# -- Default values

# Default Python code used in Python code command
DEFAULT_PYTHON_CODE = """
# Please refer to the 'Help' tab and documentation for more information.
#
# You can return command result in the 'result' variable which is a dictionary:
#   result = {"exit_code": 0, "message": "Some message"}
#   default value is {"exit_code": 0, "message": None}
"""  # noqa: E501


# Default Python code help displayed in the "Help" tab
DEFAULT_PYTHON_CODE_HELP = """
<h3>Help with Python expressions</h3>
<div style="margin-bottom: 10px;">
    <p>
        Each Python code command returns the <code>result</code> value which is a dictionary.
        <br>There are two keys in the dictionary:
        <ul>
    <li><code>exit_code</code>: Integer. Exit code of the command. "0" means success, any other value means failure. Default value is "0".</li>
    <li><code>message</code>: String. Message to be logged. Default value is "None".</li>
</ul>
You can also access the <code>custom_values</code> dictionary that contains custom values provided to the command or flight plan.
Custom values can be modified, thus can be used to pass data between commands in a flight plan.
Please keep in mind that custom values are persistent only between commands in a flight plan and are not saved to the database.
<br/>
Here is an example of a python code command:

<code style='white-space: pre-wrap'>
    server_name = server.name
    build_name = custom_values.get("build_name")
    if build_name:
        result = {"exit_code": 0, "message": "Build name for " + server_name + " is " + build_name}
    else:
        result = {"exit_code": 0, "message": "No build name provided for " + server_name}
    custom_values["build_name"] = "New build name"
</code>
</p>
<br>
Please refer to the <a href="https://cetmix.com/tower/documentation/command/#python-code-commands" target="_blank">official documentation</a> for more information and examples.
</div>
<p
>Various fields may use Python code or Python expressions. The
    following variables can be used:</p>
"""  # noqa: E501
