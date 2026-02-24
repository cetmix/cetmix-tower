# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .tools import generate_random_id

_logger = logging.getLogger(__name__)


class CxTowerJetWaypoint(models.Model):
    """Jet Waypoints represent waypoints for jets"""

    _name = "cx.tower.jet.waypoint"
    _description = "Cetmix Tower Jet Waypoint"
    _inherit = [
        "cx.tower.reference.mixin",
        "cx.tower.access.mixin",
        "cx.tower.metadata.mixin",
    ]
    _order = "create_date desc"

    name = fields.Char(required=True)
    access_level = fields.Selection(
        compute="_compute_access_level", readonly=False, store=True
    )
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("preparing", "Preparing"),
            ("ready", "Ready"),
            ("error", "Error"),
            ("arriving", "Arriving"),
            ("leaving", "Leaving"),
            ("current", "Current"),
            ("deleting", "Deleting"),
            ("deleted", "Deleted"),
        ],
        default="draft",
        required=True,
        readonly=True,
    )
    can_fly_to = fields.Boolean(
        compute="_compute_can_fly_to",
        readonly=True,
    )
    is_destination = fields.Boolean(
        help="Indicates if this waypoint is the current destination",
    )
    jet_id = fields.Many2one(
        comodel_name="cx.tower.jet",
        required=True,
        ondelete="cascade",
        help="Jet this waypoint belongs to",
    )
    jet_template_id = fields.Many2one(
        comodel_name="cx.tower.jet.template",
        related="jet_id.jet_template_id",
        readonly=True,
    )
    waypoint_template_id = fields.Many2one(
        string="Type",
        comodel_name="cx.tower.jet.waypoint.template",
        help="Waypoint template this waypoint is based on",
        domain="[('jet_template_id', '=', jet_template_id)]",
        required=True,
        ondelete="restrict",
    )
    variable_values = fields.Json(
        help="Custom variable values for this waypoint",
        readonly=True,
    )
    variable_values_text = fields.Text(
        help="Custom variable values for this waypoint",
        compute="_compute_variable_values_text",
    )

    # ------------------------------------
    # --------- Selection ------------
    # ------------------------------------
    def _selection_access_level(self):
        """
        Available access levels

        Returns:
            List of tuples: available options.
        """
        return [
            ("2", "Manager"),
            ("3", "Root"),
        ]

    # ------------------------------------
    # --------- Computed Fields ---------
    # ------------------------------------
    @api.depends("name", "create_date")
    def _compute_display_name(self):
        """
        Compute the display name of the waypoint
        """
        for waypoint in self:
            timestamp = fields.Datetime.context_timestamp(
                waypoint, waypoint.create_date
            )
            formatted_date = timestamp.strftime("%Y-%m-%d %H:%M:%S")
            waypoint.display_name = f"{waypoint.name} ({formatted_date})"

    @api.depends("jet_id.waypoint_ids", "jet_id.waypoint_ids.state")
    def _compute_can_fly_to(self):
        """
        Can fly only if waypoint is in the ready state and
        is not the current waypoint and all the jet waypoints
        are in the "ready" state
        """
        for waypoint in self:
            all_waypoints = waypoint.jet_id.waypoint_ids
            waypoint.can_fly_to = waypoint.state == "ready" and not bool(
                all_waypoints.filtered(
                    lambda w: w.state not in ["ready", "error", "current"]
                )
            )

    @api.depends("variable_values")
    def _compute_variable_values_text(self):
        """
        Compute the variable values text for the waypoint
        """
        for waypoint in self:
            waypoint.variable_values_text = (
                str(waypoint.variable_values) if waypoint.variable_values else False
            )

    # ------------------------------------
    # --------- CRUD Methods -------------
    # ------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        """
        Create waypoints
        - Generate waypoint reference if not provided
        """

        for vals in vals_list:
            if not vals.get("reference"):
                vals["reference"] = generate_random_id(
                    sections=4, population=4, separator="_"
                )
        jets = super().create(vals_list)
        return jets

    def write(self, vals):
        """
        Write. Do not allow to modify the template
        if the waypoint is not in the draft state
        """
        if "waypoint_template_id" in vals and not vals.get("state") == "draft":
            for waypoint in self:
                if (
                    waypoint.waypoint_template_id.id != vals.get("waypoint_template_id")
                    and waypoint.state != "draft"
                ):
                    raise ValidationError(
                        _(
                            "Cannot change waypoint type for %(waypoint)s "
                            "because it is not in the draft state",
                            waypoint=waypoint.name,
                        )
                    )
        # Invalidate the state field
        fields_to_invalidate = []
        if "state" in vals:
            fields_to_invalidate.append("state")
        if "variable_values" in vals:
            fields_to_invalidate.append("variable_values")
        if "is_destination" in vals:
            fields_to_invalidate.append("is_destination")
        if fields_to_invalidate:
            self.invalidate_recordset(fields_to_invalidate)
        return super().write(vals)

    def unlink(self):
        """
        Unlink.

        Raises:
            ValidationError: If the waypoint cannot be deleted
                set the context value 'waypoint_no_raise_on_delete' to True
                for not to raise the exception.
        """
        # Deletable waypoints:
        # - are in the 'draft' or 'deleting' state
        # - waypoint is in the 'ready' or 'error' state and template
        #   doesn't have on_delete flight plan
        # Non-deletable waypoints:
        # - are in the 'arriving', 'leaving' or 'preparing' state
        #   or is the current waypoint of the jet
        # Need to run the on_delete flight plan:
        # - waypoint is in the 'ready' or 'error' state and template has
        #  on_delete flight plan
        if self._context.get("waypoint_force_delete"):
            return super().unlink()

        waypoints_to_delete = self.browse()
        waypoints_to_run_delete_plan = self.browse()
        for waypoint in self:
            if waypoint.state not in ["draft", "deleted", "error", "ready"]:
                if waypoint.state == "current":
                    exception_message = _(
                        "Cannot delete the waypoint %(waypoint)s because it is"
                        " the current waypoint of the jet %(jet)s",
                        waypoint=waypoint.name,
                        jet=waypoint.jet_id.name,
                    )
                else:
                    exception_message = _(
                        "Cannot delete the waypoint %(waypoint)s because it is"
                        " in the %(state)s state",
                        waypoint=waypoint.name,
                        state=waypoint.state,
                    )
                if self._context.get("waypoint_no_raise_on_delete"):
                    _logger.error(exception_message)
                    continue
                raise ValidationError(exception_message)
            if (
                waypoint.state in ["ready", "error"]
                and waypoint.waypoint_template_id.plan_delete_id
            ):
                waypoints_to_run_delete_plan |= waypoint
                continue
            waypoints_to_delete |= waypoint

        if waypoints_to_delete:
            result = super(CxTowerJetWaypoint, waypoints_to_delete).unlink()
        else:
            result = True

        for waypoint in waypoints_to_run_delete_plan:
            waypoint.write({"state": "deleting"})
            waypoint.jet_id.server_id.sudo().run_flight_plan(
                jet=waypoint.jet_id,
                flight_plan=waypoint.waypoint_template_id.plan_delete_id,
                plan_log={"waypoint_id": waypoint.id},
                variable_values=waypoint._get_custom_variable_values(),
            )
        return result

    # ------------------------------------
    # --------- Waypoint Setters ---------
    # ------------------------------------
    def prepare(self):
        """
        Prepare the newly created waypoint.

        Returns:
            bool: True if event was handled else False
        """
        self.ensure_one()
        _logger.info(
            _(
                "Preparing waypoint %(waypoint)s on jet %(jet)s",
                waypoint=self.name,
                jet=self.jet_id.name,
            )
        )
        if not self.state == "draft":
            _logger.error(
                _(
                    "Cannot prepare waypoint %(waypoint)s on jet %(jet)s because"
                    " it is not in the 'draft' state",
                    waypoint=self.name,
                    jet=self.jet_id.name,
                )
            )
            return False
        if self.waypoint_template_id.plan_create_id:
            self.write({"state": "preparing"})
            with self.env.cr.savepoint():
                self.jet_id.server_id.sudo().run_flight_plan(
                    flight_plan=self.waypoint_template_id.plan_create_id,
                    jet=self.jet_id,
                    plan_log={
                        "waypoint_id": self.id,
                    },
                    variable_values=self._get_custom_variable_values(),
                )
        else:
            self.write({"state": "ready"})
            # Save jet variable values when state changes to ready
            self._save_variable_values()

            # Refresh the frontend views
            self.env.user.reload_views(model="cx.tower.jet", rec_ids=[self.jet_id.id])

            # Fly to this waypoint if set as destination
            if self.is_destination:
                self.fly_to()
        _logger.info(
            _(
                "Successfully prepared waypoint %(waypoint)s on jet %(jet)s",
                waypoint=self.name,
                jet=self.jet_id.name,
            )
        )
        return True

    def fly_to(self):
        """
        Fly to the waypoint

        Returns:
            bool: True if event was handled else False
        """
        self.ensure_one()
        _logger.info(
            _(
                "Flying to waypoint %(waypoint)s on jet %(jet)s",
                waypoint=self.name,
                jet=self.jet_id.name,
            )
        )
        if self.state != "ready":
            _logger.error(
                _(
                    "Cannot fly to waypoint %(waypoint)s on jet %(jet)s because"
                    " it is not in the 'ready' state",
                    waypoint=self.name,
                    jet=self.jet_id.name,
                )
            )
            return False

        # Cannot fly to waypoint if there is another waypoint
        #  in the "arriving" or state
        if self.jet_id.waypoint_ids.filtered(
            lambda w: w.state in ["arriving", "leaving"]
        ):
            _logger.error(
                _(
                    "Cannot fly to waypoint %(waypoint)s on jet %(jet)s because"
                    " there is another waypoint %(other_waypoint)s "
                    "in the 'arriving' or 'leaving' state",
                    waypoint=self.name,
                    jet=self.jet_id.name,
                )
            )
            return False

        # Leave the previous waypoint
        previous_waypoint = self.jet_id.waypoint_id
        if not previous_waypoint:
            # No previous waypoint, set state to arriving
            # Variable values will be restored in _arrive()
            self.write({"state": "arriving", "is_destination": True})
            self._arrive()
            return True

        # Don't go to the waypoint if it is already the current waypoint
        if previous_waypoint.id == self.id:
            return True

        # Cannot leave the waypoint if it is not ready or current
        if previous_waypoint.state not in ["ready", "current"]:
            return False

        # Set the new waypoint state to arriving
        # Mark this waypoint as destination
        self.write({"state": "arriving", "is_destination": True})
        # Leave the previous waypoint (this will save its variable values)
        previous_waypoint._leave()
        # If leaving completed immediately (no plan_leave_id),
        # arrive at the new waypoint (which will restore variable values)
        if previous_waypoint.state in ["ready", "current"]:
            self._arrive()
        _logger.info(
            _(
                "Successfully flew to waypoint %(waypoint)s on jet %(jet)s",
                waypoint=self.name,
                jet=self.jet_id.name,
            )
        )
        return True

    def _leave(self):
        """
        Leave the waypoint.

        Returns:
            bool: True if event was handled else False
        """
        self.ensure_one()
        if self.state not in ["ready", "current"]:
            return False
        self.write({"state": "leaving"})
        plan_leave = self.waypoint_template_id.plan_leave_id
        if plan_leave:
            with self.env.cr.savepoint():
                self.jet_id.server_id.sudo().run_flight_plan(
                    jet=self.jet_id,
                    flight_plan=plan_leave,
                    plan_log={
                        "waypoint_id": self.id,
                    },
                    variable_values=self._get_custom_variable_values(),
                )
        else:
            self.write({"state": "ready"})
            # Save jet variable values
            self._save_variable_values()
        return True

    def _arrive(self):
        """
        Arrive at the waypoint.

        Returns:
            bool: True if event was handled else False
        """
        self.ensure_one()
        if not self.state == "arriving":
            return False
        # Restore variable values before running the arrive plan
        self._restore_variable_values()
        plan_arrive = self.waypoint_template_id.plan_arrive_id
        if plan_arrive:
            self.jet_id.server_id.sudo().run_flight_plan(
                jet=self.jet_id,
                flight_plan=plan_arrive,
                plan_log={
                    "waypoint_id": self.id,
                },
                variable_values=self._get_custom_variable_values(),
            )
        else:
            # Clear destination flag when arriving without plan
            self.write({"is_destination": False, "state": "current"})
            self.jet_id.write({"waypoint_id": self.id})
            self.jet_id.invalidate_recordset(["waypoint_id"])
            # Refresh the frontend views
            self.env.user.reload_views(model="cx.tower.jet", rec_ids=[self.jet_id.id])
        return True

    # ---------------------------
    # --------- Hooks ---------
    # ---------------------------
    def _plan_finished(self, plan_log):
        """
        Handle the plan finished event

        Args:
            plan_log (cx.tower.plan.log): Plan log record

        Returns:
            bool: True if event was handled
        """
        self.ensure_one()
        if plan_log.plan_status == 0:
            # Successfully finished the plan
            jet = self.jet_id  # preserve in case of deleting

            if self.state == "arriving":
                # Set the waypoint as the current waypoint
                # when successfully arriving
                self.jet_id.write({"waypoint_id": self.id})
                self.jet_id.invalidate_recordset(["waypoint_id"])
                # Clear destination flag when successfully arrived
                self.write({"state": "current", "is_destination": False})
                _logger.info(
                    _(
                        "Successfully arrived at waypoint %(waypoint)s on jet %(jet)s",
                        waypoint=self.name,
                        jet=self.jet_id.name,
                    )
                )
            elif self.state == "deleting":
                self.write({"state": "deleted"})
                waypoint_name = self.name
                jet_name = self.jet_id.name
                self.unlink()
                _logger.info(
                    _(
                        "Successfully deleted waypoint %(waypoint)s on jet %(jet)s",
                        waypoint=waypoint_name,
                        jet=jet_name,
                    )
                )
            elif self.state in ["leaving", "preparing"]:
                # Save jet variable values
                self._save_variable_values()

                # Arrive at the destination waypoint
                # if there is any in the arriving state (only for leaving)
                if self.state == "leaving":
                    destination_waypoint = self.jet_id.waypoint_ids.filtered(
                        lambda w: w.state == "arriving"
                    )
                    if destination_waypoint:
                        destination_waypoint._arrive()

                # Set the waypoint state to ready after leaving or preparing
                prepared = self.state == "preparing"
                self.write({"state": "ready"})
                # Fly to this waypoint if set as destination
                if self.is_destination and prepared:
                    self.fly_to()

            # Refresh the frontend views
            self.env.user.reload_views(model="cx.tower.jet", rec_ids=[jet.id])
            return True

        # Failed to finish the plan
        # - restore variable values from current waypoint
        # - set the waypoint state to error
        if self.state == "arriving":
            # Restore variable values from jet's current waypoint
            current_waypoint = self.jet_id.waypoint_id
            if current_waypoint:
                current_waypoint._restore_variable_values()
                # Set current waypoint state to "current"
                current_waypoint.write({"state": "current"})
            # Clear destination flag when arriving fails
            self.write({"is_destination": False, "state": "error"})
        else:
            self.write({"state": "error"})

        # Refresh the frontend views
        self.env.user.reload_views(model="cx.tower.jet", rec_ids=[self.jet_id.id])
        return True

    # -----------------------------------
    # --------- Helper Methods ---------
    # -----------------------------------
    def _save_variable_values(self):
        """
        Save current jet variable values to the waypoint.
        Only jet-specific values are saved (not template/server/global values).

        Returns:
            bool: True if values were saved
        """
        self.ensure_one()

        # Get all variable values that belong to this jet specifically
        # (not template/server/global values)
        # Use variable_value_ids field from variable mixin
        jet_variable_values = self.jet_id.variable_value_ids

        # Build dictionary mapping variable_reference to value_char
        variable_values_dict = {}
        for var_value in jet_variable_values:
            variable_values_dict[var_value.variable_reference] = (
                var_value.value_char or ""
            )

        # Save to waypoint's variable_values field
        self.write({"variable_values": variable_values_dict})
        self.invalidate_recordset(["variable_values"])
        return True

    def _restore_variable_values(self):
        """
        Restore variable values from the waypoint to the jet.
        - Removes all variable values that are not saved in the waypoint

        Returns:
            bool: True if values were restored
        """
        self.ensure_one()
        if not self.variable_values:
            # Remove all jet variable values if waypoint has no saved values
            self.jet_id.variable_value_ids.unlink()
            return True

        # Get all current jet variable values
        current_jet_values = self.jet_id.variable_value_ids
        saved_references = set(self.variable_values.keys())

        # Remove variable values that are not in the saved waypoint values
        values_to_remove = current_jet_values.filtered(
            lambda v: v.variable_reference not in saved_references
        )
        if values_to_remove:
            values_to_remove.unlink()

        # Restore each variable value from the saved dictionary
        # Variable mixin handles checking if value is the same
        for variable_reference, saved_value in self.variable_values.items():
            self.jet_id.set_variable_value(variable_reference, saved_value)

        return True

    def _get_custom_variable_values(self):
        """
        Prepare custom variable values to pass with flight plans.
        Following custom values are available:

        __waypoint: waypoint reference
        __waypoint_type: waypoint template reference
        __waypoint_state: waypoint state
        __waypoint_<metadata_key>: waypoint metadata

        Returns:
            dict: Custom variable values to pass with flight plans
        """
        self.ensure_one()
        custom_values = {
            "__waypoint": self.reference,
            "__waypoint_type": self.waypoint_template_id.reference,
            "__waypoint_state": self.state,
        }
        if self.metadata:
            for key, value in self.metadata.items():
                custom_values[f"__waypoint_{key}"] = value
        return custom_values
