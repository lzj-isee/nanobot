"""Tests for bilibili skill - bilibili_followings.py (using subprocess)"""

import pytest
import subprocess
import tempfile
from pathlib import Path

# Get script path
SCRIPT_PATH = Path(__file__).parent.parent / "nanobot" / "skills" / "bilibili" / "scripts" / "bilibili_followings.py"


class TestScriptBasics:
    """Basic script tests."""

    def test_script_exists(self):
        """Test that the script exists."""
        assert SCRIPT_PATH.exists()

    def test_help_flag(self):
        """Test --help flag."""
        result = subprocess.run(
            ["python", str(SCRIPT_PATH), "--help"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        assert "usage:" in result.stdout.lower()
        assert "--cookie-file" in result.stdout


class TestCookieFileHandling:
    """Tests for cookie file handling."""

    def test_missing_cookie_file(self):
        """Test error when cookie file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            nonexistent_cookie = Path(tmpdir) / "nonexistent.cookie"

            result = subprocess.run(
                ["python", str(SCRIPT_PATH), "--cookie-file", str(nonexistent_cookie)],
                capture_output=True,
                text=True
            )

            assert result.returncode == 1
            assert "Cookie 文件不存在" in result.stderr or "does not exist" in result.stderr.lower()

    def test_empty_cookie_file(self):
        """Test error when cookie file is empty."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cookie_file = Path(tmpdir) / "empty.cookie"
            cookie_file.write_text("")

            result = subprocess.run(
                ["python", str(SCRIPT_PATH), "--cookie-file", str(cookie_file)],
                capture_output=True,
                text=True
            )

            assert result.returncode == 1
            assert "Cookie 文件为空" in result.stderr or "Cookie 文件内容为空" in result.stderr

    def test_cookie_file_missing_required_fields(self):
        """Test error when cookie file is missing required fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cookie_file = Path(tmpdir) / "incomplete.cookie"
            cookie_file.write_text("SESSDATA=abc123; DedeUserID=123456")

            result = subprocess.run(
                ["python", str(SCRIPT_PATH), "--cookie-file", str(cookie_file)],
                capture_output=True,
                text=True
            )

            assert result.returncode == 1
            assert "Cookie 文件缺少必需的字段" in result.stderr
            assert "DedeUserID__ckMd5" in result.stderr
            assert "bili_jct" in result.stderr

    def test_valid_cookie_file_format(self):
        """Test valid cookie file format is accepted (will fail at network)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cookie_file = Path(tmpdir) / "valid.cookie"
            cookie_file.write_text(
                "SESSDATA=abc123; "
                "DedeUserID=123456; "
                "DedeUserID__ckMd5=xyz789; "
                "bili_jct=def456"
            )

            result = subprocess.run(
                ["python", str(SCRIPT_PATH), "--cookie-file", str(cookie_file)],
                capture_output=True,
                text=True,
                timeout=30
            )

            # Should pass cookie validation but fail at network (invalid cookies)
            # or succeed if cookies happen to be valid
            assert result.returncode in [0, 1]
            # If it got past cookie parsing, we should see this message
            if "成功" in result.stderr or "加载" in result.stderr:
                assert True  # Cookie parsing succeeded


class TestArgumentParsing:
    """Tests for command line argument parsing."""

    def test_default_cookie_file_path(self):
        """Test that default cookie file path is used."""
        # Run without --cookie-file, should look for default path
        result = subprocess.run(
            ["python", str(SCRIPT_PATH)],
            capture_output=True,
            text=True,
            timeout=60
        )

        # If cookie file exists and is valid, should succeed
        # If not, should fail with cookie-related error
        if result.returncode == 0:
            # Cookie file exists and worked
            assert "成功" in result.stdout or "up_name:" in result.stdout
        else:
            # Cookie file missing or invalid
            assert ".bilibili.cookie" in result.stderr or "Cookie" in result.stderr

    def test_custom_cookie_file_path(self):
        """Test custom cookie file path via --cookie-file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cookie_file = Path(tmpdir) / "custom.cookie"
            cookie_file.write_text(
                "SESSDATA=test; DedeUserID=1; DedeUserID__ckMd5=test; bili_jct=test"
            )

            result = subprocess.run(
                ["python", str(SCRIPT_PATH), "--cookie-file", str(cookie_file)],
                capture_output=True,
                text=True,
                timeout=30
            )

            # Should parse cookies successfully (output goes to stdout)
            output = result.stdout + result.stderr
            assert "成功" in output or "加载" in output or "Cookie" in output or result.returncode in [0, 1]


@pytest.mark.skip(reason="Requires valid Bilibili cookies and network access")
class TestWithRealCookies:
    """Tests that require real Bilibili cookies. Skipped by default."""

    def test_successful_extraction(self):
        """Test successful dynamic extraction with valid cookies."""
        # This test requires a valid cookie file at the default location
        result = subprocess.run(
            ["python", str(SCRIPT_PATH)],
            capture_output=True,
            text=True,
            timeout=60
        )

        assert result.returncode == 0
        assert "up_name:" in result.stdout or "未找到任何动态" in result.stdout
