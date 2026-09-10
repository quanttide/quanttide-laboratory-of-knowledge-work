"""图形入口：主界面是「当前这任务」，动作只是它的下一步。

  kg gui        或   ./kg-gui

两页：
  台面——选任务，看它七格状态与流水，点「下一步」往前走，事实自动记进这个任务；
  浏览——工作区层面的动作（目录、审计、找文档、看材料）与不挂在任务上的一件件记录。
"""

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QFontDatabase
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from . import assets as assets_layer
from . import task as task_layer
from . import workflow as flow_layer
from . import catalog as catalog_layer
from . import records
from . import report

STEPS = (
    ("材料", "material", "记一条材料"),
    ("指令", "instruction", "写指令：目标 / 步骤 / 验收（判据写在验收里）"),
    ("核对", "review", "跑机械核对，结果写进案卷"),
    ("产出", "output", "记一笔产出"),
    ("裁决", "decision", "写下裁决"),
    ("成果", "finish", "收尾：产出收束成成果，写进报告"),
    ("历史", "history", "写这个任务的来龙去脉——报告记事，历史叙事"),
)


# ---- 浏览页：工作区层面的动作 ----


def material_paths(values: dict) -> list[str] | None:
    return values.get("材料路径", "").split() or None


def optional(field: str) -> str:
    """可选字段的名字：去掉「（可留空）」就是它的本来面目。"""
    return field.replace("（可留空）", "")


def value(values: dict, field: str) -> str:
    return values.get(field, "").strip()


@dataclass(frozen=True)
class Spec:
    """一个动作：分在哪一组、栏目名、说明、要填的字段、怎么跑；能导出的还有取数函数。"""

    group: str
    name: str
    hint: str
    fields: tuple[str, ...]
    run: object
    export: str = ""
    payload: object = None


# 分四组：工作区看整体，查看看一件，契约与案卷各管一种记录
SPECS = (
    Spec("工作区", "目录", "列全部条目——契约 × 目录", (), lambda root, v: report.catalog(root), "目录.json", lambda root, v: report.catalog_payload(root)),
    Spec("工作区", "审计", "契约有而工作区无、工作区有而契约无", ("补建缺的资产",), lambda root, v: report.audit(root, make=bool(v.get("补建缺的资产"))), "审计.json", lambda root, v: report.audit_payload(root)),
    Spec("查看", "找文档", "按名找——认文件名与中文标题", ("名字", "看正文"), lambda root, v: report.find(root, value(v, "名字"), bool(v.get("看正文")))),
    Spec("查看", "看材料", "类型 / 内容 / 来源 / 时间；阶段由位置承担", ("材料路径",), lambda root, v: report.material(root, material_paths(v)), "材料.json", lambda root, v: report.material_payload(root, material_paths(v))),
)

CAN_ABOUT = ("目录", "找文档", "看材料")


