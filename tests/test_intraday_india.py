"""Tests for strategy/intraday_india.py."""
import math
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest
import pytz

IST = pytz.timezone("Asia/Kolkata")


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _make_5m_df(n: int = 40, base_price: float = 1000.0) -> pd.DataFrame:
    """Return a minimal 5-minute OHLCV DataFrame with n rows."""
    prices = [base_price + i * 2 for i in range(n)]
    data = {
        "Open": prices,
        "High": [p + 5 for p in prices],
        "Low": [p - 5 for p in prices],
        "Close": prices,
        "Volume": [1_000_000 + i * 10_000 for i in range(n)],
    }
    idx = pd.date_range("2026-04-06 09:15", periods=n, freq="5min", tz="Asia/Kolkata")
    return pd.DataFrame(data, index=idx)


def _make_daily_df(n: int = 60, base_price: float = 900.0) -> pd.DataFrame:
    """Return a minimal daily OHLCV DataFrame."""
    prices = [base_price + i for i in range(n)]
    data = {
        "Open": prices,
        "High": [p + 10 for p in prices],
        "Low": [p - 10 for p in prices],
        "Close": prices,
        "Volume": [500_000] * n,
    }
    idx = pd.date_range("2025-01-01", periods=n, freq="B")
    return pd.DataFrame(data, index=idx)


def _ist_time(hour: int, minute: int = 0) -> datetime:
    return IST.localize(datetime(2026, 4, 6, hour, minute))


# ──────────────────────────────────────────────────────────────────────────────
# time_factor
# ──────────────────────────────────────────────────────────────────────────────

class TestTimeFactor:
    def setup_method(self):
        from strategy.intraday_india import time_factor
        self.time_factor = time_factor

    def test_very_early_open(self):
        assert self.time_factor(_ist_time(9, 20)) == 0.50

    def test_early_session(self):
        assert self.time_factor(_ist_time(9, 45)) == 0.70

    def test_strong_morning(self):
        assert self.time_factor(_ist_time(11, 0)) == 1.00

    def test_midday(self):
        assert self.time_factor(_ist_time(12, 0)) == 0.85

    def test_strong_afternoon(self):
        assert self.time_factor(_ist_time(14, 0)) == 1.00

    def test_pre_eod(self):
        assert self.time_factor(_ist_time(14, 45)) == 0.80

    def test_eod_zone(self):
        assert self.time_factor(_ist_time(15, 10)) == 0.60

    def test_naive_datetime_treated_as_ist(self):
        # A naive datetime at 11:00 should still return 1.0
        t = datetime(2026, 4, 6, 11, 0)
        assert self.time_factor(t) == 1.00


# ──────────────────────────────────────────────────────────────────────────────
# compute_intraday_features
# ──────────────────────────────────────────────────────────────────────────────

class TestComputeIntradayFeatures:
    def setup_method(self):
        from strategy.intraday_india import compute_intraday_features
        self.fn = compute_intraday_features

    def test_columns_added(self):
        df = _make_5m_df(40)
        out = self.fn(df)
        for col in ("vwap", "momentum", "rolling_avg_volume", "returns", "volatility"):
            assert col in out.columns, f"Missing column: {col}"

    def test_vwap_positive(self):
        df = _make_5m_df(40)
        out = self.fn(df)
        assert (out["vwap"].dropna() > 0).all()

    def test_input_not_mutated(self):
        df = _make_5m_df(40)
        original_cols = list(df.columns)
        self.fn(df)
        assert list(df.columns) == original_cols


# ──────────────────────────────────────────────────────────────────────────────
# should_buy
# ──────────────────────────────────────────────────────────────────────────────

