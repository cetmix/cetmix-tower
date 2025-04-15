from unittest.mock import patch

from odoo.addons.cetmix_tower_server.tests.common import TestTowerCommon
from odoo.addons.queue_job.tests.common import trap_jobs


class TestFlightPlanQueue(TestTowerCommon):
    """End-to-end queue-job tests for flight-plan execution."""

    def setUp(self):
        super().setUp()

        # 1️. Flight‑plans
        self.fp1 = self.Plan.create({"name": "FP-1"})
        self.fp2 = self.Plan.create({"name": "FP-2"})
        self.fp3 = self.Plan.create({"name": "FP-3"})

        # 2️. Commands “run another plan”
        self.cmd_run_fp2 = self.Command.create(
            {"name": "run FP-2", "action": "plan", "flight_plan_id": self.fp2.id}
        )
        self.cmd_run_fp3 = self.Command.create(
            {"name": "run FP-3", "action": "plan", "flight_plan_id": self.fp3.id}
        )

        # 3️. Extra command used by FP‑1
        self.cmd_list_all = self.Command.create(
            {
                "name": "list all",
                "path": "/home/{{ tower.server.username }}",
                "code": "cd {{ test_path_ }} && ls -al",
            }
        )

    def _drain_queue(self, trap):
        """Synchronously perform every job until the queue is empty."""
        while trap.enqueued_jobs:
            trap.perform_enqueued_jobs()

    def _assert_jobs(self, trap, expected):
        """Fail if the total number of delayed jobs is not *expected*."""
        self.assertEqual(
            len(trap.calls),
            expected,
            f"{expected} delayed jobs were expected, got {len(trap.calls)}",
        )

    def test_flight_plan_flat_chain_queue(self):
        """Flat chain produces five delayed jobs."""
        # Flight‑plan 1: FP‑2 (mkdir -> ls) -> list all -> FP‑3 (mkdir -> ls)

        # ─ Flight‑plan 1:  FP‑2 -> list all -> FP‑3
        self.plan_line.create(
            {
                "sequence": 5,
                "plan_id": self.fp1.id,
                "command_id": self.cmd_run_fp2.id,
            }
        )
        self.plan_line.create(
            {
                "sequence": 10,
                "plan_id": self.fp1.id,
                "command_id": self.cmd_list_all.id,
            }
        )
        self.plan_line.create(
            {
                "sequence": 15,
                "plan_id": self.fp1.id,
                "command_id": self.cmd_run_fp3.id,
            }
        )
        # ─ Flight‑plan 2:  mkdir -> ls
        self.plan_line.create(
            {
                "sequence": 5,
                "plan_id": self.fp2.id,
                "command_id": self.command_create_dir.id,
            }
        )
        self.plan_line.create(
            {
                "sequence": 10,
                "plan_id": self.fp2.id,
                "command_id": self.command_list_dir.id,
            }
        )
        # ─ Flight‑plan 3:  mkdir -> ls
        self.plan_line.create(
            {
                "sequence": 5,
                "plan_id": self.fp3.id,
                "command_id": self.command_create_dir.id,
            }
        )
        self.plan_line.create(
            {
                "sequence": 10,
                "plan_id": self.fp3.id,
                "command_id": self.command_list_dir.id,
            }
        )

        # Ensure no command logs exist yet
        self.assertFalse(
            self.env["cx.tower.command.log"].search(
                [("plan_log_id.plan_id", "=", self.fp1.id)]
            ),
            "Command logs should be empty before run",
        )

        # Run FP‑1 and drain the queue
        with trap_jobs() as trap:
            self.fp1._run_single(self.server_test_1)
            self._drain_queue(trap)

            # Expected delayed commands:
            #   FP‑2: mkdir, ls
            #   FP‑1: list‑all
            #   FP‑3: mkdir, ls
            self._assert_jobs(trap, expected=5)

    def test_flight_plan_nested_chain_queue(self):
        """Nested chain produces three delayed jobs."""
        # Flight‑plan 1: FP‑2 (FP‑3 (mkdir -> ls)) -> list all

        # ─ Flight‑plan 1:  FP‑2 -> list all
        self.plan_line.create(
            {"sequence": 5, "plan_id": self.fp1.id, "command_id": self.cmd_run_fp2.id}
        )
        self.plan_line.create(
            {"sequence": 10, "plan_id": self.fp1.id, "command_id": self.cmd_list_all.id}
        )

        # ─ Flight‑plan 2: FP‑3
        self.plan_line.create(
            {"sequence": 5, "plan_id": self.fp2.id, "command_id": self.cmd_run_fp3.id}
        )

        # ─ Flight‑plan 3: (mkdir -> ls)
        self.plan_line.create(
            {
                "sequence": 5,
                "plan_id": self.fp3.id,
                "command_id": self.command_create_dir.id,
            }
        )
        self.plan_line.create(
            {
                "sequence": 10,
                "plan_id": self.fp3.id,
                "command_id": self.command_list_dir.id,
            }
        )

        # No command logs expected yet
        self.assertFalse(
            self.env["cx.tower.command.log"].search(
                [("plan_log_id.plan_id", "=", self.fp1.id)]
            ),
            "Command logs should be empty before run",
        )

        # Run FP‑1 and drain the queue
        with trap_jobs() as trap:
            self.fp1._run_single(self.server_test_1)
            self._drain_queue(trap)
            # Expected delayed commands:
            #   FP‑1: list‑all
            #   FP‑3: mkdir, ls
            self._assert_jobs(trap, expected=3)

    def test_flight_plan_failed_child_queue(self):
        """Parent flight plan should not run if child flight plan failed."""

        # Flight‑plan 1: list all -> FP‑2 (list all, list all)
        # -> FP‑2 (list all, list all) -> list all
        self.plan_line.create(
            {"sequence": 5, "plan_id": self.fp1.id, "command_id": self.cmd_list_all.id}
        )
        self.plan_line.create(
            {"sequence": 10, "plan_id": self.fp1.id, "command_id": self.cmd_run_fp2.id}
        )
        self.plan_line.create(
            {"sequence": 15, "plan_id": self.fp1.id, "command_id": self.cmd_run_fp2.id}
        )
        self.plan_line.create(
            {"sequence": 20, "plan_id": self.fp1.id, "command_id": self.cmd_list_all.id}
        )

        # ─ Flight‑plan 2: list all
        self.plan_line.create(
            {"sequence": 5, "plan_id": self.fp2.id, "command_id": self.cmd_list_all.id}
        )
        self.plan_line.create(
            {"sequence": 10, "plan_id": self.fp2.id, "command_id": self.cmd_list_all.id}
        )

        cx_tower_plan_obj = self.registry["cx.tower.plan"]
        _run_single_super = cx_tower_plan_obj._run_single

        def _run_single(this, *args, **kwargs):
            if this == self.fp2:
                # Simulate a failed Plan 2. To achieve this, we need to update
                # the command associated with Plan 2 to apply the desired side effect.
                self.fp2.line_ids[1].command_id[0].code = "fail"
            return _run_single_super(this, *args, **kwargs)

        with patch.object(
            cx_tower_plan_obj, "_run_single", _run_single
        ), trap_jobs() as trap:
            self.fp1._run_single(self.server_test_1)
            self._drain_queue(trap)
            self._assert_jobs(trap, expected=2)

        # Check flight plan logs
        fp_logs = self.PlanLog.search([("plan_id", "=", self.fp1.id)])
        self.assertEqual(len(fp_logs.command_log_ids), 2)
