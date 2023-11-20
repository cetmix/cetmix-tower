# Copyright (C) 2022 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import _, api, fields, models

from ..models.tools import generate_random_id


class CxTowerPlanExecuteWizard(models.TransientModel):
    _name = "cx.tower.plan.execute.wizard"
    _description = "Execute Flightplan in Wizard"

    server_ids = fields.Many2many(
        "cx.tower.server",
        string="Servers",
    )
    plan_id = fields.Many2one(
        "cx.tower.plan",
        required=True,
    )
    tag_ids = fields.Many2many(
        comodel_name="cx.tower.tag",
        relation="cx_tower_plan_execute_tag_rel",
        column1="wizard_id",
        column2="tag_id",
        string="Tags",
    )
    any_server = fields.Boolean()
    # Lines
    plan_line_ids = fields.One2many(
        string="Commands",
        comodel_name="cx.tower.plan.line",
        compute="_compute_plan_line_ids",
    )

    @api.depends("plan_id")
    def _compute_plan_line_ids(self):
        """Sel lines in wizard based on selected plan"""
        for rec in self:
            if rec.plan_id and rec.plan_id.line_ids:
                rec.plan_line_ids = rec.plan_id.line_ids
            else:
                rec.plan_line_ids = None

    @api.onchange("any_server", "server_ids", "tag_ids")
    def _onchange_tag_ids(self):
        """Compose domain based on condition
        - any server: show commands compatible with any server
        """

        domain = []
        if self.any_server:
            domain = [("server_ids", "=", False)]
        elif self.server_ids:
            domain.append(("server_ids", "in", self.server_ids.ids))
        if self.tag_ids:
            domain.append(("tag_ids", "in", self.tag_ids.ids))

        return {"domain": {"plan_id": domain}}

    def execute(self):
        """Render selected command rendered using server method"""

        if self.plan_id and self.server_ids:
            # Generate custom label. Will be used later to locate the command log
            plan_label = generate_random_id(4)
            # Add custom values for log
            custom_values = {"plan_log": {"label": plan_label}}
            self.plan_id.execute(self.server_ids, **custom_values)
            return {
                "type": "ir.actions.act_window",
                "name": _("Plan Log"),
                "res_model": "cx.tower.plan.log",
                "view_mode": "tree,form",
                "target": "current",
                "context": {"search_default_label": plan_label},
            }
