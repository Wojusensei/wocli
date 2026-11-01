"""驾驶舱 TUI 的纯逻辑测试：数据解析、waffle 分配、状态栏与面板渲染."""

import json
from dataclasses import replace

import pytest

from helpers import fake_files
from wocli import status_data as sd
from wocli import tui_core as tc


# ---------- 夹具 ----------

def make_snapshot():
    gib = 1024 ** 3
    return sd.StatusSnapshot(
        version="0.7.3",
        cwd="/home/woju/dev/wocli",
        system=sd.SystemInfo(
            "Darwin", "27.0", "arm64", 10, "3.14.6", os_label="macOS 27.0",
        ),
        cpu=sd.CpuInfo(23.0, 10, (1.84, 2.12, 1.96)),
        memory=sd.MemoryInfo(
            total=16 * gib,
            used=int(9.6 * gib),
            categories=(
                sd.MemoryCategory("app", "应用", int(6.4 * gib)),
                sd.MemoryCategory("cache", "缓存", int(3.2 * gib)),
                sd.MemoryCategory("sys", "系统", int(2.4 * gib)),
                sd.MemoryCategory("free", "空闲", int(4.0 * gib)),
            ),
        ),
        disk=sd.DiskInfo(312 * gib, 494 * gib),
        battery=sd.BatteryInfo(84, "充电中", 132, 91, 25.0),
        wifi=sd.WifiInfo("WoCli-5G", -52, "149", "866 Mbps", None),
        git=sd.GitInfo("fix/reported-bugs", True, 3, 0, 2),
    )


def text_of(line):
    return "".join(text for _, text in line)


# ---------- waffle / 内存 ----------

def test_allocate_cells_exact():
    counts = tc.allocate_cells([40, 20, 15, 25], 100)
    assert counts == [40, 20, 15, 25]
    assert sum(counts) == 100


def test_allocate_cells_rounds_to_exact_total():
    counts = tc.allocate_cells([1, 1, 1, 1, 1, 1], 100)
    assert sum(counts) == 100
    assert max(counts) - min(counts) <= 1


def test_allocate_cells_empty():
    assert tc.allocate_cells([], 100) == []
    assert tc.allocate_cells([0, 0], 100) == [0, 0]


def test_normalize_memory_adds_unaccounted_bytes_to_free():
    cats = sd.normalize_memory_categories(
        [
            sd.MemoryCategory("app", "应用", 10),
            sd.MemoryCategory("free", "空闲", 10),
        ],
        100,
    )
    assert sum(c.bytes for c in cats) == 100
    assert next(c for c in cats if c.key == "free").bytes == 90


def test_normalize_memory_scales_overflow():
    cats = sd.normalize_memory_categories(
        [
            sd.MemoryCategory("app", "应用", 100),
            sd.MemoryCategory("free", "空闲", 100),
        ],
        100,
    )
    assert sum(c.bytes for c in cats) == 100
    assert all(c.bytes >= 0 for c in cats)


def test_parse_macos_memory_categories():
    text = """Mach Virtual Memory Statistics: (page size of 16384 bytes)
Pages free:                                    100.
Pages active:                                  200.
Pages inactive:                                100.
Pages speculative:                              10.
Pages wired down:                               50.
Pages occupied by compressor:                   20.
"""
    total = 1024 ** 3
    info = sd.parse_macos_memory(text, total)
    assert info is not None
    assert info.total == total
    assert sum(c.bytes for c in info.categories) == total
    cats = {c.key: c.bytes for c in info.categories}
    assert cats["app"] == 200 * 16384
    assert cats["cache"] == (100 + 10) * 16384
    assert cats["sys"] == (50 + 20) * 16384
    assert cats["free"] > 0


def test_parse_linux_memory_categories():
    text = (
        "MemTotal:       16384000 kB\n"
        "MemFree:         4000000 kB\n"
        "Buffers:          500000 kB\n"
        "Cached:          3496000 kB\n"
        "SReclaimable:          0 kB\n"
        "Shmem:                 0 kB\n"
        "Slab:                  0 kB\n"
    )
    info = sd.parse_linux_memory(text)
    assert info is not None
    total = 16384000 * 1024
    assert info.total == total
    assert sum(c.bytes for c in info.categories) == total
    cats = {c.key: c.bytes for c in info.categories}
    assert cats["cache"] == (500000 + 3496000) * 1024
    assert cats["free"] == 4000000 * 1024
    assert "sys" not in cats  # 没有 Slab 数据时不硬造一类


def test_parse_windows_memory_categories():
    info = sd.parse_windows_memory("16777216 4194304 2147483648")
    assert info is not None
    assert info.total == 16777216 * 1024
    assert sum(c.bytes for c in info.categories) == info.total
    cats = {c.key: c.bytes for c in info.categories}
    assert cats["free"] == 4194304 * 1024
    assert cats["cache"] == 2147483648
    assert cats["app"] == info.total - cats["free"] - cats["cache"]


