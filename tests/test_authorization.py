"""Tests for authorization module."""

import pytest
from ibm_mq_mcp.authorization import (
    Action,
    Role,
    UserPermissions,
    AuthorizationManager,
    QueuePermission,
    ROLE_PERMISSIONS,
)


class TestRolePermissions:
    """Test role-based permissions."""
    
    def test_admin_has_all_permissions(self):
        """Admin role should have all permissions."""
        admin_perms = ROLE_PERMISSIONS[Role.ADMIN]
        assert Action.PUT_MESSAGE in admin_perms
        assert Action.GET_MESSAGE in admin_perms
        assert Action.DELETE_QUEUE in admin_perms
        assert Action.MANAGE_QUEUE in admin_perms
    
    def test_writer_cannot_manage_queues(self):
        """Writer role should not be able to manage queues."""
        writer_perms = ROLE_PERMISSIONS[Role.WRITER]
        assert Action.PUT_MESSAGE in writer_perms
        assert Action.GET_MESSAGE in writer_perms
        assert Action.CREATE_QUEUE not in writer_perms
        assert Action.DELETE_QUEUE not in writer_perms
    
    def test_reader_cannot_put_messages(self):
        """Reader role should not be able to put messages."""
        reader_perms = ROLE_PERMISSIONS[Role.READER]
        assert Action.GET_MESSAGE in reader_perms
        assert Action.BROWSE_MESSAGE in reader_perms
        assert Action.PUT_MESSAGE not in reader_perms
    
    def test_browser_can_only_browse(self):
        """Browser role should only browse messages."""
        browser_perms = ROLE_PERMISSIONS[Role.BROWSER]
        assert Action.BROWSE_MESSAGE in browser_perms
        assert Action.GET_MESSAGE not in browser_perms
        assert Action.PUT_MESSAGE not in browser_perms
    
    def test_monitor_can_only_view_info(self):
        """Monitor role should only view queue information."""
        monitor_perms = ROLE_PERMISSIONS[Role.MONITOR]
        assert Action.LIST_QUEUES in monitor_perms
        assert Action.GET_QUEUE_INFO in monitor_perms
        assert Action.BROWSE_MESSAGE not in monitor_perms
        assert Action.GET_MESSAGE not in monitor_perms


class TestUserPermissions:
    """Test user permission checks."""
    
    def test_user_has_role_permission(self):
        """User should have permissions from their role."""
        user = UserPermissions(user_id="test_user", role=Role.WRITER)
        assert user.has_permission(Action.PUT_MESSAGE)
        assert user.has_permission(Action.GET_MESSAGE)
    
    def test_user_lacks_role_permission(self):
        """User should not have permissions outside their role."""
        user = UserPermissions(user_id="test_user", role=Role.READER)
        assert not user.has_permission(Action.PUT_MESSAGE)
        assert not user.has_permission(Action.CREATE_QUEUE)
    
    def test_queue_specific_allow(self):
        """Queue-specific permissions should grant additional access."""
        user = UserPermissions(
            user_id="test_user",
            role=Role.READER,
            queue_permissions=[
                QueuePermission(
                    queue_pattern="APP.*",
                    allowed_actions={Action.PUT_MESSAGE},
                    denied_actions=set()
                )
            ]
        )
        # Should have put permission on matching queue
        assert user.has_permission(Action.PUT_MESSAGE, "APP.QUEUE.1")
        # Should not have put permission on non-matching queue
        assert not user.has_permission(Action.PUT_MESSAGE, "OTHER.QUEUE")
    
    def test_queue_specific_deny(self):
        """Queue-specific denials should override role permissions."""
        user = UserPermissions(
            user_id="test_user",
            role=Role.ADMIN,
            queue_permissions=[
                QueuePermission(
                    queue_pattern="SENSITIVE.*",
                    allowed_actions=set(),
                    denied_actions={Action.PUT_MESSAGE, Action.DELETE_MESSAGE}
                )
            ]
        )
        # Should be denied on matching queue
        assert not user.has_permission(Action.PUT_MESSAGE, "SENSITIVE.DATA")
        # Should have permission on non-matching queue
        assert user.has_permission(Action.PUT_MESSAGE, "NORMAL.QUEUE")
    
    def test_wildcard_pattern_matching(self):
        """Test wildcard pattern matching."""
        user = UserPermissions(
            user_id="test_user",
            role=Role.READER,
            queue_permissions=[
                QueuePermission(
                    queue_pattern="DEV.*.REQUEST",
                    allowed_actions={Action.PUT_MESSAGE},
                    denied_actions=set()
                )
            ]
        )
        assert user.has_permission(Action.PUT_MESSAGE, "DEV.APP.REQUEST")
        assert user.has_permission(Action.PUT_MESSAGE, "DEV.SERVICE.REQUEST")
        assert not user.has_permission(Action.PUT_MESSAGE, "DEV.APP.RESPONSE")
    
    def test_question_mark_wildcard(self):
        """Test single character wildcard."""
        user = UserPermissions(
            user_id="test_user",
            role=Role.READER,
            queue_permissions=[
                QueuePermission(
                    queue_pattern="Q?",
                    allowed_actions={Action.PUT_MESSAGE},
                    denied_actions=set()
                )
            ]
        )
        assert user.has_permission(Action.PUT_MESSAGE, "Q1")
        assert user.has_permission(Action.PUT_MESSAGE, "QA")
        assert not user.has_permission(Action.PUT_MESSAGE, "Q12")


