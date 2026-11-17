# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models


class CxTowerWebhookEvalMixin(models.AbstractModel):
    _inherit = "cx.tower.webhook.eval.mixin"

    def _get_python_eval_odoo_objects(self, **kwargs):
        """Remove the current metric from webhook and authenticator code.

        A webhook payload is not bound to one metric.
        Use ``tower_metrics`` instead.
        """
        res = super()._get_python_eval_odoo_objects(**kwargs)
        res.pop("metric", None)
        res.pop("metric_value", None)
        return res
