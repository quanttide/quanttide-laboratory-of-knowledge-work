#!/usr/bin/env python3
"""程序自带测试：不用额外依赖，干净检出上直接跑。

  python3 tests/test_kg.py

两套夹具：真实工作区（集成，会因仓库变脏报红）与临时目录里现搭的假仓库（单元，不碰真文件）。
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

LAB = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(LAB / "src"))

from kg import assets as assets_layer  # noqa: E402
from kg import catalog as catalog_layer  # noqa: E402
from kg import checks as checks_layer  # noqa: E402
from kg import cli, material as material_layer  # noqa: E402
from kg import records  # noqa: E402
from kg import report  # noqa: E402
from kg import workflow as flow_layer  # noqa: E402

RESULTS: list[tuple[str, bool, str]] = []
TASK_OK = """# 任务：核对

## 目标

看结果对不对。

## 步骤

- 跑一遍判据

## 验收

- [ ] 机械：日志在 `path:data/journal/README.md`
- [ ] 闸门：创始人过目
"""


def test(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, ok, detail))


def fake_repo(tmp: Path, stray: bool = False) -> Path:
    """按资产表搭一个齐备的假工作区，可选塞一个未登记目录。"""
    root = tmp / "second-brain"
    stated = {name for _, name in assets_layer.STATED}
    for asset in assets_layer.assets():
        if asset.name in assets_layer.LOCATION:
            continue
        (root / ("data" if asset.name in stated else "docs") / asset.name).mkdir(parents=True)
    (root / "packages" / "quanttide-demo-toolkit").mkdir(parents=True)
    (root / "apps" / "demo").mkdir(parents=True)
    (root / "examples" / "default").mkdir(parents=True)
    if stray:
        (root / "data" / "未登记目录").mkdir(parents=True)
    return root


def with_repo(root: Path) -> None:
    """装上 git 并提交一次，让材料的时间字段有处可取。"""
    for cmd in (["init", "-q"], ["add", "-A"], ["-c", "user.email=lab@example.com", "-c", "user.name=lab", "commit", "-qm", "首次提交"]):
        subprocess.run(["git", *cmd], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-q", "--amend", "--date=2026-09-10T09:00:00", "--no-edit"], cwd=root, check=True, capture_output=True)


def workspace(real: Path) -> None:
    """工作区层面：资产表、目录、材料。"""
    test("契约是二十格", len(assets_layer.assets()) == 20, f"实得 {len(assets_layer.assets())}")
    test("真实工作区二十格齐备", not assets_layer.missing(real), f"缺 {[a.kind for a in assets_layer.missing(real)]}")

    with tempfile.TemporaryDirectory() as tmp:
        clean = fake_repo(Path(tmp) / "clean")
        test("假仓库：齐备时无缺资产", not assets_layer.missing(clean))
        test("假仓库：齐备时无未登记", not catalog_layer.build(clean).unregistered(clean))
        dirty = fake_repo(Path(tmp) / "dirty", stray=True)
        stray = catalog_layer.build(dirty).unregistered(dirty)
        test("假仓库：未登记目录被揪出", [p.name for p in stray] == ["未登记目录"], f"实得 {[p.name for p in stray]}")

    catalog = catalog_layer.build(real)
    test("按名词条命中规格", any("material.md" in str(e.path) for e in catalog.find("材料")))
    test("模糊兜底命中", bool(catalog.find("日志规范")))

    with tempfile.TemporaryDirectory() as tmp:
        root = fake_repo(Path(tmp) / "材料")
        (root / "data" / "journal" / "2026-09-10.md").write_text("# 今天\n\n记一笔。\n", encoding="utf-8")
        (root / "data" / "profile" / "iGuo.md").write_text("# 我\n\n档案一页。\n", encoding="utf-8")
        with_repo(root)
        found = dict(material_layer.materials(root))
        journal, profile = found["data/journal/2026-09-10.md"], found["data/profile/iGuo.md"]
        test("材料：四字段填得出", not journal.missing and not profile.missing)
        test("材料：时间取首次提交日期", journal.created_at == "2026-09-10", f"实得 {journal.created_at}")
        test("材料：阶段由位置承担", journal.stage == "原始" and profile.stage == "材料")


def instruction(real: Path) -> None:
    """指令与报告：三段、判据、核对。"""
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "指令.md"
        report.new_instruction(target, "改 data/journal/README.md")
        fresh = target.read_text(encoding="utf-8")
        test("指令：骨架三段齐全", all(f"## {name}" in fresh for name in records.TASK_SECTIONS))
        test("指令：以某件东西为题写进目标", "改 data/journal/README.md" in fresh)

        checks_text = """## 验收

