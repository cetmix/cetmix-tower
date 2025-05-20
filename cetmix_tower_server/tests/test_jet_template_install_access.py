# Copyright (C) 2025 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.exceptions import AccessError

from .common_jets import TestTowerJetsCommon


class TestTowerJetTemplateInstallAccess(TestTowerJetsCommon):
    """
    Test access rules for Jet Template Install model
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create additional server for testing
        cls.server_test_2 = cls.Server.create(
            {
                "name": "Test Server 2",
                "reference": "test_server_2",
                "ip_v4_address": "192.168.1.102",
                "ssh_username": "admin",
                "ssh_password": "password",
                "ssh_auth_mode": "p",
                "os_id": cls.os_debian_10.id,
            }
        )

    def _create_install_record(
        self,
        template=None,
        server=None,
        template_access_level="2",
        template_user_ids=None,
        template_manager_ids=None,
        server_user_ids=None,
        server_manager_ids=None,
    ):
        """Helper method to create a jet template install record"""
        if not template:
            template = self.JetTemplate.create(
                {
                    "name": "Test Template",
                    "reference": "test_template",
                    "access_level": template_access_level,
                    "user_ids": template_user_ids
                    if template_user_ids is not None
                    else [(5, 0, 0)],
                    "manager_ids": template_manager_ids
                    if template_manager_ids is not None
                    else [(5, 0, 0)],
                }
            )

        if not server:
            server = self.server_test_1

        # Update server access if needed
        if server_user_ids is not None:
            server.write({"user_ids": server_user_ids})
        if server_manager_ids is not None:
            server.write({"manager_ids": server_manager_ids})

        # Create install record
        install_record = self.JetTemplateInstall.create(
            {
                "jet_template_id": template.id,
                "server_id": server.id,
            }
        )

        return template, server, install_record

    # ======================
    # Manager Read Access Tests
    # ======================

    def test_manager_read_server_user_ids_template_access_level_manager(self):
        """Test Manager: Read when in server user_ids and template access_level <= 2"""
        _, _, install_record = self._create_install_record(
            template_access_level="2",
            server_user_ids=[(4, self.manager.id)],
        )

        records = self.JetTemplateInstall.with_user(self.manager).search(
            [("id", "=", install_record.id)]
        )
        self.assertEqual(
            len(records),
            1,
            "Manager should read when in server user_ids"
            " and template access_level <= 2",
        )

    def test_manager_read_server_manager_ids_template_access_level_manager(self):
        """
        Test Manager: Read when in server manager_ids
        and template access_level <= 2.
        """
        _, _, install_record = self._create_install_record(
            template_access_level="2",
            server_manager_ids=[(4, self.manager.id)],
        )

        records = self.JetTemplateInstall.with_user(self.manager).search(
            [("id", "=", install_record.id)]
        )
        self.assertEqual(
            len(records),
            1,
            "Manager should read when in server manager_ids"
            " and template access_level <= 2",
        )

    def test_manager_read_template_user_ids_override(self):
        """
        Test Manager: Read when in template user_ids overrides access_level
        (server user_ids or manager_ids).
        """
        # Test with server user_ids
        _, _, install_record1 = self._create_install_record(
            template_access_level="3",  # Root level - normally not accessible
            template_user_ids=[(4, self.manager.id)],
            server_user_ids=[(4, self.manager.id)],
        )

        records = self.JetTemplateInstall.with_user(self.manager).search(
            [("id", "=", install_record1.id)]
        )
        self.assertEqual(
            len(records),
            1,
            "Manager should read when in template user_ids" " and server user_ids",
        )

        # Test with server manager_ids
        _, _, install_record2 = self._create_install_record(
            template_access_level="3",  # Root level - normally not accessible
            template_user_ids=[(4, self.manager.id)],
            server_manager_ids=[(4, self.manager.id)],
        )

        records = self.JetTemplateInstall.with_user(self.manager).search(
            [("id", "=", install_record2.id)]
        )
        self.assertEqual(
            len(records),
            1,
            "Manager should read when in template user_ids" " and server manager_ids",
        )

    def test_manager_read_no_access_no_server_access(self):
        """
        Test Manager: No read access when not in
        server user_ids or manager_ids.
        """
        _, _, install_record = self._create_install_record(
            template_access_level="1",
            server_user_ids=[(5, 0, 0)],
            server_manager_ids=[(5, 0, 0)],
        )

        records = self.JetTemplateInstall.with_user(self.manager).search(
            [("id", "=", install_record.id)]
        )
        self.assertEqual(
            len(records),
            0,
            "Manager should not read when not in server user_ids or manager_ids",
        )

    def test_manager_read_no_access_template_root_level(self):
        """
        Test Manager: No read access when template access_level
        is Root and not in template user_ids.
        """
        _, _, install_record = self._create_install_record(
            template_access_level="3",  # Root level
            template_user_ids=[(5, 0, 0)],
            server_user_ids=[(4, self.manager.id)],
        )

        records = self.JetTemplateInstall.with_user(self.manager).search(
            [("id", "=", install_record.id)]
        )
        self.assertEqual(
            len(records),
            0,
            "Manager should not read when template access_level"
            " is Root and not in template user_ids",
        )

    def test_manager_read_no_access_template_manager_level_no_server_access(self):
        """
        Test Manager: No read access when template access_level
        is Manager but not in server.
        """
        _, _, install_record = self._create_install_record(
            template_access_level="2",
            server_user_ids=[(5, 0, 0)],
            server_manager_ids=[(5, 0, 0)],
        )

        records = self.JetTemplateInstall.with_user(self.manager).search(
            [("id", "=", install_record.id)]
        )
        self.assertEqual(
            len(records),
            0,
            "Manager should not read when not in server"
            " even if template access_level is Manager",
        )

    def test_manager_write_forbidden(self):
        """Test Manager: Cannot write/create/delete records"""
        _, _, install_record = self._create_install_record(
            template_access_level="2",
            server_user_ids=[(4, self.manager.id)],
        )

        # Manager should not be able to write
        with self.assertRaises(AccessError):
            install_record.with_user(self.manager).write({"state": "done"})

        # Manager should not be able to create
        template = self.JetTemplate.create(
            {
                "name": "New Template",
                "reference": "new_template",
                "access_level": "2",
            }
        )
        server = self.server_test_1
        server.write({"user_ids": [(4, self.manager.id)]})

        with self.assertRaises(AccessError):
            self.JetTemplateInstall.with_user(self.manager).create(
                {
                    "jet_template_id": template.id,
                    "server_id": server.id,
                }
            )

        # Manager should not be able to delete
        with self.assertRaises(AccessError):
            install_record.with_user(self.manager).unlink()

    # ======================
    # Root Access Tests
    # ======================

    def test_root_write_access(self):
        """Test Root: Can write any record"""
        _, _, install_record = self._create_install_record()

        # Root should be able to write
        try:
            install_record.with_user(self.root).write({"state": "done"})
            install_record.invalidate_recordset()
            self.assertEqual(
                install_record.state, "done", "Root should be able to update"
            )
        except AccessError:
            self.fail("Root should be able to update any record")

    def test_root_create_access(self):
        """Test Root: Can create any record"""
        template = self.JetTemplate.with_user(self.root).create(
            {
                "name": "Root Template",
                "reference": "root_template",
                "access_level": "3",
            }
        )
        server = self.server_test_1

        # Root should be able to create
        try:
            install_record = self.JetTemplateInstall.with_user(self.root).create(
                {
                    "jet_template_id": template.id,
                    "server_id": server.id,
                }
            )
            records = self.JetTemplateInstall.with_user(self.root).search(
                [("id", "=", install_record.id)]
            )
            self.assertEqual(len(records), 1, "Root should be able to create")
        except AccessError:
            self.fail("Root should be able to create any record")

    def test_root_delete_access(self):
        """Test Root: Can delete any record"""
        _, _, install_record = self._create_install_record()

        # Root should be able to delete
        try:
            install_record.with_user(self.root).unlink()
            records = self.JetTemplateInstall.with_user(self.root).search(
                [("id", "=", install_record.id)]
            )
            self.assertEqual(len(records), 0, "Root should be able to delete")
        except AccessError:
            self.fail("Root should be able to delete any record")

    def test_root_access_all_scenarios(self):
        """Test Root can access records in all scenarios"""
        # Test various combinations
        scenarios = [
            {
                "template_access_level": "1",
                "server_user_ids": [(5, 0, 0)],
                "server_manager_ids": [(5, 0, 0)],
            },
            {
                "template_access_level": "2",
                "server_user_ids": [(5, 0, 0)],
                "server_manager_ids": [(5, 0, 0)],
            },
            {
                "template_access_level": "3",
                "server_user_ids": [(5, 0, 0)],
                "server_manager_ids": [(5, 0, 0)],
            },
        ]

        for scenario in scenarios:
            _, _, install_record = self._create_install_record(**scenario)
            records = self.JetTemplateInstall.with_user(self.root).search(
                [("id", "=", install_record.id)]
            )
            self.assertEqual(
                len(records),
                1,
                f"Root should be able to read record with scenario: {scenario}",
            )

    # ======================
    # Edge Cases
    # ======================

    def test_manager_read_multiple_servers(self):
        """Test Manager access across multiple servers"""
        # Manager in server 1, template accessible
        template1, _, install1 = self._create_install_record(
            template_access_level="2",
            server_user_ids=[(4, self.manager.id)],
        )

        # Manager not in server 2, same template
        _, _, install2 = self._create_install_record(
            template=template1,
            server=self.server_test_2,
            template_access_level="2",
            server_user_ids=[(5, 0, 0)],
            server_manager_ids=[(5, 0, 0)],
        )

        # Manager should only see install1
        records = self.JetTemplateInstall.with_user(self.manager).search(
            [("id", "in", [install1.id, install2.id])]
        )
        self.assertEqual(len(records), 1, "Manager should only see accessible install")
        self.assertEqual(records[0].id, install1.id, "Manager should see install1")

    def test_manager_read_multiple_templates(self):
        """Test Manager access with multiple templates"""
        # Template 1: Manager level, Manager in server
        _, _, install1 = self._create_install_record(
            template_access_level="2",
            server_user_ids=[(4, self.manager.id)],
        )

        # Template 2: Root level, Manager in server but template user_ids
        _, _, install2 = self._create_install_record(
            template_access_level="3",
            template_user_ids=[(4, self.manager.id)],
            server_user_ids=[(4, self.manager.id)],
        )

        # Manager should see both
        records = self.JetTemplateInstall.with_user(self.manager).search(
            [("id", "in", [install1.id, install2.id])]
        )
        self.assertEqual(len(records), 2, "Manager should see both installs")
