"""
DevTeam plugin CLI command integration.

This module provides command-line interface for the DevTeam plugin.
"""

import argparse
import json
import logging
import sys
from typing import Any, Dict, List, Optional, TextIO, Union

logger = logging.getLogger(__name__)


def add_devteam_commands(subparsers) -> None:
    """
    Add DevTeam plugin commands to the CLI parser.

    Args:
        subparsers: The subparsers object from the main parser.
    """
    # Submit task command
    submit_parser = subparsers.add_parser(
        "task:submit", help="Submit a new task to DevTeam"
    )
    submit_parser.add_argument("--type", "-t", help="Task type", required=True)
    submit_parser.add_argument("--title", help="Task title", required=True)
    submit_parser.add_argument("--description", help="Task description", required=True)
    submit_parser.add_argument("--priority", help="Task priority", default="medium")
    submit_parser.add_argument("--tags", help="Task tags (comma-separated)")

    # List tasks command
    list_parser = subparsers.add_parser("task:list", help="List all tasks")
    list_parser.add_argument("--status", help="Filter by status")
    list_parser.add_argument("--type", help="Filter by type")
    list_parser.add_argument("--priority", help="Filter by priority")

    # Get task status command
    status_parser = subparsers.add_parser("task:status", help="Get task status")
    status_parser.add_argument("--id", help="Task ID", required=True)

    # Cancel task command
    cancel_parser = subparsers.add_parser("task:cancel", help="Cancel a task")
    cancel_parser.add_argument("--id", help="Task ID", required=True)

    # Start workflow command
    workflow_start_parser = subparsers.add_parser(
        "workflow:start", help="Start a workflow"
    )
    workflow_start_parser.add_argument(
        "--template", help="Workflow template", required=True
    )
    workflow_start_parser.add_argument("--name", help="Workflow name", required=True)
    workflow_start_parser.add_argument("--params", help="Workflow parameters (JSON)")

    # List workflows command
    workflow_list_parser = subparsers.add_parser(
        "workflow:list", help="List all workflows"
    )
    workflow_list_parser.add_argument("--status", help="Filter by status")

    # Get workflow status command
    workflow_status_parser = subparsers.add_parser(
        "workflow:status", help="Get workflow status"
    )
    workflow_status_parser.add_argument("--id", help="Workflow ID", required=True)

    # Progress monitoring command
    progress_parser = subparsers.add_parser(
        "progress", help="Monitor progress of tasks and workflows"
    )
    progress_parser.add_argument("--task-id", help="Task ID to monitor")
    progress_parser.add_argument("--workflow-id", help="Workflow ID to monitor")
    progress_parser.add_argument(
        "--watch",
        "-w",
        help="Watch mode - continuously update progress",
        action="store_true",
    )
    progress_parser.add_argument(
        "--interval",
        "-i",
        help="Update interval in seconds (for watch mode)",
        type=int,
        default=5,
    )

    # Prompt metrics command
    prompt_metrics_parser = subparsers.add_parser(
        "prompt:metrics", help="Get prompt optimization metrics"
    )

    # Start prompt experiment command
    prompt_experiment_parser = subparsers.add_parser(
        "prompt:experiment", help="Start a prompt optimization experiment"
    )
    prompt_experiment_parser.add_argument(
        "--agent-type", help="Agent type", required=True
    )
    prompt_experiment_parser.add_argument(
        "--variations", help="Number of variations to test", type=int, default=2
    )


def handle_devteam_command(args: argparse.Namespace, client) -> None:
    """
    Handle DevTeam plugin commands.

    Args:
        args: Command line arguments.
        client: AIxTerm client instance.
    """
    command = args.command

    if command == "task:submit":
        _handle_task_submit(args, client)
    elif command == "task:list":
        _handle_task_list(args, client)
    elif command == "task:status":
        _handle_task_status(args, client)
    elif command == "task:cancel":
        _handle_task_cancel(args, client)
    elif command == "workflow:start":
        _handle_workflow_start(args, client)
    elif command == "workflow:list":
        _handle_workflow_list(args, client)
    elif command == "workflow:status":
        _handle_workflow_status(args, client)
    elif command == "progress":
        _handle_progress_monitoring(args, client)
    elif command == "prompt:metrics":
        _handle_prompt_metrics(args, client)
    elif command == "prompt:experiment":
        _handle_prompt_experiment(args, client)
    else:
        logger.error(f"Unknown command: {command}")
        sys.exit(1)


