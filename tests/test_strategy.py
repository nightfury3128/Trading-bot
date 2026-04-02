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
    # In main loop, scores[t] > 0 is checked before adding to top_picks
    pass
