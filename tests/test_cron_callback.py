"""Tests for cron job callback execution."""

import asyncio
import pytest

from nanobot.cron.service import CronService
from nanobot.cron.types import CronJob, CronPayload, CronSchedule


@pytest.mark.asyncio
async def test_reminder_job_sends_directly():
    """Test that reminder jobs send message directly without agent."""
    sent_messages = []

    async def mock_on_job(job: CronJob) -> str | None:
        """Mock callback that handles both kinds."""
        if job.payload.kind == "reminder":
            # Reminder: send directly
            sent_messages.append({
                "type": "direct",
                "content": job.payload.message,
            })
            return job.payload.message
        else:
            # Task: would go through agent (mocked)
            sent_messages.append({
                "type": "agent",
                "content": f"Agent processed: {job.payload.message}",
            })
            return f"Agent processed: {job.payload.message}"

    service = CronService(
        store_path=None,  # Don't persist for this test
        on_job=mock_on_job,
    )
    service._store = type('obj', (object,), {'jobs': []})()

    # Add a reminder job
    job = service.add_job(
        name="reminder",
        schedule=CronSchedule(kind="at", at_ms=1893456000000),
        message="Drink water!",
        kind="reminder",
    )

    # Execute the job
    await service._execute_job(job)

    # Verify direct send
    assert len(sent_messages) == 1
    assert sent_messages[0]["type"] == "direct"
    assert sent_messages[0]["content"] == "Drink water!"


@pytest.mark.asyncio
async def test_task_job_goes_through_agent():
    """Test that task jobs are processed by agent."""
    sent_messages = []

    async def mock_on_job(job: CronJob) -> str | None:
        """Mock callback that handles both kinds."""
        if job.payload.kind == "reminder":
            sent_messages.append({
                "type": "direct",
                "content": job.payload.message,
            })
            return job.payload.message
        else:
            # Simulate agent processing
            response = f"Task completed: {job.payload.message}"
            sent_messages.append({
                "type": "agent",
                "content": response,
            })
            return response

    service = CronService(
        store_path=None,
        on_job=mock_on_job,
    )
    service._store = type('obj', (object,), {'jobs': []})()

    # Add a task job
    job = service.add_job(
        name="task",
        schedule=CronSchedule(kind="at", at_ms=1893456000000),
        message="Check email",
        kind="task",
    )

    # Execute the job
    await service._execute_job(job)

    # Verify agent processing
    assert len(sent_messages) == 1
    assert sent_messages[0]["type"] == "agent"
    assert "Task completed" in sent_messages[0]["content"]


@pytest.mark.asyncio
async def test_job_kind_preserved_in_payload():
    """Test that job kind is correctly stored in payload."""
    service = CronService(store_path=None)
    service._store = type('obj', (object,), {'jobs': []})()

    # Add jobs of different kinds
    reminder_job = service.add_job(
        name="reminder",
        schedule=CronSchedule(kind="every", every_ms=60000),
        message="reminder msg",
        kind="reminder",
    )

    task_job = service.add_job(
        name="task",
        schedule=CronSchedule(kind="every", every_ms=60000),
        message="task msg",
        kind="task",
    )

    # Verify kinds are preserved
    assert reminder_job.payload.kind == "reminder"
    assert task_job.payload.kind == "task"

    # Verify messages are preserved
    assert reminder_job.payload.message == "reminder msg"
    assert task_job.payload.message == "task msg"


@pytest.mark.asyncio
async def test_reminder_job_with_delivery():
    """Test reminder job with deliver flag."""
    delivered_messages = []

    async def mock_on_job_with_delivery(job: CronJob) -> str | None:
        """Mock callback that handles delivery."""
        if job.payload.kind == "reminder":
            if job.payload.to:
                delivered_messages.append({
                    "channel": job.payload.channel,
                    "to": job.payload.to,
                    "content": job.payload.message,
                })
            return job.payload.message
        return None

    service = CronService(
        store_path=None,
        on_job=mock_on_job_with_delivery,
    )
    service._store = type('obj', (object,), {'jobs': []})()

    # Add a reminder job with delivery info
    job = service.add_job(
        name="reminder",
        schedule=CronSchedule(kind="at", at_ms=1893456000000),
        message="Meeting now!",
        kind="reminder",
        deliver=True,
        channel="telegram",
        to="123456789",
    )

    # Execute
    await service._execute_job(job)

    # Verify delivery
    assert len(delivered_messages) == 1
    assert delivered_messages[0]["channel"] == "telegram"
    assert delivered_messages[0]["to"] == "123456789"
    assert delivered_messages[0]["content"] == "Meeting now!"
