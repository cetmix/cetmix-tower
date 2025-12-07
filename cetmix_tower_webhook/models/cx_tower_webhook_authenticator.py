# Copyright (C) 2025 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import ipaddress
import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.http import request

from .constants import (
    DEFAULT_WEBHOOK_AUTHENTICATOR_CODE,
    DEFAULT_WEBHOOK_AUTHENTICATOR_CODE_HELP,
)

_logger = logging.getLogger(__name__)


class CxTowerWebhookAuthenticator(models.Model):
    """Webhook Authenticator"""

    _name = "cx.tower.webhook.authenticator"
    _inherit = [
        "cx.tower.webhook.eval.mixin",
    ]
    _description = "Webhook Authenticator"

    log_count = fields.Integer(
        compute="_compute_log_count",
    )
    allowed_ip_addresses = fields.Text(
        string="Allowed IPs",
        help="Comma-separated list of IP addresses and/or subnets "
        "(e.g. 192.168.1.10,192.168.2.0/24,10.0.0.1,2001:db8::/32,2a00:1450:4001:824::200e). "  # noqa: E501
        "Requests from other addresses will be denied.",
    )
    trusted_proxy_ips = fields.Text(
        string="Trusted Proxy IPs",
        help="Comma-separated list of trusted proxy IP addresses or CIDR ranges "
        "(e.g., 10.0.0.1,192.168.1.0/24). "
        "Only these proxies can set X-Forwarded-For headers.",
    )
    variable_ids = fields.Many2many(
        comodel_name="cx.tower.variable",
        relation="cx_tower_webhook_authenticator_variable_rel",
        column1="webhook_authenticator_id",
        column2="variable_id",
    )

    @api.constrains("trusted_proxy_ips")
    def _check_trusted_proxy_ips(self):
        """
        Validate 'trusted_proxy_ips' entries. Accepts single IPs and CIDR ranges
        (IPv4/IPv6). Empty value is allowed.
        """
        for rec in self:
            invalid = self._validate_ip_token((rec.trusted_proxy_ips or "").strip())
            if invalid:
                raise ValidationError(_("Invalid trusted proxy entry: %s") % invalid)

    @api.constrains("allowed_ip_addresses")
    def _check_allowed_ip_addresses(self):
        """
        Validate 'allowed_ip_addresses' entries. Accepts single IPs and CIDR
        ranges (IPv4/IPv6). Empty value is allowed (means allow all).
        """
        for rec in self:
            invalid = self._validate_ip_token((rec.allowed_ip_addresses or "").strip())
            if invalid:
                raise ValidationError(_("Invalid allowed IP/CIDR entry: %s") % invalid)

    def _compute_log_count(self):
        """Compute log count."""
        data = {
            webhook.id: count
            for webhook, count in self.env["cx.tower.webhook.log"]._read_group(
                domain=[("authenticator_id", "in", self.ids)],
                groupby=["authenticator_id"],
                aggregates=["__count"],
            )
        }
        for rec in self:
            rec.log_count = data.get(rec.id, 0)

    def _default_eval_code(self):
        """
        Return the default Python code for the webhook authenticator.

        Returns:
            str: Default authenticator code.
        """
        return _(DEFAULT_WEBHOOK_AUTHENTICATOR_CODE)

    def _get_default_python_eval_code_help(self):
        """
        Return the default help text for the authenticator code.

        Returns:
            str: Code help description.
        """
        return _(DEFAULT_WEBHOOK_AUTHENTICATOR_CODE_HELP)

    def _get_python_eval_odoo_objects(self, **kwargs):
        """
        Extend the Python evaluation context with custom Odoo objects.

        Args:
            **kwargs: Extra context values, e.g.:
                - "headers": request headers (dict)
                - "raw_data": request body (bytes)
                - "payload": parsed request payload (dict)

        Returns:
            dict: Mapping of variables available in evaluation context.
        """
        res = {
            "headers": {
                "import": kwargs.get("headers"),
                "help": _("Dictionary of request headers"),
            },
            "raw_data": {
                "import": kwargs.get("raw_data"),
                "help": _("Raw body of the request (bytes)"),
            },
            "payload": {
                "import": kwargs.get("payload"),
                "help": _(
                    "Dictionary containing the request payload "
                    "(JSON for POST, params for GET)"
                ),
            },
        }
        res.update(super()._get_python_eval_odoo_objects(**kwargs))
        return res

    def _get_fields_for_yaml(self):
        """
        Extend fields available for YAML export.

        Returns:
            list[str]: List of field names.
        """
        res = super()._get_fields_for_yaml()
        res += [
            "name",
            "code",
            "allowed_ip_addresses",
            "trusted_proxy_ips",
            "variable_ids",
            "secret_ids",
        ]
        return res

    def authenticate(self, raise_on_error=True, **kwargs):
        """
        Run the authenticator code and return result.

        Args:
            raise_on_error (bool): Raise ValidationError on error if True.
            kwargs: Additional variables passed to the code context, e.g.:
                - "headers": request headers (dict)
                - "raw_data": request body (bytes)
                - "payload": parsed request payload (dict)

        Returns:
            dict: {
                "allowed": <bool>,
                "http_code": <int, optional>,
                "message": <str, optional>,
            }
        """
        self.ensure_one()
        try:
            result = self._run_webhook_eval_code(
                self.code,
                context_extra={
                    "headers": kwargs.get("headers"),
                    "raw_data": kwargs.get("raw_data"),
                    "payload": kwargs.get("payload"),
                },
                default_result={"allowed": False},
            )
        except Exception as e:
            if raise_on_error:
                raise ValidationError(_("Authentication code error: %s") % e) from e
            result = {
                "allowed": False,
                "http_code": 500,
                "message": str(e),
            }

        return result

    def action_view_logs(self):
        """
        Open the action displaying logs related to this authenticator.

        Returns:
            dict: Action dictionary for `ir.actions.act_window`.
        """
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "cetmix_tower_webhook.cx_tower_webhook_log_action"
        )
        action["domain"] = [("authenticator_id", "=", self.id)]
        return action

    def is_ip_allowed(self, remote_addr):
        """
        Proxy-aware allowlist check.

        Steps:
            1) Compute the effective client IP.
            2) If 'allowed_ip_addresses' is empty: allow everyone (backward compatible).
            3) Otherwise, allow only if the client IP belongs to any network in
               'allowed_ip_addresses'.

        Args:
            remote_addr (str): Immediate TCP peer IP (controller-provided).

        Returns:
            bool: True if client IP is allowed, False otherwise.
        """
        self.ensure_one()

        client_ip = self._effective_client_ip(remote_addr)
        if not client_ip:
            return False

        spec = (self.allowed_ip_addresses or "").strip()
        if not spec:
            return True

        allowed_nets = self._parse_ip_list_to_networks(spec)
        if not allowed_nets:
            # Misconfigured allowlist: fail closed
            return False

        return any(client_ip in net for net in allowed_nets)

    def _effective_client_ip(self, remote_addr):
        """
        Compute the effective client IP for the current HTTP request.

        Security model:
            - The immediate TCP peer is 'remote_addr'
              (or request.httprequest.remote_addr).
            - X-Forwarded-For / X-Real-IP are honored ONLY if the immediate peer
              is within 'trusted_proxy_ips' (single IPs or CIDR ranges).
            - If not behind a trusted proxy, headers are ignored to prevent spoofing.

        Args:
            remote_addr (str): Immediate TCP peer IP passed by the controller.

        Returns:
            ipaddress.IPv4Address|ipaddress.IPv6Address|None:
            Effective client IP or None.
        """
        immediate_peer = remote_addr or getattr(
            getattr(request, "httprequest", None), "remote_addr", None
        )
        if not immediate_peer:
            return None

        try:
            immediate_ip = ipaddress.ip_address(immediate_peer)
        except (ValueError, TypeError):
            return None

        client_ip = immediate_ip  # default to immediate peer
        trusted_nets = self._parse_ip_list_to_networks(
            (self.trusted_proxy_ips or "").strip()
        )
        headers = getattr(getattr(request, "httprequest", None), "headers", {}) or {}
        is_trusted_proxy = (
            any(immediate_ip in net for net in trusted_nets) if trusted_nets else False
        )

        if is_trusted_proxy:
            candidate = self._extract_ip_from_header(headers.get("X-Forwarded-For"))
            if not candidate:
                candidate = self._extract_ip_from_header(headers.get("X-Real-IP"))
            if candidate:
                try:
                    client_ip = ipaddress.ip_address(candidate)
                except ValueError:
                    # Fall back to immediate peer if candidate is invalid.
                    _logger.warning("Invalid IP/CIDR entry")

        return client_ip

    def _extract_ip_from_header(self, header_value):
        """
        Extract the first valid IP from a proxy-provided header.

        Behavior:
            - For X-Forwarded-For, the left-most entry is
              considered the original client IP.
            - For X-Real-IP, the value itself is considered.
            - Any non-IP tokens are skipped.

        Args:
            header_value (str): Raw header value (may contain commas for XFF).

        Returns:
            str|None: Compressed IPv4/IPv6 string, or None if nothing valid is found.
        """
        if not header_value:
            return None

        for token in header_value.split(","):
            ip_str = token.strip()
            if not ip_str:
                continue
            try:
                return ipaddress.ip_address(ip_str).compressed
            except ValueError:
                continue
        return None

    @staticmethod
    def _parse_ip_list_to_networks(spec):
        """
        Convert a CSV of IPs/CIDRs into a list of ip_network objects.
        Single IPs are normalized to /32 (IPv4) or /128 (IPv6).

        Args:
            spec (str): CSV of IPs/CIDRs.

        Returns:
            list[ipaddress.IPv4Network|ipaddress.IPv6Network]
        """
        nets = []
        if not spec:
            return nets
        for part in spec.split(","):
            s = (part or "").strip()
            if not s:
                continue
            try:
                nets.append(ipaddress.ip_network(s, strict=False))
                continue
            except ValueError:
                _logger.warning(
                    "Invalid IP/CIDR entry encountered in "
                    "trusted_proxy_ips configuration."
                )
            try:
                ip = ipaddress.ip_address(s)
                nets.append(
                    ipaddress.ip_network(
                        ip.exploded + ("/32" if ip.version == 4 else "/128")
                    )
                )
            except ValueError:
                # Ignore invalid entries silently; validation is handled by constraints.
                continue
        return nets

    def _validate_ip_token(self, spec):
        """
        Return the first invalid token from a CSV of IPs/CIDRs,
        or None if all valid.
        Accepts single IPs and CIDR ranges (IPv4/IPv6).
        Empty/whitespace tokens are ignored.
        """
        if not spec:
            return None
        for part in spec.split(","):
            s = (part or "").strip()
            if not s:
                continue
            try:
                ipaddress.ip_network(s, strict=False)
                continue
            except ValueError:
                _logger.warning("Invalid IP/CIDR entry encountered")
                pass
            try:
                ipaddress.ip_address(s)
            except ValueError:
                return s
        return None
