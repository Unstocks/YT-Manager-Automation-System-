"""
YT Manager Persistent Scheduling Engine
Provides:
1. Native Windows Task Scheduler registration via PowerShell (survives system restarts & reboots).
2. Standalone continuous daemon loop with IST (UTC+05:30) timezone awareness and retry intervals.
3. Duplicate-run protection via state manager.
"""
from __future__ import annotations

import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from .config import YTManagerConfig
from .orchestrator import WorkflowOrchestrator

TASK_NAME = "YT-Manager-Daily"


class TaskSchedulerManager:
    def __init__(self, config: YTManagerConfig):
        self.config = config

    def install_windows_task(self) -> bool:
        """
        Registers a persistent Windows Scheduled Task that executes daily at schedule_time IST.
        Survives application restarts and Windows restarts.
        Handles standard user permissions cleanly without requiring Administrator elevation.
        """
        python_exe = sys.executable
        project_dir = str(self.config.base_dir).replace('"', '`"')

        # Attempt 1: PowerShell ScheduledTask with current user scope
        ps_script = f"""
        $action = New-ScheduledTaskAction -Execute "{python_exe}" -Argument "-m yt_manager run" -WorkingDirectory "{project_dir}"
        $t1 = New-ScheduledTaskTrigger -Daily -At {self.config.schedule_time}
        $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 2)
        $principal = New-ScheduledTaskPrincipal -UserId "$env:USERNAME" -LogonType Interactive

        try {{
            $t2 = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERNAME"
            Register-ScheduledTask -TaskName "{TASK_NAME}" -Action $action -Trigger @($t1, $t2) -Settings $settings -Principal $principal -Description "YT Manager Autonomous Daily YouTube Upload" -Force | Out-Null
            Write-Output "SUCCESS_DUAL"
        }} catch {{
            try {{
                Register-ScheduledTask -TaskName "{TASK_NAME}" -Action $action -Trigger $t1 -Settings $settings -Principal $principal -Description "YT Manager Autonomous Daily YouTube Upload" -Force | Out-Null
                Write-Output "SUCCESS_DAILY"
            }} catch {{
                Write-Output "ERROR: $($_.Exception.Message)"
            }}
        }}
        """
        try:
            res = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
                capture_output=True,
                text=True,
            )
            output = res.stdout.strip()
            if "SUCCESS_DUAL" in output:
                print(f"[Scheduler] Windows Scheduled Task '{TASK_NAME}' registered successfully (Daily at {self.config.schedule_time} IST + Logon Catch-Up).")
                return True
            elif "SUCCESS_DAILY" in output:
                print(f"[Scheduler] Windows Scheduled Task '{TASK_NAME}' registered successfully (Daily at {self.config.schedule_time} IST with Catch-Up).")
                return True
        except Exception:
            pass

        # Attempt 2: Fallback to native Windows schtasks.exe (works for standard users)
        cmd = [
            "schtasks",
            "/create",
            "/tn",
            TASK_NAME,
            "/tr",
            f'"{python_exe}" -m yt_manager run',
            "/sc",
            "daily",
            "/st",
            self.config.schedule_time,
            "/f",
        ]
        try:
            sub_res = subprocess.run(cmd, capture_output=True, text=True)
            if sub_res.returncode == 0:
                print(f"[Scheduler] Windows Scheduled Task '{TASK_NAME}' registered successfully via schtasks (Daily at {self.config.schedule_time} IST).")
                return True
            else:
                err_msg = sub_res.stderr.strip() or sub_res.stdout.strip()
                print(f"[Scheduler] Warning: Failed to register Windows Scheduled Task: {err_msg}")
        except Exception as ex:
            print(f"[Scheduler] Fallback error: {ex}")

        print("\n[Scheduler TIP] If Windows permissions are restricted on your account, open PowerShell as Administrator and run:")
        print("  python -m yt_manager schedule --install\n")
        return False

    def uninstall_windows_task(self) -> bool:
        """Unregisters the scheduled task."""
        ps_script = f'Unregister-ScheduledTask -TaskName "{TASK_NAME}" -Confirm:$false -ErrorAction SilentlyContinue'
        try:
            subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
                capture_output=True,
                check=True,
            )
            print(f"[Scheduler] Windows Scheduled Task '{TASK_NAME}' unregistered successfully.")
            return True
        except Exception:
            return False

    def check_task_status(self) -> str:
        """Inspects if the Windows Scheduled Task is registered and active."""
        ps_script = f'Get-ScheduledTask -TaskName "{TASK_NAME}" -ErrorAction SilentlyContinue | Select-Object -ExpandProperty State'
        try:
            res = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
                capture_output=True,
                text=True,
            )
            state = res.stdout.strip()
            return state if state else "NOT_REGISTERED"
        except Exception:
            return "UNKNOWN"

    def run_daemon(self, poll_interval_seconds: int = 60, mock_mode: bool = False) -> None:
        """
        Runs continuous in-process daemon scheduler as a standalone process.
        Monitors 6:00 PM IST (UTC+05:30) trigger and retries if batch is incomplete.
        """
        orchestrator = WorkflowOrchestrator(self.config, mock_mode=mock_mode)
        ist_offset = timedelta(hours=self.config.utc_offset_hours)

        print("\n" + "=" * 65)
        print(f"       YT MANAGER — SCHEDULER DAEMON RUNNING")
        print("=" * 65)
        print(f"Target Schedule  : Every day at {self.config.schedule_time} IST ({self.config.timezone})")
        print(f"Retry Interval   : Every {self.config.retry_interval_minutes} minutes if clips incomplete")
        print(f"Daily Cutoff     : {self.config.daily_cutoff_time} IST")
        print(f"Polling Interval : {poll_interval_seconds}s")
        print("Press Ctrl+C to terminate daemon.\n")

        last_checked_date: Optional[str] = None

        while True:
            now_utc = datetime.now(timezone.utc)
            now_ist = now_utc + ist_offset
            today_str = now_ist.strftime("%Y-%m-%d")
            time_str = now_ist.strftime("%H:%M")

            # Check if we reached 18:00 IST or later before cutoff
            target_hour, target_min = map(int, self.config.schedule_time.split(":"))
            cutoff_hour, cutoff_min = map(int, self.config.daily_cutoff_time.split(":"))

            is_in_window = (
                (now_ist.hour > target_hour or (now_ist.hour == target_hour and now_ist.minute >= target_min))
                and (now_ist.hour < cutoff_hour or (now_ist.hour == cutoff_hour and now_ist.minute <= cutoff_min))
            )

            if is_in_window:
                # Check database to see if today's batch is completed
                batch = orchestrator.state.get_batch_for_date(today_str)
                if not batch or batch["status"] != "COMPLETED":
                    print(f"[{now_ist.strftime('%Y-%m-%d %H:%M:%S IST')}] Schedule window active. Executing daily batch...")
                    report = orchestrator.run_daily_batch(force_date=today_str)
                    print(f"Batch Execution Status: {report.execution_status}")

            time.sleep(poll_interval_seconds)
