# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
import logging

from odoo import fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class CxTowerJetWaypoint(models.Model):
    _inherit = "cx.tower.jet.waypoint"

    backup_id = fields.Many2one(
        "cx.tower.backup",
        ondelete="set null",
        readonly=True,
        copy=False,
        groups="cetmix_tower_base.group_root",
    )

    def _is_backup_waypoint(self):
        """Return whether backup context is enabled on this waypoint.

        Returns:
            bool: Both the backup and template link are still present.
        """
        return bool(
            self
            and self.sudo().backup_id
            and self.sudo().waypoint_template_id.backup_template_id
        )

    def prepare(self, is_destination=False):
        """Prepare a backup-backed waypoint through its Backup plan.

        Args:
            is_destination (bool): Whether to fly here when preparation finishes.

        Returns:
            bool: Preparation was requested or completed.

        Raises:
            ValidationError: The waypoint is not Draft or its backup cannot start.
        """
        self.ensure_one()
        template = self.waypoint_template_id.sudo().backup_template_id
        if not template:
            return super().prepare(is_destination=is_destination)
        if self.state != "draft":
            raise ValidationError(self.env._("Only a draft waypoint can be prepared."))
        with self.env.cr.savepoint():
            self.write({"state": "preparing", "is_destination": is_destination})
            self.jet_id.sudo().create_backup(template, ignore_busy=True, waypoint=self)
        return True

    def unlink(self):
        """Delete a linked backup only after checking the caller's rights.

        Returns:
            bool: Deletion was requested or completed.

        Raises:
            ValidationError: Waypoint state or a running operation prevents deletion,
                unless ``waypoint_no_raise_on_delete`` requests logging and skipping.
        """
        if self.env.context.get("waypoint_force_delete"):
            return super().unlink()
        linked = self.filtered(
            lambda waypoint: waypoint.sudo().backup_id
            and waypoint.state in ("ready", "error")
        )
        if linked:
            linked.check_access("unlink")
        eligible = self.browse()
        for waypoint in linked:
            try:
                if waypoint.is_destination:
                    raise ValidationError(
                        self.env._("A destination waypoint cannot be deleted.")
                    )
                backup = waypoint.sudo().backup_id
                backup._check_delete()
                if backup._delete_plan_is_busy():
                    raise ValidationError(
                        self.env._(
                            "The Delete plan is already running; try again later."
                        )
                    )
            except ValidationError as error:
                if not self.env.context.get("waypoint_no_raise_on_delete"):
                    raise
                _logger.error("%s", error)
                continue
            eligible |= waypoint
        for waypoint in eligible:
            backup = waypoint.sudo().backup_id
            deferred = bool(
                backup.backup_template_id.plan_delete_id
                and (backup.jet_id or backup.server_id)
            )
            if deferred:
                waypoint.write({"state": "deleting"})
            backup._delete_for_waypoint(waypoint)
            if not deferred:
                super(CxTowerJetWaypoint, waypoint).unlink()
        rest = self - linked
        return super(CxTowerJetWaypoint, rest).unlink() if rest else True

    def _leave(self, *args, **kwargs):
        """Elevate only backup-template waypoint plans.

        Args:
            *args (tuple): Parent arguments.
            **kwargs (dict): Parent keyword arguments.

        Returns:
            bool: Parent transition result.
        """
        waypoint = (
            self.sudo() if self.sudo().waypoint_template_id.backup_template_id else self
        )
        return super(CxTowerJetWaypoint, waypoint)._leave(*args, **kwargs)

    def _arrive(self, *args, **kwargs):
        """Elevate only backup-template waypoint plans.

        Args:
            *args (tuple): Parent arguments.
            **kwargs (dict): Parent keyword arguments.

        Returns:
            bool: Parent transition result.
        """
        waypoint = (
            self.sudo() if self.sudo().waypoint_template_id.backup_template_id else self
        )
        return super(CxTowerJetWaypoint, waypoint)._arrive(*args, **kwargs)

    def _get_custom_variable_values(self, *args, **kwargs):
        """Merge backup values under the waypoint's own values.

        Args:
            *args (tuple): Parent arguments.
            **kwargs (dict): Parent keyword arguments.

        Returns:
            dict: Custom plan values.
        """
        values = super()._get_custom_variable_values(*args, **kwargs)
        if self._is_backup_waypoint():
            values = {**self.sudo().backup_id._get_custom_variable_values(), **values}
        return values
