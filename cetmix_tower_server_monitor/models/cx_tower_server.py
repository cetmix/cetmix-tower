import base64
import logging
import re
import shlex
import uuid
from datetime import datetime, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class CxTowerServer(models.Model):
    _inherit = "cx.tower.server"

    # Monitoring Configuration
    monitoring_mode = fields.Selection(
        selection=[
            ("none", "None"),
            ("pull", "Pull (SSH)"),
            ("push", "Push (Webhook)"),
        ],
        default="none",
        required=True,
    )
    alert_cpu_pct = fields.Integer(string="CPU Alert (%)", default=85)
    alert_ram_pct = fields.Integer(string="RAM Alert (%)", default=85)
    alert_disk_pct = fields.Integer(string="Disk Alert (%)", default=90)
    monitor_interval_pull = fields.Integer(
        string="Monitor Interval (PULL)",
        default=1,
        help="How often to pull metrics (in minutes). Minimum 1 minute.",
    )
    monitor_interval_push = fields.Integer(
        string="Monitor Interval (PUSH)",
        default=60,
        help="How often the agent should push metrics (in seconds).",
    )

    @api.constrains("monitor_interval_pull", "monitor_interval_push", "monitoring_mode")
    def _check_monitor_intervals(self):
        for rec in self:
            if rec.monitoring_mode == "pull" and rec.monitor_interval_pull < 1:
                raise ValidationError(
                    _("Monitor Interval (PULL) must be at least 1 minute.")
                )
            if rec.monitoring_mode == "push" and rec.monitor_interval_push < 10:
                raise ValidationError(
                    _("Monitor Interval (PUSH) must be at least 10 seconds.")
                )

    monitor_token = fields.Char(
        copy=False,
        groups="cetmix_tower_server.group_manager",
        default=lambda self: str(uuid.uuid4()),
    )
    is_push_agent_installed = fields.Boolean(
        string="Push Agent Installed", default=False, readonly=True
    )
    monitor_push_status = fields.Selection(
        [
            ("none", "No Data"),
            ("active", "Active"),
            ("overdue", "Overdue"),
        ],
        string="Agent Status",
        compute="_compute_monitor_push_status",
    )

    last_metrics_id = fields.Many2one(
        comodel_name="cx.tower.server.metrics",
        string="Last Metrics Snapshot",
        readonly=True,
    )
    cpu_usage_pct = fields.Float(
        related="last_metrics_id.cpu_percent",
        string="CPU Usage (%)",
        readonly=True,
    )
    ram_usage_pct = fields.Float(
        compute="_compute_usage_pct",
        string="RAM Usage (%)",
        readonly=True,
        store=True,
    )
    disk_usage_pct = fields.Float(
        compute="_compute_usage_pct",
        string="Disk Usage (%)",
        readonly=True,
        store=True,
    )
    ram_total_mb = fields.Float(
        related="last_metrics_id.ram_total_mb", string="RAM Total (MB)"
    )
    ram_used_mb = fields.Float(
        related="last_metrics_id.ram_used_mb", string="RAM Used (MB)"
    )
    disk_total_gb = fields.Float(
        related="last_metrics_id.disk_total_gb", string="Disk Total (GB)"
    )
    disk_used_gb = fields.Float(
        related="last_metrics_id.disk_used_gb", string="Disk Used (GB)"
    )
    cpu_cores = fields.Integer(
        related="last_metrics_id.cpu_cores", string="CPU Cores", readonly=True
    )

    @api.depends(
        "last_metrics_id",
        "monitoring_mode",
        "monitor_interval_pull",
        "monitor_interval_push",
    )
    def _compute_monitor_push_status(self):
        now = datetime.now()
        for rec in self:
            if rec.monitoring_mode != "push" or not rec.last_metrics_id:
                rec.monitor_push_status = "none"
                continue

            # Tolerance for PUSH: 2x interval + 10s (since it's in seconds)
            limit = rec.last_metrics_id.create_date + timedelta(
                seconds=(rec.monitor_interval_push * 2) + 10
            )
            if now > limit:
                rec.monitor_push_status = "overdue"
            else:
                rec.monitor_push_status = "active"

    @api.depends("last_metrics_id")
    def _compute_usage_pct(self):
        for server in self:
            metrics = server.last_metrics_id
            ram_pct = 0.0
            disk_pct = 0.0
            if metrics:
                if metrics.ram_total_mb > 0:
                    ram_pct = (metrics.ram_used_mb / metrics.ram_total_mb) * 100.0
                if metrics.disk_total_gb > 0:
                    disk_pct = (metrics.disk_used_gb / metrics.disk_total_gb) * 100.0
            server.ram_usage_pct = ram_pct
            server.disk_usage_pct = disk_pct

    def get_dashboard_data(self):
        """Return historical and current metrics for the monitoring dashboard."""
        self.ensure_one()
        metrics = self.env["cx.tower.server.metrics"].search(
            [("server_id", "=", self.id)], order="timestamp desc", limit=20
        )

        # Reverse to have chronological order for the chart
        metrics = metrics.sorted("timestamp")

        history = {
            "labels": [m.timestamp.strftime("%H:%M:%S") for m in metrics],
            "cpu": [m.cpu_percent for m in metrics],
            "ram": [
                (m.ram_used_mb / m.ram_total_mb * 100) if m.ram_total_mb else 0
                for m in metrics
            ],
            "disk": [
                (m.disk_used_gb / m.disk_total_gb * 100) if m.disk_total_gb else 0
                for m in metrics
            ],
        }

        return {
            "server_id": self.id,
            "name": self.name,
            "monitoring_mode": self.monitoring_mode,
            "monitor_push_status": self.monitor_push_status,
            "last_update": self.last_metrics_id.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            if self.last_metrics_id
            else False,
            "history": history,
            "current": {
                "cpu": self.cpu_usage_pct,
                "ram": self.ram_usage_pct,
                "disk": self.disk_usage_pct,
                "ram_used": self.last_metrics_id.ram_used_mb
                if self.last_metrics_id
                else 0,
                "ram_total": self.last_metrics_id.ram_total_mb
                if self.last_metrics_id
                else 0,
                "disk_used": self.last_metrics_id.disk_used_gb
                if self.last_metrics_id
                else 0,
                "disk_total": self.last_metrics_id.disk_total_gb
                if self.last_metrics_id
                else 0,
                "cpu_cores": self.last_metrics_id.cpu_cores
                if self.last_metrics_id
                else 1,
            },
            "thresholds": {
                "cpu": self.alert_cpu_pct,
                "ram": self.alert_ram_pct,
                "disk": self.alert_disk_pct,
            },
            "monitor_interval": self.monitor_interval_push
            if self.monitoring_mode == "push"
            else self.monitor_interval_pull,
        }

    def action_open_cron(self):
        """Open the scheduled action for monitoring."""
        cron = self.env.ref("cetmix_tower_server_monitor.ir_cron_server_monitor_pull")
        return {
            "type": "ir.actions.act_window",
            "res_model": "ir.cron",
            "res_id": cron.id,
            "view_mode": "form",
            "target": "current",
        }

    @api.model
    def _cron_pull_metrics(self):
        """Method called by the cron to pull metrics for all servers in pull mode."""
        # Find all servers in pull mode
        servers = self.search([("monitoring_mode", "=", "pull")])

        # Filter servers that need an update based on their specific interval
        # We allow a small margin (5s) to avoid missing a cycle due to clock jitter
        now = fields.Datetime.now()
        servers_to_update = self.env["cx.tower.server"]
        for server in servers:
            if not server.last_metrics_id:
                servers_to_update |= server
                continue

            delta = (now - server.last_metrics_id.timestamp).total_seconds()
            if delta >= (server.monitor_interval_pull * 60 - 5):
                servers_to_update |= server

        _logger.warning(
            "Cron Pull: Found %s servers total, updating %s based on intervals",
            len(servers),
            len(servers_to_update),
        )

        if servers_to_update:
            servers_to_update.action_server_monitor_pull()
        return True

    def action_server_monitor_pull(self):
        """Execute SSH commands to fetch server metrics."""
        # Simple feedback: if it's push mod, we just refresh the computed fields
        # if the user manually triggered it.
        for server in self:
            if server.monitoring_mode == "pull":
                server._pull_metrics_ssh()
                server._compute_usage_pct()  # Ensure they are fresh
            elif server.monitoring_mode == "push":
                # Do nothing but we could notify the user or just stay still
                pass
        return True

    def _pull_metrics_ssh(self):
        """Fetch metrics using SSH."""
        self.ensure_one()
        # Commands to get RAM, Disk and CPU in one go or separate
        commands = [
            "free -m",
            "df -m /",
            "top -bn1 | grep -E -i '^(%?Cpu|CPU)' | head -n 1",
            "nproc",
        ]
        # Use ; instead of && to ensure all commands run and capture output best-effort
        full_command = " ; echo '---' ; ".join(commands)

        try:
            client = self._get_ssh_client(raise_on_error=True)
            _logger.warning(
                "Executing monitor command for server %s: %s", self.name, full_command
            )
            res = self._run_command_using_ssh(
                client=client,
                command_code=full_command,
                raise_on_error=False,
            )
            _logger.warning(
                "Monitor command result for %s: status=%s", self.name, res.get("status")
            )

            response_text = res.get("response", "")
            if response_text:
                self._process_monitor_output(response_text)

            if res.get("status") != 0:
                _logger.warning(
                    "Monitor command returned non-zero for server %s. Response: %s",
                    self.name,
                    response_text,
                )
        except Exception as e:
            # Log error in server logs or activities
            _logger.error(
                "Monitoring Pull Exception for server %s: %s", self.name, str(e)
            )
            self.message_post(body=_("Monitoring Pull Error: %s") % str(e))

    def action_monitor_debug(self):
        """Action to show the raw SSH output for debugging."""
        self.ensure_one()
        commands = [
            "free -m",
            "df -m /",
            "top -bn1 | grep -E -i '^(%?Cpu|CPU)' | head -n 1",
        ]
        full_command = " ; echo '---' ; ".join(commands)
        client = self._get_ssh_client(raise_on_error=True)
        res = self._run_command_using_ssh(
            client=client,
            command_code=full_command,
            raise_on_error=False,
        )
        raise ValidationError(
            _(
                "DEBUG MONITOR OUTPUT\n\n"
                "Status: %(status)s\n\n"
                "Response:\n%(response)s\n\n"
                "Error:\n%(error)s"
            )
            % {
                "status": res.get("status"),
                "response": res.get("response"),
                "error": res.get("error"),
            }
        )

    def _process_monitor_output(self, output):
        """Parse the output and create metrics record."""
        self.ensure_one()
        _logger.warning(
            "Parsing monitor output for server %s (length: %s)", self.name, len(output)
        )
        # Log first 200 chars of output for debugging
        _logger.warning("Raw output snippet: %s", output[:200].replace("\n", " | "))
        parts = output.split("---")
        if len(parts) < 3:
            _logger.warning(
                "Invalid monitor output format (too few parts) for server %s", self.name
            )
            return

        ram_out = parts[0].strip()
        disk_out = parts[1].strip()
        cpu_out = parts[2].strip()
        cores_out = parts[3].strip() if len(parts) > 3 else "1"

        # Regular expressions for parsing
        # RAM: free -m output (Matches: Total, Used, Free)
        # Format: Mem: total used free shared buff/cache available
        res_ram = re.search(r"Mem:\s+(\d+)\s+(\d+)\s+(\d+)", ram_out)

        # Disk: df -m / output
        # Format: Filesystem 1M-blocks Used Available Use% Mounted on
        # Capture: 1M-Blocks, Used, Available
        res_disk = re.search(r"(\d+)\s+(\d+)\s+(\d+)\s+\d+%\s+/", disk_out)

        # CPU: top -bn1 output
        # Format: %Cpu(s): 1.0 us, 0.5 sy, ... 98.5 id
        # Capture: Idle percentage (supports dot or comma)
        res_cpu = re.search(r"(\d+(?:[.,]\d+)?)\s*id", cpu_out)

        if not all([res_ram, res_disk, res_cpu]):
            failed = []
            if not res_ram:
                failed.append("RAM")
            if not res_disk:
                failed.append("Disk")
            if not res_cpu:
                failed.append("CPU")
            _logger.error(
                "Metric parsing failed for server %s. Missing: %s.\n"
                "RAM: %s\nDisk: %s\nCPU: %s",
                self.name,
                ", ".join(failed),
                ram_out,
                disk_out,
                cpu_out,
            )
            return

        try:
            metrics_vals = {
                "server_id": self.id,
                "source": "pull",
                "ram_total_mb": float(res_ram.group(1)) if res_ram else 0,
                "ram_used_mb": float(res_ram.group(2)) if res_ram else 0,
                "ram_free_mb": float(res_ram.group(3)) if res_ram else 0,
                "disk_total_gb": float(res_disk.group(1)) / 1024.0 if res_disk else 0,
                "disk_used_gb": float(res_disk.group(2)) / 1024.0 if res_disk else 0,
                "disk_free_gb": float(res_disk.group(3)) / 1024.0 if res_disk else 0,
                "cpu_cores": int(cores_out.strip())
                if cores_out.strip().isdigit()
                else 1,
            }

            if res_cpu:
                idle_str = res_cpu.group(1).replace(",", ".")
                metrics_vals["cpu_percent"] = 100.0 - float(idle_str)
            else:
                _logger.warning(
                    "Could not find CPU idle percentage for server %s in output: %s",
                    self.name,
                    cpu_out,
                )
                metrics_vals["cpu_percent"] = 0.0

            _logger.warning(
                "Created metrics for server %s: CPU %s%%, RAM %s/%s MB",
                self.name,
                metrics_vals["cpu_percent"],
                metrics_vals["ram_used_mb"],
                metrics_vals["ram_total_mb"],
            )

            metrics = self.env["cx.tower.server.metrics"].create(metrics_vals)
            self.last_metrics_id = metrics.id
            self._check_monitor_alerts(metrics)
            self._compute_usage_pct()
        except Exception as e:
            _logger.error(
                "Error creating metrics records for server %s: %s", self.name, str(e)
            )

    def _check_monitor_alerts(self, metrics):
        """Compare metrics with thresholds and create alerts."""
        self.ensure_one()
        alerts = []

        # CPU Alert
        if metrics.cpu_percent > self.alert_cpu_pct:
            alerts.append(
                {
                    "server_id": self.id,
                    "resource": "cpu",
                    "value": metrics.cpu_percent,
                    "threshold": self.alert_cpu_pct,
                }
            )

        # RAM Alert (%)
        if metrics.ram_total_mb > 0:
            ram_pct = (metrics.ram_used_mb / metrics.ram_total_mb) * 100.0
            if ram_pct > self.alert_ram_pct:
                alerts.append(
                    {
                        "server_id": self.id,
                        "resource": "ram",
                        "value": ram_pct,
                        "threshold": self.alert_ram_pct,
                    }
                )

        # Disk Alert (%)
        if metrics.disk_total_gb > 0:
            disk_pct = (metrics.disk_used_gb / metrics.disk_total_gb) * 100.0
            if disk_pct > self.alert_disk_pct:
                alerts.append(
                    {
                        "server_id": self.id,
                        "resource": "disk",
                        "value": disk_pct,
                        "threshold": self.alert_disk_pct,
                    }
                )

        if alerts:
            self.env["cx.tower.server.alert"].create(alerts)
            # Optionally post to chatter
            msg = _("Monitoring Alerts triggered: %s") % (
                ", ".join([a["resource"] for a in alerts])
            )
            self.message_post(body=msg)

    def _get_monitor_agent_script(self):
        """Returns the bash script for the monitoring agent."""
        self.ensure_one()
        base_url = (
            self.env["ir.config_parameter"].sudo().get_param("web.base.url").rstrip("/")
        )

        # Securely escape user input for shell
        url_esc = shlex.quote(f"{base_url}/cetmix_tower/monitor/push")
        token_esc = shlex.quote(self.monitor_token)
        ref_esc = shlex.quote(self.reference or self.name)
        interval_esc = int(self.monitor_interval_push)

        script = f"""#!/bin/bash
# Cetmix Tower Monitor Agent
# Server: {self.name}

URL={url_esc}
TOKEN={token_esc}
REF={ref_esc}
INTERVAL={interval_esc}

# Sanity check for interval
if [ "$INTERVAL" -lt 10 ]; then
    INTERVAL=10
fi

echo "Starting Cetmix Monitor Agent (Interval: $INTERVAL seconds)..."

while true; do
    # Collect Metrics
    MEM_TOTAL=$(grep MemTotal /proc/meminfo | awk '{{print int($2/1024)}}')
    MEM_FREE=$(grep -e MemFree -e Buffers -e "^Cached" /proc/meminfo | \\
        awk '{{sum += $2}} END {{print int(sum/1024)}}')
    MEM_USED=$((MEM_TOTAL - MEM_FREE))

    DISK_TOTAL=$(df -m / | awk 'NR==2 {{print $2}}')
    DISK_USED=$(df -m / | awk 'NR==2 {{print $3}}')

    # CPU: Two samples with 1s delay for accurate measurement
    CPU_N1=($(grep '^cpu ' /proc/stat))
    IDLE1=$((CPU_N1[4] + CPU_N1[5]))
    TOTAL1=0
    for i in {{1..10}}; do TOTAL1=$((TOTAL1 + ${{CPU_N1[i]}})); done

    sleep 1

    CPU_N2=($(grep '^cpu ' /proc/stat))
    IDLE2=$((CPU_N2[4] + CPU_N2[5]))
    TOTAL2=0
    for i in {{1..10}}; do TOTAL2=$((TOTAL2 + ${{CPU_N2[i]}})); done

    IDLE_DIFF=$((IDLE2 - IDLE1))
    TOTAL_DIFF=$((TOTAL2 - TOTAL1))

    if [ "$TOTAL_DIFF" -le 0 ]; then
        CPU_USAGE=0
    else
        CPU_USAGE=$(awk "BEGIN {{print 100 * ($TOTAL_DIFF - $IDLE_DIFF) / $TOTAL_DIFF}}")
    fi

    CPU_CORES=$(nproc 2>/dev/null || echo 1)

    # Format JSON manually
    PAYLOAD='{{"server_ref": "'$REF'", "token": "'$TOKEN'", "metrics": {{'
    PAYLOAD+='"ram_total_mb": '$MEM_TOTAL', "ram_used_mb": '$MEM_USED', '
    PAYLOAD+='"disk_total_gb": '$(awk "BEGIN {{print $DISK_TOTAL/1024}}")', '
    PAYLOAD+='"disk_used_gb": '$(awk "BEGIN {{print $DISK_USED/1024}}")', '
    PAYLOAD+='"cpu_percent": '$CPU_USAGE', "cpu_cores": '$CPU_CORES' }}}}'

    # Send to Tower and get next interval
    RESPONSE=$(curl -s -X POST -H "Content-Type: application/json" -d "$PAYLOAD" "$URL")

    # Simple JSON extraction for next_interval
    NEXT=$(echo "$RESPONSE" | grep -oP '"next_interval":\\s*\\K\\d+')
    if [ ! -z "$NEXT" ] && [ "$NEXT" -ge 10 ]; then
        INTERVAL=$NEXT
    fi

    sleep $INTERVAL
done
"""
        return script

    def action_install_push_agent(self):
        """Deploys the push agent via SSH."""
        self.ensure_one()
        if not self.monitor_token:
            self.monitor_token = str(uuid.uuid4())

        script = self._get_monitor_agent_script()
        client = self._get_ssh_client(raise_on_error=True)

        # 1. Create script file
        # Use base64 to avoid escaping issues with single quotes and special chars
        script_b64 = base64.b64encode(script.encode()).decode()
        cmd_write = (
            f"echo '{script_b64}' | base64 -d | "
            "sudo tee /usr/local/bin/cx_monitor.sh > /dev/null && "
            "sudo chmod +x /usr/local/bin/cx_monitor.sh"
        )
        res = self._run_command_using_ssh(client, cmd_write)
        if res.get("status") != 0:
            raise UserError(_("Failed to deploy script: %s", res.get("error")))

        # 2. Setup Systemd Service
        service_content = """[Unit]
Description=Cetmix Tower Monitor Agent
After=network.target

[Service]
ExecStart=/usr/local/bin/cx_monitor.sh
Restart=always
RestartSec=5
StandardOutput=null
StandardError=journal

[Install]
WantedBy=multi-user.target
"""
        service_b64 = base64.b64encode(service_content.encode()).decode()
        cmd_service = (
            f"echo '{service_b64}' | base64 -d | "
            "sudo tee /etc/systemd/system/cx_monitor.service > /dev/null && "
            "sudo systemctl daemon-reload && "
            "sudo systemctl enable cx_monitor && "
            "sudo systemctl restart cx_monitor"
        )
        res = self._run_command_using_ssh(client, cmd_service)
        if res.get("status") != 0:
            raise UserError(_("Failed to setup systemd service: %s", res.get("error")))

        self.is_push_agent_installed = True
        return True

    def action_uninstall_push_agent(self):
        """Removes the push agent via SSH."""
        self.ensure_one()
        client = self._get_ssh_client(raise_on_error=True)

        cmd_clean = (
            "sudo systemctl stop cx_monitor && "
            "sudo systemctl disable cx_monitor && "
            "sudo rm -f /usr/local/bin/cx_monitor.sh "
            "/etc/systemd/system/cx_monitor.service && "
            "sudo systemctl daemon-reload"
        )
        self._run_command_using_ssh(client, cmd_clean)

        self.is_push_agent_installed = False
        return True
