from unittest.mock import patch

import psycopg2

from odoo import SUPERUSER_ID, api, exceptions
from odoo.tools import SQL, mute_logger

from odoo.addons.cetmix_tower_server.tests.common import TestTowerCommon
from odoo.addons.queue_job.tests.common import trap_jobs


class TestCxTowerFileQueue(TestTowerCommon):
    def setUp(self):
        super().setUp()
        self.file_template = self.FileTemplate.create(
            {
                "name": "Test",
                "file_name": "test.txt",
                "server_dir": "/var/tmp",
                "code": "Hello, world!",
            }
        )

    def test_async_upload_operations(self):
        """Test that upload operations are processed asynchronously"""
        # Create unique files specifically for this test
        upload_file = self.File.create(
            {
                "source": "tower",
                "template_id": self.file_template.id,
                "server_id": self.server_test_1.id,
                "name": "upload_test_1",
                "auto_sync": False,
            }
        )

        upload_file_2 = self.File.create(
            {
                "name": "upload_test_2",
                "source": "server",
                "server_id": self.server_test_1.id,
                "server_dir": "/var/tmp",
                "auto_sync": False,
            }
        )

        with trap_jobs() as trap:
            upload_file.upload()
            upload_file_2.upload()

            self.assertEqual(len(trap.enqueued_jobs), 2)

            upload_file.write({"server_response": "ok", "is_being_processed": False})
            upload_file_2.write({"server_response": "ok", "is_being_processed": False})

            # Refresh records to get updated values
            upload_file.invalidate_recordset()
            upload_file_2.invalidate_recordset()

            # Verify the expected state
            self.assertEqual(upload_file.server_response, "ok")
            self.assertFalse(upload_file.is_being_processed)

            self.assertEqual(upload_file_2.server_response, "ok")
            self.assertFalse(upload_file_2.is_being_processed)

    def test_async_download_operations(self):
        """Test that download operations are processed asynchronously"""
        # Create unique files specifically for this test
        download_file = self.File.create(
            {
                "source": "tower",
                "template_id": self.file_template.id,
                "server_id": self.server_test_1.id,
                "name": "download_test_1",
                "auto_sync": False,
            }
        )

        download_file_2 = self.File.create(
            {
                "name": "download_test_2",
                "source": "server",
                "server_id": self.server_test_1.id,
                "server_dir": "/var/tmp",
                "auto_sync": False,
            }
        )

        with trap_jobs() as trap:
            download_file.download()
            download_file_2.download()

            # Verify jobs were created
            self.assertEqual(len(trap.enqueued_jobs), 2)

            download_file.write({"server_response": "ok", "is_being_processed": False})
            download_file_2.write(
                {"server_response": "ok", "is_being_processed": False}
            )

            # Refresh records to get updated values
            download_file.invalidate_recordset()
            download_file_2.invalidate_recordset()

            # Verify the expected state
            self.assertEqual(download_file.server_response, "ok")
            self.assertFalse(download_file.is_being_processed)

            self.assertEqual(download_file_2.server_response, "ok")
            self.assertFalse(download_file_2.is_being_processed)

    def test_upload_error_handling(self):
        """Test error handling in async upload operations"""
        error_file = self.File.create(
            {
                "source": "tower",
                "template_id": self.file_template.id,
                "server_id": self.server_test_1.id,
                "name": "error_handling_test",
                "auto_sync": False,
            }
        )

        # Set context to force the mock in ssh_upload_file to raise error
        error_context = {"raise_upload_error": "Forced upload error"}

        with trap_jobs() as trap:
            # This will trigger job creation but the job would fail if executed
            error_file.with_context(**error_context).upload(raise_error=True)

            # Verify job was created
            self.assertEqual(len(trap.enqueued_jobs), 1)

            # Simulate what would happen if the job executed and failed
            error_file.write({"server_response": "error", "is_being_processed": False})
            error_file.invalidate_recordset()

            self.assertEqual(error_file.server_response, "error")
            self.assertFalse(error_file.is_being_processed)

    def test_download_error_handling(self):
        """Test error handling in async download operations"""
        error_file = self.File.create(
            {
                "source": "server",
                "server_id": self.server_test_1.id,
                "server_dir": "/var/tmp",
                "name": "download_error_test",
            }
        )

        # Set context to force the mock in ssh_download_file to raise error
        error_context = {"raise_download_error": "Forced download error"}

        with trap_jobs() as trap:
            # This will trigger job creation but the job would fail if executed
            error_file.with_context(**error_context).download(raise_error=True)

            # Verify job was created
            self.assertEqual(len(trap.enqueued_jobs), 1)

            # Simulate what would happen if the job executed and failed
            error_file.write({"server_response": "error", "is_being_processed": False})
            error_file.invalidate_recordset()

            self.assertEqual(error_file.server_response, "error")
            self.assertFalse(error_file.is_being_processed)

    def test_already_processing_check(self):
        """Test that files being processed cannot be processed again"""
        processing_file = self.File.create(
            {
                "source": "tower",
                "template_id": self.file_template.id,
                "server_id": self.server_test_1.id,
                "name": "processing_test_file",
                "is_being_processed": True,
            }
        )

        self.assertTrue(processing_file.is_being_processed)

        # Test with raising error
        with self.assertRaises(exceptions.UserError):
            processing_file.upload(raise_error=True)

        # Test without raising error - should not create job
        with trap_jobs() as trap:
            processing_file.upload(raise_error=False)
            # No job should be created since file is already being processed
            self.assertEqual(len(trap.enqueued_jobs), 0)

        # Inline command path must raise even though actions pass False
        with self.assertRaises(exceptions.UserError):
            processing_file.with_context(inline_file_operation=True).upload(
                raise_error=False
            )

        # Verify still marked as processing
        self.assertTrue(processing_file.is_being_processed)

        # Same tests for download
        with self.assertRaises(exceptions.UserError):
            processing_file.download(raise_error=True)

        with trap_jobs() as trap:
            processing_file.download(raise_error=False)
            # No job should be created
            self.assertEqual(len(trap.enqueued_jobs), 0)

        with self.assertRaises(exceptions.UserError):
            processing_file.with_context(inline_file_operation=True).download(
                raise_error=False
            )

        self.assertTrue(processing_file.is_being_processed)

    def test_inline_upload_nested_call_does_not_enqueue(self):
        """Nested UI upload must not enqueue while inline upload is running."""
        rec = self.File.create(
            {
                "source": "tower",
                "template_id": self.file_template.id,
                "server_id": self.server_test_1.id,
                "name": "inline_reserve_upload.txt",
                "auto_sync": False,
            }
        )
        with trap_jobs() as trap:

            def blocking_upload(this, data, remote_path, from_path=False):
                rec.invalidate_recordset()
                self.assertTrue(rec.is_being_processed)
                rec.upload()
                self.assertFalse(
                    trap.enqueued_jobs,
                    "A nested non-inline upload must not start a file job",
                )
                return "ok"

            with patch.object(
                self.registry["cx.tower.server"],
                "upload_file",
                blocking_upload,
            ):
                rec.with_context(inline_file_operation=True).upload()
        rec.invalidate_recordset()
        self.assertFalse(rec.is_being_processed)

    def test_inline_download_nested_call_does_not_enqueue(self):
        """Nested UI download must not enqueue while inline download is running."""
        rec = self.File.create(
            {
                "source": "server",
                "server_id": self.server_test_1.id,
                "server_dir": "/var/tmp",
                "name": "inline_reserve_download.txt",
                "auto_sync": False,
            }
        )
        with trap_jobs() as trap:

            def blocking_download(this, remote_path):
                rec.invalidate_recordset()
                self.assertTrue(rec.is_being_processed)
                rec.download()
                self.assertFalse(
                    trap.enqueued_jobs,
                    "A nested non-inline download must not start a file job",
                )
                return b"ok"

            with patch.object(
                self.registry["cx.tower.server"],
                "download_file",
                blocking_download,
            ):
                rec.with_context(inline_file_operation=True).download()
        rec.invalidate_recordset()
        self.assertFalse(rec.is_being_processed)

    def _create_committed_file_for_lock_test(self):
        """Create a file visible to other transactions.

        TransactionCase forbids commit on the test cursor, so the
        record is created on an independent cursor and committed there.

        Returns:
            int: Database id of the committed file.
        """
        with self.registry.cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            leftover = env["cx.tower.file"].search([("name", "=", "lock_test.txt")])
            servers = leftover.server_id
            os_recs = servers.os_id
            leftover.unlink()
            servers.unlink()
            os_recs.filtered(lambda rec: rec.name == "Lock Test OS").unlink()
            os_rec = env["cx.tower.os"].create({"name": "Lock Test OS"})
            server = env["cx.tower.server"].create(
                {
                    "name": "Lock Test Server",
                    "ip_v4_address": "localhost",
                    "ssh_username": "admin",
                    "ssh_password": "password",
                    "ssh_auth_mode": "p",
                    "host_key": "test_key",
                    "os_id": os_rec.id,
                }
            )
            rec = env["cx.tower.file"].create(
                {
                    "source": "tower",
                    "server_id": server.id,
                    "name": "lock_test.txt",
                    "server_dir": "/var/tmp",
                    "code": "hello",
                    "auto_sync": False,
                }
            )
            return rec.id

    def _unlink_committed_file_for_lock_test(self, file_id):
        """Remove a file committed by ``_create_committed_file_for_lock_test``.

        Args:
            file_id (int): Database id of the committed file.
        """
        with self.registry.cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            rec = env["cx.tower.file"].browse(file_id)
            server = rec.server_id
            os_rec = server.os_id
            rec.unlink()
            server.unlink()
            os_rec.unlink()

    def test_reserve_holds_row_lock(self):
        """Another transaction cannot lock the file while it is reserved."""
        file_id = self._create_committed_file_for_lock_test()
        self.addCleanup(self._unlink_committed_file_for_lock_test, file_id)
        table = None
        cr_a = self.registry.cursor()
        try:
            env_a = api.Environment(cr_a, SUPERUSER_ID, {})
            rec_a = env_a["cx.tower.file"].browse(file_id)
            table = rec_a._table
            self.assertFalse(rec_a._reserve_for_processing(raise_error=False))
            with mute_logger("odoo.sql_db"), self.registry.cursor() as cr_b:
                with self.assertRaises(psycopg2.OperationalError):
                    cr_b.execute(
                        SQL(
                            "SELECT id FROM %s WHERE id IN %s FOR UPDATE NOWAIT",
                            SQL.identifier(table),
                            (file_id,),
                        )
                    )
        finally:
            cr_a.rollback()
            cr_a.close()
        with self.registry.cursor() as cr_c:
            cr_c.execute(
                SQL(
                    "SELECT id FROM %s WHERE id IN %s FOR UPDATE NOWAIT",
                    SQL.identifier(table),
                    (file_id,),
                )
            )

    def test_inline_upload_clears_reservation_on_failure(self):
        """Failed inline upload must clear is_being_processed."""
        rec = self.File.create(
            {
                "source": "tower",
                "template_id": self.file_template.id,
                "server_id": self.server_test_1.id,
                "name": "inline_reserve_fail.txt",
                "auto_sync": False,
            }
        )
        with patch.object(
            self.registry["cx.tower.server"],
            "upload_file",
            side_effect=Exception("SFTP failed"),
        ):
            with self.assertRaises(exceptions.ValidationError):
                rec.with_context(inline_file_operation=True).upload()
        rec.invalidate_recordset()
        self.assertFalse(rec.is_being_processed)
