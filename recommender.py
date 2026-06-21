"""
recommender.py
================
Implements the two core algorithms described in Chapter 1 & 2 of the
proposal:

1. USER-PREFERENCE TAGGING
   Automatically assigns genre/subject weights to a member's profile based
   on their borrowing history and star ratings.

2. WEIGHT-AND-RANK (W&R) SCORING ALGORITHM
   Combines four weighted factors to rank candidate books for the
   personalised "For You" section:
        - Genre match      (from preference tags)      weight 0.45
        - Peer rating       (average rating of the book) weight 0.25
        - Popularity/frequency (recent borrow count)     weight 0.15
        - Recency decay     (favours the member's recent taste shifts,
                              baked into how preference tags are built)   0.15

A recency-decay half-life of 180 days is applied so that older borrowing
activity contributes less to a member's genre weight than recent activity,
per Koren's (2010) temporal-dynamics finding cited in the literature review.
"""

import math
from datetime import datetime, date

HALF_LIFE_DAYS = 180          # recency decay half-life
TOP_N_RECOMMENDATIONS = 8     # per Herlocker et al. (2000) finding cited in proposal

W_GENRE = 0.45
W_RATING = 0.25
W_POPULARITY = 0.15
W_RECENCY_BONUS = 0.15


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _recency_decay(event_date, today=None):
    """Exponential decay: weight halves every HALF_LIFE_DAYS."""
    if event_date is None:
        return 0.3  # unknown date -> mild weight
    today = today or date.today()
    days_ago = max((today - event_date).days, 0)
    return math.pow(0.5, days_ago / HALF_LIFE_DAYS)


def rebuild_preference_tags(db, member_id):
    """
    USER-PREFERENCE TAGGING MODULE
    Recomputes a member's genre weights from borrow_history + ratings and
    persists them into preference_tags so they can be inspected/explained
    (e.g. on the member profile page).
    """
    rows = db.execute(
        """
        SELECT b.genre AS genre,
               bh.borrow_date AS event_date,
               NULL AS rating
        FROM borrow_history bh
        JOIN books b ON b.id = bh.book_id
        WHERE bh.member_id = ?
        UNION ALL
        SELECT b.genre AS genre,
               r.created_at AS event_date,
               r.rating AS rating
        FROM ratings r
        JOIN books b ON b.id = r.book_id
        WHERE r.member_id = ?
        """,
        (member_id, member_id),
    ).fetchall()

    genre_scores = {}
    today = date.today()
    for row in rows:
        genre = row["genre"]
        ev_date = _parse_date(row["event_date"])
        decay = _recency_decay(ev_date, today)
        # A star rating amplifies/dampens the signal; an unrated borrow counts as neutral (3/5)
        rating_factor = (row["rating"] if row["rating"] is not None else 3) / 5.0
        genre_scores[genre] = genre_scores.get(genre, 0.0) + decay * rating_factor

    # Normalise to 0..1 range for readability
    max_score = max(genre_scores.values()) if genre_scores else 1.0
    normalised = {g: (s / max_score if max_score else 0) for g, s in genre_scores.items()}

    db.execute("DELETE FROM preference_tags WHERE member_id = ?", (member_id,))
    for genre, weight in normalised.items():
        db.execute(
            "INSERT INTO preference_tags (member_id, genre, weight, updated_at) VALUES (?, ?, ?, ?)",
            (member_id, genre, weight, datetime.now().isoformat(timespec="seconds")),
        )
    db.commit()
    return normalised


def get_recommendations(db, member_id, limit=TOP_N_RECOMMENDATIONS):
    """
    WEIGHT-AND-RANK SCORING ALGORITHM
    Returns up to `limit` books ranked for the member's "For You" section,
    each annotated with a human-readable explanation string.
    """
    genre_weights = rebuild_preference_tags(db, member_id)

    # Books the member currently has out on loan are excluded (no point
    # recommending what they're already reading); previously returned books
    # may still resurface (re-reads / part of a series) at a damped weight.
    currently_borrowed = {
        row["book_id"]
        for row in db.execute(
            "SELECT book_id FROM borrow_history WHERE member_id = ? AND status = 'borrowed'",
            (member_id,),
        ).fetchall()
    }

    books = db.execute("SELECT * FROM books WHERE available_copies > 0").fetchall()

    # Popularity: recent (last 90 days) borrow frequency across all members, per book
    pop_rows = db.execute(
        """
        SELECT book_id, COUNT(*) AS cnt
        FROM borrow_history
        WHERE borrow_date >= date('now', '-90 day')
        GROUP BY book_id
        """
    ).fetchall()
    popularity = {row["book_id"]: row["cnt"] for row in pop_rows}
    max_pop = max(popularity.values()) if popularity else 1

    # Peer rating: average rating per book
    rating_rows = db.execute(
        "SELECT book_id, AVG(rating) AS avg_rating, COUNT(*) AS n FROM ratings GROUP BY book_id"
    ).fetchall()
    avg_ratings = {row["book_id"]: row["avg_rating"] for row in rating_rows}

    scored = []
    max_genre_weight = max(genre_weights.values()) if genre_weights else 0

    for book in books:
        if book["id"] in currently_borrowed:
            continue

        genre_score = genre_weights.get(book["genre"], 0.0)
        rating_score = (avg_ratings.get(book["id"], 3.0)) / 5.0
        pop_score = popularity.get(book["id"], 0) / max_pop if max_pop else 0
        # Small recency-bonus: newly added titles get a modest discovery boost
        added = _parse_date(book["added_at"])
        recency_bonus = _recency_decay(added) * 0.5 if added else 0.1

        final_score = (
            W_GENRE * genre_score
            + W_RATING * rating_score
            + W_POPULARITY * pop_score
            + W_RECENCY_BONUS * recency_bonus
        )

        if genre_score == max_genre_weight and max_genre_weight > 0:
            reason = f"Recommended because you've engaged with {book['genre']} titles"
        elif genre_score > 0:
            reason = f"Because you enjoyed {book['genre']}"
        elif pop_score > 0.5:
            reason = "Trending with other members right now"
        else:
            reason = "Highly rated by the community"

        scored.append({
            "book": book,
            "score": round(final_score, 4),
            "reason": reason,
        })

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:limit]
