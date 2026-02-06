---
name: scheduling
description: Use when asked to set a reminder, schedule something, create a recurring task, check scheduled tasks, or anything involving "remind me", "schedule", "every day at", "in 2 hours", "tomorrow at", "on feb 1st".
user-invocable: false
---

# Scheduling Skill

This is your reference for creating and managing scheduled tasks. You MUST actually create the cron job when asked to set a reminder - don't just acknowledge the request.

## How to Schedule

Use the CronManager class from Python:

```python
from jarvis.cron import CronManager

cron = CronManager()
cron.add_task(
    name="unique-task-name",          # lowercase, hyphens
    schedule="0 9 * * *",             # cron expression
    task_description="what to do",    # this becomes claude's prompt
    one_shot=False,                   # True = runs once then deletes itself
)
```

Run this with: `uv run python -c "..."`

## Cron Schedule Format

```
┌───────────── minute (0-59)
│ ┌───────────── hour (0-23)
│ │ ┌───────────── day of month (1-31)
│ │ │ ┌───────────── month (1-12)
│ │ │ │ ┌───────────── day of week (0-6, 0=Sunday)
│ │ │ │ │
* * * * *
```

### Common Patterns

| Want | Cron Expression |
|------|-----------------|
| Every day at 8am | `0 8 * * *` |
| Every hour | `0 * * * *` |
| Every 2 hours | `0 */2 * * *` |
| Weekdays at 9am | `0 9 * * 1-5` |
| Jan 29 at 5pm | `0 17 29 1 *` |
| Feb 1 at 10am | `0 10 1 2 *` |
| Every Monday at 10am | `0 10 * * 1` |
| First of month at noon | `0 12 1 * *` |

## One-Shot vs Recurring

- `one_shot=True`: for reminders ("remind me tomorrow at 5pm") - runs once, deletes itself
- `one_shot=False`: for recurring tasks ("every morning at 8am") - keeps running

## Task Description

The task_description becomes the prompt for a fresh claude session. Be specific:

```python
# good - specific action
task_description="Send the user a reminder about buying toothfloss and shower gel"

# bad - vague
task_description="Reminder"
```

## Managing Tasks

```python
from jarvis.cron import CronManager

cron = CronManager()

# list all scheduled tasks
tasks = cron.list_tasks()

# remove a task
cron.remove_task("task-name")
```

## Full Example: Setting a Reminder

User: "remind me tomorrow at 5pm to buy groceries"

```python
from jarvis.cron import CronManager
from datetime import datetime, timedelta

# calculate tomorrow
tomorrow = datetime.now() + timedelta(days=1)
schedule = f"0 17 {tomorrow.day} {tomorrow.month} *"

cron = CronManager()
cron.add_task(
    name="reminder-groceries",
    schedule=schedule,
    task_description="Send the user a reminder to buy groceries",
    one_shot=True,
)
```

## What Happens When Task Runs

1. Cron triggers the task
2. `scheduled_task.py` runs claude with the task_description as prompt
3. Claude executes and can send WhatsApp messages, update news.md, etc.
4. If one_shot=True, the cron entry is removed after running

## Important

- Always use `one_shot=True` for one-time reminders
- Always confirm to the user that the reminder is set (but don't mention "one-shot" or implementation details)
- Task names should be descriptive and unique (use hyphens, lowercase)
- Test the cron expression mentally before setting
