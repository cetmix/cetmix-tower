from jinja2 import Environment, Template, meta

from odoo import fields, models


class CxTowerTemplateMixin(models.AbstractModel):
    """Used to implement template rendering functions"""

    _name = "cx.tower.template.mixin"
    _description = "Cetmix Tower template rendering mixin"

    code = fields.Text(string="Code")

    def get_variables(self):
        """Get the list of variables for templates
        Returns:
            dict {record_id: {variables}...}
        """
        env = Environment()
        res = {}
        for rec in self:
            ast = env.parse(rec.code)
            undeclared_variables = meta.find_undeclared_variables(ast)
            res.update(
                {rec.id: list(undeclared_variables) if undeclared_variables else []}
            )
        return res

    def render_code(self, **kwargs):
        """Render code using variables from kwargs

        Args:
            **kwargs (dict): {variable: value, ...}
        Returns:
            dict {record_id: rendered_code, ...}}
        """
        res = {}
        for rec in self:
            rendered_code = Template(rec.code).render(kwargs)
            res.update({rec.id: rendered_code})

        return res
