from odoo import fields, models


class CxTowerYamlExportWizDownload(models.TransientModel):
    _name = "cx.tower.yaml.export.wiz.download"
    _description = "Cetmix Tower YAML Export File Download"

    yaml_file = fields.Binary(readonly=True, attachment=False)
    yaml_file_name = fields.Char(readonly=True)
