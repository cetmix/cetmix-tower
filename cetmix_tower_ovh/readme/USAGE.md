# Cetmix Tower OVHcloud Command Usage

> **Disclaimer**: The following example demonstrates one of many possible commands you can create and run with this module. The `ovh` Python library provides access to the full range of OVHcloud APIs – this is just a starting point to help you get familiar with the integration.

## Example of Cetmix Tower Python Command to Create DNS Records

* **Navigate to Command Creation**
  * Go to `Cetmix Tower > Commands > Commands`
  * Click the `Create` button

* **Configure Command Settings**
  * Set a descriptive `Name` (e.g., "List OVHcloud Instances")
  * Leave `Reference` blank to generate automatically (or set a custom reference)
  * Select `Action`: "Execute Python code"
  * Set `Access Level`: Choose appropriate level (e.g., "Manager")
  * Optional: Set `Default Path` if needed
  * Optional: Add `Tags` (e.g., "ovh", "cloud", "instance") for better organization

* **Add Required Variables**
  * In the `Variables` tab, add the previously configured variable:
    * `ovh_endpoint` (e.g., "ovh-eu")

* **Add Required Secrets**
  * In the `Secrets` field, add the previously configured secrets:
    * `ovh_application_key`
    * `ovh_application_secret`
    * `ovh_consumer_key`

* **Write Python Code**
  * Go to the `Code` tab
  * Enter the following Python code:

   ```python
   # List OVHcloud instances using ovh API
    result = {"exit_code": 0, "message": None}

  client = ovh.Client(
    endpoint={{ ovh_endpoint }},
    application_key=#!cxtower.secret.ovh_application_key!#,
    application_secret=#!cxtower.secret.ovh_application_secret!#,
    consumer_key=#!cxtower.secret.ovh_consumer_key!#
  )

  # Required variables:
  # - domain_name: The main domain (e.g., "example.com")
  # - subdomain: The subdomain to create (e.g., "test")

  try:
     # Create a new subdomain by adding a DNS entry (A record as example)
     ip_address = "1.2.3.4"  # Replace with the desired IP address
     response = client.post(
        "/domain/zone/" + domain_name + "/record",
        fieldType="A",
        subDomain=subdomain,
        target=ip_address,
        ttl=3600
     )
     # Refresh the zone to apply changes
     client.post("/domain/zone/" + domain_name + "/refresh")
     result["message"] = "Subdomain '" + subdomain + "." + domain_name + "' created and DNS zone refreshed."
  except Exception as e:
     result["exit_code"] = 1
     result["message"] = "Error: " + str(e)
  ```

* **Save the Command**
  * Click the `Save` button to create the command

## Running the OVHcloud Instance Command

* **Navigate to Server**
  * Go to `Cetmix Tower > Servers > Servers`
  * Open the server where you want to run the command

* **Execute Command from Server**
  * Click the `Command` button at the top of the server form
  * In the popup dialog:
    * Select your OVHcloud instance command from the dropdown
    * Verify the variable values (if any need adjustment)
    * Click `Run` to execute

* **View Command Results**
  * After execution, the command log will display showing:
    * The command executed
    * Execution status
    * Output message containing OVHcloud instance details if successful
