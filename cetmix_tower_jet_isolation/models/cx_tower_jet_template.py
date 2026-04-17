from odoo import models, fields

class CxTowerJetTemplate(models.Model):
    _inherit = 'cx.tower.jet.template'
    
    isolation_mode = fields.Boolean(
        "Isolation Mode",
        help="When active, prevents users from changing applicability or tags when running commands/plans."
    )
    forced_applicability = fields.Selection([
        ('this', "For selected server(s)"),
        ('shared', "Non server restricted")
    ], "Forced Applicability")
    
    forced_command_tag_ids = fields.Many2many(
        comodel_name='cx.tower.tag',
        relation='cx_tower_template_forced_command_tag_rel',
        string="Forced Command Tags",
    )
    
    forced_plan_tag_ids = fields.Many2many(
        comodel_name='cx.tower.tag',
        relation='cx_tower_template_forced_plan_tag_rel',
        string="Forced Flight Plan Tags",
    )
