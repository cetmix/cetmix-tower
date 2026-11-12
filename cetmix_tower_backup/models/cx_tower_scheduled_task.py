# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
import logging

from odoo import api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class CxTowerScheduledTask(models.Model):
    _inherit = "cx.tower.scheduled.task"

    action = fields.Selection(
        selection_add=[("backup", "Backup")], ondelete={"backup": "cascade"}
    )
    backup_template_id = fields.Many2one(
        "cx.tower.backup.template",
        groups="cetmix_tower_base.group_root",
        yaml_export="reference",
    )

    @api.constrains("action", "backup_template_id", "jet_ids", "server_ids")
    def _check_backup_targets(self):
        """Restrict Backup tasks to Jets of the configured Jet Template.

        Returns:
            None: The task targets are valid, including deferred template links.

        Raises:
            ValidationError: A Backup task targets a server or a Jet belonging
                to a different Jet Template.
        """
        for task in self.sudo():
            if task.action != "backup":
                continue
            if task.server_ids:
                raise ValidationError(self.env._("Backup tasks can target Jets only."))
            if task.backup_template_id and any(
                jet.jet_template_id != task.backup_template_id.jet_template_id
                for jet in task.jet_ids
            ):
                raise ValidationError(
                    self.env._(
                        "Every target Jet must belong to the Backup Template's "
                        "Jet Template."
                    )
                )

    def _run_action(self):
        """Capture each Jet in an independent savepoint.

        Returns:
            list[str]: Individual Jet failures for the task notification.
        """
        self.ensure_one()
        if self.action != "backup":
            return super()._run_action()
        task = self.sudo()
        if not task.backup_template_id:
            return []
        variable_values = {
            value.variable_id.reference: value.value_char
            for value in task.custom_variable_value_ids
        }
        errors = []
        for jet in task.jet_ids:
            try:
                with self.env.cr.savepoint():
                    jet.create_backup(
                        task.backup_template_id,
                        variable_values=variable_values,
                        scheduled_task=task,
                    )
            except Exception as error:
                _logger.exception("Backup task %s failed for Jet %s", task.id, jet.id)
                errors.append(
                    self.env._(
                        "Unable to back up Jet '%(jet)s': %(error)s",
                        jet=jet.display_name,
                        error=error,
                    )
                )
        return errors