def test_parse_windows_memory_without_cache():
    info = sd.parse_windows_memory("16777216 4194304")
    assert info is not None
    assert {c.key for c in info.categories} == {"app", "free"}


# ---------- 系统标签 ----------

def test_friendly_os_label():
    assert sd.friendly_os_label(
        "Darwin", "27.0.0", "", mac_version="26.0.1",
    ) == "macOS 26.0.1"
    assert sd.friendly_os_label("Darwin", "27.0.0", "") == "macOS 27.0.0"
    assert sd.friendly_os_label(
        "Windows", "10", "10.0.22631",
    ) == "Windows 11 (22631)"
    assert sd.friendly_os_label(
        "Windows", "10", "10.0.19045",
    ) == "Windows 10 (19045)"
    assert sd.friendly_os_label("Windows", "8.1", "6.3.9600") == "Windows 8.1 (9600)"
    assert sd.friendly_os_label(
        "Linux", "6.8", "", distro="Ubuntu 24.04",
    ) == "Ubuntu 24.04"
    assert sd.friendly_os_label(
        "Linux", "6.8", "", wsl=True, wsl_distro="Ubuntu-24.04",
    ) == "WSL · Ubuntu-24.04"
    assert sd.friendly_os_label("FreeBSD", "14.1", "") == "FreeBSD 14.1"


def test_linux_distro_name(monkeypatch):
    fake_files(monkeypatch, {
        "/etc/os-release": 'PRETTY_NAME="Ubuntu 24.04.1 LTS"\n',
    })
    assert sd._linux_distro_name() == "Ubuntu 24.04.1 LTS"


def test_linux_distro_name_name_plus_version(monkeypatch):
    fake_files(monkeypatch, {
        "/etc/os-release": (
            'NAME="Debian GNU/Linux"\n'
            'VERSION="12 (bookworm)"\n'
        ),
    })
    assert sd._linux_distro_name() == "Debian GNU/Linux 12 (bookworm)"


# ---------- Git ----------

def test_parse_git_status():
    porcelain = "## main...origin/main [ahead 1]\n M file.py\n?? new.txt\n"
    info = sd.parse_git_status(porcelain, "3\t1\tfile.py\n-\t-\timage.png\n")
    assert info is not None
    assert info.branch == "main"
    assert info.dirty is True
    assert info.additions == 3
    assert info.deletions == 1
    assert info.untracked == 1


def test_parse_git_status_clean():
    info = sd.parse_git_status("## main...origin/main\n")
    assert info is not None
    assert info.branch == "main"
    assert info.dirty is False
    assert info.additions == 0


def test_parse_git_status_no_commits():
    info = sd.parse_git_status("## No commits yet on main\n?? a.txt\n")
    assert info is not None
    assert info.branch == "main"
    assert info.untracked == 1


def test_parse_git_status_not_a_repo():
    assert sd.parse_git_status("") is None


def test_read_git_uses_status_and_numstat(monkeypatch):
    def fake(cwd, *args, **kwargs):
        if args and args[0] == "status":
            return "## dev\n M a.py\n"
        return "2\t5\ta.py\n"

    monkeypatch.setattr(sd, "_git", fake)
    info = sd.read_git("/tmp/repo")
    assert info is not None
    assert info.branch == "dev"
    assert info.additions == 2
    assert info.deletions == 5


def test_read_git_no_output(monkeypatch):
    monkeypatch.setattr(sd, "_git", lambda *args, **kwargs: "")
    assert sd.read_git("/tmp/not-a-repo") is None


# ---------- 状态栏 ----------

def test_signal_bars_thresholds():
    assert tc.signal_bars(-45)[1] == "极强"
    assert tc.signal_bars(-55)[1] == "强"
    assert tc.signal_bars(-65)[1] == "中"
    assert tc.signal_bars(-75)[1] == "弱"
    assert tc.signal_bars(-95)[1] == "差"
    assert tc.signal_bars(None) == ("", "离线")


def test_signal_bars_ascii_fallback():
    assert tc.signal_bars(-55, unicode_ok=False)[0] == "|||"


def test_display_width_handles_cjk():
    assert tc.display_width("abc") == 3
    assert tc.display_width("中文") == 4
    assert tc.display_width("a中") == 3