def _handle_task_submit(args: argparse.Namespace, client) -> None:
    """
    Handle task submission command.

    Args:
        args: Command line arguments.
        client: AIxTerm client instance.
    """
    # Prepare parameters
    parameters = {
        "type": args.type,
        "title": args.title,
        "description": args.description,
        "priority": args.priority,
    }

    if args.tags:
        parameters["tags"] = [tag.strip() for tag in args.tags.split(",")]

    # Send command to plugin
    response = client.send_plugin_command("devteam", "devteam:submit", parameters)

    # Process response
    if response.get("success"):
        task_id = response.get("task_id")
        print(f"Task submitted successfully. Task ID: {task_id}")
    else:
        print(f"Error submitting task: {response.get('error')}")


def _handle_task_list(args: argparse.Namespace, client) -> None:
    """
    Handle task listing command.

    Args:
        args: Command line arguments.
        client: AIxTerm client instance.
    """
    # Prepare parameters
    parameters = {}

    if args.status:
        parameters["status"] = args.status

    if args.type:
        parameters["type"] = args.type

    if args.priority:
        parameters["priority"] = args.priority

    # Send command to plugin
    response = client.send_plugin_command("devteam", "devteam:list", parameters)

    # Process response
    if response.get("success"):
        tasks = response.get("tasks", [])
        if tasks:
            print(f"Found {len(tasks)} tasks:")
            for task in tasks:
                print(
                    f"- ID: {task['id']}, Title: {task['title']}, "
                    f"Status: {task['status']}, Type: {task['type']}, "
                    f"Priority: {task['priority']}"
                )
        else:
            print("No tasks found.")
    else:
        print(f"Error listing tasks: {response.get('error')}")


def _handle_task_status(args: argparse.Namespace, client) -> None:
    """
    Handle task status command.

    Args:
        args: Command line arguments.
        client: AIxTerm client instance.
    """
    # Prepare parameters
    parameters = {"task_id": args.id}

    # Send command to plugin
    response = client.send_plugin_command("devteam", "devteam:status", parameters)

    # Process response
    if response.get("success"):
        task = response.get("task")
        if task:
            print(f"Task ID: {task['id']}")
            print(f"Title: {task['title']}")
            print(f"Status: {task['status']}")
            print(f"Type: {task['type']}")
            print(f"Priority: {task['priority']}")
            print(f"Created: {task.get('created_at')}")
            print(f"Updated: {task.get('updated_at')}")

            if "progress" in task:
                print(f"Progress: {task['progress']}%")

            if "steps" in task:
                print("\nSteps:")
                for step in task["steps"]:
                    status_marker = "✓" if step["completed"] else " "
                    print(f"  [{status_marker}] {step['name']}")
        else:
            print(f"Task not found with ID: {args.id}")
    else:
        print(f"Error getting task status: {response.get('error')}")


def _handle_task_cancel(args: argparse.Namespace, client) -> None:
    """
    Handle task cancellation command.

    Args:
        args: Command line arguments.
        client: AIxTerm client instance.
    """
    # Prepare parameters
    parameters = {"task_id": args.id}

    # Send command to plugin
    response = client.send_plugin_command("devteam", "devteam:cancel", parameters)

    # Process response
    if response.get("success"):
        print(f"Task {args.id} cancelled successfully.")
    else:
        print(f"Error cancelling task: {response.get('error')}")


def _handle_workflow_start(args: argparse.Namespace, client) -> None:
    """
    Handle workflow start command.

    Args:
        args: Command line arguments.
        client: AIxTerm client instance.
    """
    # Prepare parameters
    parameters = {
        "template": args.template,
        "name": args.name,
    }

    if args.params:
        try:
            parameters["params"] = json.loads(args.params)
        except json.JSONDecodeError:
            print("Error: Invalid JSON in params")
            sys.exit(1)

    # Send command to plugin
    response = client.send_plugin_command(
        "devteam", "devteam:workflow:start", parameters
    )

    # Process response
    if response.get("success"):
        workflow_id = response.get("workflow_id")
        print(f"Workflow started successfully. Workflow ID: {workflow_id}")
    else:
        print(f"Error starting workflow: {response.get('error')}")


