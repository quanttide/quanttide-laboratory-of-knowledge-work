# 过程

过程分两侧（`specification/process/`）：**工作流**是过程的编排定义，**任务**是过程的一次执行。一句话记住：**先串步骤，再执行**——工作流是可改、可复用的数据；**能用 AI 跑的步骤都交给 AI**，人只留在闸门。

## 一、写工作流（可改）

```bash
$ kg workflow --new 课程档案比对 --steps 定位,比对,结论 --note "比对两边的档案"
写下工作流：…/data/workflows/课程档案比对.md
```

落在 `data/workflows/<名字>.yaml`——**定义用 YAML，因为定义要「意义固定」**（字段、取值、判据种类都由 schema 定死，谁读都是同一件事）：

```yaml
name: 课程档案比对
description: 比对两边的档案
steps:
  - name: 定位
    description: 把两边的源找齐
    executor: agent             # agent | human；默认 agent
    criteria:
      - type: rule              # rule：规则引擎按字段判（看什么 + 要什么）
        note: 个人课程档案在
        path: data/profile/iGuo/course/index.md
      - type: rule
        note: 课程研发档案在
        path: /home/iguo/repos/quanttide/domains/quanttide-course/data/profile/README.md
  - name: 核对
    description: 逐项对照，落成一件产物
    executor: human             # 要人做必须显式写
    criteria:
      - type: rule
        note: 产物落成
        path: examples/default/data/artifacts/课程档案比对/比对.md
      - type: rule              # 文件含这段文字（file + contains 成对）
        file: examples/default/data/artifacts/课程档案比对/比对.md
        contains: "## 结论"
      - type: agent             # agent：智能体照 note 的判准审
        note: 两边口径是否对齐
      - type: human             # human：留给人拍板
        note: 创始人点头（回流与并法怎么定）
```

**谁判，按主体分三类**（`type`，取值英文标识）：

| type | 谁判 | 怎么判 |
|---|---|---|
| `rule` | 规则引擎（程序） | 按**字段**判，四种判法：`path:` 存在 / `absent:` 不存在 / `file:` + `contains:` 文件含这段文字 / `run:` 命令退出码为零；路径相对工作区根（绝对路径则按绝对路径，跨仓库核对用）。`note` 可省——省了由程序按字段拼一句 |
| `agent` | 智能体 | 程序把产物与 `note`（判准）交给 `pi -p`，要它逐条回答「通过 / 不通过 + 一句理由」 |
| `human` | 人类 | 不跑，原样进报告的「闸门项」等人拍板 |

**谁做**（`executor`）也是这两类：`agent`（默认）或 `human`。

三处都叫 `description`，各说一层：顶层描述整条工作流、步骤描述这一步做什么（执行者照它干）、判据描述这一条是什么（`agent` / `human` 那格就是判准与拍板事项）。

不合格的 YAML 一律挡回来，而且**不认识的字段直接报错**（不是忽略）：顶层只认 `name / description / steps`，步骤只认 `name / description / executor / criteria`，判据只认 `type / note / path / absent / file / contains / run`；`type` 只能三选一；`rule` 必须正好一种判法（`path`、`absent`、`file`+`contains`、`run` 四选一，且 `file`/`contains` 必须成对），`agent` / `human` 必须写 `note` 且不许带规则字段。不是「像不像」，是**合不合 schema**。

**可改**就在这儿：加一步、去一步、换顺序、改判据、换执行者与判据主体——动这份 YAML 就行，程序一行不用改；进 git 能 diff、能回退。

```bash
$ kg workflow 课程档案比对      # 看步骤、谁执行、几条 rule / agent / human
$ kg workflow --list           # 有哪些工作流
```

（报告与历史仍是 Markdown，流水是 JSONL：**定义要固定意义，记录要读得顺**——两回事。）

## 一之二、存下来，下次导入用

工作流本来就是一份 YAML，导出/导入只是搬文件加一道 schema 校验：

```bash
$ kg workflow 课程档案比对 --export ~/流程/课程档案比对.yaml
已导出：/home/iguo/流程/课程档案比对.yaml（步骤 3 个，原样带走）

$ kg workflow --import ~/流程/课程档案比对.yaml
已导入：workflows/课程档案比对.yaml（步骤 3 个）

$ kg workflow --import ~/流程/课程档案比对.yaml --as 课程档案比对·二   # 重名时换名字
```

导入时先按 schema 验一遍——不是工作流的文件挡回来；重名挡回来（用 `--as` 换名）。导出的是**原样**：步骤、执行者、判据一字不差，所以换一台机器、换一个 `--data`、换一个仓库，导进去就能跑。