class TestAuthorizationManager:
    """Test authorization manager."""
    
    def test_check_permission_existing_user(self):
        """Check permission for existing user."""
        users = [
            UserPermissions(user_id="user1", role=Role.WRITER),
            UserPermissions(user_id="user2", role=Role.READER),
        ]
        manager = AuthorizationManager(users)
        
        assert manager.check_permission("user1", Action.PUT_MESSAGE)
        assert not manager.check_permission("user2", Action.PUT_MESSAGE)
    
    def test_check_permission_nonexistent_user(self):
        """Check permission for non-existent user should return False."""
        manager = AuthorizationManager([])
        assert not manager.check_permission("unknown", Action.PUT_MESSAGE)
    
    def test_require_permission_success(self):
        """Require permission should not raise for authorized user."""
        users = [UserPermissions(user_id="user1", role=Role.ADMIN)]
        manager = AuthorizationManager(users)
        
        # Should not raise
        manager.require_permission("user1", Action.PUT_MESSAGE)
    
    def test_require_permission_failure(self):
        """Require permission should raise for unauthorized user."""
        users = [UserPermissions(user_id="user1", role=Role.READER)]
        manager = AuthorizationManager(users)
        
        with pytest.raises(PermissionError) as exc_info:
            manager.require_permission("user1", Action.PUT_MESSAGE)
        
        assert "does not have permission" in str(exc_info.value)
        assert "put_message" in str(exc_info.value)
    
    def test_get_user_role(self):
        """Get user role should return correct role."""
        users = [UserPermissions(user_id="user1", role=Role.WRITER)]
        manager = AuthorizationManager(users)
        
        assert manager.get_user_role("user1") == Role.WRITER
        assert manager.get_user_role("unknown") is None
    
    def test_add_user(self):
        """Add user should update permissions."""
        manager = AuthorizationManager([])
        
        user = UserPermissions(user_id="new_user", role=Role.ADMIN)
        manager.add_user(user)
        
        assert manager.check_permission("new_user", Action.PUT_MESSAGE)
    
    def test_remove_user(self):
        """Remove user should revoke permissions."""
        users = [UserPermissions(user_id="user1", role=Role.ADMIN)]
        manager = AuthorizationManager(users)
        
        manager.remove_user("user1")
        
        assert not manager.check_permission("user1", Action.PUT_MESSAGE)


class TestComplexScenarios:
    """Test complex authorization scenarios."""
    
    def test_restricted_admin(self):
        """Test admin with restrictions on sensitive queues."""
        user = UserPermissions(
            user_id="restricted_admin",
            role=Role.ADMIN,
            queue_permissions=[
                QueuePermission(
                    queue_pattern="SENSITIVE.*",
                    allowed_actions={Action.BROWSE_MESSAGE},
                    denied_actions={Action.PUT_MESSAGE, Action.GET_MESSAGE, Action.DELETE_MESSAGE}
                )
            ]
        )
        
        # Should have full access to normal queues
        assert user.has_permission(Action.PUT_MESSAGE, "NORMAL.QUEUE")
        assert user.has_permission(Action.GET_MESSAGE, "NORMAL.QUEUE")
        assert user.has_permission(Action.DELETE_MESSAGE, "NORMAL.QUEUE")
        
        # Should have restricted access to sensitive queues
        assert user.has_permission(Action.BROWSE_MESSAGE, "SENSITIVE.DATA")
        assert not user.has_permission(Action.PUT_MESSAGE, "SENSITIVE.DATA")
        assert not user.has_permission(Action.GET_MESSAGE, "SENSITIVE.DATA")
        assert not user.has_permission(Action.DELETE_MESSAGE, "SENSITIVE.DATA")
    
    def test_multiple_queue_patterns(self):
        """Test user with multiple queue-specific permissions."""
        user = UserPermissions(
            user_id="multi_user",
            role=Role.READER,
            queue_permissions=[
                QueuePermission(
                    queue_pattern="APP.OUTPUT.*",
                    allowed_actions={Action.PUT_MESSAGE},
                    denied_actions=set()
                ),
                QueuePermission(
                    queue_pattern="APP.READONLY.*",
                    allowed_actions=set(),
                    denied_actions={Action.GET_MESSAGE}
                )
            ]
        )
        
        # Can put to output queues
        assert user.has_permission(Action.PUT_MESSAGE, "APP.OUTPUT.QUEUE")
        
        # Can browse readonly queues but not get
        assert user.has_permission(Action.BROWSE_MESSAGE, "APP.READONLY.DATA")
        assert not user.has_permission(Action.GET_MESSAGE, "APP.READONLY.DATA")
        
        # Normal reader permissions on other queues
        assert user.has_permission(Action.GET_MESSAGE, "OTHER.QUEUE")
        assert not user.has_permission(Action.PUT_MESSAGE, "OTHER.QUEUE")