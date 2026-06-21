"""
test_db_consistency.py
=======================
Runs a battery of integrity / consistency checks against library.db.
Run with:  python test_db_consistency.py
Exits non-zero if any check fails.
"""
import sqlite3
import sys
from datetime import datetime

DB = "library.db"
errors = []
warnings = []


def check(label, cursor_rows, formatter=lambda r: str(dict(r))):
    """If cursor_rows (a list) is non-empty, record it as a failure."""
    if cursor_rows:
        errors.append(f"[FAIL] {label}: {len(cursor_rows)} row(s)")
        for r in cursor_rows[:10]:
            errors.append(f"        {formatter(r)}")
        if len(cursor_rows) > 10:
            errors.append(f"        ... and {len(cursor_rows)-10} more")
    else:
        print(f"[OK]   {label}")


def main():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    cur = conn.cursor()

    # 0. SQLite's own integrity & foreign-key checks
    integrity = cur.execute("PRAGMA integrity_check").fetchall()
    if integrity and integrity[0][0] == "ok":
        print("[OK]   PRAGMA integrity_check")
    else:
        errors.append(f"[FAIL] PRAGMA integrity_check: {integrity}")

    fk_violations = cur.execute("PRAGMA foreign_key_check").fetchall()
    check("PRAGMA foreign_key_check (no orphaned FK rows)", fk_violations)

    # 1. Orphan rows: borrow_history referencing missing members/books
    rows = cur.execute("""
        SELECT bh.id FROM borrow_history bh
        LEFT JOIN members m ON m.id = bh.member_id
        WHERE m.id IS NULL
    """).fetchall()
    check("borrow_history -> members orphan check", rows)

    rows = cur.execute("""
        SELECT bh.id FROM borrow_history bh
        LEFT JOIN books b ON b.id = bh.book_id
        WHERE b.id IS NULL
    """).fetchall()
    check("borrow_history -> books orphan check", rows)

    rows = cur.execute("""
        SELECT r.id FROM ratings r
        LEFT JOIN members m ON m.id = r.member_id
        WHERE m.id IS NULL
    """).fetchall()
    check("ratings -> members orphan check", rows)

    rows = cur.execute("""
        SELECT r.id FROM ratings r
        LEFT JOIN books b ON b.id = r.book_id
        WHERE b.id IS NULL
    """).fetchall()
    check("ratings -> books orphan check", rows)

    rows = cur.execute("""
        SELECT rv.id FROM reservations rv
        LEFT JOIN members m ON m.id = rv.member_id
        WHERE m.id IS NULL
    """).fetchall()
    check("reservations -> members orphan check", rows)

    rows = cur.execute("""
        SELECT rv.id FROM reservations rv
        LEFT JOIN books b ON b.id = rv.book_id
        WHERE b.id IS NULL
    """).fetchall()
    check("reservations -> books orphan check", rows)

    rows = cur.execute("""
        SELECT pt.id FROM preference_tags pt
        LEFT JOIN members m ON m.id = pt.member_id
        WHERE m.id IS NULL
    """).fetchall()
    check("preference_tags -> members orphan check", rows)

    # 2. Books: available_copies must be between 0 and total_copies
    rows = cur.execute("""
        SELECT id, title, total_copies, available_copies FROM books
        WHERE available_copies < 0 OR available_copies > total_copies
    """).fetchall()
    check("books.available_copies within [0, total_copies]", rows,
          lambda r: f"id={r['id']} title={r['title']!r} total={r['total_copies']} available={r['available_copies']}")

    rows = cur.execute("SELECT id, title, total_copies FROM books WHERE total_copies < 1").fetchall()
    check("books.total_copies >= 1", rows)

    # 3. Cross-check available_copies against actual active borrow_history rows
    #    available_copies should equal total_copies - (count of 'borrowed' rows for that book)
    mismatch = []
    for book in cur.execute("SELECT id, title, total_copies, available_copies FROM books").fetchall():
        active = cur.execute(
            "SELECT COUNT(*) c FROM borrow_history WHERE book_id=? AND status='borrowed'",
            (book["id"],),
        ).fetchone()["c"]
        expected_available = book["total_copies"] - active
        if expected_available != book["available_copies"]:
            mismatch.append({
                "book_id": book["id"], "title": book["title"],
                "total_copies": book["total_copies"],
                "active_borrows": active,
                "expected_available": expected_available,
                "actual_available": book["available_copies"],
            })
    check("books.available_copies matches (total - active borrows)", mismatch, lambda r: str(r))

    # 4. borrow_history status must be valid enum
    rows = cur.execute("""
        SELECT id, status FROM borrow_history WHERE status NOT IN ('borrowed','returned')
    """).fetchall()
    check("borrow_history.status in ('borrowed','returned')", rows)

    # 5. borrow_history: 'returned' rows must have a return_date; 'borrowed' rows must NOT
    rows = cur.execute("""
        SELECT id, status, return_date FROM borrow_history
        WHERE status='returned' AND (return_date IS NULL OR return_date = '')
    """).fetchall()
    check("returned borrow_history rows have a return_date", rows)

    rows = cur.execute("""
        SELECT id, status, return_date FROM borrow_history
        WHERE status='borrowed' AND return_date IS NOT NULL AND return_date != ''
    """).fetchall()
    check("active 'borrowed' rows have NO return_date", rows)

    # 6. Date sanity: return_date >= borrow_date, due_date >= borrow_date
    rows = cur.execute("""
        SELECT id, borrow_date, return_date FROM borrow_history
        WHERE return_date IS NOT NULL AND return_date != '' AND date(return_date) < date(borrow_date)
    """).fetchall()
    check("return_date >= borrow_date", rows)

    rows = cur.execute("""
        SELECT id, borrow_date, due_date FROM borrow_history
        WHERE due_date IS NOT NULL AND due_date != '' AND date(due_date) < date(borrow_date)
    """).fetchall()
    check("due_date >= borrow_date", rows)

    # No future-dated borrows
    today = datetime.now().date().isoformat()
    rows = cur.execute("SELECT id, borrow_date FROM borrow_history WHERE date(borrow_date) > date(?)", (today,)).fetchall()
    check("no borrow_date in the future", rows)

    # 7. A member should not have two simultaneous *active* ('borrowed') loans
    #    of the *same* book (duplicate active loan = data bug)
    rows = cur.execute("""
        SELECT member_id, book_id, COUNT(*) c
        FROM borrow_history
        WHERE status='borrowed'
        GROUP BY member_id, book_id
        HAVING c > 1
    """).fetchall()
    check("no duplicate ACTIVE borrow rows for same member+book", rows)

    # 8. Ratings: value must be 1-5
    rows = cur.execute("SELECT id, rating FROM ratings WHERE rating < 1 OR rating > 5").fetchall()
    check("ratings.rating within 1..5", rows)

    # 9. Ratings: a member should have at most ONE rating per book (app does upsert, not insert-only)
    rows = cur.execute("""
        SELECT member_id, book_id, COUNT(*) c FROM ratings
        GROUP BY member_id, book_id HAVING c > 1
    """).fetchall()
    check("no duplicate ratings for same member+book", rows)

    # 10. Reservations: status must be valid enum
    rows = cur.execute("""
        SELECT id, status FROM reservations WHERE status NOT IN ('pending','fulfilled','cancelled')
    """).fetchall()
    check("reservations.status in ('pending','fulfilled','cancelled')", rows)

    # 11. Members: emails unique (schema enforces UNIQUE, but verify) + non-empty
    rows = cur.execute("""
        SELECT email, COUNT(*) c FROM members GROUP BY lower(email) HAVING c > 1
    """).fetchall()
    check("members.email unique (case-insensitive)", rows)

    rows = cur.execute("SELECT id FROM members WHERE email IS NULL OR trim(email) = ''").fetchall()
    check("members.email non-empty", rows)

    rows = cur.execute("SELECT id FROM members WHERE role NOT IN ('member','admin')").fetchall()
    check("members.role in ('member','admin')", rows)

    # password_hash should never be empty / plaintext-looking (werkzeug hashes start with method id)
    rows = cur.execute("""
        SELECT id, email FROM members
        WHERE password_hash IS NULL OR trim(password_hash) = ''
    """).fetchall()
    check("members.password_hash non-empty", rows)

    rows = cur.execute("""
        SELECT id, email, password_hash FROM members
        WHERE password_hash NOT LIKE 'pbkdf2:%' AND password_hash NOT LIKE 'scrypt:%'
    """).fetchall()
    check("members.password_hash looks properly hashed (not plaintext)", rows,
          lambda r: f"id={r['id']} email={r['email']}")

    # 12. preference_tags: weight should be within 0..1, unique per (member, genre)
    rows = cur.execute("SELECT id, weight FROM preference_tags WHERE weight < 0 OR weight > 1.0001").fetchall()
    check("preference_tags.weight within 0..1", rows)

    rows = cur.execute("""
        SELECT member_id, genre, COUNT(*) c FROM preference_tags
        GROUP BY member_id, genre HAVING c > 1
    """).fetchall()
    check("preference_tags unique per (member, genre)", rows)

    # 13. books required fields non-empty
    rows = cur.execute("SELECT id FROM books WHERE trim(title)='' OR trim(author)='' OR trim(genre)=''").fetchall()
    check("books.title/author/genre non-empty", rows)

    # 14. No admin accidentally double-counted as 'member' role with borrow history issues, etc.
    admin_count = cur.execute("SELECT COUNT(*) c FROM members WHERE role='admin'").fetchone()["c"]
    if admin_count >= 1:
        print(f"[OK]   at least one admin account exists ({admin_count})")
    else:
        errors.append("[FAIL] no admin account found")

    # 15. Run the actual recommender against every member to make sure it
    #     doesn't throw, and returns sane scores (0..~1 range, sorted desc).
    sys.path.insert(0, ".")
    import recommender
    member_ids = [r["id"] for r in cur.execute("SELECT id FROM members WHERE role='member'").fetchall()]
    rec_errors = []
    for mid in member_ids:
        try:
            recs = recommender.get_recommendations(conn, mid)
            scores = [r["score"] for r in recs]
            if scores != sorted(scores, reverse=True):
                rec_errors.append(f"member {mid}: scores not sorted descending: {scores}")
            for r in recs:
                if r["score"] < 0:
                    rec_errors.append(f"member {mid}: negative score {r['score']} for book {r['book']['title']}")
                # currently-borrowed books must never be recommended
            currently_borrowed = {
                row["book_id"] for row in cur.execute(
                    "SELECT book_id FROM borrow_history WHERE member_id=? AND status='borrowed'", (mid,)
                ).fetchall()
            }
            for r in recs:
                if r["book"]["id"] in currently_borrowed:
                    rec_errors.append(f"member {mid}: recommended a currently-borrowed book {r['book']['title']}")
        except Exception as e:
            rec_errors.append(f"member {mid}: exception {e!r}")
    conn.rollback()  # recommender writes preference_tags; don't let test runs mutate seed data permanently in weird ways
    check("recommender.get_recommendations runs cleanly for every member", rec_errors, lambda r: r)

    # 16. preference_tags table should now be populated (recommender just ran for everyone)
    tag_count = cur.execute("SELECT COUNT(*) c FROM preference_tags").fetchone()["c"]
    if tag_count > 0:
        print(f"[OK]   preference_tags populated after recommender run ({tag_count} rows)")
    else:
        errors.append("[FAIL] preference_tags empty after recommender run")

    conn.close()

    print("\n" + "=" * 60)
    if errors:
        print(f"RESULT: {len(errors)} issue line(s) found\n")
        for e in errors:
            print(e)
        sys.exit(1)
    else:
        print("RESULT: ALL CONSISTENCY CHECKS PASSED ✅")
        sys.exit(0)


if __name__ == "__main__":
    main()
