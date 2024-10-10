# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import re

from odoo import _, api, fields, models
from odoo.osv import expression


class CxTowerReferenceMixin(models.AbstractModel):
    """
    Used to create and manage unique record references.
    """

    _name = "cx.tower.reference.mixin"
    _description = "Cetmix Tower reference mixin"

    name = fields.Char(required=True)
    reference = fields.Char(
        index=True,
        help="Can contain English letters, digits and '_'. Leave blank to autogenerate",
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
        while (
            self.search_count(
                [
                    ("reference", "=", final_reference),
                    ("id", "!=", self.id),
                ]
            )
            > 0
        ):
            counter += 1
            final_reference = _(f"{reference}_{counter}")

        return final_reference

    @api.model
    def _name_search(
        self, name="", args=None, operator="ilike", limit=100, name_get_uid=None
    ):
        """
        Search for records by matching either the 'reference' or 'name' fields
        using the given search operator.

        This method constructs a domain to search for records where either the
        'reference' or 'name' field contains the search term provided in 'name'.
        The domain also allows for additional search arguments to be passed via 'args'.

        :param name: The search term to match against the 'reference' or 'name' field.
        :param args: A list of additional domain conditions for the search.
        :param operator: The comparison operator to use for the search.
        :param limit: The maximum number of records to return (default: 100).
        :param name_get_uid: The user ID used for access rights validation.
        :return: A list of record IDs that match the search criteria.
        """
        if args is None:
            args = []

        search_domain = expression.OR(
            [[("reference", operator, name)], [("name", operator, name)]]
        )

        domain = expression.AND([args, search_domain])
        return self._search(domain, limit=limit, access_rights_uid=name_get_uid)

    @api.model_create_multi
    def create(self, vals_list):
        """
        Overrides create to ensure 'reference' is auto-corrected
        or validated for each record.

        Add `reference_mixin_override` context key to skip the reference check

        Args:
            vals_list (list[dict]): List of dictionaries with record values.

        Returns:
            Records: The created record(s).
        """
        if not self._context.get("reference_mixin_override"):
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

        Add `reference_mixin_override` context key to skip the reference check

        Args:
            vals (dict): Values to update, may include 'reference'.

        Returns:
            Result of the super `write` call.
        """
        if not self._context.get("reference_mixin_override") and "reference" in vals:
            reference = vals.get("reference", False)
            if not reference:
                # Get name from vals
                updated_name = vals.get("name")

                # No name in vals. Update records one by one
                if not updated_name:
                    for record in self:
                        record_vals = vals.copy()
                        record_vals.update(
                            {"reference": self._generate_or_fix_reference(record.name)}
                        )
                        super(CxTowerReferenceMixin, record).write(record_vals)
                    return
                # Name is present in vals
                reference = self._generate_or_fix_reference(updated_name)
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
        copy_name = _("%(name)s (copy)", name=original_name)

        counter = 1
        while self.search_count([("name", "=", copy_name)]) > 0:
            counter += 1
            copy_name = _(
                "%(name)s (copy %(number)s)", name=original_name, number=str(counter)
            )

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

    # TODO: implement caching for this method
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
