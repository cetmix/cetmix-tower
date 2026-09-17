from unittest.mock import patch

from odoo.addons.cetmix_tower_server.models.constants import FILE_CREATION_FAILED
from odoo.addons.cetmix_tower_server.tests.common import TestTowerCommon
from odoo.addons.queue_job.tests.common import trap_jobs

_UPLOAD_FILE = (
    "odoo.addons.cetmix_tower_server.models.cx_tower_server.CxTowerServer.upload_file"
)
_DOWNLOAD_FILE = (
    "odoo.addons.cetmix_tower_server.models.cx_tower_server.CxTowerServer.download_file"
)


class TestTowerFileUsingTemplateQueue(TestTowerCommon):
    """``file_using_template`` must use one command job, not a file job."""

    def _job_method_names(self, jobs):
        """Return method names of trapped jobs.

        Args:
            jobs (list): ``queue_job.job.Job`` instances.

        Returns:
            list: Method name strings.
        """
        return [job.method_name for job in jobs]

    def _latest_command_log(self, command):
        """Return the newest command log for ``command`` on the test server.

        Args:
            command (cx.tower.command): Command whose log to fetch.

        Returns:
            cx.tower.command.log: Newest matching log, or empty recordset.
        """
        return self.CommandLog.search(
            [
                ("server_id", "=", self.server_test_1.id),
                ("command_id", "=", command.id),
            ],
            order="id desc",
            limit=1,
        )

    def _assert_no_second_wave(self, trap):
        """Assert performing the command job spawned no further jobs.

        Args:
            trap (JobsTrap): Active ``trap_jobs`` context after
                ``perform_enqueued_jobs``.
        """
        self.assertFalse(
            trap.enqueued_jobs,
            f"Performing the command job must not enqueue a second wave, got "
            f"{self._job_method_names(trap.enqueued_jobs)}",
        )

    def test_tower_source_enqueues_only_command_job(self):
        """Tower-source command: one command job; transfer runs inside it."""
        command = self.command_create_file_with_template_tower_source
        with (
            trap_jobs() as trap,
            patch(_UPLOAD_FILE, return_value="ok"),
        ):
            self.server_test_1.run_command(command)
            log_record = self._latest_command_log(command)
            self.assertTrue(log_record.is_running)
            self.assertEqual(
                self._job_method_names(trap.enqueued_jobs),
                ["_queue_command_runner_wrapper"],
            )

            trap.perform_enqueued_jobs()
            log_record.invalidate_recordset()

            self.assertFalse(log_record.is_running)
            self.assertEqual(log_record.command_status, 0)
            self.assertEqual(
                log_record.command_response,
                "File created and uploaded successfully",
            )
            self._assert_no_second_wave(trap)

    def test_server_source_enqueues_only_command_job(self):
        """Server-source command: one command job; no ``_do_download`` job."""
        command = self.command_create_file_with_template_server_source

        def download_file(this, remote_path):
            return b"Hello, world!"

        cx_tower_server_obj = self.registry["cx.tower.server"]
        with (
            trap_jobs() as trap,
            patch.object(cx_tower_server_obj, "download_file", download_file),
        ):
            self.server_test_1.run_command(command)
            log_record = self._latest_command_log(command)
            self.assertTrue(log_record.is_running)
            self.assertEqual(
                self._job_method_names(trap.enqueued_jobs),
                ["_queue_command_runner_wrapper"],
            )

            trap.perform_enqueued_jobs()
            log_record.invalidate_recordset()

            self.assertFalse(log_record.is_running)
            self.assertEqual(log_record.command_status, 0)
            self.assertEqual(
                log_record.command_response,
                "File created and uploaded successfully",
            )
            self._assert_no_second_wave(trap)

    def test_transfer_error_fails_command_log(self):
        """A transfer exception finishes the log with FILE_CREATION_FAILED."""
        command = self.command_create_file_with_template_tower_source
        with (
            trap_jobs() as trap,
            patch(_UPLOAD_FILE, side_effect=Exception("SFTP failed")),
        ):
            self.server_test_1.run_command(command)
            log_record = self._latest_command_log(command)
            self.assertTrue(log_record.is_running)

            trap.perform_enqueued_jobs()
            log_record.invalidate_recordset()

            self.assertFalse(log_record.is_running)
            self.assertEqual(log_record.command_status, FILE_CREATION_FAILED)
            self._assert_no_second_wave(trap)

    def test_auto_sync_template_does_not_enqueue_file_job(self):
        """``auto_sync`` during create_file must not add a file job."""
        template = self.FileTemplate.create(
            {
                "name": "Queue auto-sync template",
                "file_name": "queue_auto_sync.txt",
                "source": "tower",
                "server_dir": "/tmp/queue-auto-sync",
                "code": "Hello, auto-sync!",
                "auto_sync": True,
            }
        )
        command = self.Command.create(
            {
                "name": "Create auto-sync file with template",
                "path": "/tmp/queue-auto-sync",
                "action": "file_using_template",
                "file_template_id": template.id,
                "if_file_exists": "raise",
            }
        )
        with (
            trap_jobs() as trap,
            patch(_UPLOAD_FILE, return_value="ok") as mock_upload,
        ):
            self.server_test_1.run_command(command)
            self.assertEqual(
                self._job_method_names(trap.enqueued_jobs),
                ["_queue_command_runner_wrapper"],
            )
            trap.perform_enqueued_jobs()
            self._assert_no_second_wave(trap)
            mock_upload.assert_called_once()

    def test_auto_sync_server_template_downloads_once(self):
        """``auto_sync`` server create must download exactly once."""
        template = self.FileTemplate.create(
            {
                "name": "Queue auto-sync server template",
                "file_name": "queue_auto_sync_dl.txt",
                "source": "server",
                "server_dir": "/tmp/queue-auto-sync-dl",
                "auto_sync": True,
            }
        )
        command = self.Command.create(
            {
                "name": "Create auto-sync server file with template",
                "path": "/tmp/queue-auto-sync-dl",
                "action": "file_using_template",
                "file_template_id": template.id,
                "if_file_exists": "raise",
            }
        )
        with (
            trap_jobs() as trap,
            patch(_DOWNLOAD_FILE, return_value=b"ok") as mock_download,
        ):
            self.server_test_1.run_command(command)
            self.assertEqual(
                self._job_method_names(trap.enqueued_jobs),
                ["_queue_command_runner_wrapper"],
            )
            trap.perform_enqueued_jobs()
            self._assert_no_second_wave(trap)
            mock_download.assert_called_once()

    def test_skip_path_does_not_enqueue_file_job(self):
        """Existing file with ``if_file_exists=skip``: command job only."""
        command = self.command_create_file_with_template_tower_source
        command.write({"if_file_exists": "skip"})
        file_template = command.file_template_id
        orig_file = file_template.create_file(
            server=self.server_test_1,
            server_dir=file_template.server_dir,
            if_file_exists="skip",
        )
        self.assertTrue(orig_file)

        with trap_jobs() as trap:
            self.server_test_1.run_command(command)
            self.assertEqual(
                self._job_method_names(trap.enqueued_jobs),
                ["_queue_command_runner_wrapper"],
            )
            trap.perform_enqueued_jobs()
            log_record = self._latest_command_log(command)
            self.assertFalse(log_record.is_running)
            self.assertEqual(log_record.command_status, 0)
            self.assertEqual(
                log_record.command_response,
                "File already exists on server. Upload skipped",
            )
            self._assert_no_second_wave(trap)

    def test_overwrite_busy_file_fails_command_log(self):
        """Overwrite of a busy file must fail the command, not skip transfer."""
        command = self.command_create_file_with_template_tower_source
        command.write({"if_file_exists": "overwrite"})
        file_template = command.file_template_id
        existing = file_template.create_file(
            server=self.server_test_1,
            server_dir=file_template.server_dir,
            if_file_exists="skip",
        )
        existing.write({"is_being_processed": True})

        with trap_jobs() as trap:
            self.server_test_1.run_command(command)
            trap.perform_enqueued_jobs()
            log_record = self._latest_command_log(command)
            self.assertFalse(log_record.is_running)
            self.assertEqual(log_record.command_status, FILE_CREATION_FAILED)
            self._assert_no_second_wave(trap)