class TestShouldBuy:
    def setup_method(self):
        import strategy.intraday_india as mod
        self.mod = mod
        # Clear state before each test
        mod._intraday_positions.clear()
        mod._last_trade_time.clear()

    def _featured_df(self, price_above_vwap: bool = True, momentum_pos: bool = True,
                     high_vol: bool = True):
        df = _make_5m_df(40)
        df = self.mod.compute_intraday_features(df)
        # Manipulate last row to control conditions
        last_idx = df.index[-1]
        close = float(df.at[last_idx, "Close"])
        vwap = float(df.at[last_idx, "vwap"])

        if price_above_vwap:
            df.at[last_idx, "vwap"] = close * 0.99  # price > vwap
        else:
            df.at[last_idx, "vwap"] = close * 1.01  # price < vwap

        df.at[last_idx, "momentum"] = 0.01 if momentum_pos else -0.01

        avg_vol = float(df.at[last_idx, "rolling_avg_volume"])
        if high_vol:
            df.at[last_idx, "Volume"] = avg_vol * 1.5
        else:
            df.at[last_idx, "Volume"] = avg_vol * 0.5

        df.at[last_idx, "volatility"] = 0.01  # low volatility
        return df

    def test_all_conditions_met_returns_buy(self):
        df = self._featured_df()
        ok, score, reason = self.mod.should_buy("TEST.NS", df, 0.5, _ist_time(11, 0))
        assert ok is True
        assert score > 0

    def test_below_vwap_no_buy(self):
        df = self._featured_df(price_above_vwap=False)
        ok, _, reason = self.mod.should_buy("TEST.NS", df, 0.5, _ist_time(11, 0))
        assert ok is False
        assert "VWAP" in reason

    def test_negative_momentum_no_buy(self):
        df = self._featured_df(momentum_pos=False)
        ok, _, reason = self.mod.should_buy("TEST.NS", df, 0.5, _ist_time(11, 0))
        assert ok is False
        assert "MOMENTUM" in reason

    def test_low_volume_no_buy(self):
        df = self._featured_df(high_vol=False)
        ok, _, reason = self.mod.should_buy("TEST.NS", df, 0.5, _ist_time(11, 0))
        assert ok is False
        assert "VOLUME" in reason

    def test_already_held_no_buy(self):
        df = self._featured_df()
        self.mod._intraday_positions["TEST.NS"] = {"shares": 10}
        ok, _, reason = self.mod.should_buy("TEST.NS", df, 0.5, _ist_time(11, 0))
        assert ok is False
        assert "ALREADY_HELD" in reason

    def test_cooldown_no_buy(self):
        df = self._featured_df()
        now = _ist_time(11, 0)
        self.mod._last_trade_time["TEST.NS"] = now - timedelta(minutes=5)
        ok, _, reason = self.mod.should_buy("TEST.NS", df, 0.5, now)
        assert ok is False
        assert "COOLDOWN" in reason

    def test_high_volatility_no_buy(self):
        df = self._featured_df()
        df.at[df.index[-1], "volatility"] = 0.06
        ok, _, reason = self.mod.should_buy("TEST.NS", df, 0.5, _ist_time(11, 0))
        assert ok is False
        assert "VOLATILITY" in reason

    def test_insufficient_data_no_buy(self):
        df = _make_5m_df(5)
        ok, _, reason = self.mod.should_buy("TEST.NS", df, 0.5, _ist_time(11, 0))
        assert ok is False
        assert "INSUFFICIENT_DATA" in reason

    def test_time_factor_applied_to_score(self):
        df = self._featured_df()
        # At 9:20 time_factor = 0.5; model_score = 0.1 → final_score = 0.05
        ok, score, _ = self.mod.should_buy("TEST.NS", df, 0.1, _ist_time(9, 20))
        # At early time factor = 0.5 so score = 0.05, but still > 0 should return ok
        # (unless other conditions fail)
        assert math.isclose(score, 0.05, rel_tol=1e-6)


# ──────────────────────────────────────────────────────────────────────────────
# should_sell_intraday
# ──────────────────────────────────────────────────────────────────────────────

