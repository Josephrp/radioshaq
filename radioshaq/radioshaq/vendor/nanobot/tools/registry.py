"""Tool registry for dynamic tool management (vendored from nanobot).

Provides a registry for managing agent tools with dynamic registration,
execution, and schema generation for LLM function calling.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from loguru import logger


@runtime_checkable
class Tool(Protocol):
    """Protocol defining the interface for agent tools."""
    
    name: str
    description: str
    
    def to_schema(self) -> dict[str, Any]:
        """Return the tool's JSON schema for LLM function calling."""
        ...
    
    def validate_params(self, params: dict[str, Any]) -> list[str]:
        """Validate parameters. Returns list of error messages (empty if valid)."""
        ...
    
    async def execute(self, **kwargs: Any) -> str:
        """Execute the tool with given parameters."""
        ...


class ToolRegistry:
    """Registry for managing agent tools.
    
    Allows dynamic registration and execution of tools. Tools can be
    registered at runtime and their schemas are automatically generated
    for LLM function calling.
    
    Example:
        registry = ToolRegistry()
        
        # Register a tool
        registry.register(MyTool())
        
        # Get tool definitions for LLM
        schemas = registry.get_definitions()
        
        # Execute a tool
        result = await registry.execute("tool_name", {"param": "value"})
    """
    
    def __init__(self):
        self._tools: dict[str, Tool] = {}
        self._execution_count: dict[str, int] = {}
    
    def register(self, tool: Tool) -> None:
        """Register a tool.
        
        Args:
            tool: Tool instance implementing the Tool protocol
            
        Raises:
            ValueError: If tool with same name already registered
        """
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' is already registered")
        
        self._tools[tool.name] = tool
        self._execution_count[tool.name] = 0
        logger.debug(f"Registered tool: {tool.name}")
    
    def unregister(self, name: str) -> Tool | None:
        """Unregister a tool by name.
        
        Args:
            name: Name of the tool to unregister
            
        Returns:
            The unregistered tool, or None if not found
        """
        tool = self._tools.pop(name, None)
        if tool:
            self._execution_count.pop(name, None)
            logger.debug(f"Unregistered tool: {name}")
        return tool
    
    def get(self, name: str) -> Tool | None:
        """Get a tool by name.
        
        Args:
            name: Tool name
            
        Returns:
            The tool instance, or None if not found
        """
        return self._tools.get(name)
    
    def has(self, name: str) -> bool:
        """Check if a tool is registered.
        
        Args:
            name: Tool name to check
            
        Returns:
            True if tool is registered
        """
        return name in self._tools
    
    def get_definitions(self) -> list[dict[str, Any]]:
        """Get all tool definitions in OpenAI function format.
        
        Returns:
            List of tool schemas for LLM function calling
        """
        return [tool.to_schema() for tool in self._tools.values()]
    
    async def execute(self, name: str, params: dict[str, Any]) -> str:
        """Execute a tool by name with given parameters.
        
        Args:
            name: Tool name to execute
            params: Parameters to pass to the tool
            
        Returns:
            Tool execution result as string
            
        Raises:
            ToolNotFoundError: If tool not found
            ToolValidationError: If parameters invalid
            ToolExecutionError: If execution fails
        """
        _HINT = "\n\n[Analyze the error above and try a different approach.]"

        tool = self._tools.get(name)
        if not tool:
            available = ", ".join(self.tool_names)
            return f"Error: Tool '{name}' not found. Available: {available}"

        try:
            # Validate parameters
            errors = tool.validate_params(params)
            if errors:
                error_msg = f"Error: Invalid parameters for tool '{name}': " + "; ".join(errors)
                return error_msg + _HINT

            # Execute tool
            logger.info(f"Executing tool: {name} with params: {params}")
            result = await tool.execute(**params)
            
            # Track execution
            self._execution_count[name] += 1
            
            if isinstance(result, str) and result.startswith("Error"):
                return result + _HINT
            return result
            
        except Exception as e:
            error_msg = f"Error executing {name}: {str(e)}"
            logger.exception(f"Tool execution failed: {name}")
            return error_msg + _HINT
    
    @property
    def tool_names(self) -> list[str]:
        """Get list of registered tool names."""
        return list(self._tools.keys())
    
    @property
    def tool_count(self) -> int:
        """Get number of registered tools."""
        return len(self._tools)
    
    def get_stats(self) -> dict[str, Any]:
        """Get tool execution statistics."""
        return {
            "registered_tools": self.tool_names,
            "execution_counts": self._execution_count,
            "total_executions": sum(self._execution_count.values()),
        }
    
    def __len__(self) -> int:
        return len(self._tools)
    
    def __contains__(self, name: str) -> bool:
        return name in self._tools
    
    def __iter__(self):
        return iter(self._tools.values())


class ToolNotFoundError(Exception):
    """Raised when a requested tool is not found."""
    pass


class ToolValidationError(Exception):
    """Raised when tool parameters are invalid."""
    pass


class ToolExecutionError(Exception):
    """Raised when tool execution fails."""
    pass
