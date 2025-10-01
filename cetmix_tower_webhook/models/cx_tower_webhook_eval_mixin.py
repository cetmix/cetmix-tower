# Copyright (C) 2025 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.safe_eval import safe_eval


class CxTowerWebhookEvalMixin(models.AbstractModel):
    _name = "cx.tower.webhook.eval.mixin"
    _inherit = [
        "cx.tower.template.mixin",
        "cx.tower.key.mixin",
        "cx.tower.yaml.mixin",
        "cx.tower.reference.mixin",
    ]
    _description = "Eval context/code helper for Cetmix Tower Webhook"

    code_help = fields.Html(
        compute="_compute_code_help",
        default=lambda self: self._default_eval_code_help(),
        compute_sudo=True,
    )
    code = fields.Text(
        default=lambda self: self._default_eval_code(),
        required=True,
    )

    @classmethod
    def _get_depends_fields(cls):
        """Add code to the depends fields."""
        return ["code"]

    def _compute_code_help(self):
        """
        Compute code help
        """
        self.code_help = self._default_eval_code_help()

    def _default_eval_code_help(self):
        """
        Return the default code help text for webhook or authenticator.

        We use default because the computation method for this field
        would not be triggered before this record is saved. And we need
        to show the value instantly.

        Returns:
            str: HTML-formatted help string containing available objects and libraries.
        """
        available_libraries = self._get_python_eval_odoo_objects()
        available_libraries.update(self._get_python_eval_libraries())
        help_text_fragments = []
        for key, value in available_libraries.items():
            if key == "server":
                # Server is not available in the webhook/authenticator eval context
                continue
            help_text_fragments.append(f"<li><code>{key}</code>: {value['help']}</li>")

        help_text = "<ul>" + "".join(help_text_fragments) + "</ul>"
        return f"{self._get_default_python_eval_code_help()}{help_text}"

    def _get_python_eval_odoo_objects(self, **kwargs):
        """
        Return Odoo objects available in the eval context.

        Args:
            **kwargs: Optional context values.

        Returns:
            dict: Mapping of object names to their import values and help.
        """
        return self.env["cx.tower.command"]._get_python_command_odoo_objects()

    def _get_python_eval_libraries(self):
        """
        Return Python libraries available in the eval context.

        Returns:
            dict: Mapping of library names to their import values and help.
        """
        return self.env["cx.tower.command"]._get_python_command_libraries()

    def _get_default_python_eval_code_help(self):
        """
        Return the default help text for eval code.

        Returns:
            str: Help text.
        """
        return ""

    def _default_eval_code(self):
        """
        Return the default code for webhook or authenticator.

        Returns:
            str: Default Python code.
        """
        return ""

    def _prepare_webhook_eval_context(self, context_extra=None, default_result=None):
        """
        Build the evaluation context for webhook or authenticator
        safe_eval.

        Args:
            context_extra (dict): Additional context variables
                (payload, headers, etc).
            default_result (dict): Default value for the 'result' variable.

        Returns:
            dict: Prepared eval context.
        """
        context_extra = context_extra or {}
        # Get the Odoo objects first
        imports = self._get_python_eval_odoo_objects(**context_extra)

        # Update with the libraries
        imports.update(self._get_python_eval_libraries())
        eval_context = {key: value["import"] for key, value in imports.items()}

        # Remove server from eval context
        eval_context.pop("server", None)

        # Set default result
        default_result = default_result or {}
        eval_context["result"] = default_result.copy()

        return eval_context

    def _run_webhook_eval_code(self, code, **kwargs):
        """
        Helper to execute user code safely. Returns the 'result' variable from context.

        Args:
            code (str): User code to run
            kwargs:
                key (dict): Extra keys for secret parser
                context_extra (dict): Extra context variables (payload, headers, etc)
                default_result (dict): Default value for the 'result' variable

        Returns:
            dict: The 'result' variable from context
        """
        eval_context = self._prepare_webhook_eval_context(**kwargs)

        if not code:
            # if code is empty, return the default result
            return eval_context["result"]

        # prepare the code for evaluation
        code_and_secrets = self.env["cx.tower.key"]._parse_code_and_return_key_values(
            code, pythonic_mode=True, **kwargs.get("key", {})
        )
        secrets = code_and_secrets.get("key_values")
        webhook_code = code_and_secrets["code"]

        code = self.env["cx.tower.key"]._parse_code(
            webhook_code, pythonic_mode=True, **kwargs.get("key", {})
        )

        # execute user code
        safe_eval(
            code,
            eval_context,
            mode="exec",
            nocopy=True,
        )
        result = eval_context["result"]
        return self._parse_eval_code_result(result, secrets=secrets, **kwargs)

    def _parse_eval_code_result(self, result, secrets=None, **kwargs):
        """
        Post-processes the result returned from webhook/authenticator eval code.

        If 'secrets' are provided, all occurrences of secret values in the
        'message' field of result will be replaced with a spoiler string to
        prevent sensitive information leakage.

        Args:
            result (dict): The dict returned from the executed eval code,
                expected to have at least a 'message' key.
            secrets (dict, optional): A mapping of secret key-value
                pairs used for replacement in 'message'.

        Returns:
            dict: The processed result with secrets masked in the 'message'
                field, if applicable.
        """
        if not isinstance(result, dict):
            raise ValidationError(
                _("Webhook/Authenticator code error: result is not a dict")
            )

        if secrets and isinstance(result.get("message"), str):
            result["message"] = self.env["cx.tower.key"]._replace_with_spoiler(
                result["message"], secrets
            )

        return result
