from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from operational_variance_toolkit.analysis.statistical_config import load_analysis_config
from operational_variance_toolkit.analysis.statistics import (
    build_design_matrix,
    calculate_attenuation,
    fit_selector_model,
    wilson_interval,
)
from operational_variance_toolkit.errors import ConfigurationError

CONFIG_PATH = Path(__file__).parents[1] / "configs" / "phase5_analysis.toml"


def test_phase5_config_parses_and_validates_frozen_contract():
    config = load_analysis_config(CONFIG_PATH)

    assert config.contract_version == "1.0.0"
    assert config.target_selector_id == "OP-0002"
    assert config.operational_condition.aisle_codes == ("A1", "A2", "A3")
    assert config.model.fallback == "linear_probability_hc3"
    assert config.sha256() == load_analysis_config(CONFIG_PATH).sha256()


def test_phase5_config_rejects_invalid_confidence_level(tmp_path):
    invalid = tmp_path / "invalid.toml"
    invalid.write_text(
        CONFIG_PATH.read_text(encoding="utf-8").replace("0.95", "0.79"), encoding="utf-8"
    )

    with pytest.raises(ConfigurationError, match="confidence_level"):
        load_analysis_config(invalid)


def test_wilson_interval_matches_hand_calculated_95_percent_interval():
    lower, upper = wilson_interval(5, 20)
    z = 1.959963984540054
    denominator = 1 + z**2 / 20
    center = (0.25 + z**2 / 40) / denominator
    half_width = z * np.sqrt(0.25 * 0.75 / 20 + z**2 / (4 * 20**2)) / denominator

    assert lower == pytest.approx(center - half_width)
    assert upper == pytest.approx(center + half_width)


def test_attenuation_returns_absolute_and_proportional_arithmetic():
    assert calculate_attenuation(0.40, 0.10) == pytest.approx((0.30, 0.75))
    assert calculate_attenuation(-0.40, -0.10) == pytest.approx((0.30, 0.75))
    assert calculate_attenuation(0.0, 0.2) == (-0.2, 0.0)


def _picks(rows=12):
    frame = pd.DataFrame(
        {
            "selector_id": ["OP-0002" if i % 3 == 0 else "OP-0001" for i in range(rows)],
            "zone_code": ["CHILLED" if i % 3 else "AMBIENT" for i in range(rows)],
            "velocity_class": ["A" if i % 3 == 1 else "B" for i in range(rows)],
            "aisle_code": [f"A{(i % 3) + 1}" for i in range(rows)],
            "requested_qty_cases": [2 + (i % 4) for i in range(rows)],
            "active_replenishment_at_pick_flag": [i % 2 for i in range(rows)],
            "shift_code": ["DAY" if i % 4 else "NIGHT" for i in range(rows)],
            "operating_date_local": [f"2026-01-{(i % 4) + 1:02d}" for i in range(rows)],
            "eligible_pick_flag": [1] * rows,
            "short_flag": [int(i % 5 == 0) for i in range(rows)],
            "trip_id": [f"TRIP-{i}" for i in range(rows)],
            "item_id": [f"ITEM-{i % 5}" for i in range(rows)],
        }
    )
    frame["target_selector"] = frame["selector_id"].eq("OP-0002").astype(int)
    frame["operational_condition"] = (
        frame["zone_code"].eq("CHILLED")
        & frame["velocity_class"].eq("A")
        & frame["aisle_code"].isin(["A1", "A2", "A3"])
    ).astype(int)
    return frame


def test_design_matrix_has_expected_grain_rank_and_target_condition_fields():
    config = load_analysis_config(CONFIG_PATH)
    picks = _picks(24)
    matrix = build_design_matrix(picks, config)

    assert len(matrix) == len(picks)
    assert list(matrix.columns) == [
        "const",
        "target_selector",
        "operational_condition",
        "requested_qty_centered",
        "active_replenishment_at_pick_flag",
        "high_velocity",
        "shift_NIGHT",
        "day_index",
    ]
    assert set(matrix["target_selector"]) == {0.0, 1.0}
    assert set(matrix["operational_condition"]) == {0.0, 1.0}
    assert np.linalg.matrix_rank(matrix.to_numpy()) == 6


def test_forced_fallback_is_deterministic_and_reports_linear_probability_model():
    config = load_analysis_config(CONFIG_PATH)
    picks = _picks(40)
    first = fit_selector_model(picks, config, force_fallback=True)
    second = fit_selector_model(picks, config, force_fallback=True)

    assert first.model_kind == "linear_probability"
    assert first.covariance == "HC3"
    assert first.fallback_used is True
    assert first.fallback_reason == "fallback forced for configured diagnostic test"
    assert first.risk_difference == pytest.approx(second.risk_difference)
    assert first.ci_lower == pytest.approx(second.ci_lower)
    assert first.ci_upper == pytest.approx(second.ci_upper)
