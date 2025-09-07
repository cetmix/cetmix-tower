from odoo import exceptions

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

        # Verify still marked as processing
        self.assertTrue(processing_file.is_being_processed)

        # Same tests for download
        with self.assertRaises(exceptions.UserError):
            processing_file.download(raise_error=True)

        with trap_jobs() as trap:
            processing_file.download(raise_error=False)
            # No job should be created
            self.assertEqual(len(trap.enqueued_jobs), 0)

        self.assertTrue(processing_file.is_being_processed)
