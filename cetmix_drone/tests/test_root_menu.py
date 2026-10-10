# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.tests import TransactionCase, tagged
from odoo.tools.convert import convert_file

from odoo.addons.cetmix_drone.models.ir_ui_menu import DRONE_ROOT_MENU_ICON

MENU_XML = "views/menuitems.xml"
TOWER_ROOT_MENU_ICON = "cetmix_tower_base,static/description/icon.png"


def _server_state(env):
    """Return the install state of ``cetmix_tower_server``.

    Args:
        env (Environment): Environment used to read ``ir.module.module``.

    Returns:
        str | bool: Module state, or ``False`` when the module row is absent.
    """
    return (
        env["ir.module.module"]
        .search([("name", "=", "cetmix_tower_server")], limit=1)
        .state
    )


class TestRootMenuName(TransactionCase):
    """Root menu is Drone while Cetmix Tower Server is not installed."""

    def test_root_menu_is_drone_without_server(self):
        """The root menu is Drone when server was never installed.

        These tests run after this module's data and before the module is
        marked installed. A combined install leaves server ``to install``
        here, so only a run that does not install server executes this.
        """
        if _server_state(self.env) != "uninstalled":
            self.skipTest("cetmix_tower_server is not uninstalled")
        menu = self.env.ref("cetmix_tower_base.menu_root")
        self.assertEqual(menu.name, "Drone")
        self.assertEqual(menu.web_icon, DRONE_ROOT_MENU_ICON)
        self.assertTrue(menu.web_icon_data)

    def test_root_menu_replaces_translated_tower_name(self):
        """Drone replaces a translation of Cetmix Tower in another language.

        The menu name is stored per language. The French value belongs to
        the Cetmix Tower Base xml id and would otherwise stay in place.
        """
        if _server_state(self.env) != "uninstalled":
            self.skipTest("cetmix_tower_server is not uninstalled")
        self.env["res.lang"]._activate_lang("fr_FR")
        menu = self.env.ref("cetmix_tower_base.menu_root")
        menu.update_field_translations(
            "name",
            {"en_US": "Cetmix Tower", "fr_FR": "Tour Cetmix"},
        )
        self.env["ir.ui.menu"]._cetmix_drone_set_root_menu_name()
        self.assertEqual(menu.with_context(lang="en_US").name, "Drone")
        self.assertEqual(menu.with_context(lang="fr_FR").name, "Drone")


@tagged("post_install", "-at_install")
class TestRootMenuNameAfterUpdate(TransactionCase):
    """A later update of this module must keep Cetmix Tower."""

    def test_root_menu_stays_cetmix_tower_when_server_installed(self):
        """Reloading menu data leaves the name Cetmix Tower.

        Server is already installed and this update does not load it.
        Reloading the menu file is the data write an update performs. An
        unconditional Drone name in that file would show up here.
        """
        if _server_state(self.env) != "installed":
            self.skipTest("cetmix_tower_server is not installed")
        convert_file(self.env, "cetmix_drone", MENU_XML, {}, mode="update")
        menu = self.env.ref("cetmix_tower_base.menu_root")
        self.assertEqual(menu.name, "Cetmix Tower")
        self.assertEqual(menu.web_icon, TOWER_ROOT_MENU_ICON)
