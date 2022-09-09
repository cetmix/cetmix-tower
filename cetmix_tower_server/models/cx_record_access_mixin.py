from odoo import fields, models


class CxRecordAccessMixin(models.AbstractModel):
    """Common fields for record based access.
    NB: Access rules in inherited models must be defined separately.
    """

    _name = "cx.record.access.mixin"

    partner_allowed_ids = fields.Many2many(
        string="Allowed Partners",
        comodel_name="res.partner",
    )
    partner_tag_ids = fields.Many2many(
        string="Allowed Partner Tags",
        comodel_name="res.partner.category",
    )
