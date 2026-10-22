"""qr 命令：静区、两种渲染的几何、SVG 导出.

用例不需要二维码解码器：把渲染结果解析回模块矩阵，和原始矩阵逐格比对，
就能锁住静区、行序、半块极性和颜色映射——这几处出错都会直接导致扫不出来。
"""
import re

from wocli.commands import qr_cmd

# 用户反馈扫不出的真实长链，用来守住"紧凑渲染必须能塞进 80 列"这条线
LONG_URL = ("https://www.bilibili.com/video/BV1cQHs6cEN5/"
            "?spm_id_from=333.1387.favlist.content.click"
            "&vd_source=1dfb4d1edcfabf3c3f60fad2fa3acd24")

FINDER = [
    "1111111",
    "1000001",
    "1011101",
    "1011101",
    "1011101",
    "1000001",
    "1111111",
]

# 紧凑渲染里字符 -> (上模块是否深色, 下模块是否深色)
COMPACT_GLYPHS = {
    "\u2588": (False, False),   # 整块白：两个都浅
    "\u2580": (False, True),    # 上半白：上浅下深
    "\u2584": (True, False),    # 下半白：上深下浅
    " ": (True, True),          # 留黑：两个都深
}


def _as_bools(matrix):
    return [[bool(value) for value in row] for row in matrix]


def _parse_wide(lines):
    """宽渲染：每行一个模块行，背景色决定明暗（每个模块两个空格）."""
    rows = []
    for line in lines:
        body = line[len(qr_cmd.INDENT):]
        assert body.endswith(qr_cmd.RESET)
        body = body[:-len(qr_cmd.RESET)]
        dark = False
        row = []
        for token in re.split(r"(\x1b\[\d+m|  )", body):
            if token == qr_cmd.BLACK_BG:
                dark = True
            elif token == qr_cmd.WHITE_BG:
                dark = False
            elif token == "  ":
                row.append(dark)
        rows.append(row)
    return rows


def _parse_compact(lines):
    """紧凑渲染：上下两个模块拼成一个字符."""
    upper_rows, lower_rows = [], []
    for line in lines:
        body = line[len(qr_cmd.INDENT):]
        match = re.match(r"\x1b\[40;37;1m(.*)\x1b\[0m$", body)
        assert match, f"每行都该是「黑底 + 亮白前景」: {line!r}"
        uppers, lowers = [], []
        for char in match.group(1):
            upper_dark, lower_dark = COMPACT_GLYPHS[char]
            uppers.append(upper_dark)
            lowers.append(lower_dark)
        upper_rows.append(uppers)
        lower_rows.append(lowers)

    matrix = []
    for uppers, lowers in zip(upper_rows, lower_rows):
        matrix.append(uppers)
        matrix.append(lowers)
    return matrix


def test_quiet_zone_is_added():
    """qrcode 的 modules 不含静区，渲染前必须自己补 4 模块.

    缺静区会被严格些的解码器直接判为无法识别——qrcode 的 border 参数
    只影响 make_image()，对终端渲染没有任何作用。
    """
    matrix = qr_cmd.build_matrix("https://example.com")
    size = len(matrix)
    assert size % 2 == 1
    for i in range(qr_cmd.QUIET_ZONE):
        assert not any(matrix[i]), f"第 {i} 行不是空白"
        assert not any(matrix[size - 1 - i]), f"倒数第 {i + 1} 行不是空白"
    for row in matrix:
        assert not any(row[:qr_cmd.QUIET_ZONE])
        assert not any(row[-qr_cmd.QUIET_ZONE:])


def test_finder_patterns_stay_intact():
    """补静区不能改动符号本体：偏移 4 的左上角仍是标准 7x7 定位图形."""
    matrix = qr_cmd.build_matrix("hello")
    offset = qr_cmd.QUIET_ZONE
    for dy, expected in enumerate(FINDER):
        row = "".join("1" if value else "0"
                      for value in matrix[offset + dy][offset:offset + 7])
        assert row == expected, f"定位图形第 {dy} 行: {row}"


def test_wide_roundtrip():
    """宽渲染解析回来必须和矩阵逐格一致（一行一个模块行）."""
    matrix = qr_cmd.build_matrix("https://example.com")
    assert _parse_wide(qr_cmd.render_wide(matrix)) == _as_bools(matrix)


