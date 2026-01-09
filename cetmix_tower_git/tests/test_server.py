try:
    from odoo.addons.queue_job.tests.common import trap_jobs
except ImportError:
    trap_jobs = None

from .common import CommonTest


class TestServer(CommonTest):
    """Test setting git project to server from plan line."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.GitProjectRel.create(
            {
                "git_project_id": cls.git_project_1.id,
                "server_id": cls.server_test_1.id,
                "file_id": cls.server_1_file_1.id,
            }
        )

    def test_server_creation_running_flight_plan(self):
        """Test that server is created with git project from plan line."""
        git_project = self.GitProject.create(
            {
                "name": "Test Git Project",
                "manager_ids": [(4, self.manager.id)],
            }
        )

        file_template = self.FileTemplate.create(
            {
                "name": "Git Config Template",
                "file_name": "repos.yaml",
                "server_dir": "/var/test",
                "code": "repositories:\n  test_repo:\n    "
                "url: https://github.com/test/repo.git\n    target: main",
            }
        )

        command = self.Command.create(
            {
                "name": "Create Git Config File",
                "action": "file_using_template",
                "file_template_id": file_template.id,
            }
        )

        flight_plan = self.Plan.create(
            {
                "name": "Git Project Setup Plan",
                "note": "Sets up a git project on the server",
            }
        )

        self.plan_line.create(
            {
                "plan_id": flight_plan.id,
                "command_id": command.id,
                "sequence": 10,
                "git_project_id": git_project.id,
            }
        )

        server_template = self.ServerTemplate.create(
            {
                "name": "Git Server Template",
                "ssh_port": 22,
                "ssh_username": "admin",
                "ssh_password": "password",
                "ssh_auth_mode": "p",
                "os_id": self.os_debian_10.id,
                "flight_plan_id": flight_plan.id,
                "manager_ids": [(4, self.manager.id)],
            }
        )

        action = server_template.action_create_server()

        # Open the wizard and fill in the data
        wizard = (
            self.env["cx.tower.server.template.create.wizard"]
            .with_context(**action["context"])
            .create(
                {
                    "name": "Git Server",
                    "ip_v4_address": "192.168.1.10",
                    "server_template_id": server_template.id,
                    "skip_host_key": True,
                }
            )
        )

        # If cetmix_tower_server_queue module is installed, test async processing
        if self.env["ir.module.module"].search_count(
            [("name", "=", "cetmix_tower_server_queue"), ("state", "=", "installed")]
        ):
            with trap_jobs() as trap:
                wizard.action_confirm()

                # Verify that jobs were created
                self.assertGreater(
                    len(trap.enqueued_jobs), 0, "Jobs should have been enqueued"
                )

                # Execute all trapped jobs to simulate async processing
                trap.perform_enqueued_jobs()
        else:
            wizard.action_confirm()

        # Now search for the created records after jobs have been executed
        server = self.Server.search(
            [
                ("name", "=", "Git Server"),
                ("server_template_id", "=", server_template.id),
            ]
        )
        self.assertEqual(len(server), 1, "Exactly one server should have been created")

        # Verify the file was created
        file = self.File.search(
            [("server_id", "=", server.id), ("name", "=", "repos.yaml")]
        )

        self.assertEqual(
            len(file), 1, "Exactly one git config file should have been created"
        )

        # Verify the git project relation exists
        git_project_rel = self.GitProjectRel.search(
            [
                ("server_id", "=", server.id),
                ("git_project_id", "=", git_project.id),
                ("file_id", "=", file.id),
            ]
        )

        self.assertEqual(
            len(git_project_rel), 1, "Exactly one git project relation should exist"
        )
        self.assertEqual(
            git_project_rel.file_id,
            file,
            "The related file should be the git config file",
        )
        self.assertEqual(
            git_project_rel.git_project_id,
            git_project,
            "The related git project should match the one in the flight plan",
        )
        self.assertEqual(
            git_project_rel.project_format,
            git_project._default_project_format(),
            "Project format should match the default format",
        )

    def test_file_creation_with_git_project_from_custom_values(self):
        """Test that git project relation is created when git project
        is provided from custom values in variable_values.
        """
        git_project = self.GitProject.create(
            {
                "name": "Test Git Project From Custom Values",
                "manager_ids": [(4, self.manager.id)],
            }
        )

        file_template = self.FileTemplate.create(
            {
                "name": "Git Config Template Custom Values",
                "file_name": "repos_custom.yaml",
                "server_dir": "/var/test",
                "code": "repositories:\n  test_repo:\n    "
                "url: https://github.com/test/repo.git\n    target: main",
            }
        )

        command = self.Command.create(
            {
                "name": "Create Git Config File Custom Values",
                "action": "file_using_template",
                "file_template_id": file_template.id,
            }
        )

        flight_plan = self.Plan.create(
            {
                "name": "Git Project Setup Plan Custom Values",
                "note": "Sets up a git project on the server from custom values",
            }
        )

        # Create plan line WITHOUT git_project_id set
        # The git project should come from custom values instead
        plan_line = self.plan_line.create(
            {
                "plan_id": flight_plan.id,
                "command_id": command.id,
                "sequence": 10,
            }
        )

        # Create plan log
        plan_log = self.env["cx.tower.plan.log"].create(
            {
                "server_id": self.server_test_1.id,
                "plan_id": flight_plan.id,
                "plan_line_executed_id": plan_line.id,
            }
        )

        # Create command log with variable_values containing __git_project__
        command_log = self.CommandLog.create(
            {
                "server_id": self.server_test_1.id,
                "command_id": command.id,
                "plan_log_id": plan_log.id,
                "variable_values": {"__git_project__": git_project.reference},
            }
        )

        # Call the method directly to test the custom values path
        file = self.server_test_1._command_runner_file_using_template_create_file(
            log_record=command_log, server_dir="/var/test"
        )

        # Verify the file was created
        self.assertTrue(file, "File should have been created")

        # Verify the git project relation exists
        git_project_rel = self.GitProjectRel.search(
            [
                ("server_id", "=", self.server_test_1.id),
                ("git_project_id", "=", git_project.id),
                ("file_id", "=", file.id),
            ]
        )

        self.assertEqual(
            len(git_project_rel), 1, "Exactly one git project relation should exist"
        )
        self.assertEqual(
            git_project_rel.file_id,
            file,
            "The related file should be the git config file",
        )
        self.assertEqual(
            git_project_rel.git_project_id,
            git_project,
            "The related git project should match the one from custom values",
        )
        self.assertEqual(
            git_project_rel.project_format,
            git_project._default_project_format(),
            "Project format should match the default format",
        )

    def test_file_creation_with_git_project_from_custom_values_priority(self):
        """Test that git project from custom values takes priority
        over git project from plan line.
        """
        git_project_custom = self.GitProject.create(
            {
                "name": "Test Git Project From Custom Values Priority",
                "manager_ids": [(4, self.manager.id)],
            }
        )

        git_project_plan_line = self.GitProject.create(
            {
                "name": "Test Git Project From Plan Line",
                "manager_ids": [(4, self.manager.id)],
            }
        )

        file_template = self.FileTemplate.create(
            {
                "name": "Git Config Template Priority",
                "file_name": "repos_priority.yaml",
                "server_dir": "/var/test",
                "code": "repositories:\n  test_repo:\n    "
                "url: https://github.com/test/repo.git\n    target: main",
            }
        )

        command = self.Command.create(
            {
                "name": "Create Git Config File Priority",
                "action": "file_using_template",
                "file_template_id": file_template.id,
            }
        )

        flight_plan = self.Plan.create(
            {
                "name": "Git Project Setup Plan Priority",
                "note": "Tests priority of custom values over plan line",
            }
        )

        # Create plan line WITH git_project_id set
        # But custom values should take priority
        plan_line = self.plan_line.create(
            {
                "plan_id": flight_plan.id,
                "command_id": command.id,
                "sequence": 10,
                "git_project_id": git_project_plan_line.id,
            }
        )

        # Create plan log
        plan_log = self.env["cx.tower.plan.log"].create(
            {
                "server_id": self.server_test_1.id,
                "plan_id": flight_plan.id,
                "plan_line_executed_id": plan_line.id,
            }
        )

        # Create command log with variable_values containing __git_project__
        # This should take priority over plan_line.git_project_id
        command_log = self.CommandLog.create(
            {
                "server_id": self.server_test_1.id,
                "command_id": command.id,
                "plan_log_id": plan_log.id,
                "variable_values": {"__git_project__": git_project_custom.reference},
            }
        )

        # Call the method directly to test the custom values path
        file = self.server_test_1._command_runner_file_using_template_create_file(
            log_record=command_log, server_dir="/var/test"
        )

        # Verify the file was created
        self.assertTrue(file, "File should have been created")

        # Verify the git project relation uses the git project from custom values
        # (not the one from plan line)
        git_project_rel = self.GitProjectRel.search(
            [
                ("server_id", "=", self.server_test_1.id),
                ("git_project_id", "=", git_project_custom.id),
                ("file_id", "=", file.id),
            ]
        )

        self.assertEqual(
            len(git_project_rel), 1, "Exactly one git project relation should exist"
        )
        self.assertEqual(
            git_project_rel.git_project_id,
            git_project_custom,
            "The related git project should match the one from custom values, "
            "not from plan line",
        )

        # Verify that the plan line git project was NOT used
        git_project_rel_plan_line = self.GitProjectRel.search(
            [
                ("server_id", "=", self.server_test_1.id),
                ("git_project_id", "=", git_project_plan_line.id),
                ("file_id", "=", file.id),
            ]
        )
        self.assertEqual(
            len(git_project_rel_plan_line),
            0,
            "No relation should exist for the plan line git project",
        )

    def test_server_get_servers_by_git_ref_success(self):
        """Check the success case of server.get_servers_by_git_ref"""

        # 1. URL only
        servers = self.Server.get_servers_by_git_ref(
            self.remote_github_https.repo_id.url
        )
        self.assertEqual(servers, self.server_test_1)

        # 2. Specific URL with specific head
        servers = self.Server.get_servers_by_git_ref(
            self.remote_github_https.repo_id.url, "123"
        )
        self.assertEqual(servers, self.server_test_1)

        # 2. Specific URL with specific head and head type
        servers = self.Server.get_servers_by_git_ref(
            self.remote_github_https.repo_id.url, "123", "pr"
        )
        self.assertEqual(servers, self.server_test_1)

    def test_server_get_servers_by_git_ref_no_match(self):
        """Check the no match case of server.get_servers_by_git_ref"""

        # 1. Repo link does not exist
        servers = self.Server.get_servers_by_git_ref(
            "https://github.com/other-org/other-repo.git", "main", "branch"
        )
        self.assertFalse(servers)

        # 2. Repo link exists, but remote does not exist
        servers = self.Server.get_servers_by_git_ref(
            self.repo_cetmix_tower.url, "3311", "pr"
        )
        self.assertFalse(servers)

        # 3. Repo link exists, but remote type does not exist
        servers = self.Server.get_servers_by_git_ref(
            self.repo_cetmix_tower.url, "main", "commit"
        )
        self.assertFalse(servers)
