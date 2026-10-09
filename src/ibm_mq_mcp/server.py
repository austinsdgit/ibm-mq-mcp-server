"""MCP server implementation for IBM MQ."""

import logging
import sys
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from .authorization import AuthorizationManager, Action, Role
from .config import ServerConfig, load_users_from_file
from .mq_client import IBMMQClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class IBMMQMCPServer:
    """MCP server for IBM MQ operations with authorization."""
    
    def __init__(self):
        """Initialize the MCP server."""
        self.config = ServerConfig()
        
        # Load user permissions
        users = load_users_from_file(self.config.ibm_mq.users_config_path if hasattr(self.config.ibm_mq, 'users_config_path') else "users.json")
        self.auth_manager = AuthorizationManager(users)
        
        # Initialize MQ client
        self.mq_client = IBMMQClient(
            config=self.config.ibm_mq,
            auth_manager=self.auth_manager,
            user_id=self.config.current_user_id
        )
        
        # Create MCP server
        self.server = Server(self.config.server_name)
        self._register_handlers()
    
    def _register_handlers(self) -> None:
        """Register MCP tool handlers."""
        
        @self.server.list_tools()
        async def list_tools() -> list[Tool]:
            """List available tools based on user permissions."""
            user_role = self.auth_manager.get_user_role(self.config.current_user_id)
            
            tools = []
            
            # Connection tools
            if self.auth_manager.check_permission(self.config.current_user_id, Action.CONNECT):
                tools.append(Tool(
                    name="connect",
                    description="Connect to IBM MQ queue manager",
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                ))
            
            if self.auth_manager.check_permission(self.config.current_user_id, Action.DISCONNECT):
                tools.append(Tool(
                    name="disconnect",
                    description="Disconnect from IBM MQ queue manager",
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                ))
            
            # Message operations
            if self.auth_manager.check_permission(self.config.current_user_id, Action.PUT_MESSAGE):
                tools.append(Tool(
                    name="put_message",
                    description="Put a message on a queue",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "queue_name": {
                                "type": "string",
                                "description": "Name of the queue"
                            },
                            "message": {
                                "type": "string",
                                "description": "Message content"
                            },
                            "message_id": {
                                "type": "string",
                                "description": "Optional message ID"
                            },
                            "correlation_id": {
                                "type": "string",
                                "description": "Optional correlation ID"
                            }
                        },
                        "required": ["queue_name", "message"]
                    }
                ))
            
            if self.auth_manager.check_permission(self.config.current_user_id, Action.GET_MESSAGE):
                tools.append(Tool(
                    name="get_message",
                    description="Get a message from a queue (destructive read)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "queue_name": {
                                "type": "string",
                                "description": "Name of the queue"
                            },
                            "wait_interval": {
                                "type": "integer",
                                "description": "Wait interval in milliseconds",
                                "default": 0
                            }
                        },
                        "required": ["queue_name"]
                    }
                ))
            
            if self.auth_manager.check_permission(self.config.current_user_id, Action.BROWSE_MESSAGE):
                tools.append(Tool(
                    name="browse_message",
                    description="Browse a message from a queue (non-destructive read)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "queue_name": {
                                "type": "string",
                                "description": "Name of the queue"
                            },
                            "browse_first": {
                                "type": "boolean",
                                "description": "Browse first message (true) or next message (false)",
                                "default": True
                            }
                        },
                        "required": ["queue_name"]
                    }
                ))
            
            # Queue information
            if self.auth_manager.check_permission(self.config.current_user_id, Action.LIST_QUEUES):
                tools.append(Tool(
                    name="list_queues",
                    description="List queues matching a pattern",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "pattern": {
                                "type": "string",
                                "description": "Queue name pattern (supports * wildcard)",
                                "default": "*"
                            }
                        },
                        "required": []
                    }
                ))
            
            if self.auth_manager.check_permission(self.config.current_user_id, Action.GET_QUEUE_INFO):
                tools.append(Tool(
                    name="get_queue_info",
                    description="Get information about a queue",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "queue_name": {
                                "type": "string",
                                "description": "Name of the queue"
                            }
                        },
                        "required": ["queue_name"]
                    }
                ))
            
            # Queue management operations
            if self.auth_manager.check_permission(self.config.current_user_id, Action.CREATE_QUEUE):
                tools.append(Tool(
                    name="create_queue",
                    description="Create a new queue",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "queue_name": {
                                "type": "string",
                                "description": "Name of the queue to create"
                            },
                            "queue_type": {
                                "type": "string",
                                "description": "Type of queue (LOCAL, ALIAS, REMOTE, MODEL)",
                                "default": "LOCAL"
                            },
                            "max_depth": {
                                "type": "integer",
                                "description": "Maximum queue depth",
                                "default": 5000
                            },
                            "description": {
                                "type": "string",
                                "description": "Queue description",
                                "default": ""
                            }
                        },
                        "required": ["queue_name"]
                    }
                ))
            
            if self.auth_manager.check_permission(self.config.current_user_id, Action.DELETE_QUEUE):
                tools.append(Tool(
                    name="delete_queue",
                    description="Delete a queue",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "queue_name": {
                                "type": "string",
                                "description": "Name of the queue to delete"
                            },
                            "purge": {
                                "type": "boolean",
                                "description": "Purge messages before deleting",
                                "default": False
                            }
                        },
                        "required": ["queue_name"]
                    }
                ))
            
            if self.auth_manager.check_permission(self.config.current_user_id, Action.MANAGE_QUEUE):
                tools.append(Tool(
                    name="alter_queue",
                    description="Alter queue attributes",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "queue_name": {
                                "type": "string",
                                "description": "Name of the queue to alter"
                            },
                            "attributes": {
                                "type": "object",
                                "description": "Queue attributes to modify (e.g., MQIA_MAX_Q_DEPTH, MQCA_Q_DESC)"
                            }
                        },
                        "required": ["queue_name", "attributes"]
                    }
                ))
                
                tools.append(Tool(
                    name="execute_mqsc",
                    description="Execute an MQSC command",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "mqsc_command": {
                                "type": "string",
                                "description": "MQSC command to execute (e.g., 'DEFINE QLOCAL(MYQUEUE) MAXDEPTH(10000)')"
                            }
                        },
                        "required": ["mqsc_command"]
                    }
                ))
            
            return tools
        
        @self.server.call_tool()
        async def call_tool(name: str, arguments: Any) -> list[TextContent]:
            """Handle tool calls."""
            try:
                if name == "connect":
                    result = self.mq_client.connect()
                    return [TextContent(
                        type="text",
                        text=f"Connected to IBM MQ:\n{self._format_dict(result)}"
                    )]
                
                elif name == "disconnect":
                    result = self.mq_client.disconnect()
                    return [TextContent(
                        type="text",
                        text=f"Disconnected from IBM MQ:\n{self._format_dict(result)}"
                    )]
                
                elif name == "put_message":
                    result = self.mq_client.put_message(
                        queue_name=arguments["queue_name"],
                        message=arguments["message"],
                        message_id=arguments.get("message_id"),
                        correlation_id=arguments.get("correlation_id")
                    )
                    return [TextContent(
                        type="text",
                        text=f"Message sent:\n{self._format_dict(result)}"
                    )]
                
                elif name == "get_message":
                    result = self.mq_client.get_message(
                        queue_name=arguments["queue_name"],
                        wait_interval=arguments.get("wait_interval", 0)
                    )
                    return [TextContent(
                        type="text",
                        text=f"Message retrieved:\n{self._format_dict(result)}"
                    )]
                
                elif name == "browse_message":
                    result = self.mq_client.browse_message(
                        queue_name=arguments["queue_name"],
                        browse_first=arguments.get("browse_first", True)
                    )
                    return [TextContent(
                        type="text",
                        text=f"Message browsed:\n{self._format_dict(result)}"
                    )]
                
                elif name == "list_queues":
                    result = self.mq_client.list_queues(
                        pattern=arguments.get("pattern", "*")
                    )
                    return [TextContent(
                        type="text",
                        text=f"Queues found:\n" + "\n".join(f"  - {q}" for q in result)
                    )]
                
                elif name == "get_queue_info":
                    result = self.mq_client.get_queue_info(
                        queue_name=arguments["queue_name"]
                    )
                    return [TextContent(
                        type="text",
                        text=f"Queue information:\n{self._format_dict(result)}"
                    )]
                
                elif name == "create_queue":
                    result = self.mq_client.create_queue(
                        queue_name=arguments["queue_name"],
                        queue_type=arguments.get("queue_type", "LOCAL"),
                        max_depth=arguments.get("max_depth", 5000),
                        description=arguments.get("description", "")
                    )
                    return [TextContent(
                        type="text",
                        text=f"Queue created:\n{self._format_dict(result)}"
                    )]
                
                elif name == "delete_queue":
                    result = self.mq_client.delete_queue(
                        queue_name=arguments["queue_name"],
                        purge=arguments.get("purge", False)
                    )
                    return [TextContent(
                        type="text",
                        text=f"Queue deleted:\n{self._format_dict(result)}"
                    )]
                
                elif name == "alter_queue":
                    result = self.mq_client.alter_queue(
                        queue_name=arguments["queue_name"],
                        **arguments.get("attributes", {})
                    )
                    return [TextContent(
                        type="text",
                        text=f"Queue altered:\n{self._format_dict(result)}"
                    )]
                
                elif name == "execute_mqsc":
                    result = self.mq_client.execute_mqsc(
                        mqsc_command=arguments["mqsc_command"]
                    )
                    return [TextContent(
                        type="text",
                        text=f"MQSC command executed:\n{self._format_dict(result)}"
                    )]
                
                else:
                    raise ValueError(f"Unknown tool: {name}")
                    
            except PermissionError as e:
                logger.error(f"Permission denied: {e}")
                return [TextContent(
                    type="text",
                    text=f"❌ Permission denied: {str(e)}"
                )]
            except Exception as e:
                logger.error(f"Error executing tool {name}: {e}", exc_info=True)
                return [TextContent(
                    type="text",
                    text=f"❌ Error: {str(e)}"
                )]
    
    @staticmethod
    def _format_dict(data: dict) -> str:
        """Format dictionary for display."""
        return "\n".join(f"  {k}: {v}" for k, v in data.items())
    
    async def run(self) -> None:
        """Run the MCP server."""
        async with stdio_server() as (read_stream, write_stream):
            logger.info(f"Starting {self.config.server_name} v{self.config.server_version}")
            logger.info(f"Current user: {self.config.current_user_id}")
            user_role = self.auth_manager.get_user_role(self.config.current_user_id)
            logger.info(f"User role: {user_role}")
            
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options()
            )


def main() -> None:
    """Main entry point."""
    import asyncio
    
    try:
        server = IBMMQMCPServer()
        asyncio.run(server.run())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()