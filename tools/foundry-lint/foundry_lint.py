#!/usr/bin/env python3
"""foundry-lint：檢查文件是否含模板規定的必備二級標題。

規格來源：docs/features/foundry-lint/LLD.md（介面、資料模型、流程、錯誤表均依該文件）。
exit code：0＝通過、1＝不通過、2＝執行／使用錯誤。
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

TYPE_TO_TEMPLATE: dict = {
    "brd": "brd.md", "prd": "prd.md", "hld": "hld.md", "lld": "lld.md",
    "review-report": "review-report.md", "test-plan": "test-plan.md",
}

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
FENCE_RE = re.compile(r"^\s{0,3}(```|~~~)")


class LintError(Exception):
    """執行／使用錯誤（exit 2），訊息直接寫 stderr。"""


@dataclass
class CheckResult:
    file: str
    doc_type: str
    required: list
    missing: list

    @property
    def passed(self) -> bool:
        return not self.missing


def extract_headings(text: str) -> list:
    """回傳二級標題的標題文字有序清單（不含 ``## `` 前綴），保序、不去重。

    圍欄程式碼區塊（``` 或 ~~~）內的行一律跳過；已知簡化：不區分兩種
    圍欄的配對、不比對圍欄長度（見 LLD 第 4 節）。
    """
    headings = []
    in_fence = False
    for line in text.splitlines():
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = HEADING_RE.match(line)
        if m and len(m.group(1)) == 2:
            headings.append(m.group(2))
    return headings


def read_text(path) -> str:
    return Path(path).read_text(encoding="utf-8", errors="replace")


def build_rules(template_path) -> list:
    """讀模板並抽出必備標題（去重保序）；讀不到或抽不出即 LintError。"""
    try:
        text = read_text(template_path)
    except OSError as e:
        raise LintError(
            f"foundry-lint: 錯誤：無法讀取模板：{template_path}（{e.strerror or e}）"
        ) from e
    required = list(dict.fromkeys(extract_headings(text)))
    if not required:
        raise LintError(
            f"foundry-lint: 錯誤：模板未含任何二級標題，無法建立規則：{template_path}"
        )
    return required


def check_file(file: str, doc_type: str, required: list) -> CheckResult:
    try:
        text = read_text(file)
    except OSError as e:
        raise LintError(
            f"foundry-lint: 錯誤：無法讀取檔案：{file}（{e.strerror or e}）"
        ) from e
    found = set(extract_headings(text))
    missing = [h for h in required if h not in found]
    return CheckResult(file=file, doc_type=doc_type, required=required, missing=missing)


def render_text(result: CheckResult) -> str:
    if result.passed:
        return (
            f"✅ {result.file} 通過 {result.doc_type} 模板章節檢查"
            f"（必備章節 {len(result.required)} 項齊備）"
        )
    lines = [
        f"❌ {result.file} 未通過 {result.doc_type} 模板章節檢查，"
        f"缺少 {len(result.missing)} 項必備章節："
    ]
    lines.extend(f"  - ## {h}" for h in result.missing)
    return "\n".join(lines)


def render_json(result: CheckResult) -> str:
    return json.dumps(
        {
            "file": result.file,
            "type": result.doc_type,
            "passed": result.passed,
            "missing_sections": [f"## {h}" for h in result.missing],
        },
        ensure_ascii=False,
        indent=2,
    )


def parse_args(argv):
    parser = argparse.ArgumentParser(
        prog="foundry-lint",
        description="檢查文件是否含模板規定的必備二級標題",
    )
    parser.add_argument("--type", required=True, choices=TYPE_TO_TEMPLATE.keys())
    parser.add_argument("--format", default="text", choices=["text", "json"])
    parser.add_argument("--templates-dir", default=None)
    parser.add_argument("file")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    exit_code = 0
    try:
        if args.templates_dir:
            templates_dir = Path(args.templates_dir)
        else:
            templates_dir = Path(__file__).resolve().parent.parent.parent / "templates"
        template_path = templates_dir / TYPE_TO_TEMPLATE[args.type]
        required = build_rules(template_path)
        result = check_file(args.file, args.type, required)
    except LintError as e:
        print(e, file=sys.stderr)
        exit_code = 2
    else:
        render = render_json if args.format == "json" else render_text
        print(render(result))
        if not result.passed:
            exit_code = 1
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
