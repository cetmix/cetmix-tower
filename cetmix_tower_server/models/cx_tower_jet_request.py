# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, fields, models
from odoo.exceptions import ValidationError


class CxTowerJetRequest(models.Model):
    """
    Requests for jets. Issued when there is a jet needed in a specific
    state on a server.

    Eg. jet "Application" needs a jet "Database" to be in state "Running"
    to be able to start.
    It looks for an existing jet in the required state and if not found,
    creates a jet request.

    During the request processing, Tower will try to find and existing jet and
    bring it to the required state. Or create a new one if not found.

    When a request is finalized, it will report the result to the request issuer
    using the callback function.

    """

    _name = "cx.tower.jet.request"
    _description = "Cetmix Tower Jet Request"
    _log_access = False

    server_id = fields.Many2one(
        comodel_name="cx.tower.server",
        required=True,
        ondelete="cascade",
        copy=False,
        help="Server where the jet is requested",
    )
    jet_id = fields.Many2one(
        comodel_name="cx.tower.jet",
        required=True,
        ondelete="cascade",
        copy=False,
        help="Jet that is requested",
    )
    jet_template_id = fields.Many2one(
        comodel_name="cx.tower.jet.template",
        required=True,
        ondelete="cascade",
        copy=False,
        help="Template of the jet that is requested. "
        "Used to create a new jet if not found.",
    )
    state_requested_id = fields.Many2one(
        comodel_name="cx.tower.jet.state",
        required=True,
        ondelete="cascade",
        copy=False,
        help="State of the jet that is requested",
    )
    requested_by_jet_id = fields.Many2one(
        comodel_name="cx.tower.jet",
        required=True,
        ondelete="cascade",
        copy=False,
        help="Jet that is requesting the jet",
    )
    state = fields.Selection(
        selection=[
            ("new", "New"),
            ("processing", "Processing"),
            ("success", "Success"),
            ("failed", "Failed"),
        ],
        default="new",
        required=True,
        copy=False,
    )

    def _create_request(
        self, server, jet=None, jet_template=None, state=None, requested_by_jet=None
    ):
        """
        Create a new jet request.

        Args:
            server (cx.tower.server()): Server to create the request on
            jet (cx.tower.jet()): Jet to create the request for
            jet_template (cx.tower.jet.template()): Template to create the request for
            state (cx.tower.jet.state()): State to create the request for
            requested_by_jet (cx.tower.jet()): Jet that is requesting the jet

        Returns:
            cx.tower.jet.request(): A jet request for the jet
        """
        if not jet and not jet_template:
            raise ValidationError(_("Jet or jet template is required"))

        self.ensure_one()
        request = self.env["cx.tower.jet.request"].create(
            {
                "server_id": server.id,
                "jet_id": jet.id if jet else None,
                "jet_template_id": jet_template.id if jet_template else None,
                "state_requested_id": state.id if state else None,
                "requested_by_jet_id": requested_by_jet.id
                if requested_by_jet
                else None,
            }
        )

        # Step 1. Use the existing jet if provided explicitly
        if jet:
            if jet.state_id == state and not jet._is_busy():
                request._finalize(result="success")
            return request

        # Step 2. Try to pick any of the existing jets from the template
        available_jets = jet_template.jet_ids.filtered(
            lambda j: j.server_id == server and j._accepts_new_links()
        )
        for available_jet in available_jets:
            # Finalize the request instantly if the jet state
            #  matches and jet is not busy
            if available_jet.state_id == state and not available_jet._is_busy():
                request.jet_id = available_jet
                request._finalize(result="success")
                break

        # Step 3. If there are no existing jets, create a new jet request
        return request

    def _finalize(self, result="success"):
        """
        Finalize a jet request.

        Args:
            result (str): Result of the request
            jet (cx.tower.jet()): Jet to finalize the request with
        """
        self.ensure_one()
        self.write(
            {
                "state": result,
            }
        )

        # Link the jet to the jet that issued the request if not already linked
        if (
            self.jet_id
            and self.requested_by_jet_id
            and self.jet_id != self.requested_by_jet_id
            and self.jet_id not in self.requested_by_jet_id.jet_linked_to_ids
        ):
            self.requested_by_jet_id.jet_linked_to_ids = [(4, self.jet_id.id)]
