"""
Component tracking database module.

Uses SQLite to track which toolchain components are installed and whether they're in PATH.
This allows automatic cleanup when purging the toolchain.

Database location: ~/.clang-tool-chain/components.db
"""

import datetime
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from clang_tool_chain.path_utils import get_home_toolchain_dir


@dataclass
class ComponentInfo:
    """
    Information about an installed toolchain component.

    Attributes:
        id: Database primary key
        name: Component name (e.g., "clang", "iwyu", "emscripten")
        installed: Whether component files are downloaded/installed
        install_path: Installation directory path (None if not installed)
        installed_at: ISO 8601 timestamp of installation
        in_path: Whether component binaries are in system PATH
        path_bin_dir: PATH directory for this component
        path_installed_at: ISO 8601 timestamp of PATH installation
        version: Component version string
    """

    id: int
    name: str
    installed: bool
    install_path: str | None = None
    installed_at: str | None = None
    in_path: bool = False
    path_bin_dir: str | None = None
    path_installed_at: str | None = None
    version: str = "1.0"

    @classmethod
    def from_db_row(cls, row: sqlite3.Row) -> "ComponentInfo":
        """Create ComponentInfo from SQLite Row."""
        # Handle optional version field (may not exist in older databases)
        try:
            version = row["version"]
        except (KeyError, IndexError):
            version = "1.0"

        return cls(
            id=row["id"],
            name=row["name"],
            installed=bool(row["installed"]),
            install_path=row["install_path"],
            installed_at=row["installed_at"],
            in_path=bool(row["in_path"]),
            path_bin_dir=row["path_bin_dir"],
            path_installed_at=row["path_installed_at"],
            version=version,
        )


def get_db_path() -> Path:
    """
    Get the path to the SQLite database.

    Returns:
        Path to ~/.clang-tool-chain/components.db
    """
    toolchain_dir = get_home_toolchain_dir()
    toolchain_dir.mkdir(parents=True, exist_ok=True)
    return toolchain_dir / "components.db"


def get_connection() -> sqlite3.Connection:
    """
    Get a database connection and ensure schema is initialized.

    Returns:
        SQLite connection
    """
    db_path = get_db_path()
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row  # Enable dict-like access to rows
    init_db(conn)
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """
    Initialize the database schema if it doesn't exist.

    Args:
        conn: SQLite connection
    """
    cursor = conn.cursor()

    # Create components table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS components (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            installed BOOLEAN NOT NULL DEFAULT 0,
            install_path TEXT,
            installed_at TIMESTAMP,
            in_path BOOLEAN NOT NULL DEFAULT 0,
            path_bin_dir TEXT,
            path_installed_at TIMESTAMP,
            version TEXT DEFAULT '1.0'
        )
        """
    )

    # Create indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_component_name ON components(name)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_installed ON components(installed)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_in_path ON components(in_path)")

    conn.commit()


def mark_component_installed(name: str, install_path: str | None = None) -> None:
    """
    Mark a component as installed (files downloaded).

    Args:
        name: Component name (e.g., "clang", "iwyu", "emscripten")
        install_path: Path to the installation directory (optional)
    """
    conn = get_connection()
    cursor = conn.cursor()

    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # Try to update existing record
    cursor.execute(
        """
        UPDATE components
        SET installed = 1,
            install_path = COALESCE(?, install_path),
            installed_at = COALESCE(installed_at, ?)
        WHERE name = ?
        """,
        (install_path, now, name),
    )

    # If no row was updated, insert new record
    if cursor.rowcount == 0:
        cursor.execute(
            """
            INSERT INTO components (name, installed, install_path, installed_at, version)
            VALUES (?, 1, ?, ?, '1.0')
            """,
            (name, install_path, now),
        )

    conn.commit()
    conn.close()


def mark_component_in_path(name: str, bin_path: str) -> None:
    """
    Mark a component as installed to the environment PATH.

    Args:
        name: Component name (e.g., "clang", "iwyu", "emscripten")
        bin_path: Path to the bin directory that was added to PATH
    """
    conn = get_connection()
    cursor = conn.cursor()

    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # Try to update existing record
    cursor.execute(
        """
        UPDATE components
        SET installed = 1,
            in_path = 1,
            path_bin_dir = ?,
            path_installed_at = ?
        WHERE name = ?
        """,
        (bin_path, now, name),
    )

    # If no row was updated, insert new record
    if cursor.rowcount == 0:
        cursor.execute(
            """
            INSERT INTO components (name, installed, in_path, path_bin_dir, path_installed_at, version)
            VALUES (?, 1, 1, ?, ?, '1.0')
            """,
            (name, bin_path, now),
        )

    conn.commit()
    conn.close()


def unmark_component_from_path(name: str) -> None:
    """
    Remove PATH installation flag from a component.

    The component itself is still installed (files on disk).

    Args:
        name: Component name (e.g., "clang", "iwyu", "emscripten")
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE components
        SET in_path = 0,
            path_bin_dir = NULL,
            path_installed_at = NULL
        WHERE name = ?
        """,
        (name,),
    )

    conn.commit()
    conn.close()


def get_component_info(name: str) -> ComponentInfo | None:
    """
    Get information about a specific component.

    Args:
        name: Component name (e.g., "clang", "iwyu", "emscripten")

    Returns:
        ComponentInfo object, or None if not found
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM components WHERE name = ?", (name,))
    row = cursor.fetchone()
    conn.close()

    if row:
        return ComponentInfo.from_db_row(row)
    return None


def is_component_installed(name: str) -> bool:
    """
    Check if a component is installed.

    Args:
        name: Component name (e.g., "clang", "iwyu", "emscripten")

    Returns:
        True if component is installed, False otherwise
    """
    info = get_component_info(name)
    return info is not None and info.installed


def is_component_in_path(name: str) -> bool:
    """
    Check if a component is currently in PATH.

    Args:
        name: Component name (e.g., "clang", "iwyu", "emscripten")

    Returns:
        True if component is in PATH, False otherwise
    """
    info = get_component_info(name)
    return info is not None and info.in_path


def get_all_installed_components() -> list[ComponentInfo]:
    """
    Get all installed components.

    Returns:
        List of ComponentInfo objects
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM components WHERE installed = 1 ORDER BY name")
    rows = cursor.fetchall()
    conn.close()

    return [ComponentInfo.from_db_row(row) for row in rows]


def get_all_path_components() -> list[tuple[str, str]]:
    """
    Get all components currently in PATH.

    Returns:
        List of (component_name, bin_path) tuples
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT name, path_bin_dir
        FROM components
        WHERE in_path = 1 AND path_bin_dir IS NOT NULL
        ORDER BY name
        """
    )
    rows = cursor.fetchall()
    conn.close()

    return [(row["name"], row["path_bin_dir"]) for row in rows]


def remove_all_components() -> None:
    """
    Remove all component records from the database.

    Used when purging the toolchain.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM components")
    conn.commit()
    conn.close()


def remove_component(name: str) -> None:
    """
    Remove a specific component from the database.

    Args:
        name: Component name (e.g., "clang", "iwyu", "emscripten")
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM components WHERE name = ?", (name,))
    conn.commit()
    conn.close()
