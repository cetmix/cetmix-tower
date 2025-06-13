## Creating Tower-Linked Product Attributes

1.  Go to **Sales → Configuration → Product Attributes**
2.  Click **Create**
3.  Enter attribute details:
    - **Name**: Descriptive name (e.g., "Server Size", "Database
      Version")
    - **Linked Tower Model**: Select either "Cetmix Tower Variable
      Options" or "Cetmix Tower Variable Values"
    - **Domain**: Optional filter expression
4.  Click **Add Attribute Values from Tower Variables**
5.  Select desired Tower records in the wizard
6.  Save the attribute

## Using Tower-Linked Attributes on Products

1.  Navigate to **Sales → Products → Products**
2.  Open any product template
3.  Go to **Attributes & Variants** tab
4.  Add the Tower-linked attribute
5.  Select which Tower-sourced values should be available for this
    product
6.  Product variants are automatically created based on Tower
    configurations

## Sales Order Configuration

1.  Create a new sales order
2.  Add products with Tower-linked attributes
3.  Configure product options using the Tower-sourced attribute values
4.  The selected attribute values map directly to Tower service
    parameters
5.  Order processing can use these mappings for automated provisioning

## Managing Attribute Values

- **View Tower Variable Reference**: In the attribute values list, check
  the "Tower Variable" column to see which Tower variable each value
  maps to
- **Manual Synchronization**: Re-run the wizard to add new Tower
  variables as attribute values
- **Domain Updates**: Modify the domain filter and re-run the wizard to
  refresh available options

## Known Limitations

- Manual synchronization required when Tower variables change
- Domain filtering requires knowledge of Tower model structure
- No automatic cleanup when Tower variables are deleted
- Limited to two specific Tower models only

## Best Practices

1.  **Naming Convention**: Use descriptive attribute names that match
    your Tower variable purposes
2.  **Domain Filtering**: Use specific domains to avoid cluttering
    attribute values with irrelevant options
3.  **Regular Updates**: Periodically refresh attribute values when
    Tower variables are updated
4.  **Testing**: Test the complete flow from product configuration to
    service provisioning
