"""Upload the weekly mp3 as a GitHub Release asset (stable, phone-friendly download link)."""

import os
from pathlib import Path

import httpx

API = "https://api.github.com"


class GitHubReleases:
    def __init__(self, repo: str, token: str):
        self.repo = repo
        self.client = httpx.Client(
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=120,
            follow_redirects=True,
        )

    @classmethod
    def from_env(cls) -> "GitHubReleases":
        return cls(os.environ["GITHUB_REPOSITORY"], os.environ["GITHUB_TOKEN"])

    def _get_or_create_release(self, tag: str, name: str, body: str) -> dict:
        r = self.client.get(f"{API}/repos/{self.repo}/releases/tags/{tag}")
        if r.status_code == 200:
            return r.json()
        r = self.client.post(
            f"{API}/repos/{self.repo}/releases",
            json={"tag_name": tag, "name": name, "body": body},
        )
        r.raise_for_status()
        return r.json()

    def upload(self, tag: str, name: str, body: str, file: Path) -> str:
        """Create (or reuse) the release and upload `file`, replacing any same-named asset.

        Returns the asset's public download URL.
        """
        release = self._get_or_create_release(tag, name, body)
        for asset in release.get("assets", []):
            if asset["name"] == file.name:
                self.client.delete(f"{API}/repos/{self.repo}/releases/assets/{asset['id']}")

        upload_url = release["upload_url"].split("{")[0]
        r = self.client.post(
            upload_url,
            params={"name": file.name},
            content=file.read_bytes(),
            headers={"Content-Type": "audio/mpeg"},
        )
        r.raise_for_status()
        return r.json()["browser_download_url"]
