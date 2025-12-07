## Configure an Authenticator

**⚠️ WARNING: You must be a member of the "Cetmix Tower/Root" group to configure authenticators.**

- Go to "Cetmix Tower > Settings > Automation > Webhook Authenticators" and click "New".

**Complete the following fields:**

- Name. Authenticator name
- Reference. Unique reference. Leave this field blank to auto generate it
- Code. Code that is used to authenticate the request. You can use all Cetmix Tower - Python command variables except for the server​ plus the following webhook specific ones:
- headers: dictionary that contains the request headers
- raw_data: string with the raw HTTP request body
- payload: dictionary that contains the JSON payload or the GET parameters of the request

**The code returns the result​ variable in the following format:**

```python
result = {"allowed": <bool, mandatory, default=False>, "http_code": <int, optional>, "message": <str, optional>}
```

eg:

```python
result = {"allowed": True}
result = {"allowed": False, "http_code": 403, "message": "Sorry..."}
```

## Configure a Webhook

**⚠️ WARNING: You must be a member of the "Cetmix Tower/Root" group to configure webhooks.**

- Go to "Cetmix Tower > Settings > Automation > Webhooks" and click "New".

**Complete the following fields:**

- Enabled. Uncheck this field to disable the webhook without deleting it
- Name. Authenticator name
- Reference. Unique reference. Leave this field blank to auto generate it
- Authenticator. Select an Authenticator used for this webhook
- Endpoint. Webhook endpoint. The complete webhook URL will be <your_tower_url>/cetmix_tower_webhooks/<endpoint>​
- Run as User. Select a user to run the webhook on behalf of. CAREFUL! You must realize and understand what you are doing, including all the possible consequences when selecting a specific user.
- Code. Code that processes the request. You can use all Cetmix Tower Python command variables (except for the server) plus the following webhook-specific one:
  - headers: dictionary that contains the request headers
  - payload: dictionary that contains the JSON payload or the GET parameters of the request

Webhook code returns a result using the Cetmix Tower Python command pattern:

```python
result = {"exit_code": <int, default=0>, "message": <string, default=None>}
```

**To configure the time for which the webhook call logs are stored:**

- Go to "Cetmix Tower > Settings > General Settings"
- Put a number of days into the "Keep Webhook Logs for (days)" field. Default value is 30.

Please refer to the [official documentation](https://tower.cetmix.com) for detailed configuration instructions.
