# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, models


class IrModuleModule(models.Model):
    _inherit = "ir.module.module"

    @api.model
    def _update_translations(self, filter_lang=None, overwrite=False):
        """Reload the root menu name after translation files are applied.

        Translation files for ``cetmix_tower_base.menu_root`` store the
        translation of Cetmix Tower. Loading a language writes that value
        back. The menu rename runs again once those files are loaded, so
        Drone stays in place while Cetmix Tower Server is not installed.

        Args:
            filter_lang (list | str | None): Languages to load.
            overwrite (bool): Replace existing translations when true.

        Returns:
            None: The parent method returns nothing.
        """
        result = super()._update_translations(
            filter_lang=filter_lang, overwrite=overwrite
        )
        self.env["ir.ui.menu"]._cetmix_drone_set_root_menu_name()
        return result