def test_compact_roundtrip():
    """紧凑渲染解析回来也必须逐格一致（上下半块极性别弄反）."""
    matrix = qr_cmd.build_matrix("wocli 中文二维码测试")
    parsed = _parse_compact(qr_cmd.render_compact(matrix))
    expected = _as_bools(matrix)
    # 行数为奇数时最后一行只有上半，解析会多补一行空的下半
    assert parsed[:len(expected)] == expected
    assert 0 <= len(parsed) - len(expected) <= 1


def test_lines_have_consistent_width():
    """同一种渲染里所有行必须等宽：参差不齐或超宽换行都会把码切坏."""
    matrix = qr_cmd.build_matrix("wocli 终端二维码测试，中文内容也要能扫")
    for lines, per_module in ((qr_cmd.render_wide(matrix), 2),
                              (qr_cmd.render_compact(matrix), 1),
                              (qr_cmd.render_plain(matrix), 1)):
        expected = len(matrix[0]) * per_module + len(qr_cmd.INDENT)
        for line in lines:
            body = re.sub(r"\x1b\[[0-9;]*m", "", line)
            assert len(body) == expected


def test_wide_needs_wide_terminal():
    """真实长链：宽渲染要两倍宽度，80 列终端放不下——所以需要紧凑渲染兜底."""
    matrix = qr_cmd.build_matrix(LONG_URL)
    modules = len(matrix[0])
    assert modules * 2 + len(qr_cmd.INDENT) > 80
    # 紧凑渲染必须塞得进 80 列，否则默认窗口里就没法显示了
    assert modules + len(qr_cmd.INDENT) <= 80


def test_choose_layout():
    """宽度够用宽渲染（不依赖字形），否则退回紧凑渲染."""
    assert qr_cmd.choose_layout(33, 120) == "wide"
    assert qr_cmd.choose_layout(33, 70) == "wide"      # 33*2+2=68 正好放得下
    assert qr_cmd.choose_layout(33, 60) == "compact"


def test_parse_args():
    text, svg, compact = qr_cmd.parse_args(["hello", "world"])
    assert (text, svg, compact) == ("hello world", None, False)
    assert qr_cmd.parse_args(["-s", "a.svg", "x", "y"]) == (
        "x y", "a.svg", False)

    text, svg, compact = qr_cmd.parse_args(["--svg", "out.svg", "hello"])
    assert (text, svg, compact) == ("hello", "out.svg", False)

    text, svg, compact = qr_cmd.parse_args(["--compact", "hello"])
    assert (text, svg, compact) == ("hello", None, True)

    text, svg, compact = qr_cmd.parse_args(["-c", "--svg", "q.svg", "hi"])
    assert (text, svg, compact) == ("hi", "q.svg", True)


def test_svg_output(tmp_path):
    """SVG 是任何终端都能用的兜底：结构、静区、深色模块数都要对."""
    matrix = qr_cmd.build_matrix("https://example.com")
    path = tmp_path / "qr.svg"
    qr_cmd.render_svg(matrix, str(path))
    text = path.read_text(encoding="utf-8")
    size = len(matrix)

    assert f'viewBox="0 0 {size} {size}"' in text
    assert 'shape-rendering="crispEdges"' in text      # 关抗锯齿，避免模块间出现灰边
    assert 'fill="#ffffff"' in text

    rects = re.findall(
        r'<rect x="(\d+)" y="(\d+)" width="1" height="1"/>', text)
    dark = sum(1 for row in matrix for value in row if value)
    assert len(rects) == dark

    xs = [int(x) for x, _ in rects]
    ys = [int(y) for _, y in rects]
    quiet = qr_cmd.QUIET_ZONE
    assert min(xs) >= quiet and min(ys) >= quiet
    assert max(xs) <= size - 1 - quiet and max(ys) <= size - 1 - quiet


def test_chinese_payload_builds():
    matrix = qr_cmd.build_matrix("你好，世界")
    assert len(matrix) >= 25 + 2 * qr_cmd.QUIET_ZONE
    assert len(matrix) == len(matrix[0])


def test_plain_fallback_has_no_ansi():
    matrix = qr_cmd.build_matrix("hello")
    joined = "".join(qr_cmd.render_plain(matrix))
    assert "\x1b[" not in joined
    assert len(qr_cmd.render_plain(matrix)) == (len(matrix) + 1) // 2
