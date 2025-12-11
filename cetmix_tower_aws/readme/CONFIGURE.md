**Prerequisites**

The module has `boto3` defined in its external dependencies, which means, you should install the Python `boto3` package manually if you don't have automatic package installation configured in your Odoo environment. Run `pip install boto3` to install it.  

**Setting up AWS Access**

1. **Create AWS Access Keys**

   To use the AWS integration with Cetmix Tower, you need to create AWS access keys:
   
   - Follow the [official AWS documentation](https://docs.aws.amazon.com/IAM/latest/UserGuide/security-creds.html) (https://docs.aws.amazon.com/IAM/latest/UserGuide/security-creds.html) for creating IAM access keys
   - It's recommended to create a dedicated IAM user with appropriate permissions for Cetmix Tower
   - Store your access key ID and secret access key securely - you'll need them in the next step

2. **Configure AWS Secrets in Cetmix Tower**

   Create two secrets in Cetmix Tower to store your AWS credentials:
   
   - Navigate to `Cetmix Tower > Settings > Keys and Secrets`
   - Create a new Secret with:
     - Name: `AWS Access Key`
     - Reference: `aws_access_key`
     - Key Type: `Secret`
   - Enter your AWS access key ID in the Secret Value tab
   - Similarly, create another Secret with:
     - Name: `AWS Secret Access Key`
     - Reference: `aws_secret_access_key`
     - Key Type: `Secret`
   - Enter your AWS secret access key in the Secret Value tab

   > Note: These secrets will be accessible as `#!cxtower.secret.aws_access_key!#` and `#!cxtower.secret.aws_secret_access_key!#` in your commands.

3. **Configure AWS Region**

   Create a variable to define your AWS region:
   
   - Navigate to `Cetmix Tower > Settings > Variables`
   - Create a new Variable with:
     - Name: `AWS Region Name`
     - Reference: `aws_region_name`
     - Type: `String`
   - Set your AWS region (e.g., `us-east-1`, `eu-west-1`) as the value
