# Copyright Cetmix OU
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import _, fields, models
from odoo.exceptions import UserError


class CxTowerJetTemplate(models.Model):
    _inherit = "cx.tower.jet.template"

    mode_ids = fields.One2many(
        comodel_name="cx.tower.jet.mode",
        inverse_name="jet_template_id",
        string="Modes",
        copy=True,
    )
    active_mode_id = fields.Many2one(
        comodel_name="cx.tower.jet.mode",
        string="Active Mode",
        domain="[('jet_template_id', '=', id)]",
    )
    active_mode_description = fields.Html(
        related="active_mode_id.description",
        string="Mode Description",
        readonly=True,
    )
    mode_required = fields.Boolean(
        default=False,
        help=(
            "If enabled, an active mode must always be selected "
            "on this template and all its jets. "
            "The mode with the lowest sequence is auto-assigned when enabling."
        ),
    )

    def write(self, vals):
        # When enabling mode_required, auto-assign the lowest-sequence mode
        # to the template itself and to all jets that have no mode yet.
        if vals.get("mode_required"):
            for template in self:
                default_mode = template.mode_ids.sorted("sequence")[:1]
                if default_mode:
                    # Auto-assign to template if it has no mode
                    if not template.active_mode_id and "active_mode_id" not in vals:
                        template_vals = dict(vals, active_mode_id=default_mode.id)
                        super(CxTowerJetTemplate, template).write(template_vals)
                        # Propagate mode_required + mode to jets
                        jets = template.jet_ids
                        if jets:
                            jets.write({"mode_required": True})
                            jets.filtered(lambda j: not j.active_mode_id).write(
                                {"active_mode_id": default_mode.id}
                            )
                        continue
                if (
                    not default_mode
                    and not template.active_mode_id
                    and "active_mode_id" not in vals
                ):
                    raise UserError(
                        _(
                            "Cannot enable 'Mode Required' without a mode assigned. "
                            "Please create at least one Mode first."
                        )
                    )
                # Template already has a mode or we have a default mode to assign
                super(CxTowerJetTemplate, template).write(vals)
                jets = template.jet_ids
                if jets:
                    jets.write({"mode_required": True})
                    if default_mode:
                        jets.filtered(lambda j: not j.active_mode_id).write(
                            {"active_mode_id": default_mode.id}
                        )
            return True

        res = super().write(vals)

        # Propagate mode_required=False to all jets
        if "mode_required" in vals and not vals["mode_required"]:
            self.mapped("jet_ids").write({"mode_required": False})

        return res
