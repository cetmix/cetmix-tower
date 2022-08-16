from odoo import fields, models


class CxTowerCommandLog(models.Model):
    _name = "cx.tower.command.log"
    _description = "Cetmix Tower Command Log"
    _order = "finish_date desc"

    server_id = fields.Many2one(comodel_name="cx.tower.server")
    command_id = fields.Many2one(comodel_name="cx.tower.command")
    finish_date = fields.Datetime(string="Finished")
    running = fields.Boolean()
    duration = fields.Float(
        string="Time consumed", help="Time consumed for execution, seconds"
    )
    command_status = fields.Integer(sting="Status")
    command_response = fields.Text(sting="Response")
    command_error = fields.Text(sting="Error")

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
        for rec in self.sudo():
            rec.write(
                {
                    "running": False,
                    "finish_date": finish_date,
                    "duration": (rec.create_date - finish_date).total_seconds(),
                    "status": status,
                    "response": response,
                    "error": error,
                }
            )
