# Copyright (C) 2022 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from unittest.mock import MagicMock, patch

from odoo.exceptions import ValidationError
from odoo.fields import Datetime

from ..models.constants import NO_COMMAND_RUNNER_FOUND
from .common import TestTowerCommon


class TestTowerCommandRunnerRegistry(TestTowerCommon):
    """Tests for ``cx.tower.server._get_command_runners`` dispatch."""

    _EXPECTED_RUNNER_METHODS = {
        "ssh_command": "_command_runner_ssh",
        "file_using_template": "_command_runner_file_using_template",
        "python_code": "_command_runner_python_code",
        "jet_action": "_command_runner_jet_action",
        "create_waypoint": "_command_runner_create_waypoint",
        "plan": "_command_runner_flight_plan",
    }

    def _patch_extension_runner(self, fake_runner):
        """Patch selection and registry so ``ext_action`` is a valid action.

        Args:
            fake_runner (callable): Runner mapped to ``ext_action``.

        Returns:
            tuple: Patch context managers for selection and runners.
        """
        command_model = self.registry["cx.tower.command"]
        server_model = self.registry["cx.tower.server"]
        original_selection = command_model._selection_action
        original_get = server_model._get_command_runners

        def _selection(this):
            return list(original_selection(this)) + [("ext_action", "Extension")]

        def _get_runners(this):
            runners = original_get(this)
            runners["ext_action"] = fake_runner
            return runners

        return (
            patch.object(command_model, "_selection_action", _selection),
            patch.object(server_model, "_get_command_runners", _get_runners),
        )

    def test_registry_keys_match_selection_action(self):
        """Registry keys are exactly the command action selection values."""
        selection_actions = {
            value for value, _label in self.Command._selection_action()
        }
        self.assertEqual(
            set(self.server_test_1._get_command_runners()),
            selection_actions,
        )

    def test_registry_entries_are_named_bound_methods(self):
        """Every registry value is the bound method named in the default map."""
        server_model = self.registry["cx.tower.server"]
        runners = self.server_test_1._get_command_runners()
        self.assertEqual(set(runners), set(self._EXPECTED_RUNNER_METHODS))
        for action, method_name in self._EXPECTED_RUNNER_METHODS.items():
            runner = runners[action]
            self.assertTrue(callable(runner), f"{action} runner must be callable")
            self.assertEqual(runner.__name__, method_name)
            self.assertIs(runner.__func__, getattr(server_model, method_name))
        self.assertTrue(
            runners["plan"].__self__.env.context.get("prevent_plan_recursion"),
            "plan runner must bind a recordset with prevent_plan_recursion",
        )

    def test_no_runner_with_log_finishes_not_found(self):
        """Empty registry finishes the log with NO_COMMAND_RUNNER_FOUND."""
        log = self.CommandLog.create(
            {
                "server_id": self.server_test_1.id,
                "command_id": self.command_create_dir.id,
                "start_date": Datetime.now(),
            }
        )
        with patch.object(
            self.registry["cx.tower.server"],
            "_get_command_runners",
            return_value={},
        ):
            self.server_test_1._command_runner(
                command=self.command_create_dir,
                log_record=log,
                rendered_command_code="ls",
            )
        log.invalidate_recordset()
        self.assertEqual(log.command_status, NO_COMMAND_RUNNER_FOUND)
        self.assertFalse(log.is_running)

    def test_no_runner_without_log_raises_validation_error(self):
        """Empty registry with no_command_log raises ValidationError."""
        with (
            patch.object(
                self.registry["cx.tower.server"],
                "_get_command_runners",
                return_value={},
            ),
            self.assertRaises(ValidationError) as err,
        ):
            self.server_test_1.with_context(no_command_log=True).run_command(
                self.command_create_dir
            )
        self.assertIn("ssh_command", str(err.exception))

    def test_extension_action_writes_server_status_without_log(self):
        """A registry-added action still writes server_status when there is no log."""
        fake_runner = MagicMock(
            return_value={"status": 0, "response": "ok", "error": None}
        )
        selection_patch, runners_patch = self._patch_extension_runner(fake_runner)
        with selection_patch, runners_patch:
            command = self.Command.create(
                {
                    "name": "Extension action status",
                    "action": "ext_action",
                    "server_status": "stopping",
                }
            )
            self.server_test_1.with_context(no_command_log=True).run_command(command)
        self.assertEqual(self.server_test_1.status, "stopping")
        fake_runner.assert_called()

    def test_extension_action_with_log_does_not_write_server_status(self):
        """A registry-added action with a log does not write server_status."""
        fake_runner = MagicMock(
            return_value={"status": 0, "response": "ok", "error": None}
        )
        selection_patch, runners_patch = self._patch_extension_runner(fake_runner)
        with selection_patch, runners_patch:
            command = self.Command.create(
                {
                    "name": "Extension action with log",
                    "action": "ext_action",
                    "server_status": "stopping",
                }
            )
            log = self.CommandLog.create(
                {
                    "server_id": self.server_test_1.id,
                    "command_id": command.id,
                    "start_date": Datetime.now(),
                }
            )
            original_status = self.server_test_1.status
            self.server_test_1._command_runner(
                command=command,
                log_record=log,
                rendered_command_code="",
            )
        self.assertEqual(self.server_test_1.status, original_status)
        self.assertTrue(log.is_running)

    def test_nested_plan_does_not_leak_uniform_names(self):
        """Parent runner kwargs are not forwarded into the child run_command."""
        child_plan = self.Plan.create({"name": "Registry child plan"})
        self.plan_line.create(
            {
                "sequence": 10,
                "plan_id": child_plan.id,
                "command_id": self.command_create_dir.id,
            }
        )
        plan_command = self.Command.create(
            {
                "name": "Run registry child plan",
                "action": "plan",
                "flight_plan_id": child_plan.id,
            }
        )

        server_model = self.registry["cx.tower.server"]
        plan_model = self.registry["cx.tower.plan"]
        original_run_command = server_model.run_command
        original_run_single = plan_model._run_single
        ssh_sentinel = object()
        child_calls = []
        command_plan_servers = []

        def _run_command(
            server,
            command,
            path=None,
            sudo=None,
            ssh_connection=None,
            jet_template=None,
            jet=None,
            **kwargs,
        ):
            if command.action == "ssh_command":
                # ssh_connection is a run_command parameter, so a leak binds
                # here instead of landing in **kwargs.
                child_calls.append((kwargs, ssh_connection))
            return original_run_command(
                server,
                command,
                path=path,
                sudo=sudo,
                ssh_connection=ssh_connection,
                jet_template=jet_template,
                jet=jet,
                **kwargs,
            )

        def _run_single(plan, server, jet_template=None, jet=None, **kwargs):
            if plan.env.context.get("from_command"):
                command_plan_servers.append(server)
            return original_run_single(
                plan,
                server,
                jet_template=jet_template,
                jet=jet,
                **kwargs,
            )

        with (
            self._patch_defer_handlers([]),
            patch.object(server_model, "run_command", _run_command),
            patch.object(plan_model, "_run_single", _run_single),
        ):
            self.server_test_1.run_command(plan_command, ssh_connection=ssh_sentinel)

        self.assertTrue(child_calls, "Child SSH run_command must be called")
        child_kwargs, child_ssh_connection = child_calls[0]
        leaked = {
            "rendered_command_code",
            "rendered_command_path",
        }.intersection(child_kwargs)
        self.assertFalse(leaked, "Parent runner names leaked into child kwargs")
        self.assertIsNot(
            child_ssh_connection,
            ssh_sentinel,
            "parent ssh_connection leaked into child run_command",
        )

        self.assertTrue(
            command_plan_servers,
            "Flight plan runner must call _run_single with from_command",
        )
        self.assertTrue(
            command_plan_servers[0].env.context.get("prevent_plan_recursion"),
            "prevent_plan_recursion must be on the server env passed to _run_single",
        )
