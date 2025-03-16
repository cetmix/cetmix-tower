# Copyright (C) 2022 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import _, api, fields, models


class TowerVariable(models.Model):
    _name = "cx.tower.variable"
    _description = "Cetmix Tower Variable"
    _inherit = ["cx.tower.reference.mixin", "cx.tower.access.mixin"]

    _order = "name"

    value_ids = fields.One2many(
        string="Values",
        comodel_name="cx.tower.variable.value",
        inverse_name="variable_id",
    )
    value_ids_count = fields.Integer(
        string="Value Count", compute="_compute_value_ids_count"
    )
    option_ids = fields.One2many(
        comodel_name="cx.tower.variable.option",
        inverse_name="variable_id",
        string="Options",
        auto_join=True,
    )
    variable_type = fields.Selection(
        selection=[("s", "String"), ("o", "Options")],
        default="s",
        required=True,
        string="Type",
    )
    note = fields.Text()

    # --- Link to records where the variable is used
    command_ids = fields.Many2many(
        comodel_name="cx.tower.command",
        relation="cx_tower_command_variable_rel",
        column1="variable_id",
        column2="command_id",
    )
    command_ids_count = fields.Integer(
        string="Command Count", compute="_compute_command_ids_count"
    )
    plan_line_ids = fields.Many2many(
        comodel_name="cx.tower.plan.line",
        relation="cx_tower_plan_line_variable_rel",
        column1="variable_id",
        column2="plan_line_id",
    )
    plan_line_ids_count = fields.Integer(
        string="Plan Line Count", compute="_compute_plan_line_ids_count"
    )
    file_ids = fields.Many2many(
        comodel_name="cx.tower.file",
        relation="cx_tower_file_variable_rel",
        column1="variable_id",
        column2="file_id",
    )
    file_ids_count = fields.Integer(
        string="File Count", compute="_compute_file_ids_count"
    )
    file_template_ids = fields.Many2many(
        comodel_name="cx.tower.file.template",
        relation="cx_tower_file_template_variable_rel",
        column1="variable_id",
        column2="file_template_id",
    )
    file_template_ids_count = fields.Integer(
        string="File Template Count", compute="_compute_file_template_ids_count"
    )
    variable_value_ids = fields.Many2many(
        comodel_name="cx.tower.variable.value",
        relation="cx_tower_variable_value_variable_rel",
        column1="variable_id",
        column2="variable_value_id",
    )
    variable_value_ids_count = fields.Integer(
        string="Variable Value Count", compute="_compute_variable_value_ids_count"
    )

    _sql_constraints = [("name_uniq", "unique (name)", "Variable names must be unique")]

    @api.depends("command_ids")
    def _compute_command_ids_count(self):
        """Count number of commands for the variable"""
        for rec in self:
            rec.command_ids_count = len(rec.command_ids)

    @api.depends("plan_line_ids")
    def _compute_plan_line_ids_count(self):
        """Count number of plan lines for the variable"""
        for rec in self:
            rec.plan_line_ids_count = len(rec.plan_line_ids)

    @api.depends("file_ids")
    def _compute_file_ids_count(self):
        """Count number of files for the variable"""
        for rec in self:
            rec.file_ids_count = len(rec.file_ids)

    @api.depends("file_template_ids")
    def _compute_file_template_ids_count(self):
        """Count number of file templates for the variable"""
        for rec in self:
            rec.file_template_ids_count = len(rec.file_template_ids)

    @api.depends("variable_value_ids")
    def _compute_variable_value_ids_count(self):
        """Count number of variable values for the variable"""
        for rec in self:
            rec.variable_value_ids_count = len(rec.variable_value_ids)

    @api.depends("value_ids", "value_ids.variable_id")
    def _compute_value_ids_count(self):
        """Count number of values for the variable"""
        for rec in self:
            rec.value_ids_count = len(rec.value_ids)

    def action_open_values(self):
        self.ensure_one()
        context = self.env.context.copy()
        context.update(
            {
                "default_variable_id": self.id,
            }
        )

        return {
            "type": "ir.actions.act_window",
            "name": _("Variable Values"),
            "res_model": "cx.tower.variable.value",
            "views": [[False, "tree"]],
            "target": "current",
            "context": context,
            "domain": [("variable_id", "=", self.id)],
        }

    def action_open_commands(self):
        """Open the commands where the variable is used"""

        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "cetmix_tower_server.action_cx_tower_command"
        )
        action.update(
            {
                "domain": [("variable_ids", "in", self.ids)],
            }
        )
        return action

    def action_open_plan_lines(self):
        """Open the plan lines where the variable is used"""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Plan Lines"),
            "res_model": "cx.tower.plan.line",
            "views": [
                [False, "tree"],
                [
                    self.env.ref("cetmix_tower_server.cx_tower_plan_line_view_form").id,
                    "form",
                ],
            ],
            "target": "current",
            "domain": [("variable_ids", "in", self.ids)],
        }

    def action_open_files(self):
        """Open the files where the variable is used"""
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "cetmix_tower_server.cx_tower_file_action"
        )
        action.update(
            {
                "domain": [("variable_ids", "in", self.ids)],
            }
        )
        return action

    def action_open_file_templates(self):
        """Open the file templates where the variable is used"""
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "cetmix_tower_server.cx_tower_file_template_action"
        )
        action.update(
            {
                "domain": [("variable_ids", "in", self.ids)],
            }
        )
        return action

    def action_open_variable_values(self):
        """Open the variable values where the variable is used"""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Variable Values"),
            "res_model": "cx.tower.variable.value",
            "views": [[False, "tree"]],
            "target": "current",
            "domain": [("variable_ids", "in", self.ids)],
        }
