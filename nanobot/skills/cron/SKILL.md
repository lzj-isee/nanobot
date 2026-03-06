---
name: cron
description: Schedule reminders and recurring tasks.
---

# Cron

Use the `cron` tool to schedule reminders or recurring tasks.

## Job Types

### 1. Reminder (`kind="reminder"`)
Message is sent directly to user without agent processing.

```example
cron(action="add", kind="reminder", message="Time to take a break!", every_seconds=1200)
```

### 2. Task (`kind="task"`)
Message is a task description, agent executes and sends result.

```example
cron(action="add", kind="task", message="Check HKUDS/nanobot GitHub stars and report", every_seconds=600)
```

## Schedule Types

| Schedule | Description | Example |
|----------|-------------|---------|
| `at` | One-time at specific time | `at="2026-03-07T10:00:00"` |
| `every` | Recurring interval | `every_seconds=3600` |
| `cron` | Cron expression | `cron_expr="0 9 * * *"` |

## Examples

One-time reminder:
```example
cron(action="add", kind="reminder", message="Meeting starts now!", at="2026-03-07T10:00:00")
```

Recurring reminder:
```example
cron(action="add", kind="reminder", message="Drink water!", every_seconds=1800)
```

Daily task with timezone:
```example
cron(action="add", kind="task", message="Morning standup summary", cron_expr="0 9 * * 1-5", tz="America/Vancouver")
```

One-time task (agent executes once at specific time):
```example
cron(action="add", kind="task", message="Generate daily report and send to team", at="2026-03-07T18:00:00")
```

List/remove:
```example
cron(action="list")
cron(action="remove", job_id="abc123")
```

## Time Expressions

| User says | Parameters |
|-----------|------------|
| every 20 minutes | `every_seconds: 1200` |
| every hour | `every_seconds: 3600` |
| every day at 8am | `cron_expr: "0 8 * * *"` |
| weekdays at 5pm | `cron_expr: "0 17 * * 1-5"` |
| 9am Vancouver time daily | `cron_expr: "0 9 * * *", tz: "America/Vancouver"` |
| at a specific time | `at: ISO datetime string` |

## Timezone

Use `tz` with `cron_expr` to schedule in a specific IANA timezone. Without `tz`, the server's local timezone is used.
