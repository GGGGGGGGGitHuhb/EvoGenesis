"""Command line interface for EvoGenesis."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from evogenesis.config import ConfigError, default_config, load_config
from evogenesis.engine import SimulationEngine
from evogenesis.io.history import summarize_state
from evogenesis.io.snapshots import SnapshotError, load_snapshot, save_snapshot
from evogenesis.runtime import RuntimeLock, RuntimeLockError, archive_runtime_outputs


def main(argv: list[str] | None = None) -> int:
    """Parse CLI arguments and run the requested command."""

    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "run":
            return _run(args)
        if args.command == "inspect":
            return _inspect(args)
        if args.command == "pause":
            return _pause(args)
        if args.command == "reset":
            return _reset(args)
        parser.print_help()
        return 1
    except (ConfigError, SnapshotError, ValueError, RuntimeLockError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2


def build_parser() -> argparse.ArgumentParser:
    """Build the EvoGenesis CLI parser."""

    parser = ChineseArgumentParser(prog="evogenesis", description="EvoGenesis RNA 世界命令行模拟器")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="运行 RNA 世界模拟")
    run_parser.add_argument("--steps", type=_positive_int, help="本次追加运行多少 tick")
    run_parser.add_argument("--until-tick", type=_non_negative_int, help="运行到指定目标 tick")
    run_parser.add_argument("--ticks", type=_positive_int, help="兼容旧参数，等同于 --steps")
    run_parser.add_argument("--config", help="配置 JSON 文件路径")
    run_parser.add_argument("--resume", help="从快照恢复运行")

    pause_parser = subparsers.add_parser("pause", help="保存当前 latest 快照并打印恢复命令")
    pause_parser.add_argument("--snapshot", default="saves/latest.json", help="要确认暂停的快照路径")

    reset_parser = subparsers.add_parser("reset", help="归档 saves/logs，让下一次 run 从 tick 0 开始")
    reset_parser.add_argument("--config", help="读取配置以确定输出目录")
    reset_parser.add_argument("--yes", action="store_true", help="确认执行归档重置")

    inspect_parser = subparsers.add_parser("inspect", help="检查已保存的快照")
    inspect_parser.add_argument("snapshot", help="快照 JSON 文件路径")
    return parser


def _run(args: argparse.Namespace) -> int:
    requested_steps = _resolve_steps(args)
    if args.resume:
        state, config, random_state = load_snapshot(args.resume)
        if args.config:
            config = load_config(args.config)
        engine = SimulationEngine(config, state=state, random_state=random_state)
        print(f"从 tick {state.tick} 恢复 RNA 世界。")
    else:
        config = load_config(args.config)
        engine = SimulationEngine(config)
        print("RNA 世界开始演化：从 tick 0 创建新世界。")

    if args.until_tick is not None:
        if engine.state.tick >= args.until_tick:
            raise ValueError(
                f"当前 tick {engine.state.tick} 已达到或超过目标 tick {args.until_tick}。"
            )
        requested_steps = args.until_tick - engine.state.tick
        print(f"计划运行到 tick {args.until_tick}，本次追加 {requested_steps} tick。")
    elif requested_steps is not None:
        print(f"计划本次追加运行 {requested_steps} tick。")
    else:
        print("进入持续运行模式。按 Ctrl+C 暂停并保存。")

    with RuntimeLock.acquire(config.snapshot_dir):
        if requested_steps is None:
            return _run_continuously(engine)
        lines = engine.run(requested_steps, run_mode="until_tick" if args.until_tick else "steps")
    for line in lines:
        print(line)
    return 0


def _inspect(args: argparse.Namespace) -> int:
    state, _config, _random_state = load_snapshot(args.snapshot)
    print(summarize_state(state))
    return 0


def _pause(args: argparse.Namespace) -> int:
    state, config, random_state = load_snapshot(args.snapshot)
    rng = __import__("random").Random(state.seed)
    rng.setstate(random_state)
    save_snapshot(args.snapshot, state, config, rng)
    print("已暂停并确认保存当前 RNA 世界。")
    print(f"当前 tick：{state.tick}")
    print(f"保存路径：{Path(args.snapshot)}")
    print(f"下一次恢复命令：python -m evogenesis run --resume {args.snapshot} --steps 1000")
    return 0


def _reset(args: argparse.Namespace) -> int:
    if not args.yes:
        raise ValueError("reset 会归档 saves/logs；请添加 --yes 明确确认。")
    config = load_config(args.config) if args.config else default_config()
    archive_dir = archive_runtime_outputs(config.snapshot_dir, config.log_dir)
    print(f"已归档旧运行数据：{archive_dir}")
    print("下一次非恢复 run 将从 tick 0 创建新世界。")
    return 0


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("tick 数必须是整数") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("tick 数必须是正整数")
    return parsed


def _non_negative_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("目标 tick 必须是整数") from exc
    if parsed < 0:
        raise argparse.ArgumentTypeError("目标 tick 不能为负数")
    return parsed


def _resolve_steps(args: argparse.Namespace) -> int | None:
    provided = [value is not None for value in [args.steps, args.ticks, args.until_tick]]
    if sum(provided) > 1:
        raise ValueError("--steps、--ticks、--until-tick 只能选择一个。")
    return args.steps if args.steps is not None else args.ticks


def _run_continuously(engine: SimulationEngine) -> int:
    chunk = max(1, engine.config.status_interval_ticks)
    delay = chunk / engine.config.ticks_per_second
    try:
        while True:
            for line in engine.run(chunk, run_mode="continuous"):
                print(line)
            time.sleep(delay)
    except KeyboardInterrupt:
        engine.save_snapshot(Path(engine.config.snapshot_dir) / "latest.json")
        print("\n已捕获暂停信号，当前世界已保存。")
        print(f"当前 tick：{engine.state.tick}")
        print(f"恢复命令：python -m evogenesis run --resume {engine.config.snapshot_dir}/latest.json --steps 1000")
        return 0


class ChineseArgumentParser(argparse.ArgumentParser):
    """ArgumentParser with Chinese error prefix for user-facing failures."""

    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        self.exit(2, f"{self.prog}: 错误：{message}\n")
