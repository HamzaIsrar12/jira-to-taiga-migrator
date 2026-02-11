import logging
import time
import re
from taiga import TaigaAPI

class TaigaService:
    def __init__(self, host, username, password, user_mapping=None):
        self.api = TaigaAPI(host=host)
        try:
            self.api.auth(username, password)
            logging.info(f"Authenticated with Taiga as {username} ✅")
        except Exception as e:
            logging.error(f"Taiga Auth Failed: {e} ❌")
            raise e
        self.project = None
        self.users_cache = {}
        self.roles_cache = {}
        self.statuses_cache = {}
        self.manual_user_map = user_mapping or {}

    def connect_project(self, project_slug):
        try:
            self.project = self.api.projects.get_by_slug(project_slug)
            logging.info(f"Connected to Project: {self.project.name} (ID: {self.project.id}) ✅")
            
            # Cache metadata
            memberships = self.project.list_memberships()
            self.users_cache = {}
            for m in memberships:
                # Store by full name and username if available
                if m.full_name:
                    self.users_cache[m.full_name] = m.user
                # Some memberships might have username directly or via user object
                try:
                    user_obj = self.api.users.get(m.user)
                    if user_obj.username:
                        self.users_cache[f"@{user_obj.username}"] = m.user
                        self.users_cache[user_obj.username] = m.user
                except:
                    pass
            # Current statuses
            self.statuses_cache = {s.slug: s.id for s in self.project.us_statuses}
            
            return self.project
        except Exception as e:
            logging.error(f"Connection Failed to {project_slug}: {e} ❌")
            raise e

    def slugify(self, text):
        text = text.lower()
        return re.sub(r'[^a-z0-9]+', '-', text).strip('-')

    def sync_statuses(self, csv_statuses, reset=False, dry_run=False):
        if not self.project:
            raise Exception("Project not connected")

        logging.info("--- Synchronizing Statuses 🔄 ---")
        
        if dry_run:
            logging.info(f"[DRY RUN] Would sync statuses. Reset={reset}. New: {csv_statuses}")
            # Return a fake mapping
            return {self.slugify(s): 1 for s in csv_statuses}

        if reset:
            logging.info("Reset enabled: Deleting existing statuses... 🗑️")
            for status in self.project.us_statuses:
                try:
                    status.delete()
                    logging.info(f"   Deleted: {status.name}")
                except Exception as e:
                    logging.warning(f"   Could not delete {status.name} (might be in use): {e}")

        # Create new statuses
        # Re-fetch statuses to be sure
        
        status_map = {}
        colors = ["#70728F", "#E47C40", "#A58C43", "#DA6095", "#8E44AD", "#2ECC71", "#3498DB"]

        for i, name in enumerate(csv_statuses):
            slug = self.slugify(name)
            is_closed = name.lower() in ["done", "dev done", "closed", "ready for prod"]
            color = colors[i % len(colors)]

            # Check if exists
            # We can't easily check blindly because sync might mean update or ignore
            # But let's check current slugs again
            found = next((s for s in self.project.us_statuses if s.slug == slug), None)
            
            if found:
                status_map[slug] = found.id
            else:
                try:
                    new_status = self.project.add_user_story_status(
                        name=name, slug=slug, is_closed=is_closed, color=color
                    )
                    status_map[slug] = new_status.id
                    logging.info(f"Created status: {name} ✨")
                except Exception as e:
                    logging.error(f"Failed to create status {name}: {e} ❌")
        
        self.statuses_cache = status_map # Update cache
        return status_map

    def create_story(self, title, description, status_id, assignee_full_name, points_value=None, comment_map=None, dry_run=False):
        if dry_run:
            logging.info(f"[DRY RUN] Create Story: {title[:30]}... | StatusID: {status_id}")
            return None

        # Assignee lookup
        assignee_id = self.users_cache.get(assignee_full_name)
        
        if not assignee_id and assignee_full_name:
            # Try manual mapping
            mapped_name = self.manual_user_map.get(assignee_full_name)
            if mapped_name:
                assignee_id = self.users_cache.get(mapped_name)
            
            # Try fuzzy matching (case insensitive, partial) if still not found
            if not assignee_id:
                for cached_name, uid in self.users_cache.items():
                    if assignee_full_name.lower() in cached_name.lower() or cached_name.lower() in assignee_full_name.lower():
                        assignee_id = uid
                        break
        
        try:
            story = self.project.add_user_story(
                subject=title,
                description=description,
                status=status_id,
                assigned_to=assignee_id
            )
            
            # Points
            if points_value and self.project.roles:
                role = self.project.roles[0] 
                p_obj = next((p for p in self.project.points if str(p.value) == str(points_value)), None)
                if p_obj:
                    story.update(points={str(role.id): p_obj.id})
            
            # Comments
            if comment_map:
                for txt in comment_map:
                    story.add_comment(txt)
            
            time.sleep(0.1) 
            return story

        except Exception as e:
            logging.error(f"Failed to create story '{title}': {e} ❌")
            raise e

    def attach_file(self, story, file_path):
        if story and file_path:
            story.attach(str(file_path))
