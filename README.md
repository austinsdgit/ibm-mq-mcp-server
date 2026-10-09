# IBM MQ MCP Server

A Model Context Protocol (MCP) server for IBM MQ with built-in role-based authorization controls. This server allows AI assistants to interact with IBM MQ queues while enforcing granular permissions based on user roles and queue-specific rules.

## Features

- 🔐 **Role-Based Authorization**: Predefined roles (Admin, Writer, Reader, Browser, Monitor) with specific permissions
- 🎯 **Queue-Specific Permissions**: Override role permissions for specific queue patterns
- 📨 **Message Operations**: Put, get, and browse messages with authorization checks
- 📊 **Queue Management**: List queues and retrieve queue information
- 🔒 **Security**: Restrict actions for full-access users on sensitive queues
- ⚙️ **Configurable**: Environment-based configuration for IBM MQ connections

## Installation

### Prerequisites

- Python 3.10 or higher
- IBM MQ Client libraries installed
- Access to an IBM MQ queue manager

### Install IBM MQ Client Libraries

#### macOS
```bash
# Download IBM MQ client from IBM website
# Then install pymqi
brew install ibm-mq
```

#### Linux
```bash
# Download and install IBM MQ client
# Follow IBM's installation guide for your distribution
```

### Install the MCP Server

```bash
cd /Users/greg/dev/bob_work/ibm-mq-mcp-server
pip install -e .
```

Or install with development dependencies:

```bash
pip install -e ".[dev]"
```

## Configuration

### 1. Environment Configuration

Copy the example environment file and configure your IBM MQ connection:

```bash
cp .env.example .env
```

Edit `.env` with your IBM MQ details:

```env
IBMMQ_QUEUE_MANAGER=QM1
IBMMQ_CHANNEL=DEV.APP.SVRCONN
IBMMQ_HOST=localhost
IBMMQ_PORT=1414
IBMMQ_USERNAME=app
IBMMQ_PASSWORD=passw0rd
MCP_CURRENT_USER_ID=admin_user
```

### 2. User Permissions Configuration

Copy the example users configuration:

```bash
cp users.json.example users.json
```

Edit `users.json` to define users and their permissions:

```json
{
  "users": [
    {
      "user_id": "admin_user",
      "role": "admin",
      "queue_permissions": []
    },
    {
      "user_id": "restricted_admin",
      "role": "admin",
      "queue_permissions": [
        {
          "queue_pattern": "SENSITIVE.*",
          "allowed_actions": ["browse_message", "get_queue_info"],
          "denied_actions": ["put_message", "get_message", "delete_message"]
        }
      ]
    }
  ]
}
```

## Roles and Permissions

### Predefined Roles

| Role | Permissions |
|------|-------------|
| **Admin** | Full access to all operations (put, get, browse, delete messages, manage queues) |
| **Writer** | Can put, get, and browse messages; cannot manage queues |
| **Reader** | Can get and browse messages; cannot put messages |
| **Browser** | Can only browse messages (non-destructive read) |
| **Monitor** | Can only view queue information; cannot access messages |

### Available Actions

- `put_message` - Put messages on queues
- `get_message` - Get messages from queues (destructive read)
- `browse_message` - Browse messages without removing them
- `delete_message` - Delete messages
- `create_queue` - Create new queues
- `delete_queue` - Delete queues
- `manage_queue` - Manage queue properties
- `connect` - Connect to queue manager
- `disconnect` - Disconnect from queue manager
- `list_queues` - List available queues
- `get_queue_info` - Get queue information

### Queue-Specific Permissions

You can override role permissions for specific queue patterns:

```json
{
  "user_id": "restricted_admin",
  "role": "admin",
  "queue_permissions": [
    {
      "queue_pattern": "SENSITIVE.*",
      "allowed_actions": ["browse_message"],
      "denied_actions": ["put_message", "get_message"]
    }
  ]
}
```

Queue patterns support wildcards:
- `*` matches any characters
- `?` matches a single character
- Examples: `APP.*`, `PROD.*.REQUEST`, `DEV.??.QUEUE`

