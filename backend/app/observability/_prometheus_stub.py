from __future__ import annotations

from typing import Dict, List, Tuple

CONTENT_TYPE_LATEST = "text/plain; version=0.0.4"


class _MetricBase:
    def __init__(self, name: str, documentation: str, labelnames: List[str]):
        self.name = name
        self.documentation = documentation
        self.labelnames = labelnames
        self.samples: Dict[Tuple[str, ...], float] = {}
        _REGISTRY.append(self)

    def _label_key(self, *labelvalues: str, **labelkw: str) -> Tuple[str, ...]:
        if labelkw:
            labelvalues = tuple(labelkw[name] for name in self.labelnames)
        if len(labelvalues) != len(self.labelnames):
            raise ValueError("Incorrect label cardinality")
        return tuple(labelvalues)


class Counter(_MetricBase):
    def labels(self, *labelvalues: str, **labelkw: str):
        key = self._label_key(*labelvalues, **labelkw)
        return _CounterProxy(self, key)


class _CounterProxy:
    def __init__(self, metric: Counter, key: Tuple[str, ...]):
        self.metric = metric
        self.key = key

    def inc(self, amount: float = 1.0) -> None:
        self.metric.samples[self.key] = self.metric.samples.get(self.key, 0.0) + amount


class Histogram(_MetricBase):
    def labels(self, *labelvalues: str, **labelkw: str):
        key = self._label_key(*labelvalues, **labelkw)
        return _HistogramProxy(self, key)


class _HistogramProxy:
    def __init__(self, metric: Histogram, key: Tuple[str, ...]):
        self.metric = metric
        self.key = key

    def observe(self, value: float) -> None:
        self.metric.samples[self.key] = self.metric.samples.get(self.key, 0.0) + value


_REGISTRY: List[_MetricBase] = []


def generate_latest() -> bytes:
    lines: List[str] = []
    for metric in _REGISTRY:
        lines.append(f"# HELP {metric.name} {metric.documentation}")
        lines.append(f"# TYPE {metric.name} gauge")
        for labels, value in metric.samples.items():
            label_parts = []
            for name, val in zip(metric.labelnames, labels):
                label_parts.append(f'{name}="{val}"')
            label_str = ",".join(label_parts)
            lines.append(f"{metric.name}{{{label_str}}} {value}")
    return "\n".join(lines).encode()
