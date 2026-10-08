"""Plain Markdown prompts; reading their text never executes instructions."""

import os
import re
import stat
import tempfile
from pathlib import Path

from platformdirs import user_data_path

from invest.models import DomainError

MAX_PROMPT_BYTES = 64 * 1024
DEFAULTS = Path(__file__).parent / "prompt_defaults"


class PromptLibrary:
    def __init__(self, directory=None):
        self.directory = Path(
            directory if directory is not None else
            os.environ.get("INVEST_PROMPTS", user_data_path("investobot") / "prompts")
        ).absolute()

    def _validate_directory(self):
        if self.directory == DEFAULTS.absolute() or DEFAULTS.absolute() in self.directory.parents:
            raise DomainError("User prompt storage must be separate from bundled defaults")
        for path in (*reversed(self.directory.parents), self.directory):
            if path.is_symlink():
                raise DomainError("Prompt directory must not contain symlinks")
            if path.exists() and not path.is_dir():
                raise DomainError("Prompt storage must be a directory")

    def _path(self, slug):
        if not isinstance(slug, str) or not re.fullmatch(r"[a-z][a-z0-9-]{0,63}", slug):
            raise DomainError("Prompt ID must be a lowercase slug of at most 64 characters")
        self._validate_directory()
        path = self.directory / f"{slug}.md"
        if path.is_symlink() or (path.exists() and not path.is_file()):
            raise DomainError("Prompt must be a regular file, never a symlink")
        return path

    def _read(self, path):
        try:
            descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(descriptor, "rb") as stream:
                if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                    raise DomainError("Prompt must be a regular file")
                content = stream.read(MAX_PROMPT_BYTES + 1)
            if len(content) > MAX_PROMPT_BYTES:
                raise DomainError("Prompt text exceeds the 64 KiB limit")
            return content.decode("utf-8")
        except (OSError, UnicodeError) as exc:
            raise DomainError("Prompt cannot be read as a local UTF-8 document") from exc

    def list(self):
        self._validate_directory()
        slugs = {path.stem for path in DEFAULTS.glob("*.md")}
        if self.directory.exists():
            slugs.update(path.stem for path in self.directory.glob("*.md"))
        return [self.show(slug) for slug in sorted(slugs)]

    def show(self, slug):
        user = self._path(slug)
        bundled = DEFAULTS / f"{slug}.md"
        if user.exists():
            content, source = self._read(user), "user"
        elif bundled.is_file():
            content, source = self._read(bundled), "bundled"
        else:
            raise DomainError("Prompt does not exist")
        title = next((line[2:].strip() for line in content.splitlines() if line.startswith("# ")), slug)
        return {
            "id": slug, "title": title, "content": content, "source": source,
            "bundled_available": bundled.is_file(),
        }

    def save(self, slug, content):
        destination = self._path(slug)
        if not isinstance(content, str) or not content.strip():
            raise DomainError("Prompt must contain nonempty Markdown text")
        try:
            payload = content.encode("utf-8")
        except UnicodeError as exc:
            raise DomainError("Prompt text must be valid UTF-8") from exc
        if len(payload) > MAX_PROMPT_BYTES:
            raise DomainError("Prompt text exceeds the 64 KiB limit")
        temporary = None
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            self._path(slug)
            with tempfile.NamedTemporaryFile(dir=self.directory, prefix=".prompt-", delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            self._path(slug)
            os.replace(temporary, destination)
        except OSError as exc:
            raise DomainError("Prompt cannot be saved in the configured directory") from exc
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        return self.show(slug)

    def delete(self, slug):
        path = self._path(slug)
        if not path.exists():
            raise DomainError("Only user-created prompts or user overrides can be deleted")
        try:
            path.unlink()
        except OSError as exc:
            raise DomainError("Prompt cannot be deleted from the configured directory") from exc
        return {"id": slug, "deleted": True, "bundled_restored": (DEFAULTS / f"{slug}.md").is_file()}
