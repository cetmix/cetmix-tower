# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from unittest.mock import patch

from .common import CommonTest


class TestGitProjectUpload(CommonTest):
    """Upload Git Project command action."""

    def _create_upload_command(self, path="/opt/git", file_name="repos.yml"):
        return self.Command.create(
            {
                "name": "Upload Git Project",
                "action": "git_project_upload",
                "path": path,
                "git_file_name": file_name,
            }
        )

    def _run_upload(self, command, jet=None, path="/opt/git"):
        """Run the upload runner with a log so the Jet is resolved."""
        if jet:
            log = self.CommandLog.start(
                jet.server_id.id,
                command.id,
                jet_id=jet.id,
            )
            server = jet.server_id
        else:
            server = self.server_test_1
            log = False
        server._command_runner_git_project_upload(
            command=command,
            log_record=log,
            rendered_command_path=path,
        )
        return log

    def test_selection_and_registry(self):
        actions = dict(self.Command._selection_action())
        self.assertIn("git_project_upload", actions)
        runners = self.server_test_1._get_command_runners()
        self.assertIn("git_project_upload", runners)
        self.assertEqual(
            runners["git_project_upload"].__func__.__name__,
            "_command_runner_git_project_upload",
        )

    def test_no_jet_and_no_project(self):
        command = self._create_upload_command()
        with patch.object(type(self.env["cx.tower.file"]), "action_push_to_server"):
            result = self.server_test_1._command_runner_git_project_upload(
                command=command,
                log_record=False,
                rendered_command_path="/opt/git",
            )
        self.assertEqual(result["status"], 0)
        self.assertIn("No Git Project", result["response"])
        self.assertFalse(
            self.File.search([("name", "=", "repos.yml"), ("source", "=", "tower")])
        )

        jet = self.jet_template_sample.create_jet(
            self.server_test_1, name="Upload Empty"
        )
        with patch.object(type(self.env["cx.tower.file"]), "action_push_to_server"):
            log = self._run_upload(command, jet=jet)
        self.assertEqual(log.command_status, 0)
        self.assertFalse(
            self.File.search([("jet_id", "=", jet.id), ("source", "=", "tower")])
        )

    def test_first_and_second_run(self):
        jet = self._create_jet_with_project("Upload Jet")
        command = self._create_upload_command()
        with patch.object(
            type(self.env["cx.tower.file"]),
            "action_push_to_server",
            return_value=True,
        ) as mocked:
            self._run_upload(command, jet=jet)
            self.assertEqual(mocked.call_count, 1)
        files = self.File.search([("jet_id", "=", jet.id), ("source", "=", "tower")])
        self.assertEqual(len(files), 1)
        self.assertTrue(files.auto_sync)
        self.assertEqual(len(files.git_project_rel_ids), 1)
        expected = jet.git_project_id._generate_code_git_aggregator(
            files.git_project_rel_ids
        )
        self.assertEqual(files.code, expected)

        with patch.object(
            type(self.env["cx.tower.file"]),
            "action_push_to_server",
            return_value=True,
        ) as mocked:
            self._run_upload(command, jet=jet)
            self.assertEqual(mocked.call_count, 1)
        files_after = self.File.search(
            [("jet_id", "=", jet.id), ("source", "=", "tower")]
        )
        self.assertEqual(files_after, files)
        self.assertEqual(len(files_after.git_project_rel_ids), 1)

    def test_changed_path_creates_new_file(self):
        jet = self._create_jet_with_project("Upload Path Jet")
        command = self._create_upload_command(path="/opt/git", file_name="a.yml")
        with patch.object(type(self.env["cx.tower.file"]), "action_push_to_server"):
            self._run_upload(command, jet=jet, path="/opt/git")
            command.write({"git_file_name": "b.yml"})
            self._run_upload(command, jet=jet, path="/opt/git")
        files = self.File.search([("jet_id", "=", jet.id), ("source", "=", "tower")])
        self.assertEqual(len(files), 2)

    def test_empty_path_reuses_file(self):
        jet = self._create_jet_with_project("Upload Empty Path")
        command = self._create_upload_command(path="", file_name="repos.yml")
        with patch.object(type(self.env["cx.tower.file"]), "action_push_to_server"):
            self._run_upload(command, jet=jet, path="")
            self._run_upload(command, jet=jet, path="")
        files = self.File.search([("jet_id", "=", jet.id), ("source", "=", "tower")])
        self.assertEqual(len(files), 1)
        self.assertEqual(files.full_server_path, "/repos.yml")

    def test_variable_file_name_reused(self):
        jet = self._create_jet_with_project("Upload Var Jet")
        variable = self.Variable.create({"name": "git_yml_name"})
        self.VariableValue.create(
            {
                "variable_id": variable.id,
                "value_char": "my_repos",
                "jet_id": jet.id,
            }
        )
        command = self._create_upload_command(
            path="/opt/git",
            file_name="{{ git_yml_name }}.yml",
        )
        self.assertIn(variable, command.variable_ids)
        with patch.object(type(self.env["cx.tower.file"]), "action_push_to_server"):
            self._run_upload(command, jet=jet)
            self._run_upload(command, jet=jet)
        files = self.File.search([("jet_id", "=", jet.id), ("source", "=", "tower")])
        self.assertEqual(len(files), 1)
        self.assertEqual(len(files.git_project_rel_ids), 1)
        self.assertTrue(files.full_server_path.endswith("my_repos.yml"))

    def test_legacy_path_does_not_use_jet_project(self):
        jet = self._create_jet_with_project("Legacy File Jet")
        template = self.FileTemplate.create(
            {
                "name": "Plain Template",
                "file_name": "plain.txt",
                "server_dir": "/tmp",
                "code": "plain",
            }
        )
        command = self.Command.create(
            {
                "name": "Create File",
                "action": "file_using_template",
                "file_template_id": template.id,
            }
        )
        log = self.CommandLog.start(
            jet.server_id.id,
            command.id,
            jet_id=jet.id,
        )
        with patch.object(type(self.env["cx.tower.file"]), "action_push_to_server"):
            jet.server_id._command_runner_file_using_template(
                log_record=log,
                rendered_command_path="/tmp",
                command=command,
            )
        files = self.File.search([("jet_id", "=", jet.id), ("source", "=", "tower")])
        self.assertTrue(files)
        self.assertFalse(files.git_project_rel_ids)
        self.assertNotEqual(files.git_project_id, jet.git_project_id)

    def test_push_not_called_during_create(self):
        jet = self._create_jet_with_project("Upload Create Push")
        command = self._create_upload_command()
        original_create = type(self.env["cx.tower.file"]).create
        push = patch.object(
            type(self.env["cx.tower.file"]),
            "action_push_to_server",
            return_value=True,
        )

        with push as mocked:

            def create_wrapper(records, vals_list):
                self.assertEqual(mocked.call_count, 0)
                return original_create(records, vals_list)

            with patch.object(
                type(self.env["cx.tower.file"]), "create", create_wrapper
            ):
                self._run_upload(command, jet=jet)
            self.assertGreaterEqual(mocked.call_count, 1)
