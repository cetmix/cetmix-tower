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
    _name = "cx.tower.file"
    _inherit = ["cx.tower.template.mixin", "mail.thread", "mail.activity.mixin"]
    _description = "Cx Tower File"
    _order = "name"

    active = fields.Boolean(default=True)
    name = fields.Char(help="File name WITHOUT path. Eg 'test.txt'")
    rendered_name = fields.Char(
        compute="_compute_render",
    )
    template_id = fields.Many2one(
        "cx.tower.file.template", inverse="_inverse_template_id"
    )
    server_dir = fields.Char(
        string="Directory on server",
        required=True,
        default="",
        help="Eg '/home/user' or '/var/log'",
    )
    rendered_server_dir = fields.Char(
        compute="_compute_render",
    )
    full_server_path = fields.Char(
        compute="_compute_full_server_path",
    )
    source = fields.Selection(
        [
            ("tower", "Tower"),
            ("server", "Server"),
        ],
        inverse="_inverse_source",
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
        [
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
        ],
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
        help="Server response received during the last operation.\n"
        "Default value if no error happened is 'ok'.\n"
        "Otherwise there will be a server error message logged."
    )
    server_id = fields.Many2one(comodel_name="cx.tower.server", required=True)
    code_on_server = fields.Text(
        readonly=True,
        help="Latest version of file content on server",
    )
    rendered_code = fields.Char(
        compute="_compute_render",
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
        attachment=True,
    )

    def _selection_file_type(self):
        """Available file types

        Returns:
            List of tuples: available options.
        """
        return [
            ("text", "Text"),
            ("binary", "Binary"),
        ]

    def _default_file_type(self):
        """Default file type

        Returns:
            Char: `file_type` field selection value
        """
        return "text"

    @api.depends("server_dir", "name")
    def _compute_full_server_path(self):
        """
        Compute server file path by file type and server directory
        """
        for file in self:
            file.full_server_path = "{}/{}".format(
                file.rendered_server_dir, file.rendered_name
            )

    @api.depends("server_id", "template_id", "name", "server_dir", "code")
    def _compute_render(self):
        """
        Compute name of file by template and server variables
        """
        for file in self:
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
            file.update(
                {
                    "rendered_name": var_vals
                    and file.name
                    and render_code_custom(file.name, **var_vals)
                    or file.name,
                    "rendered_server_dir": var_vals
                    and file.server_dir
                    and render_code_custom(file.server_dir, **var_vals)
                    or file.server_dir,
                    "rendered_code": rendered_code,
                }
            )

    def _inverse_template_id(self):
        """
        Replace file fields values by template values
        """
        for file in self.filtered(
            lambda rec: rec.template_id and rec.source == "tower"
        ):
            file.write(file._get_file_values_from_related_template())

    def _inverse_source(self):
        """
        Unlink file template if source is not tower
        """
        self.filtered(lambda rec: rec.source != "tower").template_id = False

    @api.onchange("template_id")
    def _onchange_template_id(self):
        """
        Update file data by template values
        """
        for rec in self:
            if rec.template_id:
                rec.update(self._get_file_values_from_related_template())

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

    def action_modify_code(self):
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
            res = self.with_context(is_server_code_version_process=True)._process(
                "download"
            )
            # Type check because _process method could return
            # a display_notification action dict
            if isinstance(res, dict):
                return res
            file.code_on_server = res

    def _get_file_values_from_related_template(self):
        """
        Return file values from related template
        """
        self.ensure_one()
        if not self.template_id:
            return {}
        values = self.template_id.read(list(TEMPLATE_FILE_FIELD_MAPPING), load=False)[0]
        return {
            key: values[name]
            for name, key in TEMPLATE_FILE_FIELD_MAPPING.items()
            if values[name]
        }

    @api.model
    def _sanitize_values(self, values):
        """
        Check the values and reformat if necessary
        """
        if "server_dir" in values:
            server_dir = values["server_dir"].strip()
            values.update(
                {
                    "server_dir": server_dir.endswith("/")
                    and server_dir[:-1]
                    or server_dir,
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
            tower_key_obj.parse_code(self.full_server_path),
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
                    file.check_access_rights("unlink")
                    file.check_access_rule("unlink")
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
                        file_content = tower_key_obj.parse_code(file.rendered_code)
                    file.server_id.upload_file(
                        file_content,
                        tower_key_obj.parse_code(file.full_server_path),
                    )
                elif action == "delete":
                    file.server_id.delete_file(
                        tower_key_obj.parse_code(file.full_server_path)
                    )
                else:
                    return False
                file.server_response = "ok"
            except Exception as error:
                if raise_error:
                    raise ValidationError(
                        _(
                            "Cannot pull %(f)s from server: %(err)s",
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
            if file.source == "server" and file.auto_sync:
                interval, interval_type = file.auto_sync_interval.split("-")
                vals.update(
                    {
                        "sync_date_next": last_sync_date
                        + INTERVAL_TYPES[interval_type](int(interval))
                    }
                )
            if file.server_response == "ok":
                vals.update({"sync_date_last": last_sync_date})
            file.write(vals)
