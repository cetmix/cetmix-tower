# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class ProjectTask(models.Model):
    """Show Jets linked to a Project task."""

    _inherit = "project.task"

    jet_ids = fields.Many2many(
        comodel_name="cx.tower.jet",
        relation="cx_tower_jet_project_task_rel",
        column1="task_id",
        column2="jet_id",
        string="Jets",
        copy=False,
    )

    jet_count = fields.Integer(
        compute="_compute_jet_count",
    )

    @api.depends("jet_ids", "jet_ids.active")
    def _compute_jet_count(self):
        """Count the linked Jets visible in the current environment.

        Record rules and archived filtering come from the ORM.

        Args:
            self (project.task): Tasks whose Jets are counted.

        Returns:
            None: The count is written on ``jet_count``.
        """
        for task in self:
            task.jet_count = len(task.jet_ids)

    def action_view_jets(self):
        """Open linked Jets.

        One Jet opens its form. Several open the standard Jets action
        (kanban, list, form).

        Args:
            self (project.task): Task whose Jets are opened. Single record.

        Returns:
            dict: Window action on ``cx.tower.jet``, or a close action when none.
        """
        self.ensure_one()
        jets = self.env["cx.tower.jet"].search([("task_ids", "in", self.ids)])
        if not jets:
            return {"type": "ir.actions.act_window_close"}

        action = self.env["ir.actions.actions"]._for_xml_id(
            "cetmix_tower_server.cx_tower_jet_action"
        )
        form_view = self.env.ref("cetmix_tower_server.cx_tower_jet_view_form").id
        if len(jets) == 1:
            action.update(
                {
                    "views": [(form_view, "form")],
                    "view_mode": "form",
                    "res_id": jets.id,
                    "name": self.env._("Jet"),
                }
            )
        else:
            action.update(
                {
                    "domain": [("id", "in", jets.ids)],
                    "name": self.env._("Jets"),
                }
            )
        action["context"] = {**self.env.context, "create": False}
        return action
