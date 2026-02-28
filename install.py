#!/usr/bin/env python3
"""claude-code-skills installer.

Usage:
    python install.py                          # 安装全部 skills
    python install.py --skills code-dev,dev-cr  # 选择性安装
    python install.py --list                    # 列出可用 skills
    python install.py --uninstall               # 卸载插件
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

PLUGIN_NAME = "claude-code-skills"
PLUGIN_ID = f"{PLUGIN_NAME}@local"
DEFAULT_CLAUDE_DIR = Path.home() / ".claude"


def get_script_dir() -> Path:
    return Path(__file__).resolve().parent


def get_available_skills(script_dir: Path) -> List[str]:
    skills_dir = script_dir / "skills"
    if not skills_dir.is_dir():
        return []
    return sorted(d.name for d in skills_dir.iterdir() if d.is_dir())


def get_skill_description(script_dir: Path, skill_name: str) -> str:
    skill_md = script_dir / "skills" / skill_name / "SKILL.md"
    if not skill_md.exists():
        return ""
    try:
        for line in skill_md.read_text(encoding="utf-8").splitlines()[:10]:
            if "description:" in line.lower():
                return line.split("description:", 1)[-1].strip().strip('"')
    except Exception:
        pass
    return ""


def list_skills(script_dir: Path) -> None:
    skills = get_available_skills(script_dir)
    if not skills:
        print("No skills found.")
        return
    print("Available skills:\n")
    for name in skills:
        desc = get_skill_description(script_dir, name)
        print(f"  {name:<25} {desc}")


def uninstall(claude_dir: Path) -> None:
    plugin_dir = claude_dir / "plugins" / "local" / PLUGIN_NAME
    print(f"Uninstalling {PLUGIN_NAME}...")

    # Remove plugin directory
    if plugin_dir.exists() or plugin_dir.is_symlink():
        if plugin_dir.is_symlink() or plugin_dir.is_file():
            plugin_dir.unlink()
        else:
            shutil.rmtree(plugin_dir)
        print("  Removed plugin directory")

    # Remove from installed_plugins.json
    installed_file = claude_dir / "plugins" / "installed_plugins.json"
    if installed_file.exists():
        data = json.loads(installed_file.read_text(encoding="utf-8"))
        if PLUGIN_ID in data.get("plugins", {}):
            del data["plugins"][PLUGIN_ID]
            installed_file.write_text(
                json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            print("  Removed from installed_plugins.json")

    # Remove from settings.json
    settings_file = claude_dir / "settings.json"
    if settings_file.exists():
        data = json.loads(settings_file.read_text(encoding="utf-8"))
        if PLUGIN_ID in data.get("enabledPlugins", {}):
            del data["enabledPlugins"][PLUGIN_ID]
            settings_file.write_text(
                json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            print("  Removed from settings.json")

    print("Uninstall completed.")


def create_symlink(src: Path, dst: Path) -> None:
    """Create symlink, handling cross-platform differences."""
    if sys.platform == "win32":
        # Windows: use junction for directories
        import subprocess
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(dst), str(src)],
            check=True,
            capture_output=True,
        )
    else:
        dst.symlink_to(src)


def install(
    claude_dir: Path,
    script_dir: Path,
    selected_skills: List[str],
    force: bool = False,
) -> None:
    plugin_dir = claude_dir / "plugins" / "local" / PLUGIN_NAME
    available = get_available_skills(script_dir)

    # Validate skills
    for skill in selected_skills:
        if skill not in available:
            print(f"Error: skill '{skill}' not found.")
            print(f"Available: {', '.join(available)}")
            sys.exit(1)

    print(f"Installing {PLUGIN_NAME} to Claude Code...")
    print(f"  Skills: {', '.join(selected_skills)}")
    print()

    # Step 1: Create plugin directory
    if plugin_dir.exists() or plugin_dir.is_symlink():
        if not force:
            print(f"Plugin directory already exists: {plugin_dir}")
            print("Use --force to overwrite, or --uninstall first.")
            sys.exit(1)
        if plugin_dir.is_symlink() or plugin_dir.is_file():
            plugin_dir.unlink()
        else:
            shutil.rmtree(plugin_dir)

    (plugin_dir / ".claude-plugin").mkdir(parents=True, exist_ok=True)
    (plugin_dir / "skills").mkdir(parents=True, exist_ok=True)

    # Step 2: Copy plugin manifest
    src_manifest = script_dir / ".claude-plugin" / "plugin.json"
    dst_manifest = plugin_dir / ".claude-plugin" / "plugin.json"
    shutil.copy2(src_manifest, dst_manifest)
    print("  Copied plugin manifest")

    # Step 3: Symlink selected skills
    for skill in selected_skills:
        src = script_dir / "skills" / skill
        dst = plugin_dir / "skills" / skill
        create_symlink(src, dst)
        print(f"  Linked skill: {skill}")

    # Step 4: Register plugin
    register_plugin(claude_dir, plugin_dir)

    # Step 5: Enable plugin
    enable_plugin(claude_dir)

    print()
    print("Installation completed!")
    print(f"Plugin: {plugin_dir}")
    print(f"Skills installed: {len(selected_skills)}/{len(available)}")
    print()
    print("Restart Claude Code to load the new skills.")


def register_plugin(claude_dir: Path, plugin_dir: Path) -> None:
    installed_file = claude_dir / "plugins" / "installed_plugins.json"
    installed_file.parent.mkdir(parents=True, exist_ok=True)

    if installed_file.exists():
        data = json.loads(installed_file.read_text(encoding="utf-8"))
    else:
        data = {"version": 2, "plugins": {}}

    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.000Z")
    data.setdefault("plugins", {})[PLUGIN_ID] = [
        {
            "scope": "user",
            "installPath": str(plugin_dir),
            "version": "1.0.0",
            "installedAt": now,
            "lastUpdated": now,
        }
    ]

    installed_file.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print("  Registered in installed_plugins.json")


def enable_plugin(claude_dir: Path) -> None:
    settings_file = claude_dir / "settings.json"
    if not settings_file.exists():
        return

    data = json.loads(settings_file.read_text(encoding="utf-8"))
    data.setdefault("enabledPlugins", {})[PLUGIN_ID] = True
    settings_file.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print("  Enabled in settings.json")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="claude-code-skills installer"
    )
    parser.add_argument(
        "--skills",
        help="Comma-separated skill names to install (default: all)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available skills and exit",
    )
    parser.add_argument(
        "--uninstall",
        action="store_true",
        help="Uninstall the plugin",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force overwrite existing installation",
    )
    parser.add_argument(
        "--claude-dir",
        default=str(DEFAULT_CLAUDE_DIR),
        help=f"Claude config directory (default: {DEFAULT_CLAUDE_DIR})",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    script_dir = get_script_dir()
    claude_dir = Path(args.claude_dir).expanduser().resolve()

    if args.list:
        list_skills(script_dir)
        return 0

    if args.uninstall:
        uninstall(claude_dir)
        return 0

    # Determine skills to install
    available = get_available_skills(script_dir)
    if not available:
        print("Error: no skills found in skills/ directory.")
        return 1

    if args.skills:
        selected = [s.strip() for s in args.skills.split(",") if s.strip()]
    else:
        selected = available

    install(claude_dir, script_dir, selected, force=args.force)
    return 0


if __name__ == "__main__":
    sys.exit(main())
