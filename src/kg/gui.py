"""图形入口：同一个程序开个窗，动作与命令行一模一样。

  kg gui        或   ./kg-gui

左栏选动作，右栏填参数，点「执行」，下边出结果；结果里的文件路径双击就用系统默认程序打开。
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
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
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
    QVBoxLayout,
    QWidget,
)

from . import assets as assets_layer
from . import catalog as catalog_layer
from . import records
from . import report


def material_paths(values: dict) -> list[str] | None:
    return values.get("材料路径", "").split() or None


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


OPTIONAL = ()


def optional(field: str) -> str:
    """可选字段的名字：去掉「（可留空）」就是它的本来面目。"""
    return field.replace("（可留空）", "")


def value(values: dict, field: str) -> str:
    return values.get(field, "").strip()


# 分五组：一件事是主轴，工作区看整体，查看看一件，契约与案卷各管一种记录
SPECS = (
    Spec("一件事", "起一件事", "写出材料 / 契约 / 产出 / 案卷四段骨架", ("目标文件",), lambda root, v: report.case_new(Path(value(v, "目标文件")))),
    Spec("一件事", "看一件事", "走到哪一步、有没有断链、下一步做什么", ("一件事文件",), lambda root, v: report.case(root, Path(value(v, "一件事文件")))),
    Spec("工作区", "目录", "列全部条目——契约 × 目录", (), lambda root, v: report.catalog(root), "目录.json", lambda root, v: report.catalog_payload(root)),
    Spec("工作区", "审计", "契约有而工作区无、工作区有而契约无", ("补建缺的资产",), lambda root, v: report.audit(root, make=bool(v.get("补建缺的资产"))), "审计.json", lambda root, v: report.audit_payload(root)),
    Spec("查看", "找文档", "按名找——认文件名与中文标题", ("名字", "看正文"), lambda root, v: report.find(root, value(v, "名字"), bool(v.get("看正文")))),
    Spec("查看", "看材料", "类型 / 内容 / 来源 / 时间；阶段由位置承担", ("材料路径",), lambda root, v: report.material(root, material_paths(v)), "材料.json", lambda root, v: report.material_payload(root, material_paths(v))),
    Spec("契约", "写契约骨架", "目标 / 输出形态 / 必须包含 / 检查项", ("目标文件", "以它为题（可留空）"), lambda root, v: report.new_contract(Path(value(v, "目标文件")), value(v, "以它为题（可留空）"))),
    Spec("契约", "核对契约", "段位齐不齐、机械核对过不过、闸门项有哪些", ("契约文件", "写入案卷（可留空）"), lambda root, v: report.audit_contract(root, Path(value(v, "契约文件")), Path(value(v, "写入案卷（可留空）")) if value(v, "写入案卷（可留空）") else None)),
    Spec("案卷", "写案卷骨架", "产出 / 审查 / 裁决 / 成果", ("目标文件", "以它为题（可留空）"), lambda root, v: report.new_dossier(Path(value(v, "目标文件")), value(v, "以它为题（可留空）"))),
    Spec("案卷", "核对案卷", "四段齐不齐", ("案卷文件",), lambda root, v: report.audit_dossier(Path(value(v, "案卷文件")))),
)

# 这些动作的结果是一张带路径的表，可以拿选中那行去立契约
CAN_ABOUT = ("目录", "找文档", "看材料")


class Window(QMainWindow):
    def __init__(self, root: Path | None = None):
        super().__init__()
        self.setWindowTitle("kg —— 量潮知识工作工具箱")
        self.resize(1000, 640)
        self.root = root or assets_layer.repo_root()
        self.spec = SPECS[0]
        self.widgets: dict[str, QWidget] = {}
        self.last_result: report.Result | None = None
        self.rows: dict[int, Spec | None] = {}  # 列表行号 → 动作（分组的表头为 None）
        self._build()
        self.select_action(SPECS[0].name)

    # ---- 界面 ----
    def _build(self) -> None:
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
        outer.addLayout(top)

        columns = QHBoxLayout()
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
        self.run_button.setDefault(True)
        self.run_button.clicked.connect(self.run_current)
        buttons.addWidget(self.run_button)
        self.export_button = QPushButton("导出…")
        self.export_button.clicked.connect(self._export)
        buttons.addWidget(self.export_button)
        self.about_button = QPushButton("以选中项立契约")
        self.about_button.clicked.connect(self._contract_about)
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
        outer.addLayout(columns, 1)

        self.statusBar().showMessage("选好动作，点执行。表里带路径的行，双击就用系统默认程序打开。")

    def fill_actions(self) -> None:
        """填空动作列表：分组表头不可选，其余一行一个动作。"""
        group = None
        for spec in SPECS:
            if spec.group != group:
                group = spec.group
                header = QListWidgetItem(group)
                header.setFlags(Qt.ItemFlag.ItemIsEnabled)  # 能看不能选
                font = header.font()
                font.setBold(True)
                header.setFont(font)
                header.setForeground(QColor("#666666"))
                self.list.addItem(header)
                self.rows[self.list.count() - 1] = None
            self.list.addItem(QListWidgetItem(spec.name))
            self.rows[self.list.count() - 1] = spec

    def select_action(self, name: str) -> None:
        """按名字选中动作——表头占了行号，别按序号选。"""
        for row, spec in self.rows.items():
            if spec and spec.name == name:
                self.list.setCurrentRow(row)
                return
        raise KeyError(name)

    def _select(self, row: int) -> None:
        spec = self.rows.get(row)
        if spec is None:  # 点到分组表头，什么也不做
            return
        self.spec = spec
        while self.form.count():
            item = self.form.takeAt(0)
            if widget := item.widget():
                widget.deleteLater()
        self.widgets = {}
        for field in self.spec.fields:
            if field == "看正文" or field == "补建缺的资产":
                widget = QCheckBox()
                widget.setChecked(False)
                self.widgets[field] = widget
            elif optional(field).endswith("文件") or optional(field) in ("以它为题", "写入案卷"):
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
        self.statusBar().showMessage(self.spec.hint)
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
            if optional(field) in ("目标文件", "写入案卷"):
                path, _ = QFileDialog.getSaveFileName(self, "写到哪", str(self.root), "Markdown (*.md)")
            else:
                path, _ = QFileDialog.getOpenFileName(self, "选文件", str(self.root), "Markdown (*.md)")
            if path:
                edit.setText(path)

        button.clicked.connect(choose)
        layout.addWidget(button)
        self.widgets[field] = edit
        return box

    # ---- 动作 ----
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
                for col, value in enumerate(values):
                    self.table.setItem(row, col, QTableWidgetItem(str(value)))
            self.table.resizeColumnsToContents()
            header = self.table.horizontalHeader()
            for col in range(self.table.columnCount()):
                header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            self.stack.setCurrentWidget(self.table)
        else:
            self.stack.setCurrentWidget(self.text)
        count = f"　{len(result.rows)} 行" if result.columns else ""
        self.statusBar().showMessage(f"{'通过' if result.ok else '有问题'}{count}")

    def _export(self) -> None:
        if not self.spec.payload:
            return
        path, _ = QFileDialog.getSaveFileName(self, "导出到哪", str(self.root / self.spec.export), "JSON (*.json)")
        if not path:
            return
        payload = self.spec.payload(self.root, self.values())
        catalog_layer.write_json(Path(path), payload)
        self.statusBar().showMessage(f"已导出：{path}")

    def _selected_path(self) -> str:
        """选中那一行里像路径的格子。"""
        row = self.table.currentRow()
        if row < 0:
            return ""
        for col in range(self.table.columnCount()):
            item = self.table.item(row, col)
            if item and ("/" in item.text() or item.text().endswith(".md")):
                return item.text()
        return ""

    def _contract_about(self) -> None:
        about = self._selected_path()
        if not about:
            self.statusBar().showMessage("先在表里选一行")
            return
        path, _ = QFileDialog.getSaveFileName(self, f"以「{about}」为题立契约", str(self.root), "Markdown (*.md)")
        if not path:
            return
        result = report.new_contract(Path(path), about)
        self.show_result(result)
        self.statusBar().showMessage("；".join(result.lines))

    def _open_row(self, row: int) -> None:
        for col in range(self.table.columnCount()):
            item = self.table.item(row, col)
            if not item:
                continue
            text = item.text()
            candidate = Path(text)
            path = candidate if candidate.is_absolute() else self.root / text
            if path.is_file():
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
                return
        self.statusBar().showMessage("这一行没有可打开的文件")

    def _change_root(self) -> None:
        self.root = Path(self.root_edit.text()).expanduser()
        self.statusBar().showMessage(f"工作区：{self.root}")

    def _pick_root(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选工作区", str(self.root))
        if path:
            self.root_edit.setText(path)
            self._change_root()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="kg-gui", description="量潮知识工作工具箱的窗口版")
    parser.add_argument("--root", help="工作区根（默认从当前目录往上找）")
    args = parser.parse_args(argv)
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("kg")
    window = Window(Path(args.root).resolve() if args.root else None)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
