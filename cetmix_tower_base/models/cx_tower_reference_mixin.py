# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import re
from collections import defaultdict

from odoo import _, api, fields, models
from odoo.osv import expression
from odoo.tools import ormcache


class CxTowerReferenceMixin(models.AbstractModel):
    """
    Used to create and manage unique record references.
    """

    _name = "cx.tower.reference.mixin"
    _description = "Cetmix Tower reference mixin"
    _rec_names_search = ["name", "reference"]

    # Used to check the reference before it's being fixed.
    # Ensures there's at least one valid symbol
    # that can be used later as a new reference basis.
    REFERENCE_PRELIMINARY_PATTERN = r"[\da-zA-Z]"

    name = fields.Char(required=True, index="trigram")
    reference = fields.Char(
        index=True,
        help="Can contain English letters, digits and '_'. Leave blank to autogenerate",
    )

    _sql_constraints = [
        ("reference_unique", "UNIQUE(reference)", "Reference must be unique")
    ]

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

        if vals_list and not self._context.get("reference_mixin_override"):
            # Check if we need to populate references based on parent record
            auto_generate_settings = self._get_pre_populated_model_data().get(
                self._name
            )
            if auto_generate_settings:
                parent_model, relation_field = auto_generate_settings
                vals_list = self._pre_populate_references(
                    parent_model, relation_field, vals_list
                )

            # Fix or create references
            for vals in vals_list:
                if not vals:
                    continue

                # Remove leading and trailing whitespaces from name
                vals_name = vals.get("name")
                name = vals_name.strip() if vals_name else vals_name

                # Remove leading and trailing whitespaces from reference
                vals_reference = vals.get("reference")
                reference = vals_reference.strip() if vals_reference else vals_reference

                # Nothing can be done if no name or reference is provided
                if not name and not reference:
                    continue

                # Save name back to vals if it was modified
                if vals_name != name:
                    vals["name"] = name

                # Generate reference
                vals.update(
                    {"reference": self._generate_or_fix_reference(reference or name)}
                )

        res = super().create(vals_list)
        self.env.registry.clear_cache()
        return res

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
                    return True
                # Name is present in vals
                reference = self._generate_or_fix_reference(updated_name)
            else:
                reference = self._generate_or_fix_reference(reference)
            vals.update({"reference": reference})

        res = super().write(vals)

        # Update references of dependent models
        if "reference" in vals:
            self._update_dependent_model_references()
            # Clear caches
            self.env.registry.clear_cache()
        return res

    def unlink(self):
        """
        Overrides unlink to clear cache for this method
        """
        res = super().unlink()
        self.env.registry.clear_cache()
        return res

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

        # skip copying 'name' because this function can be used in models
        # where 'name' field is not stored
        if not self.env.context.get("reference_mixin_skip_copy"):
            default["name"] = self._get_copied_name(force_name=default.get("name"))
        if "reference" not in default:
            default["reference"] = self._generate_or_fix_reference(default["name"])
        return super().copy(default=default)

    def _get_reference_pattern(self):
        """
        Returns the regex pattern used for validating and correcting references.
        This allows for easy modification of the pattern in one place.

        Important: pattern must be enclosed in square brackets!

        Returns:
            str: A regex pattern
        """
        return "[a-z0-9_]"

    def _get_pre_populated_model_data(self):
        """Returns List of models that should try to generate
        references based on the related model reference.

        Eg flight plan lines references are generated based on the flight plan one.

        Returns:
            dict: Model values dictionary:
            {model_name: [parent_model, relation_field]}
        """
        return {}

    def _get_extra_vals_fields(self):
        """Returns list of extra fields that are needed for reference generation.
        This method if used to make custom reference generation logic more flexible.
        Eg for 'cx.tower.variable.value':
            'server_id', 'server_template_id', 'plan_line_action_id'.
        So for common models like 'cx.tower.server' this method is not needed.

        Returns:
            list: List of fields:
            [field_name1, field_name2, ...]
        """
        return []

    def _get_dependent_model_relation_fields(self):
        """Returns list of fields that reference dependent models.

        Eg flight plan lines references are generated based on the flight plan one.

        Returns:
            list: List of fields:
            [field_name1, field_name2, ...]
        """
        return []

    def _update_dependent_model_references(self):
        """Update references of dependent models"""
        dependent_model_relation_fields = self._get_dependent_model_relation_fields()
        if dependent_model_relation_fields:
            for field in dependent_model_relation_fields:
                related_model_name = self[field]._name

                # Check if the related model has auto-generate settings
                auto_generate_settings = (
                    self[field]._get_pre_populated_model_data().get(related_model_name)
                )
                if auto_generate_settings:
                    parent_model, relation_field = auto_generate_settings
                else:
                    continue

                # Parse the field for all records
                for record in self:
                    related_records = record[field]
                    # Get vals list
                    rec_vals_list = related_records.read(
                        [relation_field] + related_records._get_extra_vals_fields()
                    )
                    # Transform Many2one tuples to IDs
                    for rv in rec_vals_list:
                        for k, v in rv.items():
                            # Transform m2o fields from (id, name) to id
                            if isinstance(v, tuple):
                                rv[k] = v[0]
                    related_records._pre_populate_references(
                        parent_model, relation_field, rec_vals_list
                    )
                    ref_by_id = {rv["id"]: rv["reference"] for rv in rec_vals_list}
                    for related_record in related_records:
                        related_record.reference = ref_by_id[related_record.id]

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
            reference = (
                re.sub(
                    rf"[^{inner_pattern}]",
                    "",
                    reference_source.strip().replace(" ", "_").lower(),
                )
                or self._get_model_generic_reference()
            )

        # Check if the same reference already exists and add a suffix if yes
        counter = 1
        final_reference = reference

        # If exclude same records from search results
        if self and not self.env.context.get("reference_mixin_skip_self"):
            domain = [("id", "not in", self.ids)]
        else:
            domain = []
        final_domain = expression.AND([domain, [("reference", "=", final_reference)]])

        # Search all records without restrictions including archived
        self_with_sudo_and_context = self.sudo().with_context(active_test=False)
        while self_with_sudo_and_context.search_count(final_domain) > 0:
            counter += 1
            final_reference = f"{reference}_{counter}"
            final_domain = expression.AND(
                [domain, [("reference", "=", final_reference)]]
            )

        return final_reference

    def _get_copied_name(self, force_name=None):
        """
        Return a copied name of the record
        by adding the suffix (copy) at the end
        and counter until the name is unique.

        Args:
            force_name (str): Used to use force name instead of record name.

        Returns:
            An unique name for the copied record
        """
        self.ensure_one()
        original_name = force_name or self.name
        copy_name = _("%(name)s (copy)", name=original_name)

        counter = 1
        # Ensures that the generated copy name is unique by
        # appending a counter until a unique name is found.
        while self.search_count([("name", "=", copy_name)]) > 0:
            counter += 1
            copy_name = _(
                "%(name)s (copy %(number)s)",
                name=original_name,
                number=str(counter),
            )

        return copy_name

    def _get_model_generic_reference(self):
        """Get generic reference for current model.
        Generic references are used as a fallback in the automatic
        reference generation.
        When a reference cannot be generated neither from the 'reference'
        nor from the 'name' field values.

        Eg for the 'cx.tower.plan' model such reference will look like
        'tower_plan'.

        Returns:
            Char: generated prefix
        """
        model_prefix = self._name.replace("cx.tower.", "").replace(".", "_")
        return model_prefix

    def get_by_reference(self, reference):
        """Get record based on its reference.

        Important: references are case sensitive!

        Args:
            reference (Char): record reference

        Returns:
            Record: Record that matches provided reference
        """
        return self.browse(self._get_id_by_reference(reference))

    @ormcache("self.env.uid", "self.env.su", "reference")
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

    @api.model
    def _prepare_references(self, model, key_name, vals_list):
        """
        Prepare a dictionary of references for given model records.

        This function extracts unique IDs from a list of dictionaries (vals_list)
        based on a specified key (key_name), fetches the corresponding records
        from the specified model, and returns a dictionary mapping record IDs to
        their references.

        Args:
            model (str): The name of the model to fetch records from.
            key_name (str): The key in the dictionaries of vals_list that contains
                            the record IDs.
            vals_list (list of dict): A list of dictionaries containing the values
                                    to be processed.

        Returns:
            dict: A dictionary mapping record IDs to their references.
        """
        if not vals_list:
            # No entries to process, return an empty dictionary
            return {}

        try:
            CxModel = self.env[model]
        except KeyError as err:
            raise ValueError(
                _(
                    (
                        "Model '%(model)s' does not exist. "
                        "Please provide a valid model name."
                    ),
                    model=model,
                )
            ) from err

        # Extract all unique ids from vals_list
        line_ids = {
            vals.get(key_name)
            for vals in vals_list
            if vals.get(key_name) and not vals.get("reference")
        }

        # Fetch all line references in a single query
        lines = CxModel.browse(line_ids)
        return {line.id: line.reference for line in lines if line.reference}

    @api.model
    def _pre_populate_references(self, model_name, field_name, vals_list):
        """
        Populates reference fields in a list of dictionaries (vals_list)
        intended for record creation.

        This method generates unique references for each dictionary entry in
        `vals_list` based on a specified field that links to records in
        another model (indicated by `model_name`). It uses existing references
        from the related records as a basis and appends a suffix and an
        incrementing index to ensure uniqueness.
        If reference is present in values it will not be overwritten.

        Args:
            model_name (str): The name of the related model to extract
                              reference data from.
            field_name (str): The key in each dictionary in `vals_list`
                              containing the related record's ID.
            vals_list (list of dict): A list of dictionaries where each dictionary
                               represents values for a new record.

        Returns:
            list: The modified `vals_list`, with a unique 'reference'
                  entry in each dictionary.
        """

        # Extract parent record references from vals_list
        parent_record_refs = self._prepare_references(model_name, field_name, vals_list)
        line_index_dict = defaultdict(int)

        # Used to make reference more readable
        model_reference = self._get_model_generic_reference()

        # Populate vals with references
        for vals in vals_list:
            # Skip if reference is provided explicitly and has symbols
            existing_reference = vals.get("reference")
            if existing_reference and bool(
                re.search(self.REFERENCE_PRELIMINARY_PATTERN, existing_reference)
            ):
                continue

            # Compose based on related record reference if exists
            record_id = vals.get(field_name)
            if record_id and parent_record_refs.get(record_id):
                line_index_dict[record_id] += 1
                line_index = line_index_dict[record_id]
                vals["reference"] = (
                    f"{parent_record_refs[record_id]}_{model_reference}_{line_index}"
                )
            else:
                # Handle cases where the field is not present
                line_index_dict["no_record"] += 1
                line_index = line_index_dict["no_record"]
                vals["reference"] = f"no_{model_reference}_{line_index}"

        return vals_list
