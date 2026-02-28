#!/bin/bash
set -e

# claude-code-skills installer - multi-plugin architecture
# Usage:
#   bash install.sh                                        # 安装所有插件
#   bash install.sh --plugins dev-workflow                  # 只安装指定插件
#   bash install.sh --plugins dev-workflow --skills code-dev,dev-cr  # 插件内选择性安装
#   bash install.sh --list                                 # 列出可用插件和 skills
#   bash install.sh --uninstall                            # 卸载所有插件
#   bash install.sh --uninstall --plugins dev-workflow      # 卸载指定插件

CLAUDE_DIR="${HOME}/.claude"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGINS_ARG=""
SKILLS_ARG=""
UNINSTALL=0
LIST_ONLY=0
FORCE=0

# ─── Parse arguments ───
while [[ $# -gt 0 ]]; do
    case $1 in
        --plugins)
            PLUGINS_ARG="$2"
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
        -h|--help)
            echo "Usage: bash install.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --plugins p1,p2    安装指定插件（逗号分隔）"
            echo "  --skills s1,s2     插件内选择性安装 skills（需配合单个 --plugins）"
            echo "  --list             列出所有可用插件和 skills"
            echo "  --uninstall        卸载插件"
            echo "  --force            强制覆盖已有安装"
            echo "  -h, --help         显示帮助"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# ─── Discover plugins ───
discover_plugins() {
    local plugins=()
    for dir in "${SCRIPT_DIR}/"*/; do
        [[ -f "${dir}.claude-plugin/plugin.json" ]] && plugins+=("$(basename "$dir")")
    done
    echo "${plugins[@]}"
}

get_skills() {
    local plugin_dir="$1"
    local skills=()
    for dir in "${plugin_dir}/skills/"*/; do
        [[ -d "$dir" ]] && skills+=("$(basename "$dir")")
    done
    echo "${skills[@]}"
}

# ─── List ───
if [[ $LIST_ONLY -eq 1 ]]; then
    AVAILABLE_PLUGINS=($(discover_plugins))
    for plugin in "${AVAILABLE_PLUGINS[@]}"; do
        echo "Plugin: ${plugin}"
        skills=($(get_skills "${SCRIPT_DIR}/${plugin}"))
        echo "  Skills (${#skills[@]}):"
        for skill in "${skills[@]}"; do
            printf "    %-25s\n" "$skill"
        done
        echo ""
    done
    exit 0
fi

# ─── Resolve selected plugins ───
AVAILABLE_PLUGINS=($(discover_plugins))

if [[ -z "${AVAILABLE_PLUGINS[*]}" ]]; then
    echo "Error: no plugins found."
    exit 1
fi

if [[ -n "$PLUGINS_ARG" ]]; then
    IFS=',' read -ra SELECTED_PLUGINS <<< "$PLUGINS_ARG"
    for plugin in "${SELECTED_PLUGINS[@]}"; do
        found=0
        for avail in "${AVAILABLE_PLUGINS[@]}"; do
            [[ "$plugin" == "$avail" ]] && found=1 && break
        done
        if [[ $found -eq 0 ]]; then
            echo "Error: plugin '${plugin}' not found."
            echo "Available: ${AVAILABLE_PLUGINS[*]}"
            exit 1
        fi
    done
else
    SELECTED_PLUGINS=("${AVAILABLE_PLUGINS[@]}")
fi

