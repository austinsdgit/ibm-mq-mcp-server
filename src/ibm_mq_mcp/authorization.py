"""Authorization and permission management for IBM MQ MCP server."""

from enum import Enum
from typing import Set, Dict, Optional
from pydantic import BaseModel, Field


class Action(str, Enum):
    """Available actions that can be performed on IBM MQ."""
    
    # Message operations
    PUT_MESSAGE = "put_message"
    GET_MESSAGE = "get_message"
    BROWSE_MESSAGE = "browse_message"
    DELETE_MESSAGE = "delete_message"
    
    # Queue management
    CREATE_QUEUE = "create_queue"
    DELETE_QUEUE = "delete_queue"
    MANAGE_QUEUE = "manage_queue"
    
    # Connection operations
    CONNECT = "connect"
    DISCONNECT = "disconnect"
    
    # Information operations
    LIST_QUEUES = "list_queues"
    GET_QUEUE_INFO = "get_queue_info"


class Role(str, Enum):
    """Predefined roles with specific permission sets."""
    
    ADMIN = "admin"
    WRITER = "writer"
    READER = "reader"
    BROWSER = "browser"
    MONITOR = "monitor"


# Define permissions for each role
ROLE_PERMISSIONS: Dict[Role, Set[Action]] = {
    Role.ADMIN: {
        # Full access to all operations
        Action.PUT_MESSAGE,
        Action.GET_MESSAGE,
        Action.BROWSE_MESSAGE,
        Action.DELETE_MESSAGE,
        Action.CREATE_QUEUE,
        Action.DELETE_QUEUE,
        Action.MANAGE_QUEUE,
        Action.CONNECT,
        Action.DISCONNECT,
        Action.LIST_QUEUES,
        Action.GET_QUEUE_INFO,
    },
    Role.WRITER: {
        # Can write and read messages, but not manage queues
        Action.PUT_MESSAGE,
        Action.GET_MESSAGE,
        Action.BROWSE_MESSAGE,
        Action.CONNECT,
        Action.DISCONNECT,
        Action.LIST_QUEUES,
        Action.GET_QUEUE_INFO,
    },
    Role.READER: {
        # Can only read and consume messages
        Action.GET_MESSAGE,
        Action.BROWSE_MESSAGE,
        Action.CONNECT,
        Action.DISCONNECT,
        Action.LIST_QUEUES,
        Action.GET_QUEUE_INFO,
    },
    Role.BROWSER: {
        # Can only browse messages without consuming
        Action.BROWSE_MESSAGE,
        Action.CONNECT,
        Action.DISCONNECT,
        Action.LIST_QUEUES,
        Action.GET_QUEUE_INFO,
    },
    Role.MONITOR: {
        # Can only view queue information
        Action.CONNECT,
        Action.DISCONNECT,
        Action.LIST_QUEUES,
        Action.GET_QUEUE_INFO,
    },
}


class QueuePermission(BaseModel):
    """Queue-specific permission override."""
    
    queue_pattern: str = Field(
        description="Queue name pattern (supports wildcards: * and ?)"
    )
    allowed_actions: Set[Action] = Field(
        default_factory=set,
        description="Actions allowed on matching queues"
    )
    denied_actions: Set[Action] = Field(
        default_factory=set,
        description="Actions explicitly denied on matching queues"
    )


class UserPermissions(BaseModel):
    """User permission configuration."""
    
    user_id: str = Field(description="User identifier")
    role: Role = Field(description="User's role")
    queue_permissions: list[QueuePermission] = Field(
        default_factory=list,
        description="Queue-specific permission overrides"
    )
    
    def has_permission(self, action: Action, queue_name: Optional[str] = None) -> bool:
        """
        Check if user has permission to perform an action.
        
        Args:
            action: The action to check
            queue_name: Optional queue name for queue-specific checks
            
        Returns:
            True if user has permission, False otherwise
        """
        # Get base permissions from role
        base_permissions = ROLE_PERMISSIONS.get(self.role, set())
        
        # If no queue specified, check base permissions only
        if queue_name is None:
            return action in base_permissions
        
        # Check queue-specific permissions
        for queue_perm in self.queue_permissions:
            if self._matches_pattern(queue_name, queue_perm.queue_pattern):
                # Explicit deny takes precedence
                if action in queue_perm.denied_actions:
                    return False
                # Explicit allow grants permission
                if action in queue_perm.allowed_actions:
                    return True
        
        # Fall back to base role permissions
        return action in base_permissions
    
    @staticmethod
    def _matches_pattern(queue_name: str, pattern: str) -> bool:
        """
        Check if queue name matches pattern (supports * and ? wildcards).
        
        Args:
            queue_name: The queue name to check
            pattern: The pattern to match against
            
        Returns:
            True if queue name matches pattern
        """
        import fnmatch
        return fnmatch.fnmatch(queue_name, pattern)


class AuthorizationManager:
    """Manages user permissions and authorization checks."""
    
    def __init__(self, users: list[UserPermissions]):
        """
        Initialize authorization manager.
        
        Args:
            users: List of user permission configurations
        """
        self.users: Dict[str, UserPermissions] = {
            user.user_id: user for user in users
        }
    
    def check_permission(
        self,
        user_id: str,
        action: Action,
        queue_name: Optional[str] = None
    ) -> bool:
        """
        Check if a user has permission to perform an action.
        
        Args:
            user_id: User identifier
            action: Action to check
            queue_name: Optional queue name for queue-specific checks
            
        Returns:
            True if user has permission, False otherwise
        """
        user = self.users.get(user_id)
        if user is None:
            return False
        
        return user.has_permission(action, queue_name)
    
    def require_permission(
        self,
        user_id: str,
        action: Action,
        queue_name: Optional[str] = None
    ) -> None:
        """
        Require permission or raise exception.
        
        Args:
            user_id: User identifier
            action: Action to check
            queue_name: Optional queue name for queue-specific checks
            
        Raises:
            PermissionError: If user doesn't have permission
        """
        if not self.check_permission(user_id, action, queue_name):
            queue_info = f" on queue '{queue_name}'" if queue_name else ""
            raise PermissionError(
                f"User '{user_id}' does not have permission to perform "
                f"action '{action.value}'{queue_info}"
            )
    
    def get_user_role(self, user_id: str) -> Optional[Role]:
        """
        Get user's role.
        
        Args:
            user_id: User identifier
            
        Returns:
            User's role or None if user not found
        """
        user = self.users.get(user_id)
        return user.role if user else None
    
    def add_user(self, user: UserPermissions) -> None:
        """
        Add or update a user's permissions.
        
        Args:
            user: User permission configuration
        """
        self.users[user.user_id] = user
    
    def remove_user(self, user_id: str) -> None:
        """
        Remove a user's permissions.
        
        Args:
            user_id: User identifier
        """
        self.users.pop(user_id, None)