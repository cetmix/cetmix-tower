# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models


class CxTowerJet(models.Model):
    """Link Jets to Odoo Project tasks."""

    _inherit = "cx.tower.jet"

    task_ids = fields.Many2many(
        comodel_name="project.task",
        relation="cx_tower_jet_project_task_rel",
        column1="jet_id",
        column2="task_id",
        string="Tasks",
        copy=False,
        help="Project tasks this Jet is associated with.",
    )

    task_count = fields.Integer(
        compute="_compute_task_count",
        context={},
    )

    @api.depends("task_ids", "task_ids.active")
    @api.depends_context("uid", "active_test")
    def _compute_task_count(self):
        """Count Project tasks the current user can read.

        Args:
            self (cx.tower.jet): Jets whose tasks are counted.

        Returns:
            None: The count is written on ``task_count``.
        """
        wanted = set(self.ids)
        counts = {}
        tasks = self.env["project.task"].search([("jet_ids", "in", list(wanted))])
        for task in tasks:
            linked_jets = task.with_context(active_test=False).jet_ids
            for jet_id in set(linked_jets.ids) & wanted:
                counts[jet_id] = counts.get(jet_id, 0) + 1
        for jet in self:
            jet.task_count = counts.get(jet.id, 0)

    def action_view_tasks(self):
        """Open linked tasks: one task opens its form, several open a list.

        Args:
            self (cx.tower.jet): Jet whose tasks are opened. Single record.

        Returns:
            dict: Window action on ``project.task``, or a close action when none.
        """
        self.ensure_one()
        tasks = self.env["project.task"].search([("jet_ids", "in", self.ids)])
        if not tasks:
            return {"type": "ir.actions.act_window_close"}

        action = self.env["ir.actions.actions"]._for_xml_id(
            "project.action_view_all_task"
        )
        form_view = self.env.ref("project.view_task_form2").id
        if len(tasks) == 1:
            action.update(
                {
                    "views": [(form_view, "form")],
                    "view_mode": "form",
                    "res_id": tasks.id,
                    "domain": False,
                    "name": _("Task"),
                }
            )
        else:
            list_view = self.env.ref("project.view_task_tree2").id
            action.update(
                {
                    "views": [(list_view, "list"), (form_view, "form")],
                    "view_mode": "list,form",
                    "res_id": False,
                    "domain": [("id", "in", tasks.ids)],
                    "name": _("Tasks"),
                }
            )
        action["context"] = {**self.env.context, "create": False}
        return action
