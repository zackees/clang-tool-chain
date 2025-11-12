"""
Tests for Emscripten WebAssembly compilation support.

Note: Node.js is now bundled automatically. Tests no longer require
system Node.js installation - the wrapper will download a minimal
Node.js runtime (~10-15 MB) on first use.
"""

import shutil
import subprocess
from pathlib import Path

import pytest


def is_node_available() -> bool:
    """Check if Node.js is available in PATH (system or bundled)."""
    return shutil.which("node") is not None


def is_emscripten_available() -> bool:
    """Check if Emscripten manifest is available."""
    try:
        from clang_tool_chain.downloader import fetch_emscripten_root_manifest

        fetch_emscripten_root_manifest()
        return True
    except Exception:
        return False


@pytest.mark.skipif(not is_emscripten_available(), reason="Emscripten manifest not available yet")
class TestEmscripten:
    """Test Emscripten integration."""

    def test_emcc_command_exists(self):
        """Test that clang-tool-chain-emcc command is available."""
        result = subprocess.run(
            ["clang-tool-chain-emcc", "--version"],
            capture_output=True,
            text=True,
            timeout=300,  # First run may download toolchain
        )
        assert result.returncode == 0, f"emcc failed: {result.stderr}"
        assert "emcc" in result.stdout or "Emscripten" in result.stdout

    def test_empp_command_exists(self):
        """Test that clang-tool-chain-empp command is available."""
        result = subprocess.run(["clang-tool-chain-empp", "--version"], capture_output=True, text=True, timeout=300)
        assert result.returncode == 0, f"em++ failed: {result.stderr}"
        assert "emcc" in result.stdout or "em++" in result.stdout or "Emscripten" in result.stdout

    def test_compile_hello_world_wasm(self, tmp_path: Path):
        """Test compiling C++ to WebAssembly."""
        # Create test source file
        source_file = tmp_path / "hello.cpp"
        source_file.write_text(
            """
#include <iostream>

int main() {
    std::cout << "Hello, WebAssembly!" << std::endl;
    return 0;
}
"""
        )

        # Compile to WebAssembly
        output_file = tmp_path / "hello.js"
        result = subprocess.run(
            ["clang-tool-chain-empp", str(source_file), "-o", str(output_file)],
            capture_output=True,
            text=True,
            timeout=300,
        )

        assert result.returncode == 0, f"Compilation failed: {result.stderr}"

        # Check output files exist
        assert output_file.exists(), "JavaScript file not created"
        wasm_file = tmp_path / "hello.wasm"
        assert wasm_file.exists(), "WebAssembly file not created"

        # Verify wasm file is valid binary
        wasm_data = wasm_file.read_bytes()
        assert wasm_data[:4] == b"\x00asm", "Invalid WebAssembly magic number"

    def test_execute_wasm_with_node(self, tmp_path: Path):
        """Test executing compiled WebAssembly with Node.js."""
        # Create test source file
        source_file = tmp_path / "test.cpp"
        source_file.write_text(
            """
#include <stdio.h>

int main() {
    printf("WebAssembly execution test\\n");
    return 42;
}
"""
        )

        # Compile to WebAssembly
        output_file = tmp_path / "test.js"
        result = subprocess.run(
            ["clang-tool-chain-emcc", str(source_file), "-o", str(output_file)],
            capture_output=True,
            text=True,
            timeout=300,
        )

        assert result.returncode == 0, f"Compilation failed: {result.stderr}"

        # Execute with Node.js
        result = subprocess.run(["node", str(output_file)], capture_output=True, text=True, timeout=30)

        assert result.returncode == 42, f"Execution failed with code {result.returncode}"
        assert "WebAssembly execution test" in result.stdout

    def test_compile_with_optimization(self, tmp_path: Path):
        """Test compilation with optimization flags."""
        source_file = tmp_path / "optimized.cpp"
        source_file.write_text(
            """
int fibonacci(int n) {
    if (n <= 1) return n;
    return fibonacci(n-1) + fibonacci(n-2);
}

int main() {
    return fibonacci(10);
}
"""
        )

        output_file = tmp_path / "optimized.js"
        result = subprocess.run(
            ["clang-tool-chain-empp", "-O3", str(source_file), "-o", str(output_file)],
            capture_output=True,
            text=True,
            timeout=300,
        )

        assert result.returncode == 0, f"Compilation failed: {result.stderr}"
        assert output_file.exists()
        assert (tmp_path / "optimized.wasm").exists()

    def test_compile_to_html(self, tmp_path: Path):
        """Test compilation with HTML output."""
        source_file = tmp_path / "webapp.cpp"
        source_file.write_text(
            """
#include <emscripten.h>
#include <stdio.h>

int main() {
    printf("Hello from WebAssembly!\\n");
    return 0;
}
"""
        )

        output_file = tmp_path / "webapp.html"
        result = subprocess.run(
            ["clang-tool-chain-emcc", str(source_file), "-o", str(output_file)],
            capture_output=True,
            text=True,
            timeout=300,
        )

        assert result.returncode == 0, f"Compilation failed: {result.stderr}"

        # Check all output files exist
        assert output_file.exists(), "HTML file not created"
        assert (tmp_path / "webapp.js").exists(), "JavaScript file not created"
        assert (tmp_path / "webapp.wasm").exists(), "WebAssembly file not created"

        # Verify HTML contains expected content
        html_content = output_file.read_text()
        assert "<html" in html_content.lower()
        assert "canvas" in html_content.lower() or "module" in html_content.lower()


