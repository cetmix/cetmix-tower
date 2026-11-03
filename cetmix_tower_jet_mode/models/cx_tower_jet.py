# Copyright Cetmix OU
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class CxTowerJet(models.Model):
    _inherit = "cx.tower.jet"

    active_mode_id = fields.Many2one(
        comodel_name="cx.tower.jet.mode",
        string="Active Mode",
        domain="[('jet_template_id', '=', jet_template_id)]",
    )
    active_mode_description = fields.Html(
        related="active_mode_id.description",
        string="Mode Description",
        readonly=True,
    )
    mode_required = fields.Boolean(
        default=False,
        help="If enabled, an active mode must always be selected on this jet.",
    )

    @api.constrains("active_mode_id", "jet_template_id")
    def _check_active_mode_id_template(self):
        for rec in self:
            if (
                rec.active_mode_id
                and rec.active_mode_id.jet_template_id != rec.jet_template_id
            ):
                raise ValidationError(
                    _("The selected Active Mode does not belong to the Jet's Template.")
                )

    @api.depends(
        "state_id",
        "jet_template_id",
        "jet_template_id.action_ids",
        "jet_template_id.action_ids.state_from_id",
        "jet_template_id.action_ids.state_to_id",
        "jet_template_id.action_ids.priority",
        "active_mode_id",
        "active_mode_id.action_ids",
    )
    def _compute_available_actions(self):
        res = super()._compute_available_actions()
        for rec in self:
            if rec.active_mode_id and rec.action_available_ids:
                action_ids = rec.active_mode_id.action_ids.ids
                rec.action_available_ids = rec.action_available_ids.filtered(
                    lambda a, aids=action_ids: a.id in aids
                )
        return res
