from odoo import fields, models


class CxTowerCommandLog(models.Model):
    _name = "cx.tower.command.log"
    _description = "Cetmix Tower Command Log"
    _order = "finish_date desc"

    name = fields.Char(compute="_compute_name", compute_sudo=True)
    label = fields.Char(help="Custom label. Can be used for search/tracking")
    server_id = fields.Many2one(comodel_name="cx.tower.server")
    command_id = fields.Many2one(comodel_name="cx.tower.command")
    code = fields.Text(string="Command Code")
    start_date = fields.Datetime(string="Finished")
    finish_date = fields.Datetime(string="Finished")
    duration = fields.Float(
        string="Duration, sec", help="Time consumed for execution, seconds"
    )
    command_status = fields.Integer(string="Status")
    command_response = fields.Text(string="Response")
    command_error = fields.Text(string="Error")

    def _compute_name(self):
        for rec in self:
            rec.name = ": ".join((rec.server_id.name, rec.command_id.name))

    def record(
        self,
        server_id,
        command_id,
        start_date,
        finish_date,
        status=0,
        response=None,
        error=None,
        **kwargs
    ):
        """Record completed command directly without using start/stop

        Args:
            server_id (int) id of the server.
            command_id (int) id of the command.
            start_date (datetime) command start date time.
            finish_date (datetime) command finish date time.
            status (int, optional): command execution status. Defaults to 0.
            response (list, optional): SSH response. Defaults to None.
            error (list, optional): SSH error. Defaults to None.
            **kwargs (dict): values to store
        Returns:
            (cx.tower.command.log()) new command log record
        """

        # Compute duration
        duration = (finish_date - start_date).total_seconds()
        if duration < 0:
            duration = 0

        # Compose response message
        command_response = ""
        if response:
            for r in response:
                command_response = (
                    "{}\n{}".format(command_response, r) if command_response else r
                )

        # Compose error message
        command_error = ""
        if error:
            for e in error:
                command_error = (
                    "{}\n{}".format(command_error, e) if command_error else e
                )

        vals = kwargs or {}
        vals.update(
            {
                "server_id": server_id,
                "command_id": command_id,
                "start_date": start_date,
                "finish_date": finish_date,
                "duration": duration,
                "command_status": status,
                "command_response": command_response,
                "command_error": command_error,
            }
        )
        return self.sudo().create(vals)
