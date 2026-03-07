"""Tests for tmux skill scripts."""

import pytest
import subprocess
import os
import tempfile
import time
from pathlib import Path

# Get script paths
SKILL_DIR = Path(__file__).parent.parent / "nanobot" / "skills" / "tmux" / "scripts"
FIND_SESSIONS_SCRIPT = SKILL_DIR / "find-sessions.sh"
WAIT_FOR_TEXT_SCRIPT = SKILL_DIR / "wait-for-text.sh"


@pytest.fixture
def tmux_available():
    """Check if tmux is available."""
    result = subprocess.run(
        ["which", "tmux"],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        pytest.skip("tmux not available")


@pytest.fixture
def temp_socket_dir(tmp_path):
    """Create a temporary socket directory."""
    socket_dir = tmp_path / "tmux_sockets"
    socket_dir.mkdir()
    return socket_dir


class TestFindSessionsScript:
    """Tests for find-sessions.sh script."""

    def test_script_exists(self):
        """Test that the script exists and is executable."""
        assert FIND_SESSIONS_SCRIPT.exists()
        # Check if script has shebang
        content = FIND_SESSIONS_SCRIPT.read_text()
        assert content.startswith("#!/usr/bin/env bash")

    def test_help_flag(self):
        """Test --help flag."""
        result = subprocess.run(
            ["bash", str(FIND_SESSIONS_SCRIPT), "--help"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        assert "Usage:" in result.stdout
        assert "find-sessions.sh" in result.stdout

    def test_invalid_option(self):
        """Test invalid option handling."""
        result = subprocess.run(
            ["bash", str(FIND_SESSIONS_SCRIPT), "--invalid-option"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 1
        assert "Unknown option" in result.stderr

    def test_cannot_combine_all_with_socket(self):
        """Test that --all cannot be combined with -L or -S."""
        result = subprocess.run(
            ["bash", str(FIND_SESSIONS_SCRIPT), "--all", "-L", "test"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 1
        assert "Cannot combine" in result.stderr

    def test_cannot_use_both_socket_options(self):
        """Test that -L and -S cannot be used together."""
        result = subprocess.run(
            ["bash", str(FIND_SESSIONS_SCRIPT), "-L", "test", "-S", "/tmp/test"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 1
        assert "Use either -L or -S" in result.stderr

    @pytest.mark.skipif(
        subprocess.run(["which", "tmux"], capture_output=True).returncode != 0,
        reason="tmux not available"
    )
    def test_no_tmux_server(self):
        """Test behavior when no tmux server exists."""
        # Use a non-existent socket to ensure no server
        result = subprocess.run(
            ["bash", str(FIND_SESSIONS_SCRIPT), "-L", "nonexistent_test_socket_12345"],
            capture_output=True,
            text=True
        )
        # Should report no server found
        assert result.returncode == 1 or "No tmux server found" in result.stderr

    @pytest.mark.skipif(
        subprocess.run(["which", "tmux"], capture_output=True).returncode != 0,
        reason="tmux not available"
    )
    def test_list_sessions_with_mock(self, tmux_available, temp_socket_dir):
        """Test listing sessions with actual tmux."""
        socket_name = "test_find_sessions"
        session_name = "test_session"

        try:
            # Create a tmux session
            subprocess.run(
                ["tmux", "-L", socket_name, "new-session", "-d", "-s", session_name],
                check=True,
                capture_output=True
            )

            # List sessions
            result = subprocess.run(
                ["bash", str(FIND_SESSIONS_SCRIPT), "-L", socket_name],
                capture_output=True,
                text=True
            )

            assert result.returncode == 0
            assert session_name in result.stdout
            assert "detached" in result.stdout

        finally:
            # Cleanup
            subprocess.run(
                ["tmux", "-L", socket_name, "kill-server"],
                capture_output=True
            )

    @pytest.mark.skipif(
        subprocess.run(["which", "tmux"], capture_output=True).returncode != 0,
        reason="tmux not available"
    )
    def test_query_filter(self, tmux_available, temp_socket_dir):
        """Test query filter functionality."""
        socket_name = "test_query_filter"

        try:
            # Create multiple sessions
            subprocess.run(
                ["tmux", "-L", socket_name, "new-session", "-d", "-s", "alpha_session"],
                check=True,
                capture_output=True
            )
            subprocess.run(
                ["tmux", "-L", socket_name, "new-session", "-d", "-s", "beta_session"],
                check=True,
                capture_output=True
            )

            # Query for alpha only
            result = subprocess.run(
                ["bash", str(FIND_SESSIONS_SCRIPT), "-L", socket_name, "-q", "alpha"],
                capture_output=True,
                text=True
            )

            assert result.returncode == 0
            assert "alpha_session" in result.stdout
            assert "beta_session" not in result.stdout

        finally:
            # Cleanup
            subprocess.run(
                ["tmux", "-L", socket_name, "kill-server"],
                capture_output=True
            )


class TestWaitForTextScript:
    """Tests for wait-for-text.sh script."""

    def test_script_exists(self):
        """Test that the script exists and is executable."""
        assert WAIT_FOR_TEXT_SCRIPT.exists()
        # Check if script has shebang
        content = WAIT_FOR_TEXT_SCRIPT.read_text()
        assert content.startswith("#!/usr/bin/env bash")

    def test_help_flag(self):
        """Test --help flag."""
        result = subprocess.run(
            ["bash", str(WAIT_FOR_TEXT_SCRIPT), "--help"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        assert "Usage:" in result.stdout
        assert "wait-for-text.sh" in result.stdout

    def test_missing_required_args(self):
        """Test that missing required arguments causes error."""
        # Missing target
        result = subprocess.run(
            ["bash", str(WAIT_FOR_TEXT_SCRIPT), "-p", "pattern"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 1
        assert "target and pattern are required" in result.stderr

        # Missing pattern
        result = subprocess.run(
            ["bash", str(WAIT_FOR_TEXT_SCRIPT), "-t", "target"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 1
        assert "target and pattern are required" in result.stderr

    def test_invalid_timeout(self):
        """Test that invalid timeout value is rejected."""
        result = subprocess.run(
            ["bash", str(WAIT_FOR_TEXT_SCRIPT), "-t", "target", "-p", "pattern", "-T", "abc"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 1
        assert "timeout must be an integer" in result.stderr

    def test_invalid_lines(self):
        """Test that invalid lines value is rejected."""
        result = subprocess.run(
            ["bash", str(WAIT_FOR_TEXT_SCRIPT), "-t", "target", "-p", "pattern", "-l", "abc"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 1
        assert "lines must be an integer" in result.stderr


    @pytest.mark.skipif(
        subprocess.run(["which", "tmux"], capture_output=True).returncode != 0,
        reason="tmux not available"
    )
    def test_wait_for_text_timeout(self, tmux_available):
        """Test timeout when text is not found."""
        socket_name = "test_wait_timeout"
        session_name = "wait_timeout_test"
        pane_target = f"{session_name}:0.0"

        try:
            # Create a tmux session
            subprocess.run(
                ["tmux", "-L", socket_name, "new-session", "-d", "-s", session_name],
                check=True,
                capture_output=True
            )

            # Wait for text that doesn't exist (short timeout)
            result = subprocess.run(
                ["bash", str(WAIT_FOR_TEXT_SCRIPT), "-t", pane_target, "-p", "NONEXISTENT_TEXT_12345", "-T", "1", "-i", "0.1"],
                capture_output=True,
                text=True
            )

            assert result.returncode == 1
            assert "Timed out" in result.stderr

        finally:
            # Cleanup
            subprocess.run(
                ["tmux", "-L", socket_name, "kill-server"],
                capture_output=True
            )



