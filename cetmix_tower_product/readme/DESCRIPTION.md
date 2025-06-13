This module extends Odoo's product attribute system to enable seamless
integration between product configuration and Cetmix Tower service
instance provisioning. It allows product managers to define product
attributes that directly map to Cetmix Tower variable options and
values, ensuring that when customers configure products in the sales
process, the selected attribute values automatically determine the
service instance configuration parameters.

The module adapts the mechanics from `product_attribute_model_link` but
creates a hardcoded connection specifically for Cetmix Tower models.
This creates a bridge between the sales configuration interface and the
technical service provisioning backend without external dependencies.

**Key Features:**

- Link product attributes to Cetmix Tower Variable Options
  (`cx.tower.variable.option`)
- Link product attributes to Cetmix Tower Variable Values
  (`cx.tower.variable.value`)
- Domain filtering to select specific Tower variables
- Automatic creation of product attribute values from Tower data
- Wizard-based selection interface for Tower records
- Warning system for configuration changes
- Demo data with realistic cloud service scenarios