def _handle_workflow_list(args: argparse.Namespace, client) -> None:
    """
    Handle workflow listing command.

    Args:
        args: Command line arguments.
        client: AIxTerm client instance.
    """
    # Prepare parameters
    parameters = {}

    if args.status:
        parameters["status"] = args.status

    # Send command to plugin
    response = client.send_plugin_command(
        "devteam", "devteam:workflow:list", parameters
    )

    # Process response
    if response.get("success"):
        workflows = response.get("workflows", [])
        if workflows:
            print(f"Found {len(workflows)} workflows:")
            for workflow in workflows:
                steps_completed = workflow.get("steps_completed", 0)
                steps_total = workflow.get("steps_total", 0)
                progress = f"{steps_completed}/{steps_total} steps"

                print(
                    f"- ID: {workflow['id']}, Name: {workflow['name']}, "
                    f"Status: {workflow['status']}, Progress: {progress}"
                )
        else:
            print("No workflows found.")
    else:
        print(f"Error listing workflows: {response.get('error')}")


def _handle_workflow_status(args: argparse.Namespace, client) -> None:
    """
    Handle workflow status command.

    Args:
        args: Command line arguments.
        client: AIxTerm client instance.
    """
    # Prepare parameters
    parameters = {"workflow_id": args.id}

    # Send command to plugin
    response = client.send_plugin_command(
        "devteam", "devteam:workflow:status", parameters
    )

    # Process response
    if response.get("success"):
        workflow = response.get("workflow")
        if workflow:
            print(f"Workflow ID: {workflow['id']}")
            print(f"Name: {workflow['name']}")
            print(f"Status: {workflow['status']}")
            print(f"Created: {workflow.get('start_time')}")

            steps_completed = workflow.get("steps_completed", 0)
            steps_total = workflow.get("steps_total", 0)
            print(f"Progress: {steps_completed}/{steps_total} steps")

            if "steps" in workflow:
                print("\nSteps:")
                for step in workflow["steps"]:
                    status = step.get("status", "pending")
                    status_marker = "✓" if status == "completed" else " "
                    print(f"  [{status_marker}] {step['name']}")

                    if "agent" in step:
                        print(f"      Agent: {step['agent']}")

                    if status == "failed" and "error" in step:
                        print(f"      Error: {step['error']}")
        else:
            print(f"Workflow not found with ID: {args.id}")
    else:
        print(f"Error getting workflow status: {response.get('error')}")


def _handle_progress_monitoring(args: argparse.Namespace, client) -> None:
    """
    Handle progress monitoring command.

    Args:
        args: Command line arguments.
        client: AIxTerm client instance.
    """
    if args.task_id:
        _monitor_task_progress(args.task_id, args.watch, args.interval, client)
    elif args.workflow_id:
        _monitor_workflow_progress(args.workflow_id, args.watch, args.interval, client)
    else:
        print("Error: Please specify either --task-id or --workflow-id")
        sys.exit(1)


def _monitor_task_progress(task_id: str, watch: bool, interval: int, client) -> None:
    """
    Monitor task progress.

    Args:
        task_id: ID of the task to monitor.
        watch: Whether to continuously monitor.
        interval: Update interval in seconds.
        client: AIxTerm client instance.
    """
    import os
    import time

    try:
        while True:
            # Clear screen for watch mode
            if watch:
                os.system("cls" if os.name == "nt" else "clear")
                print(f"Monitoring task {task_id} (Press Ctrl+C to stop)...\n")

            # Get task status
            response = client.send_plugin_command(
                "devteam", "devteam:status", {"task_id": task_id}
            )

            # Process response
            if response.get("success"):
                task = response.get("task")
                if task:
                    print(f"Task ID: {task['id']}")
                    print(f"Title: {task['title']}")
                    print(f"Status: {task['status']}")

                    if "progress" in task:
                        print(f"Progress: {task['progress']}%")
                        _draw_progress_bar(task["progress"])

                    if "steps" in task:
                        print("\nSteps:")
                        for step in task["steps"]:
                            status_marker = "✓" if step["completed"] else " "
                            print(f"  [{status_marker}] {step['name']}")
                else:
                    print(f"Task not found with ID: {task_id}")
            else:
                print(f"Error getting task status: {response.get('error')}")

            # Exit if not in watch mode
            if not watch:
                break

            # Wait for next update
            time.sleep(interval)

    except KeyboardInterrupt:
        print("\nMonitoring stopped.")


