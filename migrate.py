import logging
import env
import markdown
from services.jira_service import JiraService
from services.taiga_service import TaigaService

# Logging Setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler(env.LOG_FILE), logging.StreamHandler()]
)

def main():
    logging.info("Starting Migration Script 🚀")
    logging.info(f"Configurations:")
    logging.info(f"  Dry Run: {env.DRY_RUN}")
    logging.info(f"  Reset Statuses: {env.RESET_STATUSES}")
    logging.info(f"  Download Attachments: {env.DOWNLOAD_ATTACHMENTS}")

    # 1. Initialize Services
    jira_service = JiraService(username=env.JIRA_USER, api_token=env.JIRA_TOKEN)
    
    try:
        taiga_service = TaigaService(
            env.TAIGA_HOST, 
            env.TAIGA_USERNAME, 
            env.TAIGA_PASSWORD, 
            user_mapping=env.USER_MAPPING
        )
    except Exception:
        return

    # 2. Connect to Project
    try:
        project = taiga_service.connect_project(env.PROJECT_SLUG)
    except Exception:
        return

    # 3. Parse CSV
    rows = jira_service.parse_csv(env.CSV_FILE)
    if not rows:
        logging.error("No rows found. Exiting.")
        return

    # 4. Sync Statuses
    # Extract unique statuses
    unique_statuses = set(row.get('Status') for row in rows if row.get('Status'))
    
    # Sync (Reset if flag is True)
    taiga_statuses = taiga_service.sync_statuses(
        unique_statuses, 
        reset=env.RESET_STATUSES, 
        dry_run=env.DRY_RUN
    )

    # 5. Process Rows
    stats = {"success": 0, "failed": 0}
    total_rows = len(rows)

    logging.info(f"--- Processing {total_rows} User Stories 🔄 ---")

    for i, row in enumerate(rows, 1):
        summary = row.get('Summary', 'No Title')
        raw_status = row.get('Status')
        status_slug = taiga_service.slugify(raw_status) if raw_status else None
        
        status_id = taiga_statuses.get(status_slug)
        assignee = row.get('Assignee')
        raw_description = row.get('Description', '')
        # 1. Convert Jira Markup to Markdown
        description_md = jira_service.convert_markup(raw_description)
        # 2. Convert Markdown to HTML for Taiga
        description = markdown.markdown(description_md)
        points_val = row.get('Custom field (Story point estimate)')
        
        # Comments
        comments = []
        for key, value in row.items():
            if value and ('Comment' in key or key.startswith('Comment')):
                parsed = jira_service.parse_comment(value)
                if parsed:
                    comments.append(parsed)

        if i % 5 == 0: print(f"Processing {i}/{total_rows}...")

        if env.DRY_RUN:
            # For detailed dry-run, find attachments and comments
            attachments = [v for k, v in row.items() if k.startswith('Attachment') and v]
            logging.info(f"[DRY RUN] {summary[:40]}... | Status: {raw_status} | Assignee: {assignee} | Attachments: {len(attachments)} | Comments: {len(comments)}")
            continue

        try:
            # Create Story
            story = taiga_service.create_story(
                title=summary,
                description=description,
                status_id=status_id,
                assignee_full_name=assignee,
                points_value=points_val,
                comment_map=comments
            )

            # Handle Attachments
            if env.DOWNLOAD_ATTACHMENTS:
                # Find all attachment columns
                attachment_cols = [v for k, v in row.items() if k.startswith('Attachment') and v]
                
                for attachment_field in attachment_cols:
                    # Expected format: "date;author;filename;url"
                    parts = attachment_field.split(';')
                    if len(parts) >= 4:
                        att_url = parts[-1]
                        att_filename = parts[2]
                        
                        local_file = jira_service.download_attachment(att_url, att_filename)
                        if local_file:
                            taiga_service.attach_file(story, local_file)
                            local_file.unlink()

            logging.info(f"Created: {summary} 🚀")
            stats["success"] += 1

        except Exception as e:
             # Error logged in service usually, but catch here to continue
            stats["failed"] += 1

    logging.info(f"\n--- FINAL SUMMARY ---")
    logging.info(f"Success: {stats['success']} ✅")
    logging.info(f"Failed:  {stats['failed']} ❌")

if __name__ == "__main__":
    main()