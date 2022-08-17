from odoo import fields, models


class CxTowerCommandLog(models.Model):
    _name = "cx.tower.command.log"
    _description = "Cetmix Tower Command Log"
    _order = "finish_date desc"

    name = fields.Char(compute="_compute_name", compute_sudo=True)
    server_id = fields.Many2one(comodel_name="cx.tower.server")
    command_id = fields.Many2one(comodel_name="cx.tower.command")
    finish_date = fields.Datetime(string="Finished")
    running = fields.Boolean()
    duration = fields.Float(
        string="Duration, sec", help="Time consumed for execution, seconds"
    )
    command_status = fields.Integer(string="Status")
    command_response = fields.Text(string="Response")
    command_error = fields.Text(string="Error")

    def _compute_name(self):
        for rec in self:
            rec.name = ": ".join((rec.server_id.name, rec.command_id.name))

    def start(self, server_id, command_id):
        """Start logging new command

        Args:
            server_id (Integer): id of the server
            command_id (Integer): id of the command
        Returns:
            (cx.tower.command.log()) new command log record
        """
        return self.sudo().create(
            {"running": True, "server_id": server_id, "command_id": command_id}
        )

    def finish(self, status=0, response=None, error=None):
        """Log command result when finished

        Args:
            status (int, optional): _description_. Defaults to 0.
            response (_type_, optional): _description_. Defaults to None.
            error (_type_, optional): _description_. Defaults to None.
        """
        finish_date = fields.Datetime.now()
        command_response = ""
        for r in response:
            command_response = (
                "{}\n{}".format(command_response, r) if command_response else r
            )
        command_error = ""
        for e in error:
            command_error = "{}\n{}".format(command_error, e) if command_error else e

        for rec in self.sudo():
            duration = (finish_date - rec.create_date).total_seconds()
            if duration < 0:
                duration = 0
            rec.write(
                {
                    "running": False,
                    "finish_date": finish_date,
                    "duration": duration,
                    "command_status": status,
                    "command_response": command_response,
                    "command_error": command_error,
                }
            )
