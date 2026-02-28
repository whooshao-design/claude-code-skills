#!/usr/bin/env python3
"""claude-code-skills installer.

Copies skill directories to ~/.claude/skills/ (User Skills mechanism).
Restart Claude Code after installation for skills to take effect.

Usage:
    python install.py                                        # install all skills
    python install.py --groups dev-workflow                   # install from specific group
    python install.py --groups dev-workflow --skills code-dev,dev-cr  # selective install
    python install.py --list                                 # list available skills
    python install.py --uninstall                            # uninstall all skills
    python install.py --uninstall --groups dev-workflow       # uninstall specific group
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Optional

DEFAULT_SKILLS_DIR = Path.home() / ".claude" / "skills"


def get_script_dir() -> Path:
    return Path(__file__).resolve().parent


# ─── Discovery ───


def discover_groups(repo_dir: Path) -> Dict[str, Path]:
    """Scan repo for skill groups (subdirectories with skills/)."""
    groups = {}
    for child in sorted(repo_dir.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        skills_dir = child / "skills"
        if skills_dir.is_dir() and any(skills_dir.iterdir()):
            groups[child.name] = child
    return groups


def get_available_skills(group_dir: Path) -> List[str]:
    skills_dir = group_dir / "skills"
    if not skills_dir.is_dir():
        return []
    return sorted(
        d.name for d in skills_dir.iterdir()
        if d.is_dir() and (d / "SKILL.md").exists()
    )


def get_skill_description(group_dir: Path, skill_name: str) -> str:
    skill_md = group_dir / "skills" / skill_name / "SKILL.md"
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
    groups = discover_groups(repo_dir)
    if not groups:
        print("No skill groups found.")
        return

    for name, path in groups.items():
        skills = get_available_skills(path)
        print(f"Group: {name} ({len(skills)} skills)")
        for skill in skills:
            desc = get_skill_description(path, skill)
            print(f"  {skill:<25} {desc}")
        print()


# ─── Install ───


def install_skills(
    skills_dir: Path,
    group_name: str,
    group_src: Path,
    selected_skills: Optional[List[str]],
    force: bool,
) -> None:
    available = get_available_skills(group_src)

    if selected_skills:
        for skill in selected_skills:
            if skill not in available:
                print(f"  Error: skill '{skill}' not found in {group_name}.")
                print(f"  Available: {', '.join(available)}")
                sys.exit(1)
        skills = selected_skills
    else:
        skills = available

    print(f"Installing from: {group_name}")
    print(f"  Target: {skills_dir}")
    print(f"  Skills: {', '.join(skills)}")

    skills_dir.mkdir(parents=True, exist_ok=True)

    installed = 0
    skipped = 0
    for skill in skills:
        src = group_src / "skills" / skill
        dst = skills_dir / skill

        if dst.exists():
            if not force:
                print(f"  Skip (exists): {skill}")
                skipped += 1
                continue
            shutil.rmtree(dst)

        shutil.copytree(src, dst)
        installed += 1
        print(f"  Installed: {skill}")

    print(f"  Done: {installed} installed, {skipped} skipped")
    if skipped > 0:
        print(f"  Hint: use --force to overwrite existing skills")
    print()


# ─── Uninstall ───


def uninstall_skills(
    skills_dir: Path,
    group_name: str,
    group_src: Path,
    selected_skills: Optional[List[str]],
) -> None:
    available = get_available_skills(group_src)
    skills = selected_skills if selected_skills else available

    print(f"Uninstalling from: {group_name}")
    removed = 0
    for skill in skills:
        dst = skills_dir / skill
        if dst.exists():
            shutil.rmtree(dst)
            print(f"  Removed: {skill}")
            removed += 1

    print(f"  Done: {removed} removed")
    print()


# ─── CLI ───


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="claude-code-skills installer"
    )
    parser.add_argument(
        "--groups",
        help="Comma-separated group names (default: all)",
    )
    parser.add_argument(
        "--skills",
        help="Comma-separated skill names (requires single --groups)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available groups and skills",
    )
    parser.add_argument(
        "--uninstall",
        action="store_true",
        help="Uninstall skills",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force overwrite existing skills",
    )
    parser.add_argument(
        "--target",
        default=str(DEFAULT_SKILLS_DIR),
        help=f"Target skills directory (default: {DEFAULT_SKILLS_DIR})",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_dir = get_script_dir()
    skills_dir = Path(args.target).expanduser().resolve()

    all_groups = discover_groups(repo_dir)
    if not all_groups:
        print("Error: no skill groups found.")
        return 1

    if args.list:
        list_all(repo_dir)
        return 0

    # Select groups
    if args.groups:
        selected = [g.strip() for g in args.groups.split(",") if g.strip()]
        for name in selected:
            if name not in all_groups:
                print(f"Error: group '{name}' not found.")
                print(f"Available: {', '.join(all_groups.keys())}")
                return 1
    else:
        selected = list(all_groups.keys())

    # Validate --skills
    selected_skills = None
    if args.skills:
        if len(selected) != 1:
            print("Error: --skills requires a single --groups value.")
            return 1
        selected_skills = [s.strip() for s in args.skills.split(",") if s.strip()]

    print("=== claude-code-skills installer ===\n")

    if args.uninstall:
        for name in selected:
            uninstall_skills(skills_dir, name, all_groups[name], selected_skills)
        print("Uninstall completed. Restart Claude Code to apply.")
        return 0

    for name in selected:
        install_skills(skills_dir, name, all_groups[name], selected_skills, args.force)

    print("All done! Restart Claude Code to load the new skills.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
