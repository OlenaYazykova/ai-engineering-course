"""The record extracted from one text: the single source of truth for fields, types and enums.

One schema serves both sources:
  * Ukrhydrometcenter bulletins (uk): soil moisture in mm, crop phases, hazards
  * JRC MARS bulletins and news (en): crop conditions, yield outlook vs the 5-year average
A source fills only its part; everything the text does not state is null / [] / "not_stated".
An empty value is a correct answer and is checked: a filled value where the gold set is empty
counts as a hallucination.

Constraints that the JSON schema cannot express (ranges, min <= max, numbers and dates that must
be written in the text) live in validators, so the schema stays compatible with strict structured
output. List items not supported by the text are removed after validation (checks.clean_lists).
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, model_validator

Oblast = Literal[
    "vinnytsia", "volyn", "dnipropetrovsk", "donetsk", "zhytomyr", "zakarpattia",
    "zaporizhzhia", "ivano_frankivsk", "kyiv", "kirovohrad", "luhansk", "lviv",
    "mykolaiv", "odesa", "poltava", "rivne", "sumy", "ternopil", "kharkiv", "kherson",
    "khmelnytskyi", "cherkasy", "chernivtsi", "chernihiv", "crimea",
]

Crop = Literal[
    "winter_wheat", "winter_barley", "winter_rapeseed", "spring_barley",
    "maize", "sunflower", "soybean", "sugar_beet",
]

Hazard = Literal[
    "drought", "frost", "heat", "heavy_rain", "waterlogging", "hail", "hostilities",
]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SoilMoisture(Strict):
    status: Literal["deficit", "adequate", "excess", "mixed", "not_stated"] = Field(
        description="Prevailing soil moisture over the territory described in the text."
    )
    layer: Literal["0-20cm", "0-100cm", "both", "not_stated"] = Field(
        description="Soil layer the mm values refer to: arable layer 0-20 cm or metre layer 0-100 cm."
    )
    min_mm: int | None = Field(description="Smallest productive moisture value in mm stated in the text.")
    max_mm: int | None = Field(description="Largest productive moisture value in mm stated in the text.")
    deficit_oblasts: list[Oblast] = Field(
        description="Oblasts explicitly named with insufficient or unsatisfactory moisture or soil drought."
    )


class CropState(Strict):
    crop: Crop
    bbch_stage: int | None = Field(
        description="Principal BBCH growth stage 0-9 of the crop as described in the text."
    )
    condition: Literal["good", "satisfactory", "poor", "not_stated"]


class YieldOutlook(Strict):
    crop: Crop
    vs_5yr_average: Literal["above", "near", "below", "not_stated"]
    production_mt: float | None = Field(description="National production forecast in million tonnes.")


class AgroReport(Strict):
    year: int | None = Field(description="Year of the reporting period, only if written in the text.")
    month: int | None = Field(description="Month 1-12 of the reporting period.")
    decade: int | None = Field(description="Ten-day period 1-3 of the month (Hydromet bulletins only).")
    soil_moisture: SoilMoisture
    crops: list[CropState] = Field(description="Main crops whose growth stage or condition is described.")
    hazards: list[Hazard] = Field(description="Adverse conditions explicitly reported in the text.")
    yield_outlook: list[YieldOutlook] = Field(description="Yield or production outlook per crop.")

    @model_validator(mode="after")
    def check_facts(self, info: ValidationInfo) -> "AgroReport":
        problems = []
        if self.year is not None and not 2000 <= self.year <= 2100:
            problems.append(f"year {self.year} is out of range")
        if self.month is not None and not 1 <= self.month <= 12:
            problems.append(f"month {self.month} must be 1-12")
        if self.decade is not None and not 1 <= self.decade <= 3:
            problems.append(f"decade {self.decade} must be 1-3")
        sm = self.soil_moisture
        if sm.min_mm is not None and sm.max_mm is not None and sm.min_mm > sm.max_mm:
            problems.append(f"soil_moisture.min_mm {sm.min_mm} is larger than max_mm {sm.max_mm}")
        for c in self.crops:
            if c.bbch_stage is not None and not 0 <= c.bbch_stage <= 9:
                problems.append(f"crops[{c.crop}].bbch_stage {c.bbch_stage} must be 0-9")
        if len({c.crop for c in self.crops}) != len(self.crops):
            problems.append("crops: every crop must appear once")

        # With the source text in the context: deterministic checks of numbers and dates
        # (agro/extract/checks.py): mm and Mt values next to their unit, year / month / decade
        # written in the text.
        text = (info.context or {}).get("text") if info else None
        if text:
            from .checks import fact_problems
            problems += fact_problems(self, text)
        if problems:
            raise ValueError("; ".join(problems))
        return self


def json_schema() -> dict:
    """JSON schema for structured output (strict mode: every field required, no extra keys)."""
    return AgroReport.model_json_schema()
