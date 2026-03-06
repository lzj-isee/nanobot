from typer.testing import CliRunner

from nanobot.cli.commands import app

runner = CliRunner()


def test_cron_add_rejects_invalid_timezone(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("nanobot.config.loader.get_data_dir", lambda: tmp_path)

    result = runner.invoke(
        app,
        [
            "cron",
            "add",
            "--name",
            "demo",
            "--message",
            "hello",
            "--cron",
            "0 9 * * *",
            "--tz",
            "America/Vancovuer",
        ],
    )

    assert result.exit_code == 1
    assert "Error: unknown timezone 'America/Vancovuer'" in result.stdout
    assert not (tmp_path / "cron" / "jobs.json").exists()


def test_cron_add_with_kind_reminder(monkeypatch, tmp_path) -> None:
    """Test adding a reminder job via CLI."""
    monkeypatch.setattr("nanobot.config.loader.get_data_dir", lambda: tmp_path)

    result = runner.invoke(
        app,
        [
            "cron",
            "add",
            "--name",
            "water",
            "--message",
            "Drink water!",
            "--every",
            "1800",
            "--kind",
            "reminder",
        ],
    )

    assert result.exit_code == 0
    assert "Added reminder job" in result.stdout

    # Verify job was created with correct kind
    import json
    jobs_file = tmp_path / "cron" / "jobs.json"
    assert jobs_file.exists()
    data = json.loads(jobs_file.read_text())
    assert len(data["jobs"]) == 1
    assert data["jobs"][0]["payload"]["kind"] == "reminder"


def test_cron_add_with_kind_task(monkeypatch, tmp_path) -> None:
    """Test adding a task job via CLI (default kind)."""
    monkeypatch.setattr("nanobot.config.loader.get_data_dir", lambda: tmp_path)

    result = runner.invoke(
        app,
        [
            "cron",
            "add",
            "--name",
            "report",
            "--message",
            "Generate daily report",
            "--every",
            "3600",
            "--kind",
            "task",
        ],
    )

    assert result.exit_code == 0
    assert "Added task job" in result.stdout

    # Verify job was created with correct kind
    import json
    jobs_file = tmp_path / "cron" / "jobs.json"
    data = json.loads(jobs_file.read_text())
    assert data["jobs"][0]["payload"]["kind"] == "task"


def test_cron_add_default_kind_is_task(monkeypatch, tmp_path) -> None:
    """Test that default kind is 'task' when not specified."""
    monkeypatch.setattr("nanobot.config.loader.get_data_dir", lambda: tmp_path)

    result = runner.invoke(
        app,
        [
            "cron",
            "add",
            "--name",
            "default",
            "--message",
            "test message",
            "--every",
            "60",
        ],
    )

    assert result.exit_code == 0

    # Verify default kind is task
    import json
    jobs_file = tmp_path / "cron" / "jobs.json"
    data = json.loads(jobs_file.read_text())
    assert data["jobs"][0]["payload"]["kind"] == "task"


def test_cron_add_rejects_invalid_kind(monkeypatch, tmp_path) -> None:
    """Test that invalid kind is rejected."""
    monkeypatch.setattr("nanobot.config.loader.get_data_dir", lambda: tmp_path)

    result = runner.invoke(
        app,
        [
            "cron",
            "add",
            "--name",
            "test",
            "--message",
            "test",
            "--every",
            "60",
            "--kind",
            "invalid",
        ],
    )

    assert result.exit_code == 1
    assert "Error: --kind must be 'reminder' or 'task'" in result.stdout


def test_cron_add_at_with_kind_reminder(monkeypatch, tmp_path) -> None:
    """Test adding a one-time reminder."""
    monkeypatch.setattr("nanobot.config.loader.get_data_dir", lambda: tmp_path)

    result = runner.invoke(
        app,
        [
            "cron",
            "add",
            "--name",
            "meeting",
            "--message",
            "Meeting starts now!",
            "--at",
            "2026-12-31T23:59:59",
            "--kind",
            "reminder",
        ],
    )

    assert result.exit_code == 0
    assert "Added reminder job" in result.stdout

    # Verify delete_after_run is True for at jobs
    import json
    jobs_file = tmp_path / "cron" / "jobs.json"
    data = json.loads(jobs_file.read_text())
    assert data["jobs"][0]["payload"]["kind"] == "reminder"
    assert data["jobs"][0]["deleteAfterRun"] is True
