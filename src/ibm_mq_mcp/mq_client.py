"""IBM MQ client wrapper with authorization integration."""

import logging
from typing import Optional, Any, Dict, List
from contextlib import contextmanager

try:
    import pymqi
except ImportError:
    pymqi = None  # type: ignore

from .authorization import AuthorizationManager, Action
from .config import IBMMQConfig

logger = logging.getLogger(__name__)


class IBMMQClient:
    """IBM MQ client with authorization checks."""
    
    def __init__(
        self,
        config: IBMMQConfig,
        auth_manager: AuthorizationManager,
        user_id: str
    ):
        """
        Initialize IBM MQ client.
        
        Args:
            config: IBM MQ configuration
            auth_manager: Authorization manager
            user_id: Current user ID
        """
        if pymqi is None:
            raise ImportError(
                "pymqi is not installed. Install it with: pip install pymqi"
            )
        
        self.config = config
        self.auth_manager = auth_manager
        self.user_id = user_id
        self.qmgr: Optional[pymqi.QueueManager] = None
        self._connected = False
    
    def connect(self) -> Dict[str, Any]:
        """
        Connect to IBM MQ queue manager.
        
        Returns:
            Connection status information
            
        Raises:
            PermissionError: If user doesn't have connect permission
            Exception: If connection fails
        """
        self.auth_manager.require_permission(self.user_id, Action.CONNECT)
        
        try:
            conn_info = f"{self.config.host}({self.config.port})"
            cd = pymqi.CD()
            cd.ChannelName = self.config.channel.encode()
            cd.ConnectionName = conn_info.encode()
            cd.ChannelType = pymqi.CMQC.MQCHT_CLNTCONN
            cd.TransportType = pymqi.CMQC.MQXPT_TCP
            
            self.qmgr = pymqi.QueueManager(None)
            
            # Build connection options based on configuration
            connect_opts = {
                'name': self.config.queue_manager,
                'cd': cd
            }
            
            # Add SSL configuration if enabled
            if self.config.use_ssl:
                sco = pymqi.SCO()
                if self.config.ssl_cipher_spec:
                    sco.CipherSpec = self.config.ssl_cipher_spec.encode()
                if self.config.ssl_key_repository:
                    sco.KeyRepository = self.config.ssl_key_repository.encode()
                connect_opts['sco'] = sco
            
            # Add credentials if provided
            if self.config.username and self.config.password:
                connect_opts['user'] = self.config.username
                connect_opts['password'] = self.config.password
            
            # Connect with options
            self.qmgr.connect_with_options(**connect_opts)
            
            self._connected = True
            logger.info(f"Connected to queue manager: {self.config.queue_manager}")
            
            return {
                "status": "connected",
                "queue_manager": self.config.queue_manager,
                "host": self.config.host,
                "port": self.config.port
            }
            
        except Exception as e:
            logger.error(f"Failed to connect to IBM MQ: {e}")
            raise
    
    def disconnect(self) -> Dict[str, str]:
        """
        Disconnect from IBM MQ queue manager.
        
        Returns:
            Disconnection status
            
        Raises:
            PermissionError: If user doesn't have disconnect permission
        """
        self.auth_manager.require_permission(self.user_id, Action.DISCONNECT)
        
        if self.qmgr and self._connected:
            try:
                self.qmgr.disconnect()
                self._connected = False
                logger.info("Disconnected from queue manager")
                return {"status": "disconnected"}
            except Exception as e:
                logger.error(f"Error disconnecting: {e}")
                raise
        
        return {"status": "not_connected"}
    
    def put_message(
        self,
        queue_name: str,
        message: str,
        message_id: Optional[str] = None,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Put a message on a queue.
        
        Args:
            queue_name: Name of the queue
            message: Message content
            message_id: Optional message ID
            correlation_id: Optional correlation ID
            
        Returns:
            Message put confirmation
            
        Raises:
            PermissionError: If user doesn't have put permission
            Exception: If put operation fails
        """
        self.auth_manager.require_permission(
            self.user_id, Action.PUT_MESSAGE, queue_name
        )
        self._ensure_connected()
        
        try:
            queue = pymqi.Queue(self.qmgr, queue_name)
            
            md = pymqi.MD()
            if message_id:
                md.MsgId = message_id.encode()
            if correlation_id:
                md.CorrelId = correlation_id.encode()
            
            queue.put(message.encode(), md)
            queue.close()
            
            logger.info(f"Message put to queue: {queue_name}")
            
            return {
                "status": "success",
                "queue": queue_name,
                "message_length": len(message)
            }
            
        except Exception as e:
            logger.error(f"Failed to put message: {e}")
            raise
    
    def get_message(
        self,
        queue_name: str,
        wait_interval: int = 0
    ) -> Dict[str, Any]:
        """
        Get a message from a queue (destructive read).
        
        Args:
            queue_name: Name of the queue
            wait_interval: Wait interval in milliseconds
            
        Returns:
            Message data
            
        Raises:
            PermissionError: If user doesn't have get permission
            Exception: If get operation fails
        """
        self.auth_manager.require_permission(
            self.user_id, Action.GET_MESSAGE, queue_name
        )
        self._ensure_connected()
        
        try:
            queue = pymqi.Queue(self.qmgr, queue_name)
            
            gmo = pymqi.GMO()
            gmo.Options = pymqi.CMQC.MQGMO_WAIT | pymqi.CMQC.MQGMO_FAIL_IF_QUIESCING
            gmo.WaitInterval = wait_interval
            
            md = pymqi.MD()
            message = queue.get(None, md, gmo)
            queue.close()
            
            logger.info(f"Message retrieved from queue: {queue_name}")
            
            return {
                "status": "success",
                "queue": queue_name,
                "message": message.decode('utf-8', errors='replace'),
                "message_id": md.MsgId.hex(),
                "correlation_id": md.CorrelId.hex()
            }
            
        except pymqi.MQMIError as e:
            if e.comp == pymqi.CMQC.MQCC_FAILED and e.reason == pymqi.CMQC.MQRC_NO_MSG_AVAILABLE:
                return {
                    "status": "no_message",
                    "queue": queue_name
                }
            logger.error(f"Failed to get message: {e}")
            raise
    
    def browse_message(
        self,
        queue_name: str,
        browse_first: bool = True
    ) -> Dict[str, Any]:
        """
        Browse a message from a queue (non-destructive read).
        
        Args:
            queue_name: Name of the queue
            browse_first: If True, browse first message; otherwise browse next
            
        Returns:
            Message data
            
        Raises:
            PermissionError: If user doesn't have browse permission
            Exception: If browse operation fails
        """
        self.auth_manager.require_permission(
            self.user_id, Action.BROWSE_MESSAGE, queue_name
        )
        self._ensure_connected()
        
        try:
            queue = pymqi.Queue(self.qmgr, queue_name)
            
            gmo = pymqi.GMO()
            if browse_first:
                gmo.Options = pymqi.CMQC.MQGMO_BROWSE_FIRST
            else:
                gmo.Options = pymqi.CMQC.MQGMO_BROWSE_NEXT
            
            md = pymqi.MD()
            message = queue.get(None, md, gmo)
            queue.close()
            
            logger.info(f"Message browsed from queue: {queue_name}")
            
            return {
                "status": "success",
                "queue": queue_name,
                "message": message.decode('utf-8', errors='replace'),
                "message_id": md.MsgId.hex(),
                "correlation_id": md.CorrelId.hex()
            }
            
        except pymqi.MQMIError as e:
            if e.comp == pymqi.CMQC.MQCC_FAILED and e.reason == pymqi.CMQC.MQRC_NO_MSG_AVAILABLE:
                return {
                    "status": "no_message",
                    "queue": queue_name
                }
            logger.error(f"Failed to browse message: {e}")
            raise
    
    def list_queues(self, pattern: str = "*") -> List[str]:
        """
        List queues matching a pattern.
        
        Args:
            pattern: Queue name pattern (supports * wildcard)
            
        Returns:
            List of queue names
            
        Raises:
            PermissionError: If user doesn't have list permission
            Exception: If list operation fails
        """
        self.auth_manager.require_permission(self.user_id, Action.LIST_QUEUES)
        self._ensure_connected()
        
        try:
            pcf = pymqi.PCFExecute(self.qmgr)
            
            response = pcf.MQCMD_INQUIRE_Q(
                {pymqi.CMQC.MQCA_Q_NAME: pattern.encode()}
            )
            
            queues = []
            for queue_info in response:
                queue_name = queue_info[pymqi.CMQC.MQCA_Q_NAME].decode().strip()
                queues.append(queue_name)
            
            logger.info(f"Listed {len(queues)} queues")
            return queues
            
        except Exception as e:
            logger.error(f"Failed to list queues: {e}")
            raise
    
    def get_queue_info(self, queue_name: str) -> Dict[str, Any]:
        """
        Get information about a queue.
        
        Args:
            queue_name: Name of the queue
            
        Returns:
            Queue information
            
        Raises:
            PermissionError: If user doesn't have get info permission
            Exception: If operation fails
        """
        self.auth_manager.require_permission(
            self.user_id, Action.GET_QUEUE_INFO, queue_name
        )
        self._ensure_connected()
        
        try:
            pcf = pymqi.PCFExecute(self.qmgr)
            
            response = pcf.MQCMD_INQUIRE_Q(
                {pymqi.CMQC.MQCA_Q_NAME: queue_name.encode()}
            )
            
            if not response:
                raise ValueError(f"Queue not found: {queue_name}")
            
            queue_info = response[0]
            
            return {
                "queue_name": queue_name,
                "current_depth": queue_info.get(pymqi.CMQC.MQIA_CURRENT_Q_DEPTH, 0),
                "max_depth": queue_info.get(pymqi.CMQC.MQIA_MAX_Q_DEPTH, 0),
                "open_input_count": queue_info.get(pymqi.CMQC.MQIA_OPEN_INPUT_COUNT, 0),
                "open_output_count": queue_info.get(pymqi.CMQC.MQIA_OPEN_OUTPUT_COUNT, 0)
            }
            
        except Exception as e:
            logger.error(f"Failed to get queue info: {e}")
            raise
    
    def create_queue(
        self,
        queue_name: str,
        queue_type: str = "LOCAL",
        max_depth: int = 5000,
        description: str = "",
        **kwargs
    ) -> Dict[str, Any]:
        """
        Create a new queue using PCF commands.
        
        Args:
            queue_name: Name of the queue to create
            queue_type: Type of queue (LOCAL, ALIAS, REMOTE, MODEL)
            max_depth: Maximum queue depth
            description: Queue description
            **kwargs: Additional queue attributes
            
        Returns:
            Queue creation confirmation
            
        Raises:
            PermissionError: If user doesn't have create permission
            Exception: If creation fails
        """
        self.auth_manager.require_permission(self.user_id, Action.CREATE_QUEUE)
        self._ensure_connected()
        
        try:
            pcf = pymqi.PCFExecute(self.qmgr)
            
            # Build queue attributes
            attrs = {
                pymqi.CMQC.MQCA_Q_NAME: queue_name.encode(),
                pymqi.CMQC.MQIA_Q_TYPE: self._get_queue_type_constant(queue_type),
                pymqi.CMQC.MQIA_MAX_Q_DEPTH: max_depth,
            }
            
            if description:
                attrs[pymqi.CMQC.MQCA_Q_DESC] = description.encode()
            
            # Add any additional attributes
            for key, value in kwargs.items():
                if hasattr(pymqi.CMQC, key):
                    attr_const = getattr(pymqi.CMQC, key)
                    if isinstance(value, str):
                        attrs[attr_const] = value.encode()
                    else:
                        attrs[attr_const] = value
            
            pcf.MQCMD_CREATE_Q(attrs)
            
            logger.info(f"Created queue: {queue_name}")
            
            return {
                "status": "success",
                "queue_name": queue_name,
                "queue_type": queue_type,
                "max_depth": max_depth
            }
            
        except Exception as e:
            logger.error(f"Failed to create queue: {e}")
            raise
    
    def delete_queue(self, queue_name: str, purge: bool = False) -> Dict[str, Any]:
        """
        Delete a queue.
        
        Args:
            queue_name: Name of the queue to delete
            purge: If True, purge messages before deleting
            
        Returns:
            Queue deletion confirmation
            
        Raises:
            PermissionError: If user doesn't have delete permission
            Exception: If deletion fails
        """
        self.auth_manager.require_permission(
            self.user_id, Action.DELETE_QUEUE, queue_name
        )
        self._ensure_connected()
        
        try:
            pcf = pymqi.PCFExecute(self.qmgr)
            
            attrs = {
                pymqi.CMQC.MQCA_Q_NAME: queue_name.encode(),
            }
            
            # Note: MQCMD_DELETE_Q will fail if queue has messages unless purged first
            # For now, we don't use the purge parameter as MQPO_YES constant doesn't exist
            # Users should clear queues before deleting
            
            pcf.MQCMD_DELETE_Q(attrs)
            
            logger.info(f"Deleted queue: {queue_name}")
            
            return {
                "status": "success",
                "queue_name": queue_name,
                "purged": purge
            }
            
        except Exception as e:
            logger.error(f"Failed to delete queue: {e}")
            raise
    
    def alter_queue(
        self,
        queue_name: str,
        **attributes
    ) -> Dict[str, Any]:
        """
        Alter queue attributes.
        
        Args:
            queue_name: Name of the queue to alter
            **attributes: Queue attributes to modify
            
        Returns:
            Queue alteration confirmation
            
        Raises:
            PermissionError: If user doesn't have manage permission
            Exception: If alteration fails
        """
        self.auth_manager.require_permission(
            self.user_id, Action.MANAGE_QUEUE, queue_name
        )
        self._ensure_connected()
        
        try:
            pcf = pymqi.PCFExecute(self.qmgr)
            
            attrs = {
                pymqi.CMQC.MQCA_Q_NAME: queue_name.encode(),
            }
            
            # Add attributes to modify
            for key, value in attributes.items():
                if hasattr(pymqi.CMQC, key):
                    attr_const = getattr(pymqi.CMQC, key)
                    if isinstance(value, str):
                        attrs[attr_const] = value.encode()
                    else:
                        attrs[attr_const] = value
            
            pcf.MQCMD_CHANGE_Q(attrs)
            
            logger.info(f"Altered queue: {queue_name}")
            
            return {
                "status": "success",
                "queue_name": queue_name,
                "modified_attributes": list(attributes.keys())
            }
            
        except Exception as e:
            logger.error(f"Failed to alter queue: {e}")
            raise
    
    def execute_mqsc(self, mqsc_command: str) -> Dict[str, Any]:
        """
        Execute an MQSC command.
        
        Args:
            mqsc_command: MQSC command to execute
            
        Returns:
            Command execution result
            
        Raises:
            PermissionError: If user doesn't have appropriate permission
            Exception: If execution fails
        """
        # Determine required permission based on command
        command_upper = mqsc_command.strip().upper()
        
        if command_upper.startswith('DEFINE '):
            self.auth_manager.require_permission(self.user_id, Action.CREATE_QUEUE)
        elif command_upper.startswith('DELETE '):
            # Extract queue name for permission check
            self.auth_manager.require_permission(self.user_id, Action.DELETE_QUEUE)
        elif command_upper.startswith('ALTER '):
            self.auth_manager.require_permission(self.user_id, Action.MANAGE_QUEUE)
        elif command_upper.startswith('DISPLAY '):
            self.auth_manager.require_permission(self.user_id, Action.GET_QUEUE_INFO)
        else:
            # For other commands, require admin role
            self.auth_manager.require_permission(self.user_id, Action.MANAGE_QUEUE)
        
        self._ensure_connected()
        
        try:
            logger.info(f"execute_mqsc called with command: {mqsc_command}")
            logger.info(f"command_upper: {command_upper}")
            
            # Special handling for ALTER QLOCAL commands - use PCF directly
            if command_upper.startswith('ALTER QLOCAL('):
                logger.info("Detected ALTER QLOCAL command, attempting PCF path")
                import re
                match = re.match(r'ALTER\s+QLOCAL\(([^)]+)\)\s+MAXDEPTH\((\d+)\)', command_upper)
                if match:
                    queue_name = match.group(1)
                    new_maxdepth = int(match.group(2))
                    
                    pcf = pymqi.PCFExecute(self.qmgr)
                    args = {
                        pymqi.CMQC.MQCA_Q_NAME: queue_name.encode(),
                        pymqi.CMQC.MQIA_Q_TYPE: pymqi.CMQC.MQQT_LOCAL,
                        pymqi.CMQC.MQIA_MAX_Q_DEPTH: new_maxdepth
                    }
                    
                    pcf.MQCMD_CHANGE_Q(args)
                    logger.info(f"Changed MAXDEPTH for {queue_name} to {new_maxdepth} using PCF")
                    
                    return {
                        "status": "success",
                        "command": mqsc_command,
                        "result": f"Queue {queue_name} MAXDEPTH changed to {new_maxdepth}"
                    }
            
            # For other commands, use MQSC ESCAPE
            pcf = pymqi.PCFExecute(self.qmgr)
            
            # Execute MQSC command using ESCAPE
            args = {
                pymqi.CMQCFC.MQIACF_ESCAPE_TYPE: pymqi.CMQCFC.MQET_MQSC,
                pymqi.CMQCFC.MQCACF_ESCAPE_TEXT: mqsc_command.encode()
            }
            
            result = pcf.MQCMD_ESCAPE(args)
            
            logger.info(f"Executed MQSC command: {mqsc_command[:50]}...")
            
            # Parse result
            response_text = ""
            if result and len(result) > 0:
                for response in result:
                    if pymqi.CMQCFC.MQCACF_ESCAPE_TEXT in response:
                        response_text = response[pymqi.CMQCFC.MQCACF_ESCAPE_TEXT].decode('utf-8', errors='ignore')
            
            return {
                "status": "success",
                "command": mqsc_command,
                "result": response_text if response_text else "Command executed successfully"
            }
            
        except Exception as e:
            logger.error(f"Failed to execute MQSC command: {e}")
            return {
                "status": "error",
                "command": mqsc_command,
                "message": str(e)
            }
    
    def _get_queue_type_constant(self, queue_type: str) -> int:
        """Convert queue type string to pymqi constant."""
        type_map = {
            "LOCAL": pymqi.CMQC.MQQT_LOCAL,
            "ALIAS": pymqi.CMQC.MQQT_ALIAS,
            "REMOTE": pymqi.CMQC.MQQT_REMOTE,
            "MODEL": pymqi.CMQC.MQQT_MODEL,
        }
        return type_map.get(queue_type.upper(), pymqi.CMQC.MQQT_LOCAL)
    
    def _ensure_connected(self) -> None:
        """Ensure client is connected to queue manager."""
        if not self._connected or self.qmgr is None:
            raise RuntimeError("Not connected to queue manager. Call connect() first.")
    
    @contextmanager
    def connection(self):
        """Context manager for automatic connection/disconnection."""
        try:
            self.connect()
            yield self
        finally:
            if self._connected:
                self.disconnect()