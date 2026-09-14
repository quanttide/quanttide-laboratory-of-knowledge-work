# qtcloud-work-lab-v2

量潮知识工作实验室 v2——按规格重写的工作流与工单。

中心是**工单**：一条工作流的一次执行实例；命令里的每个动作，就是走其中一站。模型与行为差见[设计](docs/index.md)，里程碑与决策见[开发计划](docs/dev-guide/index.md)，动作对表见[用法](docs/user-guide/index.md)。

## 一个程序：qtcloud-work

```bash
./qtcloud-work workflow create 课程档案比对 --steps 定位,比对,结论 --description "比对两边的档案"
./qtcloud-work order create 课程档案比对 --workflow 课程档案比对 --description "比对两侧课程档案"
./qtcloud-work order next 课程档案比对       # 走下一步：智能体执行，程序核 rule 判据
./qtcloud-work order done 课程档案比对 结论   # 人记一笔（闸门放行也走这里）
./qtcloud-work order show 课程档案比对        # 全貌：封面加全量流水
uv pip install -e .                         # 或装成命令：qtcloud-work
```

| 动作 | 干什么 |
|------|--------|
| `qtcloud-work workflow create <名字> --steps 甲,乙,丙` | 写一条工作流：各写一份判据骨架（凭证由工作区按名派生，不落文件） |
| `qtcloud-work workflow show <名字>` / `workflow list` | 看步骤与判据 / 有哪些工作流 |
| `qtcloud-work workflow check <名字>` | 定义核对：判据路径在不在区内、小节有没有判据覆盖 |
| `qtcloud-work workflow export <名字> <文件>` / `workflow import <文件> [--as 名字]` | 原样存走 / 导进来用（按 schema 验、重名挡） |
| `qtcloud-work order create <名字> --workflow <工作流>` | 开工单：封面落笔即封，凭证与时刻账本方查填 |
| `qtcloud-work order show <名字>` / `order list [--json]` | 读全貌（封面加流水）/ 列工单，可按工作流筛 |
| `qtcloud-work order next <名字>` | 走下一步：智能体执行，程序核 `rule` 判据，记一条工作记录 |
| `qtcloud-work order done <名字> <步骤>` | 人记一笔；带 `human` 判据的闸门站，放行也走这里 |
| `qtcloud-work order journal <名字> <一段话>` | 日志：叙事落产物，不动流水 |
| `qtcloud-work order delete <名字>` | 删一张白纸——流水非空即拒，账本不销户 |
| `qtcloud-work catalog [--json]` / `audit [--make]` | 看目录 / 审计工作区（资产表有而工作区无、工作区有而资产表无，`--make` 补建） |
| `qtcloud-work find <名字> [--show]` | 按名找文档——认文件名与中文标题 |
| `qtcloud-work material [路径…] [--json]` | 看材料——类型、内容、来源、时间，阶段由位置承担 |

位置不进模型，由启动参数装载：

- `--root` 工作区根：判据基准与工作区级扫描面，也是人放内容的地方；缺省从当前目录往上找 `data/journal`。
- `--data` 账本：工作区身份、工单、产物与事件；缺省 CLI 自己的数据目录 `$XDG_DATA_HOME/qtcloud-work`（缺省 `~/.local/share/qtcloud-work`），指到仓库就等于把它入版控。
- `--workflows` 定义目录：缺省 `<账本>/workflows/`；固定资产常另指一处（如 `data/profile/iGuo/workflows/`）。

## 目录

- `src/qtcloud_work/` 程序：workspace（装载：根与账本、工作区身份、XDG 数据目录）、workflow（工作流与工作步骤）、workorder（工单与工作记录）、checks（判据）、execute（走一步：智能体执行与人记一笔）、events（领域事件）、artifacts（产物）、assets / catalog / material（工作区级：资产表、目录、材料）、actions（动作层）、cli（命令行入口）
- `tests/` 自带测试：`python3 tests/test_qtcloud_work.py`，不依赖 pytest（账本一律指临时目录，不碰真 XDG）
- `docs/` 说明：设计、开发计划、用法

## 许可

[CC BY 4.0](LICENSE)
