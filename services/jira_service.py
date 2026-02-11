import csv
import logging
import requests
import re
from pathlib import Path
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class JiraService:
    def __init__(self, username: str = None, api_token: str = None):
        self.username = username
        self.api_token = api_token

        self.session = requests.Session()
        if username and api_token:
            self.session.auth = (username, api_token)

        # Retry 3 times, waiting 2s, 4s, 8s between tries
        # This handles the "Read timed out" automatically
        retry_strategy = Retry(
            total=2,
            backoff_factor=2,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)

    def parse_csv(self, file_path: str):
        """Reads the CSV file and returns a list of dictionaries with unique headers."""
        try:
            with open(file_path, mode='r', encoding='utf-8-sig') as f:
                reader = csv.reader(f)
                headers = next(reader, None)
                if not headers:
                    return []

                # Make headers unique
                unique_headers = []
                counts = {}
                for header in headers:
                    if header in counts:
                        counts[header] += 1
                        unique_headers.append(f"{header}.{counts[header]}")
                    else:
                        counts[header] = 0
                        unique_headers.append(header)

                rows = []
                for row in reader:
                    rows.append(dict(zip(unique_headers, row)))

            logging.info(f"Loaded {len(rows)} rows from {file_path} 📂")
            return rows
        except FileNotFoundError:
            logging.error(f"File not found: {file_path} ❌")
            return []
        except Exception as e:
            logging.error(f"Error reading CSV: {e} ❌")
            return []

    def download_attachment(self, url: str, filename: str, target_dir: str = "attachments"):
        """Downloads an attachment from Jira with timeout protection and optimized buffering."""
        if not self.username or not self.api_token:
            logging.warning("Skipping attachment download: Missing Jira Credentials ⚠️")
            return None

        attachments_path = Path(target_dir)
        attachments_path.mkdir(exist_ok=True)
        
        # Sanitize filename (handle unicode spaces and other oddities)
        sanitized_filename = filename.replace('\u202f', ' ').strip()
        local_path = attachments_path / sanitized_filename

        try:
            with self.session.get(url, stream=True, timeout=(10, 90)) as response:

                if response.status_code != 200:
                    logging.error(f"    Download failed ({response.status_code}): {url} ❌")
                    return None

                with open(local_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            f.write(chunk)

                logging.info(f"    Downloaded: {filename} 📎")
                return local_path

        except requests.exceptions.ReadTimeout:
            logging.error(f"    TIMEOUT: Jira stopped sending data for '{filename}'. Retries failed. ❌")
            return None
        except requests.exceptions.RequestException as e:
            logging.error(f"    Network Error for {url}: {e} ❌")
            return None
        except Exception as e:
            logging.error(f"    Download error: {e} ❌")
            return None

    def convert_markup(self, body: str) -> str:
        """Converts Jira Wiki Markup to Markdown."""
        if not body:
            return ""

        # 1. Images & Attachments: !filename.png|params! -> (Attachment: filename.png)
        body = re.sub(r'!([^!|]+)(?:\|[^!]*)?!', r'(Attachment: \1)', body)

        # 2. Links: [Title|URL|params] -> [Title](URL)
        def _fix_link(match):
            inner = match.group(1)
            # Skip Jira checkboxes [ ] or [x]
            if inner == " " or inner.lower() == "x":
                return f"[{inner}]"
            
            content = inner.split('|')
            if len(content) == 1:
                return f"[{content[0]}]({content[0]})"
            return f"[{content[0]}]({content[1]})"
            
        body = re.sub(r'\[([^\]]+)\]', _fix_link, body)

        # 3. Lists: ** ->   *, *** ->     *
        # Handle '#' as bullet points too
        body = re.sub(r'^(\*\*+)\s+', lambda m: '  ' * (len(m.group(1)) - 1) + '* ', body, flags=re.MULTILINE)
        body = re.sub(r'^#\s+', '* ', body, flags=re.MULTILINE)

        # 4. Headings: h1. -> #, h2. -> ##
        body = re.sub(r'^h([1-6])\.\s+', lambda m: '#' * int(m.group(1)) + ' ', body, flags=re.MULTILINE)
        
        # 4. Text Formatting
        # Jira bold: *bold* -> Markdown bold: **bold**
        # Avoid bullet points (* item) by ensuring no space after the first asterisk 
        # and no space before the last asterisk.
        body = re.sub(r'(?<!\*)\*([^* \n](?:[^*]*?[^* \n])?)\*(?!\*)', r'**\1**', body)

        body = re.sub(r'\{\{(.+?)\}\}', r'`\1`', body)
        
        # 5. Icons / Emojis (Jira specific)
        body = body.replace('(/)', '✅').replace('(x)', '❌').replace('(!)', '⚠️')
        body = body.replace('(i)', 'ℹ️').replace('(y)', '👍').replace('(n)', '👎')

        # 6. Code blocks: {code:lang} ... {code} -> ```lang ... ```
        body = re.sub(r'\{code(?::([a-zA-Z0-9]+))?\}', r'```\1', body)
        body = body.replace('{code}', '```')
        body = re.sub(r'\{noformat\}', '```', body)

        return body

    def parse_comment(self, raw_comment: str) -> str:
        """
        Parses raw Jira CSV comment: 'Date;Author;Body'
        Converts Jira Wiki Markup to Markdown.
        """
        if not raw_comment:
            return ""

        parts = raw_comment.split(';', 2)
        if len(parts) < 3:
            # Fallback if format is unexpected
            return self.convert_markup(raw_comment)

        date, author_id, body = parts
        return self.convert_markup(body)
