#!/usr/bin/env python3
"""claude-code-skills installer - multi-plugin architecture.

Usage:
    python install.py                                        # 安装所有插件的全部 skills
    python install.py --plugins dev-workflow                  # 只安装指定插件
    python install.py --plugins dev-workflow --skills code-dev,dev-cr  # 插件内选择性安装
    python install.py --list                                 # 列出所有可用插件和 skills
    python install.py --uninstall                            # 卸载所有插件
    python install.py --uninstall --plugins dev-workflow      # 卸载指定插件
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

DEFAULT_CLAUDE_DIR = Path.home() / ".claude"


def get_script_dir() -> Path:
    return Path(__file__).resolve().parent


# ─── Plugin discovery ───


def discover_plugins(repo_dir: Path) -> Dict[str, Path]:
    """Scan repo for subdirectories containing .claude-plugin/plugin.json."""
    plugins = {}
    for child in sorted(repo_dir.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        manifest = child / ".claude-plugin" / "plugin.json"
        if manifest.exists():
            plugins[child.name] = child
    return plugins


def get_plugin_description(plugin_dir: Path) -> str:
    manifest = plugin_dir / ".claude-plugin" / "plugin.json"
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
        return data.get("description", "")
    except Exception:
        return ""


def get_available_skills(plugin_dir: Path) -> List[str]:
    skills_dir = plugin_dir / "skills"
    if not skills_dir.is_dir():
        return []
    return sorted(d.name for d in skills_dir.iterdir() if d.is_dir())


def get_skill_description(plugin_dir: Path, skill_name: str) -> str:
    skill_md = plugin_dir / "skills" / skill_name / "SKILL.md"
    if not skill_md.exists():
        return ""
    try:
        for line in skill_md.read_text(encoding="utf-8").splitlines()[:10]:
            if "description:" in line.lower():
                return line.split("description:", 1)[-1].strip().strip('"')
    except Exception:
        pass
    return ""


# ─── List ───


def list_all(repo_dir: Path) -> None:
    plugins = discover_plugins(repo_dir)
    if not plugins:
        print("No plugins found.")
        return

    for name, path in plugins.items():
        desc = get_plugin_description(path)
        skills = get_available_skills(path)
        print(f"Plugin: {name}")
        if desc:
            print(f"  {desc}")
        print(f"  Skills ({len(skills)}):")
        for skill in skills:
            sdesc = get_skill_description(path, skill)
            print(f"    {skill:<25} {sdesc}")
        print()


# ─── Symlink ───


def create_symlink(src: Path, dst: Path) -> None:
    if sys.platform == "win32":
        import subprocess
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(dst), str(src)],
            check=True,
            capture_output=True,
        )
    else:
        dst.symlink_to(src)


# ─── Install ───


def install_plugin(
    claude_dir: Path,
    plugin_name: str,
    plugin_src: Path,
    selected_skills: Optional[List[str]],
    force: bool,
) -> None:
    plugin_id = f"{plugin_name}@local"
    plugin_dir = claude_dir / "plugins" / "local" / plugin_name
    available = get_available_skills(plugin_src)

    # Determine skills
    if selected_skills:
        for skill in selected_skills:
            if skill not in available:
                print(f"  Error: skill '{skill}' not found in {plugin_name}.")
                print(f"  Available: {', '.join(available)}")
                sys.exit(1)
        skills = selected_skills
    else:
        skills = available

    print(f"Installing plugin: {plugin_name}")
    print(f"  Skills: {', '.join(skills)}")

    # Clean existing
    if plugin_dir.exists() or plugin_dir.is_symlink():
        if not force:
            print(f"  Already exists: {plugin_dir}")
            print("  Use --force to overwrite.")
            sys.exit(1)
        if plugin_dir.is_symlink() or plugin_dir.is_file():
            plugin_dir.unlink()
        else:
            shutil.rmtree(plugin_dir)

    # Create structure
    (plugin_dir / ".claude-plugin").mkdir(parents=True, exist_ok=True)
    (plugin_dir / "skills").mkdir(parents=True, exist_ok=True)

    # Copy manifest
    shutil.copy2(
        plugin_src / ".claude-plugin" / "plugin.json",
        plugin_dir / ".claude-plugin" / "plugin.json",
    )

    # Symlink skills
    for skill in skills:
        create_symlink(
            plugin_src / "skills" / skill,
            plugin_dir / "skills" / skill,
        )
        print(f"  Linked: {skill}")

    # Register & enable
    register_plugin(claude_dir, plugin_id, plugin_dir)
    enable_plugin(claude_dir, plugin_id)
    print(f"  Done ({len(skills)}/{len(available)} skills)")
    print()


def register_plugin(claude_dir: Path, plugin_id: str, plugin_dir: Path) -> None:
    installed_file = claude_dir / "plugins" / "installed_plugins.json"
    installed_file.parent.mkdir(parents=True, exist_ok=True)

    if installed_file.exists():
        data = json.loads(installed_file.read_text(encoding="utf-8"))
    else:
        data = {"version": 2, "plugins": {}}

    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.000Z")
    data.setdefault("plugins", {})[plugin_id] = [
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


def enable_plugin(claude_dir: Path, plugin_id: str) -> None:
    settings_file = claude_dir / "settings.json"
    if not settings_file.exists():
        return

    data = json.loads(settings_file.read_text(encoding="utf-8"))
    data.setdefault("enabledPlugins", {})[plugin_id] = True
    settings_file.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


# ─── Uninstall ───


def uninstall_plugin(claude_dir: Path, plugin_name: str) -> None:
    plugin_id = f"{plugin_name}@local"
    plugin_dir = claude_dir / "plugins" / "local" / plugin_name
    print(f"Uninstalling: {plugin_name}")

    if plugin_dir.exists() or plugin_dir.is_symlink():
        if plugin_dir.is_symlink() or plugin_dir.is_file():
            plugin_dir.unlink()
        else:
            shutil.rmtree(plugin_dir)
        print("  Removed plugin directory")

    # installed_plugins.json
    installed_file = claude_dir / "plugins" / "installed_plugins.json"
    if installed_file.exists():
        data = json.loads(installed_file.read_text(encoding="utf-8"))
        if plugin_id in data.get("plugins", {}):
            del data["plugins"][plugin_id]
            installed_file.write_text(
                json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

    # settings.json
    settings_file = claude_dir / "settings.json"
    if settings_file.exists():
        data = json.loads(settings_file.read_text(encoding="utf-8"))
        if plugin_id in data.get("enabledPlugins", {}):
            del data["enabledPlugins"][plugin_id]
            settings_file.write_text(
                json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

    print("  Done")
    print()


# ─── CLI ───


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="claude-code-skills installer"
    )
    parser.add_argument(
        "--plugins",
        help="Comma-separated plugin names to install (default: all)",
    )
    parser.add_argument(
        "--skills",
        help="Comma-separated skill names within a plugin (requires --plugins with single plugin)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available plugins and skills",
    )
    parser.add_argument(
        "--uninstall",
        action="store_true",
        help="Uninstall plugins",
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
    repo_dir = get_script_dir()
    claude_dir = Path(args.claude_dir).expanduser().resolve()

    all_plugins = discover_plugins(repo_dir)
    if not all_plugins:
        print("Error: no plugins found (subdirectories with .claude-plugin/plugin.json).")
        return 1

    if args.list:
        list_all(repo_dir)
        return 0

    # Select plugins
    if args.plugins:
        selected_names = [p.strip() for p in args.plugins.split(",") if p.strip()]
        for name in selected_names:
            if name not in all_plugins:
                print(f"Error: plugin '{name}' not found.")
                print(f"Available: {', '.join(all_plugins.keys())}")
                return 1
    else:
        selected_names = list(all_plugins.keys())

    # Validate --skills usage
    selected_skills = None
    if args.skills:
        if len(selected_names) != 1:
            print("Error: --skills can only be used with a single --plugins value.")
            return 1
        selected_skills = [s.strip() for s in args.skills.split(",") if s.strip()]

    # Uninstall
    if args.uninstall:
        for name in selected_names:
            uninstall_plugin(claude_dir, name)
        print("Uninstall completed.")
        return 0

    # Install
    print(f"=== claude-code-skills installer ===\n")
    for name in selected_names:
        install_plugin(
            claude_dir,
            name,
            all_plugins[name],
            selected_skills,
            args.force,
        )

    print("All done! Restart Claude Code to load the new skills.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
