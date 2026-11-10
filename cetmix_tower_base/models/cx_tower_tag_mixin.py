# Copyright (C) 2025 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import fields, models


class CxTowerTagMixin(models.AbstractModel):
    """
    Cetmix Tower Tag Mixin.
    Used to add tag functionality to models.
    """

    _name = "cx.tower.tag.mixin"
    _description = "Cetmix Tower Tag Mixin"

    tag_ids = fields.Many2many(
        comodel_name="cx.tower.tag",
        string="Tags",
    )

    def add_tags(self, tag_names):
        """Add tags to the record

        Args:
            tag_names (list of Char or Char): List of tag names to add
                or single tag name
        """
        # Single tag name is given, convert to list
        if isinstance(tag_names, str):
            tag_names = [tag_names]
        # Invalid type is given, return True
        elif not isinstance(tag_names, list):
            return True

        tags = self.env["cx.tower.tag"].search([("name", "in", tag_names)])
        if tags:
            self.write({"tag_ids": [(4, tag.id) for tag in tags]})
        return True

    def remove_tags(self, tag_names):
        """Remove tags from the record

        Args:
            tag_names (list of Char or Char): List of tag names to remove
                or single tag name.
        """
        # Single tag name is given, convert to list
        if isinstance(tag_names, str):
            tag_names = [tag_names]
        # Invalid type is given, return True
        elif not isinstance(tag_names, list):
            return True

        tags = self.env["cx.tower.tag"].search([("name", "in", tag_names)])
        if tags:
            self.write({"tag_ids": [(3, tag.id) for tag in tags]})
        return True

    def has_tags(self, tag_name, search_all=False):
        """Get all records from the recordset that have any of the given tags

        Args:
            tag_name (Char or List of Char): Tag name or list of tag names to check
            search_all (bool): If True, search all records in the model
        """

        # Empty recordset is returned as is
        if not self and not search_all:
            return self

        # Check argument type
        if isinstance(tag_name, str):
            single_tag = True
        elif isinstance(tag_name, list):
            single_tag = False
        else:
            return self.browse()

        if search_all:
            if single_tag:
                domain = [("tag_ids.name", "=", tag_name)]
            else:
                domain = [("tag_ids.name", "in", tag_name)]
            return self.env[self._name].search(domain)

        if single_tag:
            return self.filtered(
                lambda record: tag_name in record.tag_ids.mapped("name")
            )
        return self.filtered(
            lambda record: set(tag_name) & set(record.tag_ids.mapped("name"))
        )

    def has_all_tags(self, tag_names, search_all=False):
        """Get all records from the recordset that have all of the given tags

        Args:
            tag_names (list of Char): List of tag names to check
            search_all (bool): If True, search all records in the model
        """
        # No value or invalid type is given, return empty recordset
        if not tag_names or not isinstance(tag_names, list):
            return self.browse()

        # Empty recordset is returned as is
        if not self and not search_all:
            return self

        if search_all:
            records = self.env[self._name].search([("tag_ids.name", "in", tag_names)])
        else:
            records = self

        tag_names_set = set(tag_names)
        return records.filtered(
            lambda record: tag_names_set.issubset(record.tag_ids.mapped("name"))
        )
