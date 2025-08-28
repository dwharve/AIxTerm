"""
Lifecycle management utilities for AIxTerm components.

This module provides protocols and utilities for unified shutdown handling
across components, eliminating duplicated guard logic and logging patterns.
"""

import logging
from typing import Any, Iterable, Protocol, runtime_checkable


@runtime_checkable
class IShutdownCapable(Protocol):
    """
    Protocol for components that support shutdown operations.
    
    This protocol defines the interface for components that need
    to clean up resources during application shutdown.
    """

    def shutdown(self) -> None:
        """
        Shutdown the component and clean up resources.
        
        Implementations should be idempotent - calling shutdown multiple
        times should be safe and not cause errors.
        """
        ...


class LifecycleManager:
    """
    Utility class for managing component lifecycle operations.
    
    Provides unified shutdown handling with consistent logging and
    error handling patterns.
    """

    def __init__(self, logger: logging.Logger | None = None):
        """
        Initialize lifecycle manager.
        
        Args:
            logger: Logger instance, defaults to module logger
        """
        self.logger = logger or logging.getLogger(__name__)

    def shutdown_component(self, component: Any, component_name: str | None = None) -> bool:
        """
        Shutdown a single component with consistent error handling.
        
        Args:
            component: Component to shutdown
            component_name: Optional component name for logging
            
        Returns:
            True if shutdown successful, False if error occurred
        """
        if component is None:
            return True
            
        name = component_name or getattr(component, '__class__', type('')).__name__
        
        try:
            # Try shutdown() first, then stop() for different component types
            if hasattr(component, 'shutdown'):
                self.logger.debug(f"Shutting down {name}")
                component.shutdown()
                self.logger.debug(f"Successfully shut down {name}")
                return True
            elif hasattr(component, 'stop'):
                self.logger.debug(f"Stopping {name}")
                component.stop()
                self.logger.debug(f"Successfully stopped {name}")
                return True
            else:
                self.logger.debug(f"Component {name} has no shutdown/stop method")
                return True
        except Exception as e:
            self.logger.error(f"Error shutting down {name}: {e}")
            return False

    def shutdown_all(self, components: Iterable[Any], component_names: Iterable[str] | None = None) -> bool:
        """
        Shutdown multiple components in sequence.
        
        Args:
            components: Iterable of components to shutdown
            component_names: Optional names for logging (must match components order)
            
        Returns:
            True if all shutdowns successful, False if any failed
        """
        success = True
        names = list(component_names) if component_names else None
        
        for i, component in enumerate(components):
            name = names[i] if names and i < len(names) else None
            if not self.shutdown_component(component, name):
                success = False
                
        return success

    def shutdown_registry(self, registry: dict[str, Any], registry_name: str = "registry") -> bool:
        """
        Shutdown all components in a registry (dict mapping names to components).
        
        Args:
            registry: Dictionary of name -> component mappings
            registry_name: Name of the registry for logging
            
        Returns:
            True if all shutdowns successful, False if any failed
        """
        if not registry:
            return True
            
        self.logger.debug(f"Shutting down {registry_name} with {len(registry)} components")
        success = True
        
        for name, component in registry.items():
            if not self.shutdown_component(component, f"{registry_name}.{name}"):
                success = False
                
        return success


# Convenience functions for common patterns
def shutdown_all(*components: Any, logger: logging.Logger | None = None) -> bool:
    """
    Convenience function to shutdown multiple components.
    
    Args:
        *components: Components to shutdown
        logger: Optional logger for output
        
    Returns:
        True if all shutdowns successful, False if any failed
    """
    manager = LifecycleManager(logger)
    return manager.shutdown_all(components)


def shutdown_if_exists(component: Any, component_name: str | None = None, 
                      logger: logging.Logger | None = None) -> bool:
    """
    Convenience function to shutdown a component if it exists.
    
    Args:
        component: Component to shutdown (can be None)
        component_name: Optional component name for logging
        logger: Optional logger for output
        
    Returns:
        True if shutdown successful or component was None, False if error occurred
    """
    manager = LifecycleManager(logger)
    return manager.shutdown_component(component, component_name)