"""AgentConfig.from_strategy — the multi-tenant construction path.

Every field a `strategies` row leaves unset must fall back to the env
singleton (`CONFIG`), and the CLI's env path must stay untouched.
"""
import pytest

from alpaca_options_agent.config import (
    ALL_STRATEGY_SLUGS,
    CONFIG,
    STRATEGY_TYPE_SLUGS,
    AgentConfig,
)

CREDS = {"api_key": "K", "secret_key": "S", "paper": True, "baseline_equity": 50_000.0}


def test_row_values_win_over_env_defaults():
    cfg = AgentConfig.from_strategy(
        {
            "universe": ["spy", "aapl"],
            "strategy_types": ["csp"],
            "params": {
                "target_delta": 0.15,
                "min_dte": 30,
                "max_dte": 40,
                "profit_target_pct": 0.6,
                "stop_loss_multiple": 3.0,
            },
            "risk": {"max_concurrent_positions": 3, "min_open_interest": 250},
        },
        CREDS,
    )

    assert cfg.universe == ["SPY", "AAPL"]
    assert cfg.enabled_strategy_types == ["csp"]
    assert (cfg.chain_min_dte, cfg.chain_max_dte) == (30, 40)
    assert cfg.strategy_params.short_delta_target == 0.15
    assert cfg.management.profit_target_pct == 0.6
    assert cfg.management.stop_loss_multiple == 3.0
    assert cfg.risk.max_concurrent_positions == 3
    assert cfg.risk.min_open_interest == 250
    assert cfg.api_key == "K" and cfg.secret_key == "S"
    assert cfg.baseline_equity == 50_000.0
    assert cfg.paper is True


def test_absent_fields_fall_back_to_env_singleton():
    cfg = AgentConfig.from_strategy({}, CREDS)

    assert cfg.universe == list(CONFIG.universe)
    assert cfg.enabled_strategy_types == list(ALL_STRATEGY_SLUGS)
    assert cfg.chain_min_dte == CONFIG.chain_min_dte
    assert cfg.risk.max_risk_per_trade_pct == CONFIG.risk.max_risk_per_trade_pct
    assert cfg.execution.max_slippage_bps == CONFIG.execution.max_slippage_bps
    assert cfg.strategy_params.iv_rank_entry_threshold == CONFIG.strategy_params.iv_rank_entry_threshold
    assert cfg.baseline_equity == 50_000.0  # still from creds


def test_partial_risk_dict_only_overrides_named_keys():
    cfg = AgentConfig.from_strategy({"risk": {"max_bid_ask_spread_pct": 0.05}}, CREDS)

    assert cfg.risk.max_bid_ask_spread_pct == 0.05
    assert cfg.risk.max_single_underlying_exposure_pct == (
        CONFIG.risk.max_single_underlying_exposure_pct
    )


def test_missing_creds_raise():
    with pytest.raises(RuntimeError):
        AgentConfig.from_strategy({}, {"api_key": "", "secret_key": ""})


def test_env_singleton_is_not_mutated_by_from_strategy():
    before = (
        list(CONFIG.universe),
        CONFIG.risk.max_concurrent_positions,
        CONFIG.strategy_params.short_delta_target,
    )
    AgentConfig.from_strategy(
        {"universe": ["tsla"], "risk": {"max_concurrent_positions": 1},
         "params": {"target_delta": 0.99}},
        CREDS,
    )
    after = (
        list(CONFIG.universe),
        CONFIG.risk.max_concurrent_positions,
        CONFIG.strategy_params.short_delta_target,
    )
    assert before == after


def test_strategy_type_slugs_cover_every_enum_value():
    from alpaca_options_agent.strategy.types import StrategyType

    for st in StrategyType:
        assert st.value in STRATEGY_TYPE_SLUGS
