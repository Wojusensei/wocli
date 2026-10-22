"""qr 命令：静区、渲染几何，以及"按上下模块配色"的渲染不变式.

这些用例不需要二维码解码器：把渲染结果再解析回模块矩阵，和原始矩阵逐格比对，
就能锁住静区、行序、上下半块和颜色映射——这几点出错都会直接导致扫不出来。
"""
import re

from wocli.commands import qr_cmd

BLOCK_TOKEN = re.compile(r"(\x1b\[\d+;\d+m|\u2580|\x1b\[0m)")
CELL_TOKEN = re.compile(r"(\x1b\[\d+m| +)")

FINDER = [
    "1111111",
    "1000001",
    "1011101",
    "1011101",
    "1011101",
    "1000001",
    "1111111",
]


def _as_bools(matrix):
    return [[bool(value) for value in row] for row in matrix]


def _parse_blocks(lines):
    """把半块渲染的文本行解析回模块矩阵（上下两行一组）."""
    upper_rows, lower_rows = [], []
    for line in lines:
        assert line.startswith(qr_cmd.INDENT)
        body = line[len(qr_cmd.INDENT):]
        foreground = background = None
        uppers, lowers = [], []
        for token in BLOCK_TOKEN.split(body):
            if token == qr_cmd._HALF_BLOCK:
                assert foreground is not None and background is not None, \
                    "没有配色就画了半块"
                uppers.append(foreground == qr_cmd._FG[True])
                lowers.append(background == qr_cmd._BG[True])
            elif token.startswith("\x1b[") and ";" in token:
                fg_text, bg_text = token[2:-1].split(";")
                foreground, background = int(fg_text), int(bg_text)
        upper_rows.append(uppers)
        lower_rows.append(lowers)

    matrix = []
    for uppers, lowers in zip(upper_rows, lower_rows):
        matrix.append(uppers)
        matrix.append(lowers)
    return matrix


def _parse_cells(lines, scale):
    """把整格渲染的文本行解析回模块矩阵（一行一个模块）."""
    matrix = []
    for line in lines:
        assert line.startswith(qr_cmd.INDENT)
        body = line[len(qr_cmd.INDENT):]
        dark = None
        row = []
        for token in CELL_TOKEN.split(body):
            if token.startswith("\x1b["):
                code = token[2:-1]
                if code != "0":
                    dark = int(code) == qr_cmd._BG[True]
            elif token:
                assert dark is not None, "没有背景色就画了格子"
                assert len(token) % scale == 0
                row.extend([dark] * (len(token) // scale))
        matrix.append(row)
    return matrix


def test_quiet_zone_is_added():
    """qrcode 的 modules 不含静区，渲染前必须自己补 4 模块.

    缺静区会被微信这类严格解码器直接判为无法识别——之前 border=4 只对
    make_image() 生效，终端路径其实一直没有静区。
    """
    matrix = qr_cmd.build_matrix("https://example.com")
    size = len(matrix)
    assert size % 2 == 1  # 符号尺寸是奇数，补 8 之后仍是奇数
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


def test_blocks_roundtrip():
    """半块渲染再解析回来必须逐格一致（上下半块和行序都不能错）."""
    matrix = qr_cmd.build_matrix("https://example.com")
    parsed = _parse_blocks(qr_cmd.render_blocks(matrix))
    expected = _as_bools(matrix)
    # 行数是奇数时最后一行只有上半，解析会多补一行空的下半
    assert parsed[:len(expected)] == expected
    assert 0 <= len(parsed) - len(expected) <= 1


def test_cells_roundtrip():
    """整格渲染一行一个模块，解析回来也要一致（中文内容同样覆盖）."""
    matrix = qr_cmd.build_matrix("wocli 中文二维码测试")
    for scale in (1, 2):
        parsed = _parse_cells(qr_cmd.render_cells(matrix, scale), scale)
        assert parsed == _as_bools(matrix)


def test_cells_top_row_is_blank():
    """整格渲染的第一行是静区：只该有白底，不该出现黑底."""
    matrix = qr_cmd.build_matrix("hello")
    first = qr_cmd.render_cells(matrix, 1)[0]
    assert ("\033[%dm" % qr_cmd._BG[True]) not in first


def test_layout_prefers_cells_when_it_fits():
    """窗口放得下就用不依赖字形的整格渲染，窄了用单字符宽，矮了退回半块."""
    assert qr_cmd.choose_layout(33, 120, 60) == ("cells", 2)
    assert qr_cmd.choose_layout(33, 40, 60) == ("cells", 1)
    assert qr_cmd.choose_layout(33, 120, 24) == ("blocks", 1)
    assert qr_cmd.choose_layout(33, 30, 60) == ("blocks", 1)


def test_chinese_payload_builds():
    matrix = qr_cmd.build_matrix("你好，世界")
    assert len(matrix) >= 25 + 2 * qr_cmd.QUIET_ZONE
    assert len(matrix) == len(matrix[0])


def test_plain_fallback_uses_block_chars():
    """不支持 ANSI 时退回 █▀▄，静区表现为空格，行数减半."""
    matrix = qr_cmd.build_matrix("hello")
    lines = qr_cmd.render_plain(matrix)
    assert len(lines) == (len(matrix) + 1) // 2
    allowed = set("\u2588\u2580\u2584 ")
    assert all(set(line.strip()) <= allowed for line in lines)
    assert "\x1b[" not in "".join(lines)
