"""The whole flow for one practice: load, compile, validate, propose repairs."""
from __future__ import annotations

from dataclasses import dataclass

from .compiler import Packet, compile_packet, load_packet
from .repairer import propose
from .schema import AgentConfig
from .semantic import semantic_check
from .validator import Issue, run_rules

SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


@dataclass
class Analysis:
    packet: Packet
    config: AgentConfig  # as compiled, before any repair
    issues: list[Issue]


def analyze(practice_id: str, semantic_mode: str = "auto") -> Analysis:
    packet = load_packet(practice_id)
    config = compile_packet(packet)
    issues = run_rules(config, packet) + semantic_check(config, packet, mode=semantic_mode)
    issues = propose(issues, config, packet)
    issues.sort(key=lambda i: (SEVERITY_ORDER[i.severity], i.repair.route == "auto", i.id))
    return Analysis(packet, config, issues)
