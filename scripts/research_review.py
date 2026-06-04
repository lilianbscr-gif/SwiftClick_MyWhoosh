#!/usr/bin/env python3
"""
Research Review — promeut les trouvailles score 4-5 de new_learning.md
vers long-term-memory.md. À exécuter chaque dimanche.
"""
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
NEW_LEARNING = PROJECT_DIR / "memory" / "new_learning.md"
LONG_TERM = PROJECT_DIR / "memory" / "long-term-memory.md"
LOG_FILE = PROJECT_DIR / "logs" / "review.log"
ENV_FILE = PROJECT_DIR / ".env"

if ENV_FILE.exists():
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")


def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


ENTRY_PATTERN = re.compile(
    r"(### \[(\d)/5\] .+?\n"
    r"- \*\*Source\*\* : .+?\n"
    r"- \*\*URL\*\* : .+?\n"
    r"- \*\*Trouvé\*\* : .+?\n"
    r"- \*\*Statut\*\* : nouveau\n)",
    re.DOTALL,
)


def parse_candidates() -> list[dict]:
    if not NEW_LEARNING.exists():
        return []

    content = NEW_LEARNING.read_text(encoding="utf-8")
    candidates = []

    for m in ENTRY_PATTERN.finditer(content):
        full_block = m.group(1)
        score_match = re.search(r"\[(\d)/5\]", full_block)
        score = int(score_match.group(1)) if score_match else 0
        if score < 4:
            continue

        summary_match = re.search(r"### \[\d/5\] (.+)", full_block)
        source_match = re.search(r"\*\*Source\*\* : (.+)", full_block)
        url_match = re.search(r"\*\*URL\*\* : (.+)", full_block)

        candidates.append({
            "score": score,
            "summary": summary_match.group(1).strip() if summary_match else "",
            "source": source_match.group(1).strip() if source_match else "",
            "url": url_match.group(1).strip() if url_match else "",
            "full_block": full_block,
        })

    return candidates


def extract_patterns(candidates: list[dict]) -> str:
    if not API_KEY:
        return extract_patterns_simple(candidates)

    try:
        import anthropic
    except ImportError:
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "anthropic", "-q"])
        import anthropic

    client = anthropic.Anthropic(api_key=API_KEY)

    entries_text = "\n".join(
        f"[{c['score']}/5] {c['summary']} ({c['source']}) — {c['url']}"
        for c in candidates
    )

    prompt = f"""Tu analyses {len(candidates)} trouvailles de veille technologique (score 4-5/5)
pour le projet SwiftClick_MyWhoosh (bridge Python Bluetooth/clavier vers MyWhoosh, Windows 11).

Trouvailles:
{entries_text}

Identifie les patterns réutilisables à retenir dans la mémoire long terme.
Réponds avec une liste markdown courte (max 6 items), format strict:
- **[Catégorie]** : description courte et actionnable en français (source — url si utile)

Catégories: Bibliothèque | Pattern | Évitement | Outil | API | Workflow

Ne garde que ce qui est non-évident et directement applicable à ce projet."""

    try:
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text.strip()
    except Exception as e:
        log(f"  [warn] Claude API: {e} — fallback simple")
        return extract_patterns_simple(candidates)


def extract_patterns_simple(candidates: list[dict]) -> str:
    lines = []
    for c in candidates:
        lines.append(f"- **[Veille]** : {c['summary'][:100]} ({c['source']})")
    return "\n".join(lines)


def mark_promoted(candidates: list[dict]):
    content = NEW_LEARNING.read_text(encoding="utf-8")
    for c in candidates:
        promoted_block = c["full_block"].replace(
            "- **Statut** : nouveau", "- **Statut** : promu"
        )
        content = content.replace(c["full_block"], promoted_block, 1)
    NEW_LEARNING.write_text(content, encoding="utf-8")


def append_to_long_term(patterns: str, count: int):
    today = datetime.now().strftime("%Y-%m-%d")
    section = (
        f"\n\n## Veille promue — {today}\n"
        f"> {count} trouvaille(s) score 4-5 consolidées\n\n"
        f"{patterns}\n"
    )
    content = LONG_TERM.read_text(encoding="utf-8")
    LONG_TERM.write_text(content + section, encoding="utf-8")


def main():
    log("=== Research Review démarré ===")

    candidates = parse_candidates()
    if not candidates:
        log("Aucune trouvaille score 4-5 non promue. Rien à faire.")
        return

    log(f"  {len(candidates)} trouvailles score 4-5 à promouvoir")

    log("Extraction des patterns...")
    patterns = extract_patterns(candidates)
    log("  Patterns extraits:")
    for line in patterns.splitlines():
        log(f"    {line}")

    append_to_long_term(patterns, len(candidates))
    log("  long-term-memory.md mis à jour")

    mark_promoted(candidates)
    log(f"  {len(candidates)} entrées marquées 'promu' dans new_learning.md")
    log("=== Terminé ===")


if __name__ == "__main__":
    main()