## Usage

### Running the Server

```bash
ibm-mq-mcp
```

Or run directly with Python:

```bash
python -m ibm_mq_mcp.server
```

### Available Tools

The server exposes the following MCP tools (based on user permissions):

#### Connection Management

- **connect**: Connect to IBM MQ queue manager
- **disconnect**: Disconnect from queue manager

#### Message Operations

- **put_message**: Put a message on a queue
  ```json
  {
    "queue_name": "DEV.QUEUE.1",
    "message": "Hello, IBM MQ!",
    "message_id": "optional-msg-id",
    "correlation_id": "optional-corr-id"
  }
  ```

- **get_message**: Get a message from a queue (destructive)
  ```json
  {
    "queue_name": "DEV.QUEUE.1",
    "wait_interval": 5000
  }
  ```

- **browse_message**: Browse a message without removing it
  ```json
  {
    "queue_name": "DEV.QUEUE.1",
    "browse_first": true
  }
  ```

#### Queue Information

- **list_queues**: List queues matching a pattern
  ```json
  {
    "pattern": "DEV.*"
  }
  ```

- **get_queue_info**: Get information about a queue
  ```json
  {
    "queue_name": "DEV.QUEUE.1"
  }
  ```

## Use Cases

### Restricting Admin Actions on Sensitive Queues

Even users with admin role can be restricted from certain actions on sensitive queues:

```json
{
  "user_id": "admin_user",
  "role": "admin",
  "queue_permissions": [
    {
      "queue_pattern": "PROD.FINANCIAL.*",
      "allowed_actions": ["browse_message", "get_queue_info"],
      "denied_actions": ["put_message", "get_message", "delete_message", "delete_queue"]
    }
  ]
}
```

This configuration allows the admin to:
- ✅ Browse messages (read-only)
- ✅ View queue information
- ❌ Put new messages
- ❌ Get/consume messages
- ❌ Delete messages or queues

### Granting Limited Write Access

Give a reader role write access to specific queues:

```json
{
  "user_id": "app_user",
  "role": "reader",
  "queue_permissions": [
    {
      "queue_pattern": "APP.OUTPUT.*",
      "allowed_actions": ["put_message"],
      "denied_actions": []
    }
  ]
}
```

## Development

### Running Tests

```bash
pytest
```

### Code Formatting

```bash
black src/
ruff check src/
```

### Type Checking

```bash
mypy src/
```

## Architecture

```
ibm-mq-mcp-server/
├── src/ibm_mq_mcp/
│   ├── __init__.py
│   ├── authorization.py    # Role-based authorization system
│   ├── config.py           # Configuration management
│   ├── mq_client.py        # IBM MQ client wrapper
│   └── server.py           # MCP server implementation
├── pyproject.toml          # Project configuration
├── users.json              # User permissions configuration
└── .env                    # Environment configuration
```

## Security Considerations

1. **Credential Management**: Store IBM MQ credentials securely (use environment variables or secret management)
2. **Permission Auditing**: All permission checks are logged for audit purposes
3. **Least Privilege**: Assign users the minimum role needed for their tasks
4. **Queue Patterns**: Use specific patterns rather than wildcards when possible
5. **Deny Takes Precedence**: Explicit denies in queue permissions override allows

## Troubleshooting

### Connection Issues

```bash
# Check IBM MQ client installation
python -c "import pymqi; print(pymqi.__version__)"

# Verify queue manager is running
dspmq

# Test connection manually
amqsputc QUEUE.NAME QMGR.NAME
```

### Permission Errors

Check the logs for detailed permission denial messages:
```
❌ Permission denied: User 'user_id' does not have permission to perform action 'put_message' on queue 'QUEUE.NAME'
```

Verify:
1. User exists in `users.json`
2. User's role includes the required action
3. No queue-specific denials are blocking the action

## License

MIT License - See LICENSE file for details

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Submit a pull request

## Support

For issues and questions:
- GitHub Issues: [Create an issue]
- Documentation: See this README
- IBM MQ Documentation: https://www.ibm.com/docs/en/ibm-mq