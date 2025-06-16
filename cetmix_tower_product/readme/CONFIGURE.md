
### Prerequisite

To access product attributes and the Odoo product configurator, you must have the sale_management module installed.

### 1. Link Product Attributes to Tower Variables

1. Navigate to **Sales > Configuration > Products > Attributes**
2. Open an existing product attribute or create a new one
3. In the **Cetmix Tower Integration** section:
   * Select a **Tower Variable** from the dropdown.
   * This establishes the direct link between your product attribute and Tower variable.

### 2. Synchronize Tower Values

1. After linking a Tower variable to your product attribute:
   * Click the **"Sync from Tower Variable"** button.
   * The system will import all values from the linked Tower variable as product attribute values.
   * Existing attribute values are preserved - only new Tower values are added.

### 3. Duplicate Prevention

The module automatically prevents duplicates during synchronization:
* Values already linked to the same Tower variable value are skipped.
* Attribute values with identical names are not created again.

## Ongoing Management

* **Re-sync at any time**: Click the sync button to import new Tower variable values.
* **Safe deletions**: Deleting Tower variable values will not remove product attribute values.
* **Independent management**: Product attribute values can be managed independently after import.

No additional configuration files or complex setup procedures are required. 