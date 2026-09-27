from dataclasses import dataclass


@dataclass(frozen=True)
class StressInputs:
    funding: float
    price_discovery: float
    intermediation: float


def classify_stress(x: StressInputs) -> str:
    values = [x.funding, x.price_discovery, x.intermediation]
    impaired = sum(v >= 0.7 for v in values)
    pressured = sum(v >= 0.5 for v in values)
    if impaired >= 2:
        return "L3"
    if pressured >= 1:
        return "L2"
    return "L1"
