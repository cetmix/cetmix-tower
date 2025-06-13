from .common import TestTowerCommon


class TestTowerJetTemplate(TestTowerCommon):
    """Test the Jet Template model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Remove template from all servers
        cls.jet_template_sample.write({"server_ids": [(6, 0, [])]})

    def test_install_on_servers_no_install_plan(self):
        """Test the installation of a Jet Template on a server."""

        # Ensure that jet template is installed on any server
        self.assertFalse(self.jet_template_sample.server_ids)
        self.assertFalse(self.jet_template_sample.plan_install_id)

        # Install the jet template on the server

        self.jet_template_sample.install_on_servers(self.server_test_1)

        # Ensure that jet template is installed on server
        self.assertIn(self.server_test_1, self.jet_template_sample.server_ids)

    def test_install_on_servers_with_install_plan(self):
        """
        Test the installation of a Jet Template on a server
        with an install plan.
        """

        # Ensure that there are no flight plan logs for the tes server
        self.assertFalse(self.server_test_1.plan_log_ids)

        # Set the install plan
        self.jet_template_sample.plan_install_id = self.plan_1

        # Install the jet template on the server
        self.jet_template_sample.install_on_servers(self.server_test_1)

        # Ensure that the flight plan log was created
        plan_log = self.server_test_1.plan_log_ids
        self.assertEqual(len(plan_log), 1)

        # Ensure that the flight plan log is for correct flight plan
        self.assertEqual(plan_log.plan_id, self.plan_1)

        # Ensure that the flight plan log is for correct jet template
        self.assertEqual(plan_log.jet_template_id, self.jet_template_sample)

        # Ensure that the flight plan log is successful
        self.assertEqual(plan_log.plan_status, 0)

    def test_install_on_servers_with_falling_install_plan(self):
        """
        Test the installation of a Jet Template on a server
        with a falling install plan.
        """

        # Ensure that there are no flight plan logs for the tes server
        self.assertFalse(self.server_test_1.plan_log_ids)

        # Change the flight plan command code to a failing one
        self.plan_1.line_ids.command_id.filtered(
            lambda c: c.action == "ssh_command"
        ).write({"code": "fail"})

        # Set the install plan
        self.jet_template_sample.plan_install_id = self.plan_1

        # Install the jet template on the server
        self.jet_template_sample.install_on_servers(self.server_test_1)

        # Ensure that the flight plan log was created
        plan_log = self.server_test_1.plan_log_ids
        self.assertEqual(len(plan_log), 1)

        # Ensure that the flight plan log is for correct flight plan
        self.assertEqual(plan_log.plan_id, self.plan_1)

        # Ensure that the flight plan log is for correct jet template
        self.assertEqual(plan_log.jet_template_id, self.jet_template_sample)

        # Ensure that the flight plan log is not successful
        self.assertNotEqual(plan_log.plan_status, 0)
