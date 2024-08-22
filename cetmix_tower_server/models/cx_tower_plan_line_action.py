# Copyright (C) 2022 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import _, api, fields, models


class CxTowerPlanLineAction(models.Model):
    _inherit = ["cx.tower.variable.mixin"]
    _name = "cx.tower.plan.line.action"
    _description = "Cetmix Tower Flight Plan Line Action"

    active = fields.Boolean(default=True)
    name = fields.Char(compute="_compute_name")
    sequence = fields.Integer(default=10)
    line_id = fields.Many2one(comodel_name="cx.tower.plan.line", auto_join=True)
    condition = fields.Selection(
        selection=[
            ("==", "=="),
            ("!=", "!="),
            (">", ">"),
            (">=", ">="),
            ("<", "<"),
            ("<=", "<="),
        ],
        required=True,
    )
    value_char = fields.Char(string="Result", required=True)
    action = fields.Selection(
        selection=[
            ("e", "Exit with command exit code"),
            ("ec", "Exit with custom exit code"),
            ("n", "Run next command"),
        ],
        required=True,
        default="n",
    )
    custom_exit_code = fields.Integer(
        help="Will be used instead of the command exit code"
    )
    access_level = fields.Selection(
        related="line_id.access_level",
        readonly=True,
        store=True,
    )
    variable_value_ids = fields.One2many(
        inverse_name="action_id"  # Other field properties are defined in mixin
    )

    @api.depends("condition", "action", "value_char")
    def _compute_name(self):
        action_selection_vals = dict(self._fields["action"].selection)  # type: ignore
        for rec in self:
            # Some values are not updated until record is not saved.
            # This is a disclaimer to avoid misunderstanding
            if not isinstance(rec.id, int):
                rec.name = _(
                    "...save record to see the final expression "
                    "or click the line to edit"
                )

            # Compose name based on values
            elif rec.condition and rec.action and rec.value_char:
                action_string = action_selection_vals.get(rec.action)

                # Add custom exit code if action presumes it
                if rec.action == "ec":
                    action_string = "{} {}".format(action_string, rec.custom_exit_code)
                rec.name = " ".join(
                    (
                        _("If exit code"),
                        rec.condition,
                        rec.value_char,
                        _("then"),
                        action_string,
                    )
                )
            else:
                rec.name = _("Wrong action")
