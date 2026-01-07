# Copyright (C) 2025 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.exceptions import AccessError

from .common_jets import TestTowerJetsCommon


class TestTowerJetTemplateInstallLineAccess(TestTowerJetsCommon):
    """
    Test access rules for Jet Template Install Line model
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

    def _create_install_line_record(
        self,
        template=None,
        line_template=None,
        server=None,
        line_template_access_level="2",
        line_template_user_ids=None,
        server_user_ids=None,
        server_manager_ids=None,
    ):
        """
        Helper method to create a jet template install line record

        Note: Install Line access rules only check server_id and line template
        (jet_template_id), not the parent install template. So we only need
        to vary these parameters for testing.

        Args:
            template: Template for the install record (parent)
            - defaults to simple template.
            line_template: Template for the install line
            server: Server for the install record
            line_template_access_level: Access level for line template
            line_template_user_ids: User IDs for line template
            server_user_ids: User IDs for server
            server_manager_ids: Manager IDs for server
        """
        if not template:
            template = self.JetTemplate.create(
                {
                    "name": "Test Template",
                    "access_level": "2",  # Default, doesn't affect Install Line access
                }
            )

        if not line_template:
            line_template = self.JetTemplate.create(
                {
                    "name": "Test Line Template",
                    "reference": "test_line_template",
                    "access_level": line_template_access_level,
                    "user_ids": line_template_user_ids
                    if line_template_user_ids is not None
                    else [(5, 0, 0)],
                    "manager_ids": [(5, 0, 0)],
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

        # Create install line record
        install_line_record = self.JetTemplateInstallLine.create(
            {
                "jet_template_install_id": install_record.id,
                "jet_template_id": line_template.id,
                "order": 10,
            }
        )

        return template, line_template, server, install_record, install_line_record

    # ======================
    # Manager Read Access Tests
    # ======================

    def test_manager_read_server_user_ids_line_template_access_level_manager(self):
        """
        Test Manager: Read when in server user_ids
        and line template access_level <= 2.
        """
        _, _, _, _, install_line_record = self._create_install_line_record(
            line_template_access_level="2",
            server_user_ids=[(4, self.manager.id)],
        )

        records = self.JetTemplateInstallLine.with_user(self.manager).search(
            [("id", "=", install_line_record.id)]
        )
        self.assertEqual(
            len(records),
            1,
            "Manager should read when in server user_ids "
            "and line template access_level <= 2.",
        )

    def test_manager_read_server_manager_ids_line_template_access_level_manager(self):
        """
        Test Manager: Read when in server manager_ids
        and line template access_level <= 2.
        """
        _, _, _, _, install_line_record = self._create_install_line_record(
            line_template_access_level="2",
            server_manager_ids=[(4, self.manager.id)],
        )

        records = self.JetTemplateInstallLine.with_user(self.manager).search(
            [("id", "=", install_line_record.id)]
        )
        self.assertEqual(
            len(records),
            1,
            "Manager should read when in server manager_ids"
            " and line template access_level <= 2",
        )

    def test_manager_read_line_template_user_ids_override(self):
        """
        Test Manager: Read when in line template user_ids overrides access_level
        (server user_ids or manager_ids).
        """
        # Test with server user_ids
        _, _, _, _, install_line_record1 = self._create_install_line_record(
            line_template_access_level="3",  # Root level - normally not accessible
            line_template_user_ids=[(4, self.manager.id)],
            server_user_ids=[(4, self.manager.id)],
        )

        records = self.JetTemplateInstallLine.with_user(self.manager).search(
            [("id", "=", install_line_record1.id)]
        )
        self.assertEqual(
            len(records),
            1,
            "Manager should read when in line template user_ids" " and server user_ids",
        )

        # Test with server manager_ids
        _, _, _, _, install_line_record2 = self._create_install_line_record(
            line_template_access_level="3",  # Root level - normally not accessible
            line_template_user_ids=[(4, self.manager.id)],
            server_manager_ids=[(4, self.manager.id)],
        )

        records = self.JetTemplateInstallLine.with_user(self.manager).search(
            [("id", "=", install_line_record2.id)]
        )
        self.assertEqual(
            len(records),
            1,
            "Manager should read when in line template user_ids"
            " and server manager_ids",
        )

    def test_manager_read_no_access_no_server_access(self):
        """
        Test Manager: No read access when not in server
        user_ids and manager_ids.
        """
        _, _, _, _, install_line_record = self._create_install_line_record(
            line_template_access_level="1",
            server_user_ids=[(5, 0, 0)],
            server_manager_ids=[(5, 0, 0)],
        )

        records = self.JetTemplateInstallLine.with_user(self.manager).search(
            [("id", "=", install_line_record.id)]
        )
        self.assertEqual(
            len(records),
            0,
            "Manager should not read when not in server user_ids or manager_ids",
        )

    def test_manager_read_no_access_line_template_root_level(self):
        """
        Test Manager: No read access when line template
        access_level is Root and not in line template user_ids.
        """
        _, _, _, _, install_line_record = self._create_install_line_record(
            line_template_access_level="3",  # Root level
            line_template_user_ids=[(5, 0, 0)],
            server_user_ids=[(4, self.manager.id)],
        )

        records = self.JetTemplateInstallLine.with_user(self.manager).search(
            [("id", "=", install_line_record.id)]
        )
        self.assertEqual(
            len(records),
            0,
            "Manager should not read when line template access_level"
            " is Root and not in line template user_ids",
        )

    def test_manager_read_no_access_line_template_manager_level_no_server_access(self):
        """
        Test Manager: No read access when line template access_level
        is Manager but not in server.
        """
        _, _, _, _, install_line_record = self._create_install_line_record(
            line_template_access_level="2",
            server_user_ids=[(5, 0, 0)],
            server_manager_ids=[(5, 0, 0)],
        )

        records = self.JetTemplateInstallLine.with_user(self.manager).search(
            [("id", "=", install_line_record.id)]
        )
        self.assertEqual(
            len(records),
            0,
            "Manager should not read when not in server"
            " even if line template access_level is Manager",
        )

    def test_manager_write_forbidden(self):
        """Test Manager: Cannot write/create/delete records"""
        _, _, _, _, install_line_record = self._create_install_line_record(
            line_template_access_level="2",
            server_user_ids=[(4, self.manager.id)],
        )

        # Manager should not be able to write
        with self.assertRaises(AccessError):
            install_line_record.with_user(self.manager).write({"state": "done"})

        # Manager should not be able to create
        template = self.JetTemplate.create(
            {
                "name": "New Template",
                "reference": "new_template",
                "access_level": "2",
            }
        )
        line_template = self.JetTemplate.create(
            {
                "name": "New Line Template",
                "reference": "new_line_template",
                "access_level": "2",
            }
        )
        server = self.server_test_1
        server.write({"user_ids": [(4, self.manager.id)]})

        install_record = self.JetTemplateInstall.create(
            {
                "jet_template_id": template.id,
                "server_id": server.id,
            }
        )

        with self.assertRaises(AccessError):
            self.JetTemplateInstallLine.with_user(self.manager).create(
                {
                    "jet_template_install_id": install_record.id,
                    "jet_template_id": line_template.id,
                    "order": 10,
                }
            )

        # Manager should not be able to delete
        with self.assertRaises(AccessError):
            install_line_record.with_user(self.manager).unlink()

    # ======================
    # Root Access Tests
    # ======================

    def test_root_write_access(self):
        """Test Root: Can write any record"""
        _, _, _, _, install_line_record = self._create_install_line_record()

        # Root should be able to write
        try:
            install_line_record.with_user(self.root).write({"state": "done"})
            install_line_record.invalidate_recordset()
            self.assertEqual(
                install_line_record.state, "done", "Root should be able to update"
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
        line_template = self.JetTemplate.with_user(self.root).create(
            {
                "name": "Root Line Template",
                "reference": "root_line_template",
                "access_level": "3",
            }
        )
        server = self.server_test_1

        install_record = self.JetTemplateInstall.create(
            {
                "jet_template_id": template.id,
                "server_id": server.id,
            }
        )

        # Root should be able to create
        try:
            install_line_record = self.JetTemplateInstallLine.with_user(
                self.root
            ).create(
                {
                    "jet_template_install_id": install_record.id,
                    "jet_template_id": line_template.id,
                    "order": 10,
                }
            )
            records = self.JetTemplateInstallLine.with_user(self.root).search(
                [("id", "=", install_line_record.id)]
            )
            self.assertEqual(len(records), 1, "Root should be able to create")
        except AccessError:
            self.fail("Root should be able to create any record")

    def test_root_delete_access(self):
        """Test Root: Can delete any record"""
        _, _, _, _, install_line_record = self._create_install_line_record()

        # Root should be able to delete
        try:
            install_line_record.with_user(self.root).unlink()
            records = self.JetTemplateInstallLine.with_user(self.root).search(
                [("id", "=", install_line_record.id)]
            )
            self.assertEqual(len(records), 0, "Root should be able to delete")
        except AccessError:
            self.fail("Root should be able to delete any record")

    def test_root_access_all_scenarios(self):
        """Test Root can access records in all scenarios"""
        # Test various combinations
        scenarios = [
            {
                "line_template_access_level": "1",
                "server_user_ids": [(5, 0, 0)],
                "server_manager_ids": [(5, 0, 0)],
            },
            {
                "line_template_access_level": "2",
                "server_user_ids": [(5, 0, 0)],
                "server_manager_ids": [(5, 0, 0)],
            },
            {
                "line_template_access_level": "3",
                "server_user_ids": [(5, 0, 0)],
                "server_manager_ids": [(5, 0, 0)],
            },
        ]

        for scenario in scenarios:
            _, _, _, _, install_line_record = self._create_install_line_record(
                **scenario
            )
            records = self.JetTemplateInstallLine.with_user(self.root).search(
                [("id", "=", install_line_record.id)]
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
        # Manager in server 1, line template accessible
        _, line_template1, _, _, install_line1 = self._create_install_line_record(
            line_template_access_level="2",
            server_user_ids=[(4, self.manager.id)],
        )

        # Manager not in server 2, same line template
        _, _, _, _, install_line2 = self._create_install_line_record(
            line_template=line_template1,
            server=self.server_test_2,
            line_template_access_level="2",
            server_user_ids=[(5, 0, 0)],
            server_manager_ids=[(5, 0, 0)],
        )

        # Manager should only see install_line1
        records = self.JetTemplateInstallLine.with_user(self.manager).search(
            [("id", "in", [install_line1.id, install_line2.id])]
        )
        self.assertEqual(
            len(records), 1, "Manager should only see accessible install line"
        )
        self.assertEqual(
            records[0].id, install_line1.id, "Manager should see install_line1"
        )

    def test_manager_read_multiple_line_templates(self):
        """Test Manager access with multiple line templates"""
        # Line Template 1: Manager level, Manager in server
        _, _, _, _, install_line1 = self._create_install_line_record(
            line_template_access_level="2",
            server_user_ids=[(4, self.manager.id)],
        )

        # Line Template 2: Root level, Manager in server but line template user_ids
        _, _, _, _, install_line2 = self._create_install_line_record(
            line_template_access_level="3",
            line_template_user_ids=[(4, self.manager.id)],
            server_user_ids=[(4, self.manager.id)],
        )

        # Manager should see both
        records = self.JetTemplateInstallLine.with_user(self.manager).search(
            [("id", "in", [install_line1.id, install_line2.id])]
        )
        self.assertEqual(len(records), 2, "Manager should see both install lines")

    def test_manager_read_parent_template_does_not_affect_access(self):
        """
        Test Manager: Parent install template access level
        does not affect Install Line access.
        """
        # Verify that Install Line access only depends on server_id and line template,
        # not the parent install template.
        # Create a line with Root-level parent template,
        # but accessible line template - should still be accessible.
        _, _, _, _, install_line_record = self._create_install_line_record(
            template=self.JetTemplate.create(
                {
                    "name": "Root Parent Template",
                    "reference": "root_parent_template",
                    "access_level": "3",
                }
            ),
            line_template_access_level="2",  # Manager level - accessible
            server_user_ids=[(4, self.manager.id)],
        )

        records = self.JetTemplateInstallLine.with_user(self.manager).search(
            [("id", "=", install_line_record.id)]
        )
        self.assertEqual(
            len(records),
            1,
            "Manager should read Install Line when line template "
            "and server are accessible, "
            "regardless of parent install template access level",
        )
