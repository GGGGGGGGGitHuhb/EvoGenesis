# EvoGenesis

EvoGenesis 是一个命令行 RNA 世界演化模拟器。当前 V0.1.1 聚焦运行体验：RNA 家族会围绕资源复制、突变、竞争、降解和灭绝；系统会记录中文事件、周期指标、运行总结，并支持快照恢复、暂停和重置测试数据。

本阶段只实现 RNA 世界，不包含前生命化学、原始细胞、原核生命、光合作用、氧气系统或宏观生态。

## 常用命令

```powershell
python -m evogenesis run --steps 1000
python -m evogenesis run --until-tick 5000
python -m evogenesis run --config configs/rna_world.default.json
python -m evogenesis run --resume saves/latest.json --steps 1000
python -m evogenesis pause
python -m evogenesis reset --yes
python -m evogenesis inspect saves/latest.json
```

说明：

- `--steps` 表示本次追加运行多少 tick。
- `--until-tick` 表示运行到目标 tick；如果当前 tick 已超过目标，会拒绝运行。
- `--ticks` 仍可使用，等同于旧版的 `--steps`。
- 不带步数的 `run` 会进入持续运行模式，按 `Ctrl+C` 会保存 `saves/latest.json` 后退出。
- `reset --yes` 不直接删除旧数据，而是把 `saves/` 和 `logs/` 归档到 `archives/reset-*`。

## 输出文件

```text
saves/latest.json       机器恢复快照
saves/tick-1000.json    周期快照
logs/history.jsonl      结构化事件日志
logs/events.txt         中文事件日志
logs/metrics.csv        周期指标
logs/latest-summary.txt 最近一次运行总结
```

## 配置

默认配置在 `configs/rna_world.default.json`。运行体验相关字段：

- `years_per_tick`：一个 tick 对应多少模拟年份。
- `time_unit_label`：控制台显示的时间单位。
- `ticks_per_second`：持续运行模式下的观察速度。
- `status_interval_ticks`：每隔多少 tick 打印一次状态。
- `snapshot_interval`：每隔多少 tick 保存一次周期快照。
- `metrics_interval`：每隔多少 tick 写一次指标。

## 测试

```powershell
python -m unittest discover -s tests
ruff check .
python -m compileall evogenesis tests
```
