from datetime import timedelta
from unittest.mock import patch

from odoo.fields import Datetime
from odoo.tools import mute_logger

from odoo.addons.cetmix_tower_server.tests.common import TestTowerCommon


class TestTowerCommand(TestTowerCommon):
    """Test suite for verifying zombie command detection and related
    queue job cancellation.

    Tests in this class verify that commands which have been running
    longer than the timeout are properly detected as zombies, and their
    associated queue jobs are cancelled.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Set command timeout to 10 seconds
        cls.env["ir.config_parameter"].sudo().set_param(
            "cetmix_tower_server.command_timeout", "10"
        )
        # Set old time to 20 seconds ago (older than timeout)
        # to simulate running command in past
        now = Datetime.now()
        cls.old_time = now - timedelta(seconds=20)

    def _patch_command_runner(self, command_type, runner_method):
        """Helper to patch a command runner to simulate a zombie command.

        Args:
            command_type: Type of command runner to patch ('ssh' or 'python_code')
            runner_method: Original method to wrap

        Returns:
            A context manager that applies the patch
        """

        def _wrapper(*args, **kwargs):
            # Modify args to disable log record finishing
            args = list(args)
            if len(args) > 1:
                args[1] = False  # Set log_record to False
            return runner_method(*args, **kwargs)

        return patch.object(
            self.registry["cx.tower.server"],
            f"_command_runner_{command_type}",
            _wrapper,
        )

    def _verify_zombie_command_job_cancellation(self, command_action):
        """Verify zombie command is detected and job is cancelled.

        Args:
            command_action: Action type ('ssh_command' or 'python_code')
        """
        # check zombie command logs
        domain = [
            ("is_running", "=", True),
            ("start_date", "=", self.old_time),
            ("command_action", "=", command_action),
        ]
        zombie_command_logs = self.env["cx.tower.command.log"].search(domain)

        self.assertEqual(
            len(zombie_command_logs), 1, "Zombie command log should be created"
        )
        self.assertTrue(
            zombie_command_logs.queue_job_id,
            "Zombie command log should have queue job",
        )

        job = zombie_command_logs.queue_job_id
        self.assertTrue(job.exists(), "Zombie command job should exist")

        self.assertEqual(job.state, "pending", "Zombie command job should be pending")

        # run process to kill zombie command
        self.server_test_1._check_zombie_commands()

        # check that command log is cancelled
        self.assertEqual(
            job.state, "cancelled", "Zombie command job should be cancelled"
        )

    def test_check_zombie_ssh_command_queue(self):
        """
        Test that zombie ssh command is killed and job is cancelled
        """
        # Create test commands
        ssh_command = self.Command.create(
            {
                "name": "Test SSH Command",
                "code": "ls -la",
                "action": "ssh_command",
            }
        )

        # patch command runner to not finish log record
        cx_tower_server_obj = self.registry["cx.tower.server"]
        _command_runner_ssh_super = cx_tower_server_obj._command_runner_ssh

        with self._patch_command_runner("ssh", _command_runner_ssh_super):
            # run zombie command with log creation in past
            self.server_test_1.run_command(
                ssh_command, log={"start_date": self.old_time}
            )

        # check zombie command logs
        self._verify_zombie_command_job_cancellation("ssh_command")

    @mute_logger("py.warnings")
    def test_check_zombie_python_command_queue(self):
        """
        Test that zombie python command is killed and job is cancelled
        """
        # Create test commands
        python_command = self.Command.create(
            {
                "name": "Test Python Command",
                "code": "print('test')",
                "action": "python_code",
            }
        )

        # patch command runner to not finish log record
        cx_tower_server_obj = self.registry["cx.tower.server"]
        _command_runner_python_code_super = (
            cx_tower_server_obj._command_runner_python_code
        )

        with self._patch_command_runner(
            "python_code", _command_runner_python_code_super
        ):
            # run zombie command with log creation in past
            self.server_test_1.run_command(
                python_command, log={"start_date": self.old_time}
            )

        # check zombie command logs
        self._verify_zombie_command_job_cancellation("python_code")