class Browser(QWidget):
    """浏览页：左栏选动作，右栏填参数，下边出结果。"""

    def __init__(self, root: Path):
        super().__init__()
        self.root = root
        self.spec = SPECS[0]
        self.widgets: dict[str, QWidget] = {}
        self.rows: dict[int, Spec | None] = {}
        self.last_result: report.Result | None = None
        self._build()
        self.select_action("目录")

    def _build(self) -> None:
        columns = QHBoxLayout(self)
        self.list = QListWidget()
        self.fill_actions()
        self.list.setFixedWidth(150)
        self.list.currentRowChanged.connect(self._select)
        columns.addWidget(self.list)

        right = QVBoxLayout()
        self.form_host = QWidget()
        self.form = QFormLayout(self.form_host)
        self.form.setContentsMargins(0, 4, 0, 0)
        self.form.setHorizontalSpacing(12)
        self.form.setVerticalSpacing(8)
        self.form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        right.addWidget(self.form_host)

        self.hint_label = QLabel()
        self.hint_label.setWordWrap(True)
        self.hint_label.setStyleSheet("color: #666;")
        right.addWidget(self.hint_label)

        buttons = QHBoxLayout()
        self.run_button = QPushButton("执行")
        self.run_button.clicked.connect(self.run_current)
        buttons.addWidget(self.run_button)
        self.export_button = QPushButton("导出…")
        self.export_button.clicked.connect(self._export)
        buttons.addWidget(self.export_button)
        self.about_button = QPushButton("以选中项立契约")
        self.about_button.clicked.connect(self._instruction_about)
        buttons.addWidget(self.about_button)
        buttons.addStretch(1)
        right.addLayout(buttons)

        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        self.table = QTableWidget()
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.itemDoubleClicked.connect(lambda _: self._open_row(self.table.currentRow()))
        self.stack = QStackedWidget()
        self.stack.addWidget(self.table)
        self.stack.addWidget(self.text)
        right.addWidget(self.stack, 1)
        columns.addLayout(right, 1)

    def fill_actions(self) -> None:
        group = None
        for spec in SPECS:
            if spec.group != group:
                group = spec.group
                header = QListWidgetItem(group)
                header.setFlags(Qt.ItemFlag.ItemIsEnabled)
                font = header.font()
                font.setBold(True)
                header.setFont(font)
                header.setForeground(QColor("#666666"))
                self.list.addItem(header)
                self.rows[self.list.count() - 1] = None
            self.list.addItem(QListWidgetItem(spec.name))
            self.rows[self.list.count() - 1] = spec

    def select_action(self, name: str) -> None:
        for row, spec in self.rows.items():
            if spec and spec.name == name:
                self.list.setCurrentRow(row)
                return
        raise KeyError(name)

    def _select(self, row: int) -> None:
        spec = self.rows.get(row)
        if spec is None:
            return
        self.spec = spec
        while self.form.count():
            item = self.form.takeAt(0)
            if widget := item.widget():
                widget.deleteLater()
        self.widgets = {}
        for field in self.spec.fields:
            if field in ("看正文", "补建缺的资产"):
                widget = QCheckBox()
                self.widgets[field] = widget
            elif optional(field).endswith("文件") or optional(field) in ("以它为题",):
                widget = self._with_browse(field)
            else:
                widget = QLineEdit()
                widget.setPlaceholderText("留空看全部；多个用空格分开" if field == "材料路径" else field)
                self.widgets[field] = widget
            self.form.addRow(field, widget)
        self.export_button.setVisible(bool(self.spec.export))
        self.about_button.setVisible(self.spec.name in CAN_ABOUT)
        self.hint_label.setText(self.spec.hint)
        self.show_result(report.Result(lines=[f"{self.spec.name}：{self.spec.hint}"]))
        if not self.spec.fields:  # 没有参数的动作（目录、审计）选中就直接出结果
            self.run_current()

    def _with_browse(self, field: str) -> QWidget:
        box = QWidget()
        layout = QHBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        edit = QLineEdit()
        edit.setPlaceholderText("可留空" if field != optional(field) else "路径")
        layout.addWidget(edit, 1)
        button = QPushButton("浏览…")

        def choose() -> None:
            if optional(field) == "目标文件":
                path, _ = QFileDialog.getSaveFileName(self, "写到哪", str(self.root), "Markdown (*.md)")
            else:
                path, _ = QFileDialog.getOpenFileName(self, "选文件", str(self.root), "Markdown (*.md)")
            if path:
                edit.setText(path)

        button.clicked.connect(choose)
        layout.addWidget(button)
        self.widgets[field] = edit
        return box

    def values(self) -> dict:
        gathered = {}
        for field, widget in self.widgets.items():
            if isinstance(widget, QCheckBox):
                gathered[field] = widget.isChecked()
            elif isinstance(widget, QLineEdit):
                gathered[field] = widget.text().strip()
        return gathered

    def run_current(self) -> report.Result:
        values = self.values()
        for field in self.spec.fields:
            if field not in ("看正文", "补建缺的资产", "材料路径") and field == optional(field) and not values[field]:
                result = report.Result(ok=False, lines=[f"请先填「{field}」"])
                self.show_result(result)
                return result
        try:
            result = self.spec.run(self.root, values)
        except Exception as error:  # 出错也留在窗里，别让界面崩掉
            result = report.Result(ok=False, lines=[f"出错：{type(error).__name__}: {error}"])
        self.show_result(result)
        return result

    def show_result(self, result: report.Result) -> None:
        self.last_result = result
        self.text.setPlainText("\n".join(result.lines))
        if result.columns and result.rows:
            self.table.setColumnCount(len(result.columns))
            self.table.setHorizontalHeaderLabels(list(result.columns))
            self.table.setRowCount(len(result.rows))
            for row, values in enumerate(result.rows):
                for col, cell in enumerate(values):
                    self.table.setItem(row, col, QTableWidgetItem(str(cell)))
            header = self.table.horizontalHeader()
            for col in range(self.table.columnCount()):
                header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            self.stack.setCurrentWidget(self.table)
        else:
            self.stack.setCurrentWidget(self.text)

    def _export(self) -> None:
        if not self.spec.payload:
            return
        path, _ = QFileDialog.getSaveFileName(self, "导出到哪", str(self.root / self.spec.export), "JSON (*.json)")
        if not path:
            return
        catalog_layer.write_json(Path(path), self.spec.payload(self.root, self.values()))
        self.window().statusBar().showMessage(f"已导出：{path}")

    def _selected_path(self) -> str:
        row = self.table.currentRow()
        if row < 0:
            return ""
        for col in range(self.table.columnCount()):
            item = self.table.item(row, col)
            if item and ("/" in item.text() or item.text().endswith(".md")):
                return item.text()
        return ""

    def _instruction_about(self) -> None:
        about = self._selected_path()
        if not about:
            self.window().statusBar().showMessage("先在表里选一行")
            return
        path, _ = QFileDialog.getSaveFileName(self, f"以「{about}」为题写指令", str(self.root), "Markdown (*.md)")
        if path:
            self.show_result(report.new_instruction(Path(path), about))

    def _open_row(self, row: int) -> None:
        for col in range(self.table.columnCount()):
            item = self.table.item(row, col)
            if not item:
                continue
            candidate = Path(item.text())
            path = candidate if candidate.is_absolute() else self.root / item.text()
            if path.is_file():
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
                return
        self.window().statusBar().showMessage("这一行没有可打开的文件")