- [ ] 机械：目标侧文件已就位 `path:data/journal/README.md`
- [ ] 机械：旧文件已删除 `absent:gone.md`
- [ ] 闸门：落点与源位置同构
- [ ] 机械：<占位不算判据> `path:不存在`
"""
        with tempfile.TemporaryDirectory() as inner:
            root = Path(inner) / "repo"
            (root / "data" / "journal").mkdir(parents=True)
            (root / "data" / "journal" / "README.md").write_text("# 日志\n", encoding="utf-8")
            items = checks_layer.parse(checks_text)
            results, gates = checks_layer.run(root, items)
            test("判据：机械与闸门分得开，占位不算", len(results) == 2 and len(gates) == 1, f"机械 {len(results)}，闸门 {len(gates)}")
            (root / "gone.md").write_text("还在\n", encoding="utf-8")
            failed = [ok for _, ok, _ in checks_layer.run(root, items)[0]]
            test("判据：该报红时报红", failed.count(False) == 1, f"实得 {failed}")

        good = Path(tmp) / "好指令.md"
        good.write_text(TASK_OK, encoding="utf-8")
        audit = report.audit_instruction(real, good)
        test("核对指令：三段齐全、机械项有结论", audit.ok and len(audit.rows) >= 2, str(audit.lines[:2]))


def runs(real: Path) -> None:
    """工作流与运行：步骤关联任务、执行一步、报告与历史。"""
    with tempfile.TemporaryDirectory() as tmp:
        root = fake_repo(Path(tmp) / "run")
        (root / "data" / "journal" / "2026-09-10.md").write_text("# 今天\n", encoding="utf-8")
        (root / "data" / "journal" / "README.md").write_text("# 日志\n", encoding="utf-8")
        data = Path(tmp) / "data"
        started = report.run_new(root, "试一次", data, ["材料", "核对", "历史"], "把纪律落下来")
        test("起运行：步骤表就是工作流写的顺序", [row[0] for row in started.rows] == ["材料", "核对", "历史"], str(started.rows))

        run = flow_layer.open_run(root, "试一次", data)
        test("数据按三家分放", (data / "workflows" / "试一次.md").is_file() and (data / "tasks" / "试一次").is_dir() and (data / "artifacts" / "试一次").is_dir())
        test("每步关联一个任务（三段骨架）", all(set(records.read_sections(run.task_of(s.name))) >= set(records.TASK_SECTIONS) for s in run.steps()))
        test("起运行时记录一笔", len(run.events()) == 1)

        run.task_of("核对").write_text(TASK_OK, encoding="utf-8")
        first = report.run_step(root, "试一次", "材料", "记了一条", data)
        test("执行一步：没有判据也能记一笔", first.ok and first.lines[0].startswith("✓ 材料"), str(first.lines[:1]))
        step = report.run_step(root, "试一次", "核对", "跑了一遍", data)
        test("执行一步：判据通过", step.ok and any(r[1] == "✓" for r in step.rows), str(step.rows))
        test("执行一步：闸门项列出来", any(row[1] == "闸门" for row in step.rows))
        test("执行一步：记账了", len(run.events()) == 3, f"实得 {len(run.events())}")
        test("执行一步：下一步跳到历史", run.next_step().name == "历史", str(run.next_step()))

        written = (data / "artifacts" / "试一次" / "report.md").read_text(encoding="utf-8")
        test("报告：执行记录写下来了", "## 执行记录" in written and "核对" in written)
        test("报告：闸门项留给人", "## 闸门项" in written and "⧗" in written)
        test("报告：段位就是 records 说的", records.missing_sections(data / "artifacts" / "试一次" / "report.md", records.REPORT_SECTIONS) == [])

        test("列运行：还剩历史没做", report.run_list(root, data).rows[0][1] == "历史")
        report.run_history(root, "试一次", "先有纪律，再有工具。", data)
        test("历史：叙事进 artifacts", records.prose(data / "artifacts" / "试一次" / "history.md") != "")
        test("历史写完：这一步也算做过", report.run_list(root, data).rows[0][1] == "做完")
        test("执行不认得的步骤就报错", not report.run_step(root, "试一次", "乱来", "", data).ok)

        # 报告与历史进的是工作区外的实验室数据仓
        test("数据全落在数据仓的三家里", run.workflow_file.is_relative_to(data / "workflows") and run.tasks_dir.is_relative_to(data / "tasks") and run.artifacts_dir.is_relative_to(data / "artifacts"))


def links(real: Path) -> None:
    """编号与补建。"""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "second-brain"
        (root / "data" / "journal").mkdir(parents=True)
        before = len(assets_layer.missing(root))
        report.audit(root, make=True)
        left = {asset.name for asset in assets_layer.missing(root)}
        test("审计：能补建缺的格子", len(assets_layer.missing(root)) < before and (root / "data" / "history" / "README.md").is_file())
        test("审计：独立仓库那三格不凭空建", left == set(assets_layer.LOCATION), f"剩 {sorted(left)}")


def gui_smoke(real: Path) -> None:
    """界面冒烟：装了 PySide6 的窗口模块就跑，没装就跳过。"""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtWidgets import QApplication

        from kg import gui
    except ImportError:
        print("（未装 PySide6 窗口模块，跳过界面冒烟：pip install PySide6-Essentials）")
        return
    app = QApplication.instance() or QApplication([])
    window = gui.Window(real)
    browser = window.browser
    browser.select_action("目录")
    test("界面：目录出得了表", bool(browser.run_current().rows))
    browser.select_action("审计")
    test("界面：审计通过", browser.run_current().ok)
    browser.select_action("核对指令")
    browser.widgets["指令文件"].setText(str(LAB / "data" / "tasks" / "文档迁移" / "搬运.md"))
    audit = browser.run_current()
    test("界面：核对真实指令", audit.ok and len(audit.rows) >= 2, f"行 {len(audit.rows)}")
    browser.select_action("找文档")
    test("界面：空输入先拦住", not browser.run_current().ok)
    groups = [spec.group for spec in gui.SPECS]
    test("界面：浏览页分四组", groups == ["工作区", "工作区", "查看", "查看", "指令", "指令", "报告", "报告"], str(groups))

    with tempfile.TemporaryDirectory() as tmp:
        fake = fake_repo(Path(tmp) / "desk")
        (fake / "data" / "journal" / "2026-09-10.md").write_text("# 今天\n", encoding="utf-8")
        data = Path(tmp) / "data"
        desk = gui.Desk(fake, data)
        test("台面：没有运行时提示新建", "新建" in desk.next_label.text())
        flow_layer.create(fake, "试一次", data, ["材料", "核对"], "把纪律落下来")
        desk.reload()
        test("台面：步骤表按工作流列出", desk.steps_table.rowCount() == 2 and desk.steps_table.item(0, 2).text() == "—")
        desk.selected_step()
        report.run_step(fake, "试一次", "材料", "记了一条", data)
        desk.reload()
        test("台面：状态跟着走", desk.steps_table.item(0, 2).text() == "✓" and desk.log_table.rowCount() >= 2)
    window.close()
    del app


def main() -> int:
    real = assets_layer.repo_root()
    workspace(real)
    instruction(real)
    runs(real)
    links(real)
    gui_smoke(real)

    for name, ok, detail in RESULTS:
        print(f"{'✓' if ok else '✗'} {name}" + (f"——{detail}" if detail and not ok else ""))
    bad = [name for name, ok, _ in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(bad)}/{len(RESULTS)} 通过。")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
