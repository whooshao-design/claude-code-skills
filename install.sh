#!/bin/bash
set -e

# claude-code-skills installer
# Copies skill directories to ~/.claude/skills/ (User Skills mechanism).
# Restart Claude Code after installation for skills to take effect.
#
# Usage:
#   bash install.sh                                         # install all skills
#   bash install.sh --groups dev-workflow                    # install from specific group
#   bash install.sh --groups dev-workflow --skills code-dev,dev-cr  # selective install
#   bash install.sh --list                                  # list available skills
#   bash install.sh --uninstall                             # uninstall all skills

SKILLS_DIR="${HOME}/.claude/skills"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GROUPS_ARG=""
SKILLS_ARG=""
UNINSTALL=0
LIST_ONLY=0
FORCE=0

# ─── Parse arguments ───
while [[ $# -gt 0 ]]; do
    case $1 in
        --groups)
            GROUPS_ARG="$2"
            shift 2
            ;;
        --skills)
            SKILLS_ARG="$2"
            shift 2
            ;;
        --list)
            LIST_ONLY=1
            shift
            ;;
        --uninstall)
            UNINSTALL=1
            shift
            ;;
        --force)
            FORCE=1
            shift
            ;;
        --target)
            SKILLS_DIR="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: bash install.sh [OPTIONS]"
            echo ""
            echo "Copies skills to ~/.claude/skills/ for Claude Code to discover."
            echo ""
            echo "Options:"
            echo "  --groups g1,g2     Install from specific groups (default: all)"
            echo "  --skills s1,s2     Install specific skills (requires single --groups)"
            echo "  --list             List available groups and skills"
            echo "  --uninstall        Uninstall skills"
            echo "  --force            Overwrite existing skills"
            echo "  --target DIR       Target directory (default: ~/.claude/skills)"
            echo "  -h, --help         Show this help"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# ─── Discovery ───
discover_groups() {
    local groups=()
    for dir in "${SCRIPT_DIR}/"*/; do
        if [[ -d "${dir}skills" ]]; then
            groups+=("$(basename "$dir")")
        fi
    done
    echo "${groups[@]}"
}

get_skills() {
    local group_dir="$1"
    local skills=()
    for dir in "${group_dir}/skills/"*/; do
        if [[ -f "${dir}SKILL.md" ]]; then
            skills+=("$(basename "$dir")")
        fi
    done
    echo "${skills[@]}"
}

# ─── List ───
if [[ $LIST_ONLY -eq 1 ]]; then
    AVAILABLE_GROUPS=($(discover_groups))
    for group in "${AVAILABLE_GROUPS[@]}"; do
        skills=($(get_skills "${SCRIPT_DIR}/${group}"))
        echo "Group: ${group} (${#skills[@]} skills)"
        for skill in "${skills[@]}"; do
            printf "  %-25s\n" "$skill"
        done
        echo ""
    done
    exit 0
fi

# ─── Resolve groups ───
AVAILABLE_GROUPS=($(discover_groups))

if [[ -z "${AVAILABLE_GROUPS[*]}" ]]; then
    echo "Error: no skill groups found."
    exit 1
fi

if [[ -n "$GROUPS_ARG" ]]; then
    IFS=',' read -ra SELECTED_GROUPS <<< "$GROUPS_ARG"
    for group in "${SELECTED_GROUPS[@]}"; do
        found=0
        for avail in "${AVAILABLE_GROUPS[@]}"; do
            [[ "$group" == "$avail" ]] && found=1 && break
        done
        if [[ $found -eq 0 ]]; then
            echo "Error: group '${group}' not found."
            echo "Available: ${AVAILABLE_GROUPS[*]}"
            exit 1
        fi
    done
else
    SELECTED_GROUPS=("${AVAILABLE_GROUPS[@]}")
fi

# ─── Validate --skills ───
if [[ -n "$SKILLS_ARG" ]] && [[ ${#SELECTED_GROUPS[@]} -ne 1 ]]; then
    echo "Error: --skills requires a single --groups value."
    exit 1
fi

# ─── Uninstall ───
if [[ $UNINSTALL -eq 1 ]]; then
    echo "=== claude-code-skills uninstaller ==="
    echo ""
    for group in "${SELECTED_GROUPS[@]}"; do
        all_skills=($(get_skills "${SCRIPT_DIR}/${group}"))
        if [[ -n "$SKILLS_ARG" ]]; then
            IFS=',' read -ra target_skills <<< "$SKILLS_ARG"
        else
            target_skills=("${all_skills[@]}")
        fi

        echo "Uninstalling from: ${group}"
        removed=0
        for skill in "${target_skills[@]}"; do
            dst="${SKILLS_DIR}/${skill}"
            if [[ -d "$dst" ]]; then
                rm -rf "$dst"
                echo "  Removed: ${skill}"
                ((removed++))
            fi
        done
        echo "  Done: ${removed} removed"
        echo ""
    done
    echo "Uninstall completed. Restart Claude Code to apply."
    exit 0
fi

# ─── Install ───
echo "=== claude-code-skills installer ==="
echo ""

mkdir -p "$SKILLS_DIR"

for group in "${SELECTED_GROUPS[@]}"; do
    all_skills=($(get_skills "${SCRIPT_DIR}/${group}"))

    if [[ -n "$SKILLS_ARG" ]]; then
        IFS=',' read -ra install_skills <<< "$SKILLS_ARG"
        # Validate
        for skill in "${install_skills[@]}"; do
            found=0
            for avail in "${all_skills[@]}"; do
                [[ "$skill" == "$avail" ]] && found=1 && break
            done
            if [[ $found -eq 0 ]]; then
                echo "  Error: skill '${skill}' not found in ${group}."
                echo "  Available: ${all_skills[*]}"
                exit 1
            fi
        done
    else
        install_skills=("${all_skills[@]}")
    fi

    echo "Installing from: ${group}"
    echo "  Target: ${SKILLS_DIR}"
    echo "  Skills: ${install_skills[*]}"

    installed=0
    skipped=0
    for skill in "${install_skills[@]}"; do
        src="${SCRIPT_DIR}/${group}/skills/${skill}"
        dst="${SKILLS_DIR}/${skill}"

        if [[ -d "$dst" ]]; then
            if [[ $FORCE -eq 0 ]]; then
                echo "  Skip (exists): ${skill}"
                ((skipped++))
                continue
            fi
            rm -rf "$dst"
        fi

        cp -r "$src" "$dst"
        ((installed++))
        echo "  Installed: ${skill}"
    done

    echo "  Done: ${installed} installed, ${skipped} skipped"
    if [[ $skipped -gt 0 ]]; then
        echo "  Hint: use --force to overwrite existing skills"
    fi
    echo ""
done

echo "All done! Restart Claude Code to load the new skills."