def test_fit_segments_drops_low_priority():
    segments = [
        tc.StatusSegment("a", (("class:status.seg", "A" * 10),), 0),
        tc.StatusSegment("b", (("class:status.seg", "B" * 10),), 1),
        tc.StatusSegment("c", (("class:status.seg", "C" * 10),), 2),
    ]
    kept = tc.fit_segments(segments, 25)
    assert [segment.key for segment in kept] == ["a", "b"]
    kept = tc.fit_segments(segments, 40)
    assert [segment.key for segment in kept] == ["a", "b", "c"]


def test_status_segments_contain_system_values():
    snapshot = make_snapshot()
    segments = tc.build_status_segments(
        snapshot, 754, "整活", tc.GLYPHS_UNICODE, now=1700000000,
    )
    text = " | ".join(segment.text for segment in segments)
    assert "wocli v0.7.3" in text
    assert "fix/reported-bugs" in text
    assert "84%" in text
    assert "CPU 23%" in text
    assert "12m34s" in text
    assert "+3" in text
    assert "−0" in text
    assert "✦" in text


def test_status_styles_are_prompt_toolkit_classes():
    snapshot = make_snapshot()
    for mode in tc.MODES:
        segments = tc.build_status_segments(
            snapshot, 1, mode, tc.GLYPHS_UNICODE, now=1700000000,
        )
        for segment in segments:
            for style, _ in segment.parts:
                assert style.startswith("class:"), style


def test_status_fragments_have_two_lines_and_mode():
    snapshot = make_snapshot()
    segments = tc.build_status_segments(
        snapshot, 10, "正常", tc.GLYPHS_UNICODE, now=1700000000,
    )
    fragments = tc.status_fragments(
        segments, "正常", None, tc.GLYPHS_UNICODE, width=140,
    )
    text = "".join(fragment for _, fragment in fragments)
    assert "\n" in text
    first, second = text.split("\n", 1)
    assert "wocli v0.7.3" in first
    assert "▶▶ 正常模式 on" in second
    assert "shift+tab" in second


def test_battery_glyph_ascii_fallback():
    assert tc.battery_glyph(84, unicode_ok=False) == "[b]"


# ---------- 面板 / 帮助 ----------

def test_panel_contains_sections_and_stays_compact():
    snapshot = make_snapshot()
    lines = tc.build_panel_lines(snapshot, tc.GLYPHS_UNICODE, 100)
    text = "\n".join(text_of(line) for line in lines)
    for needle in ("系统上下文", "按类别统计", "应用", "缓存", "系统", "空闲",
                   "CPU", "磁盘", "电池", "网络", "Git"):
        assert needle in text
    assert "wocli v0.7.3" in text
    assert "macOS 27.0" in text
    assert "不是 Git 仓库" not in text
    # 面板太长会把顶部挤出屏幕；这个上限防止以后又加回去
    assert len(lines) <= 30


def test_panel_stacks_on_narrow_width():
    snapshot = make_snapshot()
    lines = tc.build_panel_lines(snapshot, tc.GLYPHS_UNICODE, 50)
    text = "\n".join(text_of(line) for line in lines)
    assert "系统上下文" in text
    assert "应用" in text


def test_panel_ascii_fallback_has_no_unicode_glyphs():
    snapshot = make_snapshot()
    text = "\n".join(text_of(line) for line in tc.build_panel_lines(
        snapshot, tc.GLYPHS_ASCII, 100,
    ))
    assert "#" in text
    assert "▦" not in text
    assert "◈" not in text
    assert "└" not in text
    assert "−" not in text
    assert "…" not in text


def test_status_and_panel_ascii_punctuation():
    snapshot = replace(
        make_snapshot(),
        git=sd.GitInfo(
            "feature/very-long-branch-name-that-needs-truncation", True, 12, 3, 1,
        ),
        wifi=sd.WifiInfo(
            "WoCli-5G", -52, "149", "866 Mbps",
            "系统设置 → 隐私与安全性 → 定位服务",
        ),
    )
    status = " ".join(
        segment.text for segment in tc.build_status_segments(
            snapshot, 1, "正常", tc.GLYPHS_ASCII, now=1700000000,
        )
    )
    assert "..." in status
    assert "−" not in status
    assert "…" not in status

    panel = "\n".join(text_of(line) for line in tc.build_panel_lines(
        snapshot, tc.GLYPHS_ASCII, 100,
    ))
    assert "−" not in panel
    assert "…" not in panel
    assert "->" in panel


def test_panel_handles_missing_data():
    snapshot = make_snapshot()
    snapshot = sd.StatusSnapshot(
        version=snapshot.version,
        cwd=snapshot.cwd,
        system=snapshot.system,
    )
    text = "\n".join(text_of(line) for line in tc.build_panel_lines(
        snapshot, tc.GLYPHS_UNICODE, 100,
    ))
    assert "未获取到" in text
    assert "不是 Git 仓库" in text