# ---- 台面页：任务 ----


class Desk(QWidget):
    """台面：选一件任务（工作流的一次执行），看步骤状态，走一步。"""

    def __init__(self, root: Path, data: Path):
        super().__init__()
        self.root = root
        self.data = data
        self.task: task_layer.Task | None = None
        self._build()
        self.reload()

    def _build(self) -> None:
        outer = QVBoxLayout(self)

        top = QHBoxLayout()
        top.addWidget(QLabel("任务"))
        self.picker = QComboBox()
        self.picker.setMinimumWidth(260)
        self.picker.currentIndexChanged.connect(self._picked)
        top.addWidget(self.picker)
        fresh = QPushButton("新建…")
        fresh.clicked.connect(self._new_task)
        top.addWidget(fresh)
        top.addStretch(1)
        self.next_label = QLabel()
        font = self.next_label.font()
        font.setBold(True)
        self.next_label.setFont(font)
        top.addWidget(self.next_label)
        outer.addLayout(top)

        self.steps_table = QTableWidget(0, 3)
        self.steps_table.setHorizontalHeaderLabels(["步骤", "谁执行 / 判据", "状态"])
        self.steps_table.verticalHeader().setVisible(False)
        self.steps_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.steps_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.steps_table.setAlternatingRowColors(True)
        header = self.steps_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.steps_table.itemDoubleClicked.connect(lambda _: self._open_workflow())
        outer.addWidget(self.steps_table, 1)

        row = QHBoxLayout()
        row.addWidget(QLabel("这一步做了什么"))
        self.note = QLineEdit()
        self.note.setPlaceholderText("一句话（可留空）")
        row.addWidget(self.note, 1)
        step_button = QPushButton("走下一步")
        step_button.setDefault(True)
        step_button.clicked.connect(self.run_selected)
        row.addWidget(step_button)
        workflow_button = QPushButton("看工作流")
        workflow_button.clicked.connect(self._open_workflow)
        row.addWidget(workflow_button)
        export_button = QPushButton("导出工作流…")
        export_button.clicked.connect(self._export_workflow)
        row.addWidget(export_button)
        history_button = QPushButton("写历史…")
        history_button.clicked.connect(self.write_history)
        row.addWidget(history_button)
        outer.addLayout(row)

        self.log_table = QTableWidget(0, 3)
        self.log_table.setHorizontalHeaderLabels(["时间", "步骤", "说明"])
        self.log_table.verticalHeader().setVisible(False)
        self.log_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.log_table.setAlternatingRowColors(True)
        log_header = self.log_table.horizontalHeader()
        for col in (0, 1):
            log_header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        log_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        outer.addWidget(self.log_table, 1)

    # ---- 读 ----

    def reload(self) -> None:
        keep = self.task.name if self.task else ""
        found = task_layer.listing(self.root, self.data)
        self.picker.blockSignals(True)
        self.picker.clear()
        self.picker.addItems([item.name for item in found])
        if keep:
            index = self.picker.findText(keep)
            if index >= 0:
                self.picker.setCurrentIndex(index)
        self.picker.blockSignals(False)
        self.task = found[self.picker.currentIndex()] if found else None
        self.refresh()

    def _picked(self, index: int) -> None:
        found = task_layer.listing(self.root, self.data)
        self.task = found[index] if 0 <= index < len(found) else None
        self.refresh()

    def selected_step(self) -> str:
        row = self.steps_table.currentRow()
        if row < 0:
            step = self.task.next_step() if self.task else None
            return step.name if step else ""
        item = self.steps_table.item(row, 0)
        return item.text() if item else ""

    # ---- 画 ----

    def refresh(self) -> None:
        if self.task is None:
            self.next_label.setText("还没有任务——点「新建…」起一件")
            self.steps_table.setRowCount(0)
            self.log_table.setRowCount(0)
            return
        done = self.task.done()
        steps = self.task.steps()
        self.steps_table.setRowCount(len(steps))
        for row, step in enumerate(steps):
            counts = f"{len(step.machine)} 机械" + (f" / {len(step.gates)} 闸门" if step.gates else "")
            self.steps_table.setItem(row, 0, QTableWidgetItem(step.name))
            self.steps_table.setItem(row, 1, QTableWidgetItem(f"{step.executor}　{counts}" if step.judges else step.executor))
            self.steps_table.setItem(row, 2, QTableWidgetItem("✓" if step.name in done else "—"))
        if steps and self.steps_table.currentRow() < 0:
            nxt = self.task.next_step()
            rows = [i for i, step in enumerate(steps) if nxt and step.name == nxt.name]
            self.steps_table.selectRow(rows[0] if rows else 0)
        self.next_label.setText(task_layer.state_line(self.task))
        events = self.task.events()
        self.log_table.setRowCount(len(events))
        for row, event in enumerate(reversed(events)):
            self.log_table.setItem(row, 0, QTableWidgetItem(event["at"]))
            self.log_table.setItem(row, 1, QTableWidgetItem(event["step"]))
            self.log_table.setItem(row, 2, QTableWidgetItem(event["detail"]))

    # ---- 动 ----

    def run_selected(self) -> report.Result:
        bar = self.window().statusBar()
        if self.task is None:
            bar.showMessage("先起一件任务")
            return report.Result(ok=False, lines=["先起一件任务"])
        row = self.steps_table.currentRow()
        nxt = self.task.next_step()
        current = self.selected_step()
        auto = bool(nxt and current == nxt.name)  # 选中的是下一步：按执行者分派（默认 AI）
        result = report.task_step(self.root, self.data, self.task.name, current, self.note.text().strip(), auto=auto)
        self.note.clear()
        self.reload()
        bar.showMessage(result.lines[0] if result.lines else "")
        return result

    def write_history(self) -> None:
        if self.task is None:
            return
        words, ok = QInputDialog.getMultiLineText(self, "历史", "这一次的来龙去脉（报告记事，历史叙事）")
        if ok and words.strip():
            report.task_history(self.root, self.data, self.task.name, words.strip())
            self.reload()

    def _export_workflow(self) -> None:
        if self.task is None:
            return
        flow = self.task.workflow()
        path, _ = QFileDialog.getSaveFileName(self, "存到哪", str(self.root / f"{flow.name}.md"), "Markdown (*.md)")
        if path:
            self.window().statusBar().showMessage(f"已导出：{report.workflow_export(self.data, flow.name, Path(path)).lines[0]}")

    def _open_workflow(self) -> None:
        if self.task is None:
            return
        path = self.task.workflow().file
        if path.is_file():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _new_task(self) -> None:
        name, ok = QInputDialog.getText(self, "起一件任务", "这件任务叫什么")
        if not ok or not name.strip():
            return
        flows = [flow.name for flow in flow_layer.listing(self.data)] if hasattr(flow_layer, "listing") else []
        flow, ok = QInputDialog.getItem(self, "起一件任务", "跑哪条工作流", flows, 0, False)
        if not ok or not flow:
            return
        about, ok = QInputDialog.getText(self, "起一件任务", "这一次要什么（可留空）")
        self.task = task_layer.create(self.root, self.data, name.strip(), flow, about.strip() if ok else "")
        self.reload()
        self.window().statusBar().showMessage(f"起了：{self.task.file}")


