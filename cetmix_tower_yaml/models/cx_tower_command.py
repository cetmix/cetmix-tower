# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import fields, models


class CxTowerCommand(models.Model):
    _name = "cx.tower.command"
    _inherit = ["cx.tower.command", "cx.tower.yaml.mixin"]

    access_level = fields.Selection(yaml_export=True)
    name = fields.Char(yaml_export=True)
    action = fields.Selection(yaml_export=True)
    allow_parallel_run = fields.Boolean(yaml_export=True)
    note = fields.Text(yaml_export=True)
    os_ids = fields.Many2many(yaml_export="include")
    tag_ids = fields.Many2many(yaml_export="include")
    path = fields.Char(yaml_export=True)
    file_template_id = fields.Many2one(yaml_export="include")
    if_file_exists = fields.Selection(yaml_export=True)
    disconnect_file = fields.Boolean(yaml_export=True)
    flight_plan_id = fields.Many2one(yaml_export="include")
    jet_template_id = fields.Many2one(yaml_export="reference")
    jet_action_id = fields.Many2one(yaml_export="reference")
    waypoint_template_id = fields.Many2one(yaml_export="reference")
    fly_here = fields.Boolean(yaml_export=True)
    code = fields.Text(yaml_export=True)
    no_split_for_sudo = fields.Boolean(yaml_export=True)
    server_status = fields.Selection(yaml_export=True)
    variable_ids = fields.Many2many(yaml_export="include")
    secret_ids = fields.Many2many(yaml_export="include")