# ─── Validate --skills ───
if [[ -n "$SKILLS_ARG" ]] && [[ ${#SELECTED_PLUGINS[@]} -ne 1 ]]; then
    echo "Error: --skills can only be used with a single --plugins value."
    exit 1
fi

# ─── Uninstall ───
uninstall_plugin() {
    local plugin_name="$1"
    local plugin_id="${plugin_name}@local"
    local plugin_dir="${CLAUDE_DIR}/plugins/local/${plugin_name}"
    echo "Uninstalling: ${plugin_name}"

    if [[ -d "$plugin_dir" ]] || [[ -L "$plugin_dir" ]]; then
        rm -rf "$plugin_dir"
        echo "  Removed plugin directory"
    fi

    if command -v python3 &>/dev/null; then
        python3 -c "
import json, os
for fpath, key in [
    ('${CLAUDE_DIR}/plugins/installed_plugins.json', 'plugins'),
    ('${CLAUDE_DIR}/settings.json', 'enabledPlugins'),
]:
    if not os.path.exists(fpath):
        continue
    with open(fpath, 'r') as f:
        data = json.load(f)
    if '${plugin_id}' in data.get(key, {}):
        del data[key]['${plugin_id}']
        with open(fpath, 'w') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write('\\n')
"
    fi
    echo "  Done"
    echo ""
}

if [[ $UNINSTALL -eq 1 ]]; then
    for plugin in "${SELECTED_PLUGINS[@]}"; do
        uninstall_plugin "$plugin"
    done
    echo "Uninstall completed."
    exit 0
fi

# ─── Install ───
install_plugin() {
    local plugin_name="$1"
    local plugin_id="${plugin_name}@local"
    local plugin_src="${SCRIPT_DIR}/${plugin_name}"
    local plugin_dst="${CLAUDE_DIR}/plugins/local/${plugin_name}"
    local all_skills=($(get_skills "$plugin_src"))

    # Determine skills to install
    if [[ -n "$SKILLS_ARG" ]]; then
        IFS=',' read -ra install_skills <<< "$SKILLS_ARG"
        for skill in "${install_skills[@]}"; do
            found=0
            for avail in "${all_skills[@]}"; do
                [[ "$skill" == "$avail" ]] && found=1 && break
            done
            if [[ $found -eq 0 ]]; then
                echo "  Error: skill '${skill}' not found in ${plugin_name}."
                echo "  Available: ${all_skills[*]}"
                exit 1
            fi
        done
    else
        install_skills=("${all_skills[@]}")
    fi

    echo "Installing plugin: ${plugin_name}"
    echo "  Skills: ${install_skills[*]}"

    # Clean existing
    if [[ -d "$plugin_dst" ]] || [[ -L "$plugin_dst" ]]; then
        if [[ $FORCE -eq 0 ]]; then
            echo "  Already exists: ${plugin_dst}"
            echo "  Use --force to overwrite."
            exit 1
        fi
        rm -rf "$plugin_dst"
    fi

    # Create structure
    mkdir -p "${plugin_dst}/.claude-plugin"
    mkdir -p "${plugin_dst}/skills"

    # Copy manifest
    cp "${plugin_src}/.claude-plugin/plugin.json" "${plugin_dst}/.claude-plugin/plugin.json"

    # Symlink skills
    for skill in "${install_skills[@]}"; do
        ln -s "${plugin_src}/skills/${skill}" "${plugin_dst}/skills/${skill}"
        echo "  Linked: ${skill}"
    done

    # Register & enable
    if command -v python3 &>/dev/null; then
        python3 -c "
import json, os
from datetime import datetime

now = datetime.now().strftime('%Y-%m-%dT%H:%M:%S.000Z')
plugin_id = '${plugin_id}'
plugin_dst = '${plugin_dst}'
claude_dir = '${CLAUDE_DIR}'

# Register
f = os.path.join(claude_dir, 'plugins', 'installed_plugins.json')
os.makedirs(os.path.dirname(f), exist_ok=True)
data = json.load(open(f)) if os.path.exists(f) else {'version': 2, 'plugins': {}}
data.setdefault('plugins', {})[plugin_id] = [{
    'scope': 'user', 'installPath': plugin_dst,
    'version': '1.0.0', 'installedAt': now, 'lastUpdated': now
}]
with open(f, 'w') as fh:
    json.dump(data, fh, indent=2, ensure_ascii=False)
    fh.write('\\n')

# Enable
f2 = os.path.join(claude_dir, 'settings.json')
if os.path.exists(f2):
    data2 = json.load(open(f2))
    data2.setdefault('enabledPlugins', {})[plugin_id] = True
    with open(f2, 'w') as fh:
        json.dump(data2, fh, indent=2, ensure_ascii=False)
        fh.write('\\n')
"
    else
        echo "  WARNING: python3 not found, skipping plugin registration."
    fi

    echo "  Done (${#install_skills[@]}/${#all_skills[@]} skills)"
    echo ""
}

echo "=== claude-code-skills installer ==="
echo ""

for plugin in "${SELECTED_PLUGINS[@]}"; do
    install_plugin "$plugin"
done

echo "All done! Restart Claude Code to load the new skills."
