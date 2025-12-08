# Copyright (C) 2022 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import _, api, fields, models

from ..models.tools import generate_random_id


class CxTowerPlanRunWizard(models.TransientModel):
    """
    Wizard to run a flight plan on selected servers.
    """

    _name = "cx.tower.plan.run.wizard"
    _description = "Run Flight Plan in Wizard"

    server_ids = fields.Many2many(
        "cx.tower.server",
        string="Servers",
    )
    plan_id = fields.Many2one(
        string="Flight Plan",
        comodel_name="cx.tower.plan",
        required=True,
    )
    note = fields.Text(related="plan_id.note", readonly=True)
    plan_domain = fields.Binary(
        compute="_compute_plan_domain",
    )
    tag_ids = fields.Many2many(
        comodel_name="cx.tower.tag",
        string="Tags",
    )
    applicability = fields.Selection(
        selection=[
            ("this", "For selected server(s)"),
            ("shared", "Non server restricted"),
        ],
        default="shared",
        required=True,
        compute="_compute_show_servers",
        readonly=False,
        store=True,
        help="Selected server(s): only Flight Plans that are specific"
        " to the selected server(s)\n"
        "Non server restricted: all Flight Plans that are "
        "not specific to any server",
    )
    # Lines
    plan_line_ids = fields.One2many(
        string="Commands",
        comodel_name="cx.tower.plan.line",
        compute="_compute_plan_line_ids",
        compute_sudo=True,
        groups="cetmix_tower_server.group_manager",
    )
    show_servers = fields.Boolean(
        compute="_compute_show_servers",
        store=True,
    )
    custom_variable_value_ids = fields.One2many(
        "cx.tower.plan.run.wizard.variable.value",
        "wizard_id",
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if not self._is_privileged_user():
            res["applicability"] = "this"
        return res

    @api.depends("server_ids")
    def _compute_show_servers(self):
        for rec in self:
            rec.show_servers = bool(rec.server_ids and len(rec.server_ids) > 1)

    @api.depends("plan_id")
    def _compute_plan_line_ids(self):
        """Sel lines in wizard based on selected plan"""
        for rec in self:
            if rec.plan_id and rec.plan_id.line_ids:
                rec.plan_line_ids = rec.plan_id.line_ids
            else:
                rec.plan_line_ids = None

    @api.depends("applicability", "server_ids", "tag_ids")
    def _compute_plan_domain(self):
        """Compose domain based on condition"""
        for record in self:
            domain = []
            if record.applicability == "shared":
                domain = [("server_ids", "=", False)]
            elif record.applicability == "this":
                domain.append(("server_ids", "in", record.server_ids.ids))
            if record.tag_ids:
                domain.append(("tag_ids", "in", record.tag_ids.ids))
            record.plan_domain = domain

    @api.onchange("applicability")
    def _onchange_applicability(self):
        """Reset plan after change record type"""
        self.plan_id = False

    def run_flight_plan(self):
        """Run flight plan for selected servers"""

        if self.plan_id and self.server_ids:
            # Generate custom label. Will be used later to locate the command log
            plan_label = generate_random_id(4)
            # Add custom values for log
            variable_values = {
                value.variable_id.reference: value.value_char
                for value in self.custom_variable_value_ids
            }
            custom_values = {
                "plan_log": {"label": plan_label},
                "variable_values": variable_values,
            }
            for server in self.server_ids:
                server.run_flight_plan(self.plan_id, **custom_values)
            return {
                "type": "ir.actions.act_window",
                "name": _("Plan Log"),
                "res_model": "cx.tower.plan.log",
                "view_mode": "list,form",
                "target": "current",
                "context": {"search_default_label": plan_label},
            }

    def _is_privileged_user(self):
        """Return True if current user is in Manager or Root group."""
        return self.env.user.has_group(
            "cetmix_tower_server.group_manager"
        ) or self.env.user.has_group("cetmix_tower_server.group_root")


class CxTowerPlanRunWizardVariableValue(models.TransientModel):
    """
    Custom variable values for flight plan run wizard
    """

    _inherit = "cx.tower.custom.variable.value.mixin"
    _name = "cx.tower.plan.run.wizard.variable.value"
    _description = "Custom variable values for plan run wizard"

    wizard_id = fields.Many2one(
        "cx.tower.plan.run.wizard",
        string="Wizard",
    )
