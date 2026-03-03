"""Prompt loading system for SHAKODS.

All prompts are stored as markdown files in the prompts/ directory
and loaded dynamically by the PromptLoader class.
"""

from __future__ import annotations

import string
from enum import StrEnum, auto
from pathlib import Path
from typing import Any

# Default prompts directory: project root / prompts (can be overridden)
DEFAULT_PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"


class PromptCategory(StrEnum):
    """Categories of prompts."""
    
    ORCHESTRATOR = auto()
    SPECIALIZED = auto()
    JUDGES = auto()
    SYSTEM = auto()


class PromptLoader:
    """Load and render prompts from markdown files.
    
    Prompts are organized by category in subdirectories:
    - prompts/orchestrator/ - REACT orchestrator prompts
    - prompts/specialized/ - Agent-specific prompts
    - prompts/judges/ - Judge evaluation prompts
    - prompts/system/ - System/mode prompts
    
    Example:
        loader = PromptLoader()
        
        # Load with variable substitution
        prompt = loader.load(
            "orchestrator/react_system",
            runtime_context="Current phase: REASONING",
            active_tasks="[]"
        )
        
        # Load without substitution
        raw_prompt = loader.load_raw("judges/task_completion")
    """
    
    def __init__(self, prompts_dir: Path | None = None):
        """Initialize prompt loader.
        
        Args:
            prompts_dir: Directory containing prompt files.
                        Defaults to prompts/ directory.
        """
        self.prompts_dir = prompts_dir or DEFAULT_PROMPTS_DIR
        self._cache: dict[str, str] = {}
        self._use_cache = True
    
    def load(self, path: str, use_cache: bool | None = None, **variables) -> str:
        """Load a prompt file and substitute variables.
        
        Args:
            path: Relative path under prompts/ (e.g., "orchestrator/react_system")
            use_cache: Whether to use caching (None = use default)
            **variables: Template variables to substitute
            
        Returns:
            The rendered prompt text
            
        Raises:
            FileNotFoundError: If prompt file not found
            ValueError: If path is invalid
        """
        cache_key = f"{path}:{hash(str(sorted(variables.items())))}"
        use_cache = self._use_cache if use_cache is None else use_cache
        
        if use_cache and cache_key in self._cache:
            return self._cache[cache_key]
        
        # Resolve path
        file_path = self._resolve_path(path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"Prompt not found: {file_path} (path: {path})")
        
        # Read template
        template = file_path.read_text(encoding="utf-8")
        
        # Substitute variables
        if variables:
            result = self._substitute(template, variables)
        else:
            result = template
        
        if use_cache:
            self._cache[cache_key] = result
        
        return result
    
    def load_raw(self, path: str) -> str:
        """Load a prompt file without variable substitution.
        
        Args:
            path: Relative path under prompts/
            
        Returns:
            The raw prompt text
        """
        return self.load(path, use_cache=False)
    
    def load_for_phase(
        self,
        phase: str,
        base_prompt: str = "orchestrator/react_system",
        **context,
    ) -> str:
        """Load orchestrator prompt for a specific REACT phase.
        
        Args:
            phase: REACT phase (reasoning, evaluation, acting, communicating, tracking)
            base_prompt: Base system prompt path
            **context: Additional context variables
            
        Returns:
            Combined prompt for the phase
        """
        # Load base prompt
        base = self.load(base_prompt, **context)
        
        # Load phase-specific guidance
        phase_path = f"orchestrator/phases/{phase}"
        try:
            phase_guidance = self.load_raw(phase_path)
        except FileNotFoundError:
            phase_guidance = f"# {phase.upper()} Phase\n\nProceed with {phase} phase."
        
        return f"{base}\n\n{phase_guidance}"
    
    def list_prompts(self, category: PromptCategory | None = None) -> list[str]:
        """List available prompts.
        
        Args:
            category: Optional category to filter by
            
        Returns:
            List of prompt paths (relative to prompts/)
        """
        prompts = []
        
        if category:
            search_dir = self.prompts_dir / category.value
        else:
            search_dir = self.prompts_dir
        
        for md_file in search_dir.rglob("*.md"):
            # Get relative path
            rel_path = md_file.relative_to(self.prompts_dir)
            # Remove extension
            path_str = str(rel_path.with_suffix(""))
            prompts.append(path_str)
        
        return sorted(prompts)
    
    def exists(self, path: str) -> bool:
        """Check if a prompt exists.
        
        Args:
            path: Prompt path to check
            
        Returns:
            True if prompt exists
        """
        try:
            file_path = self._resolve_path(path)
            return file_path.exists()
        except ValueError:
            return False
    
    def clear_cache(self) -> None:
        """Clear the prompt cache."""
        self._cache.clear()
    
    def set_cache_enabled(self, enabled: bool) -> None:
        """Enable or disable caching."""
        self._use_cache = enabled
        if not enabled:
            self.clear_cache()
    
    def _resolve_path(self, path: str) -> Path:
        """Resolve a prompt path to a file path.
        
        Args:
            path: Relative path (e.g., "orchestrator/react_system")
            
        Returns:
            Absolute Path to the markdown file
        """
        # Normalize path
        path = path.strip("/")
        
        # Check for invalid characters
        if ".." in path:
            raise ValueError(f"Invalid path (contains ..): {path}")
        
        # Add .md extension if not present
        if not path.endswith(".md"):
            path += ".md"
        
        return self.prompts_dir / path
    
    def _substitute(self, template: str, variables: dict[str, Any]) -> str:
        """Substitute variables into template.
        
        Uses Python's string.Template for safe substitution.
        Missing variables are left as-is (template syntax preserved).
        """
        # Convert variables to strings
        str_vars = {k: str(v) for k, v in variables.items()}
        
        # Use Template for safe substitution
        tmpl = string.Template(template)
        return tmpl.safe_substitute(str_vars)


# Convenience functions
def load_prompt(path: str, **variables) -> str:
    """Load a prompt with default loader."""
    loader = PromptLoader()
    return loader.load(path, **variables)


def get_orchestrator_prompt(phase: str, **context) -> str:
    """Get orchestrator prompt for a phase."""
    loader = PromptLoader()
    return loader.load_for_phase(phase, **context)


__all__ = [
    "PromptCategory",
    "PromptLoader",
    "DEFAULT_PROMPTS_DIR",
    "load_prompt",
    "get_orchestrator_prompt",
]
