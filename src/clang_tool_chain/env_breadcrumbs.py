"""
Environment breadcrumb tracking module.

This is a compatibility wrapper around the component_db module.
All tracking is now done via SQLite database.

Kept for backward compatibility with existing code.
"""

from clang_tool_chain import component_db


def mark_component_installed(component: str, install_path: str | None = None) -> None:
    """
    Mark a component as installed (files downloaded).

    Args:
        component: Component name (e.g., "clang", "iwyu", "emscripten")
        install_path: Path to the installation directory (optional)
    """
    component_db.mark_component_installed(component, install_path)


def mark_component_installed_to_env(component: str, bin_path: str) -> None:
    """
    Mark a component as installed to the environment PATH.

    Args:
        component: Component name (e.g., "clang", "iwyu", "emscripten")
        bin_path: Path to the bin directory that was added to PATH
    """
    component_db.mark_component_in_path(component, bin_path)


def unmark_component_installed_to_env(component: str) -> None:
    """
    Remove PATH installation flag from a component.

    Args:
        component: Component name (e.g., "clang", "iwyu", "emscripten")
    """
    component_db.unmark_component_from_path(component)


def is_component_installed_to_env(component: str) -> bool:
    """
    Check if a component is currently installed to the environment PATH.

    Args:
        component: Component name (e.g., "clang", "iwyu", "emscripten")

    Returns:
        True if component is installed to PATH, False otherwise
    """
    return component_db.is_component_in_path(component)


def get_component_bin_path(component: str) -> str | None:
    """
    Get the bin path for a component installed to environment.

    Args:
        component: Component name (e.g., "clang", "iwyu", "emscripten")

    Returns:
        Path to the bin directory, or None if not installed to env
    """
    info = component_db.get_component_info(component)
    if info and info.in_path:
        return info.path_bin_dir
    return None


def get_all_env_installed_components() -> list[tuple[str, str]]:
    """
    Get all components currently installed to the environment PATH.

    Returns:
        List of (component_name, bin_path) tuples
    """
    return component_db.get_all_path_components()
