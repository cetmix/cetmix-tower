# Cetmix Tower TLDExtract Usage

This module provides the Python `tldextract` library (wrapped safely) for use in Python commands in Cetmix Tower.

## Example

```python
# Extract domain parts
result = tldextract.extract("sub.example.co.uk")
domain = result.domain  # example
suffix = result.suffix  # co.uk