带走的判据里若写着相对路径或绝对路径，导进别的项目要自己核对一遍——判据跟着工作流走，但它认的是**那边的**工作区。

## 二、起一件任务（复用）

```bash
$ kg task --new 课程档案比对 --workflow 课程档案比对 --about "比对 work 侧与课程研发档案"
起了：…/data/tasks/课程档案比对.md
```

**同一条工作流可以起任意多件任务**：任务＝它的一次执行，各自有步骤状态、流水与产物，互不串。工作流文件拷到别的 `--data`，整套做法就跟着过去。

（注意：现在任务按名字引用工作流，**中途改工作流等于改了正在跑的任务的规矩**。要锁住当时的样子，把工作流快照一份到 `artifacts/<任务>/`。）

## 三、走下一步

```bash
$ kg task AI冒烟 --next
问候：交给 AI（AI）跑
  AI 跑完了：我在 …/artifacts/AI冒烟/问候.md 写入了一行中文问候「你好」。
✓ 问候：机械：问候落在
  ✓ 机械：问候落在（contains:…/问候.md=你好）
```

`--next` 看下一步的执行者自己分派：

- **AI**（默认）→ 程序拼一段话（这一步做什么 + 判据 + 产物落在哪）交给 `pi -p --no-session` 跑，跑完**程序自己**核对机械判据；
- **人** → 程序不抢着做，提示「轮到你」，人做完用 `kg task <名字> --done <步骤> --note "一句话"` 记一笔；
- 判据**不许 AI 写、不许 AI 改**——改了就是自评自过。

没有判据的步骤也能记一笔（`--note`）；AI 跑不成（`pi` 不在、超时、产物没落成）这一步就不算过，流水里留 ✗，修好再来。

## 四、看

```bash
$ kg task 课程档案比对
  ✓ 定位   ✓ 比对   ✓ 结论
3 个步骤都走过了
产物：artifacts/课程档案比对/report.md、artifacts/课程档案比对/history.md

$ cat data/artifacts/课程档案比对/report.md     # 执行记录 + 闸门项，机器写
```

## 五、收尾

闸门项留给人拍板；这一趟的来龙去脉写进历史（叙事，人写）：

```bash
$ kg task 课程档案比对 --history "先找齐两边，再按口径 / 重叠 / 缺口 / 格式差四条比……"
```

## 数据：三家分放

```text
data/workflows/<工作流>.yaml   定义（YAML）：串联的步骤、执行者、判据
data/tasks/<任务>.yaml         实例（YAML）：跑哪条工作流、要什么
data/artifacts/<任务>/         产物：log.jsonl（流水）、report.md（事件）、history.md（叙事）
```

## 窗口里也一样

`./kg-gui` 台面：上方选一件任务、可以新建；中间是步骤表（步骤 / 怎么算完 / 状态）；填一句「这一步做了什么」，点「走这一步」；「看工作流」打开定义，「写历史…」记叙事。

## 规矩

- **能用 AI 跑的都用 AI**：步骤默认 `executor: agent`；人只留在 `type: human` 的判据上（拍板）；
- **智能体不能审自己那一步**——同一步的执行者与判据若是同一个智能体，等于自评自过（现在实现里是同一个 pi，流水里标了「AI 审查（同一模型）」，将来要换成另一个执行者）；

- **数据全落 `data/`**（workflows / tasks / artifacts 三家），不写实验室外面；
- **定义用 YAML、记录用 Markdown**：编排与判据是定义（schema 定死），报告与历史是记录（读得顺）；
- **工作流是数据不是代码**：改流程不改程序；程序不预置编排，也不替你攒模板——想留，自己把文件放过去；
- **别人的仓库不擅动**：跨仓库的动作（如 course 侧）要授权。

## 真事一例

2026-09-10 那次比对（就是上面这份）：

```bash
kg workflow --new 课程档案比对 --steps 定位,比对,结论
kg task --new 课程档案比对 --workflow 课程档案比对 --about "比对两侧课程档案"
kg task 课程档案比对 --done 定位 --note "work 侧 3 件、course 侧 3 门课"
kg task 课程档案比对 --done 比对 --note "口径 / 重叠 / 缺口 / 格式差"
kg task 课程档案比对 --done 结论 --note "四条处置建议，闸门待创始人"
```

比出来的四条：口径不同（一边记「为什么这么办」，一边记「课里有什么」）；production-internship 两边都有却互不引用；各有缺口（work 侧有「知识工作」课与验证目标，course 侧有 vibe-coding、data-engineering 与格式约定）；格式差最要命——course 侧机读、work 侧散文，对不了账。结论挂在闸门上等创始人。
