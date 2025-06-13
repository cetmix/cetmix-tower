## Initial Setup

1.  Install the module through **Apps** menu
2.  Navigate to **Sales → Configuration → Product Attributes**
3.  Click **Create** to create a new product attribute
4.  In the product attribute form:
    - Fill in the attribute name (e.g., "Server Configuration",
      "Database Type")
    - Select **Linked Tower Model** from the dropdown:
      - **Cetmix Tower Variable Options** (`cx.tower.variable.option`)
      - **Cetmix Tower Variable Values** (`cx.tower.variable.value`)
    - Configure the **Domain** field to filter available records
      (optional)
    - Click **Add Attribute Values from Tower Variables** button to
      populate values

## Populating Attribute Values

1.  After selecting the linked model, click **Add Attribute Values from
    Tower Variables**
2.  A wizard opens showing filtered records from the selected Tower
    model
3.  Select the desired Tower records to create corresponding attribute
    values
4.  The system automatically creates `product.attribute.value` records
    with proper mapping:
    - For Variable Options: `name` = `value_char`, `linked_record_ref` =
      `variable_id.name`
    - For Variable Values: `name` = `value_char`, `linked_record_ref` =
      `variable_id.name`

## Domain Configuration Examples

Filter by specific variable:

    [('variable_id.name', '=', 'server_size')]

Filter by access level:

    [('access_level', '>=', 2)]

Filter active options:

    [('active', '=', True)]

Multiple conditions:

    [('variable_id.reference', '=', 'server_size'), ('active', '=', True)] 
