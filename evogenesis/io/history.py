"""History log and metrics CSV writers."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from evogenesis.state import EventRecord, Metrics, WorldState, compute_metrics

METRIC_FIELDS = [
    "tick",
    "total_population",
    "family_count",
    "diversity",
    "average_length",
    "average_stability",
    "best_fitness",
    "resource_pool",
    "extinction_count",
    "new_family_count",
]


class HistoryWriter:
    """Append event logs and metric rows without owning simulation state."""

    def __init__(self, log_dir: str | Path):
        self.log_dir = Path(log_dir)
        self.history_path = self.log_dir / "history.jsonl"
        self.events_text_path = self.log_dir / "events.txt"
        self.metrics_path = self.log_dir / "metrics.csv"
        self.summary_path = self.log_dir / "latest-summary.txt"
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def write_events(self, events: list[EventRecord]) -> None:
        """Append event records as readable JSON lines."""

        if not events:
            return
        with self.history_path.open("a", encoding="utf-8") as handle:
            text_handle = self.events_text_path.open("a", encoding="utf-8")
            try:
                for event in events:
                    handle.write(json.dumps(event.to_dict(), ensure_ascii=False, sort_keys=True))
                    handle.write("\n")
                    text_handle.write(format_event_for_console(event))
                    text_handle.write("\n")
            finally:
                text_handle.close()

    def write_metrics(self, tick: int, metrics: Metrics) -> None:
        """Append one metrics row, creating the CSV header when necessary."""

        exists = self.metrics_path.exists()
        with self.metrics_path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=METRIC_FIELDS)
            if not exists:
                writer.writeheader()
            row = metrics.to_dict()
            row["tick"] = tick
            writer.writerow(row)

    def write_summary(self, summary_text: str) -> None:
        """Write the latest Chinese run summary for user reading."""

        self.summary_path.write_text(summary_text, encoding="utf-8")


def summarize_state(state: WorldState) -> str:
    """Return a concise Chinese world summary."""

    metrics = compute_metrics(state)
    best = max(
        state.families,
        key=lambda family: (
            family.population,
            family.replication_rate * family.catalytic_power * family.replication_accuracy,
        ),
        default=None,
    )
    lines = [
        f"当前 tick：{state.tick}",
        f"随机种子：{state.seed}",
        f"总种群：{metrics.total_population}",
        f"家族数：{metrics.family_count}",
        f"多样性：{metrics.diversity}",
        f"资源池：{metrics.resource_pool}",
        f"累计灭绝：{metrics.extinction_count}",
        f"新家族数：{metrics.new_family_count}",
        f"模拟时间：{state.elapsed_simulation_years:g} 年",
    ]
    if best is not None:
        lines.extend(
            [
                "优势家族：",
                f"  ID：{best.id}",
                f"  谱系：{best.lineage_id}",
                f"  种群：{best.population}",
                f"  序列：{best.sequence}",
                f"  稳定性：{best.stability}",
                f"  催化能力：{best.catalytic_power}",
            ]
        )
    if state.recent_events:
        lines.append("最近事件：")
        for event in state.recent_events[-5:]:
            lines.append(f"  [tick {event.tick}] {event.display_name} {event.id}：{event.message}")
    return "\n".join(lines)


def format_event_for_console(event: EventRecord) -> str:
    """Format one event with Chinese name and compact evidence."""

    evidence = "，".join(f"{key}={value}" for key, value in event.evidence.items())
    return (
        f"[tick {event.tick}] {event.display_name} {event.id}\n"
        f"原因：{event.message}\n"
        f"证据：{evidence}\n"
        f"影响对象：家族 {event.affected_families or ['无']}；谱系 {event.affected_lineages or ['无']}"
    )
