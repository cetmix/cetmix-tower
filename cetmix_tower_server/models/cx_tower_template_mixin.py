# Copyright (C) 2022 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from jinja2 import Environment, Template, meta
from jinja2 import exceptions as jn_exceptions

from odoo import fields, models
from odoo.exceptions import UserError


class CxTowerTemplateMixin(models.AbstractModel):
    """Used to implement template rendering functions.
    Inherit in your model in case you want to render variable values in it.
    """

    _name = "cx.tower.template.mixin"
    _description = "Cetmix Tower template rendering mixin"

    code = fields.Text(string="Code", help="This field will be rendered by default")

    def get_variables(self):
        """Get the list of variables for templates
        Call to get variables for recordset of the inheriting models

        Returns:
            dict {'record_id': {variables}...}
                NB: 'record_id' is String
        """
        Environment()
        res = {}
        for rec in self:
            res.update({str(rec.id): self.get_variables_from_code(rec.code)})
        return res

    def get_variables_from_code(self, code):
        """Get the list of variables for templates
        Call to get variables from custom code string

        Args:
            code (Text) custom code (eg 'Custom {{ var }} {{ var2 }} ...')
        Returns:
            variables (List) variables (eg ['var','var2',..])
        """
        env = Environment()
        ast = env.parse(code)
        undeclared_variables = meta.find_undeclared_variables(ast)
        return list(undeclared_variables) if undeclared_variables else []

    def render_code(self, **kwargs):
        """Render record 'code' field using variables from kwargs
        Call to render recordset of the inheriting models

        Args:
            **kwargs (dict): {variable: value, ...}
        Returns:
            dict {record_id: rendered_code, ...}}
        """
        res = {}
        for rec in self:
            rendered_code = self.render_code_custom(rec.code, **kwargs)
            res.update({rec.id: rendered_code})

        return res

    def render_code_custom(self, code, **kwargs):
        """Render custom code using variables from kwargs
        Call to render any custom string

        Args:
            code (Text): code to render (eg 'some {{ custom }} text')
            **kwargs (dict): {variable: value, ...}
        Returns:
            rendered_code (text)
        """

        try:
            return Template(code, trim_blocks=True).render(kwargs)
        except jn_exceptions.UndefinedError as e:
            raise UserError(e) from e
