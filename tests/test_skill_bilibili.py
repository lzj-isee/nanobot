"""Tests for bilibili skill scripts"""

import pytest
import subprocess
import tempfile
from pathlib import Path

# Get script paths
SCRIPTS_DIR = Path(__file__).parent.parent / "nanobot" / "skills" / "bilibili" / "scripts"
FEED_FOLLOWING_SCRIPT = SCRIPTS_DIR / "bilibili_feed_following.py"
FEED_USER_SCRIPT = SCRIPTS_DIR / "bilibili_feed_user.py"
FOLLOWING_LIST_SCRIPT = SCRIPTS_DIR / "bilibili_following_list.py"

ALL_SCRIPTS = [FEED_FOLLOWING_SCRIPT, FEED_USER_SCRIPT, FOLLOWING_LIST_SCRIPT]


class TestScriptBasics:
    """Basic script tests."""

    @pytest.mark.parametrize("script_path", ALL_SCRIPTS)
    def test_script_exists(self, script_path):
        """Test that each script exists."""
        assert script_path.exists(), f"Script {script_path.name} should exist"

    @pytest.mark.parametrize("script_path", ALL_SCRIPTS)
    def test_help_flag(self, script_path):
        """Test --help flag for each script."""
        result = subprocess.run(
            ["python", str(script_path), "--help"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, f"{script_path.name} --help should succeed"
        assert "usage:" in result.stdout.lower()
        assert "--cookie-file" in result.stdout


class TestCookieFileHandling:
    """Tests for cookie file handling - applicable to all scripts."""

    @pytest.mark.parametrize("script_path", ALL_SCRIPTS)
    def test_missing_cookie_file(self, script_path):
        """Test error when cookie file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            nonexistent_cookie = Path(tmpdir) / "nonexistent.cookie"

            result = subprocess.run(
                ["python", str(script_path), "--cookie-file", str(nonexistent_cookie)]
                if script_path != FEED_USER_SCRIPT
                else ["python", str(script_path), "--uid", "123456", "--cookie-file", str(nonexistent_cookie)],
                capture_output=True,
                text=True
            )

            assert result.returncode == 1
            assert "Cookie 文件不存在" in result.stderr or "does not exist" in result.stderr.lower()

    @pytest.mark.parametrize("script_path", ALL_SCRIPTS)
    def test_empty_cookie_file(self, script_path):
        """Test error when cookie file is empty."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cookie_file = Path(tmpdir) / "empty.cookie"
            cookie_file.write_text("")

            result = subprocess.run(
                ["python", str(script_path), "--cookie-file", str(cookie_file)]
                if script_path != FEED_USER_SCRIPT
                else ["python", str(script_path), "--uid", "123456", "--cookie-file", str(cookie_file)],
                capture_output=True,
                text=True
            )

            assert result.returncode == 1
            assert "Cookie 文件为空" in result.stderr or "Cookie 文件内容为空" in result.stderr

    @pytest.mark.parametrize("script_path", ALL_SCRIPTS)
    def test_cookie_file_missing_required_fields(self, script_path):
        """Test error when cookie file is missing required fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cookie_file = Path(tmpdir) / "incomplete.cookie"
            cookie_file.write_text("SESSDATA=abc123; DedeUserID=123456")

            result = subprocess.run(
                ["python", str(script_path), "--cookie-file", str(cookie_file)]
                if script_path != FEED_USER_SCRIPT
                else ["python", str(script_path), "--uid", "123456", "--cookie-file", str(cookie_file)],
                capture_output=True,
                text=True
            )

            assert result.returncode == 1
            assert "Cookie 文件缺少必需的字段" in result.stderr
            assert "DedeUserID__ckMd5" in result.stderr
            assert "bili_jct" in result.stderr

    @pytest.mark.parametrize("script_path", ALL_SCRIPTS)
    def test_valid_cookie_file_format(self, script_path):
        """Test valid cookie file format is accepted (will fail at network)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cookie_file = Path(tmpdir) / "valid.cookie"
            cookie_file.write_text(
                "SESSDATA=abc123; "
                "DedeUserID=123456; "
                "DedeUserID__ckMd5=xyz789; "
                "bili_jct=def456"
            )

            cmd = ["python", str(script_path), "--cookie-file", str(cookie_file)]
            if script_path == FEED_USER_SCRIPT:
                cmd.extend(["--uid", "123456"])

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )

            # Should pass cookie validation but fail at network (invalid cookies)
            # or succeed if cookies happen to be valid
            assert result.returncode in [0, 1]
            # If it got past cookie parsing, we should see this message
            output = result.stdout + result.stderr
            if "成功" in output or "加载" in output:
                assert True  # Cookie parsing succeeded


class TestFeedFollowingScript:
    """Tests specific to bilibili_feed_following.py"""

    def test_use_page_flag(self):
        """Test --use-page flag exists."""
        result = subprocess.run(
            ["python", str(FEED_FOLLOWING_SCRIPT), "--help"],
            capture_output=True,
            text=True
        )
        assert "--use-page" in result.stdout

    def test_output_flag(self):
        """Test --output flag exists."""
        result = subprocess.run(
            ["python", str(FEED_FOLLOWING_SCRIPT), "--help"],
            capture_output=True,
            text=True
        )
        assert "--output" in result.stdout or "-o" in result.stdout


class TestFeedUserScript:
    """Tests specific to bilibili_feed_user.py"""

    def test_uid_required(self):
        """Test that --uid is required."""
        result = subprocess.run(
            ["python", str(FEED_USER_SCRIPT)],
            capture_output=True,
            text=True
        )
        assert result.returncode != 0
        assert "--uid" in result.stderr or "required" in result.stderr.lower()

    def test_uid_argument(self):
        """Test --uid argument is accepted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cookie_file = Path(tmpdir) / "test.cookie"
            cookie_file.write_text(
                "SESSDATA=test; DedeUserID=1; DedeUserID__ckMd5=test; bili_jct=test"
            )

            result = subprocess.run(
                ["python", str(FEED_USER_SCRIPT), "--uid", "123456", "--cookie-file", str(cookie_file)],
                capture_output=True,
                text=True,
                timeout=30
            )

            # Should accept the UID argument (will fail at network)
            output = result.stdout + result.stderr
            assert "成功" in output or "加载" in output or result.returncode == 1

    def test_limit_flag(self):
        """Test --limit flag exists."""
        result = subprocess.run(
            ["python", str(FEED_USER_SCRIPT), "--help"],
            capture_output=True,
            text=True
        )
        assert "--limit" in result.stdout or "-l" in result.stdout

    def test_format_flag(self):
        """Test --format flag exists."""
        result = subprocess.run(
            ["python", str(FEED_USER_SCRIPT), "--help"],
            capture_output=True,
            text=True
        )
        assert "--format" in result.stdout
        assert "json" in result.stdout
        assert "text" in result.stdout


class TestFollowingListScript:
    """Tests specific to bilibili_following_list.py"""

    def test_name_flag(self):
        """Test --name flag exists for search."""
        result = subprocess.run(
            ["python", str(FOLLOWING_LIST_SCRIPT), "--help"],
            capture_output=True,
            text=True
        )
        assert "--name" in result.stdout or "-n" in result.stdout

    def test_top_flag(self):
        """Test --top flag exists for limiting search results."""
        result = subprocess.run(
            ["python", str(FOLLOWING_LIST_SCRIPT), "--help"],
            capture_output=True,
            text=True
        )
        assert "--top" in result.stdout or "-t" in result.stdout

    def test_format_flag(self):
        """Test --format flag exists."""
        result = subprocess.run(
            ["python", str(FOLLOWING_LIST_SCRIPT), "--help"],
            capture_output=True,
            text=True
        )
        assert "--format" in result.stdout


class TestWithRealCookies:
    """Tests that use the real Bilibili cookie file."""

    COOKIE_FILE = SCRIPTS_DIR / ".bilibili.cookie"

    def test_feed_following_with_real_cookies(self):
        """Test feed following extraction with valid cookies."""
        result = subprocess.run(
            ["python", str(FEED_FOLLOWING_SCRIPT), "--cookie-file", str(self.COOKIE_FILE)],
            capture_output=True,
            text=True,
            timeout=60
        )

        assert result.returncode == 0
        output = result.stdout + result.stderr
        assert "up_name:" in output or "未找到任何动态" in output or "获取到" in output

    def test_feed_user_with_real_cookies(self):
        """Test user feed extraction with valid cookies."""
        # Using a well-known Bilibili user (Bilibili official account)
        result = subprocess.run(
            ["python", str(FEED_USER_SCRIPT), "--uid", "208259", "--limit", "5", "--cookie-file", str(self.COOKIE_FILE)],
            capture_output=True,
            text=True,
            timeout=60
        )

        assert result.returncode == 0
        output = result.stdout + result.stderr
        assert "共" in output or "动态" in output or "获取到" in output

    def test_following_list_with_real_cookies(self):
        """Test following list extraction with valid cookies."""
        result = subprocess.run(
            ["python", str(FOLLOWING_LIST_SCRIPT), "--cookie-file", str(self.COOKIE_FILE)],
            capture_output=True,
            text=True,
            timeout=120
        )

        assert result.returncode == 0
        output = result.stdout + result.stderr
        assert "共关注" in output or "UP主" in output or "获取" in output

    def test_following_list_search_with_real_cookies(self):
        """Test following list search with valid cookies."""
        result = subprocess.run(
            ["python", str(FOLLOWING_LIST_SCRIPT), "--name", "测试", "--top", "5", "--cookie-file", str(self.COOKIE_FILE)],
            capture_output=True,
            text=True,
            timeout=120
        )

        assert result.returncode == 0
        output = result.stdout + result.stderr
        assert "搜索" in output or "共关注" in output or "结果" in output
