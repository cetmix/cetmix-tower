# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class CxTowerCommand(models.Model):
    _inherit = "cx.tower.command"

    backup_template_id = fields.Many2one(
        "cx.tower.backup.template",
        groups="cetmix_tower_base.group_root",
        yaml_export="reference",
    )

    def _selection_action(self):
        """Return command actions including Create Backup.

        Returns:
            list[tuple]: Available action values and labels.
        """
        return super()._selection_action() + [("create_backup", "Create Backup")]

    @api.constrains("access_level", "action", "flight_plan_id")
    def _check_backup_commands(self):
        """Protect historical backup logs and affected execution trees.

        Returns:
            None: Command access levels preserve backup log protection.

        Raises:
            ValidationError: A command with backup logs is below Root level,
                or an affected backup plan tree contains non-Root records.
        """
        commands = self.sudo()
        lower = commands.filtered(lambda command: command.access_level != "3")
        if lower and self.env["cx.tower.command.log"].sudo().with_context(
            active_test=False
        ).search_count(
            [("command_id", "in", lower.ids), ("has_backup_values", "=", True)]
        ):
            raise ValidationError(
                self.env._("A command with backup logs must keep Root access level.")
            )
        self.env["cx.tower.plan"]._validate_backup_plan_trees(changed_commands=commands)

    def _get_python_command_odoo_objects(self, *args, **kwargs):
        """Expose the current backup and a model shortcut to Tower Python.

        Args:
            *args (tuple): Core context objects.
            **kwargs (dict): Core objects and optional backup record.

        Returns:
            dict: Python context objects and help descriptions.
        """
        objects = super()._get_python_command_odoo_objects(*args, **kwargs)
        objects.update(
            {
                "backup": {
                    "import": kwargs.get("backup") or self.env["cx.tower.backup"],
                    "help": self.env._(
                        "Current Cetmix Tower backup this command is running for"
                    ),
                },
                "tower_backups": {
                    "import": self.env["cx.tower.backup"],
                    "help": self.env._(
                        "A helper shortcut to the Cetmix Tower backups model"
                    ),
                },
            }
        )
        return objects
