# Copyright (C) 2025 Cetmix OÜ
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class CxTowerYamlManifestTemplate(models.Model):
    """Pre-defined YAML manifest template storing common metadata
    such as authors, website, license, and currency for reuse
    during YAML exports."""

    _name = "cx.tower.yaml.manifest.tmpl"
    _description = "YAML Manifest Template"
    _order = "name"

    name = fields.Char(
        required=True,
        help="Name of the manifest template.",
    )
    website = fields.Char(help="Website URL for the manifest.")

    author_ids = fields.Many2many(
        "cx.tower.yaml.manifest.author",
        string="Authors",
        help="List of author names to include in the YAML manifest.",
    )

    license = fields.Selection(
        selection=lambda self: self._selection_license(),
        help="License used for the code snippet.",
    )
    license_text = fields.Text(
        help="Custom license text when license type is Custom.",
    )

    currency = fields.Selection(
        selection=lambda self: self._selection_currency(),
        help="Currency for pricing information.",
    )

    version = fields.Char(
        help="Version in Major.Minor.Patch format, e.g. 1.0.0",
        default="1.0.0",
    )

    file_prefix = fields.Char(
        string="File prefix",
        help="Add prefix to the exported YAML file name when this template is selected",
    )

    @api.model
    def _selection_license(self):
        """Return available license options for manifest."""
        return [
            ("agpl-3", "AGPL-3"),
            ("lgpl-3", "LGPL-3"),
            ("mit", "MIT"),
            ("custom", _("Custom")),
        ]

    @api.model
    def _selection_currency(self):
        """Return available currency options for manifest pricing."""
        return [
            ("EUR", _("Euro")),
            ("USD", _("US Dollar")),
        ]

    @api.constrains("license", "license_text")
    def _check_license_text_for_custom(self):
        """Ensure that custom license text is provided when license is 'custom'."""
        for rec in self:
            if rec.license == "custom" and not (rec.license_text or "").strip():
                raise ValidationError(
                    _("Provide Custom License Text when License is set to 'Custom'.")
                )

    @api.constrains("version")
    def _check_version_format(self):
        """Ensure the template version follows the x.y.z semantic format.

        The version must consist of three non-negative integers (major, minor, patch)
        separated by dots—for example, “1.2.3”. Raises a ValidationError otherwise.
        """
        semver = re.compile(r"^\d+\.\d+\.\d+$")
        for rec in self:
            if rec.version and not semver.match(rec.version):
                raise ValidationError(
                    _("Version must be in the Major.Minor.Patch format, e.g. 1.2.3")
                )
