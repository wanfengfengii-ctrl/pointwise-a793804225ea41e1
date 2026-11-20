# 青汀涂层试验室同炉色差抽检

青汀涂层试验室从制样台接收同批候选片清册。日班编组员冻结左右片组，计划员指定清册版，炉台实验员抽片并录数。质控领班签发整批平均平方色差的一次估计，次班凭报告号复核原抽次、实测和仪表出处。

## 一班工作的交接

1. 制样台交付批号和左右候选片。编组员用 `register_batch` 在现场库登记这份清册。
2. 编组员用 `freeze_cohorts` 冻结两个等量、非空的有序片组。每片都须属于该批及所填侧，同版片号互异。修改现场编组时另冻一版。
3. 计划员用 `create_plan` 点名一个清册版。即使随后有新版，原计划及显式点名旧版的计划都沿用旧版。
4. 炉台用 `draw_pair` 开炉。随机端口先取左侧位置，再取右侧位置。两个位置有效后才保存抽次及同炉的两片。
5. 炉台用 `record_reading` 登记先到的一侧，次序由仪表到数决定。`load_reading_pair` 可查看左右槽位。
6. 另一侧到数后补齐同一抽次。零是有效色值。同片在另一抽次的实测属于另一炉。
7. 领班用 `issue_report` 签发。同一次提交固定报告号、V1 口径、估计及原实测出处。提交前失败后可用原抽次重试。
8. 次班重开同一库，用 `read_report` 按原号领取。后来换版或另行签发时，原号仍返回当时的定稿。

## 公开 Python 接口

使用 Python 3.11 标准库。由 `archive.open_database(path)` 打开 SQLite 库。调用方负责关闭连接，可用 `contextlib.closing`。业务写入入口管理各自的提交，应在连接没有外部事务时调用。重复开启启用外键并保留已提交的现场数据，样例数据由测试和演示显式登记。

| 包 | 接口 | 输入和结果 |
| --- | --- | --- |
| `cohorts` | `register_batch(db, batch_id, left, right)` | 用非空文本批号和片号序列登记候选清册，返回 `BatchRoster`。重复批号或无效清册报 `ValueError`。 |
| `cohorts` | `freeze_cohorts(db, batch_id, left, right)` | 两组按传入顺序冻结，返回版号。未知批号报 `KeyError`。非法片组报 `ValueError`，无新增版。 |
| `cohorts` | `get_cohort_freeze(db, freeze_id)` | 按确切版号取回 `CohortFreeze`。 |
| `sampling` | `create_plan(db, freeze_id)`、`get_plan(db, plan_id)` | 建全互配计划并返回计划号，或按号取 `FullPairPlan`。 |
| `sampling` | `create_restricted_plan(db, freeze_id, allowed_pairs)` | 按非空不重复的左右许可对清单建受限计划，冻结精确有理分布并返回计划号；清单无法满足每片 `1/n` 边际且每对正概率时返回 `None`，无新增计划或抽次。非法清单报 `ValueError`，未知冻结版报 `KeyError`。 |
| `sampling` | `draw_pair(db, plan_id, random_source)`、`get_draw(db, draw_id)` | 开炉或领取已存抽次。`Draw` 有抽次号、计划号及两片片号；受限计划返回 `RestrictedDraw`，另含实选对的精确联合概率 `probability`。 |
| `measurements` | `record_reading(db, draw_id, piece_id, value, instrument_ref)` | 录入实际片读数，返回 `Reading`。仪表引用须为非空文本。错片、重复录入和非法读数报 `ValueError`。 |
| `measurements` | `load_reading_pair(db, draw_id)` | 返回左右有序槽位，缺侧为 `None`。 |
| `analysis` | `issue_report(db, draw_id, *, before_commit=None)` | 齐备时返回 `SignedReport`，缺侧报 `ValueError`。可选的提交前回调抛错时回滚。 |
| `archive` | `read_report(db, report_id)` | 按编号取 `SignedReport`，含报告号和 `snapshot` 正文。 |

固定版号、计划号、抽次号和报告号是分别生成的正整数。查询或使用未知固定号报 `KeyError`。随机端口实现 `randbelow(upper)`，每次返回 `[0, upper)` 中的整数。线上可传入标准库模块 `secrets`，测试可传入依次返回已知位置的端口。端口抛错时异常原样传播，越界或非整数报 `ValueError`，两类失败均无新增抽次。记录实际已存抽次用于事后复核，无需再抽签。

色值接受整数、`Fraction` 以及 `Fraction` 支持的有理数文本，如 `"-1/3"` 或 `"0.5"`。浮点对象、布尔值、空值、零分母和非法文本报 `ValueError`。实测值及估计按十进制分子和正分母文本存储，领取恢复为 `Fraction`。

## 计算与可复核样例

两侧各有 n 片时，独立等概率抽片使 n² 种左右组合各以 1/n² 的概率发生。签报用实际一对的 `(左值 − 右值)²` 估计这 n² 个平方差的算术平均，计量单位为输入色值单位的平方。对于有序左组 L1、L2 和右组 R1、R2，端口依次返回 1 和 0 时抽中 L2、R1。先录右读 1/2，再录左读 0，精确签报 1/4。

以 L1=1/3、L2=0、R1=1/2、R2=0 手算，位置对 (0,0)、(0,1)、(1,0)、(1,1) 的平方差分别为 1/36、1/9、1/4、0，均值为 7/72。回归逐对经实际抽次、录数、签发和独立连接领取核对这些值。

## 同炉许可受限计划（V2）

`create_restricted_plan(db, freeze_id, allowed_pairs)` 只允许抽许可对清单内的组合。两组各 n 片时，冻结的精确有理分布保证每片边际受检概率恰为 `1/n`、每个许可对概率严格为正、清单外概率为零。当清单中存在不属于任何完美配对的边（或整体无完美配对）时约束无解，返回 `None` 且不写入计划、分布或抽次；非法清单（空、非序列、跨组片号、重复对等）报 `ValueError`。

`get_plan` 对受限计划返回 `RestrictedPairPlan`，其 `probabilities` 是 `(left_piece, right_piece)` 到 `Fraction` 的完整映射，键集恰为许可对，建计划时一次冻结。受限抽次经同一 `randbelow(upper)` 端口取一个整数，实抽频率与公开分布一致，返回的 `RestrictedDraw` 额外公开该对的联合概率 `p`；端口异常原样传播、非法位置报 `ValueError`，均无新增抽次。

受限报告正文 `basis` 为 `v2/restricted-pair-mean-squared-color-difference`，新增 `pair_count`（许可对数 M）与 `probability`（实选对联合概率 p），`estimate` 为精确 `Fraction`：`(x−y)²/(M×p)`。同批另建计划或重开库后，`read_report` 按原号领取同一份定稿；V1 计划的入口、取位、计算与报告正文保持不变。`examples/restricted_pairing.json` 给出五对可行样例（A3B3 概率必为 1/3，对应签报 12/5，五个可能签报的概率加权均值为 7/2）和三对无解样例（返回 `None`）。

## 运行

平台物化项目后运行完整正常回归。

```text
python3 -B check_project.py
```

直接运行完整 unittest 套件。

```text
python3 -B -m unittest discover -s tests -t . -v
```

演示在临时库中固定计划、抽片、异步录数、签报、换版以及重开领取。输出含实际计算、独立预期和重开结果，演示失败会返回非零退出码。

```text
python3 -B -m tests.fixtures
```
