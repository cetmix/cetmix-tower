# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import re

from odoo import _, api, fields, models, tools


class CxTowerReferenceMixin(models.AbstractModel):
    """
    Used to create and manage unique record references.
    """

    _name = "cx.tower.reference.mixin"
    _description = "Cetmix Tower reference mixin"

    name = fields.Char(required=True)
    reference = fields.Char(
        help="Can contain English letters, digits and '_'. Leave blank to autogenerate"
    )

    _sql_constraints = [
        ("reference_unique", "UNIQUE(reference)", "Reference must be unique")
    ]

    def _get_reference_pattern(self):
        """
        Returns the regex pattern used for validating and correcting references.
        This allows for easy modification of the pattern in one place.

        Important: pattern must be enclosed in square brackets!

        Returns:
            str: A regex pattern
        """
        return "[a-z0-9_]"

    def _generate_or_fix_reference(self, reference_source):
        """
        Generate a new reference of fix an existing one.

        Args:
            reference_source (str): Original string.

        Returns:
            str: Generated or fixed reference.
        """

        # Check if reference matches the pattern
        reference_pattern = self._get_reference_pattern()

        if re.fullmatch(rf"{reference_pattern}+", reference_source):
            reference = reference_source

        # Fix reference if it doesn't match
        else:
            # Modify the pattern to be used in `sub`
            inner_pattern = reference_pattern[1:-1]
            reference = re.sub(
                rf"[^{inner_pattern}]",
                "",
                reference_source.strip().replace(" ", "_").lower(),
            )

        # Check if the same reference already exists and add a suffix if yes
        counter = 1
        final_reference = reference
        while self.search_count([("reference", "=", final_reference)]) > 0:
            counter += 1
            final_reference = _(f"{reference}_{counter}")

        return final_reference

    @api.model_create_multi
    def create(self, vals_list):
        """
        Overrides create to ensure 'reference' is auto-corrected
        or validated for each record.

        Args:
            vals_list (list[dict]): List of dictionaries with record values.

        Returns:
            Records: The created record(s).
        """
        for vals in vals_list:
            vals["name"] = vals["name"].strip()
            # Generate reference
            reference = self._generate_or_fix_reference(
                vals.get("reference") or vals.get("name")
            )
            vals.update({"reference": reference})
        return super().create(vals_list)

    def write(self, vals):
        """
        Updates record, auto-correcting or validating 'reference'
        based on 'name' or existing value.

        Args:
            vals (dict): Values to update, may include 'reference'.

        Returns:
            Result of the super `write` call.
        """
        reference = vals.get("reference", False)
        if not reference:
            reference = self._generate_or_fix_reference(self.name)
        else:
            reference = self._generate_or_fix_reference(reference)
        vals.update({"reference": reference})
        return super().write(vals)

    def _get_copied_name(self):
        """
        Return a copied name of the record
        by adding the suffix (copy) at the end
        and counter until the name is unique.

        Returns:
            An unique name for the copied record
        """
        self.ensure_one()
        original_name = self.name
        copy_name = _(f"{original_name} (Copy)")
        counter = 1
        while self.search_count([("name", "=", copy_name)]) > 0:
            counter += 1
            copy_name = _(f"{original_name} (Copy {counter})")
        return copy_name

    def copy(self, default=None):
        """
        Overrides the copy method to ensure unique reference values
        for duplicated records.

        Args:
            default (dict, optional): Default values for the new record.

        Returns:
            Record: The newly copied record with adjusted defaults.
        """
        self.ensure_one()
        if default is None:
            default = {}
        default["name"] = self._get_copied_name()
        if "reference" not in default:
            default["reference"] = self._generate_or_fix_reference(default["name"])
        return super().copy(default=default)

    def get_by_reference(self, reference):
        """Get record based on its reference.

        Important: references are case sensitive!

        Args:
            reference (Char): record reference

        Returns:
            Record: Record that matches provided reference
        """
        return self.browse(self._get_id_by_reference(reference))

    @tools.ormcache("reference")
    def _get_id_by_reference(self, reference):
        """Get record id based on its reference.

        Important: references are case sensitive!

        Args:
            reference (Char): record reference

        Returns:
            Record: Record id that matches provided reference
        """
        records = self.search([("reference", "=", reference)])

        # This is in case some models will remove reference uniqueness constraint
        return records and records[0].id
