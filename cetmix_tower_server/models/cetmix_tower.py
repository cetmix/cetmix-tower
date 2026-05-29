# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import logging
import time
import warnings

from odoo import _, api, models
from odoo.exceptions import ValidationError

from . import tools
from .constants import NOT_FOUND, SSH_CONNECTION_ERROR

_logger = logging.getLogger(__name__)


class CetmixTower(models.AbstractModel):
    """Generic model used to simplify Odoo automation.
    Used to keep main integration function in a single place.
    """

    _name = "cetmix.tower"
    _description = "Cetmix Tower Odoo Automation"

    @api.model
    def server_create_from_template(self, template_reference, server_name, **kwargs):
        """
        THIS METHOD IS DEPRECATED. USE THE 'cx.tower.server.template' MODEL DIRECTLY.
        """
        _logger.warning(
            "server_create_from_template: This method is deprecated "
            "and will be removed in the future. "
            "Use the 'cx.tower.server.template' model directly instead."
        )
        return self.env["cx.tower.server.template"].create_server_from_template(
            template_reference=template_reference, server_name=server_name, **kwargs
        )

    @api.model
    def server_run_command(
        self, server_reference, command_reference, get_result=True, **variable_values
    ):
        """
        THIS METHOD IS DEPRECATED. USE THE 'cx.tower.server' MODEL DIRECTLY.
        """

        _logger.warning(
            "server_run_command: This method is deprecated and "
            "will be removed in the future. "
            "Use the 'cx.tower.server' model directly instead."
        )
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
        """THIS METHOD IS DEPRECATED. USE THE 'cx.tower.server' MODEL DIRECTLY."""
        _logger.warning(
            "server_run_flight_plan: This method is deprecated and "
            "will be removed in the future. "
            "Use the 'cx.tower.server' model directly instead."
        )
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
        """THIS METHOD IS DEPRECATED. USE THE 'cx.tower.server' MODEL DIRECTLY."""
        _logger.warning(
            "server_set_variable_value: This method is deprecated and "
            "will be removed in the future. "
            "Use the 'cx.tower.server' model directly instead."
        )
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
        """THIS METHOD IS DEPRECATED. USE THE 'cx.tower.server' MODEL DIRECTLY."""
        _logger.warning(
            "server_get_variable_value: This method is deprecated and "
            "will be removed in the future. "
            "Use the 'cx.tower.server' model directly instead."
        )
        if not check_global:
            warnings.warn(
                "server_get_variable_value: 'check_global' is deprecated and "
                "will be removed in the future. "
                "Global values are always checked.",
                DeprecationWarning,
                stacklevel=2,
            )

        # Get server by reference
        server = self.env["cx.tower.server"].get_by_reference(server_reference)
        if not server:
            _logger.warning(
                "server_get_variable_value: Server not found for reference '%s'",
                server_reference,
            )
            return None
        return (
            self.env["cx.tower.variable"]
            ._get_variable_values_by_references(
                variable_references=[variable_reference], server=server
            )
            .get(variable_reference)
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
        """
        Check if SSH connection to the server is available.
        This method uses the `test_ssh_connection` method
        of the 'cx.tower.server' model.
        It tries to connect to the server multiple times
        and is designed to be used in the Python commands or
        Odoo automated actions.

        Args:
            server_reference (Char): Server reference.
            attempts (int): Number of attempts to try the connection.
                Default is 5.
            wait_time (int): Wait time in seconds between connection attempts.
                Default is 10 seconds.
            try_command (bool): Try to execute a simple command for verification.
                Default is True. Set to False to skip command execution.
            try_file (bool): Try file operations for verification.
                Default is True. Set to False to skip file operations.
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
        Validates the provided secret value against the actual secret.

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

    @api.model
    def generate_random_id(self, sections=1, population=4, separator="-"):
        """
        Helper method that allows to generate a random id
        with customizable sections and population.
        Such ids are more human readable and less likely to collide.


        Args:
            sections (int): Number of sections to generate.
            population (int): Population of the sections.
            separator (str): Separator between sections.
        Returns:
            str: Random id
        """
        return tools.generate_random_id(
            sections=sections, population=population, separator=separator
        )

    @api.model
    def is_valid_url(self, url, no_scheme_check=False):
        """
        Check if the provided URL is a valid URL.
        The `urlparse` function from the `urllib.parse` module is used.

        Args:
            url (str): URL to check
            no_scheme_check (bool): If True, the scheme check will be skipped.
                Defaults to False.
        Returns:
            bool: True if the URL is valid, False otherwise
        """
        return tools.is_valid_url(url=url, no_scheme_check=no_scheme_check)
