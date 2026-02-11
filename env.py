import os
from dotenv import load_dotenv

load_dotenv()

# Taiga Configuration
TAIGA_HOST = os.getenv("TAIGA_HOST", "").rstrip('/')
TAIGA_USERNAME = os.getenv("TAIGA_USERNAME")
TAIGA_PASSWORD = os.getenv("TAIGA_PASSWORD")
PROJECT_SLUG = os.getenv("TAIGA_PROJECT_SLUG")

# Jira Configuration
CSV_FILE = os.getenv("JIRA_CSV_FILENAME")
JIRA_USER = os.getenv("JIRA_USERNAME")
JIRA_TOKEN = os.getenv("JIRA_API_TOKEN")

# General Configuration
LOG_FILE = os.getenv("LOG_FILE", "migration.log")

# Flags
DRY_RUN = os.getenv("DRY_RUN", "True").lower() == "true"
RESET_STATUSES = os.getenv("RESET_STATUSES", "False").lower() == "true"
DOWNLOAD_ATTACHMENTS = os.getenv("DOWNLOAD_ATTACHMENTS", "False").lower() == "true"

# User Mapping (Format: "Jira Name 1:Taiga Name 1, Jira Name 2:Taiga Name 2")
USER_MAPPING_RAW = os.getenv("USER_MAPPING", "")
USER_MAPPING = {}
if USER_MAPPING_RAW:
    for item in USER_MAPPING_RAW.split(','):
        if ':' in item:
            jira_name, taiga_name = item.split(':', 1)
            USER_MAPPING[jira_name.strip()] = taiga_name.strip()
