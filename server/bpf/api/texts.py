"""Fixed user-facing texts of the API: attribution, disclaimer and the "cheapest" scope note.

BUILD-BRIEF §8 (binding): no GVH/Árfigyelő branding beyond the attribution line "Forrás: GVH Árfigyelő
(arfigyelo.gvh.hu), <date>"; the exact Hungarian disclaimer below; KSH data is attributed "Forrás: KSH" with a
link (CC BY 4.0); "cheapest" statements are scoped to the selected stores and dated.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date

from bpf.api.schemas import AttributionOut, AttributionSet

DISCLAIMER_HU = "Nem hivatalos alkalmazás, nem áll kapcsolatban a Gazdasági Versenyhivatallal."
DISCLAIMER_EN = (
    "Unofficial app, not affiliated with the Hungarian Competition Authority (Gazdasági Versenyhivatal)."
)

GVH_URL = "https://arfigyelo.gvh.hu"
KSH_URL = "https://www.ksh.hu/stadat_files/ara/hu/ara0044.html"

# Composition tables named in BUILD-BRIEF §4.4 / docs/DATA.md: (display name, url, licence).
NUTRITION_SOURCES: dict[str, tuple[str, str, str]] = {
    "ciqual": ("ANSES-CIQUAL", "https://ciqual.anses.fr", "Licence Ouverte / Etalab 2.0"),
    "frida": ("Frida (DTU Fødevareinstituttet)", "https://frida.fooddata.dk", "CC BY 4.0"),
    "usda": ("USDA FoodData Central", "https://fdc.nal.usda.gov", "CC0 1.0"),
}


def gvh_attribution(data_date: date | None) -> AttributionOut:
    """The line "Forrás: GVH Árfigyelő (arfigyelo.gvh.hu), <data date>" (no date while there is no data)."""
    suffix = f", {data_date.isoformat()}" if data_date is not None else ""
    return AttributionOut(
        text_hu=f"Forrás: GVH Árfigyelő (arfigyelo.gvh.hu){suffix}",
        text_en=f"Source: GVH Árfigyelő (arfigyelo.gvh.hu){suffix}",
        url=GVH_URL,
        license=None,
    )


def ksh_attribution() -> AttributionOut:
    return AttributionOut(
        text_hu="Forrás: KSH",
        text_en="Source: KSH (Hungarian Central Statistical Office)",
        url=KSH_URL,
        license="CC BY 4.0",
    )


def nutrition_attribution(sources: Iterable[str]) -> AttributionOut | None:
    """Attribution for the composition tables actually present (None while there is no nutrition data)."""
    known = [NUTRITION_SOURCES[s] for s in sorted(set(sources)) if s in NUTRITION_SOURCES]
    if not known:
        return None
    names = ", ".join(name for name, _, _ in known)
    return AttributionOut(
        text_hu=f"Tápérték-adatok forrása: {names}",
        text_en=f"Nutrition data: {names}",
        url=known[0][1],
        license="; ".join(licence for _, _, licence in known),
    )


def attribution_set(data_date: date | None, nutrition_sources: Iterable[str]) -> AttributionSet:
    return AttributionSet(
        gvh=gvh_attribution(data_date),
        ksh=ksh_attribution(),
        nutrition=nutrition_attribution(nutrition_sources),
    )


def scope_note_hu(data_date: date) -> str:
    return f"a kiválasztott boltok közül, a {data_date.isoformat()}-i GVH-adatok alapján"


def scope_note_en(data_date: date) -> str:
    return f"among the selected stores, based on GVH data of {data_date.isoformat()}"
