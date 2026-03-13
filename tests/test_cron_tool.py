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
async def test_add_job_requires_kind(cron_tool):
    """Test that kind is required when adding a job."""
    result = await cron_tool.execute(
        action="add",
        message="Missing kind",
        every_seconds=60,
    )

    assert "Error: kind is required" in result


@pytest.mark.asyncio
async def test_add_job_with_custom_name(cron_tool, cron_service):
    """Test adding a job with custom name."""
    result = await cron_tool.execute(
        action="add",
        kind="reminder",
        name="Water Break",
        message="Time to drink water and stretch your legs!",
        every_seconds=1800,
    )

    assert "Created reminder job" in result

    jobs = cron_service.list_jobs(include_disabled=True)
    assert len(jobs) == 1
    assert jobs[0].name == "Water Break"
    assert jobs[0].payload.message == "Time to drink water and stretch your legs!"


@pytest.mark.asyncio
async def test_add_job_without_name_uses_message(cron_tool, cron_service):
    """Test that message is used as name fallback when name not provided."""
    result = await cron_tool.execute(
        action="add",
        kind="task",
        message="Check email and respond to urgent ones",
        every_seconds=3600,
    )

    assert "Created task job" in result

    jobs = cron_service.list_jobs(include_disabled=True)
    assert len(jobs) == 1
    # Name should be truncated message (first 30 chars)
    assert jobs[0].name == "Check email and respond to urg"
    assert jobs[0].payload.message == "Check email and respond to urgent ones"


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
        name="Test Job",
        message="Test reminder message",
        every_seconds=60,
    )

    result = await cron_tool.execute(action="list")

    assert "Test Job" in result
    assert "reminder" in result
    assert "every 60s" in result
    assert "Test reminder message" in result
    assert "enabled" in result


@pytest.mark.asyncio
async def test_list_jobs_with_cron_expr(cron_tool):
    """Test listing jobs with cron expression and timezone."""
    await cron_tool.execute(
        action="add",
        kind="task",
        name="Daily Task",
        message="Generate daily report",
        cron_expr="0 9 * * *",
        tz="America/Vancouver",
    )

    result = await cron_tool.execute(action="list")

    assert "Daily Task" in result
    assert "task" in result
    assert "0 9 * * *" in result
    assert "America/Vancouver" in result
    assert "Generate daily report" in result


@pytest.mark.asyncio
async def test_list_jobs_with_one_time(cron_tool):
    """Test listing one-time jobs."""
    await cron_tool.execute(
        action="add",
        kind="reminder",
        name="Meeting",
        message="Team standup now!",
        at="2026-12-31T23:59:59",
    )

    result = await cron_tool.execute(action="list")

    assert "Meeting" in result
    assert "one-time" in result
    assert "Team standup now!" in result


@pytest.mark.asyncio
async def test_list_jobs_multiple(cron_tool):
    """Test listing multiple jobs."""
    await cron_tool.execute(
        action="add",
        kind="reminder",
        name="Job A",
        message="Message A",
        every_seconds=60,
    )
    await cron_tool.execute(
        action="add",
        kind="task",
        name="Job B",
        message="Message B",
        every_seconds=120,
    )

    result = await cron_tool.execute(action="list")

    assert "Job A" in result
    assert "Job B" in result
    assert "Message A" in result
    assert "Message B" in result
    assert "every 60s" in result
    assert "every 120s" in result


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
