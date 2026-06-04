# AGENTS.md — Agent guidance for SwiftClick_MyWhoosh

Purpose: Help AI coding agents quickly understand, run, and modify this repository.

Quick summary
- Small Windows-focused Python utility to bridge a Zwift Click device to MyWhoosh via simulated key presses.
- Primary UI: `interface.py`. Headless/CLI script: `zwift_click_mywhoosh.py`.

Run & dev notes
- Typical start: double-click `Lancer.bat` or run `python interface.py` on Windows 10/11 with Bluetooth enabled.
- To scan devices: run `scan_click.py` (useful for debugging Bluetooth discovery).
- Dependencies: Python 3.8+, `bleak`, `pynput`. See [README.md](README.md) for details and troubleshooting.

Important files
- `Lancer.bat` — convenience launcher for Windows users.
- `interface.py` — main GUI; contains the key mapping constants near the top (`TOUCHE_PLUS`, `TOUCHE_MOINS`).
- `zwift_click_mywhoosh.py` — CLI/advanced usage.
- `scan_click.py` — Bluetooth scanning helper.

Agent rules & conventions
- Prefer minimal, link-first guidance: link to `README.md` rather than duplicating long usage text.
- Modify `interface.py` only to change user-configurable constants (key mappings) unless asked to refactor UI logic.
- Keep changes Windows-specific unless cross-platform support is explicitly requested by the user.

Testing & validation steps for agents
- Validate Python version and that `bleak` and `pynput` are importable before making runtime changes.
- To smoke-test changes: run `python scan_click.py` to ensure Bluetooth discovery still works; then run `python interface.py` and verify the UI starts.

Suggested next customizations
- Add a `.github/copilot-instructions.md` if you want organization-level instructions or CI-specific workflows.
- Create a small `skills/` file or script that automates dependency installation and a headless smoke test on Windows.

If anything here is unclear, say which area (run, dependencies, files, or agent behavior) you want expanded.
