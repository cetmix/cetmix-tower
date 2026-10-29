# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, models
from odoo.tools.translate import get_translation

TOWER_ROOT_MENU_ICON = "cetmix_tower_base,static/description/icon.png"


class IrUiMenu(models.Model):
    _inherit = "ir.ui.menu"

    @api.model
    def _cetmix_tower_server_set_root_menu_name(self):
        """Name the root menu Cetmix Tower in every language.

        ``cetmix_drone`` may have stored Drone for languages other than
        English. A record write updates only the current language, so
        those values would stay. Languages that currently hold Drone, or
        its translation, are removed and fall back to Cetmix Tower.
        Translations of Cetmix Tower itself are left as they are.
        The root menu icon is restored to the Cetmix Tower icon.

        Returns:
            None
        """
        menu = self.env.ref("cetmix_tower_base.menu_root")
        drone_names = self._cetmix_tower_server_drone_menu_names()
        stored = menu._fields["name"]._get_stored_translations(menu) or {}
        installed = {code for code, _label in self.env["res.lang"].get_installed()}
        installed.add("en_US")
        translations = {}
        if stored.get("en_US") != "Cetmix Tower":
            translations["en_US"] = "Cetmix Tower"
        for lang, value in stored.items():
            if lang.startswith("_") or lang == "en_US" or lang not in installed:
                continue
            if value in drone_names:
                translations[lang] = False
        if translations:
            menu.update_field_translations("name", translations)
        menu.web_icon = TOWER_ROOT_MENU_ICON

    @api.model
    def _cetmix_tower_server_drone_menu_names(self):
        """Return Drone and its translations in the installed languages.

        The translations live in ``cetmix_drone``. English is included
        because an untranslated language keeps the source.

        Returns:
            set: Menu names that mean Drone.
        """
        names = {"Drone"}
        for code, _label in self.env["res.lang"].get_installed():
            if code == "en_US":
                continue
            names.add(get_translation("cetmix_drone", code, "Drone", ()))
        return names
