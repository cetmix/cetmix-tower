# Copyright (C) 2022 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from base64 import b64decode, b64encode

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools import exception_to_unicode

# mapping of field names from template and field names from file
TEMPLATE_FILE_FIELD_MAPPING = {
    "code": "code",
    "file_name": "name",
    "file_type": "file_type",
    "server_dir": "server_dir",
    "keep_when_deleted": "keep_when_deleted",
    "auto_sync": "auto_sync",
}

# to convert to 'relativedelta' object
INTERVAL_TYPES = {
    "minutes": lambda interval: relativedelta(minutes=interval),
    "hours": lambda interval: relativedelta(hours=interval),
    "days": lambda interval: relativedelta(days=interval),
    "weeks": lambda interval: relativedelta(days=7 * interval),
    "months": lambda interval: relativedelta(months=interval),
    "years": lambda interval: relativedelta(years=interval),
}


class CxTowerFile(models.Model):
    """Files"""

    _name = "cx.tower.file"
    _inherit = [
        "cx.tower.template.mixin",
        "cx.tower.reference.mixin",
        "mail.thread",
        "mail.activity.mixin",
        "cx.tower.key.mixin",
    ]
    _description = "Cetmix Tower File"
    _order = "name"

    active = fields.Boolean(default=True)
    name = fields.Char(help="File name WITHOUT path. Eg 'test.txt'")
    rendered_name = fields.Char(
        compute="_compute_render",
        compute_sudo=True,
    )
    template_id = fields.Many2one(
        "cx.tower.file.template",
        inverse="_inverse_template_id",
        index=True,
    )
    server_dir = fields.Char(
        string="Directory on Server",
        required=True,
        default="",
        help="Eg '/home/user' or '/var/log'",
    )
    rendered_server_dir = fields.Char(
        compute="_compute_render",
        compute_sudo=True,
    )
    full_server_path = fields.Char(
        string="Full Path",
        compute="_compute_render",
        compute_sudo=True,
    )
    source = fields.Selection(
        [
            ("tower", "Tower"),
            ("server", "Server"),
        ],
        help="""
            - Tower:  file is pushed from Tower to server.
            - Server: file is pulled from server to Tower.
        """,
    )
    auto_sync = fields.Boolean(
        help="If enabled file will be synced automatically using cron",
        default=False,
    )
    # selection format: interval_number(integer)-interval_type(name of interval)
    # it will be parsed as 'relativedelta' object
    auto_sync_interval = fields.Selection(
        selection=lambda self: self._selection_auto_sync_interval(),
    )
    sync_date_next = fields.Datetime(
        string="Next Sync Date",
        required=True,
        default=fields.Datetime.now,
        help="Date and time of the next synchronisation",
    )
    sync_date_last = fields.Datetime(
        string="Last Sync Date",
        readonly=True,
        tracking=True,
        help="Date and time of the latest successful synchronisation",
    )
    server_response = fields.Text(
        copy=False,
        help="Server response received during the last operation.\n"
        "Default value if no error happened is 'ok'.\n"
        "Otherwise there will be a server error message logged.",
    )
    server_id = fields.Many2one(
        comodel_name="cx.tower.server", required=False, ondelete="cascade"
    )
    code_on_server = fields.Text(
        readonly=True,
        help="Latest version of file content on server",
    )
    rendered_code = fields.Char(
        compute="_compute_render",
        compute_sudo=True,
        help="File content with variables rendered",
    )
    keep_when_deleted = fields.Boolean(
        help="File will be kept on server when deleted in Tower",
    )
    file_type = fields.Selection(
        selection=lambda self: self._selection_file_type(),
        default=lambda self: self._default_file_type(),
        required=True,
    )
    file = fields.Binary(
        string="Binary Content",
        attachment=True,
    )
    variable_ids = fields.Many2many(
        comodel_name="cx.tower.variable",
        relation="cx_tower_file_variable_rel",
        column1="file_id",
        column2="variable_id",
    )

    @classmethod
    def _get_depends_fields(cls):
        """
        Define dependent fields for computing `variable_ids` in file-related models.

        This implementation specifies that the fields `code`, `server_dir`,
        and `name` are used to compute the variables associated with a file.

        Returns:
            list: A list of field names (str) representing the dependencies.

        Example:
            The following fields trigger recomputation of `variable_ids`:
            - `code`: The content of the file.
            - `server_dir`: The directory on the server where the file is located.
            - `name`: The name of the file.
        """
        return ["code", "server_dir", "name"]

    # -- Selection
    def _selection_file_type(self):
        """Available file types

        Returns:
            List of tuples: available options.
        """
        return [
            ("text", "Text"),
            ("binary", "Binary"),
        ]

    def _selection_auto_sync_interval(self):
        """
        Selection of auto sync interval
        """
        return [
            ("10-minutes", "10 min"),
            ("30-minutes", "30 min"),
            ("1-hours", "1 hour"),
            ("2-hours", "2 hour"),
            ("6-hours", "6 hour"),
            ("12-hours", "12 hour"),
            ("1-days", "1 day"),
            ("1-weeks", "1 week"),
            ("1-months", "1 month"),
            ("1-years", "1 year"),
        ]

    # -- Defaults
    def _default_file_type(self):
        """Default file type

        Returns:
            Char: `file_type` field selection value
        """
        return "text"

    # -- Computes
    @api.depends("server_id", "template_id", "name", "server_dir", "code")
    def _compute_render(self):
        """
        Compute file name, directory and code
        """
        for file in self:
            if not file.server_id:
                file.update(
                    {
                        "rendered_name": False,
                        "rendered_server_dir": False,
                        "rendered_code": False,
                        "full_server_path": False,
                    }
                )
                continue
            variables = list(
                set(
                    file.get_variables_from_code(file.name)
                    + file.get_variables_from_code(file.server_dir)
                    + file.get_variables_from_code(file.code)
                )
            )
            render_code_custom = file.render_code_custom
            var_vals = file.server_id.get_variable_values(variables).get(
                file.server_id.id
            )

            rendered_code = ""
            if file.file_type == "text" and file.source == "tower":
                rendered_code = (
                    var_vals
                    and file.code
                    and render_code_custom(file.code, **var_vals)
                    or file.code
                )
            rendered_name = (
                var_vals
                and file.name
                and render_code_custom(file.name, **var_vals)
                or file.name
            )
            rendered_server_dir = (
                var_vals
                and file.server_dir
                and render_code_custom(file.server_dir, **var_vals)
                or file.server_dir
            )
            file.update(
                {
                    "rendered_name": rendered_name,
                    "rendered_server_dir": rendered_server_dir,
                    "rendered_code": rendered_code,
                    "full_server_path": f"{rendered_server_dir}/{rendered_name}",
                }
            )

    # -- Onchange
    @api.onchange("template_id")
    def _onchange_template_id(self):
        """
        Update file data by template values
        """
        for file in self:
            if file.template_id:
                file.update(file._get_file_values_from_related_template())

    @api.onchange("source")
    def _onchange_source(self):
        """
        Reset file template after change source
        """
        self.update({"template_id": False})

    def _inverse_template_id(self):
        """
        Replace file fields values by template values
        """
        for file in self:
            if file.template_id:
                file.write(file._get_file_values_from_related_template())

    # -- Create/Write/Unlink
    @api.model_create_multi
    def create(self, vals_list):
        """
        Override to sync files
        """
        vals_list = [self._sanitize_values(vals) for vals in vals_list]
        records = super().create(vals_list)
        records._post_create_write("create")
        return records

    def write(self, vals):
        """
        Override to sync files from tower
        """
        vals = self._sanitize_values(vals)
        result = super().write(vals)

        # sync tower files after change
        sync_fields = self._get_tower_sync_field_names()
        files_to_sync = self.filtered(
            lambda file: file.auto_sync
            and file.source == "tower"
            and any(field in vals for field in sync_fields)
        )
        if files_to_sync:
            files_to_sync._post_create_write("write")
        return result

    def unlink(self):
        """
        Override to delete from server tower files with
        `keep_when_deleted` set to False
        """
        self.filtered(
            lambda file_: (
                file_.server_id
                and file_.source == "tower"
                and not file_.keep_when_deleted
            )
        ).delete()
        return super().unlink()

    # -- Actions
    def action_unlink_from_template(self):
        """
        Unlink file from template to make it editable
        """
        self.ensure_one()
        self.template_id = False

    def action_push_to_server(self):
        """
        Push the file to server
        """
        server_files = self.filtered(lambda file_: file_.source == "server")
        if server_files:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Failure"),
                    "message": _(
                        "Unable to upload file '%(f)s'.\n"
                        "Upload operation is not supported for 'server' type files.",
                        f=server_files[0].rendered_name,
                    ),
                    "sticky": False,
                },
            }
        self.upload(raise_error=True)
        single_msg = _("File uploaded!")
        plural_msg = _("Files uploaded!")
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Success"),
                "message": single_msg if len(self) == 1 else plural_msg,
                "sticky": False,
            },
        }

    def action_pull_from_server(self):
        """
        Pull file from server
        """
        tower_files = self.filtered(lambda file_: file_.source == "tower")
        server_files = self - tower_files
        tower_files.action_get_current_server_code()
        res = server_files.download(raise_error=True)
        if isinstance(res, dict):
            return res

        single_msg = _("File downloaded!")
        plural_msg = _("Files downloaded!")
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Success"),
                "message": single_msg if len(self) == 1 else plural_msg,
                "sticky": False,
            },
        }

    def action_delete_from_server(self):
        """
        Delete file from server
        """
        server_files = self.filtered(lambda file_: file_.source == "server")
        if server_files:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Failure"),
                    "message": _(
                        "Unable to delete file '%(f)s'.\n"
                        "Delete operation is not supported for 'server' type files.",
                        f=server_files[0].rendered_name,
                    ),
                    "sticky": False,
                },
            }
        self.delete(raise_error=True)
        single_msg = _("File deleted!")
        plural_msg = _("Files deleted!")
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Success"),
                "message": single_msg if len(self) == 1 else plural_msg,
                "sticky": False,
            },
        }

    def action_get_current_server_code(self):
        """
        Get actual file code from server
        """
        for file in self:
            if file.source != "tower":
                raise UserError(
                    _(
                        "File %(f)s is not 'tower' type. "
                        "This operation is supported for 'tower' "
                        "files only",
                        f=file.name,
                    )
                )

            # Calling `_process` directly to get server version of a `tower` file
            res = file.with_context(is_server_code_version_process=True)._process(
                "download"
            )
            # Type check because _process method could return
            # a display_notification action dict
            if isinstance(res, dict):
                return res
            file.code_on_server = res

    # -- Business logic
    def _post_create_write(self, op_type="write"):
        """Helper function that is called after file creation or update.
        Use this function to implement custom hooks.

        Args:
            op_type (str, optional): Operation type. Defaults to "write".
                Possible options:
                    - "create"
                    - "write"
        """

        # Pull all `auto_sync` server files
        server_files_to_sync = self.filtered(
            lambda file: file.auto_sync and file.source == "server"
        )
        if server_files_to_sync:
            server_files_to_sync.action_pull_from_server()

        # Push all `auto_sync` tower files
        tower_files_to_sync = self.filtered(
            lambda file: file.auto_sync and file.source == "tower"
        )
        if tower_files_to_sync:
            tower_files_to_sync.action_push_to_server()

    def _get_file_values_from_related_template(self):
        """
        Return file values from related template
        """
        self.ensure_one()
        if not self.template_id:
            return {}

        values = self.template_id.read(list(TEMPLATE_FILE_FIELD_MAPPING), load=False)[0]
        if (
            self.env.context.get("is_custom_server_dir")
            and self.server_dir
            and "server_dir" in values
        ):
            del values["server_dir"]

        return {
            key: values[name]
            for name, key in TEMPLATE_FILE_FIELD_MAPPING.items()
            if name in values
        }

    @api.model
    def _sanitize_values(self, values):
        """
        Check the values and reformat if necessary
        """
        if "server_dir" in values:
            server_dir = values.get("server_dir", "").strip()
            if server_dir.endswith("/") and server_dir != "/":
                server_dir = server_dir[:-1]
            values.update(
                {
                    "server_dir": server_dir,
                }
            )
        return values

    def download(self, raise_error=False):
        """Wrapper function for file download.
        Use it for custom hooks implementation.

        Args:
            raise_error (bool, optional):
                Will raise and exception on error if set to 'True'.
                Defaults to False.
        """
        return self._process("download", raise_error)

    def upload(self, raise_error=False):
        """Wrapper function for file upload.
        Use it for custom hooks implementation.

        Args:
            raise_error (bool, optional):
                Will raise and exception on error if set to 'True'.
                Defaults to False.
        """
        self._process("upload", raise_error)

    def delete(self, raise_error=False):
        """Wrapper function for file removal.
        Use it for custom hooks implementation.

        Args:
            raise_error (bool, optional):
                Will raise and exception on error if set to 'True'.
                Defaults to False.
        """
        self._process("delete", raise_error)

    def _process_download(
        self,
        tower_key_obj,
        is_server_code_version_process=False,
    ):
        """
        Processing of file download.
        Note: moved this functionality to a separate function from
        the general `_process` method because it is already too complex.

        Args:
            tower_key_obj (RecordSet): `cx.tower.key`
                recordset to parse file path.
            is_server_code_version_process (bool):
                Flag to fetch actual file content from server
                for a `tower` type file.

        Returns:
            [dict|str|None]:
                display_notification action dict if there was an error
                during the operation.
                file content if `is_server_code_version_process` is True.
                None otherwise.
        """
        self.ensure_one()
        code = self.server_id.download_file(
            tower_key_obj._parse_code(self.full_server_path),
        )
        if self.file_type == "text" and b"\x00" in code:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Failure"),
                    "message": _(
                        "Cannot download %(f)s from server: "
                        "Binary content is not supported "
                        "for 'Text' file type",
                    )
                    % {"f": self.rendered_name},
                    "sticky": True,
                },
            }
        # In case server version of a 'tower' file is requested
        if is_server_code_version_process:
            return code
        if self.file_type == "binary":
            self.file = b64encode(code)
        else:
            self.code = code

    def _process(self, action, raise_error=False):
        """Upload or download file to/from server.
        Important!
        This function will return a value only in case `is_server_code_version_process`
        key is present in context.
        This key is used to fetch actual file content from server
        for a `tower` type file.
        In all other cases it will update the file content and save
        server response into the `server_response` field.



        Args:
            action (Selection): Action to process.
                Possible options:
                    - "upload": Upload file.
                    - "download": Download file.
                    - "delete": Delete file.
            raise_error (bool, optional): Raise exception if there was an error
                 during the operation. Defaults to False.

        Raises:
            UserError: In case file format doesn't match the requested operation.
                Eg if trying to upload 'server' type file.
            ValidationError: In case there is an error while performing
                an action with a file.

        Returns:
            Char: file content or False.
        """

        tower_key_obj = self.env["cx.tower.key"]
        is_server_code_version_process = self.env.context.get(
            "is_server_code_version_process"
        )
        for file in self:
            if not is_server_code_version_process and (
                (action == "download" and file.source != "server")
                or (action == "upload" and file.source != "tower")
                or (action == "delete" and file.source != "tower")
            ):
                if raise_error:
                    raise UserError(
                        _(
                            "File %(f)s shouldn't have the '%(src)s' source "
                            " for the '%(act)s' action",
                            f=file.name,
                            src=file.source,
                            act=action,
                        )
                    )
                return False

            if action == "delete":
                try:
                    file.check_access("unlink")
                except AccessError as e:
                    if raise_error:
                        raise AccessError(
                            _(
                                "Due to security restrictions you are "
                                "not allowed to delete %(fp)s",
                                fp=file.full_server_path,
                            )
                        ) from e
                    return False

            try:
                if action == "download":
                    res = file._process_download(
                        tower_key_obj, is_server_code_version_process
                    )
                    if res:
                        return res
                elif action == "upload":
                    if file.file_type == "binary":
                        file_content = b64decode(file.file)
                    else:
                        file_content = tower_key_obj._parse_code(file.rendered_code)
                    file.server_id.upload_file(
                        file_content,
                        tower_key_obj._parse_code(file.full_server_path),
                    )
                elif action == "delete":
                    file.server_id.delete_file(
                        tower_key_obj._parse_code(file.full_server_path)
                    )
                else:
                    return False
                file.sudo().server_response = "ok"
            except Exception as error:
                if raise_error:
                    raise ValidationError(
                        _(
                            "Cannot %(action)s %(f)s to/from server: %(err)s",
                            action=action,
                            f=file.rendered_name,
                            err=exception_to_unicode(error),
                        )
                    ) from error
                file.server_response = repr(error)

        if not is_server_code_version_process:
            self._update_file_sync_date(fields.Datetime.now())

    @api.model
    def _get_tower_sync_field_names(self):
        """
        Return the list of field names to start synchronization
        after changing these fields
        """
        return ["name", "server_dir", "code"]

    @api.model
    def _run_auto_pull_files(self):
        """
        Run auto sync files
        """
        now = fields.Datetime.now()
        files = self.search(
            [
                ("source", "=", "server"),
                ("auto_sync", "=", True),
                ("sync_date_next", "<=", now),
            ]
        )
        files.download(raise_error=False)

    def _update_file_sync_date(self, last_sync_date):
        """
        Compute and update next date of sync
        """
        for file in self:
            vals = {}
            if file.source == "server" and file.auto_sync and file.auto_sync_interval:
                interval, interval_type = file.auto_sync_interval.split("-")
                vals.update(
                    {
                        "sync_date_next": last_sync_date
                        + INTERVAL_TYPES[interval_type](int(interval))
                    }
                )
            if file.server_response == "ok":
                vals.update({"sync_date_last": last_sync_date})
            file.sudo().write(vals)

    # Check cx.tower.reference.mixin for the function documentation
    def _get_pre_populated_model_data(self):
        res = super()._get_pre_populated_model_data()
        res.update({"cx.tower.file": ["cx.tower.server", "server_id"]})
        return res
