# Copyright (C) 2022 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import _, api, fields, models

from ..models.tools import generate_random_id


class CxTowerPlanExecuteWizard(models.TransientModel):
    _name = "cx.tower.plan.execute.wizard"
    _description = "Execute Flight Plan in Wizard"

    server_ids = fields.Many2many(
        "cx.tower.server",
        string="Servers",
    )
    plan_id = fields.Many2one(
        "cx.tower.plan",
        required=True,
    )
    plan_domain = fields.Binary(
        compute="_compute_plan_domain",
    )
    tag_ids = fields.Many2many(
        comodel_name="cx.tower.tag",
        relation="cx_tower_plan_execute_tag_rel",
        column1="wizard_id",
        column2="tag_id",
        string="Tags",
    )
    any_server = fields.Boolean(default=lambda self: self._default_any_server())
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

    @api.depends("any_server", "server_ids", "tag_ids")
    def _compute_plan_domain(self):
        """Compose domain based on condition
        - any server: show commands compatible with any server
        """
        for record in self:
            domain = []
            if record.any_server:
                domain = [("server_ids", "=", False)]
            elif record.server_ids:
                domain.append(("server_ids", "in", record.server_ids.ids))
            if record.tag_ids:
                domain.append(("tag_ids", "in", record.tag_ids.ids))
            record.plan_domain = domain

    def _default_any_server(self):
        any_server = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("cetmix_tower_server.any_server")
        )
        return any_server in ("1", "True", "true")

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
