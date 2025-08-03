# DevTeam Plugin Tutorial

This tutorial will guide you through using the DevTeam plugin to manage software development tasks with AIxTerm.

## Prerequisites

- AIxTerm installed and running
- Basic familiarity with AIxTerm command-line interface

## Step 1: Check Plugin Status

First, let's check if the DevTeam plugin is loaded:

```bash
ai plugin:list
```

You should see "DevTeam" in the list of loaded plugins.

If the plugin is not loaded, you can load it with:

```bash
ai plugin:load devteam
```

## Step 2: Submit Your First Task

Let's create a simple development task:

```bash
ai devteam:submit --title "Hello World Feature" --description "Create a simple Hello World function that returns a greeting message"
```

The system will respond with a task ID, which you'll use to track and manage the task:

```
Task submitted successfully: task_20250715123045
```

## Step 3: Check Task Status

Now let's check the status of our task:

```bash
ai devteam:status --task_id task_20250715123045
```

This will show you detailed information about the task, including its current status, progress, and other metadata.

## Step 4: List All Tasks

To see all your tasks:

```bash
ai devteam:list
```

You can filter by status:

```bash
ai devteam:list --status in_progress
```

## Step 5: Cancel a Task

If you need to cancel a task:

```bash
ai devteam:cancel --task_id task_20250715123045
```

## Step 6: Working with Different Task Types

The DevTeam plugin supports various task types. Let's try submitting a bug fix:

```bash
ai devteam:submit --title "Fix Null Pointer Bug" --description "Fix null pointer exception when user profile is empty" --type bugfix --priority high
```

And a documentation task:

```bash
ai devteam:submit --title "Update API Docs" --description "Update API documentation with new endpoints" --type documentation --priority medium
```

## Step 7: Understanding Task Workflow

Tasks in the DevTeam plugin follow a specific workflow:

1. **Submitted**: Task is initially received
2. **Queued**: Task is waiting to be processed
3. **Planning**: AI agents are planning the implementation
4. **In Progress**: Development work is being done
5. **Under Review**: Code review is taking place
6. **Testing**: Code is being tested
7. **Completed**: Task is successfully finished
8. **Failed**: Task encountered an error
9. **Cancelled**: Task was manually cancelled

You can track a task's progress through these stages using the status command.

## Step 8: Advanced Configuration

The DevTeam plugin can be configured in your AIxTerm configuration file. Create or edit your config file:

```bash
ai config:edit
```

And add the DevTeam plugin configuration:

```json
{
  "plugins": {
    "devteam": {
      "max_concurrent_tasks": 5,
      "agents": {
        "project_manager": { "enabled": true, "max_tasks": 10 },
        "developer": { "enabled": true, "instances": 2 }
      },
      "workflow": {
        "require_code_review": true,
        "parallel_development": true
      }
    }
  }
}
```

Save the file and restart AIxTerm to apply the changes.

## Step 9: Plugin Integration

The DevTeam plugin can be extended to work with other AIxTerm plugins. For example, if you have a version control plugin installed, the DevTeam can automatically create branches and commit changes.

This integration capability will be expanded in future updates.

## Next Steps

Now that you've learned the basics of the DevTeam plugin, you can:

1. Create more complex tasks with detailed specifications
2. Customize the plugin configuration to match your workflow
3. Explore advanced features like agent assignment and priority management

For more information, see the [DevTeam Plugin API Reference](./API.md) and [README](./README.md).
