# Copyright (C) 2025 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).


from odoo import fields, models


class CxTowerYamlManifestAuthor(models.Model):
    """Author of a YAML manifest (can be one or many)."""

    _name = "cx.tower.yaml.manifest.author"

    _sql_constraints = [
        (
            "yaml_manifest_author_name_uniq",
            "unique(name)",
            "Author name must be unique.",
        )
    ]
    _description = "YAML Manifest Author"
    _order = "name"

    name = fields.Char(required=True, translate=False)
