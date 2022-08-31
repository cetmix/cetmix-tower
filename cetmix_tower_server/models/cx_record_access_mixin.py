from odoo import models


class CxRecordAccessMixin(models.AbstractModel):
    """Common fields for record based access.
    Rules must be defined separately in inheriting model
    """

    _name = "cx.record.access.mixin"
