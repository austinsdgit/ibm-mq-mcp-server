"""Configuration management for IBM MQ MCP server."""

from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from .authorization import UserPermissions


class IBMMQConfig(BaseSettings):
    """IBM MQ connection configuration."""
    
    model_config = SettingsConfigDict(
        env_prefix="IBMMQ_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    # Connection settings
    queue_manager: str = Field(
        description="Queue manager name"
    )
    channel: str = Field(
        description="Channel name"
    )
    host: str = Field(
        default="localhost",
        description="IBM MQ host"
    )
    port: int = Field(
        default=1414,
        description="IBM MQ port"
    )
    
    # Authentication
    username: Optional[str] = Field(
        default=None,
        description="Username for authentication"
    )
    password: Optional[str] = Field(
        default=None,
        description="Password for authentication"
    )
    
    # SSL/TLS settings
    use_ssl: bool = Field(
        default=False,
        description="Use SSL/TLS connection"
    )
    ssl_cipher_spec: Optional[str] = Field(
        default=None,
        description="SSL cipher specification"
    )
    ssl_key_repository: Optional[str] = Field(
        default=None,
        description="Path to SSL key repository"
    )
    
    # Connection options
    connection_timeout: int = Field(
        default=30,
        description="Connection timeout in seconds"
    )
    max_retries: int = Field(
        default=3,
        description="Maximum connection retry attempts"
    )


class ServerConfig(BaseSettings):
    """MCP server configuration."""
    
    model_config = SettingsConfigDict(
        env_prefix="MCP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    # Server settings
    server_name: str = Field(
        default="ibm-mq-mcp-server",
        description="MCP server name"
    )
    server_version: str = Field(
        default="0.1.0",
        description="MCP server version"
    )
    
    # Current user (for authorization)
    current_user_id: str = Field(
        default="default_user",
        description="Current user ID for authorization checks"
    )
    
    # Logging
    log_level: str = Field(
        default="INFO",
        description="Logging level"
    )
    
    # IBM MQ configuration
    ibm_mq: IBMMQConfig = Field(
        default_factory=IBMMQConfig,
        description="IBM MQ connection configuration"
    )


class AuthorizationConfig(BaseSettings):
    """Authorization configuration."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    # Users will be loaded from a separate JSON/YAML file
    users_config_path: str = Field(
        default="users.json",
        description="Path to users configuration file"
    )


def load_users_from_file(file_path: str) -> list[UserPermissions]:
    """
    Load user permissions from a JSON or YAML file.
    
    Args:
        file_path: Path to the configuration file
        
    Returns:
        List of user permissions
    """
    import json
    from pathlib import Path
    
    path = Path(file_path)
    
    if not path.exists():
        # Return default user if config file doesn't exist
        from .authorization import Role
        return [
            UserPermissions(
                user_id="default_user",
                role=Role.ADMIN,
                queue_permissions=[]
            )
        ]
    
    with open(path, "r") as f:
        if path.suffix == ".json":
            data = json.load(f)
        elif path.suffix in [".yaml", ".yml"]:
            import yaml
            data = yaml.safe_load(f)
        else:
            raise ValueError(f"Unsupported config file format: {path.suffix}")
    
    users = []
    for user_data in data.get("users", []):
        users.append(UserPermissions(**user_data))
    
    return users