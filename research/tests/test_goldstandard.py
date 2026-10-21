from src.goldstandard import shown_order


RATINGS = {"a": 5.0, "b": 3.0, "c": 5.0, "d": 1.0, "e": 3.0}


def test_best_and_worst_first_follow_ratings():
    best = shown_order(RATINGS, "best_first", 1, "r")
    worst = shown_order(RATINGS, "worst_first", 1, "r")
    assert [RATINGS[p] for p in best] == sorted(RATINGS.values(), reverse=True)
    assert [RATINGS[p] for p in worst] == sorted(RATINGS.values())


def test_orders_are_seeded():
    assert shown_order(RATINGS, "shuffled", 1, "r") == shown_order(RATINGS, "shuffled", 1, "r")
    assert sorted(shown_order(RATINGS, "shuffled", 2, "r")) == sorted(RATINGS)
