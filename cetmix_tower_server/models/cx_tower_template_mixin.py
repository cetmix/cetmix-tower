# Copyright (C) 2024 Cetmix OÜ
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

    def _prepare_variable_commands(self, field_names, force_record=None):
        """
        Prepares commands to set variable references from the given fields.

        Args:
            field_names (list): List of field names to extract variable references from.
            force_record (record, optional): A record to use instead of the current one.

        Returns:
            list: An Odoo command to assign or clear variable references.
        """
        record = force_record or self
        record.ensure_one()

        all_references = set()
        for field_name in field_names:
            value = getattr(record, field_name, None)
            if value:
                all_references.update(self.get_variables_from_code(value))

        if all_references:
            variables = self.env["cx.tower.variable"].search(
                [("reference", "in", list(all_references))]
            )
            command = [(6, 0, variables.ids)]
        else:
            command = [(5, 0, 0)]

        return command

    def render_code(self, pythonic_mode=False, **kwargs):
        """Render record 'code' field using variables from kwargs
        Call to render recordset of the inheriting models

        Args:
            pythonic_mode (Bool): If True, all variables in kwargs are converted to
                                  strings and wrapped in double quotes.
                                  Default is False.
            **kwargs (dict): {variable: value, ...}
        Returns:
            dict {record_id: rendered_code, ...}}
        """
        res = {}
        for rec in self:
            rendered_code = self.render_code_custom(rec.code, pythonic_mode, **kwargs)
            res.update({rec.id: rendered_code})

        return res

    def render_code_custom(self, code, pythonic_mode=False, **kwargs):
        """
        Render custom code using variables from kwargs

        This method renders a template string (code) using the variables provided
        in kwargs. If pythonic_mode is enabled, all variables are automatically
        converted to strings and enclosed in double quotes before rendering.

        Args:
            code (Text): code to render (eg 'some {{ custom }} text')
            pythonic_mode (Bool): If True, all variables in kwargs are converted to
                                  strings and wrapped in double quotes.
                                  Default is False.
            **kwargs (dict): {variable: value, ...}
        Returns:
            rendered_code (text): The resulting string after rendering the template with
                                  the provided variables.
        """
        try:
            if pythonic_mode:
                kwargs = {
                    key: self._make_value_pythonic(value)
                    for key, value in kwargs.items()
                }
            return Template(code, trim_blocks=True).render(kwargs)
        except jn_exceptions.UndefinedError as e:
            raise UserError(e) from e

    def _make_value_pythonic(self, value):
        """Prepares value for use in 'pythonic' mode
            by enclosing strings into double quotes

        Args:
            value (Char): value to process

        Returns:
            Char: processed value
        """

        # Nothing to do here
        if isinstance(value, bool) or value is None:
            result = value

        # Handle nested dicts such as system variables
        elif isinstance(value, dict):
            result = {}
            for key, val in value.items():
                result.update({key: self._make_value_pythonic(val)})
        else:
            # Enclose in double quotes
            result = f'"{value}"'
        return result
