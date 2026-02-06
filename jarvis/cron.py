"""Cronjob management for scheduled tasks."""

from pathlib import Path
from crontab import CronTab


class CronManager:
    """Manage user crontab for scheduled tasks."""

    def __init__(self):
        self.cron = CronTab(user=True)
        self.project_root = Path(__file__).parent.parent.absolute()
        self.scripts_dir = self.project_root / "scripts"

    def add_task(
        self,
        name: str,
        schedule: str,
        task_description: str,
        *,
        one_shot: bool = False,
    ) -> str:
        """
        Add a scheduled task.

        Args:
            name: Unique identifier for the task
            schedule: Cron schedule expression (e.g., "0 */2 * * *" for every 2 hours)
            task_description: What the task should do (passed to scheduled_task.py)
            one_shot: If True, task removes itself after running once

        Returns:
            Confirmation message
        """
        # Remove existing job with same name
        self.remove_task(name)

        # Use wrapper script that handles PATH and environment setup
        wrapper_script = self.scripts_dir / "run_cronjob.sh"

        # Escape quotes in task description for shell
        escaped_desc = task_description.replace('"', '\\"')
        cmd = f'{wrapper_script} "{name}" "{escaped_desc}"'
        if one_shot:
            cmd += " --one-shot"

        job = self.cron.new(command=cmd, comment=f"jarvis:{name}")
        job.setall(schedule)

        self.cron.write()
        return f"Scheduled task '{name}' with schedule: {schedule}"

    def remove_task(self, name: str) -> bool:
        """Remove a scheduled task by name."""
        removed = False
        for job in self.cron.find_comment(f"jarvis:{name}"):
            self.cron.remove(job)
            removed = True
        self.cron.write()
        return removed

    def list_tasks(self) -> list[dict]:
        """List all Jarvis scheduled tasks."""
        tasks = []
        for job in self.cron:
            if job.comment and job.comment.startswith("jarvis:"):
                name = job.comment.replace("jarvis:", "")
                tasks.append({
                    "name": name,
                    "schedule": str(job.slices),
                    "command": job.command,
                    "enabled": job.is_enabled(),
                })
        return tasks

    def setup_memory_cleanup(self):
        """Set up the daily memory cleanup cronjob."""
        return self.add_task(
            name="memory-cleanup",
            schedule="0 3 * * *",  # Daily at 3am
            task_description="review memories using MemoryManager().get_all() - delete outdated or superseded ones with MemoryManager().delete(memory_id). chunks are auto-deleted with memory. be conservative.",
        )
