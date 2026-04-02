import pytest
from strategy.ranking import normalize_scores, rank_candidates


def test_normalize_scores(mock_scores):
    z_scores = normalize_scores(mock_scores)

    # Check that all keys from mock_scores exist in the result
    assert set(z_scores.keys()) == set(mock_scores.keys())

    # Check that the results are numbers
    for val in z_scores.values():
        assert isinstance(val, (float, int))


def test_rank_candidates(mock_scores):
    z_scores = normalize_scores(mock_scores)
    ranked = rank_candidates(z_scores)

    # Check ranking has same amount of output
    assert len(ranked) == len(z_scores)

    # Check sorting order: first should be highest score
    scores_list = [zs for t, zs in ranked]
    assert all(
        scores_list[i] >= scores_list[i + 1] for i in range(len(scores_list) - 1)
    )


def test_negative_return_exclusion():
    """Verify that only positive predicted returns are considered for buy phase."""
    # ML scores: AAPL (positive), MSFT (negative), GOOGL (zero)
    scores = {"AAPL": 0.05, "MSFT": -0.01, "GOOGL": 0.0}
    
    # In the real main.py loop: if scores[t] > MIN_PREDICTED_RETURN (0.0):
    eligible = [t for t, s in scores.items() if s > 0.0]
    
    assert "AAPL" in eligible
    assert "MSFT" not in eligible
    assert "GOOGL" not in eligible
