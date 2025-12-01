from odoo.addons.cetmix_tower_server.tests.common import TestTowerCommon
from odoo.addons.queue_job.job import Job


class TestTowerCommand(TestTowerCommon):
    """
    Test cases for command log state on queue_job failure
    """

    def test_command_log_state_on_job_fail(self):
        command = self.env["cx.tower.command"].create(
            {
                "name": "Test Command",
                "action": "ssh_command",
                "code": "echo 'Hello World'",
            }
        )
        self.assertTrue(command.id, "Command should be created successfully")

        self.server_test_1.run_command(command=command)
        command_log = self.env["cx.tower.command.log"].search(
            [("command_id", "=", command.id)], order="id desc", limit=1
        )
        self.assertTrue(command_log, "Command log should be created")

        job = command_log.queue_job_id
        self.assertTrue(job, "Queue job should be associated with command log")

        job_obj = Job.load(self.env, job.uuid)
        job_obj.set_failed()
        job_obj.store()
        self.assertEqual(job.state, "failed", "Job should be in failed state")
        self.assertEqual(
            command_log.command_status,
            self.env["queue.job"].QUEUE_JOB_ERROR,
            "Command log should be in failed state",
        )
