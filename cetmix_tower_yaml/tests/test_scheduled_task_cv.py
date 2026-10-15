# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo.tests import TransactionCase


class TestScheduledTaskCv(TransactionCase):
    """Custom variable values on scheduled tasks."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.command = cls.env["cx.tower.command"].create(
            {"name": "Command for custom value", "action": "ssh_command"}
        )
        cls.scheduled_task = cls.env["cx.tower.scheduled.task"].create(
            {
                "name": "Task for custom value",
                "action": "command",
                "command_id": cls.command.id,
            }
        )
        cls.variable = cls.env["cx.tower.variable"].create(
            {"name": "Odoo Version", "variable_type": "o"}
        )
        cls.option = cls.env["cx.tower.variable.option"].create(
            {
                "name": "18.0",
                "value_char": "18.0",
                "variable_id": cls.variable.id,
            }
        )
        cls.ScheduledTaskCv = cls.env["cx.tower.scheduled.task.cv"]

    def test_create_without_name(self):
        """Adding a custom value from the form must not require Name."""
        custom_value = self.ScheduledTaskCv.create(
            {
                "scheduled_task_id": self.scheduled_task.id,
                "variable_id": self.variable.id,
                "option_id": self.option.id,
            }
        )
        self.assertFalse(
            custom_value.name,
            "A scheduled task custom value must not get a name",
        )