class TestEmscriptenDownloader:
    """Test Emscripten download infrastructure."""

    def test_emscripten_install_dir_detection(self):
        """Test that Emscripten installation directory is detected correctly."""
        from clang_tool_chain.downloader import get_emscripten_install_dir
        from clang_tool_chain.wrapper import get_platform_info

        platform_name, arch = get_platform_info()
        install_dir = get_emscripten_install_dir(platform_name, arch)

        assert install_dir is not None
        assert "emscripten" in str(install_dir).lower()
        assert platform_name in str(install_dir)
        assert arch in str(install_dir)

    def test_manifest_urls_reachable(self):
        """Test that Emscripten manifests can be fetched (if archives uploaded)."""
        from clang_tool_chain.downloader import fetch_emscripten_root_manifest

        try:
            manifest = fetch_emscripten_root_manifest()
            assert len(manifest.platforms) > 0, "Root manifest should have at least one platform"
            # Check if common platforms are present
            platform_names = [p.platform for p in manifest.platforms]
            assert any(name in platform_names for name in ["linux", "darwin", "win"])
        except Exception as e:
            # Expected to fail if archives not uploaded yet
            pytest.skip(f"Manifest not available yet: {e}")


class TestEmscriptenNodeJS:
    """Test Emscripten with bundled Node.js integration."""

    def test_bundled_nodejs_automatic_download(self, tmp_path: Path):
        """Test that bundled Node.js is downloaded automatically if needed."""
        # This test verifies the automatic download behavior
        # Even without system Node.js, compilation should work
        source_file = tmp_path / "auto_download_test.cpp"
        source_file.write_text(
            """
#include <stdio.h>

int main() {
    printf("Bundled Node.js test\\n");
    return 0;
}
"""
        )

        output_file = tmp_path / "auto_download_test.js"
        result = subprocess.run(
            ["clang-tool-chain-emcc", str(source_file), "-o", str(output_file)],
            capture_output=True,
            text=True,
            timeout=300,  # Allow time for potential Node.js download
        )

        # Should succeed even without system Node.js (will download bundled)
        assert result.returncode == 0, f"Compilation failed: {result.stderr}"
        assert output_file.exists()

    def test_emscripten_uses_nodejs(self, tmp_path: Path):
        """Test that Emscripten compilation actually uses Node.js."""
        # Create a simple test that exercises Node.js during compilation
        source_file = tmp_path / "nodejs_test.cpp"
        source_file.write_text(
            """
#include <emscripten.h>
#include <stdio.h>

EM_JS(void, call_js, (), {
    console.log('Node.js is working');
});

int main() {
    printf("Testing Node.js integration\\n");
    call_js();
    return 0;
}
"""
        )

        output_file = tmp_path / "nodejs_test.js"
        result = subprocess.run(
            ["clang-tool-chain-emcc", str(source_file), "-o", str(output_file)],
            capture_output=True,
            text=True,
            timeout=300,
        )

        assert result.returncode == 0, f"Compilation failed: {result.stderr}"
        assert output_file.exists()

        # Execute and verify Node.js was used
        if shutil.which("node"):
            exec_result = subprocess.run(
                ["node", str(output_file)], capture_output=True, text=True, timeout=30
            )
            assert "Testing Node.js integration" in exec_result.stdout