def test_help_lines_include_shell_and_registry_commands():
    text = "\n".join(text_of(line) for line in tc.build_help_lines())
    assert "/status" in text
    assert "/theme" in text
    assert "/ip" in text
    assert "驾驶舱命令" in text


def test_doctor_lines_include_environment():
    snapshot = make_snapshot()
    text = "\n".join(text_of(line) for line in tc.build_doctor_lines(
        snapshot,
        "正常",
        tc.get_theme("catppuccin"),
        "3.0.53",
        "~/.wocli_history",
        "~/.wocli_tui.json",
    ))
    assert "prompt_toolkit: 3.0.53" in text
    assert "Catppuccin Mocha" in text
    assert "~/.wocli_history" in text


def test_banner_and_boot_render():
    theme = tc.get_theme("catppuccin")
    banner = tc.build_banner_lines("0.7.3", theme, tc.GLYPHS_UNICODE, 100)
    text = "\n".join(text_of(line) for line in banner)
    assert "wocli v0.7.3" in text
    assert "/status" in text
    boot = tc.build_boot_lines("0.7.3", 10, theme, "测试彩蛋")
    assert len(boot) == 4
    assert "测试彩蛋" in text_of(boot[-1])


# ---------- 输入 / 模式 / 主题 / 偏好 ----------

def test_parse_shell_input():
    assert tc.parse_shell_input("/status") == ("status", [])
    assert tc.parse_shell_input("/theme neon") == ("theme", ["neon"])
    assert tc.parse_shell_input("?") == ("help", [])
    assert tc.parse_shell_input("cow 你好 世界") == ("cow", ["你好", "世界"])
    assert tc.parse_shell_input("   ") is None
    assert tc.parse_shell_input("cow '未闭合") is None


def test_mode_cycle_and_aliases():
    assert tc.next_mode("正常") == "整活"
    assert tc.next_mode("整活") == "死机"
    assert tc.next_mode("死机") == "正常"
    assert tc.normalize_mode("fun") == "整活"
    assert tc.normalize_mode("normal") == "正常"
    assert tc.normalize_mode("nope") is None
    assert tc.mode_label("死机") == "死机模式"


def test_mode_descriptions_cover_all_modes():
    assert set(tc.MODE_DESCRIPTIONS) == set(tc.MODES)
    assert all(tc.MODE_DESCRIPTIONS[mode] for mode in tc.MODES)


def test_theme_cycle_and_fallback():
    assert tc.next_theme("catppuccin") == "neon"
    assert tc.next_theme("neon") == "amber"
    assert tc.next_theme("amber") == "paper"
    assert tc.next_theme("paper") == "catppuccin"
    assert tc.next_theme("unknown") == "catppuccin"
    assert tc.get_theme("unknown").key == "catppuccin"


def test_detect_theme_from_terminal_background():
    assert tc.detect_theme_from_env({"COLORFGBG": "15;0"}) == "catppuccin"
    assert tc.detect_theme_from_env({"COLORFGBG": "0;15"}) == "paper"
    assert tc.detect_theme_from_env({"COLORFGBG": "0;7"}) == "paper"
    assert tc.detect_theme_from_env({"COLORFGBG": "default;default"}) == "catppuccin"
    assert tc.detect_theme_from_env({"TERM_BACKGROUND": "light"}) == "paper"
    assert tc.detect_theme_from_env({"TERM_BACKGROUND": "dark"}) == "catppuccin"
    assert tc.detect_theme_from_env({}) == "catppuccin"


def test_resolve_theme_precedence():
    assert tc.resolve_theme("paper", "neon", {}) == "paper"
    assert tc.resolve_theme(None, "neon", {}) == "neon"
    assert tc.resolve_theme("auto", "neon", {"COLORFGBG": "0;15"}) == "paper"
    assert tc.resolve_theme(None, "auto", {"COLORFGBG": "15;0"}) == "catppuccin"
    assert tc.resolve_theme("nope", "nope", {}) == "catppuccin"


def test_prefs_roundtrip(tmp_path):
    path = tmp_path / "prefs.json"
    tc.save_prefs("neon", "整活", str(path))
    assert tc.load_prefs(str(path)) == {"theme": "neon", "mode": "整活"}


def test_prefs_invalid_file(tmp_path):
    path = tmp_path / "prefs.json"
    path.write_text("not json", encoding="utf-8")
    assert tc.load_prefs(str(path)) == {"theme": None, "mode": None}
    path.write_text(json.dumps({"theme": "nope", "mode": "nope"}), encoding="utf-8")
    assert tc.load_prefs(str(path)) == {"theme": None, "mode": None}
    path.write_text(json.dumps({"theme": "auto", "mode": "fun"}), encoding="utf-8")
    assert tc.load_prefs(str(path)) == {"theme": "auto", "mode": "整活"}
