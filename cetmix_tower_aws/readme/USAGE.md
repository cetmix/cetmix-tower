Please check the [official Boto3 Documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/index.html) (https://boto3.amazonaws.com/v1/documentation/api/latest/index.html) for the detailed information about the services and methods provided by the Boto3 library.

> **Disclaimer**: The following example demonstrates one of many possible commands you can create and run with this module. The boto3 library provides access to the full range of AWS services and methods - this is just a starting point to help you get familiar with the integration.

## Example of Cetmix Tower Python Command to List EC2 Instances

### Navigate to Command Creation
- Go to `Cetmix Tower > Commands > Commands`
- Click the `Create` button

### Configure Command Settings
- Set a descriptive `Name` (e.g., "List AWS EC2 Instances")
- Leave `Reference` blank to generate automatically (or set a custom reference)
- Select `Action`: "Execute Python code"
- Set `Access Level`: Choose appropriate level (e.g., "Manager")
- Optional: Set `Default Path` if needed
- Optional: Add `Tags` (e.g., "aws", "ec2") for better organization

### Add Required Variables
- In the `Variables` tab, add the previously configured variable:
  - `aws_region_name`

### Add Required Secrets
- In the `Secrets` field, add the previously configured secrets:
  - `aws_access_key`
  - `aws_secret_access_key`

### Write Python Code
- Go to the `Code` tab
- Enter the following Python code:

    ```python
    # List EC2 instances using boto3
    result = {"exit_code": 0, "message": None}

    session = boto3.Session(
        aws_access_key_id=#!cxtower.secret.aws_access_key!#,
        aws_secret_access_key=#!cxtower.secret.aws_secret_access_key!#,
        region_name={{ aws_region_name }}
    )
    ec2 = session.client('ec2')
    instances = ec2.describe_instances()

    instance_details = []
    for reservation in instances['Reservations']:
        for instance in reservation['Instances']:
            instance_detail = "Instance ID: " + instance['InstanceId']
            instance_detail += ", Type: " + instance.get('InstanceType', 'Unknown')
            instance_detail += ", State: " + instance.get('State', {}).get('Name', 'Unknown')
            instance_details.append(instance_detail)

    if instance_details:
        result["message"] = "Found " + str(len(instance_details)) + " EC2 instances:\n" + "\n".join(instance_details)
    else:
        result["message"] = "No EC2 instances found"
    ```

### Save the Command
- Click the `Save` button to create the command

## Running the AWS EC2 Command

### Navigate to Server
- Go to `Cetmix Tower > Servers > Servers`
- Open the server where you want to run the command

### Execute Command from Server
- Click the `Command` button at the top of the server form
- In the popup dialog:
  - Select your AWS EC2 command from the dropdown
  - Verify the variable values (if any need adjustment)
  - Click `Run` to execute

### View Command Results
- After execution, the command log will display showing:
  - The command executed
  - Execution status
  - Output message containing EC2 instance details if successful

## Example Output

For a successful execution with EC2 instances:

```bash
Found 3 EC2 instances:
Instance ID: i-0abc123def456789, Type: t2.micro, State: running
Instance ID: i-0def456abc789123, Type: t3.medium, State: stopped
Instance ID: i-0789abc123def456, Type: m5.large, State: running
```

For a successful execution with no EC2 instances:

```bash
No EC2 instances found
```

## Creating Additional AWS Commands

The cetmix_tower_aws module provides access to the boto3 Python library for AWS service integration. Here are some common services you can use:

```python
# Standard client initialization pattern
client = boto3.client(
    'service_name',  # Replace with: ec2, s3, rds, cloudwatch, etc.
    region_name={{ aws_region_name }},
    aws_access_key_id=#!cxtower.secret.aws_access_key!#,
    aws_secret_access_key=#!cxtower.secret.aws_secret_access_key!#
)

# Or use resource interface for object-oriented access
resource = boto3.resource(
    'service_name',  # Replace with: ec2, s3, etc.
    region_name={{ aws_region_name }},
    aws_access_key_id=#!cxtower.secret.aws_access_key!#,
    aws_secret_access_key=#!cxtower.secret.aws_secret_access_key!#
)
```

Popular AWS services include: EC2 (compute), S3 (storage), RDS (databases), and CloudWatch (monitoring).

For more details, see the [AWS Boto3 Documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/index.html).
