# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
import secrets

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class CxTowerJet(models.Model):
    _inherit = "cx.tower.jet"

    backup_count = fields.Integer(
        compute="_compute_backup_count", groups="cetmix_tower_base.group_root"
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
        if not ignore_busy and self._is_busy():
            raise ValidationError(self.env._("The Jet is busy with another action."))
        vals = self._prepare_backup_values(
            template,
            name=name,
            variable_values=variable_values,
            created_from_command_log=created_from_command_log,
        )
        backup = self.env["cx.tower.backup"].sudo().create(vals)
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
