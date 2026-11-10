# Copyright 2026 Cetmix OÜ
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from urllib.parse import quote

import requests
from requests.exceptions import RequestException

from odoo import api, models
from odoo.exceptions import UserError

GITHUB_API_URL = "https://api.github.com"
GITHUB_API_VERSION = "2026-03-10"
GITHUB_PAGE_SIZE = 100


class CxTowerGitRemote(models.Model):
    """GitHub head suggestions for a github.com repository."""

    _inherit = "cx.tower.git.remote"

    def _git_fetch_heads_github(
        self, repo, head_type, query, server=None, partner=None
    ):
        """Return one page of GitHub suggestions for ``head_type``.

        A host other than github.com returns an empty list before any token
        or HTTP call. The typed text is not sent to GitHub. It only filters
        the page that was returned.

        Args:
            repo (cx.tower.git.repo): Repository to list.
            head_type (str): ``branch``, ``pr``, or ``commit``.
            query (str | bool): Trimmed input, or ``False`` on focus.
            server (cx.tower.server | None): Server for the secret.
            partner (res.partner | None): Partner for the secret.

        Raises:
            UserError: When no secret resolves, GitHub cannot be reached,
                the response is not HTTP 200, or a HTTP 200 body is not a
                JSON list.

        Returns:
            list[dict]: Rows ``{"head": "<value>"}``. A pull request value
            is the number and title. A commit SHA longer than 7 characters
            is sent in ``head_reference``, and ``head`` is its first 7
            characters plus the subject. The token is not included.
        """
        if repo.host != "github.com":
            return []
        token = self._git_head_api_token(repo, server, partner)
        url, params, value_key = self._git_github_request(repo, head_type)
        if not url:
            return []
        try:
            response = requests.get(
                url,
                params=params,
                headers={
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": GITHUB_API_VERSION,
                    "Authorization": f"Bearer {token}",
                },
                timeout=10,
            )
        except RequestException as error:
            raise UserError(self.env._("GitHub could not be reached.")) from error
        if response.status_code != 200:
            raise UserError(self._git_github_error_message(response))
        try:
            payload = response.json()
        except ValueError as error:
            raise UserError(
                self.env._("GitHub returned an unexpected response.")
            ) from error
        if not isinstance(payload, list):
            raise UserError(self.env._("GitHub returned an unexpected response."))
        suggestions = []
        for item in payload:
            suggestion = self._git_github_suggestion(item, value_key)
            if not suggestion:
                continue
            row = {"head": suggestion}
            if value_key == "sha" and isinstance(item, dict):
                sha = item.get("sha")
                if isinstance(sha, str) and len(sha) > 7:
                    row["head_reference"] = sha
                elif isinstance(sha, str) and sha:
                    row = {"head": sha}
            visible = row["head"]
            if query and not self._git_github_query_matches(
                item, value_key, visible, query
            ):
                continue
            suggestions.append(row)
        return suggestions

    def _git_github_request(self, repo, head_type):
        """Build the single GitHub list request for ``head_type``.

        Args:
            repo (cx.tower.git.repo): Repository whose owner and name are used.
            head_type (str): ``branch``, ``pr``, or ``commit``.

        Returns:
            tuple: ``(url, params, value_key)``. ``url`` is empty when
            ``head_type`` is not one of those three.
        """
        owner = repo.owner_id.name
        name = repo.repo
        if not owner or not name:
            return False, {}, False
        base = self._git_github_repos_base(owner, name)
        params = {"per_page": GITHUB_PAGE_SIZE, "page": 1}
        if head_type == "branch":
            return f"{base}/branches", params, "name"
        if head_type == "pr":
            params["state"] = "open"
            return f"{base}/pulls", params, "number"
        if head_type == "commit":
            return f"{base}/commits", params, "sha"
        return False, {}, False

    @api.model
    def _git_github_repos_base(self, owner, name):
        """Return the GitHub repository URL with encoded path segments.

        Each of ``owner`` and ``name`` is one path segment. Encoding them
        keeps a reserved character inside the segment.

        Args:
            owner (str): Repository owner.
            name (str): Repository name.

        Returns:
            str: ``https://api.github.com/repos/<owner>/<name>``.
        """
        return f"{GITHUB_API_URL}/repos/{quote(owner, safe='')}/{quote(name, safe='')}"

    def _git_github_suggestion(self, item, value_key):
        """Read one suggestion from a GitHub payload item.

        Args:
            item (dict): One object from the GitHub page.
            value_key (str): ``name``, ``number``, or ``sha``.

        Returns:
            str: Suggestion text, or an empty string when the item has none.
            Pull request text is ``<number> <title>``. Commit text is
            ``<sha> <subject>``, using the first 7 characters of a longer
            SHA and the first line of ``commit.message``.
        """
        if not isinstance(item, dict):
            return ""
        value = item.get(value_key)
        if value_key == "number":
            if value is None:
                return ""
            return self._git_github_with_caption(str(value), item.get("title"))
        if value_key == "sha":
            if not isinstance(value, str) or not value:
                return ""
            short = value if len(value) <= 7 else value[:7]
            return self._git_github_with_caption(short, self._git_github_subject(item))
        if not isinstance(value, str):
            return ""
        return value

    def _git_github_with_caption(self, identifier, caption):
        """Append a one-line caption to an identifier.

        Args:
            identifier (str): Number or commit id.
            caption (str | None): Title or subject from GitHub.

        Returns:
            str: ``identifier`` when the caption is empty, otherwise both.
        """
        if not isinstance(caption, str):
            return identifier
        caption = caption.split("\n", 1)[0].strip()
        if not caption:
            return identifier
        return f"{identifier} {caption}"

    def _git_github_subject(self, item):
        """Return the first line of a commit message.

        Args:
            item (dict): One object from the commits page. The message is
                ``commit.message``.

        Returns:
            str: Subject line, or an empty string.
        """
        commit = item.get("commit")
        if not isinstance(commit, dict):
            return ""
        message = commit.get("message")
        if not isinstance(message, str):
            return ""
        return message.split("\n", 1)[0].strip()

    def _git_github_query_matches(self, item, value_key, suggestion, query):
        """Return whether ``query`` matches the row the user sees.

        A shortened commit still matches the full ``sha``.

        Args:
            item (dict): GitHub payload item.
            value_key (str): ``name``, ``number``, or ``sha``.
            suggestion (str): Text shown in the dropdown.
            query (str): Trimmed input.

        Returns:
            bool: True when the query is part of the suggestion or the SHA.
        """
        needle = query.lower()
        if needle in suggestion.lower():
            return True
        if value_key != "sha" or not isinstance(item, dict):
            return False
        sha = item.get("sha")
        return isinstance(sha, str) and needle in sha.lower()

    @api.model_create_multi
    def create(self, vals_list):
        """Store the aggregator value when the form sends a caption.

        Args:
            vals_list (list[dict]): Values passed to ``create``.

        Returns:
            recordset: Created remotes.
        """
        for vals in vals_list:
            head = vals.get("head")
            if head and not self._git_github_head_is_url(head):
                vals["head"] = self._git_github_stored_head(
                    head, self._git_github_create_head_type(vals)
                )
        return super().create(vals_list)

    def write(self, vals):
        """Store the aggregator value when the form sends a caption.

        Args:
            vals (dict): Values passed to ``write``.

        Returns:
            bool: Result of ``write``.
        """
        head = vals.get("head")
        if (
            not self
            or "head" not in vals
            or not head
            or self._git_github_head_is_url(head)
        ):
            return super().write(vals)
        if "head_type" in vals:
            return super().write(
                dict(vals, head=self._git_github_stored_head(head, vals["head_type"]))
            )
        grouped = {}
        for record in self:
            grouped.setdefault(record.head_type, self.browse())
            grouped[record.head_type] |= record
        for head_type, records in grouped.items():
            super(CxTowerGitRemote, records).write(
                dict(vals, head=self._git_github_stored_head(head, head_type))
            )
        return True

    @api.onchange("head", "head_reference")
    def onchange_head(self):
        """Reduce a selected caption before the core link check."""
        for remote in self:
            if remote.head and not self._git_github_head_is_url(remote.head):
                remote.head = self._git_github_stored_head(
                    remote.head, remote.head_type
                )
        return super().onchange_head()

    def _git_github_head_is_url(self, head):
        """Return whether ``head`` itself is a pasted link.

        A ``://`` inside a pull-request title or commit subject is not a
        pasted link. Only a value whose first word contains ``://`` is.

        Args:
            head (str): Head value from the form.

        Returns:
            bool: True when the trimmed value starts with a URL.
        """
        if not isinstance(head, str):
            return False
        return "://" in head.strip().split(" ", 1)[0]

    def _git_github_create_head_type(self, vals):
        """Return the Head Type that create will store for ``vals``.

        Odoo fills a missing ``head_type`` from ``default_get`` after this
        override, including ``default_head_type`` from the context. The
        caption has to be reduced with that same value.

        Args:
            vals (dict): One create dictionary.

        Returns:
            str | bool | None: ``head_type`` from ``vals``, or the create
            default when the key is omitted.
        """
        if "head_type" in vals:
            return vals.get("head_type")
        return self.default_get(["head_type"]).get("head_type")

    def _git_github_stored_head(self, head, head_type):
        """Keep the number or commit id from a captioned suggestion.

        A selected commit stores the full SHA with no caption, so this
        method leaves that value unchanged. A typed caption is reduced to
        its first word when that word is a pull request number or a commit
        id. git-aggregator then uses the field: ``refs/pull/<number>/head``
        for a pull request, and the head text itself for a commit.

        Args:
            head (str): Suggestion or typed head.
            head_type (str | None): ``branch``, ``pr``, or ``commit``.

        Returns:
            str: Value to store.
        """
        if not isinstance(head, str) or head_type not in ("pr", "commit"):
            return head
        stripped = head.strip()
        token, _separator, caption = stripped.partition(" ")
        if not caption.strip():
            return stripped
        if head_type == "pr" and token.isdigit():
            return token
        if head_type == "commit" and self._git_github_is_sha(token):
            return token
        return stripped

    def _git_github_is_sha(self, token):
        """Return whether ``token`` is the commit id shown in the list.

        Args:
            token (str): First word of the suggestion.

        Returns:
            bool: True for 7 to 40 hexadecimal characters.
        """
        if len(token) < 7 or len(token) > 40:
            return False
        return all(char in "0123456789abcdefABCDEF" for char in token)

    def _git_github_error_message(self, response):
        """Return the message GitHub sent with a failed response.

        Args:
            response (requests.Response): Non-200 response.

        Returns:
            str: GitHub ``message``, or the HTTP reason.
        """
        try:
            payload = response.json()
        except ValueError:
            payload = None
        if isinstance(payload, dict) and payload.get("message"):
            return payload["message"]
        return response.reason or self.env._("GitHub returned an error.")

    def _git_head_api_reference(self, repo):
        """Use the repository Secret, the owner Secret, or settings.

        Args:
            repo (cx.tower.git.repo): Repository to read.

        Returns:
            str | bool: Key reference, or a falsy value when none is set.
        """
        reference = super()._git_head_api_reference(repo)
        if reference:
            return reference
        if repo.owner_id and repo.owner_id.secret_id:
            return repo.owner_id.secret_id.reference
        param = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("cetmix_tower_git_github.default_secret_id")
        )
        if not param or not str(param).isdigit():
            return False
        key = self.env["cx.tower.key"].sudo().browse(int(param)).exists()
        if not key or key.key_type != "s":
            return False
        return key.reference
