from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser

BTOS_TO_BLS_MAJOR_NAICS = {
    "23": "23",
    "31": "31-33",
    "42": "42",
    "44": "44,45",
    "51": "51",
    "52": "52",
    "53": "53",
    "54": "54",
    "56": "56",
    "61": "61",
    "62": "62",
    "71": "71",
    "72": "72",
    "81": "81",
}


@dataclass(frozen=True)
class MajorIndustryProductivityObservation:
    entity_id: str
    outcome_year: int
    labor_productivity_change: float
    source_release_date: str
    source_vintage_id: str
    bls_naics_code: str


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tables: list[list[list[str]]] = []
        self._table: list[list[str]] | None = None
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag == "table":
            self._table = []
        elif tag == "tr" and self._table is not None:
            self._row = []
        elif tag in {"td", "th"} and self._row is not None:
            self._cell = []

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self._cell is not None and self._row is not None:
            text = " ".join("".join(self._cell).split())
            self._row.append(text)
            self._cell = None
        elif tag == "tr" and self._row is not None and self._table is not None:
            if self._row:
                self._table.append(self._row)
            self._row = None
        elif tag == "table" and self._table is not None:
            if self._table:
                self.tables.append(self._table)
            self._table = None


def parse_major_industry_labor_productivity(
    raw: bytes,
    *,
    outcome_year: int,
    source_release_date: str,
    source_vintage_id: str,
) -> tuple[MajorIndustryProductivityObservation, ...]:
    parser = _TableParser()
    parser.feed(raw.decode("utf-8", errors="replace"))

    candidate = None
    for table in parser.tables:
        blob = " ".join(cell for row in table[:5] for cell in row).lower()
        if "labor productivity" in blob and "naics" in blob:
            candidate = table
            break
    if candidate is None:
        raise ValueError(
            f"BLS major-industry labor-productivity table not found for {outcome_year}"
        )

    target_to_entity = {value: key for key, value in BTOS_TO_BLS_MAJOR_NAICS.items()}
    observations = []
    seen = set()
    for row in candidate:
        if len(row) < 3:
            continue
        naics = row[1].replace("–", "-").strip()
        entity = target_to_entity.get(naics)
        if entity is None:
            continue
        if entity in seen:
            raise ValueError(f"duplicate BLS major-industry row for APCR entity {entity}")
        try:
            value = float(row[2].replace(",", ""))
        except ValueError:
            continue
        observations.append(
            MajorIndustryProductivityObservation(
                entity_id=entity,
                outcome_year=outcome_year,
                labor_productivity_change=value,
                source_release_date=source_release_date,
                source_vintage_id=source_vintage_id,
                bls_naics_code=naics,
            )
        )
        seen.add(entity)

    return tuple(sorted(observations, key=lambda item: item.entity_id))
