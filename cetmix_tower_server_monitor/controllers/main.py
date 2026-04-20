import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class CxTowerMonitorController(http.Controller):
    @http.route(
        "/cetmix_tower/monitor/push",
        type="json",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def monitor_push(self, **post):
        """
        Receive metrics from remote server.
        Expected JSON:
        {
            "server_ref": "SRV-001",
            "token": "...",
            "metrics": {
                "ram_total_mb": 16000,
                "ram_used_mb": 8000,
                "ram_free_mb": 8000,
                "disk_total_gb": 100,
                "disk_used_gb": 40,
                "disk_free_gb": 60,
                "cpu_percent": 25.5
            }
        }
        """
        data = request.dispatcher.jsonrequest
        server_ref = data.get("server_ref")
        token = data.get("token")
        metrics_data = data.get("metrics", {})

        if not server_ref or not metrics_data:
            return {"status": "error", "message": "Missing data"}

        server = (
            request.env["cx.tower.server"]
            .sudo()
            .search(
                ["|", ("reference", "=", server_ref), ("name", "=", server_ref)],
                limit=1,
            )
        )

        if not server:
            return {"status": "error", "message": "Server not found"}

        if server.monitor_token != token:
            _logger.warning("Invalid monitor token for server %s", server_ref)
            return {"status": "error", "message": "Invalid token"}

        vals = {
            "server_id": server.id,
            "source": "push",
            "ram_total_mb": metrics_data.get("ram_total_mb"),
            "ram_used_mb": metrics_data.get("ram_used_mb"),
            "ram_free_mb": metrics_data.get("ram_free_mb"),
            "disk_total_gb": metrics_data.get("disk_total_gb"),
            "disk_used_gb": metrics_data.get("disk_used_gb"),
            "disk_free_gb": metrics_data.get("disk_free_gb"),
            "cpu_percent": metrics_data.get("cpu_percent"),
            "cpu_cores": metrics_data.get("cpu_cores", 1),
        }

        metrics = request.env["cx.tower.server.metrics"].sudo().create(vals)
        server.sudo().write({"last_metrics_id": metrics.id})
        server.sudo()._check_monitor_alerts(metrics)

        return {
            "status": "success",
            "metrics_id": metrics.id,
            "next_interval": server.monitor_interval_push,
        }

    @http.route(
        "/cetmix_tower/server/<int:server_id>/metrics/dashboard",
        type="json",
        auth="user",
    )
    def get_dashboard_metrics(self, server_id, **kwargs):
        """Fetch data for the server monitoring dashboard."""
        server = request.env["cx.tower.server"].browse(server_id)
        if not server.exists():
            return {"status": "error", "message": "Server not found"}

        # Check permissions (simplified, in Cetmix Tower it usually follows cx.tower.server ACLs)
        try:
            data = server.get_dashboard_data()
            return {"status": "success", "data": data}
        except Exception as e:
            return {"status": "error", "message": str(e)}
