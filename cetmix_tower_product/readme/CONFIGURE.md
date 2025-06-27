*Prerequisite*

To access product attributes and the Odoo product configurator, you must have the sale_management module installed.

*1. Link Product Attributes to Tower Variables*

1. Navigate to **Sales > Configuration > Products > Attributes**
2. Open an existing product attribute or create a new one
3. In the **Cetmix Tower Integration** section:
   * Select a **Tower Variable** from the dropdown.
   * This establishes the direct link between your product attribute and Tower variable.
   * (Optional) Tick **Auto Sync Values** to let Odoo pull in new Tower options automatically.

*2. Sync Tower Options*

1. After you link a Tower variable to your product attribute:
   * Click **"Sync from Tower Variable"**.
   * All options of the linked Tower variable are copied to Odoo as attribute values.
   * Existing values stay – only brand-new options are added.

*3. What happens next?*

* **No manual editing**: You cannot create or delete these attribute values inside Odoo.  Do it in Cetmix Tower instead and then press **Sync** again.
* **Duplicate protection**: The sync skips options that already exist or have the same name.
* **Option in use**: A Tower option that is already used in any product variant cannot be deleted in Tower.
* **Auto-sync convenience**: When **Auto Sync Values** is enabled, new options appear automatically without pressing **Sync**.

No extra configuration files or complex setup steps are needed. 