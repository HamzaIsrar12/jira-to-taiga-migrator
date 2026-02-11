# Jira to Taiga Migration Script

This tool migrates user stories, tasks, comments, and attachments from a Jira CSV export to a Taiga project.

## Prerequisites

1.  **Python**: This project uses `pyenv` to manage Python versions.
    ```bash
    pyenv install  # Installs version from .python-version
    ```
2.  **Virtual Environment**:
    ```bash
    python -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    ```
3.  **Configuration**:
    Copy the local environment template:
    ```bash
    cp .env.local .env
    ```
    Then edit `.env` with your actual credentials.

4.  **Taiga Project**: Create a new empty project in Taiga.
5.  **Team Members**: **CRITICAL:** You must add all team members to the Taiga project *before* running this script. The script maps Jira assignees to Taiga users by their full name. If a user is not found in the Taiga project, the story will be unassigned.

## Usage

1.  **Prepare CSV**: Export your Jira project to CSV. Ensure it includes "Summary", "Description", "Status", "Assignee", "Attachment", and "Comment" fields.
2.  **Dry Run**: Run the script with `DRY_RUN=True` to verify connection and data parsing.
    ```bash
    python3 migrate.py
    ```
3.  **Migrate**: Set `DRY_RUN=False` in `.env` and run the script again.

## Features

- **Status Sync**: Automatically creates statuses found in the CSV if `RESET_STATUSES=True`.
- **Comments**: Parses Jira comments and converts Jira markup to Markdown.
- **User Mapping**: Supports manual name overrides via `USER_MAPPING` in `.env` and fuzzy matching.
- **HTML Descriptions**: Automatically converts Jira/Markdown descriptions to HTML for rich rendering in Taiga.
- **Attachments**: Downloads files using Jira credentials and uploads them to the corresponding Taiga story.

## Configuration Details

### User Mapping
If team members have different display names in Jira and Taiga, you can map them in the `.env` file using the `USER_MAPPING` variable:
```text
USER_MAPPING=Jira Name:Taiga Name, Another Jira Name:Taiga Username
```
The script will also attempt fuzzy matching if no exact override is found.