class TestShouldSellIntraday:
    def setup_method(self):
        from strategy.intraday_india import should_sell_intraday
        self.fn = should_sell_intraday

    def _pos(self, entry: float = 1000.0) -> dict:
        return {"entry_price": entry, "buy_price": entry, "shares": 10.0}

    def test_stop_loss_triggered(self):
        pos = self._pos(1000.0)
        sell, reason = self.fn("T.NS", pos, 975.0, None)
        assert sell is True
        assert "STOP_LOSS" in reason

    def test_profit_target_triggered(self):
        pos = self._pos(1000.0)
        sell, reason = self.fn("T.NS", pos, 1025.0, None)
        assert sell is True
        assert "PROFIT_TARGET" in reason

    def test_below_vwap_triggered(self):
        df = _make_5m_df(40)
        from strategy.intraday_india import compute_intraday_features
        df = compute_intraday_features(df)
        # Force price below VWAP
        last_idx = df.index[-1]
        df.at[last_idx, "vwap"] = float(df.at[last_idx, "Close"]) * 1.05
        pos = self._pos(float(df.at[last_idx, "Close"]))
        sell, reason = self.fn("T.NS", pos, float(df.at[last_idx, "Close"]), df)
        assert sell is True
        assert "VWAP" in reason

    def test_no_sell_when_profitable_above_vwap(self):
        df = _make_5m_df(40)
        from strategy.intraday_india import compute_intraday_features
        df = compute_intraday_features(df)
        # Force price above VWAP, within profit band
        last_idx = df.index[-1]
        df.at[last_idx, "vwap"] = float(df.at[last_idx, "Close"]) * 0.99
        pos = self._pos(float(df.at[last_idx, "Close"]) * 1.005)
        sell, _ = self.fn("T.NS", pos, float(df.at[last_idx, "Close"]), df)
        assert sell is False


# ──────────────────────────────────────────────────────────────────────────────
# evaluate_eod_conversion
# ──────────────────────────────────────────────────────────────────────────────

class TestEodConversion:
    def setup_method(self):
        from strategy.intraday_india import evaluate_eod_conversion
        self.fn = evaluate_eod_conversion

    def _pos(self, entry: float) -> dict:
        return {"entry_price": entry, "buy_price": entry, "shares": 5.0}

    def test_converts_when_all_conditions_met(self):
        daily_df = _make_daily_df(60, base_price=900.0)
        # entry below current → pnl > 1%
        entry = 1050.0
        current = 1065.0
        pos = self._pos(entry)
        decision, metrics = self.fn("X.NS", pos, current, daily_df, 0.75)
        assert decision == "CONVERT"
        assert metrics["pnl"] > 0.01

    def test_exits_when_pnl_too_low(self):
        daily_df = _make_daily_df(60, base_price=900.0)
        entry = 1000.0
        current = 1002.0  # only 0.2% pnl
        pos = self._pos(entry)
        decision, _ = self.fn("X.NS", pos, current, daily_df, 0.75)
        assert decision == "EXIT"

    def test_exits_when_confidence_low(self):
        daily_df = _make_daily_df(60, base_price=900.0)
        entry = 1000.0
        current = 1020.0  # 2% pnl
        pos = self._pos(entry)
        decision, _ = self.fn("X.NS", pos, current, daily_df, 0.4)
        assert decision == "EXIT"

    def test_exits_when_no_daily_data(self):
        entry = 1000.0
        current = 1020.0
        pos = self._pos(entry)
        decision, metrics = self.fn("X.NS", pos, current, None, 0.8)
        assert decision == "EXIT"
        assert metrics["price_vs_ma20"] is False
        assert metrics["ma20_vs_ma50"] is False


# ──────────────────────────────────────────────────────────────────────────────
# is_eod_window
# ──────────────────────────────────────────────────────────────────────────────

class TestIsEodWindow:
    def setup_method(self):
        from strategy.intraday_india import is_eod_window
        self.fn = is_eod_window

    def test_inside_eod_window(self):
        assert self.fn(_ist_time(15, 18)) is True

    def test_before_eod_window(self):
        assert self.fn(_ist_time(14, 0)) is False

    def test_after_eod_window(self):
        assert self.fn(_ist_time(15, 30)) is False


# ──────────────────────────────────────────────────────────────────────────────
# capital helpers
# ──────────────────────────────────────────────────────────────────────────────

