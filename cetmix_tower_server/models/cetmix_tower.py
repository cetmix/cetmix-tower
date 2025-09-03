# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import logging
import time

from odoo import _, api, models
from odoo.exceptions import ValidationError

from .constants import NOT_FOUND, SSH_CONNECTION_ERROR

_logger = logging.getLogger(__name__)


class CetmixTower(models.AbstractModel):
    """Generic model used to simplify Odoo automation.

    Used to keep main integration function in a single place.

    For example when writing automated actions one can use
    `env["cetmix.tower"].create_server_from_template(..)`
    instead of
    `env["cx.tower.server.template"].create_server_from_template(..)
    """

    _name = "cetmix.tower"
    _description = "Cetmix Tower Odoo Automation"

    @api.model
    def server_create_from_template(self, template_reference, server_name, **kwargs):
        """Shortcut for the same method of the 'cx.tower.server.template' model.

        Important! Add dedicated tests for this function if modified later.
        """
        return self.env["cx.tower.server.template"].create_server_from_template(
            template_reference=template_reference, server_name=server_name, **kwargs
        )

    @api.model
    def server_run_command(
        self, server_reference, command_reference, get_result=True, **variable_values
    ):
        """Run command on selected server.

        Args:
            server_reference (Char): Server reference
            command_reference (Char): Command reference
            get_result (bool, optional): Get the result of the command.
                If False, the result will be saved to the log.
                Defaults to True.

        **variable_values:
            Dict: with variable values.
            The keys are the variable references and the values are the variable values.
            eg `{'odoo_version': '16.0'}`

        Returns:
            Dict: with two keys if `get_result` is True:
            - exit_code (Int): Exit code of the command
            - message (Char): Message of the command
        """

        server = self.env["cx.tower.server"].get_by_reference(server_reference)
        if not server:
            return {"exit_code": NOT_FOUND, "message": _("Server not found")}
        command = self.env["cx.tower.command"].get_by_reference(command_reference)
        if not command:
            return {"exit_code": NOT_FOUND, "message": _("Command not found")}

        # Will return command result if get_result is True
        # Otherwise will save to log and return None
        command_result = server.with_context(no_command_log=get_result).run_command(
            command, **{"variable_values": variable_values} if variable_values else {}
        )

        # Return command result if get_result is True
        if command_result:
            status = command_result.get("status")
            response = command_result.get("response", "")
            error = command_result.get("error", "")
            return {
                "exit_code": status,
                "message": response or error,
            }

    def server_run_flight_plan(
        self, server_reference, flight_plan_reference, **variable_values
    ):
        """Run flight plan on selected server.

        Args:
            server_reference (Char): Server reference
            flight_plan_reference (Char): Flight plan reference

        **variable_values:
            Dict: with variable values.
            The keys are the variable references and the values are the variable values.
            eg `{'odoo_version': '16.0'}`

        Returns:
            cx.tower.plan.log(): flight plan log record or False if error
        """
        server = self.env["cx.tower.server"].get_by_reference(server_reference)
        if not server:
            # This is not the best way to handle this, but it's the only way to
            # avoid complex response handling
            return False
        flight_plan = self.env["cx.tower.plan"].get_by_reference(flight_plan_reference)
        if not flight_plan:
            # This is not the best way to handle this, but it's the only way to
            # avoid complex response handling
            return False
        return server.run_flight_plan(
            flight_plan,
            **{"variable_values": variable_values} if variable_values else {},
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
            return {"exit_code": NOT_FOUND, "message": _("Server not found")}
        variable = self.env["cx.tower.variable"].get_by_reference(variable_reference)
        if not variable:
            return {"exit_code": NOT_FOUND, "message": _("Variable not found")}

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
            NOTE: 'check_global' is deprecated. Global values are always checked.
        Returns:
            Char: variable value or None
        """
        if not check_global:
            _logger.warning(
                "server_get_variable_value: 'check_global' is deprecated and "
                "will be removed in the future. "
                "Global values are always checked."
            )

        # Get server by reference
        server = self.env["cx.tower.server"].get_by_reference(server_reference)
        if not server:
            return None
        return (
            self.env["cx.tower.variable"]
            ._get_variable_values_by_references(
                variable_references=[variable_reference], server=server
            )
            .get(variable_reference)
        )

    @api.model
    def server_get_jet_template_variable_value(
        self, server_reference, jet_template_reference, variable_reference
    ):
        """Get variable value for selected jet template on selected server.

        Args:
            server_reference (Char): Server reference
            jet_template_reference (Char): Jet template reference
            variable_reference (Char): Variable reference
        Returns:
            Char: variable value or None
        """

        # Get server by reference
        server = self.env["cx.tower.server"].get_by_reference(server_reference)
        if not server:
            return None
        jet_template = self.env["cx.tower.jet.template"].get_by_reference(
            jet_template_reference
        )

        if not jet_template:
            return None

        return (
            self.env["cx.tower.variable"]
            ._get_variable_values_by_references(
                variable_references=[variable_reference],
                server=server,
                jet_template=jet_template,
            )
            .get(variable_reference)
        )

    @api.model
    def server_get_jet_variable_value(
        self, server_reference, jet_reference, variable_reference
    ):
        """Get variable value for selected jet on selected server.

        Args:
            server_reference (Char): Server reference
            jet_reference (Char): Jet reference
            variable_reference (Char): Variable reference
        Returns:
            Char: variable value or None
        """

        # Get server by reference
        server = self.env["cx.tower.server"].get_by_reference(server_reference)
        if not server:
            return None
        jet = self.env["cx.tower.jet"].get_by_reference(jet_reference)
        if not jet:
            return None

        return self.env["cx.tower.variable"]._get_variable_values_by_references(
            variable_references=[variable_reference], server=server, jet=jet
        )

    @api.model
    def server_check_ssh_connection(
        self,
        server_reference,
        attempts=5,
        wait_time=10,
        try_command=True,
        try_file=True,
    ):
        """Check if SSH connection to the server is available.
        This method only checks if the connection is available,
        it does not execute any commands to check if they are working.

        Args:
            server_reference (Char): Server reference.
            attempts (int): Number of attempts to try the connection.
                Default is 5.
            wait_time (int): Wait time in seconds between connection attempts.
                Default is 10 seconds.
            try_command (bool): Try to execute a command.
                Default is True.
            try_file (bool): Try file operations.
                Default is True.
        Raises:
            ValidationError:
                If the provided server reference is invalid or
                the server cannot be found.
        Returns:
            dict: {
                "exit_code": int,
                    0 for success,
                    error code for failure
                "message": str  # Description of the result
            }
        """
        server = self.env["cx.tower.server"].get_by_reference(server_reference)
        if not server:
            raise ValidationError(_("No server found for the provided reference."))

        # Try connecting multiple times
        for attempt in range(1, attempts + 1):
            try:
                _logger.info(
                    "Attempt %s of %s to connect to server %s",
                    attempt,
                    attempts,
                    server_reference,
                )
                result = server.test_ssh_connection(
                    raise_on_error=True,
                    return_notification=False,
                    try_command=try_command,
                    try_file=try_file,
                )
                if result.get("status") == 0:
                    return {
                        "exit_code": 0,
                        "message": _("Connection successful."),
                    }
                if attempt == attempts:
                    return {
                        "exit_code": SSH_CONNECTION_ERROR,
                        "message": _(
                            "Failed to connect after %(attempts)s attempts. "
                            "Error: %(err)s",
                            attempts=attempts,
                            err=result.get("error", ""),
                        ),
                    }
            except Exception as e:  # pylint: disable=broad-except
                if attempt == attempts:
                    return {
                        "exit_code": SSH_CONNECTION_ERROR,
                        "message": _("Failed to connect. Error: %(err)s", err=e),
                    }
            time.sleep(wait_time)

    @api.model
    def server_validate_secret(
        self, secret_value, secret_reference, server_reference=None
    ):
        """
        Validate the provided secret value against the actual secret.

        Accepts either a full inline reference (e.g. #!cxtower.secret.<REFERENCE>!#)
        or just a <REFERENCE>.

        Args:
            secret_value (Char): Value to validate
            secret_reference (Char): Reference code or inline reference
            server_reference (Char, optional): Reference code of the server
        Returns:
            Bool: True if the value matches the secret, False otherwise
        """
        server = self.env["cx.tower.server"]
        if server_reference:
            server = server.get_by_reference(server_reference)

        # Try to extract reference from inline format using _extract_key_parts
        key_parts = self.env["cx.tower.key"]._extract_key_parts(secret_reference)
        if key_parts:
            # _extract_key_parts returns a tuple: (key_type, reference).
            # We only need the reference part here.
            secret_reference = key_parts[1]

        value = self.env["cx.tower.key"]._resolve_key_type_secret(
            secret_reference, server_id=server.id
        )
        return value == secret_value