def _monitor_workflow_progress(
    workflow_id: str, watch: bool, interval: int, client
) -> None:
    """
    Monitor workflow progress.

    Args:
        workflow_id: ID of the workflow to monitor.
        watch: Whether to continuously monitor.
        interval: Update interval in seconds.
        client: AIxTerm client instance.
    """
    import os
    import time

    try:
        while True:
            # Clear screen for watch mode
            if watch:
                os.system("cls" if os.name == "nt" else "clear")
                print(f"Monitoring workflow {workflow_id} (Press Ctrl+C to stop)...\n")

            # Get workflow status
            response = client.send_plugin_command(
                "devteam", "devteam:workflow:status", {"workflow_id": workflow_id}
            )

            # Process response
            if response.get("success"):
                workflow = response.get("workflow")
                if workflow:
                    print(f"Workflow ID: {workflow['id']}")
                    print(f"Name: {workflow['name']}")
                    print(f"Status: {workflow['status']}")

                    steps_completed = workflow.get("steps_completed", 0)
                    steps_total = workflow.get("steps_total", 0)
                    if steps_total > 0:
                        progress = int((steps_completed / steps_total) * 100)
                        print(
                            f"Progress: {steps_completed}/{steps_total} steps ({progress}%)"
                        )
                        _draw_progress_bar(progress)

                    if "steps" in workflow:
                        print("\nSteps:")
                        for step in workflow["steps"]:
                            status = step.get("status", "pending")
                            status_marker = "✓" if status == "completed" else " "
                            print(f"  [{status_marker}] {step['name']}")

                            if "agent" in step:
                                print(f"      Agent: {step['agent']}")

                            if "start_time" in step and "end_time" in step:
                                duration = step.get("duration", "unknown")
                                print(f"      Duration: {duration}")

                            if status == "failed" and "error" in step:
                                print(f"      Error: {step['error']}")
                else:
                    print(f"Workflow not found with ID: {workflow_id}")
            else:
                print(f"Error getting workflow status: {response.get('error')}")

            # Exit if not in watch mode
            if not watch:
                break

            # Wait for next update
            time.sleep(interval)

    except KeyboardInterrupt:
        print("\nMonitoring stopped.")


def _handle_prompt_metrics(args: argparse.Namespace, client) -> None:
    """
    Handle prompt metrics command.

    Args:
        args: Command line arguments.
        client: AIxTerm client instance.
    """
    # Send command to plugin
    response = client.send_plugin_command("devteam", "devteam:prompt:metrics", {})

    # Process response
    if response.get("success"):
        metrics = response.get("metrics", {})

        print("Prompt Optimization Metrics:\n")

        # Print agent type metrics
        agent_types = metrics.get("agent_types", {})
        for agent_type, data in agent_types.items():
            print(f"{agent_type}:")
            print(f"  Current template: {data.get('has_template', False)}")
            print(f"  In experiment: {data.get('in_experiment', False)}")

            templates = data.get("templates", [])
            if templates:
                print(f"  Templates: {len(templates)}")

                # Sort by efficiency score
                sorted_templates = sorted(
                    templates, key=lambda t: t.get("efficiency_score", 0), reverse=True
                )

                for i, template in enumerate(sorted_templates[:3]):
                    name = template.get("template_name", "unknown")
                    success_rate = template.get("usage", {}).get("success_rate", 0)
                    efficiency = template.get("efficiency_score", 0)

                    print(
                        f"    {i+1}. {name}: {success_rate:.1f}% success, {efficiency:.1f} efficiency"
                    )

            print()

        # Print experiment status
        experiments = metrics.get("active_experiments", [])
        if experiments:
            print(f"Active experiments: {', '.join(experiments)}")
        else:
            print("No active experiments")
    else:
        print(f"Error getting prompt metrics: {response.get('error')}")


def _handle_prompt_experiment(args: argparse.Namespace, client) -> None:
    """
    Handle prompt experiment command.

    Args:
        args: Command line arguments.
        client: AIxTerm client instance.
    """
    # Prepare parameters
    parameters = {"agent_type": args.agent_type, "variations": args.variations}

    # Send command to plugin
    response = client.send_plugin_command(
        "devteam", "devteam:prompt:experiment", parameters
    )

    # Process response
    if response.get("success"):
        print(response.get("message", "Experiment started successfully"))
    else:
        print(f"Error starting experiment: {response.get('error')}")


def _draw_progress_bar(percent: int, width: int = 40) -> None:
    """
    Draw a progress bar.

    Args:
        percent: Progress percentage.
        width: Width of the progress bar.
    """
    filled = int(width * percent / 100)
    bar = "█" * filled + "░" * (width - filled)
    print(f"[{bar}] {percent}%")
