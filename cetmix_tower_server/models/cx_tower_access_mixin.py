# Copyright (C) 2022 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import fields, models


class CxTowerAccessMixin(models.AbstractModel):
    """Used to implement template rendering functions.
    Inherit in your model in order code that contains variables.

    """

    _name = "cx.tower.access.mixin"
    _description = "Cetmix Tower access mixin"

    def _selection_access_level(self):
        """Available access levels

        Returns:
            List of tuples: available options.
        """
        return [
            ("1", "User"),
            ("2", "Manager"),
            ("3", "Root"),
        ]

    def _default_access_level(self):
        """Default access level

        Returns:
            Char: `access_level` field selection value
        """
        return "2"

    access_level = fields.Selection(
        lambda self: self._selection_access_level(),
        string="Access Level",
        default=lambda self: self._default_access_level(),
        groups="cetmix_tower_server.group_root,cetmix_tower_server.group_manager",
        required=True,
    )
