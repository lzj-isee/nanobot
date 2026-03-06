"""Tests for CronTool."""

import pytest

from nanobot.agent.tools.cron import CronTool
from nanobot.cron.service import CronService


@pytest.fixture
def cron_service(tmp_path):
    """Create a CronService for testing."""
    return CronService(tmp_path / "cron" / "jobs.json")


@pytest.fixture
def cron_tool(cron_service):
    """Create a CronTool with context set."""
    tool = CronTool(cron_service)
    tool.set_context("test_channel", "test_chat_id")
    return tool


@pytest.mark.asyncio
async def test_add_reminder_job(cron_tool, cron_service):
    """Test adding a reminder job via tool."""
    result = await cron_tool.execute(
        action="add",
        kind="reminder",
        message="Drink water!",
        every_seconds=1800,
    )

    assert "Created reminder job" in result

    # Verify job was created with correct kind
    jobs = cron_service.list_jobs(include_disabled=True)
    assert len(jobs) == 1
    assert jobs[0].payload.kind == "reminder"
    assert jobs[0].payload.message == "Drink water!"


@pytest.mark.asyncio
async def test_add_task_job(cron_tool, cron_service):
    """Test adding a task job via tool."""
    result = await cron_tool.execute(
        action="add",
        kind="task",
        message="Check email",
        every_seconds=3600,
    )

    assert "Created task job" in result

    jobs = cron_service.list_jobs(include_disabled=True)
    assert jobs[0].payload.kind == "task"


@pytest.mark.asyncio
async def test_add_job_default_kind_is_task(cron_tool, cron_service):
    """Test that default kind is 'task' when not specified."""
    result = await cron_tool.execute(
        action="add",
        message="Default task",
        every_seconds=60,
    )

    assert "Created task job" in result

    jobs = cron_service.list_jobs(include_disabled=True)
    assert jobs[0].payload.kind == "task"


@pytest.mark.asyncio
async def test_add_job_rejects_invalid_kind(cron_tool):
    """Test that invalid kind is rejected."""
    result = await cron_tool.execute(
        action="add",
        kind="invalid",
        message="test",
        every_seconds=60,
    )

    assert "Error: kind must be 'reminder' or 'task'" in result


@pytest.mark.asyncio
async def test_add_one_time_reminder(cron_tool, cron_service):
    """Test adding a one-time reminder."""
    result = await cron_tool.execute(
        action="add",
        kind="reminder",
        message="Meeting now!",
        at="2026-12-31T23:59:59",
    )

    assert "Created reminder job" in result

    jobs = cron_service.list_jobs(include_disabled=True)
    assert jobs[0].payload.kind == "reminder"
    assert jobs[0].schedule.kind == "at"
    assert jobs[0].delete_after_run is True


@pytest.mark.asyncio
async def test_add_cron_reminder(cron_tool, cron_service):
    """Test adding a cron expression reminder."""
    result = await cron_tool.execute(
        action="add",
        kind="reminder",
        message="Daily reminder",
        cron_expr="0 9 * * *",
    )

    assert "Created reminder job" in result

    jobs = cron_service.list_jobs(include_disabled=True)
    assert jobs[0].payload.kind == "reminder"
    assert jobs[0].schedule.kind == "cron"


@pytest.mark.asyncio
async def test_list_jobs(cron_tool):
    """Test listing jobs."""
    # Add a job first
    await cron_tool.execute(
        action="add",
        kind="reminder",
        message="Test",
        every_seconds=60,
    )

    result = await cron_tool.execute(action="list")

    assert "Test" in result
    assert "reminder" in result


@pytest.mark.asyncio
async def test_remove_job(cron_tool, cron_service):
    """Test removing a job."""
    # Add a job
    await cron_tool.execute(
        action="add",
        kind="reminder",
        message="To be removed",
        every_seconds=60,
    )

    jobs = cron_service.list_jobs(include_disabled=True)
    job_id = jobs[0].id

    # Remove it
    result = await cron_tool.execute(action="remove", job_id=job_id)

    assert f"Removed job {job_id}" in result
    assert len(cron_service.list_jobs(include_disabled=True)) == 0


@pytest.mark.asyncio
async def test_remove_job_without_id(cron_tool):
    """Test removing a job without providing ID."""
    result = await cron_tool.execute(action="remove")

    assert "Error: job_id is required" in result


@pytest.mark.asyncio
async def test_add_job_without_message(cron_tool):
    """Test adding a job without message."""
    result = await cron_tool.execute(
        action="add",
        kind="reminder",
        every_seconds=60,
    )

    assert "Error: message is required" in result


@pytest.mark.asyncio
async def test_add_job_without_schedule(cron_tool):
    """Test adding a job without schedule."""
    result = await cron_tool.execute(
        action="add",
        kind="reminder",
        message="test",
    )

    assert "Error: either every_seconds, cron_expr, or at is required" in result


@pytest.mark.asyncio
async def test_add_job_without_context(cron_service):
    """Test adding a job without setting channel context."""
    tool = CronTool(cron_service)  # No context set

    result = await tool.execute(
        action="add",
        kind="reminder",
        message="test",
        every_seconds=60,
    )

    assert "Error: no session context" in result
