# Copyright (C) 2022 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import _, fields, models


class CxTowerAccessMixin(models.AbstractModel):
    """Used to implement template access levels in models."""

    _name = "cx.tower.access.mixin"
    _description = "Cetmix Tower access mixin"

    access_level = fields.Selection(
        lambda self: self._selection_access_level(),
        default=lambda self: self._default_access_level(),
        required=True,
        index=True,
    )

    def _selection_access_level(self):
        """Available access levels

        Returns:
            List of tuples: available options.
        """
        return [
            ("1", _("User")),
            ("2", _("Manager")),
            ("3", _("Root")),
        ]

    def _default_access_level(self):
        """Default access level

        Returns:
            Char: `access_level` field selection value
        """
        return "2"
