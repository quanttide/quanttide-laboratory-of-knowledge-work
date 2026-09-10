"""案卷字段化验证：一件交付的完整过程——契约 + 产出 + 审查 + 裁决 + 成果。

案卷把「谁按什么做的、核对了什么、谁拍的板、最后交出什么」记成一条可追溯的记录。
审查者报告直接由契约的机械核对生成（复用 ../contract/contract.py）。

用法：
  python3 dossier.py          打印案卷
  python3 dossier.py --save   落成 dossier.md
"""

import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "contract"))
import contract as contract_layer  # noqa: E402


@dataclass
class Dossier:
    """一件交付的案卷。"""

    goal: str  # 契约的目标
    output_spec: str  # 契约的输出形态
    produced: list[str] = field(default_factory=list)  # 生成者产出
    review: list[tuple[str, bool]] = field(default_factory=list)  # 审查者报告：检查项 + 结论
    gated: list[str] = field(default_factory=list)  # 留给闸门的检查项
    decision: str = ""  # 人类裁决
    result: list[str] = field(default_factory=list)  # 最终成果

    def problems(self) -> list[str]:
        """案卷自查：五段齐全，且没有未通过的审查项。"""
        issues = []
        for part, value in (("产出", self.produced), ("审查", self.review), ("裁决", self.decision), ("成果", self.result)):
            if not value:
                issues.append(f"缺{part}")
        issues += [f"审查未过：{what}" for what, ok in self.review if not ok]
        return issues

    def render(self) -> str:
        lines = [f"# 案卷：{self.goal}", "", f"**输出形态**：{self.output_spec}", "", "## 生成者产出"]
        lines += [f"- {item}" for item in self.produced]
        lines += ["", "## 审查者报告"]
        lines += [f"- {'✓' if ok else '✗'} {what}" for what, ok in self.review]
        lines += [f"- ⧗ {what}（留给闸门）" for what in self.gated]
        lines += ["", "## 人类裁决", "", self.decision, "", "## 最终成果"]
        lines += [f"- {item}" for item in self.result]
        return "\n".join(lines) + "\n"


def today_dossier(root: Path) -> Dossier:
    """今天的真实交付：把 Default 模块技术设计从主体迁入本领域。"""
    passed, failed = contract_layer.MIGRATION.verify(root)
    return Dossier(
        goal=contract_layer.MIGRATION.goal,
        output_spec=contract_layer.MIGRATION.output,
        produced=[
            "目标侧写入 `examples/default/examples/default-module/default.md`",
            "改写为对外可读的设计：两种模式、三种记录、三个角色",
        ],
        review=[(check.what, True) for check in passed] + [(check.what, False) for check in failed],
        gated=[check.what for check in contract_layer.MIGRATION.gate()],
        decision="创始人 2026-09-10 通过——设计与源位置同构，命名沿用目标侧规则。",
        result=[
            "laboratory：新增 `examples/default-module/default.md`",
            "quanttide-tech：删除 `apps/qtdata/examples/default/modules/default.md`",
            "父仓库指针已更新",
        ],
    )


def main(argv):
    root = contract_layer.repo_root()
    dossier = today_dossier(root)
    text = dossier.render()
    print(text, end="")
    if "--save" in argv:
        target = Path(__file__).with_name("dossier.md")
        target.write_text(text, encoding="utf-8")
        print(f"\n已保存：{target}")
    issues = dossier.problems()
    print("\n自查：" + ("案卷完整。" if not issues else "；".join(issues)))
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
