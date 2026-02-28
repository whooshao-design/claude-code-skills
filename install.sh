#!/bin/bash
set -e

# claude-code-skills installer
# Usage:
#   bash install.sh                    # 安装全部 skills
#   bash install.sh --skills code-dev,dev-cr   # 选择性安装
#   bash install.sh --list             # 列出可用 skills
#   bash install.sh --uninstall        # 卸载插件

PLUGIN_NAME="claude-code-skills"
PLUGIN_ID="${PLUGIN_NAME}@local"
CLAUDE_DIR="${HOME}/.claude"
PLUGIN_DIR="${CLAUDE_DIR}/plugins/local/${PLUGIN_NAME}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_ARG=""
UNINSTALL=0
LIST_ONLY=0
FORCE=0

# ─── Parse arguments ───
while [[ $# -gt 0 ]]; do
    case $1 in
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
        -h|--help)
            echo "Usage: bash install.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --skills s1,s2   安装指定 skills（逗号分隔）"
            echo "  --list           列出所有可用 skills"
            echo "  --uninstall      卸载插件"
            echo "  --force          强制覆盖已有安装"
            echo "  -h, --help       显示帮助"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# ─── Discover available skills ───
get_available_skills() {
    local skills=()
    for dir in "${SCRIPT_DIR}/skills/"*/; do
        [[ -d "$dir" ]] && skills+=("$(basename "$dir")")
    done
    echo "${skills[@]}"
}

# ─── List skills ───
if [[ $LIST_ONLY -eq 1 ]]; then
    echo "Available skills:"
    echo ""
    for dir in "${SCRIPT_DIR}/skills/"*/; do
        [[ -d "$dir" ]] || continue
        name=$(basename "$dir")
        # Try to extract description from SKILL.md first line
        desc=""
        if [[ -f "${dir}SKILL.md" ]]; then
            desc=$(head -5 "${dir}SKILL.md" | grep -m1 'description:' | sed 's/.*description: *//; s/"//g' || true)
        fi
        printf "  %-25s %s\n" "$name" "$desc"
    done
    exit 0
fi

# ─── Uninstall ───
if [[ $UNINSTALL -eq 1 ]]; then
    echo "Uninstalling ${PLUGIN_NAME}..."

    # Remove plugin directory
    if [[ -d "$PLUGIN_DIR" ]] || [[ -L "$PLUGIN_DIR" ]]; then
        rm -rf "$PLUGIN_DIR"
        echo "  Removed plugin directory"
    fi

    # Remove from installed_plugins.json
    INSTALLED_FILE="${CLAUDE_DIR}/plugins/installed_plugins.json"
    if [[ -f "$INSTALLED_FILE" ]] && command -v python3 &>/dev/null; then
        python3 -c "
import json, sys
with open('${INSTALLED_FILE}', 'r') as f:
    data = json.load(f)
data.get('plugins', {}).pop('${PLUGIN_ID}', None)
with open('${INSTALLED_FILE}', 'w') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
    f.write('\\n')
"
        echo "  Removed from installed_plugins.json"
    fi

    # Remove from settings.json
    SETTINGS_FILE="${CLAUDE_DIR}/settings.json"
    if [[ -f "$SETTINGS_FILE" ]] && command -v python3 &>/dev/null; then
        python3 -c "
import json
with open('${SETTINGS_FILE}', 'r') as f:
    data = json.load(f)
data.get('enabledPlugins', {}).pop('${PLUGIN_ID}', None)
with open('${SETTINGS_FILE}', 'w') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
    f.write('\\n')
"
        echo "  Removed from settings.json"
    fi

    echo "Uninstall completed."
    exit 0
fi

# ─── Determine skills to install ───
AVAILABLE_SKILLS=($(get_available_skills))

if [[ -n "$SKILLS_ARG" ]]; then
    IFS=',' read -ra SELECTED_SKILLS <<< "$SKILLS_ARG"
    # Validate
    for skill in "${SELECTED_SKILLS[@]}"; do
        found=0
        for avail in "${AVAILABLE_SKILLS[@]}"; do
            [[ "$skill" == "$avail" ]] && found=1 && break
        done
        if [[ $found -eq 0 ]]; then
            echo "Error: skill '${skill}' not found."
            echo "Available: ${AVAILABLE_SKILLS[*]}"
            exit 1
        fi
    done
else
    SELECTED_SKILLS=("${AVAILABLE_SKILLS[@]}")
fi

echo "Installing ${PLUGIN_NAME} to Claude Code..."
echo "  Skills: ${SELECTED_SKILLS[*]}"
echo ""

# ─── Step 1: Create plugin directory ───
if [[ -d "$PLUGIN_DIR" ]] || [[ -L "$PLUGIN_DIR" ]]; then
    if [[ $FORCE -eq 0 ]]; then
        echo "Plugin directory already exists: ${PLUGIN_DIR}"
        echo "Use --force to overwrite, or --uninstall first."
        exit 1
    fi
    rm -rf "$PLUGIN_DIR"
fi

mkdir -p "${PLUGIN_DIR}/.claude-plugin"
mkdir -p "${PLUGIN_DIR}/skills"

# ─── Step 2: Copy plugin manifest ───
cp "${SCRIPT_DIR}/.claude-plugin/plugin.json" "${PLUGIN_DIR}/.claude-plugin/plugin.json"
echo "  Copied plugin manifest"

# ─── Step 3: Symlink selected skills ───
for skill in "${SELECTED_SKILLS[@]}"; do
    ln -s "${SCRIPT_DIR}/skills/${skill}" "${PLUGIN_DIR}/skills/${skill}"
    echo "  Linked skill: ${skill}"
done

# ─── Step 4: Register plugin in installed_plugins.json ───
INSTALLED_FILE="${CLAUDE_DIR}/plugins/installed_plugins.json"
mkdir -p "$(dirname "$INSTALLED_FILE")"

if ! command -v python3 &>/dev/null; then
    echo "WARNING: python3 not found, skipping plugin registration."
    echo "Please manually register the plugin in:"
    echo "  ${INSTALLED_FILE}"
    echo "  ${CLAUDE_DIR}/settings.json"
else
    python3 -c "
import json, os
from datetime import datetime

installed_file = '${INSTALLED_FILE}'
plugin_id = '${PLUGIN_ID}'
plugin_dir = '${PLUGIN_DIR}'

# Load or create
if os.path.exists(installed_file):
    with open(installed_file, 'r') as f:
        data = json.load(f)
else:
    data = {'version': 2, 'plugins': {}}

now = datetime.now().strftime('%Y-%m-%dT%H:%M:%S.000Z')
data.setdefault('plugins', {})[plugin_id] = [{
    'scope': 'user',
    'installPath': plugin_dir,
    'version': '1.0.0',
    'installedAt': now,
    'lastUpdated': now
}]

with open(installed_file, 'w') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
    f.write('\\n')
"
    echo "  Registered in installed_plugins.json"

    # ─── Step 5: Enable plugin in settings.json ───
    SETTINGS_FILE="${CLAUDE_DIR}/settings.json"
    if [[ -f "$SETTINGS_FILE" ]]; then
        python3 -c "
import json

settings_file = '${SETTINGS_FILE}'
plugin_id = '${PLUGIN_ID}'

with open(settings_file, 'r') as f:
    data = json.load(f)

data.setdefault('enabledPlugins', {})[plugin_id] = True

with open(settings_file, 'w') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
    f.write('\\n')
"
        echo "  Enabled in settings.json"
    fi
fi

# ─── Done ───
echo ""
echo "Installation completed!"
echo "Plugin: ${PLUGIN_DIR}"
echo "Skills installed: ${#SELECTED_SKILLS[@]}/${#AVAILABLE_SKILLS[@]}"
echo ""
echo "Restart Claude Code to load the new skills."
