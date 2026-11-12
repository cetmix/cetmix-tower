# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import api, models
from odoo.exceptions import ValidationError


class CxTowerPlan(models.Model):
    _inherit = "cx.tower.plan"

    def _backup_plan_tree(self):
        """Collect the plans reached through Plan commands, handling cycles.

        Returns:
            cx.tower.plan: Plans reachable from this recordset.
        """
        pending = self.sudo().with_context(active_test=False)
        plans = pending.browse()
        while pending:
            plans |= pending
            pending = (
                pending.line_ids.command_id.filtered(
                    lambda command: command.action == "plan"
                ).flight_plan_id
                - plans
            )
        return plans

    def _check_backup_plan_access(self):
        """Require Root plans and commands throughout a backup execution tree.

        Raises:
            ValidationError: A reachable plan or command has a lower access level.
        """
        plans = self.sudo()._backup_plan_tree()
        if any(plan.access_level != "3" for plan in plans) or any(
            command.access_level != "3" for command in plans.line_ids.command_id
        ):
            raise ValidationError(
                self.env._(
                    "Backup flight plans and every command and sub-plan they "
                    "use must have Root access level."
                )
            )

    @api.model
    def _validate_backup_plan_trees(self, changed_plans=None, changed_commands=None):
        """Recheck affected configured trees and trees still handling backup values.

        Args:
            changed_plans (cx.tower.plan | None): Modified plans.
            changed_commands (cx.tower.command | None): Modified commands.

        Returns:
            None: Affected backup execution trees are valid.

        Raises:
            ValidationError: An affected backup plan tree contains a plan
                or command below Root access level.
        """
        templates = self.env["cx.tower.backup.template"].sudo().search([])
        waypoint_templates = (
            self.env["cx.tower.jet.waypoint.template"]
            .sudo()
            .search([("backup_template_id", "!=", False)])
        )
        running = (
            self.env["cx.tower.plan.log"]
            .sudo()
            .with_context(active_test=False)
            .search([("has_backup_values", "=", True), ("is_running", "=", True)])
        )
        roots = (
            templates.plan_backup_id
            | templates.plan_restore_id
            | templates.plan_delete_id
            | waypoint_templates.plan_arrive_id
            | waypoint_templates.plan_leave_id
            | running.plan_id
        )
        for root in roots:
            tree = root._backup_plan_tree()
            if (changed_plans and tree & changed_plans) or (
                changed_commands and tree.line_ids.command_id & changed_commands
            ):
                root._check_backup_plan_access()

    @api.constrains("access_level", "line_ids")
    def _check_backup_plans(self):
        """Protect historical backup logs and plans still receiving backup values.

        Returns:
            None: Plan access levels and affected execution trees are valid.

        Raises:
            ValidationError: A plan with backup logs is below Root level,
                or an affected backup plan tree contains non-Root records.
        """
        plans = self.sudo()
        lower = plans.filtered(lambda plan: plan.access_level != "3")
        if lower and self.env["cx.tower.plan.log"].sudo().with_context(
            active_test=False
        ).search_count(
            [("plan_id", "in", lower.ids), ("has_backup_values", "=", True)]
        ):
            raise ValidationError(
                self.env._(
                    "A flight plan with backup logs must keep Root access level."
                )
            )
        self._validate_backup_plan_trees(changed_plans=plans)

    def unlink(self):
        """Keep running backup operations' plan logs available for callbacks.

        Returns:
            bool: ORM unlink result.

        Raises:
            ValidationError: A backup execution tree is still running.
        """
        if (
            self.env["cx.tower.plan.log"]
            .sudo()
            .with_context(active_test=False)
            .search_count(
                [
                    ("plan_id", "in", self.ids),
                    ("is_running", "=", True),
                    ("has_backup_values", "=", True),
                ]
            )
        ):
            raise ValidationError(
                self.env._(
                    "A flight plan running a backup operation cannot be deleted."
                )
            )
        return super().unlink()