class TestCapitalHelpers:
    def setup_method(self):
        import strategy.intraday_india as mod
        self.mod = mod
        mod._intraday_positions.clear()

    def test_capital_limit_is_30_percent(self):
        limit = self.mod.get_intraday_capital_limit(100_000.0)
        assert math.isclose(limit, 30_000.0)

    def test_exposure_sums_positions(self):
        self.mod._intraday_positions["A.NS"] = {"entry_price": 100.0, "shares": 10.0}
        self.mod._intraday_positions["B.NS"] = {"entry_price": 200.0, "shares": 5.0}
        prices = {"A.NS": 110.0, "B.NS": 210.0}
        exposure = self.mod.get_current_intraday_exposure(prices)
        assert math.isclose(exposure, 110.0 * 10 + 210.0 * 5)

    def test_exposure_uses_entry_price_as_fallback(self):
        self.mod._intraday_positions["C.NS"] = {"entry_price": 500.0, "shares": 2.0}
        exposure = self.mod.get_current_intraday_exposure({})
        assert math.isclose(exposure, 500.0 * 2)


# ──────────────────────────────────────────────────────────────────────────────
# handle_intraday_buy / handle_intraday_sell (integration)
# ──────────────────────────────────────────────────────────────────────────────

class TestHandleIntradayBuy:
    def setup_method(self):
        import strategy.intraday_india as mod
        self.mod = mod
        mod._intraday_positions.clear()
        mod._last_trade_time.clear()

    def _featured_df_buy_signal(self) -> pd.DataFrame:
        df = _make_5m_df(40)
        df = self.mod.compute_intraday_features(df)
        last_idx = df.index[-1]
        close = float(df.at[last_idx, "Close"])
        df.at[last_idx, "vwap"] = close * 0.98
        df.at[last_idx, "momentum"] = 0.02
        avg_vol = float(df.at[last_idx, "rolling_avg_volume"])
        df.at[last_idx, "Volume"] = avg_vol * 2
        df.at[last_idx, "volatility"] = 0.01
        return df

    @patch("strategy.intraday_india.add_position")
    @patch("strategy.intraday_india.log_trade")
    def test_buy_registers_position(self, mock_log_trade, mock_add_position):
        df = self._featured_df_buy_signal()
        shares, spent = self.mod.handle_intraday_buy(
            "RELIANCE.NS", df, 0.5, 500_000.0, _ist_time(11, 0)
        )
        assert shares > 0
        assert spent > 0
        assert "RELIANCE.NS" in self.mod._intraday_positions
        mock_add_position.assert_called_once()
        mock_log_trade.assert_called_once()

    @patch("strategy.intraday_india.add_position")
    @patch("strategy.intraday_india.log_trade")
    def test_buy_respects_capital_limit(self, mock_log_trade, mock_add_position):
        df = self._featured_df_buy_signal()
        shares, spent = self.mod.handle_intraday_buy(
            "TEST.NS", df, 0.5, 1.0, _ist_time(11, 0)  # Only 1 INR available
        )
        assert shares == 0.0
        assert spent == 0.0


class TestHandleIntradaySell:
    def setup_method(self):
        import strategy.intraday_india as mod
        self.mod = mod
        mod._intraday_positions.clear()
        mod._last_trade_time.clear()

    @patch("strategy.intraday_india.remove_position")
    @patch("strategy.intraday_india.log_trade")
    def test_stop_loss_closes_position(self, mock_log_trade, mock_remove):
        self.mod._intraday_positions["X.NS"] = {
            "entry_price": 1000.0, "shares": 10.0
        }
        pos = {"entry_price": 1000.0, "buy_price": 1000.0, "shares": 10.0}
        reason, proceeds = self.mod.handle_intraday_sell(
            "X.NS", pos, 970.0, None, _ist_time(12, 0)
        )
        assert reason == "INTRADAY_STOP_LOSS"
        assert proceeds > 0
        assert "X.NS" not in self.mod._intraday_positions
        mock_remove.assert_called_once_with("X.NS")

    def test_no_sell_within_bands(self):
        self.mod._intraday_positions["Y.NS"] = {
            "entry_price": 1000.0, "shares": 5.0
        }
        pos = {"entry_price": 1000.0, "buy_price": 1000.0, "shares": 5.0}
        # price within ±1 %
        reason, proceeds = self.mod.handle_intraday_sell(
            "Y.NS", pos, 1005.0, None, _ist_time(12, 0)
        )
        assert reason is None
        assert proceeds == 0.0
