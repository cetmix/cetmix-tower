# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import exception_to_unicode

# mapping of field names from template and field names from file
TEMPLATE_FILE_FIELD_MAPPING = {
    "file_name": "name",
    "server_dir": "server_dir",
    "code": "code",
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
    _inherit = "cx.tower.template.mixin"
    _description = "Cx Tower File"

    @api.onchange("template_id")
    def _onchange_template_id(self):
        """
        Update file data by template values
        """
        if self.template_id:
            self.update(self._get_file_values_from_related_template())

    @api.depends("server_dir", "name")
    def _compute_full_server_path(self):
        """
        Compute server file path by file type and server directory
        """
        for file in self:
            file.full_server_path = "{}/{}".format(
                file.rendered_server_dir, file.rendered_name
            )

    @api.depends("template_id", *TEMPLATE_FILE_FIELD_MAPPING.values())
    def _compute_is_dirty(self):
        """
        Set dirty to True if file and template values do not match
        """
        for file in self:
            vals = file._get_file_values_from_related_template()
            if (
                file.template_id
                and file.source == "tower"
                and any(file[field] != vals[field] for field in vals.keys())
            ):
                file.is_dirty = True
            else:
                file.is_dirty = False

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
            file.update(
                {
                    "rendered_name": var_vals
                    and render_code_custom(file.name, **var_vals)
                    or file.name,
                    "rendered_server_dir": var_vals
                    and render_code_custom(file.server_dir, **var_vals)
                    or file.server_dir,
                    "rendered_code": var_vals
                    and render_code_custom(file.code, **var_vals)
                    or file.code,
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

    name = fields.Char(help="Full file name with file type for example: test.txt")
    rendered_name = fields.Char(
        compute="_compute_render",
    )
    template_id = fields.Many2one(
        "cx.tower.file.template", inverse="_inverse_template_id"
    )
    server_dir = fields.Char(
        string="Directory on server",
        required=True,
        default="~",
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
            - Tower - the file is pushed from Tower to server.
            - Server - the file is pulled from server to tower.
        """,
    )
    auto_sync = fields.Boolean(
        help="If file is synced automatically",
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
        help="Next planned sync date with server.",
    )
    sync_date_last = fields.Datetime(
        string="Last Sync Date",
        readonly=True,
        help="Previous time the file sync successfully",
    )
    sync_code = fields.Text()
    server_id = fields.Many2one(
        comodel_name="cx.tower.server",
        required=True,
    )
    rendered_code = fields.Char(
        compute="_compute_render",
    )
    is_dirty = fields.Boolean(
        compute="_compute_is_dirty",
    )

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

    @api.model_create_multi
    def create(self, vals_list):
        """
        Override to sync files
        """
        records = super(CxTowerFile, self).create(vals_list)
        records.filtered(
            lambda file: file.auto_sync and file.source == "server"
        ).action_pull_from_server()
        records.filtered(
            lambda file: file.auto_sync and file.source == "tower"
        ).action_push_to_server()
        return records

    def write(self, vals):
        """
        Override to sync files from tower
        """
        result = super(CxTowerFile, self).write(vals)

        if "template_id" not in vals:
            # remove template for dirty files
            for file in self.filtered(lambda rec: rec.is_dirty and rec.template_id):
                file.template_id = False

        # sync tower files after change
        sync_fields = self._get_tower_sync_field_names()
        self.filtered(
            lambda file: file.auto_sync
            and file.source == "tower"
            and any(field in vals for field in sync_fields)
        ).action_push_to_server()
        return result

    def action_push_to_server(self):
        """
        Push the file to server
        """
        self._process("upload", raise_error=True)
        self._update_file_sync_date(fields.Datetime.now())

    def action_pull_from_server(self):
        """
        Pull file from server
        """
        self._process("download", raise_error=True)
        self._update_file_sync_date(fields.Datetime.now())

    def _process(self, action, raise_error=True):
        """
        Main process of file manipulation
        """
        tower_key_obj = self.env["cx.tower.key"]
        for file in self:
            if (action == "download" and file.source != "server") or (
                action == "upload" and file.source != "tower"
            ):
                if raise_error:
                    raise UserError(
                        _(
                            "The file shouldn't have the {} source to {} from server!".format(
                                file.source, action
                            )
                        )
                    )
                return False

            try:
                if action == "download":
                    file.code = file.server_id.download_file(
                        tower_key_obj.parse_code(file.full_server_path)
                    )
                elif action == "upload":
                    file.server_id.upload_file(
                        tower_key_obj.parse_code(file.rendered_code),
                        tower_key_obj.parse_code(file.full_server_path),
                    )
                else:
                    return False
                file.sync_code = "ok"
            except Exception as error:
                if raise_error:
                    raise ValidationError(
                        _(
                            "Cannot pull the file {} from server: {}".format(
                                file.rendered_name, exception_to_unicode(error)
                            )
                        )
                    )
                file.sync_code = repr(error)

    @api.model
    def _get_tower_sync_field_names(self):
        """
        Return the list of field names to start synchronization after changing these fields
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
                ("sync_date_next", "=<", now),
            ]
        )._process("download", raise_error=False)
        files._update_file_sync_date(now)

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
            if file.sync_code == "ok":
                vals.update({"sync_date_last": last_sync_date})
            file.write(vals)
