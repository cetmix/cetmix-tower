# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
import secrets

from psycopg2 import errors

from odoo import api, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.cetmix_tower_server.models.constants import JET_ACTION_NOT_AVAILABLE


class CxTowerJet(models.Model):
    _inherit = "cx.tower.jet"

    backup_count = fields.Integer(
        compute="_compute_backup_count", groups="cetmix_tower_base.group_root"
    )
    active_backup_id = fields.Many2one(
        "cx.tower.backup",
        readonly=True,
        copy=False,
        ondelete="set null",
        groups="cetmix_tower_base.group_root",
        help="Backup operation reserving this Jet against new lifecycle actions.",
    )

    def _lock_backup_operation(self):
        """Serialize operation admission against a durable claim on this Jet.

        Returns:
            None: The row remains locked until the transaction ends.
        """
        self.ensure_one()
        self.flush_recordset(["target_state_id", "active_backup_id"])
        self.env.cr.execute(
            "SELECT id FROM cx_tower_jet WHERE id = %s FOR UPDATE NOWAIT",
            [self.id],
        )
        self.invalidate_recordset(
            ["target_state_id", "current_action_id", "active_backup_id"]
        )

    def _has_backup_operation(self):
        """Check running operations, including records created before claims existed.

        Returns:
            bool: A backup or deletion is still running on this Jet.
        """
        self.ensure_one()
        return bool(
            self.sudo().active_backup_id
            or self.env["cx.tower.backup"]
            .sudo()
            .search_count(
                [("jet_id", "=", self.id), ("state", "in", ["running", "deleting"])]
            )
        )

    def _is_busy(self):
        """Include backups without changing the Jet's lifecycle state.

        Returns:
            bool: A lifecycle action or backup operation reserves this Jet.
        """
        return super()._is_busy() or self._has_backup_operation()

    def _check_backup_action_admission(self):
        """Admit a new lifecycle operation before it writes its own claim.

        Returns:
            None: The Jet is locked and available for the operation.

        Raises:
            ValidationError: Another operation already owns the Jet.
        """
        self._lock_backup_operation()
        if self._is_busy():
            raise ValidationError(self.env._("The Jet is busy with another action."))

    def _trigger_action(
        self, action, from_transition=False, raise_if_not_available=True, **kwargs
    ):
        """Guard direct action requests while preserving admitted continuations.

        Args:
            action (cx.tower.jet.action): Requested action.
            from_transition (bool): Continue an already admitted state path.
            raise_if_not_available (bool): Raise instead of returning a busy status.
            **kwargs (dict): Arguments forwarded to the lifecycle implementation.

        Returns:
            dict: Parent action result or unavailable status.

        Raises:
            ValidationError: The Jet is busy and raising was requested.
        """
        if not from_transition:
            if raise_if_not_available:
                self._check_backup_action_admission()
            else:
                try:
                    with self.env.cr.savepoint():
                        self._check_backup_action_admission()
                except (
                    ValidationError,
                    errors.LockNotAvailable,
                    errors.SerializationFailure,
                ) as error:
                    message = (
                        str(error)
                        if isinstance(error, ValidationError)
                        else self.env._("The Jet is busy with another action.")
                    )
                    command_log = kwargs.get("current_command_log")
                    if command_log:
                        command_log.finish(
                            status=JET_ACTION_NOT_AVAILABLE, error=message
                        )
                    return {"status": JET_ACTION_NOT_AVAILABLE, "error": message}
        return super()._trigger_action(
            action,
            from_transition=from_transition,
            raise_if_not_available=raise_if_not_available,
            **kwargs,
        )

    def bring_to_state(self, *args, **kwargs):
        """Check external state requests even when a transition already exists.

        Args:
            *args (tuple): Positional arguments forwarded to the parent.
            **kwargs (dict): Keyword arguments forwarded to the parent.

        Returns:
            None: Parent lifecycle result.
        """
        self._check_backup_action_admission()
        return super().bring_to_state(*args, **kwargs)

    def _bring_to_state(self, *args, **kwargs):
        """Admit initial state paths, including Jet creation, before claiming them.

        Args:
            *args (tuple): Positional arguments forwarded to the parent.
            **kwargs (dict): Keyword arguments forwarded to the parent.

        Returns:
            None: Parent lifecycle result.
        """
        if not self.target_state_id:
            self._check_backup_action_admission()
        return super()._bring_to_state(*args, **kwargs)

    def _is_action_owned_backup(self, command_log):
        """Verify that a waiting backup command belongs to the current action.

        Args:
            command_log (cx.tower.command.log): Triggering Create Backup command.

        Returns:
            bool: The running root plan belongs to this Jet's current action.
        """
        self.ensure_one()
        action = self.sudo().current_action_id
        if not action or not command_log:
            return False
        log = command_log.sudo().plan_log_id
        while log.parent_flight_plan_log_id:
            log = log.parent_flight_plan_log_id
        return bool(
            log.is_running
            and log.jet_id == self
            and log.jet_action_id
            and log.jet_action_id == action
        )

    def _compute_backup_count(self):
        """Count each Jet's backups for its smart button in one grouped query.

        Returns:
            None: Assigns the count on each Jet.
        """
        counts = dict(
            self.env["cx.tower.backup"]._read_group(
                [("jet_id", "in", self.ids)], ["jet_id"], ["__count"]
            )
        )
        for jet in self:
            jet.backup_count = counts.get(jet, 0)

    def unlink(self):
        """Preserve operation logs until each backup has finished.

        Returns:
            bool: ORM unlink result.

        Raises:
            ValidationError: A source or destination Jet has an operation in progress.
        """
        if (
            self.env["cx.tower.backup"]
            .sudo()
            .search_count(
                [("jet_id", "in", self.ids), ("state", "in", ["running", "deleting"])]
            )
        ):
            raise ValidationError(
                self.env._(
                    "A Jet with a backup operation in progress cannot be deleted."
                )
            )
        if (
            self.env["cx.tower.plan.log"]
            .sudo()
            .with_context(active_test=False)
            .search_count(
                [
                    ("jet_id", "in", self.ids),
                    ("is_running", "=", True),
                    ("backup_operation", "=", "restore"),
                    ("backup_id", "!=", False),
                ]
            )
        ):
            raise ValidationError(
                self.env._("A Jet being restored from a backup cannot be deleted.")
            )
        return super().unlink()

    @api.private
    def create_backup(
        self,
        backup_template,
        name=None,
        variable_values=None,
        ignore_busy=False,
        waypoint=None,
        created_from_command_log=None,
        scheduled_task=None,
    ):
        """Capture Jet configuration and start its Backup plan.

        Args:
            backup_template (cx.tower.backup.template | str): Template or reference.
            name (str | None): Optional backup name.
            variable_values (dict | None): Custom values to preserve and replay.
            ignore_busy (bool): Allow a trigger already running on this Jet.
            waypoint (cx.tower.jet.waypoint | None): Owning waypoint.
            created_from_command_log (cx.tower.command.log | None): Waiting command.
            scheduled_task (cx.tower.scheduled.task | None): Triggering task.

        Returns:
            cx.tower.backup: Backup in the caller's environment; it may be running.

        Raises:
            ValidationError: Template, trigger ownership or busy checks fail.
        """
        self.ensure_one()
        templates = self.env["cx.tower.backup.template"]
        template = (
            templates.get_by_reference(backup_template)
            if isinstance(backup_template, str)
            else backup_template.with_env(self.env)
        )
        if not template:
            raise ValidationError(self.env._("Backup Template was not found."))
        if waypoint and waypoint.jet_id != self:
            raise ValidationError(
                self.env._("The waypoint does not belong to this Jet.")
            )
        if created_from_command_log and not (
            created_from_command_log.jet_id == self
            and created_from_command_log.is_running
            and created_from_command_log.command_id.action == "create_backup"
        ):
            raise ValidationError(
                self.env._(
                    "The triggering command is not a running Create Backup "
                    "command of this Jet."
                )
            )
        if template.jet_template_id != self.jet_template_id:
            raise ValidationError(
                self.env._("The Backup Template does not belong to this Jet Template.")
            )
        self._lock_backup_operation()
        owner_command = created_from_command_log or (
            waypoint and waypoint.sudo().created_from_command_log_id
        )
        action_owned = bool(
            ignore_busy
            and owner_command
            and owner_command.is_running
            and owner_command.jet_id == self
            and self._is_action_owned_backup(owner_command)
        )
        if self._has_backup_operation() or (super()._is_busy() and not action_owned):
            raise ValidationError(self.env._("The Jet is busy with another action."))
        vals = self._prepare_backup_values(
            template,
            name=name,
            variable_values=variable_values,
            created_from_command_log=created_from_command_log,
        )
        backup = self.env["cx.tower.backup"].sudo().create(vals)
        self.sudo().write({"active_backup_id": backup.id})
        if waypoint:
            waypoint.sudo().backup_id = backup
        log = self.server_id.sudo().run_flight_plan(
            flight_plan=template.plan_backup_id,
            jet=self,
            plan_log={
                **({"waypoint_id": waypoint.id} if waypoint else {}),
                **({"scheduled_task_id": scheduled_task.id} if scheduled_task else {}),
                "backup_id": backup.id,
                "backup_operation": "backup",
                "backup_token": backup.operation_token,
            },
            variable_values=backup._get_custom_variable_values(),
        )
        if created_from_command_log and created_from_command_log.is_running:
            created_from_command_log.sudo().triggered_plan_log_id = log
        return backup.with_env(self.env)

    def _prepare_backup_values(self, backup_template, **kwargs):
        """Build the snapshot extended by optional bridge modules.

        Args:
            backup_template (cx.tower.backup.template): Selected template.
            **kwargs (dict): Name, variable_values and created_from_command_log.

        Returns:
            dict: Values for a new backup record.
        """
        self.ensure_one()
        timestamp = fields.Datetime.context_timestamp(self, fields.Datetime.now())
        command_log = kwargs.get("created_from_command_log")
        return {
            "name": kwargs.get("name") or f"{self.name} {timestamp:%Y-%m-%d %H:%M:%S}",
            "backup_template_id": backup_template.id,
            "jet_id": self.id,
            "server_id": self.server_id.id,
            "environment_id": self.environment_id.id,
            "variable_values": {
                value.variable_reference: value.value_char or ""
                for value in self.variable_value_ids
            },
            "custom_variable_values": kwargs.get("variable_values") or {},
            "created_from_command_log_id": command_log.id if command_log else False,
            "state": "running",
            "operation_token": secrets.token_urlsafe(32),
        }

    def action_view_backups(self):
        """Open this Jet's backups.

        Returns:
            dict: Backup window action.
        """
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "cetmix_tower_backup.cx_tower_backup_action"
        )
        action["domain"] = [("jet_id", "=", self.id)]
        return action
