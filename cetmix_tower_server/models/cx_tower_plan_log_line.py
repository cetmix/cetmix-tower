# Copyright (C) 2022 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import fields, models


class CxTowerPlanLogLine(models.Model):
    _name = "cx.tower.plan.log.line"
    _description = "Cetmix Tower Flight Plan Log Line"
    _order = "id asc"
    _log_access = False

    # Plan related fields
    active = fields.Boolean(related="plan_log_id.active", store=True, readonly=True)
    plan_line_id = fields.Many2one(comodel_name="cx.tower.plan.line")
    type = fields.Selection(
        selection=lambda self: self.env["cx.tower.plan.line"]._selection_type(),
        related="plan_line_id.type",
        store=True,
        readonly=True,
    )
    name = fields.Char(related="plan_line_id.name", store=True, readonly=True)
    command_id = fields.Many2one(
        comodel_name="cx.tower.command",
        related="plan_line_id.command_id",
        store=True,
        readonly=True,
    )

    # Log related fields
    plan_log_id = fields.Many2one(comodel_name="cx.tower.plan.log", auto_join=True)
    command_log_id = fields.Many2one(comodel_name="cx.tower.command.log")
