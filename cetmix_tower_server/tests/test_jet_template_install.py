# Copyright (C) 2025 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from unittest.mock import patch

from odoo.exceptions import ValidationError

from .common_jets import TestTowerJetsCommon


class TestTowerJetTemplateInstall(TestTowerJetsCommon):
    """
    Test the cx.tower.jet.template.install model methods
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create additional servers for testing
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
        cls.server_test_3 = cls.Server.create(
            {
                "name": "Test Server 3",
                "reference": "test_server_3",
                "ip_v4_address": "192.168.1.103",
                "ssh_username": "admin",
                "ssh_password": "password",
                "ssh_auth_mode": "p",
                "os_id": cls.os_debian_10.id,
            }
        )

    def test_uninstall_creates_install_record(self):
        """Test that uninstall creates a new install record with correct data"""
        server = self.server_test_1
        template = self.jet_template_test

        # Create a dummy record to satisfy ensure_one()
        # Note: This is a workaround for ensure_one() in @api.model method
        dummy_record = self.JetTemplateInstall.create(
            {
                "jet_template_id": template.id,
                "server_id": server.id,
                "action": "install",
            }
        )

        # Call uninstall on the dummy record
        with patch(
            "odoo.addons.cetmix_tower_server.models.cx_tower_jet_template_install"
            ".CxTowerJetTemplateInstall._process_install"
        ) as mock_process:
            install_record = dummy_record.uninstall(server, template)

            # Verify install record was created
            self.assertTrue(install_record, "Should return an install record")
            self.assertEqual(
                install_record.jet_template_id,
                template,
                "Install record should reference the template",
            )
            self.assertEqual(
                install_record.server_id,
                server,
                "Install record should reference the server",
            )
            self.assertEqual(
                install_record.action,
                "uninstall",
                "Install record action should be 'uninstall'",
            )
            self.assertEqual(
                install_record.state,
                "processing",
                "Install record state should be 'processing'",
            )

            # Verify line_ids contains only the template (no dependencies)
            self.assertEqual(
                len(install_record.line_ids),
                1,
                "Should have exactly one line for uninstall",
            )
            line = install_record.line_ids[0]
            self.assertEqual(
                line.jet_template_id,
                template,
                "Line should reference the template",
            )
            self.assertEqual(line.order, 0, "Line order should be 0")

            # Verify _process_install was called
            mock_process.assert_called_once()

    def test_uninstall_creates_notification(self):
        """Test that uninstall sends a notification to the user"""
        server = self.server_test_1
        template = self.jet_template_test

        # Create a dummy record to satisfy ensure_one()
        dummy_record = self.JetTemplateInstall.create(
            {
                "jet_template_id": template.id,
                "server_id": server.id,
                "action": "install",
            }
        )

        # Mock notify_info to verify it's called
        with (
            patch.object(self.env.user.__class__, "notify_info") as mock_notify,
            patch(
                "odoo.addons.cetmix_tower_server.models.cx_tower_jet_template_install"
                ".CxTowerJetTemplateInstall._process_install"
            ),
        ):
            dummy_record.uninstall(server, template)

            # Verify notify_info was called
            self.assertEqual(mock_notify.call_count, 1, "Should call notify_info once")

            # Verify notification parameters
            call_args = mock_notify.call_args
            self.assertIn("message", call_args.kwargs, "Should have message")
            self.assertIn("title", call_args.kwargs, "Should have title")
            self.assertEqual(
                call_args.kwargs["title"],
                template.name,
                "Notification title should be template name",
            )
            self.assertEqual(
                call_args.kwargs["sticky"],
                False,
                "Notification should not be sticky",
            )
            self.assertIn("action", call_args.kwargs, "Should have action")

    def test_uninstall_different_template(self):
        """Test uninstall with a different template"""
        server = self.server_test_1
        template = self.jet_template_odoo

        # Create a dummy record to satisfy ensure_one()
        dummy_record = self.JetTemplateInstall.create(
            {
                "jet_template_id": self.jet_template_test.id,
                "server_id": server.id,
                "action": "install",
            }
        )

        with patch(
            "odoo.addons.cetmix_tower_server.models.cx_tower_jet_template_install"
            ".CxTowerJetTemplateInstall._process_install"
        ):
            install_record = dummy_record.uninstall(server, template)

            self.assertEqual(
                install_record.jet_template_id,
                template,
                "Should uninstall the specified template",
            )
            self.assertEqual(
                install_record.server_id,
                server,
                "Should uninstall on the specified server",
            )

    def test_uninstall_different_server(self):
        """Test uninstall with a different server"""
        server = self.server_test_2
        template = self.jet_template_test

        # Create a dummy record to satisfy ensure_one()
        dummy_record = self.JetTemplateInstall.create(
            {
                "jet_template_id": template.id,
                "server_id": self.server_test_1.id,
                "action": "install",
            }
        )

        with patch(
            "odoo.addons.cetmix_tower_server.models.cx_tower_jet_template_install"
            ".CxTowerJetTemplateInstall._process_install"
        ):
            install_record = dummy_record.uninstall(server, template)

            self.assertEqual(
                install_record.server_id,
                server,
                "Should uninstall on the specified server",
            )

    def test_uninstall_removes_template_from_server_ids(self):
        """Test that successful uninstallation removes template from server_ids"""
        server = self.server_test_1
        template = self.jet_template_test

        # First, add template to server_ids to simulate installed state
        template.write({"server_ids": [(4, server.id)]})
        self.assertIn(
            server.id,
            template.server_ids.ids,
            "Template should be in server_ids before uninstall",
        )

        # Create uninstall record
        uninstall_record = self.JetTemplateInstall.create(
            {
                "jet_template_id": template.id,
                "server_id": server.id,
                "action": "uninstall",
                "line_ids": [(0, 0, {"jet_template_id": template.id, "order": 0})],
            }
        )

        # Process uninstallation (without flight plan - direct completion)
        # This simulates the case where there's no flight plan
        uninstall_record.line_ids[0].write({"state": "to_process"})
        uninstall_record.with_context(cetmix_tower_no_commit=True)._process_install()

        # Verify template was removed from server_ids
        template.invalidate_recordset(["server_ids"])
        self.assertNotIn(
            server.id,
            template.server_ids.ids,
            "Template should be removed from server_ids after successful uninstall",
        )

    def test_uninstall_does_not_remove_template_on_failure(self):
        """Test that template is not removed from server_ids if uninstallation fails"""
        server = self.server_test_1
        template = self.jet_template_test

        # First, add template to server_ids to simulate installed state
        template.write({"server_ids": [(4, server.id)]})
        self.assertIn(
            server.id,
            template.server_ids.ids,
            "Template should be in server_ids before uninstall",
        )

        # Create uninstall record with a line
        uninstall_record = self.JetTemplateInstall.create(
            {
                "jet_template_id": template.id,
                "server_id": server.id,
                "action": "uninstall",
                "line_ids": [(0, 0, {"jet_template_id": template.id, "order": 0})],
            }
        )

        # Set current_line_id to simulate flight plan execution
        uninstall_record.write({"current_line_id": uninstall_record.line_ids[0].id})

        # Simulate flight plan finishing with failure (exit code != 0)
        uninstall_record.with_context(
            cetmix_tower_no_commit=True
        )._flight_plan_finished(1)

        # Verify template is still in server_ids (not removed on failure)
        template.invalidate_recordset(["server_ids"])
        self.assertIn(
            server.id,
            template.server_ids.ids,
            "Template should remain in server_ids after uninstall failure",
        )

    # ======================
    # Tests for _flight_plan_finished
    # ======================

    def test_flight_plan_finished_success_install_adds_template_to_server_ids(self):
        """Test that successful install flight plan adds template to server_ids"""
        server = self.server_test_1
        template = self.jet_template_test

        # Ensure template is not in server_ids initially
        template.write({"server_ids": [(5, 0, 0)]})
        self.assertNotIn(
            server.id,
            template.server_ids.ids,
            "Template should not be in server_ids before install",
        )

        # Create install record with a line
        install_record = self.JetTemplateInstall.create(
            {
                "jet_template_id": template.id,
                "server_id": server.id,
                "action": "install",
                "state": "processing",
                "line_ids": [(0, 0, {"jet_template_id": template.id, "order": 0})],
            }
        )

        # Set current_line_id to simulate flight plan execution
        current_line = install_record.line_ids[0]
        install_record.write({"current_line_id": current_line.id})

        # Simulate flight plan finishing successfully (exit code 0)
        with patch(
            "odoo.addons.cetmix_tower_server.models.cx_tower_jet_template_install"
            ".CxTowerJetTemplateInstall._process_install"
        ) as mock_process:
            install_record.with_context(
                cetmix_tower_no_commit=True
            )._flight_plan_finished(0)

            # Verify template was added to server_ids
            template.invalidate_recordset(["server_ids"])
            self.assertIn(
                server.id,
                template.server_ids.ids,
                "Template should be added to server_ids after install success",
            )

            # Verify current line was marked as done (check before clearing)
            current_line.invalidate_recordset(["state"])
            self.assertEqual(
                current_line.state,
                "done",
                "Current line should be marked as done",
            )

            # Verify current_line_id was cleared
            install_record.invalidate_recordset(["current_line_id"])
            self.assertFalse(
                install_record.current_line_id,
                "current_line_id should be cleared after success",
            )

            # Verify _process_install was called to continue processing
            mock_process.assert_called_once()

    def test_flight_plan_finished_success_uninstall_removes_template_from_server_ids(
        self,
    ):
        """
        Test that successful uninstall flight plan
        removes template from server_ids
        """
        server = self.server_test_1
        template = self.jet_template_test

        # Add template to server_ids to simulate installed state
        template.write({"server_ids": [(4, server.id)]})
        self.assertIn(
            server.id,
            template.server_ids.ids,
            "Template should be in server_ids before uninstall",
        )

        # Create uninstall record with a line
        uninstall_record = self.JetTemplateInstall.create(
            {
                "jet_template_id": template.id,
                "server_id": server.id,
                "action": "uninstall",
                "state": "processing",
                "line_ids": [(0, 0, {"jet_template_id": template.id, "order": 0})],
            }
        )

        # Set current_line_id to simulate flight plan execution
        current_line = uninstall_record.line_ids[0]
        uninstall_record.write({"current_line_id": current_line.id})

        # Simulate flight plan finishing successfully (exit code 0)
        with patch(
            "odoo.addons.cetmix_tower_server.models.cx_tower_jet_template_install"
            ".CxTowerJetTemplateInstall._process_install"
        ) as mock_process:
            uninstall_record.with_context(
                cetmix_tower_no_commit=True
            )._flight_plan_finished(0)

            # Verify template was removed from server_ids
            template.invalidate_recordset(["server_ids"])
            self.assertNotIn(
                server.id,
                template.server_ids.ids,
                "Template should be removed from server_ids after uninstall success",
            )

            # Verify current line was marked as done (check before clearing)
            current_line.invalidate_recordset(["state"])
            self.assertEqual(
                current_line.state,
                "done",
                "Current line should be marked as done",
            )

            # Verify current_line_id was cleared
            uninstall_record.invalidate_recordset(["current_line_id"])
            self.assertFalse(
                uninstall_record.current_line_id,
                "current_line_id should be cleared after success",
            )

            # Verify _process_install was called to continue processing
            mock_process.assert_called_once()

    def test_flight_plan_finished_failure_marks_line_as_failed(self):
        """Test that failed flight plan marks current line as failed"""
        server = self.server_test_1
        template = self.jet_template_test

        # Create install record with a line
        install_record = self.JetTemplateInstall.create(
            {
                "jet_template_id": template.id,
                "server_id": server.id,
                "action": "install",
                "state": "processing",
                "line_ids": [(0, 0, {"jet_template_id": template.id, "order": 0})],
            }
        )

        # Set current_line_id to simulate flight plan execution
        current_line = install_record.line_ids[0]
        install_record.write({"current_line_id": current_line.id})

        # Simulate flight plan finishing with failure (exit code != 0)
        install_record.with_context(cetmix_tower_no_commit=True)._flight_plan_finished(
            1
        )

        # Verify current line was marked as failed
        self.assertEqual(
            current_line.state,
            "failed",
            "Current line should be marked as failed",
        )

        # Verify install record state was set to failed
        self.assertEqual(
            install_record.state,
            "failed",
            "Install record state should be 'failed'",
        )

        # Verify date_done was set
        self.assertTrue(
            install_record.date_done,
            "date_done should be set on failure",
        )

        # Verify current_line_id was cleared
        self.assertFalse(
            install_record.current_line_id,
            "current_line_id should be cleared after failure",
        )

    def test_flight_plan_finished_failure_marks_all_to_process_lines_as_failed(self):
        """Test that failed flight plan marks all 'to_process' lines as failed"""
        server = self.server_test_1
        template = self.jet_template_test

        # Create install record with multiple lines
        install_record = self.JetTemplateInstall.create(
            {
                "jet_template_id": template.id,
                "server_id": server.id,
                "action": "install",
                "state": "processing",
                "line_ids": [
                    (0, 0, {"jet_template_id": template.id, "order": 0}),
                    (0, 0, {"jet_template_id": template.id, "order": 1}),
                    (0, 0, {"jet_template_id": template.id, "order": 2}),
                ],
            }
        )

        # Set first line as current and mark others as to_process
        current_line = install_record.line_ids[0]
        other_lines = install_record.line_ids[1:]
        install_record.write({"current_line_id": current_line.id})
        other_lines.write({"state": "to_process"})

        # Simulate flight plan finishing with failure
        install_record.with_context(cetmix_tower_no_commit=True)._flight_plan_finished(
            1
        )

        # Verify all 'to_process' lines were marked as failed
        for line in other_lines:
            self.assertEqual(
                line.state,
                "failed",
                "All 'to_process' lines should be marked as failed",
            )

    def test_flight_plan_finished_failure_sends_notification(self):
        """Test that failed flight plan sends error notification when enabled"""
        server = self.server_test_1
        template = self.jet_template_test

        # Enable error notifications
        self.env["ir.config_parameter"].sudo().set_param(
            "cetmix_tower_server.notification_type_error", "sticky"
        )

        # Create install record with a line
        install_record = self.JetTemplateInstall.create(
            {
                "jet_template_id": template.id,
                "server_id": server.id,
                "action": "install",
                "state": "processing",
                "line_ids": [(0, 0, {"jet_template_id": template.id, "order": 0})],
            }
        )

        # Set current_line_id to simulate flight plan execution
        install_record.write({"current_line_id": install_record.line_ids[0].id})

        # Mock notify_danger to verify it's called
        with patch.object(self.env.user.__class__, "notify_danger") as mock_notify:
            install_record.with_context(
                cetmix_tower_no_commit=True
            )._flight_plan_finished(1)

            # Verify notify_danger was called
            self.assertEqual(
                mock_notify.call_count, 1, "Should call notify_danger once"
            )

            # Verify notification parameters
            call_args = mock_notify.call_args
            self.assertIn("message", call_args.kwargs, "Should have message")
            self.assertIn("title", call_args.kwargs, "Should have title")
            self.assertEqual(
                call_args.kwargs["title"],
                template.name,
                "Notification title should be template name",
            )
            self.assertEqual(
                call_args.kwargs["sticky"],
                True,
                "Notification should be sticky when configured",
            )
            self.assertIn("action", call_args.kwargs, "Should have action")

    def test_flight_plan_finished_no_notification_when_disabled(self):
        """Test that failed flight plan doesn't send notification when disabled"""
        server = self.server_test_1
        template = self.jet_template_test

        # Disable error notifications
        self.env["ir.config_parameter"].sudo().set_param(
            "cetmix_tower_server.notification_type_error", False
        )

        # Create install record with a line
        install_record = self.JetTemplateInstall.create(
            {
                "jet_template_id": template.id,
                "server_id": server.id,
                "action": "install",
                "state": "processing",
                "line_ids": [(0, 0, {"jet_template_id": template.id, "order": 0})],
            }
        )

        # Set current_line_id to simulate flight plan execution
        install_record.write({"current_line_id": install_record.line_ids[0].id})

        # Mock notify_danger to verify it's NOT called
        with patch.object(self.env.user.__class__, "notify_danger") as mock_notify:
            install_record.with_context(
                cetmix_tower_no_commit=True
            )._flight_plan_finished(1)

            # Verify notify_danger was NOT called
            mock_notify.assert_not_called()

    def test_flight_plan_finished_no_current_line_id_returns_early(self):
        """Test that _flight_plan_finished returns early if no current_line_id"""
        server = self.server_test_1
        template = self.jet_template_test

        # Create install record without current_line_id
        install_record = self.JetTemplateInstall.create(
            {
                "jet_template_id": template.id,
                "server_id": server.id,
                "action": "install",
                "state": "processing",
                "line_ids": [(0, 0, {"jet_template_id": template.id, "order": 0})],
            }
        )

        # Ensure current_line_id is False
        self.assertFalse(install_record.current_line_id)

        # Mock logger to verify warning is logged
        with patch(
            "odoo.addons.cetmix_tower_server.models.cx_tower_jet_template_install._logger.warning"
        ) as mock_warning:
            install_record.with_context(
                cetmix_tower_no_commit=True
            )._flight_plan_finished(0)

            # Verify warning was logged
            mock_warning.assert_called_once()

            # Verify template was not modified (early return)
            template.invalidate_recordset(["server_ids"])
            self.assertNotIn(
                server.id,
                template.server_ids.ids,
                "Template should not be modified when no current_line_id",
            )

    def test_flight_plan_finished_wrong_state_returns_early(self):
        """Test that _flight_plan_finished returns early if state is not 'processing'"""
        server = self.server_test_1
        template = self.jet_template_test

        # Create install record in 'done' state
        install_record = self.JetTemplateInstall.create(
            {
                "jet_template_id": template.id,
                "server_id": server.id,
                "action": "install",
                "state": "done",
                "line_ids": [(0, 0, {"jet_template_id": template.id, "order": 0})],
            }
        )

        # Set current_line_id
        install_record.write({"current_line_id": install_record.line_ids[0].id})

        # Mock logger to verify warning is logged
        with patch(
            "odoo.addons.cetmix_tower_server.models.cx_tower_jet_template_install._logger.warning"
        ) as mock_warning:
            install_record.with_context(
                cetmix_tower_no_commit=True
            )._flight_plan_finished(0)

            # Verify warning was logged
            mock_warning.assert_called_once()

            # Verify template was not modified (early return)
            template.invalidate_recordset(["server_ids"])
            self.assertNotIn(
                server.id,
                template.server_ids.ids,
                "Template should not be modified when state is not 'processing'",
            )

    # ======================
    # Tests for _is_installation_needed (from JetTemplate model)
    # ======================

    def test_is_installation_needed_server_already_installed(self):
        """Test _is_installation_needed when server is already installed"""
        # pylint: disable=protected-access
        # Create a server
        server = self.Server.create(
            {
                "name": "Test Server",
                "reference": "test_server",
                "ip_v4_address": "192.168.1.100",
                "ssh_username": "admin",
                "ssh_password": "password",
                "ssh_auth_mode": "p",
            }
        )

        # Add server to template's installed servers
        self.jet_template_test.server_ids = [(4, server.id)]

        result = self.jet_template_test._is_installation_needed(server)
        self.assertFalse(result, "Should return False when server is already installed")

    def test_is_installation_needed_installation_in_progress_processing(self):
        """Test _is_installation_needed when installation is in processing state"""
        # pylint: disable=protected-access
        # Create a server
        server = self.Server.create(
            {
                "name": "Test Server",
                "reference": "test_server",
                "ip_v4_address": "192.168.1.100",
                "ssh_username": "admin",
                "ssh_password": "password",
                "ssh_auth_mode": "p",
            }
        )

        # Create an installation record in processing state
        install_record = self.JetTemplateInstall.create(
            {
                "jet_template_id": self.jet_template_test.id,
                "server_id": server.id,
                "state": "processing",
            }
        )

        # Create install line
        self.JetTemplateInstallLine.create(
            {
                "jet_template_install_id": install_record.id,
                "jet_template_id": self.jet_template_test.id,
                "state": "processing",
            }
        )

        result = self.jet_template_test._is_installation_needed(server)
        self.assertFalse(
            result, "Should return False when installation is in processing state"
        )

    def test_is_installation_needed_installation_in_progress_to_process(self):
        """Test _is_installation_needed when installation is in to_process state"""
        # pylint: disable=protected-access
        # Create a server
        server = self.Server.create(
            {
                "name": "Test Server",
                "reference": "test_server",
                "ip_v4_address": "192.168.1.100",
                "ssh_username": "admin",
                "ssh_password": "password",
                "ssh_auth_mode": "p",
            }
        )

        # Create an installation record in to_process state
        install_record = self.JetTemplateInstall.create(
            {
                "jet_template_id": self.jet_template_test.id,
                "server_id": server.id,
                "state": "processing",
            }
        )

        # Create install line
        self.JetTemplateInstallLine.create(
            {
                "jet_template_install_id": install_record.id,
                "jet_template_id": self.jet_template_test.id,
                "state": "to_process",
            }
        )

        result = self.jet_template_test._is_installation_needed(server)
        self.assertFalse(
            result, "Should return False when installation is in to_process state"
        )

    def test_is_installation_needed_installation_completed(self):
        """Test _is_installation_needed when installation is completed"""
        # pylint: disable=protected-access
        # Create a server
        server = self.Server.create(
            {
                "name": "Test Server",
                "reference": "test_server",
                "ip_v4_address": "192.168.1.100",
                "ssh_username": "admin",
                "ssh_password": "password",
                "ssh_auth_mode": "p",
            }
        )

        # Create an installation record in installed state
        install_record = self.JetTemplateInstall.create(
            {
                "jet_template_id": self.jet_template_test.id,
                "server_id": server.id,
                "state": "done",
            }
        )

        # Create install line
        self.JetTemplateInstallLine.create(
            {
                "jet_template_install_id": install_record.id,
                "jet_template_id": self.jet_template_test.id,
                "state": "done",
            }
        )

        result = self.jet_template_test._is_installation_needed(server)
        self.assertTrue(
            result,
            "Should return True when installation is completed (not in progress)",
        )

    def test_is_installation_needed_installation_failed(self):
        """Test _is_installation_needed when installation failed"""
        # pylint: disable=protected-access
        # Create a server
        server = self.Server.create(
            {
                "name": "Test Server",
                "reference": "test_server",
                "ip_v4_address": "192.168.1.100",
                "ssh_username": "admin",
                "ssh_password": "password",
                "ssh_auth_mode": "p",
            }
        )

        # Create an installation record in failed state
        install_record = self.JetTemplateInstall.create(
            {
                "jet_template_id": self.jet_template_test.id,
                "server_id": server.id,
                "state": "failed",
            }
        )

        # Create install line
        self.JetTemplateInstallLine.create(
            {
                "jet_template_install_id": install_record.id,
                "jet_template_id": self.jet_template_test.id,
                "state": "failed",
            }
        )

        result = self.jet_template_test._is_installation_needed(server)
        self.assertTrue(result, "Should return True when installation failed")

    def test_is_installation_needed_multiple_installations(self):
        """Test _is_installation_needed with multiple installation records"""
        # pylint: disable=protected-access
        # Create a server
        server = self.Server.create(
            {
                "name": "Test Server",
                "reference": "test_server",
                "ip_v4_address": "192.168.1.100",
                "ssh_username": "admin",
                "ssh_password": "password",
                "ssh_auth_mode": "p",
            }
        )

        # Create multiple installation records
        install_record1 = self.JetTemplateInstall.create(
            {
                "jet_template_id": self.jet_template_test.id,
                "server_id": server.id,
                "state": "done",
            }
        )

        install_record2 = self.JetTemplateInstall.create(
            {
                "jet_template_id": self.jet_template_test.id,
                "server_id": server.id,
                "state": "processing",
            }
        )

        # Create install lines
        self.JetTemplateInstallLine.create(
            {
                "jet_template_install_id": install_record1.id,
                "jet_template_id": self.jet_template_test.id,
                "state": "done",
            }
        )

        self.JetTemplateInstallLine.create(
            {
                "jet_template_install_id": install_record2.id,
                "jet_template_id": self.jet_template_test.id,
                "state": "processing",
            }
        )

        result = self.jet_template_test._is_installation_needed(server)
        self.assertFalse(
            result, "Should return False when any installation is in progress"
        )

    def test_is_installation_needed_different_servers(self):
        """Test _is_installation_needed with different servers"""
        # pylint: disable=protected-access
        # Create two servers
        server1 = self.Server.create(
            {
                "name": "Test Server 1",
                "reference": "test_server_1",
                "ip_v4_address": "192.168.1.101",
                "ssh_username": "admin",
                "ssh_password": "password",
                "ssh_auth_mode": "p",
            }
        )
        server2 = self.Server.create(
            {
                "name": "Test Server 2",
                "reference": "test_server_2",
                "ip_v4_address": "192.168.1.102",
                "ssh_username": "admin",
                "ssh_password": "password",
                "ssh_auth_mode": "p",
            }
        )

        # Add server1 to template's installed servers
        self.jet_template_test.server_ids = [(4, server1.id)]

        # Create installation record for server2
        install_record = self.JetTemplateInstall.create(
            {
                "jet_template_id": self.jet_template_test.id,
                "server_id": server2.id,
                "state": "processing",
            }
        )

        # Create install line
        self.JetTemplateInstallLine.create(
            {
                "jet_template_install_id": install_record.id,
                "jet_template_id": self.jet_template_test.id,
                "state": "processing",
            }
        )

        # Check server1 (already installed)
        result1 = self.jet_template_test._is_installation_needed(server1)
        self.assertFalse(result1, "Should return False for server1 (already installed)")

        # Check server2 (installation in progress)
        result2 = self.jet_template_test._is_installation_needed(server2)
        self.assertFalse(
            result2, "Should return False for server2 (installation in progress)"
        )

    def test_is_installation_needed_no_installations(self):
        """Test _is_installation_needed when no installation records exist"""
        # pylint: disable=protected-access
        # Create a server
        server = self.Server.create(
            {
                "name": "Test Server",
                "reference": "test_server",
                "ip_v4_address": "192.168.1.100",
                "ssh_username": "admin",
                "ssh_password": "password",
                "ssh_auth_mode": "p",
            }
        )

        result = self.jet_template_test._is_installation_needed(server)
        self.assertTrue(result, "Should return True when no installation records exist")

    def test_is_installation_needed_mixed_states(self):
        """Test _is_installation_needed with mixed installation states"""
        # pylint: disable=protected-access
        # Create a server
        server = self.Server.create(
            {
                "name": "Test Server",
                "reference": "test_server",
                "ip_v4_address": "192.168.1.100",
                "ssh_username": "admin",
                "ssh_password": "password",
                "ssh_auth_mode": "p",
            }
        )

        # Create installation records with different states
        install_record1 = self.JetTemplateInstall.create(
            {
                "jet_template_id": self.jet_template_test.id,
                "server_id": server.id,
                "state": "done",
            }
        )

        install_record2 = self.JetTemplateInstall.create(
            {
                "jet_template_id": self.jet_template_test.id,
                "server_id": server.id,
                "state": "failed",
            }
        )

        # Create install lines
        self.JetTemplateInstallLine.create(
            {
                "jet_template_install_id": install_record1.id,
                "jet_template_id": self.jet_template_test.id,
                "state": "done",
            }
        )

        self.JetTemplateInstallLine.create(
            {
                "jet_template_install_id": install_record2.id,
                "jet_template_id": self.jet_template_test.id,
                "state": "failed",
            }
        )

        result = self.jet_template_test._is_installation_needed(server)
        self.assertTrue(
            result, "Should return True when all installations are completed or failed"
        )

    # ======================
    # Tests for install_on_servers (from JetTemplate model)
    # ======================

    def test_install_on_servers_no_dependencies(self):
        """Test install_on_servers with template that has no dependencies"""
        # pylint: disable=protected-access
        # Use existing server from common.py
        server = self.server_test_1

        # Call install method directly with cetmix_tower_no_commit context
        self.jet_template_test.with_context(
            cetmix_tower_no_commit=True
        ).install_on_servers(server)

        # Verify installation record was created
        install_records = self.JetTemplateInstall.search(
            [
                ("jet_template_id", "=", self.jet_template_test.id),
                ("server_id", "=", server.id),
            ]
        )
        self.assertEqual(
            len(install_records), 1, "Should create exactly one installation record"
        )

    def test_install_on_servers_already_installed(self):
        """Test install_on_servers when template is already installed"""
        # pylint: disable=protected-access
        # Use existing server from common.py
        server = self.server_test_1

        # Add server to template's installed servers
        self.jet_template_test.server_ids = [(4, server.id)]

        # Call install method - should skip since already installed
        self.jet_template_test.with_context(
            cetmix_tower_no_commit=True
        ).install_on_servers(server)

        # Verify no new installation record was created
        install_records = self.JetTemplateInstall.search(
            [
                ("jet_template_id", "=", self.jet_template_test.id),
                ("server_id", "=", server.id),
            ]
        )
        self.assertEqual(
            len(install_records),
            0,
            "Should not create installation record when already installed",
        )

    def test_install_on_servers_installation_in_progress(self):
        """Test install_on_servers when installation is already in progress"""
        # pylint: disable=protected-access
        # Use existing server from common.py
        server = self.server_test_1

        # Create installation record in progress
        install_record = self.JetTemplateInstall.create(
            {
                "jet_template_id": self.jet_template_test.id,
                "server_id": server.id,
                "state": "processing",
            }
        )

        # Create install line
        self.JetTemplateInstallLine.create(
            {
                "jet_template_install_id": install_record.id,
                "jet_template_id": self.jet_template_test.id,
                "state": "processing",
            }
        )

        # Call install method - should skip since installation in progress
        self.jet_template_test.with_context(
            cetmix_tower_no_commit=True
        ).install_on_servers(server)

        # Verify no additional installation record was created
        install_records = self.JetTemplateInstall.search(
            [
                ("jet_template_id", "=", self.jet_template_test.id),
                ("server_id", "=", server.id),
            ]
        )
        self.assertEqual(
            len(install_records),
            1,
            "Should not create additional installation record",
        )

    def test_install_on_servers_dependency_satisfaction(self):
        """Test install_on_servers dependency satisfaction logic"""
        # pylint: disable=protected-access
        # Use class-level dependency hierarchy
        # Use existing server from common.py
        server = self.server_test_1

        # Install Tower Core on server
        self.jet_template_tower_core.server_ids = [(4, server.id)]

        # Call install method directly
        self.jet_template_postgres.with_context(
            cetmix_tower_no_commit=True
        ).install_on_servers(server)

        # Verify installation record was created
        install_records = self.JetTemplateInstall.search(
            [
                ("jet_template_id", "=", self.jet_template_postgres.id),
                ("server_id", "=", server.id),
            ]
        )
        self.assertEqual(
            len(install_records), 1, "Should create exactly one installation record"
        )

    def test_install_on_servers_multiple_servers(self):
        """Test install_on_servers with multiple servers"""
        # pylint: disable=protected-access
        # Use existing servers from class setup
        server1 = self.server_test_1
        server2 = self.server_test_2

        # Add server1 to template's installed servers
        self.jet_template_test.server_ids = [(4, server1.id)]

        # Call install method directly
        self.jet_template_test.with_context(
            cetmix_tower_no_commit=True
        ).install_on_servers([server1, server2])

        # Verify installation record was created only for server2
        install_records = self.JetTemplateInstall.search(
            [
                ("jet_template_id", "=", self.jet_template_test.id),
                ("server_id", "=", server2.id),
            ]
        )
        self.assertEqual(
            len(install_records), 1, "Should create installation record for server2"
        )

        # Verify no installation record for server1 (already installed)
        install_records_server1 = self.JetTemplateInstall.search(
            [
                ("jet_template_id", "=", self.jet_template_test.id),
                ("server_id", "=", server1.id),
            ]
        )
        self.assertEqual(
            len(install_records_server1),
            0,
            "Should not create installation record for server1 (already installed)",
        )

    def test_install_on_servers_empty_server_list(self):
        """Test install_on_servers with empty server list"""
        # pylint: disable=protected-access
        # Call install method with empty list
        self.jet_template_test.with_context(
            cetmix_tower_no_commit=True
        ).install_on_servers([])

        # Verify no installation record was created
        install_records = self.JetTemplateInstall.search(
            [("jet_template_id", "=", self.jet_template_test.id)]
        )
        self.assertEqual(
            len(install_records),
            0,
            "Should not create installation record with empty server list",
        )

    def test_install_on_servers_mixed_server_states(self):
        """Test install_on_servers with mixed server states"""
        # Use existing servers from class setup
        server1 = self.server_test_1
        server2 = self.server_test_2
        server3 = self.server_test_3

        # Server1: Already installed
        self.jet_template_test.server_ids = [(4, server1.id)]

        # Server2: Installation in progress
        install_record = self.JetTemplateInstall.create(
            {
                "jet_template_id": self.jet_template_test.id,
                "server_id": server2.id,
                "state": "processing",
            }
        )
        self.JetTemplateInstallLine.create(
            {
                "jet_template_install_id": install_record.id,
                "jet_template_id": self.jet_template_test.id,
                "state": "processing",
            }
        )

        # Server3: Not installed (should trigger installation)

        # Call install method directly
        self.jet_template_test.with_context(
            cetmix_tower_no_commit=True
        ).install_on_servers([server1, server2, server3])

        # Verify installation record was created only for server3
        install_records = self.JetTemplateInstall.search(
            [
                ("jet_template_id", "=", self.jet_template_test.id),
                ("server_id", "=", server3.id),
            ]
        )
        self.assertEqual(
            len(install_records), 1, "Should create installation record for server3"
        )

    def test_install_on_servers_odoo_scenario_complete_installation(self):
        """Test complete Odoo installation scenario"""
        # Use class-level dependency hierarchy
        # Use existing server from common.py
        server = self.server_test_1

        # Call install for Odoo template
        self.jet_template_odoo.with_context(
            cetmix_tower_no_commit=True
        ).install_on_servers(server)

        # Verify installation log is created
        install_records = self.JetTemplateInstall.search(
            [
                ("jet_template_id", "=", self.jet_template_odoo.id),
                ("server_id", "=", server.id),
            ]
        )
        self.assertEqual(
            len(install_records), 1, "Should create exactly one installation record"
        )

        install_record = install_records[0]
        self.assertEqual(
            install_record.jet_template_id,
            self.jet_template_odoo,
            "Installation should be for Odoo template",
        )
        self.assertEqual(
            install_record.server_id, server, "Installation should be on test server"
        )

        # Verify all dependencies are in installation log lines
        install_lines = install_record.line_ids.sorted("order")
        self.assertEqual(
            len(install_lines),
            5,
            "Should have 5 installation lines (Odoo + 4 dependencies)",
        )

        # Verify all expected templates are included
        template_ids = install_lines.mapped("jet_template_id.id")
        expected_template_ids = [
            self.jet_template_tower_core.id,
            self.jet_template_docker.id,
            self.jet_template_postgres.id,
            self.jet_template_nginx.id,
            self.jet_template_odoo.id,
        ]
        self.assertEqual(
            set(template_ids),
            set(expected_template_ids),
            "All expected templates should be in installation lines",
        )

        # Verify correct order: Odoo first, then Nginx/Postgres (either order),
        # then Docker, then Tower Core.
        odoo_line = install_lines.filtered(
            lambda line: line.jet_template_id == self.jet_template_odoo
        )
        self.assertEqual(odoo_line.order, 0, "Odoo should be first (order 0)")

        # Verify dependency relationships are correct
        # Odoo should be first (main template)
        odoo_line = install_lines.filtered(
            lambda line: line.jet_template_id == self.jet_template_odoo
        )
        self.assertEqual(len(odoo_line), 1, "Should have exactly one Odoo line")
        self.assertEqual(odoo_line.order, 0, "Odoo should be first (order 0)")

        # Nginx and Postgres should be second and third (direct dependencies of Odoo)
        nginx_line = install_lines.filtered(
            lambda line: line.jet_template_id == self.jet_template_nginx
        )
        postgres_line = install_lines.filtered(
            lambda line: line.jet_template_id == self.jet_template_postgres
        )
        self.assertEqual(len(nginx_line), 1, "Should have exactly one Nginx line")
        self.assertEqual(len(postgres_line), 1, "Should have exactly one Postgres line")
        self.assertIn(nginx_line.order, [1, 2], "Nginx should be order 1 or 2")
        self.assertIn(postgres_line.order, [1, 2], "Postgres should be order 1 or 2")
        self.assertNotEqual(
            nginx_line.order,
            postgres_line.order,
            "Nginx and Postgres should have different orders",
        )

        # Docker should be fourth (dependency of both Postgres and Nginx)
        docker_line = install_lines.filtered(
            lambda line: line.jet_template_id == self.jet_template_docker
        )
        self.assertEqual(len(docker_line), 1, "Should have exactly one Docker line")
        self.assertEqual(docker_line.order, 3, "Docker should be fourth (order 3)")

        # Tower Core should be last (dependency of Docker)
        tower_core_line = install_lines.filtered(
            lambda line: line.jet_template_id == self.jet_template_tower_core
        )
        self.assertEqual(
            len(tower_core_line), 1, "Should have exactly one Tower Core line"
        )
        self.assertEqual(
            tower_core_line.order, 4, "Tower Core should be last (order 4)"
        )

    def test_install_on_servers_woocommerce_odoo_scenario(self):
        """Test install_on_servers with WooCommerce with Odoo scenario"""
        # pylint: disable=protected-access
        # Use existing server from common.py
        server = self.server_test_1

        # Call install for WooCommerce with Odoo template
        self.jet_template_woocommerce_odoo.with_context(
            cetmix_tower_no_commit=True
        ).install_on_servers(server)

        # Verify installation log is created
        install_records = self.JetTemplateInstall.search(
            [
                ("jet_template_id", "=", self.jet_template_woocommerce_odoo.id),
                ("server_id", "=", server.id),
            ]
        )
        self.assertEqual(
            len(install_records), 1, "Should create exactly one installation record"
        )

        install_record = install_records[0]
        self.assertEqual(
            install_record.jet_template_id,
            self.jet_template_woocommerce_odoo,
            "Installation should be for WooCommerce with Odoo template",
        )
        self.assertEqual(
            install_record.server_id, server, "Installation should be on test server"
        )

        # Verify all dependencies are in installation log lines
        install_lines = install_record.line_ids.sorted("order")
        # Should have 8 installation lines:
        # WooCommerce + 7 dependencies
        # WordPress, Odoo, MariaDB, Postgres, Nginx, Docker, Tower Core
        self.assertEqual(
            len(install_lines),
            8,
            "Should have 8 installation lines (WooCommerce + 7 dependencies)",
        )

        # Verify topological constraints:
        # WooCommerce first (root), Tower Core last (deepest leaf),
        # Docker before Nginx/Postgres/MariaDB, etc.
        wc_line = install_lines.filtered(
            lambda line: line.jet_template_id == self.jet_template_woocommerce_odoo
        )
        self.assertEqual(wc_line.order, 0, "WooCommerce should be first (order 0)")

        tc_line = install_lines.filtered(
            lambda line: line.jet_template_id == self.jet_template_tower_core
        )
        self.assertEqual(tc_line.order, 7, "Tower Core should be last (order 7)")

        docker_line = install_lines.filtered(
            lambda line: line.jet_template_id == self.jet_template_docker
        )
        nginx_line = install_lines.filtered(
            lambda line: line.jet_template_id == self.jet_template_nginx
        )
        postgres_line = install_lines.filtered(
            lambda line: line.jet_template_id == self.jet_template_postgres
        )
        mariadb_line = install_lines.filtered(
            lambda line: line.jet_template_id == self.jet_template_mariadb
        )
        odoo_line = install_lines.filtered(
            lambda line: line.jet_template_id == self.jet_template_odoo
        )
        wp_line = install_lines.filtered(
            lambda line: line.jet_template_id == self.jet_template_wordpress
        )

        self.assertGreater(
            tc_line.order,
            docker_line.order,
            "Tower Core must have higher order than Docker (installed first)",
        )
        self.assertGreater(
            docker_line.order,
            nginx_line.order,
            "Docker must have higher order than Nginx (installed first)",
        )
        self.assertGreater(
            docker_line.order,
            postgres_line.order,
            "Docker must have higher order than Postgres (installed first)",
        )
        self.assertGreater(
            docker_line.order,
            mariadb_line.order,
            "Docker must have higher order than MariaDB (installed first)",
        )
        self.assertGreater(
            nginx_line.order,
            odoo_line.order,
            "Nginx must have higher order than Odoo (installed first)",
        )
        self.assertGreater(
            postgres_line.order,
            odoo_line.order,
            "Postgres must have higher order than Odoo (installed first)",
        )
        self.assertGreater(
            nginx_line.order,
            wp_line.order,
            "Nginx must have higher order than WordPress (installed first)",
        )
        self.assertGreater(
            mariadb_line.order,
            wp_line.order,
            "MariaDB must have higher order than WordPress (installed first)",
        )

        # Verify all expected templates are included
        template_ids = install_lines.mapped("jet_template_id.id")
        expected_template_ids = [
            self.jet_template_tower_core.id,
            self.jet_template_docker.id,
            self.jet_template_mariadb.id,
            self.jet_template_postgres.id,
            self.jet_template_nginx.id,
            self.jet_template_wordpress.id,
            self.jet_template_odoo.id,
            self.jet_template_woocommerce_odoo.id,
        ]
        self.assertEqual(
            set(template_ids),
            set(expected_template_ids),
            "All expected templates should be in installation lines",
        )

    # ======================
    # Tests for uninstall_from_servers (from JetTemplate model)
    # ======================

    def test_uninstall_from_servers_template_not_installed(self):
        """Test uninstall_from_servers when template is not installed"""
        server = self.server_test_1
        template = self.jet_template_test

        # Ensure template is not installed
        template.write({"server_ids": [(5, 0, 0)]})

        # Should raise ValidationError when raise_if_not_possible=True
        with self.assertRaises(ValidationError) as context:
            template.uninstall_from_servers(server, raise_if_not_possible=True)

        error_message = str(context.exception)
        self.assertIn("not installed", error_message.lower())
        self.assertIn(template.name, error_message)
        self.assertIn(server.name, error_message)

    def test_uninstall_from_servers_template_not_installed_warning(self):
        """Test uninstall_from_servers shows warning when template is not installed"""
        server = self.server_test_1
        template = self.jet_template_test

        # Ensure template is not installed
        template.write({"server_ids": [(5, 0, 0)]})

        # Mock notify_warning to verify it's called
        with patch.object(self.env.user.__class__, "notify_warning") as mock_notify:
            template.uninstall_from_servers(server, raise_if_not_possible=False)

            # Verify notify_warning was called
            mock_notify.assert_called_once()
            call_args = mock_notify.call_args
            self.assertIn("message", call_args.kwargs)
            self.assertIn("not installed", call_args.kwargs["message"].lower())

    def test_uninstall_from_servers_jets_still_exist(self):
        """Test uninstall_from_servers when jets still exist on server"""
        server = self.server_test_1
        template = self.jet_template_test

        # Install template on server
        template.write({"server_ids": [(4, server.id)]})

        # Create a jet on the server
        self.Jet.create(
            {
                "name": "Test Jet Uninstall Still Exist",
                "reference": "test_jet_uninstall_still_exist",
                "jet_template_id": template.id,
                "server_id": server.id,
            }
        )

        # Should raise ValidationError when raise_if_not_possible=True
        with self.assertRaises(ValidationError) as context:
            template.uninstall_from_servers(server, raise_if_not_possible=True)

        error_message = str(context.exception)
        self.assertIn("still jets", error_message.lower())
        self.assertIn(template.name, error_message)
        self.assertIn(server.name, error_message)

    def test_uninstall_from_servers_jets_still_exist_warning(self):
        """Test uninstall_from_servers shows warning when jets still exist"""
        server = self.server_test_1
        template = self.jet_template_test

        # Install template on server
        template.write({"server_ids": [(4, server.id)]})

        # Create a jet on the server
        self.Jet.create(
            {
                "name": "Test Jet Uninstall Still Exist Warning",
                "reference": "test_jet_uninstall_still_exist_warning",
                "jet_template_id": template.id,
                "server_id": server.id,
            }
        )

        # Mock notify_warning to verify it's called
        with patch.object(self.env.user.__class__, "notify_warning") as mock_notify:
            template.uninstall_from_servers(server, raise_if_not_possible=False)

            # Verify notify_warning was called
            mock_notify.assert_called_once()
            call_args = mock_notify.call_args
            self.assertIn("message", call_args.kwargs)
            self.assertIn("still jets", call_args.kwargs["message"].lower())

    def test_uninstall_from_servers_dependent_templates_installed(self):
        """Test uninstall_from_servers when dependent templates are installed"""
        server = self.server_test_1
        # Use postgres template which depends on docker
        base_template = self.jet_template_docker
        dependent_template = self.jet_template_postgres

        # Install both templates on server
        base_template.write({"server_ids": [(4, server.id)]})
        dependent_template.write({"server_ids": [(4, server.id)]})

        # Verify dependency exists
        self.assertTrue(
            dependent_template.template_requires_ids.filtered(
                lambda dep: dep.template_required_id == base_template
            ),
            "Postgres should depend on Docker",
        )

        # Should raise ValidationError when raise_if_not_possible=True
        with self.assertRaises(ValidationError) as context:
            base_template.uninstall_from_servers(server, raise_if_not_possible=True)

        error_message = str(context.exception)
        self.assertIn("depend", error_message.lower())
        self.assertIn(base_template.name, error_message)
        self.assertIn(server.name, error_message)

    def test_uninstall_from_servers_dependent_templates_installed_warning(self):
        """
        Test uninstall_from_servers shows warning
        when dependent templates are installed
        """
        server = self.server_test_1
        # Use postgres template which depends on docker
        base_template = self.jet_template_docker
        dependent_template = self.jet_template_postgres

        # Install both templates on server
        base_template.write({"server_ids": [(4, server.id)]})
        dependent_template.write({"server_ids": [(4, server.id)]})

        # Mock notify_warning to verify it's called
        with patch.object(self.env.user.__class__, "notify_warning") as mock_notify:
            base_template.uninstall_from_servers(server, raise_if_not_possible=False)

            # Verify notify_warning was called
            mock_notify.assert_called_once()
            call_args = mock_notify.call_args
            self.assertIn("message", call_args.kwargs)
            self.assertIn("depend", call_args.kwargs["message"].lower())

    def test_uninstall_from_servers_dependent_templates_not_installed(self):
        """
        Test uninstall_from_servers succeeds
        when dependent templates are not installed
        """
        server = self.server_test_1
        # Use docker template
        base_template = self.jet_template_docker

        # Install only base template on server (not the dependent one)
        base_template.write({"server_ids": [(4, server.id)]})

        # Mock uninstall to verify it's called
        with patch(
            "odoo.addons.cetmix_tower_server.models.cx_tower_jet_template_install"
            ".CxTowerJetTemplateInstall.uninstall"
        ) as mock_uninstall:
            base_template.uninstall_from_servers(server, raise_if_not_possible=True)

            # Verify uninstall was called
            mock_uninstall.assert_called_once_with(
                server=server, template=base_template
            )

    def test_uninstall_from_servers_success(self):
        """Test successful uninstall_from_servers"""
        server = self.server_test_1
        template = self.jet_template_test

        # Clean up any existing jets for this template/server combination
        existing_jets = server.jet_ids.filtered(
            lambda jet: jet.jet_template_id == template
        )
        if existing_jets:
            existing_jets.unlink()

        # Install template on server
        template.write({"server_ids": [(4, server.id)]})

        # Ensure no jets exist
        self.assertFalse(
            server.jet_ids.filtered(lambda jet: jet.jet_template_id == template),
            "No jets should exist for this template",
        )

        # Mock uninstall to verify it's called
        with patch(
            "odoo.addons.cetmix_tower_server.models.cx_tower_jet_template_install"
            ".CxTowerJetTemplateInstall.uninstall"
        ) as mock_uninstall:
            template.uninstall_from_servers(server, raise_if_not_possible=True)

            # Verify uninstall was called
            mock_uninstall.assert_called_once_with(server=server, template=template)

    def test_uninstall_from_servers_multiple_servers(self):
        """Test uninstall_from_servers with multiple servers"""
        server1 = self.server_test_1
        server2 = self.server_test_2
        template = self.jet_template_test

        # Clean up any existing jets for this template on both servers
        existing_jets_1 = server1.jet_ids.filtered(
            lambda jet: jet.jet_template_id == template
        )
        if existing_jets_1:
            existing_jets_1.unlink()
        existing_jets_2 = server2.jet_ids.filtered(
            lambda jet: jet.jet_template_id == template
        )
        if existing_jets_2:
            existing_jets_2.unlink()

        # Ensure no dependent templates are installed on these servers
        # Remove any templates that depend on this template from both servers
        for server in [server1, server2]:
            dependent_templates = server.jet_template_ids.filtered(
                lambda t: t.template_requires_ids.filtered(
                    lambda dep: dep.template_required_id == template
                )
            )
            if dependent_templates:
                # Remove server from dependent template's server_ids
                for dep_template in dependent_templates:
                    dep_template.write({"server_ids": [(3, server.id)]})

        # Install template on both servers
        template.write({"server_ids": [(4, server1.id), (4, server2.id)]})

        # Mock uninstall to verify it's called for both servers
        with patch(
            "odoo.addons.cetmix_tower_server.models.cx_tower_jet_template_install"
            ".CxTowerJetTemplateInstall.uninstall"
        ) as mock_uninstall:
            template.uninstall_from_servers(
                [server1, server2], raise_if_not_possible=True
            )

            # Verify uninstall was called twice (once per server)
            self.assertEqual(mock_uninstall.call_count, 2)
            # Verify both servers were called
            call_args_list = mock_uninstall.call_args_list
            servers_called = [call[1]["server"] for call in call_args_list]
            self.assertIn(server1, servers_called)
            self.assertIn(server2, servers_called)

    def test_uninstall_from_servers_mixed_validation_states(self):
        """Test uninstall_from_servers with mixed server validation states"""
        server1 = self.server_test_1
        server2 = self.server_test_2
        server3 = self.server_test_3
        template = self.jet_template_test

        # Server1: Template not installed
        template.write({"server_ids": [(5, 0, 0)]})

        # Server2: Jets still exist
        template.write({"server_ids": [(4, server2.id)]})
        self.Jet.create(
            {
                "name": "Test Jet Mixed Validation Server2",
                "reference": "test_jet_mixed_validation_server2",
                "jet_template_id": template.id,
                "server_id": server2.id,
            }
        )

        # Server3: Valid for uninstallation
        template.write({"server_ids": [(4, server3.id)]})

        # Mock uninstall and notify_warning
        with (
            patch(
                "odoo.addons.cetmix_tower_server.models.cx_tower_jet_template_install"
                ".CxTowerJetTemplateInstall.uninstall"
            ) as mock_uninstall,
            patch.object(self.env.user.__class__, "notify_warning") as mock_notify,
        ):
            template.uninstall_from_servers(
                [server1, server2, server3], raise_if_not_possible=False
            )

            # Verify warnings were shown for server1 and server2
            self.assertEqual(mock_notify.call_count, 2)

            # Verify uninstall was called only for server3
            mock_uninstall.assert_called_once_with(server=server3, template=template)