class Window(QMainWindow):
    def __init__(self, root: Path | None = None, data: Path | None = None, runs: Path | None = None):
        super().__init__()
        self.setWindowTitle("kg —— 量潮知识工作工具箱")
        self.resize(1040, 660)
        self.root = root or assets_layer.repo_root()
        self.data = data or flow_layer.lab_data()

        body = QWidget()
        self.setCentralWidget(body)
        outer = QVBoxLayout(body)

        top = QHBoxLayout()
        top.addWidget(QLabel("工作区"))
        self.root_edit = QLineEdit(str(self.root))
        self.root_edit.editingFinished.connect(self._change_root)
        top.addWidget(self.root_edit, 1)
        pick = QPushButton("选择…")
        pick.clicked.connect(self._pick_root)
        top.addWidget(pick)
        top.addWidget(QLabel("　数据"))
        self.data_label = QLabel(str(self.data))
        self.data_label.setStyleSheet("color: #666;")
        top.addWidget(self.data_label)
        outer.addLayout(top)

        self.desk = Desk(self.root, self.data)
        self.browser = Browser(self.root)
        tabs = QTabWidget()
        tabs.addTab(self.desk, "台面")
        tabs.addTab(self.browser, "浏览")
        outer.addWidget(tabs, 1)

        self.statusBar().showMessage("台面：选任务，点下一步；浏览：工作区层面的动作。")

    def _change_root(self) -> None:
        self.root = Path(self.root_edit.text()).expanduser()
        self.desk.root = self.root
        self.browser.root = self.root
        self.desk.reload()
        self.statusBar().showMessage(f"工作区：{self.root}")

    def _pick_root(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选工作区", str(self.root))
        if path:
            self.root_edit.setText(path)
            self._change_root()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="kg-gui", description="量潮知识工作工具箱的窗口版")
    parser.add_argument("--root", help="工作区根（默认从当前目录往上找）")
    parser.add_argument("--data", help="数据仓（默认本仓 data/——工作纪律：所有数据放这里）")
    parser.add_argument("--runs", help="任务放哪（默认 <数据仓>/cases）")
    args = parser.parse_args(argv)
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("kg")
    window = Window(
        Path(args.root).resolve() if args.root else None,
        Path(args.data).resolve() if args.data else None,
            )
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
