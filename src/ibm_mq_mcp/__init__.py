"""IBM MQ MCP Server - MCP server for IBM MQ with role-based authorization."""

from .authorization import (
    Action,
    Role,
    UserPermissions,
    AuthorizationManager,
    ROLE_PERMISSIONS,
)
from .config import ServerConfig, IBMMQConfig, load_users_from_file
from .mq_client import IBMMQClient
from .server import IBMMQMCPServer

__version__ = "0.1.0"

__all__ = [
    "Action",
    "Role",
    "UserPermissions",
    "AuthorizationManager",
    "ROLE_PERMISSIONS",
    "ServerConfig",
    "IBMMQConfig",
    "load_users_from_file",
    "IBMMQClient",
    "IBMMQMCPServer",
]