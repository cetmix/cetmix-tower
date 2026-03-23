# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


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

    server_id = fields.Many2one(
        comodel_name="cx.tower.server",
        required=True,
        ondelete="cascade",
        copy=False,
        help="Server where the jet is requested",
    )
    jet_id = fields.Many2one(
        comodel_name="cx.tower.jet",
        ondelete="cascade",
        string="Serviced by Jet",
        copy=False,
        help="Jet that is requested",
    )
    jet_template_id = fields.Many2one(
        comodel_name="cx.tower.jet.template",
        required=True,
        string="Requested Template",
        ondelete="cascade",
        copy=False,
        help="Template of the jet that is requested. "
        "Used to create a new jet if not found.",
    )
    state_requested_id = fields.Many2one(
        comodel_name="cx.tower.jet.state",
        ondelete="cascade",
        copy=False,
        help="State of the jet that is requested",
    )
    requested_by_jet_id = fields.Many2one(
        comodel_name="cx.tower.jet",
        ondelete="cascade",
        string="Requested by Jet",
        copy=False,
        help="Jet that is requesting the jet",
    )
    for_dependency_id = fields.Many2one(
        comodel_name="cx.tower.jet.dependency",
        ondelete="cascade",
        copy=False,
        help="Dependency for which request is created",
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

    @api.model
    def _create_request(
        self,
        server,
        jet=None,
        jet_template=None,
        state=None,
        requested_by_jet=None,
        for_dependency=None,
    ):
        """
        Create a new jet request.

        Args:
            server (cx.tower.server()): Server to create the request on
            jet (cx.tower.jet()): Jet to create the request for
            jet_template (cx.tower.jet.template()): Template to create the request for
            state (cx.tower.jet.state()): State to create the request for
            requested_by_jet (cx.tower.jet()): Jet that is requesting the jet
            for_dependency (cx.tower.jet.dependency()): Dependency for which request
                is created

        Returns:
            cx.tower.jet.request(): A jet request for the jet
        """

        # Must have either jet or jet template
        if not jet and not jet_template:
            raise ValidationError(
                _("Either a jet or a jet template must be provided to create a request")
            )

        # Set jet template from the jet if not provided
        if not jet_template and jet:
            jet.ensure_one()
            jet_template = jet.jet_template_id

        request = self.env["cx.tower.jet.request"].create(
            {
                "server_id": server.id,
                "jet_id": jet.id if jet else None,
                "jet_template_id": jet_template.id if jet_template else None,
                "state_requested_id": state.id if state else None,
                "requested_by_jet_id": requested_by_jet.id
                if requested_by_jet
                else None,
                "for_dependency_id": for_dependency.id if for_dependency else None,
            }
        )

        # Step 1. Use the existing jet if provided explicitly
        if jet:
            if jet.server_id != server:
                raise ValidationError(
                    _(
                        "Jet %(jet)s is not on server %(server)s",
                        jet=jet.name,
                        server=server.name,
                    )
                )
            if jet.state_id == state and not jet._is_busy():
                _logger.info(
                    "Jet %s is available and not busy, finalizing request", jet.name
                )
                request._finalize(failed=False)
            elif jet.target_state_id == state:
                _logger.info(
                    "Jet %s is transitioning to the target state, "
                    "waiting for it to finish",
                    jet.name,
                )
                jet._serve_jet_request(jet_request=request)
            else:
                _logger.info(
                    "Jet %s is not available or busy, triggering jet to "
                    "bring itself to the required state",
                    jet.name,
                )
                jet._serve_jet_request(jet_request=request)
            return request

        # Step 2. Try to pick any of the existing jets from the template
        available_jets = jet_template.jet_ids.filtered(
            lambda j: j.server_id == server and j._accepts_new_links()
        )
        for available_jet in available_jets:
            # Finalize the request instantly if the jet state
            #  matches and jet is not busy
            if available_jet.state_id == state and not available_jet._is_busy():
                _logger.info(
                    "Jet %s is available and not busy, finalizing request",
                    available_jet.name,
                )
                request.jet_id = available_jet
                request._finalize(failed=False)
                return request

        # Step 3. Jet is available, and is not busy, but not in the required state
        transitioning_jets = available_jets.filtered(
            lambda j: j.target_state_id == state
        )
        if transitioning_jets:
            _logger.info(
                "Jet %s is transitioning to the target state, "
                "waiting for it to finish",
                transitioning_jets[0].name,
            )
            # Trigger the jet to bring itself to the required state
            request.jet_id = transitioning_jets[0]
            return request

        # Step 4. Jet is available, and is not busy, but not in the required state
        not_busy_jets = available_jets.filtered(lambda j: not j._is_busy())
        if not_busy_jets:
            # Pick the first available jet
            not_busy_jet = not_busy_jets[0]
            _logger.info(
                "Jet %s is available and not busy, but not in the required state,"
                " triggering jet to bring itself to the required state",
                not_busy_jet.name,
            )
            # Trigger the jet to bring itself to the required state
            request.jet_id = not_busy_jet
            not_busy_jet._serve_jet_request(jet_request=request)
            return request

        # Step 5. Jet is not available, or is busy and not transitioning
        # to the required state - create a new jet
        # TODO: Add an option to wait for the jet to become available
        if jet_template:
            jet_template.ensure_one()
            _logger.info("Creating new jet using template %s", jet_template.name)
            jet = jet_template.create_jet(server)
            if jet:
                _logger.info("Created new jet %s", jet.name)
                request.jet_id = jet
                if jet.state_id == state:
                    request._finalize(failed=False)
                else:
                    # Trigger the jet to bring itself to the required state
                    jet._serve_jet_request(jet_request=request)
            else:
                _logger.error(
                    "Failed to create new jet using template %s", jet_template.name
                )
                request._finalize(failed=True)

        _logger.info("Jet request creation finished")
        return request

    def _finalize(self, failed=False):
        """
        Finalize a jet request.

        Args:
            failed (bool): Whether the request failed
        """
        self.ensure_one()

        # 1. Update the state of the request
        self.write(
            {
                "state": "success" if not failed else "failed",
            }
        )

        # 2. Notify the jet that issued the request
        if self.requested_by_jet_id:
            self.requested_by_jet_id._finalize_jet_request(self)

        # 3. Remove the link to the jet that was handling the request
        if self.jet_id and self.jet_id.served_jet_request_id == self:
            # Unlink the jet from the request
            self.jet_id.sudo().write({"served_jet_request_id": False})
