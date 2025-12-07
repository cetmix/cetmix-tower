# flake8: noqa: E501
# Copyright (C) 2025 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).


# Default Python code used in Webhook Authenticator
DEFAULT_WEBHOOK_AUTHENTICATOR_CODE = """# Please refer to the 'Help' tab and documentation for more information.
#
# You can return authenticator result in the 'result' variable which is a dictionary:
#   result = {"allowed": <bool, mandatory, default=False>, "http_code": <int, optional>, "message": <str, optional>}
#   default value is {"allowed": False}
"""

# Default Python code help used in Webhook Authenticator
DEFAULT_WEBHOOK_AUTHENTICATOR_CODE_HELP = """
<h3>Help for Webhook Authenticator Python Code</h3>
<div style="margin-bottom: 10px;">
    <p>
        The Python code for the webhook authenticator must return the <code>result</code> variable, which is a dictionary.<br>
        <strong>Allowed keys:</strong>
        <ul>
            <li><code>allowed</code> (<b>bool</b>, required): Authentication result. <code>True</code> if allowed, <code>False</code> otherwise.</li>
            <li><code>http_code</code> (<b>int</b>, optional): HTTP status code to return if authentication fails (default is 403).</li>
            <li><code>message</code> (<b>str</b>, optional): Error message to show to the client.</li>
        </ul>
        <strong>Examples:</strong>
        <pre style='background:#f7f7f7; padding:6px; border-radius:4px'>
# Allow all requests
result = {"allowed": True}

# Deny with custom code and message
result = {"allowed": False, "http_code": 401, "message": "Unauthorized request"}
        </pre>
    </p>
    <strong>Available variables:</strong>
</div>
"""


# Default Python code used in Webhook
DEFAULT_WEBHOOK_CODE = """# Please refer to the 'Help' tab and documentation for more information.
#
# You can return webhook result in the 'result' variable which is a dictionary:
#   result = {"exit_code": <int, default=0>, "message": <string, default=None>}
#   default value is {"exit_code": 0, "message": None}
"""

# Default Python code help used in Webhook
DEFAULT_WEBHOOK_CODE_HELP = """
<h3>Help for Webhook Python Code</h3>
<div style="margin-bottom: 10px;">
    <p>
        The webhook Python code must set the <code>result</code> variable, which is a dictionary.<br>
        <strong>Allowed keys:</strong>
        <ul>
            <li><code>exit_code</code> (<b>int</b>, optional, default=0): Exit code (0 means success, other values indicate failure).</li>
            <li><code>message</code> (<b>str</b>, optional): Message to return in the HTTP response and log.</li>
        </ul>
        <strong>Example:</strong>
        <pre style='background:#f7f7f7; padding:6px; border-radius:4px'>
# Simple successful result
result = {"exit_code": 0, "message": "Webhook processed successfully"}

# Failure example
result = {"exit_code": 1, "message": "Something went wrong"}
        </pre>
    </p>
    <strong>Available variables:</strong>
</div>
"""
