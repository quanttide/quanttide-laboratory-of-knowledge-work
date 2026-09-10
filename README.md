# quanttide-laboratory-of-knowledge-work

量潮知识工作实验室——知识工作实验与原型。

## 一个程序：kg

中心是**一件事**——从材料走到成果，中途发生的事都记进它的流水；命令与窗口里的动作，只是它的下一步。

```bash
./kg --help              # 本目录下直接跑；九个动作
./kg-gui                 # 开窗口版（同一个程序）
uv pip install -e .      # 或装成命令：kg / kg-gui
```

界面要 PySide6 的窗口模块——有些发行版把它拆开了（Debian/Ubuntu 上是 `python3-pyside6.qtwidgets`）：
缺了的话，实验室内建个虚拟环境即可，不动系统：

```bash
uv venv .venv && uv pip install -e ".[gui]"
.venv/bin/kg-gui
```

| 动作 | 干什么 |
|------|--------|
| `kg case --list` / `--new <名字>` | 一件事：有哪些、起一件 |
| `kg case <名字>` | 看它的六格状态、下一步与流水 |
| `kg case <名字> --material/--contract/--review/--output/--decision/--finish` | 往前走一步，事实自动记进流水 |
| `kg find <名字>` | 按名找文档——认文件名与中文标题 |
| `kg catalog` | 看目录——列全部条目，可导 JSON |
| `kg audit [--make]` | 审计——契约有而工作区无、工作区有而契约无；`--make` 补建缺的格子 |
| `kg material [路径…]` | 看材料——类型、内容、来源、时间，阶段由位置承担 |
| `kg new-contract [--about 路径]` / `kg new-dossier` | 写契约骨架（`--about` 以某件东西为题）/ 写案卷骨架 |
| `kg audit-contract [--into 案卷]` / `kg audit-dossier` | 核对契约（`--into` 把审查者报告写进案卷）/ 核对案卷 |
| `kg gui` | 开窗口——台面（当前这件事）与浏览（工作区动作）两页 |

默认工作区从当前目录往上找，`--root` 可指向别的第二大脑。

## 目录

- `src/kg/` 程序：assets（契约层）、catalog（目录层）、checks（判据）、material（材料）、records（记录的段位与骨架）、case（一件事：状态机、动作、流水）、report（动作结果与动作之间的接口，命令行与界面共用）、cli（命令行入口）、gui（窗口入口）
- `samples/` 真实契约与案卷——判例，也是格式自证
- `tests/` 自带测试：`python3 tests/test_kg.py`，26 项；装了 PySide6 窗口模块则多 6 项界面冒烟，不依赖 pytest
- `samples/` 真实契约与案卷——判例，也是格式自证
- `docs/` 说明：模式与记录（index.md）、用户指南、开发计划

## 许可

[CC BY 4.0](LICENSE)
