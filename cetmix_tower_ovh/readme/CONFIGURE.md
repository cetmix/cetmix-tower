
# Setting up OVH Access

## Create OVH API Credentials

To use the OVH integration with Cetmix Tower, you need to create OVH API credentials:

- Follow the [official OVH documentation](https://docs.ovh.com/gb/en/api/first-steps/) (https://docs.ovh.com/gb/en/api/first-steps/) for creating an application and generating API keys
- It's recommended to create a dedicated application with appropriate permissions for Cetmix Tower
- Store your Application Key, Application Secret, and Consumer Key securely—you'll need them in the next step

## Configure OVH Secrets in Cetmix Tower

Create three secrets in Cetmix Tower to store your OVH credentials:

- Navigate to `Cetmix Tower > Settings > Keys and Secrets`
- Create a new Secret with:
  - Name: `OVH Application Key`
  - Reference: `ovh_application_key`
  - Key Type: `Secret`
- Enter your OVH Application Key in the Secret Value tab
- Similarly, create another Secret with:
  - Name: `OVH Application Secret`
  - Reference: `ovh_application_secret`
  - Key Type: `Secret`
- Enter your OVH Application Secret in the Secret Value tab
- Finally, create a Secret with:
  - Name: `OVH Consumer Key`
  - Reference: `ovh_consumer_key`
  - Key Type: `Secret`
- Enter your OVH Consumer Key in the Secret Value tab

> Note: These secrets will be accessible as `#!cxtower.secret.ovh_application_key!#`, `#!cxtower.secret.ovh_application_secret!#`, and `#!cxtower.secret.ovh_consumer_key!#` in your commands.

## Configure OVH Endpoint

Create a variable to define your OVH API endpoint (region):

- Navigate to `Cetmix Tower > Settings > Variables`
- Create a new Variable with:
  - Name: `OVH Endpoint`
  - Reference: `ovh_endpoint`
  - Type: `String`
- Set your OVH endpoint (e.g., `ovh-eu`, `ovh-ca`, `ovh-us`) as the value
