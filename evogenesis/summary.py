"""Rule-based Chinese run summaries for V0.1.1."""

from __future__ import annotations

from dataclasses import dataclass

from evogenesis.config import SimulationConfig
from evogenesis.state import EventRecord, WorldState, compute_metrics


@dataclass(frozen=True)
class RunSummary:
    """Human-readable summary generated from state, metrics and events."""

    text: str
    key_events: list[str]
    stage_judgement: str
    limiting_factors: list[str]


def generate_run_summary(
    start_tick: int,
    end_state: WorldState,
    events: list[EventRecord],
    config: SimulationConfig,
) -> RunSummary:
    """Generate a concise Chinese summary without modifying simulation state."""

    metrics = compute_metrics(end_state)
    key_events = [f"{event.display_name}({event.id})@tick {event.tick}" for event in events[-8:]]
    if metrics.total_population <= 0:
        stage = "复制体系已灭绝"
    elif metrics.resource_pool <= config.max_resource_pool * 0.08:
        stage = "维持复制，但受资源崩溃限制"
    elif metrics.family_count >= 10 and metrics.diversity >= 0.5:
        stage = "稳定演化中的多家族 RNA 世界"
    else:
        stage = "维持复制的早期 RNA 世界"

    limiting_factors: list[str] = []
    if metrics.resource_pool <= config.max_resource_pool * 0.08:
        limiting_factors.append("资源池接近枯竭")
    if metrics.diversity < 0.2 and metrics.family_count > 1:
        limiting_factors.append("多样性偏低，优势谱系压制明显")
    if metrics.extinction_count > metrics.family_count:
        limiting_factors.append("累计灭绝次数较高")
    if not limiting_factors:
        limiting_factors.append("当前未出现单一压倒性限制因素")

    dominant = max(end_state.families, key=lambda family: family.population, default=None)
    dominant_text = "暂无优势家族"
    if dominant is not None:
        dominant_text = (
            f"优势家族为 {dominant.id}，谱系 {dominant.lineage_id}，"
            f"种群 {dominant.population}"
        )

    text = "\n".join(
        [
            f"本次模拟从 tick {start_tick} 推进到 tick {end_state.tick}。",
            (
                f"RNA 世界当前总种群 {metrics.total_population}，家族数 "
                f"{metrics.family_count}，多样性 {metrics.diversity}。"
            ),
            f"{dominant_text}。",
            f"阶段判断：{stage}。",
            "距离下一阶段还缺少前生命化学与原始细胞结构，本阶段仅评估 RNA 复制体系。",
            f"主要限制：{'；'.join(limiting_factors)}。",
        ]
    )
    return RunSummary(
        text=text,
        key_events=key_events,
        stage_judgement=stage,
        limiting_factors=limiting_factors,
    )
