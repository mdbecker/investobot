# Local prompt library

Prompts are plain UTF-8 Markdown for copying into an external agent. Investobot displays and stores their text; it never executes instructions. Bundled topics cover loss harvesting, concentration, fund comparisons, stocks, bonds, target generation, rebalancing, alternative portfolios, and recent developments.

The library uses `INVEST_PROMPTS`, or the `investobot` platform data directory's `prompts` subdirectory by default. An explicit directory supplied to the domain API takes precedence. For Docker persistence, set `INVEST_PROMPTS=/data/prompts` on the app service to use its existing named data volume. No credentials or external APIs are needed for prompt storage.

Prompt IDs are lowercase slugs beginning with a letter, using letters, digits, and hyphens, up to 64 characters. User documents are stored as `<id>.md`, with a 64 KiB UTF-8 limit. Symlink paths, nonregular files, traversal, and invalid IDs are rejected. Reads do not create directories; saves create the selected directory and replace files atomically.

Saving an existing bundled ID creates a user override. Bundled documents remain unchanged in the installed package. Deleting the override restores the original default; deleting a bundled original is rejected. User-only prompts can be created, edited, and deleted. Markdown content is returned in full for copying and must be displayed as text.

The shared domain API is `PromptLibrary(directory=None)`, with `list()`, `show(id)`, `save(id, content)`, and `delete(id)`. Reads return `id`, `title`, `content`, `source` (`bundled` or `user`), and `bundled_available`. Deletion returns `id`, `deleted`, and `bundled_restored`.

`executive-political-contributions` bundles the external research workflow and
strict JSON contract. The existing Prompt Library displays and copies it; it
never runs research. The [political research guide](political-research.md) explains
source-use review and import requirements.
