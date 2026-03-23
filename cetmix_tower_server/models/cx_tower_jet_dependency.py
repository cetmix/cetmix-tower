# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class CxTowerJetDependency(models.Model):
    """Model to manage dependent Jets"""

    _name = "cx.tower.jet.dependency"
    _description = "Cetmix Tower Jet Dependency"
    _log_access = False

    jet_template_dependency_id = fields.Many2one(
        comodel_name="cx.tower.jet.template.dependency",
        string="Jet Template Dependency",
        index=True,
        help="Related jet template dependency. "
        "Used to track dependency changes at the template level.",
        ondelete="cascade",
    )
    jet_id = fields.Many2one(
        comodel_name="cx.tower.jet",
        string="Jet",
        required=True,
        index=True,
        help="Jet this dependency belongs to",
        ondelete="cascade",
    )
    jet_depends_on_id = fields.Many2one(
        comodel_name="cx.tower.jet",
        string="Depends On",
        index=True,
        help="Jet this Jet depends on.",
        ondelete="cascade",
    )

    _sql_constraints = [
        (
            "unique_jet_dependency",
            "UNIQUE(jet_id, jet_depends_on_id)",
            "This dependency already exists!",
        )
    ]

    @api.constrains("jet_id", "jet_depends_on_id", "jet_template_dependency_id")
    def _check_self_dependency(self):
        for record in self:
            # Ensure jet dependency is not a self-dependency
            if record.jet_id == record.jet_depends_on_id:
                raise ValidationError(_("A jet cannot depend on itself!"))
            # Ensure jet that we depend on has the template
            # from the template dependency
            if (
                record.jet_depends_on_id
                and record.jet_template_dependency_id
                and record.jet_depends_on_id.jet_template_id
                != record.jet_template_dependency_id.template_required_id
            ):
                raise ValidationError(
                    _("A jet cannot depend on a jet with a different template!")
                )
