# 同炉许可抽检交接

`README.md` 说明现有全互配流程。受限计划也只抽一对，计划员按确切清册冻结版提供许可配对，炉台按该计划开炉，领班按原抽次签出许可总体平均平方色差的一次估计。

## 计划与抽次

新增 `sampling.create_restricted_plan(db, freeze_id, allowed_pairs)`。`allowed_pairs` 是非空序列，每项是两个片号组成的序列，左片在前，右片在后。片号须在点名冻结版的对应组内，配对不得重复。非法清单报 `ValueError`。两组各有 n 片，抽样时每片的边际受检概率恰为 `1/n`，全部许可对均有正概率，清单外概率为零。任何满足约束的精确有理分布均可。成功时冻结实际分布并返回计划号。合法清单若无法满足要求，返回 `None` 且无新增计划、分布或抽次。

原 `sampling.get_plan(db, plan_id)` 对受限计划也返回 `plan_id`、`freeze_id`、`batch_id`，并通过 `probabilities` 公开完整分布。它是从 `(left_piece, right_piece)` 到 `Fraction` 的映射，键集恰为全部许可对。读回同一计划时返回同一分布。

原 `sampling.draw_pair` 用受限计划实际抽取时，仍从调用方提供的 `randbelow(upper)` 端口取随机整数，实抽概率须与公开分布一致。原 `sampling.get_draw` 领取实抽记录。受限抽次在原字段之外公开 `probability`，值为该计划下实选片对的精确联合概率 `Fraction`。随机端口抛错时异常原样传播，返回非法位置时报 `ValueError`，两者均无新增抽次。计划分布在建计划时确定，录数和签报不再抽签。

## 录数、签报与领取

继续用 `measurements.record_reading` 录入实际同炉两片。零有效，另一炉的读数不能补位。`analysis.issue_report` 按原抽次签发。受限报告保留原 `SignedReport` 的编号和 `snapshot` 正文字段，正文的 `basis` 为 `v2/restricted-pair-mean-squared-color-difference`。正文增加两项，`pair_count` 是原计划许可对数 M，`probability` 是实选对的联合概率 p。`estimate` 为精确 `Fraction` 值 `(x−y)²/(M×p)`，左右读数及各自仪表引用照常保存。

签报失败无新增且可重试，沿用 `before_commit` 回调。同批另建计划或重开 SQLite 库后，`archive.read_report` 按原号领取签发时的正文及权重。错片及缺测报 `ValueError`，未知冻结版、计划、抽次或报告号报 `KeyError`。V1 的入口、左右取位次序、计算及原报告正文照旧。

## 样例与运行

`examples/restricted_pairing.json` 的两组数据可直接用于登记、冻结和建计划。`five_pairs` 的第三片只出现在 A3B3，故该对的概率必为 1/3。抽到该对并录入样例色值时，签报应为 12/5。以冻结概率加权五个可能抽次对应的签报值，结果应为 7/2。`three_pairs` 的 A2 只能配 B2，已占满 B2 的 1/2 机会，所以 A1B2 无法获正概率，该清单应返回 `None`。

沿用 `.pointwise-runtime.json` 的 `version` 1、`kind` 为 `cli` 和空 `setup`。`verify` 和 `demo` 都使用命令参数数组。核验入口运行完整原回归，并核对受限分布、实际选边、拒绝建计划及签报领取，失败以非零状态退出。演示入口使用可控随机端口展示五边样例的实际抽签、录数、签报和重开领取。样例未指定其余边的概率或端口取位次序。
