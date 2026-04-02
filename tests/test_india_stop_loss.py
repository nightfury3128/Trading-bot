from unittest.mock import patch

from strategy.india_strategy import (
    classify_india_risk,
    get_india_risk_and_stop_loss,
    get_india_stop_loss,
    handle_sell,
)


def test_india_risk_classification_boundaries():
    # Spec:
    # LOW: volatility < 0.02
    # MEDIUM: volatility < 0.05
    # HIGH: otherwise
    assert classify_india_risk(0.019) == "LOW"
    assert classify_india_risk(0.02) == "MEDIUM"
    assert classify_india_risk(0.049) == "MEDIUM"
    assert classify_india_risk(0.05) == "HIGH"
    assert classify_india_risk(0.10) == "HIGH"


def test_india_stop_loss_assignment_mapping():
    assert get_india_stop_loss("LOW") == 0.50
    assert get_india_stop_loss("MEDIUM") == 0.75
    assert get_india_stop_loss("HIGH") == 0.85


def test_get_india_risk_and_stop_loss_from_volatility():
    risk, stop_loss = get_india_risk_and_stop_loss(0.01)
    assert risk == "LOW"
    assert stop_loss == 0.50

    risk, stop_loss = get_india_risk_and_stop_loss(0.03)
    assert risk == "MEDIUM"
    assert stop_loss == 0.75

    risk, stop_loss = get_india_risk_and_stop_loss(0.06)
    assert risk == "HIGH"
    assert stop_loss == 0.85


def test_india_stop_loss_sell_trigger_for_ns():
    pos = {
        "buy_price": 2500.0,
        "shares": 10.0,
        "risk_level": "HIGH",
        "stop_loss": 0.85,
    }

    # Below threshold (2500 * 0.85 = 2125)
    with patch("strategy.india_strategy.remove_position") as mock_remove, patch(
        "strategy.india_strategy.log_trade"
    ) as mock_log_trade, patch("strategy.india_strategy.log.info") as mock_log_info:
        reason, proceeds = handle_sell("RELIANCE.NS", pos, 2000.0, 0.5)
        assert reason == "STOP_LOSS"
        assert proceeds > 0
        mock_remove.assert_called_once_with("RELIANCE.NS")
        mock_log_info.assert_any_call("Stop loss triggered for RELIANCE.NS")

    # Above threshold -> no STOP_LOSS/MODEL/TAKE_PROFIT should trigger here
    with patch("strategy.india_strategy.remove_position") as mock_remove, patch(
        "strategy.india_strategy.log_trade"
    ) as mock_log_trade:
        reason, proceeds = handle_sell("RELIANCE.NS", pos, 2200.0, 0.5)
        assert reason is None
        assert proceeds == 0.0
        mock_remove.assert_not_called()


def test_stop_loss_logic_is_india_only_ns_suffix():
    pos = {
        "buy_price": 100.0,
        "shares": 10.0,
        "stop_loss": 0.85,
        "risk_level": "HIGH",
    }

    # Would breach stop-loss multiplier, but ticker does not end with ".NS"
    with patch("strategy.india_strategy.remove_position") as mock_remove, patch(
        "strategy.india_strategy.log_trade"
    ) as mock_log_trade:
        reason, proceeds = handle_sell("AAPL", pos, 80.0, 0.5)
        assert reason is None
        assert proceeds == 0.0
        mock_remove.assert_not_called()

