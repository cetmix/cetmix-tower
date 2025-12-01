# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from jinja2 import Environment, Template, meta
from jinja2.exceptions import TemplateSyntaxError

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class CxTowerTemplateMixin(models.AbstractModel):
    """Used to implement template rendering functions.
    Inherit in your model in case you want to render variable values in it.
    """

    _name = "cx.tower.template.mixin"
    _description = "Cetmix Tower template rendering mixin"

    code = fields.Text(help="This field will be rendered using variables")
    variable_ids = fields.Many2many(
        string="Variables",
        comodel_name="cx.tower.variable",
        compute="_compute_variable_ids",
        store=True,
        copy=False,
    )

    @classmethod
    def _get_depends_fields(cls):
        """
        Define dependent fields for the `variable_ids` computation.

        This method should be overridden in inheriting models to provide
        a list of fields that influence the computation of `variable_ids`.
        These fields are used in the `@api.depends` decorator to trigger
        recomputation when their values change.

        Returns:
            list: A list of field names (str) that are dependencies for
                  the `variable_ids` computation. Default is an empty list.

        Example:
            In a subclass, override as follows:
            >>> @classmethod
            >>> def _get_depends_fields(cls):
            >>>     return ["code", "path"]
        """
        return []

    @api.depends(lambda self: self._get_depends_fields())
    def _compute_variable_ids(self):
        """
        Compute the values of the `variable_ids`
        field based on model-specific dependencies.

        This method retrieves the dependent fields using `_get_depends_fields`
        and dynamically calculates the values of `variable_ids` using the
        `_prepare_variable_commands` method.

        If no dependent fields or relation parameters are defined, the field
        is reset to an empty list.

        Example:
            If dependent fields include `code` and `path`, and the model-specific
            logic links them to variables, this method will update the `variable_ids`
            field accordingly.

        Raises:
            ValidationError: If the field metadata is incorrectly defined or
                             missing required attributes.

        Returns:
            None: The field `variable_ids` is updated in-place for each record.
        """
        depends_fields = self._get_depends_fields()

        for record in self:
            if depends_fields:
                record.variable_ids = record._prepare_variable_commands(depends_fields)
            else:
                record.variable_ids = [(5, 0, 0)]

    def render_code(self, pythonic_mode=False, **kwargs):
        """Render record 'code' field using variables from kwargs
        Call to render recordset of the inheriting models
        Args:
            pythonic_mode (Bool): If True, all variables in kwargs are converted to
                                  strings and wrapped in double quotes.
                                  Default is False.
            **kwargs (dict): {variable: value, ...}
        Returns:
            dict {record_id: rendered_code, ...}
        """
        return {
            rec.id: self.render_code_custom(rec.code, pythonic_mode, **kwargs)
            for rec in self
        }

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
        except Exception as e:
            raise UserError(str(e)) from e

    def get_variables(self):
        """Get the list of variables for templates
        Call to get variables for recordset of the inheriting models

        Returns:
            dict {'record_id': {variables}...}
                NB: 'record_id' is String
        """
        res = {}
        for rec in self:
            res[str(rec.id)] = self.get_variables_from_code(rec.code)
        return res

    def get_variables_from_code(self, code):
        """Get the list of variables for templates
        Call to get variables from custom code string

        Args:
            code (Text) custom code (eg 'Custom {{ var }} {{ var2 }} ...')
        Returns:
            variables (List) variables (eg ['var','var2',..])
        """
        if not code:
            return []
        env = Environment()
        try:
            ast = env.parse(code)
            undeclared_variables = meta.find_undeclared_variables(ast)
            return list(undeclared_variables) if undeclared_variables else []
        except TemplateSyntaxError as e:
            raise ValidationError(_("Variable syntax error: %s", e)) from e

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
