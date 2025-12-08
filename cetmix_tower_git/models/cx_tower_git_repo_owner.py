# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models
from odoo.tools import ormcache


class CxTowerGitRepoOwner(models.Model):
    """
    Git Repository Owner.
    Represents an organization or user that owns repositories.
    Examples: "cetmix", "OCA", etc.
    """

    _name = "cx.tower.git.repo.owner"
    _inherit = ["cx.tower.reference.mixin", "cx.tower.yaml.mixin"]
    _description = "Cetmix Tower Git Repository Owner"
    _order = "name"

    display_name = fields.Char(
        readonly=False, compute="_compute_display_name", store=True
    )

    name = fields.Char(
        help="Name of the repository owner (e.g., 'cetmix', 'OCA')",
    )
    reference = fields.Char(
        index=True,
        compute="_compute_display_name",
        required=False,
        store=True,
    )
    repo_ids = fields.One2many(
        comodel_name="cx.tower.git.repo",
        inverse_name="owner_id",
        string="Repositories",
        copy=False,
        help="Repositories owned by this organization/user",
    )
    secret_id = fields.Many2one(
        comodel_name="cx.tower.key",
        string="Secret",
        domain="[('key_type', '=', 's')]",
        help="Custom secret used for this repository owner",
    )

    @api.depends("name")
    def _compute_display_name(self):
        """Compute display name."""
        for owner in self:
            # By default, display name is the same as name
            name = owner.name
            owner.update(
                {
                    "display_name": name or False,
                    "reference": owner._generate_or_fix_reference(name)
                    if name
                    else False,
                }
            )

    @ormcache("self.env.uid", "self.env.su", "name", "create")
    def _get_owner_id_by_name(self, name, create=False):
        """Get owner id by name.

        Args:
            name (str): Owner name
            create (bool): Create owner if not found
        Returns:
            int: Owner ID or None if not found
        """
        owner = self.search([("name", "=ilike", name)], limit=1) if name else None
        if not owner and create and name:
            owner = self.create({"name": name})
        return owner.id if owner else None

    @api.model_create_multi
    def create(self, vals_list):
        """Clear cache on create."""
        res = super().create(vals_list)
        self.env.registry.clear_cache()
        return res

    def write(self, vals):
        """Clear cache on write."""
        res = super().write(vals)
        if "name" in vals:
            self.env.registry.clear_cache()
        return res

    def unlink(self):
        """Clear cache on unlink."""
        res = super().unlink()
        self.env.registry.clear_cache()
        return res

    # ------------------------------
    # YAML mixin methods
    # ------------------------------
    def _get_fields_for_yaml(self):
        res = super()._get_fields_for_yaml()
        res += [
            "display_name",
            "name",
            "secret_id",
        ]
        return res
