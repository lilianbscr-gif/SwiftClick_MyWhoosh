"""
intervals_client.py — Client API intervals.icu (lecture wellness + profil).
Credentials lus depuis .env (INTERVALS_ATHLETE_ID, INTERVALS_API_KEY).
"""
import urllib.request
import urllib.error
import base64
import json
import ssl
import datetime
from pathlib import Path

_ENV_FILE = Path(__file__).parent / ".env"
_CTX      = ssl.create_default_context()
_UA       = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
             "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


def _load_env() -> dict:
    env: dict[str, str] = {}
    if _ENV_FILE.exists():
        for line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
    return env


class IntervalsClient:
    """Client léger pour l'API intervals.icu."""

    def __init__(self):
        env = _load_env()
        self.athlete_id = env.get("INTERVALS_ATHLETE_ID", "")
        api_key         = env.get("INTERVALS_API_KEY", "")
        self.enabled    = bool(self.athlete_id and api_key)

        creds        = base64.b64encode(f"API_KEY:{api_key}".encode()).decode()
        self._headers = {
            "Authorization": f"Basic {creds}",
            "Accept":        "application/json",
            "User-Agent":    _UA,
        }
        self._base = "https://intervals.icu/api/v1"

    # ── API privée ────────────────────────────────────────────

    def _get(self, path: str) -> dict | list | None:
        if not self.enabled:
            return None
        try:
            req = urllib.request.Request(
                f"{self._base}{path}", headers=self._headers
            )
            with urllib.request.urlopen(req, timeout=12, context=_CTX) as r:
                return json.loads(r.read())
        except Exception:
            return None

    # ── API publique ──────────────────────────────────────────

    def fetch_profile(self) -> dict:
        """Retourne {ftp, vo2max, name} depuis le profil athlète."""
        data = self._get(f"/athlete/{self.athlete_id}")
        if not data:
            return {}
        return {
            "name":   data.get("name"),
            "ftp":    data.get("ftp"),
            "vo2max": data.get("vo2max"),
        }

    def fetch_wellness(self) -> dict:
        """Retourne {ctl, atl, tsb, date} du jour ou du dernier jour disponible."""
        today = datetime.date.today().isoformat()
        week  = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
        data  = self._get(
            f"/athlete/{self.athlete_id}/wellness?oldest={week}&newest={today}"
        )
        if not data:
            return {}
        # Prend le dernier point disponible
        last = data[-1]
        ctl  = last.get("ctl")
        atl  = last.get("atl")
        tsb  = round(ctl - atl, 1) if (ctl is not None and atl is not None) else None
        return {
            "date": last.get("id", ""),
            "ctl":  round(ctl, 1) if ctl is not None else None,
            "atl":  round(atl, 1) if atl is not None else None,
            "tsb":  tsb,
        }

    def fetch_all(self) -> dict:
        """Fetch profil + wellness en une seule opération."""
        return {**self.fetch_profile(), **self.fetch_wellness()}
