# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import json

from odoo import http
from odoo.http import Response, request

from ..models.constants import (
    ROUTE_CONTROLLER_STATUS,
    ROUTE_JOB_HEARTBEAT,
    ROUTE_JOB_RESULT,
)


class CetmixTowerDroneController(http.Controller):
    """Inbound API used by drone controllers."""

    def _get_bearer_token(self):
        """Return the bearer token of the request, or an empty string."""
        header = request.httprequest.headers.get("Authorization") or ""
        scheme, __, token = header.partition(" ")
        return token.strip() if scheme.lower() == "bearer" else ""

    def _get_json(self):
        """Return the request JSON object, or None if it is not one."""
        try:
            data = json.loads(request.httprequest.get_data() or b"")
        except ValueError:
            return None
        return data if isinstance(data, dict) else None

    def _respond(self, status):
        return Response(
            json.dumps({"status": status}),
            status=status,
            content_type="application/json",
        )

    def _dispatch(self, model_name, method_name):
        data = self._get_json()
        if data is None:
            return self._respond(400)
        model = request.env[model_name].sudo()
        return self._respond(
            getattr(model, method_name)(self._get_bearer_token(), data)
        )

    @http.route(
        ROUTE_JOB_RESULT,
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
        save_session=False,
    )
    def job_result(self, **kwargs):
        """Receive the result of a job."""
        return self._dispatch("cx.tower.drone.job", "_http_result")

    @http.route(
        ROUTE_JOB_HEARTBEAT,
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
        save_session=False,
    )
    def job_heartbeat(self, **kwargs):
        """Receive a heartbeat of a job."""
        return self._dispatch("cx.tower.drone.job", "_http_heartbeat")

    @http.route(
        ROUTE_CONTROLLER_STATUS,
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
        save_session=False,
    )
    def controller_status(self, **kwargs):
        """Receive the status a controller reports about itself."""
        return self._dispatch("cx.tower.drone.controller", "_http_status")
