# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import _, api, models
from odoo.exceptions import ValidationError

from .constants import SSH_CONNECTION_ERROR, SSH_CONNECTION_TIMEOUT
from .cx_tower_server import SSH


class CetmixTower(models.AbstractModel):
    """Generic model used to simplify Odoo automation.

    Used to keep main integration function in a single place.

    For example when writing automated actions one can use
    `env["cetmix.tower"].create_server_from_template(..)`
    instead of
    `env["cx.tower.server.template"].create_server_from_template(..)
    """

    _name = "cetmix.tower"
    _description = "Tower automation helper model"

    @api.model
    def server_create_from_template(self, template_reference, server_name, **kwargs):
        """Shortcut for the same method of the 'cx.tower.server.template' model.

        Important! Add dedicated tests for this function if modified later.
        """
        return self.env["cx.tower.server.template"].create_server_from_template(
            template_reference=template_reference, server_name=server_name, **kwargs
        )

    @api.model
    def server_set_variable_value(self, server_reference, variable_reference, value):
        """Set variable value for selected server.
        Modifies existing variable value or creates a new one.

        Args:
            server_reference (Char): Server reference
            variable_reference (Char): Variable reference
            value (Char): Variable value

        Returns:
            Dict: with who keys:
            - exit_code (Char)
            - message (Char)
        """

        server = self.env["cx.tower.server"].get_by_reference(server_reference)
        if not server:
            return {"exit_code": -1, "message": _("Server not found")}
        variable = self.env["cx.tower.variable"].get_by_reference(variable_reference)
        if not variable:
            return {"exit_code": -1, "message": _("Variable not found")}

        # Check if variable is already defined for the server
        variable_value_record = variable.value_ids.filtered(
            lambda v: v.server_id == server
        )
        if variable_value_record:
            variable_value_record.value_char = value
            result = {"exit_code": 0, "message": _("Variable value updated")}

        else:
            self.env["cx.tower.variable.value"].create(
                {
                    "variable_id": variable.id,
                    "server_id": server.id,
                    "value_char": value,
                }
            )
            result = {"exit_code": 0, "message": _("Variable value created")}
        return result

    @api.model
    def server_get_variable_value(
        self, server_reference, variable_reference, check_global=True
    ):
        """Get variable value for selected server.

        Args:
            server_reference (Char): Server reference
            variable_reference (Char): Variable reference
            check_global (bool, optional): Check for global value if variable
                is not defined for selected server. Defaults to True.
        Returns:
            Char: variable value or None
        """

        # Get server by reference
        server = self.env["cx.tower.server"].get_by_reference(server_reference)
        if not server:
            return None
        result = self.env["cx.tower.variable.value"].get_by_variable_reference(
            variable_reference, server.id, check_global
        )

        # Get server defined value first
        value = result.get("server")

        # Get global value if value is not set
        if not value and check_global:
            value = result.get("global")
        return value

    @api.model
    def server_check_ssh_connection(self, server_reference, attempts=5, timeout=15):
        """Check if SSH connection to the server is available.

        Args:
            server_reference (Char): Server reference.
            attempts (int): Number of attempts to try the connection.
                Default is 5.
            timeout (int): Timeout in seconds for each connection attempt.
                Default is 15 seconds.
        Raises:
            ValidationError:
                If the provided server reference is invalid or
                the server cannot be found.
        Returns:
            dict: {
                "code": int,
                    # 0 for success,
                    # 408 if the SSH connection timed out after all attempts,
                    # 503 if there was a generic SSH connection error.
                "message": str  # Description of the result
            }
        """
        server = self.env["cx.tower.server"].get_by_reference(server_reference)
        if not server:
            raise ValidationError(_("No server found for the provided reference."))

        # Prepare SSH connection parameters
        ssh_params = {
            "host": server.ip_v4_address or server.ip_v6_address,
            "username": server.ssh_username,
            "port": int(server.ssh_port),
            "timeout": timeout,
            "mode": server.ssh_auth_mode,
        }

        if server.ssh_auth_mode == "p":
            ssh_params["password"] = server.ssh_password
        elif server.ssh_auth_mode == "k":
            ssh_params["ssh_key"] = server.ssh_key_id.sudo().secret_value

        # Initialize SSH connection instance
        ssh_connection = SSH(**ssh_params)

        # Try connecting multiple times
        for attempt in range(1, attempts + 1):
            try:
                ssh_connection.connection()
                return {
                    "code": 0,
                    "message": _("Connection successful."),
                }
            except TimeoutError as e:
                if attempt == attempts:
                    return {
                        "code": SSH_CONNECTION_TIMEOUT,
                        "message": _(
                            "Connection timed out after %(attempts)s attempts. "
                            "Error: %(err)s",
                            attempts=attempts,
                            err=str(e),
                        ),
                    }
            except Exception as e:
                if attempt == attempts:
                    return {
                        "code": SSH_CONNECTION_ERROR,
                        "message": _(
                            "Failed to connect after %(attempts)s attempts. "
                            "Error: %(err)s",
                            attempts=attempts,
                            err=str(e),
                        ),
                    }
            finally:
                ssh_connection.disconnect()

        # If all attempts fail
        return {
            "code": SSH_CONNECTION_ERROR,
            "message": _("All connection connection attempts have failed."),
        }
