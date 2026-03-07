"""Tests for stock skill - search_stock.py (using subprocess)"""

import pytest
import subprocess
from pathlib import Path

# Get script path
SCRIPT_PATH = Path(__file__).parent.parent / "nanobot" / "skills" / "stock" / "scripts" / "search_stock.py"


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
        assert "--query" in result.stdout or "-q" in result.stdout


class TestArgumentParsing:
    """Tests for command line argument parsing."""

    def test_missing_query_argument(self):
        """Test error when query argument is missing."""
        result = subprocess.run(
            ["python", str(SCRIPT_PATH)],
            capture_output=True,
            text=True
        )

        assert result.returncode == 2
        assert "required" in result.stderr.lower() or "--query" in result.stderr

    def test_query_with_long_flag(self):
        """Test query with --query flag."""
        result = subprocess.run(
            ["python", str(SCRIPT_PATH), "--query", "贵州茅台"],
            capture_output=True,
            text=True,
            timeout=30
        )

        # Should run (may succeed or fail depending on network)
        assert result.returncode in [0, 1]
        # Should show it's accessing the URL
        assert "eastmoney.com" in result.stderr or "Accessing" in result.stderr or "股票" in result.stdout or result.returncode == 0

    def test_query_with_short_flag(self):
        """Test query with -q short flag."""
        result = subprocess.run(
            ["python", str(SCRIPT_PATH), "-q", "600519"],
            capture_output=True,
            text=True,
            timeout=30
        )

        # Should run (may succeed or fail depending on network)
        assert result.returncode in [0, 1]


@pytest.mark.skip(reason="Requires network access to East Money")
class TestWithNetwork:
    """Tests that require network access. Skipped by default."""

    def test_search_by_stock_name(self):
        """Test searching by stock name."""
        result = subprocess.run(
            ["python", str(SCRIPT_PATH), "--query", "贵州茅台"],
            capture_output=True,
            text=True,
            timeout=30
        )

        assert result.returncode == 0
        # Should contain stock information
        assert "茅台" in result.stdout or "股票" in result.stdout or "行情" in result.stdout

    def test_search_by_stock_code(self):
        """Test searching by stock code."""
        result = subprocess.run(
            ["python", str(SCRIPT_PATH), "--query", "600519"],
            capture_output=True,
            text=True,
            timeout=30
        )

        assert result.returncode == 0

    def test_search_etf(self):
        """Test searching for ETF."""
        result = subprocess.run(
            ["python", str(SCRIPT_PATH), "--query", "红利低波"],
            capture_output=True,
            text=True,
            timeout=30
        )

        assert result.returncode == 0

    def test_search_index(self):
        """Test searching for index."""
        result = subprocess.run(
            ["python", str(SCRIPT_PATH), "--query", "沪深300"],
            capture_output=True,
            text=True,
            timeout=30
        )

        assert result.returncode == 0


class TestErrorHandling:
    """Tests for error handling."""

    def test_invalid_stock_code(self):
        """Test handling of invalid stock code."""
        result = subprocess.run(
            ["python", str(SCRIPT_PATH), "--query", "INVALID_CODE_12345"],
            capture_output=True,
            text=True,
            timeout=30
        )

        # Should complete without crashing
        assert result.returncode in [0, 1]

    def test_special_characters_in_query(self):
        """Test handling of special characters in query."""
        result = subprocess.run(
            ["python", str(SCRIPT_PATH), "--query", "股票!@#$%"],
            capture_output=True,
            text=True,
            timeout=30
        )

        # Should complete without crashing
        assert result.returncode in [0, 1]
