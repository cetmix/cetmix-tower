# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.tests import TransactionCase

from odoo.addons.cetmix_tower_server.models.ir_ui_menu import TOWER_ROOT_MENU_ICON


class TestRootMenuName(TransactionCase):
    """Root menu is Cetmix Tower after this module's data has loaded."""

    def test_root_menu_is_cetmix_tower(self):
        """Server data names the root menu Cetmix Tower.

        When ``cetmix_drone`` is installed in the same run it loads first
        and may have set Drone. This module's data has already run.
        """
        menu = self.env.ref("cetmix_tower_base.menu_root")
        self.assertEqual(menu.name, "Cetmix Tower")
        self.assertEqual(menu.web_icon, TOWER_ROOT_MENU_ICON)
        self.assertTrue(menu.web_icon_data)

    def test_root_menu_drops_translated_drone_name(self):
        """Cetmix Tower replaces Drone in another language.

        A translation of Cetmix Tower is kept. Only a value that is Drone
        is removed, so that language falls back to Cetmix Tower.
        """
        self.env["res.lang"]._activate_lang("fr_FR")
        menu = self.env.ref("cetmix_tower_base.menu_root")
        menu.update_field_translations(
            "name",
            {"en_US": "Drone", "fr_FR": "Drone"},
        )
        self.env["ir.ui.menu"]._cetmix_tower_server_set_root_menu_name()
        self.assertEqual(menu.with_context(lang="en_US").name, "Cetmix Tower")
        self.assertEqual(menu.with_context(lang="fr_FR").name, "Cetmix Tower")
        menu.update_field_translations("name", {"fr_FR": "Tour Cetmix"})
        self.env["ir.ui.menu"]._cetmix_tower_server_set_root_menu_name()
        self.assertEqual(menu.with_context(lang="fr_FR").name, "Tour Cetmix")
        menu.web_icon = "cetmix_drone,static/description/icon.png"
        self.env["ir.ui.menu"]._cetmix_tower_server_set_root_menu_name()
        self.assertEqual(menu.web_icon, TOWER_ROOT_MENU_ICON)
        self.assertEqual(menu.with_context(lang="fr_FR").name, "Tour Cetmix")
